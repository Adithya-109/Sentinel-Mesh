#include "sentinel_proto/field_model.h"

namespace sentinel {

int classify_window(const float* f) {
    const float hs_per_s     = f[0];
    const float hs_fail      = f[1];
    const float replay_rej   = f[2];
    const float auth_fail    = f[3];
    const float stale        = f[4];
    const float frag_timeout = f[5];
    const float rssi_var     = f[7];
    const float loss_pct     = f[8];
    const float jitter_ms    = f[9];

    // Handshake flood: many handshake attempts per second with a high
    // failure rate.
    if (hs_per_s >= 5.0f && hs_fail >= 3.0f) {
        return static_cast<int>(FieldClass::FLOOD);
    }

    // Replay campaign: a burst of rejected replays in one window.
    if (replay_rej >= 3.0f) {
        return static_cast<int>(FieldClass::REPLAY);
    }

    // Impersonation: auth/signature failures without a matching burst of
    // handshake attempts or replay rejects (i.e. someone is sending
    // otherwise-well-formed traffic under the wrong identity).
    if (auth_fail >= 2.0f && hs_per_s < 5.0f && replay_rej < 3.0f) {
        return static_cast<int>(FieldClass::IMPERSONATION);
    }

    // Weak link: noisy/lossy radio conditions, not an attack — stale
    // timestamps + fragment timeouts trending up alongside RSSI variance
    // or packet loss.
    if (rssi_var >= 15.0f || loss_pct >= 10.0f || jitter_ms >= 40.0f ||
        stale >= 3.0f || frag_timeout >= 2.0f) {
        return static_cast<int>(FieldClass::WEAK_LINK);
    }

    return static_cast<int>(FieldClass::NORMAL);
}

} // namespace sentinel
