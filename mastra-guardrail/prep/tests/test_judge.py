"""`judge.py` — the shared Judge/Verdict contract (spec §4, plan P2.2).

The `judge_cases` group of `scoring_golden.json` is the cross-language drift
defence: every case runs through `parse_and_validate_verdicts` here and through
the TS `parseAndValidateVerdicts` on the other side of the seam. It is
parametrized rather than hand-written per case because each case asserts a
DIFFERENT behaviour of the same six-step algorithm — this is the golden
contract, not a matrix of the same assertion re-run over variations.

`test_out_of_range_confidence_is_discarded_not_clamped` restates the highest-
value case standalone, spelling out the assertion the fixture can only imply:
the result is NOT 1.0. Clamping would clear the 0.7 confidence floor and admit a
record on a value the model never validly produced.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest
from stubs import RaisingStubClient, RecordingStubClient, SequencedStubClient

from mastra_prep.budget import REASONING_EFFORT, BudgetExhausted, SpendBudget
from mastra_prep.judge import (
    JUDGE_MAX_COMPLETION_TOKENS,
    JUDGE_RESPONSE_SCHEMA,
    RATIONALE_OMITTED,
    RATIONALE_OUT_OF_RANGE,
    parse_and_validate_verdicts,
    run_judge,
)

FIXTURE = json.loads(
    (Path(__file__).parent / "fixtures" / "scoring_golden.json").read_text(encoding="utf-8")
)
JUDGE_CASES = FIXTURE["judge_cases"]

OBLIGATION: dict = {
    "id": "ob-1",
    "title": "Guidelines on automated decision-making transparency",
    "key_requirements": ["Disclose the logic involved in automated decisions."],
    "objective": "Set transparency expectations for automated decisions.",
}

VALID_RESPONSE = json.dumps({
    "verdicts": [{
        "obligation_id": "ob-1",
        "applies_to_draft": True,
        "omission_material": True,
        "verdict": "violation",
        "confidence": 0.9,
        "rationale": "The draft omits the disclosure requirement.",
    }]
})


class _Cfg:
    """The one `Settings` field `run_judge` reads.

    `judge_confidence_floor` is deliberately absent: the floor belongs to
    `scoring.score_missed_obligation`, and a stray attribute here would imply
    `run_judge` consults it.
    """

    model_router_string = "openai/gpt-5.6-sol"


@pytest.fixture(autouse=True)
def _no_real_backoff(monkeypatch):
    """The pinned 1s API-error backoff (§15) must not be paid by the suite.

    Patches this module's own constant rather than stdlib `time.sleep` — the
    latter would resolve through `mastra_prep.judge.time` to the real `time`
    module and blank out sleeping process-wide for the duration of the test.
    """
    monkeypatch.setattr("mastra_prep.judge.RETRY_BACKOFF_SECONDS", 0)


# ── parse_and_validate_verdicts — the six steps, against the golden fixture ──

@pytest.mark.parametrize("case", JUDGE_CASES, ids=lambda c: c["name"])
def test_golden_judge_cases(case):
    result = parse_and_validate_verdicts(case["raw_response"], case["requested_ids"])
    assert result["verdicts"] == case["expected_verdicts"]


def test_out_of_range_confidence_is_discarded_not_clamped():
    """THE case (§4 step 3). `5.0` must fall back to uncertain/0.0 — explicitly
    NOT clamped to 1.0, which would sail past judge_confidence_floor and admit a
    record on garbage. The fixture asserts the same thing; this states the
    negative the fixture can only imply."""
    raw = json.dumps({"verdicts": [{
        "obligation_id": "ob-1", "applies_to_draft": True, "omission_material": True,
        "verdict": "violation", "confidence": 5.0, "rationale": "Out of range.",
    }]})

    verdict = parse_and_validate_verdicts(raw, ["ob-1"])["verdicts"][0]

    assert verdict["confidence"] == 0.0
    assert verdict["confidence"] != 1.0, "clamped instead of discarded — see §4 step 3"
    assert verdict["verdict"] == "uncertain"
    assert verdict["applies_to_draft"] is False
    assert verdict["omission_material"] is False
    assert verdict["rationale"] == RATIONALE_OUT_OF_RANGE


@pytest.mark.parametrize("confidence", [0.0, 1.0])
def test_confidence_bounds_are_inclusive(confidence):
    """The bound is [0, 1] closed — the endpoints are valid model output, not
    garbage, and discarding them would throw away real verdicts."""
    raw = json.dumps({"verdicts": [{
        "obligation_id": "ob-1", "applies_to_draft": True, "omission_material": True,
        "verdict": "compliant", "confidence": confidence, "rationale": "At the bound.",
    }]})

    verdict = parse_and_validate_verdicts(raw, ["ob-1"])["verdicts"][0]

    assert verdict["confidence"] == confidence
    assert verdict["verdict"] == "compliant"


def test_synthesized_rationale_distinguishes_out_of_range_from_omitted():
    """Both fall back to uncertain/0.0 — identical in effect, distinguishable in
    the probe log (§4 step 4)."""
    raw = json.dumps({"verdicts": [{
        "obligation_id": "ob-1", "applies_to_draft": True, "omission_material": True,
        "verdict": "violation", "confidence": -0.2, "rationale": "Out of range.",
    }]})

    verdicts = parse_and_validate_verdicts(raw, ["ob-1", "ob-2"])["verdicts"]

    assert verdicts[0]["rationale"] == RATIONALE_OUT_OF_RANGE
    assert verdicts[1]["rationale"] == RATIONALE_OMITTED
    assert RATIONALE_OUT_OF_RANGE != RATIONALE_OMITTED


def test_schema_declares_the_confidence_bound():
    """Defence in depth and a real steering signal — never the proof (§4: OpenAI
    accepts minimum/maximum but does not structurally enforce them)."""
    confidence = (JUDGE_RESPONSE_SCHEMA["schema"]["properties"]["verdicts"]["items"]
                  ["properties"]["confidence"])
    assert confidence["minimum"] == 0
    assert confidence["maximum"] == 1
    assert JUDGE_RESPONSE_SCHEMA["strict"] is True


# ── run_judge — the call lifecycle (§3) and §15's retry ──

def test_run_judge_call_shape(budget):
    client = RecordingStubClient(
        VALID_RESPONSE,
        expected_reasoning_effort=REASONING_EFFORT,
        expected_max_completion_tokens=JUDGE_MAX_COMPLETION_TOKENS,
    )

    result = run_judge(client, [OBLIGATION], "A two-paragraph release note.", _Cfg(), budget)

    kwargs = client.last_kwargs
    # The BARE id — §13: "Stripped of the `openai/` prefix and passed as `model=`".
    # The full router string 404s on every live call (`model_not_found`), which
    # would disqualify every record AFTER Stage A and Stage B had already billed.
    assert kwargs["model"] == "gpt-5.6-sol"
    assert kwargs["response_format"]["json_schema"] is JUDGE_RESPONSE_SCHEMA
    user_text = kwargs["messages"][1]["content"]
    assert "A two-paragraph release note." in user_text
    assert OBLIGATION["key_requirements"][0] in user_text
    assert result["verdicts"][0]["confidence"] == 0.9
    budget.assert_no_open_reservations()
    assert 0 < budget.spend_so_far_usd <= budget.ceiling_usd


def test_run_judge_retries_once_on_malformed_json_then_falls_back(budget):
    client = SequencedStubClient(['{"verdicts": [{"obligation_id": ', "not json at all"])

    result = run_judge(client, [OBLIGATION], "draft", _Cfg(), budget)

    assert client.call_count == 2, "§15: exactly one retry, never a loop"
    assert result["verdicts"] == [{
        "obligation_id": "ob-1", "applies_to_draft": False, "omission_material": False,
        "verdict": "uncertain", "confidence": 0.0, "rationale": RATIONALE_OMITTED,
    }]
    budget.assert_no_open_reservations()


def test_run_judge_uses_the_retry_when_the_retry_parses(budget):
    client = SequencedStubClient(["{oops", VALID_RESPONSE])

    result = run_judge(client, [OBLIGATION], "draft", _Cfg(), budget)

    assert client.call_count == 2
    assert result["verdicts"][0]["verdict"] == "violation"
    assert result["verdicts"][0]["confidence"] == 0.9


def test_run_judge_terminates_its_reservation_on_an_api_error(budget):
    """Both attempts fail -> the exception propagates (curate maps it to
    disqualified_reason='probe_error', §15) with no reservation left open."""
    client = RaisingStubClient(status_code=500)

    with pytest.raises(Exception, match="simulated API error"):
        run_judge(client, [OBLIGATION], "draft", _Cfg(), budget)

    assert client.call_count == 2
    budget.assert_no_open_reservations()


def test_run_judge_never_retries_a_budget_exhausted_reservation():
    """§15: BudgetExhausted stops the run — never retried, never swallowed."""
    tight = SpendBudget(ceiling_usd=0.01, price_in=5.0, price_out=30.0)
    client = RecordingStubClient(VALID_RESPONSE)

    with pytest.raises(BudgetExhausted):
        run_judge(client, [OBLIGATION], "draft", _Cfg(), tight)

    assert client.call_count == 0, "the ceiling gate fires BEFORE the call"
    tight.assert_no_open_reservations()
