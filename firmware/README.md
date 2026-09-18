# SentinelMesh firmware (Claude 3)

ESP32 firmware for the 3-node mesh: `field_node` ("Node A", pipeline valve
station sensor), `gateway` ("Node B"), `attacker`. Shared wire-protocol
code lives in `lib/sentinel_proto` and is written as portable C++ (no
`Arduino.h` in the core pieces) specifically so it can be unit-tested on
the host without any hardware or PlatformIO install.

**Update:** brief v2 (protocol details) has now been read and cross-checked
against everything built in the first pass. One real bug was found and
fixed (see below); everything else was either already consistent or has
been tightened up with v2's specifics.

**Update (v4, docs/v4_energy_split.md):** brief v4 adds EnergyGate (a
learned admission gatekeeper in front of the handshake) and a measured
energy budget across all 3 streams. Firmware's slice — see "v4 energy
work" below — is built and host-tested where it can be (cookie challenge,
energy token bucket, EnergyGate rule-based stand-in); the Monitor board
(INA219 rig) and the gateway wiring are structural/ESP32-only, same
"compiles, not yet flashed" status as everything else pre-hardware.
**Note:** this batch was written during a sandbox outage that also took
down the host-test runner (`tools/run_native_tests.sh`) partway through —
every new/changed line was manually re-traced against the test assertions
and the file contents re-verified end to end, but nobody has actually run
`g++` on it yet. Run `tools/run_native_tests.sh` as the very first thing
after pulling this and before building on top of it.

**Update (2026-09-18): EnergyGate moved from the gateway to field-1.** Brief
v4 puts it on the battery-powered node being drained (sections 1-4; the
INA219 is on the field node's battery line), and the gateway is USB-powered,
so gating there protected nothing the rig measures. Now:
- **field-1** answers inbound `HELLO`s and runs the whole admission path --
  `energygate_score()` + the joule budget + the cookie -- through the new
  host-tested `lib/sentinel_proto/gate_policy.h`, which also implements the
  four `DEFENSE` modes (none / ratelimit / cookie / gate) the five-row
  experiment needs. Its `battery_pct` feature is its own ADC reading. It
  raises `PIN_ENERGY_MARKER` around each decision so the monitor measures
  EnergyGate's own cost (brief section 3).
- **gateway** relays: `DEFENSE <mode>` from the console -> a `CONTROL` mesh
  message to field-1 (on change and every 30 s); field-1's `GATE_REPORT`
  messages -> the console's `gate_decision` / `budget_exhausted` events,
  `"node": "field-1"`. New payloads in `lib/sentinel_proto/gate_msgs.h`,
  new `MsgType`s `GATE_REPORT` (0x07) and `CONTROL` (0x08). It keeps the
  signed-handshake check, replay window, trace windows and lockout.
- **attacker** `FLOOD` / `SLOW_DRIP` aim at field-1 (broadcast, so the
  gateway still overhears them for its trace windows).
- **monitor** also prints a ~1 Hz `NRG <json>` line (contracts/
  energy.schema.json) -- it previously printed only per-operation CSV, so
  the console's battery chart had no real data.
- **Feature order fixed.** The stand-in read its 8 features in a different
  order from `ml/sentinel_ml/energygate.py`'s `FEATURE_ORDER`, which the real
  model is trained on. Verified: with the old order, an exported model
  mis-scored 90 of 450 rows (every replay window scored as genuine); with
  the new order, 0 of 450 differ from Python's `predict_proba`. To use the
  trained model, copy `ml/export/energygate.h` to
  `lib/sentinel_proto/include/sentinel_proto/energygate_model.h` --
  `energygate.cpp` compiles it in automatically, and field-1 logs which
  scorer it is running at boot.

Verified for real this time: **283/283 host assertions pass** under `g++`
(the v4 ones had never actually been run), and `pio run` **compiles
field_node, gateway, attacker and monitor for the ESP32**. Before this
change none of the five envs compiled: wolfSSL (listed for every board but
used only by the benchmark) failed with "Found both ESPIDF and ARDUINO", the
gateway passed `String` where `const char*` was needed, and the monitor
used `board::` without `using namespace sentinel`. wolfSSL is now scoped to
`env:benchmark`. **`env:benchmark` still does not compile** -- the same
wolfSSL clash plus PQC API names (`KyberKey`, `wc_dilithium_*`) that don't
match the installed wolfSSL. That is the project's known go/no-go crypto
risk and was not touched here.

## v4 energy work (docs/v4_energy_split.md)

Firmware's slice, in the order it was built:

1. **Cookie challenge** (`lib/sentinel_proto/cookie.h`) — stateless
   DTLS-style return-routability cookie: an 8-byte value derived from a
   secret + sender id + time window, verified without the gateway storing
   anything. Host-tested (7 new assertions): determinism, sender/secret
   separation, window-boundary tolerance, rejection outside that window.
   Not yet wired into a real send/verify round trip — there's no wire slot
   for it until the actual HELLO/RESPONSE messages exist (brief v2 6.2),
   so `on_mesh_packet()`'s CHALLENGE branch generates a cookie but doesn't
   send it yet; that's the next step once the handshake is real.
2. **Energy token bucket** (`lib/sentinel_proto/energy_budget.h`) — joules,
   refills over time, `spend`/`can_afford`/`credit`. Host-tested (10 new
   assertions): default/explicit/clamped initial balance, spend
   success/failure, refill math and its capacity clamp, `can_afford` not
   mutating state, the `exhausted()` edge.
3. **EnergyGate rule-based stand-in** (`lib/sentinel_proto/energygate.h`,
   `energygate_score()`) — same pattern as `field_model.h`'s
   `classify_window()`: a placeholder with the exact signature Claude 1's
   real `ml/export/energygate.h` will export, so field-1's call site
   doesn't change when that lands (see the 2026-09-18 update above for the
   feature-order fix and the automatic model hook). Host-tested (3 new assertions): a
   healthy-looking sender scores high, a flooding one scores low, output
   stays in [0,1] at extreme inputs.
4. **Admission wiring** — *superseded: now on field-1, see the 2026-09-18
   update above.* Originally in `src/gateway/main.cpp`: every incoming `HELLO`
   ran EnergyGate *before* any signature-verification work: builds
   the 8-feature vector from this window's counters, scores it, spends
   from the token bucket (or challenges, or drops) based on
   `GATE_SPEND_THRESHOLD`/`GATE_CHALLENGE_THRESHOLD`, and emits a
   `gate_decision` EVT with `details.action` and the model's probability
   in the Event's top-level `score` (per the corrected contract shape —
   **not** duplicated into `details`). `budget_exhausted` fires once,
   edge-triggered, when the bucket hits zero. `energy_alert` is
   implemented (severity scales with draw-vs-baseline ratio) but has no
   live call site yet — no data path from the Monitor board to the
   gateway exists until the energy rig is actually wired up.
5. **Trace v4 fields** (`lib/sentinel_proto/trace.h`) — `frag_complete_pct`
   and `dup_pct` are now tracked and always emitted (computable from
   counters the gateway already keeps); `battery_pct` stays omitted until
   the DATA payload decrypt path exists to actually read it from the field
   node, rather than writing a fake value.
6. **Energy rig** (`src/monitor/main.cpp`, `env:monitor` in
   `platformio.ini`) — the 4th ("Monitor") ESP32: INA219 over I2C at
   ~1kHz (the chip's real achievable rate at default resolution, not
   exactly 1000.0 Hz — documented in the file), watching a GPIO marker
   pin shared with the board under test. Prints
   `monitor,op_<n>,<us>,<mJ>,<peak_mA>` per marked interval; correlate
   with `src/benchmark`'s own CSV by run order. Structural only — no
   INA219 board or second ESP32 available to build against.
7. **Attacker slow-drip profile** (`src/attacker/main.cpp`,
   `MODE SLOW_DRIP`) — ~1 handshake/min, reusing `tick_flood()`'s packet
   construction at a cadence deliberately too slow to trip
   `classify_window()`'s FLOOD threshold. The point (brief section 6):
   demonstrates why a plain rate limit misses this and EnergyGate's
   budget-over-time view is needed instead.

**Still open from `docs/v4_energy_split.md`**, not attempted this round
(need real hardware or a team decision first):
- ~~The `mode`/`attack` serial line format~~ -- settled in
  contracts/CONTRACT.md (`DEFENSE <mode>`, the attacker's existing `MODE`
  lines); the gateway now parses `DEFENSE` and relays it to field-1.
- `GatePolicyConfig::handshake_cost_j` (gate_policy.h) and
  `ENERGY_BUDGET_CAPACITY_J` / `ENERGY_BUDGET_REFILL_J_PER_S` in
  `field_node/main.cpp` are guesses -- the 5-row experiment and real cost
  table wait on the energy rig existing on real boards.
- The mesh transport (ESP-NOW) is still a stub on every board, so none of
  the messages above actually travel yet; the HELLO framing has no slot for
  the cookie echo yet (`cookie_echoed` is always false until it does).
- EnergyGate's training windows are recorded at the gateway; it runs at
  field-1, whose view of RSSI differs. Same feature definitions, different
  vantage point -- record field-1-side windows if the scores look off.
- Radio fingerprinting (stretch, brief's own cut order puts it first to
  cut) — not started.

## Status as of this milestone

Done and **verified** (175/175 host-side assertions pass, see below):
- Packet header (15B) — serialize/deserialize round-trip. **Fixed after
  reading brief v2**: the first pass had `epoch` as 4 bytes and `seq` as 2
  bytes; brief v2 section 6.1's packet-format table is authoritative and
  gives `epoch=2B, seq=4B` (`seq` is also called out as "32-bit sequence
  counter" in section 7). This was a real wire-format bug — anything built
  against the old layout would've been silently incompatible. Fixed in
  `packet.h`/`packet.cpp`, propagated through `replay.h`/`.cpp` and
  `fragment.h`'s `StreamKey`, all call sites, and the tests; re-verified
  green after the fix.
- Fragmentation + reassembly — in-order, out-of-order, duplicate, timeout
  eviction, stream-table cap. `MAX_FRAGMENT_PAYLOAD` corrected from a
  placeholder 200B to 235B (ESP-NOW v1's 250B frame budget minus the 15B
  header), matching brief v2 6.3's worked fragment-count example.
- 64-bit sliding-window replay protection + freshness check.
- Rule-based `classify_window()` field-model stand-in (5-class: normal/weak_link/replay/flood/impersonation).

Two things brief v2 changed that are worth flagging rather than silently
resolving:
- **Anomaly detector classes**: brief v2 section 9 lists 6 output classes,
  including a `Jamming` class. `contracts/CONTRACT.md`'s `LABEL` command
  only defines 5 (`normal|weak_link|replay|flood|impersonation`) — no
  jamming. Since the contract is the cross-team interface (owned by
  Claude 2) and jamming is marked "Optional" in brief v2's own threat-model
  table, `classify_window()` stays at 5 classes for now. Raise with the
  team if jamming should be added to the contract.
- **Pressure sensor resolved**: the BOM (brief v2 section 11) confirms
  there's no dedicated pressure sensor — "pressure" is the storyboard's
  (section 2) demo payload for a pipeline valve station, not real hardware
  SentinelMesh measures. `field_node/main.cpp`'s `read_pressure_reading()`
  is intentionally a simulated value; this is no longer an open question
  and lines up with the brief's own "honesty rule" (section 8: label
  simulations clearly, which this now does).

Also added, driven directly by brief v2:
- **Reed switch + voltage-anomaly tamper detection** (`field_node/main.cpp`):
  brief v2 section 10 lists 4 tamper sensors (LDR, accelerometer, magnetic
  reed switch, voltage), the first pass only wired up 2. Reed switch is a
  second, independent "case opened" channel (works if the LDR is covered);
  voltage-anomaly tracks a slow rolling baseline and flags sudden jumps —
  distinct from the plain battery-% reading the adaptive engine uses.
- **OLED + RGB LED + buzzer on `field_node` too** (`src/common/status_indicators.h`,
  shared with `gateway`): the BOM has 2 of each (section 11), meaning both
  real nodes get status indicators, not just the gateway. LED color coding
  now follows brief v2 section 10 exactly: green=secure, yellow=degraded
  crypto/weak link, steady red=network attack, flashing red=physical
  tamper. `gateway/main.cpp` now drives this too (attack detection and
  lockout both set steady red + a buzzer chirp).
- **Classical X25519/ECDSA-P256 baseline in the crypto benchmark**
  (`src/benchmark/main.cpp`, `bench_classical_baseline()`): brief v2's
  deliverables checklist explicitly asks for "Performance benchmarking vs
  classical TLS: compare ML-KEM-512/768/1024 with X25519/ECDHE". Added an
  mbedtls-based X25519 ECDH benchmark (ships with the ESP32 Arduino core,
  no extra lib_dep). Signature baseline uses ECDSA/P-256 rather than true
  Ed25519 — classic mbedtls doesn't expose Ed25519 signing directly (that's
  in mbedtls 3.x's PSA crypto API, toolchain-version dependent) — labelled
  clearly in the code comment, same honesty-rule reasoning as the pressure
  sensor.
- **Debug weak-link button clarified**: `PIN_BTN_AUX` is brief v2's demo
  "opt" beat (section 12) — pressing it simulates cut TX power so the judge
  can see the ML call "Degraded link" instead of "attack" (the false-alarm
  test that's "the strongest answer to 'isn't your ML just a threshold?'").

Written but **not yet build-verified on hardware** (no ESP32 toolchain or
these libraries available in the environment this was written in — needs a
real `pio run` once you have PlatformIO + boards):
- `src/benchmark/main.cpp` — the ML-KEM-512/768/1024 + ML-DSA-44 + classical baseline benchmark.
- EVT/TRC JSON builders (`event.h`/`trace.h`, need ArduinoJson).
- `auth_fallback.h` (HMAC-PSK, needs mbedtls — bundled with ESP32 Arduino core, should just work).
- `field_node`, `gateway`, `attacker` `main.cpp` — structural skeletons with
  the protocol pieces wired together; handshake/AEAD/mesh-transport calls
  are marked `TODO` pending the benchmark results and actual radio driver
  (brief v2 recommends ESP-NOW, no external radio needed).

**Biggest open risk, per the brief:** whether ML-DSA-44 fits ESP32's
time/RAM/flash budget for the handshake — brief v2 6.3's numbers already
show it's the dominant cost (2,420B of e.g. a 3,253B ML-KEM-512 HELLO).
Flash `src/benchmark` to a board as soon as one is available — that's
priority zero, and brief v2's build plan (section 14) agrees: hours 9-12.
If wolfSSL's PQC build doesn't fit or won't compile, switch
`SENTINEL_PQC_BACKEND_WOLFSSL` to `SENTINEL_PQC_BACKEND_PQCLEAN` in
`platformio.ini` (vendor PQClean's `ml-kem-*`/`ml-dsa-44` C sources into
`lib/sentinel_proto/third_party/pqclean/` — not fetched here, no network
access to PQClean's repo from this environment; brief v2 8 also explicitly
says don't rely on liboqs, it targets desktop/server not ESP32). If
ML-DSA-44 doesn't fit either backend, fall back to `auth_fallback.h`'s
HMAC-PSK signing — already implemented and labelled clearly as non-PQC,
same fallback brief v2's build plan names for hours 9-12.

## Layout

```
firmware/
  platformio.ini          3 hardware envs (field_node, gateway, attacker)
                           + benchmark env + env:monitor (v4) + native (host test) env
  lib/sentinel_proto/      shared protocol code
    include/sentinel_proto/
      types.h              NodeId, MsgType, KemLevel enums
      packet.h              15B wire header (epoch 2B, seq 4B per brief v2 6.1)
      fragment.h              fragmentation + reassembly (235B/frag, ESP-NOW v1 budget)
      replay.h                 64-bit sliding window + freshness check (32-bit seq)
      field_model.h              rule-based classify_window() stand-in
      event.h                     EVT line builder (ArduinoJson, ESP32-only)
      trace.h                      TRC line builder (ArduinoJson, ESP32-only; v4 fields)
      auth_fallback.h                HMAC-PSK fallback if ML-DSA doesn't fit
      cookie.h                        v4: DTLS-style handshake-flood cookie
      energy_budget.h                  v4: EnergyGate's joule token bucket
      energygate.h                      v4: rule-based energygate_score() stand-in
    src/                     .cpp for each of the above
  src/
    common/
      board_config.h          shared pin map (2 real nodes' worth of sensors/indicators + v4 energy-marker pin)
      status_indicators.h      shared RGB LED + buzzer helper (field_node + gateway)
    field_node/main.cpp        field node ("Node A") entry point
    gateway/main.cpp            gateway ("Node B") entry point -- now runs EnergyGate per HELLO (v4)
    attacker/main.cpp            attacker (red-team) entry point -- now has MODE SLOW_DRIP (v4)
    benchmark/main.cpp            crypto benchmark sketch (PQC + classical baseline)
    monitor/main.cpp               v4: INA219 energy-rig entry point (4th board)
  test/test_native/test_main.cpp  host-side unit tests (packet/fragment/replay/field_model/cookie/energy_budget/energygate)
  tools/run_native_tests.sh         g++ build+run helper for the above
```

## Build (once PlatformIO + boards are available)

```bash
cd firmware
pio run -e field_node      # or gateway / attacker
pio run -e benchmark -t upload -t monitor   # flash + watch benchmark CSV output
pio test -e native                          # host-side unit tests via PlatformIO
```

## Host-side unit tests (no PlatformIO/hardware needed)

PlatformIO isn't installed in the environment this was built in, so the
tests were written to also compile with a bare `g++` and were run that way
to confirm they pass, including after the epoch/seq wire-format fix:

```bash
cd firmware
tools/run_native_tests.sh
```

Last confirmed-green run (pre-v4): **175 passed, 0 failed**, clean build
(`-Wall -Wextra`, no warnings). Covers `PacketHeader` serialize/deserialize
(including rejecting bad version/type/frag bounds and short buffers),
`Fragmenter`/`Reassembler` (in-order, out-of-order, duplicate fragments,
timeout eviction, stream-table cap), `ReplayFilter`
(accept/duplicate/replay-rejected/stale-timestamp, per-peer independence,
reset on rehandshake), and `classify_window()` (one case per class).

v4 adds 20 more assertions (7 cookie, 10 energy budget, 3 EnergyGate) --
manually re-traced against the implementation but **not yet re-run through
g++** (written during a sandbox outage, see the v4 update note above). Run
this before relying on the v4 pieces.

## Crypto benchmark

`src/benchmark/main.cpp` prints a CSV block over serial:
`algo,op,us,heap_used_bytes,stack_hwm_bytes,ok` for keygen/encaps/decaps on
ML-KEM-512/768/1024, keygen/sign/verify on ML-DSA-44, and the classical
X25519/ECDSA-P256 baseline, plus `shared_secret_match` lines. Flash it to
any of the 2 real boards first — see "Biggest open risk" above.

## Next steps (in priority order, aligned with brief v2 section 14's build plan)

1. Get a board, flash `env:benchmark`, capture real numbers, report back —
   this decides the crypto backend for everything else (brief v2 hours 9-12).
2. Vendor PQClean sources if wolfSSL's PQC build doesn't compile.
3. Once 2 boards exist: wire up ESP-NOW (brief v2's recommended transport —
   no external radio needed) behind the `on_mesh_packet()` /
   `Fragmenter::split()` call sites already in `gateway`/`field_node`/`attacker` `main.cpp`.
4. Implement the real 3-message handshake per brief v2 6.2 (HELLO/RESPONSE/CONFIRM,
   exact contents documented in the section 6.2 table) + AES-256-GCM
   encrypt/decrypt with the header as associated data (currently `TODO`-stubbed
   in all 3 `main.cpp`).
5. When `ml/export/field_model.h` lands from Claude 1 (after the "record
   traces" check-in), swap the body of `classify_window()` in
   `lib/sentinel_proto/src/field_model.cpp` for a call into the generated
   header — call sites don't need to change, the signature is identical on
   purpose.
6. Raise the jamming-class contract gap with the team (see above).
