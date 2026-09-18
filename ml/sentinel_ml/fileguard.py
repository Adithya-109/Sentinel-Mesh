"""FileGuard: LightGBM on the 54 PE header features.

The dataset-only model is biased: its "benign" class comes from one
Windows install, so it flags ordinary third-party software as malware
(brief section 6). We correct that by folding in benign binaries pulled
from real pip/npm Windows packages (ml/benign/), upweighted so a few
hundred extra rows can outweigh ~97k dataset rows.
"""
import numpy as np
import pandas as pd
import lightgbm as lgb
from sklearn.metrics import accuracy_score, roc_auc_score, roc_curve
from sklearn.model_selection import GroupShuffleSplit

from .data import load_malware, malware_feature_columns, malware_groups
from .reasons import humanize_file_reason

SEED = 42
THIRDPARTY_SAMPLE_WEIGHT = 20.0


def tpr_at_fpr(y, scores, target_fpr):
    fpr, tpr, _ = roc_curve(y, scores)
    return float(np.interp(target_fpr, fpr, tpr))


def threshold_for_max_fpr(y, scores, max_fpr):
    fpr, tpr, thr = roc_curve(y, scores)
    ok = fpr <= max_fpr
    if not ok.any():
        return float(thr[np.argmin(fpr)])
    best = np.argmax(np.where(ok, tpr, -1))
    return float(thr[best])


def _fit(X, y, sample_weight=None):
    return lgb.LGBMClassifier(n_estimators=300, learning_rate=0.05, num_leaves=63, verbose=-1).fit(
        X, y, sample_weight=sample_weight
    )


def load_thirdparty_benign(features_csv: str, cols):
    """Load ml/benign/features/thirdparty_features.csv, aligned to `cols`."""
    df = pd.read_csv(features_csv)
    pkg = df["pkg"]
    X = df.reindex(columns=cols, fill_value=0)
    return X, pkg


def package_holdout_experiment(X_train, y_train, X_test, y_test, B, pkg, cols, n_reps=5, seed=0):
    """Hold out whole third-party packages; does adding them fix false alarms?"""
    pk = np.array(sorted(pkg.unique()))
    rng = np.random.default_rng(seed)
    rows = []
    for _ in range(n_reps):
        rng.shuffle(pk)
        half = set(pk[: len(pk) // 2])
        in_train = pkg.isin(half)
        Btr, Bte = B[in_train], B[~in_train]
        for tag, augment in [("dataset_only", False), ("plus_thirdparty_benign", True)]:
            if augment and len(Btr):
                Xa = pd.concat([X_train, Btr[cols]], ignore_index=True)
                ya = pd.concat([y_train, pd.Series(0, index=range(len(Btr)))], ignore_index=True)
                wa = np.r_[np.ones(len(X_train)), np.full(len(Btr), THIRDPARTY_SAMPLE_WEIGHT)]
            else:
                Xa, ya, wa = X_train, y_train, None
            mdl = _fit(Xa, ya, sample_weight=wa)
            s_test = mdl.predict_proba(X_test[cols])[:, 1] >= 0.5
            rows.append(dict(
                model=tag,
                detection_rate=float(s_test[y_test.values == 1].mean()),
                dataset_false_alarm=float(s_test[y_test.values == 0].mean()),
                unseen_thirdparty_false_alarm=float((mdl.predict_proba(Bte[cols])[:, 1] >= 0.5).mean())
                if len(Bte) else float("nan"),
            ))
    return pd.DataFrame(rows).groupby("model").mean().round(4).to_dict("index")


MIN_REASON_SHAP = 0.05  # log-odds; below this a feature is noise, not a reason


def shap_values(model, x_row):
    """Exact TreeSHAP values for one row, in log-odds, plus the expected value.

    LightGBM's `pred_contrib` runs the same TreeSHAP algorithm as
    `shap.TreeExplainer`, without the numba dependency (parity is tested in
    tests/test_fileguard_shap.py). The values sum, with the base value, to the
    raw margin: sigmoid(base + sum(phi)) is the model's probability.
    """
    contrib = model.booster_.predict(np.asarray(x_row, dtype=float).reshape(1, -1), pred_contrib=True)[0]
    return contrib[:-1], float(contrib[-1])


def _rank(phi, malicious, top_k):
    """Indices of the features that drove the call, strongest first.

    For a malicious verdict that means the features pushing hardest toward
    malicious; for a clean one, toward benign. Ranking by absolute size (the old
    behaviour) let a benign-pointing feature lead a malicious verdict's reasons.
    """
    if malicious is None:
        return list(np.argsort(-np.abs(phi))[:top_k])
    sign = 1.0 if malicious else -1.0
    order = [int(i) for i in np.argsort(-sign * phi) if sign * phi[i] >= MIN_REASON_SHAP][:top_k]
    return order or list(np.argsort(-np.abs(phi))[:top_k])


def explain_detail(model, cols, x_row, malicious=None, top_k=3):
    """Structured explanation: the base value, the margin, and the top-k SHAP contributions."""
    x_row = np.asarray(x_row, dtype=float)
    phi, base = shap_values(model, x_row)
    margin = base + float(phi.sum())
    top = [
        {"feature": cols[i], "value": float(x_row[i]), "shap": round(float(phi[i]), 4),
         "pushes": "malicious" if phi[i] > 0 else "benign"}
        for i in _rank(phi, malicious, top_k)
    ]
    return {"base_value": round(base, 4), "margin": round(margin, 4),
            "probability": round(float(1.0 / (1.0 + np.exp(-margin))), 6), "top": top}


def explain(model, cols, x_row, top_k=3, malicious=None):
    """Plain-English top-k reasons. Pass `malicious` (the verdict) to explain that verdict."""
    detail = explain_detail(model, cols, x_row, malicious=malicious, top_k=top_k)
    return [humanize_file_reason(t["feature"], t["value"], t["shap"]) for t in detail["top"]]


def train(security_root: str, thirdparty_features_csv: str = None, max_false_alarm: float = 0.001, seed: int = SEED):
    """Full FileGuard train + evaluate. Returns (model, cols, threshold, metrics)."""
    m = load_malware(security_root)
    cols = malware_feature_columns(df=m)
    X, y = m[cols], m["label"]
    groups = malware_groups(X)

    metrics = {
        "malware_rows": len(m),
        "malware_share": round(float(y.mean()), 4),
        "malware_rows_with_duplicate_feature_vector": int(groups.duplicated(keep=False).sum()),
    }

    tr_idx, te_idx = next(GroupShuffleSplit(n_splits=1, test_size=0.2, random_state=seed).split(X, y, groups=groups))
    X_tr, y_tr = X.iloc[tr_idx].reset_index(drop=True), y.iloc[tr_idx].reset_index(drop=True)
    X_te, y_te = X.iloc[te_idx].reset_index(drop=True), y.iloc[te_idx].reset_index(drop=True)

    baseline = _fit(X_tr, y_tr)
    s = baseline.predict_proba(X_te)[:, 1]
    p = s >= 0.5
    metrics["malware_group_split"] = dict(
        acc=round(accuracy_score(y_te, p), 4),
        auc=round(roc_auc_score(y_te, s), 5),
        detection_rate=round(float(p[y_te.values == 1].mean()), 4),
        false_alarm=round(float(p[y_te.values == 0].mean()), 4),
        detection_at_0p1pct_false_alarm=round(tpr_at_fpr(y_te, s, 0.001), 4),
    )
    gain = pd.Series(baseline.booster_.feature_importance("gain"), index=cols)
    metrics["malware_top_gain_share"] = (gain / gain.sum()).sort_values(ascending=False).head(5).round(3).to_dict()

    if not thirdparty_features_csv:
        threshold = threshold_for_max_fpr(y_te.values, s, max_false_alarm)
        return baseline, cols, threshold, metrics

    B, pkg = load_thirdparty_benign(thirdparty_features_csv, cols)
    metrics["thirdparty_benign_files"] = len(B)
    metrics["thirdparty_packages"] = int(pkg.nunique())
    metrics["thirdparty_flagged_by_dataset_model"] = round(float((baseline.predict_proba(B[cols])[:, 1] >= 0.5).mean()), 4)
    metrics["thirdparty_experiment_mean_of_5"] = package_holdout_experiment(X_tr, y_tr, X_te, y_te, B, pkg, cols)

    # Final production model: dataset train + ALL benign third-party rows, upweighted.
    Xa = pd.concat([X_tr, B[cols]], ignore_index=True)
    ya = pd.concat([y_tr, pd.Series(0, index=range(len(B)))], ignore_index=True)
    wa = np.r_[np.ones(len(X_tr)), np.full(len(B), THIRDPARTY_SAMPLE_WEIGHT)]
    final = _fit(Xa, ya, sample_weight=wa)

    s_final = final.predict_proba(X_te)[:, 1]
    threshold = threshold_for_max_fpr(y_te.values, s_final, max_false_alarm)
    p_final = s_final >= threshold
    metrics["malware_group_split_final"] = dict(
        threshold=round(threshold, 4),
        acc=round(accuracy_score(y_te, p_final), 4),
        auc=round(roc_auc_score(y_te, s_final), 5),
        detection_rate=round(float(p_final[y_te.values == 1].mean()), 4),
        false_alarm=round(float(p_final[y_te.values == 0].mean()), 4),
        detection_at_0p1pct_false_alarm=round(tpr_at_fpr(y_te, s_final, 0.001), 4),
        thirdparty_false_alarm=round(float((final.predict_proba(B[cols])[:, 1] >= threshold).mean()), 4),
    )
    return final, cols, threshold, metrics
