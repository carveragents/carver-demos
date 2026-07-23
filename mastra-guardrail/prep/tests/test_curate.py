"""Tests for `mastra_prep.curate` (spec §3's curation loop, §4's per-record tie-together).

Two layers, deliberately:

  * **The loop** (`run_curation`) is tested against a FAKE `probe_and_score_one`
    (`_FakeProbe`, monkeypatched over the module global the loop actually calls).
    What is under test there is the cap arithmetic and the stop-reason priority —
    not what a record's three API calls do — and a fake makes a 400-record sweep a
    millisecond instead of 1,200 stubbed calls. The two cap tests are the reason
    this module exists in its current shape (§3's per-record fix), so they get an
    exact expected `probed`/`len(survivors)`, never an inequality.
  * **The record** (`probe_and_score_one`) is tested end-to-end through the REAL
    `probe`/`judge`/`scoring` modules with stub clients and a real `SpendBudget`,
    because the things worth checking there are compositional: that the judge floor
    is threaded from `cfg`, that the URL gate spends nothing, and that an exhausted
    retry is a `probe_error` rather than evidence.

All HTTP is stubbed via `httpx.MockTransport` — zero network calls. `_no_real_network`
is an autouse guard (the same shape `test_urls.py` uses): any test that reaches the
URL gate without installing a transport fails loudly instead of hitting the network.
"""
from __future__ import annotations

import json
from types import SimpleNamespace

import httpx
import pytest

from mastra_prep import curate
from mastra_prep.budget import (
    PINNED_PRICE_INPUT_USD_PER_MILLION,
    PINNED_PRICE_OUTPUT_USD_PER_MILLION,
    BudgetExhausted,
    SpendBudget,
)
from mastra_prep.scenarios import SCENARIO_A
from stubs import RaisingStubClient, StubOpenAIClient

_GROUND_TRUTH_URL = "https://eur-lex.europa.eu/eli/reg/2026/451/oj"


# ---------------------------------------------------------------------------
# Fixtures & builders
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _no_real_network(monkeypatch):
    """Any test reaching `resolve_url` without installing a transport of its own
    fails loudly rather than silently reaching the real network."""
    import mastra_prep.urls as urls_module

    def _guard(request: httpx.Request) -> httpx.Response:
        raise AssertionError(
            f"test attempted a real HTTP request to {request.url!r} without "
            "installing a MockTransport via _install_transport()")

    monkeypatch.setattr(urls_module, "_client", httpx.Client(transport=httpx.MockTransport(_guard)))


def _install_transport(monkeypatch, status_code: int = 200):
    """Point `mastra_prep.urls`'s shared client at a MockTransport answering every
    request with `status_code` — 200 for a record whose ground truth resolves, 404
    for one whose ground truth is gone (§2's gate)."""
    import mastra_prep.urls as urls_module

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(status_code)

    monkeypatch.setattr(urls_module, "_client", httpx.Client(transport=httpx.MockTransport(handler)))


def _cfg(**overrides) -> SimpleNamespace:
    """A duck-typed stand-in for `config.Settings` carrying only the keys curate
    reads. `config.yaml`'s real values are the defaults, so a test that overrides
    one is visibly saying which knob it is exercising."""
    base = dict(
        model_router_string="openai/gpt-5.6-sol",
        sample_seed=42,
        probe_batch_size=40,
        target_set_size=200,
        probe_max_records=400,
        judge_confidence_floor=0.7,
    )
    base.update(overrides)
    return SimpleNamespace(**base)


def _records(count: int) -> list[dict]:
    """`count` minimally-shaped records — enough for `stratified_sample_sequence`
    to bucket them and for the loop to read `artifact_id`. The loop tests never
    reach the real probe, so nothing else is needed."""
    return [
        {
            "artifact_id": f"rec-{index:04d}",
            "update_type": "guidance",
            "jurisdiction_country": "DE",
            "reconciled_published_date": "2026-04-01",
        }
        for index in range(count)
    ]


def _eligible_record(artifact_id: str = "rec-eligible") -> dict:
    """`extract_record`'s flat shape for a record that is `is_eligible(_, SCENARIO_A)`
    (EU jurisdiction + an AI industry tag) and carries one ground-truth reg-reference
    URL embedded in prose, which is what §2's gate resolves."""
    return {
        "artifact_id": artifact_id,
        "title": "AI transparency obligations for deployers",
        "objective": "Ensure deployers disclose AI interaction to end users.",
        "key_requirements": ["Disclose to end users that they are interacting with an AI system"],
        "update_type": "guidance",
        "jurisdiction_country": "DE",
        "jurisdiction_bloc": None,
        "impacted_business": {"industry": ["Generative AI"]},
        "impacted_functions": ["Product"],
        "compliance_date": "2026-09-01",
        "reconciled_published_date": "2026-04-01",
        "reg_rules": [f"Regulation (EU) 2026/451 on AI transparency ({_GROUND_TRUTH_URL})"],
        "reg_statutes": [],
        "reg_other_ref": [],
    }


_STAGE_B_BODY = json.dumps({
    "knows_source": False,
    "source_name": None,
    "source_url": None,
    "compliance_date": None,
    "confidence_note": "not confident enough to cite a source",
})


def _judge_body(record_id: str, confidence: float) -> str:
    """A judge response that satisfies every conjunct of §4's `is_failure` EXCEPT
    possibly the confidence floor — so the floor is the only thing under test."""
    return json.dumps({"verdicts": [{
        "obligation_id": record_id,
        "applies_to_draft": True,
        "omission_material": True,
        "verdict": "violation",
        "confidence": confidence,
        "rationale": "the draft never mentions the disclosure requirement",
    }]})


class _FakeProbe:
    """Stands in for `probe_and_score_one` inside `run_curation`'s loop.

    `fail_indices` are positions (in probe order, not input order — so the tests do
    not depend on `stratified_sample_sequence`'s reordering) whose result does NOT
    pass the failure bar. `raise_at` is the position at which `BudgetExhausted`
    fires instead of a result, standing in for a reservation the ceiling refused.
    """

    def __init__(self, passes: bool = True, fail_indices=(), raise_at: int | None = None):
        self.passes = passes
        self.fail_indices = set(fail_indices)
        self.raise_at = raise_at
        self.seen: list[str] = []

    def __call__(self, client, record, scenario, cfg, budget) -> dict:
        index = len(self.seen)
        if index == self.raise_at:
            raise BudgetExhausted("simulated ceiling refusal")
        self.seen.append(record["artifact_id"])
        passes = self.passes and index not in self.fail_indices
        return {
            "record_id": record["artifact_id"],
            "disqualified_reason": None,
            "resolving_urls": [],
            "stage_a": None, "stage_b": None, "judge": None,
            "citation": None, "date": None, "obligation": None,
            "passes_failure_bar": passes,
            "evidence_modes": ["citation_fabricated"] if passes else [],
        }


class _RefusesNthReservation(SpendBudget):
    """A REAL `SpendBudget` whose Nth `reserve()` is refused.

    Subclassed rather than faked so Stage A/B still reserve, settle and account for
    real — the point of the test that uses it is that the two calls which DID land
    are properly terminated while the record they belonged to counts for nothing.
    """

    def __init__(self, refuse_on: int):
        super().__init__(ceiling_usd=1000.0,
                         price_in=PINNED_PRICE_INPUT_USD_PER_MILLION,
                         price_out=PINNED_PRICE_OUTPUT_USD_PER_MILLION)
        self.refuse_on = refuse_on
        self.reserve_count = 0

    def reserve(self, payload):
        self.reserve_count += 1
        if self.reserve_count == self.refuse_on:
            raise BudgetExhausted("simulated ceiling refusal")
        return super().reserve(payload)


# ---------------------------------------------------------------------------
# run_curation — the four stop conditions (§3)
# ---------------------------------------------------------------------------


def test_target_reached_stops_at_the_survivor_ceiling(monkeypatch, budget):
    cfg = _cfg(target_set_size=5, probe_max_records=400)
    probe = _FakeProbe()
    monkeypatch.setattr(curate, "probe_and_score_one", probe)

    result = curate.run_curation(None, _records(50), SCENARIO_A, cfg, budget)

    assert result["stop_reason"] == "target_reached"
    assert len(result["survivors"]) == 5
    assert result["probed"] == 5


def test_sweep_cap_stops_at_probe_max_records(monkeypatch, budget):
    cfg = _cfg(target_set_size=200, probe_max_records=7)
    probe = _FakeProbe(passes=False)
    monkeypatch.setattr(curate, "probe_and_score_one", probe)

    result = curate.run_curation(None, _records(50), SCENARIO_A, cfg, budget)

    assert result["stop_reason"] == "sweep_cap"
    assert result["probed"] == 7
    assert result["survivors"] == []


def test_spend_ceiling_stops_the_run_and_the_refused_record_is_not_counted(monkeypatch, budget):
    """`BudgetExhausted` is the one stop that fires mid-record (§3). The record it
    fired on is counted in NEITHER `probed` NOR `survivors` — it taught us nothing."""
    cfg = _cfg()
    probe = _FakeProbe(raise_at=3)
    monkeypatch.setattr(curate, "probe_and_score_one", probe)

    result = curate.run_curation(None, _records(50), SCENARIO_A, cfg, budget)

    assert result["stop_reason"] == "spend_ceiling"
    assert result["probed"] == 3
    assert len(result["survivors"]) == 3


def test_pool_exhausted_when_neither_cap_binds(monkeypatch, budget):
    cfg = _cfg()
    probe = _FakeProbe()
    monkeypatch.setattr(curate, "probe_and_score_one", probe)

    result = curate.run_curation(None, _records(10), SCENARIO_A, cfg, budget)

    assert result["stop_reason"] == "pool_exhausted"
    assert result["probed"] == 10
    assert len(result["survivors"]) == 10


def test_a_cap_beats_pool_exhaustion_at_the_final_record(monkeypatch, budget):
    """§3's deterministic tie-break: when the pool runs out on the very record that
    also hits a cap, the CAP is the reported reason — "we stopped because we were
    done" is more informative than "we ran out", and it keeps `stop_reason` a pure
    function of the final counts rather than of loop-exit order. Both caps bind at
    once here, so this also pins their documented priority: target before sweep."""
    cfg = _cfg(target_set_size=10, probe_max_records=10)
    probe = _FakeProbe()
    monkeypatch.setattr(curate, "probe_and_score_one", probe)

    result = curate.run_curation(None, _records(10), SCENARIO_A, cfg, budget)

    assert result["stop_reason"] == "target_reached"   # not "pool_exhausted", not "sweep_cap"
    assert result["probed"] == 10


# ---------------------------------------------------------------------------
# The caps bind PER-RECORD, not per-batch (§3's fix) — the reason this module
# was rewritten. A batch-boundary check overshoots by up to probe_batch_size.
# ---------------------------------------------------------------------------


def test_survivor_ceiling_exact_at_batch_crossing(monkeypatch, budget):
    """One record fails the bar at probe index 5, so the 6th 40-record batch (probe
    indices 200-239) is ENTERED at 199 survivors and the 200th survivor is found
    INSIDE it. A batch-boundary check would run that batch to completion and end at
    239 survivors — 39 past goal #11's ceiling."""
    cfg = _cfg(target_set_size=200, probe_batch_size=40, probe_max_records=400)
    probe = _FakeProbe(fail_indices={5})
    monkeypatch.setattr(curate, "probe_and_score_one", probe)

    result = curate.run_curation(None, _records(400), SCENARIO_A, cfg, budget)

    assert len(result["survivors"]) == cfg.target_set_size   # EXACTLY 200, never 200+n
    assert result["probed"] == 201                            # 200 survivors + the one that failed
    assert result["stop_reason"] == "target_reached"


def test_sweep_cap_exact_at_batch_crossing(monkeypatch, budget):
    """`probe_max_records=210` lands mid-batch (the 6th batch covers 200-239). A
    batch-boundary check would probe 240 records; the per-record check stops at 210."""
    cfg = _cfg(target_set_size=200, probe_batch_size=40, probe_max_records=210)
    probe = _FakeProbe(passes=False)
    monkeypatch.setattr(curate, "probe_and_score_one", probe)

    result = curate.run_curation(None, _records(400), SCENARIO_A, cfg, budget)

    assert result["probed"] == cfg.probe_max_records          # EXACTLY 210, never 240
    assert result["stop_reason"] == "sweep_cap"


@pytest.mark.parametrize("probe_batch_size", [1, 40])
def test_cap_is_identical_across_batch_sizes(monkeypatch, budget, probe_batch_size):
    """`probe_batch_size` is a LOGGING CADENCE (§3) — it may not influence a cap by
    even one record. Same pool, same fake, two batch sizes, identical counts."""
    cfg = _cfg(target_set_size=200, probe_batch_size=probe_batch_size, probe_max_records=400)
    probe = _FakeProbe(fail_indices={5})
    monkeypatch.setattr(curate, "probe_and_score_one", probe)

    result = curate.run_curation(None, _records(400), SCENARIO_A, cfg, budget)

    assert len(result["survivors"]) == 200
    assert result["probed"] == 201
    assert result["stop_reason"] == "target_reached"


# ---------------------------------------------------------------------------
# exclude_ids — §7's winner's-curse fix
# ---------------------------------------------------------------------------


def test_excluded_ids_are_never_probed(monkeypatch, budget):
    """The trial's already-probed records are filtered out BEFORE any spend, so
    curation measures a fresh sample rather than re-probing the records the winning
    scenario was chosen for out-performing on."""
    cfg = _cfg()
    probe = _FakeProbe()
    monkeypatch.setattr(curate, "probe_and_score_one", probe)
    excluded = frozenset({"rec-0000", "rec-0003", "rec-0007"})

    result = curate.run_curation(None, _records(10), SCENARIO_A, cfg, budget,
                                 exclude_ids=excluded)

    assert not excluded & set(probe.seen)
    assert result["probed"] == 7
    assert sorted(probe.seen) == [f"rec-{i:04d}" for i in (1, 2, 4, 5, 6, 8, 9)]


# ---------------------------------------------------------------------------
# probe_and_score_one — the real composition
# ---------------------------------------------------------------------------


def test_judge_confidence_floor_is_threaded_from_cfg(monkeypatch, budget):
    """§4's rule is `confidence >= cfg.judge_confidence_floor`, but its pinned 4-arg
    signature cannot receive `cfg` — so an operator who RAISES the floor to 0.9 must
    not silently get `MIN_JUDGE_CONFIDENCE_FLOOR` (0.7) at this call site and admit
    verdicts in [0.7, 0.9). Same 0.8-confidence violation, two floors, two answers."""
    _install_transport(monkeypatch, status_code=200)
    record = _eligible_record()

    def probe_once(floor: float) -> dict:
        client = StubOpenAIClient([
            "a two-paragraph rollout announcement",
            _STAGE_B_BODY,
            _judge_body(record["artifact_id"], confidence=0.8),
        ])
        return curate.probe_and_score_one(
            client, record, SCENARIO_A, _cfg(judge_confidence_floor=floor),
            SpendBudget(1000.0, PINNED_PRICE_INPUT_USD_PER_MILLION,
                        PINNED_PRICE_OUTPUT_USD_PER_MILLION))

    raised = probe_once(0.9)
    assert raised["obligation"]["is_failure"] is False, (
        "a 0.8-confidence verdict must NOT be scored as a failure under a 0.9 floor — "
        "the floor was not threaded from cfg")
    assert raised["passes_failure_bar"] is False
    assert raised["evidence_modes"] == []

    # The other arm is what makes the first non-vacuous: the verdict is otherwise a
    # full §4 failure, so ONLY the floor can be deciding it.
    pinned = probe_once(0.7)
    assert pinned["obligation"]["is_failure"] is True
    assert pinned["passes_failure_bar"] is True
    assert pinned["evidence_modes"] == ["violation"]


def test_url_gate_disqualifies_before_spending_anything(monkeypatch, budget):
    """§2's gate is the FIRST thing that runs: a record with no resolving
    ground-truth URL never reaches Stage A/B/Judge and makes zero reservations."""
    _install_transport(monkeypatch, status_code=404)
    client = StubOpenAIClient("a draft that must never be requested")

    result = curate.probe_and_score_one(client, _eligible_record(), SCENARIO_A, _cfg(), budget)

    assert result["disqualified_reason"] == "no_resolving_ground_truth_url"
    assert result["passes_failure_bar"] is False
    assert result["evidence_modes"] == []
    assert result["resolving_urls"] == []
    assert client.call_count == 0
    assert budget.spend_so_far_usd == 0.0


def test_gate_records_the_resolving_citation_name_and_url(monkeypatch, budget):
    """§5's citation-selection input: the gate stores every resolving `(name, url)`
    pair, `name` being the containing string's text before the parenthetical URL, so
    human review reads an already-computed list rather than re-resolving anything.

    The same document cited from a second lane (here with a trailing slash — the same
    URL under `scoring._normalize_url`'s rule) is ONE choice for the reviewer, not two.
    """
    _install_transport(monkeypatch, status_code=200)
    record = _eligible_record()
    record["reg_statutes"] = [f"Regulation (EU) 2026/451, as amended ({_GROUND_TRUTH_URL}/)"]
    client = StubOpenAIClient([
        "a two-paragraph rollout announcement",
        _STAGE_B_BODY,
        _judge_body("rec-eligible", confidence=0.9),
    ])

    result = curate.probe_and_score_one(client, record, SCENARIO_A, _cfg(), budget)

    assert result["resolving_urls"] == [
        ("Regulation (EU) 2026/451 on AI transparency", _GROUND_TRUTH_URL)]


def test_exhausted_retry_is_a_probe_error_not_evidence(monkeypatch, budget):
    """§15: an API error gets ONE retry (a brand-new call with its own reservation and
    its own terminal operation); if that also fails the record is `probe_error` and is
    excluded from survivors — an API failure is not evidence about the baseline."""
    _install_transport(monkeypatch, status_code=200)
    monkeypatch.setattr(curate, "RETRY_BACKOFF_SECONDS", 0.0)
    client = RaisingStubClient()

    result = curate.probe_and_score_one(client, _eligible_record(), SCENARIO_A, _cfg(), budget)

    assert result["disqualified_reason"] == "probe_error"
    assert result["passes_failure_bar"] is False
    assert result["evidence_modes"] == []
    assert client.call_count == 2, "§15's one retry: two attempts, no more, no fewer"
    budget.assert_no_open_reservations()   # each attempt terminated its OWN reservation


def test_budget_exhaustion_mid_record_counts_toward_neither_probed_nor_survivors(monkeypatch):
    """The judge's reservation is refused AFTER Stage A and Stage B have landed — the
    genuinely mid-record stop (§3). The record is probed-but-incomplete, so it is
    counted in neither `probed` nor `survivors`, and the two calls that did land are
    still fully accounted for."""
    _install_transport(monkeypatch, status_code=200)
    budget = _RefusesNthReservation(refuse_on=3)
    client = StubOpenAIClient([
        "a two-paragraph rollout announcement",
        _STAGE_B_BODY,
        _judge_body("rec-eligible", confidence=0.9),
    ])

    result = curate.run_curation(client, [_eligible_record()], SCENARIO_A, _cfg(), budget)

    assert result["stop_reason"] == "spend_ceiling"
    assert result["probed"] == 0
    assert result["survivors"] == []
    assert client.call_count == 2, "Stage A and Stage B must have landed — this is a MID-record stop"
    # The two calls that DID land are still billed: spend_usd is read from the
    # budget's own ledger at the moment of the stop, never a constant.
    assert result["spend_usd"] == budget.spend_so_far_usd > 0
    budget.assert_no_open_reservations()
