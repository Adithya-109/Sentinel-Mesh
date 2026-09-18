"""Which of EnergyGate's 8 signals does the model actually need?

SIMULATED. Same data, depth, leaf size and evaluation protocol as the shipped
simulated model (train_energygate_synthetic.py): the tests/generate_synthetic_traces.py
--hard traces (30 sessions, seed 0), a depth-5 tree with min_samples_leaf=20, and
every window scored by a tree that never saw its recording session.

The shipped tree's feature importances say `hs_fail` and `dup_pct` do almost all
the work. This checks that by retraining on feature subsets:

  * all 8                       the shipped feature set
  * hs_fail + dup_pct           just the two features the tree leans on
  * the other 6                 everything except those two: is the signal
                                carried anywhere else?
  * hs_fail only / dup_pct only each alone
  * battery_pct only            a leakage control. In the generator battery_pct is
                                one constant per session, so a model that has not
                                seen the session cannot learn anything real from
                                it: AUC should sit near 0.5.

Read the result as a statement about the *generator*, not about real traffic:
hs_fail and dup_pct matter here because the generator makes attacks produce
failures and duplicates. Real recordings may weight the signals differently.

    python experiments/energygate_ablation.py     # writes reports/energygate_synthetic_ablation.json
"""
import json
import os
import sys
import tempfile

import numpy as np
from sklearn.metrics import brier_score_loss, log_loss, roc_auc_score
from sklearn.tree import DecisionTreeClassifier

HERE = os.path.dirname(os.path.abspath(__file__))
ML = os.path.dirname(HERE)
sys.path.insert(0, ML)
sys.path.insert(0, os.path.join(ML, "tests"))

from sentinel_ml import energygate  # noqa: E402
import generate_synthetic_traces as gen  # noqa: E402

OUT = os.path.join(ML, "reports", "energygate_synthetic_ablation.json")

SYNTH_REAL_LABELS = {"SYNTH_normal", "SYNTH_weak_link"}
DEPTH = 5              # the shipped depth
MIN_SAMPLES_LEAF = 20  # the shipped leaf size (fixed up front, not tuned)
TOP_TWO = ["hs_fail", "dup_pct"]

SUBSETS = {
    "all 8 (shipped)": list(energygate.FEATURE_ORDER),
    "hs_fail + dup_pct": TOP_TWO,
    "the other 6 (without hs_fail, dup_pct)": [f for f in energygate.FEATURE_ORDER if f not in TOP_TWO],
    "hs_fail only": ["hs_fail"],
    "dup_pct only": ["dup_pct"],
    "battery_pct only (leakage control)": ["battery_pct"],
}


def load_simulated(n_sessions=30):
    """Regenerate the shipped simulated dataset into a temp dir (same seed, so identical)."""
    with tempfile.TemporaryDirectory() as tmp:
        gen.main(n_sessions=n_sessions, rows_per_session=120, seed=0, hard=True, out_dir=tmp)
        df = energygate.load_traces(tmp)
    for col, default in energygate.OPTIONAL_DEFAULTS.items():
        df[col] = df[col].fillna(default) if col in df.columns else default
    return df


def out_of_fold(X, y, sessions):
    """Score every session with a tree that never saw it."""
    p = np.zeros(len(y))
    for s in sorted(set(sessions)):
        te = sessions == s
        m = DecisionTreeClassifier(max_depth=DEPTH, min_samples_leaf=MIN_SAMPLES_LEAF, random_state=42)
        p[te] = m.fit(X[~te], y[~te]).predict_proba(X[te])[:, 1]
    return p


def main():
    df = load_simulated()
    y = df["label"].isin(SYNTH_REAL_LABELS).astype(int).values
    sessions = df["session"].values

    results = {}
    for name, cols in SUBSETS.items():
        X = df[cols].values.astype(float)
        p = out_of_fold(X, y, sessions)
        results[name] = dict(
            features=cols,
            auc=round(float(roc_auc_score(y, p)), 4),
            # clip only for log loss so a pure leaf's 0/1 doesn't give infinity
            log_loss=round(float(log_loss(y, np.clip(p, 1e-3, 1 - 1e-3))), 4),
            brier=round(float(brier_score_loss(y, p)), 4),
            accuracy_at_0p5=round(float(((p >= 0.5) == y).mean()), 4),
        )

    report = dict(
        SIMULATED=True,
        note="simulated traces (generate_synthetic_traces.py --hard); a statement about the generator, "
             "not about real traffic; not a result",
        rows=len(df), sessions=int(len(set(sessions))), real_pct=round(float(y.mean()) * 100, 1),
        depth=DEPTH, min_samples_leaf=MIN_SAMPLES_LEAF,
        protocol="leave-one-recording-session-out; every window scored by a tree that never saw its session",
        by_feature_subset=results,
    )
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w") as f:
        json.dump(report, f, indent=2)

    print(f"SIMULATED, {len(df)} windows / {report['sessions']} sessions, depth {DEPTH}")
    print(f"{'feature subset':44s} {'AUC':>6s} {'logloss':>8s} {'acc@0.5':>8s}")
    for name, r in results.items():
        print(f"{name:44s} {r['auc']:6.3f} {r['log_loss']:8.3f} {r['accuracy_at_0p5']:8.3f}")
    print(f"wrote {OUT}")


if __name__ == "__main__":
    main()
