# v4 energy work — split across the 3 streams

Written by the orchestrating session on 2026-09-18, after reading
`SentinelMesh_Project_Brief_v4.pdf` against the current repo state (master,
`6e37dde`). Brief v4 adds a research claim (the battery, not the message, is
the attack surface) and two contributions: a measured energy budget and
EnergyGate, a learned admission gatekeeper in front of the PQC handshake. It
keeps the v3 split of `ml/` (Claude 1) / `console/`+`contracts/` (Claude 2) /
`firmware/` (Claude 3) unchanged — v4 is additive work inside each owner's
existing folder, not a re-org.

**Contract already frozen for this** (`contracts/CHANGELOG.md`, 2026-09-18,
"v2 energy delta"): two new `field`-layer event types (`gate_decision`,
`energy_sample`) and three new *optional* Trace fields (`battery_pct`,
`frag_complete_pct`, `dup_pct`). Additive only — 46/46 console tests still
pass. Pull `master` before starting any of the below; do not re-litigate the
shape, raise it in the changelog if it turns out to be wrong.

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
   verifying anything, per the brief — don't add a feature that does.
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

## Claude 2 — `console/` (+ `contracts/`, already updated this session)

1. **Battery/energy chart**: new Evidence-page (or new tab) view reading
   `energy_sample` events — 3 lines (no attack / undefended / EnergyGate)
   with a projected flat-battery date per line, per brief §6's "chart for
   the pitch."
2. **Per-decision feed**: a live view of `gate_decision` events (action,
   `prob_real`, `budget_j`) — same visual language as the existing Why panel.
3. **5-row experiment table** (brief §6: energy/hour, projected days,
   legit-still-connects, extra delay) in the Evidence page, sourced from
   firmware's bench log once it exists.
4. **Stand-ins first, so nothing waits**: extend `tools/mock_events.py` with
   a mock "drain attack → switch on EnergyGate" beat (brief §8, beats 3–4 —
   "the moment that sells the project") and `tools/mock_serial.py` with a
   scenario emitting `gate_decision`/`energy_sample` lines, so the chart and
   feed above can be built and demoed today against fake data.
5. `console/demo/RUNBOOK.md`: add that beat with a fallback, same style as
   the existing runbook entries.
6. Correlation (`api/correlation.py`): recommend leaving R1–R5 untouched for
   v4 — `gate_decision`/`energy_sample` are routine telemetry, not alerts,
   and R1 already excludes `info`-severity events from incidents. Only
   revisit if a judge-facing reason to correlate sustained `drop`s turns up.
7. You own `contracts/` day to day — the v2 delta this session made is
   already committed and changelogged; from here, any further contract
   change while building the above is yours to make (and changelog) as
   normal.
8. Once the above lands, update root `CLAUDE.md` §3 (deliverables/status)
   and §4 (hard-won facts) the way you already do — that file is written in
   your voice.

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
   admission decision and periodic `energy_sample` `EVT`s, per the contract
   delta above.
4. **Attacker**: add the slow-drip profile (~1/min, brief §6 — "sits under
   any fixed rate limit but still drains the cell") alongside the existing
   flood profile in `attacker/main.cpp`.
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
