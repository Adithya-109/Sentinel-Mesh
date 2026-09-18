"""SentinelMesh ML scoring service (contracts/CONTRACT.md): FastAPI on :8001.

Endpoints:
    GET  /health
    POST /score/email  {"text": "..."}                                  -> Event
    POST /score/file    multipart file  OR  {"features": {54 PE feats}}  -> Event
    POST /score/eml     multipart .eml file                              -> [Event]

Run:
    uvicorn service:app --port 8001
"""
import os
import tempfile

import joblib
import pandas as pd
from fastapi import FastAPI, HTTPException, Request

from sentinel_ml import eml as eml_parser
from sentinel_ml import fileguard, mailguard
from sentinel_ml.pe_features import extract as extract_pe_features
from sentinel_ml.schemas import Event, file_event, mail_event, unsupported_attachment_event

PE_EXTENSIONS = (".exe", ".dll")

HERE = os.path.dirname(os.path.abspath(__file__))
MODELS_DIR = os.path.join(HERE, "models")

app = FastAPI(title="SentinelMesh ML scoring service")

_mail = None
_file = None


def _load_models():
    global _mail, _file
    mail_path = os.path.join(MODELS_DIR, "mailguard.joblib")
    file_path = os.path.join(MODELS_DIR, "fileguard.joblib")
    _mail = joblib.load(mail_path) if os.path.exists(mail_path) else None
    _file = joblib.load(file_path) if os.path.exists(file_path) else None


_load_models()


@app.get("/health")
def health():
    return {
        "status": "ok",
        "mailguard_loaded": _mail is not None,
        "fileguard_loaded": _file is not None,
    }


def _score_email_text(text: str, details: dict = None) -> Event:
    score = float(mailguard.predict_proba(_mail["vectorizer"], _mail["model"], [text])[0])
    is_malicious = score >= _mail["threshold"]
    reasons = mailguard.explain(_mail["vectorizer"], _mail["model"], text)
    return mail_event(is_malicious, score, reasons, details=details or {})


def _extract_pe_bytes(data: bytes, suffix: str) -> dict:
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
        tmp.write(data)
        tmp_path = tmp.name
    try:
        return extract_pe_features(tmp_path)
    finally:
        os.remove(tmp_path)


def _score_pe_features(feats: dict, details: dict = None) -> Event:
    cols = _file["cols"]
    x = pd.Series(feats).reindex(cols, fill_value=0)
    x_row = x.values.astype(float)
    score = float(_file["model"].predict_proba(pd.DataFrame([x_row], columns=cols))[:, 1][0])
    is_malicious = score >= _file["threshold"]
    detail = fileguard.explain_detail(_file["model"], cols, x_row, malicious=is_malicious, top_k=5)
    reasons = fileguard.explain(_file["model"], cols, x_row, malicious=is_malicious)
    return file_event(is_malicious, score, reasons, details={**(details or {}), "shap": detail})


@app.post("/score/email", response_model=Event)
async def score_email(request: Request):
    if _mail is None:
        raise HTTPException(503, "MailGuard model not loaded; run build_all.py first")
    body = await request.json()
    text = body.get("text", "")
    return _score_email_text(text)


@app.post("/score/file", response_model=Event)
async def score_file(request: Request):
    if _file is None:
        raise HTTPException(503, "FileGuard model not loaded; run build_all.py first")
    content_type = request.headers.get("content-type", "")

    if "multipart/form-data" in content_type:
        form = await request.form()
        upload = form.get("file")
        if upload is None:
            raise HTTPException(400, "multipart body must include a 'file' field")
        data = await upload.read()
        suffix = os.path.splitext(upload.filename or "")[1] or ".bin"
        try:
            feats = _extract_pe_bytes(data, suffix)
        except Exception as exc:
            raise HTTPException(400, f"could not parse as a PE file: {exc}")
        details = {"filename": upload.filename}
    else:
        body = await request.json()
        features = body.get("features")
        if features is None:
            raise HTTPException(400, "JSON body must include a 'features' object")
        feats = features
        details = {}

    return _score_pe_features(feats, details=details)


@app.post("/score/eml", response_model=list[Event])
async def score_eml(request: Request):
    if _mail is None:
        raise HTTPException(503, "MailGuard model not loaded; run build_all.py first")
    content_type = request.headers.get("content-type", "")
    if "multipart/form-data" not in content_type:
        raise HTTPException(400, "expected multipart/form-data with a 'file' field (.eml)")
    form = await request.form()
    upload = form.get("file")
    if upload is None:
        raise HTTPException(400, "multipart body must include a 'file' field")
    raw = await upload.read()

    parsed = eml_parser.parse_eml(raw)
    message_id = parsed["message_id"]

    events = []
    mail_text = f"{parsed['subject']} {parsed['text']}"
    events.append(_score_email_text(mail_text, details={
        "message_id": message_id, "subject": parsed["subject"], "from": parsed["from"],
    }))

    for att in parsed["attachments"]:
        filename = att["filename"] or "unnamed"
        ext = os.path.splitext(filename)[1].lower()
        if ext in PE_EXTENSIONS and _file is not None:
            try:
                feats = _extract_pe_bytes(att["data"], ext)
                events.append(_score_pe_features(feats, details={
                    "message_id": message_id, "filename": filename,
                }))
                continue
            except Exception:
                pass  # not a parseable PE despite the extension -> fall through as unsupported
        events.append(unsupported_attachment_event(filename, message_id))

    return events
