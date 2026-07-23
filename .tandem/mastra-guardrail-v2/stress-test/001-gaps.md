---
mode: autonomous
stage: 01-spec
stress_test: 001
date: 2026-07-16
readers: 6 (demo journey, experimental validity ×2 independent, anti-padding, cost/operability, template/cross-seam)
---

# Stress-test 001 — compiled gaps

**Severity bar (autonomous mode):** refine only on gaps that **block the goal** or
**contradict the artifacts**. Nice-to-haves are logged here without refining.

**Confirmation note:** experimental validity was read twice, independently. The two reads
**converged** on V6/V7/V8/V9 — independent agreement, not one reader's opinion. The second read
additionally found V1/V2/V3/V5, the most conceptually serious findings of the whole test.

**Orchestrator verification:** D1 was verified first-hand against the artifact before routing
(see `001-transcript.md` §Verification). The rest are routed on the readers' citations, which
were spot-checked for line accuracy.

---

## BLOCKING — measurement design (the project's core claim)

These are the ones that would let the artifact ship looking successful while proving something
other than "Carver's contribution". Goal #9: *"It would appear to succeed, which is exactly what
makes it dangerous."*

**V1 — No specificity / false-positive measurement exists anywhere. A guardrail that blocks
100% of everything passes every assertion in §12.**
`guardedCatchScorer` scores 1 iff the tripwire fired ∧ ground truth ∈ `violated_obligation_ids`
(§12:3919–3937), evaluated only over `partition.scored` — records that *should* block.
`knowledgeOnly`/`crowdedOut` are deliberately never sent to the guarded agent (§12:3943–3944:
*"would spend real money to collect a 0 that proves nothing"*). The processor's non-blocking
paths are proved only by **stubbed-judge unit tests** (§14:4170), never by the real judge on a
real draft. All four `evals.test.ts` assertions pass for a degenerate always-blocking guardrail.
**Route: §12** (+ §14). A live negative-control population and a reported specificity/false-positive
number are required. The `knowledgeOnly` rationale is exactly backwards: a 0 there is the only
thing that proves the guardrail discriminates rather than blankets.

**V2 — The single "PAIRED" row's two cells are different metrics with opposite polarity, and
both estimate the same underlying quantity.**
Baseline cell = violation rate (`missed-obligation-reproduces`, §12:3790 — higher is *worse*).
Guarded cell = block rate (`guarded-blocks-known-obligation`, §12:3920 — higher is *better*).
Printed side by side under one row labelled PAIRED; the prose explains it (§12:3992–3994) but the
`console.table` columns and polarity are never pinned (§12:4019). A reader sees `0.83 | 0.95` and
infers a 12-point improvement. Worse: `guardedAgent` differs from `baselineAgent` only by an
**output** processor, which cannot influence generation — so both cells ≈ P(judge flags this
obligation against a draft from this agent), making `>= 0.8` and `>= 0.9` internally
inconsistent bars on one quantity. The honest, dramatic contrast — **baseline blocked 0% /
guarded blocked 90%** — is never printed. **Route: §12.**

**V3 — Uncontrolled confound inside the one paired row: judge batch size.**
Baseline arm's judge call carries **1** obligation (§12:3792); guarded arm's carries **1–5**
(§9b:3228, 3246). §4:1476–1481 asserts immateriality (*"identical question, in the identical
shape, differing only in how many obligations are batched"*) — asserted, never controlled or
measured. §12's own `crowdedOut` partition exists because multi-candidate narrowing is expected
(§12:3987), so this is not an edge case. **Route: §12 / §9b.**

**V4 — `requestContext.firmProfile` is given to the guarded arm only, and the spec never
establishes or tests that `requestContext` is invisible to the model.**
Guarded gets it (§10:3515; §12:3908–3909); baseline does not (§10:3372; §12:3772). §8:2800–2806
argues only *where it lives* (`requestContext` vs working memory, "static per-run
configuration") — never that it cannot reach the generation context. If Mastra surfaces it, the
guarded agent drafts with the firm's jurisdiction/sector/`impactedFunctions` in hand while the
baseline drafts blind: goal #9:62's fatal case (*"differing ONLY in whether Carver data is
present"*), and it would look like success. Other framework behaviours in this spec carry
"verified 2026-07-16" stamps (e.g. §8:2976–2985); this one does not. §14's template tests contain
no such assertion. **Route: §8 / §10 / §14.** Verify against Mastra's docs and pin the citation;
add a test.

**V5 — `maxProcessorRetries: 1` is set on `guardedAgent` only; its semantics and interaction with
`abort()` are never defined.**
§8:2715, 2827 set it on guarded and not baseline. §15:4218 assigns it a live role (*"Mastra's
structured-output path itself retries per `maxProcessorRetries`"*). If it regenerates the draft
after a processor abort, the guarded arm gets a **second draft the baseline never gets** — a
literal second chance — and §11's "same draft, one shipped, one blocked" framing (§11:3656–3660)
silently breaks. **Route: §8 / §15.**

---

## BLOCKING — evidence integrity

**V6 — `resolve_url`'s fail-closed rule manufactures `citation_fabricated` evidence when applied
to the *baseline's* URL.** *(confirmed by both validity reads)*
§15:4206 specifies network error → *"treated as 'does not resolve' (fail-closed, matching goal's
'if it doesn't resolve, the record is out')"*. Correct and conservative for the **ground-truth**
gate (it *drops* records). Applied to the **baseline's** citation (§4:1421) the valence inverts: a
false negative **admits** a record whose baseline may have cited a real, correct source. 403 from
a regulator blocking datacenter IPs, geo-blocking, transient 5xx and timeouts are all treated
identically to a 404. §4:1429–1433 claims this is *"unarguable… objectively a dead, invented
link"* — true only under a no-false-negatives assumption the spec never states, while conceding
regulator sites reject `HEAD` (§2) and that live URLs die (§14:4189). §6's three structured
reviewer questions fire **only** for `missed_obligation` (§6:2074, 2111–2113), so a citation-only
record has no backstop. Contradicts goal #2 (*"only with recorded evidence of how the baseline
failed it"*). **Route: §4 (+ §6, §15).** Distinguish 404/410 (evidence of non-existence) from
403/429/5xx/timeout (evidence of nothing → a new non-failure outcome mirroring
`citation_alternative_real`), and/or add a reviewer confirmation for `citation_fabricated`.

**V7 — `reasoning_effort` is an unconstrained runtime dial on baseline strength — the one
unblocked padding/rigging lever.** *(confirmed by both validity reads)*
§13 types it `low|medium|high` with **no floor, no validation, no entry in §6's anti-padding
table, and no template counterpart at all**. Setting `low` weakens the same pinned model → more
probes fail → larger yield: goal #9's named rigging failure mode (*"harvest more failures… That
is rigging, and it is forbidden"*) reached by a lever goal #9 did not anticipate. Every
comparable knob — `candidate_cutoff_date`, `judge_confidence_floor`, `target_set_size`,
`price_*`, `snapshot_date` — is floored, ceilinged, or demoted to a code constant, several with
doubled enforcement. This one is a bare enum. **Route: §13 (+ §6, §8).** Pin as a code constant
(like `SNAPSHOT_DATE`) or floor at `medium` in `load_settings()`; add the §6 table row; **and**
give the template a matching generation config so curation and the scoreboard measure the same
arm under the same config (see V10).

**V8 — Fair-test discipline exists only in `prep/`; the template's prompt builders are
unspecified, contradictory, and exempt.** *(confirmed by both validity reads)*
Four defects in one module:
(a) **`buildStageBPrompt` is used (§12:3775) but appears in no module's public surface**
(§8:3049 lists only `buildStageAPrompt`, `DOMAIN_BUCKETS`, `SCENARIO_TASK_TEMPLATES`) — no
owner, no definition. An implementer cannot build it.
(b) **Flat contradiction:** §7:2584 says `scenario/prompts.ts`'s task templates are **generated**
by `emit_template_config` ("never hand-written… one mechanical, deterministic, run-once script");
§1:174 and §8:3049 say the same module is **hand-authored**. Generated-from-prep and
hand-mirrored are materially different guarantees about whether the eval asks the same question
the evidence was recorded for. Violates rubric 21.
(c) **The tag→bucket mapping is defined nowhere and named three ways:** `DOMAIN_BUCKETS`
(§3:496–499), `INDUSTRY_TAG_TO_BUCKET` (§15:4230), `DOMAIN_BUCKETS` again (§8:3049). The bucket
*vocabulary* is closed (§7); the *mapping* is not — despite §7's own rule ("CLOSED lists,
complete as specified here — not a 'TBD, enumerate at implementation time' placeholder") and
despite being duplicated across the seam with **no golden fixture**, while scoring and narrowing
both get one on the stated grounds that silent divergence "would be worse than the bug it
replaces" (§12).
(d) **No fair-test enforcement TS-side:** §3's MAY/MUST-NOT list and
`test_task_instance_excludes_leaked_fields` have no counterpart, yet
`buildStageAPrompt(record: ClearedRecord)` receives `title`, `key_requirements`, `objective`,
`what_changed`, `why_it_matters`, `citation`, `compliance_date` — every field §3's MUST-NOT list
forbids — and drives the demo, the containment test, and **both eval arms**. §14's template table
has no leak test.
**Route: §1 / §3 / §7 / §8 / §14.** Resolve (b) first — it determines whether (d) is a live risk.

**V9 — Goal #3's re-derivation rule is absent; nothing couples the cutoff to the pinned model.**
*(confirmed by both validity reads)*
Only the "never loosen" half survives: the `>= "2026-03-01"` floor (§13:4109) is **independent of
`MODEL_ID`**; nothing couples `CANDIDATE_CUTOFF_DATE`/`MODEL_CUTOFF` to `MODEL_ID`; no test
checks the relation — while §8:2736–2738 actively promotes the one-line model swap and goal #9
invites it. A forker pointing `MODEL_ID` at a later-cutoff model passes every check while
admitting documents inside the new model's training data: the exact silent corruption goal #3
names. Separately, **`MODEL_CUTOFF` has no prep-side home**: every `ClearedRecord` must carry
`model_cutoff: "2026-02-16"` (§5:1992) but no prep constant or config key holds it and no section
names its writer — while `MODEL_ID` and `JUDGE_CONFIDENCE_FLOOR` each get a dedicated drift
check. **Route: §2 / §5 / §13.** Add a prep-side `MODEL_CUTOFF`, a drift check against
`config.ts`, and a `load_settings()` assertion `candidate_cutoff_date >= model_cutoff + 14d`
replacing the bare hardcoded floor with the derivation goal #3 actually specifies.

**V10 — Probe/template generation-config parity is unspecified.**
Prep pins `reasoning_effort: medium` (§13:4057) and per-call `max_completion_tokens` (§3's table)
on every call. The template's agents (§8:2811–2838) pass **neither**; §13:4127–4130's template
config surface lists no generation parameter. So evidence is recorded at `medium` and the
scoreboard replays at the provider default. §12's `>= 0.8` bar is defended only as stochastic
tolerance (§12:4008), attributing to sampling noise a variance source that is partly a
configuration difference. **Route: §8 / §13.** (Same fix family as V7.)

---

## BLOCKING — the demo journey

**D1 — `requestContext.firmProfile` is never wired into any `compareWorkflow` run, and the one
place that reads it throws on `undefined`.** *(orchestrator-verified first-hand)*
- §10:3559 — `inputSchema: z.object({ prompt: z.string() })`: no firmProfile channel.
- §10:3590 and §11:3640–3641 — both pinned call sites are `run.start({ inputData: { prompt } })`:
  no `requestContext`.
- §10:3457 — `FirmProfileSchema.parse((requestContext as any)?.firmProfile)`.
- §10:3514 — the `try` opens **57 lines later**.
`Zod.parse(undefined)` throws, unguarded, on **every** run, before `agent.generate()` is reached.
The guardrail cannot fire; SC#2, #4 and #5 all fail. The comment at §10:3454–3456 conceals it: a
true statement about the *processor's* graceful zero-candidate degradation (§9a) used to justify
the *step's* unguarded parse, which throws long before §9a runs. **Route: §10 (+ §8, §11).**
Note this interacts with V4 — resolve them together, deciding deliberately whether the profile
travels via `requestContext` at all.

**D2 — No specified path for a developer to trigger `compareWorkflow` from Studio's own UI.**
SC#2 requires the block be seen **in Studio**, and the north star's literal scene is watching it
happen there. The only documented real-run path is `scripts/demo.ts` via `tsx`, in a **separate
Node process** from the `mastra dev` server Studio renders; nothing shows or asserts that such a
run's trace appears in a concurrently-running Studio. No text documents how a developer would
discover the prompt and trigger the workflow live from Studio's trigger form. **Route: §11 (+ §8).**
Mastra Studio supports editing `RequestContext` values (JSON, or a schema-driven form when
`requestContextSchema` is set) — verify and pin the citation, then specify the path.

**D3 — `scripts/demo.ts` has no specified behaviour when the live run doesn't block.**
`generateHtmlReport` throws when `guarded.blocked !== true` (§11:3642–3645) — correct: it fails
loudly rather than shipping a fake demo. But `main()`'s handling (catch? retry? diagnostic? exit
code?) is unaddressed, while §12 explicitly accepts a `>= 0.9`, not 100%, live catch rate — so a
non-block on the single trigger record is acknowledged-possible, not hypothetical. As pinned, the
developer gets an uncaught Node stack trace. **Route: §11.**

**T1 — `template/` ships no `README.md`, so goal #9's disclosure requirement is unmet exactly
where the goal puts it.**
The layout (§1:83) places one `README.md` at the **project root**; `template/`'s subtree
(§1:146–194) has none. But goal.md says twice that this content belongs in **the template
README**: *"State the baseline model and its cutoff plainly in the template README and in the
HTML report"* (goal:60) and *"Say so in the template README"* re: provider-swap (goal:63). Since
SC#1 is phrased "from a fresh clone of `template/`" and goal #1 requires `template/` be
"trivially extractable into its own repo", a real extraction ships with **zero setup
instructions and zero model/cutoff disclosure** — destroying precisely what goal #9 calls "the
defence against the cherry-picking charge". **Route: §1 (+ §11).**

---

## QUALIFYING — interface holes, contradictions, factual errors

These contradict the artifact's own discipline or leave an implementer unable to build. Cheap to
close; batched into this cycle.

| # | Gap | Route |
|---|---|---|
| I1 | **`annotations_path: ../../../carver-showcase/…` is one level short.** From `prep/` (goal #13's stated CWD) the sibling repo needs **four** `../` (`prep → mastra-guardrail → projects → carver-adhoc → repos`). As written it resolves to `carver-adhoc/carver-showcase/`, which does not exist → `FileNotFoundError` on the very first command. | §13:4060 |
| I2 | **`tsconfig.json` is named once (§1:148) and never given any content; `package.json` shows only deps** — no `"type": "module"`, no `"engines"`. Goal #12 locks Node ≥22.13.0, ESM-only, modern `module`/`moduleResolution`, and flags CommonJS as a **specific Mastra-breaking failure mode**. The spec claims to operationalize *every* locked decision; this one is inherited by reference only. | §1 / §8 |
| I3 | **How `.env` reaches `process.env` under `mastra dev` is never stated** — no `dotenv` in `template/package.json`, no `dotenv.config()` shown. This is the one load-bearing SC#1 claim carrying no "verified" stamp, in a spec that stamps every other framework claim. | §8:3007–3012 |
| I4 | **`log()` is used throughout `prep/` (§3:922, 934, 950, 1118, 1234) but defined nowhere** — no owning module, signature, or statement of whether progress is visible by default (contrast `reader.py`'s explicit `logger.warning`). §1's layout lists no logging module. | §1 / §3 |
| I5 | **`report_curation(result)` (§3:1109) has no specified output fields** — the run's main terminal output, left implicit. This is exactly what inherited issue 17 rejected for `report_insufficient_trial` (*"the one terminal shape a reader most needs, left implicit"*). Must also state that `survivors/probed` is **success-conditioned** (stop-on-target, §3:1200), and that its denominator is the scenario-eligible subset (§3:1107), **not** the goal's headline 8,260. | §3 |
| I6 | **Baseline compliance-date parsing/normalization is unspecified.** Ground truth handles unparseable (`not_applicable`); the baseline side has no parse step and `DateScore.outcome` has no `date_unparseable`. §4 itself proves OpenAI does not structurally enforce non-structural schema keywords — and applies that lesson exhaustively to `confidence` while trusting a bare description for the date. `"September 1, 2026"` vs `"2026-09-01"` → `date_wrong` → **admits on a correct answer**. Same direction as V6. | §4 |
| I7 | **`strength()` documents "1-3 distinct modes" (§7:2486–2492) but 3 is unreachable**: `date_wrong` requires `citation_correct` (§4:1459–1464), mutually exclusive with `citation_fabricated`, so `evidence_modes` ⊆ {cit_fab, missed} or {date_wrong, missed} — max 2. Trigger ranking by `-len(baseline_failures)` (§7:2612) therefore resolves to two values and the id tie-break dominates. | §7 / §5 |
| I8 | **`strength()`'s `+confidence` term applies only when `missed_obligation` is present**, partially re-ranking scenarios by Stage-A evidence — contradicting §7's own callout: *"The decision rule is unchanged… silently re-ranking scenarios by Stage-A evidence would be relitigating it under the guise of a bug fix"* (§7:2675–2677). | §7 |
| I9 | **Same seed + identical list construction** (§7:2409 vs §3:1107/1210) means curation **re-probes the winner's exact 30 trial records first** — the very records the winner was selected for out-performing on. The published `mean_strength` echoed into the README (§7:2523–2525) is a max-of-two-noisy-arms statistic with no winner's-curse caveat. Also double-spends absent `--replay`. | §3 / §7 |
| I10 | **`config.test.ts` / `firmProfile.test.ts` are named (§7:2700–2703) but appear in neither §1's tree nor §14's table. `prep/templates/` is referenced (§7:2723, 2768) but absent from §1's tree**, and no `.tmpl` fragment is specified despite §7 step 8 requiring all four. No test asserts `SCENARIO_PERSONA_INSTRUCTIONS !== ""` — the persona placeholder (§8:2812) could ship empty. | §1 / §7 / §14 |
| I11 | **The two golden fixtures are asserted byte-identical across the seam but nothing tests that they are.** Each side tests its own copy; if one gains a case the other doesn't, both suites pass while the parity guarantee silently weakens — the exact "claimed but unenforced" class this spec's history repeatedly closes. | §12 / §14 |
| I12 | **"Never import `carver_showcase`" (goal #13) has no mechanical test**, unlike the structurally identical no-circular-imports rule, which already walks `mastra_prep` with `ast`. The same walk could assert it in one line. | §14 |

---

## LOGGED — nice-to-haves, NOT routed this cycle

Recorded per the severity bar; not refined.

- **Negative control for prompt-induced fabrication.** Stage B presupposes the answer exists
  ("I heard there's been…"), a leading question aimed at a document the model cannot know.
  Abstention is invited and scored non-failure, and the alternative-source case is handled — but
  nothing measures the prompt's *own* fabrication-inducing rate. A ~30-record arm against
  pre-cutoff records the baseline demonstrably knows would cost ~$1 against a $120 ceiling and
  produce a headline number for goal #9's transparency section. **Deliberately deferred**: V1's
  specificity population is the higher-value negative control and may subsume it. Revisit after
  V1 lands.
- No dollar estimate for `npm test` / `npm run demo`; no template-side spend ceiling (worst case
  ~800 calls). *(Note: `goal.md` never required a dollar ceiling at all — the entire $120
  mechanism is the spec's own unforced rigor.)*
- `npm test` has no `--replay`-equivalent; an interrupted run re-bills every completed call.
- §15's template error table has no row for a raw network/timeout error on a live
  `agent.generate()`.
- A present-but-wrong `OPENAI_API_KEY` burns up to 400 doomed (unbilled) calls before reporting
  0 survivors, instead of failing fast.
- `comparisonWorkflow.test.ts`'s `expect(guarded.blocked).toBe(true)` is a single non-retried
  live call with hard pass/fail, where the spec hedges identically-grounded claims everywhere else.
- Goal #9's README obligation is pinned verbatim for the HTML report but only generically for the
  README (subsumed by T1).
- `validate_cleared_record` checks evidence *shape*, not *provenance* — a hand-authored record
  would validate. (The limit of what a spec can defend; the real gate is git review.)
- No cross-invocation ledger prevents "reroll until it fails" resampling of the fuzzy dimension.
  Deterred by real per-record spend; only `missed_obligation` is meaningfully exposed.
- The printed scoreboard's column headers, metric names and polarity legend are unpinned
  (partially subsumed by V2).

---

## Accepted without action

**The spec's own "Goal issue" callout (§ lines 62–75) is correct, and the flaw is in `goal.md`,
not the spec.** Goal #3 filters candidates to `impact_label == "high"`, so every vendored record
is `high` by construction — making goal #6's `medium`/`low` enforcement branches dead code
against real data, exercisable only by synthetic Vitest fixtures. The spec's own resolution is
accepted verbatim: not a contradiction (the filter and the severity rule serve different
purposes), but the README must say `medium`/`low` coverage is unit-test-only rather than implying
the demo exercises the full ladder. No goal amendment; no refinement action beyond what §1 and
T1 already require of the README.
