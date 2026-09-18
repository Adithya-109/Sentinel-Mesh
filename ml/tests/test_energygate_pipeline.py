"""End-to-end test of the EnergyGate pipeline (sentinel_ml/energygate.py)
using synthetic data, so the pipeline is proven correct before real
recordings exist.

Never treat the metrics this prints as a real result -- every underlying
label is "SYNTH_"-prefixed and nothing here touches ml/reports/ or the real
ml/export/energygate.h.

Steps: generate synthetic traces (shared with the field-model test) ->
train -> export to C -> compile with gcc -> run 500 fresh random feature
rows through both the Python model and the compiled C model -> assert
they agree (within float rounding) everywhere.

Usage:
    python test_energygate_pipeline.py
"""
import csv
import json
import os
import subprocess
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, ".."))

from sentinel_ml import energygate  # noqa: E402
import generate_synthetic_traces as gen  # noqa: E402

TRACE_DIR = os.path.join(HERE, "synthetic_traces")
HEADER_PATH = os.path.join(HERE, "synthetic_energygate.h")
METRICS_PATH = os.path.join(HERE, "synthetic_energygate_metrics.json")
CSV_PATH = os.path.join(HERE, "energygate_parity_features.csv")
HARNESS_SRC = os.path.join(HERE, "energygate_harness.c")
HARNESS_BIN = os.path.join(HERE, "energygate_harness.exe")

N_PARITY_ROWS = 500
PROB_TOLERANCE = 1e-4  # float32 (C) vs float64 (sklearn) rounding

SYNTH_REAL_LABELS = {"SYNTH_normal", "SYNTH_weak_link"}

# Broad, boundary-stressing ranges per feature (superset of what
# generate_synthetic_traces.py produces), so the parity check isn't just
# re-testing the training distribution.
FEATURE_RANGES = {
    "hs_per_s": (0, 600),
    "hs_fail": (0, 200),
    "rssi_mean": (-100, -20),
    "rssi_var": (0, 25),
    "loss_pct": (0, 100),
    "dup_pct": (0, 100),
    "frag_complete_pct": (0, 100),
    "battery_pct": (0, 100),
}


def generate_parity_rows(n, seed=99):
    rng = np.random.default_rng(seed)
    rows = np.column_stack([
        rng.uniform(lo, hi, size=n) for lo, hi in
        (FEATURE_RANGES[f] for f in energygate.FEATURE_ORDER)
    ])
    return rows


def main():
    print("== 1. generating synthetic Trace rows (SYNTH_-prefixed labels) ==")
    gen.main(n_sessions=6, rows_per_session=120, seed=0)

    print("== 2. training the EnergyGate decision tree on synthetic data ==")
    clf, metrics = energygate.train(TRACE_DIR, max_depth=4, real_labels=SYNTH_REAL_LABELS)
    with open(METRICS_PATH, "w") as f:
        json.dump(metrics, f, indent=2, default=str)
    print(f"   SYNTHETIC leave-one-session-out (not a real result): {metrics['leave_one_session_out']}")

    print("== 3. exporting to C ==")
    energygate.export_c(clf, HEADER_PATH)
    print(f"   wrote {HEADER_PATH}")

    print(f"== 4. generating {N_PARITY_ROWS} parity-test feature rows ==")
    X = generate_parity_rows(N_PARITY_ROWS)
    with open(CSV_PATH, "w", newline="") as f:
        csv.writer(f).writerows(X)

    py_prob = clf.predict_proba(X)[:, 1]

    print("== 5. compiling the C harness with gcc ==")
    subprocess.run(["gcc", "-O2", "-I", HERE, HARNESS_SRC, "-o", HARNESS_BIN], check=True)

    print("== 6. running the compiled harness and comparing to sklearn ==")
    result = subprocess.run([HARNESS_BIN, CSV_PATH], check=True, capture_output=True, text=True)
    c_prob = [float(x) for x in result.stdout.split()]

    if len(c_prob) != len(py_prob):
        raise AssertionError(f"row count mismatch: C emitted {len(c_prob)}, Python has {len(py_prob)}")

    diffs = np.abs(np.array(c_prob) - py_prob)
    mismatches = np.where(diffs > PROB_TOLERANCE)[0]
    if len(mismatches):
        for i in mismatches[:10]:
            print(f"   MISMATCH row {i}: C={c_prob[i]:.6f} python={py_prob[i]:.6f} features={X[i].tolist()}")
        raise AssertionError(f"{len(mismatches)}/{len(py_prob)} rows disagree by more than {PROB_TOLERANCE}")

    print(f"PASS: C and Python agree on all {len(py_prob)} rows (max diff {diffs.max():.2e}).")


if __name__ == "__main__":
    main()
