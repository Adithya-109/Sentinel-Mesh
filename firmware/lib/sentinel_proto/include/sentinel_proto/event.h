#pragma once
// Event (EVT line) builder — matches contracts/CONTRACT.md exactly:
//
//   { "id": "uuid4", "ts": <epoch ms>, "layer": "mail|file|field|tamper",
//     "type": "<see table>", "severity": "info|low|medium|high|critical",
//     "score": <0..1 or null>, "node": "field-1|gateway|attacker|null",
//     "technique": "<ATT&CK id or null>", "summary": "<one line>",
//     "reasons": ["<top 3 reasons>"], "details": {} }
//
// ESP32-only (needs ArduinoJson + Arduino's String/random) — not part of
// the host-side unit test suite. See firmware/README.md.
//
// Usage (gateway emitting a field-layer event):
//   JsonDocument evt = sentinel::new_event("field", "replay_rejected",
//                                           "medium", "gateway",
//                                           "T1692.002",
//                                           "Replayed packet rejected from field-1");
//   evt["reasons"].add("seq behind window");
//   evt["reasons"].add("peer=field-1");
//   evt["details"]["seq"] = seq;
//   Serial.println(sentinel::to_evt_line(evt));

#include <ArduinoJson.h>
#include <Arduino.h>

namespace sentinel {

// Generates an RFC4122-ish version-4 UUID string using esp_random() /
// Arduino random(). Good enough for demo event ids — not cryptographically
// reviewed, just needs to be unique per event.
String generate_uuid4();

// Builds a JsonDocument pre-filled with the required Event skeleton:
// id (auto uuid4), ts (epoch ms, pass 0 to auto-fill from millis() as a
// placeholder until the gateway has real wall-clock sync), layer, type,
// severity, node, technique, summary, an empty "reasons" array, and an
// empty "details" object. score defaults to JSON null — set
// doc["score"] = <float> explicitly if the layer produces one.
//
// node/technique may be nullptr to encode JSON null (per contract, e.g.
// mail/file "clean" events have technique: null).
JsonDocument new_event(const char* layer,
                        const char* type,
                        const char* severity,
                        const char* node,
                        const char* technique,
                        const char* summary,
                        uint32_t ts_epoch_ms = 0);

// Serializes `doc` and prepends the "EVT " serial-line prefix, per
// contract: "gateway -> console: EVT <Event JSON>".
String to_evt_line(JsonDocument& doc);

} // namespace sentinel
