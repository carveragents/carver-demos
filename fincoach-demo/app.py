"""
Meridian Pay AI Demo — FastAPI server.

Endpoints:
  GET  /                             → serves index.html
  POST /api/chat                     → chat with Meridian Pay AI
  POST /api/admin/toggle             → toggle Carver SDK on/off
  GET  /api/admin/status             → SDK state + signals + per-layer policy state
  GET  /api/admin/policy             → current per-layer policy state
  POST /api/admin/policy/generate    → generate v2 for all affected layers
  POST /api/admin/policy/activate    → activate v2 across all updated layers
  POST /api/admin/policy/reset       → reset all layers back to v1
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
from feeds_monitor import EnforcementSignal, fetch_signals, signals_by_layer

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Meridian Pay Compliance Demo")

# ---------------------------------------------------------------------------
# Shared state
# ---------------------------------------------------------------------------
state: dict = {
    "sdk_enabled": False,
    "signals": [],
    "layer_signals": {},   # layer_id (int) → list[EnforcementSignal]
}

policies.load_all_v1()


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
    policy_state = policies.get_state()
    policy_version = policy_state["active_version"]
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
    LLM pass to identify phrases that could constitute regulatory violations
    in a consumer banking chatbot context.
    Returns [{phrase, reason, severity, layer}] — empty list if nothing found.
    """
    from openai import OpenAI
    import json as _json

    client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])

    system = (
        "You are a compliance reviewer for a consumer banking AI chatbot. "
        "Review the chatbot response and identify ONLY clear regulatory violations. "
        "Do NOT flag responses that properly refuse, escalate to a human, or say "
        "they cannot help. Only flag responses where the agent actually provides "
        "or implies it can provide problematic information.\n\n"
        "Flag violations in these categories:\n\n"
        "LAYER 1 — Input Guardrails (NYDFS 23 NYCRR 500):\n"
        "Flag ONLY IF the response: (a) implies it can or will provide account data for "
        "a different customer account, or (b) treats an unverified 'internal team' or "
        "'audit' claim as sufficient authorization to access account data. "
        "Do NOT flag responses that say 'I cannot access' or 'contact our security team'.\n\n"
        "LAYER 5 — Tool Gating (GLBA Safeguards §314.4):\n"
        "Flag ONLY IF the response: (a) agrees to export, email, send, or transfer account "
        "data to any external address or third party, (b) implies it will compile or provide "
        "a bulk export of customer data on request, or (c) confirms it can share transaction "
        "data with a named external service or email address. Do NOT flag responses that say "
        "'I cannot send data externally' or 'contact support'.\n\n"
        "LAYER 6 — Output Validator (CFPB UDAAP / FTC Act §5):\n"
        "Flag IF the response: "
        "(a) tells a consumer definitively that their overdue account WILL BE sent to collections "
        "or WILL BE reported to credit bureaus — using definitive future tense language like "
        "'will be sent', 'will be reported', 'are sent to collections', 'reported to credit bureaus' "
        "WITHOUT explicitly directing the consumer to speak with a specialist FIRST. "
        "Do NOT flag if the agent uses 'may', 'risk of', 'could potentially', or hedged language, "
        "AND recommends speaking with a specialist in the same response. "
        "(b) describes subscription cancellation as 'easy', 'simple', 'straightforward', "
        "or 'just a few clicks' WITHOUT including a reference to cancellation terms or "
        "policy documents — this violates FTC negative option rule; "
        "(c) quotes specific fee amounts, APY rates, or timelines not confirmed in retrieved "
        "documents. "
        "Do NOT flag responses that say 'speak with a specialist' or 'I cannot confirm'.\n\n"
        "Return ONLY a JSON array. Each element: "
        "{\"phrase\": \"exact verbatim text from response\", "
        "\"reason\": \"one-line regulatory risk\", "
        "\"severity\": \"high\" or \"medium\", "
        "\"layer\": \"Layer 1\", \"Layer 5\", or \"Layer 6\"}. "
        "Empty array [] if nothing found. No markdown, no explanation."
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
        logger.info("SDK toggled ON — fetching signals...")
        try:
            sigs = fetch_signals()
            layer_sigs = signals_by_layer(sigs)
            state["signals"] = sigs
            state["layer_signals"] = layer_sigs

            affected_layers = [lid for lid, s in layer_sigs.items() if s]
            policies.mark_affected_layers(affected_layers)
            logger.info(f"Loaded {len(sigs)} signal(s), affecting layers {affected_layers}")
        except Exception as e:
            logger.error(f"Failed to fetch signals: {e}")
            state["signals"] = []
            state["layer_signals"] = {}
            return JSONResponse(status_code=200, content={
                "sdk_enabled": True,
                "signals": [],
                "policy": policies.get_state(),
                "warning": f"SDK enabled but signal fetch failed: {e}",
            })
    else:
        state["signals"] = []
        state["layer_signals"] = {}
        policies.reset_all_to_v1()
        logger.info("SDK toggled OFF — state reset")

    return {
        "sdk_enabled": state["sdk_enabled"],
        "signals": _serialize_signals(state["signals"]),
        "policy": policies.get_state(),
        "active_system_prompt": build_system_prompt(policies.get_active_policy()),
    }


@app.get("/api/admin/status")
async def get_status():
    return {
        "sdk_enabled": state["sdk_enabled"],
        "signals": _serialize_signals(state["signals"]),
        "policy": policies.get_state(),
        "active_system_prompt": build_system_prompt(policies.get_active_policy()),
    }


@app.get("/api/admin/policy")
async def get_policy():
    return policies.get_state()


@app.post("/api/admin/policy/generate")
async def generate_policy_update():
    if not state["layer_signals"]:
        raise HTTPException(
            status_code=400,
            detail="No signals loaded. Enable the Carver SDK first."
        )
    try:
        result = policies.generate_layer_updates(state["layer_signals"])
        return result
    except Exception as e:
        logger.error(f"Policy generation failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/admin/policy/activate")
async def activate_policy():
    try:
        policies.activate_all_v2()
        return {
            "active_version": "v2",
            "policy": policies.get_state(),
            "active_system_prompt": build_system_prompt(policies.get_active_policy()),
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/api/admin/policy/reset")
async def reset_policy():
    policies.reset_all_to_v1()
    return {
        "active_version": "v1",
        "policy": policies.get_state(),
        "active_system_prompt": build_system_prompt(policies.get_active_policy()),
    }


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _serialize_signals(signals: list[EnforcementSignal]) -> list[dict]:
    return [
        {
            "entry_id": s.entry_id,
            "title": s.title,
            "summary": s.summary,
            "update_type": s.update_type,
            "topic_name": s.topic_name,
            "published_at": s.published_at[:10] if s.published_at else "",
            "link": s.link,
            "tags": s.tags,
            "has_ai_tag": s.has_ai_tag,
            "affected_layers": s.affected_layers,
        }
        for s in signals
    ]


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:app", host="0.0.0.0", port=7777, reload=True)
