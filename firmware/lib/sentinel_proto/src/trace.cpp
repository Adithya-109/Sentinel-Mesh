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

    // v4 EnergyGate free signals -- optional in trace.schema.json, so only
    // written when the gateway actually has something to say. frag_complete_pct
    // and dup_pct are always computable from this window's counters (they
    // default to sensible values -- 100%/0% -- when nothing happened yet);
    // battery_pct stays omitted until the DATA payload decrypt path exists
    // (see gateway main.cpp), rather than writing a fake 0.
    doc["frag_complete_pct"] = c.frag_complete_pct();
    doc["dup_pct"] = c.dup_pct();
    if (c.battery_pct >= 0.0f) {
        doc["battery_pct"] = c.battery_pct;
    }
    return doc;
}

String to_trc_line(JsonDocument& doc) {
    String out = "TRC ";
    serializeJson(doc, out);
    return out;
}

} // namespace sentinel
#endif // ARDUINO
