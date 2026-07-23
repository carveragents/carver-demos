"""`schema.py` — the seam (spec §5).

**Why this file is unusually paranoid.** `schema.py`'s JSON shape is vendored
verbatim into `template/src/data/cleared-set.json` and Zod-parsed on the other
side of the language boundary. A key or a type wrong here does not fail loudly:
the two halves drift silently, and the drift surfaces as a demo that does not
fire. So every one of `validate_cleared_record`'s five rejection modes is
asserted INDIVIDUALLY (a validator that rejects everything would pass a single
"invalid input is rejected" test just as well as a correct one), and
`predicts_stage_a_violation` is asserted at the boundary that matters, not only
at its two easy ends.

**`ClearedRecord.jurisdiction` is NESTED, and that is not a D15 violation.**
D15 rules that `extract_record()`'s output is FLAT (`jurisdiction_country`),
and it is — that is the *pipeline* record. `ClearedRecord` is the *published*
record: a different object, at a different stage, pinned NESTED by §5's
TypedDict (`jurisdiction: dict`), by §5's Zod mirror (`z.object({scope, country,
bloc, region_name})`), by §9a's `jurisdictionMatches` and by
`firmProfileForRecord`. Flattening it here to "comply" with D15 would break the
seam D15 exists to protect. `review.py::record_signoff` is what converts one
shape into the other.
"""
from __future__ import annotations

import copy
import inspect
import json
from pathlib import Path

import pytest

from mastra_prep.schema import (
    CONFIRMATION_KEYS,
    SCORE_OUTCOME_TO_FAILURE_MODE,
    STAGE_OF_MODE,
    predicts_stage_a_violation,
    to_json,
    validate_cleared_record,
)

FIXTURES = Path(__file__).parent / "fixtures"


# ---------------------------------------------------------------------------
# Builders — a VALID record, and the mutations that must each be rejected.
# ---------------------------------------------------------------------------

def _valid_record() -> dict:
    """A minimal record that `validate_cleared_record` must ACCEPT.

    Every rejection test below is this record with exactly ONE thing changed,
    so a failure names the rule that broke rather than "something is wrong".
    """
    return {
        "id": "art-0001",
        "title": "Guidelines on automated decision-making transparency",
        "regulator_name": "Malta Financial Services Authority",
        "jurisdiction": {
            "scope": "national",
            "country": "MT",
            "bloc": "EU",
            "region_name": None,
        },
        "update_type": "guidance",
        "impact_label": "high",
        "objective": "Set transparency expectations for automated decisions.",
        "what_changed": "New disclosure obligation for profiling systems.",
        "why_it_matters": "Affects any firm deploying automated profiling.",
        "key_requirements": ["Disclose the logic involved in automated decisions."],
        "compliance_date": "2026-09-01",
        "citation": {
            "name": "MFSA Guidance Note 04/2026",
            "url": "https://www.mfsa.mt/guidance-04-2026",
        },
        "impacted_business": {
            "size": ["medium", "large"],
            "type": ["credit institution"],
            "industry": ["Artificial Intelligence"],
        },
        "impacted_functions": ["Compliance", "Engineering"],
        "scenario": "A",
        "baseline_failures": [
            {
                "mode": "missed_obligation",
                "stage": "A",
                "baseline_response_excerpt": "We're excited to announce our new feature...",
                "judge_rationale": "The draft omits the required disclosure of decision logic.",
            }
        ],
        "human_review": {
            "reviewer": "achint",
            "reviewed_at": "2026-07-16T10:00:00Z",
            "attestation": "approved",
            "obligation_applies_confirmed": True,
            "artifact_capable_of_violation_confirmed": True,
            "omission_materiality_confirmed": True,
        },
        "source": {
            "artifact_id": "art-0001",
            "topic_id": "topic-77",
            "source_id": "src-12",
            "snapshot_date": "2026-07-11",
        },
        "probed_at": "2026-07-15T09:30:00Z",
        "model_id": "openai/gpt-5.6-sol",
        "model_cutoff": "2026-02-16",
    }


def _citation_only_record() -> dict:
    """A record admitted SOLELY on Stage B knowledge evidence.

    This is a perfectly good cleared record — it proves the baseline does not
    know this regulation. It proves NOTHING about whether a Stage A draft
    violates the obligation, which is the whole point of
    `predicts_stage_a_violation`.
    """
    record = _valid_record()
    record["baseline_failures"] = [
        {
            "mode": "citation_fabricated",
            "stage": "B",
            "baseline_response_excerpt": (
                "source_name='MFSA Circular 12/2026' "
                "source_url='https://www.mfsa.mt/circular-12-2026' "
                "compliance_date='2026-09-01'"
            ),
            "judge_rationale": None,
        }
    ]
    # §6: the three confirmations are only ASKED when missed_obligation is among
    # the modes; a Stage-B-only record carries None for all three.
    record["human_review"].update(
        obligation_applies_confirmed=None,
        artifact_capable_of_violation_confirmed=None,
        omission_materiality_confirmed=None,
    )
    return record


# ---------------------------------------------------------------------------
# The happy path — asserted FIRST, so a validator that rejects everything
# cannot pass the five rejection tests below and look correct.
# ---------------------------------------------------------------------------

def test_valid_record_is_accepted():
    ok, errors = validate_cleared_record(_valid_record())
    assert ok is True
    assert errors == []


def test_citation_only_record_is_also_valid():
    """A Stage-B-only record is VALID — it just does not license a Stage A
    expectation (see `test_predicts_stage_a_violation_*` below). Conflating
    "not valid" with "does not predict a block" is the error §5 names as the
    most dangerous available in this design."""
    ok, errors = validate_cleared_record(_citation_only_record())
    assert ok is True
    assert errors == []


# ---------------------------------------------------------------------------
# validate_cleared_record — the publication gate. Five rejection modes,
# each asserted on its own (§5:2482-2486).
# ---------------------------------------------------------------------------

def test_rejects_empty_baseline_failures():
    record = _valid_record()
    record["baseline_failures"] = []
    ok, errors = validate_cleared_record(record)
    assert ok is False
    assert any("baseline_failures" in e for e in errors)


@pytest.mark.parametrize("attestation", ["rejected", "pending", "APPROVED", "", None])
def test_rejects_attestation_other_than_approved(attestation):
    """Exactly `"approved"` — never a case variant, never a truthy stand-in.
    This is the schema-level half of "impossible to ship unreviewed"."""
    record = _valid_record()
    record["human_review"]["attestation"] = attestation
    ok, errors = validate_cleared_record(record)
    assert ok is False
    assert any("attestation" in e for e in errors)


def test_rejects_unlisted_top_level_key():
    record = _valid_record()
    record["relevance"] = 0.9  # the one field goal.md forbids surfacing, ever
    ok, errors = validate_cleared_record(record)
    assert ok is False
    assert any("relevance" in e for e in errors)


def test_rejects_stage_disagreeing_with_stage_of_mode():
    """`stage` is DERIVED (§5) — a record asserting `missed_obligation` at
    stage "B" is claiming Stage B produced draft evidence, which no scorer can
    do. It must never reach the file."""
    record = _valid_record()
    record["baseline_failures"][0]["stage"] = "B"  # mode is missed_obligation -> "A"
    ok, errors = validate_cleared_record(record)
    assert ok is False
    assert any("stage" in e for e in errors)


def test_rejects_broken_three_confirmation_conjunction():
    """§5: "missed_obligation in modes => all three confirmations are True
    (never None, never False)". Asserted for EACH of the three keys and for
    BOTH falsy values — a validator checking only one key, or only `False`,
    passes a single-case test and ships a half-reviewed record."""
    for key in (
        "obligation_applies_confirmed",
        "artifact_capable_of_violation_confirmed",
        "omission_materiality_confirmed",
    ):
        for bad in (False, None):
            record = _valid_record()
            record["human_review"][key] = bad
            ok, errors = validate_cleared_record(record)
            assert ok is False, f"{key}={bad!r} must be rejected"
            assert any(key in e for e in errors), f"{key}={bad!r}: {errors}"


@pytest.mark.parametrize("url", ["not-a-url", "www.mfsa.mt/x", "ftp://mfsa.mt/x", "javascript:alert(1)"])
def test_rejects_a_citation_url_that_is_not_http(url):
    """The seam's one place where the TS side was stricter than this gate: §5's
    Zod mirror types this `z.string().url()`. A citation that cannot be fetched
    cannot be shown to resolve — and goal #8 requires every shipped citation URL
    to resolve."""
    record = _valid_record()
    record["citation"]["url"] = url
    ok, errors = validate_cleared_record(record)
    assert ok is False
    assert any("citation.url" in e for e in errors)


@pytest.mark.parametrize("bad", [None, 1, 3.14, True, "a string", [], ["approved"]])
def test_validate_never_raises_on_non_record_input(bad):
    """The contract is "never raises — it returns its complaints". It is reachable:
    a `data/cleared/*.json` holding `[null]` (truncated write, bad merge) must make
    the clearance gate NAME the offender, not die with an unrelated TypeError."""
    ok, errors = validate_cleared_record(bad)
    assert ok is False
    assert errors


@pytest.mark.parametrize("bad", [None, 1, "a string", []])
def test_to_json_raises_value_error_not_type_error_on_junk(bad):
    """`to_json`'s documented contract is `Raises: ValueError`. A TypeError
    escaping it would be an undocumented failure mode in the write path."""
    with pytest.raises(ValueError):
        to_json(bad)


def test_rejects_missing_required_key():
    record = _valid_record()
    del record["citation"]
    ok, errors = validate_cleared_record(record)
    assert ok is False
    assert any("citation" in e for e in errors)


def test_errors_accumulate_rather_than_short_circuit():
    """A reviewer fixing one problem at a time, learning of the next only after
    re-running, is a worse gate than one that reports all of them."""
    record = _valid_record()
    record["baseline_failures"] = []
    record["human_review"]["attestation"] = "rejected"
    record["extra_key"] = 1
    ok, errors = validate_cleared_record(record)
    assert ok is False
    assert len(errors) >= 3


# ---------------------------------------------------------------------------
# predicts_stage_a_violation — the single predicate licensing a "the guardrail
# blocks this draft" expectation (§5:2348-2397).
# ---------------------------------------------------------------------------

def test_predicts_stage_a_violation_false_for_citation_only():
    """THE case this predicate exists for. A record admitted solely on
    `citation_fabricated` proves a Stage B KNOWLEDGE failure — not that its
    Stage A draft violates the obligation."""
    assert predicts_stage_a_violation(_citation_only_record()) is False


def test_predicts_stage_a_violation_false_for_date_only():
    record = _citation_only_record()
    record["baseline_failures"][0]["mode"] = "date_wrong"
    assert predicts_stage_a_violation(record) is False


def test_predicts_stage_a_violation_true_for_confirmed_missed_obligation():
    assert predicts_stage_a_violation(_valid_record()) is True


@pytest.mark.parametrize(
    "key",
    [
        "obligation_applies_confirmed",
        "artifact_capable_of_violation_confirmed",
        "omission_materiality_confirmed",
    ],
)
@pytest.mark.parametrize("bad", [False, None])
def test_predicts_stage_a_violation_false_when_any_confirmation_not_true(key, bad):
    """The boundary that matters. §5 calls (b) "redundant in normal operation"
    and re-checks it anyway — so it must actually be checked. Note these inputs
    would be REJECTED by validate_cleared_record; the predicate must not
    silently depend on that validator having run."""
    record = _valid_record()
    record["human_review"][key] = bad
    assert predicts_stage_a_violation(record) is False


def test_predicts_stage_a_violation_true_for_mixed_evidence():
    """A record carrying BOTH Stage B and confirmed Stage A evidence still
    predicts a block — the predicate requires missed_obligation to be present,
    not to be the only mode."""
    record = _valid_record()
    record["baseline_failures"].append(
        {
            "mode": "citation_fabricated",
            "stage": "B",
            "baseline_response_excerpt": "source_name='X' source_url='https://x/' compliance_date=None",
            "judge_rationale": None,
        }
    )
    assert predicts_stage_a_violation(record) is True


def test_confirmation_keys_match_the_predicates_inline_names():
    """`predicts_stage_a_violation` deliberately restates the three confirmation
    names inline (mirroring §5:2394-2396 and the TS mirror verbatim) rather than
    reading `CONFIRMATION_KEYS`. That is the right call — the two halves' copies
    must stay diffable against the spec line by line — but it means the names
    live in two places, and nothing but this test stops them drifting."""
    source = inspect.getsource(predicts_stage_a_violation)
    for key in CONFIRMATION_KEYS:
        assert key in source, (
            f"{key!r} is in CONFIRMATION_KEYS but not in predicts_stage_a_violation's "
            f"body — the validator's list and the predicate have drifted"
        )
    assert set(CONFIRMATION_KEYS) == {
        "obligation_applies_confirmed",
        "artifact_capable_of_violation_confirmed",
        "omission_materiality_confirmed",
    }


# ---------------------------------------------------------------------------
# to_json — validation is INSIDE it, before every write.
# ---------------------------------------------------------------------------

def test_to_json_returns_the_pinned_shape():
    out = to_json(_valid_record())
    assert out == _valid_record()


def test_to_json_refuses_an_invalid_record():
    """The gate. If `to_json` could be talked into emitting an unvalidated
    record, "impossible to ship unreviewed" would be a comment, not a
    mechanism."""
    record = _valid_record()
    record["human_review"]["attestation"] = "rejected"
    with pytest.raises(ValueError) as exc:
        to_json(record)
    assert "attestation" in str(exc.value)


def test_to_json_does_not_mutate_its_input():
    record = _valid_record()
    before = copy.deepcopy(record)
    to_json(record)
    assert record == before


def test_to_json_round_trips_a_non_latin_regulator_name():
    """`ensure_ascii=False` throughout — the wire is UTF-8 (D11). Escaping
    non-ASCII would ship `\\uXXXX` soup into a file the spec requires to be
    human-readable as vendored."""
    record = _valid_record()
    record["regulator_name"] = "금융감독원"  # Korea's FSS — goal.md's own long-tail example
    record["title"] = "전자금융거래 안내"
    out = to_json(record)
    text = json.dumps(out, ensure_ascii=False)
    assert "금융감독원" in text
    assert "\\u" not in text
    assert json.loads(text)["regulator_name"] == "금융감독원"


# ---------------------------------------------------------------------------
# The two closed maps (§5:2313-2346).
# ---------------------------------------------------------------------------

def test_score_outcome_to_failure_mode_is_the_closed_three_entry_map():
    assert SCORE_OUTCOME_TO_FAILURE_MODE == {
        "citation_fabricated": "citation_fabricated",
        "date_wrong": "date_wrong",
        "violation": "missed_obligation",
    }


@pytest.mark.parametrize(
    "model_id",
    [
        "openai/gpt-5.6",            # D17 — the ALIAS. Rejected: an alias's target changes,
                                      # and a knowledge cutoff is a property of a MODEL, not of
                                      # a name that currently points at one.
        "openai/gpt-5.6-turbo",
        "anthropic/claude-opus-4-8",  # goal #9 — the Anthropic API is out of scope, full stop
        "",
    ],
)
def test_rejects_any_model_id_other_than_the_explicit_pinned_one(model_id):
    """The controlled experiment's basis (goal #9): baseline and guarded MUST be
    the identical model. A record carrying a different `model_id` — including
    the bare ALIAS D17 forbids — is evidence about a different model, and
    admitting it would silently turn Carver's claim into a model comparison."""
    record = _valid_record()
    record["model_id"] = model_id
    ok, errors = validate_cleared_record(record)
    assert ok is False
    assert any("model_id" in e for e in errors)


def test_rejects_a_model_cutoff_other_than_the_pinned_one():
    """`model_cutoff` is what makes the recency claim falsifiable. A record whose
    cutoff disagrees with the pinned model's documented one is unauditable."""
    record = _valid_record()
    record["model_cutoff"] = "2026-06-01"
    ok, errors = validate_cleared_record(record)
    assert ok is False
    assert any("model_cutoff" in e for e in errors)


def test_stage_of_mode_is_closed_and_covers_every_failure_mode():
    assert STAGE_OF_MODE == {
        "citation_fabricated": "B",
        "date_wrong": "B",
        "missed_obligation": "A",
    }
    # Round-trip: every mode the outcome map can PRODUCE has a stage. Without
    # this, a fourth outcome could be added to one map and not the other.
    assert set(SCORE_OUTCOME_TO_FAILURE_MODE.values()) == set(STAGE_OF_MODE)


# ---------------------------------------------------------------------------
# The clearance gate over the real deliverable directory.
# ---------------------------------------------------------------------------

def test_no_unreviewed_records_in_cleared_dir():
    """Every record in `data/cleared/` validates — i.e. carries evidence and an
    `"approved"` attestation. Vacuously true until Phase 8 vendors real records;
    it is here so it fires the moment one lands, not after."""
    cleared_dir = Path(__file__).resolve().parents[1] / "data" / "cleared"
    if not cleared_dir.is_dir():
        pytest.skip("data/cleared/ does not exist yet (Phase 8 creates it)")

    offenders: list[str] = []
    for path in sorted(cleared_dir.glob("*.json")):
        payload = json.loads(path.read_text(encoding="utf-8"))
        records = payload if isinstance(payload, list) else [payload]
        for record in records:
            ok, errors = validate_cleared_record(record)
            if not ok:
                offenders.append(f"{path.name}:{record.get('id', '?')}: {errors}")
    assert not offenders, f"unreviewed/invalid records in data/cleared/: {offenders}"


# ---------------------------------------------------------------------------
# stage_a_predicate_cases — the golden group both halves execute (§12).
# ---------------------------------------------------------------------------

def test_stage_a_predicate_golden_parity():
    """`scorers.test.ts` runs this same group through `predictsStageAViolation`.
    The two implementations cannot drift without one of them going red."""
    golden = json.loads((FIXTURES / "scoring_golden.json").read_text(encoding="utf-8"))
    cases = golden["stage_a_predicate_cases"]
    assert len(cases) >= 3, "the fixture must cover false/true/boundary at minimum"

    for case in cases:
        actual = predicts_stage_a_violation(case["record"])
        assert actual is case["expected"], (
            f"{case['name']}: expected {case['expected']}, got {actual}"
        )


def test_stage_a_predicate_golden_covers_the_three_named_cases():
    """§5:2417-2419 names exactly which three cases this group must carry. A
    fixture that quietly lost the boundary case would still pass the parity
    test above."""
    golden = json.loads((FIXTURES / "scoring_golden.json").read_text(encoding="utf-8"))
    cases = golden["stage_a_predicate_cases"]

    expectations = {c["name"]: c["expected"] for c in cases}
    assert expectations.get("citation_only") is False
    assert expectations.get("missed_obligation_all_three_confirmed") is True
    assert expectations.get("missed_obligation_one_confirmation_false") is False
