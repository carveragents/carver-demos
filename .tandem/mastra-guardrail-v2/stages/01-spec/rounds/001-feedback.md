---
verdict: CHANGES_REQUESTED
round: 1
---

## Issues

1. Break the Python dependency cycles in the specified module graph. `probe.py` and `judge.py` import `SpendBudget` from `curate.py`, while `curate.py` imports `probe` and `judge`; this is a direct circular import and can leave partially initialized modules/undefined symbols. Move `SpendBudget`, `BudgetExhausted`, `BudgetPoisoned`, pricing constants, and request-reservation helpers into a neutral `budget.py` (or equivalent leaf module), then make `probe.py`, `judge.py`, `curate.py`, `scenario_decision.py`, and `run_prep.py` depend one-way on it. Update the layout, re-exports, public-surface table, and tests.

2. Stop claiming the checked overhead allowance makes overspend impossible. `record_actual()` runs only after the billable call; if actual prompt usage exceeds the reservation, it truthfully adds the overage and can push `spend_so_far_usd` above `total_spend_ceiling_usd` before poisoning future calls. Therefore statements such as “the run cannot spend past ... full stop” and “the guarantee is unconditional” are false. Either reserve against a provider-enforced maximum input/context bound that mathematically prevents the first-call overage, or state the precise weaker guarantee (pre-call reservation plus immediate post-call anomaly stop) and reconcile it with rubric 12's hard dollar ceiling. A post-spend check cannot retroactively enforce a hard ceiling.

3. Make the scoreboard's paired comparison use genuinely identical populations. `buildBaselineDataset()` creates Stage A items for every `predictsStageAViolation` record, including `crowdedOut`, while guarded scoring uses only `partition.scored`; the prose nevertheless claims the Stage A baseline and guarded sides use the same record set. Compute/report a paired Stage A baseline metric over exactly `partition.scored` for the headline comparison, and report crowded-out Stage A and Stage B knowledge metrics separately. Do not aggregate Stage A and Stage B items into one baseline rate and present it beside guarded catch rate as a paired contrast.

4. Fix guarded catch attribution when multiple relevant obligations are violated. `partition.scored` proves the ground-truth record is in the top five, but the processor can validly judge several high-impact candidates as violated and place a different first/highest record in `tripwire.metadata.record`. `guardedCatchScorer` then records a miss even if the expected ground-truth obligation was also violated and the guardrail correctly blocked. Include the deterministic set of all violated obligation IDs in tripwire metadata/audit output and score membership of `groundTruth.id` in that set, or otherwise isolate the evaluated obligation without changing runtime semantics. Keep the single display record for the HTML report if desired.

5. Resolve remaining interface/quality contradictions. The module table says both `schema.ts` and `judge/contract.ts` export `GuardrailVerdictSchema`, while the detailed design says it is defined once in `judge/contract.ts`; choose one owner and update imports/table/layout. Specify `runJudge()`'s retry/out-of-range fallback implementation rather than only naming its signature, so Stage A eval follows the same six-step contract as runtime enforcement. Remove the duplicated `BudgetExhausted if...` line in `SpendBudget.reserve()` and revise the headline claim that the Python/TypeScript predicate copies are locked by `scoring_golden.json` if that fixture does not actually execute both implementations against identical predicate cases.

## Notes

The inherited five issues are otherwise addressed well: trigger candidates require human-confirmed Stage A evidence; knowledge-only records are partitioned; null jurisdiction/topical signals are excluded before spend; count caps bind per record; confidence is bounded and independently validated; and request reservation now distinguishes SDK kwargs from wire framing.
