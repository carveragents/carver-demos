"""
FinCoach AI Demo — FastAPI server.

Endpoints:
  GET  /                             → serves index.html
  POST /api/chat                     → chat with FinCoach AI
  POST /api/admin/toggle             → toggle Carver SDK on/off
  GET  /api/admin/status             → SDK state + enforcement signals + policy state
  GET  /api/admin/policy             → current policy state (versions + diff)
  POST /api/admin/policy/generate    → generate v2 from enforcement signals
  POST /api/admin/policy/activate    → activate v2 as the live policy
  POST /api/admin/policy/reset       → reset back to v1
"""

import logging
import os
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel

load_dotenv(Path(__file__).parent / ".env")

import policies
from agent import get_response, PLATFORM_CONTEXT, build_system_prompt
from feeds_monitor import EnforcementSignal, fetch_enforcements, format_enforcements_for_prompt

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="FinCoach AI Demo")

# ---------------------------------------------------------------------------
# Shared state
# ---------------------------------------------------------------------------
state: dict = {
    "sdk_enabled": False,
    "enforcements": [],
    "enforcement_context": "",
}

# Pre-load v1 at startup
policies.load_v1()


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------
class ChatMessage(BaseModel):
    role: str
    content: str

class ChatRequest(BaseModel):
    messages: list[ChatMessage]

class ToggleRequest(BaseModel):
    sdk_enabled: bool


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.get("/")
def serve_ui():
    return FileResponse(Path(__file__).parent / "static" / "index.html")


@app.post("/api/chat")
async def chat(req: ChatRequest):
    messages = [{"role": m.role, "content": m.content} for m in req.messages]
    policy_text = policies.get_active_policy()
    policy_version = policies.get_state()["active_version"]
    try:
        reply = get_response(messages=messages, policy_text=policy_text)
        flags = _annotate_risks(reply)
        return {
            "reply": reply,
            "flags": flags,
            "sdk_enabled": state["sdk_enabled"],
            "policy_version": policy_version,
        }
    except Exception as e:
        logger.error(f"Agent error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


def _annotate_risks(text: str) -> list[dict]:
    """
    Run a fast LLM pass to identify phrases in `text` that could constitute
    FTC violations around earnings claims, unqualified guarantees, AI
    non-disclosure, or testimonials without incentive disclosure.
    Returns [{phrase, reason, severity}] — empty list if nothing found.
    """
    from openai import OpenAI
    import json as _json

    client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])

    system = (
        "You are a compliance reviewer. Given a chatbot response, identify any phrases "
        "that could constitute FTC violations in the following categories:\n"
        "1. Specific unsubstantiated earnings claims (percentages, dollar figures, timeframes)\n"
        "2. Unqualified guarantee or refund claims (no mention of terms/restrictions)\n"
        "3. Testimonials shared without disclosing that participants may have received benefits\n"
        "4. Failure to disclose AI identity when the bot refers to itself\n"
        "5. Income aspiration language presented as achievable fact\n\n"
        "Return ONLY a JSON array. Each element: "
        "{\"phrase\": \"exact text from response\", \"reason\": \"one-line FTC risk\", "
        "\"severity\": \"high\" | \"medium\"}. "
        "Empty array [] if nothing is found. No other text."
    )

    try:
        r = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": f"Response to review:\n\n{text}"},
            ],
            temperature=0,
            max_tokens=400,
        )
        raw = r.choices[0].message.content.strip()
        # Strip markdown code fences if present
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        return _json.loads(raw)
    except Exception as e:
        logger.warning(f"Risk annotation failed: {e}")
        return []


@app.post("/api/admin/toggle")
async def toggle_sdk(req: ToggleRequest):
    state["sdk_enabled"] = req.sdk_enabled

    if req.sdk_enabled:
        logger.info("SDK toggled ON — fetching enforcement signals...")
        try:
            signals = fetch_enforcements()
            state["enforcements"] = signals
            state["enforcement_context"] = format_enforcements_for_prompt(signals)
            logger.info(f"Loaded {len(signals)} enforcement signal(s)")
        except Exception as e:
            logger.error(f"Failed to fetch enforcements: {e}")
            state["enforcements"] = []
            state["enforcement_context"] = ""
            return JSONResponse(status_code=200, content={
                "sdk_enabled": True,
                "enforcements": [],
                "policy": policies.get_state(),
                "warning": f"SDK enabled but enforcement fetch failed: {e}",
            })
    else:
        state["enforcements"] = []
        state["enforcement_context"] = ""
        policies.reset_to_v1()
        logger.info("SDK toggled OFF — enforcement context and policy reset")

    return {
        "sdk_enabled": state["sdk_enabled"],
        "enforcements": _serialize_enforcements(state["enforcements"]),
        "policy": policies.get_state(),
        "active_system_prompt": build_system_prompt(policies.get_active_policy()),
    }


@app.get("/api/admin/status")
async def get_status():
    return {
        "sdk_enabled": state["sdk_enabled"],
        "enforcements": _serialize_enforcements(state["enforcements"]),
        "policy": policies.get_state(),
        "active_system_prompt": build_system_prompt(policies.get_active_policy()),
    }


@app.get("/api/admin/policy")
async def get_policy():
    return policies.get_state()


@app.post("/api/admin/policy/generate")
async def generate_policy_update():
    if not state["enforcement_context"]:
        raise HTTPException(
            status_code=400,
            detail="No enforcement signals loaded. Enable the SDK first."
        )
    try:
        result = policies.generate_v2(state["enforcement_context"])
        return result
    except Exception as e:
        logger.error(f"Policy generation failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/admin/policy/activate")
async def activate_policy():
    try:
        policies.activate_v2()
        return {
            "active_version": "v2",
            "policy": policies.get_state(),
            "active_system_prompt": build_system_prompt(policies.get_active_policy()),
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/api/admin/policy/reset")
async def reset_policy():
    policies.reset_to_v1()
    return {
        "active_version": "v1",
        "policy": policies.get_state(),
        "active_system_prompt": build_system_prompt(policies.get_active_policy()),
    }


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _serialize_enforcements(signals: list[EnforcementSignal]) -> list[dict]:
    return [
        {
            "entry_id": s.entry_id,
            "title": s.title,
            "summary": s.summary,
            "topic_name": s.topic_name,
            "published_at": s.published_at[:10] if s.published_at else "",
            "link": s.link,
            "tags": s.tags,
            "has_ai_tag": s.has_ai_tag,
        }
        for s in signals
    ]


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:app", host="0.0.0.0", port=7777, reload=True)
