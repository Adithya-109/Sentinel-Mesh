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


def explain(model, cols, x_row, top_k=3):
    """Top-k feature contributions for one row, via LightGBM pred_contrib."""
    contrib = model.booster_.predict(x_row.reshape(1, -1), pred_contrib=True)[0]
    contrib = contrib[:-1]  # drop the bias/expected-value term
    order = np.argsort(-np.abs(contrib))[:top_k]
    return [humanize_file_reason(cols[i], x_row[i], float(contrib[i])) for i in order]


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
