#pragma once
#include <cstdint>
#include <cstddef>
#include <vector>
#include <map>
#include "sentinel_proto/packet.h"

// Fragmentation and reassembly for the SentinelMesh mesh protocol.
//
// Radios/LoRa-class links have a small MTU, so any payload bigger than
// MAX_FRAGMENT_PAYLOAD is split into frag_n pieces sharing one (sender,
// epoch, seq) identity — seq is NOT incremented per fragment, only frag_i
// is. The Reassembler buffers fragments per stream, evicts stale/incomplete
// streams after a timeout, and caps how many concurrent streams it will
// track so a flood of bogus fragment-0s can't exhaust RAM (this doubles as
// the "frag_timeout" counter source for the Trace JSON).

namespace sentinel {

constexpr size_t MAX_FRAGMENT_PAYLOAD = 235;      // bytes of payload per fragment
// 235 = ESP-NOW v1's 250-byte frame budget minus the 15-byte header (brief v2
// section 6.3: "ESP-NOW v1 carries at most 250 bytes per frame"). Its worked
// example (a 3,253B ML-KEM-512 HELLO taking 14 frames) implies almost exactly
// this per-frame payload. Bump toward ESP-NOW v2's 1,470B frames (needs a
// recent ESP-IDF) once that's confirmed available on the boards in hand.
constexpr size_t MAX_REASSEMBLY_STREAMS = 8;       // cap on concurrent in-flight messages
constexpr uint32_t REASSEMBLY_TIMEOUT_MS = 3000;   // per-stream inactivity timeout

// Splits `payload` into 1..255 fragments, each carrying a header derived
// from `tmpl` (same sender/epoch/seq/version/type/prio) with frag_i/frag_n
// filled in. Fragment N's serialized bytes are [15B header][payload chunk].
// Returns an empty vector if payload_len is too large to fit in 255
// fragments at the given mtu.
class Fragmenter {
public:
    static std::vector<std::vector<uint8_t>> split(
        const PacketHeader& tmpl,
        const uint8_t* payload,
        size_t payload_len,
        size_t mtu = MAX_FRAGMENT_PAYLOAD);
};

struct StreamKey {
    uint8_t sender;
    uint16_t epoch;
    uint32_t seq;

    bool operator<(const StreamKey& o) const {
        if (sender != o.sender) return sender < o.sender;
        if (epoch != o.epoch) return epoch < o.epoch;
        return seq < o.seq;
    }
};

class Reassembler {
public:
    explicit Reassembler(uint32_t timeout_ms = REASSEMBLY_TIMEOUT_MS,
                          size_t max_streams = MAX_REASSEMBLY_STREAMS);

    // Feed one fragment (already header-verified) at time now_ms.
    // On the fragment that completes a message, fills `out` with the
    // reassembled payload (concatenated in frag_i order) and returns true.
    // Otherwise returns false (message still incomplete, or fragment was
    // rejected — e.g. stream table full and this is a new stream, or
    // frag_n mismatch against an in-flight stream with the same key).
    bool feed(const PacketHeader& hdr,
              const uint8_t* frag_payload,
              size_t frag_payload_len,
              uint32_t now_ms,
              std::vector<uint8_t>& out);

    // Evicts streams that haven't seen a fragment in > timeout_ms.
    // Returns how many were evicted — feed this into the "frag_timeout"
    // Trace JSON counter.
    size_t expire(uint32_t now_ms);

    size_t active_streams() const { return streams_.size(); }

private:
    struct InFlight {
        std::vector<std::vector<uint8_t>> parts;
        std::vector<bool> got;
        size_t received_count = 0;
        uint32_t last_seen_ms = 0;
    };

    std::map<StreamKey, InFlight> streams_;
    uint32_t timeout_ms_;
    size_t max_streams_;
};

} // namespace sentinel
