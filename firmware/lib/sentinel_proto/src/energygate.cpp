#include "sentinel_proto/energygate.h"

// The trained model, when present: ml/export/energygate.h copied here as
// energygate_model.h. It defines a global `static inline float
// energygate_score(const float* f)` over the same FEATURE_ORDER; this file
// wraps it as sentinel::energygate_score so no call site changes.
#if defined(__has_include)
#  if __has_include("sentinel_proto/energygate_model.h")
#    include "sentinel_proto/energygate_model.h"
#    define SENTINEL_ENERGYGATE_TRAINED_MODEL 1
#  endif
#endif

namespace sentinel {

namespace {
inline float clamp01(float v) {
    if (v < 0.0f) return 0.0f;
    if (v > 1.0f) return 1.0f;
    return v;
}
} // namespace

#ifdef SENTINEL_ENERGYGATE_TRAINED_MODEL

float energygate_score(const float* f) { return clamp01(::energygate_score(f)); }
bool energygate_uses_trained_model() { return true; }

#else

// Rule-based stand-in, until real recorded traces train the model. Start
// from "probably legitimate" and subtract the evidence a flooding/spoofing
// sender tends to produce: failed handshakes relative to attempts, fragment
// sets that never complete, high loss/duplicate rates, and erratic RSSI
// variance (spoofed packets often come from a different physical radio).
float energygate_score(const float* f) {
    const float hs_per_s          = f[EG_HS_PER_S];
    const float hs_fail           = f[EG_HS_FAIL];
    const float rssi_var          = f[EG_RSSI_VAR];
    const float loss_pct          = f[EG_LOSS_PCT];
    const float dup_pct           = f[EG_DUP_PCT];
    const float frag_complete_pct = f[EG_FRAG_COMPLETE_PCT];

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

bool energygate_uses_trained_model() { return false; }

#endif

} // namespace sentinel
