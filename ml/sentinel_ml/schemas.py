"""The Event schema every SentinelMesh layer emits (contracts/CONTRACT.md)."""
import time
import uuid
from typing import Any, Literal, Optional

from pydantic import BaseModel, Field

Layer = Literal["mail", "file", "field", "tamper"]
Severity = Literal["info", "low", "medium", "high", "critical"]


class Event(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    ts: int = Field(default_factory=lambda: int(time.time() * 1000))
    layer: Layer
    type: str
    severity: Severity
    score: Optional[float] = None
    node: Optional[str] = None
    technique: Optional[str] = None
    summary: str
    reasons: list[str] = Field(default_factory=list)
    details: dict[str, Any] = Field(default_factory=dict)


def mail_event(is_malicious: bool, score: float, reasons: list[str], node: Optional[str] = None) -> Event:
    return Event(
        layer="mail",
        type="email_malicious" if is_malicious else "email_clean",
        severity="high" if is_malicious else "info",
        score=score,
        node=node,
        technique="T1566.001" if is_malicious else None,
        summary="Malicious email detected" if is_malicious else "Email looks clean",
        reasons=reasons,
    )


def file_event(is_malicious: bool, score: float, reasons: list[str], node: Optional[str] = None,
               details: Optional[dict] = None) -> Event:
    return Event(
        layer="file",
        type="file_malicious" if is_malicious else "file_clean",
        severity="high" if is_malicious else "info",
        score=score,
        node=node,
        technique="T1204.002" if is_malicious else None,
        summary="Malicious file detected" if is_malicious else "File looks clean",
        reasons=reasons,
        details=details or {},
    )
