---
mode: autonomous
stage: 01-spec
artifact: stages/01-spec/artifact.md (5,610 lines / 55,984 words, round 8, APPROVED after refine #1)
date: 2026-07-16
---

# Stress-test 002 — 01-spec, post-refinement (autonomous)

## Method

Targeted re-test, not a repeat sweep. Refinement 1 closed 23 gaps and grew the artifact
40,662 → 55,984 words (+37%). That new material had been seen only by the maker/checker loop —
the same single-frame problem that made stress-test 001 worth running. Two grounded readers,
same rules (artifacts only, cite, uncovered-in-scope = GAP, deferred-to-02 ≠ gap):

| Reader | Scope | Model | Result |
|---|---|---|---|
| Gap-closure audit | all 23 routed gaps + regression sample | sonnet | **23/23 CLOSED, 0 PARTIAL, 0 OPEN, 0 REGRESSED** |
| Measurement design | the rewritten §12 + eval transport | opus | 1 BLOCKING, 13 MINOR |

## Reader 1 — closure audit: clean

All 23 gaps closed with a concrete mechanism (interface, algorithm, constant, or test) rather
than a claim. Spot-checks on the items most susceptible to being faked all held:

- **V1** — a **live, billed** negative control (`runNegativeControl`, real `runEvals` over 10
  closed prompts) plus `test_blanket_guardrail_fails_the_suite`. A guardrail that blocks
  everything scores 0.00 and fails assertion 5.
- **V5** — `maxProcessorRetries` **deleted**, not patched; retry moved into `callJudge.ts` so it
  retries the *verdict*, not the draft. The guarded arm can no longer get a second draft.
- **V6** — tri-state `UrlStatus`: `citation_fabricated` only from **404/410**;
  403/429/5xx/timeout → `citation_unverifiable`, `is_failure=False`. Link rot can no longer
  manufacture evidence.
- **V7** — `REASONING_EFFORT = "medium"` as a code constant + anti-padding row + drift check.
- **V8** — the generated-vs-hand-authored contradiction resolved toward **generated**;
  `buildStageBPrompt` owned; TS leak test over every vendored record; `buckets_golden.json`.
- **I3** — `dotenv` added as a real dependency with `import "dotenv/config"` first in
  `mastra.ts`, citing Mastra's own known gap (`mastra-ai/mastra#4880`).

**Regression sample: no losses.** Non-recursive `judgeAgent`, `budget.py` leaf + enforced DAG,
the `Reservation` lifecycle + ceiling proof, doubled price floors, per-record cap binding, honest
abstentions excluded, `citation_alternative_real`, confidence discarded-not-clamped,
`SNAPSHOT_DATE` demoted, no-edit review + three sub-attestations, the anti-padding table (extended,
not shrunk), the interleaved trial, discriminated schemas, dual-layer containment — all intact.

## Reader 2 — measurement design: the fix is real, the residue is not

**The two headline defects are genuinely closed.**

*Q: Could a blanket blocker now FAIL?* Yes, traced end to end: an unconditional `abort()` →
`blocked === true` on all 10 → `benignPassScorer` returns 0 each → average 0.00 → assertion 5
(`>= 0.9`) fails with a named message. Narrowing non-emptiness under `DEMO_FIRM_PROFILE` is a
tested invariant, so the verdict stage is genuinely exercised rather than short-circuited.

*Q: Is the paired row honest now?* Yes. Both cells are the same `unsafeShipScorer`, same polarity
(lower=better), over literally the same array object, computed once and passed to two `runArm`
calls differing only in `arm`. Guarded by `test_paired_row_uses_one_scorer`. The callout's
reasoning is correct: an *output* processor cannot change P(draft violates), so the guardrail's
effect is on **delivery** — which is what row 1 now measures.

*Q: Is the negative-control metric honestly named?* Yes, "unusually so". §8 explicitly **refuses**
the FPR framing — a true FPR needs per-draft "this violates nothing" ground truth, which does not
exist for *generated* drafts, and the only available oracle is the judge that made the block
decision (circular). It is named for what it measures and called a **lower bound on
discrimination**, not an error rate. No overclaim.

*Q: Batch-size confound?* Controlled **and** measured: `unsafeShipScorer` calls `runJudge` with
exactly one obligation on both arms; rows 3a/3b break the catch rate down by `|candidates|` from
the ledger at zero extra API cost.

*Q: `requestContext` invisibility?* "One of the strongest parts of the spec" — `new
RequestContext({...})` (an instance) at all six call sites, `requestContextSchema` on the
workflow, and invisibility **established and tested** behaviourally via the public
`getInstructions`/`getModel`/`listTools` accessors with a populated context.

**What it introduced:** one real wiring omission (the eval workflows are never registered) and a
layer of prose from the abandoned intermediate design left standing beside the final code.

## Orchestrator note

Reader 1 independently flagged the loose thread the orchestrator had left: `refinement.md` still
carried the withdrawn `2026-03-02` amendment. It resolved correctly (goal.md is the authority and
the artifact matches it), but the withdrawal is now recorded in `refinement.md` itself so no
downstream reader acts on a superseded ruling.
