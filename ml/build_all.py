"""Train MailGuard and FileGuard, save artifacts, write reports/metrics.json.

Usage:
    python build_all.py --data "path/to/security" [--benign-features benign/features/thirdparty_features.csv]

This is the one script that reproduces everything service.py needs:
models/mailguard.joblib, models/fileguard.joblib, demo/malicious_features.json
and reports/metrics.json.
"""
import argparse
import json
import os

import joblib
import numpy as np
import pandas as pd

from sentinel_ml import fileguard, mailguard
from sentinel_ml.data import load_malware, malware_feature_columns

HERE = os.path.dirname(os.path.abspath(__file__))
MODELS_DIR = os.path.join(HERE, "models")
DEMO_DIR = os.path.join(HERE, "demo")
REPORTS_DIR = os.path.join(HERE, "reports")


def build_demo_malicious_samples(security_root, cols, held_out_row_ids, n=20, seed=7):
    m = load_malware(security_root)
    pool = m.iloc[held_out_row_ids]
    pool = pool[pool.label == 1]
    sample = pool.sample(min(n, len(pool)), random_state=seed)
    rows = sample[cols].to_dict("records")
    os.makedirs(DEMO_DIR, exist_ok=True)
    with open(os.path.join(DEMO_DIR, "malicious_features.json"), "w") as f:
        json.dump(rows, f, indent=2)
    return len(rows)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", required=True, help="the unzipped 'security' folder")
    ap.add_argument("--benign-features", default=os.path.join(HERE, "benign", "features", "thirdparty_features.csv"))
    ap.add_argument("--max-email-false-alarm", type=float, default=0.02)
    ap.add_argument("--max-file-false-alarm", type=float, default=0.001)
    ap.add_argument("--only", choices=["all", "mailguard", "fileguard"], default="all",
                     help="retrain just one model; the other's metrics.json section is kept as-is")
    args = ap.parse_args()

    os.makedirs(MODELS_DIR, exist_ok=True)
    os.makedirs(REPORTS_DIR, exist_ok=True)
    metrics_path = os.path.join(REPORTS_DIR, "metrics.json")
    metrics = {}
    if os.path.exists(metrics_path):
        with open(metrics_path) as f:
            metrics = json.load(f)

    if args.only in ("all", "mailguard"):
        print("== training MailGuard ==")
        vec, model, mail_threshold, mail_metrics = mailguard.train(args.data, max_false_alarm=args.max_email_false_alarm)
        joblib.dump({"vectorizer": vec, "model": model, "threshold": mail_threshold}, os.path.join(MODELS_DIR, "mailguard.joblib"))
        metrics["mailguard"] = mail_metrics
        print(json.dumps(mail_metrics, indent=2, default=str))
    else:
        print("== skipping MailGuard (--only fileguard); keeping its existing metrics.json section ==")

    if args.only not in ("all", "fileguard"):
        with open(metrics_path, "w") as f:
            json.dump(metrics, f, indent=2, default=str)
        print(f"wrote {metrics_path}")
        return

    print("== training FileGuard ==")
    benign_csv = args.benign_features if os.path.exists(args.benign_features) else None
    if benign_csv is None:
        print(f"  no benign feature file at {args.benign_features}; training dataset-only (will be biased)")
    fmodel, cols, file_threshold, file_metrics = fileguard.train(
        args.data, thirdparty_features_csv=benign_csv, max_false_alarm=args.max_file_false_alarm
    )
    joblib.dump({"model": fmodel, "cols": cols, "threshold": file_threshold}, os.path.join(MODELS_DIR, "fileguard.joblib"))
    metrics["fileguard"] = file_metrics
    print(json.dumps(file_metrics, indent=2, default=str))

    print("== building held-out malicious demo samples ==")
    m = load_malware(args.data)
    cols_all = malware_feature_columns(df=m)
    # the same group split fileguard.train used, so demo rows are genuinely held out
    from sklearn.model_selection import GroupShuffleSplit
    from sentinel_ml.data import malware_groups
    groups = malware_groups(m[cols_all])
    _, te_idx = next(GroupShuffleSplit(n_splits=1, test_size=0.2, random_state=fileguard.SEED).split(m[cols_all], m.label, groups=groups))
    n_demo = build_demo_malicious_samples(args.data, cols_all, te_idx)
    metrics["demo_malicious_samples"] = n_demo
    print(f"  wrote {n_demo} demo malicious feature rows")

    with open(os.path.join(REPORTS_DIR, "metrics.json"), "w") as f:
        json.dump(metrics, f, indent=2, default=str)
    print(f"wrote {os.path.join(REPORTS_DIR, 'metrics.json')}")


if __name__ == "__main__":
    main()
