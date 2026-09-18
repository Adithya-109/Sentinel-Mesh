"""The FileGuard red-team library models edits a real PE could have; check it keeps to that.

    python tests/test_fileguard_redteam.py        (or: make test-fileguard)
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

from sentinel_ml import pe_features, redteam  # noqa: E402

ART = joblib.load(os.path.join(ML, "models", "fileguard.joblib"))
MODEL, COLS, THR = ART["model"], ART["cols"], ART["threshold"]
MAL = pd.DataFrame(json.load(open(os.path.join(ML, "demo", "malicious_features.json")))).reindex(columns=COLS, fill_value=0)
DON = pd.read_csv(os.path.join(ML, "benign", "features", "local_windows_features.csv")).reindex(columns=COLS, fill_value=0)
DON = DON[DON.Machine == MAL.Machine.iloc[0]].sample(len(MAL), random_state=3).reset_index(drop=True)


def test_every_feature_has_exactly_one_control_class():
    assert set(redteam.CONTROL_CLASS) == set(COLS), "classification must cover all 54 features and nothing else"
    assert len(redteam.CONTROL_CLASS) == 54


def test_no_edit_groups_is_the_identity():
    out = redteam.perturb(MAL, DON, [])
    pd.testing.assert_frame_equal(out, MAL)


def test_only_declared_features_change():
    for group, feats in redteam.GROUPS.items():
        out = redteam.perturb(MAL, DON, [group], k_sections=4)
        changed = {c for c in COLS if not np.allclose(out[c].to_numpy(float), MAL[c].to_numpy(float))}
        assert changed <= set(feats), f"{group} changed undeclared features: {changed - set(feats)}"


def test_imports_resources_and_sections_are_add_only():
    out = redteam.perturb(MAL, DON, ["resources", "imports", "sections"], k_sections=4)
    for col in ["ResourcesNb", "ImportsNb", "ImportsNbDLL", "VersionInformationSize", "SectionsNb",
                "SectionsMaxEntropy", "SectionMaxRawsize", "SectionMaxVirtualsize", "SizeOfImage", "SizeOfInitializedData"]:
        assert (out[col].to_numpy(float) >= MAL[col].to_numpy(float) - 1e-9).all(), f"{col} decreased"
    for col in ["SectionsMinEntropy", "SectionsMinRawsize", "SectionsMinVirtualsize"]:
        assert (out[col].to_numpy(float) <= MAL[col].to_numpy(float) + 1e-9).all(), f"{col} increased"
    assert (out.SectionsNb.to_numpy(float) == MAL.SectionsNb.to_numpy(float) + 4).all()


def test_section_mean_is_the_exact_weighted_mean():
    out = redteam.perturb(MAL, DON, ["sections"], k_sections=3)
    n0 = MAL.SectionsNb.to_numpy(float)
    expect = (n0 * MAL.SectionsMeanEntropy.to_numpy(float) + 3 * DON.SectionsMeanEntropy.to_numpy(float)) / (n0 + 3)
    assert np.allclose(out.SectionsMeanEntropy.to_numpy(float), expect)


def test_resource_statistics_combine_correctly():
    # 2 old resources (mean entropy 4, min 2, max 6) + 3 added (mean 1, min 0.5, max 2)
    n0, n1 = np.array([2.0]), np.array([3.0])
    assert np.isclose(redteam._combine(n0, np.array([4.0]), n1, np.array([1.0]), "mean")[0], (2 * 4 + 3 * 1) / 5)
    assert redteam._combine(n0, np.array([2.0]), n1, np.array([0.5]), "min")[0] == 0.5
    assert redteam._combine(n0, np.array([6.0]), n1, np.array([2.0]), "max")[0] == 6.0
    # no old resources: the added ones' statistics stand alone; none at all stays 0
    assert redteam._combine(np.array([0.0]), np.array([0.0]), n1, np.array([1.0]), "mean")[0] == 1.0
    assert redteam._combine(np.array([0.0]), np.array([0.0]), np.array([0.0]), np.array([0.0]), "max")[0] == 0.0


def test_appended_overlay_bytes_change_none_of_the_54_features():
    """The 'inflate size / dilute entropy' attack is a no-op here: there is no file-size or whole-file entropy feature."""
    import shutil
    import tempfile
    src = next((p for p in [r"C:\Windows\SysWOW64\ping.exe", r"C:\Windows\SysWOW64\notepad.exe"] if os.path.exists(p)), None)
    if src is None:
        print("  (skipped: no sample benign binary on this machine)")
        return
    tmp = tempfile.mkdtemp()
    try:
        a, b = os.path.join(tmp, "a.exe"), os.path.join(tmp, "b.exe")
        shutil.copyfile(src, a)
        shutil.copyfile(a, b)
        with open(b, "ab") as f:
            f.write(os.urandom(1024 * 1024))
        fa, fb = pe_features.extract(a), pe_features.extract(b)
        assert {k for k in fa if fa[k] != fb[k]} == set()
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_evaluate_reports_a_clean_baseline_and_all_tiers():
    res = redteam.evaluate(MODEL, COLS, THR, MAL, DON, k_donors=3, seed=0)
    assert res["clean"]["n"] == len(MAL)
    assert [t["name"] for t in res["tiers"]] == [n for n, _ in redteam.TIERS]
    for t in res["tiers"] + res["solo"]:
        assert 0 <= t["adaptive"]["detected"] <= len(MAL)


if __name__ == "__main__":
    tests = [(n, f) for n, f in sorted(globals().items()) if n.startswith("test_") and callable(f)]
    for name, fn in tests:
        fn()
        print(f"ok  {name}")
    print(f"{len(tests)} passed")
