"""v4: GET /status -- the frontend's top bar.

Every field is derived from something the console actually observed (events,
trace rows, energy samples) or was actually told (the demo controls). Where
there is no data yet, the field is null -- the UI shows a dash, it does not
invent a plausible number. `link` has an extra `offline` state for the same
reason: with no boards connected, "secure" would be a lie.

Link state, first match wins (same rules the timeline would lead a human to):
  tamper    a tamper-layer event in the last 60 s
  attack    an attack-shaped field event in the last 30 s (see ATTACK_TYPES)
  degraded  a link_degraded event in the last 30 s
  offline   nothing heard from field-1 or the gateway for OFFLINE_AFTER_MS
  secure    otherwise
"""
import json
import sqlite3
from typing import Any, Optional

from . import config, db, energy, experiment

TAMPER_WINDOW_MS = 60_000
RECENT_WINDOW_MS = 30_000

# field events that mean "someone is attacking the link right now"
ATTACK_TYPES = {"replay_rejected", "handshake_rejected", "attack_detected", "budget_exhausted"}

NODES = ["field-1", "gateway"]


def _recent(conn: sqlite3.Connection, since: int) -> list[dict]:
    return db.get_events(conn, since=since - 1, limit=10_000)


def _is_attack(e: dict) -> bool:
    if e["layer"] != "field":
        return False
    if e["type"] in ATTACK_TYPES:
        return True
    if e["type"] == "energy_alert" and e["severity"] in ("medium", "high", "critical"):
        return True
    return e["type"] == "gate_decision" and e["details"].get("action") == "drop"


def link_state(conn: sqlite3.Connection, now: int, seen: dict) -> str:
    recent = _recent(conn, now - TAMPER_WINDOW_MS)
    if any(e["layer"] == "tamper" for e in recent):
        return "tamper"
    last30 = [e for e in recent if e["ts"] >= now - RECENT_WINDOW_MS]
    if any(_is_attack(e) for e in last30):
        return "attack"
    if any(e["type"] == "link_degraded" for e in last30):
        return "degraded"
    heard = [seen[n]["last_ts"] for n in NODES if n in seen]
    if not heard or now - max(heard) > config.OFFLINE_AFTER_MS:
        return "offline"
    return "secure"


def _crypto_level(conn: sqlite3.Connection) -> Optional[int]:
    r = conn.execute(
        "SELECT details FROM events WHERE type = 'rekey' ORDER BY ts DESC LIMIT 1").fetchone()
    if r is None:
        return None
    return json.loads(r["details"]).get("level")


def _budget(conn: sqlite3.Connection) -> tuple[Optional[float], Optional[float]]:
    """Latest bucket state the gateway reported (gate_decision details), or 0
    after a budget_exhausted that is newer than the last decision."""
    r = conn.execute(
        """SELECT type, details FROM events WHERE type IN ('gate_decision', 'budget_exhausted')
           ORDER BY ts DESC LIMIT 20""").fetchall()
    budget = budget_max = None
    for row in r:
        d = json.loads(row["details"])
        if budget_max is None and d.get("budget_max_j") is not None:
            budget_max = d["budget_max_j"]
        if budget is None:
            if row["type"] == "budget_exhausted":
                budget = 0.0
            elif d.get("budget_j") is not None:
                budget = d["budget_j"]
    return budget, budget_max


def _node_state(node: str, link: str, now: int, seen: dict, recent: list[dict]) -> str:
    if node not in seen or now - seen[node]["last_ts"] > config.OFFLINE_AFTER_MS:
        return "offline"
    if node == "field-1":
        if any(e["layer"] == "tamper" and e.get("node") in (None, "field-1") for e in recent):
            return "tamper"
        if any(e["type"] == "link_degraded" for e in recent if e["ts"] >= now - RECENT_WINDOW_MS):
            return "degraded"
    return "attack" if link == "attack" else "secure"


def build(conn: sqlite3.Connection, now: Optional[int] = None) -> dict[str, Any]:
    now = now or energy.now_ms()
    experiment.finalize_due(conn, now)
    seen = db.get_nodes_seen(conn)
    control = db.get_control(conn)
    recent = _recent(conn, now - TAMPER_WINDOW_MS)

    link = link_state(conn, now, seen)
    last = energy.latest(conn)
    battery = None if last is None else last["battery_pct"]
    power = energy.current_power_mw(conn, now)
    base, base_source = energy.baseline_mw(conn, now)
    budget, budget_max = _budget(conn)

    nodes = []
    for n in NODES + (["attacker"] if "attacker" in seen else []):
        s = seen.get(n)
        nodes.append({
            "id": n,
            "state": _node_state(n, link, now, seen, recent),
            "rssi": None if s is None else s["rssi"],
            "battery_pct": None if s is None else s["battery_pct"],
            "last_seen_ms": None if s is None else max(0, now - s["last_ts"]),
        })

    return {
        "ts": now,
        "link": link,
        "crypto_level": _crypto_level(conn),
        "battery_pct": battery,
        "power_mw": None if power is None else round(power, 1),
        "baseline_mw": None if base is None else round(base, 1),
        "baseline_source": base_source,
        "projected_days": energy.projected_days(power, battery),
        "projected_days_idle": energy.projected_days(base, battery),
        "projection_assumes_wh": config.BATTERY_WH,
        "mode": control["mode"],
        "attack_profile": control["attack_profile"],
        "budget_j": budget,
        "budget_max_j": budget_max,
        "simulated": last is not None and last["source"] == "sim",
        "nodes": nodes,
    }
