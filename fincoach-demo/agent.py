"""
Meridian Pay AI support agent.

The system prompt is assembled from:
  1. A fixed platform context (who the agent is and what Meridian Pay does)
  2. The active Layer 4 compliance policy (managed in policies.py)

All compliance behaviour derives from the policy document, so every behaviour
change is traceable to a policy update in a specific deployment layer.
"""

import os
from openai import OpenAI

PLATFORM_CONTEXT = """You are the Meridian Pay customer support assistant. \
Meridian Pay is a consumer fintech company offering prepaid debit cards, \
P2P money transfers, and basic savings accounts.

Your role:
- Help customers and internal teams with account and transaction inquiries
- Look up transaction history and account balances
- Help initiate card replacements and dispute cases
- Answer questions about Meridian Pay products and policies
- Transfer customers to a human specialist when needed

What you do not do:
- You do not give investment, legal, tax, or financial planning advice
- You do not make decisions on credit"""


def build_system_prompt(policy_text: str) -> str:
    return (
        f"{PLATFORM_CONTEXT}\n\n"
        "---\n"
        "COMPLIANCE POLICY — BINDING OPERATING RULES (Layer 4: System Prompt)\n"
        "Every clause below is a hard constraint on your output, not a guideline.\n"
        "- Clauses using SHALL or MUST are mandatory.\n"
        "- Clauses using SHALL NOT or MUST NOT are absolute prohibitions.\n"
        "- Where any clause conflicts with being helpful, the clause wins.\n\n"
        f"{policy_text}\n"
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
