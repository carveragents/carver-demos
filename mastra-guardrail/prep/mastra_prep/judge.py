"""The shared Judge/Verdict contract (spec §4) — one prompt family, one response
schema, one post-processing algorithm.

`run_judge` is used by prep's curation (always with exactly ONE obligation) and
its six-step post-processing is re-implemented once on the TypeScript side
(`judge/contract.ts::parseAndValidateVerdicts`, §8) for the template's runtime
guardrail (1-5 obligations). Both sides run the identical six steps against the
shared `scoring_golden.json::judge_cases` fixture, so a drift shows up as a red
test on whichever side drifted.

**`confidence` is bounded to [0, 1], and the wire schema is NOT where that bound
is enforced.** `JUDGE_RESPONSE_SCHEMA` declares `{"minimum": 0, "maximum": 1}`
and OpenAI's strict structured outputs ACCEPT those keywords — but (verified
against OpenAI's own structured-outputs guide, §4) they are not structurally
ENFORCED: the model is steered by them, the API does not guarantee them, and
OpenAI's own guidance is to validate independently where strict conformance
matters. It matters here — an out-of-range confidence flows straight into §4's
`is_failure` conjunction (admitting a record) and §9c's abort decision (blocking
a live draft). `parse_and_validate_verdicts` step 3 is therefore the single
authoritative check; the schema is defence in depth, never the proof.

**Discarded, never clamped.** Clamping `5.0 -> 1.0` would silently promote a
malformed response into a MAXIMUM-confidence verdict, sailing past
`judge_confidence_floor` — i.e. clamping fails toward "violation", the one
direction every other degenerate path here is designed to avoid. Discard-then-
fallback fails toward "uncertain", consistently with malformed JSON (step 1) and
omitted ids (step 4).

Intra-package imports: `budget`, `logging_` — both leaves (§1's DAG). `Settings`
is imported under TYPE_CHECKING only: it is used purely as an annotation, and
keeping the runtime edge absent keeps this module cheap to import.
"""
from __future__ import annotations

import json
import math
import time
from pathlib import Path
from typing import TYPE_CHECKING, Literal, TypedDict

from .budget import (
    REASONING_EFFORT,
    BudgetExhausted,
    SpendBudget,
    build_request_payload,
    terminal_for_exception,
)
from .logging_ import log

if TYPE_CHECKING:
    from .config import Settings

PROMPTS_DIR = Path(__file__).resolve().parents[1] / "prompts"

# This call type's own cap (§3's per-call table). Also the completion side of the
# reservation basis, so it must be the value actually sent, never a guess.
JUDGE_MAX_COMPLETION_TOKENS = 1200

# §15's "one retry with exponential backoff (1s)" for an API error. Paid ONLY on
# the API-error path: a malformed-JSON retry is not a transient-network wait, and
# sleeping there would tax the suite for nothing.
RETRY_BACKOFF_SECONDS = 1.0

# §4 step 4's two synthesized rationales. Identical in effect (both fall back to
# uncertain/0.0); distinguishable in the probe log, which is the whole point —
# "the model said nothing" and "the model said something invalid" are different
# facts about the provider, and only one of them is a bug worth chasing.
RATIONALE_OMITTED = "model omitted this obligation from its response"
RATIONALE_OUT_OF_RANGE = "model returned an out-of-range confidence for this obligation"

_VERDICT_VALUES = ("compliant", "violation", "uncertain")

JUDGE_RESPONSE_SCHEMA: dict = {
    "name": "obligation_judge",
    "strict": True,
    "schema": {
        "type": "object",
        "properties": {
            "verdicts": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "obligation_id": {"type": "string"},
                        "applies_to_draft": {"type": "boolean"},
                        "omission_material": {"type": "boolean"},
                        "verdict": {"type": "string", "enum": list(_VERDICT_VALUES)},
                        # DECLARED here, ENFORCED in parse_and_validate_verdicts —
                        # see the module docstring. Both, deliberately.
                        "confidence": {"type": "number", "minimum": 0, "maximum": 1},
                        "rationale": {"type": "string"},
                    },
                    "required": ["obligation_id", "applies_to_draft", "omission_material",
                                 "verdict", "confidence", "rationale"],
                    "additionalProperties": False,
                },
            },
        },
        "required": ["verdicts"],
        "additionalProperties": False,
    },
}


class JudgeObligationInput(TypedDict):
    id: str
    title: str
    key_requirements: list[str]
    objective: str


class JudgeVerdict(TypedDict):
    obligation_id: str
    applies_to_draft: bool     # §4's applicability fix — see score_missed_obligation
    omission_material: bool    # §4's materiality fix
    verdict: Literal["compliant", "violation", "uncertain"]
    confidence: float          # ALWAYS in [0.0, 1.0] — guaranteed by
                               # parse_and_validate_verdicts, never merely
                               # requested by the wire schema
    rationale: str


class JudgeResult(TypedDict):
    verdicts: list[JudgeVerdict]


def run_judge(client, obligations: list[JudgeObligationInput], draft_text: str,
              cfg: "Settings", budget: SpendBudget) -> JudgeResult:
    """Ask the judge about `obligations` against `draft_text` (§4).

    Always takes a LIST — prep passes exactly one element; the template's verdict
    stage passes 1-5. That is the whole point of the shared contract: both halves
    ask the identical question in the identical shape, differing only in batch
    size.

    Follows §3's call lifecycle exactly (build payload once -> reserve THAT dict
    -> unpack the SAME dict into the SDK call -> exactly one terminal operation
    on every path), and §15's retry rule, which fires for two distinct reasons:

      * an API error -> one retry after RETRY_BACKOFF_SECONDS. If the retry also
        fails the exception PROPAGATES: an API error is not evidence about the
        baseline, so the caller (`probe_and_score_one`) records
        disqualified_reason="probe_error" rather than a failure.
      * a malformed-JSON response -> one retry with the same input. If the retry
        is also unparseable, every requested id takes step 4's omission fallback
        ("uncertain") — never "violation".

    `BudgetExhausted` is NEVER retried (§15): it means stop the run, and a retry
    would only re-raise it against an already-refused ceiling.
    """
    requested_ids = [obligation["id"] for obligation in obligations]
    payload = _build_payload(obligations, draft_text, cfg)

    raw_response = ""
    for attempt in (1, 2):
        is_final_attempt = attempt == 2
        try:
            raw_response = _call_judge_once(client, payload, budget)
        except BudgetExhausted:
            raise
        except Exception:
            if is_final_attempt:
                raise
            log(f"judge call failed — retrying once in {RETRY_BACKOFF_SECONDS}s (§15)")
            time.sleep(RETRY_BACKOFF_SECONDS)
            continue
        if is_final_attempt or _parse_verdict_entries(raw_response) is not None:
            break
        log("judge returned unparseable JSON — retrying once (§4 step 1)")

    return parse_and_validate_verdicts(raw_response, requested_ids)


def parse_and_validate_verdicts(raw_response: str, requested_ids: list[str]) -> JudgeResult:
    """§4's six steps — the single authoritative post-processing algorithm.

    1. Parse JSON. On failure every requested_id gets step 4's fallback (the
       CALLER, `run_judge`, is what retries once first).
    2. Index obligation_id -> entry using FIRST occurrence only: a stray
       duplicate never gets to vote twice.
    3. RANGE-VALIDATE confidence — THIS function, not the wire schema, is where
       [0, 1] is actually enforced. An entry whose confidence is not a real
       number in [0.0, 1.0] is DISCARDED and thereafter treated exactly as an
       omission. Deliberately not clamped — see the module docstring.
    4. Every requested id absent from the index (omitted, or discarded by step 3)
       gets verdict="uncertain", confidence=0.0, applies_to_draft=False,
       omission_material=False, and a rationale naming WHICH case fired. Never
       "compliant" (would hide a real risk), never "violation" (would fabricate
       evidence). The two flags default to False so an omitted verdict cannot
       satisfy §4's is_failure conjunction even if a future refactor forgot to
       also check `verdict`.
    5. Entries whose obligation_id is not in requested_ids (hallucinated/stale)
       are dropped silently — this is what stops §9c ever dereferencing an id
       absent from its own candidate set.
    6. Return exactly one verdict per requested id, IN requested_ids ORDER, every
       one carrying a confidence PROVABLY in [0.0, 1.0] — the model's own
       in-range value or step 4's 0.0. That invariant holds no matter what the
       provider returns.
    """
    entries = _parse_verdict_entries(raw_response)

    index: dict[str, dict] = {}
    for entry in entries or []:
        if not isinstance(entry, dict):
            continue
        obligation_id = entry.get("obligation_id")
        if not isinstance(obligation_id, str) or obligation_id not in requested_ids:
            continue                      # step 5
        if obligation_id in index:
            continue                      # step 2 — first occurrence wins
        index[obligation_id] = entry

    # Step 3. Applied AFTER the first-wins index is built, per §4's step order: a
    # duplicate never rescues an out-of-range first entry (it was already dropped
    # as a duplicate), and the discarded id takes the fallback like any omission.
    discarded_ids = {
        obligation_id for obligation_id, entry in index.items()
        if not _is_confidence_in_range(entry.get("confidence"))
    }
    for obligation_id in discarded_ids:
        del index[obligation_id]

    verdicts: list[JudgeVerdict] = []
    for obligation_id in requested_ids:                      # step 6 — requested order
        entry = index.get(obligation_id)
        if entry is None:
            verdicts.append(_fallback_verdict(obligation_id, obligation_id in discarded_ids))
        else:
            verdicts.append(_verdict_from_entry(obligation_id, entry))
    return JudgeResult(verdicts=verdicts)


# ── internals ───────────────────────────────────────────────────────────────

def _build_payload(obligations: list[JudgeObligationInput], draft_text: str,
                   cfg: "Settings") -> dict:
    """§4's substitution table, verbatim: the judge only ever sees obligations and
    a draft — it is scenario-agnostic, so there is no scenario substitution here."""
    obligations_json = json.dumps(
        [{"id": o["id"], "title": o["title"], "key_requirements": o["key_requirements"],
          "objective": o["objective"]} for o in obligations],
        ensure_ascii=False, indent=2,
    )
    user_text = (_load_prompt("judge_user.md")
                 .replace("{{OBLIGATIONS_JSON}}", obligations_json)
                 .replace("{{DRAFT_TEXT}}", draft_text))
    return build_request_payload(
        model=_bare_model_id(cfg.model_router_string),
        system_text=_load_prompt("judge_system.md"),
        user_text=user_text,
        max_completion_tokens=JUDGE_MAX_COMPLETION_TOKENS,
        reasoning_effort=REASONING_EFFORT,
        schema=JUDGE_RESPONSE_SCHEMA,
    )


def _bare_model_id(model_router_string: str) -> str:
    """`openai/gpt-5.6-sol` -> `gpt-5.6-sol`. The SDK's `model=` takes the bare id;
    the `provider/model` form is a Mastra-side convention kept in `config.yaml` so
    both halves' config files read identically (§13's own table: "Stripped of the
    `openai/` prefix and passed as `model=`", and config.yaml says so at the key).
    `config.py` validates the prefix is present, so the strip is unconditional.

    DUPLICATED from `probe.py::_bare_model_id` (its deviation 1), deliberately and
    not by oversight: §1's DAG gives this module's imports as `budget` + `openai`,
    so a `judge -> probe` edge to share one line is the worse trade. Both call
    sites are one `removeprefix` against a constant `config.py` enforces — if a
    third site ever appears, home it in a leaf rather than growing a third copy.
    """
    return model_router_string.removeprefix("openai/")


def _load_prompt(name: str) -> str:
    return (PROMPTS_DIR / name).read_text(encoding="utf-8")


def _call_judge_once(client, payload: dict, budget: SpendBudget) -> str:
    """§3's pinned lifecycle, verbatim. The `else` is load-bearing, not stylistic:
    Python does not route an exception raised in an `else` block to that same
    `try`'s `except` clauses, so a `BudgetPoisoned` out of `settle()` cannot reach
    `terminal_for_exception` and double-terminate an already-terminal handle."""
    reservation = budget.reserve(payload)      # may raise BudgetExhausted -> caller stops
    try:
        response = client.chat.completions.create(**payload)   # the SAME dict, unpacked
    except Exception as exc:
        terminal_for_exception(reservation, exc)
        raise
    else:
        reservation.settle(response.usage.model_dump() if response.usage is not None else None)
    return response.choices[0].message.content or ""


def _parse_verdict_entries(raw_response: str) -> list | None:
    """The parsed `verdicts` array, or None if the response cannot be read as one
    at all (step 1). None is what `run_judge` retries on."""
    try:
        parsed = json.loads(raw_response)
    except (json.JSONDecodeError, TypeError, ValueError):
        return None
    if not isinstance(parsed, dict):
        return None
    verdicts = parsed.get("verdicts")
    return verdicts if isinstance(verdicts, list) else None


def _is_confidence_in_range(value) -> bool:
    """Step 3's actual check. `bool` is rejected explicitly BEFORE the range
    comparison: Python's `isinstance(True, int)` is True and `0.0 <= True <= 1.0`
    is True, so a naive check accepts a boolean and treats it as confidence 1.0 —
    admitting a record on a value the model never validly produced, and diverging
    from TypeScript, where `typeof true === "boolean"` rejects it.

    NaN/Infinity are rejected by `isfinite`, never by the comparison: every
    comparison against NaN is False, so `0.0 <= nan <= 1.0` would silently... not
    pass, but the same trap the other way around (`nan > floor` is False) is why
    this is checked positively rather than by negating a range test.
    """
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return False
    return math.isfinite(value) and 0.0 <= float(value) <= 1.0


def _fallback_verdict(obligation_id: str, was_discarded: bool) -> JudgeVerdict:
    return JudgeVerdict(
        obligation_id=obligation_id,
        applies_to_draft=False,
        omission_material=False,
        verdict="uncertain",
        confidence=0.0,
        rationale=RATIONALE_OUT_OF_RANGE if was_discarded else RATIONALE_OMITTED,
    )


def _verdict_from_entry(obligation_id: str, entry: dict) -> JudgeVerdict:
    """Read an in-range entry into the typed shape.

    Every field but `confidence` is structurally guaranteed by the strict wire
    schema, so the defaults below can only fire against a provider that broke its
    own contract. Each one fails toward "uncertain"/False — never toward
    "violation" — for the same reason step 3 discards rather than clamps.
    """
    verdict = entry.get("verdict")
    return JudgeVerdict(
        obligation_id=obligation_id,
        applies_to_draft=entry.get("applies_to_draft") is True,
        omission_material=entry.get("omission_material") is True,
        verdict=verdict if verdict in _VERDICT_VALUES else "uncertain",
        confidence=float(entry["confidence"]),
        rationale=entry["rationale"] if isinstance(entry.get("rationale"), str) else "",
    )
