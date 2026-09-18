#pragma once
#include <cstdint>
#include <cstddef>

// Fallback authentication path if the crypto benchmark (src/benchmark)
// shows ML-DSA-44 doesn't fit ESP32's time/RAM/flash budget for the
// handshake. Per the brief: "If ML-DSA doesn't fit, fall back to a
// pre-shared HMAC key and label it clearly." This is that label + the
// implementation.
//
// THIS IS NOT POST-QUANTUM AND IS NOT A DROP-IN EQUIVALENT OF ML-DSA:
// it authenticates with a symmetric pre-shared key (all 3 boards embed the
// same key, provisioned like the ML-DSA public keys would be) rather than
// a public/private signature. Anyone holding the key can forge messages
// for anyone else — acceptable for a hackathon demo, not for production.
// Use only if bench results in src/benchmark rule out ML-DSA-44 on-target.
//
// Uses mbedtls (bundled with the ESP32 Arduino core) for HMAC-SHA256, so
// it needs no extra library dependency beyond what's already required for
// AES-256-GCM. Not part of the host-side unit test suite (mbedtls isn't
// linked there) — validate on-target once boards arrive.

namespace sentinel {

constexpr size_t HMAC_PSK_KEY_LEN = 32;  // 256-bit pre-shared key
constexpr size_t HMAC_TAG_LEN = 32;      // full HMAC-SHA256 output

class HmacPskAuth {
public:
    // `key` must point to HMAC_PSK_KEY_LEN bytes, provisioned the same way
    // as ML-DSA public keys would be (host script -> embedded header).
    explicit HmacPskAuth(const uint8_t* key);

    // Computes HMAC-SHA256(key, msg) into `tag_out` (must have room for
    // HMAC_TAG_LEN bytes). Returns true on success.
    bool sign(const uint8_t* msg, size_t msg_len, uint8_t* tag_out) const;

    // Recomputes the HMAC and compares in constant time against `tag`.
    // Returns true iff they match.
    bool verify(const uint8_t* msg, size_t msg_len, const uint8_t* tag) const;

private:
    uint8_t key_[HMAC_PSK_KEY_LEN];
};

} // namespace sentinel
