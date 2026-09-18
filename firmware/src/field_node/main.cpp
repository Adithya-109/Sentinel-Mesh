// SentinelMesh field node firmware ("Node A" in brief v2's storyboard —
// the pipeline valve station pressure sensor).
//
// Responsibilities (brief v2 section 2 storyboard + section 10):
//  - Send a pressure reading every ~30s as a DATA message to the gateway
//    (brief v2 storyboard says "every 30 seconds"; using 3s here so the
//    demo doesn't sit idle — tune back up for the real pitch if desired).
//  - On tamper (LDR case-opened, MPU6050 moved, reed switch case-opened,
//    or a sudden voltage anomaly): wipe keys, force a re-handshake, and
//    notify the gateway (the gateway is the one that emits the tamper EVT
//    to the console, since only it talks to serial).
//  - Adaptive crypto level: watch battery %, RSSI, and the urgent button;
//    re-handshake at a new ML-KEM level when the level should change
//    (brief v2 section 8).
//  - Drive its own OLED + RGB LED + buzzer (BOM has 2 of each — field_node
//    and gateway both get status indicators, brief v2 section 11/12).
//  - v4 (brief v4 sections 1-4): run EnergyGate. This node runs from the
//    18650 cell the INA219 measures, so it is the one a HELLO flood drains
//    ("an attacker who simply keeps saying hello can flatten a field node's
//    battery"). Every inbound HELLO goes through energygate_score() + the
//    joule budget + the cookie, via gate_policy.h, BEFORE any signature or
//    KEM work. The defence mode arrives from the console as `DEFENSE <mode>`,
//    relayed by the gateway as a CONTROL message; each decision goes back to
//    the gateway as a GATE_REPORT, which it turns into the console's
//    `gate_decision` event. (This node has no serial link during a run --
//    USB would bypass the INA219 -- hence the relay both ways.)
//    The PIN_ENERGY_MARKER pin is raised around each decision so the monitor
//    board measures EnergyGate's own cost (brief v4 section 3: "EnergyGate
//    itself -- microseconds and millijoules per decision").
//
// Pressure sensor note (resolved from brief v2): the BOM (section 11) has
// no dedicated pressure sensor — "pressure" is the storyboard's demo
// payload for a pipeline valve station, not a sensor SentinelMesh itself
// measures. read_pressure_reading() below is intentionally a simulated
// value, consistent with the brief's "honesty rule" (section 8): a
// simulation is fine as long as it's labelled, which it is here.
//
// STATUS: structural skeleton. Handshake/encryption logic are TODO stubs
// pending the crypto benchmark decision (src/benchmark) — see
// firmware/README.md. Not yet build-verified on hardware.

#include <Arduino.h>
#include <Wire.h>
#include <cstring>
#include <Adafruit_MPU6050.h>
#include <Adafruit_Sensor.h>
#include <Adafruit_GFX.h>
#include <Adafruit_SSD1306.h>

#include "sentinel_proto/packet.h"
#include "sentinel_proto/fragment.h"
#include "sentinel_proto/replay.h"
#include "sentinel_proto/trace.h"
#include "sentinel_proto/cookie.h"
#include "sentinel_proto/energy_budget.h"
#include "sentinel_proto/energygate.h"
#include "sentinel_proto/gate_policy.h"
#include "sentinel_proto/gate_msgs.h"
#include "common/board_config.h"
#include "common/status_indicators.h"

using namespace sentinel;

static Adafruit_MPU6050 g_mpu;
static bool g_mpu_ok = false;
static Adafruit_SSD1306 g_oled(board::OLED_WIDTH, board::OLED_HEIGHT, &Wire, -1);
static bool g_oled_ok = false;

static uint16_t g_epoch = 1;        // bumped on every re-handshake/rekey (16-bit, brief v2 6.1)
static uint32_t g_seq = 0;          // bumped per DATA message sent (32-bit, brief v2 section 7)
static KemLevel g_kem_level = KemLevel::KEM_512; // starts at the cheapest level
static StatusColor g_status = StatusColor::GREEN;
static bool g_weak_link_debug = false; // toggled by PIN_BTN_AUX, simulates cut TX power

// Baseline accel magnitude sampled at boot, used to detect "moved" tamper
// via a simple deviation threshold. Replace with something more robust
// (e.g. a short moving-average + hysteresis) once real motion data is in
// hand from the boards.
static float g_accel_baseline = 9.8f; // ~1g at rest
constexpr float ACCEL_TAMPER_DELTA = 2.0f; // m/s^2

// Rolling voltage baseline for tamper detection (distinct from the plain
// battery-% reading the adaptive engine uses): brief v2 section 10 —
// "sudden voltage drop or spike: battery swap, or a forced short" should
// be flagged as tamper, separately from the slow, expected discharge curve
// the adaptive engine already handles.
static float g_voltage_baseline = -1.0f; // -1 = not yet initialized

// ---------------------------------------------------------------------
// v4 EnergyGate state (moved here from the gateway -- see file header)
// ---------------------------------------------------------------------

// Starts undefended, matching the console's default (`DEFENSE none`); the
// gateway relays the console's current mode as soon as it is connected.
static DefenseMode g_defense = DefenseMode::NONE;

// Joule token bucket. PLACEHOLDER capacity/refill until the INA219 rig
// measures real per-handshake cost (brief v4 section 3).
constexpr float ENERGY_BUDGET_CAPACITY_J = 20.0f;
constexpr float ENERGY_BUDGET_REFILL_J_PER_S = 0.05f;
static EnergyBudget g_energy(ENERGY_BUDGET_CAPACITY_J, ENERGY_BUDGET_REFILL_J_PER_S);
static bool g_budget_was_exhausted = false;

static GatePolicyConfig g_gate_cfg; // thresholds + handshake cost, see gate_policy.h

// Re-seeded from esp_random() in setup(); a fixed secret would let an
// attacker precompute cookies.
static CookieChallenge g_cookie(0);

// Link-level view from this node's side, for EnergyGate's free signals
// (same counters and definitions as the gateway's trace windows, so the
// features match what the model was trained on).
static TraceWindowCounters g_link;
static uint32_t g_link_window_start_ms = 0;
constexpr uint32_t LINK_WINDOW_MS = 5000;

// Per-sender: when did it last try (RATELIMIT mode). 0 = never.
static uint32_t g_last_attempt_ms[256] = {0};

static ReplayFilter g_replay; // for CONTROL messages from the gateway

static void send_to_gateway(MsgType type, const uint8_t* payload, size_t len);

// ---------------------------------------------------------------------
// Sensors
// ---------------------------------------------------------------------

static float read_pressure_reading() {
    // Simulated demo payload — see file header note. Synthesizes a slowly
    // drifting value so the rest of the pipeline (DATA send, fragmentation,
    // gateway decode) can be exercised end to end.
    static float sim = 101.3f; // kPa, roughly sea-level atmospheric
    sim += (random(-10, 11) / 100.0f);
    return sim;
}

static bool check_tamper_ldr() {
    int v = analogRead(board::PIN_LDR);
    return v > board::LDR_TAMPER_THRESHOLD; // case opened -> more light hits the LDR
}

static bool check_tamper_motion() {
    if (!g_mpu_ok) return false;
    sensors_event_t accel, gyro, temp;
    g_mpu.getEvent(&accel, &gyro, &temp);
    float mag = sqrtf(accel.acceleration.x * accel.acceleration.x +
                       accel.acceleration.y * accel.acceleration.y +
                       accel.acceleration.z * accel.acceleration.z);
    return fabsf(mag - g_accel_baseline) > ACCEL_TAMPER_DELTA;
}

// Second, independent case-opened channel (brief v2 section 10: "works in
// the dark", defends against an attacker covering the LDR).
static bool check_tamper_reed() {
    return digitalRead(board::PIN_REED_SWITCH) == HIGH; // HIGH = circuit open = case opened
}

static float read_battery_voltage() {
    int raw = analogRead(board::PIN_BATTERY_ADC);
    float adc_v = (raw / 4095.0f) * 3.3f; // ESP32 ADC full-scale ~3.3V
    return adc_v * board::BATTERY_DIVIDER_RATIO;
}

static float read_battery_percent() {
    float vbat = read_battery_voltage();
    float pct = (vbat - board::BATTERY_EMPTY_V) /
                (board::BATTERY_FULL_V - board::BATTERY_EMPTY_V) * 100.0f;
    if (pct < 0) pct = 0;
    if (pct > 100) pct = 100;
    return pct;
}

// Sudden voltage jump/drop vs. a slow-moving baseline -> tamper (battery
// swap or a forced short), as opposed to the normal, gradual discharge
// curve the adaptive engine reacts to.
static bool check_tamper_voltage() {
    float v = read_battery_voltage();
    if (g_voltage_baseline < 0) {
        g_voltage_baseline = v; // first reading seeds the baseline
        return false;
    }
    bool anomaly = fabsf(v - g_voltage_baseline) > board::VOLTAGE_ANOMALY_DELTA_V;
    // Slowly track the baseline so normal discharge doesn't false-trigger.
    g_voltage_baseline += (v - g_voltage_baseline) * 0.02f;
    return anomaly;
}

// ---------------------------------------------------------------------
// Tamper response
// ---------------------------------------------------------------------

static void on_tamper_detected(const char* kind) {
    // TODO: actually wipe the derived session keys from RAM (explicit_bzero
    // or equivalent) once the handshake layer exists.
    g_epoch++; // new epoch forces the replay window to reset on the gateway
    g_seq = 0;
    // TODO: kick off a real re-handshake here.

    g_status = StatusColor::FLASHING_RED;
    buzz_alert();

    // Notify the gateway with a plain DATA message carrying the tamper
    // kind; the gateway maps this to a `tamper` EVT (case_opened / moved /
    // voltage_anomaly per contract) since it owns the console link.
    Serial.print("LOG tamper detected: ");
    Serial.println(kind);
}

// ---------------------------------------------------------------------
// Adaptive level (brief v2 section 8)
// ---------------------------------------------------------------------

static KemLevel pick_adaptive_level(float battery_pct, int rssi, bool urgent_pressed) {
    // Simple, documented rules. Tune thresholds once real RF/battery data
    // exists (brief v2: "Model: a small decision tree trained offline...
    // exported as a lookup table" — this is the rule-based stand-in for
    // that, same pattern as classify_window() in field_model.h).
    if (urgent_pressed) return KemLevel::KEM_1024;      // urgent message gets its own fresh 1024 handshake
    if (battery_pct < 20.0f) return KemLevel::KEM_512;  // conserve power
    if (rssi < -85) return KemLevel::KEM_512;           // weak link: cheapest handshake
    if (rssi > -60 && battery_pct > 50.0f) return KemLevel::KEM_1024;
    return KemLevel::KEM_768; // default middle ground
}

static void maybe_rehandshake_for_level(KemLevel desired) {
    if (desired == g_kem_level) return;
    g_kem_level = desired;
    g_epoch++;
    g_seq = 0;
    // TODO: real re-handshake at the new level; emit a REKEY message so the
    // gateway can log a `rekey` EVT (details.level, details.reason).
    Serial.printf("LOG re-handshake at level %d\n", static_cast<int>(g_kem_level));
}

// ---------------------------------------------------------------------
// Send path
// ---------------------------------------------------------------------

static void send_pressure_reading() {
    float p = read_pressure_reading();

    // TODO: AES-256-GCM encrypt the payload with the outbound session key,
    // nonce = sender||epoch||seq, before fragmenting/sending. Sending
    // plaintext bytes here as a structural placeholder. If g_weak_link_debug
    // is set, the transport should simulate cut TX power (drop/delay some
    // fraction of frags) -- brief v2 section 12 "opt" beat.
    uint8_t payload[sizeof(float)];
    memcpy(payload, &p, sizeof(p));
    send_to_gateway(MsgType::DATA, payload, sizeof(payload));
}

// ---------------------------------------------------------------------
// v4 EnergyGate: inbound HELLO admission + reports to the gateway
// ---------------------------------------------------------------------

// Sends one message to the gateway. Same structural transport stub as
// send_pressure_reading() -- TODO: hand the fragments to ESP-NOW once the
// radio driver is wired up (and AES-GCM encrypt first, see there).
static void send_to_gateway(MsgType type, const uint8_t* payload, size_t len) {
    PacketHeader hdr;
    hdr.type = type;
    hdr.sender = SENTINEL_NODE_ID;
    hdr.epoch = g_epoch;
    hdr.seq = g_seq++;
    hdr.time_ms = millis();
    hdr.prio = 0;
    auto frags = Fragmenter::split(hdr, payload, len);
    for (auto& frag : frags) {
        (void)frag; // TODO: mesh transport (ESP-NOW)
    }
}

static void report_gate_decision(uint8_t sender, GateAction action, float prob_real,
                                 bool budget_exhausted_edge) {
    GateReport r;
    r.sender = sender;
    r.action = action;
    r.mode = g_defense;
    r.budget_exhausted_edge = budget_exhausted_edge;
    r.prob_real = prob_real;
    r.budget_j = g_energy.balance_j();
    r.budget_max_j = g_energy.capacity_j();
    uint8_t buf[GATE_REPORT_LEN];
    serialize_gate_report(r, buf, sizeof(buf));
    send_to_gateway(MsgType::GATE_REPORT, buf, sizeof(buf));

    // Bench visibility when USB *is* attached (not during a measured run).
    Serial.printf("LOG gate %s sender=%u p=%.2f mode=%s budget=%.2f/%.0fJ\n",
                  gate_action_name(action), sender, prob_real, defense_mode_name(g_defense),
                  g_energy.balance_j(), g_energy.capacity_j());
}

// EnergyGate's 8 features, in ml/sentinel_ml/energygate.py's FEATURE_ORDER
// (see energygate.h -- placed by name, never by position).
static void build_gate_features(float f[ENERGYGATE_NUM_FEATURES]) {
    f[EG_HS_PER_S] = g_link.hs_per_s();
    f[EG_HS_FAIL] = static_cast<float>(g_link.hs_fail);
    f[EG_RSSI_MEAN] = g_link.rssi_mean();
    f[EG_RSSI_VAR] = g_link.rssi_var();
    f[EG_LOSS_PCT] = g_link.loss_pct();
    f[EG_DUP_PCT] = g_link.dup_pct();
    f[EG_FRAG_COMPLETE_PCT] = g_link.frag_complete_pct();
    // This node's own battery, from its ADC. On the gateway this feature was
    // never available and silently defaulted to 100%.
    f[EG_BATTERY_PCT] = read_battery_percent();
}

static void on_inbound_hello(const PacketHeader& hdr, const uint8_t* payload, size_t payload_len,
                             uint32_t now_ms) {
    (void)payload;
    (void)payload_len;
    g_link.hs_count++;
    if (hdr.frag_i == 0) g_link.frag_sets_started++;

    // Mark the decision for the monitor board: this interval is EnergyGate's cost.
    digitalWrite(board::PIN_ENERGY_MARKER, HIGH);

    float f[ENERGYGATE_NUM_FEATURES];
    build_gate_features(f);

    GateInputs in;
    in.prob_real = energygate_score(f);
    // TODO: set once HELLO framing carries the cookie echo (brief v2 6.2 has
    // no slot for it yet); verify with g_cookie.verify(hdr.sender, now_ms, echo).
    in.cookie_echoed = false;
    uint32_t last = g_last_attempt_ms[hdr.sender];
    in.ms_since_last_attempt = (last == 0) ? NEVER_SEEN : (now_ms - last);
    g_last_attempt_ms[hdr.sender] = now_ms ? now_ms : 1;

    GateAction action = decide_admission(g_defense, in, g_energy, g_gate_cfg, now_ms);

    digitalWrite(board::PIN_ENERGY_MARKER, LOW);

    // budget_exhausted is edge-triggered so a sustained drain doesn't spam
    // the console with one per HELLO.
    bool exhausted = !g_energy.can_afford(g_gate_cfg.handshake_cost_j, now_ms);
    bool edge = exhausted && !g_budget_was_exhausted && g_defense == DefenseMode::GATE;
    g_budget_was_exhausted = exhausted;

    report_gate_decision(hdr.sender, action, in.prob_real, edge);

    if (action == GateAction::CHALLENGE) {
        uint8_t cookie[COOKIE_LEN];
        g_cookie.generate(hdr.sender, CookieChallenge::time_window_for(now_ms), cookie);
        (void)cookie; // TODO: send once HELLO/RESPONSE framing exists
        return;
    }
    if (action == GateAction::DROP) {
        return; // silence, and it's logged via the report
    }

    // SPEND: TODO -- the full PQC handshake: reassemble, verify the sender's
    // ML-DSA signature (or the HMAC-PSK fallback, auth_fallback.h), ML-KEM
    // decapsulate, answer. On failure: g_link.hs_fail++.
}

static void on_control(const uint8_t* payload, size_t payload_len) {
    ControlMsg m;
    if (!deserialize_control(payload, payload_len, m)) return;
    DefenseMode mode;
    if (m.kind == ControlKind::DEFENSE && defense_mode_from_byte(m.value, mode) && mode != g_defense) {
        g_defense = mode;
        Serial.printf("LOG defence mode set to %s\n", defense_mode_name(g_defense));
    }
}

// Called once per received, header-parsed packet from the mesh transport.
// TODO: register as the ESP-NOW receive callback once the radio driver is
// wired up (same state as the gateway's on_mesh_packet).
static void on_mesh_packet(const PacketHeader& hdr, const uint8_t* payload, size_t payload_len,
                           float rssi, uint32_t now_ms) {
    g_link.add_rssi(rssi);

    if (hdr.type == MsgType::HELLO) {
        on_inbound_hello(hdr, payload, payload_len, now_ms);
        return;
    }

    g_link.total_received++;
    ReplayFilter::Result rr = g_replay.check(hdr.sender, hdr.seq, hdr.time_ms, now_ms);
    if (rr == ReplayFilter::Result::DUPLICATE) {
        g_link.duplicate_count++;
        return;
    }
    if (rr != ReplayFilter::Result::ACCEPT) return;

    // CONTROL is only accepted from the gateway (TODO: and only once the
    // AEAD layer authenticates it -- until then this is structural).
    if (hdr.type == MsgType::CONTROL && hdr.sender == static_cast<uint8_t>(NodeId::GATEWAY)) {
        on_control(payload, payload_len);
    }
}

static void roll_link_window(uint32_t now_ms) {
    if (now_ms - g_link_window_start_ms < LINK_WINDOW_MS) return;
    g_link.reset();
    g_link.window_ms = LINK_WINDOW_MS;
    g_link_window_start_ms = now_ms;
}

// ---------------------------------------------------------------------
// Status display (brief v2 section 12: "ML-KEM-1024 | Batt 90% | Seq 0142 | Secure")
// ---------------------------------------------------------------------

static void update_status_display(float battery_pct) {
    if (!g_oled_ok) return;
    g_oled.clearDisplay();
    g_oled.setCursor(0, 0);
    g_oled.setTextSize(1);
    g_oled.setTextColor(SSD1306_WHITE);
    const char* status_text =
        (g_status == StatusColor::FLASHING_RED) ? "TAMPER" :
        (g_status == StatusColor::STEADY_RED)   ? "ATTACK" :
        (g_status == StatusColor::YELLOW)       ? "Degraded" : "Secure";
    g_oled.printf("ML-KEM-%d | Batt %d%%\nSeq %04lu | %s\ngate:%s %d/%dJ\n",
                  static_cast<int>(g_kem_level), static_cast<int>(battery_pct),
                  static_cast<unsigned long>(g_seq), status_text,
                  defense_mode_name(g_defense), static_cast<int>(g_energy.balance_j()),
                  static_cast<int>(g_energy.capacity_j()));
    g_oled.display();
}

// ---------------------------------------------------------------------
// Arduino entry points
// ---------------------------------------------------------------------

void setup() {
    Serial.begin(board::CONSOLE_SERIAL_BAUD);
    randomSeed(esp_random());

    pinMode(board::PIN_LDR, INPUT);
    pinMode(board::PIN_REED_SWITCH, INPUT_PULLUP);
    pinMode(board::PIN_BTN_URGENT, INPUT_PULLUP);
    pinMode(board::PIN_BTN_AUX, INPUT); // input-only pin on WROOM-32, no internal pullup available
    pinMode(board::PIN_BATTERY_ADC, INPUT);
    pinMode(board::PIN_ENERGY_MARKER, OUTPUT);
    digitalWrite(board::PIN_ENERGY_MARKER, LOW);
    status_indicators_init();

    g_cookie = CookieChallenge(esp_random());
    g_link.reset();
    g_link.window_ms = LINK_WINDOW_MS;
    g_link_window_start_ms = millis();

    Wire.begin(board::I2C_SDA, board::I2C_SCL);
    g_mpu_ok = g_mpu.begin();
    if (g_mpu_ok) {
        sensors_event_t accel, gyro, temp;
        g_mpu.getEvent(&accel, &gyro, &temp);
        g_accel_baseline = sqrtf(accel.acceleration.x * accel.acceleration.x +
                                  accel.acceleration.y * accel.acceleration.y +
                                  accel.acceleration.z * accel.acceleration.z);
    }
    g_oled_ok = g_oled.begin(SSD1306_SWITCHCAPVCC, board::OLED_I2C_ADDR);

    Serial.printf("LOG field_node boot complete; EnergyGate scorer: %s; defence: %s\n",
                  energygate_uses_trained_model() ? "trained model" : "rule-based stand-in",
                  defense_mode_name(g_defense));
    // TODO once the mesh transport (ESP-NOW) is wired up: register
    // on_mesh_packet() as the receive callback.
}

void loop() {
    static uint32_t last_send_ms = 0;
    static uint32_t last_adapt_ms = 0;
    static uint32_t last_display_ms = 0;
    uint32_t now = millis();
    g_energy.tick(now);
    roll_link_window(now);

    if (check_tamper_ldr()) {
        on_tamper_detected("case_opened");
        delay(1000); // avoid re-triggering on every loop while case is open
    }
    if (check_tamper_motion()) {
        on_tamper_detected("moved");
        delay(1000);
    }
    if (check_tamper_reed()) {
        on_tamper_detected("case_opened"); // second channel, same tamper kind
        delay(1000);
    }
    if (check_tamper_voltage()) {
        on_tamper_detected("voltage_anomaly");
        delay(1000);
    }

    g_weak_link_debug = (digitalRead(board::PIN_BTN_AUX) == HIGH);
    if (g_status != StatusColor::FLASHING_RED && g_status != StatusColor::STEADY_RED) {
        g_status = g_weak_link_debug ? StatusColor::YELLOW : StatusColor::GREEN;
    }
    set_status_color(g_status);

    if (now - last_send_ms >= 3000) { // storyboard says "every 30 seconds"; 3s keeps the demo lively
        send_pressure_reading();
        last_send_ms = now;
    }

    if (now - last_adapt_ms >= 5000) {
        bool urgent = (digitalRead(board::PIN_BTN_URGENT) == LOW);
        float batt = read_battery_percent();
        int rssi = g_weak_link_debug ? -90 : -60; // TODO: pull from the real radio driver once wired up
        maybe_rehandshake_for_level(pick_adaptive_level(batt, rssi, urgent));
        last_adapt_ms = now;
    }

    if (now - last_display_ms >= 1000) {
        update_status_display(read_battery_percent());
        last_display_ms = now;
    }

    delay(20);
}
