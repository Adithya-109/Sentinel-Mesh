"""Stand-in for the v4 hardware: a simulated field node + INA219 monitor +
gateway, driven live by the console's demo controls.

Until Claude 3's energy rig exists, this is what lets the whole v4 frontend be
built and rehearsed -- the battery chart, the gate-decision feed, the defence
and attack buttons, and the five-row experiment table -- with nothing plugged in.

Once a second it:
  * reads GET /control (the same state the serial bridge relays to real boards);
  * posts one power sample to POST /energy whose draw depends on the current
    defence x attack combination, and drains a simulated battery accordingly;
  * posts the events the gateway would relay: gate_decision (field-1 runs
    EnergyGate on inbound HELLOs; the gateway forwards its decisions -- EnergyGate mode
    only), energy_alert when draw spikes, budget_exhausted if the token bucket
    empties, and replay/impersonation rejections for those attack profiles;
  * posts a Trace row every few seconds, so /status sees the gateway alive and
    trace recording works end to end.

EVERY NUMBER HERE IS MADE UP. Draw figures are chosen to mirror the brief's
hypothesis (a loud flood drains the cell; a slow drip slips under a rate limit;
EnergyGate holds draw near idle) -- they illustrate the claim, they are not
evidence for it. Every sample is tagged `source: "sim"`, so the console labels
the chart, the status bar and any experiment row it touches as SIMULATED.

    python tools/mock_rig.py                     # run until Ctrl+C
    python tools/mock_rig.py --time-warp 120     # battery drains 120x real time
"""
import argparse
import os
import random
import sys
import time
import uuid

import requests

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from mock_serial import make_trace  # noqa: E402

DEFAULT_CONSOLE = "http://127.0.0.1:8000"   # never localhost -- see api/config.py
HTTP = requests.Session()

IDLE_MW = 84.0

# mean draw (mW) for attack profile x defence. Illustrative, see docstring.
DRAW = {
    "none":        {"none": IDLE_MW, "ratelimit": IDLE_MW, "cookie": IDLE_MW, "gate": IDLE_MW + 3},
    "loud":        {"none": 512.0, "ratelimit": 190.0, "cookie": 130.0, "gate": 96.0},
    # the slow drip's point: it sits under a rate limit, so the limit does nothing
    "slow_drip":   {"none": 150.0, "ratelimit": 150.0, "cookie": 110.0, "gate": 92.0},
    "replay":      {"none": 118.0, "ratelimit": 118.0, "cookie": 118.0, "gate": 118.0},
    "impersonate": {"none": 160.0, "ratelimit": 140.0, "cookie": 120.0, "gate": 105.0},
    "weak_link":   {"none": 100.0, "ratelimit": 100.0, "cookie": 100.0, "gate": 100.0},
}

# seconds between attacker admission attempts EnergyGate has to rule on
ATTEMPT_EVERY_S = {"loud": 2, "slow_drip": 15, "impersonate": 6}
TRACE_SCENARIO = {"none": "normal", "loud": "flood", "slow_drip": "flood", "replay": "replay",
                  "impersonate": "impersonation", "weak_link": "weak_link"}

BUDGET_MAX_J = 40.0
REFILL_J_PER_S = 0.5
COST_J = {"spend": 2.1, "challenge": 0.05, "drop": 0.01}


class Rig:
    def __init__(self, console: str, warp: float, battery_pct: float, rng: random.Random):
        self.console = console
        self.warp = warp
        self.battery_pct = battery_pct
        self.rng = rng
        self.budget_j = BUDGET_MAX_J
        self.tick = 0
        self.last_alert_tick = -999
        self.exhausted_sent = False

    # -- http --------------------------------------------------------------

    def post(self, path, payload):
        try:
            r = HTTP.post(f"{self.console}{path}", json=payload, timeout=3)
            if r.status_code >= 400:
                print(f"! {path} -> {r.status_code} {r.text[:160]}", file=sys.stderr)
        except requests.RequestException as exc:
            print(f"! console unreachable: {exc.__class__.__name__}", file=sys.stderr)

    def control(self) -> dict:
        try:
            return HTTP.get(f"{self.console}/control", timeout=3).json()
        except (requests.RequestException, ValueError):
            return {"mode": "none", "attack_profile": "none"}

    def event(self, type_, severity, summary, reasons, details, score=None, node="gateway",
              technique=None):
        self.post("/events", {
            "id": str(uuid.uuid4()), "ts": int(time.time() * 1000), "layer": "field",
            "type": type_, "severity": severity, "score": score, "node": node,
            "technique": technique, "summary": summary, "reasons": reasons, "details": details,
        })

    # -- one simulated second ---------------------------------------------

    def step(self):
        self.tick += 1
        c = self.control()
        mode, attack = c.get("mode", "none"), c.get("attack_profile", "none")

        draw = DRAW.get(attack, DRAW["none"]).get(mode, IDLE_MW) * self.rng.uniform(0.94, 1.06)
        joules = draw / 1000 * self.warp                           # this second, time-warped
        self.battery_pct = max(0.0, self.battery_pct - joules / (9.25 * 3600) * 100)
        volts = round(3.3 + 0.9 * self.battery_pct / 100, 3)
        self.post("/energy", {"power_mw": round(draw, 1), "volts": volts,
                              "amps": round(draw / volts / 1000, 4),
                              "battery_pct": round(self.battery_pct, 3), "source": "sim"})

        if self.tick % 5 == 0:
            trace = make_trace(TRACE_SCENARIO.get(attack, "normal"), self.tick * 1000, self.rng)
            trace["battery_pct"] = round(self.battery_pct, 2)
            self.post("/traces", trace)

        if mode == "gate":
            self.budget_j = min(BUDGET_MAX_J, self.budget_j + REFILL_J_PER_S)
            self.gate(attack)
        else:
            self.budget_j = BUDGET_MAX_J
            self.exhausted_sent = False

        multiple = draw / IDLE_MW
        if multiple >= 1.6 and self.tick - self.last_alert_tick >= 20:
            self.last_alert_tick = self.tick
            sev = "critical" if multiple >= 6 else "high" if multiple >= 4 else "medium" if multiple >= 2 else "low"
            self.event("energy_alert", sev, f"Battery draw {multiple:.1f}x baseline",
                       [f"draw {draw:.0f} mW vs {IDLE_MW:.0f} mW idle",
                        f"attack profile '{attack}' active, defence '{mode}'"],
                       {"draw_mw": round(draw, 1), "baseline_mw": IDLE_MW}, node="field-1")

        if attack == "replay" and self.tick % 8 == 0:
            self.event("replay_rejected", "medium", "Replayed reading rejected (seq already seen)",
                       ["sequence inside the 64-bit replay window", "session timestamp stale"],
                       {"peer": "field-1"}, node="attacker", technique="T1692.002")
        if attack == "impersonate" and mode != "gate" and self.tick % 6 == 0:
            self.event("handshake_rejected", "high", "Handshake rejected: ML-DSA signature did not verify",
                       ["claimed sender field-1", "ML-DSA-44 verify failed"],
                       {"claimed_sender": "field-1"}, node="attacker", technique="T0830")
        return mode, attack, draw

    def gate(self, attack: str):
        # the genuine gateway handshaking with field-1 every 10 s -- EnergyGate
        # runs on field-1, so the legitimate sender it must still let through
        # is the gateway (brief v4 beat 4: "a genuine node still gets through")
        if self.tick % 10 == 0:
            self.decide("spend", self.rng.uniform(0.88, 0.97), "gateway",
                        ["known sender gateway", "fragments 100% complete",
                         f"RSSI steady ({self.rng.randint(-56, -47)} dBm)"])
        every = ATTEMPT_EVERY_S.get(attack)
        if every and self.tick % every == 0:
            sender = "unknown-7f"
            if self.rng.random() < 0.35:
                self.decide("challenge", self.rng.uniform(0.15, 0.3), sender,
                            ["no completed handshake before",
                             f"{self.rng.randint(3, 9)} attempts in 4 s"])
            else:
                self.decide("drop", self.rng.uniform(0.02, 0.09), sender,
                            ["cookie not echoed",
                             f"fragments never complete ({self.rng.randint(5, 20)}% complete)",
                             "no completed handshake before"])

    def decide(self, action: str, prob_real: float, sender: str, reasons: list[str]):
        self.budget_j = max(0.0, self.budget_j - COST_J[action])
        sev = {"spend": "info", "challenge": "low", "drop": "medium"}[action]
        self.event("gate_decision", sev, f"EnergyGate: {action.upper()} {sender}", reasons,
                   {"action": action, "sender": sender, "budget_j": round(self.budget_j, 2),
                    "budget_max_j": BUDGET_MAX_J}, score=round(prob_real, 3), node="field-1")
        if self.budget_j <= 0 and not self.exhausted_sent:
            self.exhausted_sent = True
            self.event("budget_exhausted", "high", "EnergyGate budget exhausted",
                       ["token bucket empty", "further handshakes deferred until refill"], {}, node="field-1")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--console", default=DEFAULT_CONSOLE)
    ap.add_argument("--time-warp", type=float, default=60.0,
                    help="battery drains this many times faster than real time, so a "
                         "change is visible within a minute on stage")
    ap.add_argument("--battery", type=float, default=80.0, help="starting battery %%")
    ap.add_argument("--seconds", type=int, default=0, help="stop after N ticks (0 = forever)")
    ap.add_argument("--interval", type=float, default=1.0, help="seconds per tick")
    ap.add_argument("--seed", type=int, default=11)
    args = ap.parse_args()

    rig = Rig(args.console, args.time_warp, args.battery, random.Random(args.seed))
    print("mock rig running -- every sample is tagged SIMULATED. Ctrl+C to stop.")
    try:
        while args.seconds == 0 or rig.tick < args.seconds:
            mode, attack, draw = rig.step()
            if rig.tick % 10 == 0:
                print(f"t={rig.tick:>5}s  defence={mode:<9} attack={attack:<11} "
                      f"draw={draw:6.1f} mW  battery={rig.battery_pct:5.1f}%  budget={rig.budget_j:4.1f} J")
            time.sleep(args.interval)
    except KeyboardInterrupt:
        pass
    print("mock rig stopped")


if __name__ == "__main__":
    main()
