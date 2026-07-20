---
mode: autonomous
stage: 01-spec
artifact: stages/01-spec/artifact.md (4,319 lines / 40,662 words, round 4, APPROVED)
date: 2026-07-16
---

# Stress-test 001 — 01-spec (autonomous)

## Method

Questions were generated systematically from `goal.md` (14 locked decisions, 9 hard
constraints, 9 success criteria) and `stages/01-spec/task.md` + `rubric.md`, against the
coverage checklist: user personas/journeys, edge cases, failure modes, integration points,
non-functional concerns (performance, security, operability).

The artifact is 40,662 words — too large for one context. The Q&A was therefore executed as
**five parallel grounded readers**, each assigned one coverage dimension and each bound by the
same grounding rules the orchestrator is bound by:

- read ONLY `stages/01-spec/artifact.md` + `goal.md`;
- answer every question from those files, citing section or line;
- never infer, guess, or use outside knowledge to fill a gap;
- uncovered-but-in-scope = **GAP**; deferred-to-stage-02 (ordering, phases, TDD sequencing,
  verification commands) is **not** a gap;
- zero gaps is a valid result — do not manufacture findings.

The orchestrator owns the severity decision; the readers are instruments. Every BLOCKING
finding below was **independently verified by the orchestrator against the artifact** before
being routed (see §Verification).

Dimensions and models:

| # | Dimension | Model | Result |
|---|---|---|---|
| 1 | Demo journey & the north star | sonnet | 3 blocking, 2 minor |
| 2 | Experimental validity | opus | 3 blocking, 3 substantive |
| 3 | Anti-padding & data integrity | sonnet | **clean** — 2 minor |
| 4 | Cost, operability, failure modes | sonnet | **clean** — 5 minor |
| 5 | Template deliverable & cross-seam | sonnet | 1 blocking, 5 minor |

## Dimension 1 — Demo journey & the north star

**Q: Trace `npm run dev` → a developer seeing the tripwire in Studio. What must be true?**
A: Trigger and profile are generated, not hand-authored — `emit_template_config` (§7) restricts
to the winning scenario, then to `predicts_stage_a_violation` records (§5), ranks by failure
count (id ascending on ties), picks the first that survives `narrowObligationsPure` under its
own synthesized profile, and re-validates before writing (§7). The prompt is never a literal:
`buildStageAPrompt(clearedSet.find(r => r.id === DEMO_TRIGGER_RECORD_ID))`. **But the trace
breaks**: nothing supplies `requestContext.firmProfile` to any run → GAP (blocking).

**Q: Can the demo provably fire?**
A: Narrowing-survival is provable (§7 step 4 + §9a proof + regression test). The live block is
**empirical, not provable** — §3 concedes OpenAI is non-deterministic; §12 sets the guarded bar
at ≥0.9, explicitly not 100%. `comparisonWorkflow.test.ts` asserts `blocked === true` as a
single non-retried live call with hard pass/fail — un-hedged where the spec hedges everywhere
else. MINOR.

**Q: `npm run demo` → HTML. Real or replayed? Citation resolution timing?**
A: Both drafts real — `baseline.text` is the live draft; `guarded.blocked_draft` is the actual
pre-block draft captured by the processor (§9c, §11). Citations resolved at **clearing time
only**; a link dying between clearing and demo is documented as out of scope for v1 (§14) —
covered, not a gap.

**Q: SC#4 — both branches complete, tripwire never aborts?**
A: Thoroughly specified. `.parallel()` isolates; `guardedStep` has dual containment (checks
`result.tripwire` on normal return AND catches thrown `TripWireError`, covering Mastra's own
doc inconsistency); both converge on `buildBlockedResult` which always returns a
schema-conforming value (§10:3514–3535). Written proof at §10:3571–3579. Verified by a live
test specified as the literal first TDD spike. **Caveat**: containment sits downstream of an
unguarded `FirmProfileSchema.parse` (§10:3457) — see GAP-1.

**Q: SC#5 — no server, no network?**
A: Concretely specified — inline `<style>`, no `<link>`/`<script src>`, no web fonts, with a
test asserting no `http(s)://` inside `<script`/`<link`/`<img src` (§11:3649–3654). No images,
fonts, or CDN refs exist anywhere. Clean.

**Q: Goal #9 — model id + cutoff in README and report?**
A: Report: pinned verbatim (§11:3666–3668). README: referenced only generically (§1:83). GAP.

**Q: What if the demo runs and does NOT block?**
A: `generateHtmlReport` throws (§11:3642–3645) — correct, fails loudly rather than shipping a
fake demo. But `demo.ts::main()`'s handling of that throw is unspecified. Given §12 accepts
≥0.9 (not 100%), a non-block is acknowledged-possible. GAP.

## Dimension 2 — Experimental validity

**Q: Is the experiment controlled?**
A: Model identity: yes, well covered — one `MODEL_ID` constant, reference-equality test on both
agents' `instructions`/`model`, cross-language drift check reading `config.ts` as text.
**Model config: no.** Prep sends `reasoning_effort: medium` + `max_completion_tokens`; the
template's agents pass neither. Evidence is recorded at `medium`; the scoreboard replays at the
provider default. GAP.

**Q: Can a record be admitted without proven failure?**
A: No. One admission path, three sequential gates (URL before spend, failure bar, human review).
`passes_failure_bar` is `len(evidence) > 0` over three booleans — "No weighting, no '2 of 3,' no
fuzzy score threshold." Every non-admission path forces `evidence_modes=[]`. COVERED.

**Q: Can the probe leak the answer?**
A: Answer-leakage: tightly specified MAY/MUST-NOT lists + a test battery (§3, §14). Note leakage
would make the baseline *succeed* — it costs yield, not validity. **Failure-induction** is the
sharper reading and is only partly addressed: Stage B presupposes the answer exists ("I heard
there's been {{UPDATE_TYPE_PHRASE}} {{RECENCY_PHRASE}}…"). Abstention is invited and scored
non-failure — but nothing measures the prompt's own fabrication-inducing rate. GAP.

**Q: Honest abstention scored as failure?**
A: No — one of the spec's strongest sections. `citation_missing`/`date_missing`/judge
`"uncertain"` all `is_failure=False`, with the reasoning stated: treating abstention as failure
"would reward the model for confidently guessing over honestly abstaining, backwards from what a
compliance guardrail should reward." Every degenerate judge path fails toward `"uncertain"`.
COVERED.

**Q: Can a different-but-correct citation score as fabrication?**
A: Conceptually no — §4's `citation_alternative_real` is exactly this fix. **But the mechanism
is one HTTP check with a known false-positive class**: 403/timeout/5xx are treated identically
to 404. Applied to the *baseline's* URL, fail-closed inverts valence and manufactures evidence.
GAP (blocking).

**Q: Is the judge confined to the fuzzy check?**
A: Yes, strictly. Two scorers are pure string/HTTP work; only `score_missed_obligation` consults
a judge, and its verdict label is explicitly not authoritative — a four-condition deterministic
conjunction is. COVERED.

**Q: Zero/thin yield?**
A: Fully specified at three levels, no minimum imposed, ships smaller rather than pads. §7's
Goal-issue callout handles the "survivors exist but none Stage-A-capable" case by raising and
refusing to auto-resolve: "a user decision, not an automatic override." COVERED.

**Q: Can config loosen the bar?**
A: Every knob goal #11 names is blocked in code — several with doubled enforcement.
**`reasoning_effort` is the exception**: typed enum, no floor, no validation, absent from the
anti-padding table, absent from `template/` entirely. GAP (blocking).

## Dimension 3 — Anti-padding & data integrity — CLEAN

All seven forbidden shortcuts verified mechanically blocked against the actual algorithms, not
the spec's own claims table. `impact_label == "high"` and `ACTIONABLE_UPDATE_TYPES` have no
config surface. `SNAPSHOT_DATE` was deliberately demoted from a config key (an earlier draft
exposed it; `"3000-01-01"` would have defeated the date-rot gate). Out-of-range judge confidence
is **discarded, not clamped** — closing a real loophole where `5.0` would clamp to `1.0` and
clear the floor. `record_signoff()` has no parameter capable of overriding an extracted field.
An eighth, unforced protection exists: price floors.

Two MINOR residuals: (1) `validate_cleared_record` checks evidence *shape*, not *provenance* —
a hand-authored record would validate (this is about the limit of what a spec can defend; the
real gate is git review); (2) no cross-invocation ledger prevents "reroll until it fails"
resampling of the fuzzy dimension (deterred by real per-record spend; only
`missed_obligation` is meaningfully exposed).

## Dimension 4 — Cost, operability, failure modes — CLEAN

The ceiling is **hard**, not soft: `reserve()` holds the provider-guaranteed maximum
(`MODEL_MAX_CONTEXT_TOKENS × price_in + max_completion_tokens × price_out`) *before* the call
fires, with a written proof (§3:1125–1155) and a per-terminal-op invariant table. Price floors
enforced twice independently. Caps bind per-record, not per-batch (an inherited bug, fixed).
Retries never inherit a prior reservation. `assert_no_open_reservations()` in a `finally` on
every exit path. Typical ≈ $17, worst case ≈ $93.5 (78% of the $120 ceiling). Streaming
confirmed (generator, one line resident). No unbounded loops/retries/memory.

**Calibration note the orchestrator accepts:** `goal.md` never required a dollar ceiling — its
only ceiling is the 50–200 record count. The entire $120 mechanism is the spec's own unforced
rigor.

Five MINOR: no dollar estimate for `npm test`/`npm run demo` and no template-side ceiling
(worst case ~800 calls); no resume for `npm test`; no network-error row in the template table;
`log()` used throughout prep but never defined; a present-but-wrong API key burns up to 400
doomed (unbilled) calls instead of failing fast.

## Dimension 5 — Template deliverable & cross-seam

**Q: SC#1 — fresh clone + key → `npm run dev`?**
A: Dependency chain traced clean: no build step, no codegen, no network at install/dev.
**Two caveats**: the spec never states how `.env` reaches `process.env` (no `dotenv` in deps, no
`dotenv.config()` shown) — the one load-bearing SC#1 claim not stamped "verified"; and
`template/` ships no README. GAP.

**Q: SC#9 — zero references out?**
A: Confirmed. Module dependency table lists no `prep/`/`carver-showcase` edges; the three
`carver-showcase` hits in the document are all prep-side.

**Q: The seam — drift prevention?**
A: Real but indirect: `schema.test.ts` Zod-parses the actual vendored JSON, so any unmirrored
Python-side change fails CI on next vendoring. `.strict()` mirrors Python's unlisted-key
rejection. Scorers are reimplemented (a runtime cross-language import would violate goal #1) and
locked by byte-identical golden fixtures — **but nothing tests the two fixture copies are
actually identical**. GAP (minor).

**Q: Mastra idiom?**
A: Clean throughout — router string form, `createTool` + Zod, `outputProcessors` on the Agent
constructor (citing a verified doc page and filed issue `mastra-ai/mastra#7234` for the
`.nullable()` discipline), `createWorkflow` + `.parallel()`, `runEvals` per its documented
surfaces. Nothing non-idiomatic found.

**Q: Forbidden tech?**
A: None. Zero Anthropic hits document-wide. No AI SDK package. RAG/vector/embeddings explicitly
out of scope. No frontend/server/SPA.

**Q: Goal #12's ESM/Node/moduleResolution?**
A: `tsconfig.json` is named once in the file tree and **never given any content**;
`package.json` shows only deps — no `"type": "module"`, no `"engines"`. Goal #12 flags CommonJS
as a specific Mastra-breaking failure mode. GAP.

## Verification (orchestrator, first-hand)

GAP-1 was verified directly against the artifact rather than accepted on a reader's word:

- `artifact.md:3559` — `inputSchema: z.object({ prompt: z.string() })` — no firmProfile channel.
- `artifact.md:3590` — `run.start({ inputData: { prompt } })` — no `requestContext` passed.
- `artifact.md:3457` — `FirmProfileSchema.parse((requestContext as any)?.firmProfile)`.
- `artifact.md:3514` — the `try` block opens **57 lines later**.

`Zod.parse(undefined)` throws, unguarded, on every run, before `agent.generate()`. Confirmed
blocking. The comment at :3454–3456 is what conceals it: a true statement about the
*processor's* graceful zero-candidate degradation (§9a), used to justify the *step's* unguarded
parse, which throws long before §9a runs.

## Note on method

The maker/checker loop approved this artifact at round 4 with zero issues, having closed 17
issues across 4 rounds — including a real circular import, leaked budget reservations, and a
`settle()` path that spent its hold before validating usage. It is a strong document. The gaps
below are not a failure of that loop; they are what a loop converging inside one frame cannot
see about itself. Note also that the **anti-padding** reader's own table of padding levers
omitted `reasoning_effort` — the lever the **validity** reader identified as the single
unblocked bypass. Two competent grounded reads of the same document; only the one approaching
from a different angle saw it. That is the argument for multiple lenses over one deeper pass.
