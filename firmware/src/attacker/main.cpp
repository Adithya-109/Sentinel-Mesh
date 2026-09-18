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
//   MODE SLOW_DRIP      v4: ~1 handshake/min -- stays under any fixed rate
//                        limit but still drains the energy budget over time
//                        (brief v4 / docs/v4_energy_split.md task 4)
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

enum class AttackMode { OFF, REPLAY, FLOOD, IMPERSONATE, WEAK_LINK, SLOW_DRIP };
static AttackMode g_mode = AttackMode::OFF;

// Captured packet for REPLAY mode.
static std::vector<uint8_t> g_captured_packet;
static bool g_have_capture = false;

static uint16_t g_flood_epoch_base = 0xA11C;  // 16-bit epoch (brief v2 6.1), bogus each time
static uint32_t g_flood_seq = 0;   // 32-bit seq per brief v2 section 7

// v4 (docs/v4_energy_split.md, firmware task 4): "the slow-drip profile
// (~1/min, brief section 6 -- 'sits under any fixed rate limit but still
// drains the cell')". A handshake attempt roughly once a minute never
// looks like a flood by rate alone -- the whole point is that a naive
// rate-limit defense passes it through, while EnergyGate's token bucket
// still bleeds down over the hour even at that low a rate. Reuses the
// FLOOD path's packet construction, just at a much slower cadence.
static uint16_t g_slow_drip_epoch_base = 0x5D91; // distinct base from FLOOD's, purely cosmetic
static uint32_t g_slow_drip_seq = 0;
constexpr uint32_t SLOW_DRIP_INTERVAL_MS = 60000; // ~1/min

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

static void tick_slow_drip() {
    static uint32_t last_ms = 0;
    uint32_t now = millis();
    if (now - last_ms < SLOW_DRIP_INTERVAL_MS) return;
    last_ms = now;

    PacketHeader hdr;
    hdr.type = MsgType::HELLO;
    hdr.sender = static_cast<uint8_t>(NodeId::ATTACKER);
    hdr.epoch = g_slow_drip_epoch_base++;
    hdr.seq = g_slow_drip_seq++;
    hdr.time_ms = now;
    hdr.frag_n = 1;

    uint8_t buf[HEADER_SIZE];
    hdr.serialize(buf, sizeof(buf));
    // TODO: send `buf` on the mesh transport, same as tick_flood(). At
    // ~1/min this shouldn't trip classify_window()'s hs_per_s/hs_fail
    // FLOOD threshold (field_model.h) -- that's the point, per brief
    // section 6: demonstrates why a plain rate limit isn't enough and
    // EnergyGate's budget-over-time view is needed instead. Expected
    // gateway behavior: individually unremarkable gate_decision events,
    // but the energy budget trends down over the demo's run instead of
    // holding steady the way idle/normal traffic does.
    (void)buf;
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
    } else if (cmd == "MODE SLOW_DRIP") {
        g_mode = AttackMode::SLOW_DRIP;
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
    Serial.println("LOG attacker boot complete. Commands: MODE REPLAY|FLOOD|IMPERSONATE|WEAK_LINK|SLOW_DRIP|OFF");
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
        case AttackMode::WEAK_LINK: tick_weak_link(); break;
        case AttackMode::SLOW_DRIP: tick_slow_drip(); break;
        case AttackMode::OFF: delay(100); break;
    }
}
