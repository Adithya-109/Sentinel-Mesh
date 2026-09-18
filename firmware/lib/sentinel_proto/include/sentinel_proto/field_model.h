#pragma once
// Rule-based stand-in for the field-classification ML model (firmware
// prompt point 9: "start with rules behind `int classify_window(const
// float* f)`. When ml/export/field_model.h exists, swap it in.").
//
// This lets the gateway classify each detection window (normal /
// weak_link / replay / flood / impersonation) from day one, without
// waiting on Claude 1's trained decision tree. Once ml/export/field_model.h
// exists (after the "record traces" check-in), replace the body of
// classify_window() with a call into that generated header — the call
// site in gateway main.cpp doesn't need to change since the signature
// (`int classify_window(const float* f)`) is the same on purpose.
//
// Feature order (10 floats) matches the numeric fields of the Trace JSON,
// in the order they appear in contracts/CONTRACT.md, minus ts/node/label:
//   f[0] = hs_per_s
//   f[1] = hs_fail
//   f[2] = replay_rej
//   f[3] = auth_fail
//   f[4] = stale
//   f[5] = frag_timeout
//   f[6] = rssi_mean
//   f[7] = rssi_var
//   f[8] = loss_pct
//   f[9] = jitter_ms
//
// No Arduino.h dependency — portable, host-testable like the rest of
// sentinel_proto.

#include <cstddef>

namespace sentinel {

enum class FieldClass : int {
    NORMAL = 0,
    WEAK_LINK = 1,
    REPLAY = 2,
    FLOOD = 3,
    IMPERSONATION = 4,
};

constexpr int FIELD_MODEL_NUM_FEATURES = 10;

inline const char* field_class_name(int cls) {
    switch (static_cast<FieldClass>(cls)) {
        case FieldClass::NORMAL: return "normal";
        case FieldClass::WEAK_LINK: return "weak_link";
        case FieldClass::REPLAY: return "replay";
        case FieldClass::FLOOD: return "flood";
        case FieldClass::IMPERSONATION: return "impersonation";
        default: return "unknown";
    }
}

// Rule-based classifier. `f` must point to FIELD_MODEL_NUM_FEATURES floats
// in the order documented above. Returns a FieldClass value as int (see
// enum) so the signature matches the eventual ML-exported function exactly.
//
// Thresholds are placeholder guesses, deliberately conservative (favor
// NORMAL) until real recorded traces let Claude 1 tune/replace them —
// see demo/RUNBOOK.md check-in "Record traces".
int classify_window(const float* f);

} // namespace sentinel
