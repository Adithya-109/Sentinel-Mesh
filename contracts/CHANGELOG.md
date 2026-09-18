# Contract changelog

Owner: Console / Claude 2. **Every entry here must be announced to all three
streams.** Entries are newest first.

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
