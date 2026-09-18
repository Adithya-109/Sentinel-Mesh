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

    PacketHeader hdr;
    hdr.type = MsgType::DATA;
    hdr.sender = SENTINEL_NODE_ID;
    hdr.epoch = g_epoch;
    hdr.seq = g_seq++;
    hdr.time_ms = millis();
    hdr.prio = 0;

    // TODO: AES-256-GCM encrypt the payload with the outbound session key,
    // nonce = sender||epoch||seq, before fragmenting/sending. Sending
    // plaintext bytes here as a structural placeholder.
    uint8_t payload[sizeof(float)];
    memcpy(payload, &p, sizeof(p));

    auto frags = Fragmenter::split(hdr, payload, sizeof(payload));
    for (auto& frag : frags) {
        // TODO: hand `frag` (header + ciphertext bytes) to the real mesh
        // transport (ESP-NOW) once wired up. If g_weak_link_debug is set,
        // simulate cut TX power here (drop/delay some fraction of frags)
        // instead of actually reducing radio TX power — brief v2 section
        // 12 "opt" beat.
        (void)frag;
    }
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
    g_oled.printf("ML-KEM-%d | Batt %d%%\nSeq %04lu | %s\n",
                  static_cast<int>(g_kem_level), static_cast<int>(battery_pct),
                  static_cast<unsigned long>(g_seq), status_text);
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
    status_indicators_init();

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

    Serial.println("LOG field_node boot complete");
}

void loop() {
    static uint32_t last_send_ms = 0;
    static uint32_t last_adapt_ms = 0;
    static uint32_t last_display_ms = 0;
    uint32_t now = millis();

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
