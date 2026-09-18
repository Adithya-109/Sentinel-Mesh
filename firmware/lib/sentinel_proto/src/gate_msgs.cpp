#include "sentinel_proto/gate_msgs.h"

#include <cstring>

namespace sentinel {

namespace {

void put_f32(uint8_t* out, float v) {
    uint32_t bits;
    std::memcpy(&bits, &v, sizeof(bits));
    out[0] = static_cast<uint8_t>(bits >> 24);
    out[1] = static_cast<uint8_t>(bits >> 16);
    out[2] = static_cast<uint8_t>(bits >> 8);
    out[3] = static_cast<uint8_t>(bits);
}

float get_f32(const uint8_t* in) {
    uint32_t bits = (static_cast<uint32_t>(in[0]) << 24) | (static_cast<uint32_t>(in[1]) << 16) |
                    (static_cast<uint32_t>(in[2]) << 8) | static_cast<uint32_t>(in[3]);
    float v;
    std::memcpy(&v, &bits, sizeof(v));
    return v;
}

constexpr uint8_t FLAG_BUDGET_EXHAUSTED = 0x01;

} // namespace

size_t serialize_gate_report(const GateReport& r, uint8_t* out, size_t out_len) {
    if (out == nullptr || out_len < GATE_REPORT_LEN) return 0;
    out[0] = r.sender;
    out[1] = static_cast<uint8_t>(r.action);
    out[2] = static_cast<uint8_t>(r.mode);
    out[3] = r.budget_exhausted_edge ? FLAG_BUDGET_EXHAUSTED : 0;
    put_f32(out + 4, r.prob_real);
    put_f32(out + 8, r.budget_j);
    put_f32(out + 12, r.budget_max_j);
    return GATE_REPORT_LEN;
}

bool deserialize_gate_report(const uint8_t* in, size_t in_len, GateReport& out) {
    if (in == nullptr || in_len < GATE_REPORT_LEN) return false;
    GateReport r;
    r.sender = in[0];
    if (!gate_action_from_byte(in[1], r.action)) return false;
    if (!defense_mode_from_byte(in[2], r.mode)) return false;
    if (in[3] & ~FLAG_BUDGET_EXHAUSTED) return false;
    r.budget_exhausted_edge = (in[3] & FLAG_BUDGET_EXHAUSTED) != 0;
    r.prob_real = get_f32(in + 4);
    r.budget_j = get_f32(in + 8);
    r.budget_max_j = get_f32(in + 12);
    out = r;
    return true;
}

size_t serialize_control(const ControlMsg& m, uint8_t* out, size_t out_len) {
    if (out == nullptr || out_len < CONTROL_LEN) return 0;
    out[0] = static_cast<uint8_t>(m.kind);
    out[1] = m.value;
    return CONTROL_LEN;
}

bool deserialize_control(const uint8_t* in, size_t in_len, ControlMsg& out) {
    if (in == nullptr || in_len < CONTROL_LEN) return false;
    if (in[0] != static_cast<uint8_t>(ControlKind::DEFENSE)) return false;
    DefenseMode mode;
    if (!defense_mode_from_byte(in[1], mode)) return false;
    out.kind = ControlKind::DEFENSE;
    out.value = in[1];
    return true;
}

} // namespace sentinel
