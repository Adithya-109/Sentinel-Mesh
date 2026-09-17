"""End-to-end test of the field-model pipeline (sentinel_ml/field_model.py)
using synthetic data, so the pipeline is proven correct before real
traces ever exist.

Never treat the metrics this prints as real detection numbers -- every
class is "SYNTH_"-prefixed and nothing here touches ml/reports/ or the
real ml/export/field_model.h.

Steps: generate synthetic traces -> train -> export to C -> compile with
gcc -> run 500 fresh random feature rows through both the Python model
and the compiled C model -> assert they agree everywhere.

Usage:
    python test_field_model_pipeline.py
"""
import csv
import json
import os
import subprocess
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, ".."))

from sentinel_ml import field_model  # noqa: E402
import generate_synthetic_traces as gen  # noqa: E402

TRACE_DIR = os.path.join(HERE, "synthetic_traces")
HEADER_PATH = os.path.join(HERE, "synthetic_field_model.h")
METRICS_PATH = os.path.join(HERE, "synthetic_field_model_metrics.json")
CSV_PATH = os.path.join(HERE, "parity_features.csv")
HARNESS_SRC = os.path.join(HERE, "field_model_harness.c")
HARNESS_BIN = os.path.join(HERE, "field_model_harness.exe")

N_PARITY_ROWS = 500

# Broad, boundary-stressing ranges per feature (superset of what
# generate_synthetic_traces.py produces), so the parity check isn't just
# re-testing the training distribution.
FEATURE_RANGES = {
    "window_ms": (1000, 10000),
    "hs_per_s": (0, 600),
    "hs_fail": (0, 200),
    "replay_rej": (0, 100),
    "auth_fail": (0, 150),
    "stale": (0, 20),
    "frag_timeout": (0, 30),
    "rssi_mean": (-100, -20),
    "rssi_var": (0, 25),
    "loss_pct": (0, 100),
    "jitter_ms": (0, 50),
}


def generate_parity_rows(n, seed=99):
    rng = np.random.default_rng(seed)
    rows = np.column_stack([
        rng.uniform(lo, hi, size=n) for lo, hi in
        (FEATURE_RANGES[f] for f in field_model.FEATURE_ORDER)
    ])
    return rows


def main():
    print("== 1. generating synthetic Trace rows (SYNTH_-prefixed labels) ==")
    gen.main(n_sessions=6, rows_per_session=120, seed=0)

    print("== 2. training the field-model decision tree on synthetic data ==")
    clf, metrics = field_model.train(TRACE_DIR, max_depth=6, classes=gen.SYNTH_CLASSES)
    with open(METRICS_PATH, "w") as f:
        json.dump(metrics, f, indent=2, default=str)
    print(f"   SYNTHETIC leave-one-session-out (not a real result): {metrics['leave_one_session_out']}")

    print("== 3. exporting to C ==")
    field_model.export_c(clf, HEADER_PATH, classes=gen.SYNTH_CLASSES)
    print(f"   wrote {HEADER_PATH}")

    print(f"== 4. generating {N_PARITY_ROWS} parity-test feature rows ==")
    X = generate_parity_rows(N_PARITY_ROWS)
    with open(CSV_PATH, "w", newline="") as f:
        csv.writer(f).writerows(X)

    py_pred = clf.predict(X).astype(int).tolist()

    print("== 5. compiling the C harness with gcc ==")
    subprocess.run(["gcc", "-O2", "-I", HERE, HARNESS_SRC, "-o", HARNESS_BIN], check=True)

    print("== 6. running the compiled harness and comparing to sklearn ==")
    result = subprocess.run([HARNESS_BIN, CSV_PATH], check=True, capture_output=True, text=True)
    c_pred = [int(x) for x in result.stdout.split()]

    if len(c_pred) != len(py_pred):
        raise AssertionError(f"row count mismatch: C emitted {len(c_pred)}, Python has {len(py_pred)}")

    mismatches = [i for i, (a, b) in enumerate(zip(c_pred, py_pred)) if a != b]
    if mismatches:
        for i in mismatches[:10]:
            print(f"   MISMATCH row {i}: C={c_pred[i]} python={py_pred[i]} features={X[i].tolist()}")
        raise AssertionError(f"{len(mismatches)}/{len(py_pred)} rows disagree between C and Python")

    print(f"PASS: C and Python agree on all {len(py_pred)} rows.")


if __name__ == "__main__":
    main()
