"""
AmiCompliant — FastAPI backend.

Endpoints:
  GET  /                      → SPA
  POST /api/sanitise          → sanitise submitted text (LLM or meta-prompt)
  POST /api/evaluate          → evaluate a prompt against live regulatory signals
  POST /api/suggest-update    → generate suggested prompt diff for the top signal
  POST /api/leads             → capture email for gated signal list
"""

import json
import logging
import os
import uuid
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, UploadFile, File, Form
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel

load_dotenv(Path(__file__).parent / ".env")

import feeds_monitor
import sanitise as san
from db import Lead, SignalCache, get_db, init_db

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="AmiCompliant")


@app.on_event("startup")
def on_startup():
    init_db()
    logger.info("DB initialised")


# ---------------------------------------------------------------------------
# Static
# ---------------------------------------------------------------------------

@app.get("/")
def serve_ui():
    return FileResponse(Path(__file__).parent / "static" / "index.html")


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------

class SanitiseRequest(BaseModel):
    text: str
    mode: str = "do_it"   # "do_it" | "give_prompt"


class LeadRequest(BaseModel):
    email: str
    evaluation_id: str = ""


# ---------------------------------------------------------------------------
# Sanitise
# ---------------------------------------------------------------------------

@app.post("/api/sanitise")
async def sanitise(req: SanitiseRequest):
    if not req.text.strip():
        raise HTTPException(status_code=400, detail="text is required")

    if req.mode == "give_prompt":
        return {"mode": "give_prompt", "meta_prompt": san.build_meta_prompt(req.text)}

    try:
        result = san.sanitise_text(req.text)
        return {"mode": "do_it", "sanitised": result}
    except Exception as e:
        logger.error(f"Sanitise error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ---------------------------------------------------------------------------
# Evaluate
# ---------------------------------------------------------------------------

def _extract_text_from_pdf(data: bytes) -> str:
    from pypdf import PdfReader
    import io
    reader = PdfReader(io.BytesIO(data))
    raw = "\n".join(page.extract_text() or "" for page in reader.pages)
    # pypdf often emits each line twice (visual + accessibility layer).
    # Deduplicate consecutive identical lines while preserving blank separators.
    seen: set[str] = set()
    deduped: list[str] = []
    for line in raw.splitlines():
        stripped = line.strip()
        if not stripped:
            seen.clear()          # blank line resets the window
            deduped.append(line)
        elif stripped not in seen:
            seen.add(stripped)
            deduped.append(line)
    return "\n".join(deduped)


@app.post("/api/evaluate")
async def evaluate(
    prompt_text: str = Form(default=""),
    file: UploadFile = File(default=None),
):
    # Resolve the prompt text
    text = prompt_text.strip()

    if file and not text:
        raw = await file.read()
        filename = (file.filename or "").lower()
        if filename.endswith(".pdf"):
            try:
                text = _extract_text_from_pdf(raw)
            except Exception as e:
                raise HTTPException(status_code=400, detail=f"PDF parse error: {e}")
        else:
            # Treat as UTF-8 markdown/plain text
            try:
                text = raw.decode("utf-8")
            except UnicodeDecodeError:
                raise HTTPException(status_code=400, detail="File must be UTF-8 encoded text or PDF")

    if not text:
        raise HTTPException(status_code=400, detail="Provide prompt_text or upload a file")

    # Fetch live signals from Carver
    try:
        signals = feeds_monitor.fetch_signals()
    except Exception as e:
        logger.error(f"Signal fetch error: {e}")
        raise HTTPException(status_code=502, detail=f"Could not reach Carver API: {e}")

    if not signals:
        evaluation_id = str(uuid.uuid4())
        return {
            "evaluation_id": evaluation_id,
            "n_relevant": 0,
            "top_signal": None,
            "remaining": 0,
            "liability": None,
            "message": "No enforcement or final-rule signals found in the last 30 days.",
        }

    # Score relevance against the user's prompt
    signals = feeds_monitor.score_relevance(signals, text)

    n_relevant = len(signals)
    evaluation_id = str(uuid.uuid4())

    # Signal 1: best match for prompt compliance update (highest relevance)
    compliance_signal = signals[0]

    # Signal 2: best anchor for financial exposure (concrete penalty amounts preferred)
    liability_signal = feeds_monitor.pick_liability_signal(signals)

    remaining = max(0, n_relevant - (1 if compliance_signal.entry_id == liability_signal.entry_id else 2))

    # Cache signals to DB for the lead gating lookup
    db = get_db()
    try:
        for s in signals:
            existing = db.query(SignalCache).filter_by(entry_id=s.entry_id).first()
            if not existing:
                db.add(SignalCache(
                    topic_name=s.topic_name,
                    entry_id=s.entry_id,
                    data=json.dumps(feeds_monitor.serialize_signal(s)),
                ))
        db.commit()
    except Exception as e:
        logger.warning(f"Signal cache write failed: {e}")
        db.rollback()
    finally:
        db.close()

    return {
        "evaluation_id": evaluation_id,
        "n_relevant": n_relevant,
        "compliance_signal": feeds_monitor.serialize_signal(compliance_signal),
        "liability_signal": feeds_monitor.serialize_signal(liability_signal),
        "same_signal": compliance_signal.entry_id == liability_signal.entry_id,
        "remaining": remaining,
        "liability": liability_signal.liability,
        # prompt_text echoed back so the frontend can call /api/suggest-update
        "prompt_text": text,
    }


# ---------------------------------------------------------------------------
# Suggest update (separate call so evaluate results appear immediately)
# ---------------------------------------------------------------------------

class SuggestRequest(BaseModel):
    prompt_text: str
    signal: dict


@app.post("/api/suggest-update")
async def suggest_update(req: SuggestRequest):
    if not req.prompt_text.strip():
        raise HTTPException(status_code=400, detail="prompt_text is required")
    if not req.signal:
        raise HTTPException(status_code=400, detail="signal is required")

    # Reconstruct a lightweight EnforcementSignal from the serialised dict
    from feeds_monitor import EnforcementSignal
    sig = EnforcementSignal(
        entry_id=req.signal.get("entry_id", ""),
        title=req.signal.get("title", ""),
        summary=req.signal.get("summary", ""),
        update_type=req.signal.get("update_type", "enforcement"),
        topic_name=req.signal.get("topic_name", ""),
        topic_id=req.signal.get("topic_id", ""),
        published_at=req.signal.get("published_at", ""),
        link=req.signal.get("link", ""),
        tags=req.signal.get("tags", []),
        has_ai_tag=req.signal.get("has_ai_tag", False),
    )

    try:
        diff = feeds_monitor.generate_prompt_update(req.prompt_text, sig)
        return {"diff": diff}
    except Exception as e:
        logger.error(f"suggest-update error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ---------------------------------------------------------------------------
# Leads
# ---------------------------------------------------------------------------

@app.post("/api/leads")
async def capture_lead(req: LeadRequest):
    if not req.email or "@" not in req.email:
        raise HTTPException(status_code=400, detail="Valid email required")

    db = get_db()
    try:
        lead = Lead(email=req.email.strip().lower(), evaluation_id=req.evaluation_id or None)
        db.add(lead)
        db.commit()
        logger.info(f"Lead captured: {req.email}")
        return {"status": "ok"}
    except Exception as e:
        db.rollback()
        logger.error(f"Lead capture error: {e}")
        raise HTTPException(status_code=500, detail="Could not save lead")
    finally:
        db.close()


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:app", host="0.0.0.0", port=7777, reload=True)
