#pragma once
// EnergyGate's scoring function: the probability, in [0,1], that the sender
// of an inbound HELLO is a legitimate node. Runs on field-1, before any
// signature or KEM work (brief v4 section 4). The spend/challenge/drop
// decision that consumes this score is gate_policy.h, not here.
//
// Two implementations behind one signature:
//   * the trained model -- Claude 1's `ml/sentinel_ml/energygate.py` exports a
//     decision tree to `ml/export/energygate.h`. Copy that file to
//     `include/sentinel_proto/energygate_model.h` and energygate.cpp compiles
//     it in automatically (energygate_uses_trained_model() then returns true).
//   * otherwise, a rule-based stand-in with the same inputs and output range,
//     so the call site exists and is tested before the model does.
//
// Feature order (8 floats) -- MUST match `FEATURE_ORDER` in
// ml/sentinel_ml/energygate.py, because that is the order the trained model
// was fitted on. (An earlier stand-in used its own order; dropping the real
// model in would have read rssi_mean as frag_complete_pct, silently.)
//   f[0] = hs_per_s            handshake attempts per second this window
//   f[1] = hs_fail             failed handshakes this window
//   f[2] = rssi_mean           dBm
//   f[3] = rssi_var            dBm^2
//   f[4] = loss_pct            packet loss %, 0-100
//   f[5] = dup_pct             duplicate-packet rate %, 0-100
//   f[6] = frag_complete_pct   % of fragment sets that completed, 0-100
//   f[7] = battery_pct         field-1's own battery %, 0-100
//
// No Arduino.h dependency -- host-testable like the rest of sentinel_proto.

#include <cstddef>

namespace sentinel {

constexpr int ENERGYGATE_NUM_FEATURES = 8;

// Indices into the feature vector, in FEATURE_ORDER.
enum EnergyGateFeature : int {
    EG_HS_PER_S = 0,
    EG_HS_FAIL = 1,
    EG_RSSI_MEAN = 2,
    EG_RSSI_VAR = 3,
    EG_LOSS_PCT = 4,
    EG_DUP_PCT = 5,
    EG_FRAG_COMPLETE_PCT = 6,
    EG_BATTERY_PCT = 7,
};

float energygate_score(const float* f);

// True when the trained model (energygate_model.h) is compiled in; false for
// the rule-based stand-in. Logged at boot so nobody mistakes one for the other.
bool energygate_uses_trained_model();

} // namespace sentinel
