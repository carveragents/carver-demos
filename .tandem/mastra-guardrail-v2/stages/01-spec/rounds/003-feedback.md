---
verdict: CHANGES_REQUESTED
round: 3
---

## Issues

1. Close the malformed/missing-usage response path in `Reservation.settle()`. It calls `_claim_terminal("settle")` before reading `usage["prompt_tokens"]`/`["completion_tokens"]`; if usage is absent or malformed, it raises after marking the handle terminal while retaining the full hold, without explicitly classifying the call as unknown-billing, poisoning the budget, or following the documented retry/error contract. Validate usage before claiming settlement, and on invalid usage terminate via a dedicated conservative operation (or `finalize_unknown`) that keeps the provider-maximum hold, poisons/stops if appropriate, and cannot be double-terminated. Add tests for missing keys, non-numeric/negative/out-of-cap values, and a response whose usage parsing fails before a retry.

2. Validate `violated_obligation_ids` against the actual narrowed candidate IDs, not just the vendored corpus. A stale/forged ID that names a real vendored record but was not in this call's top-five candidates currently passes `buildBlockedResult` and the Zod refinements. Recompute the candidate IDs from `requestContext.firmProfile` (or carry an authenticated `candidate_obligation_ids` set from the processor), require every violated ID to be a unique member of that exact set, and require the canonical display-record summary to match the vendored record for the first ID. Add negative tests for a known-but-not-narrowed ID and a valid ID paired with forged title/citation metadata.

3. Make end-of-run reservation auditing unconditional and complete the insufficient-trial value. Specify `run_prep.py::main` wrapping the entire scenario-decision/curation/review execution in `try/finally: budget.assert_no_open_reservations()` so every normal return, `insufficient_trial`, and unexpected exception checks for leaked handles. Replace the `ScenarioDecision(..., ...)` ellipsis in the `insufficient_trial` branch with every required field and exact values, including strength/survivor counts, planned/completed counts, discarded rounds, timestamp, and evidence path; rubric 21 disallows leaving a terminal result shape implicit.

## Notes

Round 3 successfully added explicit reservation handles and terminal operations, provider-maximum holds, balanced interleaved scenario trials with a sufficiency outcome, corrected schema ownership/exception documentation, and display/uniqueness/known-record validation for multi-violation metadata.
