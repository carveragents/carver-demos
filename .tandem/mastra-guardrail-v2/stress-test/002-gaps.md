---
mode: autonomous
stage: 01-spec
stress_test: 002
date: 2026-07-16
readers: 2 (gap-closure audit, measurement-design re-read)
outcome: 1 BLOCKING + 13 MINOR routed as refinement 2 → APPROVED round 10
---

# Stress-test 002 — compiled gaps (post-refinement-1)

**Severity bar (autonomous mode):** refine only on gaps that block the goal or contradict the
artifacts. Nice-to-haves logged, not routed.

## Reader 1 — closure audit: 23/23 CLOSED, 0 PARTIAL, 0 OPEN, 0 REGRESSED

No gaps. Every routed item from stress-test 001 closed with a concrete mechanism rather than a
claim, and the regression sample (16 credited items) survived intact. See `002-transcript.md`.

## Reader 2 — measurement design: the fix is real; the residue is not

**Confirmed genuinely fixed** (the two defects that mattered most):
- A blanket blocker now **fails**, traced end to end.
- The paired row is one scorer, one polarity, one shared population object.
- The negative control is honestly named — it **refuses** the FPR framing on the correct grounds
  (generated drafts have no per-draft ground truth; the only oracle is the judge that made the
  block decision, which is circular) and calls itself a lower bound on discrimination.
- `requestContext` invisibility: "one of the strongest parts of the spec."

### BLOCKING (1) — routed as E1

| # | Gap | Route |
|---|---|---|
| E1 | **The two new eval workflows are never registered; `npm test` cannot run.** `deliveryWorkflow`/`stageBWorkflow` call `mastra.getAgent(...)` (§12:4786, 5080) but `mastra.ts` registers only `workflows: { compareWorkflow }` (§8:3704, 3846; §12:5552). Nothing gives either a Mastra instance → SC#6 fails. **Same class as the round-4 defect §10:4381 itself calls fatal: a call site that was never wired — reintroduced two rounds later, in code created by the fix for it.** | §12 / §8 |

### QUALIFYING — corrections (routed as E2–E8)

| # | Gap | Route |
|---|---|---|
| E2 | Guarded per-item call count omits the **guardrail's own verdict call** (§9b:4038). Stated "1 call"/"≈1.1 avg"; real ≈2.04. Bound undercounts by ~s calls (~456→~569, ~$17→~$21). A spec carrying a written ceiling proof cannot carry a wrong call count. | §12 |
| E3 | Negative control `n=10` vs `>= 0.9` is a knife-edge — 1 block passes, 2 fail. The assertion that makes every other number meaningful has very low power. $0.08/item; the cheapest fix in the harness. | §12 / §8 |
| E4 | Two load-bearing premises carry **no citation**, unlike every other 1.51.0 claim: (a) a workflow-target scorer's `run.output` is the workflow's output (§12:4754 — the premise the redesign rests on); (b) `scorerResults[id].output` exists (§12:4932). **Round 5 failed on exactly this class.** | §12 |
| E5 | `scoreMissedObligation`'s TS call can't match the Python contract it claims to port (`ScenarioSpec` vs `Literal["A","B"]`; template owns no `ScenarioSpec`/`isEligible`), so "identical signatures" can't hold and the golden fixture's `not_applicable` case is unreproducible TS-side. | §12 / §1 |
| E6 | `score_compliance_date` heading omits its third param (`citation: CitationScore`), which the signature, module table and both call sites all take. | §4 |
| E7 | `mean(ledger.scores[k]) === averages[k]` — strict float equality on independently-summed means under concurrency; spuriously flaky. | §12 / §14 |
| E8 | `runScoreboard(clearedSet)` parameterizes the partition but `runArm`/`runNegativeControl` read module-level `vendoredClearedSet`. Latent only. | §12 |

### QUALIFYING — deletions (routed as E9–E14)

Prose from the abandoned intermediate design left standing beside the final code. None break the
design; all would mislead an implementer, and this spec's own standard is that a stale claim is a
defect.

| # | Stale claim | Route |
|---|---|---|
| E9 | §12 says the fix "uses `targetOptions`" — the final design uses it **nowhere** and §12:5102 explicitly rejects it. §12 contradicts itself about its own mechanism. | §12 |
| E10 | "a negative control is 1 + 1 … its judge call always runs" — `benignPassScorer` makes **no judge call at all**. | §12 |
| E11 | `normalizeDelivery` declared as shared by `guardedStep`/`deliveryStep`, with §12 leaning on it ("the containment guarantee §10's spike proves is the same code the scoreboard depends on") — but §10 inlines its own containment and returns a schema `DeliveryResult` cannot express. The shared-code guarantee was unsupported. | §12 / §10 / §1 |
| E12 | Assertion 6 references `baseline.pairedStageA` / `crowdedOutStageA` / `.length` — none exist on the returned shapes. Uncodeable as written. | §12 / §14 |
| E13 | Dead pre-fix helpers `EvalItem`/`stageAItems`/`stageBItems`: defined, exported by nothing, used nowhere; `EvalItem.input: string` contradicts the workflow items' `{prompt, arm}`. | §12 |
| E14 | §8 still describes `unsafeShipScorer` calling `runJudge([...groundTruth], output.text)` — **the exact defects** §12's own callout and round-7 say were fixed. | §8 |

## Outcome

All 14 routed as **refinement 2** (surgical: one wiring fix + corrections + deletions; explicitly
not a redesign). Closed at **round 10, APPROVED**, `refine_count=2`.

The checker's round-9 pass caught three things worth recording, because they show the standard
transferred rather than being imposed from outside:
- E11's refactor was **half-wired** — `normalizeDelivery` returned `TripwireOutcome` while
  `deliveryStep` still declared `DeliveryResultSchema` (a straight type mismatch), and
  `guardedStep` never called it, so "shared containment" was still prose.
- `DeliveryScorer`'s union omitted `blockedScorer` while every call site passed it — a failure of
  the very `tsc --noEmit` gate the spec promises.
- The E1 registration fix was contradicted by **two other stale constructors** elsewhere in the
  document. Fixing the authoritative one is not enough when the document says both things.

Adjustments made beyond the routed list: negative control widened **10 → 30** (killing E3's
knife-edge), and the corrected cost estimate now includes the guardrail's verdict call —
**~609 calls / ~$23** typical, still well inside the $120 ceiling.

## Logged, not routed

Carried forward from `001-gaps.md` §LOGGED and still not routed: the negative control for
prompt-induced fabrication (V1's specificity population may subsume it — revisit only if the plan
stage surfaces a reason); no `npm test` resume; no template network-error row; wrong-key
fail-fast. None are goal-blocking.
