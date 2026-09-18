#pragma once
#include <cstdint>
#include "sentinel_proto/energy_budget.h"

// EnergyGate's admission policy: given the model's probability that a
// sender is real, the joule budget and the defence mode the console
// selected, decide SPEND / CHALLENGE / DROP for one inbound HELLO.
//
// Runs on field-1 -- the battery-powered node whose battery the INA219
// measures (brief v4 sections 1-4: "the node has to decide who is worth
// spending energy on before it spends it", "the node holds an energy
// budget"). It used to live inline in gateway/main.cpp, but the gateway is
// USB-powered, so gating there protected nothing the rig measures. Moved
// here so the decision logic is host-tested rather than ESP32-only.
//
// The four modes are the five-row experiment's defences (brief v4 section
// 6), selected by the console's `DEFENSE <mode>` line (relayed to field-1
// by the gateway):
//   NONE       undefended: every request is paid for. The "attack, no
//              defence" row.
//   RATELIMIT  a fixed per-sender rate limit: at most one admission per
//              ratelimit_min_interval_ms. The "simple rate limit" row. A slow
//              drip (~1/min) sits under it by design -- that is the point
//              brief section 6 makes.
//   COOKIE     challenge every sender until it echoes a valid cookie, then
//              admit. The "cookie challenge only" row; no model, no budget.
//   GATE       EnergyGate: the model's score against the joule budget.
//
// No Arduino.h dependency -- host-testable like the rest of sentinel_proto.

namespace sentinel {

enum class DefenseMode : uint8_t { NONE = 0, RATELIMIT = 1, COOKIE = 2, GATE = 3 };
enum class GateAction : uint8_t { SPEND = 0, CHALLENGE = 1, DROP = 2 };

// "none" | "ratelimit" | "cookie" | "gate" -- the contract's DEFENSE vocabulary.
const char* defense_mode_name(DefenseMode m);
// Parses exactly those four lowercase names. Returns false (out untouched) otherwise.
bool parse_defense_mode(const char* s, DefenseMode& out);
bool defense_mode_from_byte(uint8_t v, DefenseMode& out);

// "spend" | "challenge" | "drop" -- the contract's gate_decision details.action.
const char* gate_action_name(GateAction a);
// Contract severity for a gate_decision: info (spend) / low (challenge) / medium (drop).
const char* gate_action_severity(GateAction a);
bool gate_action_from_byte(uint8_t v, GateAction& out);

struct GatePolicyConfig {
    // Thresholds on the [0,1] "probability the sender is real" score.
    // Placeholders until real recorded traces tune them.
    float spend_threshold = 0.7f;
    float challenge_threshold = 0.4f;
    // Joules booked per admitted handshake. PLACEHOLDER until the INA219 rig
    // measures the real cost (brief v4 section 3); charged at the worst case
    // until the HELLO payload can be parsed to read the requested level.
    float handshake_cost_j = 0.02f;
    // RATELIMIT mode: minimum gap between admissions from one sender. 10 s
    // stops a loud flood and lets a ~1/min slow drip straight through.
    uint32_t ratelimit_min_interval_ms = 10000;
};

// ms_since_last_attempt value for a sender never seen before.
constexpr uint32_t NEVER_SEEN = 0xFFFFFFFFu;

struct GateInputs {
    float prob_real = 0.0f;                   // energygate_score() output
    bool cookie_echoed = false;               // sender returned a valid cookie (cookie.h verify())
    uint32_t ms_since_last_attempt = NEVER_SEEN;
};

// One admission decision. In GATE mode a SPEND deducts cfg.handshake_cost_j
// from `budget`; the other modes leave the budget alone (it is EnergyGate's
// mechanism, not the baselines'). GATE mode, per brief v4 section 4 ("spends
// only when the expected value of a genuine connection beats the measured
// cost and the budget allows it; otherwise it challenges, and when the budget
// is nearly gone it drops"):
//   1. score >= spend_threshold and the budget covers a handshake  -> SPEND
//   2. a valid cookie came back ("8-byte cookie, then re-check"), the score
//      is at least challenge_threshold, and the budget covers it    -> SPEND
//   3. the budget cannot cover even one handshake ("nearly gone")   -> DROP
//      (a cookie would only lead to a handshake it can't pay for)
//   4. score >= challenge_threshold                                  -> CHALLENGE
//   5. otherwise                                                     -> DROP
GateAction decide_admission(DefenseMode mode, const GateInputs& in, EnergyBudget& budget,
                            const GatePolicyConfig& cfg, uint32_t now_ms);

} // namespace sentinel
