# Stage 02 — Plan: Carver × Mastra Compliance Guardrail

Produce a **step-by-step, test-driven implementation plan** that an engineer (or a fleet of
subagents) can execute to build exactly the system in the approved spec. Write it to
`artifact.md`.

## Authoritative inputs

- **The approved spec** — the contract; build precisely this: `stages/01-spec/artifact.md`
  (6,002 lines / ~62k words; read it in chunks — it far exceeds a single read)
- **Overall goal** (still binding, incl. all 14 locked decisions + 9 success criteria): `goal.md`
- Sibling project whose conventions to mirror: `projects/gics-topic-tagging/`
  (venv layout, `config.yaml`, `prompts/`, stub-client tests, `run_pipeline.py` entrypoint,
  results-vs-scratch split)
- Repo conventions: `CLAUDE.md`, `docs/LESSONS.md`, `docs/development/conventions.md`

## The three sequencing facts that shape this plan

Get these right and the plan is sound; get them wrong and it wastes money or blocks.

1. **The real probe run is the only expensive, irreversible step.** Everything else — both
   halves, every module, every test — must be built and proven with **stubbed clients and
   synthetic fixtures, making ZERO billed calls**. The real run happens **once, late**, when
   everything around it is already green. Plan for that ordering explicitly.
2. **`template/` does NOT have to wait for the real cleared set.** It vendors
   `src/data/cleared-set.json`, but every template module can be built and tested against a
   **synthetic fixture** conforming to the same Zod schema. Sequencing the template *before*
   the real run de-risks it and means the money is spent once, against a proven consumer.
   The real set is swapped in afterwards; the schema contract test (`schema.test.ts`) is what
   makes that swap safe.
3. **There are two blocking human checkpoints**, and the plan must show them as such:
   - **Human review** (spec §6) — the clearance gate. Manual, blocking, cannot be automated.
   - **The yield escalation gate** — if the curation run yields **fewer than ~20 survivors**,
     STOP and report to the user. Per goal #11, ship a smaller set; **NEVER** loosen the
     filter, weaken the failure bar, or pad. This is the one condition the user asked to be
     woken for. Make it an explicit, named step with a hard stop — not a footnote.

## What the plan MUST contain

1. **Ordered, incremental tasks grouped into phases.** Each phase ends in a working,
   verifiable state. Build bottom-up so each module is testable before its dependents exist.
   Respect the spec's module DAG (§1): `LEAF → LEVEL 1 → LEVEL 2 → LEVEL 3 → LEVEL 4`. A
   suggested order (adjust only with justification):
   - Phase 0: scaffolding — dirs, `prep/.venv` (`python3.10 -m venv`), pinned
     `requirements*.txt`, `config.yaml`, project-local `.gitignore`, `package.json`,
     `tsconfig.json`, `.env.example` files.
   - Phase 1: `prep/` LEAF modules + tests — `config`, `reader`, `extract`, `candidates`,
     `urls`, `sampling`, `scenarios`, `schema`, `budget`, `openai_client`. Include
     `test_imports.py::test_no_circular_imports` (the `ast` DAG check, §1) early — it is
     cheap and guards the whole build.
   - Phase 2: `prep/` LEVEL 1–2 + tests — `probe`, `judge`, `scoring`, `curate`. All against
     stub clients. This is where the reservation lifecycle (§3) and the failure bar (§4) get
     proven.
   - Phase 3: `prep/` LEVEL 3 + tests — `scenario_decision`, `generate_template_config`.
   - Phase 4: `review.py` + tests — the clearance CLI.
   - Phase 5: `run_prep.py` + tests — the whole pipeline, stubbed, end-to-end, still zero
     billed calls.
   - Phase 6: `template/` — every module against a **synthetic** cleared-set fixture:
     schema, tools, processor, workflow, report, evals, agents, Mastra wiring. Includes the
     tripwire-containment proof (§10) and the Studio smoke check.
   - Phase 7: **THE REAL RUN** — scenario trial → curation → human review. The money step and
     the escalation gate.
   - Phase 8: vendor the real cleared set, generate the scenario-locked template constants
     (§7), wire the demo trigger.
   - Phase 9: end-to-end verification against the goal's **9 success criteria**, one by one.
2. **TDD discipline, concretely.** For each module, name the tests to write FIRST (referencing
   the spec's test tables and stress scenarios, §14), and the minimal implementation that makes
   them pass. Each task names the exact functions/classes it creates and the **spec section it
   implements**.
3. **Verification per phase** — the exact commands (e.g. `prep/.venv/bin/python -m pytest tests/test_budget.py -q`,
   `cd template && npx vitest run`) and the observable success criteria. Every documented
   Python command runs through `prep/.venv/bin/python`, from `prep/` (goal #13).
4. **The zero-billed-call guarantee.** State explicitly which phases make NO API calls (0–6)
   and which do (7, and `evals.test.ts` in 9). Say how a developer verifies they haven't
   accidentally billed anything.
5. **The real-run procedure (Phase 7)** in full: preconditions (all tests green, budget
   configured, key present), the exact command, what to watch, the expected cost, what "good"
   looks like, the human-review loop, and the **<20-survivor escalation stop**.
6. **Dependency / order callouts** — which tasks block which; what can be parallelized (this
   plan may be executed by parallel subagents, so mark genuinely independent tracks).
7. **Risk / lever notes** — the cost levers (sample size, early-stop, `max_completion_tokens`,
   the scenario trial's size); how to keep real-API spend minimal during the shakeout; the
   known tripwire-propagation risk (goal #8) and when it gets resolved empirically.
8. **Definition of done** for the whole project, mapped **one-to-one** to the goal's 9 success
   criteria. Each criterion → the exact command/observation that proves it.

## Constraints

- **The plan implements the spec verbatim.** Introduce NO new design decisions and contradict
  nothing in the spec. If you find a spec defect, raise it as an explicit **"spec issue"**
  callout rather than silently diverging.
- Keep tasks small enough to implement and verify independently.
- Honor repo conventions: TDD; right-sized models per task; run the **python-code-reviewer**
  agent after each Python change and have the **python-expert** fix findings; project
  self-contained under `projects/`; pinned deps; extracted prompts; no secrets in code;
  `data/cleared/` tracked, `data/scratch/` gitignored.
- **Commit as you go on a work branch; NEVER push** (goal, hard constraints).
- `../carver-showcase` is **strictly read-only**.
- No placeholders, no TBDs, no ambiguous steps.

---

## Carried forward from the spec stage — read this before planning

`01-spec` took **13 rounds and 3 refinement cycles** (2 orchestrator stress-tests, 6 independent
grounded readers) to reach APPROVED. What that produced, and what it means for your plan:

**The spec is unusually hardened. Trust it, and implement it verbatim.** It survived: a real
circular import (`probe → curate → probe`); leaked budget reservations on failed calls; a
`settle()` that spent its hold before validating usage; a scoreboard where a guardrail blocking
100% of everything would have scored 1.0; a "paired" row comparing a violation rate against a
block rate; `Zod.parse(undefined)` throwing on every workflow run; and `resolve_url`'s fail-closed
rule manufacturing fabrication evidence out of link rot. All closed with mechanisms and tests.

**Three facts the plan must respect, learned the hard way:**

1. **The eval harness bills real money and is not free to run.** Corrected figures: `npm test` is
   ~**609 calls / ~$23** typical (worst case 1,260 calls) — this *includes* the guardrail's own
   verdict call, which an earlier draft omitted. `prep/`'s full run is ~**$17** typical, ~**$93.5**
   worst case against a hard, proof-backed **$120** ceiling. Plan the shakeout so these are paid
   **once**, late, deliberately.
2. **The negative control is n=30 and load-bearing.** It is the only thing proving the guardrail
   discriminates rather than blankets — `test_blanket_guardrail_fails_the_suite` exists precisely
   to keep that true. Never plan a step that weakens or skips it.
3. **The recurring defect class in this project is "fix the authoritative site, miss its
   restatements."** It surfaced three times (stale `{ compareWorkflow }` constructors; §15's stale
   call count; `isTripWireError`'s orphaned owner row). When a plan task changes a figure, an
   owner, or an interface, it must say **where else that fact is stated** and require those updated
   in the same task. Do not let a task close with the codebase saying two things.

**The spec's own accepted Goal issue** (its opening callout): goal #3's `impact_label == "high"`
filter means every vendored record is `high`, so goal #6's `medium`/`low` severity branches are
**dead code against real data** — unit-test-only. The plan must not schedule a task that tries to
exercise them live, and the README task must state this rather than implying the demo exercises
the full ladder.
