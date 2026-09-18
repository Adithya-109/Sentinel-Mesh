# SentinelMesh — working notes for Claude

Written for: me (Claude), to re-orient at the start of any session. Source of
truth for intent is `SentinelMesh_Project_Brief_v3.pdf` (team brief v3,
17 Sep 2026); `contracts/CONTRACT.md` is the source of truth for interfaces.

## 1. Who I am here

**I am Claude 2: the console and integration engineer.**

The project is split into three streams that barely overlap, each on its own
folder, held together by a contract frozen before anyone started:

| | Owns | Builds |
|---|---|---|
| Claude 1 | `ml/` | MailGuard (email) + FileGuard (malware) + the FieldGuard model |
| **Claude 2 — me** | **`console/` and `contracts/`** | **console API, correlation, UI, serial bridge, stand-ins, runbook** |
| Claude 3 | `firmware/` | ESP32 field node / gateway / attacker, ESP-NOW, post-quantum handshake |

**I do not edit `ml/` or `firmware/`.** I read `ml/reports/` for the Evidence
page and write trace files the ML stream consumes — that is the whole coupling.
I own `contracts/`, so if I change `CONTRACT.md` I add a `CHANGELOG.md` entry
and tell the human. Each stream also builds stand-ins for the other two, so
nobody waits.

## 2. What the project is

Hackathon entry for **Code Cortex 3.0, Security track** (30-hour build). Four
detection layers along one attack chain, modelled on the 23 Dec 2015 Ukraine
grid attack — phishing mail → malicious attachment → field network → physical
access — plus a console that joins the alerts into one incident.

| Layer | Detects | Owner |
|---|---|---|
| L1 MailGuard | malicious email | Claude 1 |
| L2 FileGuard | malicious Windows PE | Claude 1 |
| L3 FieldGuard | replay / impersonation on the ESP32 radio link | Claude 1 (model) + 3 (firmware) |
| L4 TamperGuard | case opened / node moved | Claude 3 |
| Console | correlates all four into one incident | **me** |

## 3. My deliverables — status

All built and verified, 46 tests passing:

1. **`console/api`** — FastAPI on :8000. `POST /events`, `GET /events`,
   `GET /incidents`, SQLite storage, every event validated against
   `contracts/event.schema.json` (invalid → 422 naming the field).
2. **`console/bridge/serial_bridge.py`** — pyserial, configurable port. Reads
   `EVT`/`TRC`, sends `LABEL <x>`. Three sources: `--port`, `--replay`,
   `--stdin`, so the demo never depends on hardware.
3. **Correlation** — `api/correlation.py`. Rules only, five of them (R1–R5),
   documented in the module docstring, one test each.
4. **Streamlit UI** — `ui/app.py`. Timeline, Incidents (attack-chain strip +
   Why panel + ATT&CK), Scan (calls ML :8001), Trace recording, Evidence.
5. **Stand-ins** — `tools/mock_events.py` (the 5-beat story),
   `tools/mock_serial.py` (EVT/TRC without hardware).
6. **`console/demo/RUNBOOK.md`** — the demo script with a fallback per beat,
   plus `demo/serial_log.txt` as the hardware-failure fallback.

**Not mine / still open:** real firmware events (Claude 3), real trace
recordings, the L3 model hand-off (`ml/data/traces/` → `make field-model` →
`ml/export/field_model.h` → firmware).

## 4. Hard-won facts (do not re-derive)

- **`127.0.0.1`, never `localhost`.** On this Windows machine `localhost`
  resolves to `::1` first and stalls **2047 ms per request** before falling
  back to IPv4; `127.0.0.1` is **2.4 ms**. It made the serial bridge take
  >120 s to replay 50 lines; after the fix, 0.73 s. Every default in
  `console/` is already `127.0.0.1`. **The ML stream's `demo/run_demo.py` still
  defaults to `localhost` — worth telling Claude 1.**
- Streamlit serves HTML *before* running the script, so "the port answers"
  proves nothing. `tests/test_ui_smoke.py` uses `AppTest` to actually execute
  every page.
- SQLite has no `ADD COLUMN IF NOT EXISTS`; `db.py` carries a tiny migration
  list so a stale `console.db` on the gateway laptop does not crash.
- The console stamps the **operator's** label on trace rows, not the gateway's,
  and counts disagreements as `gw_label` + a UI warning — that catches
  recording one attack under another's name.

## 5. Project-wide rules (from the brief — these are the pitch)

1. **Never download, store or run live malware.** Malicious file demos are
   held-out *feature rows*; only benign files are scanned live.
2. **Honest numbers only** — held-out-corpus and group-split numbers alongside
   the flattering random-split one; detection at a fixed low false-alarm rate,
   not bare accuracy.
3. **Correlation is rules, not ML, and we say so.** The ML lives in the
   detectors. This is a selling point, not an apology.
4. Call L1 a *malicious-email* detector, not a phishing detector.
5. State the blind spots openly: the 64-bit malware gap, the benign class
   coming from one Windows install, `ImageBase` carrying most of the weight.

## 6. Environment

- `console/.venv` — Python 3.12.10, FastAPI, Streamlit, pyserial, jsonschema.
  `ml/.venv` is the ML stream's, separate.
- **The raw `security/` dataset is not on this machine**, so anything needing
  `--data` cannot run here. The ML stream's trained models are committed.
- Run everything from `console/`; see `console/README.md`.

## 7. Measured ML numbers vs the brief (for the Evidence page)

Quote **ours** (`ml/reports/metrics.json`), not the brief's, where they differ.
The one material discrepancy: the brief says the dataset-only model flagged
**42%** of benign third-party software; the repo measured **18.1%**. The bias is
real but smaller. **Do not repeat "42%" as our own result.**
