// SentinelMesh attacker firmware — demo red-team node.
//
// Modes, selected over USB serial (so it can be driven from the console or
// a terminal during the demo), per the brief:
//   MODE REPLAY        capture the next packet seen, then replay it on repeat
//   MODE FLOOD          handshake flood (spam HELLOs)
//   MODE IMPERSONATE    spoof the field node's sender id with the attacker's
//                        own keys (should fail signature/HMAC verification
//                        on the gateway, which is the point — see brief
//                        threat model)
//   MODE WEAK_LINK      simulate a degraded link (drop/delay/jitter its own
//                        traffic) rather than attacking outright
//   MODE OFF             stop whatever mode is running
//
// This only needs to construct and send plausible-looking packets; it does
// NOT need to hold valid keys for anything except IMPERSONATE, where using
// its OWN keys under the field node's claimed identity is exactly the
// attack (and exactly what the gateway's signature check should catch).
//
// STATUS: structural skeleton. Real packet transmission depends on the
// mesh transport (TODO, same as field_node/gateway) and on the packet
// capture buffer for REPLAY mode. Not yet build-verified on hardware.

#include <Arduino.h>
#include <vector>
#include "sentinel_proto/packet.h"
#include "sentinel_proto/fragment.h"
#include "common/board_config.h"

using namespace sentinel;

enum class AttackMode { OFF, REPLAY, FLOOD, IMPERSONATE, WEAK_LINK };
static AttackMode g_mode = AttackMode::OFF;

// Captured packet for REPLAY mode.
static std::vector<uint8_t> g_captured_packet;
static bool g_have_capture = false;

static uint16_t g_flood_epoch_base = 0xA11C;  // 16-bit epoch (brief v2 6.1), bogus each time
static uint32_t g_flood_seq = 0;   // 32-bit seq per brief v2 section 7

// ---------------------------------------------------------------------
// Mode handlers — called from loop() at whatever cadence suits the mode.
// ---------------------------------------------------------------------

static void tick_replay() {
    if (!g_have_capture) {
        // TODO: hook into the real mesh receive path; on the first packet
        // seen from field-1, copy its raw bytes into g_captured_packet and
        // set g_have_capture = true.
        return;
    }
    // TODO: re-transmit g_captured_packet verbatim on the mesh transport.
    // This should be rejected by the gateway's replay window / freshness
    // check (contract: field/replay_rejected, or attack_detected with
    // details.kind = "replay_campaign" if sent in a burst).
    delay(500);
}

static void tick_flood() {
    PacketHeader hdr;
    hdr.type = MsgType::HELLO;
    hdr.sender = static_cast<uint8_t>(NodeId::ATTACKER);
    hdr.epoch = g_flood_epoch_base++; // new bogus epoch each time
    hdr.seq = g_flood_seq++;
    hdr.time_ms = millis();
    hdr.frag_n = 1;

    uint8_t buf[HEADER_SIZE];
    hdr.serialize(buf, sizeof(buf));
    // TODO: send `buf` (no valid signature attached) on the mesh transport.
    // Expected gateway behavior: handshake_rejected per-packet, and
    // attack_detected with details.kind = "handshake_flood" once the rate
    // crosses the classify_window() threshold.
    delay(50); // fast enough to trip hs_per_s thresholds, not so fast it starves the radio
}

static void tick_impersonate() {
    PacketHeader hdr;
    hdr.type = MsgType::HELLO;
    hdr.sender = static_cast<uint8_t>(NodeId::FIELD_1); // spoofed identity
    hdr.epoch = millis(); // plausible-looking, attacker doesn't know the real epoch
    hdr.seq = 0;
    hdr.time_ms = millis();
    hdr.frag_n = 1;

    uint8_t buf[HEADER_SIZE];
    hdr.serialize(buf, sizeof(buf));
    // TODO: sign with the ATTACKER's own ML-DSA/HMAC key (not field-1's —
    // that's the whole point) and send on the transport. Expected gateway
    // behavior: signature/HMAC verification fails ->
    // handshake_rejected + attack_detected(details.kind="impersonation").
    delay(1000);
}

static void tick_weak_link() {
    // Simulate a degraded link by sending the attacker's own traffic with
    // deliberately induced jitter/drops, rather than targeting anyone.
    // This exercises the gateway's `link_degraded` classification path
    // (rssi_var / loss_pct / jitter_ms thresholds in field_model.h)
    // without it being flagged as an attack.
    static uint32_t last = 0;
    uint32_t now = millis();
    uint32_t jitter = random(0, 400); // ms
    if (now - last >= 1000 + jitter) {
        // TODO: send a normal-looking DATA packet, occasionally dropped
        // (skip sending ~1 in 5) to simulate loss.
        last = now;
    }
}

// ---------------------------------------------------------------------
// Serial command intake
// ---------------------------------------------------------------------

static void handle_command(const String& cmd) {
    if (cmd == "MODE REPLAY") {
        g_mode = AttackMode::REPLAY;
        g_have_capture = false;
    } else if (cmd == "MODE FLOOD") {
        g_mode = AttackMode::FLOOD;
    } else if (cmd == "MODE IMPERSONATE") {
        g_mode = AttackMode::IMPERSONATE;
    } else if (cmd == "MODE WEAK_LINK") {
        g_mode = AttackMode::WEAK_LINK;
    } else if (cmd == "MODE OFF") {
        g_mode = AttackMode::OFF;
    } else {
        Serial.print("LOG unknown command: ");
        Serial.println(cmd);
        return;
    }
    Serial.print("LOG mode set to ");
    Serial.println(cmd);
}

// ---------------------------------------------------------------------
// Arduino entry points
// ---------------------------------------------------------------------

void setup() {
    Serial.begin(board::CONSOLE_SERIAL_BAUD);
    randomSeed(esp_random());
    Serial.println("LOG attacker boot complete. Commands: MODE REPLAY|FLOOD|IMPERSONATE|WEAK_LINK|OFF");
}

void loop() {
    while (Serial.available()) {
        String line = Serial.readStringUntil('\n');
        line.trim();
        if (line.length() > 0) handle_command(line);
    }

    switch (g_mode) {
        case AttackMode::REPLAY: tick_replay(); break;
        case AttackMode::FLOOD: tick_flood(); break;
        case AttackMode::IMPERSONATE: tick_impersonate(); break;
        case AttackMode::WEAK_LINK