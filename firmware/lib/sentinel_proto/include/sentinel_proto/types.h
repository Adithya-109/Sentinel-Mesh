#pragma once
#include <cstdint>

// Shared node/message enums for the SentinelMesh mesh protocol.
// Kept dependency-free (no Arduino.h) so this header is usable both on
// ESP32 targets and in host-side unit tests.

namespace sentinel {

// Logical node ids on the mesh. Keep small — sender is a single byte on
// the wire (see packet.h).
enum class NodeId : uint8_t {
    FIELD_1  = 1,
    GATEWAY  = 2,
    ATTACKER = 3,
};

// Message types, per contracts/CONTRACT.md "Message types".
enum class MsgType : uint8_t {
    HELLO    = 0x01,
    RESPONSE = 0x02,
    CONFIRM  = 0x03,
    DATA     = 0x04,
    ACK      = 0x05,
    REKEY    = 0x06,
};

inline bool is_valid_msg_type(uint8_t v) {
    switch (v) {
        case static_cast<uint8_t>(MsgType::HELLO):
        case static_cast<uint8_t>(MsgType::RESPONSE):
        case static_cast<uint8_t>(MsgType::CONFIRM):
        case static_cast<uint8_t>(MsgType::DATA):
        case static_cast<uint8_t>(MsgType::ACK):
        case static_cast<uint8_t>(MsgType::REKEY):
            return true;
        default:
            return false;
    }
}

// ML-KEM security levels the adaptive-crypto layer can pick between.
enum class KemLevel : uint16_t {
    KEM_512  = 512,
    KEM_768  = 768,
    KEM_1024 = 1024,
};

} // namespace sentinel
