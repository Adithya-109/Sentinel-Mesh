"""Train the real FieldGuard on-device model from data/traces/*.jsonl and
export it to export/field_model.h. Single entrypoint for `make field-model`.

Raises (via sentinel_ml.field_model.train) if no trace files exist yet.
"""
import json
import os

from sentinel_ml import field_model

HERE = os.path.dirname(os.path.abspath(__file__))
TRACE_DIR = os.path.join(HERE, "data", "traces")
EXPORT_PATH = os.path.join(HERE, "export", "field_model.h")
METRICS_PATH = os.path.join(HERE, "reports", "field_model_metrics.json")


def main():
    clf, metrics = field_model.train(TRACE_DIR)
    field_model.export_c(clf, EXPORT_PATH)
    os.makedirs(os.path.dirname(METRICS_PATH), exist_ok=True)
    with open(METRICS_PATH, "w") as f:
        json.dump(metrics, f, indent=2, default=str)
    print(json.dumps(metrics, indent=2, default=str))
    print(f"wrote {EXPORT_PATH}")


if __name__ == "__main__":
    main()
