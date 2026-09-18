"""Train SMS Guard on the real UCI SMS Spam Collection and write real
artifacts: model.joblib, vectorizer.joblib, manifest.json.

Dataset: UCI SMS Spam Collection (5,574 real labeled SMS messages), CC-BY-4.0.
https://archive.ics.uci.edu/dataset/228/sms+spam+collection
"ham" -> legitimate, "spam" -> smishing (the standard academic label for this
collection; it is the class of unsolicited SMS -- fake prize/delivery/OTP/bank
scam messages included -- that "smishing" refers to in this demo).

Does NOT touch ml/, MailGuard or FileGuard in any way. Everything this script
reads or writes lives under channels/sms/.

Usage (from anywhere; auto-downloads the dataset on first run and caches it):
    python channels/sms/train.py
    python channels/sms/train.py --data path/to/SMSSpamCollection   # offline / already downloaded
    python channels/sms/train.py --max-false-alarm 0.03             # looser threshold

What it writes, all under channels/sms/:
    model.joblib         the fitted LogisticRegression
    vectorizer.joblib    the fitted FeatureUnion (word + char TF-IDF)
    manifest.json        real accuracy/precision/recall from the held-out
                          test split -- this file is regenerated every run,
                          so the numbers on screen always match the model
                          actually sitting next to it
    metrics.json         the fuller evaluation report (both classes, AUC,
                          confusion counts, top global n-grams) for anyone
                          who wants to check the manifest numbers by hand
"""
import argparse
import io
import json
import os
import urllib.request
import zipfile

import joblib
import numpy as np
import pandas as pd
from sklearn.metrics import (accuracy_score, confusion_matrix, precision_score,
                             recall_score, roc_auc_score)
from sklearn.model_selection import train_test_split

import sms_guard

HERE = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(HERE, "data")
DATASET_URL = "https://archive.ics.uci.edu/static/public/228/sms+spam+collection.zip"
SEED = sms_guard.SEED


def _download_dataset() -> str:
    """Downloads and caches the UCI zip, returns the path to the extracted
    SMSSpamCollection file (tab-separated: label \\t message, no header)."""
    os.makedirs(DATA_DIR, exist_ok=True)
    out_path = os.path.join(DATA_DIR, "SMSSpamCollection")
    if os.path.exists(out_path):
        return out_path
    print(f"downloading {DATASET_URL} ...")
    with urllib.request.urlopen(DATASET_URL, timeout=60) as resp:
        raw = resp.read()
    with zipfile.ZipFile(io.BytesIO(raw)) as zf:
        with zf.open("SMSSpamCollection") as f, open(out_path, "wb") as out:
            out.write(f.read())
    print(f"cached to {out_path}")
    return out_path


def load_dataset(path: str = None) -> pd.DataFrame:
    """Returns columns: text, label (1 = smishing/spam, 0 = legitimate/ham)."""
    if path is None:
        path = _download_dataset()
    elif os.path.isdir(path):
        candidate = os.path.join(path, "SMSSpamCollection")
        path = candidate if os.path.exists(candidate) else path
    rows = []
    with open(path, encoding="utf-8", errors="replace") as f:
        for line in f:
            line = line.rstrip("\n")
            if not line:
                continue
            label, _, text = line.partition("\t")
            if label not in ("ham", "spam") or not text:
                continue
            rows.append((text, 1 if label == "spam" else 0))
    df = pd.DataFrame(rows, columns=["text", "label"])
    df = df.drop_duplicates("text").reset_index(drop=True)
    return df


def threshold_for_max_fpr(y, scores, max_fpr):
    """Same approach as mailguard.threshold_for_max_fpr: the highest-recall
    threshold whose false-alarm rate on legitimate messages stays <= max_fpr."""
    from sklearn.metrics import roc_curve
    fpr, tpr, thr = roc_curve(y, scores)
    ok = fpr <= max_fpr
    if not ok.any():
        return float(thr[np.argmin(fpr)])
    best = np.argmax(np.where(ok, tpr, -1))
    return float(thr[best])


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--data", default=None,
                     help="path to an already-downloaded SMSSpamCollection file/dir; "
                          "omit to auto-download from UCI")
    ap.add_argument("--max-false-alarm", type=float, default=0.03,
                     help="tune the decision threshold to stay under this false-alarm "
                          "rate on legitimate messages (default 0.03, i.e. <=3%%)")
    ap.add_argument("--test-size", type=float, default=0.2)
    args = ap.parse_args()

    df = load_dataset(args.data)
    print(f"loaded {len(df)} messages after de-duplication "
          f"({int(df.label.sum())} spam/smishing, {int((df.label == 0).sum())} ham/legitimate)")

    train, test = train_test_split(df, test_size=args.test_size, stratify=df.label, random_state=SEED)
    # a small validation slice off the training data to tune the threshold on,
    # so the held-out test split is only ever touched once, at the very end
    train, val = train_test_split(train, test_size=0.15, stratify=train.label, random_state=SEED)

    print(f"train={len(train)} val={len(val)} test={len(test)}")

    vec, model = sms_guard.fit(train.text, train.label)

    val_scores = sms_guard.predict_proba(vec, model, val.text)
    threshold = threshold_for_max_fpr(val.label.values, val_scores, args.max_false_alarm)

    # -- held-out evaluation, touched exactly once, at the tuned threshold --
    test_scores = sms_guard.predict_proba(vec, model, test.text)
    test_pred = test_scores >= threshold
    y_test = test.label.values

    acc = accuracy_score(y_test, test_pred)
    prec = precision_score(y_test, test_pred, zero_division=0)     # spam/smishing class
    rec = recall_score(y_test, test_pred, zero_division=0)         # spam/smishing class
    auc = roc_auc_score(y_test, test_scores)
    tn, fp, fn, tp = confusion_matrix(y_test, test_pred).ravel()

    metrics = {
        "dataset": "UCI SMS Spam Collection (CC-BY-4.0)",
        "dataset_url": "https://archive.ics.uci.edu/dataset/228/sms+spam+collection",
        "total_messages_after_dedup": int(len(df)),
        "train_size": int(len(train)),
        "val_size": int(len(val)),
        "test_size": int(len(test)),
        "threshold": round(threshold, 4),
        "max_false_alarm_target": args.max_false_alarm,
        "held_out_test_metrics": {
            "accuracy": round(float(acc), 4),
            "precision_smishing": round(float(prec), 4),
            "recall_smishing": round(float(rec), 4),
            "auc": round(float(auc), 4),
            "confusion_matrix": {
                "true_negative_legit_correct": int(tn),
                "false_positive_legit_flagged": int(fp),
                "false_negative_smishing_missed": int(fn),
                "true_positive_smishing_caught": int(tp),
            },
        },
        "top_global_smishing_ngrams": sms_guard.top_global_ngrams(vec, model, top_k=15),
    }

    print(json.dumps(metrics, indent=2))

    joblib.dump(model, os.path.join(HERE, "model.joblib"))
    joblib.dump(vec, os.path.join(HERE, "vectorizer.joblib"))
    with open(os.path.join(HERE, "metrics.json"), "w") as f:
        json.dump(metrics, f, indent=2)

    manifest = {
        "id": "sms",
        "display_name": "SMS Guard",
        "description": "Real, trained smishing classifier: word + character n-gram "
                        "TF-IDF -> Logistic Regression, same model family as MailGuard "
                        "('same engine, new config'), tuned for SMS's short length.",
        "status": "active",
        "enabled": True,
        "model_path": "channels/sms/model.joblib",
        "vectorizer_path": "channels/sms/vectorizer.joblib",
        "metrics": {
            "accuracy": round(float(acc), 4),
            "precision_smishing": round(float(prec), 4),
            "recall_smishing": round(float(rec), 4),
            "auc": round(float(auc), 4),
            "threshold": round(threshold, 4),
            "trained_on": f"UCI SMS Spam Collection, {len(df)} msgs after de-dup "
                          f"({len(test)} held out for this evaluation)",
        },
        "live_classify": True,
    }
    manifest_path = os.path.join(HERE, "manifest.json")
    with open(manifest_path, "w") as f:
        json.dump(manifest, f, indent=2)
    print(f"\nwrote {manifest_path} (enabled=true, live_classify=true)")
    print("wrote model.joblib, vectorizer.joblib, metrics.json")
    print("\nRestart the console API (or it will pick this up on its next startup) "
          "for SMS Guard to appear in GET /channels.")


if __name__ == "__main__":
    main()
