# SentinelMesh integration contract v1 + v2-energy delta (owner: Console/Claude 2. Announce any change to all three.)

## Ports / transport
- Console API: http://localhost:8000
- ML scoring service: http://localhost:8001
- Gateway ESP32 -> console: USB serial, 115200 baud, one message per line

## Event: every layer emits exactly this JSON
{ "id": "uuid4", "ts": <epoch ms>, "layer": "mail|file|field|tamper", "type": "<see table>",
  "severity": "info|low|medium|high|critical", "score": <0..1 or null>,
  "node": "field-1|gateway|attacker|null", "technique": "<ATT&CK id or null>",
  "summary": "<one line for the timeline>", "reasons": ["<top 3 reasons>"], "details": {} }

| layer  | type                                             | technique  | severity |
|--------|--------------------------------------------------|------------|----------|
| mail   | email_malicious / email_clean                    | T1566.001 / null | high / info |
| file   | file_malicious / file_clean                      | T1204.002 / null | high / info |
| field  | replay_rejected                                  | T1692.002  | medium   |
| field  | handshake_rejected                               | T0830      | high     |
| field  | attack_detected (details.kind: replay_campaign, handshake_flood, impersonation) | by kind | high |
| field  | link_degraded                                    | null       | low      |
| field  | rekey (details.level: 512/768/1024, details.reason) | null    | info     |
| field  | gate_decision (details: action=spend\|challenge\|drop, sender; `score`=prob. sender is real) | null | info(spend)/low(challenge)/medium(drop) |
| field  | energy_alert (details: draw_mw, baseline_mw)     | null       | low..critical, scales with draw multiple |
| field  | budget_exhausted                                 | null       | high |
| tamper | case_opened / moved / voltage_anomaly            | null       | critical |

## HTTP
- POST :8000/events (Event) -> 201 | GET :8000/events?since=<ms> | GET :8000/incidents
- POST :8001/score/email {"text": "..."} -> Event
- POST :8001/score/file (multipart file) or {"features": {<54 PE features>}} -> Event
- GET  :8001/health

**Open, not yet frozen (v4):** a `sentinelmesh_frontend_kit.zip` (React/Vite,
copied into `console/frontend-kit/`) already assumes `GET /status`,
`GET /energy` (continuous power samples — NOT events, see above),
`GET /experiment`, `POST /mode {mode}`, `POST /attack {profile}` and
`POST /experiment/run`. `mode`/`attack` reach the boards over serial per the
kit's own comments, so their exact request/response shapes and the new
serial line(s) they trigger are Claude 2's (+ Claude 3 for the serial side)
first v4 task, not decided here — see `docs/v4_energy_split.md`.

## Serial lines
- gateway -> console: `EVT <Event JSON>` | `TRC <Trace JSON>` | `LOG <text>` (ignored)
- console -> gateway: `LABEL <normal|weak_link|replay|flood|impersonation>` (tags the TRC lines that follow)

## Trace JSON (one row per detection window, used to train the field model)
{ "ts": 0, "node": "gateway", "label": "normal", "window_ms": 5000, "hs_per_s": 0, "hs_fail": 0,
  "replay_rej": 0, "auth_fail": 0, "stale": 0, "frag_timeout": 0, "rssi_mean": -55.2,
  "rssi_var": 3.1, "loss_pct": 0.0, "jitter_ms": 2.4 }

v4 adds three optional fields to the same row — EnergyGate's free signals,
not required so pre-v4 producers keep validating: `battery_pct` (0-100),
`frag_complete_pct` (0-100, % of this sender's fragment sets that arrived
complete), `dup_pct` (0-100, duplicate-packet rate).