# Refinement 2 — 01-spec (SURGICAL: one wiring fix + deletions. NOT a redesign.)

Refinement 1 worked. An independent closure audit found **23/23 gaps CLOSED, 0 PARTIAL, 0 OPEN,
0 REGRESSED** (regression sample: every credited item still intact). An independent Opus re-read
of the rewritten §12 confirms both headline defects are genuinely fixed:

- A blanket blocker now **fails**, traced end to end: unconditional `abort()` → all 10 negative
  controls blocked → `benignPassScorer` 0.00 → assertion 5 fails by name.
- The paired row is **one scorer, one polarity, one shared population object**, guarded by
  `test_paired_row_uses_one_scorer`.
- The negative control is honestly named — refusing the FPR framing because *generated* drafts
  have no per-draft ground truth is exactly right, and "lower bound on discrimination" is the
  honest label.
- `requestContext` invisibility is "one of the strongest parts of the spec".
- V5's fix (delete `maxProcessorRetries`, move retry into `callJudge`) and V6's tri-state
  `UrlStatus` (404/410 = fabricated; 403/429/5xx/timeout = `citation_unverifiable`, not a failure)
  are both exactly right.

**Do not redesign.** This cycle is **one wiring fix plus corrections and deletions**. Everything
above, and everything credited in earlier rounds, stays. A silent revert is an automatic
CHANGES_REQUESTED. Detail: `stress-test/002-gaps.md`, `002-transcript.md`. Refinement 1 is
archived at `stress-test/001-refinement.md` and still binds.

---

## BLOCKING — one item

**E1. The two new eval workflows are never registered; `npm test` cannot run.**
`deliveryWorkflow` and `stageBWorkflow` call `mastra.getAgent(...)` (§12:4786, 5080), but
`mastra.ts` registers only `workflows: { compareWorkflow }` (§8:3704, 3846; §12:5552), and
`evals/deliveryWorkflow.ts`'s declared deps (§1:3844) list `agents/*`, not `mastra.ts`. Nothing
gives either eval workflow a Mastra instance, so `mastra` is unestablished in both step contexts
and **SC#6 (`npm test`) fails**. Same class as the round-4 defect §10:4381 itself calls fatal: a
call site that was never wired.
Register both — and **decide deliberately** whether they should surface in Studio (registering
does add two workflows to its UI; the spec never discusses the trade-off). If they shouldn't, say
how and why. Add a test that proves the wiring holds.

## QUALIFYING — factual corrections

**E2. The guarded arm's per-item call count and cost are wrong.** §12:4700 says "a guarded item =
**1** call"; §12:5264 says "≈1.1 on average". Both omit the **guardrail's own verdict call**
(§9b:4038–4041 — `runJudge` via `judgeAgent`, fired on every guarded generation with ≥1
candidate). A guarded item is 1 draft + 1 verdict + (1 scorer judge if delivered) ≈ **2.04**. The
`2k + m + 1.1s + 2g` bound (§12:5267) undercounts by ~s calls: typical ~456 → ~569 calls, ~$17 →
~$21. Still inside the ceiling — **but a spec carrying a written ceiling proof cannot carry a
wrong call count.** Fix the count, the bound, and every derived figure.

**E3. The negative control's `n = 10` against `>= 0.9` is a knife-edge.** One block passes, two
fail. The single assertion that makes every other number meaningful has very low power and is
flaky-by-design at the margin. At $0.08/item (§12:5272) it is the cheapest assertion in the
harness — widen `n` and restate the bar so one stochastic block cannot decide it.

**E4. Two load-bearing premises carry no citation**, unlike every other 1.51.0 claim in §12:
(a) a workflow-target scorer's `run.output` **is** the workflow's output (§12:4754 — the premise
the entire redesign rests on); (b) `scorerResults[id]` carries an `output` field (§12:4932–4934,
asserted "public, documented", no URL). **Round 5 failed on exactly this class of uncited
assumption about what a scorer receives.** Verify both against the pinned version, pin the URLs —
or redesign whatever does not hold.

**E5. `scoreMissedObligation`'s TS call does not match the Python contract it claims to port.**
§12:4856 calls `scoreMissedObligation(record, record.scenario, judgeResult, record.id)`, but the
Python signature (§1:352, §5:2024) takes `scenario: ScenarioSpec` and gates on
`is_eligible(record, scenario)` — while `record.scenario` is `Literal["A","B"]` (§5:2327). The
template owns no `ScenarioSpec` and no `isEligible` (§1:3843, §8:3417–3424), so "identical
signatures" (§1:3843) cannot hold, and the `not_applicable` case `scoring_golden.json` locks on
both sides (§14:5401) is unreproducible TS-side. Resolve the contract for real.

**E6. `score_compliance_date`'s heading omits its third parameter.** §4:1741 reads
`score_compliance_date(stage_b, record) → DateScore`; the signature (§4:1808), the module table
(§1:352) and both call sites (§5:2129, §12:4895) all take `citation: CitationScore`.

**E7. Float equality in the reconciliation test.** `mean(ledger.scores[k]) === averages[k]`
(§12:5024, §14:5426) compares independently-summed means with `===`; summation order is not
guaranteed under concurrent items, so it can fail spuriously. Use a tolerance.

**E8. `runScoreboard(clearedSet)` parameterizes the partition, but `runArm`'s ledger (§12:5012)
and `runNegativeControl` (§12:5064) read module-level `vendoredClearedSet`** — as does the
processor under test. A non-default `clearedSet` would measure a vendored-set guardrail against a
foreign partition. Latent today (the only non-default caller fails at assertion 1 first) — close
it or drop the parameter.

## DELETE — revision residue

Prose from the abandoned intermediate design, left standing beside the final code. None of these
break the design; all of them would mislead an implementer — and this spec's own standard is that
a stale claim is a defect. Delete or correct each:

- **E9.** §12:4696–4699 and 4750–4752 state the fix "uses `runEvals`'s two documented per-call
  configuration surfaces — `targetOptions` …" and that "structured output is
  `targetOptions: { structuredOutput: { schema } }`". **The final design uses `targetOptions`
  nowhere**, and §12:5102–5109 explicitly rejects it for Stage B. §12 contradicts itself about its
  own mechanism.
- **E10.** §12:5264–5265: "a negative control is 1 + 1 (it is expected *not* to block, so its
  judge call always runs)" — `benignPassScorer` (§12:4881) makes **no judge call at all**.
- **E11.** §12:4799–4804 and §1:3845 declare `normalizeDelivery(call)` factored out so
  `guardedStep` and `deliveryStep` "share **one** implementation", and §12 leans on it ("the
  containment guarantee §10's first TDD spike proves is then the same code the scoreboard depends
  on"). But §10's `guardedStep` (4240–4332) inlines its own dual-layer try/catch and returns
  `GuardedResultSchema` — carrying `text`/`blocked_draft`/`reason`/`processorId`/`record`, which
  `DeliveryResult` cannot express. As typed, one function cannot serve both: **the shared-code
  guarantee and the "already proven" claim are unsupported.** Make it true or drop the claim.
- **E12.** Assertion 6 asserts `baseline.pairedStageA.length === guarded.length` (§12:5229), the
  prose names a `crowdedOutStageA` rate (§12:5233), and §14:5426's
  `test_paired_populations_are_identical` repeats `baseline.pairedStageA`. But `runScoreboard`
  returns `{partition, baselinePaired, guardedPaired, crowdedOut, negativeControl, stageB}`
  (§12:5041) and `runArm` returns `{ledger, averages}` (§12:5017) — **no `pairedStageA`, no
  `crowdedOutStageA`, no `.length`.** Assertion 6 is uncodeable as written.
- **E13.** Dead pre-fix helpers: `EvalItem`, `stageAItems`, `stageBItems` (§12:4714–4719) are
  defined, exported by no module surface (§1:3843), used nowhere — `runArm`/`runStageBEval` build
  items inline. `EvalItem`'s `input: string` also contradicts the workflow items'
  `input: {prompt, arm}`.
- **E14.** §8:3655–3656 still states "§12's `unsafeShipScorer` calls
  `runJudge([asJudgeObligation(groundTruth)], output.text)`" — both the `output.text` read and the
  `groundTruth` param are **the exact defects** §12's own callout (4733–4743) and round-7 issue 22
  say were fixed. The real code is `runJudge([asJudgeObligation(record)], out.delivered_text)`
  (§12:4855).

## Standing — do not reopen

`goal.md` is the authority: cutoff **2026-03-01**, pool **8,260**. The `2026-03-02` / 8,199
amendment was **withdrawn** (see `stress-test/001-refinement.md`, final section) — the maker's
inclusive convention was correct and the goal's wording, not its date, was the error. The artifact
already matches. Do not relitigate.
