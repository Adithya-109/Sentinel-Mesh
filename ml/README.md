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
bash fetch_pip_wheels.sh      # pip download --only-binary=:all: win_amd64 AND win32
                               # for pkg_list_pip.txt (~107 packages), one at a time
                               # so a missing win32 wheel doesn't abort the batch
bash extract_new_wheels.sh    # unzip into extracted/, platform-tagged so
                               # same-named win_amd64/win32 packages don't collide

# a handful more npm Windows-native packages (see git history for the exact list)
npm pack @esbuild/win32-x64 @esbuild/win32-ia32 lightningcss-win32-x64-msvc ... \
  --pack-destination npm_downloads
# untar each .tgz into extracted/npm_<pkg>/

python build_benign_features.py   # -> features/thirdparty_features.csv
```

This produced 1,566 native `.pyd/.dll/.exe/.node` files across 198
packages. Replace with real Program Files binaries when the team collects
them; `build_all.py` picks up whatever is in
`benign/features/thirdparty_features.csv`.

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
curl -X POST http://localhost:8001/score/eml -F "file=@some_message.eml"
```

`/score/eml` (multipart `.eml`) parses headers and an HTML-or-plain body,
scores the body with MailGuard, scores `.exe`/`.dll` attachments with
FileGuard, and returns `file_clean`-style Events with
`details.unsupported=true` for anything else — a list of Events sharing
one `details.message_id` so the console can group them into an incident.

## 5. Run the live-demo script

```
cd demo
python build_demo_fixtures.py --data "path/to/security"
python run_demo.py
```

Walks held-out malicious/legit emails (plus a padded red-team one),
held-out malicious file features, and real benign binaries through the
service, in the brief's demo order, and posts each Event to the console
if one is listening. See `demo/README.md`.

## 6. Phase 2: FieldGuard on-device model

Waits on `data/traces/*.jsonl` (one file per recording session, each line
a `Trace` row per the contract). Once present, one command:

```
make field-model
```

trains the decision tree and writes `export/field_model.h`, exposing
`int classify_window(const float* f)` with no runtime dependency, for the
ESP32 build. `make test-field-model` proves the same pipeline (train ->
C export -> `gcc` compile -> 500-row parity check) against synthetic
`SYNTH_`-labelled data in `ml/tests/` -- never a real result, see that
folder's docstrings.

## Model cards + explanations

`reports/model_cards.md`: each model's data, honest metrics and known
limits (the 64-bit blind spot, 2000-2008 email dates, a re-implemented
feature extractor, and more). `sentinel_ml/reasons.py`: the word/feature
-> plain-English map behind every `Event.reasons` entry.

## Optional: DistilBERT vs. TF-IDF

`notebooks/transformer_mailguard.ipynb` -- brief section 5's "strengthen
at the event" transformer experiment, meant for a free Colab/Kaggle GPU
(not run in this repo). See `notebooks/README.md`.

## Layout

```
sentinel_ml/       data.py, text.py, eml.py, mailguard.py, fileguard.py,
                    field_model.py, reasons.py, schemas.py (Event), pe_features.py
service.py          FastAPI: /health, /score/email, /score/file, /score/eml
build_all.py         trains MailGuard + FileGuard, writes reports/metrics.json
train_field_model.py the real field-model entrypoint (`make field-model`)
benign/              third-party benign binaries + build_benign_features.py
demo/                held-out fixtures + run_demo.py for the live demo
reports/             metrics.json, model_cards.md, charts/*.png (make_charts.py)
export/              field_model.h (phase 2, C export, real traces only)
tests/               synthetic field-model pipeline test (never a real result)
notebooks/           transformer_mailguard.ipynb (optional, GPU-only)
```
