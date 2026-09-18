# v4 energy work — split across the 3 streams

Written by the orchestrating session on 2026-09-18, after reading
`SentinelMesh_Project_Brief_v4.pdf` against the current repo state (master,
`6e37dde`). Brief v4 adds a research claim (the battery, not the message, is
the attack surface) and two contributions: a measured energy budget and
EnergyGate, a learned admission gatekeeper in front of the PQC handshake. It
keeps the v3 split of `ml/` (Claude 1) / `console/`+`contracts/` (Claude 2) /
`firmware/` (Claude 3) unchanged — v4 is additive work inside each owner's
existing folder, not a re-org.

**Contract already frozen for this** (`contracts/CHANGELOG.md`, 2026-09-18 —
read the *second* entry of that date, the first was wrong and is marked
superseded): two new `field`-layer event types, `gate_decision` (`details:
{action: spend|challenge|drop, sender?}`, probability-sender-is-real goes in
the Event's existing top-level `score`, not in `details`) and `energy_alert`
(`details: {draw_mw, baseline_mw}`), plus `budget_exhausted` (no required
details); and three new *optional* Trace fields (`battery_pct`,
`frag_complete_pct`, `dup_pct`). Additive only — 46/46 console tests still
pass, and the shapes are verified against real fixture rows (below). Pull
`master` before starting any of the below; do not re-litigate the shape,
raise it in the changelog if it turns out to be wrong.

**Also found this session and copied into the repo:**
`console/frontend-kit/` — a React/Vite starter (not yet wired up; root
`README.md` is still the one-line `# front-end` placeholder) whose
`src/types.ts` says it "mirrors contracts/CONTRACT.md (v1.1)" and whose
fixtures are what fixed the contract shapes above. It assumes a `GET
/status`, `GET /energy` (continuous power/battery samples — deliberately
**not** events, see the changelog), `GET /experiment`, and `POST
/mode`/`POST /attack`/`POST /experiment/run` for demo control. None of
those six are specified in `CONTRACT.md` yet — that's Claude 2's first v4
task below, not something to guess at further.

---

## Claude 1 — `ml/`: EnergyGate model + stretch fingerprinting

1. **`sentinel_ml/energygate.py`** — mirror the existing `field_model.py` /
   `train_field_model.py` pattern (small `DecisionTreeClassifier`, exported to
   C, host-`gcc` parity test), but export a **probability**, not a class:
   `float energygate_score(const float* f)`. The spend/challenge/drop policy
   itself (compare against budget + cost) is firmware's job — it needs live
   budget state this model doesn't have. Keep the split that clean.
2. Feature set = the brief's "free signals," mapped onto the Trace row (v1
   fields + this session's 3 new v4 fields): `rssi_mean`, `rssi_var`,
   `hs_fail`/`hs_per_s` as a completion-rate proxy, `frag_complete_pct`,
   `loss_pct`/`dup_pct`, `battery_pct`. Nothing here requires decrypting or
   verifying anything, per the brief — don't add a feature that does. Your
   score is what ends up as the `gate_decision` event's top-level `score`
   field on the console side (see Claude 2's section) — keep that in mind if
   you're the one who ends up wiring the last mile, though that call site is
   firmware's.
3. Training data: extend `ml/tests/generate_synthetic_traces.py`'s
   `SYNTH_`-labelled generator with the 3 new fields for a parity test now;
   swap to real recordings via `ml/data/traces/` the same way `field_model`
   already does, once console/firmware produce them. Add a `make energygate`
   target to `ml/Makefile` alongside the existing `make field-model`.
4. `energygate.h`'s own inference cost (µs/mJ) is *measured on-device by
   Claude 3*, not estimated here — your job is to keep the tree small enough
   that it plausibly clears "far cheaper than the handshake it protects."
   Say so in the model card, don't invent a number.
5. Stretch, lowest priority (brief's own cut order puts fingerprinting first
   to cut): a short notebook/script on per-node `rssi_mean`/`rssi_var`/
   `jitter_ms` separability. A clean negative result is a fine deliverable —
   write it up honestly in `reports/model_cards.md`, same rule as everything
   else in this repo.
6. Free cleanup while you're in this folder: root `CLAUDE.md` §4 flags that
   `ml/demo/run_demo.py` still defaults to `localhost` (2s/request stall on
   this Windows box vs 2.4ms for `127.0.0.1`, already fixed everywhere in
   `console/`). Fix it if you touch that file.
7. Update `ml/README.md` with an "EnergyGate" section shaped like the
   existing Phase 2 (field model) one.

## Claude 2 — `console/` (+ `contracts/`) + the new frontend

The biggest v4 chunk of console work is standing up `console/frontend-kit/`
into a real app — the root `README.md`'s one-line `# front-end` placeholder
has been sitting there since before this session; the kit turned up in
Downloads today, already scaffolded and fixture-driven. Read
`console/frontend-kit/README.md` first, it's short and specific (poll not
stream, always show `reasons`, one y-axis per chart, never colour alone).

1. **Freeze the six new endpoints first** — this is the actual open contract
   work, not decided by this session because it needs your API/serial
   judgment, not a guess from outside the stream:
   - `GET /status` → `Status` (`console/frontend-kit/src/types.ts`): link
     state, battery, current draw vs baseline, projected days, `mode`
     (`none|ratelimit|cookie|gate`), `attack_profile` (`none|loud|slow_drip`),
     `budget_j`/`budget_max_j`, per-node state.
   - `GET /energy?since=` → `EnergySeries`: `{ts, power_mw, battery_pct,
     volts, amps}` samples + `{ts, label}` markers (e.g. "attack starts",
     "EnergyGate on") — this is the source for the battery-over-time chart,
     brief §6's "chart for the pitch." Deliberately not an event stream.
   - `GET /experiment` → `Experiment`: the five-row table from brief §6,
     each row `{condition, label, energy_j_per_hour, projected_days,
     legit_connect_pct, legit_extra_delay_ms, status}`.
   - `POST /mode {mode}`, `POST /attack {profile}`, `POST /experiment/run
     {condition, profile}` — demo controls. The kit's own comment says these
     "reach the boards over serial" — that's the part to settle with Claude 3:
     does `POST /mode {mode:"gate"}` become a new serial line like the
     existing `LABEL <x>` (e.g. `MODE gate`), and does `attack_profile`
     control reach the attacker board via the gateway relay or a second
     serial port? Whatever you land on, write it into `CONTRACT.md`'s Serial
     lines section and `CHANGELOG.md`, same as always.
   - Write these up as **console-local** (like `/health`, `/recording/*` are
     today) unless one of the other two streams needs to know the exact
     JSON shape independent of you — `/status` and `/energy` plausibly stay
     console-local since only the frontend reads them; the `mode`/`attack`
     serial line(s) are the one piece that's genuinely cross-team.
2. **Stand up the frontend**: `npm create vite@latest` per the kit's README,
   copy `frontend-kit/fixtures/*` → `public/fixtures/`, `src/types.ts` +
   `src/api.ts` → `src/`, build with `VITE_USE_FIXTURES=1` against the
   fixtures before the backend endpoints above even exist — the kit is
   designed for exactly that order. Swap to the real API once `/status` etc.
   are live (delete the fixtures env var, add the `/api` dev proxy per the
   kit's README).
3. **Battery/energy chart**: `GET /energy`'s series, 3 lines (no attack /
   undefended / EnergyGate) with a projected flat-battery date per line.
   One y-axis per chart (the kit's own rule) — never battery % and power
   draw on the same axes.
4. **Per-decision feed**: a live view of `gate_decision` events — `action`
   from `details.action`, the probability from the event's `score`, `reasons`
   always shown (kit rule #2) — same visual language as the existing Why
   panel.
5. **5-row experiment table** (`GET /experiment`) in the Evidence page/UI.
6. **Stand-ins so nothing waits on hardware or the frontend build**: extend
   `tools/mock_events.py` with the "drain attack → switch on EnergyGate"
   beat (brief §8, beats 3–4 — "the moment that sells the project"),
   emitting `gate_decision`/`energy_alert`/`budget_exhausted`; extend
   `tools/mock_serial.py` similarly. Also worth a small mock/fake
   implementation of the new `/status`/`/energy`/`/experiment` endpoints so
   the real frontend (not just its fixture mode) has something to poll
   before firmware exists.
7. `console/demo/RUNBOOK.md`: add the beat-3→4 moment with a fallback, same
   style as the existing entries.
8. Correlation (`api/correlation.py`): leave R1–R5 untouched for v4 —
   `gate_decision`/`energy_alert` are routine telemetry/alerts, not
   cross-layer signals, and nothing in the brief asks for them to form
   incidents. Revisit only if a judge-facing reason to correlate sustained
   `drop`s or a `budget_exhausted` turns up.
9. Once the above lands, update root `CLAUDE.md` §3 (deliverables/status)
   and §4 (hard-won facts) the way you already do — that file is written in
   your voice. Also worth a line there about the frontend existing now, so a
   future cold-start session doesn't miss it the way this session almost did.

## Claude 3 — `firmware/`: the energy rig + the gatekeeper (highest risk)

This stream carries the project's biggest unresolved risk from before v4
even landed: whether ML-DSA-44 fits the ESP32 at all (`firmware/README.md`,
"Biggest open risk"). Everything below sits downstream of that — you can't
measure real handshake energy until a real handshake runs on real hardware.
Flash `env:benchmark` first if that still hasn't happened.

1. **Energy rig**: new `src/monitor/main.cpp` + `platformio.ini` env for the
   second ("Monitor") ESP32 — INA219 over I²C at ~1kHz, reads a GPIO marker
   the field node raises/lowers at each operation's start/end, attributes mJ
   per operation. Extend the existing benchmark CSV shape
   (`algo,op,us,heap_used_bytes,stack_hwm_bytes,ok`) with `mJ`/
   `peak_current_mA` columns sourced from the monitor board (the field node
   can't see its own battery current). Cover: ML-KEM keygen/encaps/decaps
   ×3 levels, ML-DSA-44 sign/verify, AES-256-GCM per KB, radio handshake per
   level, idle/hourly baseline.
2. **Cookie challenge** in the gateway's handshake path: 8-byte value
   derived from a secret + sender id + time; refuse to reassemble until it's
   echoed back. This part isn't novel (DTLS-style) — the brief says so —
   keep it a small, host-testable addition to `lib/sentinel_proto` alongside
   `replay.h`, same convention as everything else there.
3. **Energy token bucket + EnergyGate integration** on the gateway: joules,
   refills over time. Track the new free signals as you go (battery_pct,
   frag_complete_pct, dup_pct — matching the Trace v4 fields) so the
   features you feed `energygate_score()` (from Claude 1's export, once it
   lands) match what it was trained on. Emit one `gate_decision` `EVT` per
   admission decision — `details: {action, sender?}`, put the model's
   probability in the Event's top-level `score`, not in `details` (that's
   what the console side actually expects, corrected this session after an
   initial guess was wrong) — plus `energy_alert` `EVT`s when draw spikes
   over baseline (`details: {draw_mw, baseline_mw}`) and a `budget_exhausted`
   `EVT` when the bucket hits zero.
4. **Attacker**: add the slow-drip profile (~1/min, brief §6 — "sits under
   any fixed rate limit but still drains the cell") alongside the existing
   flood profile in `attacker/main.cpp`. Claude 2 will likely come to you
   wanting a `POST /attack {profile}` from the new frontend to control this
   live during the demo — coordinate whether that becomes a new serial line
   (e.g. `ATTACK loud|slow_drip`) alongside the existing `LABEL <x>`, and
   whether it reaches the attacker board directly or via a gateway relay.
5. **Run the 5-row experiment** (brief §6 table) once 2+ boards and the INA219
   rig exist; hand the CSV/log to Claude 2 for the chart and table above.
6. Stretch, cut first per the brief's own order: radio fingerprinting is
   mostly a reporting exercise on data you're likely already capturing
   (`rssi_mean`/`rssi_var`/`jitter_ms` are already in the Trace schema) — low
   code lift, but only after everything above is solid.
7. Update `firmware/README.md`'s status section the way you already do —
   keep `tools/run_native_tests.sh` green throughout.

---

**Cut order if the clock runs out** (from the brief, unchanged): (1) radio
fingerprinting, (2) the slow-drip attack profile, (3) the learned policy —
fall back to cookie + rate limit and still report the energy numbers, (4)
tamper sensors beyond the light sensor. **Never cut**: the energy
measurements, the five-row comparison, the signed handshake and replay
window.
