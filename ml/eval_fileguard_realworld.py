"""Real-world false-positive test for the committed FileGuard model.

Scores benign binaries the model was never trained on (built by
benign/build_local_benign_features.py from real Windows and installed-app
files) and reports the false-positive rate with Wilson 95% intervals, sliced so
that Windows system files -- which resemble the dataset's own benign class -- do
not flatter the headline number.

    python eval_fileguard_realworld.py [--features benign/features/local_windows_features.csv]

Writes reports/fileguard_realworld_fp.json. It never touches reports/metrics.json.
"""
import argparse
import json
import os

import joblib
import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))


def wilson(k, n, z=1.96):
    if n == 0:
        return [None, None]
    p = k / n
    d = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / d
    half = z * np.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return [round(float(max(0, centre - half)), 4), round(float(min(1, centre + half)), 4)]


def rate(mask):
    n, k = int(mask.size), int(mask.sum())
    return {"n": n, "flagged": k, "rate": round(k / n, 4) if n else None, "ci95": wilson(k, n)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--features", default=os.path.join(HERE, "benign", "features", "local_windows_features.csv"))
    ap.add_argument("--model", default=os.path.join(HERE, "models", "fileguard.joblib"))
    ap.add_argument("--out", default=os.path.join(HERE, "reports", "fileguard_realworld_fp.json"))
    args = ap.parse_args()

    art = joblib.load(args.model)
    model, cols, thr = art["model"], art["cols"], art["threshold"]
    df = pd.read_csv(args.features)
    score = model.predict_proba(df.reindex(columns=cols, fill_value=0))[:, 1]
    df["score"], df["fp"], df["fp_050"] = score, score >= thr, score >= 0.5

    windows = df.category.str.startswith("windows_")
    x86 = df.arch == "x86"
    x64 = df.arch == "x64"
    out = {
        "what": "FileGuard false-positive rate on real benign software the model was not trained on",
        "model": os.path.relpath(args.model, HERE),
        "threshold": round(float(thr), 4),
        "files": int(len(df)),
        "caveat": "Files are trusted install locations on one machine and are assumed benign, not verified. "
                  "This measures false alarms only -- it says nothing about detection.",
        "overall": rate(df.fp.values),
        "overall_at_0.5": rate(df.fp_050.values),
        "apps_only_not_windows_system": rate(df.fp[~windows].values),
        "windows_system_only": rate(df.fp[windows].values),
        "x86": rate(df.fp[x86].values),
        "x64": rate(df.fp[x64].values),
        "apps_x86": rate(df.fp[~windows & x86].values),
        "apps_x64": rate(df.fp[~windows & x64].values),
        "by_category": {c: rate(g.fp.values) for c, g in df.groupby("category")},
        "signed": rate(df.fp[df.signed == 1].values),
        "unsigned": rate(df.fp[df.signed == 0].values),
        "flagged_files_by_app": df[df.fp].groupby("pkg").size().sort_values(ascending=False).to_dict(),
    }
    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    with open(args.out, "w") as f:
        json.dump(out, f, indent=2)

    def show(name, r):
        print(f"{name:34s} {r['flagged']:>4d} / {r['n']:<5d} = {r['rate']:.2%}   95% CI {r['ci95'][0]:.2%} - {r['ci95'][1]:.2%}")

    print(f"threshold {thr:.4f}")
    for k in ["overall", "overall_at_0.5", "apps_only_not_windows_system", "windows_system_only", "x86", "x64", "apps_x86", "apps_x64", "signed", "unsigned"]:
        show(k, out[k])
    print("flagged files by app:", out["flagged_files_by_app"])
    print(f"wrote {args.out}")


if __name__ == "__main__":
    main()
