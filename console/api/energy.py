"""v4 energy telemetry: INA219 samples, chart markers, and the derived numbers.

Samples arrive as `NRG <json>` serial lines (contracts/energy.schema.json) via
the bridge's POST /energy. They are continuous telemetry -- deliberately not
Events -- and back the battery-over-time chart and the experiment table.

Everything derived here is labelled for what it is:
  * `power_mw` now      -- measured (mean of the last few seconds of samples)
  * `baseline_mw`       -- measured if we have idle data, else configured, else null
  * `projected_days`    -- an ESTIMATE: measured draw against an ASSUMED cell
                           capacity (config.BATTERY_WH). The UI says so.
"""
import sqlite3
import statistics
import time
from typing import Any, Optional

from . import config

# Anything below this is a device uptime (millis()), not epoch ms: 1e12 ms is
# September 2001. ESP32s have no wall clock, so every board-originated ts is
# uptime; the console swaps it for arrival time. See CONTRACT.md "Timestamps".
EPOCH_MS_FLOOR = 10 ** 12

NOW_WINDOW_MS = 5_000           # "current draw" = mean over this many ms
BASELINE_LOOKBACK_MS = 6 * 3600 * 1000


def now_ms() -> int:
    return int(time.time() * 1000)


def normalize_ts(ts: Optional[int], arrived: Optional[int] = None) -> tuple[int, Optional[int]]:
    """Return (epoch_ms_to_store, device_ts_or_None)."""
    arrived = arrived or now_ms()
    if ts is None:
        return arrived, None
    if ts < EPOCH_MS_FLOOR:
        return arrived, ts
    return ts, None


def insert_sample(conn: sqlite3.Connection, sample: dict[str, Any]) -> dict[str, Any]:
    ts, device_ts = normalize_ts(sample.get("ts"))
    row = {
        "ts": ts,
        "node": sample.get("node") or "field-1",
        "power_mw": float(sample["power_mw"]),
        "volts": float(sample["volts"]),
        "amps": float(sample["amps"]),
        "battery_pct": None if sample.get("battery_pct") is None else float(sample["battery_pct"]),
        "source": sample.get("source") or "ina219",
        "device_ts": device_ts,
    }
    conn.execute(
        """INSERT INTO energy_samples (ts, node, power_mw, volts, amps, battery_pct, source, device_ts)
           VALUES (:ts, :node, :power_mw, :volts, :amps, :battery_pct, :source, :device_ts)""",
        row,
    )
    conn.commit()
    return row


def add_marker(conn: sqlite3.Connection, label: str, ts: Optional[int] = None) -> dict:
    ts = ts or now_ms()
    conn.execute("INSERT INTO energy_markers (ts, label) VALUES (?, ?)", (ts, label))
    conn.commit()
    return {"ts": ts, "label": label}


def _sample_out(r: sqlite3.Row) -> dict[str, Any]:
    return {"ts": r["ts"], "power_mw": r["power_mw"], "battery_pct": r["battery_pct"],
            "volts": r["volts"], "amps": r["amps"], "source": r["source"]}


def series(conn: sqlite3.Connection, since: Optional[int] = None, limit: int = 3600) -> dict[str, Any]:
    """The EnergySeries the frontend polls. Newest `limit` samples, oldest-first."""
    since = since or 0
    rows = conn.execute(
        """SELECT * FROM (SELECT * FROM energy_samples WHERE ts > ? ORDER BY ts DESC LIMIT ?)
           ORDER BY ts""", (since, limit)
    ).fetchall()
    markers = conn.execute(
        "SELECT ts, label FROM energy_markers WHERE ts > ? ORDER BY ts", (since,)
    ).fetchall()
    samples = [_sample_out(r) for r in rows]
    return {
        "samples": samples,
        "markers": [{"ts": m["ts"], "label": m["label"]} for m in markers],
        "simulated": any(s["source"] == "sim" for s in samples),
    }


def samples_between(conn: sqlite3.Connection, start: int, end: int) -> list[sqlite3.Row]:
    return conn.execute(
        "SELECT * FROM energy_samples WHERE ts >= ? AND ts <= ? ORDER BY ts", (start, end)
    ).fetchall()


def latest(conn: sqlite3.Connection) -> Optional[sqlite3.Row]:
    return conn.execute("SELECT * FROM energy_samples ORDER BY ts DESC LIMIT 1").fetchone()


def current_power_mw(conn: sqlite3.Connection, now: Optional[int] = None) -> Optional[float]:
    """Mean draw over the last few seconds; falls back to the latest sample."""
    now = now or now_ms()
    rows = conn.execute("SELECT power_mw FROM energy_samples WHERE ts >= ?",
                        (now - NOW_WINDOW_MS,)).fetchall()
    if rows:
        return statistics.fmean(r["power_mw"] for r in rows)
    last = latest(conn)
    return None if last is None else last["power_mw"]


def baseline_mw(conn: sqlite3.Connection, now: Optional[int] = None) -> tuple[Optional[float], str]:
    """Idle draw and where it came from, in order of trustworthiness:

    1. the most recent finished `no_attack` experiment run -- a deliberate,
       controlled idle measurement;
    2. config.BASELINE_MW, if the team set it from the rig;
    3. the 10th percentile of the last 6 h of samples -- the idle floor, which
       an attack raises but does not usually remove entirely;
    4. nothing: return None rather than make a number up.
    """
    row = conn.execute(
        """SELECT energy_j_per_hour FROM experiment
           WHERE condition = 'no_attack' AND status = 'done' AND energy_j_per_hour IS NOT NULL
           ORDER BY ended_ts DESC LIMIT 1"""
    ).fetchone()
    if row:
        return row["energy_j_per_hour"] / 3600 * 1000, "no_attack experiment run"
    if config.BASELINE_MW is not None:
        return config.BASELINE_MW, "configured (SENTINEL_BASELINE_MW)"
    now = now or now_ms()
    rows = conn.execute("SELECT power_mw FROM energy_samples WHERE ts >= ? ORDER BY power_mw",
                        (now - BASELINE_LOOKBACK_MS,)).fetchall()
    if len(rows) >= 10:
        return rows[len(rows) // 10]["power_mw"], "10th percentile of recent samples"
    return None, "no data yet"


def projected_days(power_mw: Optional[float], battery_pct: Optional[float] = 100.0) -> Optional[float]:
    """Days until flat at a constant `power_mw`, from `battery_pct` of an
    assumed config.BATTERY_WH cell. An estimate; None if it cannot be computed."""
    if power_mw is None or power_mw <= 0:
        return None
    pct = 100.0 if battery_pct is None else battery_pct
    joules = config.BATTERY_WH * 3600 * pct / 100.0
    return round(joules / (power_mw / 1000.0) / 86400, 2)
