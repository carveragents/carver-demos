---
verdict: CHANGES_REQUESTED
round: 2
---

## Issues

1. Define a correct reservation lifecycle for API calls that fail before returning usage. `reserve()` immediately adds the worst-case amount to `spend_so_far_usd`, but `record_actual()` is only called on a response; a timeout/network/API error followed by the specified retry leaves the first reservation counted as actual spend forever, then reserves again. This contradicts the proof invariant that `spend_so_far_usd` equals billed actual costs, corrupts reported spend, and can prematurely exhaust the run. Return a reservation token/handle and specify exactly one terminal operation per reservation: settle with usage, release when the provider confirms no billable response, or conservatively finalize when billing status is unknown. Make retries use that lifecycle and test success, no-usage failure, unknown-billing failure, and retry paths without weakening the hard ceiling.

2. Make `decide_scenario()`'s budget/error contract executable and fair. Its pseudocode is a list comprehension with no `BudgetExhausted` handling, yet §15 says `decide_scenario` catches the exception and stops with `stop_reason="spend_ceiling"`; `ScenarioDecision` has no stop-reason/partial-result shape. Specify what happens if budget exhaustion or repeated API failure occurs midway through A or before/during B. It must not compare a full A arm against a partial/empty B arm and declare a winner. Either reserve sufficient trial budget up front, use balanced paired progress with a defined minimum, or return a non-winning terminal result that `run_prep.py` handles explicitly. Add boundary tests for exhaustion in each arm.

3. Finish the judge-schema ownership cleanup everywhere. The project-layout tree still labels `schema.ts` as containing `GuardrailVerdictSchema`, while the detailed table and implementation correctly give sole ownership to `judge/contract.ts`. Update the tree and any remaining references. Likewise fix `BudgetExhausted`'s docstring claiming `reserve()` is the only raiser: `record_actual()` explicitly raises its `BudgetPoisoned` subclass. State the exact raisers/catch contract once without contradiction.

4. Tighten the multi-violation/report invariant. `BlockedGuardedResultSchema` requires a non-empty `violated_obligation_ids` array but does not encode or runtime-check the documented invariant that `record.id === violated_obligation_ids[0]`, nor does `buildBlockedResult` validate every ID is a known narrowed candidate. Validate uniqueness, known-candidate membership, and display-record equality before producing the blocked result; otherwise malformed/stale metadata can pass Zod and make audit, scoring, and report attribution disagree. Add negative tests for duplicate, unknown, and display-mismatch IDs.

## Notes

Round 2 successfully moved budget logic into a leaf module, supplied a provider-cap-based ceiling proof, separated the three eval populations, shared one partition object across the paired headline, emitted full violated-obligation IDs, centralized judge calls/fallback, and made the golden fixture groups explicit.
