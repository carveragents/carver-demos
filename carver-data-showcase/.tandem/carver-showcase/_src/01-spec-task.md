# Stage 01 — SPEC: Carver Annotation Data Showcase (v1)

## What to produce (this stage)

A detailed **feature spec / design doc** for the v1 showcase: the two Streamlit prototypes and
the shared data pipeline beneath them. This stage produces the **design** — "what each app does,
what it shows, and every load-bearing design decision" — NOT the build sequence and NOT the
per-file change list (those are Stage 02, the phased implementation plan, which references this
approved spec).

Concretely, **decide and specify in this spec**:

1. **Architecture & module boundaries** — the shared pipeline (`ingest -> normalize -> metrics`)
   and the two apps as separate Streamlit entrypoints that both consume the normalized snapshot.
   Name the modules, their responsibilities, and their interfaces (what each takes/returns). Keep
   units small and single-purpose so they can be tested independently.

2. **The normalized record schema** — the flat, predictable analytics row each annotation becomes
   on ingest. Enumerate the concrete columns (join keys; the 3 score axes with label/score/
   confidence + urgency.basis; classification `update_type`/`update_subtype`/`regulator_*`/
   `jurisdiction_*`; source `title`/`summary`/`base_url`/`feed_url`/`language`; the richness
   presence-flags and counts — e.g. `n_tags`, `n_entities`, populated-actionable-lane count,
   non-empty critical-date count, `n_reg_rules`/`n_reg_statutes`, `has_impact_summary`,
   impacted-business/functions counts, penalties count; the key dates; envelope timestamps). State
   how nested `output_data.metadata.*` / `output_data.classification.*` map to columns, and the
   normalization rules for empties/placeholders. Persist the normalized frame (e.g. parquet) for
   fast app loads.

3. **(A) Showcase Gallery — external** — define the view inventory and what each view proves,
   mapped explicitly to **range / quality / richness**: a corpus-at-a-glance overview with an
   "what is an annotation" explainer + headline KPIs; range views (jurisdiction/geography breadth,
   category->topic structure, update_type mix, volume over publication time); quality views (the
   three score distributions with confidence, urgency.basis, label-vs-score calibration); a
   single-record **richness drill-down** that renders the full nested annotation beautifully
   (5-part impact_summary, 7-lane actionables, critical-dates timeline, entities/tags, reg_refs,
   impacted business/functions, penalties, jurisdiction reasoning); and a curated **highlight
   reel** selected by a DETERMINISTIC richness score (define the formula). Specify the live
   sidebar filters (category, jurisdiction, regulator, update_type, score ranges) and that they
   drive all views.

4. **(B) Data-Quality Cockpit — internal** — define the view inventory mapped to
   **coverage / gaps / anomalies / triage**: a per-field **coverage matrix** (population % overall
   and sliced by category / update_type / jurisdiction); a **gap finder / cleanup queue** (a
   filterable, CSV-exportable table of records failing quality predicates, each linkable to its
   `feed_url` for triage); **anomaly & consistency checks** (define the concrete DETERMINISTIC
   rules: score out of range, label/score mismatch, date-order inconsistencies, empty-but-
   expected, duplicate `entry_id`, invalid `jurisdiction.country`, suspiciously short prose, etc.,
   each with a count + drill-down); distribution/outlier views; and a coverage-over-time trend.

5. **Cross-cutting decisions** — performance (snapshot + `st.cache_data`, target load feel);
   honest-coverage stance (surface real %s); the deterministic-only constraint (no LLM) and how
   each "smart" feature (richness score, quality predicates, anomaly rules, curation) is computed
   without one; testability (what gets unit-tested — normalization, metrics, predicates — with
   HTTP stubbed); repo conventions (venv 3.12, dir layout, `.env`); and a short list of the
   v2/LLM-deferred ideas to be captured in `docs/v2-llm-enrichment-ideas.md`.

You MAY include a short illustrative directory tree and a couple of representative column/metric
definitions to pin conventions, but the full file-by-file build list is a Stage 02 deliverable.

## Product context

See `goal.md` (carried into every stage) for the dataset shape, scale, the two audiences, and the
seven locked decisions. The data snapshot is already pulled to `data/annotations.jsonl` via the
direct Artifacts API; `artifact.output_data` is the annotation, with envelope `topic_id`/`state`/
timestamps alongside. The live payload has been verified and is RICHER than the public docs
(`reg_references` also has `personnel`/`precedents`/`past_release`; `impact_summary.
key_requirements` is a list; `impacted_business` has `type`/`industry`/`jurisdiction`/
`other_notes`; every `*_date` has a paired `*_calendar`).

## Hard constraints (must be honored by the design)

- **Data access:** the direct Carver Artifacts API only (offset-paginated). Apps read the local
  snapshot, never call the live API on render.
- **Sample size:** the showcase uses the pulled snapshot of **30K-100K** annotation records.
- **No LLM enrichment** anywhere in v1. Every derived signal is deterministic and explainable.
- **Build on `classification.jurisdiction`**, not the deprecated `jurisdiction_tier`.
- **Two separate apps, one shared pipeline.** Don't duplicate ingest/normalize logic per app.
- **Honest coverage** — coverage % are real, computed from the snapshot.

## Out of scope (whole pipeline)

- Actually pulling new data or changing the API route (snapshot already exists).
- Any LLM-backed feature (captured for v2, not built).
- Deployment/hosting beyond `streamlit run` locally.

## Out of scope (this stage only — deferred to Stage 02)

- The dependency-ordered phased build plan and the explicit file-by-file creation list.
- Ready-to-run code, exact function signatures beyond illustrative interface sketches, and the
  test-by-test list.
- Exact chart library choice rationale at the line level (name the candidate; final pick is a
  Stage 02 detail) — but DO decide the view inventory and what each view must show.

The spec MUST decide enough design (named modules, the normalized schema columns, each app's view
inventory, the deterministic formulas/predicates/rules) that Stage 02 can produce the phased plan
and file list without re-deciding any of it.
