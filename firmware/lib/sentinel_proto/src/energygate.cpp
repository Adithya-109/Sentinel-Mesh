#include "sentinel_proto/energygate.h"

namespace sentinel {

namespace {
inline float clamp01(float v) {
    if (v < 0.0f) return 0.0f;
    if (v > 1.0f) return 1.0f;
    return v;
}
} // namespace

float energygate_score(const float* f) {
    const float hs_per_s          = f[0];
    const float hs_fail           = f[1];
    const float frag_complete_pct = f[2];
    const float loss_pct          = f[3];
    const float dup_pct           = f[4];
    const float rssi_var          = f[6];

    // Start from "probably legitimate" and subtract evidence of the free
    // signals a flooding/spoofing sender tends to produce: lots of failed
    // handshakes relative to attempts, fragment sets that never complete,
    // high loss/duplicate rates, and an erratic RSSI variance (spoofed
    // packets often arrive from a different physical radio than the
    // legitimate sender they're impersonating).
    float score = 1.0f;

    if (hs_per_s > 0.0f) {
        float fail_ratio = hs_fail / (hs_per_s + hs_fail);
        score -= 0.4f * fail_ratio;
    }

    score -= 0.3f * (1.0f - frag_complete_pct / 100.0f);
    score -= 0.15f * (loss_pct / 100.0f);
    score -= 0.15f * (dup_pct / 100.0f);

    if (rssi_var > 20.0f) {
        score -= 0.2f; // noticeably more erratic than a stationary node's usual fading
    }

    return clamp01(score);
}

} // namespace sentinel
