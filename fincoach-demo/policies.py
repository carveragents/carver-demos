"""
Policy document management for FinCoach AI demo.

Handles loading v1, generating v2 from enforcement signals via LLM,
and computing structured diffs for display in the admin UI.
"""

import difflib
import logging
import os
from dataclasses import dataclass, field
from pathlib import Path

from openai import OpenAI

logger = logging.getLogger(__name__)

POLICIES_DIR = Path(__file__).parent / "policies"


@dataclass
class DiffLine:
    type: str   # "context" | "added" | "removed" | "header"
    content: str


@dataclass
class PolicyState:
    active_version: str = "v1"
    v1: str = ""
    v2: str = ""
    diff: list[DiffLine] = field(default_factory=list)


# Module-level state
_state = PolicyState()


def load_v1() -> str:
    path = POLICIES_DIR / "v1.md"
    content = path.read_text()
    _state.v1 = content
    return content


def get_active_policy() -> str:
    """Return the currently active policy text."""
    if _state.active_version == "v2" and _state.v2:
        return _state.v2
    if not _state.v1:
        load_v1()
    return _state.v1


def get_state() -> dict:
    return {
        "active_version": _state.active_version,
        "v1": _state.v1,
        "v2": _state.v2,
        "diff": [{"type": d.type, "content": d.content} for d in _state.diff],
    }


def activate_v2() -> None:
    if not _state.v2:
        raise ValueError("v2 has not been generated yet")
    _state.active_version = "v2"
    logger.info("Policy activated: v2")


def reset_to_v1() -> None:
    _state.active_version = "v1"
    _state.v2 = ""
    _state.diff = []
    logger.info("Policy reset to v1")


def generate_v2(enforcement_context: str) -> dict:
    """
    Call the LLM to generate a v2 policy document based on v1 + enforcement signals.
    Computes and stores the diff. Returns the state dict.
    """
    if not _state.v1:
        load_v1()

    client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])

    system = (
        "You are a senior compliance officer at a fintech company. "
        "Your task is to update an AI agent compliance policy based on recent regulatory "
        "enforcement actions. You must:\n"
        "1. Keep the exact same document structure, section numbering, and heading format as v1.\n"
        "2. Modify or strengthen existing clauses where the enforcement actions reveal gaps.\n"
        "3. Add new clauses where the enforcement actions require conduct not addressed in v1.\n"
        "4. For each changed or added clause, append a short inline citation in square brackets, "
        "e.g. [Added per FTC v. Publishing.com, Apr 2026].\n"
        "5. Update the Version to 2.0 and Effective date to today.\n"
        "6. Output ONLY the updated policy document — no explanation, no preamble."
    )

    user = (
        f"Current policy (v1):\n\n{_state.v1}\n\n"
        f"Regulatory enforcement signals that must be addressed:\n\n{enforcement_context}"
    )

    logger.info("Generating policy v2 via LLM...")
    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        temperature=0.2,
        max_tokens=1800,
    )

    v2_text = response.choices[0].message.content.strip()
    _state.v2 = v2_text
    _state.diff = _compute_diff(_state.v1, v2_text)
    logger.info(f"Policy v2 generated ({len(v2_text)} chars, {len(_state.diff)} diff lines)")
    return get_state()


def _compute_diff(v1: str, v2: str) -> list[DiffLine]:
    """
    Compute a line-level unified diff between v1 and v2.
    Returns a list of DiffLine objects for rendering in the UI.
    """
    v1_lines = v1.splitlines(keepends=True)
    v2_lines = v2.splitlines(keepends=True)

    diff_lines: list[DiffLine] = []
    opcodes = difflib.SequenceMatcher(None, v1_lines, v2_lines).get_opcodes()

    for tag, i1, i2, j1, j2 in opcodes:
        if tag == "equal":
            for line in v1_lines[i1:i2]:
                diff_lines.append(DiffLine("context", line.rstrip("\n")))
        elif tag == "replace":
            for line in v1_lines[i1:i2]:
                diff_lines.append(DiffLine("removed", line.rstrip("\n")))
            for line in v2_lines[j1:j2]:
                diff_lines.append(DiffLine("added", line.rstrip("\n")))
        elif tag == "delete":
            for line in v1_lines[i1:i2]:
                diff_lines.append(DiffLine("removed", line.rstrip("\n")))
        elif tag == "insert":
            for line in v2_lines[j1:j2]:
                diff_lines.append(DiffLine("added", line.rstrip("\n")))

    return diff_lines
