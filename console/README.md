# SentinelMesh console

Written for: the other two streams and anyone picking this up cold.

The integration point. Every layer's alerts arrive here, get validated against
the contract, and are joined into one incident an operator can act on. Owned by
the console stream (Claude 2), which also owns `contracts/`.

- **Do not edit `ml/` or `firmware/` from here.** The console reads
  `ml/reports/` for the Evidence page and writes trace files the ML stream
  consumes, and that is the whole coupling.
- Changes to `contracts/CONTRACT.md` need a `contracts/CHANGELOG.md` entry and
  an announcement to all three streams.

## Setup

```bash
cd console
py -3.12 -m venv .venv
.venv/Scripts/python -m pip install -r requirements.txt
.venv/Scripts/python -m pytest tests/ -q          # 46 passed
```

## Run

```bash
# API on :8000
.venv/Scripts/python -m uvicorn api.main:app --host 127.0.0.1 --port 8000

# UI on :8501
.venv/Scripts/python -m streamlit run ui/app.py

# serial bridge -- one of:
.venv/Scripts/python -m bridge.serial_bridge --port COM5 -v          # real gateway
.venv/Scripts/python -m bridge.serial_bridge --replay demo/serial_log.txt -v
python tools/mock_serial.py | .venv/Scripts/python -m bridge.serial_bridge --stdin -v
```

**Use `127.0.0.1`, not `localhost`.** On Windows `localhost` resolves to `::1`
first and stalls ~2 s per request before falling back to IPv4 — measured here at
2047 ms vs 2.4 ms. Every default in this folder is already `127.0.0.1`; if you
add a URL, keep it that way.

## Stand-ins — nothing waits for another stream

```bash
python tools/mock_events.py                 # the full 5-beat demo story -> :8000
python tools/mock_events.py --speed 20 --clear
python tools/mock_serial.py --scenario replay          # EVT/TRC lines, no hardware
python tools/mock_serial.py --log demo/serial_log.txt --scenario all
```

`mock_events.py` copies the exact `reasons` shapes the real detectors emit, so
the Why panel looks identical whether an event came from MailGuard or the mock.

## HTTP

Contract endpoints (`contracts/CONTRACT.md`):

| | |
|---|---|
| `POST /events` | an Event → 201. Validated against `contracts/event.schema.json`; invalid → 422 naming the field. Re-posting an id is idempotent. |
| `GET /events?since=<ms>` | events after that timestamp (exclusive), oldest first |
| `GET /incidents?window_ms=` | correlated incidents, newest first |

Console-local (not contract surface — see `contracts/CHANGELOG.md`):
`GET /health`, `GET /recording`, `POST /recording/{start,stop,label}`,
`GET /traces`, `POST /traces`, `DELETE /events`.

## How the pieces fit

```
ML service :8001 ─POST /events──┐
                                 ├──> console API :8000 ──> SQLite
gateway ESP32 ──serial──> bridge ┘          │
      ^                                     ├──> correlation.py (rules) ──> /incidents
      └────── LABEL <x> ───────┘            └──> data/traces/<session>.jsonl
                                                        │
                                    UI :8501 (reads the API only)
```

The bridge holds no state: it polls `GET /recording` and sends `LABEL <x>` when
`label_version` changes. That keeps one writer on the serial port and one owner
of the trace files (the API).

## Correlation, in one paragraph

Rules, not ML — deliberately, and it is in the pitch. Informational events never
form incidents (R1). Alerts within a sliding 10-minute window are one incident
(R2). Severity starts at the worst member (R3), escalates one step when two or
more layers fire (R4), and becomes a **critical "coordinated attack"** when
mail + file + field all appear (R5) — the Ukraine-2015 shape. Full reasoning in
`api/correlation.py`; every rule has a test in `tests/test_correlation.py`.

## Layout

```
api/          main.py (FastAPI), db.py (SQLite), correlation.py (the rules),
              validation.py (JSON Schema), attack.py (ATT&CK labels), config.py
bridge/       serial_bridge.py -- serial <-> HTTP, and LABEL back to the gateway
ui/           app.py (Streamlit, 5 pages), theme.py (severity palette)
tools/        mock_events.py, mock_serial.py -- the other streams' stand-ins
demo/         RUNBOOK.md (read this before presenting), serial_log.txt (fallback)
tests/        46 tests: correlation rules, contract validation, API, UI smoke
data/         console.db + traces/<session>.jsonl   (gitignored)
```

## Trace hand-off to the ML stream

The console records TRC windows under the label the operator picked, one
`.jsonl` per session, validated against `contracts/trace.schema.json`. The
operator's label wins over the gateway's; a disagreement is kept as `gw_label`
and counted, and the UI warns when the count climbs — that catches recording one
attack under another attack's name, which would quietly train the field model on
the wrong thing.

```bash
cp console/data/traces/*.jsonl ml/data/traces/
cd ml && make field-model                     # -> ml/export/field_model.h
```
