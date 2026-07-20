# Refinement 1 — 01-spec

The spec was **approved** at round 4 and is strong: 17 issues closed across 4 rounds, including a
real circular import, leaked budget reservations, and a `settle()` that spent its hold before
validating usage. An orchestrator stress-test (six independent grounded readers — see
`stress-test/001-transcript.md` and `001-gaps.md`) then found gaps the maker/checker loop could
not see about itself, because both were reasoning inside the same frame.

**Two dimensions came back CLEAN** and must not be disturbed: **anti-padding/data integrity**
(all seven forbidden shortcuts verified mechanically blocked against the real algorithms) and
**cost/operability** (the hard ceiling with its written proof survived four adversarial
revisions; typical ≈ $17, worst case ≈ $93.5 of $120).

## THIS IS A REVISION, NOT A REWRITE

Same rule as last round, and it matters more now: the gaps below are **contract holes and
measurement-design errors in an otherwise sound architecture**. The architecture is right. Do not
restructure. Change what these gaps require and what those changes force — nothing else.

**Do not regress anything credited across the previous rounds**, including but not limited to:
the non-recursive `judgeAgent`; the broken judge dependency cycle; the `budget.py` leaf module
and the enforced import DAG; the `Reservation` single-terminal-op lifecycle and its written
ceiling proof; price floors enforced twice; per-record cap binding; honest abstentions excluded
from the failure bar; `citation_alternative_real`; out-of-range confidence **discarded, not
clamped**; the snapshot-derived date upper bound; `SNAPSHOT_DATE` demoted from config; the exact
snake_case seam; no-edit human review and its three sub-attestations; the anti-padding table;
the interleaved scenario trial and `insufficient_trial`; discriminated blocked/pass schemas;
`violated_obligation_ids` recomputed against this call's candidates; the dual-layer tripwire
containment and its first-TDD-spike test; deterministic ascending-id trigger selection.
A silent revert is an automatic CHANGES_REQUESTED. A **deliberate** change to any of the above
must carry an inline **Revision callout** saying what changed and why.

Full detail, citations and reasoning for every item: **`stress-test/001-gaps.md`**. Read it.

---

## BLOCKING — measurement design (close these first; they are the project's core claim)

**V1. No specificity / false-positive measurement exists. A guardrail that blocks 100% of
everything passes every assertion in §12.**
`guardedCatchScorer` only ever runs over `partition.scored` — records that *should* block.
`knowledgeOnly`/`crowdedOut` are deliberately never sent to the guarded agent (§12:3943–3944:
"would spend real money to collect a 0 that proves nothing"). **That rationale is exactly
backwards**: a 0 there is the only thing that proves the guardrail *discriminates* rather than
blankets. Non-blocking is proved only by stubbed-judge unit tests (§14:4170), never by the real
judge on a real draft. Specify a **live negative-control population** and a reported
specificity / false-positive-rate number. Budget it (the ceiling has headroom).

**V2. The one "PAIRED" row compares two different metrics with opposite polarity — and both
cells estimate the same underlying quantity.**
Baseline = violation rate (higher worse, §12:3790); guarded = block rate (higher better,
§12:3920). Since `guardedAgent` differs from `baselineAgent` only by an **output** processor —
which cannot influence generation — both ≈ P(judge flags this obligation). `>= 0.8` and `>= 0.9`
are therefore inconsistent bars on one quantity. Pin the printed table's columns, metric names
and polarity legend (§12:4019 currently specifies only three rows + `n`s). **Print the honest
contrast the goal actually claims: baseline blocked 0% / guarded blocked ~90%.**

**V3. Uncontrolled confound in that same row: judge batch size.** Baseline's judge call carries
1 obligation (§12:3792); guarded's carries 1–5 (§9b:3228, 3246). §4:1476–1481 asserts
immateriality — assertion is not control. Either control it or measure it.

**V4. `requestContext.firmProfile` goes to the guarded arm only, and nothing establishes or
tests that `requestContext` is invisible to the model.** §8:2800–2806 argues only *where it
lives*. If Mastra surfaces it into the generation context, the guarded agent drafts knowing the
firm's jurisdiction/sector while the baseline drafts blind — goal #9's fatal case, and it would
look like success. **Verify against Mastra's docs, pin the citation** (this spec stamps every
other framework claim "verified 2026-07-16"; this one is bare), and **add a test**.

**V5. `maxProcessorRetries: 1` is on `guardedAgent` only** (§8:2715, 2827), semantics undefined,
interaction with `abort()` unspecified — while §15:4218 gives it a live retry role. If it
regenerates the draft after an abort, the guarded arm gets a second chance the baseline never
gets, and §11's "same draft, one shipped, one blocked" breaks. Define it, or set it on both, or
justify the asymmetry explicitly.

**V10. Probe/template generation-config parity.** Prep pins `reasoning_effort: medium` and
per-call `max_completion_tokens`; the template's agents pass neither, so evidence is recorded at
`medium` and the scoreboard replays at the provider default. §12's `>= 0.8` bar is defended as
stochastic tolerance, which silently absorbs a configuration difference. Give the template a
matching pinned generation config and a drift check (same family as V7).

## BLOCKING — evidence integrity

**V6. `resolve_url`'s fail-closed rule manufactures `citation_fabricated` evidence when applied
to the baseline's URL.** *(both validity readers, independently)* Fail-closed is correct for the
**ground-truth** gate — it *drops* records. On the **baseline's** citation the valence inverts:
a false negative **admits** a record whose baseline may have cited a real, correct source.
403/geo-block/5xx/timeout are treated identically to 404. §4:1429–1433's "unarguable… objectively
a dead, invented link" holds only under a no-false-negatives assumption the spec never states,
while conceding regulator sites reject `HEAD` and that live links die. Distinguish **404/410**
(evidence of non-existence) from **403/429/5xx/timeout** (evidence of nothing → a new non-failure
outcome mirroring `citation_alternative_real`), and/or add a reviewer confirmation for
`citation_fabricated` mirroring the three that exist for `missed_obligation`. Contradicts goal #2.

**V7. `reasoning_effort` is the one unblocked rigging/padding lever.** *(both validity readers)*
Bare enum: no floor, no validation, no §6 anti-padding row, no template counterpart. `low`
weakens the same pinned model → more failures → bigger yield: goal #9's named rigging mode via a
lever it didn't anticipate. Every comparable knob is floored, ceilinged, or a code constant —
several doubly enforced. Pin it as a code constant or floor it at `medium` in `load_settings()`,
and add the §6 row.

**V8. Fair-test discipline exists only in `prep/`; the template's prompt builders are
unspecified, contradictory, and exempt.** *(both validity readers)* Four defects, one module:
- (a) `buildStageBPrompt` is **used** (§12:3775) but in no module's public surface (§8:3049).
- (b) **Flat contradiction — resolve this first, it determines whether (d) is live:** §7:2584
  says `scenario/prompts.ts` is **generated** ("never hand-written"); §1:174 / §8:3049 say
  **hand-authored**.
- (c) The tag→bucket mapping is defined nowhere and carries three names (`DOMAIN_BUCKETS` ×2,
  `INDUSTRY_TAG_TO_BUCKET` §15:4230), duplicated across the seam with **no golden fixture** —
  while scoring and narrowing each get one on the stated grounds that silent divergence "would be
  worse than the bug it replaces". §7's own rule: "CLOSED lists, complete as specified here."
- (d) No TS-side leak test, yet `buildStageAPrompt(record: ClearedRecord)` receives every field
  §3's MUST-NOT list forbids and drives the demo, the containment test, and **both eval arms**.

**V9. Goal #3's re-derivation rule is absent.** *(both validity readers)* The `>= "2026-03-01"`
floor is **independent of `MODEL_ID`**; nothing couples the cutoff to the model; no test checks
it — while §8:2736–2738 promotes the one-line swap. A later-cutoff model passes every check
while admitting in-training-data documents. Also: **`MODEL_CUTOFF` has no prep-side home** — every
`ClearedRecord` must carry it, but no constant/config key holds it and no section names its
writer. Add a prep-side `MODEL_CUTOFF`, a drift check against `config.ts`, and a
`load_settings()` assertion `candidate_cutoff_date >= model_cutoff + 14d` — replacing the bare
hardcoded floor with the derivation goal #3 actually specifies.

## BLOCKING — the demo journey

**D1. `requestContext.firmProfile` is never wired into any run; the parse throws on every run.**
*(orchestrator-verified first-hand)* §10:3559's `inputSchema` has no firmProfile channel; both
pinned call sites (§10:3590, §11:3640–3641) pass no `requestContext`; §10:3457's
`FirmProfileSchema.parse(...)` sits **57 lines outside** the `try` that opens at §10:3514.
`Zod.parse(undefined)` throws before `agent.generate()` — **the guardrail cannot fire, on any
run**. SC#2, #4, #5 all fail. The comment at §10:3454–3456 conceals it: a true claim about the
*processor's* zero-candidate degradation used to justify the *step's* unguarded parse.
**Resolve together with V4** — decide deliberately whether the profile travels via
`requestContext` at all.

**D2. No specified path to trigger `compareWorkflow` from Studio's UI.** SC#2 requires the block
be seen **in Studio**; the north star's literal scene is watching it there. The only real-run path
is `scripts/demo.ts` via `tsx`, in a separate process from `mastra dev`. Nothing shows a
`tsx`-invoked run's trace reaching a running Studio, and nothing documents triggering it from
Studio's own form. (Studio supports editing `RequestContext` — JSON, or a schema-driven form when
`requestContextSchema` is set. Verify, pin the citation, specify the path.)

**D3. `scripts/demo.ts` has no behaviour specified when the live run doesn't block.**
`generateHtmlReport` throwing is correct — fail loudly, never ship a fake demo. But `main()`'s
handling is unaddressed while §12 accepts `>= 0.9`, not 100%. As pinned: an uncaught stack trace.

**T1. `template/` ships no `README.md`.** goal.md says **twice** the model/cutoff and
provider-swap disclosure belongs in **the template README** (goal:60, 63). §1:83 puts one README
at the project root; `template/`'s subtree has none. Since SC#1 says "fresh clone of `template/`"
and goal #1 requires it be trivially extractable, a real extraction ships with zero setup and
**zero model/cutoff disclosure** — destroying what goal #9 calls "the defence against the
cherry-picking charge". Also state there (per the spec's own accepted Goal-issue callout) that
`medium`/`low` severity coverage is unit-test-only.

## QUALIFYING — close these too (see `001-gaps.md` for detail)

- **I1.** `annotations_path` is one level short — from `prep/` it needs **four** `../`, not three.
  As written → `FileNotFoundError` on the first command.
- **I2.** `tsconfig.json` is named once and never given content; `package.json` has no
  `"type": "module"`, no `"engines"`. Goal #12 locks these and flags CommonJS as a specific
  Mastra-breaking mode.
- **I3.** How `.env` reaches `process.env` under `mastra dev` is never stated (no `dotenv` dep, no
  `dotenv.config()`) — the only load-bearing SC#1 claim with no "verified" stamp.
- **I4.** `log()` is used throughout `prep/` but defined nowhere — no module, signature, or
  default visibility.
- **I5.** `report_curation` has no specified output fields — the run's main terminal output, left
  implicit, exactly what inherited issue 17 rejected. Must also state that `survivors/probed` is
  **success-conditioned** and that its denominator is the scenario-eligible subset, **not** the
  goal's headline 8,260.
- **I6.** Baseline compliance-date parsing/normalization unspecified; no `date_unparseable`
  outcome. `"September 1, 2026"` → `date_wrong` → **admits on a correct answer**. The spec applies
  this exact lesson exhaustively to `confidence` and trusts a bare description for the date.
- **I7.** `strength()` documents "1-3 modes"; 3 is unreachable (`date_wrong ⟹ citation_correct`
  excludes `citation_fabricated`) — max 2, so trigger ranking collapses to the id tie-break.
- **I8.** `strength()`'s `+confidence` applies only for `missed_obligation`, partially re-ranking
  scenarios by Stage-A evidence — contradicting §7's own callout that the decision rule is
  unchanged.
- **I9.** Same seed + identical construction ⇒ curation re-probes the winner's exact 30 trial
  records first (the ones it was selected for out-performing on); published `mean_strength` is a
  max-of-two-noisy-arms statistic with no winner's-curse caveat; also double-spends absent
  `--replay`.
- **I10.** `config.test.ts`/`firmProfile.test.ts` named but in neither §1's tree nor §14's table;
  `prep/templates/` referenced but absent from the tree with no `.tmpl` specified; nothing asserts
  `SCENARIO_PERSONA_INSTRUCTIONS !== ""`.
- **I11.** The two golden fixtures are asserted byte-identical across the seam; nothing tests it.
- **I12.** "Never import `carver_showcase`" has no mechanical test — the existing `ast` walk could
  assert it in one line.

## Logged, NOT required this cycle

See `001-gaps.md` §LOGGED. Notably the **negative control for prompt-induced fabrication** is
deliberately deferred — V1's specificity population is the higher-value control and may subsume
it. Revisit after V1 lands. Do not build both blindly.

## Accepted without action

The spec's own **Goal issue** callout (lines 62–75) is **correct, and the flaw is in `goal.md`,
not the spec**: goal #3's `impact_label == "high"` filter makes goal #6's `medium`/`low` branches
dead code against real data. The spec's resolution is accepted verbatim — not a contradiction,
but the README must say `medium`/`low` coverage is unit-test-only rather than implying the demo
exercises the full ladder (folded into T1). No goal amendment. Do not re-litigate.

---

# ORCHESTRATOR AMENDMENT — 2026-07-16 (answers round-5 feedback, issue 4)

**The checker was right to refuse a silent 13-for-14 substitution, and the error was mine, not
the maker's.** This amendment resolves it. `goal.md` has been amended and the workspace copy
synced — **re-read `goal.md`; it is the authority, and it changed.**

## The conflict

My refinement demanded `candidate_cutoff_date >= MODEL_CUTOFF + 14d`. But `goal.md` locked the
filter at **2026-03-01**, and 2026-02-16 + 14d = **2026-03-02**. March 1 is **13** days past the
cutoff — while the goal simultaneously described it as "a clean, indisputable two-week margin".
Both my numbers could not be right. The maker implemented `+13d` to preserve the locked date and
said so; the checker correctly declined to treat that as satisfying the stated criterion.

## The ruling: tighten to 2026-03-02, keep a true 14-day margin

- **`MARGIN_DAYS = 14`. `candidate_cutoff_date == model_cutoff + MARGIN_DAYS` → `2026-03-02`.**
- **Enforce the derivation, not the literal.** `load_settings()` asserts
  `candidate_cutoff_date >= model_cutoff + timedelta(days=MARGIN_DAYS)`. A bare hardcoded floor
  independent of `MODEL_ID` is precisely the hole V9 was raised to close — do not close V9 with
  another hardcoded date.
- **This is a TIGHTENING, which goal #3 explicitly sanctions** ("Tighten if the cutoff is later;
  NEVER loosen it"). It also makes the goal's own stated rationale true rather than approximately
  false.

## Measured cost — verified against the corpus, not estimated

| Filter | Margin | Pool | Ratio @200 |
|---|---|---|---|
| 2026-03-01 (old, goal-locked) | 13d | 8,260 | 41:1 |
| **2026-03-02 (amended)** | **14d** | **8,199** | **41:1** |

**61 records, 0.74%.** March by month becomes **2,139** (was 2,200). Every other month is
unchanged. `goal.md`'s pool figures — the brief's corpus block, decision #3, and decision #9's
"31% smaller pool (11,909 → 8,199)" — are all updated. Use **8,199** and **2026-03-02**
throughout; any surviving `8,260` or `2026-03-01` in the spec is now stale except where it
explicitly narrates this amendment's history.

## On the other three round-5 issues — no amendment, the checker is right

Issues 1, 2 and 3 stand as written and are the maker's to close:

1. **The eval transport boundary is the real blocker.** V1/V2 are not closed until the metrics are
   *executable* on `@mastra/core@1.51.0`. Reading `output.tripwire`/`output.text`/`output.object`
   from a scorer is not that version's contract. Redesign only that boundary — preserve the
   one-generation-per-item rule, the paired population, the separated polarities, full violated-id
   attribution, and the batch-size breakdown.
2. **Pin real citations.** The checker is correct that *"'verified 2026-07-16' prose without a URL
   is not a pinned citation"* — that applies to my own V4/D2 wording too. Pin the URLs, and add a
   **typecheck command to the acceptance path** so these API contracts are mechanically checked
   rather than described.
3. **Name the negative-control metric honestly.** If it measures a benign-task pass rate, call it
   that everywhere and stop claiming equivalence to a false-positive rate — or define a true
   true-negative denominator. Keep the live `>= 0.9` assertion and the proof that an
   unconditional blocker scores zero. **That proof is V1's entire point**: without it, a guardrail
   that blocks everything still passes.

---

# ⚠️ THE AMENDMENT ABOVE IS WITHDRAWN — 2026-07-16, orchestrator

**The `2026-03-02` / `MARGIN_DAYS = 14 (exclusive)` / 8,199-pool ruling above is WITHDRAWN.
`2026-03-01` and the measured **8,260** pool stand. `goal.md` is the authority and has been
amended to match; the artifact already implements this correctly. Do not act on the superseded
ruling above — it is retained only as provenance.**

**Why it was wrong.** The amendment was issued on the premise that `goal.md` contained an
arithmetic error ("two-week margin" vs a 13-day gap). It did not. Goal #3's prose and its number
are consistent under an **inclusive** convention — counting the cutoff date as day 1, 2026-02-16 →
2026-03-01 **is** 14 days. The error was imprecise *wording* in the goal (a margin stated without
naming its convention), not a wrong date. `goal.md` §3 now names the convention explicitly.

**The maker was right, and behaved exactly as it should.** It recognised the ambiguity, took the
defensible reading, and **flagged the conflict for the orchestrator rather than silently
choosing** — noting correctly that moving a locked decision and its measured pool "is not
something a maker may do unilaterally." That escalation is why this surfaced in two rounds
instead of being baked into the plan. The checker was equally right to refuse a silent 13-for-14
substitution.

**Standing requirement (unchanged, and already satisfied):** enforce the **derivation**, never a
hardcoded literal. `assert_cutoff_margin` must derive the floor from `MODEL_CUTOFF` with the
day-count convention named at the constant, in the function, and in a test. A bare floor
independent of `MODEL_ID` is the V9 hole itself; closing V9 with another hardcoded date would
have closed it in name only.
