# Contract changelog

Owner: Console / Claude 2. **Every entry here must be announced to all three
streams.** Entries are newest first.

---

## 2026-09-18 — v2 energy delta (additive, frozen ahead of the three streams starting v4 work)

Brief v4 adds EnergyGate (a gatekeeper in front of the PQC handshake) and a
measured energy budget. Two new `field`-layer event types and three new
optional Trace fields, so all three streams can start in parallel against a
frozen shape instead of serializing on a contract discussion:

- **`gate_decision`** — one per admission decision. `details.action` is
  `spend|challenge|drop`, plus `prob_real` (0-1) and `budget_j` (token-bucket
  balance after the decision) are required; `cost_est_mj` is optional.
  Emitted by firmware (Claude 3) each time EnergyGate/the cookie challenge
  runs; the console (me) renders it as the per-decision feed the brief's demo
  beat 4 needs.
- **`energy_sample`** — periodic telemetry, independent of any one decision.
  `details.mj_hour` and `details.source` (`field-1|monitor`) are required,
  `details.battery_pct` optional. This is what feeds the battery-over-time
  chart (brief section 6's closing slide).
- **Trace row**: three new *optional* fields — `battery_pct`,
  `frag_complete_pct`, `dup_pct` — EnergyGate's free signals (ML stream,
  Claude 1, uses these to train it). Not added to `required`: existing
  producers (mocks, any already-recorded sessions) keep validating without
  them, per the same reasoning as `additionalProperties: true` above.

No existing event type, severity mapping, or required field changed. No
serial line format changed — `gate_decision`/`energy_sample` events travel
as ordinary `EVT <json>` lines, same as everything else.

**Still open, not decided by this entry** (each stream's own call, not a
contract question): the token-bucket refill rate and starting balance, the
exact EnergyGate feature set/model format, and how `cost_est_mj` gets
estimated before a handshake it hasn't run yet. Raise here if any of those
turn out to need a shared shape.

---

## 2026-09-18 — schemas added (additive, no semantic change)

Added, alongside the unchanged `CONTRACT.md` v1:

- `event.schema.json` — JSON Schema (draft 2020-12) for the Event shape. The
  console validates every `POST /events` body against it.
- `trace.schema.json` — JSON Schema for the Trace row. The console validates
  every `TRC` line before appending it to a trace file.

**Nothing in `CONTRACT.md` changed.** These files only write down what the prose
already said, so an invalid event fails loudly at the console rather than
quietly at demo time. Two points where the prose was silent and the schema had
to choose — flagged here because they are the parts you might trip over:

1. **Required vs optional fields.** Required: `id`, `ts`, `layer`, `type`,
   `severity`, `summary`. Optional with defaults: `score` (null), `node` (null),
   `technique` (null), `reasons` (`[]`), `details` (`{}`). This keeps
   hand-written firmware JSON from being rejected over an omitted `reasons`.
2. **Conditional `details`.** `attack_detected` must carry `details.kind`
   (`replay_campaign` | `handshake_flood` | `impersonation`) and `rekey` must
   carry `details.level` (512/768/1024) and `details.reason`, exactly as the
   event table says. Both are enforced.

`additionalProperties` is **false** on Event (a typo'd field is a bug worth
catching) and **true** on Trace (so the console can stamp `session` provenance
without breaking producers).

### Console-local HTTP, not part of the cross-team contract

The console serves these beyond the three contract endpoints. No other stream
calls them, so they are not contract surface and can change without an
announcement:

```
GET  /health
GET  /recording                  current trace-recording session + label
POST /recording/start            {"session": "...", "label": "normal"}
POST /recording/stop
POST /recording/label            {"label": "replay"}
GET  /traces                     recorded sessions and row counts
POST /traces                     one Trace row, appended if recording is active
DELETE /events                   clear the demo database
```

The serial bridge is the only client of `POST /traces`; it polls `GET /recording`
and sends `LABEL <x>` down the wire when `label_version` changes.

---

## 2026-09-17 — v1

Initial contract: ports, Event schema and event table, HTTP endpoints, serial
line formats, Trace schema. Frozen so all three streams could start at once.
