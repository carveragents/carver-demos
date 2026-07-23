---
verdict: CHANGES_REQUESTED
round: 6
---

## Issues

1. **The new incremental `scorers.test.ts` contract is ordered backwards and makes P6.3 unrunnable.** Phase 6 executes P6.3 before P6.4, but §0 says the shared file is authored `P6.4 → P6.3 → P6.12b`; P6.3's Verify runs `tests/scorers.test.ts`, while P6.4 still says it creates that file later. P6.4 also contradicts itself: first it says it creates all four `describe` groups (including targets not yet built), then says it creates only `judge_cases`. Make the ownership match the actual task order: P6.3 creates `scorers.test.ts` with only `stage_a_predicate_cases` and its imports; P6.4 appends only `judge_cases` and its imports; P6.12b appends `citation_date_cases` and `obligation_cases`. Correct the §0 order and delete every stale “all four groups created in P6.4” / “P6.4 creates the file first” statement. Each task's stated Verify must pass at the point that task runs, including a fresh execution from no pre-existing test file.

2. **P6.12b's newly enumerated `judge/contract.ts` symbols overstate the module dependency.** The task now claims `evals/scorers.ts` imports `GuardrailVerdictSchema`, `parseAndValidateVerdicts`, and `JudgeObligationInput`, but the approved implementation routes parsing/schema enforcement through P6.6's `runJudge`; the scorer module's direct contract dependency is for the judge-result/input types it actually annotates (not the parser and schema). The `judge_cases` test directly imports `parseAndValidateVerdicts`, but that is P6.4's test dependency, not an `evals/scorers.ts` import. Re-derive this row from the spec's scorer code and list only symbols the module itself imports (at minimum the appropriate `JudgeResult` type; include `JudgeObligationInput` only if the implementation actually annotates an adapter with it). Keep the newly identified `scenario/prompts.ts` omission as an explicit spec-issue callout.

## Notes

The single-command P8.0 gate now binds an acknowledgment to both the current survivor count and cleared-set digest, and the literal Verify/RC fixes and P6.12a dependency correction close the round-5 feedback. Preserve them.
