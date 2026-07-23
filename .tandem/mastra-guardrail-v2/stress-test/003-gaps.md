---
mode: autonomous
stage: 01-spec
stress_test: 003 (targeted closure check, 1 reader)
date: 2026-07-16
outcome: 3 artifact self-contradictions routed as refinement 3 → APPROVED round 13
---

# Stress-test 003 — final closure check

**Reader:** one targeted closure check over refinement 2's 14 items + the new surface it created
(`normalizeDelivery` rewiring, negative control 10 → 30).

**Result: 13/14 CLOSED, nothing goal-blocking.** Confirmed properly closed and well done:
- **E1** — every `new Mastra(` snippet registers all three workflows; Studio trade-off explicitly
  decided, not defaulted; registration test specified.
- **E11** — `normalizeDelivery` genuinely shared: both `guardedStep` and `deliveryStep` call it and
  map its `TripwireOutcome` into their own schemas. The only `catch (err)` left in the document is
  inside the helper. Old inline containment gone.
- **E4** — closed by **retracting the unverifiable premise rather than dressing it up**: instead of
  hunting a citation for `scorerResults[id].output`, the design changed so `blockedScorer` supplies
  the rate as a documented average. The right instinct.
- **E3** — n=30 with a real power argument ("3 blocks still pass at 0.967").
- Cost arithmetic independently re-derived and correct: typical 240+64+244.8+60 = 608.8 ≈ **609
  calls / ~$23**; worst case 400+200+600+60 = **1,260 calls** (correctly using 3 calls/guarded-item
  at a 0% block rate, not the 2.04 average).

## Routed as refinement 3 — three artifact self-contradictions

| # | Gap | Route |
|---|---|---|
| F1 | **§15 "Cost guarantees" still carried the pre-E2 undercount** — "1 for the guarded pass" — beside §12's authoritative 2.04/3-call figures. E2 said "fix … **every derived figure**"; this one was missed. A spec pinning a written ceiling proof cannot contradict itself about call counts in the section named "Cost guarantees". | §15 |
| F2 | **`isTripWireError` listed as a public symbol of two modules** (`carverGuardrail.ts` and `tripwireContainment.ts`) with no re-export path — leftover from the E11 extraction. Same two-owners defect the spec forbids elsewhere (`GuardrailVerdictSchema`'s "sole owner" discipline) and already fixed once at inherited issue 13. | §8 |
| F3 | **Sweep for siblings.** F1/F2 are the same pattern: a fix that corrected the authoritative site but not its restatements — the third occurrence (round 9's two stale `{ compareWorkflow }` constructors being the first). Asked for one deliberate pass over §15/§8's module tables rather than another whack-a-mole round. | §8 / §15 |

## Outcome — the sweep was worth it

Closed at **round 13, APPROVED** (11: 1 issue → 12: 1 issue → 13: clean). F3 found more than F1+F2:
`carverGuardrail.ts` was still listing dependencies it no longer has, and
`compareWorkflow.ts`/`deliveryWorkflow.ts` carried stale config/prompt/agent imports. All corrected.

**Final: 6,002 lines / 61,994 words. `refine_count=3` (maxed).**

## Not routed — accepted, logged

- The template has **no enforced spend ceiling of its own**; §12's "well inside the same $120
  ceiling discipline" borrows prep's separately-enforced `SpendBudget` figure. True but rhetorical,
  not mechanical. `goal.md` never required a template-side ceiling.
- No dollar total computed for the template's 1,260-call worst case (only the call count and a
  qualitative "well inside"), unlike prep's call-by-call $88.4 → $93.5 derivation.
- Carried forward from 001/002 §LOGGED: the negative control for prompt-induced fabrication (V1's
  specificity population may subsume it); no `npm test` resume; no template network-error row;
  wrong-key fail-fast. None goal-blocking.
