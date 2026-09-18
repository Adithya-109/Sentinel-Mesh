"""The serial bridge's routing and control relay, and the stand-ins' output.

The stand-ins are what the demo falls back on when hardware fails, so their
output is held to the same contract as the real boards': every EVT, TRC and
NRG they produce must validate against contracts/*.schema.json.
"""
import json
import os
import random
import sys

CONSOLE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, CONSOLE)
sys.path.insert(0, os.path.join(CONSOLE, "tools"))

from api import validation  # noqa: E402
from bridge import serial_bridge  # noqa: E402

import mock_events  # noqa: E402
import mock_rig  # noqa: E402
import mock_serial  # noqa: E402


class FakeResponse:
    def __init__(self, status=201, body=None):
        self.status_code = status
        self._body = body if body is not None else {}
        self.content = b"{}"
        self.text = json.dumps(self._body)

    def json(self):
        return self._body


class FakeHTTP:
    """Records posts; answers GET /control from a dict the test mutates."""
    def __init__(self):
        self.posts = []
        self.control = {"label": "normal", "label_version": 1, "mode": "none", "mode_version": 1,
                        "attack_profile": "none", "attack_version": 1,
                        "label_line": "LABEL normal", "defense_line": "DEFENSE none",
                        "attack_line": "MODE OFF"}

    def post(self, url, json=None, timeout=None):
        self.posts.append((url.rsplit(":8000", 1)[-1], json))
        return FakeResponse()

    def get(self, url, timeout=None):
        return FakeResponse(200, dict(self.control))


# -- bridge routing ------------------------------------------------------------

def test_bridge_routes_each_line_kind(monkeypatch):
    http = FakeHTTP()
    monkeypatch.setattr(serial_bridge, "HTTP", http)
    stats = serial_bridge.Stats()
    for line in ['EVT {"id":"a"}', 'TRC {"ts":1}', 'NRG {"power_mw":84}', "LOG hello",
                 "GARBAGE", "EVT {not json"]:
        serial_bridge.handle_line(line, "http://127.0.0.1:8000", stats, verbose=False)
    assert [p for p, _ in http.posts] == ["/events", "/traces", "/energy"]
    # the non-JSON EVT counts as unparseable, not as an EVT
    assert (stats.evt, stats.trc, stats.nrg, stats.log, stats.bad) == (1, 1, 1, 1, 2)


def test_bridge_pushes_all_control_lines_once_then_only_changes(monkeypatch):
    http = FakeHTTP()
    monkeypatch.setattr(serial_bridge, "HTTP", http)
    sent, state = [], {}
    serial_bridge.poll_control("http://x", state, sent.append)
    assert sent == ["LABEL normal\n", "DEFENSE none\n", "MODE OFF\n"]   # start-up resync

    sent.clear()
    serial_bridge.poll_control("http://x", state, sent.append)
    assert sent == []                                                    # nothing changed

    http.control.update(mode="gate", mode_version=2, defense_line="DEFENSE gate")
    serial_bridge.poll_control("http://x", state, sent.append)
    assert sent == ["DEFENSE gate\n"]


# -- stand-ins honour the contract ---------------------------------------------

def test_every_mock_story_event_validates():
    for name, story in mock_events.STORIES.items():
        for _, template, _ in story:
            if isinstance(template, tuple):
                continue
            _, errors = validation.validate_event(mock_events.build(template))
            assert not errors, (name, template["type"], errors)


def test_mock_serial_lines_validate_and_use_uptime_timestamps():
    rng = random.Random(1)
    for scenario in mock_serial.SCENARIOS:
        t = mock_serial.make_trace(scenario, 5000, rng)
        assert not validation.validate_trace(t)[1], scenario
        e = mock_serial.make_energy(scenario, 9000, rng, 80.0)
        assert not validation.validate_energy(e)[1], scenario
        ev = mock_serial.make_event(scenario, rng, 9000)
        if ev:
            assert not validation.validate_event(ev)[1], scenario
            assert ev["ts"] < 10 ** 12, "a replay log must not bake in wall-clock time"


def test_committed_serial_log_is_valid_and_replayable():
    path = os.path.join(CONSOLE, "demo", "serial_log.txt")
    kinds = {}
    with open(path, encoding="utf-8") as f:
        for raw in f:
            gap, _, line = raw.strip().partition(" ")
            assert gap.startswith("+"), raw
            kind, _, body = line.partition(" ")
            kinds[kind] = kinds.get(kind, 0) + 1
            if kind == "EVT":
                ev = json.loads(body)
                assert not validation.validate_event(ev)[1], ev["type"]
                assert ev["ts"] < 10 ** 12, "stale wall-clock ts in the fallback log"
            elif kind == "TRC":
                assert not validation.validate_trace(json.loads(body))[1]
            elif kind == "NRG":
                assert not validation.validate_energy(json.loads(body))[1]
    assert kinds.get("EVT") and kinds.get("TRC") and kinds.get("NRG")


def test_mock_rig_output_validates_for_every_control_combination(monkeypatch):
    posted = []

    class RigHTTP(FakeHTTP):
        def post(self, url, json=None, timeout=None):
            posted.append((url.rsplit(":8000", 1)[-1], json))
            return FakeResponse()

    http = RigHTTP()
    monkeypatch.setattr(mock_rig, "HTTP", http)
    for attack in mock_rig.DRAW:
        for mode in ("none", "ratelimit", "cookie", "gate"):
            http.control.update(mode=mode, attack_profile=attack)
            rig = mock_rig.Rig("http://127.0.0.1:8000", 60, 80.0, random.Random(0))
            for _ in range(30):
                rig.step()

    checks = {"/events": validation.validate_event, "/energy": validation.validate_energy,
              "/traces": validation.validate_trace}
    seen = {}
    for path, body in posted:
        errors = checks[path](body)[1]
        assert not errors, (path, body.get("type"), errors)
        if path == "/energy":
            assert body["source"] == "sim", "rig samples must be labelled simulated"
        if path == "/events":
            seen[body["type"]] = seen.get(body["type"], 0) + 1
    for t in ("gate_decision", "energy_alert", "replay_rejected", "handshake_rejected"):
        assert seen.get(t), f"rig never produced {t}"


def test_rig_draw_mirrors_the_hypothesis_it_illustrates():
    """Not evidence -- just a guard that the simulation says what the docs say."""
    d = mock_rig.DRAW
    assert d["loud"]["none"] > 4 * mock_rig.IDLE_MW                 # a flood drains the cell
    assert d["slow_drip"]["ratelimit"] == d["slow_drip"]["none"]    # the drip slips under a rate limit
    assert d["loud"]["gate"] < d["loud"]["cookie"] < d["loud"]["ratelimit"] < d["loud"]["none"]
