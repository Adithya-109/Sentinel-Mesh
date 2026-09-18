"""Red-team FileGuard: can an attacker dodge it without touching the malicious code?

    python redteam_fileguard.py                    # the 20 held-out demo malware rows (small; a probe)
    python redteam_fileguard.py --data <security>  # the full held-out group-split test set

Works in feature space (sentinel_ml/redteam.py). No live malware is downloaded, stored or
run: malware rows are the dataset's numeric features. The only real files touched are
BENIGN Windows binaries, copied to a temp folder for the overlay/header-edit demonstration.

Writes reports/fileguard_redteam.json and reports/charts/fileguard_red_team.png. It never
touches reports/metrics.json.
"""
import argparse
import json
import os
import shutil
import sys
import tempfile

import joblib
import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from sentinel_ml import pe_features, redteam  # noqa: E402


def overlay_and_header_demo():
    """On a real BENIGN 32-bit binary: do appended junk bytes change any feature? Can header edits be made?"""
    import pefile
    src = next((p for p in [r"C:\Windows\SysWOW64\ping.exe", r"C:\Windows\SysWOW64\notepad.exe",
                            r"C:\Windows\SysWOW64\find.exe"] if os.path.exists(p)), None)
    if src is None:
        return {"skipped": "no 32-bit benign sample binary found on this machine"}
    tmp = tempfile.mkdtemp(prefix="fg_redteam_")
    try:
        a = os.path.join(tmp, "sample.exe")
        shutil.copyfile(src, a)
        base = pe_features.extract(a)

        # (a) append 2 MB of random junk: the "inflate file size / dilute entropy" attack
        b = os.path.join(tmp, "with_overlay.exe")
        shutil.copyfile(a, b)
        with open(b, "ab") as f:
            f.write(os.urandom(2 * 1024 * 1024))
        over = pe_features.extract(b)
        changed = sorted(k for k in base if base[k] != over[k])

        # (b) edit header fields with pefile and re-extract: are they real, expressible edits?
        c = os.path.join(tmp, "header_edited.exe")
        pe = pefile.PE(a)
        edits = {"MajorOperatingSystemVersion": 6, "MajorLinkerVersion": 14, "CheckSum": 0x12345, "ImageBase": 0x10000000,
                 "Subsystem": 2}
        for k, v in edits.items():
            setattr(pe.OPTIONAL_HEADER, k, v)
        pe.write(c)
        pe.close()
        edited = pe_features.extract(c)
        return {
            "benign_sample": os.path.basename(src),
            "appended_junk_bytes": 2 * 1024 * 1024,
            "features_changed_by_appended_junk": changed,
            "note": "FileGuard has no file-size or whole-file-entropy feature, and section statistics cover only the "
                    "sections, so bytes appended after the last section (an overlay) change none of the 54 features."
                    if not changed else "unexpected: appended bytes changed features",
            "header_edits_requested": {k: hex(v) for k, v in edits.items()},
            "header_edits_read_back": {k: hex(int(edited[k])) for k in edits},
            "header_edits_applied": all(int(edited[k]) == v for k, v in edits.items()),
        }
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def chart(res, out_path, title_note):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    names = ["clean"] + [t["name"] for t in res["tiers"]]
    adaptive = [res["clean"]["rate"]] + [t["adaptive"]["rate"] for t in res["tiers"]]
    single = [res["clean"]["rate"]] + [t["single_shot_detection_rate"] for t in res["tiers"]]
    x = np.arange(len(names))
    w = 0.38
    fig, ax = plt.subplots(figsize=(9, 4.8))
    ax.bar(x - w / 2, [100 * v for v in single], width=w, color="#A6A6A6", label="Naive attacker (1 random benign donor)")
    ax.bar(x + w / 2, [100 * v for v in adaptive], width=w, color="#C00000", label="Adaptive attacker (25 donors, keeps the best)")
    ax.set_xticks(x)
    ax.set_xticklabels([n.replace(" + ", "\n+ ").replace(" ", "\n", 1) if n != "clean" else "no attack" for n in names], fontsize=8)
    ax.set_ylabel("Malware detected (%)")
    ax.set_ylim(0, 105)
    ax.set_title(f"FileGuard red-team: detection as the attacker gets more capable\n{title_note}", fontsize=10)
    ax.legend(fontsize=8, loc="upper right")
    fig.tight_layout()
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    fig.savefig(out_path, dpi=150)
    plt.close(fig)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", help="the unzipped 'security' folder; if given, use the full held-out test set")
    ap.add_argument("--model", default=os.path.join(HERE, "models", "fileguard.joblib"))
    ap.add_argument("--donors", default=os.path.join(HERE, "benign", "features", "local_windows_features.csv"))
    ap.add_argument("--k-donors", type=int, default=25)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--out", default=os.path.join(HERE, "reports", "fileguard_redteam.json"))
    args = ap.parse_args()

    art = joblib.load(args.model)
    model, cols, thr = art["model"], art["cols"], art["threshold"]

    if args.data:
        from sklearn.model_selection import GroupShuffleSplit
        from sentinel_ml import fileguard
        from sentinel_ml.data import load_malware, malware_feature_columns, malware_groups
        m = load_malware(args.data)
        c = malware_feature_columns(df=m)
        groups = malware_groups(m[c])
        _, te = next(GroupShuffleSplit(n_splits=1, test_size=0.2, random_state=fileguard.SEED).split(m[c], m.label, groups=groups))
        test = m.iloc[te]
        mal = test[test.label == 1][cols].reset_index(drop=True)
        source = f"full held-out group-split test set ({len(mal)} malware rows)"
    else:
        mal = pd.DataFrame(json.load(open(os.path.join(HERE, "demo", "malicious_features.json")))).reindex(columns=cols, fill_value=0)
        source = f"the {len(mal)} held-out demo malware rows only -- a probe, NOT a full-test-set result"

    donor_raw = pd.read_csv(args.donors)
    donors = donor_raw.reindex(columns=cols, fill_value=0)
    res = redteam.evaluate(model, cols, thr, mal, donors, k_donors=args.k_donors, seed=args.seed)

    is_dll = (donor_raw.Characteristics.astype(int) & 0x2000) != 0
    apps = ~donor_raw.category.str.startswith("windows_")
    pools = {"all benign": donors, "consumer apps only": donors[apps], "EXEs only": donors[~is_dll],
             "consumer-app EXEs only": donors[apps & ~is_dll]}
    sens = redteam.sensitivity(model, cols, thr, mal, pools)
    from sentinel_ml import fileguard
    phi = np.vstack([fileguard.shap_values(model, mal.iloc[i].to_numpy(dtype=float))[0] for i in range(len(mal))])
    evidence = redteam.evidence_by_control_class(phi, cols)
    out = {
        "what": "FileGuard red-team in feature space: detection after physically-plausible edits to the malware's PE header data",
        "malware_source": source,
        "donor_pool": f"{len(donors)} real benign binaries from one machine, never used in training; matched to the malware's architecture",
        "threshold": round(float(thr), 4),
        "feature_control_classes": {"trivial": redteam.HEADER_BYTES, "moderate": redteam.BASE_FLAGS + redteam.RESOURCES + redteam.IMPORTS + redteam.SECTIONS,
                                    "hard_not_modelled": redteam.NOT_MODELLED},
        "results": res,
        "sensitivity_donors_pool_by_attacker_effort": {"pool_sizes": {k: int(len(v)) for k, v in pools.items()}, "detected": sens},
        "where_the_models_malicious_evidence_sits": evidence,
        "overlay_and_header_edit_demo": overlay_and_header_demo(),
        "caveats": [
            "Feature-space attack: it edits the 54 numbers, not a real binary. Header edits are shown to be expressible on a real "
            "benign file, but not every tier's edit combination was built into a working malware executable.",
            "ImageBase changes need a relinked binary, base relocations, or a wrapper; a pre-built no-relocation executable cannot "
            "simply be rebased.",
            "Donor values come from the same distribution the model was recently fixed on; a model retrained on these donors "
            "would see them as benign, which is the point of an attacker copying them.",
        ],
    }
    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    with open(args.out, "w") as f:
        json.dump(out, f, indent=2)
    chart(res, os.path.join(HERE, "reports", "charts", "fileguard_red_team.png"), source[:80])

    print(f"threshold {thr:.4f} | malware: {source}")
    c = res["clean"]
    print(f"{'no attack':28s} {c['detected']:>3d}/{c['n']:<3d} = {c['rate']:.1%}")
    for t in res["tiers"] + res["solo"]:
        a = t["adaptive"]
        print(f"{t['name']:28s} adaptive {a['detected']:>3d}/{a['n']:<3d} = {a['rate']:6.1%}  (95% CI {a['ci95'][0]:.0%}-{a['ci95'][1]:.0%})   naive single-shot {t['single_shot_detection_rate']:6.1%}")
    print("single features that evade on their own:", json.dumps(res["single_feature"]))
    print("evidence by control class:", json.dumps(evidence["share_of_malicious_evidence"]))
    print("overlay demo:", json.dumps(out["overlay_and_header_edit_demo"], indent=1))
    print(f"wrote {args.out}")


if __name__ == "__main__":
    main()
