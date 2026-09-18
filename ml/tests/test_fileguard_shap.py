"""FileGuard explanations: exact SHAP values, ranked by the verdict.

Runs against the committed model and demo rows -- no dataset needed.

    python tests/test_fileguard_shap.py        (or: make test-fileguard)
"""
import json
import os
import sys

import joblib
import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
ML = os.path.dirname(HERE)
sys.path.insert(0, ML)

from sentinel_ml import fileguard  # noqa: E402

ART = joblib.load(os.path.join(ML, "models", "fileguard.joblib"))
MODEL, COLS, THR = ART["model"], ART["cols"], ART["threshold"]
MAL = pd.DataFrame(json.load(open(os.path.join(ML, "demo", "malicious_features.json")))).reindex(columns=COLS, fill_value=0)
BEN_CSV = os.path.join(ML, "benign", "features", "local_windows_features.csv")
BEN = (pd.read_csv(BEN_CSV).reindex(columns=COLS, fill_value=0).sample(60, random_state=0)
       if os.path.exists(BEN_CSV) else MAL.iloc[:0])
ALL = pd.concat([MAL, BEN], ignore_index=True)


def test_shap_values_are_additive():
    """base + sum(phi) is the raw margin, and sigmoid(margin) is the model's probability."""
    for i in range(len(ALL)):
        x = ALL.iloc[i].values.astype(float)
        phi, base = fileguard.shap_values(MODEL, x)
        margin = MODEL.booster_.predict(x.reshape(1, -1), raw_score=True)[0]
        assert abs(base + phi.sum() - margin) < 1e-9
        p = MODEL.predict_proba(ALL.iloc[[i]])[0, 1]
        assert abs(1 / (1 + np.exp(-margin)) - p) < 1e-9


def test_matches_shap_library_when_available():
    try:
        import shap
    except ImportError:
        print("  (skipped: the shap library is not installed; additivity is still tested)")
        return
    explainer = shap.TreeExplainer(MODEL)
    ref = explainer.shap_values(ALL.values.astype(float))
    ref = ref[1] if isinstance(ref, list) else ref
    ours = np.vstack([fileguard.shap_values(MODEL, ALL.iloc[i].values.astype(float))[0] for i in range(len(ALL))])
    assert np.abs(ours - ref).max() < 1e-6


def test_malicious_verdicts_are_explained_by_malicious_features():
    """The old ranking (by |shap|) let a benign-pointing feature lead a malicious verdict."""
    checked = 0
    for i in range(len(MAL)):
        x = MAL.iloc[i].values.astype(float)
        if MODEL.predict_proba(MAL.iloc[[i]])[0, 1] < THR:
            continue
        detail = fileguard.explain_detail(MODEL, COLS, x, malicious=True)
        assert detail["top"], "a malicious verdict must have at least one reason"
        assert all(t["pushes"] == "malicious" and t["shap"] > 0 for t in detail["top"])
        checked += 1
    assert checked > 0


def test_clean_verdicts_are_explained_by_benign_features():
    checked = 0
    for i in range(len(BEN)):
        x = BEN.iloc[i].values.astype(float)
        if MODEL.predict_proba(BEN.iloc[[i]])[0, 1] >= THR:
            continue
        detail = fileguard.explain_detail(MODEL, COLS, x, malicious=False)
        assert all(t["pushes"] == "benign" and t["shap"] < 0 for t in detail["top"])
        checked += 1
    assert checked > 0 or len(BEN) == 0


def test_reasons_are_plain_english_strings_with_readable_addresses():
    x = MAL.iloc[0].values.astype(float)
    reasons = fileguard.explain(MODEL, COLS, x, malicious=True)
    assert 1 <= len(reasons) <= 3 and all(isinstance(r, str) for r in reasons)
    joined = " ".join(reasons)
    assert "e+0" not in joined  # ImageBase reads 0x400000, not 4.1943e+06
    assert "suggests malicious" in joined


def test_probability_in_detail_matches_the_model():
    x = MAL.iloc[0].values.astype(float)
    detail = fileguard.explain_detail(MODEL, COLS, x)
    assert abs(detail["probability"] - MODEL.predict_proba(MAL.iloc[[0]])[0, 1]) < 1e-5


if __name__ == "__main__":
    tests = [(n, f) for n, f in sorted(globals().items()) if n.startswith("test_") and callable(f)]
    for name, fn in tests:
        fn()
        print(f"ok  {name}")
    print(f"{len(tests)} passed")
