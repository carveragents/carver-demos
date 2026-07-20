# STATUS — where this project is, and how to pick it up

**Last updated:** 2026-07-20 · **Phases 0–6 complete**

## Ported from carver-adhoc (2026-07-20)

This project was built in the `carver-adhoc` repo on branch `feat-mastra-guardrail`
(head `5b24b07`) and moved here, where it belongs alongside the other demos. The move
was a flat copy — the 35 original commits were not replayed. The decision record that
justifies the code is `goal.md` + `docs/orchestrator-decisions.md` (D1–D30), not the
commit log, so nothing load-bearing was lost.

**What changed in the move — one thing, and it matters:**

- `prep/config.yaml`'s `annotations_path` went from **four** `../` to **three**. The old
  path walked `prep → mastra-guardrail → projects → carver-adhoc → repos/carver`; the new
  layout drops the `projects/` level. Four `../` now resolves outside `repos/carver`
  entirely and fails on the first documented command. Verified: three levels resolves to
  the real 1.83 GB corpus. `tests/test_config.py`'s `BASE_CONFIG` mirror was updated to match.

The `.tandem/mastra-guardrail-v2/` workspace came across too (spec, plan, 13 rounds).
Its files still say `projects/mastra-guardrail` — deliberately. The spec is frozen by
doctrine and the round files are a historical record; rewriting paths inside them would
falsify what was actually written at the time. Read those paths as "wherever the project
lives now."

---

## The one-line state

**Everything up to the paid run is built and green: 800 tests (642 Python, 158 TypeScript), zero
billed API calls, $0 spent.** The demo app runs end to end — against a **synthetic 6-record
fixture**, because the real dataset requires Phase 7.

## The one thing blocking progress

**`OPENAI_API_KEY` in `mastra-guardrail/prep/.env`.** It is the only secret this project
reads (no Carver key, no Anthropic key, no Mastra token — see `goal.md` #9). Phase 7 is the first
phase that bills anything, budgeted ~$17 against a hard ceiling that fails closed.

## Read these first, in this order

1. **`goal.md`** — THE AUTHORITY. 14 locked decisions, 9 hard constraints, 9 success criteria.
2. **`docs/orchestrator-decisions.md`** — **D1–D30.** Binding addendum; **overrides the spec**.
   Precedence: `goal.md` → this file → spec → plan.
3. `.tandem/mastra-guardrail-v2/stages/01-spec/artifact.md` — the spec (approved, **frozen**,
   refine-capped; it cannot be edited, which is why the rulings file exists).
4. `.tandem/mastra-guardrail-v2/stages/02-plan/artifact.md` — the plan.

## Verify the state in 30 seconds

```bash
cd mastra-guardrail/prep     && .venv/bin/python -m pytest tests/ -q   # 642 passed
cd mastra-guardrail/template && npx tsc --noEmit && npm test           # 158 passed
```

---

## What's built

| | Phase | State |
|---|---|---|
| ✅ | **1–3** — `prep/` pipeline | 14 modules: reader, candidates, extract, urls, sampling, scenarios, schema, budget, openai_client, config, logging_, probe, judge, scoring, curate, scenario_decision, generate_template_config |
| ✅ | **4–5** — review gate + entrypoint | `review.py` (the publication gate, sole writer of `data/cleared/`), `run_prep.py` (3 argv branches) |
| ✅ | **6** — the Mastra template | agents, `narrowObligations` tool, `CarverGuardrail`, tripwire containment, compare + delivery workflows, 5 scorers, HTML report, `mastra.ts`, demo scripts, README, 5 cross-language drift checks, phase gate |

## What's left

| | Phase | Needs |
|---|---|---|
| ⬜ | **7** — THE REAL RUN | **`OPENAI_API_KEY`.** R7.0 live preflight (~$0.01) → R7.3 the run (~$17) → R7.4 human review via `run_prep.py --review` → R7.5 escalation gate |
| ⬜ | **8** — vendor the real set | Re-run the SAME generator over real data (P8.2). **P8.0 is the yield gate** — see below. **P8.1 must update `template/README.md`'s Status section**, whose central claim inverts at that moment |
| ⬜ | **9** — the 9 success criteria | |

### The yield gate (P8.0) — the user's own stop condition, made real

`n >= 20` survivors → proceed. Otherwise it reads `data/results/yield-decision.md` and exits 0 **only
if** `survivor_count` matches, `set_digest` matches THIS set, `decision: PROCEED`, and
`user_instruction` is non-empty. **Exit 3 = HARD STOP.** Verified against 16 cases by execution, not
by reading — an early version passed on `user_instruction: ""` because the regex captured the two
quote characters as a truthy string.

---

## Traps that will bite you if you don't know them

- **`data/cleared/` IS EMPTY.** The vendored `template/src/data/cleared-set.json` is the **synthetic**
  6-record fixture. Anything claiming the demo runs on real human-reviewed records is **false today**
  and becomes true at P8.1. The README's Status section says so; keep it honest.
- **`record["id"]` vs `record["artifact_id"]`** — the flat pipeline shape (`extract_record`) uses
  **`artifact_id`**; the published `ClearedRecord` uses **`id`**. The spec confuses them repeatedly.
  Four agents hit this.
- **`evidence_modes` carries SCORER literals, not shipped names** — the obligation failure is
  **`"violation"`**; `"missed_obligation"` is only its rename in the shipped record
  (`SCORE_OUTCOME_TO_FAILURE_MODE`). Testing the shipped name against a scorer literal made a counter
  always-zero once already.
- **A correct guardrail block prints a red `[WORKFLOW] Error executing step …` + stack** (D26/D28).
  Mastra wraps output processors in a workflow. **The success path looks like a crash.** Know this
  before demoing.
- **`new RequestContext({ firmProfile })` compiles nowhere** (D28/D29). Typed form for a
  schema-bearing workflow's `run.start()`; `RequestContext<unknown>` for Agent accessors / `runEvals`.
- **Never hand-edit generated files** — `src/scenario/prompts.ts`, and the generated declarations in
  `config.ts` / `firmProfile.ts` / `baselineAgent.ts`. Fix the `.tmpl` in `prep/templates/` and
  regenerate, or P8.2's re-run silently reverts you.

## The lesson this project keeps re-teaching

**Every real defect here — roughly 30 of them — was found by COMPILING or RUNNING. None by reading**,
across 13 spec rounds, 2 stress tests, and many grounded reviews. The recurring shape is *a mechanism
that reads correct and does nothing*: a `<` guard vs NaN; a leak audit keyed on recycled `id()`s; an
anti-rigging test asserting on a private field (passes on the rigged agent); a phase gate that greps a
substring where the property is imports (red on correct code). **Two agents refused an orchestrator
instruction of mine on evidence and were right both times.** Run things.

## Pace

Per the user: **speed to demo, done beats perfect** (D21). Report at **phase boundaries** only. But
D25 records that D21 over-cut once — the human-review gate is a goal constraint, not ceremony. The
test: does it protect **the demo's claim** or **the user's money**? Keep it. Does it protect against a
hypothetical a walkthrough would surface anyway? Cut it.
