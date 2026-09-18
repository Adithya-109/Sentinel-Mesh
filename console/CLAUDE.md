# Console stream notes (Claude 2)

Written for: the Claude session that owns `console/` and `contracts/`, to
re-orient at the start of a session. Claude Code loads this file only when
working in `console/`; the team-wide rules are in the root `CLAUDE.md` — read
that first. Other streams keep their own notes in their own folders.

**Pull `master` and read the newest `contracts/CHANGELOG.md` entry first** —
other sessions write there too.

## Scope

Owns `console/` and `contracts/`. Reads `ml/` and `firmware/` to check
integration; never edits them — problems there go to the human. Any contract
change gets a `CHANGELOG.md` entry and an announcement to all three streams.

## Deliverables — status (89 tests)

v3:
1. `api/` — FastAPI :8000, SQLite, `POST/GET /events`, `GET /incidents`, every
   event validated against `contracts/event.schema.json`.
2. `bridge/serial_bridge.py` — EVT/TRC/NRG in; LABEL/DEFENSE/MODE out.
   `--port` / `--replay` / `--stdin`. **One bridge per board.**
3. `api/correlation.py` — rules R1–R5, one test each.
4. `ui/app.py` (Streamlit) — the **fallback** UI; still the only one with trace
   recording.
5. `tools/mock_events.py`, `tools/mock_serial.py`.
6. `demo/RUNBOOK.md`.

v4 (`docs/v4_energy_split.md`, Claude 2 section — all nine items done):
- **React console `web/`** (Vite + Recharts), stood up from `frontend-kit/`.
  `npm run build` → the API serves it at **http://127.0.0.1:8000/**.
  `web/src/types.ts` + `api.ts` must stay identical to the kit's copies.
- `api/v4.py`, `energy.py`, `status.py`, `experiment.py`: `/status`, `/energy`,
  `/experiment` (+ run/stop/result), `/mode`, `/attack`, `/control`, `/reset`.
  All also under `/api/*`; `api/frontend.py` adapts `/api/events` +
  `/api/incidents` to the kit's shapes and proxies `/api/scan/*` to ML.
- `tools/mock_rig.py` — SIMULATED rig reacting live to the controls; output
  tagged `source: sim` → SIMULATED banners everywhere.
- Contract: `DEFENSE` / `MODE` / `NRG` serial lines, `energy.schema.json`,
  optional `budget_j`/`budget_max_j` on `gate_decision`.

**Waiting on other streams:** real boards + INA219 rig, `DEFENSE` handling and
`MODE SLOW_DRIP` (Claude 3); the measured experiment table and legit-client
numbers (firmware posts them to `POST /experiment/result`); real trace
recordings for FieldGuard and EnergyGate.

## Console-specific facts (do not re-derive)

- **Trace hand-off verified end to end:** traces recorded through the console
  (label switched per attack) train `ml/`'s EnergyGate unmodified — 180 rows,
  3 sessions, all 5 labels. EnergyGate maps `normal`/`weak_link` → real, the
  rest → not real, and reads the v4 optional fields `frag_complete_pct`,
  `dup_pct`, `battery_pct`, which the stand-ins now emit too.
- `gate_decision` must not correlate (R1). Measured: otherwise mail + file +
  gate decisions = a fake "coordinated attack", and the decision stream holds
  the window open forever. `energy_alert`/`budget_exhausted` do correlate.
- `GET /events` without `since` returns the **newest** `limit`.
- `POST /reset` keeps finished experiment rows (evidence recorded before the
  pitch); drops only a run in progress.
- `/status` returns `null` (UI shows —) and `link: "offline"` without data.
  Projected days = measured draw vs an **assumed** 9.25 Wh cell
  (`SENTINEL_BATTERY_WH`), always labelled an estimate.
- The monitor board's benchmark CSV rows reach the bridge as unrecognised
  lines (counted, harmless). Ask Claude 3 to prefix them `LOG `.
- Streamlit serves HTML before running the script — `tests/test_ui_smoke.py`
  uses `AppTest`. For the React app, look at it: headless Edge
  (`msedge --headless=new --screenshot=out.png --virtual-time-budget=8000 URL`).
- Recharts: SVG attributes don't reliably take CSS `var()` — `web/src/charts.tsx`
  uses hex mirrors of the CSS tokens. Marker labels are thinned (newest-first,
  ≤2, ≥⅓ chart apart) or they smear.
- Scripted Python edits via heredoc can turn `"\n"` into a real newline → syntax
  error. Use the Edit tool for escapes; parse-check after scripted edits.
- A stale uvicorn from an earlier session can hold :8000 and serve old code —
  check `netstat -ano | grep :8000` and the process's command line first.

## Environment

`console/.venv` — Python 3.12 (FastAPI, Streamlit, pyserial, jsonschema,
python-multipart). `console/web` — Node 22, Vite 8, React 19, Recharts 3,
TypeScript 7. See `README.md` and `demo/RUNBOOK.md`.
