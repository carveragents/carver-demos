# Orchestrator decisions — binding addendum to the spec

**Status:** authoritative. Read alongside `goal.md`, the approved spec
(`.tandem/mastra-guardrail-v2/stages/01-spec/artifact.md`) and the approved plan
(`.tandem/mastra-guardrail-v2/stages/02-plan/artifact.md`).

**Why this file exists.** `01-spec` is APPROVED and **refine-capped at 3** — it cannot be edited.
The plan therefore raised four genuine spec defects as **callouts with pinned safe readings**,
each explicitly deferred to the orchestrator ("*so the two consumers cannot diverge while the
orchestrator decides*"). This records the rulings. **Where this file and the spec disagree, this
file wins; everywhere else the spec is unchanged and binding.**

**Precedence:** `goal.md` → this file → spec → plan.

---

## D1 — `asJudgeObligation` is owned by `judge/contract.ts` (type-only import). ACCEPTED.

**The defect.** `evals/scorers.ts` (spec:5108) and `processors/carverGuardrail.ts` (spec:4211)
both call `asJudgeObligation(record)`; §9b describes its behaviour (spec:4225 — builds
`{id, title, key_requirements, objective}`, never `citation`, never `baseline_failures`). **No §1
module row exports it.** It could not simply be added to `judge/contract.ts`, whose imports §1 pins
as "zod only", while the adapter takes a `ClearedRecord` (owned by `schema.ts`).

**Ruling — the plan's reading, accepted verbatim.** `judge/contract.ts` **owns**
`asJudgeObligation`. Its import row becomes **"zod, plus `type ClearedRecord` from `schema.ts`"**.
**P6.4 creates it; P6.9 and P6.12b import it.**

**Why this is safe, not a fudge.** A TypeScript `import type` is **fully erased at compile time**
— it adds no runtime edge whatsoever. `contract.ts` keeps the leaf property that actually matters,
and the `judgeAgent ↔ scorers` cycle cannot re-form (`schema.ts` imports zod only).

**Why it had to be decided rather than left.** This is the most dangerous of the four. A subagent
with nowhere to put the adapter would most likely define it **twice** — and because it builds the
judge's obligation *input*, two drifting copies would feed the guarded arm and the eval **subtly
different questions while every test still passed**. A silent divergence in the one function that
frames the question is exactly the failure this project's whole measurement design exists to
prevent.

## D2 — `emit_template_config` writes by idempotent replacement. ACCEPTED.

**The defect.** §7 step 8 says the generator renders a fragment and writes it into its owning `.ts`
file, but never says what happens when that file **already contains** a previously generated line
plus hand-authored code — which is exactly P8.2's state, where the generator re-runs over real
reviewed data against files Phase 6 has since filled in.

**Ruling — the plan's reading, accepted verbatim.** The write is **idempotent replacement**: if a
line declaring the target symbol exists, replace it in place; otherwise insert it. P3.2's
`test_emit_is_idempotent` asserts it — running the generator twice over a file carrying
hand-authored code yields byte-identical output, exactly one declaration of each generated symbol,
and the hand-authored exports still present.

**Why.** The alternative reading (whole-file write) would have **P8.2 silently delete every
hand-authored export in `config.ts`, `firmProfile.ts` and `baselineAgent.ts` one step before
ship**. The spec licenses neither reading; only one is survivable.

## D3 — `evals/scorers.ts` imports `scenario/prompts.ts`. ACCEPTED (omission confirmed).

**The defect.** `runArm` calls `buildStageAPrompt(record)` (spec:5276) and `runStageBEval` calls
`buildStageBPrompt(r)` (spec:5427); both builders live in `scenario/prompts.ts`. §8's import row
for `evals/scorers.ts` omits it. A subagent following the pinned list literally would call two
unimported functions.

**Ruling.** The row is **incomplete**; `evals/scorers.ts` **does** import `scenario/prompts.ts`.
No cycle is introduced (`prompts.ts` is generated and imports only `schema.ts`). An omission to
confirm, not a design change.

**Note.** The plan's diagnosis is correct and worth recording: the spec's own F8 fix removed
`scenario/prompts.ts` from **`deliveryWorkflow.ts`**'s row (those workflows receive already-built
prompt strings) and noted the builders are "called by `evals/scorers.ts`" — *without adding it to
that module's row*. **The authoritative site was fixed; its restatement went stale.** That is the
third instance of this exact pattern found in the approved spec, and the reason the plan's rubric
now requires every task changing a fact to name where else that fact is stated.

## D4 — `stubs.py` holds the classes; `conftest.py` holds the fixtures. ACCEPTED.

**The defect.** §1's tree gives `conftest.py` and `stubs.py` overlapping descriptions.

**Ruling — the plan's reading, accepted verbatim.** **Classes in `stubs.py`, fixtures in
`conftest.py`.** §1's own parenthetical justifies `stubs.py` on import-trap grounds (see
`docs/LESSONS.md`), which only makes sense if the classes live there.

---

## Also recorded

**The plan's "Spec issues found while planning: None" summary is STALE.** Four callouts exist in
the task bodies (P2.0, P3.2, P6.12b ×2) and the round-8 changelog describes raising them. The
summary was written at round 4 and never updated as rounds 6–8 found them — *the same
authoritative-site-fixed, restatement-stale pattern the plan itself keeps catching, one level up.*
**This file is the authority on spec issues, not that section.** Implementation must not read
"None" and conclude there are no rulings to follow.

**Carried forward from the spec, unchanged — planned constraints, not defects:**
- Every vendored record is `impact_label == "high"` by construction (goal #3), so goal #6's
  `medium`/`low` severity branches are **dead code against real data**. Covered by synthetic
  fixtures in `carverGuardrail.test.ts` (P6.9); `template/README.md` states the limitation (P6.16).
  No task exercises them live.
- Goal #10's scenario rule does not guarantee the winner can support success criterion #2. Handled
  by reporting (`stage_a_survivor_counts`) and a loud raise (P8.2) — **never** by silently
  re-ranking scenarios.

**The cutoff is `2026-03-01`, the pool `8,260`.** The `2026-03-02` / 8,199 amendment was issued and
**withdrawn** (`.tandem/mastra-guardrail-v2/stress-test/001-refinement.md`, final section). Do not
relitigate.

---

## D5 — The RC substep's mandated agents do not exist. RULED. *(added 2026-07-17)*

**The defect.** This repo's `CLAUDE.md` (lines 18–19) names **`python-code-reviewer`** and
**`python-expert`** and mandates running them after every Python change. **Neither is installed** —
no definition at user or project level, and neither is a valid agent type. The goal inherited the
requirement from `CLAUDE.md`; the plan restated it as a mandatory **RC** substep on every Python
task (4 mentions). Nobody checked the agents existed. **The RC substep, as written throughout this
project, cannot execute.**

**A second, related contradiction.** `CLAUDE.md` says **Opus** for "code review". The only real
reviewer, `code-quality-reviewer`, is pinned in its frontmatter to **sonnet**.

**Ruling — the RC substep is redefined as follows, and this supersedes the goal, the plan, and
`CLAUDE.md` on this point:**

1. Dispatch **`code-quality-reviewer`** (it exists) with **`model: "opus"` set explicitly on the
   Agent call**. The `model` parameter overrides frontmatter, which resolves `CLAUDE.md`'s own
   sonnet-vs-Opus contradiction in favour of what it actually asks for.
2. **The implementing agent applies the findings itself** — there is no `python-expert` to delegate
   to. Findings are **not** applied blindly: where a finding is wrong, or would violate a spec/goal
   constraint, the agent says so with its reasoning and does not make the change. **The spec is the
   contract; a reviewer's opinion does not override it.**
3. Re-run the task's Verify and paste real output.

**Why this is recorded rather than silently worked around.** The RC substep is the project's only
per-task quality gate. A mandated gate that cannot run is worse than no gate: every task reports
"RC done" against an agent that was never invoked, and the claim reads as coverage. That is the
same defect class this project has now found four times — *a claim of a mechanism, standing over
no mechanism* — arriving this time through the repo's own conventions rather than the spec.

**`CLAUDE.md` is not edited** (this repo forbids modifying it during a session). This file is the
authority on what RC means here.

## D6 — Model right-sizing for the remaining phases. RECORDED. *(added 2026-07-17)*

`CLAUDE.md`: Haiku = mechanical · Sonnet = routine implementation · **Opus = complex reasoning,
security-sensitive/high-impact changes, and code review.**

**An evidenced miss, recorded so it isn't repeated.** Stress-test 001 ran the *anti-padding*
dimension on Sonnet and *experimental validity* on Opus. The Sonnet reader's own table of padding
levers **omitted `reasoning_effort`** — the single unblocked rigging bypass — which the Opus reader
found on a different dimension. Same document, same grounding rules. **Adversarial reading is Opus
work.**

**Binding for the rest of the build:**

| Work | Model | Why |
|---|---|---|
| `prompts/*.md` (verbatim from spec), `.env.example`, file moves | **Haiku** | genuinely mechanical; nothing has used Haiku yet, which means over-spend |
| LEAF modules, `review.py`, report/demo scripts, README | **Sonnet** | routine implementation against a pinned spec |
| `budget.py`, `probe.py`, `curate.py`, `scoring.py` (the failure bar), `scenario_decision.py`, `carverGuardrail.ts`, `evals/*` | **Opus** | evidence integrity, the spend ceiling, the measurement — high-impact by `CLAUDE.md`'s own rule |
| **Every RC review** (per D5) | **Opus** | `CLAUDE.md` names code review as Opus work |
| **Every adversarial stress-test / audit** | **Opus** | see the evidenced miss above |

## D7 — §3/§4's verbatim prompt templates are authoritative; §1's tree comments are STALE. RULED. *(added 2026-07-17)*

**The defect.** The spec's §1 layout tree annotates each prompt file with its placeholders
(lines 294–299). Those annotations **contradict §3/§4's verbatim templates**, which are the actual
prompt text:

| File | §1's tree comment (line) | §3/§4's real template | Verdict |
|---|---|---|---|
| `stage_a_system.md` | `{{PERSONA}} {{COMPANY}} {{JURISDICTION_PHRASE}} {{DOMAIN_PHRASE}} {{TASK_VERB_PHRASE}}` (294) | `{{PERSONA}}` `{{COMPANY}}` | tree comment over-lists |
| `stage_b_user.md` | `{{FOLLOWUP_QUESTION}}` (297) | `{{DOMAIN_PHRASE}}` `{{JURISDICTION_PHRASE}}` `{{RECENCY_PHRASE}}` `{{TASK_NOUN_PHRASE}}` `{{TASK_VERB_PHRASE}}` `{{UPDATE_TYPE_PHRASE}}` | **entirely wrong** |
| `judge_user.md` | `{{RECORD_SUMMARY}} {{DRAFT_TEXT}}` (299) | `{{OBLIGATIONS_JSON}}` `{{DRAFT_TEXT}}` | **half wrong** |

**Proof they are phantoms, not an alternative reading.** Across the whole 6,002-line spec:
- **`{{FOLLOWUP_QUESTION}}` occurs exactly ONCE — at line 297, the tree comment itself.** It
  appears in no template, no renderer, and no test.
- **`{{RECORD_SUMMARY}}` occurs exactly ONCE — at line 299, the tree comment itself.**

A placeholder that exists only in a comment describing a file is not a placeholder. Both are
residue from an early draft, never updated as §3/§4's templates were rewritten across 13 rounds.

**Ruling.** **§3/§4's verbatim templates are authoritative.** `{{FOLLOWUP_QUESTION}}` and
`{{RECORD_SUMMARY}}` **do not exist** and must never be introduced. §1's tree comments on lines
294–299 are stale and carry no weight.

**The authoritative placeholder set — every downstream renderer builds against THIS:**

| File | Placeholders |
|---|---|
| `stage_a_system.md` | `{{PERSONA}}` `{{COMPANY}}` |
| `stage_a_user.md` | `{{TASK_INSTANCE}}` |
| `stage_b_system.md` | `{{PERSONA}}` `{{COMPANY}}` |
| `stage_b_user.md` | `{{DOMAIN_PHRASE}}` `{{JURISDICTION_PHRASE}}` `{{RECENCY_PHRASE}}` `{{TASK_NOUN_PHRASE}}` `{{TASK_VERB_PHRASE}}` `{{UPDATE_TYPE_PHRASE}}` |
| `judge_system.md` | *(none)* |
| `judge_user.md` | `{{OBLIGATIONS_JSON}}` `{{DRAFT_TEXT}}` |

The shipped files (P1.13, commit `94540e9`) already match this and are **correct as built**.

**Why this needed a ruling rather than a shrug.** P2.1 implements `render_task_instance()`, which
**asserts no `{{}}` remains** after rendering. A renderer built against §1's list would look for
`{{FOLLOWUP_QUESTION}}` in a template that has six different placeholders — and §3's fair-test
discipline is enforced by `test_task_instance_excludes_leaked_fields`, which checks what the
rendered prompt contains. Getting the placeholder set wrong breaks the renderer *and* the test that
guards the experiment's fairness.

**This is the FIFTH instance of one pattern in this project** — *the authoritative site is fixed;
its restatement goes stale.* Previously: the two `{ compareWorkflow }` constructors; §15's stale
call count; `isTripWireError`'s orphaned owner row; `evals/scorers.ts`'s missing import row (D3).
A sixth sits one level up, in the plan's own "Spec issues found while planning: **None**" summary,
written at round 4 and never updated as rounds 6–8 found four. It is the defect class this project
generates, and the reason the plan's rubric now requires every task changing a fact to name where
else that fact is stated.

**Found by a Haiku agent doing verbatim transcription** — it noticed the templates disagreed with
the brief, followed the spec's actual text, and reported the conflict instead of silently picking
one. Right-sizing does not mean the cheap tier cannot catch things; it means matching the tier to
the *kind* of work. Transcription is exactly where a placeholder mismatch becomes visible.

## D8 — 🔴 NaN defeats the spend ceiling entirely. FIXED. Both enforcement points must guard. *(added 2026-07-17)*

**The defect — a live path to unbounded spend on a real card.** The spec's price floor and ceiling
gate are both `<`/`>` comparisons. **Every comparison against NaN returns `False`**, so a NaN price
passes every guard. `config.yaml` is user-editable and PyYAML resolves `.nan` to a real float.

**Verified by execution, not argued:**

```
config.yaml: 'price_input_per_million_usd: .nan'  ->  nan  (type float)   # PyYAML resolves it
nan < 5.00                       -> False    # the price floor PASSES a NaN price
spend + nan > 120.0              -> False    # reserve()'s ceiling gate NEVER fires
spend after 3 reserves           -> nan      # ceiling 120.0, never raised
assert spend <= ceiling          -> False    # ...but never RAN: every guard short-circuited
```

**One word in a config file defeats the most defended mechanism in this project** — the ceiling
with four adversarial revisions, doubled enforcement, and a written proof ending in ∎. The proof's
premise (`spend_so_far_usd <= ceiling_usd` at every point) is *false* under NaN and *never
evaluated*, because each guard that would have raised compared against NaN and returned False.

**Ruling.** `math.isfinite()` guards on **every** price and on `ceiling_usd`, at **both**
enforcement points. Verified: `isfinite` rejects `nan`, `inf` and `-inf`, and accepts real values.
- `SpendBudget.__init__` — **done** (P1.11, commit `12f4688`), tested with 5 below-floor params,
  4 non-finite, and boundary cases.
- **`load_settings()` — REQUIRED, and P1.1's author MUST implement it.** §13's check is the same
  `<` shape and has the same hole. The spec's own rationale for doubling this check ("so it holds
  even for direct construction in a test or script that bypasses `load_settings()`") applies
  symmetrically: a guard that exists twice must be *correct* twice.

**Why no amount of reading found this.** `if price < PINNED_PRICE_INPUT: raise` reads as obviously
correct, and did so through 13 spec rounds, two orchestrator stress-tests, and six grounded
readers. It is only wrong when executed with a value whose comparison semantics are unusual. **This
is the third time in this project that execution beat reading** — after the yield gate's empty
`user_instruction` and the `ast`-walk's escaping `level >= 2` relative imports. Treat "the guard
reads correct" as unverified until it has been run against its adversarial input.

## D9 — `id()` reuse made the reservation leak audit a no-op. FIXED (monotonic `seq`). *(added 2026-07-17)*

**The defect.** `_open` held `id(r)` **ints, not references**. A leaked handle is freed by
refcounting immediately, CPython recycles its address, and the next `reserve()` gets the same
`id()` — so `add(id(r))` was a no-op and terminating the *new* handle discarded the *leaked* one's
entry. **Measured through the real `reserve()` path: the leak was masked in 4,999 of 5,000 runs.**
With a monotonic `seq`: **0 of 5,000**.

**Why it matters beyond the bug.** §3's proof table credits this row to
`assert_no_open_reservations()` — the audit existed precisely to catch a leaked hold, and in the
one scenario it exists for, it almost never worked. Ceiling-safe either way (a leak *over*-states
spend), but a proof citing a mechanism that does nothing is the same defect class as a claim
standing over no mechanism.

**Noted, because it is instructive:** the implementing agent's first probe showed 0/2000 and it
nearly dismissed the finding — a stray `gc.collect()` was perturbing the allocator. It re-probed
and reported *"The reviewer was right; I was wrong."* A first measurement that clears a suspicion
is not proof; measure the measurement.

## D10 — `budget.py` uses stdlib `logging` directly, not `logging_.log()`. FORCED. *(added 2026-07-17)*

**The contradiction.** §3's pinned `budget.py` code calls `log()` from `logging_.py`. But §1 pins
`budget.py`'s intra-package imports to **none**, and `test_imports.py` enforces it with
`PINNED_EMPTY_LEAVES = ("budget", "logging_")`. **§3's code cannot satisfy §1's constraint.**

**Ruling.** §1's leaf property wins — it is structural (it is what broke the real
`probe → curate → probe` cycle) and mechanically enforced. `budget.py` calls
`logging.getLogger("mastra_prep").info(...)` directly, which §1:458 pins as exactly what
`logging_.log` wraps: **identical channel, no behavioural difference**, now asserted by a `caplog`
test. Not a licence to bypass `logging_` elsewhere — `budget.py` is the only pinned-empty leaf that
§3's code asks to log.

## D11 — §3:1180's `reservation_basis_tokens` is authoritative; §14's restatement is STALE. *(added 2026-07-17)*

§14's restatement of `reservation_basis_tokens` **omits `ensure_ascii=False`**, which §3:1180's
pinned code has. **§3 is right**: the wire is UTF-8, and escaping non-ASCII inflates the byte count,
which *weakens* the anomaly tripwire the reservation basis feeds. Pinned by a non-ASCII test —
without which, dropping the kwarg passed the **entire suite** silently.

**Sixth instance** of authoritative-site-fixed / restatement-stale (after the two
`{ compareWorkflow }` constructors, §15's call count, `isTripWireError`'s owner row, D3's import
row, and D7's prompt placeholders). It is this project's signature defect.

## D12 — `candidates.py` and `config.py` are NOT leaves. Import from `budget.py`; never duplicate. *(added 2026-07-17)*

**The coming edge.** `assert_cutoff_margin` (the D-goal-#3 derivation) needs `MODEL_CUTOFF` and
`CUTOFF_MARGIN_DAYS`, which live in `budget.py`. So `candidates → budget` and `config → candidates`
edges are real — but **§1:427 lists both `candidates` and `config` as LEAVES**, and
`test_imports.py` will **not** catch the error (neither edge forms a cycle).

**Ruling, binding on P1.4 and P1.1.** **Import the constants from `budget.py`. Do NOT duplicate
them.** Duplication is precisely the drift the cross-language drift-check exists to prevent, and it
would put the cutoff derivation's inputs in two places — the exact shape of V9, the hole that
ruling was raised to close. §1:427's leaf listing for these two modules is **stale**; `budget.py`
remains the only pinned-empty leaf that matters, and it stays empty.

## D13 — §2 wins: the cutoff key was INERT, and the equality check is required. RULED. *(added 2026-07-17)*

**The defect — V9 reopened one level down.** §13:5717 describes `candidate_cutoff_date`'s effect as
the "`is_candidate()` predicate". But §2:579 pins `is_candidate(rec: dict)` — **no `cfg`
parameter** — and §2:576 pins `CANDIDATE_CUTOFF_DATE` as a **module constant**. The config key
therefore **cannot reach the filter**. `assert_cutoff_margin` validated the key; `is_candidate`
read the constant. **The guard guarded a value nothing read.**

**Why this is worse than an inconsistency.** After a model swap, an operator who *complied with the
error message* — edited `candidate_cutoff_date` to the new model's derived floor — would see
startup pass while the filter kept admitting from `2026-03-01`, inside the new model's training
window. Reproduced by the implementing agent: **three in-training-data records admitted.** V9 was
raised in stress-test 001 precisely to stop this; the spec closed it at the site I named and left
it open at the site I didn't.

**Ruling.** **§2 is authoritative** (it pins the executable signatures). The fix stands: the
derivation now checks **the constant the filter actually reads**, and `config.py` asserts the key
and the constant agree — so §13's claim becomes *true* rather than aspirational. Re-verified: the
exploit is unreachable by any config edit.

**This is the fifth "mechanism that reads correct and does nothing" in this project** — after the
yield gate's unenforced `user_instruction`, the `ast`-walk's escaping relative imports, NaN
defeating the ceiling, and `id()` reuse nulling the leak audit. Also in this task:
`CUTOFF_MARGIN_IS_INCLUSIVE` — §2's advertised "flip one constant" escape hatch — was **a switch
connected to nothing**, now wired.

**Also ruled, from the same task (all ACCEPTED):**
- **Dedup is "first occurrence in file order wins"** (§2's literal rule). The agent's own first
  implementation used "first *passing* occurrence", which **widened the pool via re-annotation —
  the padding direction**. Caught in its own code and corrected.
- **`load_settings()` raises a documented error on `OverflowError`.** A 400-digit int makes
  `float()` raise `OverflowError`, which is **not** a `ValueError` and escaped the documented
  contract as a traceback. Found by probing, not reading.
- **`judge_confidence_floor` gets `isfinite` and a `<= 1.0` upper bound.** §13 pins only `>= 0.7`;
  spec:2046/3761 make 1.0 the right ceiling. Additive; tightens.
- **D8's battery extended beyond the brief:** `!!float nan` (explicit tag) and `1.0e+400`
  (exponent overflow to `inf`, which does not *look* non-finite) both reach real floats through
  PyYAML and are now rejected. `1e999` stays a `str` and dies on the type check.
- **`MODEL_ID` does not exist prep-side.** §2:668's error message interpolates it — as written a
  `NameError` (the only occurrence is a *comment* at `budget.py:91`), and importing `config` would
  close a `config → candidates → config` cycle. The message names the real edit sites instead.

## D14 — 🔴 V9's true residual: nothing ties `MODEL_CUTOFF` to `MODEL_ID`. MUST CLOSE. *(added 2026-07-17)*

**The defect, flagged by P1.1's author and correctly NOT fixed unilaterally.** §13:5714 pins
`model_router_string`'s only constraint as *"must start with `openai/`"*. So a forker can swap
`MODEL_ID` to a later-cutoff model, **forget `MODEL_CUTOFF`**, and every check passes — while the
filter admits documents inside the new model's training data. D13 fixed the key→constant link;
this is the *other* half, and it is the hole V9 was actually about.

**Why prose cannot close it.** goal #9 **actively invites the swap** ("anyone forking this —
including Mastra — can swap providers by editing one line"), and goal #3 says the date "**MUST** be
re-derived from the new model's documented cutoff". A MUST with no mechanism is the defect class
this project keeps producing. D8, D9, D13 are all the same lesson.

**Ruling — close it with a table, not a sentence.**
1. Add **`MODEL_CUTOFFS: dict[str, str]`** to `budget.py` (it already owns `MODEL_CUTOFF`; it stays
   an empty leaf) — a pinned map of known model-router strings → their **provider-documented**
   knowledge cutoffs. Seed it with the verified entry: `"openai/gpt-5.6-sol": "2026-02-16"`.
2. **`load_settings()` asserts `MODEL_CUTOFF == MODEL_CUTOFFS[model_router_string]`**, and raises a
   loud, instructive error when the model is **absent from the table**: *"unknown model — add its
   documented cutoff to `MODEL_CUTOFFS` and re-derive `CANDIDATE_CUTOFF_DATE`; see goal #3."*
3. Effect: the one-line swap goal #9 invites now **fails closed**. You cannot change `MODEL_ID`
   without confronting the cutoff, and once the cutoff is right, `assert_cutoff_margin` derives the
   correct filter date automatically.

This makes goal #3's "MUST be re-derived" a mechanism. **It tightens only** — no currently-shipping
value changes: `openai/gpt-5.6-sol`, cutoff `2026-02-16`, filter `2026-03-01`, pool **8,260**.

## D15 — §2's FLAT record shape wins over §7's nested pseudocode. RULED. *(added 2026-07-17)*

**The defect.** §7's eligibility pseudocode reads `record["jurisdiction"]["country"]` (**nested**).
But `extract_record()` — built from **§2's own `FIELD_MAP`**, already landed and tested against the
real corpus record — flattens that to top-level **`jurisdiction_country`** / **`jurisdiction_bloc`**.
§7's form would `KeyError` on the first real record.

**Ruling.** **§2 is authoritative.** §2 owns the extractor; every record flowing through this
pipeline has §2's flat shape, verified against `sample_record.json` (a trimmed copy of the real
line 1 of `annotations.jsonl`) and `test_extract.py`. `scenarios.py` implements the flat shape and
documents why at the top of the module and its test.

**Pattern note:** producer and consumer disagreeing about a data shape is the same defect family as
D3/D7/D11 — a fact restated in a second place and left stale. Here the *executable* site (the
`FIELD_MAP`) is right and the *pseudocode* is wrong, which is the safer direction only because a
`KeyError` is loud.

## D16 — 🔴 The spec's own negative-control task fails the spec's own benign test. FIXED. *(added 2026-07-17)*

**The defect.** `NEGATIVE_CONTROL_TASKS["B"]` includes, verbatim, *"the **marketing** team's
offsite venue and travel logistics"* as a **benign** topic. But `marketing` is itself a
`SCENARIO_B_PROMOTIONAL_TERMS` keyword — so **the spec's own literal text fails its own
`test_negative_control_tasks_are_benign`.**

**Why this is not cosmetic.** The negative control is **V1's fix** — the population that proves the
guardrail *discriminates* rather than blankets, and the only thing standing between this project
and a guardrail that blocks everything scoring 1.0. A "benign" prompt that is itself
Scenario-B-eligible is **not benign**: it could legitimately be blocked, and the
`benign_task_pass_rate` — the number the whole specificity argument rests on — would be measuring
something else. A control that isn't controlled is worse than none.

**Ruling.** Renamed to *"the **sales** team's offsite venue and travel logistics"* — same benign
intent, no keyword collision. Documented inline as a spec bug, not a design change. **ACCEPTED.**

**Also ruled, from the same task (all ACCEPTED):**
- **`_domain_phrase` leaked the other scenario's bucket into prompts.** It searched the tag→bucket
  table **unscoped**, so a record eligible for both scenarios could carry Scenario B's domain
  phrase into a Scenario A prompt — a **fair-test leak** in the exact module §3's MUST-NOT list
  exists to protect. Fixed with per-scenario keyword slices; covered by a leak test and a
  full-keyword-sweep invariant.
- **`make_client()` accepted a blank key.** It checked presence, not emptiness, so `OPENAI_API_KEY=`
  produced a client that fails opaquely on first real use. Now requires a stripped non-empty value.
  (Same shape as the yield gate's `user_instruction: ""` — *present* is not *populated*.)
- **`is_eligible` raises on an unrecognized scenario id** instead of silently falling through to B.
- **The proportionality bound's claim now matches its evidence.** The reviewer flagged the
  `<1`-per-prefix bound as provable for 3 strata but **unproven for K≥4** ("unproven, not false").
  The agent ran an exhaustive search — 4,342 small configurations + 60 randomized up to 80 strata,
  **zero violations, worst observed 0.988** — added a many-strata regression test, and **softened
  the docstring to "strongly empirically supported"** rather than assert an unproven theorem.
  Measuring rather than deferring, then making the claim fit the evidence: the correct move at both
  ends.

**Deferred, correctly:** `buckets_golden.json` (the cross-language mapping lock) is owned by P1.9
and had not landed. Rather than create a file outside its task's scope, `test_scenarios.py` asserts
the same invariants inline so the parity test can be bolted on without touching the module.

## D17 — Model ALIASES are rejected. Only the explicit id. RULED, and it overturns goal #9. *(added 2026-07-17)*

**Surfaced by D14's implementing agent, by execution, against a ruling I wrote.**

**goal #9 blessed two router strings** — `openai/gpt-5.6-sol` (explicit) and `openai/gpt-5.6` (the
bare alias → Sol). I recorded that from the model research and never revisited it. D14's
`MODEL_CUTOFFS` table, seeded per the ruling's literal "one verified entry", rejects the alias.
That looked like an oversight. **It is the correct behaviour, and the reason matters:**

**An alias's target changes.** A forker complying *honestly* with D14's error message — "add your
model's documented cutoff to `MODEL_CUTOFFS`" — would add `openai/gpt-5.6` pinned to today's Sol
cutoff. **The day the alias re-points to a newer model, that pinned cutoff silently stops being
true — and passes both D14 checks**, because the model *is* in the table and the cutoff *does*
match the table. V9, reopened through the one door D14 opened. Verified by execution.

**Ruling.** **Aliases are forbidden as the pinned model. `MODEL_CUTOFFS` contains explicit model
ids only.** goal #9's blessing of `openai/gpt-5.6` is **superseded on this narrow point**;
`goal.md` is amended. D14's error message now warns explicitly against pinning an alias. Everything
else in goal #9 stands: `openai/gpt-5.6-sol`, cutoff `2026-02-16`, filter `2026-03-01`, pool 8,260.

**A knowledge cutoff is a property of a MODEL, not of a NAME that currently points at one.** Any
indirection between the pinned id and the weights makes the pinned cutoff unfalsifiable at the only
moment it matters.

### D14's true limit — state it plainly, and put it in the template README

The implementing agent's own words, accepted verbatim:

> *"The table's correctness rests on a human reading provider docs, and no code can check that. D14
> converts 'forget the cutoff entirely' (silent) into 'state the cutoff wrongly' (a deliberate,
> reviewable act) — a real tightening, but not a proof. The residual is a forker who guesses a
> date. It closes the **forgetting**, not the **lying**."*

**D14 must not be cited as closing V9 completely.** It closes the *silent* path. The remaining
residual is a human writing a wrong date into a reviewable table — visible in a diff, unlike the
original hole. That is the honest claim, and goal #9's transparency section (the "defence against
the cherry-picking charge") is the wrong place to overstate it. **P6.16's README task must carry
this limitation verbatim.**

### Also recorded — the signature defect, four times, inside the fix that was closing an instance of it

D14's RC (`code-quality-reviewer`, opus) found, in the agent's *own* new code:
1. **An "ORDER IS LOAD-BEARING" comment that was false.** It claimed reversing two gates would let
   a bad config *pass*; both raise, so closure is order-independent. But the order *does* matter —
   for **remediation correctness**: running the derivation first announces a floor computed from
   the *stale* cutoff, and an operator complying with **that** message re-corrupts the filter —
   **D13's exact shape**. The claim was rewritten and pinned with a test, mutation-verified to fail
   when reordered.
2. **`MODEL_CUTOFF`'s own comment went stale in the very change closing an instance of
   authoritative-site-fixed/restatement-stale** — the **seventh** instance, produced by the fix for
   the sixth. It now names the cross-check and records that the duplicated date **is** the
   mechanism: DRY-ing it to `MODEL_CUTOFFS[...]` would reduce the assertion to `x == x`.
3. **`assert not isinstance(exc, KeyError)` could never fire** (disjoint exception hierarchies) — a
   **dead assertion carrying the test's whole point**, inside a test written to prevent dead
   assertions.

This project's defect is not carelessness. It is that **a claim about a mechanism is itself
unmechanized**, and writing the claim feels like establishing the fact. It reproduces inside the
fixes for itself. Only execution and adversarial review have ever caught an instance.

## D18 — `impactedFunctions` (camelCase) wins; §9a's pseudocode is wrong. RULED. *(added 2026-07-17)*

**The defect — D15's family, with a worse blast radius.** §9a's `narrowObligationsPure` pseudocode
reads **`firm.impacted_functions`** (:4090, :4095). But `FirmProfileSchema` (:3319-3325),
`firmProfileForRecord` (:3360), **§9a's own proof** (:4150) and §1's module table all pin
**`impactedFunctions`**.

**Why it matters more than a naming nit.** In TypeScript, reading a misspelled property is not an
error — it is `undefined`. §9a's snippet would therefore narrow on **jurisdiction alone**, silently.
The guardrail would still fire, still block, still look correct — and surface the **wrong
obligations**, because one of its two required predicates evaporated. Nothing would fail.

**Ruling.** **`impactedFunctions` (camelCase) is authoritative** — the executable sites and §9a's
own proof agree; only the snippet dissents. Per D15's precedent, the executable site wins.
`narrowing_golden.json` is built on `impactedFunctions` and a test pins it, so **a P6 implementer
copying §9a's snippet verbatim goes RED** rather than shipping a non-narrowing guardrail. That is
the correct failure direction and the reason this must be a ruling, not a comment.

**Eighth instance** of authoritative-site-fixed / restatement-stale.

## D19 — The `confidence_nan` golden case is `prep_only`. §4:2120 asks for the unachievable. RULED. *(added 2026-07-17)*

**The defect — a spec requirement no implementation can satisfy.** The golden fixtures must
reproduce **every** case identically on both sides of the Python/TypeScript seam. For
`confidence_nan_discarded`, that is **impossible**, because the two languages disagree on whether
the input is *parseable at all*:

| | `json.loads` (Python) | `JSON.parse` (JS) |
|---|---|---|
| bare `NaN` in the payload | **accepts** → §4 **step 3** → rationale *"out-of-range"* | **rejects** → §4 **step 1** → rationale *"omitted"* |

§4:2088-2093 **requires the two rationales to differ**, so **no single expected value satisfies both
sides.** The implementing agent's own "convergence" note was wrong, and it said so.

**Ruling.** The case is tagged **`prep_only`** with a named allowlist — resolved exactly as §4
already resolves its own 4-arg/3-arg signature seam. **Narrower and true** beats a shared claim
that cannot hold. §4:2120's "reproduces every case on both sides" is **scoped to cases both
languages can parse**; the allowlist is the mechanism, and it is mutation-tested (an unlisted
escape fails).

**Both behaviours remain correct** — each language discards the value; only the *rationale* differs,
and the rationale is a diagnostic, not a decision. Nothing about the failure bar changes.

## D20 — `buckets_golden`'s scenario-scoped defaults vs the template's flat `DOMAIN_BUCKETS`. RULED. *(added 2026-07-17)*

**The defect.** `buckets_golden.json`'s unmapped-tag defaults are **scenario-scoped** (A and B have
different fallbacks). But §8:4007 pins the template's `DOMAIN_BUCKETS: readonly string[]` — **flat,
the winner's five only**, because goal #10 ships exactly one scenario. So `prompts.test.ts` can only
run the cases for the shipped scenario, making §14:5782's *"reproduces **every** case"* false at P6.

**Ruling.** **`prompts.test.ts` runs the shipped scenario's cases only**, and §14:5782's "every
case" is **scoped to the shipped scenario**. This is not a weakening: the template *has* no other
scenario — goal #10 locks one winner and `emit_template_config` generates its constants alone. A
test asserting the losing scenario's buckets would be asserting against code that does not ship.
`prep/`'s side continues to cover **both** scenarios (it must — the trial probes both).

The fixture's `_readme` records the split. **Ruled now, deliberately** — the agent's point that it
is "cheap to rule on now, expensive once both byte-identical copies are frozen" is correct.

## Also recorded — from P1.9/P1.10

**🔴 A boolean `confidence` walks a naive range check as `1.0`.** `isinstance(True, int)` is `True`
and `0.0 <= True <= 1.0` passes — so a judge returning `confidence: true` would clear the **0.7
floor** and admit a record. **D8's family, on the judge axis** (D8 was NaN through a `<`; this is a
bool through a range check). TypeScript rejects it, so the two sides would have diverged silently.
Now `confidence_boolean_discarded`, tested both sides. *Every* naive numeric guard in this project
has now been found permeable by exactly one unusual value.

**`validate_cleared_record` broke its own "never raises" contract** — it raised `TypeError` on
`None`/`int`/`float`/`bool`, reachable in the real world via a `data/cleared/` file containing
`[null]`. The publication gate must never raise; it must **reject**.

**`citation.url` was the seam's one reversal** — TypeScript stricter than the Python gate. Fixed.

**Found only by execution, again:**
- The agent's own bucket fixture **claimed full coverage and had 9/10** — a missing `retail
  financial promotions` case, visible only when run against the real table.
- **`narrowing_golden`'s `expectedTopFiveIds` were hand-authored against a function that does not
  exist yet.** Rather than ship unverified expectations, the agent wrote a reference port of §9a
  and ran all 17 cases. Hand-authored expectations for unwritten code are assertions wearing a
  fixture's clothes.
- **P1.10 catches the realistic drift**: a byte flip *inside a string* that leaves the JSON
  perfectly valid is invisible to a parse check and caught **only** by the byte comparison.

## Correction to my own instruction — `__init__.py` belongs to P3.2

**My P1.9 brief was wrong.** I asked for §1's pinned re-export block "verbatim" in Phase 1. The plan
had already assigned it to **P3.2** (G6), and stated why: *"a Phase-1 `__init__.py` would import
modules that do not exist yet."*

The agent **did not argue — it tested my instruction**: three of the thirteen re-exported modules
(`curate`, `scenario_decision`, `generate_template_config`) are Phase 2/3, so the verbatim block
raises `ModuleNotFoundError` on **any** `mastra_prep` import and collapses the suite from **449
passed to 5 collection errors, 0 tests run** — violating the "no regression" constraint in my own
brief. My verification item ("`test_imports.py` still passes with `__init__.py` populated") rested
on a false premise.

**Ruling: `__init__.py` stays with P3.2, unchanged.** Recorded because the correction came from an
agent refusing an orchestrator instruction **on evidence**, which is exactly the behaviour every
brief in this project asks for and the reason it is worth asking.

## D21 — Demo speed beats coverage. The plan's ceremony is CUT. RULED. *(added 2026-07-17)*

**The user's instruction, verbatim:** *"we're building a simple demo, not a full baked production
product. i'd rather have something quick to test on and iterate than a bulletproof
code-that-takes-weeks-to-build artifact because we're thinking of every edge case possible. the
purpose of this specific project is speed to demo. done is better than perfect. when we do a demo
walkthru, we can always fix issues."*

This is a **user instruction and therefore outranks everything below `goal.md`** — including the
approved plan. The plan optimized for a correctness proof; the user wants a walkthrough.

**CUT from the plan, with immediate effect:**

| Cut | Plan ref | Why it goes |
|---|---|---|
| Aggregate review substeps | P1.14, P2.5, P3.3, P4.2 | Each task's own RC substep already reviews it. A second pass over the same diff is duplicate spend. |
| Zero-spend proof | P5.2 | Phases 0–6 bill nothing because every client is a stub. A test proving it is a proof of a property nothing threatens. |
| Test matrices | P2.4, P3.1 et al | Re-running one assertion across `probe_batch_size ∈ {1,7,40}` tests the same line three times. Keep **one** case per behaviour. |
| `review.py`'s full clearance CLI | P4.1 | A terminal UI over probed records. For ~30 records the orchestrator reads the JSON. Slim to a formatter, or skip. |

**KEPT, and not negotiable even at speed** — these are not edge cases, they are the demo:
- **The budget reserve/settle lifecycle.** It is what stands between Phase 7 and an unbounded bill
  on the user's own key. Speed is not a reason to spend their money wrong.
- **The confidence-range discard (D-range / P2.2).** Clamping `5.0` to `1.0` clears the 0.7 floor
  and admits records on garbage — it corrupts the dataset the demo is *made of*.
- **The leak test (`test_task_instance_excludes_leaked_fields`).** If record content reaches the
  baseline prompt, the baseline is not a baseline and the whole side-by-side is a lie.
- **All of Phase 6.** The Mastra template *is* the artifact being demoed.
- **The P8.0 yield gate.** The user asked to be stopped if too few records clear. That stands.

**The test for what else to cut:** does it protect the *demo's claim* or the *user's money*? Keep
it. Does it protect against a hypothetical that a walkthrough would surface anyway? Cut it.

**Reporting cadence also changes:** phase boundaries only, per the same instruction. Per-finding
narration was its own tax on the user.

## D22 — `probe_log` stays, `--replay` is CUT. RULED. *(added 2026-07-17)*

**The gap (found in P2.4):** §3 rests its determinism/reproducibility claim on
`data/scratch/probe_log/` and a `--replay` flag. **Neither has an owning plan task** — `grep
probe_log` over the plan returns nothing. Nothing creates them, so §15's determinism guarantee is
currently claimed but not built.

**Ruling — split them, because they are not the same bet:**

- **`probe_log/` STAYS.** It is a **write-only append** of each probe's raw request/response, and it
  is cheap insurance on the one phase that spends the user's own money. Phase 7 bills ~$17 against
  their real key; if it dies at record 380 of 400 with no transcript, the only recovery is to pay
  again. A log costs nothing to write and is the difference between one paid run and two. It also
  carries the evidence the HTML report needs to show *what the baseline actually said* — which is
  the demo's whole claim. **Owner: P5** (`run_prep.py`), where the run loop lives.
- **`--replay` is CUT.** Re-running curation from a log is a convenience for a pipeline that runs
  many times. This one runs **once**, at Phase 7. Building a replay harness to avoid a rerun we do
  not expect to need is exactly the speculative hardening D21 cuts.

**Consequence, stated plainly rather than papered over:** with `--replay` gone, §15's *"the run is
reproducible"* is **false as written** and must not be claimed in the README or the report. What is
true, and sufficient, is the weaker claim: **the run is auditable** — every probe's inputs and
outputs are on disk and can be read. Do not restate the stronger claim anywhere. A guarantee nobody
built is worse than no guarantee, because a reader plans against it.

**Deferred, not resolved (all latent, none demo-blocking):**
- §3's `CurationResult(survivors, probed, ...)` positional form is a `TypeError` — a TypedDict takes
  keywords only. Three of four pinned call sites are wrong. Fix on contact; do not sweep.
- The URL cache's honest scope is **one record**, not the run (`probe_and_score_one`'s pinned
  signature has no cache seam). Recurring regulator URLs get re-resolved. **Costs latency, not
  correctness** — leave it.
- §1's dependency tables for `scoring.py` and `curate.py` both omit real imports (`urls`,
  `candidates`). The tables are wrong; the edges are downward and `test_imports.py` is green. The
  code is right — leave it.

## D23 — A zero-eligible arm is a WALKOVER, not a stalemate. RULED. *(added 2026-07-17)*

**The gap (found in P3.1, and it is a good one).** §7's sufficiency test is
`completed >= min(planned, trial_min)`, which for an arm that never ran reads `0 >= min(0, 10)` →
`0 >= 0` → **True**. The agent's diagnosis is exact and worth preserving verbatim:

> `mean_strength([]) == 0.0` is **the absence of a measurement wearing the costume of the worst
> possible score.**

So `planned {A:0, B:20}` lets B probe 20 records, find nothing, and **lose to an arm that probed
zero**. The agent's guard — `planned == 0` is never sufficient — is **correct and stands**.

**But the guard opens a hole §7 never contemplated,** which is what needs ruling. `planned {A:20,
B:0}` now stops with `insufficient_trial` while the budget is intact, the API is healthy, and 20
probes are already paid for. §7's only prescribed recovery is *"raise the ceiling and re-run"* —
and re-running **changes nothing**, because eligibility is a pure function of the corpus. The run
is deterministic; it will stop at the same place forever. This is reachable in practice: scenario B
requires a financial **and** a promotional term, and a corpus may simply never pair them.

**RULING — three parts:**

1. **A zero-eligible arm is a walkover, not a stalemate.** If exactly one arm has `planned == 0`
   **and the other met `scenario_trial_min` on its own merits**, the other arm **wins**, with
   `outcome="walkover"` and a reason naming the empty arm. This is honest: the scenario choice is
   **upstream** of the experiment, not part of it. Which scenario we demo is a staging decision;
   goal #9's anti-rigging constraint governs the baseline-vs-guarded comparison, which a walkover
   does not touch. What would be dishonest is a **silent** A-win — hence a distinct outcome value,
   not a fold into `"A"`.
2. **The walkover must never be reachable by a weak arm.** The `trial_min` bar is on the WINNER's
   own record count. An arm does not win by surviving; it wins by qualifying.
3. **`insufficient_trial` must diagnose which failure it is.** *"This arm never ran — widen
   eligibility or accept the walkover"* and *"this arm was truncated — raise the ceiling and
   re-run"* are different problems with **non-overlapping** fixes. §7 specifies only the second.
   Emitting it for the first sends the operator to re-run a deterministic dead end. **Owner: P5.1's
   `report_insufficient_trial`.**

**Implementation timing, per D21: DECIDED NOW, BUILT ON CONTACT.** If the Phase-7 trial pairs both
arms — the expected case — none of this fires and building it is speculative work. The ruling exists
so that *if* it fires, the answer is already settled and nobody improvises at the money step. P5.1
carries part 3 (a one-line message split, cheap); parts 1–2 land only if an arm actually comes up
empty.

## D24 — §9a's three unspecified operators, PINNED. RULED. *(added 2026-07-17)*

**The gap (found in P3.2).** §9a names `daysBetween`, `overlapCount` and `intersects` and **defines
none of them**, and no `narrowing_golden.json` case distinguishes the competing readings. This is
load-bearing: the golden is duplicated byte-for-byte across Python and TypeScript precisely because
goal #1 forbids importing across the language boundary, so **the fixture is the only thing keeping
the two ports in lockstep — and it cannot lock a semantic no case exercises.** A P6 implementer
re-deriving these would produce a TS port that passes the golden and disagrees with Python in the
field.

**RULING — all three of P3.2's chosen contracts are RATIFIED as specified. The TS port in P6 copies
them; it does not re-derive them.**

1. **`overlapCount` iterates the RECORD's tags against a SET of the firm's.** Direction is
   observable, not a style choice: `firm_profile_for_record` always duplicates `industry[0]` into
   `sector`, so iterating the firm's tags instead **double-counts that duplicate** and can flip
   top-5 membership.
2. **`daysBetween`'s delta is SIGNED.** A compliance date already in the past is **near** (weight 2),
   not far. `Math.abs` would rank an overdue obligation as if it were years away — the exact
   inversion of its real urgency. Past dates are routine here: §2's cutoff bounds the **publication**
   date, never the compliance date.
3. **An unparseable compliance date scores 1**, matching JS `NaN <= 180 === false`. Chosen because it
   makes the two ports agree **by construction** rather than by a fixture case, which is the only
   kind of agreement that survives an unwritten test.

**Why ratify rather than re-decide:** each reading is justified by an asymmetry in the data, not by
taste — and #2 and #3 both fail in the direction that would corrupt the demo's ranking silently. The
alternative to ratifying is adding golden cases, which means editing a shared byte-identical fixture
on both sides; that is real work for a property the docstring already pins, and D21 says do the
cheap thing. **If a golden case is ever added for these, it must land in both copies in the same
commit.**

## D25 — D21 over-cut: `review.py` STAYS. Correcting my own ruling. *(added 2026-07-17)*

**D21 listed `review.py`'s clearance CLI as ceremony and told the implementer to "slim to a
formatter, or skip". That was wrong, and it is my error, not the plan's.**

Reading Phase 4 properly: `review.py` is **the publication gate**. It owns `record_signoff` /
`record_rejection` and is the **only writer of `data/cleared/`**. Three things depend on it that
D21 did not weigh:

1. **The goal's hard constraint** — *never ship a record that has not been human-reviewed*. The
   user chose "hand-cleared public set" as the dataset decision at the outset. Cutting the CLI
   means either no sign-off at all, or sign-off that leaves no `human_review.attestation` in the
   record — i.e. a dataset that **claims** clearance it cannot evidence.
2. **§6's anti-padding table** names "waiving human review" as a rigging mode. D21 would have
   waived it for convenience — the exact motive the table anticipates.
3. **P5.1's `--review` branch dispatches to it.** Cutting it leaves the entrypoint's own pinned
   checkpoint with no implementation, which is the defect this project has found four times now.

**RULING: `review.py` is built as P4.1 specifies.** No batch-approve path, in code or config. It
remains the sole writer of `data/cleared/`.

**What D21's cut correctly reached, and still holds:** P4.2's *aggregate review pass* is still cut
(the per-task review covers it). The distinction I missed the first time is between **the gate**
and **a second look at the gate**. The gate is the goal; a second look at it is ceremony.

**The lesson, since this is the second time it has bitten:** "cut for speed" is a judgement about
*ceremony*, and ceremony is what protects against hypotheticals. A mechanism that enforces a **hard
constraint the user chose** is not ceremony however tedious it looks — thirty records is a small
enough set that reviewing them by hand is *cheap*, which is an argument for keeping the gate, not
against it. D21's own stated test ("does it protect the demo's claim or the user's money?") gives
the right answer here and I applied it carelessly: a dataset with no attestation **is** the demo's
claim.

**Also superseded from D22:** `--replay` is cut, so P5.1 implements **three** argv branches, not
§3's four: `--review`, `--emit-template-config`, `--verify-cleared`.

## D26 — Mastra's tripwire does NOT throw. §12's snippet reads dead properties. RULED. *(added 2026-07-17)*

**Three findings from P6.8, in descending order of how badly they would have hurt.**

### 1. §12's `normalizeDelivery` snippet reads properties that do not exist. 🔴

§12 pins `err.reason` and `err.metadata` off a thrown `TripWire`. On a real instance **both are
`undefined`**. The actual shape (verified against `@mastra/core@1.51.0` source):

| §12 says | Reality |
|---|---|
| `err.reason` | `err.message` |
| `err.metadata` | `err.options?.metadata` |
| `err.processorId` | ✅ correct — the only one |

**Copying the spec verbatim yields a block carrying no reason and no obligation ids** — which §10's
soundness check then rejects as *"unsound metadata"*, converting a **correct guardrail block into a
loud crash**. This is the project's signature defect once more, and in the worst possible place: the
mechanism the entire demo exists to show. The implementation reads the real shape; a mutation test
pins it.

### 2. My own brief's premise was inverted, and the agent tested it rather than believing me. 🔴

I told the agent: *"Mastra's `abort()` in an output processor surfaces as a thrown error, not a
return value."* **That is wrong.** The agent read the source and then **drove a real Agent with a
real output processor calling the real `abort()`**, finding:

- `abort()` throws `TripWire` internally and `runOutputProcessors` re-throws — **but Mastra's stream
  machinery catches it and converts it to state.**
- `agent.generate()` **returns normally**, with `result.tripwire = {reason, retry?, metadata?,
  processorId?}`, `result.error === undefined`, `finishReason: "other"`.
- A **genuine exception** *does* escape `generate()`, wrapped as a `MastraError`.

So the two cases are distinguished by **return shape vs throw** — nearly the opposite of what I
briefed. `goal.md`'s #8 "verified" note was right all along; my brief contradicted it and I did not
check. **Layer 2 (the throw path) is RATIFIED as kept** — it is defence for other call paths and
future versions, it costs nothing, and it is not dead code.

**This is the second time an agent has refused an orchestrator instruction on evidence and been
right** (the first was `__init__.py`/P3.2). Both times the agent ran the thing instead of reasoning
about it. That is the behaviour every brief in this project asks for, and it is worth more than my
confidence.

### 3. `processorId` optionality — RATIFIED as built.

Mastra types `processorId?: string` on both tripwire forms; the spec's `TripwireOutcome` and both
callers require `string`. Every abort path in 1.51.0 passes `processor.id`, so it is unreachable in
practice but typed reachable. **The agent's call stands:** keep the spec's pinned `string` with a
documented `UNKNOWN_PROCESSOR_ID` fallback, rather than reshaping a type under two callers it does
not own. Correct instinct — a demo does not need a type refactor to close an unreachable branch.

### Consequent carve-out, stated so it is not quietly false

`isTripWireError` has **one** owner: `tripwireContainment.ts` (§8's table wrongly claims it for
`carverGuardrail.ts` too — the known F2 duplicate). The claim *"the only `catch` in the template is
inside `normalizeDelivery`"* must be stated as **"the only DELIVERY-containment `catch`"**:
`judge/contract.ts` holds a `catch {}` for a JSON-parse retry, which is a different concern and is
legitimate. An unqualified claim would be false, and a false claim about where errors are contained
is worse than no claim.

## D27 — §8's agent API doesn't compile; `sharedConfig` as specified is an import cycle. RULED. *(added 2026-07-17)*

**Three defects from P6.4–P6.6, every one found by COMPILING or RUNNING — none by reading.** That
is now the pattern for essentially every real defect in this project.

### 1. §8's `generate()` call does not compile against the pinned Mastra. 🔴 — implementation RATIFIED

§8 (and §4:1983) pin `agent.generate(prompt, { output: GuardrailVerdictSchema })`. Against the
pinned `@mastra/core@1.51.0` this is **`TS2769: 'output' does not exist in type…`**, confirmed by
execution. `output` survives only on the legacy `AgentGenerateOptions`. The real API is
`{ structuredOutput: { schema } }`. **The implementation is correct; the spec is wrong in two
places.** No judgement needed — it either compiles or it doesn't.

### 2. `sharedConfig.ts` + `baselineAgent.ts` as specified are a MANDATORY import cycle. 🔴

The three pins are jointly unsatisfiable:
- §7/P6.2 put the **generated** `SCENARIO_PERSONA_INSTRUCTIONS` in `baselineAgent.ts`;
- §8 puts `instructions: SCENARIO_PERSONA_INSTRUCTIONS` **inside `SHARED_AGENT_CONFIG`** in
  `sharedConfig.ts`;
- §8 has `baselineAgent` **spread that object**.

Any module reading the persona at eval time must evaluate *after* `baselineAgent.ts`'s body; any
module it imports evaluates *before*. **Both orders TDZ-`ReferenceError` at import.**

**Root cause worth naming: §1 has NO ROW for `sharedConfig.ts` at all** — it exists only in §8's
prose. It is the one module whose dependency direction the module table never checked, and it is
the one module with a cycle. That is not a coincidence; the table is the mechanism, and a module
outside it is unchecked by construction.

**RULING — the shipped resolution STANDS:** declare the object beside the constant it closes over
in `baselineAgent.ts`, and have `sharedConfig.ts` re-export it. Every consumer's import site, the
object's shape, and the one-object guarantee are **exactly as specified**; only which file holds
the `export const` differs. The alternative (regenerate the persona into `sharedConfig.ts`) is a
generator change plus a re-run to satisfy a file-location preference — D21 says do the cheap thing,
and the cheap thing here preserves every property that was actually specified.

### 3. §8's own lint test cannot pass as written — P6.10 must re-express it

`expect(await agent.getModel({ requestContext: ctx })).toBe(MODEL_ID)` fails: `getModel()` resolves
to a model **object** (`{ provider: "openai", modelId: "gpt-5.6-sol" }`), never the router string.
Verified by execution; it needs no key and makes no network call.

**RULING — assert the two arms resolve to the SAME model, not that one equals a string.** Compare
`baselineAgent`'s resolved model to `guardedAgent`'s (`.provider` and `.modelId`), and each to the
pinned id. The string-equality form tests a coincidence of representation; **the property the
experiment actually needs is that the two arms are the same model** — which is the whole basis of
the baseline-vs-guarded claim. Re-expressing it this way makes the test say what it was always
trying to say.

### Consequent — a fifth drift check, ACCEPTED

Nothing mechanically locks `JUDGE_SYSTEM_PROMPT` to `prep/prompts/judge_system.md`; P6.15 covers
only `MODEL_ID`, `MODEL_CUTOFF`, `JUDGE_CONFIDENCE_FLOOR`, `REASONING_EFFORT`. They are
byte-identical **today**. **Add the text-read check** — it is a file read and a string compare, and
it protects the fair-test property that curation and the runtime scoreboard ask the judge the same
question. Cheap, and it guards the demo's claim rather than a hypothetical. **Owner: P6.15.**

## D28 — The anti-rigging test was VACUOUS. Plus §9c/§10/RequestContext. RULED. *(added 2026-07-17)*

Five findings from P6.9/P6.10. Every one found by **running or compiling**. The first is the worst
defect this project has produced.

### 1. 🔴 `test_guarded_agent_has_no_processor_retries` CANNOT FAIL — and it guards the rigging control

`maxProcessorRetries` is **not a public field** on `Agent@1.51.0` — it is private, with no accessor.
The agent built two agents, one **with** `maxProcessorRetries: 1`, and **both read `undefined`**.
§8's assertion passes just as happily on the agent that has the retry.

**Why this is the worst one yet.** Processor retries are the single option that would make the
guarded arm a **materially stronger system** than the baseline — not "the same model with data",
but "the same model with data *and extra attempts*". That is goal #9's named rigging mode. The
spec put a test on it. **The test cannot fail.** So the one control standing between this demo and
an unfair comparison was decorative, and it would have shipped to Mastra's own team reading as
proof.

**RULING: re-expressed as a SOURCE-TEXT check** — the project's existing drift-check pattern
(P6.15). If the runtime gives you no observable, assert on the source. **The test must be able to
fail; that is not negotiable for this one.** Verified by construction: the agent proved the runtime
form is unfalsifiable before replacing it.

### 2. 🔴 §9c's `return { messages }` does not compile. §8/§10/§11/§12's `new RequestContext({...})` does not compile.

- `processOutputResult` returns `MessageList | MastraDBMessage[]` — **the array itself**, not a
  wrapper. Mastra's own built-ins do this.
- `new RequestContext({ firmProfile })` is **TS2353**; the constructor takes an entry-tuple
  iterable. Worse, the *typed* `RequestContext<{firmProfile}>` is **not assignable** to the
  `RequestContext<unknown>` the Agent accessors take.

**The form that works at every boundary — P6.11 and P6.12 WILL hit this:**
```ts
new RequestContext<unknown>([["firmProfile", profile]])
```

### 3. Latent §9c ↔ §10 contradiction — LEFT ALONE, deliberately

§9c picks the display record by **max severity**; §10's `superRefine` requires
`violated_obligation_ids[0] === record.id`. These disagree whenever a lower-ranked violation
outranks a higher-ranked one on severity. **It is unreachable only because every `impact_label` is
`"high"`** — a candidate-filter criterion. *Uniform data is the only thing hiding it.*

**RULING: do not fix.** It cannot fire against this dataset, and the fix is a real redesign of which
record a block displays. **But it is written down here**, because "unreachable" rests entirely on a
filter that a future fork could loosen — and D21's speed mandate is a reason to defer work, never a
reason to leave a landmine unlabelled.

### 4. Enforcement-coverage seam — RATIFIED

§14 asks for medium/low enforcement coverage that the pinned types make untestable
(`impact_label` is `z.literal("high")`, cleared set module-scope-only). The optional `clearedSet`
constructor param stands. `new CarverGuardrail()` is unchanged, so no caller moves.

### 5. 🔴 DEMO-FACING — a correct block prints a red error and a stack trace

Mastra wraps output processors in a workflow, so `abort()` on the **success path** emits
`[WORKFLOW] Error executing step …` plus a stack to stderr. **The guardrail working correctly looks
like a crash.**

This is not cosmetic. The artifact's entire purpose is showing Mastra's team a guardrail doing its
job; a demo whose success path prints a red stack trace argues against itself, and no viewer reads
the code to find out otherwise. **RULING: P6.11/P6.14 must ensure the demo surface presents a block
as a BLOCK** — the HTML report and the Studio-visible workflow output must show it as the designed
outcome. Suppressing Mastra's own stderr is not required; **not letting it be the demo's headline
is.** Owner: P6.14 (report) and P6.11 (workflow shape).

## D29 — Correcting D28's RequestContext rule; the scoreboard row is MISLABELLED. RULED. *(added 2026-07-17)*

### 1. D28's RequestContext ruling was OVER-GENERALIZED. My error, corrected.

D28 said `new RequestContext<unknown>([["firmProfile", p]])` is *"the one form that works at every
boundary"*. **It isn't**, and P6.11 found out by compiling. `compareWorkflow` declares a
`requestContextSchema`, so `run.start()` **requires** `RequestContext<{firmProfile: FirmProfile}>`
and **rejects** the `<unknown>` form.

**Corrected rule — BOTH forms are needed, and which one depends on the boundary:**

| Boundary | Form |
|---|---|
| A schema-bearing workflow's `run.start()` | **typed** — `RequestContext<{firmProfile: FirmProfile}>` |
| Agent accessors, `runEvals` data items | **`<unknown>`** — `new RequestContext<unknown>([["firmProfile", p]])` |

What stands from D28 is the part that was actually verified: **`new RequestContext({ firmProfile })`
— the object-literal form pinned in §8, §10, §11 and §12 — does not compile anywhere** (TS2353; the
constructor takes an entry-tuple iterable). I generalized one agent's working form into a universal
rule without checking the other boundary. **Same failure I keep ruling against: a claim stated more
broadly than the evidence behind it.**

### 2. 🔴 The scoreboard's `stageB` row measures something OTHER than its label claims

`stageBScorer` **cannot produce `citation_fabricated`**. §4's algorithm needs `resolve_url`'s
tri-state; **the template has no URL resolver** (§2's resolver is prep-only, and §8's import row for
this module names none). The golden fixture supplies a per-case `url_cache`, so the port takes one —
but **at runtime that cache is empty**, so the row measures **wrong dates only**.

§12 labels that row **"Cited a fabricated/wrong source."**

**This is a demo-integrity defect, not a cosmetic one.** The scoreboard is the artifact Mastra's own
team reads. A row labelled "fabricated source" that silently measures only dates **overclaims what
the demo detected** — and it would overclaim in the exact direction that flatters us. Nobody reading
the scoreboard can tell.

**RULING: RELABEL the row to what it measures. Do not build a resolver.**

- The row becomes **"Cited a wrong compliance date"** (or equivalent language naming *dates only*).
- The README/report must not claim citation-fabrication detection on the template side.
- **Citation fabrication is still detected — in `prep/`, at curation time, where the resolver
  exists.** That is where the cleared set's `citation_fabricated` evidence comes from, and that
  claim remains true and is unaffected. The template's *runtime scoreboard* simply does not re-derive
  it.

**Why relabel rather than build:** a URL resolver in the template means live network calls inside
the demo, a new failure mode on stage, and a dependency §8 excludes — real work for a row we can
simply describe accurately. D21 says do the cheap thing; **honesty is the cheap thing here.** An
accurate narrow claim beats an impressive broad one that a careful reader can falsify — especially
with this audience.

### 3. Ratified without comment
§10's `reportStep` inputSchema (a step's `outputSchema` is a StandardSchema, not a ZodType — TS18046);
§12's `run.input.recordId` optionality; `printScoreboard` homed in `scorers.ts` (goal #14 requires a
printer that no Creates list owned); `CitationGroundTruth` (`ClearedRecord` has one resolved
citation, not §4's prep-side `reg_*` fields). All are compile-or-run facts, not judgement calls.

## D30 — P6.17's gate is RED on correct code. The residual overclaims. RULED. *(added 2026-07-17)*

### 1. 🔴 The phase gate tests a SUBSTRING where success criterion #9 is about IMPORTS

P6.17 pins the gate as `grep -rn "carver-showcase\|\.\./prep\|mastra_prep" template/src template/tests`
→ expect **no hits**. Run today, it **has hits** — and I verified every one is a **prose doc
comment** explaining the cross-language contract (`config.ts`, `schema.ts`, `narrowObligations.ts`,
`baselineAgent.ts`). **Not one is an import.**

**Why this is worse than a merely wrong test.** The gate is red on correct code, so the obvious way
to make it green is to **delete the comments** — the very comments that tell a reader which Python
function a TS port must stay in lockstep with. The gate would make the code *worse* while reporting
that a goal was met. SC#9 is about **dependencies**: the template must not import from `prep/` or
the showcase repo. A comment naming a file is not a dependency; it is documentation of one that
deliberately does not exist.

**RULING: the gate tests IMPORTS.** Grep import/`from`-clauses (or resolve the module graph) — not
free text. The property is *"no module in `template/` resolves anything from `prep/` or
`carver-showcase`"*, and that is exactly what must be asserted. **The doc comments stay.**

*(This is the same defect class as D28's vacuous test, inverted: there a check couldn't fail; here
it can't pass. Both come from asserting on a proxy instead of the property.)*

### 2. The last citation-fabrication overclaim — DESCRIPTION fixed, ID kept

D29 §2 relabelled the scoreboard **row**. The residual: `stageBScorer`'s `id`
(`citation-date-reproduces`) and `description` (*"fabricated citation or wrong date"*) still name
citation fabrication. Both are §12-pinned; no printed surface renders them.

**RULING — split them:**
- **The `description` is FIXED.** It is a **claim**, and it is false: that scorer cannot produce
  `citation_fabricated` (no URL resolver template-side, D29 §2). "Not rendered on a surface we
  currently print" is not a defence — **this artifact is a template Mastra's own team will read**,
  and source they are meant to learn from must not describe a thing it does not do. Mastra Studio
  may surface scorer descriptions in any case.
- **The `id` STAYS.** An id is an opaque handle, not a claim, and it is pinned; changing it risks
  the fixtures for no honesty gain.

### 3. Cosmetic, and worth one cheap fix

The generated Stage A prompt reads *"a AI-assisted decisioning feature"*. **Harmless to the
experiment** — both arms receive the identical string, so the comparison is unaffected. But it is
in a template being handed to Mastra as reference work. **Fix it in `prep/templates/prompts_ts_fragment.tmpl`
and regenerate** — never by hand-editing `prompts.ts`, which would be reverted by the Phase-8 re-run.

### Ratified without comment
`demo.ts` uses D29 §1's **typed** RequestContext form (§11's object-literal form is TS2353);
module-relative report output (§11's cwd-relative path is identical under `npm run demo` and correct
elsewhere).
