"""Train EnergyGate on SIMULATED traces and export a header the firmware can
compile in -- for use until real board recordings exist.

The data is ml/tests/generate_synthetic_traces.py --hard: hand-written, but with
overlapping classes, partial/stealthy attacks, measurement noise and 3% label
noise so scores are graded and evaluation is not trivially perfect. It is still
our own assumptions about attacks, so nothing here is a result: the exported
header carries a SIMULATED banner and metrics are flagged SIMULATED.

    python train_energygate_synthetic.py            # writes export/energygate_synthetic.h
    python train_energygate_synthetic.py --firmware # ...and copies it into firmware/

Depth is chosen by out-of-fold log loss over held-out recording sessions (never
by training fit), and the header is parity-checked (gcc vs. sklearn, 500 rows)
before it is written anywhere the firmware can see it. The out-of-fold scores
also drive the operating-point sweep in experiments/energygate_sweep.py.
"""
import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile

import numpy as np
from sklearn.metrics import brier_score_loss, log_loss, roc_auc_score
from sklearn.tree import DecisionTreeClassifier

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "tests"))
sys.path.insert(0, os.path.join(HERE, "experiments"))

from sentinel_ml import energygate  # noqa: E402
import generate_synthetic_traces as gen  # noqa: E402
import energygate_sweep  # noqa: E402
from test_energygate_pipeline import (FEATURE_RANGES, HARNESS_SRC,  # noqa: E402
                                      PROB_TOLERANCE, SYNTH_REAL_LABELS)

TRACE_DIR = os.path.join(HERE, "tests", "synthetic_traces_hard")
EXPORT_PATH = os.path.join(HERE, "export", "energygate_synthetic.h")
METRICS_PATH = os.path.join(HERE, "reports", "energygate_synthetic_metrics.json")
SWEEP_JSON = os.path.join(HERE, "reports", "energygate_synthetic_sweep.json")
SWEEP_PNG = os.path.join(HERE, "reports", "charts", "energygate_sweep_SIMULATED.png")
FIRMWARE_HEADER = os.path.join(HERE, "..", "firmware", "lib", "sentinel_proto", "include",
                               "sentinel_proto", "energygate_model.h")

MIN_SAMPLES_LEAF = 20      # fixed up front (~0.6% of the data), not tuned
DEPTHS = (3, 4, 5)         # kept shallow: the point is a tiny on-device model

BANNER = [
    "SIMULATED -- NOT A RESULT.",
    "Trained on synthetic Trace rows from ml/tests/generate_synthetic_traces.py --hard",
    "(overlapping classes, noise, 3% label noise), not on real board recordings. It",
    "encodes our own assumptions about attack traffic. Replace with the output of",
    "`make energygate` (ml/README.md, phase 3) once real traces exist in ml/data/traces/.",
    "Never present its accuracy as a measured result.",
]


def ece(y, p, bins=10):
    edges = np.linspace(0, 1, bins + 1)
    idx = np.clip(np.digitize(p, edges) - 1, 0, bins - 1)
    return float(sum(abs(y[idx == b].mean() - p[idx == b].mean()) * (idx == b).mean()
                     for b in range(bins) if (idx == b).any()))


def out_of_fold(X, y, sessions, depth):
    """Score every session with a tree that never saw it."""
    p = np.zeros(len(y))
    for s in sorted(set(sessions)):
        te = sessions == s
        m = DecisionTreeClassifier(max_depth=depth, min_samples_leaf=MIN_SAMPLES_LEAF, random_state=42)
        p[te] = m.fit(X[~te], y[~te]).predict_proba(X[te])[:, 1]
    return p


def scores(y, p):
    # clip only for log loss so a pure leaf's 0/1 doesn't give infinity
    return dict(auc=round(float(roc_auc_score(y, p)), 4),
                log_loss=round(float(log_loss(y, np.clip(p, 1e-3, 1 - 1e-3))), 4),
                brier=round(float(brier_score_loss(y, p)), 4),
                ece=round(ece(y, p), 4),
                accuracy_at_0p5=round(float(((p >= 0.5) == y).mean()), 4))


def parity_check(clf, header_path, n=500, seed=99):
    """Compile the header with gcc and compare to sklearn on n boundary-stressing rows."""
    rng = np.random.default_rng(seed)
    X = np.column_stack([rng.uniform(*FEATURE_RANGES[f], size=n) for f in energygate.FEATURE_ORDER])
    with tempfile.TemporaryDirectory() as tmp:
        # The harness includes "synthetic_energygate.h". A quoted include searches the
        # source file's own folder first, so compile a COPY of the harness in tmp --
        # otherwise a stale tests/synthetic_energygate.h from an earlier test run wins
        # and this would silently check the wrong model.
        shutil.copy(header_path, os.path.join(tmp, "synthetic_energygate.h"))
        harness = os.path.join(tmp, "energygate_harness.c")
        shutil.copy(HARNESS_SRC, harness)
        exe = os.path.join(tmp, "harness.exe")
        csv_path = os.path.join(tmp, "rows.csv")
        np.savetxt(csv_path, X, delimiter=",", fmt="%.9g")
        subprocess.run(["gcc", "-O2", harness, "-o", exe], check=True)
        out = subprocess.run([exe, csv_path], check=True, capture_output=True, text=True).stdout
    c_prob = np.array([float(v) for v in out.split()])
    py_prob = clf.predict_proba(X)[:, 1]
    assert len(c_prob) == len(py_prob), f"C emitted {len(c_prob)} rows, Python {len(py_prob)}"
    worst = float(np.abs(c_prob - py_prob).max())
    assert worst <= PROB_TOLERANCE, f"C and Python disagree by up to {worst:.2e}"
    return worst


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--sessions", type=int, default=30,
                    help="simulated recording sessions; more sessions stop the tree latching onto "
                         "per-session constants like battery_pct")
    ap.add_argument("--firmware", action="store_true", help="also copy the header into firmware/")
    a = ap.parse_args()

    gen.main(n_sessions=a.sessions, rows_per_session=120, seed=0, hard=True, out_dir=TRACE_DIR)
    df = energygate.load_traces(TRACE_DIR)
    for col, default in energygate.OPTIONAL_DEFAULTS.items():
        df[col] = df[col].fillna(default) if col in df.columns else default
    X = df[energygate.FEATURE_ORDER].values.astype(float)
    y = df["label"].isin(SYNTH_REAL_LABELS).astype(int).values
    sessions = df["session"].values

    # -- choose depth by out-of-fold log loss on held-out sessions
    by_depth, oof = {}, {}
    for d in DEPTHS:
        oof[d] = out_of_fold(X, y, sessions, d)
        by_depth[str(d)] = scores(y, oof[d])
    depth = int(min(DEPTHS, key=lambda d: by_depth[str(d)]["log_loss"]))
    p = oof[depth]

    clf, base = energygate.train(TRACE_DIR, max_depth=depth, real_labels=SYNTH_REAL_LABELS,
                                 min_samples_leaf=MIN_SAMPLES_LEAF)
    leaf_p = clf.tree_.value[clf.tree_.children_left == -1][:, 0, :]
    leaf_p = leaf_p[:, 1] / leaf_p.sum(axis=1)
    importances = dict(zip(energygate.FEATURE_ORDER, (round(float(v), 3) for v in clf.feature_importances_)))

    energygate.export_c(clf, EXPORT_PATH, banner=BANNER)
    worst = parity_check(clf, EXPORT_PATH)

    metrics = dict(
        SIMULATED=True,
        note="simulated traces (generate_synthetic_traces.py --hard); encodes our own assumptions; not a result",
        rows=len(df), sessions=len(set(sessions)), real_pct=base["real_pct"],
        label_noise=gen.LABEL_FLIP_PROB, min_samples_leaf=MIN_SAMPLES_LEAF,
        depth_selected=depth, out_of_fold_by_depth=by_depth,
        leaves=int(clf.get_n_leaves()), nodes=int(clf.tree_.node_count),
        leaf_probabilities=sorted(round(float(v), 3) for v in leaf_p),
        feature_importances=importances,
        c_vs_python_max_abs_diff_500_rows=worst,
    )
    with open(METRICS_PATH, "w") as f:
        json.dump(metrics, f, indent=2)

    sweep = energygate_sweep.run(p, y, SWEEP_JSON, SWEEP_PNG)

    print(f"SIMULATED, {len(df)} windows / {len(set(sessions))} sessions, {base['real_pct']}% real, "
          f"{gen.LABEL_FLIP_PROB:.0%} label noise")
    for d in DEPTHS:
        print(f"  depth {d}: out-of-fold {by_depth[str(d)]}")
    print(f"selected depth {depth}: {metrics['leaves']} leaves; leaf probabilities {metrics['leaf_probabilities']}")
    print(f"feature importances {importances}")
    fw = sweep["firmware_default_thresholds"]
    print(f"at firmware defaults 0.7/0.4: legit connected {fw['legit_connected_pct']:.1f}% "
          f"({fw['legit_delayed_pct']:.1f}% delayed by a challenge), attack energy {fw['attack_energy_pct']:.1f}% "
          f"of undefended; {fw['share_of_windows_in_challenge_band']:.1f}% of windows land in the challenge band")
    print(f"parity: C == Python on 500 rows (max diff {worst:.2e})")
    print(f"header: {EXPORT_PATH} ({os.path.getsize(EXPORT_PATH)} bytes of source)")
    print(f"sweep:  {SWEEP_JSON}\n        {SWEEP_PNG}")

    if a.firmware:
        shutil.copy(EXPORT_PATH, FIRMWARE_HEADER)
        print(f"copied to {os.path.normpath(FIRMWARE_HEADER)}")


if __name__ == "__main__":
    main()
