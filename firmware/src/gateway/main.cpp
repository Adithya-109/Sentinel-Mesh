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
//  - v4: relay for EnergyGate, which runs on field-1 (the battery-powered
//    node the INA219 measures -- brief v4 sections 1-4; this board is
//    USB-powered, so gating here protected nothing the rig measures). The
//    gateway forwards the console's `DEFENSE <mode>` line to field-1 as a
//    CONTROL message, and turns field-1's GATE_REPORT messages into the
//    console's gate_decision / budget_exhausted events ("node": "field-1").
//    It still overhears the attacker's HELLOs for its trace windows, and it
//    still owns the signed-handshake check (impersonation, demo beat 5).
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
#include "sentinel_proto/gate_policy.h"
#include "sentinel_proto/gate_msgs.h"
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

// v4: the defence mode the console selected (`DEFENSE <mode>`), relayed to
// field-1, which is where EnergyGate actually runs. Kept here only to relay
// it and show it on the OLED.
static DefenseMode g_defense = DefenseMode::NONE;
// Re-sent periodically as well as on change: field-1 may reboot or miss a
// packet, and a stale mode would silently invalidate an experiment row.
constexpr uint32_t CONTROL_RESEND_MS = 30000;
static uint32_t g_last_control_ms = 0;
static uint32_t g_ctrl_seq = 0;

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

// `details_kind`, when non-null, is written to details.kind. Required by
// contracts/event.schema.json for every attack_detected event (one of
// replay_campaign|handshake_flood|impersonation) -- without it the console
// rejects the POST with a 422.
static void emit_event(const char* layer, const char* type, const char* severity,
                        const char* node, const char* technique, const char* summary,
                        const char* reason1 = nullptr, const char* reason2 = nullptr,
                        const char* reason3 = nullptr, const char* details_kind = nullptr) {
    JsonDocument evt = new_event(layer, type, severity, node, technique, summary);
    if (reason1) evt["reasons"].add(reason1);
    if (reason2) evt["reasons"].add(reason2);
    if (reason3) evt["reasons"].add(reason3);
    if (details_kind) evt["details"]["kind"] = details_kind;
    Serial.println(to_evt_line(evt));
}

static const char* node_name_for(uint8_t sender) {
    switch (static_cast<NodeId>(sender)) {
        case NodeId::FIELD_1: return "field-1";
        case NodeId::GATEWAY: return "gateway";
        case NodeId::ATTACKER: return "attacker";
    }
    return "unknown";
}

// v4: gate_decision, on field-1's behalf. `score` is the model's probability
// the sender is real -- contract-required at the Event's top level, not in
// details. details.sender is the node whose HELLO was ruled on; budget_j /
// budget_max_j are the optional fields GET /status reads.
static void emit_gate_decision(const GateReport& r) {
    char summary[80];
    snprintf(summary, sizeof(summary), "EnergyGate %s for %s (defence: %s)",
             gate_action_name(r.action), node_name_for(r.sender), defense_mode_name(r.mode));
    JsonDocument evt = new_event("field", "gate_decision", gate_action_severity(r.action),
                                  "field-1", nullptr, summary);
    evt["score"] = r.prob_real;
    evt["details"]["action"] = gate_action_name(r.action);
    evt["details"]["sender"] = node_name_for(r.sender);
    evt["details"]["budget_j"] = r.budget_j;
    evt["details"]["budget_max_j"] = r.budget_max_j;
    Serial.println(to_evt_line(evt));
}

// v4: energy_alert when observed draw spikes over baseline. Severity
// scales with how far over baseline the draw is (contract: "low..critical,
// scales with draw multiple") -- once the Monitor board's INA219 readings
// actually reach the gateway (no data path yet, see src/monitor), call
// this from wherever that telemetry is consumed.
static const char* energy_alert_severity(float draw_mw, float baseline_mw) {
    if (baseline_mw <= 0.0f) return "low";
    float ratio = draw_mw / baseline_mw;
    if (ratio >= 5.0f) return "critical";
    if (ratio >= 3.0f) return "high";
    if (ratio >= 1.5f) return "medium";
    return "low";
}

static void emit_energy_alert(const char* node, float draw_mw, float baseline_mw, const char* summary) {
    JsonDocument evt = new_event("field", "energy_alert", energy_alert_severity(draw_mw, baseline_mw),
                                  node, nullptr, summary);
    evt["details"]["draw_mw"] = draw_mw;
    evt["details"]["baseline_mw"] = baseline_mw;
    Serial.println(to_evt_line(evt));
}

static void emit_budget_exhausted(const char* node, const char* summary) {
    emit_event("field", "budget_exhausted", "high", node, nullptr, summary);
}

static void lockout_sender(uint8_t sender, const char* node_name, const char* attack_kind) {
    g_locked_out[sender] = true;
    g_replay.reset(sender); // force re-handshake if they ever come back
    g_status = StatusColor::STEADY_RED;
    buzz_alert();
    emit_event("field", "attack_detected", "high", node_name, nullptr,
               "Sender locked out after attack", attack_kind, nullptr, nullptr, attack_kind);
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
        String summary = String("Detection window classified as ") + kind;
        emit_event("field", "attack_detected", "high", "gateway", nullptr,
                   summary.c_str(), kind, nullptr, nullptr, kind);
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

// Relays the current defence mode to field-1 as a CONTROL message. Same
// structural transport stub as the rest of this file -- TODO: hand the
// fragments to ESP-NOW (and AES-GCM encrypt) once the radio driver exists.
static void send_control_to_field_node(uint32_t now_ms) {
    ControlMsg m;
    m.kind = ControlKind::DEFENSE;
    m.value = static_cast<uint8_t>(g_defense);
    uint8_t payload[CONTROL_LEN];
    serialize_control(m, payload, sizeof(payload));

    PacketHeader hdr;
    hdr.type = MsgType::CONTROL;
    hdr.sender = static_cast<uint8_t>(NodeId::GATEWAY);
    hdr.seq = g_ctrl_seq++;
    hdr.time_ms = now_ms;
    auto frags = Fragmenter::split(hdr, payload, sizeof(payload));
    for (auto& frag : frags) {
        (void)frag; // TODO: mesh transport (ESP-NOW) -> field-1
    }
    g_last_control_ms = now_ms;
}

static void handle_console_line(const String& line) {
    if (line.startsWith("LABEL ")) {
        String label = line.substring(6);
        label.trim();
        label.toCharArray(g_current_label, sizeof(g_current_label));
        Serial.print("LOG label set to ");
        Serial.println(g_current_label);
    } else if (line.startsWith("DEFENSE ")) {
        // contracts/CONTRACT.md: `DEFENSE <none|ratelimit|cookie|gate>`. The
        // gateway does not act on it -- field-1 runs EnergyGate -- it relays it.
        String mode = line.substring(8);
        mode.trim();
        DefenseMode parsed;
        if (parse_defense_mode(mode.c_str(), parsed)) {
            g_defense = parsed;
            send_control_to_field_node(millis());
            Serial.printf("LOG defence mode %s relayed to field-1\n", defense_mode_name(g_defense));
        } else {
            Serial.print("LOG unknown defence mode: ");
            Serial.println(mode);
        }
    }
    // Anything else (e.g. the attacker's MODE lines) is ignored: the console
    // sends every control line to every board, and each acts on its own.
}

// v4: one EnergyGate decision from field-1 -> the console's events.
static void on_gate_report(const uint8_t* payload, size_t payload_len) {
    GateReport r;
    if (!deserialize_gate_report(payload, payload_len, r)) {
        Serial.println("LOG malformed GATE_REPORT from field-1 dropped");
        return;
    }
    emit_gate_decision(r);
    if (r.budget_exhausted_edge) {
        emit_budget_exhausted("field-1",
                              "EnergyGate budget exhausted on field-1 -- dropping admissions until it refills");
    }
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

    const char* node_name = (hdr.sender == static_cast<uint8_t>(NodeId::FIELD_1)) ? "field-1" : "attacker";

    if (hdr.type == MsgType::HELLO) {
        g_window.hs_count++;
        if (hdr.frag_i == 0) g_window.frag_sets_started++;

        // Counted for the trace windows (FieldGuard, and EnergyGate's
        // training data) whether the HELLO was meant for us or overheard on
        // its way to field-1, and it continues through the replay check and
        // reassembly below exactly as before, so the recorded windows keep
        // their meaning. EnergyGate itself runs on field-1, not here.

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
    g_window.total_received++;
    ReplayFilter::Result rr = g_replay.check(hdr.sender, hdr.seq, hdr.time_ms, now_ms);
    switch (rr) {
        case ReplayFilter::Result::REPLAY_REJECTED:
            g_window.replay_rej++;
            emit_event("field", "replay_rejected", "medium",
                       node_name, "T1692.002", "Replayed packet rejected",
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
            // re-acknowledges." Counted for v4's dup_pct free signal.
            g_window.duplicate_count++;
            return;
        case ReplayFilter::Result::ACCEPT:
            break;
    }

    std::vector<uint8_t> reassembled;
    bool complete = g_reassembler.feed(hdr, payload, payload_len, now_ms, reassembled);
    if (!complete) return;
    g_window.frag_sets_completed++;

    g_window.packets_received++;

    // v4: field-1's EnergyGate decisions. (TODO: decrypt first, like DATA.)
    if (hdr.type == MsgType::GATE_REPORT) {
        if (hdr.sender == static_cast<uint8_t>(NodeId::FIELD_1)) {
            on_gate_report(reassembled.data(), reassembled.size());
        }
        return;
    }

    // TODO: AES-256-GCM decrypt `reassembled` with the per-direction key
    // derived at handshake time (nonce = sender||epoch||seq, GCM tag
    // verified against the associated-data header, per brief v2 6.1),
    // then hand the plaintext DATA payload (the pressure reading) to
    // whatever consumes it. Once this exists, the field node can also
    // report its own battery_pct here (currently left unset, see trace.h).
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
    g_oled.printf("SentinelMesh gateway\nlabel: %s\ndefence: %s\n%s\n",
                  g_current_label, defense_mode_name(g_defense), status_text);
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
    // stack"). TODO (v4): the monitor board reports draw to the console
    // directly (NRG lines on its own USB serial), so emit_energy_alert() has
    // no data path here yet.
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
    if (now - g_last_control_ms >= CONTROL_RESEND_MS) {
        send_control_to_field_node(now); // keep field-1's mode in sync
    }
    if (now - g_window_start_ms >= WINDOW_MS) {
        size_t evicted = g_reassembler.expire(now);
        g_window.frag_timeout += static_cast<uint32_t>(evicted);
        close_detection_window(now);
        update_status_display();
    }

    delay(10);
}
