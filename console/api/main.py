"""SentinelMesh console API (contracts/CONTRACT.md): FastAPI on :8000.

Contract endpoints:
    POST /events          an Event -> 201
    GET  /events?since=   events since an epoch-ms timestamp
    GET  /incidents       correlated incidents (rules, see correlation.py)

Console-local (not contract surface -- see contracts/CHANGELOG.md):
    GET  /health
    GET/POST /recording, POST /recording/{start,stop,label}
    GET/POST /traces
    DELETE /events

Run:
    uvicorn api.main:app --port 8000        # from console/
"""
import json
import os
import re
import time
from typing import Any, Optional

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.responses import JSONResponse

from . import attack, config, correlation, db, validation

app = FastAPI(title="SentinelMesh console", version="1.0")

_conn = db.connect()

TRACE_LABELS = ["normal", "weak_link", "replay", "flood", "impersonation"]
_SAFE_SESSION = re.compile(r"[^A-Za-z0-9_-]+")


def _session_filename(session: str) -> str:
    """Session names become file names, so they are sanitized, not trusted."""
    safe = _SAFE_SESSION.sub("_", session).strip("_")
    return safe or "session"


@app.get("/health")
def health():
    rec = db.get_recording(_conn)
    n = _conn.execute("SELECT COUNT(*) AS n FROM events").fetchone()["n"]
    return {
        "status": "ok",
        "events": n,
        "recording": rec["active"],
        "session": rec["session"],
        "db": config.DB_PATH,
        "trace_dir": config.TRACE_DIR,
    }


# -- contract endpoints ----------------------------------------------------

@app.post("/events", status_code=201)
async def post_event(request: Request):
    """Validate against contracts/event.schema.json, then store."""
    try:
        payload = await request.json()
    except Exception:
        raise HTTPException(400, "body must be JSON")

    event, errors = validation.validate_event(payload)
    if errors:
        return JSONResponse(
            status_code=422,
            content={"detail": "event does not match contracts/event.schema.json", "errors": errors},
        )

    stored = db.insert_event(_conn, event)
    return {"id": event["id"], "stored": stored, "duplicate": not stored}


@app.get("/events")
def get_events(since: Optional[int] = Query(None, description="epoch ms, exclusive"),
               limit: int = Query(1000, ge=1, le=10000)):
    events = db.get_events(_conn, since=since, limit=limit)
    for e in events:
        e["technique_name"] = attack.technique_name(e.get("technique"))
    return {"events": events, "count": len(events), "server_ts": int(time.time() * 1000)}


@app.get("/incidents")
def get_incidents(window_ms: Optional[int] = Query(None, ge=1000),
                  limit: int = Query(1000, ge=1, le=10000)):
    events = db.get_events(_conn, limit=limit)
    incidents = correlation.build_incidents(events, window_ms=window_ms)
    return {
        "incidents": incidents,
        "count": len(incidents),
        "window_ms": window_ms or config.INCIDENT_WINDOW_MS,
        "rules": "see console/api/correlation.py -- rules only, no ML",
    }


@app.delete("/events")
def delete_events():
    """Reset the demo database between rehearsals."""
    n = db.clear_events(_conn)
    return {"deleted": n}


# -- trace recording -------------------------------------------------------

@app.get("/recording")
def get_recording():
    return db.get_recording(_conn)


@app.post("/recording/start")
async def start_recording(request: Request):
    body = await _json_body(request)
    label = body.get("label", "normal")
    if label not in TRACE_LABELS:
        raise HTTPException(400, f"label must be one of {TRACE_LABELS}")
    session = body.get("session") or time.strftime("session_%Y%m%d_%H%M%S")
    rec = db.start_recording(_conn, _session_filename(session), label)
    os.makedirs(config.TRACE_DIR, exist_ok=True)
    return rec


@app.post("/recording/stop")
def stop_recording():
    return db.stop_recording(_conn)


@app.post("/recording/label")
async def set_label(request: Request):
    body = await _json_body(request)
    label = body.get("label")
    if label not in TRACE_LABELS:
        raise HTTPException(400, f"label must be one of {TRACE_LABELS}")
    return db.set_label(_conn, label)


@app.get("/traces")
def list_traces():
    """Recorded sessions on disk -- what gets handed to the ML stream."""
    out = []
    if os.path.isdir(config.TRACE_DIR):
        for name in sorted(os.listdir(config.TRACE_DIR)):
            if not name.endswith(".jsonl"):
                continue
            path = os.path.join(config.TRACE_DIR, name)
            labels: dict[str, int] = {}
            rows = 0
            with open(path, encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    rows += 1
                    try:
                        label = json.loads(line).get("label", "?")
                    except json.JSONDecodeError:
                        label = "<unparseable>"
                    labels[label] = labels.get(label, 0) + 1
            out.append({"session": name[:-6], "file": path, "rows": rows, "labels": labels})
    return {"trace_dir": config.TRACE_DIR, "sessions": out}


@app.post("/traces", status_code=202)
async def post_trace(request: Request):
    """One Trace row from the serial bridge.

    Dropped unless a recording session is active -- the gateway emits TRC lines
    continuously, and only the ones an operator deliberately labelled belong in
    the training set. Rows that fail contracts/trace.schema.json are counted and
    dropped rather than written: a malformed row would become silent zeros in
    the ML stream's features.
    """
    body = await _json_body(request)
    rec = db.get_recording(_conn)
    if not rec["active"]:
        return {"stored": False, "reason": "not recording"}

    row, errors = validation.validate_trace(body)
    if errors:
        db.count_trace_row(_conn, stored=False)
        return JSONResponse(
            status_code=422,
            content={"stored": False, "detail": "trace does not match contracts/trace.schema.json",
                     "errors": errors},
        )

    # The console owns ground truth: the operator chose the label in the UI, so
    # it is stamped here. A disagreeing gateway label is kept for debugging.
    gw_label = row.get("label")
    row["label"] = rec["label"]
    row["session"] = rec["session"]
    mismatched = bool(gw_label and gw_label != rec["label"])
    if mismatched:
        row["gw_label"] = gw_label

    os.makedirs(config.TRACE_DIR, exist_ok=True)
    path = os.path.join(config.TRACE_DIR, f"{rec['session']}.jsonl")
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(row) + "\n")
    db.count_trace_row(_conn, stored=True, mismatched=mismatched)
    return {"stored": True, "session": rec["session"], "label": rec["label"],
            "file": path, "gw_label_mismatch": mismatched}


async def _json_body(request: Request) -> dict[str, Any]:
    try:
        body = await request.json()
    except Exception:
        return {}
    return body if isinstance(body, dict) else {}
