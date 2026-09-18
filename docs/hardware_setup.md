# Hardware setup — energy rig (v4)

Written 2026-09-18 for whoever has the boards in hand. Grounded in what's
already in the repo (`firmware/platformio.ini`, `firmware/src/common/
board_config.h`) rather than invented from scratch, so it doesn't
contradict what the firmware stream already assumed. Companion to
`docs/v4_energy_split.md` (the work split) — this file is just the
physical setup, step by step, verifying each stage before wiring the next.

## Why four boards, not three

The existing `platformio.ini` only defines three environments —
`field_node`, `gateway`, `attacker`. v4 adds a fourth board, **Monitor**,
whose only job is reading the energy sensor so the measurement never
disturbs the node being measured (brief v4 §3's own reasoning: if the field
node read its own current sensor, the act of reading would cost energy and
contaminate the number).

| Board | Role | Powered by |
|---|---|---|
| Field node | Runs the crypto, the thing being measured | 18650 cell, via the rig below |
| Gateway | Receives the field node's traffic | USB (its battery life isn't the point) |
| Attacker | Sends HELLO floods / slow drip **at the field node** (the gateway overhears them for its trace windows) | USB |
| **Monitor (new)** | Reads the INA219, logs mJ per operation | USB (it's instrumentation) |

## Power path — battery → field node

```
18650 cell (+) ──> INA219 (VIN+ → VIN-) ──> 18650 boost/charge shield ──> 5V/VIN pin ──> field node
18650 cell (−) ──────────────────────────────────────────────────────> shield GND ──> field node GND
```

`board_config.h` already assumes "18650 on 5V shield" with a 100k/100k
divider onto ADC pin 39 (`PIN_BATTERY_ADC`) for a coarse, self-reported
battery percentage — that part predates v4 and stays as-is; it's a cheap
secondary reading, not the measurement rig.

**The INA219 goes on the raw battery lead, before the boost shield** — not
on the shield's regulated 5V output. Brief v4 §3 is explicit about this
("the INA219 measures current by sitting in series with the battery's
positive line"), and it matters: a boost converter's own efficiency would
otherwise get baked into every joule number without anyone noticing.

## Measurement path — INA219 → Monitor board (separate from power)

```
INA219 SDA/SCL   ──> Monitor ESP32 I2C bus (pins 21/22 — same defaults board_config.h
                                              already uses for the OLED/MPU6050 on the
                                              other boards; nothing else is on the
                                              Monitor's bus, so no address conflict)
Field node GPIO  ──> Monitor ESP32 GPIO input   (pick an unused pin on each — e.g. GPIO 4
                                                  on both — the field node raises it at an
                                                  operation's start, lowers it at the end)
Field node GND   ──> Monitor ESP32 GND          (REQUIRED — without a shared ground
                                                  reference the GPIO marker reads garbage
                                                  and I2C can misbehave, even though the
                                                  two boards have separate power supplies)
Monitor ESP32    ──> USB ──> laptop              (this is the board whose serial output
                                                   you actually watch during a run)
```

## Bill of materials

Brief v4 §10, cross-checked against what "already listed" means in this
repo's own v3 BOM:

| Item | Qty | Notes |
|---|---|---|
| ESP32-WROOM-32 dev board | 4 | 3 already accounted for (field_node/gateway/attacker); **1 new** for Monitor |
| 18650 Li-ion cell + boost/charge shield | 1 | Already in the v3 BOM. **Use a protected cell**, or one with a protection PCB — bare 18650s have no over-discharge/short protection built in |
| INA219 current/voltage sensor (I²C) | 1–2 | ~₹150–250 each. One is enough to start; a second on the gateway is optional/stretch per the brief |
| Jumper wires, screw terminals or JST leads | 1 set | ~₹50–100, for putting the INA219 in series safely |

## Safety notes

- Double-check polarity before connecting the INA219 — modules are usually
  silkscreened VIN+/VIN-. Reversed polarity on a shunt-based sensor is a
  common way to get either nonsense readings or a damaged board.
- **Never let the INA219's two leads touch each other or anything else**
  while the battery is connected — that is a direct short across the cell.
- Use a protected cell (see BOM above). If only a bare cell is available,
  add an inline fuse or a protection module rather than skipping it.

## Bring-up — one step at a time, verify before the next

Don't skip a row. Each one isolates exactly one new variable, so a failure
at step 5 doesn't leave four things to debug at once.

| # | Do | Verify before moving on |
|---|---|---|
| 1 | `pio run -e benchmark -t upload -t monitor` to **one** board, USB power only, no battery/INA219 yet | Serial prints the `algo,op,us,heap_used_bytes,stack_hwm_bytes,ok` CSV and the board doesn't crash/reboot. This is firmware's own pre-v4 "biggest risk" — does ML-DSA-44 even fit — resolve it before energy numbers matter at all. |
| 2 | Wire the INA219 to the Monitor board's I2C only (pins 21/22). Power the INA219 from a USB supply with a known load (an LED + resistor is enough). Flash a basic `Adafruit_INA219` library example | Serial prints plausible volts/mA for that known load — proves the sensor and I2C wiring are good, in isolation from every other unknown |
| 3 | Move the INA219 in series with the real 18650 → boost shield → field node. **Disconnect USB from the field node** — battery only. Field node just runs idle/blink firmware, nothing else | Field node boots and stays up on battery alone; the Monitor's INA219 reading settles to a sane idle mA figure. This is the "idle/hourly baseline" row in the brief's measurement table (§3). |
| 4 | Add the GPIO marker wire (field node → Monitor) and the shared GND. Flash a trivial sketch on the field node that just toggles the marker pin in a loop | Monitor sees clean, correctly-timed high/low edges — no floating or noisy transitions. Confirm this before trusting any per-operation energy number. |
| 5 | Flash the real `env:benchmark` sketch to the field node (now on battery, with INA219 + marker wired), Monitor logging CSV alongside it | The Monitor's mJ readings line up in time with the benchmark's own `us` timings for each operation. This is the actual "measured energy budget" deliverable (brief §3) — ML-KEM keygen/encaps/decaps ×3 levels, ML-DSA-44 sign/verify, AES-256-GCM per KB, radio handshake per level. |
| 6 | Only once step 5 is solid: bring in the gateway and attacker boards, wire up ESP-NOW, and move to the cookie challenge / token bucket / 5-row experiment (`docs/v4_energy_split.md`, Claude 3's section) | — |

## Where this feeds back into the software streams

- Step 1's benchmark CSV feeds directly into `firmware/src/benchmark/main.cpp`'s
  existing output format — v4 extends its columns with `mJ`/`peak_current_mA`
  sourced from the Monitor board (see `docs/v4_energy_split.md`, Claude 3 §1).
- Step 5's correlated mJ-per-operation numbers are what the console's
  battery chart and the brief's five-row experiment table (§6) are built
  from — see Claude 2's section of the same doc.
- None of this blocks `ml/`'s EnergyGate model work (Claude 1) or the
  console's frontend work (Claude 2) — both build against synthetic/fixture
  data first, per the stand-ins pattern this repo already uses everywhere.
