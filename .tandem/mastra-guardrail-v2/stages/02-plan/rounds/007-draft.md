# Plan: Carver × Mastra Compliance Guardrail (v1)

**Stage:** 02-plan **Round:** 4 (revision)
**Status:** Draft
**Implements:** `stages/01-spec/artifact.md` (6,002 lines) — **verbatim**. This plan introduces
no design decisions. Where it looked like it needed one, that is a **spec issue** callout, not a
divergence. Section references (§N) are to the spec unless stated.

**Round 2 closes eight issues.** Three of them meant the plan **would not have run as written**,
which is the useful summary: a plan is executable or it is prose.

| # | Round-1 issue | Fix |
|---|---|---|
| 1 | **Two violations of the zero-billed / one-late-run contract.** P6.11 made a live call inside a phase labelled zero-billed; a *paid* tiny-cap prep run (then `R7.2`, now **deleted**) was scheduled before the real one. Worse, that dry run set `scenario_trial_size: 2` against the shipped `scenario_trial_min: 10` validation — **it would have raised at `load_settings()` and never run at all** | Live spike → **R7.0**, Phase 7's preflight (first billed call, before any corpus spend, stop-on-propagation kept). Paid dry run **deleted** — shakeout is stubs/synthetic only. Phase map, Bills lines, zero-spend proof, stress table, preconditions and cost text all updated together |
| 2 | **Phase 6's order contradicted the TS DAG**: `callJudge` built before `judgeAgent` (it imports it); `guardedAgent` built before `CarverGuardrail` (it imports it) | Reordered to the real chain: contract → baseline+judge agents → callJudge → narrowing → containment → **CarverGuardrail → guardedAgent** → workflows → evals. New **P6.9** splits `guardedAgent` out of P6.4. Tests moved to the first task where their imports exist |
| 3 | **A hand-written stand-in `scenario/prompts.ts`** — violating §8's generated-only contract — plus `.skip`ped tests until P8.2 | The **real** generator runs against synthetic data (now **P6.2**), emitting all four fragments mechanically. **Every skip deleted.** P8.2 reruns the same generator on real data. One generator, two inputs, nothing hand-written |
| 4 | **False parallelism**: "P6 INDEPENDENT of P1–P5" (the generator task needs P3.2); "all P1 leaves independent" (P1.1's cutoff test calls P1.4) | Graph and table rewritten with the **joins named**: the generator task→P3.2, P1.4→P1.1, P1.9→both tracks, and the drift-check task writing into `prep/`'s tests |
| 5 | **The Python commands did not run.** `prep/.venv/bin/python` "from `prep/`" resolves to `prep/prep/…` | One form everywhere: **`cd prep && .venv/bin/python …`**, applied to every gate, real-run, review, generation and DoD command |
| 6 | **The review cadence was weakened** — "after each Python change" reinterpreted as once per phase | An **RC** substep on every Python task (review this task's diff → python-expert fixes → re-verify → commit). Phase gates are now an *additional* aggregate pass |
| 7 | **The DoD expanded a CLI contract the spec excludes** — `--verify-cleared` "re-resolves each citation" is a post-clearing crawler §14 puts out of scope, quoted two lines from the exclusion itself | Criterion 8 now proves from §2's clearing-time gate + the reviewer's pick from `resolving_urls` + structural validation. `--verify-cleared`'s contract pinned at its definition: **no network calls** |
| 8 | **The work branch was created after four tasks of edits** | **P0.0** — branch first, before any file exists. P0.5 is now the first commit |

Issues 1, 2 and 5 are the same defect the spec stage hit eight times, in a new costume: **each
half of a contradiction read correctly on its own.** "Run from `prep/`" and
`prep/.venv/bin/python` are each fine; together they are a path that does not exist. That is why
this plan pins **one** command form, and why the `Also update` field exists at all.

**Round 3 closes four issues, and two of them are this plan's own thesis used against it.**

Round 2 renumbered Phase 6's headings to fix the DAG order — and left eight **restatements**
pointing at the old numbers: `P6.8` claiming to depend on "P6.3 (`runJudge`)" when `runJudge` had
become P6.5; `R7.0` naming a phase gate two IDs stale; four stress-scenario rows assigned to
tasks that had moved. That is **exactly** the defect the `Also update` field exists to prevent,
committed in the round that introduced the field. It is worth stating rather than quietly fixing:
the discipline is not self-executing, and *renumbering* is precisely the kind of change whose
restatements are invisible — every stale line still named a real task, just the wrong one.

| # | Round-2 issue | Fix |
|---|---|---|
| 1 | **The generator task was ordered before the fixture it reads**, and invented `run_prep.py --emit-template-config --synthetic` — **a CLI branch the approved spec does not have**, added in the same round that criticised the `--verify-cleared` crawler for exactly that | **P6.1** (fixtures) now precedes **P6.2** (generate). `run_prep.py` is **unmodified**: P6.2 calls `emit_template_config(...)` directly with the project-local interpreter, over **two committed fixtures** — a 6-record synthetic cleared set and a **fully specified** `ScenarioDecision` (every field literal; the earlier "plausible strengths/counts" was a TBD wearing an adjective). P8.2 keeps the approved `run_prep.py --emit-template-config` path on real data |
| 2 | **The renumbering left eight stale references** — dependencies, the R7.0 gate, four stress rows, the drift-check target | Every `P6.x` reference swept and re-pointed. A **mechanical check** now backs it: each referenced ID must resolve to a real heading (§0), and it is run at the end of every round rather than trusted |
| 3 | **Phase 1's heading still claimed "Parallelizable: all ten modules"** while §2 correctly listed the two joins — a contradictory summary at the boundary a subagent reads first | Heading now names the independent subset and both joins (`P1.4 → P1.1`, `P1.9 → P1.10`) |
| 4 | **`--review` was invoked by R7.4 but implemented by no task** — the plan's own blocking human checkpoint had no code behind it | **P5.1** now creates all four approved argv branches, with `--review`'s dispatch contract and three tests (dispatches to `review.py`; makes **no** API calls; is the only writer of `data/cleared/`) |

**Round 4 closes two, and both are the round-3 fixes not going far enough.**

| # | Round-3 issue | Fix |
|---|---|---|
| 1 | **Track B still claimed independence its own join disproves** — the table said it was independent of "`prep/` **implementation**" and could "start at P0", while **P6.2 is second in that strict chain** and runs `prep/`'s generator. Round 3 fixed the *sentence* ("P6 INDEPENDENT of P1–P5") and left the *table row* making a narrower version of the same false claim | Track B **split into B1/B2**, in the table **and** the graph: **B1** (P6.1's synthetic fixtures + P0.4's build config) is genuinely early and consumes nothing from `prep/`; **B2** (P6.2 → P6.17, i.e. *everything else*) is **BLOCKED on P3.2**. The track as a whole is not independent and cannot start at P0 |
| 2 | **Two IDs survived the renumbering** — "P6.14 edits `prep/tests/test_config.py`" (drift is **P6.15**) and criterion 8's README "(P6.15)" (README is **P6.16**) | Both corrected; a full `P6.13`–`P6.17` sweep run against the authoritative headings |

**Why my own reference check missed issue 2, stated plainly.** Round 3 added a mechanical check
after this exact defect bit twice — and it tested the wrong property. It asked *"does every
referenced ID resolve to a real heading?"* Both `P6.14` and `P6.15` **resolve**. They are real
tasks. They are simply not the tasks those sentences name. I had written, one round earlier, the
precise diagnosis — *"every stale line still named a real task, just the wrong one, which is why
nothing looked broken"* — and then built a checker that could not distinguish those two cases.

The property that actually needs checking is *"does this reference denote the task it claims?"*,
which is semantic and does not reduce to a grep. So the honest control is not a cleverer regex:
it is that **a renumbering is never a mechanical edit** — every reference must be re-read against
the new headings, by hand, in the same task. That is now what §0's `Also update` field requires
for any change to a task ID, and it is why this round's sweep was a manual read of all seventeen
Phase-6 references rather than a script.

**Refinement 1 (round 5) closes nine items. The first is the plan telling itself a comfortable
lie.**

| # | Refinement item | Fix |
|---|---|---|
| **G1** | **Phase 6's gate was hollow for the two biggest test files, and the plan claimed otherwise.** `test:unit` excludes `evals.test.ts` and `comparisonWorkflow.test.ts` **at file level** (spec:3936), so "ends green when `npm run test:unit` passes" covered neither, and "the negative battery … runs now" / "`evals.test.ts`'s non-billing cases" were **false**. `evals.test.ts`'s partition/ledger logic would first execute at **Phase 9, ~609 calls / ~$23 an iteration** — a bug in free, deterministic code discoverable only after real spend, which is exactly what Fact 1 exists to prevent | Verified first that billing lives **inside** `test()` bodies (spec:5534) and not at module top-level, so a name filter can reach the free cases. Phase 6, P6.17 and P5.2 now run `npx vitest run tests/evals.test.ts tests/comparisonWorkflow.test.ts -t 'unit:'`. The selector is a **`describe("unit: …")` wrapper**, not a renamed test — the spec pins three literal `test()` strings in `evals.test.ts`, and renaming them would be a silent edit of an approved, refine-capped spec. **Allowlist, so it fails closed.** All three false sentences corrected |
| **G2** | **The `<20`-survivor gate was a paragraph.** R7.4's human review is backed by code; **R7.5 had no analogue** — nothing in P8.1 (a `cp`) or P8.2 read the count, so an agent narrating the checklist could vendor a single-digit set with nothing stopping it | **P8.0**, a new blocking task before P8.1, whose Verify is a command that **exits 3** below the threshold. Past it only via a **recorded** human decision (`data/results/yield-decision.md`); no flag, env var or config key silences it. Goal #11 still governs the response: ship smaller, report honestly, never pad |
| **G3** | **P6.2 writes into files P6.3/P6.5 later "Create"** — a naive whole-file `Write` destroys the generated line | Explicit generated-vs-hand-authored table in **P6.2**, with ⚠ pointers from P6.3 and P6.5. Reading derived from the spec (§5's own listing of `config.ts` contains the hand-authored constants **and** says generation writes a *line* into that file), not chosen by this plan. **Plus a spec issue:** §7 step 8 never says what a **re-run** does — and **P8.2 re-runs the generator** over files Phase 6 has since filled in. One reading silently deletes every hand-authored export one step before ship. P3.2 now implements idempotent replacement and `test_emit_is_idempotent` proves it |
| **G4** | `Verify` mandatory by §0 but **missing from ~25 tasks**, whose **RC** step 3 says "re-run the task's own Verify" | §0 now states the **default** command for `prep/`/`template/` tasks, defines "green" (**`0 passed` is red**), and names every deviation exhaustively |
| **G5** | **P6.12 bundled two spec modules**, ~20 symbols, ~900 spec lines behind a flat test list | Split into **P6.12a** (`deliveryWorkflow.ts`) / **P6.12b** (`scorers.ts`) along the module boundary §1's table already draws. **Suffixes, not a renumber** — renumbering Phase 6 has caused two defect rounds here, and the round-4 checker built to catch it tested the wrong property |
| **G6** | `__init__.py`'s pinned re-export block had **no owning task** | Assigned to **P3.2** (the only point where every re-exported module exists). `test_package_reexports` also asserts `probe`/`judge`/`scoring` stay **absent** — that omission is the circular-import fix, not an oversight |
| **G7** | `prep/tests/conftest.py` **created by no task** | Assigned to **P2.0**: fixtures only, classes stay in `stubs.py`. **Spec issue** — §1's tree gives both files the same description; the plan states its reading and flags it |
| **G8** | Three golden groups (`citation_date_cases`, `obligation_cases`, `stage_a_predicate_cases`) named in **no** task's tests-first list | Assigned: first two to **P6.12b**, third to **P6.3**. **And a hole the item only hinted at:** `evals/scorers.ts` owns `scoreCitation`/`scoreComplianceDate`/`scoreMissedObligation` (spec:4010) and **P6.12's Creates list named none of them** — the golden groups had targets no task built. Now listed |
| **G9** | Phases 3/4 carried no **Bills:**/**Ends green when**; P3.3/P4.2 no Verify | Both headers and both gates completed |

**Round 6 closes three, and all three are round 5's fixes stopping short of their own standard.**

| # | Round-5 issue | Fix |
|---|---|---|
| 1 | **P8.0 did not mechanically require the acknowledgment G2 demanded.** The command only counted records; `yield-decision.md` was **never read**. The prose then told the agent to *"re-run this task with the threshold the user authorised"* — asking a subagent to author a command, and letting **any** lowered literal pass, acknowledgment or not, matching this dataset or not. G2 asked for a mechanism; round 5 delivered a paragraph with a `sys.exit` in it | **One literal command, both paths.** `n >= 20` → exit 0. Otherwise it **reads** `data/results/yield-decision.md` and exits 0 only if the artifact records this exact dataset — `survivor_count` **and** a `set_digest` of the cleared set itself, `decision: PROCEED`, and a verbatim `user_instruction`. No second variant to invent; no flag, env var or config key; the literal `20` is fixed in the plan, never a per-run parameter. **Executed against fixtures** across six cases before being written down |
| 2 | **The `Verify` default claimed coverage it could not deliver.** The "exhaustive" list swept in tasks the default cannot describe: P6.1 owns no test module; **no `callJudge.test.ts` or `guardedAgent.test.ts` exists in the spec's 12-file tree**; P6.14 spans two files; and **P6.15 writes Python**, where the template default names a real *other* file that passes and proves nothing | Literal `Verify` on every one of them, all moved into the deviations table; the default now applies **only** where substituting the module name yields the real command, and the tasks it covers are listed by ID. **P6.15 now carries RC** — it changes a Python test file and was falling through §0's "template tasks have no RC" carve-out on the accident of which phase it sits in |
| 3 | **P6.12a asserted a false dependency on P6.10 (`guardedAgent`).** §8 is explicit: `evals/deliveryWorkflow.ts` does **not** import `agents/*` — `deliveryStep` resolves its agent via `mastra.getAgent(...)`. The claim also broke this plan's own rule that a dependency names the imported symbol: none could be named, because none is imported | Dependencies restated from §8's pinned import row (`normalizeDelivery`, `FirmProfileSchema`, `StageBResponseSchema`). Run-time agent resolution stated **separately as sequencing**, and it binds only the live path — this task's tests stub the agent |

**Round 7 closes two, and both are round 6's fixes inheriting a defect from the fix above them.**

| # | Round-6 issue | Fix |
|---|---|---|
| 1 | **The new shared-file contract was ordered backwards, and made P6.3 unrunnable.** §0 said `scorers.test.ts` is authored `P6.4 → P6.3 → P6.12b`, but **Phase 6 runs P6.3 before P6.4** — so the stated creator ran second and **P6.3's own `Verify` would have run against a file that did not exist**. P6.4 then contradicted itself in one task: "creates all four `describe` groups" (three of whose targets are tasks away — the exact import error the rule forbids) *and* "creates the file containing ONLY `judge_cases`" | Chain corrected to **P6.3 → P6.4 → P6.12b**, matching the phase's task order. **P6.3 creates** the file with only `stage_a_predicate_cases` + its imports, and pins the one-describe-per-group convention once; **P6.4 appends** only `judge_cases`; **P6.12b appends** `citation_date_cases` + `obligation_cases`. Every "P6.4 creates the file" / "all four groups" statement deleted. §0 now states the test that matters: **each task's `Verify` must pass at the point that task runs, from no pre-existing test file** |
| 2 | **P6.12b's dependency row overstated the module's contract import.** It claimed `evals/scorers.ts` imports `GuardrailVerdictSchema`, `parseAndValidateVerdicts` and `JudgeObligationInput` — but §8 routes parsing and schema enforcement **inside** `runJudge`, and spec:4195–4198 says so at the parallel call site verbatim: *"TYPE only — no runtime dependency … NOT imported … nor `GuardrailVerdictSchema`/`renderJudgeUserPrompt`/`parseAndValidateVerdicts` — all three moved inside `runJudge`"* | Row re-derived from the spec's scorer code: **`type JudgeResult` only** (`scoreMissedObligation` annotates it). `parseAndValidateVerdicts` is imported by **`scorers.test.ts`'s `judge_cases` block** — a *test* dependency, not a module import; the two are no longer conflated. The same correction applied to **P6.9**, which had the same overstatement |

**Fixing issue 2 surfaced a third unowned symbol, and this one is dangerous.** Re-deriving the row
meant asking where `asJudgeObligation` comes from — and **no §1 module row exports it**, though
`evals/scorers.ts` (spec:5108) and `processors/carverGuardrail.ts` (spec:4211) both call it. It
cannot simply go in `judge/contract.ts`, whose imports §1 pins as **"zod only"** while the adapter
takes a `ClearedRecord`. This is the third instance of one pattern this stage has now found in the
approved spec — `scoreCitation`'s owner (G8), `scenario/prompts.ts`'s missing import row, and now
this — and it is the worst of the three: the adapter **builds the judge's obligation input**, so
two drifting copies would feed the guarded arm and the eval subtly different questions **while
every test still passed**. Raised as a spec issue in P6.12b with the plan's pinned reading
(`contract.ts` owns it; `type ClearedRecord` is a type-only import adding no runtime edge), so the
two consumers cannot diverge while the orchestrator decides.

**Issue 2 of round 6 exposed a defect underneath the one reported.** Fixing the `Verify` table meant asking
what `-t 'judge_cases'` actually does on a shared test file, and the answer is that round 5 got it
backwards: `-t` filters *execution*, not *module loading*, so a file importing a not-yet-built
export fails to load and **no** filter rescues it. Round 5's "the bare file run is red until P6.12b
**by design**" was therefore wrong twice — it would have been an import error rather than a clean
red, and the redness was never necessary. §0 now pins the real rule: **shared test files are
authored incrementally, each task adding only its own `describe` and only its own imports** — under
which every file is green at every point. Three files are shared (`scorers.test.ts`,
`carverGuardrail.test.ts`, `evals.test.ts`), and all three now say who adds what.

**One item corrected me while I was writing the fix for it.** Drafting Phase 3's header I wrote
"Parallelizable: P3.1 and P3.2 are independent modules." Checking before claiming it —
`ScenarioDecision` is defined in `scenario_decision.py` (spec:2673) and `emit_template_config`
annotates `decision: "ScenarioDecision"`, so **P3.2 joins on P3.1**. The header now states the
join. This plan's own rule is *"a parallelism claim that is wrong is worse than none — a subagent
acts on it"*; it is worth recording that the rule caught its author in the act, one round after
G1 showed what an unverified convenience claim costs.

---

## 0. How to read this plan

**Task IDs are stable** (`P1.3`, `T6.2`) — dependency callouts and the parallelism map use them.
Every implementation task carries the same five fields, and none is optional:

| Field | Meaning |
|---|---|
| **Spec** | The section this task implements. If a task has no §, it is scaffolding. |
| **Creates** | Exact file paths and the exact function/class names, as spelled in the spec. |
| **Tests first** | The test file and the named cases to write **before** the implementation. |
| **Verify** | The literal command, and what output means "green". **Defaults — see below.** |
| **Also update** | **Every other place that states the same fact.** Non-negotiable — see below. |
| **RC** | The review/fix substep. Every **Python** task carries it. Defined once, immediately below. |

### The `Verify` default — so no task is left without a command

`Verify` is mandatory, and the **RC** substep's step 3 ("re-run the task's own `Verify` command")
presumes one exists. A task that states no `Verify` therefore has an unrunnable RC step — and a
subagent should never have to *infer* the command it is judged by. So the default is stated here
once rather than repeated on forty tasks:

> **Default `Verify`** — run the task's own test file, and nothing else:
> - **`prep/` task:** `cd prep && .venv/bin/python -m pytest tests/test_<module>.py -q`
> - **`template/` task:** `cd template && npx vitest run tests/<name>.test.ts`
>
> **Green** = exit status 0 with every named case in **Tests first** reported as passed — not
> skipped, not filtered out. A task whose `Verify` reports `0 passed` is **red**, however green
> the exit status: an empty selection is the failure mode this plan's own G1 fix exists to catch.

**The default applies ONLY where substituting the task's module name yields the real command** —
i.e. the module owns a test file of the same name. That is true for every `prep/` module task and
for the four template tasks whose module and test file agree. **Everywhere else the task states a
literal `Verify`**, and every such task is in the deviations table below. A subagent never infers.

| Task | Why the default does not apply | Its `Verify` |
|---|---|---|
| **P0.0–P0.5** | Scaffolding — no test file exists yet | stated on each task |
| **P6.1** | A **fixture** task: creates two JSON files, owns no test module | stated on the task |
| **P6.2** | Runs a **generator**, not a suite; proved by the files it wrote | stated on the task |
| **P6.3** | Owns **three** modules + one golden group in a shared file | stated on the task |
| **P6.4** | Its cases are one **group** inside the shared `scorers.test.ts` | stated on the task |
| **P6.5** | Its cases are part of the shared `carverGuardrail.test.ts` | stated on the task |
| **P6.6** | **No `callJudge.test.ts` exists** — the spec's tree has 12 test files and none is named for this module; its cases join `carverGuardrail.test.ts` | stated on the task |
| **P6.10** | **No `guardedAgent.test.ts` exists** — its cases live in `carverGuardrail.test.ts` | stated on the task |
| **P6.11, P6.12a, P6.12b** | Their files are **excluded from `test:unit` at file level**; they need the `-t 'unit:'` selector, never the bare file run | stated on each task |
| **P6.14** | Spans **`mastra.test.ts` and `evals.test.ts`** — two files, one task | stated on the task |
| **P6.15** | Writes **Python** (`prep/tests/test_config.py`); the template default is the wrong language *and* the wrong directory. **Carries the RC substep** | stated on the task |
| **P3.1–P3.3, P4.1–P4.2** | Stated explicitly (they precede this section in reading order) | stated on each task |
| **P6.17, P5.1–P5.2, P7.x, P8.x, P9.x** | Phase gates and live runs | stated on each task |

**Tasks that take the default**, exhaustively: `P1.2`–`P1.9`, `P1.12`, `P2.1`–`P2.4` (Python);
`P6.7` (`narrowObligations`), `P6.8` (`tripwireContainment`), `P6.9` (`carverGuardrail`), `P6.13`
(`prompts`), `P6.16` (`README`). For each, substituting the module name **is** the command.

### Shared test files are authored incrementally — imports included

Three files are written by more than one task, **each chain in the order the tasks actually run**:
**`scorers.test.ts`** (P6.3 → P6.4 → P6.12b), **`carverGuardrail.test.ts`** (P6.5 → P6.6 → P6.9 →
P6.10) and **`evals.test.ts`** (P6.12a → P6.12b → P6.14). The rule, which is not optional:

> **Each task adds its own `describe` block AND only the imports that block needs.** A task never
> writes a test for a symbol a later task creates, and never imports one.

**Why this is a correctness rule, not housekeeping.** `-t` filters which tests *execute*; it does
**not** stop Vitest loading the module. A file importing a not-yet-created export fails to load,
and **every** case in it errors — the filter cannot rescue it. So "write the whole file early and
filter" does not work, and an earlier draft of this plan said P6.4's bare file run would be "red
until P6.12b **by design**" — which was wrong twice over: it would have been an *import error*
rather than a clean red, and it is unnecessary, because a file containing only landed groups is
simply **green**. Each task's `-t '<group>'` filter therefore proves *that task's* cases
specifically; the bare file run is green at every point too.

> **The chain must match the phase's task order, and one earlier draft's did not.** It listed
> `scorers.test.ts` as `P6.4 → P6.3 → P6.12b` while Phase 6 runs **P6.3 before P6.4** — so the
> file's stated creator ran *second*, and **P6.3's own `Verify` would have executed against a file
> that did not exist yet.** The same draft had P6.4 both "creates the file with all four
> `describe` groups" (groups whose targets are three tasks away — the very import error this rule
> exists to prevent) *and* "creates the file containing ONLY `judge_cases`", in one task. **The
> ordering test that matters:** each task's stated `Verify` must pass **at the point that task
> runs**, starting from no pre-existing test file. Read the chain against the phase's task order
> — not the order the groups were convenient to describe in.

**Phase 6's gate (P6.17) is where every file must be green at once** — nothing ships on a filtered
pass.

### The `RC` substep — what "after each Python change" actually requires

The repo convention (`CLAUDE.md`) is: *"Run the Python Code Reviewer agent after each code change
and have the Python Expert fix any issues found."* An earlier draft of this plan acknowledged that
sentence and then substituted **one review per phase boundary** — a reinterpretation of "after
each" as "once per phase" that would let ten modules land before any of them is reviewed, which is
precisely the batching the convention exists to prevent. It is now a substep of every Python task,
and phase gates are an *additional* aggregate pass rather than the only one:

> **RC (every `prep/` task):** after the task's tests are green and before the task closes —
> 1. Run the **python-code-reviewer** agent over **this task's diff** (not the whole tree).
> 2. Have the **python-expert** agent fix every finding.
> 3. Re-run the task's own `Verify` command; it must still be green.
> 4. Commit. One commit-sized Python change → one review → one fix pass → one commit.

Tasks below write **RC** rather than restating those four lines twenty times. A `prep/` task
without **RC** is incomplete. (`template/` tasks have no RC substep — the convention names the
*Python* reviewer/expert pair; TypeScript is guarded by `npm run typecheck` + Vitest.)

### The "Also update" field exists because of one specific defect

The spec stage took 13 rounds, and the **single most recurring defect** — three times in the
spec alone, plus five more across its refinement cycles — was *fixing the authoritative site and
missing its restatements*: stale `{ compareWorkflow }` constructors surviving a registration fix;
§15's "Cost guarantees" still quoting a superseded call count; `isTripWireError` left owned by two
modules after its extraction. Each was individually trivial and collectively poisonous, because
**every fragment read correctly on its own.**

So: **a task that changes a figure, an owner, or an interface does not close until every
restatement of that fact is updated in the same task.** Where a fact is stated twice by
construction (a constant and its drift test; a fixture and both consumers), the task names both.
This is why several tasks below look over-specified in their "Also update" line — that line is the
one this project has proven it cannot leave to memory.

**A dependency claim must name a symbol.** The spec's final rounds established this rule and the
plan inherits it: when a task says module A depends on module B, it says *which symbol* — because
`(module)` alone is unfalsifiable, while `(module, symbol)` dies to a grep the moment it stops
being true.

---

## 1. The three sequencing facts, and what they buy

**Fact 1 — the real probe run is the only expensive, irreversible step.** Phases 0–6 make
**zero billed calls**. Everything is proven against stub clients and synthetic fixtures. The money
is spent **once**, in Phase 7, when every consumer of the data it produces is already green.

**Fact 2 — `template/` does not wait for real data.** It vendors `src/data/cleared-set.json`, but
every module can be built against a **synthetic fixture** conforming to the same
`ClearedRecordSchema`. So `template/` is built in Phase 6, *before* the real run. This is the
plan's most important ordering choice and it is worth being explicit about why: it means the
expensive step is paid against a **proven consumer**. If the template were built after the run and
turned out to need a schema change, the money would be spent twice. `schema.test.ts` (Zod-parsing
the vendored file) is what makes the eventual swap safe — it is the mechanism, not a hope.

**Fact 3 — two human checkpoints block, and neither can be automated.**
- **Human review** (§6) — the clearance gate. Manual, blocking, no batch-approve path exists in
  code or config, by design (§6's anti-padding row).
- **The <20-survivor escalation gate** (Phase 7, task `R7.5`) — a **hard stop** that reports to
  the user. It is the one condition the user asked to be woken for. It is a named step with its
  own ID, not a footnote.

---

## 2. Phase map, dependencies, and what can run in parallel

```
P0.0 branch ─► P0 scaffolding ──┬────────────────────────────────────────────┐
                                │                                            │
                                ├─ P1  prep LEAF                             ├─ B1 (early, truly
                                │    P1.0 test_imports (first — DAG guard)   │   independent):
                                │    P1.2 logging_ · P1.3 reader             │   P6.1 synthetic
                                │    P1.5 extract · P1.6 urls                │   fixtures +
                                │    P1.7 sampling · P1.8 scenarios          │   P0.4 build config
                                │    P1.11 budget · P1.12 openai_client      │        │
                                │    P1.13 prompts/*.md                      │        │
                                │    P1.4 candidates ─► P1.1 config          │        │
                                │      (JOIN: load_settings calls            │        │
                                │       assert_cutoff_margin)                │        │
                                │    P1.9 schema + GOLDEN FIXTURES ─► P1.10  │        │
                                │            │            │                  │        │
                                ▼            │            └─ (C blocks BOTH tracks' consumers)
                          P2  prep L1–L2 (probe judge scoring curate)        │        │
                                │            │                              │        │
                                ▼            │                              │        │
                          P3  prep L3 (scenario_decision, generate_template_config)   │
                                │            │                              │        │
                                │       P3.2 ├──────────────── JOIN ────────┼────────┤
                                ▼            │                              │        ▼
                          P4  review.py      │                     B2 (BLOCKED until P3.2):
                                │            │                       P6.2 GENERATE the 4 fragments
                                ▼            │                       → P6.3 schema/config/firmProfile
                          P5  run_prep.py    │                       → P6.4 judge/contract
                             (stubbed E2E)   │                       → P6.5 sharedConfig+baseline+judge
                                │            │                       → P6.6 callJudge → P6.7 narrowing
                                │            │                       → P6.8 containment
                                │            │                       → P6.9 CarverGuardrail
                                │            │                       → P6.10 guardedAgent
                                │            │                       → P6.11 workflows
                                │            │                       → P6.12a deliveryWorkflow
                                │            │                       → P6.12b scorers + scoreboard
                                │            │                       → P6.13 prompts.test
                                │            │                       → P6.14 report/mastra/scripts
                                │            │                       → P6.15 drift (writes into prep/!)
                                │            │                       → P6.16 README → P6.17 gate
                                │                                             │
                       P5 ∧ P6.17 ───────────────────────────────────────────▼
                                  P7  R7.0 live preflight (~$0.01) → R7.3 THE REAL RUN (~$17)
                                      → R7.4 human review → R7.5 escalation gate
                                             │
                                  P8  vendor real set → rerun the SAME generator on real data
                                             │
                                  P9  the 9 success criteria
```

**Parallel tracks — and their joins, stated honestly.** Earlier drafts twice claimed independence
the plan's own text disproved: first "P6 INDEPENDENT of P1–P5", then — after that was flagged — a
track B still described as independent of "`prep/` **implementation**" whose *second task* runs
`prep/`'s generator. **Both were false**, and rubric 13 rejects exactly that: P6.2 runs
`emit_template_config`; P1.1's cutoff test calls P1.4's function; P6.15 edits
`prep/tests/test_config.py`.

The honest split is **B1 / B2** below. Only the synthetic fixtures and build config are genuinely
early; **everything downstream of the generator waits on P3.2.** A parallelism claim that is wrong
is worse than none — a subagent acts on it, and the cost is discovering at P6.3 that the constants
it imports do not exist yet.

| Track | Tasks | Independent of | **Joins (hard ordering)** |
|---|---|---|---|
| **A — `prep/`** | P1 → P2 → P3 → P4 → P5 | — | Sequential within itself: the spec's DAG (§1) is a strict `LEAF → L1 → L2 → L3 → L4` |
| **B1 — synthetic fixtures + build config** | **P6.1** (and P0.4's `package.json`/`tsconfig.json`) | `prep/` entirely | **Can start at P0.** Pure data + config; consumes nothing from `prep/` |
| **B2 — everything else in `template/`** | **P6.2 → … → P6.17** | *nothing* | **BLOCKED on P3.2.** P6.2 (the generator) is **second in a strict chain**, and every module after it consumes its output (`DEMO_TRIGGER_RECORD_ID`, `DEMO_FIRM_PROFILE`, `SCENARIO_PERSONA_INSTRUCTIONS`, `scenario/prompts.ts`). So the template track as a whole is **not** independent of `prep/` implementation, and its work **cannot** start at P0 |
| **C — golden fixtures** | P1.9 → P1.10 | — | **Blocks** `test_scoring.py`/`test_judge.py` (A) **and** `scorers.test.ts`/`narrowObligations.test.ts` (B). Both consumers join on it |
| **D — drift checks** | P6.15 | — | Needs **both** `prep/`'s constants (P1.11) **and** `template/src/config.ts` (P6.3). It **writes into `prep/tests/test_config.py`** — so it is *not* a pure track-B task |

**Within P1** — mutually independent, safe for parallel subagents: `P1.0`, `P1.2`, `P1.3`, `P1.5`,
`P1.6`, `P1.7`, `P1.8`, `P1.11`, `P1.12`, `P1.13`. **Two are not:**
- **`P1.4` → `P1.1`.** `load_settings()` calls `assert_cutoff_margin()`, so `candidates.py` must
  exist before `config.py`'s cutoff validation test can pass. (An earlier draft listed both as
  independent leaves *and* noted the call in P1.4's own text — the claim and its counter-example
  one page apart.)
- **`P1.9` → `P1.10`.** The parity test needs the fixtures it compares.

**Within P6**, the module DAG (§8) dictates a strict chain, and two orderings an earlier draft got
backwards are worth naming because they are the kind that "look fine":
`judge/contract → judgeAgent → callJudge` (**callJudge imports judgeAgent** — building it first is a
module importing a file that does not exist), and
`CarverGuardrail → guardedAgent` (**guardedAgent imports the processor** — same shape).

**False parallelism to avoid** — these look independent and are not:
- P2's `curate.py` and P1's `budget.py`: `curate` imports `SpendBudget`. The whole point of
  `budget.py` being a leaf (§1) is that `probe`/`judge`/`curate` depend on it one-way; it must
  exist first.
- P6's `evals/scorers.ts` and `evals/deliveryWorkflow.ts`: scorers import the workflow's schemas.
- P8's two halves: the template constants are generated *from* the cleared set; vendoring lands
  first.

# PHASE 0 — Scaffolding

**Bills: nothing.** Ends green when `pytest` and `vitest` both run and collect zero tests without
import errors.

### P0.0 — Work branch **(preflight — before any file is created)**
- **Spec:** goal hard constraints
- **Do:** `git status` — confirm a clean tree and note the current branch. Then
  `git checkout -b feat-mastra-guardrail`.
- **Verify:** `git rev-parse --abbrev-ref HEAD` prints `feat-mastra-guardrail`.
- **Why this is P0.0 and not P0.5:** every task after this one **creates or edits tracked files** —
  the project skeleton, the root README's Projects table, `requirements*.txt`, `package.json`,
  `package-lock.json`. Branching afterwards means those edits land on whatever branch was checked
  out (likely `master`), which is exactly what "commit as you go **on a work branch**" exists to
  prevent. Branch first, then scaffold, then commit incrementally.
- **Standing constraint for every subsequent task: NEVER push.** No PR, no remote interaction of
  any kind — the user integrates via their own flux workflow.

### P0.1 — Project skeleton and the two `.gitignore` facts
- **Spec:** §1 (layout), goal hard constraints
- **Creates:** `projects/mastra-guardrail/` with the §1 tree's directories;
  `projects/mastra-guardrail/.gitignore` covering **at minimum** `node_modules/`, `.mastra/`,
  `data/scratch/`, `prep/.venv/`, `.env`; `data/cleared/` **tracked** (it is the deliverable), with
  a `.gitkeep` so the empty dir survives.
- **Verify:** `git check-ignore -v prep/.venv data/scratch node_modules` names the project-local
  file for each; `git check-ignore data/cleared` exits non-zero (**not** ignored).
- **Also update:** root `README.md`'s Projects table (a row for this project) — goal's repo
  conventions require it and it is easiest to add now, while the layout is fresh.

### P0.2 — The venv, pinned, project-local
- **Spec:** goal #13
- **Creates:** `prep/.venv` via `python3.10 -m venv .venv` run **from `prep/`**;
  `prep/requirements.txt` (`openai==1.76.0`, `httpx==0.28.1`, `PyYAML`, `python-dotenv` — pinned,
  no ranges); `prep/requirements-dev.txt` (`pytest`, plus `pytest-cov` if the sibling uses it).
- **Verify:** `cd prep && .venv/bin/python -c "import openai, httpx, yaml, dotenv; print('ok')"` prints
  `ok`. `cd prep && .venv/bin/python -c "import carver_showcase"` **fails** with `ModuleNotFoundError` —
  goal #13's isolation, proven rather than assumed.
- **Note — the ONE command form, used everywhere in this plan:**
  **`cd prep && .venv/bin/python …`**, invoked from the project root.
  An earlier draft wrote `prep/.venv/bin/python …` and said "run from `prep/`" — which, from
  `prep/`, resolves to `prep/prep/.venv/bin/python` and **does not exist**. The two halves of that
  instruction each read fine and contradicted each other: the same class of defect the spec stage
  hit eight times. Goal #13's requirement is satisfied either way (the interpreter is the
  project-local `prep/.venv`); what matters is that the written command **runs**. Every phase gate,
  real-run command, review/generation/verification command and DoD proof below uses this form and
  no other. No system Python, no sibling venv, ever.

### P0.3 — `config.yaml` and the `Settings` contract
- **Spec:** §13
- **Creates:** `prep/config.yaml` with **every** key §13's table lists, at its specified default:
  `model_router_string: openai/gpt-5.6-sol`, `annotations_path:
  ../../../../carver-showcase/data/annotations.jsonl` (**four** `../` — §13's I1 correction; three
  resolves inside this repo and fails on the first command), `candidate_cutoff_date: "2026-03-01"`,
  `sample_seed: 42`, `probe_batch_size: 40`, `target_set_size: 200`, `probe_max_records: 400`,
  `scenario_trial_size: 30`, `scenario_trial_min: 10`, `price_input_per_million_usd: 5.00`,
  `price_output_per_million_usd: 30.00`, `total_spend_ceiling_usd: 120.0`,
  `judge_confidence_floor: 0.7`, `dotenv_path: .env`, `cleared_dir: data/cleared`,
  `scratch_dir: data/scratch`.
- **Explicitly NOT keys** (§13, and each for a stated anti-padding reason): `reasoning_effort`,
  `snapshot_date`. Both are code constants. A task that adds either to `config.yaml` is wrong.
- **Creates:** `prep/.env.example` (`OPENAI_API_KEY=`), `template/.env.example` (same). Both
  tracked; both real `.env` files gitignored.
- **Verify:** file exists; `P1.1` asserts `load_settings()` reads it.

### P0.4 — `template/` build config (goal #12's locked stack)
- **Spec:** §8's `package.json`/`tsconfig.json` blocks
- **Creates:** `template/package.json` — `"type": "module"`, `"engines": {"node": ">=22.13.0"}`,
  scripts `dev`/`demo`/`demo:prompt`/`typecheck`/`test`/`test:unit` exactly as §8 pins them (note
  `test` runs `npm run typecheck && vitest run`); deps `@mastra/core@1.51.0`, `zod@4.0.0`,
  `dotenv@16.4.7`; devDeps `mastra@1.51.0`, `typescript@5.7.3`, `tsx@4.19.2`, `vitest@2.1.8`,
  `@types/node@22.13.0`. All exact pins, no carets. `template/tsconfig.json` — `module: ES2022`,
  `moduleResolution: bundler`, `resolveJsonModule: true`, `strict: true`, `noEmit: true`.
  `template/vitest.config.ts`.
- **Why this is Phase 0 and not later:** goal #12 names CommonJS as a *specific Mastra-breaking
  failure mode*. Getting `"type": "module"` and `moduleResolution: bundler` wrong is not a lint
  issue; it breaks resolution at the first import, and it is cheapest to get right before any
  module exists.
- **Verify:** `cd template && npm install && npm run typecheck` — passes on an empty `src/`.

### P0.5 — First commit
- **Do:** commit the scaffolding (`git add` the project tree, the two `.gitignore`/`.env.example`
  pairs, `config.yaml`, `package.json`, `tsconfig.json`, the root README row). Meaningful message.
  **Never push.**
- **Note:** the branch itself was created in **P0.0**, before any of these files existed.

---

# PHASE 1 — `prep/` LEAF modules

**Bills: nothing** (no module here takes a client). **Parallelizable:** the independent subset
only — `P1.0`, `P1.2`, `P1.3`, `P1.5`, `P1.6`, `P1.7`, `P1.8`, `P1.11`, `P1.12`, `P1.13`.
**Two ordered joins: `P1.4` → `P1.1`** (`load_settings()` calls `assert_cutoff_margin()`) and
**`P1.9` → `P1.10`** (the parity test needs the fixtures). See §2's table — an earlier draft's
heading here claimed "all ten modules" while §2 correctly listed both joins, which is a
contradictory summary at exactly the boundary a subagent reads before picking up work.
Ends green when `cd prep && .venv/bin/python -m pytest tests/ -q` passes and `test_imports.py` proves
the DAG.

### P1.0 — `test_imports.py` FIRST (the cheap guard on the whole build)
- **Spec:** §1's DAG + §14
- **Tests first (this task IS the test):** `test_no_circular_imports` — walk every `mastra_prep`
  module with `ast`, extract intra-package imports **without executing them**, assert the graph is
  acyclic and that `budget.py`'s and `logging_.py`'s intra-package import sets are **empty**;
  `test_never_imports_carver_showcase` — the same walk asserts no module imports `carver_showcase`
  (goal #13); `test_no_stdlib_shadowing` — no module named `logging`/`json`/`types` (this is why
  `logging_.py` carries its underscore).
- **Why first:** it is ~30 lines, needs no implementation to exist, and it is the mechanical guard
  against the exact defect the spec stage found in the wild (`probe → curate → probe`). It costs
  nothing and it fails the instant someone reintroduces a cycle.
- **Verify:** `cd prep && .venv/bin/python -m pytest tests/test_imports.py -q` — passes trivially on an
  empty package, and keeps passing as P1–P5 land.

### P1.1 — `config.py`
- **Spec:** §13 | **Creates:** `mastra_prep/config.py` — `Settings` (dataclass),
  `load_settings(path="config.yaml") → Settings`
- **Tests first:** `test_config.py` — `load_settings()` raises `ValueError` for
  `judge_confidence_floor: 0.5` (below the 0.7 floor); for `price_input_per_million_usd` /
  `price_output_per_million_usd` below `PINNED_PRICE_*_USD_PER_MILLION`; for `target_set_size: 201`
  (>200, goal #11's ceiling); for `scenario_trial_min` outside `1..scenario_trial_size`;
  `candidate_cutoff_date` boundary (`2026-03-01` passes, `2026-02-28` raises — via
  `assert_cutoff_margin`, P1.4); **`test_settings_has_no_snapshot_date`** and
  **`…_no_reasoning_effort`** — an unknown key in `config.yaml` raises, proving neither can be
  reintroduced as a tunable.
- **Verify:** `cd prep && .venv/bin/python -m pytest tests/test_config.py -q`
- **Also update:** none yet — the two cross-language drift checks (`test_model_id_matches_template`,
  `…_model_cutoff…`, `…_judge_confidence_floor…`, `…_reasoning_effort…`) land in **P6.15**, when
  `template/src/config.ts` exists to read. Listed here so they are not forgotten: they belong to
  `test_config.py` but cannot run until P6.
- **RC** — see the substep definition above. Not optional.

### P1.2 — `logging_.py`
- **Spec:** §1, §3 | **Creates:** `log(message: str) → None`, `configure_logging()`
- **Tests first:** `test_logging.py` — `log()` emits at INFO; `configure_logging()` is idempotent.
- **Why it exists at all:** `log()` is used throughout `prep/` (§3's curation loop, §7's trial) and
  the spec's own review found it *defined nowhere*. A 400-record sweep that prints nothing for 20
  minutes is indistinguishable from a hang, so progress is visible **by default**.
- **RC** — see the substep definition above. Not optional.

### P1.3 — `reader.py`
- **Spec:** §2 | **Creates:** `stream_annotations(path) → Iterator[dict]`
- **Tests first:** `test_reader.py` — streams a 3-line fixture **without loading the whole file**
  (assert via generator-exhaustion, not a memory profiler); a malformed line is skipped + warned and
  the stream continues; a missing file raises `FileNotFoundError`.
- **Non-negotiable:** the real file is ~1.8 GB (goal). One JSON object per line, streamed. Never
  `json.load()` the file.
- **RC** — see the substep definition above. Not optional.

### P1.4 — `candidates.py`
- **Spec:** §2 | **Creates:** `ACTIONABLE_UPDATE_TYPES: frozenset[str]`, `SNAPSHOT_DATE`
  (code constant), `is_candidate(rec) → tuple[bool, list[str]]`, `filter_candidates(records) →
  Iterator[dict]`, **`assert_cutoff_margin(candidate_cutoff_date) → None`**
- **Tests first:** `test_candidates.py` — each predicate individually (cutoff boundary at exactly
  `2026-03-01` passes / `2026-02-28` fails; snapshot boundary `2026-07-11` passes / `2026-07-12`
  fails; **`test_snapshot_upper_bound_catches_rot_even_when_valid_flag_lies`** — a `2569-01-01`,
  `valid=True` fixture is rejected by the upper bound alone; each of the 8 actionable types passes
  and `"press release"` fails; `impact_label="medium"` fails; empty `key_requirements` fails);
  **`test_duplicate_ids_deduped`** (first occurrence wins — the sole dedup layer);
  **`test_cutoff_is_derived_from_model`** — with the shipped constants the floor is **exactly
  `2026-03-01`**, and setting `MODEL_CUTOFF` later makes the unchanged cutoff **raise**, naming the
  re-derivation goal #3 requires.
- **Also update:** none — but note `assert_cutoff_margin` is *called by* `load_settings()` (P1.1),
  so P1.1's cutoff test depends on this task. Build P1.4 before P1.1's cutoff case, or stub it.
- **RC** — see the substep definition above. Not optional.

### P1.5 — `extract.py`
- **Spec:** §2 | **Creates:** `FIELD_MAP: dict[str,str]`, `extract_record(raw) → dict|None`
- **Tests first:** `test_extract.py` — every `FIELD_MAP` dotted path resolves against the real
  sample-record fixture; a missing nested path yields `None`, **not** `KeyError`; a missing `id`
  returns `None`.
- **Constraint:** `FIELD_MAP` is this project's **own** hand-derived copy. Never import
  `carver_showcase.schema` (goal #13; `test_imports.py` enforces it).
- **RC** — see the substep definition above. Not optional.

### P1.6 — `urls.py`
- **Spec:** §2's tri-state | **Creates:** `UrlStatus` (Literal), `extract_urls(text) → list[str]`,
  `resolve_url(url, cache: dict[str, UrlStatus], timeout=10.0) → UrlStatus`
- **Tests first:** `test_urls.py` — `extract_urls` against the real
  `reg_rules` prose-with-parenthetical-URL sample; **`resolve_url` returns the exact `UrlStatus`
  per case** against an httpx `MockTransport`: `200`/`301→200` → `"resolves"`; **`404`/`410` →
  `"not_found"`** (the only statuses that may ever become failure evidence); **`403`/`429`/`500`/
  `503`/timeout/DNS-error → `"unverifiable"`**; the HEAD→GET retry path; cache memoization.
- **Why the tri-state matters:** fail-closed is right for the ground-truth gate (it *drops* a
  record) and **inverts** on the baseline's citation (it *admits* one). A 403 from a regulator
  blocking datacenter IPs must never read as a fabricated citation.
- **RC** — see the substep definition above. Not optional.

### P1.7 — `sampling.py`
- **Spec:** §3 | **Creates:** `stratified_sample_sequence(rows, seed=42) → list[dict]`
- **Tests first:** `test_sampling.py` — determinism (same seed → identical sequence);
  proportionality; full-pool coverage (`len(sequence) == len(candidates)` — it returns the whole
  deterministic order; callers take prefixes).
- **RC** — see the substep definition above. Not optional.

### P1.8 — `scenarios.py`
- **Spec:** §7 | **Creates:** `SCENARIO_A`/`SCENARIO_B` (`ScenarioSpec`), `DOMAIN_BUCKETS`,
  `INDUSTRY_TAG_TO_BUCKET`, `NEGATIVE_CONTROL_TASKS`, `NEGATIVE_CONTROL_ARTIFACTS`,
  `build_task_instance(record, scenario) → dict`, `build_negative_control_prompts(scenario) →
  list[str]`, `is_eligible(record, scenario) → bool`, and the module-private
  `_keyword_eligible_a/_b`, `_jurisdiction_eligible_a`, `_jurisdiction_usable`,
  `_topical_signal_usable`
- **Tests first:** `test_scenarios.py` + `test_scenario_decision.py`'s eligibility cases —
  `_tag_matches_keyword` word-boundary behavior (`"ai"` matches `"Generative AI"`, not
  `"retail"`); a US-jurisdiction AI fixture is **False** for A, `country="DE"` **True**;
  **`test_marketing_alone_not_eligible_for_b`**; **`test_null_country_and_bloc_not_eligible_for_b`**;
  **`test_empty_topical_signal_not_eligible`**; **`test_negative_control_tasks_are_benign`** — none
  contains any scenario keyword; `build_negative_control_prompts` returns **exactly 30**
  (10 topics × 3 artifacts), deterministic and order-stable; `buckets_golden.json` parity.
- **Why `is_eligible` lives here and not in `scenario_decision.py`:** §1 is explicit — `scoring.py`
  imports it, and `scoring → scenario_decision → curate → scoring` would be a cycle. This is the
  homing decision that keeps the DAG acyclic; do not move it.
- **RC** — see the substep definition above. Not optional.

### P1.9 — `schema.py` + the golden fixtures **[parallel track C]**
- **Spec:** §5 | **Creates:** `BaselineFailure`/`ClearedRecord` (TypedDicts),
  `SCORE_OUTCOME_TO_FAILURE_MODE`, `STAGE_OF_MODE`, `to_json(record) → dict`,
  `validate_cleared_record(obj) → tuple[bool, list[str]]`,
  **`predicts_stage_a_violation(record) → bool`**
- **Also creates:** `prep/tests/fixtures/scoring_golden.json` with **four named groups** —
  `citation_date_cases`, `judge_cases` (incl. out-of-range `5.0`/`-0.2`/`NaN`), `obligation_cases`
  (incl. exactly one `prep_only: true` case — the `not_applicable` one the 3-arg TS port cannot
  reach), `stage_a_predicate_cases`; plus `narrowing_golden.json` and `buckets_golden.json`.
- **Tests first:** `test_schema.py` — `validate_cleared_record` rejects an `attestation` other than
  `"approved"`, an unlisted extra key, empty `baseline_failures`, a `BaselineFailure.stage`
  disagreeing with `STAGE_OF_MODE[mode]`; **`test_no_unreviewed_records_in_cleared_dir`**;
  **`test_predicts_stage_a_violation`** (citation-only → False; missed_obligation + all three
  confirmations → True; any one confirmation False/None → False).
- **Also update:** the fixtures are **byte-identical duplicates** across the seam. When this task
  creates them under `prep/tests/fixtures/`, it **also** copies them to
  `template/tests/fixtures/` and P1.10 asserts they match. Creating one without the other is the
  exact drift this mechanism exists to prevent.
- **RC** — see the substep definition above. Not optional.

### P1.10 — `test_fixture_parity.py`
- **Spec:** §12 | **Tests:** **`test_golden_fixtures_are_byte_identical`** — reads all three
  fixtures from both sides as **bytes** and asserts equality.
- **Why:** each side otherwise tests only its own copy; if one gains a case the other lacks, both
  suites stay green while the parity guarantee silently weakens. This is the one test that reads
  across the seam — and it reads **data**, never code, so goal #1 is untouched.
- **RC** — see the substep definition above. Not optional.

### P1.11 — `budget.py` (the leaf everything reserves against)
- **Spec:** §3 | **Creates:** `MODEL_MAX_CONTEXT_TOKENS`, `REQUEST_OVERHEAD_ALLOWANCE_TOKENS`,
  `PINNED_PRICE_INPUT_USD_PER_MILLION`, `PINNED_PRICE_OUTPUT_USD_PER_MILLION`, `REASONING_EFFORT`,
  `MODEL_CUTOFF`, `CUTOFF_MARGIN_DAYS`, `CUTOFF_MARGIN_IS_INCLUSIVE`, `UNBILLED_STATUS_CODES`,
  `build_request_payload(...)`, `estimate_tokens(text)`, `reservation_basis_tokens(payload)`,
  `SpendBudget` (`.reserve` → `Reservation`, `.max_call_cost`, `.assert_no_open_reservations`),
  `Reservation` (`.settle` / `.release` / `.finalize_unknown` / `.finalize_unusable_usage`),
  `terminal_for_exception(reservation, exc)`, `BudgetExhausted`, `BudgetPoisoned`
- **Tests first:** `test_budget.py` — **one test per row of §3's lifecycle table**, each asserting
  BOTH invariants (`spend_so_far_usd <= ceiling_usd` **and** `>= true billed`):
  `test_settle_books_actual_and_returns_headroom`;
  **`test_release_returns_the_full_hold`** (a 400-shaped exception via `terminal_for_exception`);
  **`test_finalize_unknown_keeps_the_full_hold`** (timeout-shaped);
  **`test_retry_does_not_double_count`** — the exact leak: a timeout then a successful retry leaves
  spend = retry's true cost **plus** the first attempt's provider-max hold, never two full holds;
  **`test_double_terminal_raises`**; **`test_assert_no_open_reservations`**;
  **`test_ceiling_holds_at_provider_maximum`**; **`test_settle_poisons_when_tight_estimate_is_beaten`**;
  the **unbookable-usage battery** (`settle(None)`, `{}`, one key missing, non-numeric, `True`
  (bool-is-int), negative, and **`test_usage_above_provider_cap_poisons`**) — each asserting the
  handle ends terminal, the hold is retained, `BudgetPoisoned` raises, and a second terminal op
  then raises; **`test_settle_failure_does_not_reach_terminal_for_exception`** (the `else`-block
  placement); **`test_tiny_ceiling_rejects_every_call`**;
  **`test_reservation_includes_overhead_allowance`**;
  `SpendBudget(price_in=0.001, …)` raises `ValueError`.
- **Verify:** `cd prep && .venv/bin/python -m pytest tests/test_budget.py -q`
- **Why this module is a leaf:** §1's DAG. `probe`/`judge`/`curate` all need `SpendBudget`; homing
  it in `curate.py` (an earlier spec draft did) created a real `probe → curate → probe` cycle.
  `test_imports.py` (P1.0) asserts its intra-package import set is **empty**.
- **RC** — see the substep definition above. Not optional.

### P1.12 — `openai_client.py`
- **Spec:** §3, §15 | **Creates:** `load_env(dotenv_path) → None`, `make_client() → openai.OpenAI`
- **Tests first:** missing `.env` logs a WARNING and proceeds (the key may be in the shell env);
  absent `OPENAI_API_KEY` raises `KeyError` with a clear message.
- **The only secret this project has is `OPENAI_API_KEY`** (goal #9). No Carver key, no Anthropic
  key, no Mastra token. This module is the only place a key is read.
- **RC** — see the substep definition above. Not optional.

### P1.13 — `prompts/*.md`  **[parallelizable]**
- **Spec:** §3, §4 | **Creates:** all six, with their exact placeholders:
  `stage_a_system.md` (`{{PERSONA}} {{COMPANY}} {{JURISDICTION_PHRASE}} {{DOMAIN_PHRASE}}
  {{TASK_VERB_PHRASE}}`), `stage_a_user.md` (`{{TASK_INSTANCE}}`), `stage_b_system.md`,
  `stage_b_user.md` (`{{FOLLOWUP_QUESTION}}`), `judge_system.md`, `judge_user.md`
  (`{{RECORD_SUMMARY}} {{DRAFT_TEXT}}` / `{{OBLIGATIONS_JSON}}`).
- **Fair-test discipline is the whole point:** §3's MAY/MUST-NOT list governs what a prompt may
  contain. `test_probe.py::test_task_instance_excludes_leaked_fields` (P2.1) is what enforces it.

### P1.14 — Phase-1 aggregate review
- **Do:** an **additional** `python-code-reviewer` pass over P1 as a whole — looking for
  cross-module issues no single-task review can see (duplicated helpers across leaves,
  inconsistent error types, a constant that drifted between two modules). **This is on top of**
  the per-task **RC** substep, never instead of it.

---

# PHASE 2 — `prep/` LEVEL 1–2 (stubbed clients, still zero billed calls)

**Bills: nothing.** Every call goes through a stub. Ends green when the full curation loop runs
end-to-end against canned responses.

### P2.0 — `tests/stubs.py` FIRST
- **Spec:** §14 | **Creates:** `StubOpenAIClient` (configurable canned response per call index),
  `RecordingStubClient` (captures kwargs; asserts **no `temperature`** param and the correct
  `reasoning_effort`/`max_completion_tokens`), `TruncatingStubClient` (`finish_reason="length"`).
- **Note:** the stub **classes** live in `tests/stubs.py`, importable — **not** `conftest.py` —
  avoiding the `tests/` package self-import trap documented in `docs/LESSONS.md`.
- **Also creates — `prep/tests/conftest.py`** (spec §1:304). It was created by no task. The spec's
  tree lists **both** files and attributes "StubOpenAIClient family" to `conftest.py` **and**
  "importable stub clients" to `stubs.py` — the same content, two owners. **This plan resolves it
  the way the spec's own stated reason points:** the classes live in `stubs.py` (that line gives
  the reason — the import trap), and `conftest.py` holds **only thin pytest fixtures wrapping
  them**, e.g. `@pytest.fixture def stub_client(): return StubOpenAIClient(...)`, plus any shared
  fixture the suite needs. **It defines no stub class of its own.** Two definitions of
  `StubOpenAIClient` — one importable, one fixture-injected — is precisely the "two
  implementations of one thing" defect this plan flags everywhere else; the difference is that
  here it would drift silently between test files.
  > **Spec issue (callout, not a divergence):** §1's tree gives `conftest.py` and `stubs.py`
  > overlapping descriptions. The plan reads them as *classes in `stubs.py`, fixtures in
  > `conftest.py`* because §1's own parenthetical justifies `stubs.py` on import-trap grounds,
  > which only makes sense if the classes are there. If the orchestrator intends `conftest.py` to
  > hold the classes, then `stubs.py`'s stated rationale — and this plan's P2.0 — need amending.
- **RC** — see the substep definition above. Not optional.
- **Verify:** `cd prep && .venv/bin/python -c "import sys; sys.path.insert(0,'tests'); import stubs; print('ok')"`
  — the stub module imports standalone (the trap, checked rather than assumed). Its behavioural
  cases run inside P2.1's `test_probe.py`.

### P2.1 — `probe.py`
- **Spec:** §3 | **Creates:** `run_stage_a(client, record, scenario, cfg, budget) → StageAResult`,
  `run_stage_b(...) → StageBResult`
- **Tests first:** `test_probe.py` — **`test_task_instance_excludes_leaked_fields`** across a
  fixture battery (rubric 11's fair-test assertion: the prompt may contain the persona, company, a
  `DOMAIN_BUCKETS` phrase and a jurisdiction phrase — and **nothing** from the record);
  Stage B's structured response parses via `StubOpenAIClient`.
- **Depends on:** P1.11 (`SpendBudget`, `build_request_payload`), P1.8 (`scenarios`).
- **Every call follows §3's lifecycle verbatim:** `build_request_payload` → `budget.reserve` → the
  SDK call with **that same dict** → `settle(usage)` on the `else`, `terminal_for_exception` on the
  `except`. The `else`-block placement is load-bearing (Python does not route an `else`-block
  exception to that `try`'s `except`), so a `BudgetPoisoned` from `settle` cannot double-terminate.
- **RC** — see the substep definition above. Not optional.

### P2.2 — `judge.py`
- **Spec:** §4 | **Creates:** `JUDGE_RESPONSE_SCHEMA` (with `confidence: {minimum: 0, maximum: 1}`),
  `JudgeObligationInput`/`JudgeVerdict`/`JudgeResult`, `run_judge(client, obligations, draft_text,
  cfg, budget) → JudgeResult`, `parse_and_validate_verdicts(raw_response, requested_ids) →
  JudgeResult`
- **Tests first:** `test_judge.py` — duplicate `obligation_id` → first wins; omitted id →
  `"uncertain"`, confidence `0.0`, `applies_to_draft=False`, `omission_material=False`, **never**
  `"violation"`; hallucinated id → dropped; malformed JSON → retry once → all-omission fallback;
  **`test_out_of_range_confidence_discarded_not_clamped`** — `5.0` yields `uncertain`/`0.0`/
  `is_failure=False`, **explicitly not** `1.0` (clamping would clear the 0.7 floor and admit a
  record on garbage); same for `-0.2`, `NaN`, `Infinity`, `"0.9"`; `0.0` and `1.0` accepted; the
  synthesized rationale distinguishes out-of-range from omitted.
- **The schema bound is not the enforcement point.** OpenAI accepts `minimum`/`maximum` but does
  **not** structurally enforce them; `parse_and_validate_verdicts` step 3 is the only real check.
- **RC** — see the substep definition above. Not optional.

### P2.3 — `scoring.py`
- **Spec:** §4 | **Creates:** `score_citation(stage_b, record) → CitationScore`,
  `parse_baseline_date(raw) → str|None`, `score_compliance_date(stage_b, record, citation) →
  DateScore` (**three** args — the spec's F-round heading fix), `score_missed_obligation(record,
  scenario, judge_result, obligation_id) → ObligationScore`, `passes_failure_bar(citation, date,
  obligation) → tuple[bool, list[str]]`
- **Tests first:** `test_scoring.py` — one test per outcome value against `scoring_golden.json`,
  asserting `is_failure` is **True for exactly** `citation_fabricated` / `date_wrong` /
  `violation-above-floor-with-both-flags-true`, and **False for every other outcome** including
  `citation_alternative_real`, **`citation_unverifiable`**, `date_missing`, **`date_unparseable`**,
  `date_uncertain_attribution`; `score_missed_obligation` returns `not_applicable` without
  consulting the judge at all when `is_eligible` is False; `score_compliance_date` with a
  non-`citation_correct` citation always returns `date_uncertain_attribution`; failure-bar OR-logic;
  `SCORE_OUTCOME_TO_FAILURE_MODE`/`STAGE_OF_MODE` round-trip over exactly the 3 closed values.
- **`parse_baseline_date` is not optional polish:** `"September 1, 2026"` is a **correct** answer in
  the wrong shape; a raw string compare admits the record on evidence the baseline got it *right*.
  Ambiguous forms (`"01/09/2026"`) resolve to `None` → `date_unparseable`, never a guess.
- **RC** — see the substep definition above. Not optional.

### P2.4 — `curate.py`
- **Spec:** §3 | **Creates:** `CurationResult`, `probe_and_score_one(...) → ProbeAndScoreResult`,
  `_cap_stop_reason(survivors, probed, cfg) → str|None`, `run_curation(client, candidates, scenario,
  cfg, budget, exclude_ids=frozenset()) → CurationResult`
- **Tests first:** `test_curate.py` — all four stop conditions;
  **`test_survivor_ceiling_exact_at_batch_crossing`** (enter a 40-batch at 199 survivors → asserts
  `len(survivors) == target_set_size` **exactly**, never 200+n);
  **`test_sweep_cap_exact_at_batch_crossing`**; **both re-run across `probe_batch_size ∈ {1,7,40}`
  asserting identical counts** (batch size cannot influence a cap); a `BudgetExhausted` can stop
  mid-record and that record counts toward neither `probed` nor `survivors`;
  **`test_excluded_ids_are_never_probed`** (§7's winner's-curse fix).
- **The caps bind per-record, not per-batch.** A batch-boundary check overshoots by up to
  `probe_batch_size` — 39 records past goal #11's stated ceiling. Batching is now a **logging
  cadence only**.
- **RC** — see the substep definition above. Not optional.

### P2.5 — Phase-2 aggregate review (as P1.14 — additional to each task's RC substep)

---

# PHASE 3 — `prep/` LEVEL 3
**Bills: NO.** Every test here stubs the client; `decide_scenario` takes a `client` parameter
precisely so it can be. **Ordered, not parallel:** P3.1 defines `ScenarioDecision` (spec:2673) and
P3.2's `emit_template_config(cleared_records, decision: "ScenarioDecision")` annotates against it,
so **P3.1's TypedDict must exist before P3.2 type-checks**. It is a one-symbol join, not a deep
dependency — but it is a join, and this plan does not claim parallelism it has not verified.
Import it under `if TYPE_CHECKING:` (the spec's annotations are quoted forward references, and
`test_imports.py::test_no_circular_imports` walks the AST — keep the runtime graph acyclic).
**Ends green when** P3.3's Verify passes.

### P3.1 — `scenario_decision.py`
- **Spec:** §7 | **Creates:** `ScenarioDecision` (TypedDict), `decide_scenario(client, trial_pool,
  cfg, budget) → ScenarioDecision`, `strength(result) → float`, `mean_strength(probed) → float`
- **Tests first:** `test_scenario_decision.py` —
  **`test_budget_exhaustion_truncates_both_arms_equally`** (exhaustion mid-round 7 → both arms at 6,
  the in-flight round discarded whole, and **A is not declared winner off a fuller arm**);
  **`test_insufficient_trial_returns_no_winner`** (below `scenario_trial_min` → `outcome=
  "insufficient_trial"`, `winner is None`, `run_prep` locks no scenario and exits 0);
  **`test_small_eligible_pool_is_sufficient_when_fully_probed`**;
  **`test_discarded_round_drops_both_arms`**; `mean_strength` tie → `A`; `B` wins on strictly higher
  MEAN even with a smaller trial; evidence-file shape.
- **The arms interleave.** Running A to completion then B means any budget stop truncates B alone
  and hands the win to A — invisibly, since A is also the tie-break. One record each, in lockstep.
- **RC** — see the substep definition above. Not optional.
- **Verify:** `cd prep && .venv/bin/python -m pytest tests/test_scenario_decision.py -q`

### P3.2 — `generate_template_config.py`
- **Spec:** §7 | **Creates:** `TemplateConfigBundle`, `firm_profile_for_record(record) → dict`
  (**camelCase keys** — it is serialized straight into a TS object literal),
  `narrow_obligations_pure(firm_profile, cleared_records) → list[str]` (the Python port of §9a),
  `emit_template_config(cleared_records, decision) → TemplateConfigBundle`
- **Tests first:** `test_generate_template_config.py` — `test_trigger_tie_broken_by_id_ascending`;
  **`test_trigger_never_citation_only`** (the highest-failure-count record carries only
  citation/date evidence; the 1-mode `missed_obligation` record is chosen — **evidence type gates
  candidacy before strength ranks it**); **`test_raises_when_no_stage_a_evidence`** (ValueError
  naming the cause; writes **no** files); **`test_trigger_skips_crowded_out_candidate`**; step 7's
  narrowing assertion fires on a non-matching profile; **`test_narrowing_golden_parity`**.
- **Also update:** this task writes **four** `.tmpl` fragments under `prep/templates/` —
  `config_ts_fragment.tmpl`, `firm_profile_ts_fragment.tmpl`, `persona_ts_fragment.tmpl`,
  `prompts_ts_fragment.tmpl`. The fourth renders `scenario/prompts.ts` **in full**
  (`buildStageAPrompt`, `buildStageBPrompt`, `INDUSTRY_TAG_TO_BUCKET`, `DOMAIN_BUCKETS`,
  `SCENARIO_TASK_TEMPLATES`, `NEGATIVE_CONTROL_PROMPTS`). §8 resolves that module as **generated**,
  not hand-authored — that is what makes §12's eval ask the same question the evidence was recorded
  for.
- **Step 8's write is IDEMPOTENT REPLACEMENT, and this task is where that is implemented and
  proved.** For the three fragment targets, render the `.tmpl`, then: if a line declaring the
  target symbol already exists in the file, **replace that line in place**; otherwise **insert**
  it. `prompts.ts` alone is written whole. **`test_emit_is_idempotent`** — running
  `emit_template_config` twice over a `config.ts` that also carries hand-authored exports yields
  **byte-identical** output, exactly **one** declaration of each generated symbol, and leaves the
  hand-authored exports present. Without this, P8.2's re-run over Phase-6-populated files either
  deletes hand-authored code or emits a duplicate `export const`. See **P6.2**'s spec-issue
  callout for why the spec does not settle this and why the plan pins the safe reading.
- **Also update — `prep/mastra_prep/__init__.py`'s pinned re-export block** (spec §1:396–412).
  It had **no owning task**. It lands **here** and not in Phase 1 because its last two lines
  re-export `decide_scenario` (P3.1) and `emit_template_config`/`firm_profile_for_record` (this
  task) — a Phase-1 `__init__.py` would import modules that do not exist yet. Copy the block
  **exactly** as spec §1 pins it, including the `from .budget import …  # NOT curate.py` comment.
- **`probe.py`, `judge.py` and `scoring.py` are deliberately NOT re-exported** (spec:414), and
  that omission is load-bearing, not an oversight: re-exporting them at package level is what
  re-creates the `probe → judge → curate → probe` cycle the spec stage fixed by extracting the
  leaf `budget.py`. **`test_package_reexports`** — every name in the pinned block imports cleanly
  from `mastra_prep`, **and** `probe`/`judge`/`scoring` are absent from the package namespace.
  `test_imports.py::test_no_circular_imports` (P1.x) still guards the module graph itself; this
  test guards the package surface, which is a different thing and is what nothing else checked.
- **RC** — see the substep definition above. Not optional.
- **Verify:** `cd prep && .venv/bin/python -m pytest tests/test_generate_template_config.py tests/test_imports.py -q`

### P3.3 — Phase-3 aggregate review (additional to each task's RC substep)
- **Verify:** `cd prep && .venv/bin/python -m pytest tests/test_scenario_decision.py tests/test_generate_template_config.py -q`
  — both modules green together before Phase 4 opens.

---

# PHASE 4 — `review.py`, the clearance CLI
**Bills: NO.** `review.py` is a terminal CLI over already-probed records — it makes no model call
at all, so there is nothing to stub. **Single task:** P4.1 is one module; nothing to parallelize.
**Ends green when** P4.2's Verify passes.

### P4.1 — `review.py`
- **Spec:** §6 | **Creates:** `HumanReview` (TypedDict), `present_for_review(record,
  resolving_citations) → str`, `select_citation(resolving_citations) → tuple[str,str]`,
  `ask_obligation_confirmations(record) → dict[str,bool]|None`, `record_signoff(record, reviewer,
  obligation_confirmations) → ClearedRecord`, `record_rejection(record, reviewer, reason) → None`
- **Tests first:** `test_review.py` — `record_signoff` has **no parameter capable of overriding**
  `title`/`why_it_matters`/any extracted field (a `TypeError` on an extra kwarg — the signature
  takes only `record`/`reviewer`/`obligation_confirmations`); citation auto-selected with no prompt
  when exactly one URL resolves, prompted when >1; `ask_obligation_confirmations` returns `None`
  immediately when `missed_obligation` is absent; **any single `False` among the three questions
  makes the CLI refuse to reach `approve`** (routes to `record_rejection`);
  `validate_cleared_record` rejects a `human_review` with a stray confirmation.
- **This is the publication gate** (goal hard constraint: *never ship a record that has not been
  human-reviewed*). There is no batch-approve flag in code or config, and adding one is the
  "waiving human review" row of §6's anti-padding table.
- **RC** — see the substep definition above. Not optional.
- **Verify:** `cd prep && .venv/bin/python -m pytest tests/test_review.py -q`

### P4.2 — Phase-4 aggregate review (additional to each task's RC substep)
- **Verify:** `cd prep && .venv/bin/python -m pytest tests/test_review.py -q` — plus confirm by
  inspection that no batch-approve path exists in `review.py` or `config.yaml`, and that
  `review.py` remains the **only** writer of `data/cleared/` (`grep -rn "data/cleared" prep/` shows
  no other writer). This is the goal's human-review constraint; it is checked, not assumed.

---

# PHASE 5 — `run_prep.py`, stubbed end-to-end

### P5.1 — `run_prep.py`
- **Spec:** §3's pinned entrypoint | **Creates:** `main(argv=None) → None` with the exact structure
  §3 pins: `load_settings` → `load_env` → `make_client` → `SpendBudget` → **`try:`** filter
  candidates → `decide_scenario` → write evidence → **`if outcome == "insufficient_trial"`: report
  and return** → filter by `is_eligible` → `run_curation(exclude_ids=…)` → `report_curation` →
  **`finally:` `budget.assert_no_open_reservations()`** + log spend.
  Plus the argv branches, **all four** of the spec's: `--review`, `--replay`,
  `--emit-template-config`, `--verify-cleared`.
- **`--review` is the human checkpoint's command** (§6; invoked by **R7.4**) and it must exist
  before Phase 7 — an earlier draft listed only three branches while R7.4 called
  `run_prep.py --review`, i.e. the plan's own blocking checkpoint had no implementing task.
  **Dispatch contract:** loads survivors from `data/scratch/`, and for each one drives §6's loop —
  `present_for_review` → `select_citation` (auto-pick when exactly one URL resolved; prompt when
  >1) → `ask_obligation_confirmations` (returns `None` immediately unless `missed_obligation` is
  among the modes) → `record_signoff` **or** `record_rejection`. It makes **no API calls** (every
  input was recorded at probe time) and it is the **only** write path into `data/cleared/`.
- **Tests first (add to `test_run_prep.py`):** **`test_review_branch_dispatches_to_review_module`**
  — `--review` calls `review.py`'s loop and **never** `run_curation`/`decide_scenario`;
  **`test_review_makes_no_api_calls`** — the branch runs to completion with a stub client that
  raises on any call; **`test_review_is_the_only_writer_of_cleared_dir`** — no other argv branch
  writes there.
- **`--verify-cleared`'s contract, pinned so it does not grow:** it validates **structure** —
  every file in `data/cleared/` parses as a `ClearedRecord`, `validate_cleared_record` passes,
  `human_review.attestation == "approved"`, and `citation.url` matches one of the record's recorded
  resolving URLs. It **makes no network calls and re-resolves nothing.** §14 places post-clearing
  re-validation explicitly **out of scope for v1**; an earlier draft's DoD had this flag
  "re-resolve each `citation.url`", which silently added a URL crawler the spec excludes — and
  quoted §14's own exclusion two lines later. Citations are validated at **clearing time**, by
  §2's gate; a link that dies afterwards is a manual fix the README documents.
- **Tests first:** `test_run_prep.py` — `main()` filters through `is_eligible` **before**
  constructing `run_curation`'s input; **`test_reservation_audit_runs_on_every_exit_path`** — the
  `finally` fires on **all four** exits (clean finish, `insufficient_trial` early return,
  `BudgetExhausted` stop, unexpected exception); **`test_insufficient_trial_short_circuits`** —
  writes the evidence file, calls `run_curation` **zero** times, returns 0.
- **`report_curation`'s output fields are pinned** (§3) — including that `survivors/probed` is
  **success-conditioned** (curation stops at target, so the rate is biased upward) and that its
  denominator is the **scenario-eligible subset**, not the goal's headline 8,260.
- **Verify:** `cd prep && .venv/bin/python -m pytest tests/ -q` — **the entire `prep/` suite green, zero
  billed calls.** This is the phase gate.
- **RC** — see the substep definition above. Not optional.

### P5.2 — Zero-spend proof *(the check that makes "Phases 0–6 bill nothing" verifiable)*
- **How a developer proves they have not accidentally billed anything:**
  1. **`unset OPENAI_API_KEY`**, then run the full gate:
     `cd prep && .venv/bin/python -m pytest tests/ -q` **and**
     `cd template && npm run test:unit && npm run typecheck` **and**
     `cd template && npx vitest run tests/evals.test.ts tests/comparisonWorkflow.test.ts -t 'unit:'`.
     **If a suite passes with no key present, it made no calls.** That is the whole proof, it is
     mechanical, and it costs nothing — a test that secretly billed would fail here with an auth
     error rather than pass.
     > **The third command is not redundant — without it this proof was vacuous for the two
     > largest test files.** `npm run test:unit` **excludes `evals.test.ts` and
     > `comparisonWorkflow.test.ts` at file level** (spec:3936). An earlier draft ran only the
     > first two commands and concluded "Phases 0–6 bill nothing" — a claim that was *true*, but
     > established by **not running** the files in question rather than by running them keyless.
     > A proof whose strength comes from skipping the interesting cases is worth nothing; this is
     > the same class of defect as asserting a ratio over an empty set. The `-t 'unit:'` command
     > is what makes step 1 an actual proof for those files.
  2. `grep -rn "make_client()" prep/tests/` → **no hits**; every test injects a stub (P2.0).
  3. `grep -rln "OPENAI_API_KEY" prep/tests template/tests` → **no hits**.
  4. After Phase 7, confirm the *only* spend is what §3's ledger recorded: the final `log()` line
     from `run_prep.py` plus R7.0's ~$0.01, against the provider's own usage dashboard.
- **Which phases bill, stated once, authoritatively:**
  | Phase | Bills |
  |---|---|
  | **0–6** | **Nothing.** No exceptions. Stub clients (`prep/`) and a synthetic fixture (`template/`) |
  | **7** | **Everything.** `R7.0` (~$0.01, the live containment preflight) + `R7.3` (~$17 typical, ~$93.5 worst) |
  | **8** | Nothing — vendoring and generation are file operations |
  | **9** | `npm test` (~609 calls / **~$23**, incl. the guardrail's own verdict call) + `npm run demo` (~4 calls) |
- **Run this check at every phase gate**, not just once. It is one `unset` and two commands.

---

# PHASE 6 — `template/` (synthetic fixture; still zero billed calls) **[parallel track B]**

**Bills: NOTHING — no exceptions.** `comparisonWorkflow.test.ts`'s *non-billing* negative battery
runs here (**P6.11**); its **live** assertions are excluded from `test:unit` and deferred to **R7.0**,
Phase 7's preflight. Ends green when **both** commands in P6.17's gate pass — `npm run test:unit`
**and** the deterministic-case command below, which `test:unit` cannot reach.

> **The `test:unit` gap, and the command that closes it.** The spec pins
> `"test:unit": "… vitest run --exclude tests/evals.test.ts --exclude tests/comparisonWorkflow.test.ts"`
> — a **file-level** exclusion (spec §8). So `npm run test:unit` does **not** execute *any* test in
> those two files, including the deterministic ones. An earlier draft of this plan said their
> "non-billing cases run now" in Phase 6 **and** that Phase 6 ends green on `test:unit` — those two
> statements cannot both be true, and the false one was load-bearing: it meant
> `evals.test.ts`'s partition/ledger logic would first execute during **`npm test` in Phase 9, at
> ~609 calls / ~$23 per iteration**. A bug in deterministic, zero-cost logic discoverable only
> after real spend is precisely what Fact 1 exists to prevent, and P5.2's zero-bill proof was
> **vacuously true** for both files — the command it relies on skips them.
>
> **Verified before relying on it:** the billing in both files lives **inside `test()` bodies**
> (`runScoreboard()`, `run.start()`), not at module top-level. Module scope only constructs
> `Agent`/`Mastra` objects from a router **string** and imports schemas — no network call. So
> Vitest's `-t` name filter can execute the deterministic cases while never entering a billing
> body. If that ever stops being true — a top-level `await` that bills — this approach fails and
> the honest statement is that those cases are first proven at Phase 9's expense; it is not true
> today.
>
> **This is consistent with the spec, not a divergence from it.** The spec's own test inventory
> already marks both files' `Network?` as **"Yes (the metadata-completeness and invariant cases:
> No)"** (`comparisonWorkflow.test.ts`) and **"Yes (the partition + dataset-routing cases: No)"**
> (`evals.test.ts`), and says `test_partition_is_disjoint_and_total` is asserted "over the real
> vendored set with **zero API calls**". The spec therefore *already asserts* these cases cost
> nothing; it simply never gave them a runnable selector. This plan adds the selector.
>
> **The mechanism is a `describe` wrapper + a command — no `package.json` edit, no renamed test.**
> In each of the two files, the zero-network cases are grouped under `describe("unit: …")`, and
> Phase 6 runs:
> ```
> cd template && npx vitest run tests/evals.test.ts tests/comparisonWorkflow.test.ts -t 'unit:'
> ```
> Vitest matches `-t` against the **full** name (`describe > test`), so the wrapper alone selects
> them.
>
> **Why a wrapper and not a name prefix — a constraint a subagent must not discover the hard way.**
> The spec pins the *literal* `test()` string for three deterministic cases in `evals.test.ts`:
> `test("report has no external references", …)`, `test("report escapes draft text", …)` and
> `test("report renders both real branch outputs and the matching record", …)`. Renaming any of
> them to add a prefix would be a **silent edit of an approved, refine-capped spec**. A `describe`
> wrapper changes the *full* name while leaving every pinned `test()` string byte-identical. The
> cases the spec labels only in snake_case (`test_partition_is_disjoint_and_total`,
> `test_delivery_scorer_union_is_complete`, `test_blanket_guardrail_fails_the_suite`,
> `test_forged_record_metadata_is_ignored`, …) carry no pinned literal, so the wrapper is the one
> uniform mechanism that fits both kinds. **Do not rename a spec-pinned test to satisfy the
> filter.**
>
> **Fail-closed by construction.** The filter is an **allowlist**: a case runs only if it is inside
> a `unit:` describe. A newly added billing test is invisible to this command by default — the
> failure mode is "a free test doesn't run", never "a billing test bills unexpectedly". The
> inverse design (a negated pattern excluding known billing tests) fails **open** and is rejected
> for that reason. `test:unit`'s pinned definition is **untouched**; the billing cases sit outside
> the wrapper and run only in R7.0 (`comparisonWorkflow`) and Phase 9 (`npm test`).

### P6.1 — Synthetic generator inputs **(the fixture comes FIRST — P6.2 consumes it)**
- **Spec:** §5, §7 | **Creates two committed fixtures**, both exact, neither "plausible":
  1. `template/src/data/cleared-set.json` — a **synthetic**, schema-conforming set of **6**
     records covering, one each: a `missed_obligation` record with all three confirmations
     (`obligation_applies_confirmed`/`artifact_capable_of_violation_confirmed`/
     `omission_materiality_confirmed` all `true`); a citation-only record
     (`citation_fabricated`); a record carrying **both**; a record that will be `crowdedOut`
     (same tags as the trigger, nearer `compliance_date`); a **non-ASCII** regulator name; a
     null-`compliance_date` record. Every record: `impact_label: "high"`, `scenario: "A"`,
     `model_id: "openai/gpt-5.6-sol"`, `model_cutoff: "2026-02-16"`,
     `source.snapshot_date: "2026-07-11"`.
  2. `prep/tests/fixtures/synthetic_scenario_decision.json` — a **fully specified**
     `ScenarioDecision`, every field of §7's TypedDict given a literal value:
     `outcome: "decided"`, `winner: "A"`, `stop_reason: "complete"`, `discarded_rounds: 0`,
     `strength_scores: {"A": 1.5, "B": 1.0}`, `survivor_counts: {"A": 4, "B": 2}`,
     `stage_a_survivor_counts: {"A": 2, "B": 1}`, `probed_ids: {"A": [...], "B": [...]}`,
     `trial_planned: {"A": 4, "B": 2}`, `trial_completed: {"A": 4, "B": 2}`,
     `decided_at: "2026-07-16T00:00:00+00:00"`, `evidence_path:
     "data/scratch/scenario_decision.json"`.
- **No "plausible" values.** An earlier draft said to "build a synthetic `ScenarioDecision`
  (winner `"A"`, plausible strengths/counts)" — which is a TBD wearing an adjective. These are
  committed files with literal fields, so P6.2's generation is reproducible and reviewable.
- **Verify (deviates from the default — this task owns no test module; it makes two fixtures):**
  ```
  cd prep && .venv/bin/python -c "
  import json
  d = json.load(open('tests/fixtures/synthetic_scenario_decision.json'))
  c = json.load(open('../template/src/data/cleared-set.json'))
  assert d['outcome'] == 'decided' and d['winner'] == 'A', d
  assert len(c) == 6, len(c)
  assert all(r['impact_label'] == 'high' and r['scenario'] == 'A' for r in c)
  print('fixtures ok:', len(c), 'records')"
  ```
  Both fixtures are **consumed** — and therefore really validated — by P6.2 (which fails loudly on
  a malformed decision) and by `schema.test.ts` in P6.3, which Zod-parses every record. This
  command is the cheap structural check that P6.2 has something well-formed to read.
- **Why synthetic and why now:** this is Fact 2. Every template module is built and proven against
  it, so the real run (P7) is paid **once**, against a consumer already known to work. The cleared
  set is replaced wholesale in P8.1; `schema.test.ts` is what makes that swap safe.

### P6.2 — **Generate the template's scenario-locked source from those fixtures** *(needs P3.2)*
- **Spec:** §7's generation contract
- **Do:** invoke the **real** generator directly — no new CLI surface:
  ```
  cd prep && .venv/bin/python -c "
  import json
  from mastra_prep.generate_template_config import emit_template_config
  cleared  = json.load(open('../template/src/data/cleared-set.json'))
  decision = json.load(open('tests/fixtures/synthetic_scenario_decision.json'))
  print(emit_template_config(cleared, decision))"
  ```
  It writes all **four** fragments mechanically: `config.ts`'s `DEMO_TRIGGER_RECORD_ID`,
  `firmProfile.ts`'s `DEMO_FIRM_PROFILE`, `baselineAgent.ts`'s `SCENARIO_PERSONA_INSTRUCTIONS`,
  and `scenario/prompts.ts` **in full**.
- **`run_prep.py` is NOT modified.** An earlier draft invented
  `run_prep.py --emit-template-config --synthetic` — **a new argv branch the approved spec does not
  have**. That is the same defect as that draft's `--verify-cleared` URL crawler, committed in the
  same round it was corrected: silently widening a CLI contract the spec pins. `emit_template_config`
  is an ordinary function with an ordinary signature (§7); calling it with two committed fixtures
  needs no flag. **P8.2 uses the approved `run_prep.py --emit-template-config` path** over real
  reviewed data — that branch exists in the spec and is untouched here.
- **Why generate at all in Phase 6.** An earlier draft hand-authored a "stand-in"
  `scenario/prompts.ts` and `.skip`ped every test depending on generated constants until P8.2. Both
  were wrong, and the second was a symptom of the first:
  - §8 states this module is **generated in full and never hand-authored**. A stand-in is not a
    scaffold — it is a **second implementation of a generated file**, and what §8's rule buys is
    that the eval asks the *same question the evidence was recorded for*. A stand-in silently
    reintroduces exactly that drift, and would have tested green all through Phase 6.
  - The `.skip`s were load-bearing: `SCENARIO_PERSONA_INSTRUCTIONS !== ""` **is** the check that
    generation ran, so skipping it meant Phase 6 could not tell a generated persona from an
    un-generated one. Running the real generator here deletes the skip machinery entirely.
- **P8.2 reruns this same generator** on reviewed real data and reruns the same tests. One
  generator, two inputs — synthetic then real. Nothing hand-written at either point.
- **Dependency (stated, not glossed):** needs **P3.2**'s `emit_template_config`. This is the join
  that makes track B *not* wholly independent of the prep track — see §2's graph.
- **Verify:** the four files exist and are non-empty; `git diff --stat template/src` shows exactly
  them.

#### ⚠ Generated-vs-hand-authored contract — read this before P6.3 and P6.5 touch these files
This task and P6.3/P6.5 **write into the same three files**. Nothing structural stops a later task
from destroying this one's output with a whole-file `Write`; it would self-correct via
`test_generation_step_actually_ran`, but only after a wasted pass — and a subagent acting on an
unstated contract is exactly the failure this plan exists to prevent. The contract:

| File | Generated by P6.2 | Hand-authored by | Rule for the later task |
|---|---|---|---|
| `src/config.ts` | **one line**: `export const DEMO_TRIGGER_RECORD_ID: string = "…";` | P6.3 (`MODEL_ID`, `MODEL_CUTOFF`, `SNAPSHOT_DATE`, `JUDGE_CONFIDENCE_FLOOR`, `REASONING_EFFORT`, `MAX_OUTPUT_TOKENS`, `GENERATION_CONFIG`) | **Add around the generated line. Never re-author the file whole.** |
| `src/firmProfile.ts` | **one const**: `DEMO_FIRM_PROFILE` | P6.3 (`FirmProfileSchema`, `FirmProfile`, `firmProfileForRecord`) | same |
| `src/agents/baselineAgent.ts` | **one const**: `SCENARIO_PERSONA_INSTRUCTIONS` | P6.5 (the agent construction) | same |
| `src/scenario/prompts.ts` | **the entire file** (§8: generated in full, never hand-authored) | **nobody** | **Never edit by hand at all.** Change the `.tmpl` and re-generate. |

**This is read from the spec, not chosen by this plan.** Spec §7 step 8's "WRITE the files" could
be read as whole-file writes, but §5's own listing of `config.ts` (spec:3275–3282) shows it
containing the hand-authored `MODEL_ID`/`MODEL_CUTOFF`/`SNAPSHOT_DATE`/`JUDGE_CONFIDENCE_FLOOR`
**plus** a comment stating that generation "writes the rendered **line** … **into this file**"
(spec:3287–3298). A whole-file write of a one-line fragment would delete constants the spec
itself puts in that file, so **line-level insertion is the only reading consistent with the
spec.** `prompts.ts` is the stated exception: generated in full.

> **Spec issue (callout, not a divergence) — `emit_template_config`'s re-run semantics are
> unspecified, and P8.2 re-runs it.**
> §7 step 8 says the generator renders a fragment and writes it into its owning `.ts` file, but
> never says what happens when that file **already contains** a previously generated line plus
> hand-authored code — which is exactly the state at **P8.2**, where the generator re-runs over
> real reviewed data against files Phase 6 has since filled in. Two readings, and the spec
> licenses neither over the other: (a) whole-file write ⇒ **P8.2 silently deletes every
> hand-authored export in `config.ts`, `firmProfile.ts` and `baselineAgent.ts` one step before
> ship**; (b) line replacement ⇒ correct, but requires idempotency the spec never states, and a
> naive append would emit a **duplicate** `export const` (a TypeScript compile error — loud, at
> least). `TemplateConfigBundle.written_files` records *that* files were written, not *how*.
> **The plan cannot edit the approved spec, so it pins the safe reading and makes it testable:**
> P3.2 implements the write as **idempotent replacement** — if a line declaring the target symbol
> exists, replace it in place; otherwise insert it — and P3.2's tests assert it
> (`test_emit_is_idempotent`: running the generator twice over a file carrying hand-authored code
> yields byte-identical output and exactly one declaration of each generated symbol, with the
> hand-authored exports still present). If the orchestrator reads §7 step 8 as mandating
> whole-file writes, this needs a spec amendment before P8.2 — the difference is destructive and
> lands at ship time.

### P6.3 — `schema.ts` + `config.ts` + `firmProfile.ts`
- **Spec:** §5, §8 | **Creates:** `BaselineFailureSchema`, `ClearedRecordSchema` (`.strict()`),
  `ClearedRecord`, `StageBResponseSchema`, **`predictsStageAViolation`** (schema.ts — **not**
  `GuardrailVerdictSchema`, whose sole owner is `judge/contract.ts`); `MODEL_ID`, `MODEL_CUTOFF`,
  `SNAPSHOT_DATE`, `JUDGE_CONFIDENCE_FLOOR`, `REASONING_EFFORT`, `MAX_OUTPUT_TOKENS`,
  `GENERATION_CONFIG` (config.ts — **no `MAX_PROCESSOR_RETRIES`**); `FirmProfileSchema`,
  `FirmProfile`, `DEMO_FIRM_PROFILE`, `firmProfileForRecord` (firmProfile.ts)
- **Tests first:** `schema.test.ts` (the vendored file parses for every record);
  `config.test.ts` (`test_generation_step_actually_ran` — `DEMO_TRIGGER_RECORD_ID !== ""` and
  resolves; **`SCENARIO_PERSONA_INSTRUCTIONS !== ""`**, since its declared default is the empty
  string and a forgotten generation step would ship an agent with **no persona** — a silently
  different experiment, not a crash; `GENERATION_CONFIG` is the same object both agents hold;
  `MAX_PROCESSOR_RETRIES` is **not exported**); `firmProfile.test.ts`;
  **`scorers.test.ts`'s `stage_a_predicate_cases` group against `predictsStageAViolation`** — this
  module owns that function (spec:2405), so it owns the golden group that proves its TS behaviour
  matches prep's Python original over the shared `scoring_golden.json` (G8's cross-seam parity).
- **This task CREATES `scorers.test.ts`** — it is the first of the three tasks that write it (§0's
  shared-test-file rule; the chain is **P6.3 → P6.4 → P6.12b**, matching the phase's task order).
  It creates the file containing **only** `describe("stage_a_predicate_cases", …)` and **only**
  that block's imports (`predictsStageAViolation`, the fixture). It does **not** stub, scaffold or
  placeholder the other three groups: their targets do not exist yet, and importing them would
  fail the module load and error every case in the file.
- **It also pins the file's structure, once, for the two tasks that follow:** **one `describe` per
  golden group, named exactly after the group** — `stage_a_predicate_cases` (here),
  `judge_cases` (P6.4), `citation_date_cases` and `obligation_cases` (P6.12b). That naming is what
  lets each owning task verify **its own** group with `-t '<group>'`. The spec pins no literal test
  name in this file (unlike `evals.test.ts`), so the convention is free to adopt.
- **Verify:** `cd template && npx vitest run tests/schema.test.ts tests/config.test.ts tests/firmProfile.test.ts && npx vitest run tests/scorers.test.ts -t 'stage_a_predicate'`
- **No skips.** These cases pass in Phase 6 because **P6.2 ran the real generator** against
  synthetic data, so `DEMO_TRIGGER_RECORD_ID` and `SCENARIO_PERSONA_INSTRUCTIONS` are genuinely
  populated — by the same code path P8.2 will use on real data.
- **⚠ PRESERVE P6.2's GENERATED LINES — do not author these files whole.** P6.2 has already
  written `DEMO_TRIGGER_RECORD_ID` into `config.ts` and `DEMO_FIRM_PROFILE` into `firmProfile.ts`
  (spec §7 step 8). This task **adds** the hand-authored exports **around** them. See the
  generated-vs-hand-authored contract in P6.2 — a whole-file `Write` here destroys P6.2's output
  and `test_generation_step_actually_ran` will fail on the empty default.

### P6.4 — `judge/contract.ts` **(the leaf: no agent, no scorer)**
- **Spec:** §8 | **Creates:** `JUDGE_SYSTEM_PROMPT`, `renderJudgeUserPrompt`,
  `GuardrailVerdictSchema` (**sole owner**; `confidence: z.number().min(0).max(1)`),
  `JudgeObligationInput`/`JudgeResult`, `parseAndValidateVerdicts`, **`asJudgeObligation`**
- **`asJudgeObligation(record)` lands here under the spec-issue callout in P6.12b** — read it
  before building this module. It builds `{id, title, key_requirements, objective}` from a cleared
  record and **never** its `citation` or `baseline_failures` (spec:4225). Both consumers
  (`carverGuardrail.ts`, `evals/scorers.ts`) import it from here, so the guarded arm and the eval
  ask the judge the **same** question by construction rather than by coincidence.
- **Depends on:** zod, **plus `import type { ClearedRecord } from "../schema"`** for
  `asJudgeObligation`'s parameter — a **type-only** import (P6.3), erased at compile time, adding
  **no runtime edge**. §1 pins this module's imports as "zod only"; that is why the change is
  raised as a spec issue in P6.12b rather than made silently. **Never** an agent, **never** a
  scorer — that is the whole point of this module: it is the leaf that breaks the
  `judgeAgent ↔ scorers` cycle, and a type-only import of a zod-only module cannot re-form it.
- **Tests first:** `scorers.test.ts`'s `judge_cases` group against `parseAndValidateVerdicts`
  (out-of-range confidence **discarded, not clamped**; duplicate id → first wins; omitted →
  `"uncertain"`; hallucinated → dropped; malformed → retry → all-uncertain).
- **Verify (deviates from the default):**
  `cd template && npx vitest run tests/scorers.test.ts -t 'judge_cases'`
- **This task APPENDS to `scorers.test.ts`, which P6.3 created** — it adds **only**
  `describe("judge_cases", …)` and **only** that block's imports (`parseAndValidateVerdicts`,
  `GuardrailVerdictSchema`, the fixture). It does not re-author the file, and it does not touch
  P6.3's `stage_a_predicate_cases` block. P6.12b appends the last two groups when their targets
  exist. See §0's shared-test-file rule and its chain: **P6.3 → P6.4 → P6.12b**. The bare file run
  is green here and at every later point; the filter proves *this* group specifically.

### P6.5 — `agents/sharedConfig.ts` + `baselineAgent` + `judgeAgent`
- **Spec:** §8 | **Creates:** `SHARED_AGENT_CONFIG` (`instructions`/`model`/`defaultOptions` — the
  ONE object both compared agents spread); `baselineAgent` (`...SHARED_AGENT_CONFIG`);
  `judgeAgent` (`instructions: JUDGE_SYSTEM_PROMPT`, `defaultOptions: GENERATION_CONFIG`)
- **Depends on:** `config.ts` (`MODEL_ID`, `GENERATION_CONFIG`), `judge/contract.ts`
  (`JUDGE_SYSTEM_PROMPT` — one-way).
- **NOT `guardedAgent`** — it imports `CarverGuardrail`, which does not exist until **P6.9**. It is
  built in **P6.10**; see the ordering note there.
- **⚠ PRESERVE P6.2's GENERATED LINE.** `agents/baselineAgent.ts` already contains the generated
  `SCENARIO_PERSONA_INSTRUCTIONS` const (spec §7 step 8). This task adds the agent construction
  **around** it and has `SHARED_AGENT_CONFIG.instructions` reference it. A whole-file `Write`
  destroys it, and `config.test.ts`'s `SCENARIO_PERSONA_INSTRUCTIONS !== ""` then fails — see the
  generated-vs-hand-authored contract in **P6.2**.
- **Verify:** `cd template && npx vitest run tests/carverGuardrail.test.ts -t 'share'` (the
  shared-config reference-equality cases; the full file lands in P6.9/P6.10).

### P6.6 — `judge/callJudge.ts`
- **Spec:** §8 | **Creates:** `runJudge(obligations, draftText)` — the **only** place `judgeAgent`
  is ever invoked; the single implementation of §4's retry-once-then-all-uncertain degradation
  (including the out-of-range-confidence throw the `[0,1]` Zod bound introduces).
- **Depends on:** `judge/contract.ts` **and** `agents/judgeAgent.ts` — **both must already exist**
  (P6.4, P6.5). An earlier draft built this before `judgeAgent`, which is a module importing a
  file that does not exist yet.
- **Tests first:** inside `describe("runJudge", …)` in **`carverGuardrail.test.ts`** — a stubbed
  `judgeAgent` throwing on both attempts → `runJudge` returns the all-`"uncertain"` fallback rather
  than propagating (the fail-open contract §9b depends on); malformed JSON on the first attempt →
  **retried once** → parsed result returned.
- **Why that file, and not `callJudge.test.ts`:** the spec's test tree pins **12** files (§1) and
  **none is named for this module**. Rather than invent a thirteenth — the approved spec is
  refine-capped and its tree is pinned — these cases join `carverGuardrail.test.ts`, which already
  owns §9b's judge-failure behaviour (`test_judge_parse_failure_passes_through`). Per §0's
  shared-test-file rule this task adds **only** its `describe` and **only** its imports
  (`runJudge`, a stub agent); `CarverGuardrail` itself does not exist until P6.9 and must not be
  imported here.
- **Verify (deviates from the default — no `callJudge.test.ts` exists):**
  `cd template && npx vitest run tests/carverGuardrail.test.ts -t 'runJudge'`

### P6.7 — `tools/narrowObligations.ts`
- **Spec:** §9a | **Creates:** `narrowObligations` (Tool), `narrowObligationsPure(firmProfile,
  clearedSet) → string[]`
- **Tests first:** `narrowObligations.test.ts` — zero-required-match; exactly-one; >5 (ranking
  exercised); jurisdiction-only with no industry/function overlap **excluded** (required-AND);
  **`test_every_cleared_record_is_relevant_to_its_own_profile`** (§9a's proof, over the real
  vendored set); **`test_null_country_and_bloc_record_cannot_match`**;
  **`test_narrowing_golden_parity`**; **`test_demo_trigger_record_survives_narrowing`** — no skip:
  P6.2 generated `DEMO_TRIGGER_RECORD_ID`/`DEMO_FIRM_PROFILE` from the synthetic set, and the
  generator's own step-7 assertion guarantees the trigger narrows under the emitted profile.
- **`urgencyWeight` uses `SNAPSHOT_DATE`, never `Date.now()`** — narrowing must be deterministic on
  every machine, forever.

### P6.8 — `processors/tripwireContainment.ts` **(goal #8's KNOWN RISK — resolved HERE, early)**
- **Spec:** §10, §12 | **Creates:** `TripwireOutcome`, `normalizeDelivery(call) →
  Promise<TripwireOutcome>`, `isTripWireError(err)` (**sole owner** — not `carverGuardrail.ts`)
- **Tests first:** `tripwireContainment.test.ts` —
  **`test_both_tripwire_forms_normalize_identically`**: a stubbed agent that **returns**
  `{tripwire}` and one that **throws** `TripWireError` yield the same `{tripped: true, reason,
  processorId, metadata}`; a non-tripwire error re-throws untouched; a clean call →
  `{tripped: false, text}`. Then **both mappings**: guarded → `GuardedResultSchema`,
  delivery → `DeliveryResultSchema`.
- **This is where goal #8's risk gets resolved empirically, and it is deliberately early.** The
  goal says *"Verify this in the first hour of the template stage; do not assume either way."* The
  unit test pins both forms with stubs (free, instant) **here**; the **live** proof is **R7.0**,
  the first billed call in the project and the first step of Phase 7.

### P6.9 — `processors/carverGuardrail.ts`
- **Spec:** §9 | **Creates:** `CarverGuardrail` (class), `AuditEntry`, `AuditWriter`,
  `FileAuditWriter`; the three stages (narrow → verdict → enforce)
- **Tests first:** `carverGuardrail.test.ts` — a synthetic verdict drives each of high/medium/low
  through enforcement (**medium/low are unit-test-only** — see the Goal-issue note in §11 below);
  **audit writes** asserted via an injected stub `AuditWriter`, including the high/abort path
  (catch the thrown tripwire, check the stub was called **before** the throw); zero-violation → no
  write; **`test_multi_violation_reports_full_set`** — a stubbed judge returning three violated
  obligations asserts `violated_obligation_ids` lists all three **in narrowing-rank order**, that
  `record.id` is the first, and the audit entry carries the same array;
  **`test_judge_parse_failure_passes_through`** — a judge throwing on both attempts returns the
  draft **unchanged**, calls `abort()` never, writes no audit entry, propagates **no exception**.
- **Depends on:** **P6.6** (`runJudge`), **P6.7** (`narrowObligationsPure`), **P6.3**
  (`ClearedRecord`), **P6.4** (**`type JudgeResult`** and **`asJudgeObligation`** — TYPE-only for
  the former; spec:4195). (`normalizeDelivery`, P6.8, is used by P6.11's step — not by the
  processor itself.)
  **Not** `agents/judgeAgent.ts` — the guardrail delegates through `callJudge.ts`, the only
  permitted path to that agent. **Not** `GuardrailVerdictSchema`/`renderJudgeUserPrompt`/
  `parseAndValidateVerdicts` — spec:4196–4198 states all three moved **inside** `runJudge`; the
  same rule that binds P6.12b binds this module, for the same reason.

### P6.10 — `agents/guardedAgent.ts` **(only now — it imports `CarverGuardrail`)**
- **Spec:** §8 | **Creates:** `guardedAgent` — `...SHARED_AGENT_CONFIG` (**the same object**
  `baselineAgent` spreads, not a copy) + `outputProcessors: [new CarverGuardrail()]`. **No
  `maxProcessorRetries`.**
- **Depends on:** `agents/sharedConfig.ts` (P6.5) **and** `processors/carverGuardrail.ts` (P6.9).
  This is why it is not in P6.5 with the other two agents: an earlier draft built all three there,
  which had `guardedAgent` importing a processor that would not exist for four more tasks.
- **The processor is the ONLY difference between the two arms** — that is the entire experiment
  (goal #9), and it is the reason both agents spread one shared object rather than repeat three
  fields that happen to agree.
- **Tests first (now that both arms exist):** inside `describe("guarded arm", …)` in
  **`carverGuardrail.test.ts`** —
  **`test_requestContext_cannot_reach_either_prompt`**: `SHARED_AGENT_CONFIG.instructions`/`.model`
  are **static values, not functions** (a dynamic config function is the only documented path from
  `requestContext` into a prompt); via the public accessors, `getInstructions({requestContext})`
  returns the unchanged constant and does **not** contain the profile's country/sector;
  `listTools()` is empty; the two arms resolve identically.
  **`test_guarded_agent_has_no_processor_retries`** — `maxProcessorRetries` undefined.
- **Why this is a controlled-experiment guard, not a lint:** if `requestContext` reached the
  prompt, the guarded arm would draft *knowing the firm's jurisdiction and sector* while the
  baseline drafts blind — goal #9's explicitly fatal case, and it would **look like success**.
- **Verify (deviates from the default — there is no `guardedAgent.test.ts`; the spec's tree has no
  such file, and these cases are *about both arms*, so they belong with the shared-config cases):**
  `cd template && npx vitest run tests/carverGuardrail.test.ts` — by this task the whole file is
  landed (P6.5's shared-config cases, P6.6's `runJudge` cases, P6.9's enforcement cases and this
  task's), so the **bare file run** is the honest check here, not a filter.

### P6.11 — `workflows/compareWorkflow.ts`
- **Spec:** §10 | **Creates:** `draftStep`, `guardedStep`, `reportStep`, `GuardedResultSchema`
  (discriminated union + `superRefine` on the union — `z.discriminatedUnion` needs plain
  `ZodObject` members, so the refinement wraps the union), `ComparisonReportSchema`,
  `compareWorkflow` (**with `requestContextSchema: z.object({firmProfile: FirmProfileSchema})`** —
  validated at `run.start()`, and what gives Studio a schema-driven form)
- **`guardedStep` calls `normalizeDelivery` and maps** — it does **not** inline a `try/catch`.
  `buildBlockedResult` recomputes `narrowObligationsPure(firmProfile, vendoredClearedSet)` as the
  authoritative candidate set (metadata cannot vouch for itself), requires every violated id to be a
  unique member **in rank order**, and **derives** the display record from the vendored set rather
  than trusting metadata's copy.
- **Tests first:** the negative battery in `comparisonWorkflow.test.ts` — **all non-billing, and
  they genuinely execute in this phase**, because this task places them inside the file's
  `describe("unit: guardedStep invariants")` block, which the phase gate's
  `-t 'unit:'` command selects (see Phase 6's header). They are **not** reachable via
  `npm run test:unit`, which excludes this file at file level; the wrapper is what makes them
  runnable at all before Phase 9. Cases: `test_incomplete_metadata_fails_loudly`; duplicate id; an
  id that is not a vendored record; **`test_known_but_not_narrowed_id_rejected`**; ids out of rank
  order; **`test_forged_record_metadata_is_ignored`** (a forged title/citation yields the
  **vendored** record's real values).
- **Do NOT wrap** the file's live tripwire-containment proof
  (`test("guarded branch tripwire never ends the workflow run")`, a real billed run) in the `unit:`
  block — it is R7.0's live preflight and must stay outside the filter. Its `test()` string is
  spec-pinned; leave it exactly as written.
- **Verify (deviates from the default — this file is excluded from `test:unit` at file level, and
  its unfiltered run BILLS):**
  `cd template && npx vitest run tests/comparisonWorkflow.test.ts -t 'unit:'`
  A bare `npx vitest run tests/comparisonWorkflow.test.ts` would execute the live containment proof
  and **spend real money inside a zero-billed phase**. That run is R7.0's job, at the start of
  Phase 7, deliberately — see Phase 6's header.

> **P6.12 is split into P6.12a and P6.12b** along the module boundary the spec already draws
> (spec §1's module table: `evals/deliveryWorkflow.ts` and `evals/scorers.ts` are two rows, and
> `scorers.ts` imports the workflows' result types, not the reverse). One task bundling ~20
> exported symbols across ~900 spec lines behind a flat test list was the one task large enough to
> need its own plan. **Suffixes, not a renumber:** P6.13–P6.17 keep their numbers. Renumbering
> Phase 6 has twice left stale references in this plan (rounds 2 and 3), and the round-4 check
> that was supposed to catch it tested the wrong property — a renumbering is never a mechanical
> edit. The suffix costs nothing and touches no other reference.
>
> **Both tasks put their zero-network cases inside `describe("unit: …")`** so Phase 6's
> `-t 'unit:'` command actually executes them (see the phase header). The live cases
> (`runScoreboard()`, `test_benign_task_pass_rate_bar`) stay **outside** the wrapper.

### P6.12a — `evals/deliveryWorkflow.ts` (workflows + their schemas)
- **Spec:** §12 | **Depends on** (imports only, each naming the symbol — §8's pinned row):
  **P6.8** (`normalizeDelivery`), **P6.3** (`FirmProfileSchema` for `requestContextSchema`;
  `StageBResponseSchema` for `stageBWorkflow`'s output). Plus `@mastra/core` and zod.
- **NOT `agents/*` — this module imports no agent, and an earlier draft of this task claimed it
  did.** §8's row is explicit: *"**Not** `agents/*` — `deliveryStep` resolves its agent through
  `mastra.getAgent(inputData.arm …)`, never a direct import"* (the spec's own F6 correction). The
  draft's `Depends on: P6.10 (guardedAgent)` was a **false import dependency**, and it broke this
  plan's own rule that every dependency claim names the imported symbol — `guardedAgent` is not
  imported, so no symbol could be named. It would have forced a subagent to serialize behind
  P6.10 for no reason, and invited an `import { guardedAgent }` that §8 forbids.
- **Sequencing, stated separately from dependency:** `deliveryStep` resolves its agent by **name at
  run time**, so a *live* run needs the arm registered in `mastra.ts` (**P6.14**) — but this task's
  tests **stub the agent**, so nothing here waits on P6.10 or P6.14. The live path is Phase 9's.
- **Creates:** `DeliveryInputSchema` (incl. **`recordId`** — the ground truth rides in the workflow
  input, because a scorer's `run` carries `runId`/`input`/`output`/`requestContext` and **no
  `groundTruth`**), `DeliveryResultSchema`, `DeliveryResult` (type), `deliveryStep`,
  `deliveryWorkflow`, `stageBStep`, `stageBWorkflow`.
- **Tests first** (in `evals.test.ts`, inside `describe("unit: delivery workflow")`):
  **`test_delivery_result_shape`** — `deliveryStep` normalizes a **stubbed** tripwire and a
  **stubbed** clean call into `DeliveryResultSchema` (via `normalizeDelivery`, P6.8 — not an
  inlined `try/catch`), carrying `recordId` through unchanged. No network: the agent is stubbed.
- **Verify:** `cd template && npx vitest run tests/evals.test.ts -t 'unit: delivery workflow'`
- **Why this half is first:** `scorers.ts` imports `DeliveryResult`; building the scorers against a
  type that does not yet exist is the same "imports a thing four tasks early" defect the P6.9/P6.10
  ordering already fixed.

### P6.12b — `evals/scorers.ts` (the scorers + the scoreboard)
- **Spec:** §12, §4 | **Depends on** (imports only, each naming the symbol — §8's pinned row):
  **P6.12a** (`DeliveryInput`, `DeliveryResult` types — §8's row for this module *does* list
  `evals/deliveryWorkflow.ts`, unlike P6.12a's non-dependency on agents), **P6.6** (`runJudge`),
  **P6.4** (**`type JudgeResult` only** — see below), **P6.7** (`narrowObligationsPure`), **P6.3**
  (`predictsStageAViolation`, `FirmProfileSchema`). Plus `@mastra/core/evals`.
- **From `judge/contract.ts` this module imports the TYPE and nothing else.** An earlier draft of
  this task listed `GuardrailVerdictSchema`, `parseAndValidateVerdicts` and `JudgeObligationInput`
  — **overstating the dependency and contradicting §8's architecture.** The spec is explicit at
  the parallel call site (§9b, spec:4195–4198): *"`import type { JudgeResult } from
  "../judge/contract"; // TYPE only — no runtime dependency` … **NOT imported**: judgeAgent …
  **nor `GuardrailVerdictSchema`/`renderJudgeUserPrompt`/`parseAndValidateVerdicts` — all three
  moved inside `runJudge`** when `callJudge.ts` was extracted."* This module calls `runJudge`
  (spec:5108) for exactly the same reason, so the same rule binds it: parsing and schema
  enforcement happen **inside** `runJudge`, and a second import of the parser here would be the
  "two paths to one contract" defect §8's extraction exists to prevent. `JudgeResult` is needed
  because `scoreMissedObligation(record, judgeResult, obligationId)` annotates it.
  **`parseAndValidateVerdicts` is imported by `scorers.test.ts`'s `judge_cases` block (P6.4) —
  that is a *test* dependency, not an `evals/scorers.ts` import.** Do not conflate the two.
  > **Spec issue (callout, not a divergence) — `asJudgeObligation` is called by two modules and
  > exported by none.** `evals/scorers.ts` calls `asJudgeObligation(record)` (spec:5108) and
  > `processors/carverGuardrail.ts` calls it too (spec:4211); §9b describes its behaviour
  > (spec:4225 — builds `{id, title, key_requirements, objective}`, never `citation`, never
  > `baseline_failures`). But **no module row in §1 exports it**, and it cannot simply be added to
  > `judge/contract.ts`, whose imports are pinned as **"zod only"** while the adapter takes a
  > `ClearedRecord` (owned by `schema.ts`). A subagent has nowhere to put it and would most likely
  > define it **twice** — and since it builds the judge's obligation input, two drifting copies
  > would feed the guarded arm and the eval subtly different questions while every test still
  > passed. **The plan's reading, pinned so the two consumers agree:** `judge/contract.ts` owns
  > `asJudgeObligation`, and its import row becomes *"zod, plus `type ClearedRecord` from
  > `schema.ts`"* — a **type-only** import that adds no runtime edge and cannot re-form the
  > `judgeAgent ↔ scorers` cycle (`schema.ts` imports zod only), so the leaf property that
  > actually matters is preserved. **P6.4 creates it; P6.9 and P6.12b import it.** If the
  > orchestrator prefers a different home, it is a one-line change to §1 — but it needs *a* home.
  > **Spec issue (callout, not a divergence) — `evals/scorers.ts`'s pinned import list omits
  > `scenario/prompts.ts`, which its own exports call.** `runArm` calls
  > `buildStageAPrompt(record)` (spec:5276) and `runStageBEval` calls `buildStageBPrompt(r)`
  > (spec:5427); both are exports of **this** module, and both builders live in
  > `scenario/prompts.ts`. But §8's import row for `evals/scorers.ts` lists
  > `@mastra/core/evals`, `evals/deliveryWorkflow.ts`, `judge/callJudge.ts`, `judge/contract.ts`,
  > `schema.ts`, `firmProfile.ts`, `tools/narrowObligations.ts` — and **not** `scenario/prompts.ts`.
  > This looks like the spec's own F8 fix stopping one line short: F8 correctly removed
  > `scenario/prompts.ts` from **`deliveryWorkflow.ts`**'s row (those workflows receive
  > already-built prompt strings) and noted the builders are "called by `evals/scorers.ts`" —
  > without adding it to *that* module's row. It is the same authoritative-site-fixed,
  > restatement-stale defect this plan keeps catching, one level up. **This task imports
  > `scenario/prompts.ts`**; a subagent following the pinned list literally would call two
  > unimported functions. No cycle is introduced (`prompts.ts` is generated and imports only
  > `schema.ts`), so this is an omission to confirm, not a design change.
- **Creates:** **`scoreCitation(stageB, record)`, `scoreComplianceDate(stageB, record, citation)`,
  `scoreMissedObligation(record, judgeResult, obligationId)`** — the **TS ports of §4**
  (spec §1:4010 puts them in this module; an earlier draft of this plan omitted all three from its
  Creates list even though `scorers.test.ts`'s golden groups target them); `recordFor`,
  `extractScores`, `LedgerRow`, `DeliveryScorer` (the union — **including `blockedScorer`**), the
  five scorers (`unsafeShipScorer`, `blockedScorer`, `guardedCatchScorer`, `benignPassScorer`,
  `stageBScorer` — all `createScorer<In, Out>` **generics**, not a `type:` object),
  `partitionForGuardedEval`, `stageBRecords`, `runArm`, `runNegativeControl`, `runStageBEval`,
  `runScoreboard` (**no parameter**).
- **Call order is a §4 contract, not a style choice:** `scoreCitation` MUST run before
  `scoreComplianceDate`, which takes the resulting `CitationScore` (spec:5154–5155).
- **Tests first — golden parity.** This task **APPENDS to `scorers.test.ts`** (created by P6.3,
  appended by P6.4 — §0's chain **P6.3 → P6.4 → P6.12b**), adding the last two groups and **only**
  their imports, under the convention P6.3 pinned — **one `describe` named exactly after the
  group**: `describe("citation_date_cases", …)` → `scoreCitation` / `scoreComplianceDate`;
  `describe("obligation_cases", …)` → `scoreMissedObligation` (**every** case, minus those marked
  `prep_only`). **No `unit:` wrapper here** — `scorers.test.ts` is **not** excluded from
  `test:unit` (only `evals.test.ts` and `comparisonWorkflow.test.ts` are), so it needs no selector
  to be reachable and an earlier draft's `describe("unit: scorers")` was both unnecessary and a
  collision with the group-naming convention. The `unit:` wrapper exists **solely** for the two
  file-level-excluded files; do not spread it to files that do not need it.
  Both groups are asserted in `prep/`'s `test_scoring.py` against the Python originals (P1.x) and
  here against these TS ports, over the **same** `scoring_golden.json` — that identity is the
  parity claim. (`judge_cases` → `parseAndValidateVerdicts` is P6.4; `stage_a_predicate_cases` →
  `predictsStageAViolation` is P6.3 — see those tasks.)
- **Tests first — harness invariants** (`evals.test.ts`, inside `describe("unit: scoreboard")`,
  all zero-network):
  **`test_partition_is_disjoint_and_total`** (over the real vendored set — the spec pins this at
  **zero API calls**);
  **`test_knowledge_only_records_are_never_sent_to_the_guarded_agent`** (stub-target run);
  **`test_delivery_scorer_union_is_complete`**;
  **`test_catch_scored_on_membership_not_display_record`** (stubbed tripwire, §9c's attribution
  fix); **`test_empty_scored_partition_fails_loudly`** (fixture cleared set of citation/date-only
  records ⇒ the scoreboard **fails** with the named message, never a vacuous pass);
  **`test_blanket_guardrail_fails_the_suite`** — a stubbed always-aborting processor **passes** the
  unsafe-ship and catch assertions and **fails** the benign-task assertion.
- **Live cases — OUTSIDE the `unit:` wrapper, first run in Phase 9:**
  `test_benign_task_pass_rate_bar`; `test_paired_row_uses_one_scorer`;
  `test_ledger_matches_runEvals_averages`; `test_negative_control_contract`'s `runScoreboard()`
  material-gap assertion. Each depends on a real `runScoreboard()` run and cannot be made free.
- **Verify:** `cd template && npx vitest run tests/scorers.test.ts && npx vitest run tests/evals.test.ts -t 'unit: scoreboard'`
- **`test_blanket_guardrail_fails_the_suite` is the point of the whole harness.** Without the
  negative control, a processor whose enforcement is `abort()` — no narrowing, no judge, no Carver
  data — scores a perfect 0.00 unsafe-ship and 1.00 catch and passes everything else. **Never
  weaken or skip it** (rubric 23). It is deliberately in the **free** tier: the guard on the guard
  must be provable without spending $23.

### P6.13 — `prompts.test.ts` — fair-test discipline, template-side
- **Spec:** §8 | **Tests:** **`test_prompt_builders_never_leak`** — over **every** vendored record
  and **both** builders (`buildStageAPrompt`, `buildStageBPrompt`), assert no `title` / `objective`
  / `what_changed` / `why_it_matters` / `citation.url` / `citation.name` / `compliance_date` /
  `key_requirements` substring appears in the prompt, and that a `DOMAIN_BUCKETS` phrase does;
  **`buckets_golden.json` parity** — `INDUSTRY_TAG_TO_BUCKET` reproduces every case prep's
  `test_scenarios.py` asserts, including the unmapped-tag default.
- **Why this is its own task and not a footnote:** §3's MUST-NOT list and
  `test_task_instance_excludes_leaked_fields` existed **only in `prep/`**. But
  `buildStageAPrompt(record: ClearedRecord)` receives an object carrying every field §3 forbids,
  and it drives the demo, the containment test and **both eval arms**. Nothing structural stopped a
  future edit from interpolating `record.title` "to make the prompt more realistic" and silently
  leaking the answer into the question the whole experiment turns on. The rule binds both halves or
  it binds neither.
- **Sequencing:** `scenario/prompts.ts` is **generated by P6.2** from synthetic data, so this
  test's subject is real generated source from the first run — never a hand-authored stand-in.
  P8.2 regenerates it from real data and this same test reruns unchanged.

### P6.14 — `report/`, `mastra.ts`, `scripts/`
- **Spec:** §11, §8 | **Creates:** `report/reportTemplate.ts` (`renderReportHtml`, `escapeHtml` —
  inline CSS, **no external refs**), `report/generateHtmlReport.ts`; `mastra.ts` — `import
  "dotenv/config"` **first**, then `new Mastra({agents: {baselineAgent, guardedAgent, judgeAgent},
  workflows: {compareWorkflow, deliveryWorkflow, stageBWorkflow}})`; `scripts/demo.ts` (with the
  non-blocking diagnosis + exit codes 1/2), `scripts/printPrompt.ts`
- **Tests first:** `mastra.test.ts::test_all_targets_are_registered` — all three workflows resolve
  and each eval workflow's step can reach `mastra.getAgent("baselineAgent")`.
  **All three workflows must be registered or `npm test` cannot run at all** — the eval steps call
  `mastra.getAgent(...)`, and an unregistered workflow's step context has no `mastra`.
  In `evals.test.ts`, inside `describe("unit: report", …)` — all four fed a **synthetic**
  `ComparisonReport`, zero network: `test("report has no external references", …)`;
  `test("report escapes draft text", …)`; `test("report renders both real branch outputs and the
  matching record", …)`; and the generator rejecting a non-blocked result.
- **Those three `test()` strings are pinned verbatim by the spec** (§11) — reproduce them exactly.
  The `describe("unit: report")` wrapper is what makes them reachable by Phase 6's `-t 'unit:'`
  command **without renaming a single one**; that is precisely why the selector is a wrapper rather
  than a name prefix (see §0 / Phase 6's header). This task adds only its own `describe` and
  imports — `evals.test.ts`'s scoreboard cases belong to P6.12b.
- **Verify (deviates from the default — one task, two test files):**
  `cd template && npx vitest run tests/mastra.test.ts && npx vitest run tests/evals.test.ts -t 'unit: report'`
  The second command is filtered because `evals.test.ts` is **excluded from `test:unit` at file
  level** and its unfiltered run would reach P6.12b's **billing** scoreboard cases. A bare
  `npx vitest run tests/evals.test.ts` here would **spend real money in a zero-billed phase.**
- **Also update:** `template/README.md` (**P6.16**) states that Studio lists three workflows and that
  `compareWorkflow` is the demo — the Studio-clutter cost of registration is paid in docs.

### P6.15 — Cross-language drift checks (now that `config.ts` exists)
- **Spec:** §8, §2 | **Creates (in `prep/tests/test_config.py`):**
  `test_model_id_matches_template`, `test_model_cutoff_matches_template`,
  `test_judge_confidence_floor_matches_template`, `test_reasoning_effort_matches_template` — each
  reads `template/src/config.ts` **as text**, regex-extracts the literal, and asserts equality with
  prep's constant.
- **Why text and never import:** the two halves are different languages and different venvs (goal
  #1/#13). Reading as text is the only safe crossing, and it is the same trick `prep/templates/`
  uses to *write* those files.
- **This is a PYTHON task living in Phase 6, and that has two consequences a subagent must not
  miss.** It is the one task in the phase that writes no TypeScript:
  1. **RC** — see the substep definition in §0. **Not optional.** The repo convention names the
     *Python* reviewer/expert pair and this task changes a Python test file; the "template tasks
     have no RC" carve-out in §0 does **not** reach it. An earlier draft let it fall through that
     gap purely because of the phase it sits in.
  2. **Verify (deviates from the default — wrong language, wrong directory):**
     `cd prep && .venv/bin/python -m pytest tests/test_config.py -q`
     The template default (`npx vitest run tests/config.test.ts`) would point at a **different,
     already-existing file in the other half of the repo** — it resolves, it passes, and it proves
     nothing about this task. That is precisely the "the reference names a real thing, just the
     wrong one" failure this plan has hit twice.
- **Also update:** this task edits `prep/tests/test_config.py`, which **P1.1 created**. Add the
  four drift cases; do not re-author the file.

### P6.16 — `template/README.md`
- **Spec:** §11 | **Creates:** the required content §11 tables: quickstart (`npm install` → key in
  `.env` → `npm run dev`); **baseline model & cutoff verbatim** (`openai/gpt-5.6-sol`, cutoff
  `2026-02-16`, snapshot `2026-07-11`, every record `2026-03-01`+) **and why** (the flagship,
  deliberately the *strongest* baseline); provider-swap (one line in `config.ts`, and the cutoff
  must be **re-derived**); the Studio path (workflow → run form → prompt from `npm run demo:prompt`
  → `requestContext.firmProfile`); the scoreboard; dataset provenance; **severity-ladder
  coverage** — plainly, that every shipped record is `impact_label == "high"` by construction so
  `medium`/`low` are **unit-test-only**; known limitations.
- **Tests first:** `README.test.ts` — the file exists and contains the literal `MODEL_ID`,
  `MODEL_CUTOFF`, `SNAPSHOT_DATE` read as text from `config.ts`. **Goal #9's disclosure is a test
  failure when it drifts**, not a documentation aspiration.
- **Why `template/` needs its own README:** goal #9 names *the template README* twice, and goal #1
  requires `template/` be trivially extractable. A root-level README does not travel with an
  extraction — Mastra would receive a repo with zero setup instructions and **zero model/cutoff
  disclosure**, destroying what goal #9 calls the defence against the cherry-picking charge.

### P6.17 — Phase gate
- **Verify — all four, and the second is not optional:**
  1. `cd template && npm run test:unit` — green.
  2. `cd template && npx vitest run tests/evals.test.ts tests/comparisonWorkflow.test.ts -t 'unit:'`
     — green, **and reports a non-zero number of passed tests**. `test:unit` **excludes both these
     files at file level** (spec:3936), so command 1 does not execute a single case in either; this
     command is the only thing that does before Phase 9. A `0 passed` result means the `unit:`
     wrappers are missing or misnamed — that is a **red gate**, not a pass. See the Phase 6 header
     for why this exists.
  3. `cd template && npm run typecheck` — green.
  4. `grep -rn "carver-showcase\|\.\./prep\|mastra_prep" template/src template/tests` — **no hits**
     (goal #9 / success criterion 9).
- **Zero-bill check (closing P5.2's vacuum for these two files):** run command 2 with
  `OPENAI_API_KEY` **unset**. It must still pass. Every case inside a `unit:` wrapper is stubbed or
  pure by construction, so an unset key is a real test of that claim rather than a restatement of
  it. If it fails, a billing case has been wrapped by mistake — fix the wrapper, never the check.

---

# PHASE 7 — THE REAL RUN *(the money step — the FIRST phase that bills at all)*

**Bills: ~$17 typical, ~$93.5 worst case, against the hard $120 ceiling — plus R7.0's ~$0.01.**
Phases 0–6 bill **nothing**. This phase is where every billed call in the project lives.

### R7.0 — **Live tripwire-containment preflight** *(the first billed call in the project)*
- **Spec:** §10, rubric 15, goal #8's KNOWN RISK
- **Runs:** `cd template && npx vitest run tests/comparisonWorkflow.test.ts` against the
  **synthetic** fixture, with a real `OPENAI_API_KEY`. **~2 calls, < $0.01.**
- **Placed here, not in Phase 6:** Phase 6 is a **zero-billed** phase and a single live call
  inside it would make that label false — and a phase whose billing guarantee is "zero, except
  one" is a guarantee nobody can check. It is placed at the **start** of Phase 7, before any
  corpus probing, so it is still the *first* thing money is spent on and still resolves goal #8's
  risk before the expensive step depends on it.
- **Preconditions:** **P6.17**'s zero-cost phase gate green (`npm run test:unit` + `typecheck`).
- **Asserts:** `result.status === "success"` (**not** `"tripwire"` — the core assertion);
  `guarded.blocked === true`; non-empty `blocked_draft`/`reason`; `processorId ===
  "carver-guardrail"`; `violated_obligation_ids` **contains** the trigger id; `record.id ===
  violated_obligation_ids[0]`; `baseline.text` truthy (**the baseline branch completed
  independently**).
- **If a tripwire DOES propagate and kill the run: STOP.** Report and go no further into Phase 7.
  §10's dual-layer containment exists to prevent exactly this; if it does not hold, the comparison
  workflow's shape is wrong, success criteria #2/#4/#5 are unreachable, and **no amount of corpus
  probing fixes it**. Spending ~$17 on curation before knowing this would be spending it on a
  demo that cannot exist. That is the whole reason this is the preflight and not a Phase-9 check.

### R7.1 — Preconditions (all must hold; do not start otherwise)
- `cd prep && .venv/bin/python -m pytest tests/ -q` — **entire suite green**.
- `cd template && npm run test:unit` and `npm run typecheck` — green.
- **R7.0 passed** — the live containment preflight. Do not proceed past a propagating tripwire.
- `prep/.env` has a real `OPENAI_API_KEY`.
- `config.yaml` reviewed: `total_spend_ceiling_usd: 120.0`, `probe_max_records: 400`,
  `target_set_size: 200`, `scenario_trial_size: 30`.
- `../carver-showcase/data/annotations.jsonl` exists and is **read-only** to us
  (`annotations_path` resolves — the **four**-`../` value, P0.3).

### R7.3 — The scenario trial + curation
- **Command:** `cd prep && .venv/bin/python run_prep.py` (from `prep/`)
- **Expected:** ~$17 typical. `decide_scenario` runs first (60 records, ~$2.30), writes
  `scenario_decision.json`, locks a winner; curation then sweeps up to 400 **fresh** records
  (`exclude_ids` = the winner's trial ids — §7's winner's-curse fix).
- **What "good" looks like:** `stop_reason` is `target_reached` or `sweep_cap` (**not**
  `spend_ceiling`); survivors ≥ ~20; `stage_a_survivor_counts[winner] ≥ 1`; the spend line well
  under $120.
- **What to watch for, and what each means:**
  | Observation | Meaning | Action |
  |---|---|---|
  | `stop_reason="spend_ceiling"` | The ceiling bound before the sweep finished | Report actual spend; do **not** raise the ceiling reflexively — check first whether a prompt is pathologically long |
  | `BudgetPoisoned` | An estimate assumption broke (§3) | **Stop.** Report. This is the ledger saying it can no longer predict; it is a bug, not a budget event |
  | `outcome="insufficient_trial"` | The trial could not support a winner | Report per §7's Goal-issue callout. **Do not** apply the A tie-break to a trial that did not happen |
  | `stage_a_survivor_counts[winner] == 0` | Valid dataset, **no live demo possible** | Escalate — `emit_template_config` will raise in P8.2 |

### R7.4 — Human review *(BLOCKING, MANUAL, cannot be automated)*
- **Command:** `cd prep && .venv/bin/python run_prep.py --review`
- **Per record:** read the evidence beside the ground truth; pick the citation if >1 resolved;
  answer §6's **three** sub-attestations when `missed_obligation` is among the modes — (a) the
  obligation applies to the fictional firm/activity, (b) the requested artifact is capable of
  violating it, (c) the judge's cited omission is material. **Any one `False` → the CLI refuses to
  offer `approve`.**
- **Output:** `data/cleared/` — tracked, and the deliverable.
- **This gate cannot be delegated to a subagent, a model, or a batch flag.** Goal: *human review
  IS the publication gate; there is no automated substitute.*

### R7.5 — **THE YIELD ESCALATION GATE — HARD STOP** 🛑
- **Trigger:** fewer than **~20 records** survive review.
- **Do:** **STOP. Report to the user.** State the true number, the `stop_reason`, the survivor
  breakdown by evidence mode, and the spend.
- **NEVER, under any circumstance:** loosen `candidate_cutoff_date`; admit `medium`/`low` impact;
  admit noisy `update_type`s; accept unresolvable citations; waive human review; weaken the failure
  bar; or synthesize/paraphrase records. Each is a named row in §6's anti-padding table, each is
  mechanically blocked, and **each block exists precisely because this moment is when someone would
  want to remove it.**
- **The correct outcome of a thin yield is a smaller set and an honest report.** Goal #11: *"A
  30-record set of proven baseline failures is a success; a 200-record set padded with records the
  baseline handles competently is a failure."* If fewer than ~20 survive, that is **the** condition
  the user asked to be woken for — the user decides, not the implementer.
- **This gate is enforced by P8.0's command, not by this prose.** See immediately below.

---

# PHASE 8 — Vendor + generate
**Bills: NO.** Vendoring is a copy; generation is string templating; neither calls a model.
**Ends green when** P8.3 has committed and `npm run test:unit` + the `-t 'unit:'` command are both
green against the **real** cleared set.

### P8.0 — 🛑 **YIELD GATE — a command that fails, not a checkbox** *(blocks P8.1)*
- **Why this task exists.** R7.4's human-review requirement is backed by real code: no
  batch-approve path, `review.py` the only writer of `data/cleared/`. **R7.5 had no analogue** — it
  was a paragraph. Nothing in P8.1 (a `cp`) or P8.2 inspected the survivor count, so an executing
  agent treating plan steps as a checklist to narrate-and-continue could vendor a single-digit
  cleared set with **nothing in the code stopping it**. This project's standard is *"mechanically
  blocked, not merely asserted"* — every row of spec §6's anti-padding table meets it. The one gate
  the user explicitly asked to be woken for must too.
- **ONE command, both paths. There is no second variant to invent.** An earlier draft stopped at
  a bare count check and then told the executing agent to *"re-run this task with the threshold the
  user authorised"* — which is not a mechanism: it asks a subagent to author a modified command,
  and **any** lowered literal would pass, acknowledgment or not, matching this cleared set or not.
  That is the same "narrate the checklist and continue" hole G2 exists to close, one level in. The
  gate below is a **single literal command** that decides both cases itself. It reads the
  acknowledgment; the acknowledgment does not read it.
  ```
  cd prep && .venv/bin/python -c "
  import json, hashlib, pathlib, re, sys

  records = json.load(open('data/cleared/cleared_records.json'))
  n = len(records)
  digest = hashlib.sha256(
      json.dumps(records, sort_keys=True, separators=(',', ':')).encode()
  ).hexdigest()[:12]
  print(f'cleared survivors: {n}   set-digest: {digest}')

  if n >= 20:
      print('PASS: yield at or above the bar.')
      sys.exit(0)

  p = pathlib.Path('data/results/yield-decision.md')
  if not p.exists():
      print(f'STOP: {n} survivors (< 20) and no recorded decision at {p}.')
      sys.exit(3)

  text = p.read_text()
  def field(name):
      m = re.search(rf'^{name}:[ \t]*(.+?)[ \t]*\$', text, re.M)
      return m.group(1).strip() if m else None

  problems = []
  if field('survivor_count') != str(n):
      problems.append(f'survivor_count must be {n} (the CURRENT count)')
  if field('set_digest') != digest:
      problems.append(f'set_digest must be {digest} (THIS cleared set)')
  if field('decision') != 'PROCEED':
      problems.append('decision must be exactly PROCEED')
  if not (field('user_instruction') or ''):
      problems.append('user_instruction must quote the user verbatim')
  if problems:
      print(f'STOP: {p} does not authorise this set:')
      for x in problems: print(f'  - {x}')
      sys.exit(3)

  print(f'PASS: {n} survivors, shipping smaller by recorded user decision.')
  sys.exit(0)"
  ```
- **Verify:** the command exits **0**. **Exit 3 is a HARD STOP** — not a warning, not a number to
  note in a summary and move past. On exit 3 the executing agent **must not run P8.1**; it stops
  and reports to the user per R7.5.
- **The acknowledgment artifact** — `prep/data/results/yield-decision.md`, written **only** after
  the user has been shown the true number and has answered. Four fields are machine-checked; the
  rest is the honest report R7.5 requires:
  ```
  survivor_count: 14
  set_digest: 9f2a1c4e8b70
  decision: PROCEED
  user_instruction: "Ship the 14. Do not loosen anything."
  ```
  plus, in prose: the `stop_reason`, the survivor breakdown by evidence mode, and the spend.
- **Why it is bound to the count AND a digest of the set itself.** A decision authorises **one
  specific dataset**, not a threshold forever. The digest means a re-curated or edited set voids
  the acknowledgment automatically — you cannot approve 14 records, re-run the probe, and have a
  different 14 sail through on the old note. A count-only check would let exactly that happen.
- **This command was executed against fixtures before being written down**, not reasoned about:
  14 records + no artifact → **exit 3**; artifact with a stale `survivor_count: 99` → **exit 3**;
  correct artifact → **exit 0**; **14 records replaced by a *different* 14 → exit 3 on
  `set_digest`** (the claim above, tested rather than asserted); 25 records + no artifact →
  **exit 0**; boundary **20 → 0**, **19 → 3**. The `\$` in the regex is escaped for the shell's
  double quotes and reaches Python as an end-of-line anchor — verified, since that is exactly the
  kind of quoting bug that would silently make every field read `None` and turn the gate into a
  rubber stamp that always exits 3.
- **There is no flag, env var or config key that silences this gate**, and none may be added —
  that would be the "waiving human review" row of §6's anti-padding table in a new costume. The
  only unlock is an artifact recording a real human answer about a real dataset.
- **The unlock does not license loosening anything.** Goal #11 still governs the *response*: ship
  smaller, report honestly, **never** loosen the filter, weaken the bar, admit `medium`/`low`, or
  pad. The gate's job is to make sure a human sees the number — **not** to make the number bigger.
  `PROCEED` means "ship the smaller set"; there is no value of this artifact that means "go get
  more records by relaxing a rule".
- **Threshold note (deliberate, not sloppy):** R7.5 says "fewer than **~20**". The command pins
  the tilde to a literal `20`, because a command cannot branch on an approximation. Exactly 20
  proceeds; 19 escalates. The literal is **fixed in the plan** and is not a per-run parameter — a
  thin run is unlocked by the acknowledgment path above, never by editing this number.

### P8.1 — Vendor the real cleared set *(blocked by P8.0)*
- **Do:** copy `prep/data/cleared/cleared_records.json` → `template/src/data/cleared-set.json`,
  replacing the synthetic fixture.
- **Verify:** `cd template && npx vitest run tests/schema.test.ts` — **every real record parses**
  against `ClearedRecordSchema`. This is the swap-safety mechanism Fact 2 promised; if it fails, the
  seam drifted and P8 stops here.

### P8.2 — Generate the scenario-locked constants
- **Command:** `cd prep && .venv/bin/python run_prep.py --emit-template-config`
- **Writes (as ordinary committed `template/` source):** `config.ts`'s `DEMO_TRIGGER_RECORD_ID`,
  `firmProfile.ts`'s `DEMO_FIRM_PROFILE`, `baselineAgent.ts`'s `SCENARIO_PERSONA_INSTRUCTIONS`,
  `scenario/prompts.ts` in full.
- **Raises rather than emits** if the winner has **no** `predicts_stage_a_violation` record (→ R7.5's
  sibling escalation) or if no candidate survives narrowing.
- **Also update:** nothing to unskip — **P6.2 already ran this generator** against synthetic data,
  so every generated-constant test has been green since Phase 6. This task changes the generator's
  *input* (synthetic → real reviewed records), not its existence, and the **same** tests rerun
  unchanged. That symmetry is the point: if P8.2's output breaks a test, the break is in the data
  or the review, not in a code path first exercised here.
- **Verify:** `cd template && npm run test:unit` — green, nothing skipped, and
  `git diff template/src/scenario/prompts.ts` shows the regenerated file differs from P6.2's only
  in scenario-derived content.

### P8.3 — Commit
- Work branch, meaningful message. **Never push.**

---

# PHASE 9 — Definition of Done: the 9 success criteria, one by one

Each criterion → the exact command or observation that proves it. Nothing here is "should work".

| # | Success criterion (goal) | Proof |
|---|---|---|
| **1** | Fresh clone of `template/`, only `OPENAI_API_KEY`: `npm install && npm run dev` serves Studio on `:4111`, no further setup | `git clone` the extracted `template/` to a **fresh directory**, `cp .env.example .env` + real key, `npm install && npm run dev`; `curl -sf localhost:4111 > /dev/null` exits 0. (`import "dotenv/config"` is what makes this true across `mastra dev`/`tsx`/`vitest` alike, rather than relying on each runner's undocumented `.env` handling.) |
| **2** | A scripted prompt makes the guarded agent produce a **visible tripwire block in Studio**, citing a real Carver obligation with a **resolvable** URL and a real compliance date | `npm run demo:prompt` → paste into Studio's `compareWorkflow` run form → set `requestContext.firmProfile` (schema-driven form) → Run. **Observe:** `guardedStep` tripwires in the graph; the trace names the matched record; the citation URL opens. |
| **3** | The same prompt against the unguarded baseline produces **visibly non-compliant output** | Same run: `draftStep`'s branch completes and its draft is delivered. `npm test`'s baseline unsafe-ship rate `>= 0.8` is the quantitative form. |
| **4** | The comparison workflow appears in Studio with **no Studio-specific code**, and one run executes **both** branches to completion — guarded blocked, baseline not. A tripwire must **never** abort the run | `npx vitest run tests/comparisonWorkflow.test.ts` — asserts `status === "success"` (**not** `"tripwire"`), `guarded.blocked === true`, `baseline.text` truthy. Plus the Studio graph showing both branches. |
| **5** | `npm run demo` emits a **self-contained** HTML report, opening with **no server and no network** | `npm run demo` → `output/demo-report.html`. **Disconnect the network**, open via `file://`. Both drafts side by side, the obligation, a clickable citation, the compliance date. `evals.test.ts::test("report has no external references")` is the mechanical form. |
| **6** | `npm test` prints a baseline-vs-guarded scoreboard with a **material, reproducible gap** | `cd template && npm test` (**~609 calls / ~$23**; worst case 1,260 — this **includes the guardrail's own verdict call**). Prints the pinned table: baseline unsafe-ship `>= 0.8` vs guarded `<= 0.1` over the **same** `partition.scored`; block rate `0.00` vs `~0.96`; catch `>= 0.9`; **benign-task pass rate `>= 0.9`** over the n=30 control. |
| **7** | Every record in `data/cleared/` carries recorded failure evidence **and** a human sign-off | `cd prep && .venv/bin/python run_prep.py --verify-cleared` → `validate_cleared_record` over every file; `test_schema.py::test_no_unreviewed_records_in_cleared_dir`. |
| **8** | Every citation URL in the cleared set resolves | **Proved from the clearing-time record, not by a new crawler.** (a) §2's URL gate is the **first** thing `probe_and_score_one` does and it is unconditional: a record with no `"resolves"` ground-truth URL is returned disqualified **before any LLM call**, so an unresolvable citation cannot reach curation. (b) `citation.url` is the reviewer's pick **from `resolving_urls`** — the list of URLs that returned `"resolves"` at gate time (§5) — and `record_signoff` has no parameter capable of substituting another. (c) `--verify-cleared` re-checks the **structure**: every shipped record parses, carries `citation.url` matching a recorded resolving URL, and has an `"approved"` sign-off. (d) Optional human spot-check: open a sample of citations from the report. **§14 is explicit that citations are validated at clearing time only and that post-clearing re-validation is NOT automated in v1** — a stale link found later is a manual fix, and `template/README.md` (P6.16) states that limitation. |
| **9** | `template/` has **zero** references to `prep/`, `carver-showcase`, or anything else in this repo | `grep -rn "carver-showcase\|\.\./prep\|mastra_prep\|carver_showcase" template/` → **no hits**. Then the real proof: copy `template/` to `/tmp`, `npm install && npm run test:unit` → green. |

### P9.1 — Learnings
- **Do:** add the non-obvious findings to `docs/LESSONS.md` (repo convention). Candidates already
  known from the spec stage: the `probe → curate → probe` cycle and the `ast` guard; reservations
  leaking on failed calls; `runEvals` handing agent scorers a message array, not the generate
  result; OpenAI accepting but not enforcing `minimum`/`maximum`.
- **Do:** confirm the root README's Projects table row from P0.1 is still accurate.

---

## Stress scenarios (spec §14) — every one assigned to a task

§14 specifies eleven stress scenarios and a behavior for each. None may be dropped; this table is
the assignment, so a reader can check coverage without trusting that they are scattered somewhere
above.

| §14 scenario | Task | Test that proves it |
|---|---|---|
| Empty narrowing result | **P6.9** | `carverGuardrail.test.ts` — a firm profile matching zero records → `processOutputResult` returns the draft **unchanged**, no `abort()`, **no `auditWriter.write()`** (the audit log means "a violation occurred"; a narrowing miss is not one) |
| Tripwire in `.parallel()` | **P6.8** (stubs, free) + **R7.0** (live preflight) | `tripwireContainment.test.ts::test_both_tripwire_forms_normalize_identically`; `comparisonWorkflow.test.ts` asserts `status === "success"`, never `"tripwire"` |
| Unresolvable citation URL | **P1.6**, **P2.3**, **P4.1** | `test_urls.py` (the tri-state); `test_scoring.py` (`citation_fabricated` only on 404/410; `citation_unverifiable` otherwise); §6 drops a record if **no** URL resolves |
| Garbage/absent ground-truth compliance date | **P2.3** | `test_scoring.py` — unparseable/empty ground truth → `DateScore.not_applicable`, `is_failure=False`; the record is **not** excluded from candidacy, the dimension simply contributes no evidence |
| Malformed judge JSON | **P2.2** (prep), **P6.9** (template) | `test_judge.py` — retry once, then all-`"uncertain"`, **never** `"violation"`; `carverGuardrail.test.ts::test_judge_parse_failure_passes_through` — fail-open to pass-through, no exception escapes |
| Zero probe survivors | **P5.1**, **R7.5** | `run_prep.py` prints *"0 records survived — see goal #11: ship nothing rather than pad"* and exits **0** (an honest empty result, not an error) |
| Survivors exist but none carries Stage-A evidence | **P3.1**, **P8.2** | `stage_a_survivor_counts` surfaces it at *decision* time; `test_generate_template_config.py::test_raises_when_no_stage_a_evidence` — raises, writes nothing |
| A cleared record ranks outside its own profile's top 5 (`crowdedOut`) | **P3.2**, **P6.12b** | `test_trigger_skips_crowded_out_candidate`; `evals.test.ts::test_partition_is_disjoint_and_total` — reported as its own partition, never scored as a miss |
| Non-ASCII regulator names | **P1.9** | `test_schema.py` — a non-Latin regulator name round-trips (`ensure_ascii=False` throughout) |
| Duplicate records | **P1.4** | `test_candidates.py::test_duplicate_ids_deduped` — `filter_candidates` is the **sole** dedup layer; first occurrence in file order wins |
| A citation that dies between clearing and demo | **P6.16** | Out of scope for automated re-checking in v1 — no scheduled re-validation job. `template/README.md` states it as a known limitation (§14) |

## Risk / lever notes

**Cost levers, and what each actually does:**

| Lever | Effect | When to touch it |
|---|---|---|
| `probe_max_records` (400) | Linear on curation spend — the single biggest lever | Lower it for a shakeout. Raising it does **not** relax the filter, so it is safe — it just costs more |
| `scenario_trial_size` (30) | 2 arms × 3 calls each — ~$2.30 | Lower for a dry run only; below `scenario_trial_min` the trial returns no winner **by design** |
| `target_set_size` (200) | Early-stop: curation halts at the ceiling | May shrink freely; `load_settings()` **raises** above 200 (goal #11's ceiling) |
| `max_completion_tokens` (3,000/1,500/1,200) | Bounds the **reservation**, and the output half of real cost | Do not raise casually — it is the output term of every reservation |
| `total_spend_ceiling_usd` (120) | The hard wall | Lowering is always safe (stops earlier). Raising is a deliberate spend decision |

**Levers that are NOT levers** — mechanically blocked, and the block is the point:
`reasoning_effort` (code constant; `low` would weaken the baseline → more failures → bigger yield =
goal #9's named rigging mode), `candidate_cutoff_date` (derived from `MODEL_CUTOFF`),
`judge_confidence_floor` (≥0.7), `snapshot_date` (code constant), `price_*` (pinned floors).

**Known risks:**

| Risk | Resolution |
|---|---|
| **Tripwire propagates out of `.parallel()` and kills the run** (goal #8's KNOWN RISK) | Resolved **empirically**: stubs in **P6.6** (free, both forms pinned), then **R7.0**'s live preflight — the first billed call, before any corpus spend. Not assumed either way, not deferred to Phase 9 |
| Thin yield (<20 survivors) | **R7.5's hard stop.** Report; never pad |
| Winner has zero Stage-A evidence | Visible at *decision* time via `stage_a_survivor_counts`; `emit_template_config` raises in P8.2. A **user decision**, not an automatic scenario switch (§7's Goal issue) |
| A citation dies between clearing and demo | Out of scope for automated re-checking in v1; README states it (§14) |
| Real prompts render badly against real corpus prose | Covered **without spending**: `test_probe.py`'s leak battery and `prompts.test.ts` assert prompt *content* against real record fixtures, and `stratified_sample_sequence` is deterministic — so a bad render shows up in a stubbed test, not a billed one. Residual risk is accepted: it is the price of the one-late-run rule, and R7.3's `log()` progress line surfaces a pathological prompt within the first records |

---

## Spec issues found while planning

**None.** Every module, test, fixture, stress scenario and figure this plan schedules is stated in
the spec. Where this plan makes a choice, it is a **sequencing** choice it owns (which phase a
task lands in), never a design change — the spec is silent on execution order by construction,
which is what this stage is for.

Two things carried forward as **planned constraints**, not defects:
- The spec's own accepted **Goal issue** — every vendored record is `impact_label == "high"`, so
  goal #6's `medium`/`low` branches are **dead code against real data**. No task exercises them
  live; `carverGuardrail.test.ts` covers them with synthetic fixtures (**P6.9**) and
  `template/README.md` states the limitation (**P6.16**).
- §7's **Goal issue** — goal #10's scenario rule does not guarantee the winner can support success
  criterion #2. Handled by reporting (`stage_a_survivor_counts`) and a loud raise (P8.2), never by
  silently re-ranking scenarios.
