#pragma once
// Rule-based stand-in for EnergyGate's admission-scoring model (brief v4 /
// docs/v4_energy_split.md: Claude 1 owns `sentinel_ml/energygate.py`,
// exporting `float energygate_score(const float* f)` the same way
// `field_model.py` exports `classify_window()` -- train offline, export to
// C, host-gcc parity test). This header is the placeholder that lets the
// gateway's EnergyGate call site exist and be tested *before* that lands,
// with the exact same signature so swapping the body over is a drop-in
// once `ml/export/energygate.h` exists (see field_model.h for the
// established pattern this mirrors).
//
// Output is a probability the sender is a legitimate node, in [0,1] --
// NOT a class. The gateway's own policy (spend/challenge/drop, compare
// against EnergyBudget) consumes this score; it does not live here, per
// docs/v4_energy_split.md's explicit split ("the policy itself ... is
// firmware's job").
//
// Feature order (8 floats) -- the free signals doc lists (rssi_mean,
// rssi_var, hs_fail/hs_per_s as a completion-rate proxy,
// frag_complete_pct, loss_pct/dup_pct, battery_pct); this is this stand-
// in's concrete choice among those, kept intentionally close to
// TraceWindowCounters (trace.h) plus the v4 Trace fields so the gateway
// can build the feature vector directly off state it already tracks per
// window. Claude 1's real model may pick a different order/subset --
// whichever it settles on becomes the new contract for this function once
// ml/export/energygate.h exists; update this comment and the gateway call
// site together at that point.
//   f[0] = hs_per_s            (handshake attempts/s this window)
//   f[1] = hs_fail              (failed handshakes this window)
//   f[2] = frag_complete_pct     (% of this sender's fragment sets that completed)
//   f[3] = loss_pct               (packet loss % on the link)
//   f[4] = dup_pct                  (duplicate-packet rate)
//   f[5] = rssi_mean                 (dBm)
//   f[6] = rssi_var                   (dBm^2)
//   f[7] = battery_pct                 (field node's own battery %, 0-100)
//
// No Arduino.h dependency -- host-testable like the rest of sentinel_proto.

#include <cstddef>

namespace sentinel {

constexpr int ENERGYGATE_NUM_FEATURES = 8;

// Rule-based placeholder. Deliberately conservative (biased toward a
// mid-range score rather than confidently vouching for a sender) until
// real recorded traces let Claude 1 replace this with a trained model --
// same reasoning as field_model.cpp's classify_window() stand-in.
float energygate_score(const float* f);

} // namespace sentinel
