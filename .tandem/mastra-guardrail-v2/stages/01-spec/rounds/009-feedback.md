---
verdict: CHANGES_REQUESTED
round: 9
---

## Issues

1. **E11's shared containment is still prose-only, and the shown delivery workflow no longer satisfies its own output schema.** `normalizeDelivery()` now returns `TripwireOutcome` (`{tripped,...}`), but `deliveryStep.execute` still does `return normalizeDelivery(...)` while declaring `outputSchema: DeliveryResultSchema` (`{blocked, delivered_text, violated_obligation_ids}`). That is a direct type/runtime mismatch. The prose says delivery maps the outcome, but no mapping exists in the code. Conversely, §10's actual `guardedStep` still contains the complete old inline `try { agent.generate; result.tripwire } catch { isTripWireError }` implementation and never calls `normalizeDelivery`; `grep` finds only the delivery call. Thus the two callers do not share containment and §10's spike still does not prove the eval path. Wire the refactor in both executable snippets: each calls `await normalizeDelivery(...)`; delivery validates/extracts `violated_obligation_ids` and maps to `DeliveryResultSchema`, while guarded maps `tripped` through `buildBlockedResult` and maps pass-through text to `GuardedResultSchema`. Remove the now-duplicated inline return/throw handling and add/adjust a unit test that drives both returned-tripwire and thrown-tripwire forms through the shared helper/mappings.

2. **`DeliveryScorer` omits `blockedScorer`, but every paired `runArm` call now passes it.** The union contains only `unsafeShipScorer | guardedCatchScorer | benignPassScorer`; `runScoreboard()` passes `[unsafeShipScorer, blockedScorer]` and `[unsafeShipScorer, blockedScorer, guardedCatchScorer]`. Under the promised strict typecheck, those calls fail. Add `typeof blockedScorer` to the derived union (or derive the accepted type without an incomplete manual member list).

3. **E1's registration correction is contradicted by two load-bearing stale declarations.** The final `src/mastra.ts` snippet correctly registers all three workflows, but §8 still says `new Mastra({ ..., workflows: { compareWorkflow } })` when explaining `judgeAgent`, and §1's `mastra.ts` module-surface row says “registers all three” while its literal constructor at the end again contains only `{ compareWorkflow }`. Correct both to `{ compareWorkflow, deliveryWorkflow, stageBWorkflow }`. This refinement specifically requires deleting misleading revision residue; an implementer should not have to guess which constructor is authoritative.

4. **E12 remains in the test matrix after being fixed in §12.** The `evals.test.ts` row still says `test_paired_populations_are_identical` compares `baseline.pairedStageA` and `guarded`, neither of which exists. Replace it with the actual round-9 assertion: element-for-element equality of `baselinePaired.ledger.map(recordId)` and `guardedPaired.ledger.map(recordId)`. Keep only one test name for that invariant if `test_paired_row_uses_one_scorer` already performs the same check.

## Notes

The other Refinement-2 items are closed: all eval workflows are registered with an explicit Studio trade-off; the guarded and negative-control call counts and ~$23 typical estimate include the guardrail verdict; the control population is widened deterministically to 30; scorer inputs use documented workflow fields; the TS/Python missed-obligation seam is stated honestly; date heading, float tolerance, vendored-set parameter removal, and the remaining stale helper/call-count prose are corrected.
