---
mode: autonomous
stage: 02-plan
stress_test: 004
date: 2026-07-16
readers: 2 (coverage/executability, money-path/escalation/fidelity)
---

# Stress-test 004 — 02-plan (post-APPROVED at round 4)

## What held up — verified, not assumed

**Coverage: complete.** All 19 `prep/` modules and all 18 `template/` modules owned by a task.
All 11 spec §14 stress scenarios mapped 1:1. Every named test assigned, including
`test_no_circular_imports` **and** `test_never_imports_carver_showcase`, `test_fixture_parity.py`,
`mastra.test.ts`, `README.test.ts`, and `test_blanket_guardrail_fails_the_suite`.

**Ordering: correct.** Every claim walked symbol-by-symbol against spec §8's DAG —
`budget.py` before probe/judge/curate; `judge/contract → judgeAgent → callJudge`;
`CarverGuardrail → guardedAgent`; `P1.4 → P1.1`; `P1.9 → P1.10`; scorers after deliveryWorkflow.

**Parallelism: honest.** B1 (synthetic fixtures + build config) genuinely imports and executes
nothing from `prep/`. B2 genuinely blocked on P3.2. No parallel-marked task secretly shares state.

**The generator twist works.** P8.2 invokes the same `run_prep.py --emit-template-config` CLI
branch calling the identical `emit_template_config` P6.2 called. No second implementation.

**Money path: cost fidelity exact.** The corrected figures are used throughout (grep for "456":
zero hits outside a meta-reference). R7.0's ~$0.01 live preflight before the ~$17 run is a genuine
improvement, and round 1 explicitly **deleted** an earlier paid dry run.

**Zero-bill: mechanically provable** for everything `test:unit` actually runs — P5.2
`unset OPENAI_API_KEY` and run the suites; "if a suite passes with no key present, it made no
calls", plus greps for `make_client()` / `OPENAI_API_KEY` in tests.

**DoD: 1:1.** All 9 success criteria have an exact proving command or observation.

## BLOCKING (3)

| # | Gap | Tasks |
|---|---|---|
| **G1** | **Phase 6's gate is hollow for the two biggest test files.** Spec `package.json` excludes `evals.test.ts` **and** `comparisonWorkflow.test.ts` from `npm run test:unit` at **file level** (spec:3936), not per-test. So the plan's "Ends green when `npm run test:unit` pass" (plan:748) and its claims that `evals.test.ts`'s "non-billing cases" (plan:951) and `comparisonWorkflow.test.ts`'s "negative battery… run now" (plan:936) are exercised in Phase 6 are **false — neither file executes at all**. `evals.test.ts`'s first execution is `npm test` in Phase 9 (~609 calls / **~$23**), so a bug in deterministic partition/ledger logic — exactly what unit tests catch for free — is discoverable only after real spend, and each fix iteration costs another ~$23. P5.2's zero-bill proof is likewise **vacuously true** for those files: the command it relies on skips them. Not raised as a spec-issue callout, despite the plan's stated practice of flagging this exact contradiction class. | P6.11, P6.12, P6.17, P5.2 |
| **G2** | **The `<20`-survivor escalation gate (R7.5) has no code-level enforcement** — it is prose only. The human-review gate immediately before it (R7.4) *is* mechanically enforced (`review.py` has no batch-approve path and is the only writer of `data/cleared/`). Nothing in P8.1 (a `cp`) or P8.2 checks the survivor count or requires acknowledgment. "An executing agent that treats plan steps as a checklist to narrate-and-continue could proceed straight into vendoring a single-digit cleared set with nothing in the code stopping it." **This plan will be executed by subagents.** The project's own standard — every anti-padding row is a code-level block, "mechanically blocked, not merely asserted" — is not met by the one gate the user explicitly asked to be woken for. | R7.5, P8.1, P8.2 |
| **G3** | **P6.2 writes into files that P6.3/P6.5 later "Create".** P6.2 writes one generated line each into `config.ts` (`DEMO_TRIGGER_RECORD_ID`), `firmProfile.ts` (`DEMO_FIRM_PROFILE`), `agents/baselineAgent.ts` (`SCENARIO_PERSONA_INSTRUCTIONS`) per spec §7 step 8. P6.3/P6.5 are sequenced **after** and their "Creates" fields read as whole-file authorship, with **no stated append-vs-overwrite instruction**. A naive `Write` destroys P6.2's output. Self-correcting via P6.3's own `test_generation_step_actually_ran`, but only after a wasted pass — and it is exactly the "wrong ordering → a subagent builds against the wrong thing" failure the plan itself warns about. | P6.2, P6.3, P6.5 |

## MINOR (6) — routed anyway; all cheap, and subagents will execute this

| # | Gap | Tasks |
|---|---|---|
| G4 | **`Verify` is declared mandatory by the plan's own §0** ("none is optional") but omitted by the large majority of module tasks — leaving the mandatory RC substep's "re-run the task's own Verify command" with no command. Uniformly inferable, but a subagent should not have to infer. | P1.2–P1.9, P1.12, P2.1–P2.4, P3.1–P3.2, P4.1, P6.1, P6.3–P6.16 |
| G5 | **P6.12 bundles two entire spec modules** (`evals/deliveryWorkflow.ts` + `evals/scorers.ts`, ~20 exported symbols, ~900 spec lines) into one task with a flat 7-item test list — the standout candidate for a split. | P6.12 |
| G6 | `prep/mastra_prep/__init__.py`'s pinned re-export block (spec §1:396–412) has **no owning task**. | P1.* |
| G7 | `prep/tests/conftest.py` — listed separately from `stubs.py` in spec §1:304 — is **created by no task**; P2.0 creates only `stubs.py`. | P2.0 |
| G8 | `scorers.test.ts`'s `citation_date_cases`, `obligation_cases`, `stage_a_predicate_cases` golden groups are **never named** in the Tests-first lists of the tasks building their targets; only `judge_cases` is assigned (P6.4). | P6.3, P6.12 |
| G9 | **Phase 3 and Phase 4 headers carry no "Bills:"/"Ends green when" statement**, unlike every other phase; P3.3/P4.2 have no Verify either. Absorbed by P5.1's full-suite gate, but the phases are not self-contained. | P3.3, P4.2 |

## Orchestrator note on G2

G2 lands on the orchestrator, not only the plan. The `<20` gate is the one thing the user asked to
be woken for, and it is currently the only gate in the project protected by intention rather than
mechanism. Two independent fixes, both applied:
1. **Routed to the plan** — make it a command that exits non-zero, not a sentence.
2. **Enforced by the orchestrator** — the survivor count is checked directly between Phase 7 and
   Phase 8 before any vendoring subagent is dispatched. A prose gate in a plan executed by
   subagents is not a gate.
