# SentinelMesh — notes for every Claude session in this repo

Written for: any Claude session working here, whichever stream it belongs to.
Claude Code loads this file into every session, so it holds only what is true
for all of them. Stream-specific notes live in that stream's own folder.

## Which stream are you?

The work is split across three Claude sessions, each owning one folder. **Your
human tells you which one you are. If you have not been told, ask — do not
infer it from the folder you happen to be in.**

| Stream | Owns | Builds | Stream notes |
|---|---|---|---|
| Claude 1 — ML | `ml/` | MailGuard, FileGuard, FieldGuard model, EnergyGate model | `ml/README.md` |
| Claude 2 — console + integration | `console/`, `contracts/` | console API, correlation, React console, serial bridge, runbook | `console/CLAUDE.md` |
| Claude 3 — firmware | `firmware/` | ESP32 field node, gateway, attacker, INA219 monitor | `firmware/README.md` |

- **Edit only your own folder.** You may read the others to check integration;
  report problems in someone else's folder to the human instead of fixing them.
- `docs/` holds cross-stream plans (`v4_energy_split.md` — who does what in v4;
  `hardware_setup.md` — the energy rig). Whoever is orchestrating edits those.
- A stream may add its own `CLAUDE.md` inside its folder; Claude Code loads it
  when working there. Never put stream-specific instructions in this file.

## The project

Hackathon entry for **Code Cortex 3.0, Security track**. Four detection layers
along the 2015 Ukraine grid attack chain — phishing email → malicious
attachment → field network → physical access — plus a console that joins their
alerts into one incident. **v4** adds a research claim, *the battery, not the
message, is the attack surface*, with a measured energy budget and
**EnergyGate**, a learned gatekeeper in front of the post-quantum handshake
(spend / challenge / drop).

Sources of truth: the team briefs (v3; v4 summarised in
`docs/v4_energy_split.md`) for intent, and `contracts/` for every interface.

## Working rules for all streams

1. **Pull `master` before starting, and read the newest entry in
   `contracts/CHANGELOG.md`.** Other sessions change shared shapes.
2. **The contract is the interface.** `contracts/CONTRACT.md` plus the JSON
   Schemas beside it. The console validates every event, trace row and energy
   sample on arrival and rejects mismatches with a 422 that names the field.
   To change a shape, ask the console stream (Claude 2), which owns
   `contracts/`; every change gets a `CHANGELOG.md` entry announced to all three.
3. **Never download, store or run live malware.** Malicious-file demos are
   held-out dataset feature rows; only benign files are scanned live.
4. **Honest numbers only.** Report held-out and group-split results next to the
   flattering random-split ones, and detection at a fixed low false-alarm rate
   rather than bare accuracy. Anything simulated is labelled SIMULATED and never
   presented as a result. Quote the repo's measured numbers
   (`ml/reports/metrics.json`), not the brief's, where they differ.
5. **Correlation is rules, not ML** — the ML lives in the detectors. Say so.
6. **Build stand-ins for the other streams** so nobody blocks on anybody.

## Facts that bite every stream

- **Use `127.0.0.1`, never `localhost`.** On the team's Windows laptop,
  `localhost` tries IPv6 first and stalls ~2 s per request (2047 ms vs 2.4 ms).
- **Board timestamps are uptime, not wall-clock.** ESP32s have no clock, and
  `new_event()` takes `uint32_t` (epoch ms does not fit). The console replaces any
  `ts` below 1e12 with arrival time and keeps the original as
  `details.device_ts`, so boards need not sync time.
- **EnergyGate runs on field-1, not the gateway.** It protects the battery the
  INA219 measures, and the gateway is USB-powered. field-1 answers inbound
  `HELLO`s and runs the score, joule budget, cookie and spend/challenge/drop
  policy; the attacker's flood targets it. The gateway relays the console's
  `DEFENSE <none|ratelimit|cookie|gate>` to field-1 over the mesh and relays
  field-1's decisions back as `gate_decision` events with `"node": "field-1"`.
  (An early plan put it on the gateway; brief v4 sections 1-4 say otherwise.)
- **`MODE` belongs to the attacker board** (`MODE REPLAY|FLOOD|...`). The
  console sends every control line to every board it is connected to; boards
  ignore lines that are not theirs.
- **EnergyGate's 8 features use `ml/sentinel_ml/energygate.py`'s
  `FEATURE_ORDER`** on both sides: `hs_per_s, hs_fail, rssi_mean, rssi_var,
  loss_pct, dup_pct, frag_complete_pct, battery_pct`.
- **The raw `security/` dataset is not in the repo** (and not on every
  machine). Anything taking `--data` needs its path from the human. Trained
  models are committed.
- Recorded trace files hand off console → ML by copying
  `console/data/traces/*.jsonl` into `ml/data/traces/`.
