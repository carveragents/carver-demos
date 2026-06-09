# Stage 02 — PLAN: phased implementation plan for the Carver Annotation Data Showcase

## What to produce (this stage)

A **dependency-ordered, phased implementation plan** that turns the APPROVED Stage 01 spec
(`stages/01-spec/artifact.md`) into a buildable sequence — ready to execute via subagent-driven,
**test-driven** development. This stage produces the BUILD SEQUENCE and the file-by-file +
test-by-test detail; it must NOT re-decide design (the spec owns architecture, the normalized
schema, the deterministic formulas/predicates/rules, and the app view inventories). Where the spec
is the source of truth, reference it — don't restate or change it.

Concretely, the plan must contain:

1. **Phase breakdown.** An ordered list of phases, each an independently-testable increment with
   explicit **dependencies**, the **files** it creates/edits (paths matching the spec's §9.4
   layout), the **functions/interfaces** it implements (from spec §3.1), the **tests** it adds
   (from spec §9.3, written BEFORE the implementation per TDD), and crisp **acceptance criteria**
   (how we verify the phase is done). Suggested spine (refine as needed, keep dependency order):
   - **Phase 0 — Data foundation (mostly DONE; formalize).** The stratified snapshot
     `data/annotations.jsonl` (58,982 records: Finance 40,000 / Data protection 10,132 / Medical
     Devices 8,850) and `data/topic_categories.csv` already exist via `tools/pull_stratified.py`
     (direct Artifacts API + catalog, no SDK/LLM). This phase ADDS the still-missing
     `tools/pull_topic_catalog.py` → `data/topic_catalog.csv` (all 1,071 institutions, per spec G4)
     and documents the one-time pull commands. State clearly what already exists vs. what to build;
     do NOT re-pull what's present.
   - **Phase 1 — `config.py` + `schema.py`** (constants + the normalized column contract).
   - **Phase 2 — `ingest.py` + `normalize.py`** (+ tests): streaming load, empties→NA, flags/counts,
     date parsing, category + institution join from the catalog CSVs.
   - **Phase 3 — `load.py` (parquet build/cache) + `metrics.py`** (+ tests): coverage matrix, score/
     confidence distributions, breadth, volume-over-time, historical-depth metrics (spec G5).
   - **Phase 4 — `richness.py` + `quality.py`** (+ tests): richness score & highlight reel; quality
     predicates, anomaly rules, cleanup queue.
   - **Phase 5 — shared app components** (`apps/components/filters.py`, `render.py`).
   - **Phase 6 — `apps/gallery.py`** (external; all spec §6 views incl. institutions view G4 +
     historical-depth KPIs G5).
   - **Phase 7 — `apps/cockpit.py`** (internal; all spec §7 views).
   - **Phase 8 — wiring & verification**: `requirements.txt`, README run instructions, run both apps
     (`streamlit run …`), smoke-verify each view loads over the real snapshot, perf sanity.
   (Merge/split phases if it improves testability or dependency clarity — but justify.)

2. **File-by-file manifest.** Every file to create/edit with a one-line purpose, grouped by phase,
   matching spec §9.4. Include `tests/` files.

3. **Test-by-test list (TDD).** For each pipeline module, the concrete unit tests to write first
   (cases from spec §9.3 — e.g. empties→NA, `n_actionable_lanes` over 7 lanes, richness bounds &
   monotonicity, each predicate/anomaly rule firing on a crafted row, `apply_filters` conjunction,
   `ingest.pull_*` with httpx stubbed). Name the fixtures/strategy (tiny crafted frames; HTTP
   stubbed — never hit the live API in tests).

4. **Execution notes for subagent-driven TDD.** For each phase, the right-sized model guidance
   (mechanical vs. complex), the review gate (python-code-reviewer after each change; python-expert
   fixes), and the verification command(s) that prove the phase done. Note worktree/venv specifics
   (Python 3.12 `.venv/`, `streamlit run apps/gallery.py` / `apps/cockpit.py`).

5. **Risks / sequencing checks.** Call out anything that could bite (e.g. parquet build time over
   443 MB JSONL; choropleth needs ISO-2→name/ISO-3 mapping; category join is left-join with
   measured population; `topic_catalog.csv` must exist before the institutions view). Each with a
   concrete mitigation already chosen — no open questions.

## Inputs (read these)
- `stages/01-spec/artifact.md` — the APPROVED design (carry it forward; do not change it).
- `goal.md` — the overall brief + locked decisions + constraints.
- Existing artifacts on disk to account for: `data/annotations.jsonl` (58,982 stratified records),
  `data/topic_categories.csv`, `data/coverage_snapshot.md`, and `tools/` (`pull_stratified.py`,
  `pull_annotations.py`, `probe_api.py`, `coverage_probe.py`).

## Hard constraints (unchanged from the spec/goal)
- Direct Artifacts API + sanctioned catalog GET only (no SDK); apps read local snapshot only.
- **No LLM** anywhere — every derived signal deterministic.
- TDD: tests precede implementation for every pipeline module.
- One shared pipeline; two Streamlit apps; honest coverage.

## Out of scope (this is the terminal plan stage — defer nothing further)
Produce the complete, executable plan. The only thing NOT in this stage is the actual code (that is
the implementation that follows). Do not leave TODOs/placeholders in load-bearing parts of the plan.
