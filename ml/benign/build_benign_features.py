"""Build the benign third-party PE feature set used to de-bias FileGuard.

We never had the team's own Program-Files binaries in time, so this script
builds a stand-in set the same way: pull prebuilt native binaries out of
ordinary Windows pip wheels and npm packages (never source-built, never
executed) and extract the same 54 header features malware.csv uses.

Usage:
    python build_benign_features.py

Reads every .pyd/.dll/.exe/.node file under extracted/<source>_<pkg>/...
and writes features/thirdparty_features.csv with columns: the 54 PE
features, `path` (relative to extracted/) and `pkg` (the top-level package
folder, used to hold out whole packages at evaluation time).
"""
import glob
import os
import sys

import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "sentinel_ml"))
from pe_features import extract  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
EXTRACTED = os.path.join(HERE, "extracted")
OUT = os.path.join(HERE, "features", "thirdparty_features.csv")


def main():
    rows, failed = [], 0
    for path in glob.glob(os.path.join(EXTRACTED, "**", "*"), recursive=True):
        if not os.path.isfile(path):
            continue
        if not path.lower().endswith((".exe", ".dll", ".pyd", ".node")):
            continue
        try:
            r = extract(path)
        except Exception:
            failed += 1
            continue
        rel = os.path.relpath(path, EXTRACTED)
        r["path"] = rel
        r["pkg"] = rel.split(os.sep)[0]  # e.g. "pip_numpy", "npm_esbuild-win32-x64-0.28.2"
        rows.append(r)

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    df = pd.DataFrame(rows)
    df.to_csv(OUT, index=False)
    print(f"extracted features for {len(df)} files ({df.pkg.nunique()} packages), {failed} failed")
    print(f"wrote {OUT}")


if __name__ == "__main__":
    main()
