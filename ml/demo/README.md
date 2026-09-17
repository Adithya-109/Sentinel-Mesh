# Demo malicious samples

`malicious_features.json` is a list of 54-feature PE rows, sampled from
`malware.csv` rows held out of FileGuard's training/threshold-tuning split
(built by `build_all.py`, same GroupShuffleSplit + group key FileGuard's
evaluation uses, so these are genuinely unseen by the model that scores
them).

**Safety rule (brief section 6 / Q&A prep): no live malware is ever
downloaded, stored or run.** The "malicious file" beat in the demo sends
one of these feature rows to `POST /score/file` as JSON
(`{"features": {...}}`), never an actual executable. Only real, benign
files (e.g. 7-Zip) are scanned live via file upload.
