"""Paths and tunables for the console. Everything is overridable by env var
so the demo can be pointed at a different DB, port or trace folder without
editing code."""
import os

HERE = os.path.dirname(os.path.abspath(__file__))
CONSOLE_DIR = os.path.dirname(HERE)
REPO_DIR = os.path.dirname(CONSOLE_DIR)

CONTRACTS_DIR = os.environ.get("SENTINEL_CONTRACTS_DIR", os.path.join(REPO_DIR, "contracts"))
EVENT_SCHEMA_PATH = os.path.join(CONTRACTS_DIR, "event.schema.json")
TRACE_SCHEMA_PATH = os.path.join(CONTRACTS_DIR, "trace.schema.json")

DB_PATH = os.environ.get("SENTINEL_DB", os.path.join(CONSOLE_DIR, "data", "console.db"))

# Recorded traces land here. The ML stream trains from ml/data/traces/, so the
# handoff is a copy -- see demo/RUNBOOK.md. Kept inside console/ because the
# console owns its own folder.
TRACE_DIR = os.environ.get("SENTINEL_TRACE_DIR", os.path.join(CONSOLE_DIR, "data", "traces"))

# 127.0.0.1, never "localhost": on Windows, "localhost" resolves to ::1 first and
# stalls ~2s per request before falling back to IPv4 (measured on the gateway
# laptop: 2047ms vs 2.4ms). At demo pace that lag is visible on stage.
CONSOLE_URL = os.environ.get("SENTINEL_CONSOLE_URL", "http://127.0.0.1:8000")
ML_URL = os.environ.get("SENTINEL_ML_URL", "http://127.0.0.1:8001")

# Correlation window: events more than this far apart start a new incident.
INCIDENT_WINDOW_MS = int(os.environ.get("SENTINEL_INCIDENT_WINDOW_MS", 10 * 60 * 1000))

# Where the ML stream's charts and metrics live, for the Evidence page (read-only).
ML_REPORTS_DIR = os.environ.get("SENTINEL_ML_REPORTS", os.path.join(REPO_DIR, "ml", "reports"))
