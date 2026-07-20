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

---

## 0. How to read this plan

**Task IDs are stable** (`P1.3`, `T6.2`) — dependency callouts and the parallelism map use them.
Every implementation task carries the same five fields, and none is optional:

| Field | Meaning |
|---|---|
| **Spec** | The section this task implements. If a task has no §, it is scaffolding. |
| **Creates** | Exact file paths and the exact function/class names, as spelled in the spec. |
| **Tests first** | The test file and the named cases to write **before** the implementation. |
| **Verify** | The literal command, and what output means "green". |
| **Also update** | **Every other place that states the same fact.** Non-negotiable — see below. |
| **RC** | The review/fix substep. Every **Python** task carries it. Defined once, immediately below. |

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
                                │            │                       → P6.11 workflows → P6.12 evals
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
- **Note:** in `tests/stubs.py`, importable — **not** `conftest.py` — avoiding the `tests/` package
  self-import trap documented in `docs/LESSONS.md`.
- **RC** — see the substep definition above. Not optional.

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
- **RC** — see the substep definition above. Not optional.

### P3.3 — Phase-3 aggregate review (additional to each task's RC substep)

---

# PHASE 4 — `review.py`, the clearance CLI

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

### P4.2 — Phase-4 aggregate review (additional to each task's RC substep)

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
     `cd template && npm run test:unit && npm run typecheck`.
     **If a suite passes with no key present, it made no calls.** That is the whole proof, it is
     mechanical, and it costs nothing — a test that secretly billed would fail here with an auth
     error rather than pass.
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
Phase 7's preflight. Ends green when `npm run test:unit` and `npm run typecheck` pass.

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
  `MAX_PROCESSOR_RETRIES` is **not exported**); `firmProfile.test.ts`.
- **No skips.** These cases pass in Phase 6 because **P6.2 ran the real generator** against
  synthetic data, so `DEMO_TRIGGER_RECORD_ID` and `SCENARIO_PERSONA_INSTRUCTIONS` are genuinely
  populated — by the same code path P8.2 will use on real data.

### P6.4 — `judge/contract.ts` **(leaf — zod only)**
- **Spec:** §8 | **Creates:** `JUDGE_SYSTEM_PROMPT`, `renderJudgeUserPrompt`,
  `GuardrailVerdictSchema` (**sole owner**; `confidence: z.number().min(0).max(1)`),
  `JudgeObligationInput`/`JudgeResult`, `parseAndValidateVerdicts`
- **Depends on:** zod only. **Never** an agent, **never** a scorer — that is the whole point of
  this module: it is the leaf that breaks the `judgeAgent ↔ scorers` cycle.
- **Tests first:** `scorers.test.ts`'s `judge_cases` group against `parseAndValidateVerdicts`
  (out-of-range confidence **discarded, not clamped**; duplicate id → first wins; omitted →
  `"uncertain"`; hallucinated → dropped; malformed → retry → all-uncertain).

### P6.5 — `agents/sharedConfig.ts` + `baselineAgent` + `judgeAgent`
- **Spec:** §8 | **Creates:** `SHARED_AGENT_CONFIG` (`instructions`/`model`/`defaultOptions` — the
  ONE object both compared agents spread); `baselineAgent` (`...SHARED_AGENT_CONFIG`);
  `judgeAgent` (`instructions: JUDGE_SYSTEM_PROMPT`, `defaultOptions: GENERATION_CONFIG`)
- **Depends on:** `config.ts` (`MODEL_ID`, `GENERATION_CONFIG`), `judge/contract.ts`
  (`JUDGE_SYSTEM_PROMPT` — one-way).
- **NOT `guardedAgent`** — it imports `CarverGuardrail`, which does not exist until **P6.9**. It is
  built in **P6.10**; see the ordering note there.

### P6.6 — `judge/callJudge.ts`
- **Spec:** §8 | **Creates:** `runJudge(obligations, draftText)` — the **only** place `judgeAgent`
  is ever invoked; the single implementation of §4's retry-once-then-all-uncertain degradation
  (including the out-of-range-confidence throw the `[0,1]` Zod bound introduces).
- **Depends on:** `judge/contract.ts` **and** `agents/judgeAgent.ts` — **both must already exist**
  (P6.4, P6.5). An earlier draft built this before `judgeAgent`, which is a module importing a
  file that does not exist yet.
- **Tests first:** a stubbed `judgeAgent` throwing on both attempts → `runJudge` returns the
  all-`"uncertain"` fallback rather than propagating (the fail-open contract §9b depends on).

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
- **Depends on:** **P6.6** (`runJudge`), **P6.7** (`narrowObligationsPure`), P6.3 (`schema.ts`).
  (`normalizeDelivery`, P6.8, is used by P6.11's step — not by the processor itself.)
  **Not** `agents/judgeAgent.ts` — the guardrail delegates through `callJudge.ts`, the only
  permitted path to that agent.

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
- **Tests first (now that both arms exist):** `carverGuardrail.test.ts` —
  **`test_requestContext_cannot_reach_either_prompt`**: `SHARED_AGENT_CONFIG.instructions`/`.model`
  are **static values, not functions** (a dynamic config function is the only documented path from
  `requestContext` into a prompt); via the public accessors, `getInstructions({requestContext})`
  returns the unchanged constant and does **not** contain the profile's country/sector;
  `listTools()` is empty; the two arms resolve identically.
  **`test_guarded_agent_has_no_processor_retries`** — `maxProcessorRetries` undefined.
- **Why this is a controlled-experiment guard, not a lint:** if `requestContext` reached the
  prompt, the guarded arm would draft *knowing the firm's jurisdiction and sector* while the
  baseline drafts blind — goal #9's explicitly fatal case, and it would **look like success**.

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
- **Tests first:** the negative battery in `comparisonWorkflow.test.ts` (all non-billing, run now):
  duplicate id; an id that is not a vendored record; **`test_known_but_not_narrowed_id_rejected`**;
  ids out of rank order; **`test_forged_record_metadata_is_ignored`** (a forged title/citation
  yields the **vendored** record's real values).

### P6.12 — `evals/deliveryWorkflow.ts` + `evals/scorers.ts`
- **Spec:** §12 | **Creates:** `DeliveryInputSchema` (incl. **`recordId`** — the ground truth rides
  in the workflow input, because a scorer's `run` carries `runId`/`input`/`output`/`requestContext`
  and **no `groundTruth`**), `DeliveryResultSchema`, `deliveryStep`, `deliveryWorkflow`,
  `stageBStep`, `stageBWorkflow`; `recordFor`, `extractScores`, `LedgerRow`, `DeliveryScorer`
  (the union — **including `blockedScorer`**), the five scorers (`unsafeShipScorer`,
  `blockedScorer`, `guardedCatchScorer`, `benignPassScorer`, `stageBScorer` — all
  `createScorer<In, Out>` **generics**, not a `type:` object), `partitionForGuardedEval`,
  `stageBRecords`, `runArm`, `runNegativeControl`, `runStageBEval`, `runScoreboard` (**no
  parameter**)
- **Tests first:** `evals.test.ts`'s non-billing cases —
  **`test_partition_is_disjoint_and_total`**;
  **`test_knowledge_only_records_are_never_sent_to_the_guarded_agent`**;
  **`test_paired_row_uses_one_scorer`** (both arms carry `ships-violating-draft`, and their ledgers'
  `recordId` sequences are identical element-for-element);
  **`test_ledger_matches_runEvals_averages`** (`|mean − avg| < 1e-9` — a **tolerance**, since
  concurrent items make summation order non-deterministic);
  **`test_negative_control_contract`** (`length === 30`, deterministic, benign, in-scenario,
  narrowing non-empty); **`test_delivery_scorer_union_is_complete`**;
  **`test_blanket_guardrail_fails_the_suite`** — a stubbed always-aborting processor **passes** the
  unsafe-ship and catch assertions and **fails** the benign-task assertion.
- **That last test is the point of the whole harness.** Without the negative control, a processor
  whose enforcement is `abort()` — no narrowing, no judge, no Carver data — scores a perfect 0.00
  unsafe-ship and 1.00 catch and passes everything else. **Never weaken or skip it** (rubric 23).

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
  `evals.test.ts` — report has no external refs; rejects a non-blocked result; escapes injected
  `<script>`; renders **both** real branch outputs plus the matching record.
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
- **Verify:** `cd template && npm run test:unit` — green. `npm run typecheck` — green.
  `grep -rn "carver-showcase\|\.\./prep\|mastra_prep" template/src template/tests` — **no hits**
  (goal #9 / success criterion 9).

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

---

# PHASE 8 — Vendor + generate

### P8.1 — Vendor the real cleared set
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
| A cleared record ranks outside its own profile's top 5 (`crowdedOut`) | **P3.2**, **P6.12** | `test_trigger_skips_crowded_out_candidate`; `evals.test.ts::test_partition_is_disjoint_and_total` — reported as its own partition, never scored as a miss |
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
