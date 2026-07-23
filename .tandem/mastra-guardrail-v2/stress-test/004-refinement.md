# Refinement 1 — 02-plan

The plan is strong and an independent stress-test (two grounded readers) confirms its core holds:
**every** spec module and test owned; all 11 stress scenarios assigned; every ordering claim
verified symbol-by-symbol against spec §8's DAG; **both** parallelism claims true (B1 genuinely
imports nothing from `prep/`; B2 genuinely blocked on P3.2); the generator twist coherent (P8.2
invokes the same `emit_template_config` CLI branch P6.2 called — no second implementation); cost
fidelity exact (zero hits for the superseded 456-call figure); and all 9 success criteria carry a
proving command. R7.0's ~$0.01 live preflight before the ~$17 run is a genuine improvement, as was
deleting the earlier paid dry run.

**Do not restructure.** The phase map, the B1/B2 split, and the task decomposition are right. This
cycle fixes three real defects and closes six cheap gaps. Detail: `stress-test/004-gaps.md`.

**The standard this plan is held to:** it will be executed by **parallel subagents**. The plan's own
words — *"A parallelism claim that is wrong is worse than none — a subagent acts on it."* The same
applies to every ambiguity below.

---

## BLOCKING

**G1. Phase 6's gate is hollow for the two biggest test files, and the plan says otherwise.**
Spec `package.json` (spec:3936) excludes `evals.test.ts` **and** `comparisonWorkflow.test.ts` from
`npm run test:unit` at **file level** — not per-test. So:
- "Ends green when `npm run test:unit` … pass" (plan:748) does **not** cover either file.
- `evals.test.ts`'s "non-billing cases" (plan:951) and `comparisonWorkflow.test.ts`'s "negative
  battery … run now" (plan:936) **never execute in Phase 6**.
- P5.2's zero-bill proof is **vacuously true** for them — the command it relies on skips them.

Consequence: `evals.test.ts`'s first execution is `npm test` in **Phase 9** (~609 calls / **~$23**).
A bug in deterministic partition/ledger logic — precisely what a unit test catches for free — is
discoverable only after real spend, and each iteration costs another ~$23. That is the exact
failure the plan's own Fact 1 exists to prevent.

**Fix it, or stop claiming it.** Preferred: make Phase 6 actually run the deterministic cases at
zero cost — e.g. a name/pattern-filtered `npx vitest run tests/evals.test.ts -t '<pattern>'`, which
is a *command*, not a package.json change. **Verify first that the billing lives inside test bodies
and not at module top-level** — if importing the file bills, that approach fails and you must say
so. If the file's structure makes zero-cost execution impossible, raise it as an explicit **"spec
issue" callout** (§1-spec is refine-capped; the plan cannot silently edit it) and state plainly
that these cases are first proven at Phase 9's expense. Either outcome is acceptable. **Claiming
they run when they do not is not.**

**G2. The `<20`-survivor gate has no enforcement — make it a command that exits non-zero, not a
sentence.**
R7.4 (human review) is backed by real code: no batch-approve path, `review.py` the only writer of
`data/cleared/`. **R7.5 has no analogue.** Nothing in P8.1 (a `cp`) or P8.2 checks the survivor
count. As the reader put it: *"an executing agent that treats plan steps as a checklist to
narrate-and-continue could proceed straight into vendoring a single-digit cleared set with nothing
in the code stopping it."*

This project's standard is **"mechanically blocked, not merely asserted"** — every row of spec §6's
anti-padding table meets it. The one gate the user explicitly asked to be woken for does not.
Add a **named blocking task before P8.1** whose Verify is a command that **fails** on thin yield —
e.g. counting records in `prep/data/cleared/cleared_records.json` and exiting non-zero below the
threshold, requiring an explicit recorded acknowledgment to pass. Goal #11 still governs the
*response*: ship smaller, report honestly, **never** loosen the filter, weaken the bar, or pad.

**G3. P6.2 writes into files that P6.3/P6.5 later "Create" — state append-vs-overwrite.**
P6.2 writes one generated line each into `config.ts` (`DEMO_TRIGGER_RECORD_ID`), `firmProfile.ts`
(`DEMO_FIRM_PROFILE`) and `agents/baselineAgent.ts` (`SCENARIO_PERSONA_INSTRUCTIONS`) per spec §7
step 8. P6.3/P6.5 are sequenced **after**, and their "Creates" fields read as whole-file authorship
with **no append-vs-overwrite instruction**. A naive `Write` destroys P6.2's output. It
self-corrects via P6.3's `test_generation_step_actually_ran` — but only after a wasted pass, and
it is exactly the "a subagent acts on it" failure this plan warns about. State the contract
explicitly in P6.2, P6.3 and P6.5: which file regions are generated, which are hand-authored, and
how a later task must preserve the earlier one's output.

## QUALIFYING

- **G4. `Verify` is mandatory by the plan's own §0 ("none is optional") but missing from most
  module tasks** — P1.2–P1.9, P1.12, P2.1–P2.4, P3.1–P3.2, P4.1, P6.1, P6.3–P6.16. The mandatory
  **RC** substep says "re-run the task's own Verify command"; for those tasks there is none. It is
  uniformly inferable (`cd prep && .venv/bin/python -m pytest tests/test_<module>.py -q` /
  `npx vitest run tests/<name>.test.ts`) — **a subagent should not have to infer it.** Add the
  literal command to every task, or state in §0 that it defaults to that pattern and name the
  exceptions.
- **G5. Split P6.12.** It bundles two entire spec modules (`evals/deliveryWorkflow.ts` +
  `evals/scorers.ts`), ~20 exported symbols, ~900 spec lines, behind a flat 7-item test list. It is
  the one task large enough to need its own plan. Split it along the module boundary the spec
  already draws (workflows and their schemas; then the scorers that import them) and give each half
  its own tests-first list and Verify.
- **G6.** `prep/mastra_prep/__init__.py`'s pinned re-export block (spec §1:396–412) has **no owning
  task** — assign it.
- **G7.** `prep/tests/conftest.py` (spec §1:304, listed separately from `stubs.py`) is **created by
  no task** — P2.0 creates only `stubs.py`. Assign it, or state why it is unnecessary.
- **G8.** `scorers.test.ts`'s `citation_date_cases`, `obligation_cases` and
  `stage_a_predicate_cases` golden groups are never named in the Tests-first lists of the tasks
  building their targets (P6.12 / P6.3); only `judge_cases` is assigned (P6.4). The whole point of
  the byte-identical fixtures is cross-seam parity — assign every group.
- **G9.** Phase 3 and Phase 4 headers carry **no "Bills:"/"Ends green when"** statement, unlike
  every other phase; P3.3/P4.2 have no Verify. P5.1's full-suite gate absorbs it, but the phases
  are not self-contained.

## Standing

`goal.md` is the authority. `01-spec` is APPROVED and **refine-capped at 3** — the plan may **not**
edit it. Any spec defect found while fixing the above is a **"spec issue" callout**, never a silent
divergence. Everything the plan already gets right (above) stays.
