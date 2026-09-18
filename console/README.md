# SentinelMesh console

Written for: the other two streams and anyone picking this up cold.

The integration point. Every layer's alerts arrive here, get validated against
the contract, and are joined into one incident an operator can act on. Since v4
it also holds the energy telemetry, the demo controls and the experiment table,
and serves the React console. Owned by the console stream (Claude 2), which also
owns `contracts/`.

- **Do not edit `ml/` or `firmware/` from here.** The console reads
  `ml/reports/` for the Streamlit Evidence page and writes trace files the ML
  stream consumes, and that is the whole coupling.
- Changes to `contracts/CONTRACT.md` need a `contracts/CHANGELOG.md` entry and
  an announcement to all three streams.

## Setup

```bash
cd console
py -3.12 -m venv .venv
.venv/Scripts/python -m pip install -r requirements.txt
.venv/Scripts/python -m pytest tests/ -q          # 92 passed

cd web && npm ci && npm run build                  # React console -> web/dist
```

## Run

```bash
# API on :8000 -- also serves the React console at http://127.0.0.1:8000/
.venv/Scripts/python -m uvicorn api.main:app --host 127.0.0.1 --port 8000

# one serial bridge per board (gateway, attacker, INA219 monitor)
.venv/Scripts/python -m bridge.serial_bridge --port COM5 -v
.venv/Scripts/python -m bridge.serial_bridge --replay demo/serial_log.txt -v   # no hardware
python tools/mock_serial.py | .venv/Scripts/python -m bridge.serial_bridge --stdin -v

# fallback UI (Streamlit) on :8501 -- also the only UI with trace recording
.venv/Scripts/python -m streamlit run ui/app.py
```

Frontend development with hot reload (proxies `/api` to :8000):

```bash
cd web && npm run dev                  # against the live API
cd web && npm run dev:fixtures         # against frontend-kit's fixtures, no backend at all
```

**Use `127.0.0.1`, not `localhost`.** On this Windows machine `localhost`
resolves to `::1` first and stalls ~2 s per request (measured 2047 ms vs
2.4 ms). Every default in this folder, including the Vite proxy, avoids it.

## Stand-ins — nothing waits for another stream

```bash
python tools/mock_rig.py                     # SIMULATED v4 rig: power samples, gate decisions,
                                             #   energy alerts -- reacts live to the demo controls
python tools/mock_events.py                  # classic 5-beat story, then the drain -> EnergyGate beat
python tools/mock_events.py --story drain --speed 4
python tools/mock_serial.py --scenario flood # EVT / TRC / NRG lines, no hardware
python tools/mock_serial.py --log demo/serial_log.txt --scenario all
```

Everything the rig produces is tagged `source: "sim"`; the console then shows a
SIMULATED banner and marks any experiment row it touched. Its draw figures mirror
the brief's hypothesis — they illustrate it, they are not evidence for it.

`mock_events.py`'s `reasons` are verbatim output of the ML stream's
`sentinel_ml/reasons.py`, so the Why panel looks identical either way.
`mock_serial.py` stamps board uptime, like real firmware, so a replayed log lands
at replay time and still correlates with live events.

## HTTP

Contract endpoints (`contracts/CONTRACT.md`):

| | |
|---|---|
| `POST /events` | an Event → 201. Validated against `contracts/event.schema.json`; invalid → 422 naming the field. A `ts` below 1e12 (board uptime) is replaced with arrival time. Re-posting an id is idempotent. |
| `GET /events?since=<ms>` | after that timestamp (exclusive), oldest first; without `since`, the newest `limit` |
| `GET /incidents?window_ms=` | correlated incidents, newest first |

Console-local (not contract surface — see `contracts/CHANGELOG.md`):

| | |
|---|---|
| `GET /status` | the top bar: link state, battery, draw vs idle, projected days, budget, per-node state. `null` wherever there is no data yet |
| `GET /energy?since=`, `POST /energy` | INA219 samples (+ chart markers); the bridge posts NRG lines here |
| `GET /experiment?profile=`, `POST /experiment/{run,stop,result}`, `DELETE /experiment` | the five-row table |
| `POST /mode {mode}`, `POST /attack {profile}`, `GET /control` | demo controls; the bridge polls `/control` |
| `POST /reset` | clear events, energy and controls (keeps finished experiment rows and trace files) |
| `GET /health`, `/recording/*`, `/traces` | liveness and trace recording |
| `/api/*` | all of the above for the React app, plus `/api/events` and `/api/incidents` in `frontend-kit/src/types.ts` shapes and `/api/scan/{email,file}` (the console calls the ML service and stores the verdict) |

## How the pieces fit

```
ML service :8001 <--- /api/scan/* ----.
                                       |
boards --serial--> bridges --HTTP-->  console API :8000 --> SQLite (events, energy,
  ^   (EVT/TRC/NRG)                    |  |                          experiment, controls)
  |                                    |  '--> correlation.py (rules) --> /incidents
  '-- LABEL / DEFENSE / MODE <-- GET /control
                                       |
             React console (web/dist, served at /)  ·  Streamlit fallback (:8501)
```

The bridges hold no state: each polls `GET /control` and sends a line when that
line's version changes, to its own board. Every board gets every line and ignores
the ones that are not its own, so no bridge needs to know which board it is on.

## Correlation, in one paragraph

Rules, not ML — deliberately, and it is in the pitch. Informational events and
EnergyGate's per-decision `gate_decision` telemetry never form incidents (R1).
Alerts within a sliding 10-minute window are one incident (R2). Severity starts at
the worst member (R3), escalates one step when two or more layers fire (R4), and
becomes a critical **"coordinated attack"** when mail + file + field all appear
(R5). Reasoning in `api/correlation.py`; every rule has a test.

## Layout

```
api/       main.py (FastAPI + store_event), correlation.py (the rules), db.py (SQLite),
           validation.py (JSON Schema), attack.py (ATT&CK labels), config.py
           v4.py (status/energy/experiment/controls), energy.py, status.py,
           experiment.py, frontend.py (/api shapes + scan proxy)
bridge/    serial_bridge.py -- serial <-> HTTP, control lines back to the boards
web/       the React console (Vite + Recharts); src/types.ts + api.ts mirror frontend-kit/.
           Two routes: "/" a landing page, "/dashboard" the sidebar+tabs operator console
           (Overview/Events/Incidents/Energy/Experiment/Scan). Visual design (palette, the
           mesh-canvas background, the tilt-on-hover cards, the quantum-core hero visual)
           ported from a separately-contributed Front-End/ folder (now removed -- its
           design lives here, its data wiring was fixture-only and never real).
frontend-kit/  the kit as delivered: fixtures + the reference types.ts/api.ts
ui/        Streamlit fallback UI (5 pages, incl. trace recording)
tools/     mock_rig.py, mock_events.py, mock_serial.py -- the other streams' stand-ins
demo/      RUNBOOK.md (read before presenting), serial_log.txt (hardware fallback)
tests/     92 tests: rules, contract validation, API, v4, bridge, stand-ins, UI smoke
data/      console.db + traces/<session>.jsonl   (gitignored)
```

## Trace hand-off to the ML stream

Record in the Streamlit **Trace recording** page. Rows are validated against
`contracts/trace.schema.json`; the operator's label wins over the gateway's, and
disagreements are counted and warned about.

```bash
cp console/data/traces/*.jsonl ml/data/traces/
cd ml && make field-model                     # -> ml/export/field_model.h
```
