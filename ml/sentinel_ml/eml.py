"""Parse raw .eml bytes: headers, HTML body -> plain text, attachments.

Used by POST /score/eml. Only stdlib (email, html.parser) -- no extra
dependency for something this small.
"""
import re
import uuid
from email import policy
from email.parser import BytesParser
from html.parser import HTMLParser


class _HTMLTextExtractor(HTMLParser):
    _SKIP_TAGS = {"script", "style"}
    _BREAK_TAGS = {"br", "p", "div", "tr", "li", "table", "h1", "h2", "h3"}

    def __init__(self):
        super().__init__()
        self._chunks = []
        self._skip_depth = 0

    def handle_starttag(self, tag, attrs):
        if tag in self._SKIP_TAGS:
            self._skip_depth += 1
        elif tag in self._BREAK_TAGS:
            self._chunks.append("\n")

    def handle_endtag(self, tag):
        if tag in self._SKIP_TAGS and self._skip_depth:
            self._skip_depth -= 1

    def handle_data(self, data):
        if not self._skip_depth:
            self._chunks.append(data)

    def text(self):
        return re.sub(r"\n{3,}", "\n\n", "".join(self._chunks)).strip()


def html_to_text(html: str) -> str:
    p = _HTMLTextExtractor()
    p.feed(html)
    return p.text()


def parse_eml(raw: bytes) -> dict:
    """Returns {message_id, subject, from, to, date, text, attachments}.

    attachments: list of {filename, content_type, data: bytes}.
    """
    msg = BytesParser(policy=policy.default).parsebytes(raw)
    message_id = (msg.get("Message-ID") or "").strip("<> \t") or str(uuid.uuid4())
    subject = str(msg.get("Subject", "") or "")
    from_ = str(msg.get("From", "") or "")
    to = str(msg.get("To", "") or "")
    date = str(msg.get("Date", "") or "")

    text = ""
    body_part = msg.get_body(preferencelist=("plain", "html"))
    if body_part is not None:
        try:
            content = body_part.get_content()
        except Exception:
            content = ""
        if body_part.get_content_type() == "text/html":
            text = html_to_text(content)
        else:
            text = content

    attachments = []
    for part in msg.iter_attachments():
        filename = part.get_filename() or "unnamed"
        content_type = part.get_content_type()
        try:
            data = part.get_payload(decode=True) or b""
        except Exception:
            data = b""
        attachments.append({"filename": filename, "content_type": content_type, "data": data})

    return {
        "message_id": message_id,
        "subject": subject,
        "from": from_,
        "to": to,
        "date": date,
        "text": text,
        "attachments": attachments,
    }
