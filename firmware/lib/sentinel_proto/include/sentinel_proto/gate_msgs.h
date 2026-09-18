#pragma once
#include <cstddef>
#include <cstdint>
#include "sentinel_proto/gate_policy.h"

// Payloads for the two v4 mesh messages that connect EnergyGate (on field-1)
// to the rest of the system. field-1 runs from its battery during a run and
// has no serial link to the console, so:
//
//   GATE_REPORT  field-1 -> gateway. One per admission decision. The gateway
//                turns it into the console's `gate_decision` event (and a
//                `budget_exhausted` event on the edge), with "node": "field-1".
//   CONTROL      gateway -> field-1. Relays the console's `DEFENSE <mode>`.
//
// Both are fixed-size and big-endian, matching packet.h's wire convention.
// They travel as the payload of an ordinary packet (header + payload, AEAD
// once the handshake layer exists), so the replay window and fragmentation
// apply to them exactly as to DATA.
//
// No Arduino.h dependency -- host-testable like the rest of sentinel_proto.

namespace sentinel {

// GATE_REPORT payload, 16 bytes:
//   0  u8   sender        -- NodeId byte of the HELLO being ruled on
//   1  u8   action        -- GateAction
//   2  u8   mode          -- DefenseMode in force when it was decided
//   3  u8   flags         -- bit 0: the budget just ran out (edge, not level)
//   4  f32  prob_real     -- energygate_score(), IEEE-754, big-endian bits
//   8  f32  budget_j      -- joule balance after the decision
//   12 f32  budget_max_j  -- bucket capacity
constexpr size_t GATE_REPORT_LEN = 16;

struct GateReport {
    uint8_t sender = 0;
    GateAction action = GateAction::DROP;
    DefenseMode mode = DefenseMode::NONE;
    bool budget_exhausted_edge = false;
    float prob_real = 0.0f;
    float budget_j = 0.0f;
    float budget_max_j = 0.0f;
};

// Returns GATE_REPORT_LEN, or 0 if out_len is too small.
size_t serialize_gate_report(const GateReport& r, uint8_t* out, size_t out_len);
// False on a short buffer, an unknown action/mode byte, or unknown flag bits.
bool deserialize_gate_report(const uint8_t* in, size_t in_len, GateReport& out);

// CONTROL payload, 2 bytes:
//   0  u8  kind   -- ControlKind
//   1  u8  value  -- for DEFENSE: a DefenseMode byte
constexpr size_t CONTROL_LEN = 2;

enum class ControlKind : uint8_t { DEFENSE = 1 };

struct ControlMsg {
    ControlKind kind = ControlKind::DEFENSE;
    uint8_t value = 0;
};

size_t serialize_control(const ControlMsg& m, uint8_t* out, size_t out_len);
// False on a short buffer, an unknown kind, or (for DEFENSE) an unknown mode.
bool deserialize_control(const uint8_t* in, size_t in_len, ControlMsg& out);

// Ordering check for CONTROL on field-1. Not ReplayFilter: its freshness test
// compares the sender's millis() with the receiver's, and the gateway's and
// field-1's uptimes never match until a handshake establishes a shared session
// clock -- so every CONTROL would be rejected as stale and the console's
// DEFENSE switch would silently do nothing. Instead: the gateway stamps a
// random per-boot epoch and a counter; accept a new epoch (the gateway
// rebooted) or a higher seq within the current one, reject anything else.
// Anti-replay across epochs needs the AEAD session layer (TODO, like all
// traffic); a stale mode would also be overwritten by the gateway's periodic
// re-send within CONTROL_RESEND_MS.
class ControlSequencer {
public:
    bool accept(uint16_t epoch, uint32_t seq) {
        if (!seen_ || epoch != epoch_) {
            seen_ = true;
            epoch_ = epoch;
            seq_ = seq;
            return true;
        }
        if (seq <= seq_) return false;
        seq_ = seq;
        return true;
    }

private:
    bool seen_ = false;
    uint16_t epoch_ = 0;
    uint32_t seq_ = 0;
};

} // namespace sentinel
