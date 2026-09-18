"""Contract validation: every event and trace row is checked against the JSON
Schemas in contracts/ before it is stored.

The console is the integration point, so it is the right place for a wrong
event to fail loudly. A firmware event with a typo'd field should break at
hour 14, not during the pitch.
"""
import json
from typing import Any

from jsonschema import Draft202012Validator

from . import config

_EVENT_DEFAULTS = {"score": None, "node": None, "technique": None, "reasons": [], "details": {}}


def _load(path: str) -> Draft202012Validator:
    with open(path, encoding="utf-8") as f:
        return Draft202012Validator(json.load(f))


_event_validator = None
_trace_validator = None


def event_validator() -> Draft202012Validator:
    global _event_validator
    if _event_validator is None:
        _event_validator = _load(config.EVENT_SCHEMA_PATH)
    return _event_validator


def trace_validator() -> Draft202012Validator:
    global _trace_validator
    if _trace_validator is None:
        _trace_validator = _load(config.TRACE_SCHEMA_PATH)
    return _trace_validator


def _errors(validator: Draft202012Validator, payload: Any) -> list[str]:
    out = []
    for e in sorted(validator.iter_errors(payload), key=lambda e: list(e.path)):
        where = "/".join(str(p) for p in e.path) or "(root)"
        out.append(f"{where}: {e.message}")
    return out


def validate_event(payload: Any) -> tuple[dict, list[str]]:
    """Validate and normalize one event.

    Returns (event_with_defaults_filled, errors). The optional fields are
    filled in *after* validation so storage never has to deal with missing
    keys, while a producer that omits `reasons` is still accepted.
    """
    if not isinstance(payload, dict):
        return {}, ["(root): event must be a JSON object"]
    errors = _errors(event_validator(), payload)
    if errors:
        return {}, errors
    event = {**_EVENT_DEFAULTS, **payload}
    return event, []


def validate_trace(payload: Any) -> tuple[dict, list[str]]:
    if not isinstance(payload, dict):
        return {}, ["(root): trace row must be a JSON object"]
    errors = _errors(trace_validator(), payload)
    if errors:
        return {}, errors
    return dict(payload), []
