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

# per-class Trace generators: (feature overrides as (low, high) ranges)
TRACE_PROFILES = {
    "normal": dict(hs_per_s=(0.0, 0.2), hs_fail=(0, 0), replay_rej=(0, 0), auth_fail=(0, 0),
                   stale=(0, 0), frag_timeout=(0, 0), rssi_mean=(-62, -48), rssi_var=(0.5, 4.0),
                   loss_pct=(0.0, 1.5), jitter_ms=(1.0, 4.0)),
    "weak_link": dict(hs_per_s=(0.0, 0.4), hs_fail=(0, 1), replay_rej=(0, 0), auth_fail=(0, 0),
                      stale=(0, 2), frag_timeout=(0, 3), rssi_mean=(-92, -78), rssi_var=(6.0, 18.0),
                      loss_pct=(8.0, 34.0), jitter_ms=(12.0, 45.0)),
    "replay": dict(hs_per_s=(0.0, 0.2), hs_fail=(0, 0), replay_rej=(6, 28), auth_fail=(0, 1),
                   stale=(3, 14), frag_timeout=(0, 1), rssi_mean=(-64, -46), rssi_var=(0.5, 5.0),
                   loss_pct=(0.0, 2.0), jitter_ms=(1.0, 5.0)),
    "flood": dict(hs_per_s=(4.0, 22.0), hs_fail=(8, 40), replay_rej=(0, 2), auth_fail=(0, 3),
                  stale=(0, 3), frag_timeout=(1, 8), rssi_mean=(-70, -50), rssi_var=(1.0, 8.0),
                  loss_pct=(2.0, 15.0), jitter_ms=(4.0, 22.0)),
    "impersonation": dict(hs_per_s=(0.4, 2.5), hs_fail=(3, 12), replay_rej=(0, 3), auth_fail=(4, 18),
                          stale=(0, 4), frag_timeout=(0, 2), rssi_mean=(-68, -44), rssi_var=(1.0, 9.0),
                          loss_pct=(0.5, 6.0), jitter_ms=(2.0, 10.0)),
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


def make_event(scenario: str, rng: random.Random) -> dict | None:
    """The EVT a gateway would raise for this window, if any."""
    base = {"id": str(uuid.uuid4()), "ts": int(time.time() * 1000), "node": "attacker"}
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

    try:
        emit("LOG gateway boot, ESP-NOW up, awaiting handshake", 0)
        for scenario in scenarios:
            emit(f"LOG scenario={scenario}", gap_ms)
            ts = 0
            event_emitted = False
            for _ in range(args.windows):
                ts += args.window_ms
                emit("TRC " + json.dumps(make_trace(scenario, ts, rng, args.window_ms)), gap_ms)
                if not event_emitted:
                    ev = make_event(scenario, rng)
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
