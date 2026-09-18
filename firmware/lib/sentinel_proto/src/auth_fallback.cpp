// ESP32-only: depends on mbedtls, which isn't linked into the host-side
// native test build (see test/test_native and tools/run_native_tests.sh —
// that build only needs packet.cpp/fragment.cpp/replay.cpp). Compiles to
// nothing when ARDUINO isn't defined so it's safe to glob this whole
// directory on host builds too.
#ifdef ARDUINO

#include "sentinel_proto/auth_fallback.h"
#include <cstring>
#include <mbedtls/md.h>

namespace sentinel {

HmacPskAuth::HmacPskAuth(const uint8_t* key) {
    memcpy(key_, key, HMAC_PSK_KEY_LEN);
}

bool HmacPskAuth::sign(const uint8_t* msg, size_t msg_len, uint8_t* tag_out) const {
    const mbedtls_md_info_t* info = mbedtls_md_info_from_type(MBEDTLS_MD_SHA256);
    if (info == nullptr) return false;
    int rc = mbedtls_md_hmac(info, key_, HMAC_PSK_KEY_LEN, msg, msg_len, tag_out);
    return rc == 0;
}

bool HmacPskAuth::verify(const uint8_t* msg, size_t msg_len, const uint8_t* tag) const {
    uint8_t computed[HMAC_TAG_LEN];
    if (!sign(msg, msg_len, computed)) return false;

    // Constant-time comparison to avoid leaking a timing side-channel on
    // where the tags first diverge.
    uint8_t diff = 0;
    for (size_t i = 0; i < HMAC_TAG_LEN; ++i) {
        diff |= static_cast<uint8_t>(computed[i] ^ tag[i]);
    }
    return diff == 0;
}

} // namespace sentinel

#endif // ARDUINO
