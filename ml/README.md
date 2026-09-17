# SentinelMesh ML (MailGuard + FileGuard + FieldGuard)

Owned by the ML stream. Scores emails and files, and (once traces arrive)
classifies FieldGuard windows. Implements the ML side of
`contracts/CONTRACT.md` — every response is a contract `Event`.

## Setup

```
python -m venv .venv
.venv\Scripts\activate        # PowerShell: .venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

## 1. Confirm the brief's numbers

```
python scratch_audit/audit_and_baselines.py --data "path/to/security"
```

Reproduces `SentinelMesh_Project_Brief_v3.pdf`'s numbers (email random-split
vs leave-one-corpus-out, the padding red-team test, the malware group split).
`scratch_audit/` is a gitignored scratch copy of the starter kit — the real
pipeline lives in `sentinel_ml/` and `build_all.py`.

## 2. Build the benign third-party binary set (FileGuard de-biasing)

Until the team's own Program Files / phone binaries arrive, `ml/benign/`
is bootstrapped from ordinary Windows pip wheels and npm packages — never
malware, never anything executed:

```
cd benign
python -m pip download --dest pip_downloads --platform win_amd64 \
  --python-version 312 --implementation cp --abi cp312 --only-binary=:all: --no-deps \
  numpy scipy pillow lxml pywin32 pyzmq cryptography grpcio protobuf psutil \
  pandas pyarrow scikit-learn regex ujson orjson pydantic-core tokenizers watchdog cffi
# unzip each .whl into extracted/pip_<pkg>/ (see build_benign_features.py's docstring for the loop)

npm pack @esbuild/win32-x64 lightningcss-win32-x64-msvc @rollup/rollup-win32-x64-msvc \
  @swc/core-win32-x64-msvc @img/sharp-win32-x64 @img/sharp-libvips-win32-x64 \
  @next/swc-win32-x64-msvc esbuild-windows-64 --pack-destination npm_downloads
# untar each .tgz into extracted/npm_<pkg>/

python build_benign_features.py   # -> features/thirdparty_features.csv
```

This produced 370 native `.pyd/.dll/.exe/.node` files across 27 packages —
in line with the brief's 369-file/27-package set. Replace with real
Program Files binaries when the team collects them; `build_all.py` picks
up whatever is in `benign/features/thirdparty_features.csv`.

## 3. Train MailGuard + FileGuard, write reports/metrics.json

```
python build_all.py --data "path/to/security"
python reports/make_charts.py
```

Writes `models/mailguard.joblib`, `models/fileguard.joblib`,
`demo/malicious_features.json` (held-out malware rows for the live demo —
**no live malware is ever downloaded or run**) and `reports/metrics.json`
+ `reports/charts/*.png`.

## 4. Run the scoring service

```
uvicorn service:app --host 0.0.0.0 --port 8001
```

```
curl http://localhost:8001/health
curl -X POST http://localhost:8001/score/email -H "Content-Type: application/json" \
  -d '{"text": "URGENT: verify your account now"}'
curl -X POST http://localhost:8001/score/file -F "file=@C:/Windows/System32/notepad.exe"
curl -X POST http://localhost:8001/score/file -H "Content-Type: application/json" \
  -d "{\"features\": $(python -c "import json;print(json.dumps(json.load(open('demo/malicious_features.json'))[0]))")}"
```

## 5. Phase 2: FieldGuard on-device model

Waits on `data/traces/*.jsonl` (one file per recording session, each line
a `Trace` row per the contract). Once present:

```python
from sentinel_ml import field_model
clf, metrics = field_model.train("data/traces")
field_model.export_c(clf, "export/field_model.h")
```

`export/field_model.h` exposes `int classify_window(const float* f)` with
no runtime dependency, for the ESP32 build.

## Layout

```
sentinel_ml/       data.py, text.py, mailguard.py, fileguard.py, field_model.py,
                    schemas.py (Event), pe_features.py
service.py          FastAPI: /health, /score/email, /score/file
build_all.py         trains MailGuard + FileGuard, writes reports/metrics.json
benign/              third-party benign binaries + build_benign_features.py
demo/                held-out malicious_features.json for the live demo
reports/             metrics.json + charts/*.png (make_charts.py)
export/              field_model.h (phase 2, C export)
```
