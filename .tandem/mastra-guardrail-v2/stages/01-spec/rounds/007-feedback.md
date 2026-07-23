---
verdict: CHANGES_REQUESTED
round: 7
---

## Issues

1. **`runArm` still spells `MastraScorer` with the wrong generic arity/order.** In the pinned declarations the class is `MastraScorer<TID, TInput, TRunOutput, TAccumulatedResults>`, not `MastraScorer<TInputSchema, TOutputSchema>`. The shown `MastraScorer<typeof DeliveryInputSchema, typeof DeliveryResultSchema>[]` binds a Zod schema object as the scorer id and another schema object as the input value type, and omits two parameters. Use a compile-valid alias with all four positions and inferred value types, e.g. `MastraScorer<any, z.infer<typeof DeliveryInputSchema>, z.infer<typeof DeliveryResultSchema>, any>`, or a union of the concrete `typeof unsafeShipScorer | typeof guardedCatchScorer` instances accepted by `runArm`. Keep the custom schema declarations on `createScorer`; those are correct.

2. **The ledger reads a workflow result from a property the pinned runtime does not pass to `onItemComplete`.** Although the 1.51.0 declaration/documentation calls the callback value a workflow `targetResult`, the actual `runEvals` implementation's `executeWorkflow()` returns an internal wrapper `{ traceId, spanId, entityType, scoringData: { output, ... } }`, then passes that wrapper to `onItemComplete`; it does not include `targetResult.result`. Both `DeliveryResultSchema.parse(targetResult.result)` calls therefore parse `undefined` at runtime. Do not couple the ledger to that declaration/runtime mismatch. Each `scorerResults[id]` is the full public scorer-run result and already carries the same typed `output` the scorer consumed; parse `scorerResults[expectedIds[0]].output` as `DeliveryResult`, assert every expected scorer result carries an identical output if desired, and extract each numeric `.score` in the same checked boundary helper. Apply this to `runArm` and `runNegativeControl`. This keeps the ledger entirely on the scorer-result contract and avoids an undocumented `scoringData` reach-in.

3. **The `runArm` snippet contains a literal duplicate `ledger.push({` line.** Remove the extra line; as written the promised `tsc --noEmit` gate fails with a syntax error.

## Notes

The four scorer definitions now use the correct custom schema form, read `run.groundTruth`, and include the previously missing Stage-B scorer. Numeric score extraction is also correct in principle. These three corrections are mechanical completion of that same fix; no measurement or architecture change is requested.
