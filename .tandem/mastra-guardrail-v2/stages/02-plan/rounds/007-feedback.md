---
verdict: CHANGES_REQUESTED
round: 7
---

## Issues

1. **P6.12b's re-derived import row is still not the scorer module's actual symbol map.** It says the module imports `DeliveryInput` from P6.12a, but the approved public surface does not export that type; spec:5081 defines `type DeliveryInput = z.infer<typeof DeliveryInputSchema>` locally inside `evals/scorers.ts`. The row must therefore name `DeliveryInputSchema`, not a nonexistent exported `DeliveryInput`. It also names `FirmProfileSchema`, while the scorer code calls `firmProfileForRecord(record)` repeatedly (spec:5280/5293); and it omits the workflow values used as `runEvals` targets (`deliveryWorkflow`, `stageBWorkflow`). Re-derive the **entire P6.12b dependency row from the scorer implementation**, not just the judge-contract edge: list the exact exported symbols imported from `evals/deliveryWorkflow.ts`, `firmProfile.ts`, `schema.ts`, `judge/callJudge.ts`, `judge/contract.ts`, `tools/narrowObligations.ts`, `scenario/prompts.ts`, and the vendored data as applicable. Keep `DeliveryInput` local via `z.infer`, keep `type JudgeResult` as the only direct judge-contract type unless the chosen `asJudgeObligation` ownership adds that explicit import, and do not name a symbol merely because its module is related. This plan's own rule is symbol-level dependency accuracy; the corrected row must be executable without inventing or searching for exports.

## Notes

The P6.3 → P6.4 → P6.12b shared-test chain now matches task order and is independently runnable. The round-6 acknowledgment gate and verification fixes remain sound. Preserve them and the explicit `asJudgeObligation` / generated-prompt spec-issue callouts.
