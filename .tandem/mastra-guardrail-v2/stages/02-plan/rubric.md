# Rubric — Stage 02 Plan: Carver × Mastra Compliance Guardrail

APPROVED only when ALL criteria hold; otherwise CHANGES_REQUESTED with numbered, actionable
issues.

## Coverage
1. Every module in the approved spec's layout (§1) is produced by some task — both halves.
   `prep/`: `config`, `reader`, `extract`, `candidates`, `urls`, `sampling`, `scenarios`,
   `budget`, `probe`, `judge`, `scoring`, `openai_client`, `curate`, `scenario_decision`,
   `schema`, `review`, `generate_template_config`, `run_prep.py`, all six `prompts/*.md`,
   `config.yaml`, `requirements*.txt`. `template/`: `config.ts`, `schema.ts`, `firmProfile.ts`,
   `judge/contract.ts`, `judge/callJudge.ts`, all three agents, `carverGuardrail.ts`,
   `narrowObligations.ts`, `compareWorkflow.ts`, `scenario/prompts.ts`, the report pair,
   `evals/scorers.ts`, `mastra.ts`, `scripts/demo.ts`, `package.json`, `tsconfig.json`,
   `vitest.config.ts`. Plus the project-local `.gitignore` and `README.md`.
2. Every test file in the spec's layout is assigned to a task. No spec test is dropped —
   including `test_imports.py::test_no_circular_imports` (§1's `ast` DAG check) and
   `comparisonWorkflow.test.ts` (§10's tripwire-containment proof).
3. Every stress scenario in spec §14 is assigned to a task.
4. The duplicated golden fixtures (`scoring_golden.json`, `narrowing_golden.json` — the
   cross-language lockstep mechanism) are created and used on BOTH sides.

## The three sequencing facts (this plan is right or wrong here)
5. **Stub-first is explicit and enforced.** The plan states which phases make ZERO billed API
   calls and which bill, and says how a developer verifies no accidental spend. Every `prep/`
   module is proven against stub clients before the real run.
6. **`template/` is sequenced BEFORE the real probe run**, built against a synthetic
   schema-conforming fixture, with the schema contract test as the swap-safety mechanism. A
   plan that blocks template work on the real cleared set is REJECTED — it burns the expensive
   step before its consumer is proven.
7. **The real run is ONE late phase**, with preconditions (all tests green, budget configured,
   key present), the exact command, expected cost, what to watch, and what "good" looks like.
8. **The <20-survivor escalation gate is an explicit, named, hard-stop step** — not a footnote.
   It stops and reports to the user. It NEVER loosens the filter, weakens the failure bar, or
   pads. (Goal #11; the one condition the user asked to be woken for.)
9. **Human review (spec §6) appears as a blocking manual checkpoint**, correctly placed, and is
   not automated away.

## Executability
10. Tasks are ordered so dependencies are built before dependents, respecting the spec's module
    DAG (§1: LEAF → L1 → L2 → L3 → L4). Each phase ends in a verifiable state with the exact
    verification command(s) and success criteria given.
11. TDD is concrete: each implementation task names the tests to write first and the spec
    section/functions it implements.
12. Every documented Python command runs via `prep/.venv/bin/python` from `prep/` (goal #13).
    No system Python. No sibling venv. No `carver_showcase` import.
13. Genuinely independent tracks are marked as parallelizable (this plan may be executed by
    parallel subagents); false parallelism (tasks that actually share state or order) is not
    claimed.

## Fidelity
14. The plan implements the spec **verbatim** — introduces NO new design decisions and
    contradicts nothing in it. Any suspected spec defect is an explicit "spec issue" callout,
    not a silent divergence.
15. Function/class names, file paths, config keys, prompt placeholders, and schemas in the plan
    match the spec exactly.
16. Honors every locked decision in `goal.md` — spot-check: model is `openai/gpt-5.6-sol` from
    ONE shared constant; no Anthropic anywhere; `OPENAI_API_KEY` the only secret; no RAG/vector
    store; no custom frontend/server/SPA; commit-as-you-go on a work branch but NEVER push;
    `../carver-showcase` read-only.

## Quality
17. Tasks are small, independently verifiable, and unambiguous. No TBDs, placeholders, or
    "figure this out at implementation time".
18. Cost levers are named with their effect (sample size, early-stop, `max_completion_tokens`,
    scenario-trial size), and the shakeout keeps real spend minimal.
19. The known tripwire-propagation risk (goal #8) is scheduled for empirical resolution early
    in the template phase — not assumed either way, not left to the end.
20. Repo conventions honored: python-code-reviewer after each Python change with python-expert
    fixing findings; pinned deps; extracted prompts; `data/cleared/` tracked and
    `data/scratch/` gitignored; no secrets in code; a row added to the root README's Projects
    table and learnings to `docs/LESSONS.md`.

## Definition of done
21. A whole-project Definition of Done maps **one-to-one** to the goal's 9 success criteria,
    each with the exact command or observation that proves it — including: fresh-clone
    `npm install && npm run dev` on `OPENAI_API_KEY` alone; a visible tripwire citing a
    resolvable URL; both workflow branches completing in one Studio graph with no run abort;
    `npm run demo` producing server-less network-less HTML from a real run; `npm test` showing
    a material baseline-vs-guarded gap; every cleared record carrying failure evidence + human
    sign-off; every citation resolving; `template/` referencing nothing else in the repo.

---

## Carried forward from the spec stage (additional; this run only)

22. **The corrected cost figures are used, not the superseded ones.** `npm test` ≈ 609 calls /
    ~$23 typical (worst case 1,260 calls) — *including* the guardrail's own verdict call;
    `prep/` ≈ $17 typical, ≈ $93.5 worst case against the hard $120 ceiling. A plan quoting the
    old ~456-call / ~$17 `npm test` figure, or omitting the verdict call, is REJECTED.
23. **The n=30 negative control is scheduled and never weakened.** It is the only evidence the
    guardrail discriminates rather than blankets; `test_blanket_guardrail_fails_the_suite` must be
    assigned to a task.
24. **Restatement discipline.** Any task that changes a figure, an owner, or an interface must
    name **where else that fact is stated** and require those updated in the same task. This
    project's recurring defect is fixing the authoritative site and missing its restatements — it
    occurred three times in the spec stage alone.
25. **`medium`/`low` severity coverage is planned as unit-test-only**, per the spec's accepted Goal
    issue (every vendored record is `impact_label == "high"` by construction). No task attempts to
    exercise those branches live; the README task states the limitation.
