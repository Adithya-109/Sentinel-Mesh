#pragma once
#include <cstdint>
#include <cstddef>
#include "sentinel_proto/types.h"

// Wire packet header for the SentinelMesh mesh protocol.
//
// 15-byte header, big-endian on the wire — sizes per brief v2 section 6.1
// (the packet-format table), which is the authoritative byte layout:
//   offset  size  field
//   0       1     ver_type   (bits 7..4 = protocol version, bits 3..0 = MsgType)
//   1       1     sender     (NodeId)
//   2       2     epoch      (uint16 — handshake/session epoch, bumped on rekey)
//   4       4     seq        (uint32 — sequence number within the epoch;
//                             brief v2 section 7: "32-bit sequence counter")
//   8       4     time_ms    (uint32 — sender's session-relative timestamp, ms)
//   12      1     prio       (0-255, higher = more urgent; drives adaptive level)
//   13      1     frag_i     (fragment index, 0-based)
//   14      1     frag_n     (total fragment count; 1 = message is unfragmented)
//
// The header is sent in clear but is authenticated as AES-GCM associated
// data (brief v2 6.1: "sent in clear but authenticated by AES-GCM, so any
// change to it is detected"). The GCM nonce is sender||epoch||seq (1+2+4 = 7
// bytes, padded to the cipher's nonce size by the AEAD layer — TODO once
// handshake.cpp exists). Total per-packet overhead is 15B header + 16B GCM
// tag = 31B, matching brief v2's figure; the tag is appended once to the
// full (reassembled) ciphertext, not per fragment.
//
// Payload (ciphertext for DATA/HELLO/etc, or plaintext control bytes for
// ACK) follows immediately after these 15 bytes and is handled by the
// caller — this struct only covers the header.
//
// No Arduino.h dependency on purpose: this is exercised by host-side unit
// tests in test/test_native as well as compiled into the ESP32 targets.

namespace sentinel {

constexpr uint8_t PROTO_VERSION = 1;
constexpr size_t HEADER_SIZE = 15;

struct PacketHeader {
    uint8_t  version = PROTO_VERSION;
    MsgType  type    = MsgType::DATA;
    uint8_t  sender  = 0;
    uint16_t epoch   = 0;
    uint32_t seq     = 0;
    uint32_t time_ms = 0;
    uint8_t  prio    = 0;
    uint8_t  frag_i  = 0;
    uint8_t  frag_n  = 1;

    // Serializes this header into `out` (must have room for HEADER_SIZE
    // bytes). Returns HEADER_SIZE on success, 0 if out_len is too small.
    size_t serialize(uint8_t* out, size_t out_len) const;

    // Parses a header from `in`. Returns true on success. Fails if
    // in_len < HEADER_SIZE, the version doesn't match PROTO_VERSION, the
    // type byte isn't a known MsgType, or frag_i >= frag_n.
    static bool deserialize(const uint8_t* in, size_t in_len, PacketHeader& out);

    bool operator==(const PacketHeader& o) const {
        return version == o.version && type == o.type && sender == o.sender &&
               epoch == o.epoch && seq == o.seq && time_ms == o.time_ms &&
               prio == o.prio && frag_i == o.frag_i && frag_n == o.frag_n;
    }
};

} // namespace sentinel
