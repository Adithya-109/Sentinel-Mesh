#pragma once
#include <cstdint>
#include <map>

// Per-peer replay protection: a 64-bit sliding window over sequence
// numbers, plus a freshness check on the sender's session-relative
// timestamp (header.time_ms). Brief v2 section 7: "a 32-bit sequence
// counter per sender, per session, plus a 64-bit sliding-window bitmap
// (the same technique IPsec and DTLS use)" — seq is uint32_t (matches the
// 4-byte seq field in packet.h), the window bitmap stays 64 bits wide.
//
// Two independent defenses, both required by the brief:
//  1. Sliding window — classic IPsec-style anti-replay. Tracks the highest
//     seq seen from a peer plus a 64-bit bitmap of which of the previous
//     64 sequence numbers have already been accepted. A seq that falls
//     inside the window and is already marked -> DUPLICATE (benign retry:
//     drop silently, re-ACK). A seq that falls entirely outside/behind the
//     window -> REPLAY_REJECTED (real replay attack).
//  2. Freshness check — independent of seq, catches a captured-and-delayed
//     packet whose seq the attacker also rolled forward correctly (e.g.
//     spliced from a later legitimate capture). `now_ms` is the receiver's
//     estimate of the sender's current session-relative clock (established
//     at handshake time and tracked by the caller); if header.time_ms is
//     further than freshness_threshold_ms_ away from that, the packet is
//     rejected regardless of what the window says.
//
// No Arduino.h dependency — host-testable.

namespace sentinel {

constexpr uint32_t DEFAULT_FRESHNESS_THRESHOLD_MS = 2000;

class ReplayFilter {
public:
    enum class Result {
        ACCEPT,           // new packet, in or ahead of window -> accepted, window advanced
        DUPLICATE,        // exact seq already seen -> benign retry, drop silently, re-ACK
        REPLAY_REJECTED,  // seq behind the window (already retired) -> real replay
        STALE_TIMESTAMP,  // freshness check failed (checked before the window)
    };

    explicit ReplayFilter(uint32_t freshness_threshold_ms = DEFAULT_FRESHNESS_THRESHOLD_MS)
        : freshness_threshold_ms_(freshness_threshold_ms) {}

    // Call once per received, signature/AEAD-verified packet for `peer`.
    // `now_ms` must be in the same session-relative clock domain as
    // header.time_ms (see class comment) — it is NOT millis().
    Result check(uint8_t peer, uint32_t seq, uint32_t time_ms, uint32_t now_ms);

    // Clears window + freshness state for a peer, e.g. after a successful
    // re-handshake / rekey (new epoch means seq starts over legitimately).
    void reset(uint8_t peer);

    // Sets the freshness threshold at runtime (adaptive-level logic may
    // want to widen it on a degraded link).
    void set_freshness_threshold(uint32_t ms) { freshness_threshold_ms_ = ms; }

private:
    struct PeerState {
        uint64_t highest_seq = 0;
        uint64_t window = 0;   // bit i set => (highest_seq - i) already accepted
        bool initialized = false;
    };

    std::map<uint8_t, PeerState> peers_;
    uint32_t freshness_threshold_ms_;
};

} // namespace sentinel
