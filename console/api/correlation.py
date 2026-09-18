"""Incident correlation -- RULES ONLY, no machine learning.

This is a deliberate design choice and part of the pitch: the ML lives in the
detectors (MailGuard, FileGuard, FieldGuard), and the thing that joins their
alerts into one story stays simple enough to explain in a sentence. If a judge
asks "is the correlation ML?", the answer is no, and this file is the evidence.

THE RULES, in the order they are applied
----------------------------------------
R1. Informational events and per-decision telemetry never form incidents.
    Severity `info` means "we looked and it was fine" (email_clean, file_clean)
    or "routine housekeeping" (rekey). `gate_decision` (v4) is telemetry too:
    EnergyGate emits one per admission decision, so during a drain attack it
    arrives every few seconds at low/medium severity. Letting it correlate
    would (a) count as a `field` layer hit, so an email + a file + routine gate
    decisions would be misreported as a coordinated attack, and (b) keep the
    sliding window open indefinitely, swallowing unrelated alerts into one
    incident. All of these are stored and shown on the timeline and the gate
    feed; they never start or join an incident. `energy_alert` and
    `budget_exhausted` DO correlate -- they are discrete alerts, and a battery
    drain is a genuine attack on the field network.

R2. Events are grouped by a sliding time window (default 10 minutes).
    Walking the alerts oldest-first, an alert joins the current incident if it
    lands within the window of the PREVIOUS alert in that incident; otherwise
    it starts a new one. The window slides with each alert, so a slow-burning
    chain of alerts 9 minutes apart stays one incident.

R3. An incident's severity starts as the worst severity among its alerts.

R4. Two or more distinct layers in one incident escalate severity by one step.
    One layer firing is a detection. Two layers firing minutes apart is a
    pattern, and it should outrank either alert on its own.

R5. mail + file + field together = "coordinated attack", severity critical.
    That is the Ukraine-2015 shape the whole project is built around -- inbox,
    then endpoint, then the field network -- and it is the one case we are
    willing to name outright.

Incidents are derived, never stored: `GET /incidents` recomputes from the
events table every time, so an event that arrives late simply lands in the
right incident instead of leaving a stale row behind.
"""
from typing import Any, Iterable

from . import attack, config

SEVERITY_ORDER = ["info", "low", "medium", "high", "critical"]
SEVERITY_RANK = {s: i for i, s in enumerate(SEVERITY_ORDER)}

COORDINATED_LAYERS = {"mail", "file", "field"}

# Event types that are telemetry, not alerts, regardless of severity (R1).
TELEMETRY_TYPES = {"gate_decision"}


def severity_rank(severity: str) -> int:
    return SEVERITY_RANK.get(severity, 0)


def escalate(severity: str, steps: int = 1) -> str:
    return SEVERITY_ORDER[min(severity_rank(severity) + steps, len(SEVERITY_ORDER) - 1)]


def _title(layers_in_order: list[str], worst_event: dict, coordinated: bool) -> str:
    if coordinated:
        return "Coordinated attack: inbox → endpoint → field network"
    if len(set(layers_in_order)) >= 2:
        names = " + ".join(dict.fromkeys(layers_in_order))
        return f"Multi-layer activity: {names}"
    return worst_event["summary"]


def _summarize(members: list[dict], window_ms: int) -> dict[str, Any]:
    layers_in_order = [e["layer"] for e in members]
    layer_set = set(layers_in_order)

    worst = max(members, key=lambda e: (severity_rank(e["severity"]), e["ts"]))
    severity = worst["severity"]                                    # R3

    coordinated = COORDINATED_LAYERS.issubset(layer_set)            # R5
    escalated_by = []
    if len(layer_set) >= 2:                                         # R4
        severity = escalate(severity)
        escalated_by.append(f"{len(layer_set)} layers fired in one window")
    if coordinated:
        severity = "critical"
        escalated_by.append("mail + file + field = coordinated attack")

    techniques = list(dict.fromkeys(e["technique"] for e in members if e.get("technique")))

    return {
        "id": members[0]["id"],          # stable: the first alert's id names the incident
        "started_ts": members[0]["ts"],
        "last_ts": members[-1]["ts"],
        "window_ms": window_ms,
        "severity": severity,
        "base_severity": worst["severity"],
        "escalated_by": escalated_by,
        "coordinated": coordinated,
        "title": _title(layers_in_order, worst, coordinated),
        "layers": sorted(layer_set, key=lambda l: attack.CHAIN.get(l, (9, l))[0]),
        "chain": attack.chain_state(layer_set),
        "techniques": techniques,
        "technique_names": [attack.technique_name(t) for t in techniques],
        "event_count": len(members),
        "event_ids": [e["id"] for e in members],
        "events": members,
    }


def build_incidents(events: Iterable[dict], window_ms: int = None) -> list[dict]:
    """Group events into incidents. Newest incident first."""
    window_ms = config.INCIDENT_WINDOW_MS if window_ms is None else window_ms

    alerts = [e for e in events                                                   # R1
              if severity_rank(e.get("severity", "info")) > 0
              and e.get("type") not in TELEMETRY_TYPES]
    alerts.sort(key=lambda e: e["ts"])

    groups: list[list[dict]] = []
    for e in alerts:                                                              # R2
        if groups and e["ts"] - groups[-1][-1]["ts"] <= window_ms:
            groups[-1].append(e)
        else:
            groups.append([e])

    incidents = [_summarize(g, window_ms) for g in groups]
    incidents.sort(key=lambda i: i["started_ts"], reverse=True)
    return incidents
