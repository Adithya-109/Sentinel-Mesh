#pragma once
// Trace (TRC line) builder — matches contracts/CONTRACT.md exactly:
//
//   { "ts": 0, "node": "gateway", "label": "normal", "window_ms": 5000,
//     "hs_per_s": 0, "hs_fail": 0, "replay_rej": 0, "auth_fail": 0,
//     "stale": 0, "frag_timeout": 0, "rssi_mean": -55.2, "rssi_var": 3.1,
//     "loss_pct": 0.0, "jitter_ms": 2.4 }
//
// One row per detection window. `label` is set by the console via a
// `LABEL <normal|weak_link|replay|flood|impersonation>` serial command and
// tags whichever TRC lines follow (see gateway main.cpp), so the recorded
// stream can be used as supervised training data for the field model.
//
// ESP32-only (ArduinoJson) — not part of the host-side unit test suite.

#include <ArduinoJson.h>
#include <Arduino.h>

namespace sentinel {

// Raw counters accumulated by the gateway over one detection window
// (see gateway main.cpp DetectionWindow). This struct is the plain-data
// half that's easy to accumulate in a plain loop; TraceBuilder below turns
// it into contract-exact JSON.
struct TraceWindowCounters {
    uint32_t window_ms = 5000;
    uint32_t hs_count = 0;       // handshakes started, ÷ window -> hs_per_s
    uint32_t hs_fail = 0;
    uint32_t replay_rej = 0;
    uint32_t auth_fail = 0;
    uint32_t stale = 0;
    uint32_t frag_timeout = 0;
    // Running stats for RSSI, accumulated via sum/sumsq/count so mean+var
    // can be computed at window close without keeping every sample.
    double rssi_sum = 0;
    double rssi_sumsq = 0;
    uint32_t rssi_samples = 0;
    uint32_t packets_expected = 0; // for loss_pct (e.g. from seq gaps)
    uint32_t packets_received = 0;
    double jitter_sum_ms = 0;
    uint32_t jitter_samples = 0;

    void reset() { *this = TraceWindowCounters{}; window_ms = 5000; }
    void add_rssi(float rssi) {
        rssi_sum += rssi;
        rssi_sumsq += static_cast<double>(rssi) * rssi;
        rssi_samples++;
    }
    void add_jitter(float ms) { jitter_sum_ms += ms; jitter_samples++; }

    float rssi_mean() const { return rssi_samples ? static_cast<float>(rssi_sum / rssi_samples) : 0.0f; }
    float rssi_var() const {
        if (rssi_samples < 2) return 0.0f;
        float mean = rssi_mean();
        return static_cast<float>(rssi_sumsq / rssi_samples - static_cast<double>(mean) * mean);
    }
    float loss_pct() const {
        if (packets_expected == 0) return 0.0f;
        uint32_t lost = (packets_expected > packets_received) ? (packets_expected - packets_received) : 0;
        return 100.0f * static_cast<float>(lost) / static_cast<float>(packets_expected);
    }
    float jitter_mean_ms() const { return jitter_samples ? static_cast<float>(jitter_sum_ms / jitter_samples) : 0.0f; }
    float hs_per_s() const { return window_ms ? (1000.0f * hs_count / window_ms) : 0.0f; }
};

// Builds the contract-exact Trace JsonDocument from accumulated counters.
JsonDocument new_trace(const char* node, const char* label, uint32_t ts_epoch_ms,
                        const TraceWindowCounters& c);

// Serializes `doc` and prepends the "TRC " serial-line prefix.
String to_trc_line(JsonDocument& doc);

} // namespace sentinel
