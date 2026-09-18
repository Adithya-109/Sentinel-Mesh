"""Stand-in for the gateway ESP32: emits EVT / TRC / LOG lines, no hardware.

Produces exactly the line protocol contracts/CONTRACT.md defines, so the
serial bridge can be developed and rehearsed before any board arrives, and so
the demo has a fallback if the hardware dies on stage.

    # live, into the bridge
    python tools/mock_serial.py | python -m bridge.serial_bridge --stdin -v

    # write the fallback log the runbook replays
    python tools/mock_serial.py --log demo/serial_log.txt --scenario all

TRC lines carry one detection window each, in the five classes the field model
learns: normal, weak_link, replay, flood, impersonation. `--scenario` picks
which. Lines written to a log are prefixed `+<ms> ` with the gap that followed
the previous line, so `serial_bridge --replay` can reproduce the pacing.
"""
import argparse
import json
import random
import sys
import time
import uuid

SCENARIOS = ["normal", "weak_link", "replay", "flood", "impersonation"]

# per-class Trace generators: (feature overrides as (low, high) ranges).
# frag_complete_pct / dup_pct are the v4 optional fields EnergyGate trains on
# (ml/sentinel_ml/energygate.py): without them a recording made from this
# stand-in would silently fall back to EnergyGate's "healthy" defaults. A
# replay shows up as duplicates; a flood as fragment sets that never complete.
TRACE_PROFILES = {
    "normal": dict(hs_per_s=(0.0, 0.2), hs_fail=(0, 0), replay_rej=(0, 0), auth_fail=(0, 0),
                   stale=(0, 0), frag_timeout=(0, 0), rssi_mean=(-62, -48), rssi_var=(0.5, 4.0),
                   loss_pct=(0.0, 1.5), jitter_ms=(1.0, 4.0),
                   frag_complete_pct=(97.0, 100.0), dup_pct=(0.0, 1.0)),
    "weak_link": dict(hs_per_s=(0.0, 0.4), hs_fail=(0, 1), replay_rej=(0, 0), auth_fail=(0, 0),
                      stale=(0, 2), frag_timeout=(0, 3), rssi_mean=(-92, -78), rssi_var=(6.0, 18.0),
                      loss_pct=(8.0, 34.0), jitter_ms=(12.0, 45.0),
                      frag_complete_pct=(70.0, 92.0), dup_pct=(1.0, 6.0)),
    "replay": dict(hs_per_s=(0.0, 0.2), hs_fail=(0, 0), replay_rej=(6, 28), auth_fail=(0, 1),
                   stale=(3, 14), frag_timeout=(0, 1), rssi_mean=(-64, -46), rssi_var=(0.5, 5.0),
                   loss_pct=(0.0, 2.0), jitter_ms=(1.0, 5.0),
                   frag_complete_pct=(95.0, 100.0), dup_pct=(15.0, 45.0)),
    "flood": dict(hs_per_s=(4.0, 22.0), hs_fail=(8, 40), replay_rej=(0, 2), auth_fail=(0, 3),
                  stale=(0, 3), frag_timeout=(1, 8), rssi_mean=(-70, -50), rssi_var=(1.0, 8.0),
                  loss_pct=(2.0, 15.0), jitter_ms=(4.0, 22.0),
                  frag_complete_pct=(5.0, 30.0), dup_pct=(2.0, 10.0)),
    "impersonation": dict(hs_per_s=(0.4, 2.5), hs_fail=(3, 12), replay_rej=(0, 3), auth_fail=(4, 18),
                          stale=(0, 4), frag_timeout=(0, 2), rssi_mean=(-68, -44), rssi_var=(1.0, 9.0),
                          loss_pct=(0.5, 6.0), jitter_ms=(2.0, 10.0),
                          frag_complete_pct=(60.0, 90.0), dup_pct=(0.0, 4.0)),
}


def _rand(rng, lo_hi, integer: bool):
    lo, hi = lo_hi
    return rng.randint(int(lo), int(hi)) if integer else round(rng.uniform(lo, hi), 2)


INT_FIELDS = {"hs_fail", "replay_rej", "auth_fail", "stale", "frag_timeout"}


def make_trace(scenario: str, ts: int, rng: random.Random, window_ms: int = 5000) -> dict:
    prof = TRACE_PROFILES[scenario]
    row = {"ts": ts, "node": "gateway", "label": scenario, "window_ms": window_ms}
    for name, rng_pair in prof.items():
        row[name] = _rand(rng, rng_pair, name in INT_FIELDS)
    return row


# power draw (mW) the INA219 would see during each scenario -- illustrative only
SCENARIO_DRAW_MW = {"normal": 84.0, "weak_link": 100.0, "replay": 118.0, "flood": 512.0,
                    "impersonation": 160.0}


def make_energy(scenario: str, uptime_ms: int, rng: random.Random, battery_pct: float) -> dict:
    """One NRG sample, as the INA219 monitor board would print it. `ts` is
    uptime millis() like real firmware; the console swaps in arrival time.
    Tagged source=sim so nobody quotes these numbers."""
    draw = SCENARIO_DRAW_MW[scenario] * rng.uniform(0.95, 1.05)
    volts = round(3.3 + 0.9 * battery_pct / 100, 3)
    return {"ts": uptime_ms, "power_mw": round(draw, 1), "volts": volts,
            "amps": round(draw / volts / 1000, 4), "battery_pct": round(battery_pct, 2),
            "source": "sim"}


def make_event(scenario: str, rng: random.Random, uptime_ms: int = 0) -> dict | None:
    """The EVT a gateway would raise for this window, if any.

    `ts` is the board's uptime millis(), exactly as firmware sends it -- NOT
    wall-clock time. A replay log with baked-in epoch times would land those
    events in the past on replay and they would never correlate with the live
    mail/file events; with uptime, the console stamps them on arrival."""
    base = {"id": str(uuid.uuid4()), "ts": uptime_ms, "node": "attacker"}
    if scenario == "replay":
        return {**base, "layer": "field", "type": "replay_rejected", "severity": "medium",
                "score": None, "technique": "T1692.002",
                "summary": f"Replayed reading rejected (seq {rng.randint(20, 60)} already seen)",
                "reasons": ["sequence inside the 64-bit replay window", "session timestamp stale"],
                "details": {"peer": "field-1"}}
    if scenario == "flood":
        return {**base, "layer": "field", "type": "attack_detected", "severity": "high",
                "score": None, "technique": "T0830",
                "summary": "Handshake flood from attacker node",
                "reasons": [f"{rng.randint(12, 40)} handshakes in one window",
                            "all failed signature verification", "sender locked out"],
                "details": {"kind": "handshake_flood", "locked_out": True}}
    if scenario == "impersonation":
        return {**base, "layer": "field", "type": "handshake_rejected", "severity": "high",
                "score": None, "technique": "T0830",
                "summary": "Handshake rejected: ML-DSA signature did not verify",
                "reasons": ["claimed sender field-1", "ML-DSA-44 verify failed",
                            "public key not in the provisioned set"],
                "details": {"claimed_sender": "field-1"}}
    if scenario == "weak_link":
        return {**base, "layer": "field", "type": "link_degraded", "severity": "low",
                "node": "field-1", "score": None, "technique": None,
                "summary": "Field node link degraded",
                "reasons": ["low RSSI", "elevated packet loss"], "details": {}}
    return None


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--scenario", default="all", choices=SCENARIOS + ["all"],
                    help="'all' walks every class in turn")
    ap.add_argument("--windows", type=int, default=12, help="trace windows per scenario")
    ap.add_argument("--window-ms", type=int, default=5000)
    ap.add_argument("--interval", type=float, default=1.0, help="seconds between lines when streaming")
    ap.add_argument("--log", help="write to this file (with +<ms> pacing prefixes) instead of streaming")
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--no-energy", dest="energy", action="store_false",
                    help="omit the v4 NRG lines and energy_alert")
    args = ap.parse_args()

    rng = random.Random(args.seed)
    scenarios = SCENARIOS if args.scenario == "all" else [args.scenario]

    out = open(args.log, "w", encoding="utf-8") if args.log else sys.stdout
    logging = args.log is not None
    gap_ms = int(args.interval * 1000)

    def emit(line: str, gap: int):
        if logging:
            out.write(f"+{gap} {line}\n")
        else:
            out.write(line + "\n")
            out.flush()
            time.sleep(gap / 1000.0)

    uptime = 3_000        # board uptime ms, like firmware's millis()
    battery = 80.0
    try:
        emit("LOG gateway boot, ESP-NOW up, awaiting handshake", 0)
        for scenario in scenarios:
            emit(f"LOG scenario={scenario}", gap_ms)
            ts = 0
            event_emitted = False
            alert_emitted = False
            for _ in range(args.windows):
                ts += args.window_ms
                uptime += args.window_ms
                trace = make_trace(scenario, ts, rng, args.window_ms)
                trace["battery_pct"] = round(battery, 2)
                emit("TRC " + json.dumps(trace), gap_ms)
                if args.energy:
                    battery = max(0.0, battery - SCENARIO_DRAW_MW[scenario] / 5000)
                    emit("NRG " + json.dumps(make_energy(scenario, uptime, rng, battery)), gap_ms)
                    if scenario == "flood" and not alert_emitted:
                        alert_emitted = True
                        draw = SCENARIO_DRAW_MW["flood"]
                        emit("EVT " + json.dumps({
                            "id": str(uuid.uuid4()), "ts": uptime, "layer": "field",
                            "type": "energy_alert", "severity": "high", "score": None,
                            "node": "field-1", "technique": None,
                            "summary": f"Battery draw {draw / 84:.1f}x baseline",
                            "reasons": ["handshake requests far above normal rate"],
                            "details": {"draw_mw": draw, "baseline_mw": 84.0}}), gap_ms)
                if not event_emitted:
                    ev = make_event(scenario, rng, uptime)
                    if ev:
                        emit("EVT " + json.dumps(ev), gap_ms)
                        event_emitted = True
    except KeyboardInterrupt:
        pass
    finally:
        if logging:
            out.close()
            print(f"wrote {args.log}")


if __name__ == "__main__":
    main()
