"""The cleared-record schema — the seam between the two halves (spec §5).

**This module defines the literal JSON shape** written by `to_json()`, vendored
verbatim into `template/src/data/cleared-set.json`, and Zod-parsed by
`template/src/schema.ts`. The two halves hand-maintain their own schema objects
(goal #1 forbids `template/` depending on `prep/`), so a key or a type wrong on
either side does not fail loudly — it drifts silently, and surfaces as a demo
that does not fire. Keys are `snake_case` on BOTH sides, deliberately: one fewer
moving part, and the vendored file stays human-readable as shipped.

**A LEAF module** (§1) — it imports nothing from `mastra_prep`. That is
structural: `generate_template_config.py` needs `predicts_stage_a_violation`,
and homing the predicate here (beside the schema it reads) rather than in
`evals/` is what lets §7's generation contract depend on it without depending on
the eval harness.

---

**`jurisdiction` is NESTED here, and this is NOT a D15 violation.**

D15 rules that `extract_record()`'s output is FLAT (top-level
`jurisdiction_country` / `jurisdiction_bloc`), and it is. But that is the
*pipeline* record — the raw annotation, flattened by §2's `FIELD_MAP`, consumed
by `candidates.py` / `scenarios.py` / `scoring.py`. `ClearedRecord` is the
*published* record: a different object, at a later stage, produced by
`review.py::record_signoff`, and pinned **nested** by four independent
authoritative sites:

  * §5's `ClearedRecord` TypedDict — `jurisdiction: dict  # {"scope", "country",
    "bloc", "region_name"}`;
  * §5's Zod mirror — `jurisdiction: z.object({scope, country, bloc, region_name})`;
  * §9a's `jurisdictionMatches` — reads `record.jurisdiction.country`;
  * §8's `firmProfileForRecord` — reads `record.jurisdiction.bloc`.

Flattening it here to "comply" with D15 would break the seam D15 exists to
protect. D15's own words scope it precisely: "*`extract_record()` produces
top-level `jurisdiction_country`*". The published shape is the other end of the
pipeline, and §5 is authoritative over it.

---

**The two things in this module that are load-bearing, and why.**

1. `validate_cleared_record` is the **publication gate**. It runs inside
   `to_json()` before every write. It is the schema-level half of "impossible to
   ship unreviewed" (§6 has the other half) — and a gate that can be bypassed by
   calling the writer directly is not a gate.

2. `predicts_stage_a_violation` is the **single predicate** licensing a "the
   guardrail blocks this draft" expectation. See its docstring; the short
   version is that conflating Stage B knowledge evidence with Stage A draft
   evidence fails in the direction that looks like success.
"""
from __future__ import annotations

from typing import Any, Literal, TypedDict

# ---------------------------------------------------------------------------
# The two closed maps (§5).
# ---------------------------------------------------------------------------

# Only outcomes where is_failure=True ever reach this map (only such dimensions
# become BaselineFailure entries at all — §4's passes_failure_bar), so it is
# exhaustive over "citation_fabricated"/"date_wrong"/"violation" and NOTHING
# else. "citation_missing"/"citation_alternative_real"/"citation_unverifiable"/
# "date_missing"/"date_unparseable"/"date_uncertain_attribution"/
# "not_applicable"/"compliant"/"uncertain" can never appear here because
# is_failure is never True for them.
SCORE_OUTCOME_TO_FAILURE_MODE: dict[str, str] = {
    "citation_fabricated": "citation_fabricated",   # goal #2's "fabricated citation"
    "date_wrong": "date_wrong",                     # goal #2's "wrong compliance date"
    # RENAMED: the scorer's internal literal is "violation" — a generic name the
    # runtime guardrail's verdict stage (§9b) reuses for a live draft — but the
    # shipped dataset's evidence label is the more descriptive "missed_obligation".
    "violation": "missed_obligation",               # goal #2's "missed obligation"
}

# `BaselineFailure.stage` is DERIVED, never set independently, so it can never
# disagree with the mode that produced it. citation_fabricated/date_wrong are
# produced exclusively by Stage B's structured probe; missed_obligation
# exclusively by Stage A's draft + the Judge — disjoint by construction, so
# there is no ambiguous entry and `to_json()` never needs a fallback branch.
STAGE_OF_MODE: dict[str, str] = {
    "citation_fabricated": "B",
    "date_wrong": "B",
    "missed_obligation": "A",
}

# §6's three sub-attestations — the VALIDATOR's list.
#
# `predicts_stage_a_violation` deliberately does NOT read this tuple: it restates
# the three names inline, mirroring §5:2394-2396 and the TypeScript
# `predictsStageAViolation` verbatim. That is the property that matters most in
# this module — the two halves' copies must be diffable against the spec line by
# line — and routing it through a constant would make that check harder, not
# easier. So the names ARE stated twice, on purpose, and
# `test_confirmation_keys_match_the_predicates_inline_names` is what stops them
# drifting. (Naming a constant and then claiming it prevents a drift it does not
# actually prevent is this project's signature defect; this comment previously
# did exactly that.)
CONFIRMATION_KEYS: tuple[str, ...] = (
    "obligation_applies_confirmed",
    "artifact_capable_of_violation_confirmed",
    "omission_materiality_confirmed",
)

# The EXACT top-level key set. Mirrors the TS `.strict()` — no unlisted key, no
# missing key. Explicitly absent, and rejected on sight: `relevance` (any form,
# goal.md), `category`/`class_system`/`class_sector`/`class_leaf`,
# `locality`/`jurisdiction.reasoning`, `human_review.notes`.
CLEARED_RECORD_KEYS: frozenset[str] = frozenset({
    "id", "title", "regulator_name", "jurisdiction", "update_type", "impact_label",
    "objective", "what_changed", "why_it_matters", "key_requirements",
    "compliance_date", "citation", "impacted_business", "impacted_functions",
    "scenario", "baseline_failures", "human_review", "source", "probed_at",
    "model_id", "model_cutoff",
})

BASELINE_FAILURE_KEYS: frozenset[str] = frozenset({
    "mode", "stage", "baseline_response_excerpt", "judge_rationale",
})

HUMAN_REVIEW_KEYS: frozenset[str] = frozenset({
    "reviewer", "reviewed_at", "attestation", *CONFIRMATION_KEYS,
})

JURISDICTION_KEYS: frozenset[str] = frozenset({"scope", "country", "bloc", "region_name"})
CITATION_KEYS: frozenset[str] = frozenset({"name", "url"})
IMPACTED_BUSINESS_KEYS: frozenset[str] = frozenset({"size", "type", "industry"})
SOURCE_KEYS: frozenset[str] = frozenset({"artifact_id", "topic_id", "source_id", "snapshot_date"})

# Pinned literals — mirrored by the TS side's `z.literal(...)`. These are the
# values a drift across the seam would silently change.
IMPACT_LABEL: str = "high"          # by construction (goal #3); typed narrowly on purpose
SNAPSHOT_DATE: str = "2026-07-11"
MODEL_ID: str = "openai/gpt-5.6-sol"
MODEL_CUTOFF: str = "2026-02-16"
ATTESTATION_APPROVED: str = "approved"   # "rejected" never reaches this file at all


# ---------------------------------------------------------------------------
# The shape (§5) — Python TypedDicts, `snake_case` keys as-shipped.
# ---------------------------------------------------------------------------

class BaselineFailure(TypedDict):
    mode: Literal["citation_fabricated", "date_wrong", "missed_obligation"]
    stage: Literal["A", "B"]                  # = STAGE_OF_MODE[mode], always
    baseline_response_excerpt: str            # verbatim (<=1000 chars), never paraphrased
    judge_rationale: str | None               # non-null iff mode == "missed_obligation"


class ClearedRecord(TypedDict):
    id: str                                    # = source artifact_id, non-empty
    title: str                                 # verbatim from extract_record(); never edited (§6)
    regulator_name: str
    jurisdiction: dict                         # {"scope", "country", "bloc", "region_name"}
    update_type: str
    impact_label: Literal["high"]
    objective: str                             # verbatim
    what_changed: str                          # verbatim
    why_it_matters: str                        # verbatim
    key_requirements: list[str]                # verbatim, non-empty (candidate filter guarantee)
    compliance_date: str | None                # ISO 8601 date or null (many legitimately have none)
    citation: dict                             # {"name", "url"} — the ONE reviewer-selected citation
    impacted_business: dict                    # {"size", "type", "industry"}
    impacted_functions: list[str]
    scenario: Literal["A", "B"]
    baseline_failures: list[BaselineFailure]   # >= 1 element, enforced below
    human_review: dict                         # HumanReview (§6)
    source: dict                               # {"artifact_id", "topic_id", "source_id", "snapshot_date"}
    probed_at: str                             # ISO datetime of the probe that produced baseline_failures
    model_id: Literal["openai/gpt-5.6-sol"]
    model_cutoff: Literal["2026-02-16"]


# ---------------------------------------------------------------------------
# predicts_stage_a_violation — §5's one predicate.
# ---------------------------------------------------------------------------

def predicts_stage_a_violation(record: ClearedRecord) -> bool:
    """TRUE iff this record's OWN recorded evidence licenses the expectation:
    "the guardrail blocks a Stage A draft written for this record's scenario."

    Requires (a) missed_obligation evidence — which per STAGE_OF_MODE is the ONLY
    mode produced by judging an actual draft — AND (b) all three of §6's human
    sub-attestations: the obligation applies to the fictional firm/activity, the
    requested artifact is capable of violating it, and the judge's cited omission
    is material in that context.

    (b) is redundant in normal operation: validate_cleared_record() (§5) already
    enforces "missed_obligation in modes => all three confirmations are True
    (never None, never False)", so any SHIPPED record with missed_obligation
    evidence necessarily carries them. It is re-checked anyway, for the same
    reason score_missed_obligation re-checks is_eligible: this predicate gates the
    live demo and the headline scoreboard number, and it must not silently depend
    on a validator elsewhere having run.

    WHY THIS EXISTS — do not widen it. A record admitted SOLELY for
    `citation_fabricated` or `date_wrong` proves a Stage B KNOWLEDGE failure: the
    baseline does not know this regulation. That is a perfectly good cleared
    record. It proves NOTHING about whether a *draft* written for that scenario
    violates the obligation, so it does not predict the guardrail will block.
    Expecting a block anyway makes the live demo and the guarded scoreboard fail
    **while the system behaves exactly as its own curated evidence says it
    should** — sending an implementer to hunt a bug that does not exist, in a
    template whose entire purpose is to be trusted at a glance. That is the most
    dangerous error available in this design, because it fails in the direction
    that looks like success.
    """
    modes = {f["mode"] for f in record["baseline_failures"]}
    if "missed_obligation" not in modes:
        return False
    hr = record["human_review"]
    return (hr["obligation_applies_confirmed"] is True
            and hr["artifact_capable_of_violation_confirmed"] is True
            and hr["omission_materiality_confirmed"] is True)


# ---------------------------------------------------------------------------
# validate_cleared_record — the publication gate.
# ---------------------------------------------------------------------------

def _check_key_set(obj: Any, expected: frozenset[str], where: str, errors: list[str]) -> bool:
    """Exact key-set check, mirroring the TS `.strict()` + required-keys pair.

    Returns False (and records why) if `obj` is not a dict or its keys differ,
    so callers can skip dependent checks rather than raise a TypeError out of a
    function whose contract is to RETURN its complaints.
    """
    if not isinstance(obj, dict):
        errors.append(f"{where}: expected an object, got {type(obj).__name__}")
        return False
    ok = True
    for key in sorted(set(obj) - expected):
        errors.append(f"{where}: unlisted key {key!r} (§5 pins the exact key set)")
        ok = False
    for key in sorted(expected - set(obj)):
        errors.append(f"{where}: missing required key {key!r}")
        ok = False
    return ok


def _check_str_list(value: Any, where: str, errors: list[str], *, min_len: int = 0) -> None:
    if not isinstance(value, list) or not all(isinstance(v, str) for v in value):
        errors.append(f"{where}: expected a list of strings")
        return
    if len(value) < min_len:
        errors.append(f"{where}: must have at least {min_len} element(s), got {len(value)}")


def _validate_baseline_failures(record: dict, errors: list[str]) -> None:
    failures = record.get("baseline_failures")
    if not isinstance(failures, list):
        errors.append("baseline_failures: expected a list")
        return
    # Rejection mode 1 — a record with no evidence is exactly what goal #2
    # forbids shipping ("A record enters the set ONLY with recorded evidence").
    if not failures:
        errors.append(
            "baseline_failures: must have >= 1 element — a record with no recorded "
            "baseline-failure evidence must never ship (goal #2)"
        )
        return

    for i, failure in enumerate(failures):
        where = f"baseline_failures[{i}]"
        if not _check_key_set(failure, BASELINE_FAILURE_KEYS, where, errors):
            continue

        mode = failure["mode"]
        if mode not in STAGE_OF_MODE:
            errors.append(
                f"{where}.mode: {mode!r} is not one of goal #2's three named modes "
                f"{sorted(STAGE_OF_MODE)}"
            )
            continue

        # Rejection mode 2 — `stage` is DERIVED (§5). A disagreement means the
        # record is claiming a stage produced evidence that stage cannot produce.
        expected_stage = STAGE_OF_MODE[mode]
        if failure["stage"] != expected_stage:
            errors.append(
                f"{where}.stage: {failure['stage']!r} disagrees with "
                f"STAGE_OF_MODE[{mode!r}] == {expected_stage!r} — stage is derived, "
                f"never set independently (§5)"
            )

        if not isinstance(failure["baseline_response_excerpt"], str):
            errors.append(f"{where}.baseline_response_excerpt: expected a string")

        # §5: judge_rationale is non-null IFF mode == "missed_obligation" — there
        # is no judge involved in producing a citation_*/date_* mode, so a
        # rationale on one is evidence that never existed.
        rationale = failure["judge_rationale"]
        if mode == "missed_obligation":
            if not isinstance(rationale, str):
                errors.append(
                    f"{where}.judge_rationale: must be non-null for "
                    f"mode='missed_obligation' (it is the judge's own rationale)"
                )
        elif rationale is not None:
            errors.append(
                f"{where}.judge_rationale: must be null for mode={mode!r} — no judge "
                f"is involved in producing a citation_*/date_* mode (§5)"
            )


def _validate_human_review(record: dict, errors: list[str]) -> None:
    hr = record.get("human_review")
    if not _check_key_set(hr, HUMAN_REVIEW_KEYS, "human_review", errors):
        return

    if not isinstance(hr["reviewer"], str) or not hr["reviewer"].strip():
        errors.append("human_review.reviewer: expected a non-empty string")
    if not isinstance(hr["reviewed_at"], str) or not hr["reviewed_at"].strip():
        errors.append("human_review.reviewed_at: expected a non-empty ISO datetime string")

    # Rejection mode 3 — the attestation. Exactly "approved", never a case
    # variant, never a truthy stand-in. "rejected" never reaches this file at
    # all (§5); a rejection's reason lives only in data/scratch/.
    if hr["attestation"] != ATTESTATION_APPROVED:
        errors.append(
            f"human_review.attestation: must be exactly {ATTESTATION_APPROVED!r}, got "
            f"{hr['attestation']!r} — human review is the publication gate (goal #11)"
        )

    for key in CONFIRMATION_KEYS:
        if hr[key] not in (True, False, None):
            errors.append(f"human_review.{key}: expected true, false or null")

    # Rejection mode 4 — the three-confirmation conjunction. This is what makes
    # predicts_stage_a_violation's clause (b) redundant for SHIPPED records, and
    # therefore what makes a Stage A expectation trustworthy at all.
    failures = record.get("baseline_failures")
    if isinstance(failures, list):
        modes = {f["mode"] for f in failures if isinstance(f, dict) and "mode" in f}
        if "missed_obligation" in modes:
            for key in CONFIRMATION_KEYS:
                if hr[key] is not True:
                    errors.append(
                        f"human_review.{key}: must be true (never false, never null) for a "
                        f"record carrying missed_obligation evidence — all three of §6's "
                        f"sub-attestations are required, got {hr[key]!r}"
                    )
        else:
            # The three questions are only ASKED when missed_obligation is among
            # the modes (§6, review.py::ask_obligation_confirmations returns None
            # otherwise). A `True` here would be an attestation nobody made.
            for key in CONFIRMATION_KEYS:
                if hr[key] is not None:
                    errors.append(
                        f"human_review.{key}: must be null for a record with no "
                        f"missed_obligation evidence — the three confirmations are only "
                        f"asked when that evidence exists (§6), got {hr[key]!r}"
                    )


def validate_cleared_record(obj: dict) -> tuple[bool, list[str]]:
    """Return `(is_valid, errors)` for a candidate cleared record (§5).

    **Never raises** — it returns its complaints, so `review.py` can show a
    reviewer everything wrong at once and `to_json()` can turn the list into one
    informative failure. Errors ACCUMULATE rather than short-circuit: a gate that
    reveals one problem per run is a worse gate.

    Rejects, each independently and each covered by its own test:
      * an empty `baseline_failures` (goal #2 — no evidence, no record);
      * a `human_review.attestation` other than exactly `"approved"`;
      * a broken three-confirmation conjunction (missed_obligation evidence
        without all three of §6's sub-attestations `True`);
      * an unlisted top-level key (mirrors the TS `.strict()`);
      * a `BaselineFailure` whose `stage` disagrees with `STAGE_OF_MODE[mode]`.

    It additionally enforces the rest of §5's pinned shape — missing keys, the
    `impact_label`/`model_id`/`model_cutoff`/`snapshot_date` literals, the
    `judge_rationale` iff-rule, and the nested objects' own key sets. §5's list of
    rejections is a floor on what must be caught, not a ceiling on what may be:
    every addition here fails CLOSED (it rejects a malformed record rather than
    shipping one), and each mirrors a constraint the TS Zod schema already
    enforces on the other side of the seam.
    """
    errors: list[str] = []

    # A non-dict must return, not fall through: every check below is `key in obj`,
    # which raises TypeError for None/int/float/bool — breaking this function's
    # "never raises" contract AND to_json's documented `Raises: ValueError`. It is
    # reachable: a data/cleared/*.json holding `[null]` (a truncated write, a bad
    # merge) would make the clearance gate die with an unrelated traceback instead
    # of naming the offending record.
    if not isinstance(obj, dict):
        return (False, [f"record: expected an object, got {type(obj).__name__}"])

    # Key-set problems are reported; dependent checks below still run on whatever
    # IS present, so one typo does not mask five real errors.
    _check_key_set(obj, CLEARED_RECORD_KEYS, "record", errors)

    for key in ("id", "title", "regulator_name", "update_type", "objective",
                "what_changed", "why_it_matters", "probed_at"):
        if key in obj and (not isinstance(obj[key], str) or not obj[key].strip()):
            errors.append(f"{key}: expected a non-empty string")

    if "impact_label" in obj and obj["impact_label"] != IMPACT_LABEL:
        errors.append(
            f"impact_label: must be exactly {IMPACT_LABEL!r} — every shipped record is "
            f"high-impact by construction (goal #3), got {obj['impact_label']!r}"
        )
    if "model_id" in obj and obj["model_id"] != MODEL_ID:
        errors.append(f"model_id: must be exactly {MODEL_ID!r}, got {obj['model_id']!r}")
    if "model_cutoff" in obj and obj["model_cutoff"] != MODEL_CUTOFF:
        errors.append(f"model_cutoff: must be exactly {MODEL_CUTOFF!r}, got {obj['model_cutoff']!r}")
    if "scenario" in obj and obj["scenario"] not in ("A", "B"):
        errors.append(f"scenario: must be 'A' or 'B', got {obj['scenario']!r}")

    if "key_requirements" in obj:
        _check_str_list(obj["key_requirements"], "key_requirements", errors, min_len=1)
    if "impacted_functions" in obj:
        _check_str_list(obj["impacted_functions"], "impacted_functions", errors)

    if "compliance_date" in obj and not isinstance(obj["compliance_date"], (str, type(None))):
        errors.append("compliance_date: expected an ISO 8601 date string or null")

    if "jurisdiction" in obj and _check_key_set(
        obj["jurisdiction"], JURISDICTION_KEYS, "jurisdiction", errors
    ):
        j = obj["jurisdiction"]
        if not isinstance(j["scope"], str):
            errors.append("jurisdiction.scope: expected a string")
        for key in ("country", "bloc", "region_name"):
            if not isinstance(j[key], (str, type(None))):
                errors.append(f"jurisdiction.{key}: expected a string or null")

    if "citation" in obj and _check_key_set(obj["citation"], CITATION_KEYS, "citation", errors):
        for key in ("name", "url"):
            if not isinstance(obj["citation"][key], str) or not obj["citation"][key].strip():
                errors.append(f"citation.{key}: expected a non-empty string")
        # The seam's ONE place where the TS side was stricter than this gate: §5's
        # Zod mirror types this `z.string().url()`, and §11's HTML report re-checks
        # the scheme "defensively" on the stated grounds that "§5's schema already
        # guarantees this". Prep-side, nothing did — so `"not-a-url"` would pass
        # to_json, get vendored, and only fail at the TS CI one hop later. Goal #8
        # ("Every citation URL in the cleared set resolves") cannot even be
        # attempted against a string that is not a URL.
        url = obj["citation"].get("url")
        if isinstance(url, str) and url.strip() and not url.startswith(("http://", "https://")):
            errors.append(
                f"citation.url: must be an http(s) URL (the TS mirror types this "
                f"z.string().url(); a citation that cannot be fetched cannot be "
                f"shown to resolve — goal #8), got {url!r}"
            )

    if "impacted_business" in obj and _check_key_set(
        obj["impacted_business"], IMPACTED_BUSINESS_KEYS, "impacted_business", errors
    ):
        for key in sorted(IMPACTED_BUSINESS_KEYS):
            _check_str_list(obj["impacted_business"][key], f"impacted_business.{key}", errors)

    if "source" in obj and _check_key_set(obj["source"], SOURCE_KEYS, "source", errors):
        for key in ("artifact_id", "topic_id", "source_id"):
            if not isinstance(obj["source"][key], str) or not obj["source"][key].strip():
                errors.append(f"source.{key}: expected a non-empty string")
        if obj["source"]["snapshot_date"] != SNAPSHOT_DATE:
            errors.append(
                f"source.snapshot_date: must be exactly {SNAPSHOT_DATE!r}, got "
                f"{obj['source']['snapshot_date']!r}"
            )

    if "baseline_failures" in obj:
        _validate_baseline_failures(obj, errors)
    if "human_review" in obj:
        _validate_human_review(obj, errors)

    return (not errors, errors)


# ---------------------------------------------------------------------------
# to_json — the write path. Validation is INSIDE it.
# ---------------------------------------------------------------------------

def to_json(record: ClearedRecord) -> dict:
    """Return the JSON-ready dict for `record` — the literal shape §5 pins.

    **Validates first, and raises on failure.** This is deliberate and is the
    point of the function: `validate_cleared_record` runs here, before every
    write, so there is no code path that emits an unreviewed or malformed record.
    A gate a caller can skip by reaching for the writer directly is not a gate —
    and "impossible to ship unreviewed" has to be true by construction, not by
    every caller remembering.

    Returns a deep copy, so a caller mutating the result cannot retroactively
    invalidate what was validated (and so the record handed in is never touched).

    NOTE ON SERIALIZATION: this returns a dict, not text. Callers writing it out
    MUST use `ensure_ascii=False` (D11) — the wire is UTF-8, and escaping
    non-ASCII would both inflate the byte count and ship `\\uXXXX` soup into a
    file §5 requires to stay human-readable as vendored.

    Raises:
        ValueError: if `record` fails `validate_cleared_record`, with every
            complaint named (not just the first).
    """
    ok, errors = validate_cleared_record(record)  # type: ignore[arg-type]
    if not ok:
        raise ValueError(
            "refusing to serialize an invalid cleared record — "
            f"{len(errors)} problem(s): " + "; ".join(errors)
        )
    return _deep_copy(record)  # type: ignore[arg-type]


def _deep_copy(obj: Any) -> Any:
    """Structural deep copy over the JSON types §5's shape is built from.

    `copy.deepcopy` would do this, but this stays explicit about the fact that a
    ClearedRecord is pure JSON — there is nothing here to copy that json.dump
    could not write.
    """
    if isinstance(obj, dict):
        return {k: _deep_copy(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_deep_copy(v) for v in obj]
    return obj
