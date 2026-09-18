# SentinelMesh demo runbook

Written for: whoever is driving the laptop during the pitch — follow it
top to bottom, including someone who did not write the console.

**Target: about 4 minutes.** Every beat has a fallback that does not need
hardware, and one that does not need the ML service. If something dies, take
the fallback and keep talking — never debug on stage.

---

## 0. Before the judges arrive (15 minutes)

Three terminals, all from the repo root. Leave them running.

```bash
# T1 -- console API
cd console && .venv/Scripts/python -m uvicorn api.main:app --host 127.0.0.1 --port 8000

# T2 -- ML scoring service (the ML stream's; ask them to start it)
cd ml && .venv/Scripts/python -m uvicorn service:app --host 127.0.0.1 --port 8001

# T3 -- console UI
cd console && .venv/Scripts/python -m streamlit run ui/app.py
```

Then the gateway, once boards exist:

```bash
# T4 -- serial bridge (swap COM5 for the gateway's port)
cd console && .venv/Scripts/python -m bridge.serial_bridge --port COM5 -v
```

**Pre-flight checklist — all five must pass:**

```bash
cd console
.venv/Scripts/python -m pytest tests/ -q                      # 46 passed
curl http://127.0.0.1:8000/health                             # "status":"ok"
curl http://127.0.0.1:8001/health                             # mailguard_loaded, fileguard_loaded true
.venv/Scripts/python tools/mock_events.py --dry-run | head -3  # story builds
```

5. Open the UI, confirm the sidebar says **console up**.

**Reset to a clean slate right before you present:**

```bash
curl -X DELETE http://127.0.0.1:8000/events
```

> Always use `127.0.0.1`, never `localhost`. On Windows `localhost` tries IPv6
> first and costs ~2 seconds per request — measured on this laptop at 2047 ms
> vs 2.4 ms. The demo will look broken.

---

## The five beats

### Beat 1 — Inbox (about 45 s)

**Say:** "Attacks on grids start in someone's inbox. This is a real phishing
email from a collection the model has never seen."

1. UI → **Scan** → *Email* tab → paste a held-out malicious email
   (`ml/demo/emails/malicious_1.txt`) → **Scan email**.
2. Point at the verdict and the **top words that drove it** — that is the Why
   panel, straight from the logistic-regression weights.
3. Paste the padded version (`malicious_1_padded.txt`): same email with
   ordinary text stapled on. **Say:** "This is how a spammer evades a filter.
   The baseline model dropped to 16% on this trick. The model we ship is
   adversarially trained, so it still catches it."

- **Fallback (ML service down):** `python tools/mock_events.py` — beat 3 of the
  story is the same email verdict, already scored.

### Beat 2 — Endpoint (about 45 s)

**Say:** "The attachment. We never download or run live malware — malicious
samples are held-out feature rows from the dataset. Only benign files are
scanned live."

1. Scan page → *File* tab → upload a **real benign** binary
   (7-Zip, `esbuild.exe`, or `C:\Windows\System32\notepad.exe`) → allowed.
2. **Say:** "The dataset's benign files all come from one Windows install, so
   the naive model flagged ordinary third-party software as malware. We
   measured it, added benign third-party binaries, and it dropped to under 1%."

- **Safety line, say it out loud:** "No live malware at any point."
- **Fallback:** the mock story's `file_malicious` event carries the same
  top-3 feature contributions.

### Beat 3 — Field network (about 60 s)

**Say:** "Suppose the attacker gets in anyway. Now they are on the radio link
to the field sensor."

1. Attacker ESP32 → replay mode. Gateway rejects it; `replay_rejected` appears
   on the timeline within a second.
2. Attacker → impersonate mode. `handshake_rejected` — **say:** "The handshake
   is signed with ML-DSA. It cannot forge that signature, so it is locked out."

- **Fallback A (boards dead):** replay the recorded serial log — this is why
  it exists:
  ```bash
  cd console
  .venv/Scripts/python -m bridge.serial_bridge --replay demo/serial_log.txt --speed 4 -v
  ```
  Identical EVT/TRC lines, no hardware. Say "recorded from our boards earlier"
  — **do not claim it is live.**
- **Fallback B (bridge dead):** `python tools/mock_events.py`.

### Beat 4 — Physical (about 30 s)

**Say:** "Last layer. Someone opens the enclosure."

1. Open the field node's case. `case_opened` arrives as **critical**; the node
   wipes its session keys, re-handshakes, and comes back green.
2. Point at the `rekey` event that follows: "It recovered on its own, at a
   stronger ML-KEM level."

- **Fallback:** the mock story ends with exactly these two events.

### Beat 5 — The console (about 60 s) — **the point of the whole demo**

**Say:** "Four alerts from four layers. An operator does not want four alerts.
They want one story."

1. UI → **Incidents**. One incident:
   **"Coordinated attack: inbox → endpoint → field network"**, severity
   **critical**.
2. Walk the **attack-chain strip** left to right — Inbox → Endpoint → Field
   network → Physical, all four lit.
3. Open **"Why this severity"**: "base high → critical, because more than one
   layer fired and because mail + file + field together is the Ukraine-2015
   shape."
4. Expand the timeline and show the **Why panel** on two or three alerts, with
   the ATT&CK labels (T1566.001, T1204.002, T0830, T1692.002).
5. **Close with:** "The correlation is rules, not ML, and we say so — that
   keeps it explainable. The machine learning is in the detectors."

---

## If a judge asks

| Question | Answer |
|---|---|
| "Is the correlation ML?" | No — rules, ~80 lines, documented in `console/api/correlation.py` with a test per rule. The ML is in the detectors. |
| "What if two things are unrelated?" | Then they are separate incidents. The window is 10 minutes and configurable; `GET /incidents?window_ms=` shows it live. |
| "Would a clean email make an incident?" | No. Informational events are recorded on the timeline but never form incidents — rule R1. |
| "Is this event format real, or per-demo?" | One contract, `contracts/CONTRACT.md`, frozen before any of the three streams started. Every event is validated against `contracts/event.schema.json` on arrival; invalid ones are rejected with 422. |
| "Did you handle live malware?" | Never. Malicious samples are held-out dataset rows. Only benign files are scanned live. |

---

## Recording traces (not part of the pitch — this is the L3 hand-off)

Do this once the boards work, before the field model is trained.

1. Start the bridge against the real gateway (`--port COM5`).
2. UI → **Trace recording** → name the session → **Start recording**.
3. For each class in turn — `normal`, `weak_link`, `replay`, `flood`,
   `impersonation` — click that label, **then** run the matching mode on the
   attacker node, and leave it for 60–90 seconds.
4. Watch the **mismatch warning**. If it keeps climbing, the label and the
   attack disagree and you are recording mislabelled data — stop and fix it
   before collecting more.
5. **Stop recording.** Check the session table for a sane spread across labels.
6. Hand off to the ML stream:
   ```bash
   cp console/data/traces/*.jsonl ml/data/traces/
   cd ml && make field-model          # -> ml/export/field_model.h
   ```
   Then the firmware stream picks up `field_model.h`.

Rows are validated against `contracts/trace.schema.json` before they are
written — a malformed row is dropped and counted, never silently turned into
zeros in someone's training set.

---

## Emergency card

| Symptom | Do this |
|---|---|
| Console UI says "console API down" | Restart T1. Events already stored survive — SQLite on disk. |
| Timeline empty | `python tools/mock_events.py --clear` |
| Everything looks stale | Sidebar → **Refresh now**, or tick **Auto-refresh (3s)** |
| Scan page errors | ML service is down; skip to the mock story, do not debug |
| Gateway silent | `--replay demo/serial_log.txt`, and say it is a recording |
| Events rejected 422 | A stream changed its event shape. `curl` the error — it names the offending field. Use the mock story and fix after. |
| Total collapse | Play the backup video. Record it by hour 24. |
