// SentinelMesh gateway firmware ("Node B" in brief v2's storyboard).
//
// Responsibilities (brief v2 section 4 "Alert / recovery" + contracts/CONTRACT.md):
//  - Bridge the mesh (field node, attacker-under-test) to the console over
//    USB serial: print "EVT <json>" / "TRC <json>" lines, accept
//    "LABEL <x>" lines from the console.
//  - Keep per-window detection counters, run them through classify_window()
//    every window and print a TRC line (a stand-in field model until
//    ml/export/field_model.h exists — see field_model.h).
//  - Lock out a sender after it's flagged as an attack.
//  - Drive the OLED / RGB LED / buzzer as a status indicator (brief v2
//    section 10: green=secure, yellow=degraded, steady red=attack,
//    flashing red=tamper).
//
// STATUS: structural skeleton wiring sentinel_proto together end to end.
// The handshake/AEAD decrypt path is stubbed (TODO) pending the crypto
// benchmark results (src/benchmark) deciding wolfCrypt vs PQClean vs the
// HMAC-PSK fallback (auth_fallback.h) — see firmware/README.md. Not yet
// build-verified on hardware (no ESP32 toolchain in this environment).

#include <Arduino.h>
#include <Wire.h>
#include <Adafruit_GFX.h>
#include <Adafruit_SSD1306.h>

#include "sentinel_proto/packet.h"
#include "sentinel_proto/fragment.h"
#include "sentinel_proto/replay.h"
#include "sentinel_proto/field_model.h"
#include "sentinel_proto/event.h"
#include "sentinel_proto/trace.h"
#include "common/board_config.h"
#include "common/status_indicators.h"

using namespace sentinel;

// ---------------------------------------------------------------------
// State
// ---------------------------------------------------------------------

static Adafruit_SSD1306 g_oled(board::OLED_WIDTH, board::OLED_HEIGHT, &Wire, -1);
static bool g_oled_ok = false;
static StatusColor g_status = StatusColor::GREEN;

static Reassembler g_reassembler;
static ReplayFilter g_replay;
static TraceWindowCounters g_window;
static uint32_t g_window_start_ms = 0;
static const uint32_t WINDOW_MS = 5000;

// Current LABEL from the console (set via `LABEL <x>` serial command),
// tags the TRC lines that follow it until changed again. "normal" until
// told otherwise.
static char g_current_label[16] = "normal";

// Simple per-sender lockout after an attack is flagged. Index by NodeId
// byte value (small, fixed set of nodes on this mesh).
static bool g_locked_out[256] = {false};

// Maps field_model.h's short class name to the contract's details.kind
// vocabulary (contract: attack_detected details.kind is one of
// replay_campaign, handshake_flood, impersonation).
static const char* to_contract_attack_kind(int cls) {
    switch (static_cast<FieldClass>(cls)) {
        case FieldClass::REPLAY: return "replay_campaign";
        case FieldClass::FLOOD: return "handshake_flood";
        case FieldClass::IMPERSONATION: return "impersonation";
        default: return "unknown";
    }
}

// ---------------------------------------------------------------------
// EVT helpers
// ---------------------------------------------------------------------

static void emit_event(const char* layer, const char* type, const char* severity,
                        const char* node, const char* technique, const char* summary,
                        const char* reason1 = nullptr, const char* reason2 = nullptr,
                        const char* reason3 = nullptr) {
    JsonDocument evt = new_event(layer, type, severity, node, technique, summary);
    if (reason1) evt["reasons"].add(reason1);
    if (reason2) evt["reasons"].add(reason2);
    if (reason3) evt["reasons"].add(reason3);
    Serial.println(to_evt_line(evt));
}

static void lockout_sender(uint8_t sender, const char* node_name, const char* reason) {
    g_locked_out[sender] = true;
    g_replay.reset(sender); // force re-handshake if they ever come back
    g_status = StatusColor::STEADY_RED;
    buzz_alert();
    emit_event("field", "attack_detected", "high", node_name, nullptr,
               "Sender locked out after attack", reason);
}

// ---------------------------------------------------------------------
// Detection window -> TRC line + rule-based (or ML-exported) classification
// ---------------------------------------------------------------------

static void close_detection_window(uint32_t now_ms) {
    g_window.window_ms = now_ms - g_window_start_ms;

    JsonDocument trc = new_trace("gateway", g_current_label, now_ms, g_window);
    Serial.println(to_trc_line(trc));

    // Feed the same counters into classify_window() so the gateway can act
    // on detections live, independent of what the console does with the
    // recorded TRC line. Order must match field_model.h's documented
    // feature order.
    float features[FIELD_MODEL_NUM_FEATURES] = {
        g_window.hs_per_s(),
        static_cast<float>(g_window.hs_fail),
        static_cast<float>(g_window.replay_rej),
        static_cast<float>(g_window.auth_fail),
        static_cast<float>(g_window.stale),
        static_cast<float>(g_window.frag_timeout),
        g_window.rssi_mean(),
        g_window.rssi_var(),
        g_window.loss_pct(),
        g_window.jitter_mean_ms(),
    };
    int cls = classify_window(features);
    if (cls != static_cast<int>(FieldClass::NORMAL) &&
        cls != static_cast<int>(FieldClass::WEAK_LINK)) {
        const char* kind = to_contract_attack_kind(cls); // replay_campaign | handshake_flood | impersonation
        g_status = StatusColor::STEADY_RED;
        buzz_alert();
        emit_event("field", "attack_detected", "high", "gateway", nullptr,
                   String("Detection window classified as ") + kind,
                   kind);
        // TODO: once this is wired to the real sender identity (not just
        // "gateway"), call lockout_sender() here too — currently only the
        // per-packet replay_rejected path below has a concrete sender id
        // to lock out.
    } else if (cls == static_cast<int>(FieldClass::WEAK_LINK)) {
        if (g_status != StatusColor::STEADY_RED && g_status != StatusColor::FLASHING_RED) {
            g_status = StatusColor::YELLOW;
        }
        emit_event("field", "link_degraded", "low", "field-1", nullptr,
                    "Link quality degraded this window");
    } else if (g_status != StatusColor::STEADY_RED && g_status != StatusColor::FLASHING_RED) {
        g_status = StatusColor::GREEN;
    }

    g_window.reset();
    g_window.window_ms = WINDOW_MS;
    g_window_start_ms = now_ms;
}

// ---------------------------------------------------------------------
// Serial line handling: console -> gateway (LABEL), gateway -> console (EVT/TRC/LOG)
// ---------------------------------------------------------------------

static void handle_console_line(const String& line) {
    if (line.startsWith("LABEL ")) {
        String label = line.substring(6);
        label.trim();
        label.toCharArray(g_current_label, sizeof(g_current_label));
        Serial.print("LOG label set to ");
        Serial.println(g_current_label);
    }
    // Anything else from the console on this line is ignored per contract
    // (only LABEL is defined console -> gateway).
}

// ---------------------------------------------------------------------
// Mesh packet handling (placeholder transport — swap in the real radio/
// ESP-NOW receive path once hardware is wired up)
// ---------------------------------------------------------------------

// Called once per received, header-parsed packet from the mesh transport.
// `payload`/`payload_len` is the fragment's payload (still ciphertext at
// this point for DATA messages — decrypt AFTER reassembly + replay check,
// per the brief v2 6.1/6.2 handshake design; decrypt call is a TODO here).
static void on_mesh_packet(const PacketHeader& hdr, const uint8_t* payload, size_t payload_len,
                            float rssi, uint32_t now_ms) {
    g_window.add_rssi(rssi);

    if (g_locked_out[hdr.sender]) {
        return; // silently drop, sender is locked out
    }

    if (hdr.type == MsgType::HELLO) {
        g_window.hs_count++;
        // TODO: verify ML-DSA signature by the sender over the HELLO
        // contents (brief v2 6.2: "ML-DSA signature by A over all of it"),
        // or the HMAC-PSK fallback (auth_fallback.h), against the sender's
        // provisioned public key. On failure: g_window.hs_fail++;
        // g_window.auth_fail++; emit handshake_rejected EVT
        // (technique T0830 per contract).
    }

    // Replay check uses the sender's session-relative clock; until the
    // handshake layer tracks a real per-peer clock offset (brief v2
    // section 7: "each side records its local millis() at handshake
    // time"), approximate now_ms in that domain with our own millis()
    // (fine once both sides are freshly re-handshaken; TODO tighten once
    // handshake.cpp exists).
    ReplayFilter::Result rr = g_replay.check(hdr.sender, hdr.seq, hdr.time_ms, now_ms);
    switch (rr) {
        case ReplayFilter::Result::REPLAY_REJECTED:
            g_window.replay_rej++;
            emit_event("field", "replay_rejected", "medium",
                       hdr.sender == static_cast<uint8_t>(NodeId::FIELD_1) ? "field-1" : "attacker",
                       "T1692.002", "Replayed packet rejected",
                       "seq behind replay window");
            return;
        case ReplayFilter::Result::STALE_TIMESTAMP:
            g_window.stale++;
            return;
        case ReplayFilter::Result::DUPLICATE:
            // Benign retry: drop silently, re-ACK (ACK send path is a TODO
            // pending the real transport). Brief v2 section 7: "If an
            // acknowledgement is lost, the sender retries with the same
            // sequence number. The receiver drops the copy and
            // re-acknowledges."
            return;
        case ReplayFilter::Result::ACCEPT:
            break;
    }

    std::vector<uint8_t> reassembled;
    bool complete = g_reassembler.feed(hdr, payload, payload_len, now_ms, reassembled);
    if (!complete) return;

    g_window.packets_received++;
    // TODO: AES-256-GCM decrypt `reassembled` with the per-direction key
    // derived at handshake time (nonce = sender||epoch||seq, GCM tag
    // verified against the associated-data header, per brief v2 6.1),
    // then hand the plaintext DATA payload (the pressure reading) to
    // whatever consumes it.
}

// ---------------------------------------------------------------------
// Status display (brief v2 section 12 demo flow text)
// ---------------------------------------------------------------------

static void update_status_display() {
    if (!g_oled_ok) return;
    g_oled.clearDisplay();
    g_oled.setCursor(0, 0);
    g_oled.setTextSize(1);
    g_oled.setTextColor(SSD1306_WHITE);
    const char* status_text =
        (g_status == StatusColor::FLASHING_RED) ? "TAMPER" :
        (g_status == StatusColor::STEADY_RED)   ? "ATTACK DETECTED" :
        (g_status == StatusColor::YELLOW)       ? "Degraded, still secure" : "Secure";
    g_oled.printf("SentinelMesh gateway\nlabel: %s\n%s\n", g_current_label, status_text);
    g_oled.display();
}

// ---------------------------------------------------------------------
// Arduino entry points
// ---------------------------------------------------------------------

void setup() {
    Serial.begin(board::CONSOLE_SERIAL_BAUD);
    status_indicators_init();

    Wire.begin(board::I2C_SDA, board::I2C_SCL);
    g_oled_ok = g_oled.begin(SSD1306_SWITCHCAPVCC, board::OLED_I2C_ADDR);
    if (g_oled_ok) update_status_display();

    g_window.reset();
    g_window.window_ms = WINDOW_MS;
    g_window_start_ms = millis();

    Serial.println("LOG gateway boot complete");

    // TODO once mesh transport (ESP-NOW radio driver) is wired up:
    // register on_mesh_packet() as the receive callback. TODO: run the
    // crypto work in its own FreeRTOS task with a large stack (brief v2
    // section 8: "Run the crypto in its own FreeRTOS task with a large
    // stack").
}

void loop() {
    // Console -> gateway serial line intake.
    while (Serial.available()) {
        String line = Serial.readStringUntil('\n');
        line.trim();
        if (line.length() > 0) {
            handle_console_line(line);
        }
    }

    set_status_color(g_status);

    uint32_t now = millis();
    if (now - g_window_start_ms >= WINDOW_MS) {
        size_t evicted = g_reassembler.expire(now);
        g_window.frag_timeout += static_cast<uint32_t>(evicted);
        close_detection_window(now);
        update_status_display();
    }

    delay(10);
}
