# Rubric — Stage 01 SPEC (Carver Annotation Data Showcase v1)

The checker judges every draft against these criteria. A draft is APPROVED only when all are
satisfied (or any gap is explicitly and correctly justified as out-of-scope / deferred to Stage
02). This stage is the **design/PRD**: the phased build plan and per-file change list are
deferred to Stage 02 and are NOT judged here — but the spec must decide enough design that Stage
02 can produce them without re-deciding (judged under criteria 1, 2, 11, 14).

1. **Problem, audiences & scope** — States the goal (demonstrate range/quality/richness of the
   annotation dataset) and cleanly distinguishes the TWO audiences and the TWO prototypes they
   map to: (A) external Showcase Gallery, (B) internal Data-Quality Cockpit. Names what is
   explicitly out of scope for v1.

2. **Shared-pipeline architecture & boundaries** — Specifies one `ingest -> normalize -> metrics`
   pipeline that BOTH apps consume (no duplicated ingest/normalize per app). Names the modules,
   their single responsibilities, and their interfaces (inputs/outputs). Module boundaries are
   small and independently testable. The two apps are separate Streamlit entrypoints over the
   shared normalized snapshot.

3. **Normalized record schema is concrete** — Enumerates the actual flattened columns an
   annotation becomes: join keys; the 3 score axes (label/score/confidence) + urgency.basis;
   classification (`update_type`, `update_subtype`, `regulator_name`/`division`, `jurisdiction_*`
   incl. country/scope/bloc); source (`title`/`summary`/`base_url`/`feed_url`/`language`);
   richness counts/flags (tags, entities, populated actionable lanes, non-empty critical dates,
   reg rules/statutes, impact_summary presence, impacted business/functions, penalties); key
   dates; envelope timestamps. States how nested `output_data.metadata.*` /
   `classification.*` map down, and the rule for treating empty-string / placeholder values as
   missing. Names the persisted format (e.g. parquet).

4. **Data-access compliance** — The design reads the local snapshot pulled via the **direct
   Artifacts API** (offset-paginated, `annotations-v1`); treats `output_data` as the annotation
   and carries envelope `topic_id`/`state`/timestamps; never calls the live API on render. Builds
   on `classification.jurisdiction`, NOT the deprecated `jurisdiction_tier`.

5. **Sample size** — The showcase explicitly uses the **30K-100K**-record snapshot; the spec
   states the count band and that all corpus metrics are computed over it.

6. **No-LLM constraint is provably honored** — Every derived/"smart" signal is DETERMINISTIC and
   explainable: the richness score, the quality predicates, the anomaly rules, and the
   highlight-reel curation are all defined as concrete formulas/threshold rules with no model
   call. The spec explicitly flags any place an LLM would be tempting and states the deterministic
   alternative chosen for v1.

7. **(A) Showcase Gallery — range/quality/richness coverage** — Defines a concrete view inventory
   in which EACH of range, quality, and richness is demonstrably covered: an overview with an
   "what is an annotation" explainer + headline KPIs; RANGE views (jurisdiction breadth,
   category->topic structure, update_type mix, volume over time); QUALITY views (the three score
   distributions with confidence + urgency.basis + label/score calibration); and a single-record
   RICHNESS drill-down rendering the full nested annotation (5-part impact_summary, 7-lane
   actionables, critical-dates, entities/tags, reg_refs, impacted business/functions, penalties,
   jurisdiction reasoning). Each view says what it proves to a buyer.

8. **(A) Curation & interactivity** — Defines a DETERMINISTIC richness/"wow" score (explicit
   formula over populated rich fields) used to auto-select a highlight reel, and the live sidebar
   filters (category, jurisdiction, regulator, update_type, score ranges) that drive all views —
   i.e. it uses the chosen Streamlit interactivity, it isn't a static report.

9. **(B) Data-Quality Cockpit — coverage/gaps/anomalies/triage coverage** — Defines: a per-field
   **coverage matrix** (population % overall AND sliced by category / update_type / jurisdiction);
   a **gap finder / cleanup queue** (filterable, CSV-exportable table of records failing quality
   predicates, each linkable to `feed_url`); **anomaly & consistency checks** as concrete
   deterministic rules (at minimum: score-out-of-range, label/score mismatch, date-order
   inconsistency, empty-but-expected, duplicate `entry_id`, invalid `jurisdiction.country`,
   suspiciously-short prose) each with a count + drill-down; plus distribution/outlier views and a
   coverage-over-time trend. The cockpit gives the QA team an actionable triage surface, not just
   charts.

10. **Honest coverage** — The design surfaces REAL field-population percentages from the snapshot
    (acknowledging scores/keys ~100%, prose ~83-89%, dates/refs sparser) and never presents the
    dataset as 100% complete. The coverage story is shared between both apps via the metrics
    module.

11. **Cross-cutting: performance, testability, conventions** — States the snapshot + `st.cache_data`
    strategy (no live API on render) and a load-feel target; what is unit-tested (normalization,
    metrics, quality predicates/anomaly rules) with any HTTP stubbed; and repo conventions
    (Python 3.12 `.venv/`, directory layout, git-ignored `.env`, dependency list). Concrete enough
    for Stage 02 to build tests from.

12. **v2 / LLM-deferred ideas captured** — Lists the enhancements that would need an LLM (and are
    therefore out of v1) to be recorded in `docs/v2-llm-enrichment-ideas.md` — e.g. semantic
    search, natural-language quality critique, auto-summarized gap explanations — so the no-LLM
    line is explicit and the value isn't lost.

13. **Audience fit is explicit** — Each app's design choices are justified against ITS audience:
    Gallery decisions serve a prospective buyer (credibility, breadth, depth, explorability);
    Cockpit decisions serve an internal cleanup workflow (find/triage/export the bad records).
    The spec doesn't blur the two into one generic dashboard.

14. **Internal consistency & explicit assumptions** — Self-consistent; no contradictions between
    architecture, schema, and view descriptions; no reliance on fields that don't exist in the
    verified payload; assumptions stated explicitly; decisions concrete enough that the Stage 02
    plan can build on them without re-litigating. No placeholders/TBDs in load-bearing sections.
