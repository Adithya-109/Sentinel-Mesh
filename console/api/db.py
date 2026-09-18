"""SQLite storage for events, trace rows and the recording session.

One row per Event, with `reasons` and `details` stored as JSON text. Incidents
are NOT stored -- they are derived from the events table on every read (see
correlation.py), so a late-arriving event can never leave a stale incident
behind.
"""
import json
import os
import sqlite3
import threading
import time
from typing import Any, Optional

from . import config


class _LockingConnection(sqlite3.Connection):
    """sqlite3.Connection with one process-wide lock around every statement.

    The console shares a single connection across every request, and FastAPI
    runs plain `def` routes in a thread-pool -- `check_same_thread=False`
    only disables Python's own thread-affinity guard, it does not make the
    underlying SQLite connection safe for two threads to touch at once.
    Reproduced live: with the v4 mock rig posting energy/gate_decision data
    every ~1s while the frontend polls /api/status, /api/energy and
    /api/incidents on the same cadence, two threads hit the shared
    connection at the same moment often enough to raise
    `sqlite3.InterfaceError: bad parameter or other API misuse` -- v3 never
    wrote to the database this often, so it never surfaced before v4.
    A single lock around every statement (not just around commits) is the
    standard fix for "one shared connection, many threads" and covers every
    caller automatically, since every module executes through this same
    connection object.
    """
    _lock = threading.Lock()

    def execute(self, *args, **kwargs):
        with self._lock:
            return super().execute(*args, **kwargs)

    def executemany(self, *args, **kwargs):
        with self._lock:
            return super().executemany(*args, **kwargs)

    def executescript(self, *args, **kwargs):
        with self._lock:
            return super().executescript(*args, **kwargs)

    def commit(self):
        with self._lock:
            return super().commit()

SCHEMA = """
CREATE TABLE IF NOT EXISTS events (
    id          TEXT PRIMARY KEY,
    ts          INTEGER NOT NULL,
    layer       TEXT    NOT NULL,
    type        TEXT    NOT NULL,
    severity    TEXT    NOT NULL,
    score       REAL,
    node        TEXT,
    technique   TEXT,
    summary     TEXT    NOT NULL,
    reasons     TEXT    NOT NULL,
    details     TEXT    NOT NULL,
    received_ts INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_events_ts ON events(ts);

-- single-row table holding the trace-recording state the serial bridge polls
CREATE TABLE IF NOT EXISTS recording (
    k             INTEGER PRIMARY KEY CHECK (k = 1),
    active        INTEGER NOT NULL DEFAULT 0,
    session       TEXT,
    label         TEXT    NOT NULL DEFAULT 'normal',
    label_version INTEGER NOT NULL DEFAULT 0,
    started_ts    INTEGER,
    rows          INTEGER NOT NULL DEFAULT 0,
    dropped       INTEGER NOT NULL DEFAULT 0
);
INSERT OR IGNORE INTO recording (k) VALUES (1);

-- v4: continuous INA219 samples (NRG lines). Telemetry, not events.
CREATE TABLE IF NOT EXISTS energy_samples (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    ts          INTEGER NOT NULL,
    node        TEXT    NOT NULL,
    power_mw    REAL    NOT NULL,
    volts       REAL    NOT NULL,
    amps        REAL    NOT NULL,
    battery_pct REAL,
    source      TEXT    NOT NULL,
    device_ts   INTEGER
);
CREATE INDEX IF NOT EXISTS idx_energy_ts ON energy_samples(ts);

-- chart annotations ("attack starts", "EnergyGate on"), added by the controls
CREATE TABLE IF NOT EXISTS energy_markers (
    id    INTEGER PRIMARY KEY AUTOINCREMENT,
    ts    INTEGER NOT NULL,
    label TEXT    NOT NULL
);

-- v4: demo controls the bridge relays to the boards (DEFENSE / MODE lines)
CREATE TABLE IF NOT EXISTS control (
    k              INTEGER PRIMARY KEY CHECK (k = 1),
    mode           TEXT    NOT NULL DEFAULT 'none',
    mode_version   INTEGER NOT NULL DEFAULT 0,
    attack_profile TEXT    NOT NULL DEFAULT 'none',
    attack_version INTEGER NOT NULL DEFAULT 0
);
INSERT OR IGNORE INTO control (k) VALUES (1);

-- last time each node was heard from, for GET /status's per-node state
CREATE TABLE IF NOT EXISTS node_seen (
    node        TEXT PRIMARY KEY,
    last_ts     INTEGER NOT NULL,
    rssi        REAL,
    battery_pct REAL
);

-- v4: the five-row comparison (brief section 6), one row per profile x condition
CREATE TABLE IF NOT EXISTS experiment (
    profile              TEXT    NOT NULL,
    condition            TEXT    NOT NULL,
    status               TEXT    NOT NULL,
    started_ts           INTEGER,
    ended_ts             INTEGER,
    duration_s           INTEGER,
    energy_j_per_hour    REAL,
    projected_days       REAL,
    legit_connect_pct    REAL,
    legit_extra_delay_ms REAL,
    source               TEXT,
    samples              INTEGER,
    PRIMARY KEY (profile, condition)
);
"""

# Columns added after the first demo DBs were created. SQLite has no
# "ADD COLUMN IF NOT EXISTS", and a stale console.db on the gateway laptop
# would otherwise crash at recording time.
MIGRATIONS = [
    ("recording", "mismatched", "INTEGER NOT NULL DEFAULT 0"),
]


def _migrate(conn: sqlite3.Connection) -> None:
    for table, column, decl in MIGRATIONS:
        existing = {r["name"] for r in conn.execute(f"PRAGMA table_info({table})")}
        if column not in existing:
            conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {decl}")
    conn.commit()


def connect(db_path: Optional[str] = None) -> sqlite3.Connection:
    path = db_path or config.DB_PATH
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    conn = sqlite3.connect(path, check_same_thread=False, factory=_LockingConnection)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.executescript(SCHEMA)
    _migrate(conn)
    return conn


def _row_to_event(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "id": row["id"],
        "ts": row["ts"],
        "layer": row["layer"],
        "type": row["type"],
        "severity": row["severity"],
        "score": row["score"],
        "node": row["node"],
        "technique": row["technique"],
        "summary": row["summary"],
        "reasons": json.loads(row["reasons"]),
        "details": json.loads(row["details"]),
    }


def insert_event(conn: sqlite3.Connection, event: dict[str, Any]) -> bool:
    """Store an event. Returns False if that id was already stored.

    Re-POSTing an id is idempotent rather than an error: the gateway may resend
    a line after a serial hiccup, and a duplicated alert on the timeline would
    be worse than a silently ignored one.
    """
    cur = conn.execute(
        """INSERT OR IGNORE INTO events
           (id, ts, layer, type, severity, score, node, technique, summary, reasons, details, received_ts)
           VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
        (
            event["id"], event["ts"], event["layer"], event["type"], event["severity"],
            event.get("score"), event.get("node"), event.get("technique"), event["summary"],
            json.dumps(event.get("reasons", [])), json.dumps(event.get("details", {})),
            int(time.time() * 1000),
        ),
    )
    conn.commit()
    return cur.rowcount > 0


def get_events(conn: sqlite3.Connection, since: Optional[int] = None, limit: int = 1000) -> list[dict]:
    """Events in timeline order (oldest first). `since` is exclusive.

    Without `since` this is the NEWEST `limit` events, still oldest-first. It
    used to be the oldest `limit`, which was harmless at v3 volumes but at v4's
    one-gate-decision-every-few-seconds would freeze the timeline and
    /incidents on stale history after a long rehearsal. With `since` it pages
    forward oldest-first, which is what a poller wants.
    """
    if since is None:
        rows = conn.execute(
            """SELECT * FROM (SELECT * FROM events ORDER BY ts DESC, received_ts DESC LIMIT ?)
               ORDER BY ts, received_ts""", (limit,)
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM events WHERE ts > ? ORDER BY ts, received_ts LIMIT ?", (since, limit)
        ).fetchall()
    return [_row_to_event(r) for r in rows]


def clear_events(conn: sqlite3.Connection) -> int:
    cur = conn.execute("DELETE FROM events")
    conn.commit()
    return cur.rowcount


# -- recording state -------------------------------------------------------

def get_recording(conn: sqlite3.Connection) -> dict[str, Any]:
    r = conn.execute("SELECT * FROM recording WHERE k = 1").fetchone()
    return {
        "active": bool(r["active"]),
        "session": r["session"],
        "label": r["label"],
        "label_version": r["label_version"],
        "started_ts": r["started_ts"],
        "rows": r["rows"],
        "dropped": r["dropped"],
        "mismatched": r["mismatched"],
    }


def start_recording(conn: sqlite3.Connection, session: str, label: str) -> dict:
    conn.execute(
        """UPDATE recording SET active = 1, session = ?, label = ?,
           label_version = label_version + 1, started_ts = ?, rows = 0, dropped = 0,
           mismatched = 0
           WHERE k = 1""",
        (session, label, int(time.time() * 1000)),
    )
    conn.commit()
    return get_recording(conn)


def stop_recording(conn: sqlite3.Connection) -> dict:
    conn.execute("UPDATE recording SET active = 0 WHERE k = 1")
    conn.commit()
    return get_recording(conn)


def set_label(conn: sqlite3.Connection, label: str) -> dict:
    """Bumping label_version is what tells the serial bridge to send LABEL <x>."""
    conn.execute(
        "UPDATE recording SET label = ?, label_version = label_version + 1 WHERE k = 1",
        (label,),
    )
    conn.commit()
    return get_recording(conn)


def count_trace_row(conn: sqlite3.Connection, stored: bool, mismatched: bool = False) -> None:
    col = "rows" if stored else "dropped"
    conn.execute(f"UPDATE recording SET {col} = {col} + 1 WHERE k = 1")
    if mismatched:
        conn.execute("UPDATE recording SET mismatched = mismatched + 1 WHERE k = 1")
    conn.commit()


# -- v4 control state ------------------------------------------------------

def get_control(conn: sqlite3.Connection) -> dict[str, Any]:
    c = conn.execute("SELECT * FROM control WHERE k = 1").fetchone()
    r = get_recording(conn)
    return {
        "mode": c["mode"], "mode_version": c["mode_version"],
        "attack_profile": c["attack_profile"], "attack_version": c["attack_version"],
        "label": r["label"], "label_version": r["label_version"],
    }


def set_mode(conn: sqlite3.Connection, mode: str) -> None:
    conn.execute("UPDATE control SET mode = ?, mode_version = mode_version + 1 WHERE k = 1", (mode,))
    conn.commit()


def set_attack(conn: sqlite3.Connection, profile: str) -> None:
    conn.execute("UPDATE control SET attack_profile = ?, attack_version = attack_version + 1 WHERE k = 1",
                 (profile,))
    conn.commit()


def touch_node(conn: sqlite3.Connection, node: str, ts: int, rssi: Optional[float] = None,
               battery_pct: Optional[float] = None) -> None:
    """Record that `node` was heard from. rssi/battery only overwrite when given."""
    conn.execute(
        """INSERT INTO node_seen (node, last_ts, rssi, battery_pct) VALUES (?,?,?,?)
           ON CONFLICT(node) DO UPDATE SET
             last_ts = MAX(last_ts, excluded.last_ts),
             rssi = COALESCE(excluded.rssi, rssi),
             battery_pct = COALESCE(excluded.battery_pct, battery_pct)""",
        (node, ts, rssi, battery_pct),
    )
    conn.commit()


def get_nodes_seen(conn: sqlite3.Connection) -> dict[str, dict]:
    return {r["node"]: dict(r) for r in conn.execute("SELECT * FROM node_seen")}
