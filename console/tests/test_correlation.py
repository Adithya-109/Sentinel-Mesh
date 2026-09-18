"""The correlation rules are the 'threat analysis' claim in the pitch, so they
get tests. Each test names the rule from correlation.py's docstring it pins."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from api.correlation import build_incidents, escalate, severity_rank  # noqa: E402

MIN = 60 * 1000
BASE = 1_700_000_000_000


def ev(offset_min, layer, type_, severity, **kw):
    return {
        "id": kw.pop("id", f"{layer}-{type_}-{offset_min}"),
        "ts": BASE + int(offset_min * MIN),
        "layer": layer, "type": type_, "severity": severity,
        "score": kw.pop("score", None), "node": kw.pop("node", None),
        "technique": kw.pop("technique", None),
        "summary": kw.pop("summary", f"{layer} {type_}"),
        "reasons": kw.pop("reasons", []), "details": kw.pop("details", {}),
    }


# -- R1: informational events never form incidents -------------------------

def test_info_events_do_not_form_incidents():
    events = [ev(0, "mail", "email_clean", "info"), ev(1, "file", "file_clean", "info")]
    assert build_incidents(events) == []


def test_info_events_are_excluded_from_an_incident_they_neighbour():
    events = [ev(0, "mail", "email_clean", "info"), ev(1, "mail", "email_malicious", "high")]
    incidents = build_incidents(events)
    assert len(incidents) == 1
    assert incidents[0]["event_count"] == 1
    assert incidents[0]["events"][0]["type"] == "email_malicious"


# -- R2: sliding window ----------------------------------------------------

def test_alerts_inside_the_window_are_one_incident():
    events = [ev(0, "mail", "email_malicious", "high"), ev(9, "file", "file_malicious", "high")]
    assert len(build_incidents(events)) == 1


def test_alerts_outside_the_window_are_separate_incidents():
    events = [ev(0, "mail", "email_malicious", "high"), ev(11, "file", "file_malicious", "high")]
    assert len(build_incidents(events)) == 2


def test_window_slides_so_a_chain_of_close_alerts_stays_one_incident():
    """Nine minutes apart each, 27 minutes end to end, still one incident."""
    events = [
        ev(0, "mail", "email_malicious", "high"),
        ev(9, "file", "file_malicious", "high"),
        ev(18, "field", "replay_rejected", "medium"),
        ev(27, "tamper", "case_opened", "critical"),
    ]
    incidents = build_incidents(events)
    assert len(incidents) == 1
    assert incidents[0]["event_count"] == 4


def test_out_of_order_arrival_still_groups_correctly():
    events = [ev(9, "file", "file_malicious", "high"), ev(0, "mail", "email_malicious", "high")]
    incidents = build_incidents(events)
    assert len(incidents) == 1
    assert [e["layer"] for e in incidents[0]["events"]] == ["mail", "file"]


# -- R3/R4: severity -------------------------------------------------------

def test_single_layer_keeps_its_worst_severity():
    events = [ev(0, "field", "replay_rejected", "medium"), ev(1, "field", "link_degraded", "low")]
    inc = build_incidents(events)[0]
    assert inc["base_severity"] == "medium"
    assert inc["severity"] == "medium"
    assert inc["escalated_by"] == []


def test_two_layers_escalate_one_step():
    events = [ev(0, "mail", "email_malicious", "high"), ev(1, "field", "replay_rejected", "medium")]
    inc = build_incidents(events)[0]
    assert inc["base_severity"] == "high"
    assert inc["severity"] == "critical"
    assert "2 layers" in inc["escalated_by"][0]


def test_escalation_saturates_at_critical():
    events = [ev(0, "tamper", "case_opened", "critical"), ev(1, "field", "replay_rejected", "medium")]
    assert build_incidents(events)[0]["severity"] == "critical"
    assert escalate("critical") == "critical"


# -- R5: the coordinated attack -------------------------------------------

def test_mail_file_field_is_a_coordinated_attack():
    events = [
        ev(0, "mail", "email_malicious", "high", technique="T1566.001"),
        ev(2, "file", "file_malicious", "high", technique="T1204.002"),
        ev(5, "field", "replay_rejected", "medium", technique="T1692.002"),
    ]
    inc = build_incidents(events)[0]
    assert inc["coordinated"] is True
    assert inc["severity"] == "critical"
    assert "Coordinated attack" in inc["title"]
    assert inc["techniques"] == ["T1566.001", "T1204.002", "T1692.002"]


def test_mail_and_file_alone_is_not_coordinated():
    events = [ev(0, "mail", "email_malicious", "high"), ev(2, "file", "file_malicious", "high")]
    inc = build_incidents(events)[0]
    assert inc["coordinated"] is False
    assert "Multi-layer" in inc["title"]


# -- chain strip and ordering ---------------------------------------------

def test_chain_lights_up_the_layers_that_fired():
    events = [ev(0, "mail", "email_malicious", "high"), ev(2, "tamper", "case_opened", "critical")]
    chain = build_incidents(events)[0]["chain"]
    assert [c["lit"] for c in chain] == [True, False, False, True]
    assert [c["step"] for c in chain] == ["Inbox", "Endpoint", "Field network", "Physical"]


def test_incidents_are_newest_first_and_ids_are_stable():
    events = [ev(0, "mail", "email_malicious", "high", id="first"),
              ev(30, "file", "file_malicious", "high", id="second")]
    incidents = build_incidents(events)
    assert [i["id"] for i in incidents] == ["second", "first"]
    assert [i["id"] for i in build_incidents(events)] == ["second", "first"]


def test_severity_rank_orders_the_contract_severities():
    assert severity_rank("info") < severity_rank("low") < severity_rank("medium") \
        < severity_rank("high") < severity_rank("critical")


def test_custom_window_is_honoured():
    events = [ev(0, "mail", "email_malicious", "high"), ev(3, "file", "file_malicious", "high")]
    assert len(build_incidents(events, window_ms=2 * MIN)) == 2
    assert len(build_incidents(events, window_ms=5 * MIN)) == 1


# -- R1 (v4): gate_decision is telemetry ------------------------------------

def test_gate_decisions_never_form_an_incident():
    events = [ev(k, "field", "gate_decision", "medium", details={"action": "drop"}) for k in range(5)]
    assert build_incidents(events) == []


def test_gate_decisions_do_not_fake_a_coordinated_attack():
    """mail + file + routine gate decisions is NOT the Ukraine-2015 shape."""
    events = [ev(0, "mail", "email_malicious", "high"), ev(1, "file", "file_malicious", "high")]
    events += [ev(2 + k, "field", "gate_decision", "low", details={"action": "challenge"}) for k in range(3)]
    inc = build_incidents(events)[0]
    assert inc["coordinated"] is False
    assert inc["layers"] == ["mail", "file"]


def test_a_stream_of_gate_decisions_does_not_hold_the_window_open():
    """A drain attack emits a decision every couple of minutes for as long as
    it runs; that must not merge an unrelated tamper 40 minutes later."""
    events = [ev(0, "mail", "email_malicious", "high")]
    events += [ev(3 + 2 * k, "field", "gate_decision", "medium", details={"action": "drop"})
               for k in range(15)]
    events.append(ev(40, "tamper", "case_opened", "critical"))
    assert len(build_incidents(events)) == 2


def test_energy_alerts_still_correlate():
    """A battery drain is a real field-network attack, unlike the gate feed."""
    events = [ev(0, "mail", "email_malicious", "high"), ev(1, "file", "file_malicious", "high"),
              ev(2, "field", "energy_alert", "high", details={"draw_mw": 512, "baseline_mw": 84})]
    assert build_incidents(events)[0]["coordinated"] is True
