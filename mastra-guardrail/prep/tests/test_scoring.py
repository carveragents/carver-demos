"""`scoring.py` — the three deterministic scorers and the failure bar (spec §4,
plan P2.3).

The `citation_date_cases` and `obligation_cases` groups of `scoring_golden.json`
are the cross-language drift defence (§12): every case runs through this
implementation and through the TS port, except the two tagged `prep_only` which
the template structurally cannot reach. They are parametrized because each case
pins a DIFFERENT outcome value of the same scorer — the fixture IS the contract.

The tests that are not fixture-driven exist because they assert something the
fixture cannot express: that a branch is never reached (the judge is not
consulted), that a value is not merely equal but not-something-else (discarded,
not clamped), and that the two closed maps round-trip over exactly 3 values.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from mastra_prep.config import MIN_JUDGE_CONFIDENCE_FLOOR
from mastra_prep.judge import parse_and_validate_verdicts
from mastra_prep.scenarios import SCENARIOS
from mastra_prep.schema import SCORE_OUTCOME_TO_FAILURE_MODE, STAGE_OF_MODE
from mastra_prep.scoring import (
    parse_baseline_date,
    passes_failure_bar,
    score_citation,
    score_compliance_date,
    score_missed_obligation,
)

FIXTURE = json.loads(
    (Path(__file__).parent / "fixtures" / "scoring_golden.json").read_text(encoding="utf-8")
)
CITATION_DATE_CASES = FIXTURE["citation_date_cases"]
OBLIGATION_CASES = FIXTURE["obligation_cases"]

# A record the judge WOULD flag, under a scenario it is eligible for — the base
# both hand-written obligation tests vary from.
ELIGIBLE_RECORD: dict = {
    "artifact_id": "art-ob-001",
    "jurisdiction_country": "DE",
    "jurisdiction_bloc": "EU",
    "impacted_business": {"industry": ["Artificial Intelligence"]},
    "impacted_functions": ["Compliance"],
}


def _score(outcome: str, is_failure: bool) -> dict:
    """A minimal dimension result — passes_failure_bar reads only these two keys."""
    return {"outcome": outcome, "is_failure": is_failure}


# ── score_citation / score_compliance_date — one case per outcome value ──────

@pytest.mark.parametrize("case", CITATION_DATE_CASES, ids=lambda c: c["name"])
def test_golden_citation_and_date_cases(case):
    citation = score_citation(case["stage_b_result"], case["record"], dict(case["url_cache"]))
    date = score_compliance_date(case["stage_b_result"], case["record"], citation)

    assert citation["outcome"] == case["expected_citation_outcome"]
    assert citation["is_failure"] is case["expected_citation_is_failure"]
    assert date["outcome"] == case["expected_date_outcome"]
    assert date["is_failure"] is case["expected_date_is_failure"]


def test_citation_fabricated_is_the_only_citation_failure():
    """is_failure is True for EXACTLY one citation outcome. Stated over the whole
    taxonomy rather than case by case: an honest abstention, a plausible
    alternative source, and a server that declined to answer are each evidence of
    nothing, and counting any of them would manufacture a failure.

    Runs the SCORER over every case — reading the fixture's own
    `expected_*` fields instead would asserta property of the JSON file, and stay
    green if `score_citation` started failing on `citation_unverifiable`. The
    all-five-outcomes assertion is what stops a dropped fixture case from quietly
    narrowing the taxonomy this claims to cover."""
    scored = [score_citation(case["stage_b_result"], case["record"], dict(case["url_cache"]))
              for case in CITATION_DATE_CASES]

    assert {c["outcome"] for c in scored} == {
        "citation_correct", "citation_missing", "citation_alternative_real",
        "citation_unverifiable", "citation_fabricated"}
    assert {c["outcome"] for c in scored if c["is_failure"]} == {"citation_fabricated"}


def test_date_wrong_is_the_only_date_failure():
    """The date taxonomy's other half, scorer-run for the same reason."""
    scored = []
    for case in CITATION_DATE_CASES:
        citation = score_citation(case["stage_b_result"], case["record"], dict(case["url_cache"]))
        scored.append(score_compliance_date(case["stage_b_result"], case["record"], citation))

    assert {d["outcome"] for d in scored} == {
        "date_correct", "date_wrong", "date_missing", "date_unparseable",
        "date_uncertain_attribution", "not_applicable"}
    assert {d["outcome"] for d in scored if d["is_failure"]} == {"date_wrong"}


def test_a_non_correct_citation_always_yields_uncertain_attribution():
    """The other half of the fair-test fix (§4). Even a date that matches ground
    truth EXACTLY is unattributable when the baseline never confirmed it was
    talking about this record's source — the date may be perfectly correct for
    whatever other document it actually had in mind."""
    record = {"reg_rules": ["Rule (https://www.example.gov/rule-1)"],
              "compliance_date": "2026-09-01"}
    stage_b = {"source_url": "https://www.example.gov/some-other-real-rule",
               "compliance_date": "2026-09-01"}
    cache = {"https://www.example.gov/some-other-real-rule": "resolves"}

    citation = score_citation(stage_b, record, cache)
    date = score_compliance_date(stage_b, record, citation)

    assert citation["outcome"] == "citation_alternative_real"
    assert date["outcome"] == "date_uncertain_attribution"
    assert date["is_failure"] is False
    assert date["baseline_date"] == "2026-09-01", "logged verbatim, never dropped"


# ── parse_baseline_date — a correct answer in the wrong shape is not a failure ─

@pytest.mark.parametrize("raw", [
    "2026-09-01", "1 September 2026", "September 1, 2026", "Sept 1 2026",
    "2026-09-01T00:00:00Z",
])
def test_parse_baseline_date_accepts_every_unambiguous_form(raw):
    """All five name the same day. A raw string compare would score four of them
    date_wrong and admit the record on evidence the baseline got it RIGHT."""
    assert parse_baseline_date(raw) == "2026-09-01"


@pytest.mark.parametrize("raw", [
    "01/09/2026",   # day-first vs month-first is unknowable — THE case
    "Q3 2026",      # prose that names a period, not a day
    "",             # the empty answer
    "2026-13-01",   # ISO SHAPE, impossible calendar date — only date() catches this
])
def test_parse_baseline_date_never_guesses(raw):
    """Ambiguity resolves to None -> date_unparseable -> evidence of nothing.
    None costs only this dimension's evidence for this record; a guess would
    invent a wrong answer and score a failure off it."""
    assert parse_baseline_date(raw) is None


# ── score_missed_obligation — one case per outcome value ─────────────────────

@pytest.mark.parametrize("case", OBLIGATION_CASES, ids=lambda c: c["name"])
def test_golden_obligation_cases(case):
    obligation = score_missed_obligation(
        case["record"], SCENARIOS[case["scenario"]], case["judge_result"], case["obligation_id"])

    assert obligation["outcome"] == case["expected_outcome"]
    assert obligation["is_failure"] is case["expected_is_failure"]


def test_not_applicable_never_consults_the_judge():
    """§4: an ineligible record returns not_applicable WITHOUT the judge's verdict
    for this dimension being consulted at all. Asserted by making consultation
    impossible rather than by trusting the returned outcome — a scorer that read
    the verdict first would still return not_applicable here and hide the bug."""
    class _Exploding(dict):
        def __getitem__(self, key):
            raise AssertionError("judge_result was consulted for an ineligible record")

    us_only_record = dict(ELIGIBLE_RECORD, jurisdiction_country="US", jurisdiction_bloc=None)

    obligation = score_missed_obligation(
        us_only_record, SCENARIOS["A"], _Exploding(), "ob-1")

    assert obligation["outcome"] == "not_applicable"
    assert obligation["is_failure"] is False


def test_out_of_range_confidence_cannot_admit_a_record():
    """The seam this whole batch turns on, end to end: a judge that returns
    confidence 5.0 on a both-flags-true "violation" must not produce evidence.
    Clamped to 1.0 it would clear the 0.7 floor, satisfy all four conjuncts, and
    admit the record on a value the model never validly produced."""
    raw = json.dumps({"verdicts": [{
        "obligation_id": "ob-1", "applies_to_draft": True, "omission_material": True,
        "verdict": "violation", "confidence": 5.0, "rationale": "Out of range.",
    }]})

    judge_result = parse_and_validate_verdicts(raw, ["ob-1"])
    obligation = score_missed_obligation(ELIGIBLE_RECORD, SCENARIOS["A"], judge_result, "ob-1")

    assert obligation["outcome"] == "uncertain"
    assert obligation["confidence"] == 0.0
    assert obligation["is_failure"] is False
    admitted, evidence = passes_failure_bar(
        _score("citation_correct", False), _score("date_correct", False), obligation)
    assert (admitted, evidence) == (False, [])


def test_confidence_floor_is_inclusive_and_defaults_to_the_goals_guard():
    """>= 0.7, not > 0.7 — and the default IS the goal's near-miss guard, so a
    caller that forgets to thread cfg.judge_confidence_floor gets the floor, never
    no floor."""
    verdicts = {"verdicts": [{"obligation_id": "ob-1", "applies_to_draft": True,
                             "omission_material": True, "verdict": "violation",
                             "confidence": MIN_JUDGE_CONFIDENCE_FLOOR,
                             "rationale": "At the floor."}]}

    at_floor = score_missed_obligation(ELIGIBLE_RECORD, SCENARIOS["A"], verdicts, "ob-1")
    raised_floor = score_missed_obligation(ELIGIBLE_RECORD, SCENARIOS["A"], verdicts, "ob-1",
                                           confidence_floor=0.9)

    assert at_floor["is_failure"] is True
    assert raised_floor["is_failure"] is False


# ── passes_failure_bar — OR-logic, no partial credit ─────────────────────────

def test_each_dimension_alone_admits_a_record():
    """A single real, recorded failure mode is sufficient AND necessary — no
    weighting, no "2 of 3", no threshold to tune."""
    citation_only = passes_failure_bar(
        _score("citation_fabricated", True), _score("date_missing", False),
        _score("compliant", False))
    date_only = passes_failure_bar(
        _score("citation_correct", False), _score("date_wrong", True),
        _score("compliant", False))
    obligation_only = passes_failure_bar(
        _score("citation_correct", False), _score("date_correct", False),
        _score("violation", True))

    assert citation_only == (True, ["citation_fabricated"])
    assert date_only == (True, ["date_wrong"])
    assert obligation_only == (True, ["violation"])


def test_all_non_failures_is_rejected_and_multiple_evidence_accumulates():
    near_miss = passes_failure_bar(
        _score("citation_alternative_real", False), _score("date_uncertain_attribution", False),
        _score("uncertain", False))
    two_modes = passes_failure_bar(
        _score("citation_fabricated", True), _score("date_uncertain_attribution", False),
        _score("violation", True))

    assert near_miss == (False, [])
    assert two_modes == (True, ["citation_fabricated", "violation"])


def test_failure_outcomes_round_trip_through_the_two_closed_maps():
    """Every outcome passes_failure_bar can emit is a key of
    SCORE_OUTCOME_TO_FAILURE_MODE, and every mode it maps to has a stage — the
    three closed values of goal #2's named failure modes, no more."""
    _, evidence = passes_failure_bar(
        _score("citation_fabricated", True), _score("date_wrong", True),
        _score("violation", True))

    assert evidence == ["citation_fabricated", "date_wrong", "violation"]
    assert set(evidence) == set(SCORE_OUTCOME_TO_FAILURE_MODE)
    modes = [SCORE_OUTCOME_TO_FAILURE_MODE[outcome] for outcome in evidence]
    assert modes == ["citation_fabricated", "date_wrong", "missed_obligation"]
    assert [STAGE_OF_MODE[mode] for mode in modes] == ["B", "B", "A"]
