# SentinelMesh demo runbook

Written for: whoever is driving the laptop during the pitch — follow it
top to bottom, including someone who did not write the console.

**Target: about 5 minutes.** Every beat has a fallback that needs no hardware.
If something dies, take the fallback and keep talking — never debug on stage.

> Beat order follows brief v3 §10, with brief v4's drain → EnergyGate moment
> inserted after the field-network beat. If brief v4 §8 orders it differently,
> follow the brief; each beat below stands on its own.

---

## 0. Before the judges arrive (20 minutes)

### Once per laptop

```bash
cd console
py -3.12 -m venv .venv && .venv/Scripts/python -m pip install -r requirements.txt
cd web && npm ci && npm run build        # -> console/web/dist, served by the API at /
```

### Terminals — all from `console/`, leave them running

```bash
# T1 -- console API + the React console at http://127.0.0.1:8000/
.venv/Scripts/python -m uvicorn api.main:app --host 127.0.0.1 --port 8000

# T2 -- ML scoring service (the ML stream's; from ml/)
.venv/Scripts/python -m uvicorn service:app --host 127.0.0.1 --port 8001

# T3.. -- one serial bridge PER BOARD. Every bridge sends every control line to its
#         board; each board ignores the lines that are not its own.
.venv/Scripts/python -m bridge.serial_bridge --port COM5 -v      # gateway
.venv/Scripts/python -m bridge.serial_bridge --port COM6 -v      # attacker
.venv/Scripts/python -m bridge.serial_bridge --port COM7 -v      # INA219 monitor (NRG lines)
```

No boards yet, or a board dies? Replace the bridges with the simulator (see
"Fallbacks" — and say so out loud):

```bash
.venv/Scripts/python tools/mock_rig.py          # SIMULATED rig: power, gate decisions, alerts
```

Open **http://127.0.0.1:8000/** full-screen on the projector.
(Streamlit fallback UI: `.venv/Scripts/python -m streamlit run ui/app.py`.)

### Pre-flight — all must pass

```bash
.venv/Scripts/python -m pytest tests/ -q            # all pass
curl http://127.0.0.1:8000/health                   # "status":"ok"
curl http://127.0.0.1:8001/health                   # mailguard_loaded, fileguard_loaded true
curl http://127.0.0.1:8000/control                  # the lines the bridges will send
```

- The console's header says **console API connected**.
- Every bridge terminal printed `-> LABEL ...`, `-> DEFENSE ...`, `-> MODE ...`
  on start-up (it pushes current state so rebooted boards resync).
- The **Field link** tile shows the gateway and field-1 **not** offline.
- If a yellow **SIMULATED** banner is showing and the rig *is* connected, a
  `mock_rig.py` is still running somewhere — stop it.

### Record the experiment table (before the pitch, not during it)

Needs the INA219 rig. In the console's **Energy experiment** card, pick the
attack profile, set the run length (default 120 s), and click **Run** on each
row in turn: No attack → Attack, no defence → Rate limit → Cookie → EnergyGate.
Each run sets the defence and the attack itself and stops the attacker when it
ends. Then post the firmware's legit-client numbers per row:

```bash
curl -X POST http://127.0.0.1:8000/experiment/result -H "Content-Type: application/json" \
  -d '{"condition":"gate","profile":"loud","legit_connect_pct":97,"legit_extra_delay_ms":120}'
```

The console never fills those two columns itself — it cannot see the legit
client. Rows recorded from `mock_rig.py` are marked **SIMULATED**: never show
those as results.

### Reset right before you present

**Reset demo** button (top right of the controls), or `curl -X POST http://127.0.0.1:8000/reset`.
It clears events, energy samples and markers, and sets the controls back to
off. It **keeps** the finished experiment rows and the recorded trace files —
those are evidence (only an in-progress run is dropped). To clear the table on
purpose: `curl -X DELETE http://127.0.0.1:8000/experiment`.

> Always `127.0.0.1`, never `localhost`: on this laptop `localhost` costs ~2 s
> per request (IPv6 first). Every default in `console/` already avoids it.

---

## The beats

### Beat 1 — Inbox (about 40 s)

**Say:** "Attacks on grids start in someone's inbox. This email comes from a
collection the model has never seen."

1. **Scan** card → paste `ml/demo/emails/malicious_1.txt` → **Scan email**.
   Point at the verdict and its three reasons, in plain English.
2. Paste `malicious_1_padded.txt` (same email with ordinary text stapled on).
   **Say:** "Padding like this dropped the baseline model to 16%. The shipped
   model is adversarially trained, so it still catches it."

- **Fallback (ML service down):** `python tools/mock_events.py --story classic`
  — it posts the same verdict, pre-scored.

### Beat 2 — Endpoint (about 40 s)

**Say:** "The attachment. We never download or run live malware — malicious
samples are held-out feature rows. Only benign files are scanned live."

1. Scan card → choose a **benign** binary (`esbuild.exe`, 7-Zip, or
   `C:\Windows\System32\notepad.exe`) → **Scan file** → allowed.
2. **Say:** "The dataset's benign files all come from one Windows install, so
   the naive model flagged about 40% of ordinary third-party software. We added
   1,566 benign third-party binaries; under half a percent now."

### Beat 3 — Field network (about 40 s)

**Say:** "Suppose the attacker gets onto the radio link."

1. **Attack → Replay.** `replay_rejected` appears on the timeline.
2. **Attack → Impersonate.** `handshake_rejected` — **say:** "The handshake is
   signed with ML-DSA; it cannot forge that, so it's locked out."
3. **Attack → None.**

- **Fallback:** `.venv/Scripts/python -m bridge.serial_bridge --replay demo/serial_log.txt --speed 4 -v`
  — "recorded from our boards earlier". **Do not claim it is live.**

### Beat 4 — The drain (about 45 s) — *brief v4: the battery is the attack surface*

**Say:** "Now the attack nobody defends against. Nothing here is forged. The
attacker just asks the node to do expensive post-quantum handshakes — and the
battery pays."

1. Defence → **No defence**. Attack → **Loud flood**.
2. Point at the **Power draw** chart jumping and the **Draw now** tile's
   "× idle" multiple; the **Projected life** tile falls from weeks to about a day.
   An `energy_alert` lands on the timeline.

### Beat 5 — EnergyGate (about 45 s) — *the moment that sells the project*

**Say:** "Same attack. Now EnergyGate decides, before any crypto runs, whether
this sender is worth paying for."

1. Defence → **EnergyGate**. The "EnergyGate on" marker appears on both charts.
2. Point at the **EnergyGate decisions** feed: unknown sender **CHALLENGE**,
   then **DROP** when the cookie never comes back, each with its reasons;
   field-1 still gets **SPEND**. Draw falls back toward idle.
3. Point at **Battery projection** (from the recorded experiment): the three
   lines and their flat-battery dates. **Say** which numbers are measured and
   that the day counts assume the cell's rated capacity.
4. Attack → **None**.

- **Fallback (rig dead):** run `tools/mock_rig.py` and click the same buttons.
  The **SIMULATED** banner appears — say "this is the simulator; the measured
  table is here" and point at the experiment card. **Never** present simulated
  numbers as results.
- **Fallback (no clicking possible):** `python tools/mock_events.py --story drain`.

### Beat 6 — Physical (about 30 s)

**Say:** "Last layer. Someone opens the enclosure."

1. Open the field node's case. **Field link** goes **TAMPER**; keys are wiped,
   a fresh handshake runs, and a `rekey` event follows.

- **Fallback:** `python tools/mock_events.py --story classic` ends with exactly
  these two events.

### Beat 7 — One incident (about 45 s) — *the point of the console*

**Say:** "Alerts from four layers. An operator doesn't want four alerts; they
want one story."

1. **Incidents** card: **"Coordinated attack: inbox → endpoint → field
   network"**, critical. Walk the chain strip: Inbox → Endpoint → Field network
   → Physical, all **HIT**.
2. Read the **Why critical** line: "more than one layer fired, and mail + file +
   field together is the Ukraine-2015 shape."
3. **Close:** "The correlation is rules, not ML — so we can explain every alert.
   The machine learning is in the detectors, and EnergyGate is the one deciding
   what the battery is allowed to spend."

---

## If a judge asks

| Question | Answer |
|---|---|
| "Is the correlation ML?" | No — five documented rules in `console/api/correlation.py`, one test each. |
| "Why aren't EnergyGate decisions in the incident?" | They're telemetry — one per admission decision. Counting them would fake a "coordinated attack" and hold incidents open forever; we measured both. The drain itself (`energy_alert`) does correlate. |
| "Are those battery numbers real?" | The experiment rows marked measured came from the INA219 rig. The day counts are projections: measured draw against the cell's rated capacity. Anything from the simulator is labelled SIMULATED. |
| "Is the event format real?" | One contract, frozen before the three streams started; every event is validated on arrival (`contracts/event.schema.json`), invalid ones rejected with a 422. |
| "Did you handle live malware?" | Never. Malicious samples are held-out dataset rows. |

---

## Recording field-model traces (the L3 hand-off, not part of the pitch)

Streamlit UI → **Trace recording** (the React console does not have this page).

1. Name the session → **Start recording**.
2. For each class — `normal`, `weak_link`, `replay`, `flood`, `impersonation` —
   click the label, **then** start that attack, and leave it 60–90 s.
3. Watch the **mismatch warning**: if it climbs, the label and the attack
   disagree — stop and fix it.
4. **Stop recording**, then hand off:
   ```bash
   cp console/data/traces/*.jsonl ml/data/traces/
   cd ml && make field-model          # -> ml/export/field_model.h
   ```

---

## Emergency card

| Symptom | Do this |
|---|---|
| Header says "console API unreachable" | Restart T1. Stored events survive (SQLite on disk). |
| Page is blank at http://127.0.0.1:8000/ | `web/dist` missing: `cd web && npm run build`, restart T1. Or use Streamlit. |
| Button pressed, board didn't react | Check that board's bridge printed `-> DEFENSE` / `-> MODE`. If not, restart that bridge. |
| Tiles show "—" | No data yet — that's honest, not a bug. Start the rig or `mock_rig.py`. |
| SIMULATED banner when it shouldn't be | A `mock_rig.py` is still running. Stop it, **Reset demo**. |
| Events rejected 422 | A stream changed its event shape; the bridge log names the field. Use the mock story, fix after. |
| Gateway silent | `--replay demo/serial_log.txt`, and say it is a recording. |
| Total collapse | Play the backup video. |
