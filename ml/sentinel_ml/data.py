"""Data loaders for the Code Cortex 3.0 security dataset.

Rules (see contracts/CONTRACT.md and the project brief, sections 4-6):
  - Emails: only CEAS_08, Enron, Ling, Nigerian_Fraud, SpamAssasin. Never
    phishing_email.csv (duplicates those five) or emails.csv (99.8% inside
    Enron). Exact duplicates are dropped; a `source` column is kept.
  - Malware: malware.csv is '|'-separated. Name and md5 are dropped (Name
    leaks the label). label = 1 - legitimate. Splits must group identical
    feature vectors so the same underlying sample never appears in both
    train and test.
"""
import csv
import os
import re
import sys

import numpy as np
import pandas as pd

csv.field_size_limit(min(sys.maxsize, 2 ** 31 - 1))

EMAIL_CORPORA = ["CEAS_08", "Enron", "Ling", "Nigerian_Fraud", "SpamAssasin"]


def _norm_key(text):
    """Collapse whitespace/punctuation/case so near-identical rows dedup."""
    return re.sub(r"\W+", "", str(text).lower())[:400]


def load_emails(security_root: str) -> pd.DataFrame:
    """Load and dedup the five approved email corpora.

    Returns columns: source, text, label, key.
    """
    base = os.path.join(security_root, "phishing emails", "archive (6)")
    parts = []
    for name in EMAIL_CORPORA:
        path = os.path.join(base, name + ".csv")
        d = pd.read_csv(path, engine="python")
        d["source"] = name
        d["text"] = d["subject"].fillna("").astype(str) + " " + d["body"].fillna("").astype(str)
        parts.append(d[["source", "text", "label"]])
    em = pd.concat(parts, ignore_index=True)
    em["key"] = em["text"].map(_norm_key)
    em = em.drop_duplicates("key").reset_index(drop=True)
    em["label"] = em["label"].astype(int)
    return em


MALWARE_DROP_COLS = ["Name", "md5"]


def load_malware(security_root: str) -> pd.DataFrame:
    """Load malware.csv, drop leaking columns, derive the malware label.

    Returns the feature columns plus a `label` column (1 = malware).
    """
    path = os.path.join(security_root, "malware", "malware.csv")
    m = pd.read_csv(path, sep="|")
    m["label"] = (m["legitimate"] == 0).astype(int)
    m = m.drop(columns=[c for c in MALWARE_DROP_COLS if c in m.columns] + ["legitimate"])
    return m


def malware_feature_columns(security_root: str = None, df: pd.DataFrame = None):
    """The 54 PE header feature columns, in the order malware.csv provides them."""
    if df is None:
        df = load_malware(security_root)
    return [c for c in df.columns if c != "label"]


def malware_groups(X: pd.DataFrame) -> pd.Series:
    """Group key per row: identical feature vectors get the same group.

    Used with GroupShuffleSplit so a duplicated sample can't leak across
    the train/test boundary (malware.csv has ~35.8k duplicate feature rows).
    """
    return pd.util.hash_pandas_object(X, index=False)
