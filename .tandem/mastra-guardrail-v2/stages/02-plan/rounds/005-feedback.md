---
verdict: CHANGES_REQUESTED
round: 5
---

## Issues

1. **P8.0 still does not mechanically require the recorded acknowledgment that G2 requires.** The only executable command exits 3 whenever `n < 20`; `yield-decision.md` is never read. The prose then says to “re-run this task with the threshold the user authorised,” which asks the executing subagent to invent a modified command and permits any lowered literal to pass whether or not the acknowledgment exists or matches the current cleared set. Make the unlock path exact and mechanical: keep the fixed `20` first-pass stop, then give a literal post-escalation command which exits 0 only when the decision artifact exists, records the current survivor count, and records the user's explicit instruction to proceed with that smaller set. P8.1 must be blocked until either `n >= 20` or that exact acknowledgment check passes. Do not add a flag, environment variable, config bypass, or permission to weaken/pad the data.

2. **The G4 `Verify` default claims coverage for tasks to which it cannot be applied.** The exhaustive table says P6.1, P6.6–P6.10, and P6.13–P6.16 take `tests/<name>.test.ts`, but at least: P6.1 is a fixture task with no named test module; P6.6 does not name its test file; P6.10's named cases live in `carverGuardrail.test.ts`, not a `guardedAgent.test.ts`; P6.14's cases span `mastra.test.ts` and `evals.test.ts`; and P6.15 changes `prep/tests/test_config.py`, so the template default is the wrong language and directory. This leaves the RC/verification contract ambiguous in exactly the way G4 required this refinement to close. Add literal `Verify` commands to every non-one-module/one-test task (including those examples), move all of them into the deviations table, and ensure P6.15 carries the Python RC substep because it changes a Python test. Keep the default only where substituting the task's module name produces the actual command without inference.

3. **P6.12a adds a false dependency on P6.10.** It says `Depends on: P6.10 (guardedAgent)`, but approved spec §8 explicitly says `evals/deliveryWorkflow.ts` does **not** depend on `agents/*`; `deliveryStep` resolves the selected agent through `mastra.getAgent(...)`. Remove that module dependency. If P6.10 must precede the task only because the overall phase is being executed as one strict integration chain, state that separately as sequencing, not as an import/symbol dependency. Also keep the plan's own rule that every dependency claim names the imported symbol.

## Notes

The free `unit:` selector, generated/hand-authored preservation contract, P6.12 module split, missing Python-file ownership, golden-group coverage, and Phase 3/4 gates otherwise close G1 and G3–G9. Preserve those changes.
