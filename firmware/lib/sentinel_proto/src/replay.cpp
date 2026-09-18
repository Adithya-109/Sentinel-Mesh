#include "sentinel_proto/replay.h"
#include <cstdlib>

namespace sentinel {

ReplayFilter::Result ReplayFilter::check(uint8_t peer, uint32_t seq, uint32_t time_ms,
                                          uint32_t now_ms) {
    // Freshness check first — a stale timestamp is rejected even if the
    // sequence number itself would pass the window (e.g. a spliced replay
    // that reuses a plausible-looking seq).
    uint32_t delta = (time_ms > now_ms) ? (time_ms - now_ms) : (now_ms - time_ms);
    if (delta > freshness_threshold_ms_) {
        return Result::STALE_TIMESTAMP;
    }

    PeerState& state = peers_[peer]; // creates on first contact

    if (!state.initialized) {
        state.initialized = true;
        state.highest_seq = seq;
        state.window = 1; // bit 0 = highest_seq itself, now seen
        return Result::ACCEPT;
    }

    if (seq > state.highest_seq) {
        // New high-water mark. Shift the window forward by the gap,
        // dropping bits that age out past bit 63.
        uint64_t shift = static_cast<uint64_t>(seq) - state.highest_seq;
        if (shift >= 64) {
            state.window = 0;
        } else {
            state.window <<= shift;
        }
        state.window |= 1; // mark the new seq as seen (bit 0)
        state.highest_seq = seq;
        return Result::ACCEPT;
    }

    // seq <= highest_seq: within or behind the window.
    uint64_t back = static_cast<uint64_t>(state.highest_seq) - seq;
    if (back >= 64) {
        // Too far behind — window has no memory of this range at all;
        // treat conservatively as a replay rather than silently accepting.
        return Result::REPLAY_REJECTED;
    }

    uint64_t bit = (static_cast<uint64_t>(1) << back);
    if (state.window & bit) {
        return Result::DUPLICATE; // benign retry — same seq already accepted
    }

    // In-window, not yet seen: legitimate out-of-order delivery.
    state.window |= bit;
    return Result::ACCEPT;
}

void ReplayFilter::reset(uint8_t peer) {
    peers_.erase(peer);
}

} // namespace sentinel
