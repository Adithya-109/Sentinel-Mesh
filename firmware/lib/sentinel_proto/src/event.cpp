#ifdef ARDUINO
#include "sentinel_proto/event.h"
#include <esp_random.h>

namespace sentinel {

String generate_uuid4() {
    uint8_t b[16];
    for (int i = 0; i < 16; ++i) {
        b[i] = static_cast<uint8_t>(esp_random() & 0xFF);
    }
    // Set version (4) and variant (10xxxxxx) bits per RFC4122.
    b[6] = (b[6] & 0x0F) | 0x40;
    b[8] = (b[8] & 0x3F) | 0x80;

    char out[37];
    snprintf(out, sizeof(out),
             "%02x%02x%02x%02x-%02x%02x-%02x%02x-%02x%02x-%02x%02x%02x%02x%02x%02x",
             b[0], b[1], b[2], b[3], b[4], b[5], b[6], b[7],
             b[8], b[9], b[10], b[11], b[12], b[13], b[14], b[15]);
    return String(out);
}

JsonDocument new_event(const char* layer,
                        const char* type,
                        const char* severity,
                        const char* node,
                        const char* technique,
                        const char* summary,
                        uint32_t ts_epoch_ms) {
    JsonDocument doc;
    doc["id"] = generate_uuid4();
    doc["ts"] = (ts_epoch_ms != 0) ? ts_epoch_ms : millis();
    doc["layer"] = layer;
    doc["type"] = type;
    doc["severity"] = severity;
    doc["score"] = nullptr; // caller overwrites with a float if applicable

    if (node != nullptr) doc["node"] = node; else doc["node"] = nullptr;
    if (technique != nullptr) doc["technique"] = technique; else doc["technique"] = nullptr;

    doc["summary"] = summary;
    doc["reasons"].to<JsonArray>();   // empty array, caller appends up to 3
    doc["details"].to<JsonObject>();  // empty object, caller fills in

    return doc;
}

String to_evt_line(JsonDocument& doc) {
    String out = "EVT ";
    serializeJson(doc, out);
    return out;
}

} // namespace sentinel
#endif // ARDUINO
