// SentinelMesh energy-rig firmware -- the "Monitor" ESP32 (brief v4 /
// docs/v4_energy_split.md, firmware task 1: "new src/monitor/main.cpp +
// platformio.ini env for the second ('Monitor') ESP32 -- INA219 over I2C
// at ~1kHz, reads a GPIO marker the field node raises/lowers at each
// operation's start/end, attributes mJ per operation.").
//
// Wiring: the INA219 breakout sits in series with the board-under-test's
// supply (whichever board is running src/benchmark during a bench
// measurement, or the field node during a real deployment run), and its
// I2C pins (SDA/SCL) go to this Monitor board. A single GPIO jumper
// (board::PIN_ENERGY_MARKER, same pin number on both boards) carries the
// marker: HIGH while a measured operation is in progress, LOW at rest.
// This board has no idea *what* operation is running -- it only knows a
// marked interval started and ended, and how many mJ and how much peak
// current passed during it. Correlate rows here with the matching
// src/benchmark CSV line by run order (start both captures together) or
// by hand-annotating the label at capture time.
//
// Covers, per docs/v4_energy_split.md task 1: ML-KEM keygen/encaps/decaps
// x3 levels, ML-DSA-44 sign/verify, AES-256-GCM per KB, radio handshake
// per level, idle/hourly baseline -- src/benchmark's job is to bracket
// each of those with the marker pin; this board just measures whatever
// interval it's shown.
//
// STATUS: structural, matches the rest of the firmware's "write code that
// compiles, not yet build-verified on hardware" state -- no INA219 board
// or second ESP32 available in the environment this was written in.

#include <Arduino.h>
#include <Wire.h>
#include <Adafruit_INA219.h>
#include "common/board_config.h"

using namespace sentinel; // board:: lives in sentinel::board (common/board_config.h)

static Adafruit_INA219 g_ina219;
static bool g_ina219_ok = false;

// Sampling target ~1kHz (brief v4 task 1). The INA219's default 12-bit
// bus+shunt ADC conversion takes ~532us/sample, so 1ms is close to the
// fastest this chip can actually manage without trading away resolution
// -- documented so real hardware isn't "surprised" to land near ~1.5-1.8kHz
// achievable rather than exactly 1000.0 Hz.
constexpr uint32_t SAMPLE_INTERVAL_US = 1000;

static bool g_marker_active = false;
static uint32_t g_interval_start_us = 0;
static double g_interval_energy_uj = 0.0; // accumulated over the current marked interval
static float g_interval_peak_ma = 0.0f;
static uint32_t g_op_index = 0;
static uint32_t g_last_sample_us = 0;

// v4: continuous telemetry for the console's battery chart -- one
// `NRG <json>` line per second (contracts/CONTRACT.md "Serial lines",
// contracts/energy.schema.json), alongside the per-operation CSV above.
// Without it the console's power/battery charts have no real data.
constexpr uint32_t NRG_INTERVAL_US = 1000000;
static uint32_t g_nrg_start_us = 0;
static double g_nrg_energy_mj = 0.0;  // integral of power over the interval
static double g_nrg_seconds = 0.0;
static float g_last_load_v = 0.0f;
static float g_last_current_ma = 0.0f;

// Reports a completed interval. CSV columns extend the src/benchmark shape
// (algo,op,us,heap_used_bytes,stack_hwm_bytes,ok) with the two columns
// only this board can measure -- mJ and peak_current_mA -- prefixed with
// a running op_index instead of an algo/op name, since this board can't
// see which operation the board under test thinks it's running.
static void report_interval(uint32_t duration_us) {
    double mj = g_interval_energy_uj / 1000.0; // accumulated in micro-joules -> milli-joules
    Serial.printf("monitor,op_%lu,%lu,%.3f,%.2f\n",
                  static_cast<unsigned long>(g_op_index),
                  static_cast<unsigned long>(duration_us),
                  mj, static_cast<double>(g_interval_peak_ma));
    g_op_index++;
}

static void poll_marker(uint32_t now_us) {
    bool marker = digitalRead(board::PIN_ENERGY_MARKER) == HIGH;
    if (marker && !g_marker_active) {
        // Rising edge: a new measured operation started.
        g_marker_active = true;
        g_interval_start_us = now_us;
        g_interval_energy_uj = 0.0;
        g_interval_peak_ma = 0.0f;
    } else if (!marker && g_marker_active) {
        // Falling edge: it ended.
        g_marker_active = false;
        report_interval(now_us - g_interval_start_us);
    }
}

static void sample_ina219(double dt_s) {
    if (!g_ina219_ok) return;

    float current_ma = g_ina219.getCurrent_mA();
    float bus_v = g_ina219.getBusVoltage_V();
    float shunt_mv = g_ina219.getShuntVoltage_mV();
    float load_v = bus_v + (shunt_mv / 1000.0f);
    float power_mw = load_v * current_ma; // V * mA = mW

    g_nrg_energy_mj += static_cast<double>(power_mw) * dt_s;
    g_nrg_seconds += dt_s;
    g_last_load_v = load_v;
    g_last_current_ma = current_ma;

    if (g_marker_active) {
        g_interval_energy_uj += static_cast<double>(power_mw) * dt_s * 1000.0; // mW*s = mJ, *1000 -> uJ
        if (current_ma > g_interval_peak_ma) g_interval_peak_ma = current_ma;
    }
}

// Battery % from the cell voltage. The INA219 sits on the raw battery lead
// (docs/hardware_setup.md), so its load voltage is the cell's. An estimate --
// voltage sags under load -- which is why battery_pct is optional in the schema.
static float battery_pct_from_volts(float v) {
    float pct = (v - board::BATTERY_EMPTY_V) / (board::BATTERY_FULL_V - board::BATTERY_EMPTY_V) * 100.0f;
    if (pct < 0.0f) pct = 0.0f;
    if (pct > 100.0f) pct = 100.0f;
    return pct;
}

static void emit_nrg_line() {
    if (!g_ina219_ok || g_nrg_seconds <= 0.0) return;
    double mean_mw = g_nrg_energy_mj / g_nrg_seconds;
    g_nrg_energy_mj = 0.0;
    g_nrg_seconds = 0.0;
    if (mean_mw < 0.0) {
        // Negative current usually means the shunt is wired backwards. The
        // schema rejects negative power, so say so instead of sending it.
        Serial.println("LOG monitor: negative power -- is the INA219 wired VIN+/VIN- backwards?");
        return;
    }
    // ts is uptime millis(); the console swaps in arrival time (CONTRACT.md "Timestamps").
    Serial.printf("NRG {\"ts\":%lu,\"power_mw\":%.1f,\"volts\":%.3f,\"amps\":%.4f,\"battery_pct\":%.1f}\n",
                  static_cast<unsigned long>(millis()), mean_mw, static_cast<double>(g_last_load_v),
                  static_cast<double>(g_last_current_ma) / 1000.0,
                  static_cast<double>(battery_pct_from_volts(g_last_load_v)));
}

void setup() {
    Serial.begin(board::CONSOLE_SERIAL_BAUD);
    pinMode(board::PIN_ENERGY_MARKER, INPUT);

    Wire.begin(board::I2C_SDA, board::I2C_SCL);
    g_ina219_ok = g_ina219.begin();
    if (g_ina219_ok) {
        // 32V/2A range covers a USB-powered ESP32 dev board comfortably;
        // tighten this once the actual 18650-via-divider setup is known,
        // for better ADC resolution on the much smaller currents involved.
        g_ina219.setCalibration_32V_2A();
    } else {
        Serial.println("LOG monitor: INA219 not found on I2C bus");
    }

    Serial.println("LOG monitor boot complete");
    Serial.println("monitor,op,us,mJ,peak_current_mA");
    g_last_sample_us = micros();
    g_nrg_start_us = g_last_sample_us;
}

void loop() {
    uint32_t now_us = micros();
    if (now_us - g_last_sample_us >= SAMPLE_INTERVAL_US) {
        double dt_s = static_cast<double>(now_us - g_last_sample_us) / 1e6;
        sample_ina219(dt_s);
        poll_marker(now_us);
        g_last_sample_us = now_us;
    }
    if (now_us - g_nrg_start_us >= NRG_INTERVAL_US) {
        emit_nrg_line();
        g_nrg_start_us = now_us;
    }
}
