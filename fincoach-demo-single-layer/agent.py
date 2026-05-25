"""
FinCoach AI agent.

The system prompt is assembled from two parts:
  1. A fixed platform context (who the agent is and what the platform does)
  2. The active compliance policy document (v1 or v2, managed in policies.py)

The agent is instructed to treat the policy as its operating rules.
No compliance logic is baked into the platform context — all guardrails
come from the policy document, so the behavior change is entirely traceable
to a policy update, not a prompt swap.
"""

import os
from openai import OpenAI

# ---------------------------------------------------------------------------
# Fixed platform context — describes the product, never changes.
# Contains NO compliance instructions — those live in the policy document.
# ---------------------------------------------------------------------------

PLATFORM_CONTEXT = """You are FinCoach AI, the virtual assistant for FinCoach — a \
subscription-based investment education and trading signals platform.

About the platform:
- Members receive daily buy/sell signals with a tracked performance record
- Courses cover technical analysis, options strategies, and swing trading
- Subscription comes with a satisfaction guarantee for new members
- Thousands of active members, many of whom share success stories in our community

Your role:
- Answer visitor questions about the platform helpfully and enthusiastically
- When visitors ask about results, share member outcomes to help them decide
- Explain how the signals and courses work
- Help interested visitors get started with a subscription"""


def build_system_prompt(policy_text: str) -> str:
    return (
        f"{PLATFORM_CONTEXT}\n\n"
        "---\n"
        "COMPLIANCE POLICY — BINDING OPERATING RULES\n"
        "Every clause below is a hard constraint on your output, not a guideline.\n"
        "- Clauses using SHALL or MUST are mandatory — never omit them.\n"
        "- Clauses using SHALL NOT or MUST NOT are absolute prohibitions.\n"
        "- Where any clause conflicts with being helpful or enthusiastic, the clause wins.\n"
        "- Apply SHALL/MUST clauses proactively — do not wait to be asked.\n\n"
        f"{policy_text}\n\n"
        "BEFORE EVERY RESPONSE, run this checklist silently:\n"
        "1. Does the policy have a MUST clause about how to open this conversation? Apply it first.\n"
        "2. Does my response include any earnings figures, percentages, or dollar amounts? "
        "If a SHALL NOT clause prohibits them, remove them.\n"
        "3. Does my response mention a guarantee? If a SHALL clause requires restriction "
        "disclosure, add it.\n"
        "4. Does my response reference testimonials or member stories? If a SHALL clause "
        "requires an incentive disclaimer, add it.\n"
        "---"
    )


def get_response(
    messages: list[dict],
    policy_text: str,
    model: str = "gpt-4o-mini",
) -> str:
    client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])
    system_prompt = build_system_prompt(policy_text)
    full_messages = [{"role": "system", "content": system_prompt}] + messages

    response = client.chat.completions.create(
        model=model,
        messages=full_messages,
        temperature=0.7,
        max_tokens=400,
    )
    return response.choices[0].message.content
