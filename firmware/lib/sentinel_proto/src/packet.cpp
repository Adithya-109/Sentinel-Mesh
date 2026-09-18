#include "sentinel_proto/packet.h"

namespace sentinel {

namespace {
inline void put_u16(uint8_t* p, uint16_t v) {
    p[0] = static_cast<uint8_t>(v >> 8);
    p[1] = static_cast<uint8_t>(v & 0xFF);
}
inline void put_u32(uint8_t* p, uint32_t v) {
    p[0] = static_cast<uint8_t>(v >> 24);
    p[1] = static_cast<uint8_t>(v >> 16);
    p[2] = static_cast<uint8_t>(v >> 8);
    p[3] = static_cast<uint8_t>(v & 0xFF);
}
inline uint16_t get_u16(const uint8_t* p) {
    return static_cast<uint16_t>((p[0] << 8) | p[1]);
}
inline uint32_t get_u32(const uint8_t* p) {
    return (static_cast<uint32_t>(p[0]) << 24) | (static_cast<uint32_t>(p[1]) << 16) |
           (static_cast<uint32_t>(p[2]) << 8) | static_cast<uint32_t>(p[3]);
}
} // namespace

size_t PacketHeader::serialize(uint8_t* out, size_t out_len) const {
    if (out == nullptr || out_len < HEADER_SIZE) return 0;

    out[0] = static_cast<uint8_t>((version & 0x0F) << 4) |
             (static_cast<uint8_t>(type) & 0x0F);
    out[1] = sender;
    put_u16(&out[2], epoch);
    put_u32(&out[4], seq);
    put_u32(&out[8], time_ms);
    out[12] = prio;
    out[13] = frag_i;
    out[14] = frag_n;
    return HEADER_SIZE;
}

bool PacketHeader::deserialize(const uint8_t* in, size_t in_len, PacketHeader& out) {
    if (in == nullptr || in_len < HEADER_SIZE) return false;

    const uint8_t ver = (in[0] >> 4) & 0x0F;
    const uint8_t type_byte = in[0] & 0x0F;
    if (ver != PROTO_VERSION) return false;
    if (!is_valid_msg_type(type_byte)) return false;

    PacketHeader hdr;
    hdr.version = ver;
    hdr.type = static_cast<MsgType>(type_byte);
    hdr.sender = in[1];
    hdr.epoch = get_u16(&in[2]);
    hdr.seq = get_u32(&in[4]);
    hdr.time_ms = get_u32(&in[8]);
    hdr.prio = in[12];
    hdr.frag_i = in[13];
    hdr.frag_n = in[14];

    if (hdr.frag_n == 0) return false;       // must always be at least 1
    if (hdr.frag_i >= hdr.frag_n) return false; // index out of range

    out = hdr;
    return true;
}

} // namespace sentinel
