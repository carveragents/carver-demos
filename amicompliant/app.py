"""
Agent Compliance Lab — FastAPI backend.

Endpoints:
  GET  /                       → SPA
  GET  /api/sanitisation-prompt → curated, copy-pasteable sanitisation prompt
  POST /api/evaluate           → evaluate a policy against live regulatory signals
  POST /api/suggest-update     → generate suggested policy diff for cited signals
  POST /api/leads              → capture email for gated signal list
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
from db import Lead, SignalCache, get_db, init_db

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Agent Compliance Lab")


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
# Industries (public metadata, no topic IDs)
# ---------------------------------------------------------------------------

@app.get("/api/industries")
def list_industries():
    return {"industries": feeds_monitor.public_industries()}


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------

class LeadRequest(BaseModel):
    email: str
    evaluation_id: str = ""


# ---------------------------------------------------------------------------
# Sanitisation prompt (curated; user runs it themselves elsewhere)
# ---------------------------------------------------------------------------

_SANITISATION_PROMPT_PATH = Path(__file__).parent / "prompts" / "sanitisation_prompt.txt"


@app.get("/api/sanitisation-prompt")
def get_sanitisation_prompt():
    try:
        return {"prompt": _SANITISATION_PROMPT_PATH.read_text()}
    except FileNotFoundError:
        raise HTTPException(status_code=500, detail="Sanitisation prompt file is missing")


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
    industry: str = Form(...),
    user_context: str = Form(default=""),
    file: UploadFile = File(default=None),
):
    industry = (industry or "").strip().lower()
    if industry not in feeds_monitor.load_industries():
        raise HTTPException(status_code=400, detail="Unknown or missing industry")

    # Business context is mandatory — the relevance check is only useful with it.
    user_context_clean = (user_context or "").strip()
    if len(user_context_clean.split()) < 15:
        raise HTTPException(
            status_code=400,
            detail="Please describe your AI agent in at least 2 sentences (about 15+ words).",
        )

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
        signals = feeds_monitor.fetch_signals(industry)
    except Exception as e:
        logger.error(f"Signal fetch error: {e}")
        raise HTTPException(status_code=502, detail=f"Could not reach Carver API: {e}")

    if not signals:
        evaluation_id = str(uuid.uuid4())
        return {
            "evaluation_id": evaluation_id,
            "industry": industry,
            "n_relevant": 0,
            "compliance_signal": None,
            "second_signal": None,
            "remaining": 0,
            "liability": None,
            "sector_ceiling": None,
            "compliance_score": 0,
            "compliance_bucket": "Low",
            "compliance_rationale": "",
            "message": "No enforcement or final-rule signals found in the last 30 days.",
        }

    # Score relevance against the user's prompt
    signals = feeds_monitor.score_relevance(signals, text, industry, user_context_clean)

    # Compute deterministic compliance score and LLM rationale
    score, bucket = feeds_monitor.compute_compliance_score(signals)
    rationale = feeds_monitor.generate_compliance_rationale(text, signals, score, bucket, industry)

    n_relevant = len(signals)
    evaluation_id = str(uuid.uuid4())

    # Signal 1: best match for policy compliance update (highest relevance)
    compliance_signal = signals[0]

    # Signal 2: second-best for source attribution, only if it clears the
    # configured minimum (so we don't force a weak citation into the diff).
    ranking_cfg = feeds_monitor.load_ranking_config()
    second_signal = None
    if len(signals) > 1 and signals[1].relevance_score >= ranking_cfg["second_signal_min_score"]:
        second_signal = signals[1]

    # Cited set drives BOTH the diff AND the liability anchor — internally
    # consistent.
    cited_signals = [compliance_signal] + ([second_signal] if second_signal else [])
    liability = feeds_monitor.compute_liability(cited_signals, ranking_cfg["liability_min_relevance"])
    sector_ceiling = feeds_monitor.compute_sector_ceiling(signals)

    # Cards shown: just the cited signals. Remaining = total minus those.
    remaining = max(0, n_relevant - len(cited_signals))

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
        "industry": industry,
        "n_relevant": n_relevant,
        "compliance_signal": feeds_monitor.serialize_signal(compliance_signal),
        "second_signal": feeds_monitor.serialize_signal(second_signal) if second_signal else None,
        "remaining": remaining,
        "liability": liability,
        "sector_ceiling": sector_ceiling,
        "compliance_score": score,
        "compliance_bucket": bucket,
        "compliance_rationale": rationale,
        # prompt_text echoed back so the frontend can call /api/suggest-update
        "prompt_text": text,
    }


# ---------------------------------------------------------------------------
# Suggest update (separate call so evaluate results appear immediately)
# ---------------------------------------------------------------------------

class SuggestRequest(BaseModel):
    prompt_text: str
    signals: list[dict] | None = None
    signal: dict | None = None  # legacy single-signal payload


def _to_signal(d: dict):
    from feeds_monitor import EnforcementSignal
    return EnforcementSignal(
        entry_id=d.get("entry_id", ""),
        title=d.get("title", ""),
        summary=d.get("summary", ""),
        update_type=d.get("update_type", "enforcement"),
        topic_name=d.get("topic_name", ""),
        topic_id=d.get("topic_id", ""),
        published_at=d.get("published_at", ""),
        link=d.get("link", ""),
        tags=d.get("tags", []),
        has_ai_tag=d.get("has_ai_tag", False),
    )


@app.post("/api/suggest-update")
async def suggest_update(req: SuggestRequest):
    if not req.prompt_text.strip():
        raise HTTPException(status_code=400, detail="prompt_text is required")

    raw_signals = req.signals if req.signals else ([req.signal] if req.signal else [])
    raw_signals = [s for s in raw_signals if s]
    if not raw_signals:
        raise HTTPException(status_code=400, detail="At least one signal is required")

    sigs = [_to_signal(s) for s in raw_signals]

    try:
        diff = feeds_monitor.generate_prompt_update(req.prompt_text, sigs)
        return {
            "diff": diff,
            "sources": [
                {
                    "topic_name": s.topic_name,
                    "update_type": s.update_type,
                    "title": s.title,
                    "link": s.link,
                }
                for s in sigs
            ],
        }
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
