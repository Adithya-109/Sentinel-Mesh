# SentinelMesh integration contract v1 (owner: Console/Claude 2. Announce any change to all three.)

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
| tamper | case_opened / moved / voltage_anomaly            | null       | critical |

## HTTP
- POST :8000/events (Event) -> 201 | GET :8000/events?since=<ms> | GET :8000/incidents
- POST :8001/score/email {"text": "..."} -> Event
- POST :8001/score/file (multipart file) or {"features": {<54 PE features>}} -> Event
- GET  :8001/health

## Serial lines
- gateway -> console: `EVT <Event JSON>` | `TRC <Trace JSON>` | `LOG <text>` (ignored)
- console -> gateway: `LABEL <normal|weak_link|replay|flood|impersonation>` (tags the TRC lines that follow)

## Trace JSON (one row per detection window, used to train the field model)
{ "ts": 0, "node": "gateway", "label": "normal", "window_ms": 5000, "hs_per_s": 0, "hs_fail": 0,
  "replay_rej": 0, "auth_fail": 0, "stale": 0, "frag_timeout": 0, "rssi_mean": -55.2,
  "rssi_var": 3.1, "loss_pct": 0.0, "jitter_ms": 2.4 }