"""API + contract-validation tests, against a throwaway database."""
import os
import sys
import tempfile
import uuid

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

_tmp = tempfile.mkdtemp(prefix="sentinelmesh-test-")
os.environ["SENTINEL_DB"] = os.path.join(_tmp, "test.db")
os.environ["SENTINEL_TRACE_DIR"] = os.path.join(_tmp, "traces")

from fastapi.testclient import TestClient  # noqa: E402

from api.main import app  # noqa: E402

client = TestClient(app)


def event(**over):
    e = {
        "id": str(uuid.uuid4()), "ts": 1_700_000_000_000, "layer": "mail",
        "type": "email_malicious", "severity": "high", "score": 0.97, "node": None,
        "technique": "T1566.001", "summary": "Malicious email detected",
        "reasons": ["'urgent' -> malicious signal (+0.7)"], "details": {},
    }
    e.update(over)
    return e


def trace(**over):
    t = {
        "ts": 5000, "node": "gateway", "label": "normal", "window_ms": 5000,
        "hs_per_s": 0.1, "hs_fail": 0, "replay_rej": 0, "auth_fail": 0, "stale": 0,
        "frag_timeout": 0, "rssi_mean": -55.2, "rssi_var": 3.1, "loss_pct": 0.0, "jitter_ms": 2.4,
    }
    t.update(over)
    return t


@pytest.fixture(autouse=True)
def clean():
    client.delete("/events")
    client.post("/recording/stop")
    yield


# -- POST /events ----------------------------------------------------------

def test_post_event_returns_201():
    assert client.post("/events", json=event()).status_code == 201


def test_posted_event_comes_back_intact():
    e = event()
    client.post("/events", json=e)
    got = client.get("/events").json()["events"][0]
    for k in ("id", "ts", "layer", "type", "severity", "score", "technique", "summary", "reasons"):
        assert got[k] == e[k]


def test_reposting_the_same_id_is_idempotent():
    e = event()
    assert client.post("/events", json=e).json()["stored"] is True
    second = client.post("/events", json=e)
    assert second.status_code == 201
    assert second.json()["duplicate"] is True
    assert len(client.get("/events").json()["events"]) == 1


def test_optional_fields_may_be_omitted():
    minimal = {"id": str(uuid.uuid4()), "ts": 1_700_000_000_000, "layer": "field",
               "type": "link_degraded", "severity": "low", "summary": "link degraded"}
    assert client.post("/events", json=minimal).status_code == 201
    got = client.get("/events").json()["events"][0]
    assert got["reasons"] == [] and got["details"] == {} and got["score"] is None


# -- contract validation ---------------------------------------------------

def test_unknown_severity_is_rejected():
    r = client.post("/events", json=event(severity="catastrophic"))
    assert r.status_code == 422
    assert "severity" in r.json()["errors"][0]


def test_type_must_match_its_layer():
    """A mail event carrying a field type is exactly the drift we want caught."""
    r = client.post("/events", json=event(layer="mail", type="replay_rejected"))
    assert r.status_code == 422


def test_attack_detected_must_carry_details_kind():
    bad = event(layer="field", type="attack_detected", severity="high", technique="T0830", details={})
    assert client.post("/events", json=bad).status_code == 422
    good = {**bad, "id": str(uuid.uuid4()), "details": {"kind": "impersonation"}}
    assert client.post("/events", json=good).status_code == 201


def test_rekey_must_carry_level_and_reason():
    bad = event(layer="field", type="rekey", severity="info", technique=None,
                details={"level": 768})
    assert client.post("/events", json=bad).status_code == 422
    good = {**bad, "id": str(uuid.uuid4()), "details": {"level": 768, "reason": "battery"}}
    assert client.post("/events", json=good).status_code == 201


def test_score_outside_zero_to_one_is_rejected():
    assert client.post("/events", json=event(score=1.4)).status_code == 422


def test_unknown_field_is_rejected():
    assert client.post("/events", json=event(oops="typo")).status_code == 422


def test_missing_summary_is_rejected():
    e = event()
    del e["summary"]
    assert client.post("/events", json=e).status_code == 422


# -- GET /events -----------------------------------------------------------

def test_since_is_exclusive_and_filters():
    client.post("/events", json=event(id="a", ts=1000))
    client.post("/events", json=event(id="b", ts=2000))
    got = client.get("/events", params={"since": 1000}).json()["events"]
    assert [e["id"] for e in got] == ["b"]


def test_events_are_returned_oldest_first():
    client.post("/events", json=event(id="late", ts=5000))
    client.post("/events", json=event(id="early", ts=1000))
    assert [e["id"] for e in client.get("/events").json()["events"]] == ["early", "late"]


def test_events_carry_a_readable_technique_name():
    client.post("/events", json=event())
    assert "Spearphishing" in client.get("/events").json()["events"][0]["technique_name"]


# -- GET /incidents --------------------------------------------------------

def test_incidents_are_derived_from_stored_events():
    client.post("/events", json=event(id="m", ts=1_700_000_000_000))
    client.post("/events", json=event(id="f", ts=1_700_000_060_000, layer="file",
                                      type="file_malicious", technique="T1204.002"))
    incidents = client.get("/incidents").json()["incidents"]
    assert len(incidents) == 1
    assert incidents[0]["severity"] == "critical"   # two layers escalate high -> critical


def test_incident_window_is_overridable_by_query():
    client.post("/events", json=event(id="m", ts=1_700_000_000_000))
    client.post("/events", json=event(id="f", ts=1_700_000_300_000, layer="file",
                                      type="file_malicious"))
    assert client.get("/incidents", params={"window_ms": 60_000}).json()["count"] == 2
    assert client.get("/incidents", params={"window_ms": 600_000}).json()["count"] == 1


# -- traces ----------------------------------------------------------------

def test_trace_is_dropped_when_not_recording():
    assert client.post("/traces", json=trace()).json()["stored"] is False


def test_trace_is_written_with_the_operator_label():
    client.post("/recording/start", json={"session": "t1", "label": "replay"})
    body = client.post("/traces", json=trace(label="normal")).json()
    assert body["stored"] is True

    path = os.path.join(os.environ["SENTINEL_TRACE_DIR"], "t1.jsonl")
    with open(path, encoding="utf-8") as f:
        row = __import__("json").loads(f.readline())
    assert row["label"] == "replay"      # console's label wins
    assert row["gw_label"] == "normal"   # gateway's kept for debugging
    assert row["session"] == "t1"


def test_gateway_label_mismatch_is_counted():
    """Guards the operator against recording one attack under another's name."""
    client.post("/recording/start", json={"session": "t3", "label": "flood"})
    assert client.post("/traces", json=trace(label="flood")).json()["gw_label_mismatch"] is False
    assert client.post("/traces", json=trace(label="normal")).json()["gw_label_mismatch"] is True
    rec = client.get("/recording").json()
    assert rec["rows"] == 2 and rec["mismatched"] == 1


def test_malformed_trace_is_rejected_not_written():
    client.post("/recording/start", json={"session": "t2", "label": "normal"})
    bad = trace()
    del bad["rssi_mean"]
    assert client.post("/traces", json=bad).status_code == 422
    assert client.get("/recording").json()["dropped"] == 1


def test_label_version_bumps_so_the_bridge_notices():
    before = client.get("/recording").json()["label_version"]
    client.post("/recording/label", json={"label": "flood"})
    after = client.get("/recording").json()
    assert after["label_version"] > before
    assert after["label"] == "flood"


def test_unknown_label_is_rejected():
    assert client.post("/recording/label", json={"label": "nonsense"}).status_code == 400


def test_session_name_cannot_escape_the_trace_directory():
    client.post("/recording/start", json={"session": "../../evil", "label": "normal"})
    assert "/" not in client.get("/recording").json()["session"]


def test_health_reports_event_count():
    client.post("/events", json=event())
    assert client.get("/health").json()["events"] == 1
