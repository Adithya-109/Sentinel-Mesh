"""SQLite storage for events, trace rows and the recording session.

One row per Event, with `reasons` and `details` stored as JSON text. Incidents
are NOT stored -- they are derived from the events table on every read (see
correlation.py), so a late-arriving event can never leave a stale incident
behind.
"""
import json
import os
import sqlite3
import time
from typing import Any, Optional

from . import config

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
    conn = sqlite3.connect(path, check_same_thread=False)
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
    """Events in timeline order (oldest first). `since` is exclusive."""
    if since is None:
        rows = conn.execute("SELECT * FROM events ORDER BY ts, received_ts LIMIT ?", (limit,)).fetchall()
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
