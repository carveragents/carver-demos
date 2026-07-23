"""Tests for `mastra_prep.probe` (spec §3 — Stage A / Stage B).

The fixture record (`tests/fixtures/sample_record.json`, the same one
`test_extract.py` uses) is real, non-trivial data: a Malta Financial Services
Authority bulletin with a title, summary, objective, key requirements, and
regulation citations that are all genuinely present and genuinely forbidden
from leaking into either probe's prompt. That is what makes
`test_task_instance_excludes_leaked_fields` a real assertion rather than one
that passes vacuously against an empty fixture.
"""
from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from mastra_prep.extract import extract_record
from mastra_prep.probe import (
    STAGE_A_MAX_COMPLETION_TOKENS,
    STAGE_B_MAX_COMPLETION_TOKENS,
    UPDATE_TYPE_PHRASES,
    run_stage_a,
    run_stage_b,
)
from mastra_prep.scenarios import SCENARIO_A, SCENARIO_B
from stubs import RaisingStubClient, RecordingStubClient, StubOpenAIClient

FIXTURE_PATH = Path(__file__).parent / "fixtures" / "sample_record.json"

# A canonical, schema-valid Stage B response body — reused wherever a test only
# needs Stage B's call to succeed, not to check specific parsed values.
_STAGE_B_BODY = {
    "knows_source": False,
    "source_name": None,
    "source_url": None,
    "compliance_date": None,
    "confidence_note": "not confident enough to cite a source",
}

# Every field the fair-test discipline (spec §3, rubric #11) forbids from
# reaching either prompt, verbatim or paraphrased. `impacted_business`/
# `impacted_functions`/`update_type`/`jurisdiction_*` are deliberately absent:
# those are the record-derived signals the discipline explicitly ALLOWS,
# funneled through scenarios.py's closed DOMAIN_BUCKETS/jurisdiction lookups
# rather than rendered verbatim.
_FORBIDDEN_STRING_FIELDS = (
    "title", "summary", "regulator_name", "objective", "what_changed", "why_it_matters",
    "effective_date", "compliance_date",
)
_FORBIDDEN_LIST_FIELDS = (
    "key_requirements", "penalties_consequences", "reg_rules", "reg_statutes", "reg_other_ref",
)


@pytest.fixture
def sample_record() -> dict:
    return json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))


@pytest.fixture
def cfg() -> SimpleNamespace:
    """A minimal duck-typed stand-in for `config.Settings` — `probe.py` reads
    only `.model_router_string` (see its module docstring on why it does not
    import `Settings` from `config.py` at all)."""
    return SimpleNamespace(model_router_string="openai/gpt-5.6-sol")


def _forbidden_substrings(record: dict) -> list[str]:
    substrings = []
    for field in _FORBIDDEN_STRING_FIELDS:
        value = record.get(field)
        if isinstance(value, str) and value.strip():
            substrings.append(value)
    for field in _FORBIDDEN_LIST_FIELDS:
        for item in record.get(field) or []:
            if isinstance(item, str) and item.strip():
                substrings.append(item)
    return substrings


def _rendered_prompt(client: StubOpenAIClient) -> str:
    return "\n".join(m["content"] for m in client.calls[-1]["messages"])


def test_task_instance_excludes_leaked_fields(sample_record, cfg, budget):
    """THE critical fair-test assertion (spec §3, rubric #11). The rendered
    Stage A / Stage B prompt may contain the persona, company, a
    DOMAIN_BUCKETS phrase, and a jurisdiction phrase — and NOTHING from the
    record itself, for either scenario."""
    record = extract_record(sample_record)
    forbidden = _forbidden_substrings(record)
    assert forbidden, "fixture must actually carry forbidden content, or this test is vacuous"

    for scenario in (SCENARIO_A, SCENARIO_B):
        client_a = StubOpenAIClient("a two-paragraph draft")
        run_stage_a(client_a, record, scenario, cfg, budget)
        prompt_a = _rendered_prompt(client_a)

        client_b = StubOpenAIClient(json.dumps(_STAGE_B_BODY))
        run_stage_b(client_b, record, scenario, cfg, budget)
        prompt_b = _rendered_prompt(client_b)

        for prompt in (prompt_a, prompt_b):
            assert "{{" not in prompt, "no unrendered {{...}} placeholder may survive"
            for leaked in forbidden:
                assert leaked not in prompt, f"record field leaked into the prompt: {leaked!r}"


def test_stage_a_call_shape(sample_record, cfg, budget):
    """RecordingStubClient's own assertions do the checking: no `temperature`,
    `reasoning_effort="medium"`, `max_completion_tokens=3000`. Also checks the
    `openai/` router prefix is stripped before it reaches `model=` (§13)."""
    record = extract_record(sample_record)
    client = RecordingStubClient(
        "a two-paragraph draft",
        expected_reasoning_effort="medium",
        expected_max_completion_tokens=STAGE_A_MAX_COMPLETION_TOKENS,
    )

    result = run_stage_a(client, record, SCENARIO_A, cfg, budget)

    assert client.last_kwargs["model"] == "gpt-5.6-sol"
    assert "response_format" not in client.last_kwargs   # Stage A: no output schema
    assert result["record_id"] == record["artifact_id"]
    assert result["draft_text"] == "a two-paragraph draft"
    assert result["usage"]["reasoning_tokens"] is None   # stub usage carries no such detail


def test_stage_b_call_shape(sample_record, cfg, budget):
    """Same shape assertions as Stage A, at Stage B's own cap (1,500), plus the
    structured-output schema attached to the call."""
    record = extract_record(sample_record)
    client = RecordingStubClient(
        json.dumps(_STAGE_B_BODY),
        expected_reasoning_effort="medium",
        expected_max_completion_tokens=STAGE_B_MAX_COMPLETION_TOKENS,
    )

    run_stage_b(client, record, SCENARIO_A, cfg, budget)

    assert client.last_kwargs["response_format"]["json_schema"]["name"] == "stage_b_citation_probe"
    assert client.last_kwargs["response_format"]["json_schema"]["strict"] is True


def test_stage_b_parses_structured_response(sample_record, cfg, budget):
    """The structured JSON response comes back through StubOpenAIClient and
    every field lands where it should in StageBResult."""
    record = extract_record(sample_record)
    body = {
        "knows_source": True,
        "source_name": "Some Regulation 2026/1",
        "source_url": "https://example.org/reg/2026-1",
        "compliance_date": "2026-09-01",
        "confidence_note": "fairly confident",
    }
    client = StubOpenAIClient(json.dumps(body))

    result = run_stage_b(client, record, SCENARIO_A, cfg, budget)

    assert result["record_id"] == record["artifact_id"]
    assert result["knows_source"] is True
    assert result["source_name"] == "Some Regulation 2026/1"
    assert result["source_url"] == "https://example.org/reg/2026-1"
    assert result["compliance_date"] == "2026-09-01"
    assert result["confidence_note"] == "fairly confident"


def test_raising_client_releases_on_unbilled_status_else_finalizes_unknown(sample_record, cfg, budget):
    """The one budget-path test: a pre-inference rejection (an
    UNBILLED_STATUS_CODES status, e.g. 429) RELEASES the hold in full; a
    raise with no such status (billing status unknown) keeps it, and either
    way the original exception propagates and the reservation reaches a
    terminal state."""
    record = extract_record(sample_record)
    spend_before = budget.spend_so_far_usd

    with pytest.raises(Exception):
        run_stage_a(RaisingStubClient(status_code=429), record, SCENARIO_A, cfg, budget)
    assert budget.spend_so_far_usd == pytest.approx(spend_before)   # released: back to zero delta
    budget.assert_no_open_reservations()

    with pytest.raises(Exception):
        run_stage_a(RaisingStubClient(), record, SCENARIO_A, cfg, budget)
    assert budget.spend_so_far_usd > spend_before   # finalize_unknown: hold retained
    budget.assert_no_open_reservations()


def test_update_type_phrases_cover_actionable_update_types():
    """Drift guard: UPDATE_TYPE_PHRASES is independently derived (spec §3
    pins only 3 of its 8 entries verbatim — see probe.py's module docstring),
    so it is checked here against candidates.py's own closed set rather than
    trusted to stay in sync by inspection alone."""
    from mastra_prep.candidates import ACTIONABLE_UPDATE_TYPES

    assert set(UPDATE_TYPE_PHRASES) == ACTIONABLE_UPDATE_TYPES
