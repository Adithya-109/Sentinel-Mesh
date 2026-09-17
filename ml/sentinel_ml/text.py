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
    # TfidfVectorizer skips its own lowercasing when given a custom
    # preprocessor, so this has to do it -- otherwise "Free" and "free"
    # become different tokens and the model fragments its vocabulary.
    text = str(text).lower()
    text = _URL_RE.sub(" urltok ", text)
    text = _EMAIL_RE.sub(" emailtok ", text)
    text = _NUM_RE.sub(" numtok ", text)
    return text
