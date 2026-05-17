"""
Prompt sanitisation for AmiCompliant.

Two modes:
  - do_it: call the LLM and return the cleaned text
  - give_prompt: return a ready-to-copy meta-prompt pre-filled with the user's text
"""

import os

from openai import OpenAI

_SYSTEM = (
    "You are a privacy and confidentiality editor. "
    "Review the following text and remove all company-specific details: "
    "company names, product names, brand names, proprietary terminology, "
    "internal jargon, named individuals, and specific financial figures tied to a single entity. "
    "Replace each removed item with a neutral placeholder in square brackets, e.g. "
    "[COMPANY], [PRODUCT], [PERSON], [AMOUNT]. "
    "Preserve the structure, intent, and compliance logic of the original text exactly. "
    "Return ONLY the sanitised text — no explanation, no preamble."
)

_META_PROMPT_TEMPLATE = """\
You are a privacy and confidentiality editor.

Review the text below and remove all company-specific details: company names, product names, \
brand names, proprietary terminology, internal jargon, named individuals, and specific financial \
figures tied to a single entity.

Replace each removed item with a neutral placeholder in square brackets, for example:
[COMPANY], [PRODUCT], [PERSON], [AMOUNT]

Preserve the structure, intent, and compliance logic of the original text exactly.
Return ONLY the sanitised text — no explanation, no preamble.

---
{text}
---\
"""


def sanitise_text(text: str) -> str:
    """Call the LLM and return the sanitised version of the text."""
    client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": _SYSTEM},
            {"role": "user", "content": text},
        ],
        temperature=0,
        max_tokens=2000,
    )
    return response.choices[0].message.content.strip()


def build_meta_prompt(text: str) -> str:
    """Return a ready-to-copy prompt the user can paste into any LLM."""
    return _META_PROMPT_TEMPLATE.format(text=text)
