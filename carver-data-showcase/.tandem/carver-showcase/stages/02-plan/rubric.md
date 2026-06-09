# Rubric — Stage 02 PLAN (Carver Annotation Data Showcase)

The checker judges every plan draft against these criteria. APPROVED only when all are satisfied
(or a gap is explicitly justified). The plan is the BUILD SEQUENCE for the APPROVED Stage 01 spec;
it must not re-decide design, and it must be executable via subagent-driven TDD without re-deciding
anything.

1. **Faithful to the approved spec.** Every plan step traces to the spec (`stages/01-spec/
   artifact.md`). No new design decisions; no contradictions with the spec's architecture (§3),
   normalized schema (§4), deterministic signals (§5), or app view inventories (§6/§7). Where a
   choice is needed, it cites the spec rather than inventing.

2. **Dependency-ordered, phased, independently testable.** Phases are ordered so each depends only
   on earlier ones; each phase is a coherent, independently-verifiable increment with explicit
   dependencies and acceptance criteria. No forward references (a phase never needs a later phase).

3. **Complete module coverage.** Every shared-pipeline module in spec §3.1 (`config`, `ingest`,
   `schema`, `normalize`, `load`, `metrics`, `richness`, `quality`) and every app/component
   (`gallery`, `cockpit`, `filters`, `render`) maps to a build step. Nothing in the spec is left
   unbuilt; nothing is built that the spec didn't call for.

4. **Complete view coverage.** Every Gallery view (spec §6, incl. the **Monitored institutions**
   view (G4) and the **historical-depth** KPIs (G5)) and every Cockpit view (spec §7) appears in a
   phase with where it's implemented and how it's verified.

5. **File-by-file manifest.** A concrete create/edit list with per-file purpose, grouped by phase,
   matching spec §9.4 layout (`carver_showcase/…`, `apps/…`, `tests/…`, `tools/…`, `data/…`,
   `requirements.txt`). Includes `tests/` files. No vapor — every named file is real or
   to-be-created.

6. **TDD test list is concrete.** For each pipeline module, named unit tests written BEFORE
   implementation, covering the spec §9.3 cases (empties→NA; `n_actionable_lanes` over 7 lanes;
   richness bounded `[0,100]` + monotonic + deterministic reel; each quality predicate and each
   anomaly rule firing on a crafted row — incl. out-of-range score, label/score mismatch, reversed
   dates, 2105 pub date, duplicate entry_id, bad country, residual tier, rare update_type, near-dup
   regulator; `apply_filters` conjunction; `ingest.pull_*` with **httpx stubbed**). Fixtures/stub
   strategy named; tests never hit the live API.

7. **Accounts for existing data foundation.** Recognizes that `data/annotations.jsonl` (58,982
   stratified records: Finance 40,000 / DP 10,132 / MD 8,850), `data/topic_categories.csv`, and the
   `tools/` pullers ALREADY exist; does NOT schedule a re-pull of present data. Schedules building
   the still-missing `data/topic_catalog.csv` (full 1,071 institutions, G4) via the sanctioned
   catalog GET. Distinguishes done vs. to-build.

8. **Constraints honored.** Direct Artifacts API + sanctioned catalog GET only (no SDK); **no LLM**
   anywhere; apps read the local snapshot only (no live API on render); one shared pipeline (no
   per-app duplication). Any place these could be violated is flagged with the compliant choice.

9. **Executable via subagent-driven TDD.** Each phase gives: right-sized model guidance (mechanical
   vs. complex), the review gate (python-code-reviewer after each change → python-expert fixes), and
   the exact **verification command(s)** proving the phase done (`pytest …`, `streamlit run …`,
   smoke checks). Concrete enough that a fresh implementer subagent could execute a phase from the
   plan + spec alone.

10. **Risks pre-resolved.** Names real risks (parquet build over a 443 MB JSONL; choropleth ISO-2→
    name/ISO-3 mapping; left-join category population; `topic_catalog.csv` precedes the institutions
    view; Streamlit filter perf over ~59K rows) and gives an already-chosen mitigation for each — no
    open questions left for implementation.

11. **Internal consistency & no placeholders.** Self-consistent; phase dependencies, file manifest,
    and test list agree; no TODO/TBD in load-bearing parts; the final phase verifies BOTH apps run
    and every view loads over the real snapshot.
