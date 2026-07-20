# Refinement 3 — 01-spec (FINAL; three line-level corrections. Nothing else.)

Refinement 2 landed. An independent closure check confirms **13 of 14 items fully CLOSED**, with
nothing goal-blocking, and singles out two fixes as notably well done:

- **E1** is properly closed — *every* `new Mastra(` snippet in the document now registers all
  three workflows, and the Studio visibility trade-off is explicitly decided rather than
  defaulted.
- **E11** is real — `guardedStep` and `deliveryStep` both call `normalizeDelivery(call)` and map
  its `TripwireOutcome` into their own distinct schemas; the only `catch (err)` left in the
  entire document is inside the helper itself. The old inline containment is genuinely gone.
- **E4** was closed the right way: rather than hunt a citation for the `scorerResults[id].output`
  premise, the **design changed** so `blockedScorer` supplies the rate as a documented average.
  Retracting an unverifiable claim beats dressing it up. This is the correct instinct.
- **E3**'s n=30 now carries a real power argument ("3 blocks still pass at 0.967"), not a vibe.

**This cycle is three line-level corrections. Change nothing else.** No redesign, no
restructuring, no new mechanisms. Everything credited across every prior round stays; a silent
revert is an automatic CHANGES_REQUESTED. Prior directives remain binding and are archived at
`stress-test/001-refinement.md` and `002-refinement.md`.

---

## The three corrections

**F1. §15's "Cost guarantees" still carries the pre-E2 undercount.** Lines ~5775–5776 read:
*"`npm test`'s spend is bounded by `data/cleared/`'s fixed size (≤200 records, ≤2 items each for
the baseline pass, **1** for the guarded pass)"* — the exact guarded=1 figure E2 required
corrected, left standing beside §12's authoritative 2.04-average / 3-worst-case arithmetic.
E2 said *"fix the count, the bound, and **every derived figure**"*; this one was missed. Correct
it to match §12. **A spec that pins a written ceiling proof cannot contradict itself about call
counts — least of all in the section named "Cost guarantees".**

**F2. `isTripWireError` is listed as a public symbol of two modules.** §8's module table claims it
for **both** `processors/carverGuardrail.ts` (~line 3932) and `processors/tripwireContainment.ts`
(~line 3940). It is only defined and used inside `tripwireContainment.ts`'s `normalizeDelivery`
(~line 4952), and `carverGuardrail.ts`'s own Dependencies column doesn't even import
`tripwireContainment.ts` — so no re-export path explains the duplicate. Leftover from the E11
extraction: the `carverGuardrail.ts` row wasn't pruned. **Give it one owner.** This is the same
two-owners defect the spec explicitly forbids elsewhere (`GuardrailVerdictSchema`'s "sole owner"
discipline) and already fixed once, at inherited issue 13.

**F3. While fixing F1, sweep for its siblings.** F1 and F2 are both residue that survived a fix
which corrected the authoritative site but not its restatements — the same pattern as round 9's
"two stale `{ compareWorkflow }` constructors". Do one pass over §15 and §8's module tables for
any other figure or ownership claim that contradicts §12/§10's final code. Report what you find,
or state plainly that you found nothing. **Do not take this as licence to edit anything beyond a
contradicted figure or a wrong owner.**

## Standing — do not reopen

`goal.md` is the authority: cutoff **2026-03-01**, pool **8,260**; the `2026-03-02`/8,199
amendment was **withdrawn** (`stress-test/001-refinement.md`, final section). The measurement
design, the negative control, the reservation lifecycle, anti-padding, evidence integrity, and
tripwire containment are all settled and independently verified. Nothing above touches them.
