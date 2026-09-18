"""MailGuard reports a score plus a clean / suspicious / malicious verdict, no reasons."""
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sentinel_ml import mailguard  # noqa: E402
from sentinel_ml.schemas import mail_event  # noqa: E402


@pytest.mark.parametrize("score,expected", [
    (0.0, "clean"), (0.05, "clean"), (0.3999, "clean"),
    (0.40, "suspicious"), (0.55, "suspicious"), (0.7499, "suspicious"),
    (0.75, "malicious"), (0.999, "malicious"), (1.0, "malicious"),
])
def test_verdict_bands(score, expected):
    assert mailguard.verdict(score) == expected


@pytest.mark.parametrize("verdict,type_,severity,technique", [
    ("clean", "email_clean", "info", None),
    ("suspicious", "email_suspicious", "medium", "T1566.001"),
    ("malicious", "email_malicious", "high", "T1566.001"),
])
def test_mail_event_shape(verdict, type_, severity, technique):
    e = mail_event(verdict, 0.5)
    assert (e.layer, e.type, e.severity, e.technique) == ("mail", type_, severity, technique)
    assert e.score == 0.5
    assert e.reasons == []


def test_mailguard_has_no_word_explanation():
    assert not hasattr(mailguard, "explain")
