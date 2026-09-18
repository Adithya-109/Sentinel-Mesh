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
                           + benchmark env + native (host test) env
  lib/sentinel_proto/      shared protocol code
    include/sentinel_proto/
      types.h              NodeId, MsgType, KemLevel enums
      packet.h              15B wire header (epoch 2B, seq 4B per brief v2 6.1)
      fragment.h              fragmentation + reassembly (235B/frag, ESP-NOW v1 budget)
      replay.h                 64-bit sliding window + freshness check (32-bit seq)
      field_model.h              rule-based classify_window() stand-in
      event.h                     EVT line builder (ArduinoJson, ESP32-only)
      trace.h                      TRC line builder (ArduinoJson, ESP32-only)
      auth_fallback.h                HMAC-PSK fallback if ML-DSA doesn't fit
    src/                     .cpp for each of the above
  src/
    common/
      board_config.h          shared pin map (2 real nodes' worth of sensors/indicators)
      status_indicators.h      shared RGB LED + buzzer helper (field_node + gateway)
    field_node/main.cpp        field node ("Node A") entry point
    gateway/main.cpp            gateway ("Node B") entry point
    attacker/main.cpp            attacker (red-team) entry point
    benchmark/main.cpp            crypto benchmark sketch (PQC + classical baseline)
  test/test_native/test_main.cpp  host-side unit tests (packet/fragment/replay/field_model)
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

Last run: **175 passed, 0 failed**, clean build (`-Wall -Wextra`, no warnings).
Covers `PacketHeader` serialize/deserialize (including rejecting bad
version/type/frag bounds and short buffers), `Fragmenter`/`Reassembler`
(in-order, out-of-order, duplicate fragments, timeout eviction, stream-table
cap), `ReplayFilter` (accept/duplicate/replay-rejected/stale-timestamp,
per-peer independence, reset on rehandshake), and `classify_window()`
(one case per class).

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
