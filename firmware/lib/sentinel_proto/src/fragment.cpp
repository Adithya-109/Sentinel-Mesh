#include "sentinel_proto/fragment.h"

namespace sentinel {

std::vector<std::vector<uint8_t>> Fragmenter::split(
    const PacketHeader& tmpl,
    const uint8_t* payload,
    size_t payload_len,
    size_t mtu) {

    std::vector<std::vector<uint8_t>> out;
    if (mtu == 0) return out;

    size_t frag_n = (payload_len + mtu - 1) / mtu;
    if (frag_n == 0) frag_n = 1; // zero-length payload still gets one fragment
    if (frag_n > 255) return out; // doesn't fit in a uint8_t frag_n

    out.reserve(frag_n);
    for (size_t i = 0; i < frag_n; ++i) {
        const size_t offset = i * mtu;
        const size_t chunk_len = (offset + mtu <= payload_len) ? mtu : (payload_len - offset);

        PacketHeader hdr = tmpl;
        hdr.frag_i = static_cast<uint8_t>(i);
        hdr.frag_n = static_cast<uint8_t>(frag_n);

        std::vector<uint8_t> buf(HEADER_SIZE + chunk_len);
        hdr.serialize(buf.data(), buf.size());
        if (chunk_len > 0) {
            for (size_t b = 0; b < chunk_len; ++b) {
                buf[HEADER_SIZE + b] = payload[offset + b];
            }
        }
        out.push_back(std::move(buf));
    }
    return out;
}

Reassembler::Reassembler(uint32_t timeout_ms, size_t max_streams)
    : timeout_ms_(timeout_ms), max_streams_(max_streams) {}

bool Reassembler::feed(const PacketHeader& hdr,
                        const uint8_t* frag_payload,
                        size_t frag_payload_len,
                        uint32_t now_ms,
                        std::vector<uint8_t>& out) {
    // Unfragmented fast path.
    if (hdr.frag_n == 1) {
        out.assign(frag_payload, frag_payload + frag_payload_len);
        return true;
    }

    StreamKey key{hdr.sender, hdr.epoch, hdr.seq};
    auto it = streams_.find(key);

    if (it == streams_.end()) {
        if (streams_.size() >= max_streams_) {
            // Stream table full: refuse to start tracking a new message
            // rather than evict an arbitrary in-flight one. Caller should
            // count this toward frag_timeout / drop metrics.
            return false;
        }
        InFlight fresh;
        fresh.parts.resize(hdr.frag_n);
        fresh.got.resize(hdr.frag_n, false);
        auto res = streams_.emplace(key, std::move(fresh));
        it = res.first;
    } else if (it->second.parts.size() != hdr.frag_n) {
        // frag_n changed mid-stream — treat as corrupt/attack, drop the
        // whole stream and start over defensively.
        streams_.erase(it);
        return false;
    }

    InFlight& inflight = it->second;
    inflight.last_seen_ms = now_ms;

    if (hdr.frag_i < inflight.got.size() && !inflight.got[hdr.frag_i]) {
        inflight.parts[hdr.frag_i].assign(frag_payload, frag_payload + frag_payload_len);
        inflight.got[hdr.frag_i] = true;
        inflight.received_count++;
    }
    // else: duplicate fragment, ignore (benign retry / re-transmission).

    if (inflight.received_count < inflight.parts.size()) {
        return false; // still waiting on more fragments
    }

    // Complete — concatenate in order and drop the stream.
    out.clear();
    for (auto& part : inflight.parts) {
        out.insert(out.end(), part.begin(), part.end());
    }
    streams_.erase(it);
    return true;
}

size_t Reassembler::expire(uint32_t now_ms) {
    size_t evicted = 0;
    for (auto it = streams_.begin(); it != streams_.end();) {
        if (now_ms - it->second.last_seen_ms > timeout_ms_) {
            it = streams_.erase(it);
            evicted++;
        } else {
            ++it;
        }
    }
    return evicted;
}

} // namespace sentinel
