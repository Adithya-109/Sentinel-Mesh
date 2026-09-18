"""Stress-test SMS Guard's shipped numbers. Read-only with respect to the model:
it never writes model.joblib, vectorizer.joblib, manifest.json or metrics.json;
its only output is eval_report.json next to it.

train.py reports one random split (131 spam in the test slice). This adds:

  1. reproduce   Rebuild train.py's exact split and model and check the confusion
                 matrix matches metrics.json, so everything below is about the
                 shipped recipe and not a lookalike.
  2. cv          Repeated stratified 5-fold cross-validation (3 repeats). In every
                 fold the threshold is tuned the way train.py tunes it (a false-alarm
                 target on a held-out slice of that fold's training data), then
                 scored on the fold. Done for the shipped 3% target and stricter 2%
                 and 1% targets. Gives a spread instead of a single number, and a
                 check on the stricter targets that does not reuse the shipped test
                 split.
  3. thresholds  On the shipped test split: threshold tuned on validation for a
                 range of false-alarm targets, then recall / false alarms /
                 precision on test. Also what it would cost to push the threshold
                 high enough to stop the rehearsed `legit_reminder` fixture (score
                 0.895) being flagged.
  4. digits      False-alarm rate on legitimate messages that contain a digit vs
                 those that do not, at the tuned threshold: the model's strongest
                 global features are number/URL placeholders, so this checks
                 whether legitimate messages with numbers are the weak spot.

Same dataset, same scikit-learn recipe (sms_guard.fit), same seed as train.py.
Run with an environment that has scikit-learn 1.8.0 (console/requirements.txt):

    python channels/sms/evaluate.py                  # uses channels/sms/data/SMSSpamCollection
    python channels/sms/evaluate.py --data <path>
"""
import argparse
import json
import math
import os
import re

import numpy as np
from sklearn.model_selection import RepeatedStratifiedKFold, train_test_split

import sms_guard
import train

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "eval_report.json")
SEED = sms_guard.SEED
SHIPPED_MAX_FA = 0.03
CV_TARGETS = (0.03, 0.02, 0.01)   # shipped target first
_DIGIT = re.compile(r"\d")


def wilson(k, n, z=1.96):
    """95% Wilson score interval for k successes in n trials."""
    if n == 0:
        return [None, None]
    p = k / n
    d = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / d
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return [round(centre - half, 4), round(centre + half, 4)]


def counts(y, scores, thr):
    pred = scores >= thr
    tp = int((pred & (y == 1)).sum())
    fp = int((pred & (y == 0)).sum())
    fn = int((~pred & (y == 1)).sum())
    tn = int((~pred & (y == 0)).sum())
    return tp, fp, fn, tn


def rates(y, scores, thr):
    tp, fp, fn, tn = counts(y, scores, thr)
    return dict(
        recall=round(tp / (tp + fn), 4) if tp + fn else None,
        false_alarm=round(fp / (fp + tn), 4) if fp + tn else None,
        precision=round(tp / (tp + fp), 4) if tp + fp else None,
        tp=tp, fp=fp, fn=fn, tn=tn,
    )


def shipped_split(df):
    """train.py's split, verbatim."""
    tr, te = train_test_split(df, test_size=0.2, stratify=df.label, random_state=SEED)
    tr, val = train_test_split(tr, test_size=0.15, stratify=tr.label, random_state=SEED)
    return tr, val, te


def fit_and_tune(train_df, targets=CV_TARGETS):
    """Fit on 85% of train_df and tune one threshold per false-alarm target on the
    other 15%, like train.py. Returns (vec, model, {target: threshold})."""
    fit_part, val = train_test_split(train_df, test_size=0.15, stratify=train_df.label, random_state=SEED)
    vec, model = sms_guard.fit(fit_part.text, fit_part.label)
    s_val = sms_guard.predict_proba(vec, model, val.text)
    return vec, model, {t: train.threshold_for_max_fpr(val.label.values, s_val, t) for t in targets}


def summarize(values):
    a = np.array(values, dtype=float)
    return dict(mean=round(float(a.mean()), 4), std=round(float(a.std(ddof=1)), 4),
                min=round(float(a.min()), 4), max=round(float(a.max()), 4))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--data", default=None, help="SMSSpamCollection file/dir (default: cached copy in data/)")
    ap.add_argument("--repeats", type=int, default=3)
    a = ap.parse_args()

    df = train.load_dataset(a.data)
    y_all = df.label.values
    print(f"{len(df)} messages after dedup: {int(y_all.sum())} spam, {int((y_all == 0).sum())} legitimate")

    # ---- 1. reproduce the shipped model ----------------------------------------
    tr, val, te = shipped_split(df)
    vec, model = sms_guard.fit(tr.text, tr.label)
    s_val = sms_guard.predict_proba(vec, model, val.text)
    s_te = sms_guard.predict_proba(vec, model, te.text)
    thr = train.threshold_for_max_fpr(val.label.values, s_val, SHIPPED_MAX_FA)
    y_te = te.label.values
    tp, fp, fn, tn = counts(y_te, s_te, thr)

    with open(os.path.join(HERE, "metrics.json"), encoding="utf-8") as f:
        shipped = json.load(f)
    cm = shipped["held_out_test_metrics"]["confusion_matrix"]
    shipped_cm = (cm["true_positive_smishing_caught"], cm["false_positive_legit_flagged"],
                  cm["false_negative_smishing_missed"], cm["true_negative_legit_correct"])
    reproduced = dict(
        matches_shipped=bool((tp, fp, fn, tn) == shipped_cm and round(thr, 4) == shipped["threshold"]),
        threshold=round(thr, 4), shipped_threshold=shipped["threshold"],
        confusion_tp_fp_fn_tn=[tp, fp, fn, tn], shipped_confusion_tp_fp_fn_tn=list(shipped_cm),
    )
    print(f"1. reproduce: threshold {thr:.4f} (shipped {shipped['threshold']}), tp/fp/fn/tn {tp}/{fp}/{fn}/{tn} "
          f"(shipped {shipped_cm}) -> {'MATCH' if reproduced['matches_shipped'] else 'MISMATCH'}")

    # ---- 2. repeated stratified 5-fold CV ---------------------------------------
    folds = {t: [] for t in CV_TARGETS}
    pooled = []                     # repeat-0 out-of-fold predictions at the shipped target, for the digit analysis
    rskf = RepeatedStratifiedKFold(n_splits=5, n_repeats=a.repeats, random_state=SEED)
    for i, (tr_idx, te_idx) in enumerate(rskf.split(df.text, df.label)):
        train_df, test_df = df.iloc[tr_idx], df.iloc[te_idx]
        v, m, thrs = fit_and_tune(train_df)
        s = sms_guard.predict_proba(v, m, test_df.text)
        for target, t in thrs.items():
            r = rates(test_df.label.values, s, t)
            r["threshold"] = round(t, 4)
            folds[target].append(r)
        if i < 5:
            t0 = thrs[SHIPPED_MAX_FA]
            pooled.append((test_df.text.values, test_df.label.values, s >= t0))
    cv = dict(splits="5-fold x %d repeats = %d fits" % (a.repeats, len(folds[SHIPPED_MAX_FA])), by_false_alarm_target={})
    print(f"2. CV ({cv['splits']}); threshold tuned per fold on a validation slice:")
    for target, fl in folds.items():
        c = dict(
            recall=summarize([f["recall"] for f in fl]),
            false_alarm=summarize([f["false_alarm"] for f in fl]),
            precision=summarize([f["precision"] for f in fl]),
            threshold=summarize([f["threshold"] for f in fl]),
            per_fold=fl,
        )
        cv["by_false_alarm_target"][str(target)] = c
        tag = " (shipped)" if target == SHIPPED_MAX_FA else ""
        print(f"   target <={target:.0%}{tag}: recall {c['recall']['mean']:.3f} +/- {c['recall']['std']:.3f} "
              f"[{c['recall']['min']:.3f}-{c['recall']['max']:.3f}], false alarm {c['false_alarm']['mean']:.3f} "
              f"+/- {c['false_alarm']['std']:.3f}, precision {c['precision']['mean']:.3f} +/- {c['precision']['std']:.3f} "
              f"[{c['precision']['min']:.3f}-{c['precision']['max']:.3f}]")

    # ---- 3. threshold trade-off on the shipped split ----------------------------
    sweep = []
    for target in (0.005, 0.01, 0.02, 0.03, 0.05, 0.10):
        t = train.threshold_for_max_fpr(val.label.values, s_val, target)
        sweep.append(dict(val_false_alarm_target=target, threshold=round(t, 4), **rates(y_te, s_te, t)))
    fixture_thr = 0.896   # just above the legit_reminder fixture's score (0.895)
    stop_fixture = dict(threshold=fixture_thr, **rates(y_te, s_te, fixture_thr))
    print("3. threshold trade-off (tuned on validation, scored on the held-out test split):")
    for r in sweep:
        print(f"   FA target {r['val_false_alarm_target']:.3f} -> thr {r['threshold']:.3f}: recall {r['recall']:.3f}, "
              f"false alarm {r['false_alarm']:.3f}, precision {r['precision']:.3f}")
    print(f"   threshold {fixture_thr} (needed to stop the legit_reminder fixture being flagged): "
          f"recall {stop_fixture['recall']:.3f}, false alarm {stop_fixture['false_alarm']:.3f}, "
          f"precision {stop_fixture['precision']:.3f}")

    # ---- 4. do digits drive the false alarms? -----------------------------------
    def digit_split(texts, labels, flagged, label):
        has = np.array([bool(_DIGIT.search(t)) for t in texts])
        out = {}
        for name, mask in (("with_digit", has), ("without_digit", ~has)):
            sel = (labels == label) & mask
            n = int(sel.sum())
            k = int(flagged[sel].sum())
            out[name] = dict(n=n, flagged=k, rate=round(k / n, 4) if n else None, ci95=wilson(k, n))
        return out

    texts = np.concatenate([p[0] for p in pooled])
    labels = np.concatenate([p[1] for p in pooled])
    flagged = np.concatenate([p[2] for p in pooled])
    digits = dict(
        note="out-of-fold predictions from repeat 0 of the CV (every message scored once, by a model that never saw it)",
        legitimate=digit_split(texts, labels, flagged, 0),
        spam=digit_split(texts, labels, flagged, 1),
    )
    for lab in ("legitimate", "spam"):
        d = digits[lab]
        print(f"4. digits, {lab:10s}: with a digit {d['with_digit']['flagged']}/{d['with_digit']['n']} flagged "
              f"({d['with_digit']['rate']}), without {d['without_digit']['flagged']}/{d['without_digit']['n']} "
              f"({d['without_digit']['rate']})")

    report = dict(
        note="Read-only evaluation of the shipped SMS Guard recipe; does not modify the model or metrics.json.",
        dataset=dict(messages=int(len(df)), spam=int(y_all.sum()), legitimate=int((y_all == 0).sum())),
        reproduce_shipped_split=reproduced,
        repeated_cv=cv,
        threshold_tradeoff_on_shipped_test_split=sweep,
        threshold_needed_to_stop_legit_reminder_fixture=stop_fixture,
        digits_vs_false_alarms=digits,
    )
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)
    print(f"wrote {OUT}")


if __name__ == "__main__":
    main()
