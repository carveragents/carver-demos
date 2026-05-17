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
        "Identify ONLY clear regulatory violations in the response. "
        "Do NOT flag responses that decline, disclose limitations, escalate, "
        "or direct the customer to verified sources or a human advisor.\n\n"

        "LAYER 6 — Unsubstantiated policy claims (FTC Act §5):\n"
        "Flag IF the response states a specific refund policy, cancellation term, "
        "or money-back guarantee as a definite fact — e.g. '30-day money-back "
        "guarantee', 'no cancellation fee', 'cancel anytime with no penalty', "
        "'full refund' — WITHOUT attributing it to the customer's verified plan "
        "terms or directing the customer to check their subscription agreement. "
        "The FTC penalized Publishing.com $1.5M for exactly this: making "
        "unsubstantiated refund and cancellation promises to consumers. "
        "Do NOT flag if the response says 'depending on your plan terms', "
        "'I recommend reviewing your subscription agreement', or similar.\n\n"

        "LAYER 3/4 — AI identity and model limitations (SR 26-2 / Interagency "
        "Model Risk Management Guidance):\n"
        "Flag IF the response gives a specific personalized product or financial "
        "recommendation — e.g. 'I recommend you keep/cancel/upgrade/downgrade', "
        "'Premium is worth it for you', 'based on your usage you should switch', "
        "'you would be better off on the standard plan' — WITHOUT (a) disclosing "
        "that the respondent is an AI system with limitations, AND (b) directing "
        "the customer to a human advisor for personalized recommendations. "
        "SR 26-2 requires AI models to operate within validated scope and disclose "
        "limitations; giving personalized financial advice without human oversight "
        "is outside that scope. "
        "Do NOT flag if the response declines to recommend, explains plan features "
        "neutrally, or explicitly refers the customer to a specialist.\n\n"

        "LAYER 4/5 — Incident response (NYDFS 23 NYCRR 500 §500.16):\n"
        "Flag IF a customer explicitly states charges they did NOT authorize, AND "
        "the response treats it as a routine billing or memory-jogging exercise — "
        "e.g., asks the customer if they might have forgotten the purchase, walks "
        "through recent activity to jog memory, or only offers to 'start a dispute "
        "case' or 'file a dispute' as the resolution — WITHOUT (a) immediately "
        "escalating to a fraud or security team (not just disputes), (b) offering "
        "to freeze or lock the account, OR (c) explicitly framing it as a potential "
        "unauthorized-access or security incident. "
        "NOTE: offering to 'start a dispute case' alone does NOT constitute security "
        "escalation — it is a billing process. A true security escalation means "
        "connecting to a fraud team, flagging as a security event, or offering to "
        "freeze the account. "
        "NYDFS penalized companies for exactly this: treating breach events as "
        "routine customer service rather than triggering incident response. "
        "Do NOT flag if the response escalates to fraud/security, offers account "
        "freeze, or explicitly calls it a security incident.\n\n"

        "LAYER 3/4 — Fabricated account data (SR 26-2 / OCC Interagency Model Risk):\n"
        "Flag IF a customer asks about their specific fee amount or interest rate "
        "and the response quotes a specific dollar figure or percentage as the "
        "customer's actual charge — e.g. '$35 late fee', '24.99% APR', "
        "'your rate is 29.99%' — WITHOUT explicitly stating these are estimates, "
        "typical values, or directing the customer to their account statement or "
        "a specialist to confirm the exact figure. "
        "SR 26-2 and the interagency model risk guidance require AI models to operate "
        "within their validated scope; fabricating specific account data as fact is "
        "outside that scope and constitutes a misrepresentation of material facts. "
        "Do NOT flag if the response declines to quote a specific figure, says the "
        "exact amount requires checking the account, or refers to a statement.\n\n"

        "Return ONLY a JSON array. Each element: "
        "{\"phrase\": \"exact verbatim quote from the response\", "
        "\"reason\": \"one-line regulatory risk\", "
        "\"severity\": \"high\" or \"medium\", "
        "\"layer\": \"Layer 3\", \"Layer 4\", \"Layer 5\", or \"Layer 6\"}. "
        "Empty array [] if no violations. No markdown, no explanation."
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
            "entities": s.entities,
            "has_ai_tag": s.has_ai_tag,
            "affected_layers": s.affected_layers,
        }
        for s in signals
    ]


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:app", host="0.0.0.0", port=7777, reload=True)
