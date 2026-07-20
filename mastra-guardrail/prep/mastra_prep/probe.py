"""Stage A (grounded drafting) and Stage B (grounded citation/date) probes (spec §3).

Both stages run the **same fair-test-legal substitution set** `scenarios.py::
build_task_instance` computes from a record — persona, company, a
`DOMAIN_BUCKETS` phrase, a country/bloc-granularity jurisdiction phrase, and
(Stage B only) `update_type` rendered through a fixed lookup plus a
non-record-derived recency phrase. **Nothing else from the record ever reaches
either prompt** — no title, summary, objective, what_changed, why_it_matters,
key_requirements, penalties_consequences, regulator_name, or any
`critical_dates`/`compliance_date` value. `tests/test_probe.py::
test_task_instance_excludes_leaked_fields` is the fair-test assertion this
buys: the experiment is only a baseline if the baseline was never shown the
answer.

**The call lifecycle is pinned verbatim (spec §3) and both `run_stage_a`/
`run_stage_b` follow it identically**: build the SDK-ready payload once,
`budget.reserve(payload)` (may raise `BudgetExhausted` — the caller stops),
unpack that SAME dict into `client.chat.completions.create`, and terminate the
reservation on every path — `terminal_for_exception` in `except`,
`Reservation.settle(usage)` in `else`. The `else` placement is load-bearing:
Python does not route an `else`-block exception to that `try`'s `except`, so a
`BudgetPoisoned` raised out of `settle()` cannot be double-terminated by
`terminal_for_exception`. The `usage` dict is captured once, inside `else`,
before `settle()` is called, purely so this function can also report
`reasoning_tokens` in its return value after `settle()` succeeds — this is the
same value `settle()` reads, just kept in a name instead of recomputed.

**Two deliberate departures from what a literal reading of §3 gives verbatim,
each because the alternative would be structurally wrong, not a style choice:**

1. **`model=` strips the `openai/` prefix.** `cfg.model_router_string` is
   `"openai/gpt-5.6-sol"` (§13's config value, shared verbatim with the
   template's mirror so both halves' config files read identically per goal
   #9). The OpenAI SDK's `model=` parameter takes the bare id. §13's own table
   states this exactly: "`model_router_string` ... Stripped of the `openai/`
   prefix and passed as `model=`". Done once, here (`_bare_model_id`), at both
   call sites in this module.

2. **This module does NOT import `Settings` from `config.py`.** §1's
   dependency table lists `probe.py`'s dependencies as `openai, scenarios,
   budget` only — not `config`. `cfg` is therefore accepted duck-typed (only
   `.model_router_string` is ever read) and annotated as a bare forward
   reference; `from __future__ import annotations` (PEP 563) makes every
   annotation in this file a string, never evaluated at import time, so no
   runtime import is needed to keep the type hint honest. Importing `config`
   here would add a real edge with no corresponding entry in §1's table for no
   functional benefit — `run_prep.py` is the module that already holds a
   `Settings` instance and passes it through.

**`UPDATE_TYPE_PHRASES` is NOT given verbatim by the spec.** §3 pins three
example mappings ("enforcement" -> "an enforcement action", "guidance" -> "new
guidance", "proposed rule" -> "a proposed rule") and says "one entry per value
in `ACTIONABLE_UPDATE_TYPES`" (§2, 8 values total) — the remaining five
("advisory", "bulletin", "final rule", "comment request", "standard") are
derived here, in the same natural, non-record-leaking register as the three
given, exactly as `scenarios.py::INDUSTRY_TAG_TO_BUCKET` was derived rather
than quoted for the analogous domain-bucket table. Deliberately NOT imported
from `candidates.ACTIONABLE_UPDATE_TYPES` (which would add an edge absent from
§1's dependency table for this module) — `tests/test_probe.py` instead asserts
the two sets agree, so a future edit to either cannot drift silently without a
test going red.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import TypedDict

from .budget import REASONING_EFFORT, SpendBudget, build_request_payload, terminal_for_exception
from .scenarios import ScenarioSpec, build_task_instance

_PROMPTS_DIR = Path(__file__).resolve().parent.parent / "prompts"

_STAGE_A_SYSTEM_TEMPLATE = (_PROMPTS_DIR / "stage_a_system.md").read_text(encoding="utf-8")
_STAGE_A_USER_TEMPLATE = (_PROMPTS_DIR / "stage_a_user.md").read_text(encoding="utf-8")
_STAGE_B_SYSTEM_TEMPLATE = (_PROMPTS_DIR / "stage_b_system.md").read_text(encoding="utf-8")
_STAGE_B_USER_TEMPLATE = (_PROMPTS_DIR / "stage_b_user.md").read_text(encoding="utf-8")

# §3's per-call-type `max_completion_tokens` cap (= the completion reservation
# basis SpendBudget.reserve() holds against the ceiling). Judge's own 1,200 cap
# is judge.py's constant, not this module's.
STAGE_A_MAX_COMPLETION_TOKENS = 3_000
STAGE_B_MAX_COMPLETION_TOKENS = 1_500

# §3's Structured Outputs schema for Stage B, pinned verbatim. `["string",
# "null"]` union types (not `.optional()`-style omission) are deliberate — see
# §8's note on the verified GPT-5-family structured-output bug with optional
# fields; the same discipline applies here even though this is the Chat
# Completions JSON-schema path, not the Agents SDK path where the bug was
# filed, to keep the pattern uniform across both halves.
STAGE_B_RESPONSE_SCHEMA: dict = {
    "name": "stage_b_citation_probe",
    "strict": True,
    "schema": {
        "type": "object",
        "properties": {
            "knows_source": {"type": "boolean"},
            "source_name": {"type": ["string", "null"]},
            "source_url": {"type": ["string", "null"]},
            "compliance_date": {"type": ["string", "null"], "description": "ISO 8601 YYYY-MM-DD or null"},
            "confidence_note": {"type": "string"},
        },
        "required": ["knows_source", "source_name", "source_url", "compliance_date", "confidence_note"],
        "additionalProperties": False,
    },
}

# §3's fixed update_type -> natural-language phrase lookup. See the module
# docstring: three entries are pinned verbatim by the spec, the remaining five
# are derived in the same register. Complete over candidates.ACTIONABLE_UPDATE_TYPES
# (asserted by test_probe.py, not imported here — see the module docstring).
UPDATE_TYPE_PHRASES: dict[str, str] = {
    "enforcement": "an enforcement action",
    "advisory": "a new advisory",
    "guidance": "new guidance",
    "bulletin": "a new bulletin",
    "final rule": "a final rule",
    "proposed rule": "a proposed rule",
    "comment request": "a new comment request",
    "standard": "a new standard",
}

# The bucket used when a record's update_type is somehow absent from
# UPDATE_TYPE_PHRASES. Unreachable in the real pipeline (candidates.py's
# is_candidate() already restricts every probed record's update_type to
# ACTIONABLE_UPDATE_TYPES before it ever reaches curate.py), but run_stage_b
# accepts a bare dict and must not KeyError on a hand-built test/fixture record.
_DEFAULT_UPDATE_TYPE_PHRASE = "a regulatory development"

# §3's fixed literal — deliberately NOT derived from the record's actual date,
# so it cannot leak anything record-specific (the record's own recency is
# already implicit in it being a candidate at all, via §2's cutoff filter).
RECENCY_PHRASE = "in the past few months"


class StageAResult(TypedDict):
    record_id: str
    draft_text: str
    usage: dict  # {prompt_tokens: int, completion_tokens: int, reasoning_tokens: int | None}
    called_at: str  # ISO 8601 datetime


class StageBResult(TypedDict):
    record_id: str
    knows_source: bool
    source_name: str | None
    source_url: str | None
    compliance_date: str | None
    confidence_note: str
    usage: dict
    called_at: str


def _render(template: str, substitutions: dict) -> str:
    """`{{KEY}}` substitution over a prompt template — the same convention
    `scenarios.py::build_task_instance` uses for `TASK_INSTANCE`, applied here
    to the full system/user prompt text. Unused keys in `substitutions` are
    harmless no-ops (no matching placeholder to replace)."""
    rendered = template
    for key, value in substitutions.items():
        rendered = rendered.replace("{{" + key + "}}", value)
    return rendered


def _bare_model_id(model_router_string: str) -> str:
    """Strip the `openai/` router prefix — see the module docstring's
    deviation (1). `model_router_string` is validated by `config.py` to start
    with this exact prefix, so a plain slice is safe; `removeprefix` is a
    no-op (returns the string unchanged) on anything that doesn't carry it."""
    return model_router_string.removeprefix("openai/")


def _iso_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _usage_summary(usage: dict) -> dict:
    """`usage` is the SAME bookable dict just handed to `Reservation.settle()`
    (guaranteed non-None and shape-valid by the time this runs, since an
    unusable report routes `settle()` through `finalize_unusable_usage`, which
    raises before returning here). `reasoning_tokens` is read from
    `completion_tokens_details.reasoning_tokens` when the SDK's `model_dump()`
    included it (GPT-5-family responses expose this breakdown); `None`
    otherwise — reasoning and visible-output tokens are billed at the same
    output rate, so this is retained for audit/reporting only, never for
    accounting."""
    details = usage.get("completion_tokens_details")
    reasoning_tokens = details.get("reasoning_tokens") if isinstance(details, dict) else None
    return {
        "prompt_tokens": usage["prompt_tokens"],
        "completion_tokens": usage["completion_tokens"],
        "reasoning_tokens": reasoning_tokens,
    }


def run_stage_a(client, record: dict, scenario: ScenarioSpec, cfg, budget: SpendBudget) -> StageAResult:
    """The grounded drafting probe (spec §3) — the SAME call shape the guarded
    agent makes at runtime. No output schema: `response.choices[0].message.
    content` (the free-form draft) is captured verbatim as `draft_text`.

    `record` is `extract_record`'s flat shape (`record["artifact_id"]`, never
    `record["id"]` — see `scenarios.py`'s docstring for the same, already-
    documented pseudocode-vs-real-shape disagreement this mirrors).

    Raises whatever `client.chat.completions.create` raises (after routing the
    reservation through `terminal_for_exception`), and `BudgetExhausted`/
    `BudgetPoisoned` from `budget.reserve`/`Reservation.settle`. The caller
    (`curate.py::probe_and_score_one` et al.) is responsible for catching and
    retrying/stopping per §3/§15.
    """
    task = build_task_instance(record, scenario)
    system_text = _render(_STAGE_A_SYSTEM_TEMPLATE, task)
    user_text = _render(_STAGE_A_USER_TEMPLATE, task)

    payload = build_request_payload(
        model=_bare_model_id(cfg.model_router_string),
        system_text=system_text,
        user_text=user_text,
        max_completion_tokens=STAGE_A_MAX_COMPLETION_TOKENS,
        reasoning_effort=REASONING_EFFORT,
        schema=None,
    )
    res = budget.reserve(payload)
    try:
        response = client.chat.completions.create(**payload)
    except Exception as exc:
        terminal_for_exception(res, exc)
        raise
    else:
        usage = response.usage.model_dump() if response.usage is not None else None
        res.settle(usage)

    return {
        "record_id": record["artifact_id"],
        "draft_text": response.choices[0].message.content,
        "usage": _usage_summary(usage),
        "called_at": _iso_now(),
    }


def run_stage_b(client, record: dict, scenario: ScenarioSpec, cfg, budget: SpendBudget) -> StageBResult:
    """The grounded citation & compliance-date probe (spec §3) — OpenAI
    Structured Outputs, strict mode, over `STAGE_B_RESPONSE_SCHEMA`.

    Adds exactly two more fair-test-legal, non-record-leaking signals on top
    of Stage A's substitution set: `UPDATE_TYPE_PHRASE` (record['update_type']
    rendered through the fixed `UPDATE_TYPE_PHRASES` lookup — a coarse
    category shared by hundreds of pool records, never the record's own text)
    and the fixed literal `RECENCY_PHRASE`.

    Same raise contract as `run_stage_a`. `response.choices[0].message.content`
    is parsed as JSON directly — Structured Outputs' strict mode guarantees a
    schema-conforming response, so no retry/repair path lives here (unlike
    Judge's free-form JSON, §4).
    """
    task = build_task_instance(record, scenario)
    update_type = (record.get("update_type") or "").strip().lower()
    substitutions = {
        **task,
        "UPDATE_TYPE_PHRASE": UPDATE_TYPE_PHRASES.get(update_type, _DEFAULT_UPDATE_TYPE_PHRASE),
        "RECENCY_PHRASE": RECENCY_PHRASE,
    }
    system_text = _render(_STAGE_B_SYSTEM_TEMPLATE, substitutions)
    user_text = _render(_STAGE_B_USER_TEMPLATE, substitutions)

    payload = build_request_payload(
        model=_bare_model_id(cfg.model_router_string),
        system_text=system_text,
        user_text=user_text,
        max_completion_tokens=STAGE_B_MAX_COMPLETION_TOKENS,
        reasoning_effort=REASONING_EFFORT,
        schema=STAGE_B_RESPONSE_SCHEMA,
    )
    res = budget.reserve(payload)
    try:
        response = client.chat.completions.create(**payload)
    except Exception as exc:
        terminal_for_exception(res, exc)
        raise
    else:
        usage = response.usage.model_dump() if response.usage is not None else None
        res.settle(usage)

    parsed = json.loads(response.choices[0].message.content)
    return {
        "record_id": record["artifact_id"],
        "knows_source": parsed["knows_source"],
        "source_name": parsed["source_name"],
        "source_url": parsed["source_url"],
        "compliance_date": parsed["compliance_date"],
        "confidence_note": parsed["confidence_note"],
        "usage": _usage_summary(usage),
        "called_at": _iso_now(),
    }
