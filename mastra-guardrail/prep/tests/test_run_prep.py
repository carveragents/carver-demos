"""`run_prep.py` — the entrypoint (spec §3's pinned `main`, plan P5.1).

**Everything here fakes `decide_scenario`/`run_curation`.** What is under test is
`main`'s STRUCTURE — the order of its phases, the branches that return before the
flow starts, and the `finally` that fires on all four exits. `test_curate.py` and
`test_scenario_decision.py` already own what those two functions do; a stub keeps
this file about the entrypoint's own contract.

**Zero billed calls.** `make_client` is faked in every test that reaches the main
flow, and the `--review` branch is asserted to construct no client at all.
"""
from __future__ import annotations

import json
from types import SimpleNamespace

import pytest

from mastra_prep import run_prep
from mastra_prep.budget import BudgetExhausted
from mastra_prep.run_prep import (
    ProbeLogClient,
    main,
    report_curation,
    report_insufficient_trial,
)
from stubs import RaisingStubClient, StubOpenAIClient

_CONFIG_TEMPLATE = """\
model_router_string: openai/gpt-5.6-sol
annotations_path: {annotations}
candidate_cutoff_date: "2026-03-01"
sample_seed: 42
probe_batch_size: 40
target_set_size: 200
probe_max_records: 400
scenario_trial_size: 30
scenario_trial_min: 10
price_input_per_million_usd: 5.00
price_output_per_million_usd: 30.00
total_spend_ceiling_usd: 120.0
judge_confidence_floor: 0.7
dotenv_path: {dotenv}
cleared_dir: {cleared}
scratch_dir: {scratch}
"""


# ---------------------------------------------------------------------------
# Fixtures & builders
# ---------------------------------------------------------------------------

@pytest.fixture
def workspace(tmp_path):
    """A throwaway prep workspace: a valid `config.yaml` whose `cleared_dir` and
    `scratch_dir` point inside `tmp_path`, so no test can touch the real
    `data/cleared/`."""
    cleared = tmp_path / "cleared"
    scratch = tmp_path / "scratch"
    cleared.mkdir()
    scratch.mkdir()
    config = tmp_path / "config.yaml"
    config.write_text(_CONFIG_TEMPLATE.format(
        annotations=tmp_path / "annotations.jsonl", dotenv=tmp_path / ".env",
        cleared=cleared, scratch=scratch))
    return SimpleNamespace(root=tmp_path, config=config, cleared=cleared, scratch=scratch,
                           argv=["--config", str(config)])


def _record(artifact_id: str, *, eligible: bool) -> dict:
    """`extract_record`'s flat shape. `eligible` toggles scenario A's jurisdiction
    gate (EU/EEA only): a US record with the same AI tag is is_eligible=False."""
    return {
        "artifact_id": artifact_id,
        "topic_id": "topic-1",
        "source_id": "src-1",
        "title": f"Title {artifact_id}",
        "regulator_name": "MFSA",
        "jurisdiction_scope": "national",
        "jurisdiction_country": "DE" if eligible else "US",
        "jurisdiction_bloc": None,
        "jurisdiction_region": None,
        "update_type": "guidance",
        "impact_label": "high",
        "objective": "obj",
        "what_changed": "changed",
        "why_it_matters": "matters",
        "key_requirements": ["do the thing"],
        "compliance_date": "2026-09-01",
        "impacted_business": {"size": ["SME"], "type": ["Bank"], "industry": ["Generative AI"]},
        "impacted_functions": ["Product"],
        "reconciled_published_date": "2026-04-01",
    }


def _decision(workspace, **overrides) -> dict:
    base = {
        "outcome": "decided",
        "winner": "A",
        "stop_reason": "complete",
        "discarded_rounds": 0,
        "strength_scores": {"A": 1.84, "B": 1.12},
        "survivor_counts": {"A": 12, "B": 8},
        "stage_a_survivor_counts": {"A": 5, "B": 3},
        "probed_ids": {"A": ["art-eligible-0"], "B": []},
        "trial_planned": {"A": 30, "B": 30},
        "trial_completed": {"A": 30, "B": 30},
        "decided_at": "2026-07-16T10:00:00+00:00",
        "evidence_path": str(workspace.scratch / "scenario_decision.json"),
    }
    base.update(overrides)
    return base


def _survivor(record_id: str, evidence_modes=("citation_fabricated",)) -> dict:
    return {
        "record_id": record_id, "disqualified_reason": None,
        "resolving_urls": [("MFSA BR/99", "https://mfsa.mt/br-99")],
        "stage_a": {"draft_text": "draft", "called_at": "2026-07-16T10:00:00+00:00"},
        "stage_b": {"source_name": "BR/99", "source_url": "https://mfsa.mt/fake",
                    "compliance_date": "2026-09-01"},
        "judge": {"verdicts": [{"rationale": "no disclosure"}]},
        "citation": None, "date": None,
        "obligation": {"outcome": "violation", "confidence": 0.9, "applies_to_draft": True,
                       "omission_material": True, "is_failure": "violation" in evidence_modes},
        "passes_failure_bar": True, "evidence_modes": list(evidence_modes),
    }


def _curation_result(survivors=(), probed=0, stop_reason="pool_exhausted") -> dict:
    return {"survivors": list(survivors), "probed": probed, "spend_usd": 16.84,
            "stop_reason": stop_reason}


class _FakeBudget:
    """Records whether the audit ran. `leaked=True` makes
    `assert_no_open_reservations()` raise, which is how the four exit-path tests
    prove the `finally` FIRED rather than merely was written."""

    def __init__(self, *args, leaked: bool = False, **kwargs):
        self.audited = 0
        self.leaked = leaked
        self.spend_so_far_usd = 16.84
        self.ceiling_usd = 120.0

    def assert_no_open_reservations(self) -> None:
        self.audited += 1
        if self.leaked:
            raise AssertionError("1 reservation was never terminated")


@pytest.fixture
def wired(monkeypatch, workspace):
    """Fake every seam `main` reaches through, and hand the test handles to them.

    `filter_candidates`/`stream_annotations` are faked rather than fed a real
    annotations file: this module's contract is what `main` does with candidates,
    not §2's filter.
    """
    calls = SimpleNamespace(curation=[], decision=[], budgets=[], client=None)

    def fake_make_client():
        calls.client = StubOpenAIClient("{}")
        return calls.client

    def fake_budget(*args, **kwargs):
        budget = _FakeBudget(*args, **kwargs)
        calls.budgets.append(budget)
        return budget

    monkeypatch.setattr(run_prep, "make_client", fake_make_client)
    monkeypatch.setattr(run_prep, "load_env", lambda path: None)
    monkeypatch.setattr(run_prep, "stream_annotations", lambda path: iter([]))
    monkeypatch.setattr(run_prep, "SpendBudget", fake_budget)
    return calls


def _wire_pool(monkeypatch, records: list[dict]) -> None:
    monkeypatch.setattr(run_prep, "filter_candidates", lambda stream: iter(records))


def _wire_decision(monkeypatch, calls, decision: dict) -> None:
    def fake_decide(client, candidates, cfg, budget):
        calls.decision.append(list(candidates))
        return decision
    monkeypatch.setattr(run_prep, "decide_scenario", fake_decide)


def _wire_curation(monkeypatch, calls, result=None, raises: Exception | None = None) -> None:
    def fake_curation(client, candidates, scenario, cfg, budget, exclude_ids=frozenset()):
        calls.curation.append(SimpleNamespace(candidates=list(candidates), scenario=scenario,
                                             exclude_ids=exclude_ids))
        if raises is not None:
            raise raises
        return result if result is not None else _curation_result()
    monkeypatch.setattr(run_prep, "run_curation", fake_curation)


# ---------------------------------------------------------------------------
# §4's applicability fix — the filter that must happen BEFORE curation.
# ---------------------------------------------------------------------------

def test_main_filters_through_is_eligible_before_constructing_curations_input(
        monkeypatch, workspace, wired):
    """§4's applicability fix: every record `run_curation` ever probes is guaranteed
    scenario-eligible, because `main` filters the pool through `is_eligible(r,
    winner)` BEFORE building the list. `run_curation` states this as a precondition
    it does not re-check — so if `main` does not do it, nothing does, and an
    over-broad judge flag on a record with no real connection to the scenario would
    become "evidence".

    The trial's own probed ids arrive as `exclude_ids` (§7's winner's-curse note):
    curation measures a FRESH sample rather than re-probing the records the winner
    was chosen for out-performing on.
    """
    pool = [_record("art-eligible-0", eligible=True), _record("art-us-1", eligible=False),
            _record("art-eligible-2", eligible=True)]
    _wire_pool(monkeypatch, pool)
    _wire_decision(monkeypatch, wired, _decision(workspace))
    _wire_curation(monkeypatch, wired)

    main(workspace.argv)

    assert len(wired.curation) == 1
    seen = [r["artifact_id"] for r in wired.curation[0].candidates]
    assert seen == ["art-eligible-0", "art-eligible-2"], "the US record is not is_eligible for A"
    # decide_scenario, by contrast, gets the UNFILTERED pool — it runs its own
    # per-arm eligibility, and pre-filtering to one arm would rig the trial.
    assert len(wired.decision[0]) == 3
    assert wired.curation[0].exclude_ids == frozenset({"art-eligible-0"})


# ---------------------------------------------------------------------------
# insufficient_trial — the terminal state that is NOT an error.
# ---------------------------------------------------------------------------

def test_insufficient_trial_short_circuits(monkeypatch, workspace, wired):
    """`test_scenario_decision.py::test_insufficient_trial_returns_no_winner`'s other
    half, which that test's docstring explicitly hands to this file: on
    `outcome="insufficient_trial"` `main` **locks no scenario**, writes the evidence
    file, calls `run_curation` **zero** times, and returns normally (exit 0).

    Reading a winner out of a trial that never happened is what §7 rules out — and
    the cost of that mistake is a scenario locked in by budget exhaustion rather
    than by evidence, then curated against for real money.
    """
    decision = _decision(workspace, outcome="insufficient_trial", winner=None,
                         stop_reason="spend_ceiling", trial_completed={"A": 3, "B": 3})
    _wire_pool(monkeypatch, [_record("art-eligible-0", eligible=True)])
    _wire_decision(monkeypatch, wired, decision)
    _wire_curation(monkeypatch, wired)

    assert main(workspace.argv) is None            # returns normally -> exit 0

    assert wired.curation == [], "no curation may run without a locked scenario"
    written = json.loads((workspace.scratch / "scenario_decision.json").read_text())
    assert written["outcome"] == "insufficient_trial"
    assert written["winner"] is None
    assert wired.budgets[0].audited == 1           # the `finally` still ran


def test_report_insufficient_trial_distinguishes_never_ran_from_truncated(workspace):
    """D23: *"this arm never ran — widen eligibility or accept the walkover"* and
    *"this arm was truncated — raise the ceiling and re-run"* are different problems
    with **non-overlapping** fixes. §7 specifies only the second; emitting it for the
    first sends the operator to re-run a **deterministic dead end** — eligibility is
    a pure function of the corpus, so the run stops at the same place forever.
    """
    cfg = SimpleNamespace(scenario_trial_min=10)
    never_ran = report_insufficient_trial(
        _decision(workspace, outcome="insufficient_trial", winner=None, stop_reason="complete",
                  trial_planned={"A": 30, "B": 0}, trial_completed={"A": 30, "B": 0}), cfg=cfg)
    assert "arm B NEVER RAN" in never_ran
    assert "RE-RUNNING CHANGES NOTHING" in never_ran
    assert "widen scenario B's eligibility" in never_ran
    assert "walkover" in never_ran
    assert "raise total_spend_ceiling_usd" not in never_ran, (
        "the truncation fix must NOT be offered for an arm with no eligible records")

    truncated = report_insufficient_trial(
        _decision(workspace, outcome="insufficient_trial", winner=None,
                  stop_reason="spend_ceiling", trial_planned={"A": 30, "B": 30},
                  trial_completed={"A": 3, "B": 3}), cfg=cfg)
    assert "WAS TRUNCATED" in truncated
    assert "raise total_spend_ceiling_usd" in truncated
    assert "NEVER RAN" not in truncated
    assert "walkover" not in truncated


# ---------------------------------------------------------------------------
# The reservation audit — §3's `finally`.
# ---------------------------------------------------------------------------

def test_reservation_audit_runs_on_every_exit_path(monkeypatch, workspace, wired):
    """§3 pins the audit in a `finally` precisely because a leak check that only ran
    on the happy path would miss the runs most likely to leak — the failure paths are
    the ones that terminate reservations under pressure.

    All four exits, each asserted separately, each with a budget carrying a LEAKED
    handle so the audit's `AssertionError` proves the `finally` fired rather than
    merely was written. On the two exception paths the audit's error REPLACES the
    original (§3, deliberate): a leaked reservation means the spend figure in the
    original error's own report is wrong.
    """
    def leaky_budget(*args, **kwargs):
        budget = _FakeBudget(leaked=True)
        wired.budgets.append(budget)
        return budget
    monkeypatch.setattr(run_prep, "SpendBudget", leaky_budget)
    _wire_pool(monkeypatch, [_record("art-eligible-0", eligible=True)])

    # 1 — a clean finish.
    _wire_decision(monkeypatch, wired, _decision(workspace))
    _wire_curation(monkeypatch, wired)
    with pytest.raises(AssertionError, match="never terminated"):
        main(workspace.argv)

    # 2 — the insufficient_trial early return.
    _wire_decision(monkeypatch, wired, _decision(workspace, outcome="insufficient_trial",
                                                 winner=None))
    with pytest.raises(AssertionError, match="never terminated"):
        main(workspace.argv)

    # 3 — a BudgetExhausted stop propagating out of decide_scenario.
    def exhausted(*args, **kwargs):
        raise BudgetExhausted("ceiling refused the reservation")
    monkeypatch.setattr(run_prep, "decide_scenario", exhausted)
    with pytest.raises(AssertionError, match="never terminated"):
        main(workspace.argv)

    # 4 — an unexpected exception propagating out of run_curation.
    _wire_decision(monkeypatch, wired, _decision(workspace))
    _wire_curation(monkeypatch, wired, raises=RuntimeError("something nobody predicted"))
    with pytest.raises(AssertionError, match="never terminated"):
        main(workspace.argv)

    assert [b.audited for b in wired.budgets] == [1, 1, 1, 1]


# ---------------------------------------------------------------------------
# --review — the human checkpoint (§6, D25).
# ---------------------------------------------------------------------------

def test_review_branch_dispatches_to_review_module(monkeypatch, workspace, wired):
    """`--review` drives §6's loop and **never** `run_curation`/`decide_scenario`.
    It is a separate branch that returns before the main flow: the human checkpoint
    reads what the probe already recorded, and re-probing at review time would both
    spend money and let the evidence a reviewer sees differ from the evidence that
    admitted the record."""
    seen = {}

    def fake_loop(candidates, reviewer, **kwargs):
        seen["candidates"] = candidates
        seen["reviewer"] = reviewer
        seen["cleared_dir"] = kwargs["cleared_dir"]
        return {"approved": [], "rejected": []}

    monkeypatch.setattr(run_prep, "run_review_loop", fake_loop)
    monkeypatch.setattr(run_prep, "load_review_candidates", lambda path: [{"stub": True}])
    _wire_decision(monkeypatch, wired, _decision(workspace))
    _wire_curation(monkeypatch, wired)

    main(workspace.argv + ["--review", "--reviewer", "ana"])

    assert seen["reviewer"] == "ana"
    assert seen["candidates"] == [{"stub": True}]
    assert str(workspace.cleared) == str(seen["cleared_dir"])
    assert wired.curation == [] and wired.decision == []


def test_review_makes_no_api_calls(monkeypatch, workspace):
    """The branch runs to completion with a client that RAISES on any call — and
    `call_count == 0` proves it was never even reached. Every input `--review` reads
    was recorded at probe time, including the resolving URLs (§5: human review
    re-resolves nothing), so there is nothing left to call the API for."""
    client = RaisingStubClient(exc=AssertionError("--review must make no API call"))
    monkeypatch.setattr(run_prep, "make_client", lambda: client)
    monkeypatch.setattr(run_prep, "load_env", lambda path: None)
    monkeypatch.setattr(run_prep, "load_review_candidates", lambda path: [])
    monkeypatch.setattr(run_prep, "run_review_loop",
                        lambda candidates, reviewer, **kwargs: {"approved": [], "rejected": []})

    main(workspace.argv + ["--review", "--reviewer=ana"])

    assert client.call_count == 0


def test_review_is_the_only_writer_of_cleared_dir(monkeypatch, workspace, wired):
    """The goal's hard constraint, checked rather than assumed (P4.2): no argv branch
    other than `--review` puts anything in `data/cleared/`. The full curation flow and
    `--verify-cleared` both run here against an EMPTY cleared dir and must leave it
    empty."""
    _wire_pool(monkeypatch, [_record("art-eligible-0", eligible=True)])
    _wire_decision(monkeypatch, wired, _decision(workspace))
    _wire_curation(monkeypatch, wired,
                   result=_curation_result([_survivor("art-eligible-0")], probed=1))

    main(workspace.argv)                                   # the full curation flow
    main(workspace.argv + ["--verify-cleared"])            # the validator

    assert list(workspace.cleared.iterdir()) == [], "only review.py may write data/cleared/"
    # Survivors reached SCRATCH, which is §6's second construction proof: curation's
    # output waits for a human, it does not ship.
    queued = (workspace.scratch / "candidates_for_review.jsonl").read_text().splitlines()
    assert len(queued) == 1
    assert json.loads(queued[0])["source_record"]["artifact_id"] == "art-eligible-0"


def test_no_batch_approve_flag_exists_and_unknown_flags_are_refused(workspace):
    """§6's anti-padding table names "waiving human review" as a rigging mode, and
    D25 is the record of that cut being proposed once, for convenience, and reversed.
    No such flag exists — and an unrecognised flag is REFUSED rather than ignored.

    Ignoring it would be worse than either alternative: a typo'd `--verify-clared`
    would silently start the full curation flow — real client, real budget, ~$17
    against the user's key — when the operator asked for a free read-only check.
    `config.py` takes the identical posture on unknown config keys.
    """
    for flag in ("--approve-all", "--batch-approve", "--yes", "--auto-approve",
                 "--verify-clared", "--reveiw"):
        with pytest.raises(SystemExit, match="unknown flag"):
            main(workspace.argv + [flag])

    assert list(workspace.cleared.iterdir()) == []


def test_known_flag_values_are_not_mistaken_for_flags(monkeypatch, workspace, wired):
    """`--config <path>`'s value must not be inspected as a flag — a path is not an
    argv token this entrypoint gets to have an opinion about."""
    _wire_pool(monkeypatch, [_record("art-eligible-0", eligible=True)])
    _wire_decision(monkeypatch, wired, _decision(workspace))
    _wire_curation(monkeypatch, wired)

    main(workspace.argv)                                   # --config <path>
    main(["--config=" + str(workspace.config)])            # --config=<path>


# ---------------------------------------------------------------------------
# --verify-cleared — STRUCTURE only, no network.
# ---------------------------------------------------------------------------

def _cleared_record(**overrides) -> dict:
    base = {
        "id": "art-0001", "title": "T", "regulator_name": "MFSA",
        "jurisdiction": {"scope": "national", "country": "MT", "bloc": "EU", "region_name": None},
        "update_type": "guidance", "impact_label": "high", "objective": "o",
        "what_changed": "w", "why_it_matters": "y", "key_requirements": ["k"],
        "compliance_date": "2026-09-01",
        "citation": {"name": "MFSA BR/99", "url": "https://mfsa.mt/br-99"},
        "impacted_business": {"size": ["SME"], "type": ["Bank"], "industry": ["AI"]},
        "impacted_functions": ["Product"], "scenario": "A",
        "baseline_failures": [{"mode": "citation_fabricated", "stage": "B",
                               "baseline_response_excerpt": "made it up",
                               "judge_rationale": None}],
        "human_review": {"reviewer": "ana", "reviewed_at": "2026-07-16T10:00:00+00:00",
                         "attestation": "approved", "obligation_applies_confirmed": None,
                         "artifact_capable_of_violation_confirmed": None,
                         "omission_materiality_confirmed": None},
        "source": {"artifact_id": "art-0001", "topic_id": "t", "source_id": "s",
                   "snapshot_date": "2026-07-11"},
        "probed_at": "2026-07-16T10:00:00+00:00", "model_id": "openai/gpt-5.6-sol",
        "model_cutoff": "2026-02-16",
    }
    base.update(overrides)
    return base


def test_verify_cleared_passes_a_valid_set_and_makes_no_network_calls(monkeypatch, workspace):
    """§14 puts post-clearing re-validation explicitly OUT OF SCOPE for v1. An
    earlier draft had this flag "re-resolve each citation.url", which silently adds
    a URL crawler the spec excludes — and quoted §14's own exclusion two lines later.

    The guard is at the TRANSPORT, not at `resolve_url`: every module in this package
    binds `from .urls import resolve_url`, which captures the function object at
    import time, so monkeypatching `mastra_prep.urls.resolve_url` could never fire
    for the most likely way someone would add a crawler. `httpx.Client.request` is
    the one chokepoint `urls.py` actually goes through, and patching it catches a
    crawler added by ANY route, including a fresh `httpx` call written inline.
    """
    monkeypatch.setattr("httpx.Client.request",
                        lambda *a, **k: pytest.fail("--verify-cleared must make no network call"))
    monkeypatch.setattr("httpx.Client.send",
                        lambda *a, **k: pytest.fail("--verify-cleared must make no network call"))
    (workspace.cleared / "cleared_records.json").write_text(json.dumps([_cleared_record()]))

    main(workspace.argv + ["--verify-cleared"])            # no raise == pass


def test_verify_cleared_reports_how_many_citations_it_actually_checked(workspace, caplog):
    """The citation check needs the scratch queue that recorded the probe-time
    resolutions, and a vendored data/cleared/ (Phase 8) legitimately travels without
    it — which is exactly when someone runs this flag. Claiming coverage over records
    it skipped would make the success message false at the one moment it is read."""
    (workspace.cleared / "cleared_records.json").write_text(json.dumps([_cleared_record()]))

    with caplog.at_level("INFO", logger="mastra_prep"):
        main(workspace.argv + ["--verify-cleared"])

    assert "checked against the recorded resolving URLs for 0 of 1 record(s)" in caplog.text
    assert "were NOT checked" in caplog.text


def test_verify_cleared_rejects_an_unapproved_record(workspace):
    """The gate's whole point: a hand-edited attestation fails the process, non-zero,
    rather than printing a complaint nobody reads."""
    record = _cleared_record()
    record["human_review"]["attestation"] = "pending"
    (workspace.cleared / "cleared_records.json").write_text(json.dumps([record]))

    with pytest.raises(SystemExit, match="FAILED"):
        main(workspace.argv + ["--verify-cleared"])


def test_verify_cleared_rejects_a_citation_not_recorded_as_resolving(workspace):
    """`citation.url` must be one of the URLs THIS record recorded as resolving at
    probe time — checked against the queue that produced it, so the check needs no
    network. A citation nobody resolved is one somebody typed."""
    (workspace.scratch / "candidates_for_review.jsonl").write_text(json.dumps({
        "source_record": {"artifact_id": "art-0001"},
        "resolving_urls": [["MFSA BR/99", "https://mfsa.mt/br-99"]],
    }) + "\n")
    record = _cleared_record(citation={"name": "Invented", "url": "https://mfsa.mt/typed-by-hand"})
    (workspace.cleared / "cleared_records.json").write_text(json.dumps([record]))

    with pytest.raises(SystemExit, match="FAILED"):
        main(workspace.argv + ["--verify-cleared"])


# ---------------------------------------------------------------------------
# report_curation — the number a human reads to decide whether this worked.
# ---------------------------------------------------------------------------

def test_report_curation_states_all_three_ways_the_hit_rate_could_mislead(workspace):
    """§3 pins these fields because each is a way the headline number misleads:
    the denominator is the scenario-eligible subset (not the goal's headline 8,260),
    the rate is success-conditioned (curation stops at target, so it is biased
    upward), and survivors are not the shipped set (review can only reduce it).

    All three are printed. A reader who sees only the terminal output must not come
    away with a corpus-wide yield.
    """
    report = report_curation(
        _curation_result([_survivor(f"r-{i}", ("citation_fabricated", "violation"))
                          for i in range(137)], probed=400, stop_reason="target_reached"),
        _decision(workspace), candidate_count=8260, eligible_count=2104, ceiling_usd=120.0)

    assert "137 of 400 probed  = 34.2% hit rate" in report
    assert "2,104 scenario-eligible" in report
    assert "stop_reason=target_reached" in report
    assert "BIASED UPWARD" in report
    assert "NOT the 8,260" in report
    assert "survivors are NOT the shipped set" in report
    assert "run_prep.py --review" in report
    # The scorer's "violation" is renamed to §5's shipped label — a report that
    # skipped SCORE_OUTCOME_TO_FAILURE_MODE would print 0 for the one mode the demo
    # depends on.
    assert "missed_obligation    137" in report
    assert "$16.84 of $120.00 ceiling" in report
    assert "date_wrong           0" in report


def test_report_curation_zero_survivors_says_ship_nothing_rather_than_pad(workspace):
    """§14's zero-survivor case uses this same function: the same shape, plus goal
    #11's line, and exit 0. An honest empty result is a result, not an error."""
    report = report_curation(_curation_result([], probed=400, stop_reason="sweep_cap"),
                             _decision(workspace), candidate_count=8260, eligible_count=2104)

    assert "0 records survived" in report
    assert "ship nothing rather than pad" in report
    assert "--review" not in report, "there is nothing to review"


# ---------------------------------------------------------------------------
# The probe log — D22's insurance on the one phase that spends real money.
# ---------------------------------------------------------------------------

def test_probe_log_captures_every_call_including_one_that_dies(tmp_path):
    """D22: the log is what turns a run dying at record 380 of 400 into ONE paid run
    instead of two. So it must capture the call that DIED, not only the ones that
    returned — the wrapper writes at call time, which is why a mid-sweep stop still
    leaves every prior call on disk.

    Nothing reads this back: `--replay` is CUT. The claim the log supports is that
    the run is AUDITABLE, never that it is reproducible.
    """
    log_dir = tmp_path / "probe_log"
    inner = StubOpenAIClient(["draft text", "{}"])
    client = ProbeLogClient(inner, log_dir)

    client.chat.completions.create(model="gpt-5.6-sol", messages=[], reasoning_effort="medium",
                                   max_completion_tokens=3000)
    client.chat.completions.create(
        model="gpt-5.6-sol", messages=[], reasoning_effort="medium", max_completion_tokens=1500,
        response_format={"type": "json_schema",
                         "json_schema": {"name": "stage_b_citation_probe"}})

    dying = ProbeLogClient(RaisingStubClient(exc=RuntimeError("connection reset")), log_dir)
    with pytest.raises(RuntimeError):
        dying.chat.completions.create(
            model="gpt-5.6-sol", messages=[], reasoning_effort="medium",
            max_completion_tokens=1200,
            response_format={"type": "json_schema", "json_schema": {"name": "obligation_judge"}})

    # The stage is DERIVED from the payload's own schema name (Stage A passes none).
    assert sorted(p.name for p in log_dir.iterdir()) == [
        "0001_judge.json", "0001_stage_a.json", "0002_stage_b.json"]
    stage_a = json.loads((log_dir / "0001_stage_a.json").read_text())
    assert stage_a["response"]["content"] == "draft text"
    assert stage_a["request"]["max_completion_tokens"] == 3000
    assert "connection reset" in json.loads((log_dir / "0001_judge.json").read_text())["response"]["error"]


def test_probe_log_failure_never_kills_a_paid_run(tmp_path):
    """Insurance that burns down the house is worse than no insurance. A log dir
    that cannot be written must cost the transcript, never the $17 run in flight."""
    blocked = tmp_path / "not-a-dir"
    blocked.write_text("this is a file, so mkdir under it fails")
    client = ProbeLogClient(StubOpenAIClient("draft"), blocked / "probe_log")

    response = client.chat.completions.create(model="m", messages=[])

    assert response.choices[0].message.content == "draft"


def test_probe_log_stage_names_are_read_off_their_owning_modules():
    """The two schema names are DERIVED from `probe.py`/`judge.py`, never retyped —
    a literal copy would agree today and drift silently: rename
    `STAGE_B_RESPONSE_SCHEMA["name"]` and every Stage B call would log as `stage_a`
    with the suite green.

    The payloads here are built by the REAL `build_request_payload`, so the nesting
    the derivation reads (`response_format.json_schema.name`) is the nesting the
    real call sites produce — a hand-fabricated payload would test this file's guess
    at the shape rather than the shape.
    """
    from mastra_prep.budget import build_request_payload
    from mastra_prep.judge import JUDGE_RESPONSE_SCHEMA
    from mastra_prep.probe import STAGE_B_RESPONSE_SCHEMA

    def payload(schema):
        return build_request_payload(model="m", system_text="s", user_text="u",
                                     max_completion_tokens=100, reasoning_effort="medium",
                                     schema=schema)

    assert run_prep._stage_of_payload(payload(None)) == "stage_a"
    assert run_prep._stage_of_payload(payload(STAGE_B_RESPONSE_SCHEMA)) == "stage_b"
    assert run_prep._stage_of_payload(payload(JUDGE_RESPONSE_SCHEMA)) == "judge"
