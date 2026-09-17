"""Build demo/ fixtures: held-out emails (+ one padded), the benign-file
list and expected.json that run_demo.py walks through.

Uses the exact same train/val/test split MailGuard's final model was
fit and threshold-tuned on (sentinel_ml.mailguard, same SEED), so these
emails are genuinely unseen by the model that will score them. Same for
the 3 malicious feature rows: reuses demo/malicious_features.json, which
build_all.py already built from FileGuard's held-out group split.

Usage:
    python build_demo_fixtures.py --data "path/to/security"

Run after build_all.py.
"""
import argparse
import json
import os
import sys

import numpy as np
from sklearn.model_selection import train_test_split

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from sentinel_ml.data import load_emails  # noqa: E402
from sentinel_ml.mailguard import SEED, pad_with_legit  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
EMAILS_DIR = os.path.join(HERE, "emails")

DEFAULT_BENIGN_FILES = """\
# One path per line; lines starting with # are ignored.
# Paths are resolved relative to ml/demo/ unless absolute.
# Edit this for your machine -- prefer real third-party (non-Microsoft)
# binaries, since that's the bias FileGuard's benign augmentation fixes.
# The pip_/npm_ examples below need `python build_benign_features.py`
# (see ../benign/README via build_benign_features.py's docstring) to have
# been run first; they're gitignored, so they won't exist on a fresh clone.
../benign/extracted/pip_numpy/numpy/fft/_pocketfft_umath.cp312-win_amd64.pyd
../benign/extracted/npm_esbuild-win32-x64-0.28.2/package/esbuild.exe
C:\\Windows\\System32\\notepad.exe
"""


def held_out_email_split(security_root):
    em = load_emails(security_root)
    em["t"] = em["text"].str.slice(0, 3000)
    tr, rest = train_test_split(em, test_size=0.3, stratify=em.label, random_state=SEED)
    val, te = train_test_split(rest, test_size=0.5, stratify=rest.label, random_state=SEED)
    return tr, val, te


def write_email(fname, text):
    with open(os.path.join(EMAILS_DIR, fname), "w", encoding="utf-8") as f:
        f.write(text)


def main(security_root):
    os.makedirs(EMAILS_DIR, exist_ok=True)
    tr, val, te = held_out_email_split(security_root)

    mal = te[te.label == 1].sample(3, random_state=11).reset_index(drop=True)
    legit = te[te.label == 0].sample(2, random_state=11).reset_index(drop=True)

    for i, row in mal.iterrows():
        write_email(f"malicious_{i + 1}.txt", row.t)
    for i, row in legit.iterrows():
        write_email(f"legit_{i + 1}.txt", row.t)

    # padded version of malicious_1 -- the red-team beat
    rng = np.random.default_rng(123)
    legit_pool = tr[tr.label == 0].t.str.slice(0, 600).values
    padded = pad_with_legit([mal.loc[0, "t"]], legit_pool, rng)[0]
    write_email("malicious_1_padded.txt", padded)

    # 3 held-out malicious feature rows, reused from build_all.py's output
    with open(os.path.join(HERE, "malicious_features.json")) as f:
        mal_rows = json.load(f)
    demo_rows = mal_rows[:3]
    with open(os.path.join(HERE, "malicious_features_demo.json"), "w") as f:
        json.dump(demo_rows, f, indent=2)

    benign_list_path = os.path.join(HERE, "benign_files.txt")
    if not os.path.exists(benign_list_path):
        with open(benign_list_path, "w") as f:
            f.write(DEFAULT_BENIGN_FILES)
    with open(benign_list_path) as f:
        benign_paths = [l.strip() for l in f if l.strip() and not l.startswith("#")]

    entries = [
        {"id": "malicious_1", "type": "email", "path": "emails/malicious_1.txt",
         "source": mal.loc[0, "source"], "expected_malicious": True,
         "description": f"held-out malicious email ({mal.loc[0, 'source']})"},
        {"id": "malicious_1_padded", "type": "email", "path": "emails/malicious_1_padded.txt",
         "source": mal.loc[0, "source"], "expected_malicious": True,
         "description": "malicious_1 padded with legit text -- red-team beat"},
        {"id": "malicious_2", "type": "email", "path": "emails/malicious_2.txt",
         "source": mal.loc[1, "source"], "expected_malicious": True,
         "description": f"held-out malicious email ({mal.loc[1, 'source']})"},
        {"id": "malicious_3", "type": "email", "path": "emails/malicious_3.txt",
         "source": mal.loc[2, "source"], "expected_malicious": True,
         "description": f"held-out malicious email ({mal.loc[2, 'source']})"},
        {"id": "legit_1", "type": "email", "path": "emails/legit_1.txt",
         "source": legit.loc[0, "source"], "expected_malicious": False,
         "description": f"held-out legit email ({legit.loc[0, 'source']})"},
        {"id": "legit_2", "type": "email", "path": "emails/legit_2.txt",
         "source": legit.loc[1, "source"], "expected_malicious": False,
         "description": f"held-out legit email ({legit.loc[1, 'source']})"},
    ]
    for i in range(len(demo_rows)):
        entries.append({"id": f"malicious_file_{i + 1}", "type": "file_features",
                         "path": "malicious_features_demo.json", "index": i,
                         "expected_malicious": True,
                         "description": "held-out malicious PE feature row"})
    for i, p in enumerate(benign_paths, start=1):
        entries.append({"id": f"benign_file_{i}", "type": "file_upload", "path": p,
                         "expected_malicious": False,
                         "description": "real benign binary, scanned live"})

    with open(os.path.join(HERE, "expected.json"), "w") as f:
        json.dump(entries, f, indent=2)
    print(f"wrote {len(entries)} demo entries to demo/expected.json")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", required=True, help="the unzipped 'security' folder")
    a = ap.parse_args()
    main(a.data)
