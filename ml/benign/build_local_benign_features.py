"""Broaden FileGuard's benign corpus with real software installed on this machine.

The pip/npm third-party set (build_benign_features.py) is developer tooling only,
and the dataset's own benign class is one Windows install. This script samples
what ordinary Windows machines actually contain -- system utilities and drivers,
and installed 32- and 64-bit applications -- and extracts the same 54 header
features with the repo's own extractor (sentinel_ml/pe_features.py).

Read-only: it opens each file with pefile and reads headers. Nothing is executed,
and only trusted install locations are read (never Downloads or user folders).
Sampling is deterministic (seed 42) and capped per app so no single vendor
dominates.

Usage:
    python build_local_benign_features.py [--out features/local_windows_features.csv]

Output columns: the 54 PE features, plus `pkg` (the app or category -- the unit to
hold out), `category`, `arch`, `signed` (has an embedded Authenticode block; NOT a
model feature, recorded for analysis) and `size_bytes`.

App folder names are hashed by default (`app-1a2b3c4d`): the CSV is committed to a
public repo and would otherwise list everything installed on the machine. Grouping
for hold-out is unaffected. Pass --keep-names to write the real names locally.
"""
import argparse
import hashlib
import os
import random
import sys
from concurrent.futures import ProcessPoolExecutor

import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, ".."))
from sentinel_ml import pe_features  # noqa: E402

SEED = 42
MAX_BYTES = 64 * 1024 * 1024
EXTS = (".exe", ".dll", ".sys")
ARCH = {0x14C: "x86", 0x8664: "x64", 0xAA64: "arm64"}

# (category, root, recursive, extensions, per_app_cap, total_cap)
PLAN = [
    ("windows_system32", r"C:\Windows\System32", False, (".exe", ".dll"), None, 900),
    ("windows_syswow64", r"C:\Windows\SysWOW64", False, (".exe", ".dll"), None, 700),
    ("windows_drivers", r"C:\Windows\System32\drivers", False, (".sys",), None, 300),
    ("program_files", r"C:\Program Files", True, (".exe", ".dll"), 30, 1500),
    ("program_files_x86", r"C:\Program Files (x86)", True, (".exe", ".dll"), 30, 800),
    ("user_programs", os.path.expandvars(r"%LOCALAPPDATA%\Programs"), True, (".exe", ".dll"), 30, 500),
]


def _walk(root, recursive, exts):
    if not os.path.isdir(root):
        return
    if not recursive:
        with os.scandir(root) as it:
            for e in it:
                if e.is_file() and e.name.lower().endswith(exts):
                    yield e.path
        return
    for dirpath, _dirs, files in os.walk(root):
        for f in files:
            if f.lower().endswith(exts):
                yield os.path.join(dirpath, f)


def _app_of(root, path):
    rel = os.path.relpath(path, root)
    return rel.split(os.sep)[0] if os.sep in rel else "(root)"


def plan_files():
    rng = random.Random(SEED)
    picked = []
    for category, root, recursive, exts, per_app, total_cap in PLAN:
        by_app = {}
        for p in _walk(root, recursive, exts):
            try:
                if os.path.getsize(p) > MAX_BYTES:
                    continue
            except OSError:
                continue
            app = category if not recursive else f"{category}/{_app_of(root, p)}"
            by_app.setdefault(app, []).append(p)
        chosen = []
        for app, paths in by_app.items():
            paths.sort()
            rng.shuffle(paths)
            for p in (paths if per_app is None else paths[:per_app]):
                chosen.append((category, app, p))
        rng.shuffle(chosen)
        chosen = chosen[:total_cap]
        print(f"  {category:18s} {len(chosen):5d} files from {len(set(a for _, a, _ in chosen)):4d} groups")
        picked.extend(chosen)
    return picked


def extract_one(item):
    import pefile  # noqa: WPS433 (worker process)
    category, app, path = item
    try:
        pe = pefile.PE(path)
        try:
            r = pe_features._extract_fields(pe)
            signed = int(pe.OPTIONAL_HEADER.DATA_DIRECTORY[4].Size > 0)
        finally:
            pe.close()
        r.update(pkg=app, category=category, arch=ARCH.get(r["Machine"], hex(r["Machine"])),
                 signed=signed, size_bytes=os.path.getsize(path))
        return r
    except Exception:
        return None


def anonymise(pkg):
    """windows_* categories have no app folder; anything else becomes category/app-<hash>."""
    if "/" not in pkg:
        return pkg
    category, app = pkg.split("/", 1)
    return f"{category}/app-{hashlib.sha1(app.encode()).hexdigest()[:8]}"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=os.path.join(HERE, "features", "local_windows_features.csv"))
    ap.add_argument("--workers", type=int, default=min(16, os.cpu_count() or 4))
    ap.add_argument("--keep-names", action="store_true", help="write real app folder names (do not commit the result)")
    args = ap.parse_args()

    print("planning sample:")
    items = plan_files()
    print(f"extracting {len(items)} files with {args.workers} workers ...")
    with ProcessPoolExecutor(max_workers=args.workers) as ex:
        rows = [r for r in ex.map(extract_one, items, chunksize=16) if r is not None]
    df = pd.DataFrame(rows)
    if not args.keep_names:
        df["pkg"] = df["pkg"].map(anonymise)
    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    df.to_csv(args.out, index=False)
    print(f"parsed {len(df)} of {len(items)} ({len(items) - len(df)} unparseable, skipped)")
    print(df.groupby(["category", "arch"]).size().to_string())
    print(f"wrote {args.out}")


if __name__ == "__main__":
    main()
