"""The mechanical A/B scenario decision (spec §7) — a small, symmetric, PAIRED trial.

Prep's first phase. Each scenario is probed against a bounded sample of the records
it could plausibly govern, and the arm with the higher `mean_strength` wins. The
result is locked for the rest of prep and all of the template stage.

**THE ARMS INTERLEAVE. This is the module's reason for existing.** Running arm A to
completion and THEN arm B means any budget stop truncates B alone — the run then
compares a full 30-record A arm against a partial (or empty) B arm and declares A
the winner. That is not a scenario decision; it is the budget picking A, wearing the
probe's clothes. And it would be invisible: A winning is goal #10's own tie-break, so
nothing would look wrong. Interleaving fixes it structurally — the two arms advance
one record each, in lockstep, so a stop at round `i` leaves BOTH arms with `i`
records and whatever is compared is always like-for-like. A round that dies
half-finished is discarded from both arms, for the same reason: counting arm A's
surviving half of a broken pair reintroduces the exact asymmetry.

The same logic covers infrastructure noise. A dead ground-truth URL or an exhausted
retry (`disqualified_reason`) tells us nothing about whether the baseline fails, so
its whole round is thrown away and counted in `discarded_rounds` — deliberately kept
OUT of the comparison rather than landing in one arm only.

**Both arms draw against the ONE shared `SpendBudget`** (§3) — there is no separate
"scenario budget".

**This module does not WRITE the evidence file.** It reports the path it will be
written to (`evidence_path`); `run_prep.py::main` does
`write_json(decision["evidence_path"], decision)` on BOTH outcomes (§3's pinned
entrypoint). Keeping the write there is what lets every test here run without a
filesystem.

**Two places this module deliberately departs from §7's pinned pseudocode, both
flagged in the task report:**

  1. **An arm that planned ZERO records is never `sufficient`.** §7 pins the
     sufficiency test as `completed[sid] >= min(planned[sid], cfg.scenario_trial_min)`,
     which for an arm with NO eligible records at all reads `0 >= min(0, 10)` — i.e.
     `0 >= 0` — True. That arm is then "sufficient" and scores `0.0`, and the tie-break
     reads that `0.0` as if it were a measurement.

     **The root of it: `mean_strength([]) == 0.0` is the ABSENCE of a measurement
     wearing the costume of the worst possible score.** An arm that never ran did not
     score badly — it did not score. Comparing against it is not a comparison, in
     either direction, and §7 is explicit that the `>=` "does not license reading a
     winner out of a trial that never happened". Three shapes are reachable, and the
     rule is wrong on all three:

       (i)   planned {A: 0, B: 0}  -> `decided`, winner A, off zero probes in total.
       (ii)  planned {A: 0, B: 20} -> B probes 20 and finds nothing (mean 0.0); A
             probes NOTHING (mean 0.0); `0.0 >= 0.0` hands A the win. The sharpest
             case: the arm that did the work loses to the arm that never ran.
       (iii) planned {A: 20, B: 0} -> A wins a walkover on real evidence. The most
             defensible of the three, and still not a contest: B's `0.0` says nothing
             about scenario B, and no amount of re-running will make it say anything.

     Zero is categorically unlike any positive planned size — that is where the line
     is. At `planned == 1` the arm has thin but REAL evidence, and `min(planned,
     trial_min)` deliberately admits it (a legitimately small eligible pool is not a
     failure, §7 — `test_small_eligible_pool_is_sufficient_when_fully_probed`). At
     `planned == 0` there is no evidence to be thin. So the guard is uniform across
     both arms rather than only guarding the winner's: an untried scenario must not be
     scored against, whichever way the number would fall.

     Failing this way is also the non-admitting direction: the alternative locks a
     scenario in by an empty eligibility filter rather than by evidence, and then
     curates against it for real money. An empty pool instead becomes the honest
     terminal report `insufficient_trial` already specifies, naming which arm fell
     short and by how much — and an arm with zero eligible records in a corpus this
     size is itself a finding about the eligibility rules worth stopping for (goal
     #11: an awkward yield is a finding to report, not a problem to engineer around).
     **But see the task report:** case (iii) reaches `insufficient_trial` with the
     budget intact and the API healthy, which §7's "this costs nothing real" argument
     does not cover — its stated recovery (raise the ceiling and re-run) is a no-op
     against a deterministic eligibility filter. The honest recovery is a reviewed
     change to §7's own closed keyword lists, which §7 explicitly sanctions ("adding
     it is a normal, reviewable code change to a fixed constant") — but `run_prep.py`
     (P5.1) must therefore diagnose "this arm never ran" differently from "this arm
     was truncated", and §7 currently specifies only the latter.
  2. **`ScenarioDecision` is built once, by `_decision`, for both outcomes.** §7
     writes the twelve fields out twice — once per return path — and states that an
     `insufficient_trial` result is a FULL decision whose `winner` is "the ONLY field
     that differs, and it differs by being None rather than by being absent". One
     constructor makes that structurally true instead of true by convention: the two
     shapes cannot drift apart in a later edit. No field's value changes.

Intra-package imports: `budget` (`BudgetExhausted` — raised by any of a record's
three reservations and caught here to stop the trial), `curate`
(`probe_and_score_one` — the same per-record procedure curation uses, so the trial
and the sweep measure the identical thing), `sampling`, `scenarios`. §1's dependency
table also lists `probe`; nothing here calls it (its result types arrive inside
`ProbeAndScoreResult`), so it is not imported — flagged in the task report. `Settings`
is imported under TYPE_CHECKING only, as `curate.py` does: it is used purely as an
annotation, and `from __future__ import annotations` makes every annotation here a
string that is never evaluated at import time.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING, Literal, TypedDict

from .budget import BudgetExhausted, SpendBudget
from .curate import ProbeAndScoreResult, probe_and_score_one
from .sampling import stratified_sample_sequence
from .scenarios import SCENARIOS, is_eligible
from .schema import SCORE_OUTCOME_TO_FAILURE_MODE

if TYPE_CHECKING:
    from .config import Settings

# The two arms, in the order each round probes them. A fixed tuple rather than
# `SCENARIOS.keys()`: the round loop's call order is the interleave guarantee, and
# it must not ride on a dict's iteration order.
ARMS: tuple[str, str] = ("A", "B")

EVIDENCE_PATH = "data/scratch/scenario_decision.json"


class ScenarioDecision(TypedDict):
    outcome: Literal["decided", "insufficient_trial"]   # the discriminator
    winner: Literal["A", "B"] | None       # None IFF outcome == "insufficient_trial"
    stop_reason: Literal["complete", "spend_ceiling"]
    discarded_rounds: int                  # paired rounds thrown away because an arm's record was
                                           # disqualified (dead URL) or errored — infrastructure
                                           # noise, deliberately kept OUT of the comparison
    strength_scores: dict[str, float]      # {"A": ..., "B": ...}
    survivor_counts: dict[str, int]
    stage_a_survivor_counts: dict[str, int]  # survivors whose evidence includes missed_obligation,
                                             # i.e. the ones capable of supporting a live demo (§5).
                                             # DIAGNOSTIC ONLY: reported, never an input to `winner`
                                             # — goal #10's rule is locked and unchanged. Counted on
                                             # EVIDENCE alone (human review has not run at trial
                                             # time), so it is an UPPER BOUND on how many will
                                             # ultimately satisfy predicts_stage_a_violation (§5).
    probed_ids: dict[str, list[str]]       # the record ids each arm actually probed AND scored, in
                                           # order. run_prep.py passes the winner's list to
                                           # run_curation as exclude_ids, so curation samples FRESH
                                           # records and its hit rate is not measured on the very
                                           # records the scenario was selected for winning on.
    trial_planned: dict[str, int]          # min(len(eligible), scenario_trial_size) per arm — what
                                           # the trial SET OUT to probe. May legitimately differ
                                           # between arms if one scenario's eligible pool is
                                           # smaller; mean_strength normalizes for exactly that.
    trial_completed: dict[str, int]        # records actually probed AND scored per arm. Equals
                                           # trial_planned on a clean run; lower after a stop or a
                                           # discarded round. Reported separately so a truncated
                                           # trial can never be mistaken for a complete one.
    decided_at: str                        # ISO 8601 datetime
    evidence_path: str


def decide_scenario(client, trial_pool: list[dict], cfg: "Settings",
                    budget: SpendBudget) -> ScenarioDecision:
    """Probe both scenarios against the records each could plausibly govern, and
    return the full decision (§7).

    Both arms draw from the SAME underlying `trial_pool`, filtered to their own
    `is_eligible` predicate, ordered by the same seed, and bounded by the same
    `scenario_trial_size` — fair allocation despite possibly-unequal pool sizes. A
    pool smaller than `scenario_trial_size` is never padded; `mean_strength` is what
    makes the two arms comparable when they legitimately differ in size.

    Every round probes one record per arm, in `ARMS` order, and counts only if EVERY
    arm still in play produced a scored result. An arm whose eligible pool ran out
    simply stops advancing; the other continues alone.

    `BudgetExhausted` (including its `BudgetPoisoned` subclass) stops the trial where
    it fires — never retried (§15), and the in-flight round is discarded whole.
    """
    eligible = {arm: [r for r in trial_pool if is_eligible(r, SCENARIOS[arm])] for arm in ARMS}
    order = {arm: stratified_sample_sequence(eligible[arm], seed=cfg.sample_seed)[:cfg.scenario_trial_size]
             for arm in ARMS}
    planned = {arm: len(order[arm]) for arm in ARMS}
    probed: dict[str, list[ProbeAndScoreResult]] = {arm: [] for arm in ARMS}
    discarded_rounds = 0
    stop_reason: Literal["complete", "spend_ceiling"] = "complete"

    for index in range(max(planned.values())):
        round_results: dict[str, ProbeAndScoreResult] = {}
        try:
            for arm in ARMS:
                if index < planned[arm]:
                    round_results[arm] = probe_and_score_one(
                        client, order[arm][index], SCENARIOS[arm], cfg, budget)
        except BudgetExhausted:
            # DISCARD round_results — a half-finished pair is NEVER counted, since
            # counting it is exactly the asymmetry interleaving exists to remove.
            stop_reason = "spend_ceiling"
            break
        if any(r["disqualified_reason"] is not None for r in round_results.values()):
            discarded_rounds += 1
            continue
        for arm, result in round_results.items():
            probed[arm].append(result)

    completed = {arm: len(probed[arm]) for arm in ARMS}
    return _decision(
        sufficient=all(_arm_is_sufficient(planned[arm], completed[arm], cfg) for arm in ARMS),
        stop_reason=stop_reason, discarded_rounds=discarded_rounds,
        strengths={arm: mean_strength(probed[arm]) for arm in ARMS},
        probed=probed, planned=planned, completed=completed,
    )


def strength(result: ProbeAndScoreResult) -> float:
    """Per-record strength: the number of distinct failure modes a survivor carries;
    0.0 for a non-survivor. A record failing on two dimensions outweighs one failing
    on a single dimension.

    THE RANGE IS 1-2, NOT 1-3 — no third value is reachable. §4's fair-test rule makes
    3 impossible: `date_wrong` REQUIRES `citation_correct` (a date claim is only
    attributable once the citation independently confirms which document is meant),
    which is mutually exclusive with `citation_fabricated`. So `evidence_modes` is
    always a subset of {citation_fabricated, violation} or {date_wrong, violation} —
    never both citation modes, never all three.

    NOTE THE VOCABULARY, because it is a live trap. `evidence_modes` carries the
    SCORER's outcome literals, so the obligation failure reads `"violation"` — NOT
    the shipped dataset's `"missed_obligation"`, which is
    `SCORE_OUTCOME_TO_FAILURE_MODE`'s rename of it (§5). This function is immune (it
    counts, never names); `stage_a_survivor_counts` below was not.

    THERE IS NO +confidence TERM. It would apply only when `missed_obligation` is
    present, quietly re-ranking the two SCENARIOS by Stage-A evidence — which is
    relitigating goal #10 under the guise of a bug fix, in the very metric goal #10's
    rule reads. Mode COUNT is the neutral reading of "more and stronger": strength
    counts dimensions, and every dimension counts the same.
    """
    if not result["passes_failure_bar"]:
        return 0.0
    return float(len(result["evidence_modes"]))   # 1 or 2


def mean_strength(probed: list[ProbeAndScoreResult]) -> float:
    """MEAN strength across ALL probed records for a scenario (denominator = the
    scenario's actual trial size, NOT its survivor count) — deliberately not a sum.

    A sum lets a scenario win purely by fielding a LARGER trial (an artifact of that
    scenario's eligible pool happening to be bigger in this corpus), independent of
    whether the baseline actually fails more often under that scenario's framing —
    exactly the unequal-sampling artifact a sum-based metric would reward. Dividing
    by `len(probed)` makes the two arms comparable however many records each drew,
    and STILL captures goal #10's "more AND stronger": a higher survivor RATE (more,
    normalized) and deeper per-survivor evidence (stronger) both raise the mean.
    """
    return sum(strength(r) for r in probed) / len(probed) if probed else 0.0


# ── internals ───────────────────────────────────────────────────────────────

def _arm_is_sufficient(planned: int, completed: int, cfg: "Settings") -> bool:
    """One arm's sufficiency: it completed either its FULL planned trial (a
    legitimately small eligible pool is not a failure) or at least
    `scenario_trial_min` records. Below that there is no trial worth reading a winner
    out of.

    `planned == 0` is NOT sufficient — see DEVIATION 1 in the module docstring. §7's
    pinned `completed >= min(planned, trial_min)` reads True for it (`0 >= 0`), which
    scores an arm that never ran as `0.0` and lets the tie-break compare against it.
    The guard is uniform across both arms, not just the winner's: an untried scenario
    must not be scored against in either direction.
    """
    if planned == 0:
        return False
    return completed >= min(planned, cfg.scenario_trial_min)


def _decision(*, sufficient: bool, stop_reason: Literal["complete", "spend_ceiling"],
              discarded_rounds: int, strengths: dict[str, float],
              probed: dict[str, list[ProbeAndScoreResult]],
              planned: dict[str, int], completed: dict[str, int]) -> ScenarioDecision:
    """ONE constructor for both outcomes (DEVIATION 2). An `insufficient_trial`
    result is a FULL ScenarioDecision, not a stub: same evidence file, same tooling,
    every field with its exact value — including `strength_scores`, so a reader can
    see WHAT the partial arms scored even though it is not a basis for a winner.
    `winner` is the only field that differs, and it differs by being None.

    `strengths["A"] >= strengths["B"]` (not `>`) makes goal #10's A tie-break literal
    and mechanical, including the degenerate `{"A": 0.0, "B": 0.0}` — both arms ran,
    neither yielded a survivor — which still resolves to A and never stalls.
    """
    return ScenarioDecision(
        outcome="decided" if sufficient else "insufficient_trial",
        winner=("A" if strengths["A"] >= strengths["B"] else "B") if sufficient else None,
        stop_reason=stop_reason,
        discarded_rounds=discarded_rounds,
        strength_scores=strengths,
        survivor_counts={arm: sum(1 for r in probed[arm] if r["passes_failure_bar"])
                         for arm in ARMS},
        # Reported, never consulted by `winner` above (§7's Goal issue callout). A
        # winner with 0 here can pass every check in this module and still be unable
        # to produce the demo, so the number is surfaced now — before curation spends
        # anything — rather than discovered by emit_template_config at the end.
        #
        # MAPPED, not name-matched. `evidence_modes` holds the SCORER's outcome
        # literals; the obligation failure is `"violation"` there, and only becomes
        # `"missed_obligation"` in the SHIPPED record, via this map (§5). Testing the
        # shipped name against a scorer literal made this counter ALWAYS ZERO — so the
        # one number §7 says must be surfaced "before curation spends anything"
        # reported "no Stage-A evidence" on every run, and the check whose whole
        # purpose is to fail early could not fail at all. `test_scenario_decision.py`
        # hid it by faking `evidence_modes` with shipped names the pipeline never
        # emits; `test_stage_a_survivor_counts_uses_real_scorer_vocabulary` now builds
        # them through `passes_failure_bar` itself.
        stage_a_survivor_counts={arm: sum(1 for r in probed[arm]
                                          if r["passes_failure_bar"]
                                          and any(SCORE_OUTCOME_TO_FAILURE_MODE.get(outcome)
                                                  == "missed_obligation"
                                                  for outcome in r["evidence_modes"]))
                                 for arm in ARMS},
        probed_ids={arm: [r["record_id"] for r in probed[arm]] for arm in ARMS},
        trial_planned=planned,
        trial_completed=completed,
        decided_at=datetime.now(timezone.utc).isoformat(),
        evidence_path=EVIDENCE_PATH,
    )
