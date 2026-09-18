"""Train the real EnergyGate on-device model from data/traces/*.jsonl and
export it to export/energygate.h. Single entrypoint for `make energygate`.

Raises (via sentinel_ml.energygate.train) if no trace files exist yet, or
if every recorded row falls on the same side of REAL_LABELS.
"""
import json
import os

from sentinel_ml import energygate

HERE = os.path.dirname(os.path.abspath(__file__))
TRACE_DIR = os.path.join(HERE, "data", "traces")
EXPORT_PATH = os.path.join(HERE, "export", "energygate.h")
METRICS_PATH = os.path.join(HERE, "reports", "energygate_metrics.json")


def main():
    clf, metrics = energygate.train(TRACE_DIR)
    energygate.export_c(clf, EXPORT_PATH)
    os.makedirs(os.path.dirname(METRICS_PATH), exist_ok=True)
    with open(METRICS_PATH, "w") as f:
        json.dump(metrics, f, indent=2, default=str)
    print(json.dumps(metrics, indent=2, default=str))
    print(f"wrote {EXPORT_PATH}")


if __name__ == "__main__":
    main()
