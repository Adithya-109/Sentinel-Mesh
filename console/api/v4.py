"""v4 console-local endpoints: status, energy, experiment, and the demo controls.

Mounted twice by main.py -- at the root and under /api -- so the Streamlit UI,
the serial bridge and the React frontend (which calls /api/*) all reach the
same handlers. Response shapes follow console/frontend-kit/src/types.ts.

The controls only change console state. Getting it to the boards is the serial
bridge's job: it polls GET /control and, when a *_version changes, sends the
line to every bridged port (CONTRACT.md, "Serial lines"):

    POST /mode   {mode}     ->  DEFENSE <none|ratelimit|cookie|gate>   (gateway, relayed to field-1)
    POST /attack {profile}  ->  MODE <OFF|FLOOD|SLOW_DRIP|...>          (attacker)
"""
from typing import Any, Optional

from fastapi import APIRouter, HTTPException, Query, Request

from . import db, energy, experiment, status, validation

router = APIRouter()
_conn = None   # set by main.py, so tests and the app share one connection

MODES = ["none", "ratelimit", "cookie", "gate"]

# console attack profile -> the attacker board's existing MODE command
ATTACK_MODE_LINE = {
    "none": "OFF",
    "loud": "FLOOD",
    "slow_drip": "SLOW_DRIP",
    "replay": "REPLAY",
    "impersonate": "IMPERSONATE",
    "weak_link": "WEAK_LINK",
}

MODE_MARKER = {"none": "defence off", "ratelimit": "rate limit on",
               "cookie": "cookie challenge on", "gate": "EnergyGate on"}


def bind(conn) -> None:
    global _conn
    _conn = conn


async def _body(request: Request) -> dict[str, Any]:
    try:
        body = await request.json()
    except Exception:
        return {}
    return body if isinstance(body, dict) else {}


# -- read side -------------------------------------------------------------

@router.get("/status")
def get_status():
    return status.build(_conn)


@router.get("/energy")
def get_energy(since: Optional[int] = Query(None), limit: int = Query(3600, ge=1, le=100_000)):
    return energy.series(_conn, since=since, limit=limit)


@router.get("/experiment")
def get_experiment(profile: Optional[str] = Query(None)):
    try:
        return experiment.table(_conn, profile)
    except experiment.ExperimentError as exc:
        raise HTTPException(400, str(exc))


@router.get("/control")
def get_control():
    """What the serial bridge polls. The *_line fields are exactly what it sends."""
    c = db.get_control(_conn)
    c["defense_line"] = f"DEFENSE {c['mode']}"
    c["attack_line"] = f"MODE {ATTACK_MODE_LINE[c['attack_profile']]}"
    c["label_line"] = f"LABEL {c['label']}"
    return c


# -- ingest ----------------------------------------------------------------

@router.post("/energy", status_code=201)
async def post_energy(request: Request):
    """One INA219 sample (the bridge forwards NRG lines here)."""
    sample, errors = validation.validate_energy(await _body(request))
    if errors:
        raise HTTPException(422, {"detail": "sample does not match contracts/energy.schema.json",
                                  "errors": errors})
    row = energy.insert_sample(_conn, sample)
    db.touch_node(_conn, row["node"], row["ts"], battery_pct=row["battery_pct"])
    return {"stored": True, "ts": row["ts"], "device_ts": row["device_ts"]}


@router.post("/energy/marker", status_code=201)
async def post_marker(request: Request):
    label = (await _body(request)).get("label")
    if not isinstance(label, str) or not label.strip():
        raise HTTPException(400, "label must be a non-empty string")
    return energy.add_marker(_conn, label.strip()[:80])


# -- demo controls ---------------------------------------------------------

@router.post("/mode")
async def post_mode(request: Request):
    mode = (await _body(request)).get("mode")
    if mode not in MODES:
        raise HTTPException(400, f"mode must be one of {MODES}")
    db.set_mode(_conn, mode)
    energy.add_marker(_conn, MODE_MARKER[mode])
    return {"ok": True, "mode": mode, "line": f"DEFENSE {mode}"}


@router.post("/attack")
async def post_attack(request: Request):
    profile = (await _body(request)).get("profile")
    if profile not in ATTACK_MODE_LINE:
        raise HTTPException(400, f"profile must be one of {list(ATTACK_MODE_LINE)}")
    db.set_attack(_conn, profile)
    energy.add_marker(_conn, "attack stopped" if profile == "none" else f"attack starts: {profile}")
    return {"ok": True, "attack_profile": profile, "line": f"MODE {ATTACK_MODE_LINE[profile]}"}


@router.post("/experiment/run")
async def post_experiment_run(request: Request):
    body = await _body(request)
    try:
        return experiment.run(_conn, body.get("condition"), body.get("profile"), body.get("duration_s"))
    except experiment.ExperimentError as exc:
        raise HTTPException(409 if "in progress" in str(exc) else 400, str(exc))


@router.post("/experiment/stop")
def post_experiment_stop():
    done = experiment.stop(_conn)
    return {"ok": True, "stopped": done}


@router.post("/experiment/result")
async def post_experiment_result(request: Request):
    """Firmware-measured legit-client numbers for a finished row."""
    b = await _body(request)
    try:
        return experiment.record_result(_conn, b.get("condition"), b.get("profile"),
                                        b.get("legit_connect_pct"), b.get("legit_extra_delay_ms"))
    except experiment.ExperimentError as exc:
        raise HTTPException(400, str(exc))


@router.delete("/experiment")
def delete_experiment():
    experiment.reset(_conn)
    return {"ok": True}
