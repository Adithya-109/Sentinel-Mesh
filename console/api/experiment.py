"""v4: the five-row comparison table (brief section 6).

One run = one (attack profile, condition) pair: set the defence and the attack,
record energy for `duration_s`, then summarize the samples in that window.

What the console can and cannot measure, stated plainly:
  * energy_j_per_hour, projected_days -- computed here from the INA219 samples
    recorded during the run (projected_days from a FULL assumed cell, so the
    five rows compare like with like).
  * legit_connect_pct, legit_extra_delay_ms -- how a legitimate node fared.
    Only the firmware sees that, so these stay null until someone posts them to
    POST /experiment/result. The console never fills them in by itself.

Runs finish lazily: the next read after `started_ts + duration_s` finalizes
the row. No background thread, so nothing can be left half-running by a
crash -- a restarted console simply finalizes the run on its next read.
"""
import sqlite3
import statistics
from typing import Any, Optional

from . import config, db, energy

CONDITIONS = {
    #  condition     label                       defence      attack?
    "no_attack":  ("No attack (baseline)",      "none",      False),
    "undefended": ("Attack, no defence",        "none",      True),
    "ratelimit":  ("Attack + rate limit",       "ratelimit", True),
    "cookie":     ("Attack + cookie only",      "cookie",    True),
    "gate":       ("Attack + EnergyGate",       "gate",      True),
}
PROFILES = ["loud", "slow_drip"]

# the first slice of a run is the transition from the previous condition
SETTLE_FRACTION = 0.1


class ExperimentError(ValueError):
    pass


def _row_out(condition: str, r: Optional[sqlite3.Row]) -> dict[str, Any]:
    label = CONDITIONS[condition][0]
    if r is None:
        return {"condition": condition, "label": label, "energy_j_per_hour": None,
                "projected_days": None, "legit_connect_pct": None,
                "legit_extra_delay_ms": None, "status": "pending", "source": None}
    return {
        "condition": condition, "label": label,
        "energy_j_per_hour": r["energy_j_per_hour"], "projected_days": r["projected_days"],
        "legit_connect_pct": r["legit_connect_pct"], "legit_extra_delay_ms": r["legit_extra_delay_ms"],
        "status": r["status"], "source": r["source"],
        "started_ts": r["started_ts"], "ended_ts": r["ended_ts"],
        "duration_s": r["duration_s"], "samples": r["samples"],
    }


def running(conn: sqlite3.Connection) -> Optional[sqlite3.Row]:
    return conn.execute("SELECT * FROM experiment WHERE status = 'running' LIMIT 1").fetchone()


def finalize_due(conn: sqlite3.Connection, now: Optional[int] = None) -> Optional[dict]:
    """Finish the running row if its time is up. Returns the finished row, if any."""
    now = now or energy.now_ms()
    r = running(conn)
    if r is None or now < r["started_ts"] + r["duration_s"] * 1000:
        return None
    return _finish(conn, r, r["started_ts"] + r["duration_s"] * 1000)


def _finish(conn: sqlite3.Connection, r: sqlite3.Row, end: int) -> dict:
    start = r["started_ts"] + int(r["duration_s"] * 1000 * SETTLE_FRACTION)
    rows = energy.samples_between(conn, start, end)
    j_per_hour = days = source = None
    if rows:
        mean_mw = statistics.fmean(x["power_mw"] for x in rows)
        j_per_hour = round(mean_mw / 1000 * 3600, 1)
        days = energy.projected_days(mean_mw, 100.0)
        source = "simulated" if any(x["source"] == "sim" for x in rows) else "measured"
    conn.execute(
        """UPDATE experiment SET status = 'done', ended_ts = ?, energy_j_per_hour = ?,
           projected_days = ?, source = ?, samples = ? WHERE profile = ? AND condition = ?""",
        (end, j_per_hour, days, source, len(rows), r["profile"], r["condition"]),
    )
    conn.commit()
    # stop the attacker so it does not keep draining the cell between runs
    if CONDITIONS[r["condition"]][2]:
        db.set_attack(conn, "none")
    energy.add_marker(conn, f"experiment done: {CONDITIONS[r['condition']][0]} ({r['profile']})", end)
    return {"profile": r["profile"], "condition": r["condition"], "samples": len(rows)}


def run(conn: sqlite3.Connection, condition: str, profile: str,
        duration_s: Optional[int] = None) -> dict[str, Any]:
    if condition not in CONDITIONS:
        raise ExperimentError(f"condition must be one of {list(CONDITIONS)}")
    if profile not in PROFILES:
        raise ExperimentError(f"profile must be one of {PROFILES}")
    finalize_due(conn)
    if running(conn) is not None:
        raise ExperimentError("another run is in progress; wait for it or POST /experiment/stop")

    duration_s = int(duration_s or config.EXPERIMENT_DURATION_S)
    if not 5 <= duration_s <= 3600:
        raise ExperimentError("duration_s must be between 5 and 3600")

    label, defence, attacked = CONDITIONS[condition]
    db.set_mode(conn, defence)
    db.set_attack(conn, profile if attacked else "none")

    now = energy.now_ms()
    conn.execute(
        """INSERT INTO experiment (profile, condition, status, started_ts, duration_s)
           VALUES (?, ?, 'running', ?, ?)
           ON CONFLICT(profile, condition) DO UPDATE SET status = 'running', started_ts = excluded.started_ts,
             ended_ts = NULL, duration_s = excluded.duration_s, energy_j_per_hour = NULL,
             projected_days = NULL, legit_connect_pct = NULL, legit_extra_delay_ms = NULL,
             source = NULL, samples = NULL""",
        (profile, condition, now, duration_s),
    )
    conn.commit()
    energy.add_marker(conn, f"experiment: {label} ({profile})", now)
    return {"ok": True, "condition": condition, "profile": profile, "mode": defence,
            "attack_profile": profile if attacked else "none",
            "started_ts": now, "duration_s": duration_s, "ends_ts": now + duration_s * 1000}


def stop(conn: sqlite3.Connection) -> Optional[dict]:
    """End the running row now, keeping whatever was recorded so far."""
    r = running(conn)
    if r is None:
        return None
    return _finish(conn, r, energy.now_ms())


def record_result(conn: sqlite3.Connection, condition: str, profile: str,
                  legit_connect_pct: Optional[float], legit_extra_delay_ms: Optional[float]) -> dict:
    """The firmware-measured legit-client numbers for a finished row."""
    if condition not in CONDITIONS or profile not in PROFILES:
        raise ExperimentError("unknown condition or profile")
    cur = conn.execute(
        """UPDATE experiment SET legit_connect_pct = ?, legit_extra_delay_ms = ?
           WHERE profile = ? AND condition = ?""",
        (legit_connect_pct, legit_extra_delay_ms, profile, condition),
    )
    conn.commit()
    if cur.rowcount == 0:
        raise ExperimentError("no run recorded for that condition/profile yet")
    return table(conn, profile)


def reset(conn: sqlite3.Connection) -> None:
    conn.execute("DELETE FROM experiment")
    conn.commit()


def table(conn: sqlite3.Connection, profile: Optional[str] = None) -> dict[str, Any]:
    """The Experiment the frontend renders."""
    finalize_due(conn)
    if profile is None:
        last = conn.execute(
            "SELECT profile FROM experiment ORDER BY COALESCE(started_ts, 0) DESC LIMIT 1"
        ).fetchone()
        profile = last["profile"] if last else PROFILES[0]
    if profile not in PROFILES:
        raise ExperimentError(f"profile must be one of {PROFILES}")
    stored = {r["condition"]: r for r in conn.execute(
        "SELECT * FROM experiment WHERE profile = ?", (profile,))}
    rows = [_row_out(c, stored.get(c)) for c in CONDITIONS]

    notes = []
    if any(r["source"] == "simulated" for r in rows):
        notes.append("SIMULATED: some rows were recorded from tools/mock_rig.py, not the INA219 rig.")
    if any(r["status"] == "done" and r["legit_connect_pct"] is None for r in rows):
        notes.append("Legit-client columns stay empty until the firmware's numbers are posted to "
                     "POST /experiment/result -- the console cannot observe them.")
    notes.append(f"Projected days assume a {config.BATTERY_WH:g} Wh cell (SENTINEL_BATTERY_WH).")
    r = running(conn)
    return {
        "profiles": PROFILES,
        "profile": profile,
        "rows": rows,
        "running": None if r is None else {
            "condition": r["condition"], "profile": r["profile"],
            "ends_ts": r["started_ts"] + r["duration_s"] * 1000},
        "note": " ".join(notes),
    }
