# Live demo fixtures

**Safety rule (brief section 6 / Q&A prep): no live malware is ever
downloaded, stored or run.** Every "malicious file" beat sends a held-out
feature row to `POST /score/file` as JSON (`{"features": {...}}`), never
an actual executable. Only real, benign files are scanned live via file
upload.

## Build

```
python ../build_all.py --data "path/to/security"      # models + malicious_features.json
python build_demo_fixtures.py --data "path/to/security"  # this folder's fixtures
```

`build_demo_fixtures.py` reuses MailGuard's exact train/val/test split and
FileGuard's exact GroupShuffleSplit (same seeds), so everything here is
genuinely unseen by the models that score it.

## Contents

- `emails/malicious_{1,2,3}.txt` -- held-out malicious emails.
- `emails/malicious_1_padded.txt` -- `malicious_1.txt` padded with legit
  text (the red-team beat: still caught, because the shipped model is
  already adversarially trained).
- `emails/legit_{1,2}.txt` -- held-out legit emails.
- `malicious_features.json` -- 20 held-out malicious PE feature rows
  (built by `build_all.py`).
- `malicious_features_demo.json` -- the first 3 of those, used by the demo.
- `benign_files.txt` -- paths to real benign binaries to scan live, one
  per line. Machine-specific; edit it for your laptop. Defaults to two
  third-party binaries from `ml/benign/extracted/` (prefer these -- they
  demonstrate the bias fix FileGuard needed) plus a Windows system binary.
- `expected.json` -- the demo script, in order: each entry's input and the
  verdict it should get.

## Run

```
python run_demo.py [--ml-url http://127.0.0.1:8001] [--console-url http://127.0.0.1:8000]
```

Scores every entry in `expected.json` against the ML service, prints
actual vs. expected, and POSTs each Event to the console. If nothing at
`--console-url` answers `POST /events` with `201` (contract-defined
success), events are scored but not posted -- this also protects against
silently POSTing into an unrelated service that happens to be listening
on the same port (e.g. Docker Desktop's proxy).
