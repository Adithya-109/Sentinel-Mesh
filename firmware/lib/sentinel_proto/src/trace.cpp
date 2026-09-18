#ifdef ARDUINO
#include "sentinel_proto/trace.h"

namespace sentinel {

JsonDocument new_trace(const char* node, const char* label, uint32_t ts_epoch_ms,
                        const TraceWindowCounters& c) {
    JsonDocument doc;
    doc["ts"] = ts_epoch_ms;
    doc["node"] = node;
    doc["label"] = label;
    doc["window_ms"] = c.window_ms;
    doc["hs_per_s"] = c.hs_per_s();
    doc["hs_fail"] = c.hs_fail;
    doc["replay_rej"] = c.replay_rej;
    doc["auth_fail"] = c.auth_fail;
    doc["stale"] = c.stale;
    doc["frag_timeout"] = c.frag_timeout;
    doc["rssi_mean"] = c.rssi_mean();
    doc["rssi_var"] = c.rssi_var();
    doc["loss_pct"] = c.loss_pct();
    doc["jitter_ms"] = c.jitter_mean_ms();
    return doc;
}

String to_trc_line(JsonDocument& doc) {
    String out = "TRC ";
    serializeJson(doc, out);
    return out;
}

} // namespace sentinel
#endif // ARDUINO
