"""Tests for `mastra_prep.scenario_decision` (spec §7's A/B trial).

**Everything here fakes `probe_and_score_one`.** What is under test is the TRIAL's
shape — that the two arms advance in lockstep, that a stop truncates them equally,
that an in-flight round is discarded whole, and that the winner falls out of
`mean_strength` and nothing else. None of that is about what a record's three API
calls do; `test_curate.py` already owns that, end-to-end through the real
`probe`/`judge`/`scoring` modules. A fake keeps a 60-record trial a millisecond and
— more importantly — lets a test say "the budget dies on arm B's record in round 7"
in one line instead of arranging a real ceiling to refuse the 14th reservation.

`_FakeProbe` is monkeypatched over the module global `decide_scenario` actually
calls, exactly as `test_curate.py` fakes the same function inside `run_curation`.

The client is a bare sentinel: `decide_scenario` must thread it through untouched and
never inspect it (`test_client_and_budget_are_threaded_through_untouched`), so a stub
with canned responses would be testing `curate.py`'s contract, not this module's.
"""
from __future__ import annotations

import json
from datetime import datetime
from types import SimpleNamespace

import pytest

from mastra_prep import scenario_decision
from mastra_prep.budget import BudgetExhausted
from mastra_prep.scenario_decision import (
    ScenarioDecision,
    decide_scenario,
    mean_strength,
    strength,
)
from mastra_prep.schema import SCORE_OUTCOME_TO_FAILURE_MODE
from mastra_prep.scoring import (
    CitationScore,
    DateScore,
    ObligationScore,
    passes_failure_bar,
)

_CLIENT = object()      # a sentinel: this module must never touch it
_BUDGET = object()      # ditto — every reservation happens inside the faked probe


# ---------------------------------------------------------------------------
# Fixtures & builders
# ---------------------------------------------------------------------------


def _cfg(**overrides) -> SimpleNamespace:
    """A duck-typed stand-in for `config.Settings` carrying only the three keys
    `decide_scenario` reads. `config.yaml`'s real values are the defaults, so a test
    that overrides one is visibly saying which knob it is exercising."""
    base = dict(sample_seed=42, scenario_trial_size=30, scenario_trial_min=10)
    base.update(overrides)
    return SimpleNamespace(**base)


def _record_a(index: int) -> dict:
    """`extract_record`'s flat shape for a record eligible for scenario A ONLY —
    an EU jurisdiction plus an AI industry tag, and no financial/promotional tag."""
    return {
        "artifact_id": f"a-{index:04d}",
        "update_type": "guidance",
        "jurisdiction_country": "DE",
        "jurisdiction_bloc": None,
        "impacted_business": {"industry": ["Generative AI"]},
        "impacted_functions": ["Product"],
        "reconciled_published_date": "2026-04-01",
    }


def _record_b(index: int) -> dict:
    """Eligible for scenario B ONLY — a financial term AND a promotional term, and
    no AI/data-protection tag (so it cannot leak into arm A). Non-EU on purpose: B
    is jurisdiction-general, and a US record proves it."""
    return {
        "artifact_id": f"b-{index:04d}",
        "update_type": "guidance",
        "jurisdiction_country": "US",
        "jurisdiction_bloc": None,
        "impacted_business": {"industry": ["Asset Management"]},
        "impacted_functions": ["Marketing"],
        "reconciled_published_date": "2026-04-01",
    }


def _pool(count_a: int, count_b: int) -> list[dict]:
    """A trial pool with disjoint per-arm eligibility, so a test knows exactly which
    records each arm can draw. (`is_eligible` admits a record to BOTH arms when it
    carries both signals — the two trials are independent filters, not a partition —
    which is real behavior but makes an arm's contents unreadable in a test.)"""
    return [_record_a(i) for i in range(count_a)] + [_record_b(i) for i in range(count_b)]


class _FakeProbe:
    """Stands in for `probe_and_score_one` inside `decide_scenario`'s round loop.

    Positions are given as `(arm_id, per_arm_index)` — the index within that ARM's
    own probe order, which is exactly the round number, so a test can name "arm B's
    record in round 7" without depending on `stratified_sample_sequence`'s
    reordering of the pool.

      `evidence`      — per-arm evidence modes for a record that passes the failure
                        bar; `[]` means the record was probed and did NOT pass.
      `raise_at`      — the position at which `BudgetExhausted` fires instead of a
                        result, standing in for a reservation the ceiling refused.
      `disqualify_at` — positions returning `disqualified_reason` set (a dead
                        ground-truth URL or an exhausted retry).
    """

    def __init__(self, evidence: dict[str, list[str]], raise_at: tuple[str, int] | None = None,
                 disqualify_at: tuple[tuple[str, int], ...] = ()):
        self.evidence = evidence
        self.raise_at = raise_at
        self.disqualify_at = set(disqualify_at)
        self.seen: dict[str, list[str]] = {"A": [], "B": []}
        self.call_log: list[str] = []      # arm ids, in call order — the interleave itself
        self.clients: list = []
        self.budgets: list = []

    def __call__(self, client, record, scenario, cfg, budget) -> dict:
        arm = scenario["id"]
        index = len(self.seen[arm])
        if self.raise_at == (arm, index):
            raise BudgetExhausted("simulated ceiling refusal")
        self.seen[arm].append(record["artifact_id"])
        self.call_log.append(arm)
        self.clients.append(client)
        self.budgets.append(budget)
        if (arm, index) in self.disqualify_at:
            return _fake_result(record["artifact_id"], disqualified_reason="probe_error")
        return _fake_result(record["artifact_id"], evidence_modes=self.evidence[arm])


def _fake_result(record_id: str, evidence_modes: list[str] | None = None,
                 disqualified_reason: str | None = None) -> dict:
    """A `ProbeAndScoreResult` carrying only the five keys §7 reads off one."""
    modes = list(evidence_modes or [])
    return {
        "record_id": record_id,
        "disqualified_reason": disqualified_reason,
        "resolving_urls": [],
        "stage_a": None, "stage_b": None, "judge": None,
        "citation": None, "date": None, "obligation": None,
        "passes_failure_bar": disqualified_reason is None and bool(modes),
        "evidence_modes": [] if disqualified_reason else modes,
    }


@pytest.fixture
def fake_probe(monkeypatch):
    """Installs a `_FakeProbe` over the module global the round loop calls."""

    def install(**kwargs) -> _FakeProbe:
        probe = _FakeProbe(**kwargs)
        monkeypatch.setattr(scenario_decision, "probe_and_score_one", probe)
        return probe

    return install


# ---------------------------------------------------------------------------
# THE critical property: the arms interleave
# ---------------------------------------------------------------------------


def test_arms_advance_one_record_each_in_lockstep(fake_probe):
    """The reason this module exists. Run A to completion and then B, and any
    budget stop truncates B alone and hands the win to A — invisibly, since A is
    also the tie-break. The call order itself is the guarantee."""
    probe = fake_probe(evidence={"A": ["citation_fabricated"], "B": ["citation_fabricated"]})

    decide_scenario(_CLIENT, _pool(4, 4), _cfg(scenario_trial_size=4, scenario_trial_min=1), _BUDGET)

    assert probe.call_log == ["A", "B", "A", "B", "A", "B", "A", "B"]


def test_budget_exhaustion_truncates_both_arms_equally(fake_probe):
    """Exhaustion mid-round 7 (on arm B's record, after arm A's already succeeded)
    leaves BOTH arms at 6: the in-flight round is discarded whole, including arm A's
    perfectly good result. And A is NOT declared winner off a fuller arm — with the
    arms equal at 6, B's strictly higher mean takes it."""
    probe = fake_probe(
        evidence={"A": ["citation_fabricated"], "B": ["citation_fabricated", "violation"]},
        raise_at=("B", 6),      # round index 6 == the 7th round; arm A's record already probed
    )

    decision = decide_scenario(_CLIENT, _pool(30, 30),
                               _cfg(scenario_trial_size=30, scenario_trial_min=5), _BUDGET)

    assert decision["stop_reason"] == "spend_ceiling"
    assert decision["trial_planned"] == {"A": 30, "B": 30}
    # Both arms at 6 — not 7 and 6, and not 30 and 6.
    assert decision["trial_completed"] == {"A": 6, "B": 6}
    assert len(decision["probed_ids"]["A"]) == len(decision["probed_ids"]["B"]) == 6
    # Arm A's round-7 record WAS probed, and is deliberately not counted: a
    # half-finished pair is never scored, or the asymmetry comes straight back.
    assert len(probe.seen["A"]) == 7
    assert probe.seen["A"][6] not in decision["probed_ids"]["A"]
    # The whole point: the budget did not pick the winner.
    assert decision["outcome"] == "decided"
    assert decision["winner"] == "B"


def test_discarded_round_drops_both_arms(fake_probe):
    """A disqualified record in ONE arm throws away the ENTIRE round — the other
    arm's result included. A dead URL or an exhausted retry is infrastructure noise;
    letting it land in one arm only would let that noise decide the scenario.

    Disqualified from BOTH arms (round 2 via A, round 4 via B): a check that reads
    only one arm's result reintroduces the exact defect — the other arm's
    disqualification lands in `probed` with `passes_failure_bar=False`, dragging its
    own mean down while its partner's result is counted."""
    probe = fake_probe(
        evidence={"A": ["citation_fabricated"], "B": ["citation_fabricated"]},
        disqualify_at=(("A", 2), ("B", 4)),
    )

    decision = decide_scenario(_CLIENT, _pool(10, 10),
                               _cfg(scenario_trial_size=10, scenario_trial_min=1), _BUDGET)

    assert decision["discarded_rounds"] == 2
    assert decision["stop_reason"] == "complete"      # a discard is not a stop
    # Every round still ran; only rounds 2 and 4's PAIRS are uncounted, in both arms.
    assert len(probe.seen["A"]) == len(probe.seen["B"]) == 10
    assert decision["trial_completed"] == {"A": 8, "B": 8}
    for arm, discarded_round in (("A", 2), ("B", 4)):
        for other in ("A", "B"):
            assert probe.seen[other][discarded_round] not in decision["probed_ids"][other], (
                f"round {discarded_round} was disqualified via arm {arm}; arm {other}'s "
                f"record from that round must not be counted")


# ---------------------------------------------------------------------------
# Sufficiency — reading a winner out of a trial that actually happened
# ---------------------------------------------------------------------------


def test_insufficient_trial_returns_no_winner(fake_probe):
    """Below `scenario_trial_min`, `>=` over two three-record arms is a coin-flip
    wearing the probe's clothes. No winner is claimed — and the result is still a
    FULL ScenarioDecision (scores and all), because it is the one shape a reader
    most needs to diagnose.

    NOTE: this test covers `decide_scenario`'s half of the behavior. The other half
    — "`run_prep` locks no scenario and exits 0" — belongs to `run_prep.py::main`,
    which lands in P5.1 and does not exist yet; `test_run_prep.py` owns it. Flagged
    in the task report.
    """
    fake_probe(evidence={"A": ["citation_fabricated"], "B": ["citation_fabricated"]},
               raise_at=("B", 3))

    decision = decide_scenario(_CLIENT, _pool(30, 30),
                               _cfg(scenario_trial_size=30, scenario_trial_min=10), _BUDGET)

    assert decision["outcome"] == "insufficient_trial"
    assert decision["winner"] is None
    assert decision["stop_reason"] == "spend_ceiling"
    assert decision["trial_completed"] == {"A": 3, "B": 3}    # 3 < min(30, 10)
    # Reported anyway — a reader should see WHAT the partial arms scored, even
    # though it is not a basis for a winner.
    assert decision["strength_scores"] == {"A": 1.0, "B": 1.0}
    assert decision["survivor_counts"] == {"A": 3, "B": 3}


def test_small_eligible_pool_is_sufficient_when_fully_probed(fake_probe):
    """A legitimately small eligible pool is not a failure. Three records planned,
    three completed — the arm did everything the corpus offered, so `scenario_trial_min`
    does not veto it (the floor is `min(planned, trial_min)`, not `trial_min`)."""
    fake_probe(evidence={"A": ["citation_fabricated"], "B": ["citation_fabricated"]})

    decision = decide_scenario(_CLIENT, _pool(3, 3),
                               _cfg(scenario_trial_size=30, scenario_trial_min=10), _BUDGET)

    assert decision["trial_planned"] == {"A": 3, "B": 3}      # never padded to 30
    assert decision["trial_completed"] == {"A": 3, "B": 3}
    assert decision["outcome"] == "decided"
    assert decision["winner"] == "A"


def test_trial_is_bounded_by_scenario_trial_size(fake_probe):
    """The trial is a BOUNDED sample — a 50-record eligible pool is probed 4 deep,
    not 50 deep. This is the only thing standing between a decision phase that costs
    ~60 API calls and one that sweeps the whole corpus at three calls a record until
    the ceiling stops it — which would then report `spend_ceiling`, and quite possibly
    `insufficient_trial`, making the regression both expensive AND disguised as a
    budget problem."""
    probe = fake_probe(evidence={"A": ["citation_fabricated"], "B": ["citation_fabricated"]})

    decision = decide_scenario(_CLIENT, _pool(50, 50),
                               _cfg(scenario_trial_size=4, scenario_trial_min=1), _BUDGET)

    assert decision["trial_planned"] == {"A": 4, "B": 4}        # never the full 50
    assert decision["trial_completed"] == {"A": 4, "B": 4}
    assert len(probe.seen["A"]) == len(probe.seen["B"]) == 4    # nothing beyond was spent on


def test_an_arm_that_never_ran_cannot_win_by_tie_break(fake_probe):
    """DEVIATION 1's sharpest case (module docstring, case (ii)). Arm A has NO
    eligible records; arm B probed 20 and found nothing. §7's `0 >= min(0, 10)` makes
    A "sufficient" at a mean of 0.0, and `0.0 >= 0.0` hands A the win — off ZERO
    probes, against the arm that did the work. `mean_strength([])` is the absence of a
    measurement, not the worst possible score.

    `evidence={"A": [], "B": []}` is load-bearing: if B scored above zero it would win
    under §7's rule too, and the defect would hide."""
    fake_probe(evidence={"A": [], "B": []})

    decision = decide_scenario(_CLIENT, _pool(0, 20), _cfg(scenario_trial_min=10), _BUDGET)

    assert decision["trial_planned"] == {"A": 0, "B": 20}
    assert decision["strength_scores"] == {"A": 0.0, "B": 0.0}
    assert decision["outcome"] == "insufficient_trial"
    assert decision["winner"] is None


def test_empty_eligible_pool_is_insufficient_not_a_win_for_a(fake_probe):
    """DEVIATION 1, case (iii) — the walkover. Arm A probes 20 records on real
    evidence; arm B has no eligible records at all. §7's rule declares A the winner,
    but B's 0.0 says nothing about scenario B and no re-run will make it say anything.
    An untried scenario is not scored against in either direction, so the guard is
    uniform rather than only protecting the winner's arm.

    See the module docstring: this is the case that reaches `insufficient_trial` with
    the budget intact, which §7's cost argument does not cover — flagged, deliberately
    resolved in the non-admitting direction."""
    fake_probe(evidence={"A": ["citation_fabricated"], "B": ["citation_fabricated"]})

    decision = decide_scenario(_CLIENT, _pool(20, 0), _cfg(scenario_trial_min=10), _BUDGET)

    assert decision["trial_planned"] == {"A": 20, "B": 0}
    assert decision["strength_scores"] == {"A": 1.0, "B": 0.0}   # A had real evidence
    assert decision["outcome"] == "insufficient_trial"
    assert decision["winner"] is None


# ---------------------------------------------------------------------------
# The decision rule: mean_strength, and nothing else
# ---------------------------------------------------------------------------


def test_mean_strength_tie_breaks_to_a(fake_probe):
    """`>=`, not `>` — goal #10's tie-break, mechanical and never a stall."""
    fake_probe(evidence={"A": ["citation_fabricated"], "B": ["violation"]})

    decision = decide_scenario(_CLIENT, _pool(10, 10), _cfg(scenario_trial_min=10), _BUDGET)

    assert decision["strength_scores"] == {"A": 1.0, "B": 1.0}
    assert decision["winner"] == "A"


def test_both_arms_scoring_zero_still_resolves_to_a(fake_probe):
    """The degenerate case: both arms ran, neither yielded a survivor. `0.0 >= 0.0`
    resolves to A rather than stalling."""
    fake_probe(evidence={"A": [], "B": []})

    decision = decide_scenario(_CLIENT, _pool(10, 10), _cfg(scenario_trial_min=10), _BUDGET)

    assert decision["strength_scores"] == {"A": 0.0, "B": 0.0}
    assert decision["survivor_counts"] == {"A": 0, "B": 0}
    assert decision["outcome"] == "decided"
    assert decision["winner"] == "A"


def test_b_wins_on_higher_mean_even_with_a_smaller_trial(fake_probe):
    """The reason the metric is a MEAN and not a sum. Arm A fields 20 records at
    strength 1 (sum 20); arm B fields 5 at strength 2 (sum 10). A sum hands it to A
    purely for having a bigger eligible pool in this corpus — an unequal-sampling
    artifact, not evidence that the baseline fails more often under A's framing."""
    fake_probe(evidence={"A": ["citation_fabricated"],
                         "B": ["citation_fabricated", "violation"]})

    decision = decide_scenario(_CLIENT, _pool(20, 5),
                               _cfg(scenario_trial_size=20, scenario_trial_min=5), _BUDGET)

    assert decision["trial_completed"] == {"A": 20, "B": 5}
    assert decision["strength_scores"] == {"A": 1.0, "B": 2.0}
    assert decision["winner"] == "B"


def test_stage_a_survivor_counts_are_reported_never_consulted(fake_probe):
    """§7's Goal issue callout: `stage_a_survivor_counts` is DIAGNOSTIC ONLY. Arm A
    wins on mean strength with ZERO records carrying `missed_obligation` — i.e. the
    winner cannot support the live demo — and the decision rule does not blink.
    Surfacing it here is what makes that visible before curation spends anything."""
    fake_probe(evidence={"A": ["citation_fabricated", "date_wrong"], "B": ["violation"]})

    decision = decide_scenario(_CLIENT, _pool(10, 10), _cfg(scenario_trial_min=10), _BUDGET)

    assert decision["winner"] == "A"
    assert decision["stage_a_survivor_counts"] == {"A": 0, "B": 10}


# ---------------------------------------------------------------------------
# Eligibility & threading
# ---------------------------------------------------------------------------


def test_each_arm_probes_only_its_own_eligible_records(fake_probe):
    """Both arms draw from the SAME pool, filtered to their own eligibility. A
    record neither scenario could plausibly govern is never probed at all — probing
    it would measure "out of domain", not "does the baseline fail here"."""
    ineligible = {
        "artifact_id": "x-0000", "update_type": "guidance",
        "jurisdiction_country": "US", "jurisdiction_bloc": None,
        "impacted_business": {"industry": ["Food Safety"]},
        "impacted_functions": ["Operations"], "reconciled_published_date": "2026-04-01",
    }
    probe = fake_probe(evidence={"A": ["citation_fabricated"], "B": ["citation_fabricated"]})

    decision = decide_scenario(_CLIENT, _pool(3, 3) + [ineligible],
                               _cfg(scenario_trial_min=1), _BUDGET)

    assert all(rid.startswith("a-") for rid in decision["probed_ids"]["A"])
    assert all(rid.startswith("b-") for rid in decision["probed_ids"]["B"])
    assert "x-0000" not in probe.seen["A"] + probe.seen["B"]


def test_client_and_budget_are_threaded_through_untouched(fake_probe):
    """Both arms draw against the ONE shared `SpendBudget` — there is no separate
    "scenario budget" — and the client is passed straight through, which is what
    makes every test in this module free."""
    probe = fake_probe(evidence={"A": ["citation_fabricated"], "B": ["citation_fabricated"]})

    decide_scenario(_CLIENT, _pool(2, 2), _cfg(scenario_trial_min=1), _BUDGET)

    assert probe.clients == [_CLIENT] * 4
    assert probe.budgets == [_BUDGET] * 4


# ---------------------------------------------------------------------------
# The evidence file's shape
# ---------------------------------------------------------------------------


def test_evidence_file_shape(fake_probe):
    """`run_prep.py::main` does `write_json(decision["evidence_path"], decision)` on
    BOTH outcomes, so the decision must be exactly §7's pinned field set and must
    round-trip through JSON with nothing lost."""
    probe = fake_probe(evidence={"A": ["citation_fabricated", "violation"],
                                 "B": ["violation"]})

    decision = decide_scenario(_CLIENT, _pool(3, 3), _cfg(scenario_trial_min=1), _BUDGET)

    assert set(decision) == set(ScenarioDecision.__annotations__)
    assert decision["evidence_path"] == "data/scratch/scenario_decision.json"
    datetime.fromisoformat(decision["decided_at"])          # ISO 8601, parseable
    assert json.loads(json.dumps(decision)) == decision     # no un-serializable value
    # §7 pins probed_ids as "the record ids each arm actually probed AND scored, IN
    # ORDER" — run_curation takes the winner's list as exclude_ids.
    assert decision["probed_ids"] == probe.seen
    assert decision == {
        "outcome": "decided", "winner": "A", "stop_reason": "complete",
        "discarded_rounds": 0,
        "strength_scores": {"A": 2.0, "B": 1.0},
        "survivor_counts": {"A": 3, "B": 3},
        "stage_a_survivor_counts": {"A": 3, "B": 3},
        "probed_ids": probe.seen,
        "trial_planned": {"A": 3, "B": 3}, "trial_completed": {"A": 3, "B": 3},
        "decided_at": decision["decided_at"],
        "evidence_path": "data/scratch/scenario_decision.json",
    }


def test_insufficient_trial_is_a_full_decision_differing_only_in_winner(fake_probe):
    """An `insufficient_trial` result is written to the same file and read by the
    same tooling as a decided one. `winner` is the ONLY field that differs, and it
    differs by being None rather than by being absent."""
    fake_probe(evidence={"A": ["citation_fabricated"], "B": ["citation_fabricated"]},
               raise_at=("A", 2))

    decision = decide_scenario(_CLIENT, _pool(30, 30), _cfg(scenario_trial_min=10), _BUDGET)

    assert decision["outcome"] == "insufficient_trial"
    assert set(decision) == set(ScenarioDecision.__annotations__)
    assert json.loads(json.dumps(decision)) == decision


# ---------------------------------------------------------------------------
# strength / mean_strength as units
# ---------------------------------------------------------------------------


def test_strength_is_zero_for_a_non_survivor():
    assert strength(_fake_result("r-1", evidence_modes=[])) == 0.0


def test_strength_counts_distinct_failure_modes():
    """Mode COUNT, with no +confidence term: a record failing on two dimensions
    outweighs one failing on a single dimension, and every dimension counts the
    same. Weighting `missed_obligation` would re-rank the SCENARIOS by Stage-A
    evidence — relitigating goal #10 under the guise of a bug fix."""
    assert strength(_fake_result("r-1", evidence_modes=["citation_fabricated"])) == 1.0
    assert strength(_fake_result("r-2", evidence_modes=["violation"])) == 1.0
    assert strength(
        _fake_result("r-3", evidence_modes=["citation_fabricated", "violation"])) == 2.0


def test_mean_strength_denominator_is_the_trial_size_not_the_survivor_count():
    """One 2-mode survivor in a 4-record trial is 0.5, not 2.0 — a scenario cannot
    win on a single lucky record, and a lower survivor RATE lowers the mean."""
    probed = [_fake_result("r-1", evidence_modes=["citation_fabricated", "violation"])]
    probed += [_fake_result(f"r-{i}", evidence_modes=[]) for i in range(2, 5)]

    assert mean_strength(probed) == 0.5


def test_mean_strength_of_an_empty_arm_is_zero():
    assert mean_strength([]) == 0.0


# ---------------------------------------------------------------------------
# The vocabulary trap: `evidence_modes` holds SCORER literals, not shipped names
# ---------------------------------------------------------------------------

def _real_evidence_modes(*, obligation_fails: bool) -> list[str]:
    """`evidence_modes` built by the REAL scorer, never hand-typed.

    This helper exists because `_fake_result`'s caller-supplied `evidence_modes`
    is exactly how the always-zero `stage_a_survivor_counts` bug survived: the
    tests passed `"missed_obligation"`, a name `passes_failure_bar` cannot emit,
    so the counter's name-match looked correct against fixtures and matched
    nothing against the pipeline. Anything asserting on the CONTENT of
    `evidence_modes` must source it from `passes_failure_bar` itself.
    """
    citation: CitationScore = {
        "outcome": "citation_fabricated", "baseline_url": "https://example.invalid/x",
        "matched_ground_truth_url": None, "url_status": "unresolvable", "is_failure": True,
    }
    date: DateScore = {
        "outcome": "date_uncertain_attribution", "ground_truth_date": None,
        "baseline_date": None, "baseline_date_normalized": None, "is_failure": False,
    }
    obligation: ObligationScore = {
        "outcome": "violation" if obligation_fails else "compliant",
        "confidence": 0.9, "applies_to_draft": True,
        "omission_material": True, "is_failure": obligation_fails,
    }
    _, modes = passes_failure_bar(citation, date, obligation)
    return modes


def test_scorer_never_emits_the_shipped_obligation_name():
    """The trap itself, pinned. `"missed_obligation"` is the SHIPPED rename (§5);
    the scorer says `"violation"`. Any `in evidence_modes` test against the shipped
    name is dead code that reports zero forever."""
    modes = _real_evidence_modes(obligation_fails=True)
    assert "violation" in modes
    assert "missed_obligation" not in modes
    assert SCORE_OUTCOME_TO_FAILURE_MODE["violation"] == "missed_obligation"


def test_stage_a_survivor_counts_uses_real_scorer_vocabulary(fake_probe):
    """`stage_a_survivor_counts` must count obligation failures the pipeline can
    actually produce. It previously matched the shipped name against scorer
    literals and was ALWAYS ZERO — so §7's "surface this before curation spends
    anything" check could not fire, and the run would discover it had no Stage-A
    evidence only at `emit_template_config`, after the money was gone."""
    modes = _real_evidence_modes(obligation_fails=True)
    fake_probe(evidence={"A": modes, "B": modes})

    decision = decide_scenario(_CLIENT, _pool(6, 6),
                               _cfg(scenario_trial_size=30, scenario_trial_min=3), _BUDGET)

    assert decision["stage_a_survivor_counts"]["A"] > 0, (
        "every probed record carries a real `violation` outcome, so the Stage-A "
        "counter cannot legitimately be zero")
    assert decision["stage_a_survivor_counts"]["B"] > 0
