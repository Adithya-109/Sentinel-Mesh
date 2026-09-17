"""Text normalization shared by MailGuard training and scoring.

Numbers, URLs and email addresses are replaced with placeholder tokens so
the model can't just memorize years, sender domains or phone numbers from
one corpus (see brief section 5, "strengthen at the event").
"""
import re

_URL_RE = re.compile(r"https?://\S+|www\.\S+", re.IGNORECASE)
_EMAIL_RE = re.compile(r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+")
_NUM_RE = re.compile(r"\d+")


def normalize_text(text: str) -> str:
    text = str(text)
    text = _URL_RE.sub(" URLTOK ", text)
    text = _EMAIL_RE.sub(" EMAILTOK ", text)
    text = _NUM_RE.sub(" NUMTOK ", text)
    return text
