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


_MAIL_VERDICTS = {
    # verdict: (type, severity, technique, summary)
    "clean": ("email_clean", "info", None, "Email looks clean"),
    "suspicious": ("email_suspicious", "medium", "T1566.001", "Suspicious email"),
    "malicious": ("email_malicious", "high", "T1566.001", "Malicious email detected"),
}


def mail_event(verdict: str, score: float, node: Optional[str] = None,
               details: Optional[dict] = None) -> Event:
    """MailGuard event for a 'clean' / 'suspicious' / 'malicious' verdict. No reasons: score only."""
    type_, severity, technique, summary = _MAIL_VERDICTS[verdict]
    return Event(
        layer="mail",
        type=type_,
        severity=severity,
        score=score,
        node=node,
        technique=technique,
        summary=summary,
        details=details or {},
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


def unsupported_attachment_event(filename: str, message_id: str, node: Optional[str] = None) -> Event:
    """A file_clean-style Event for an attachment type we don't score (not PE)."""
    return Event(
        layer="file",
        type="file_clean",
        severity="info",
        score=None,
        node=node,
        technique=None,
        summary="attachment type not analysed",
        reasons=[],
        details={"message_id": message_id, "filename": filename, "unsupported": True},
    )
