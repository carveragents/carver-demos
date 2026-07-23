# Stage 01 — Spec: Carver × Mastra Compliance Guardrail

Produce a **complete, implementation-ready specification** for the v1 system described in
the goal. The spec is the contract the plan (stage 02) and the implementation will follow.
Write it to `artifact.md`.

## Authoritative inputs (read these first — paths relative to the carver-adhoc worktree root)

- **The goal** (the brief; every locked decision in it is binding): `goal.md` (also at
  `projects/mastra-guardrail/goal.md`)
- **Annotation corpus** (read-only, ~1.8 GB, one JSON object per line):
  `../carver-showcase/data/annotations.jsonl`
- **Normalized column contract + probe-confirmed nested field paths** (mirror these paths;
  do NOT re-derive them by guessing): `../carver-showcase/carver_showcase/schema.py`
- **Curation reference** (how the showcase drops `update_type` noise):
  `../carver-showcase/carver_showcase/curate.py`
- **Topic catalog** (1,070 regulatory bodies + GICS/Carver-Gov taxonomy):
  `../carver-showcase/data/topic_catalog.csv`
- **Sibling project conventions to mirror** (venv layout, config.yaml, prompts/, tests,
  results-vs-scratch split): `projects/gics-topic-tagging/` — its `README.md`,
  `config.yaml`, `docs/output_schema.md`
- Repo conventions: `CLAUDE.md`, `docs/LESSONS.md`, `docs/development/conventions.md`

## Confirmed decisions (from `goal.md` — do NOT relitigate; spec them precisely)

All 14 locked decisions and 9 hard constraints in `goal.md` are binding. The load-bearing ones:

- **Two halves:** `prep/` (Python 3.10, own `.venv`, never ships) + `template/` (TypeScript,
  self-contained, vendored data, extractable to its own repo, zero references back).
- **Model = `openai/gpt-5.6-sol`** (cutoff **2026-02-16**), one shared pinned constant.
  **No Anthropic API, ever.** `OPENAI_API_KEY` is the only secret.
- **Candidate filter** = published **2026-03-01+** · actionable `update_type` ·
  `impact_label == "high"` · valid parseable date · non-empty `key_requirements` ·
  ≥1 resolvable `reg_references` URL. **Measured pool: 8,260.**
- **Dataset = measured baseline failure only.** Filter is a floor (never loosened); set size
  (50–200) is a ceiling (freely reduced). Never pad.
- **Score deterministically wherever the check is deterministic.** LLM judge only for
  irreducibly fuzzy checks.
- **Guardrail = Mastra `outputProcessor`**, 3 stages: deterministic narrow → LLM verdict →
  enforce. **Severity from Carver's `impact_label`**: high → `abort()`, medium → annotate,
  low → pass.
- **No RAG, no vector store, no embeddings.** Canned JSON + deterministic filter tools.
- **Two surfaces:** Studio (mechanism, via a comparison workflow) + generated self-contained
  HTML report (contrast, via `npm run demo`). No custom frontend, no server, no SPA.
- **Scenario decided once by the probe** — (A) coding agent / EU AI Act + GDPR, or
  (B) marketing agent / financial promotions. Tie-break → A. Build one, never both.

## The spec MUST define, precisely and unambiguously

1. **Project layout & module responsibilities** — every file under
   `projects/mastra-guardrail/` (`prep/`, `template/`, `data/cleared/`, `data/scratch/`,
   `docs/`), plus `.gitignore`, `config.yaml`, `requirements*.txt`, `package.json`,
   `tsconfig.json`. For each module: public functions/exports (names + signatures + return
   types), purpose, dependencies.

2. **`prep/` — the carve.** Streaming reader over the 1.8 GB JSONL (never load it whole);
   the exact nested extraction paths (from `schema.py`); the candidate filter as testable
   predicates; how "resolvable URL" is checked (HTTP method, timeout, retry, cache, what
   counts as resolvable); how the 1442→2569 date rot and the `press release` noise are
   excluded **by construction**; determinism + seeding.

3. **The probe — THE HARD PART. Spec it in full.**
   - **Question generation:** exactly how a Carver record becomes a prompt that tests the
     baseline. This is load-bearing and must not be hand-waved. Define whether the probe
     tests *knowledge* (does the model know this obligation, its date, its citation?) or
     *drafting behavior* (does the model's draft violate it?) — or both, as distinct
     stages — and justify the choice against the goal's north star. Give the exact prompt
     template(s), every placeholder, and what is deliberately withheld so the test is fair.
   - **Fair-test discipline:** the probe must not leak the answer into the question. Spell
     out what the prompt may and may not contain.
   - **Sampling & cost control:** the pool is 8,260; the target is 50–200 survivors. The
     probe MUST sample and stop early, not sweep. Define the sampling strategy (stratified
     by what? seeded how?), the stop condition, the per-record and total call budget, and a
     hard spend ceiling with a documented estimated cost. **This is the one place the
     project can get expensive — treat it as a first-class requirement.**
   - **Determinism/reproducibility:** how a probe run is replayed; what is cached.

4. **Scoring — deterministic first.** For each failure mode, state the check and whether it
   needs a model:
   - *Fabricated citation* — extract citations/URLs from the baseline answer, check against
     the record's `reg_references`, resolve over HTTP. Deterministic. Define extraction
     precisely (a model naming a real regulation in prose without a URL is a different
     outcome from inventing a URL — say which counts as fabrication and why).
   - *Wrong compliance date* — compare against `metadata.critical_dates.compliance_date`.
     Deterministic. Define tolerance and how absent/garbage ground-truth dates are handled.
   - *Missed obligation* — irreducibly fuzzy → LLM judge. Define the judge prompt, its
     structured output schema, and how a judge disagreement/uncertainty resolves.
   - Define the **failure bar**: exactly what combination admits a record to the cleared set.
     A near-miss must NOT count (goal #11).

5. **The cleared-record schema** — the exact JSON shape vendored into `template/`. Every
   field, type, and provenance. Must carry: the Carver annotation subset the guardrail needs,
   the recorded **baseline-failure evidence**, the **human-review sign-off**, and the
   citation URLs. This is the seam between the halves — pin it exactly.

6. **Human review** — the clearance gate. What the reviewer is shown, what they attest to,
   how the sign-off is recorded in-band, and how an unreviewed record is made
   *impossible* to ship (not merely discouraged).

7. **Scenario decision procedure** — the exact, mechanical rule the probe applies to pick A
   or B, the evidence it records, where it is written down, and the A tie-break. Must be
   decidable without a human and must not stall.

8. **`template/` — Mastra wiring.** The `Mastra` instance; the baseline agent; the guarded
   agent; `outputProcessors` registration; the firm profile (where it lives — working memory
   vs `requestContext` — and its schema); the deterministic filter tools (`createTool`, Zod
   in/out schemas); the shared pinned-model config constant; `.env` handling; `package.json`
   scripts (`dev`, `demo`, `test`).

9. **The `CarverGuardrail` processor** — the full three-stage contract. Stage (a): the exact
   narrowing predicates and how "relevant to this firm" is decided. Stage (b): the verdict
   prompt + Zod schema. Stage (c): the `impact_label` → action mapping, the `abort()` call,
   the tripwire reason payload, and `onViolation` audit logging. Specify behavior when
   narrowing returns zero candidates.

10. **The comparison workflow** — `createStep`/`createWorkflow`/`.parallel()` shape, the
    input/output schemas, registration, and **the tripwire-containment contract**: the
    guarded step MUST catch its own tripwire and return a structured
    `{ blocked, reason, processorId, record }` so the run stays `success` and the baseline
    branch always completes (goal #8 KNOWN RISK; success criterion #4). Spec the verification
    that proves containment works.

11. **The HTML report** — `npm run demo`. The generator's inputs (a real run, never
    hand-authored), the exact output (self-contained, inline CSS, no external assets, no
    network, opens from `file://`), what it shows (both drafts, the Carver obligation, the
    clickable citation, the compliance date, **and the baseline model id + its cutoff**, per
    goal #9), and where it is written.

12. **The eval harness** — `runEvals()` + Vitest as `npm test`. Which scorers (the SAME ones
    the probe uses — goal #4, do not build two harnesses), the dataset, the baseline-vs-guarded
    comparison, and what is asserted. Specify how the scorers are shared across the
    Python/TypeScript seam, or justify precisely why they are reimplemented.

13. **Config schema** — every `config.yaml` key (type, default, effect) and every env var.

14. **Testing strategy** — pytest for `prep/` (stubbed OpenAI client; no key, no network in
    tests), Vitest for `template/`. Which pure functions are unit-tested. Concrete stress
    scenarios: empty narrowing result, tripwire in parallel, unresolvable URL, garbage/absent
    ground-truth date, malformed judge JSON, zero probe survivors, non-ASCII regulator names,
    duplicate records, a record whose citation dies between clearing and demo.

15. **Error handling, determinism & cost guarantees** across both halves.

## Constraints

- Faithful to every locked decision in `goal.md`. Where the goal is explicit, the spec
  restates it precisely; where the goal is silent, the spec decides and says so.
- Spec the *what* and the *interfaces*; leave step ordering and effort to stage 02 — but be
  concrete enough that two engineers would build the same thing.
- **No placeholders, no TBDs, no contradictions.**
- If you believe a goal decision is wrong, raise it as an explicit **"goal issue"** callout —
  do not silently diverge.
