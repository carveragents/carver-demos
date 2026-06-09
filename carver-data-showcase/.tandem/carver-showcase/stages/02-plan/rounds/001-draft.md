# Stage 02 — Phased Implementation Plan: Carver Annotation Data Showcase (v1)

**Builds:** the APPROVED Stage 01 spec (`stages/01-spec/artifact.md`). This plan is the **build
sequence + file/test manifest** only — it does not re-decide design. Where a choice is needed it
**cites the spec** (e.g. "spec §4.2"); it never changes the spec's architecture (§3), normalized
schema (§4), deterministic signals (§5), or app view inventories (§6/§7).

**Execution model:** subagent-driven, **test-driven** (tests precede implementation for every
pipeline module), from the repo root with the project `.venv`. After every code change the
**python-code-reviewer** reviews and the **python-expert** fixes findings (per CLAUDE.md) before
the phase's verification command is run.

---

## A. What already exists (DONE) vs. what to build

Grounded against the on-disk worktree. **Do not re-pull or regenerate the DONE items.**

| Status | Artifact | Notes |
|---|---|---|
| ✅ DONE | `data/annotations.jsonl` | **58,982** stratified records (Finance 40,000 / Data protection 10,132 / Medical Devices 8,850), 423 MB, via `tools/pull_stratified.py`. |
| ✅ DONE | `data/annotations.prev.jsonl` | the earlier Finance-heavy contiguous slice (Finance reuse source); keep, do not delete. |
| ✅ DONE | `data/topic_categories.csv` | **610** categorized topics → `category` + attrs (`jurisdiction_code, jurisdiction_detail, scope, govt_body, acronym, hq, base_domain, sectors, industries, entity_type`). Already has most-specific category (MD>DP>Finance). **Lacks the institution `name`** and the non-categorized topics. |
| ✅ DONE | `data/coverage_snapshot.md` | deterministic probe over the 58,982 snapshot — the source of the spec's honest %s and the **concrete field paths** (see Phase 1). |
| ✅ DONE | `tools/pull_stratified.py`, `pull_annotations.py`, `probe_api.py`, `coverage_probe.py` | the pullers/probes. Reuse their auth/client pattern; do not re-run the snapshot pull. |
| ✅ DONE | `.env` (`CARVER_API_KEY`, `CARVER_BASE_URL`), `.venv/`, `docs/` (architecture, data-access, data-model, development, LESSONS, README) | env + reference docs present. |
| 🔨 BUILD | `tools/pull_topic_catalog.py` → `data/topic_catalog.csv` | **all 1,071** monitored institutions incl. `name` (spec G4 / §6.2 v1a), via the sanctioned catalog GET. |
| 🔨 BUILD | `carver_showcase/` package | `config, schema, ingest, normalize, load, metrics, richness, quality` (spec §3.1). |
| 🔨 BUILD | `apps/` | `gallery.py`, `cockpit.py`, `components/filters.py`, `components/render.py` (spec §6/§7). |
| 🔨 BUILD | `tests/` | unit tests per spec §9.3 (TDD). |
| 🔨 BUILD | `requirements.txt`, `docs/v2-llm-enrichment-ideas.md`, README run section | tooling/docs (spec §9.4, §10). |

---

## B. Phase breakdown (dependency-ordered)

Each phase: **Depends on · Files · Interfaces (spec ref) · Tests-first (spec §9.3) · Acceptance &
verification command · Model**. No phase references a later phase.

> **Deviation from the suggested spine (justified):** `requirements.txt` + venv setup move into
> **Phase 0** (pandas/pyarrow are needed by Phase 2 tests, streamlit by Phase 5); Phase 8 only
> *pins/finalizes* it. `richness_score` (a spec §4.2 column) is **materialized in Phase 4** by
> extending the Phase-3 `load.py` build — an edit to an earlier file by a later phase, never a
> forward dependency (metrics in Phase 3 don't need it).

### Phase 0 — Project setup + complete the data foundation
- **Depends on:** nothing (existing snapshot).
- **Files:** `requirements.txt` (create); `tools/pull_topic_catalog.py` (create) →
  `data/topic_catalog.csv` (generate, one-time); `.gitignore` (ensure `data/*.jsonl`,
  `data/*.parquet`, `data/*.csv` except checked-in fixtures, `.env`, `.venv/` ignored).
- **Interfaces:** `pull_topic_catalog.py` mirrors `pull_stratified.py`'s client/auth
  (`httpx`, `X-API-Key`, `CARVER_BASE_URL`); pulls `GET /api/v1/feeds/topics?details=true`
  (per `docs/data-access.md`) for all institutions, joins `category` from the existing
  most-specific assignment (reuse `fetch_catalog` logic: `GET /api/v1/feeds/categories` +
  `/categories/{id}/topics`, MD>DP>Finance), writes columns
  `topic_id,name,acronym,category,jurisdiction_code,entity_type,govt_body,scope,sectors,industries`
  (+ `jurisdiction_detail,hq,base_domain` for parity with `topic_categories.csv`).
- **Tests-first:** `tests/test_pull_topic_catalog.py` — `pull_topic_catalog` with **httpx
  `MockTransport`** (stubbed `/feeds/topics` + `/feeds/categories[/{id}/topics]`); asserts row
  count == stubbed institution count, `name` populated, `category` assigned most-specific, and the
  empty-filter guard. (No live API in tests.)
- **Acceptance & verify:**
  `.venv/bin/python -m pip install -r requirements.txt` succeeds;
  `.venv/bin/python tools/pull_topic_catalog.py` writes `data/topic_catalog.csv` with **1,071**
  rows, `name` non-empty, `jurisdiction_code` ≈98.6% / `entity_type` ≈98.7% populated;
  `.venv/bin/python -m pytest tests/test_pull_topic_catalog.py -q` green.
- **Model:** Sonnet (puller mirrors an existing pattern; care on the count-validation guard).

### Phase 1 — `config.py` + `schema.py` (constants + the column contract)
- **Depends on:** Phase 0.
- **Files:** `carver_showcase/__init__.py`, `carver_showcase/config.py`, `carver_showcase/schema.py`.
- **Interfaces (spec §3.1, §4):**
  - `config.py` constants only: paths (`DATA_DIR`, `ANNOTATIONS_JSONL`, `ANNOTATIONS_PARQUET`,
    `TOPIC_CATEGORIES_CSV`, `TOPIC_CATALOG_CSV`), API params, `PLACEHOLDERS` (spec §4.1),
    `SCORE_RANGE=(0,10)` / `CONFIDENCE_RANGE=(0,1)` (A1), `LABEL_BANDS` (A2),
    `PLAUSIBLE_DATE_WINDOW` (A1/§5.3/G5), `RICHNESS_WEIGHTS` (spec §5.2 — sum=1),
    `MIN_PROSE_CHARS=40`, `RARE_UPDATE_TYPE_CUTOFF`, `ACTIONABLE_LANES` (the 7), `REG_REF_LANES`
    (the 6), `IMPACT_SUMMARY_PARTS` (the 5), `ISO_COUNTRY` (ISO-2→{ISO-3,name} table — see Risk R3).
  - `schema.py`: `NORMALIZED_COLUMNS: list[str]` (exactly the spec §4.2 columns), `DTYPES`, and
    `FIELD_MAP` (nested JSONL path → column). **FIELD_MAP path resolution is pinned from
    `data/coverage_snapshot.md` + `docs/data-access.md`** (see table below); this resolves *where*
    a value lives, it does **not** change the spec's column names, semantics, or honest %s.

  **FIELD_MAP path resolution (load-bearing — confirmed by the probe, not invented):**
  | Spec column | Concrete source path |
  |---|---|
  | `artifact_id` | envelope `id` |
  | `topic_id` | envelope `topic_id` (100%) |
  | `entry_id` | `output_data.entry_id` (== `input_data.id`) |
  | `state` | envelope `state` |
  | `artifact_created_at/updated_at` | envelope `created_at` / `completed_at` / `updated_at` (probe: `completed_at` 100%) |
  | scores ×3 | `output_data.scores.{impact,urgency,relevance}.{label,score,confidence}` + `urgency.basis` |
  | classification | `output_data.classification.{update_type,update_subtype, regulatory_source.{name,division_office,other_agency}, jurisdiction.{scope,country,bloc,locality,region_*,reasoning}}` |
  | `has_jurisdiction_tier_legacy` | presence of `output_data.classification.jurisdiction_tier` (5.1%) |
  | metadata blocks | `output_data.metadata.{tags,entities,actionables.*,critical_dates.*,impact_summary.*,reg_references.*,impacted_business.*,impacted_functions,penalties_consequences}` |
  | `title` | **`output_data.classification.metadata.title`** (95.6%) — probe-confirmed location |
  | `feed_url` | **`output_data.classification.metadata.feed_url`** (53.9% ≈ spec's ≈54%) — probe-confirmed; `input_data.extracted_metadata.url` only as fallback |
  | `base_url` | deterministic registrable domain of `feed_url` |
  | `summary`,`language` | `input_data.extracted_metadata.{summary,language}` if present else NA (population measured) |
  | key dates + calendars | `output_data.metadata.critical_dates.{effective,compliance,comment_deadline,early_adoption,updated}_date` (+ `*_calendar`), `pub_date_content` |
  | `reconciled_published_date` (+ provenance) | `output_data.reconciled_published_date.{date,source,converted,original_calendar,valid}` (spec G3: `date`, not `value`) |
- **Tests-first:** `tests/test_schema.py` — `NORMALIZED_COLUMNS` matches the spec §4.2 set (no
  missing/extra), `RICHNESS_WEIGHTS` sum to 1, `LABEL_BANDS` partition `[0,10]`, `FIELD_MAP` keys ⊆
  columns.
- **Acceptance & verify:** `.venv/bin/python -m pytest tests/test_schema.py -q` green; importing
  `carver_showcase.config`/`schema` raises nothing.
- **Model:** Sonnet (the column contract + path pinning is load-bearing).

### Phase 2 — `ingest.py` + `normalize.py` (+ tests)
- **Depends on:** Phase 1.
- **Files:** `carver_showcase/ingest.py`, `carver_showcase/normalize.py`,
  `tests/test_ingest.py`, `tests/test_normalize.py`, `tests/conftest.py` (fixtures).
- **Interfaces (spec §3.1):**
  - `ingest.load_snapshot(path) -> Iterator[dict]` (stream JSONL, one envelope per line);
    `ingest.pull_snapshot(...)` / `pull_topic_catalog(...)` (thin wrappers around the proven
    `tools/` pull pattern; not run on render).
  - `normalize.normalize_record(raw) -> dict` (apply FIELD_MAP; empties→NA per spec §4.1; counts
    **after** the empties pass; presence flags; date parsing + `*_calendar` pairing);
    `normalize.normalize_frame(records, categories) -> DataFrame` (left-join the
    `topic_categories.csv` map on `topic_id`; unmapped → `"Uncategorized"`).
- **Tests-first (spec §9.3):** `test_normalize.py` —
  `test_empty_string_and_placeholders_become_na`, `test_whitespace_only_is_na`,
  `test_counts_computed_after_empties` (an actionable `""` not counted),
  `test_n_actionable_lanes_over_seven_lanes`, `test_presence_flags_follow_na_rule`,
  `test_scores_and_classification_nested_mapping`,
  `test_title_and_feed_url_from_classification_metadata` (asserts the probe-confirmed path →
  catches a wrong FIELD_MAP), `test_reconciled_published_date_from_date_field`,
  `test_date_parse_and_calendar_pairing`, `test_jurisdiction_tier_legacy_flag`,
  `test_category_left_join_most_specific_and_uncategorized_fallback`,
  `test_n_critical_dates_and_n_reg_refs_total_counts`. `test_ingest.py` —
  `test_load_snapshot_streams_each_line` (tiny JSONL fixture),
  `test_pull_snapshot_paginates_until_short_page` (**httpx MockTransport**),
  `test_pull_snapshot_topic_ids_in_filter`, `test_pull_refuses_empty_topic_ids`.
  Fixtures in `conftest.py`: `raw_envelope()` (a realistic single record incl. populated + empty +
  anomalous fields), `tiny_jsonl(tmp_path)`, `categories_df()`.
- **Acceptance & verify:** `.venv/bin/python -m pytest tests/test_ingest.py tests/test_normalize.py -q`
  green; tests never touch the network.
- **Model:** Sonnet (normalization rules are moderate; path correctness matters).

### Phase 3 — `load.py` (parquet build/cache) + `metrics.py` (+ tests)
- **Depends on:** Phase 2 (+ Phase 0 for the catalog CSV).
- **Files:** `carver_showcase/load.py`, `carver_showcase/metrics.py`, `tests/test_metrics.py`.
- **Interfaces (spec §3.1):**
  - `load.load_normalized(parquet_path, jsonl_path, categories_path) -> DataFrame` (build-or-load:
    if parquet missing/`--rebuild`, stream JSONL → `normalize_frame` → persist parquet; else read
    parquet); `load.load_catalog(catalog_path) -> DataFrame` (`topic_catalog.csv`). Streaming build
    keeps only normalized scalar columns (drops the heavy raw nested payload) — see Risk R1.
  - `metrics.coverage_matrix(df, slice_by=None)`, `score_distributions(df)`, `breadth_summary(df)`,
    `volume_over_time(df, freq)`, `historical_depth(df)` (G5: earliest **plausible** date, span,
    recency buckets — excludes `PLAUSIBLE_DATE_WINDOW` outliers).
- **Tests-first (spec §9.3):** `test_coverage_matrix_overall_and_sliced`,
  `test_coverage_counts_na_as_missing` (honest %), `test_score_distributions_buckets`,
  `test_breadth_summary_distinct_counts`,
  `test_volume_over_time_excludes_implausible_by_default`,
  `test_historical_depth_uses_plausible_min_and_recency_buckets` (1947/2105 excluded; median/p10/p90
  on a crafted frame). `load` smoke covered in Phase 8 over the real snapshot (build is slow for a
  unit test) — unit-test `load_normalized` on a `tiny_jsonl` fixture: `test_build_then_cached_read`.
- **Acceptance & verify:** `.venv/bin/python -m pytest tests/test_metrics.py -q` green; a one-shot
  `load_normalized(...)` over the **real** snapshot prints shape `(58982, N)` and coverage numbers
  matching `data/coverage_snapshot.md` (impact 100%, prose ≈88%, feed_url ≈53.9%, country ≈80.5%,
  jurisdiction_tier 5.1%).
- **Model:** Sonnet.

### Phase 4 — `richness.py` + `quality.py` (+ tests); materialize `richness_score`
- **Depends on:** Phase 3.
- **Files:** `carver_showcase/richness.py`, `carver_showcase/quality.py`, `tests/test_richness.py`,
  `tests/test_quality.py`; **edit** `carver_showcase/load.py` to attach the `richness_score` column
  during the parquet build (spec §4.2) — earlier-file edit, not a forward dep.
- **Interfaces (spec §5.2/§5.3):** `richness.richness_scores(df) -> Series` (the §5.2 weighted
  formula), `richness.highlight_reel(df, n, diversify=True) -> DataFrame`;
  `quality.predicate_flags(df) -> DataFrame[bool]`, `quality.anomaly_report(df) -> dict`,
  `quality.cleanup_queue(df, predicates=None) -> DataFrame`.
- **Tests-first (spec §9.3):** `test_richness.py` — `test_score_bounded_0_100`,
  `test_score_monotonic_per_component`, `test_weights_sum_to_one`,
  `test_highlight_reel_deterministic_order_and_tiebreak`,
  `test_highlight_reel_diversify_one_per_topic`. `test_quality.py` — one test **per predicate**
  (missing_core_score, missing_join_key, missing_feed_url, missing_jurisdiction_country,
  missing_update_type, no_impact_summary, short_prose, no_actionables, empty_but_expected) and one
  **per anomaly rule** firing on a crafted row: `test_score_out_of_range`,
  `test_label_score_mismatch`, `test_date_order_inconsistency`, `test_implausible_pub_date_2105`,
  `test_invalid_reconciled_date_valid_false`, `test_duplicate_entry_id` (cross-row, full-frame),
  `test_invalid_jurisdiction_country`, `test_residual_legacy_field`, `test_update_type_rare`,
  `test_regulator_near_duplicate_canonicalization`, `test_unparseable_date`,
  `test_cleanup_queue_includes_any_failing_predicate`.
- **Acceptance & verify:** `.venv/bin/python -m pytest tests/test_richness.py tests/test_quality.py -q`
  green; rebuilt parquet now carries `richness_score` ∈ `[0,100]`.
- **Model:** Sonnet for impl, **Opus** for the python-code-reviewer pass (the anomaly rules +
  regulator canonicalization are the subtle deterministic core).

### Phase 5 — shared app components (`filters.py`, `render.py`) (+ filter tests)
- **Depends on:** Phase 4.
- **Files:** `apps/__init__.py`, `apps/components/__init__.py`, `apps/components/filters.py`,
  `apps/components/render.py`, `tests/test_filters.py`.
- **Interfaces (spec §3.1, §6.1):** `filters.FilterState` (+ `sidebar_filters(df) -> FilterState`),
  `filters.apply_filters(df, state) -> DataFrame` (pure, vectorized, conjunctive);
  `render` helpers: `kpi_cards(...)`, `sampling_caveat_banner()` (spec §2.2/§8), and
  `record_drilldown(row)` (spec §6.3 — renders every populated section, **hides empty ones**).
- **Tests-first (spec §9.3):** `test_apply_filters_each_dimension_narrows`,
  `test_apply_filters_is_conjunctive`, `test_apply_filters_score_and_date_ranges`,
  `test_apply_filters_min_richness`. (`apply_filters` is pure → testable without Streamlit; render
  helpers verified via the Phase-8 smoke run.)
- **Acceptance & verify:** `.venv/bin/python -m pytest tests/test_filters.py -q` green.
- **Model:** Sonnet.

### Phase 6 — `apps/gallery.py` (external; ALL spec §6 views)
- **Depends on:** Phase 5 (+ Phase 0 `topic_catalog.csv` for v1a).
- **Files:** `apps/gallery.py`.
- **Implements every §6.2 view** (mapping below), all driven by the shared sidebar filters, all
  reading the cached snapshot (no live API). Charting: **Plotly** (spec §9.4 candidate).

  | Spec view | Built with |
  |---|---|
  | v0 Overview + "what is an annotation" + KPIs + **historical-depth block (G5)** + sampling banner | `metrics.breadth_summary`, `metrics.historical_depth`, `render.kpi_cards`, `render.sampling_caveat_banner` |
  | v1 Jurisdiction & geography breadth | `metrics.breadth_summary` + Plotly choropleth (ISO map, R3) |
  | **v1a Monitored institutions (G4)** | `load.load_catalog` joined to snapshot counts by `topic_id`; table + by-country/by-regulator-type/by-scope charts; CSV export; 1,071⊃610⊃405 framing |
  | v2 Category → topic structure | `category` (joined) sunburst/treemap |
  | v3 Update-type mix | `update_type` distribution + long-tail count |
  | v4 Volume over time | `metrics.volume_over_time` (implausible excluded) |
  | v5 Score distributions | `metrics.score_distributions` |
  | v6 Urgency basis breakdown | `urgency_basis` value counts |
  | v7 Label-vs-score calibration | per-axis band×score heatmap |
  | v8 Single-record richness drill-down | `render.record_drilldown` (spec §6.3) |
  | v9 Highlight reel | `richness.highlight_reel` → cards → drill-down |
- **Tests-first:** UI is verified by the Phase-8 smoke run (Streamlit views aren't unit-tested); the
  data each view calls is already covered by Phases 3–5 tests.
- **Acceptance & verify:** `.venv/bin/python -m streamlit run apps/gallery.py` loads; each view
  renders over the real snapshot without exception; v1a shows 1,071 institutions with sample-record
  counts; v0 shows earliest **plausible** date (not 1947).
- **Model:** Sonnet.

### Phase 7 — `apps/cockpit.py` (internal; ALL spec §7 views)
- **Depends on:** Phase 5 (+ Phase 0 catalog for the §7.1 cross-check note).
- **Files:** `apps/cockpit.py`.
- **Implements every §7 view:** 7.1 coverage matrix (overall + sliced by category/update_type/
  jurisdiction; **catalog cross-check note** for institutions missing `jurisdiction_code`/
  `entity_type` or 0 records) via `metrics.coverage_matrix` + `load.load_catalog`; 7.2 gap finder /
  cleanup queue (`quality.cleanup_queue`, CSV export, `feed_url` triage links); 7.3 anomaly &
  consistency panel (`quality.anomaly_report` — count + drill-down per rule); 7.4 field-health /
  cardinality (update_type 56 + rare list; regulator 3,219 near-dup grouping); 7.5 distribution /
  outlier; 7.6 coverage-over-time trend; 7.7 deprecation/migration tracker (jurisdiction_tier
  ≈3,037/5.1%, MD/DP-heavy).
- **Tests-first:** as Phase 6 — the underlying `quality`/`metrics` functions are unit-tested
  (Phases 3–4); the views are smoke-verified in Phase 8.
- **Acceptance & verify:** `.venv/bin/python -m streamlit run apps/cockpit.py` loads; every §7 view
  renders; the coverage matrix matches `coverage_snapshot.md`; the cleanup queue exports CSV.
- **Model:** Sonnet.

### Phase 8 — wiring, docs & full verification
- **Depends on:** Phases 0–7.
- **Files:** finalize/pin `requirements.txt`; `README.md` (run section); `docs/v2-llm-enrichment-
  ideas.md` (spec §10 list); ensure `.gitignore` correct.
- **Acceptance & verify (criterion 11 — both apps + every view over the real snapshot):**
  1. `.venv/bin/python -m pytest -q` — entire suite green.
  2. `.venv/bin/python -c "from carver_showcase.load import load_normalized; ..."` builds the parquet
     once and prints shape `(58982, N)` + key coverage %s matching `coverage_snapshot.md`.
  3. `.venv/bin/python -m streamlit run apps/gallery.py` and `… apps/cockpit.py` — open headless,
     click through **every** view (Gallery v0–v9 incl. v1a/historical-depth; Cockpit 7.1–7.7), no
     exceptions; perf sane (warm filter re-render sub-second).
  4. `docs/v2-llm-enrichment-ideas.md` lists the 8 spec §10 items.
- **Model:** Sonnet for wiring; Haiku for the docs prose.

---

## C. File-by-file manifest (grouped by phase)

```
# Phase 0
requirements.txt                         # httpx, python-dotenv, pandas, pyarrow, streamlit, plotly, pytest
tools/pull_topic_catalog.py              # one-time: /feeds/topics?details=true -> data/topic_catalog.csv (1,071)
data/topic_catalog.csv                   # GENERATED (git-ignored): all monitored institutions + name + attrs
tests/test_pull_topic_catalog.py         # httpx-stubbed catalog pull

# Phase 1
carver_showcase/__init__.py
carver_showcase/config.py                # constants, thresholds, ISO table, richness weights, plausible window
carver_showcase/schema.py                # NORMALIZED_COLUMNS, DTYPES, FIELD_MAP (probe-pinned paths)
tests/test_schema.py

# Phase 2
carver_showcase/ingest.py                # load_snapshot (stream), pull_snapshot/pull_topic_catalog wrappers
carver_showcase/normalize.py             # normalize_record / normalize_frame (empties->NA, flags, counts, joins)
tests/conftest.py                        # raw_envelope(), tiny_jsonl(), categories_df(), tiny_frame()
tests/test_ingest.py
tests/test_normalize.py

# Phase 3
carver_showcase/load.py                  # load_normalized (build-or-load parquet), load_catalog
carver_showcase/metrics.py               # coverage_matrix, score_distributions, breadth, volume_over_time, historical_depth
tests/test_metrics.py

# Phase 4
carver_showcase/richness.py              # richness_scores, highlight_reel
carver_showcase/quality.py               # predicate_flags, anomaly_report, cleanup_queue
carver_showcase/load.py                  # EDIT: attach richness_score to the parquet build
tests/test_richness.py
tests/test_quality.py

# Phase 5
apps/__init__.py
apps/components/__init__.py
apps/components/filters.py               # FilterState, sidebar_filters, apply_filters (pure)
apps/components/render.py                # kpi_cards, sampling_caveat_banner, record_drilldown
tests/test_filters.py

# Phase 6
apps/gallery.py                          # external — spec §6 views v0–v9 (incl. v1a G4, historical-depth G5)

# Phase 7
apps/cockpit.py                          # internal — spec §7 views 7.1–7.7

# Phase 8
README.md                                # run instructions
docs/v2-llm-enrichment-ideas.md          # spec §10 deferred ideas
requirements.txt                         # EDIT: pin versions
```

---

## D. Test-by-test list (TDD) — written BEFORE each module

Per-module tests are listed inline in the phases above. Summary of coverage vs. spec §9.3:

| Module | Test file | Key cases |
|---|---|---|
| `normalize` | `test_normalize.py` | empties/placeholders→NA; whitespace→NA; counts-after-empties; `n_actionable_lanes` over 7 lanes; flags; nested mapping; **title/feed_url from `classification.metadata`**; `reconciled_published_date.date`; date+calendar pairing; tier-legacy flag; category left-join + Uncategorized; `n_critical_dates`/`n_reg_refs_total` |
| `ingest` | `test_ingest.py` | stream each line; **httpx-stubbed** paginate-until-short; `topic_ids_in` filter; empty-filter guard |
| `metrics` | `test_metrics.py` | coverage overall+sliced; NA-as-missing; distributions; breadth distinct counts; volume excludes implausible; **historical_depth** plausible-min + recency buckets |
| `richness` | `test_richness.py` | bounded `[0,100]`; monotonic per component; weights sum 1; reel deterministic order/tiebreak; reel diversity |
| `quality` | `test_quality.py` | each predicate (9) + each anomaly rule (11) on crafted rows — incl. out-of-range, label/score mismatch, reversed dates, 2105 date, dup entry_id, bad country, residual tier, rare update_type, near-dup regulator; cleanup-queue union |
| `filters` | `test_filters.py` | each dimension narrows; conjunctive; score/date ranges; min richness |
| `load` | `test_metrics.py`/Phase 8 | build-then-cached-read on a tiny fixture; full-snapshot smoke in Phase 8 |
| `pull_topic_catalog` | `test_pull_topic_catalog.py` | stubbed catalog → 1,071 rows, name populated, most-specific category |

**Fixtures / stub strategy (`tests/conftest.py`):** `tiny_frame()` — a handful of crafted
normalized rows spanning populated / empty / anomalous cases (drives `metrics`/`richness`/`quality`/
`filters`); `raw_envelope()` + `tiny_jsonl(tmp_path)` — raw records for `ingest`/`normalize`;
HTTP via **`httpx.MockTransport`** (no extra dependency, no network) for all `pull_*` tests. Tests
**never** hit the live API.

---

## E. Execution notes for subagent-driven TDD

- **Per-phase loop:** (1) python-expert writes the phase's tests first (red); (2) python-expert
  implements until green; (3) **python-code-reviewer** reviews the diff; (4) python-expert applies
  fixes; (5) run the phase's verification command; only then advance.
- **Model right-sizing (CLAUDE.md):** Haiku — docs/boilerplate (`requirements.txt`, README, v2 doc).
  Sonnet — Phases 0–3, 5–8 implementation. Sonnet impl + **Opus review** — Phase 4 (anomaly rules,
  regulator canonicalization). Opus — any cross-phase design question that arises (should be none;
  the spec is the authority).
- **Env:** run everything from the repo root with `.venv` on **Python 3.12** (locked, goal §7 —
  see Risk R7); `streamlit run apps/gallery.py` / `apps/cockpit.py`; secrets from git-ignored `.env`.
- **No live API on render or in tests** — apps read `data/*.parquet`/`*.csv`; pulls are one-time
  `tools/` scripts; tests stub httpx.

---

## F. Risks / sequencing checks (each with a chosen mitigation — no open questions)

- **R1 — Parquet build over the 423 MB JSONL (memory/time).** `ingest.load_snapshot` **streams**
  line-by-line; `normalize_frame` keeps only the ~70 scalar/flag/count columns and **discards the
  raw nested payload**, so the persisted parquet is small and warm loads are <1s. Build once;
  `st.cache_data` on `load_*`; a `--rebuild` flag forces a rebuild. Cold build target tens of
  seconds, verified in Phase 8.
- **R2 — Field-path mismatch vs. spec prose.** The spec §4.2 prose places `title`/`feed_url` under
  `input_data.extracted_metadata`, but the probe (`coverage_snapshot.md`) shows the canonical,
  honestly-counted values live under `output_data.classification.metadata.*` (title 95.6%, feed_url
  53.9%), and the envelope timestamp is `completed_at`. **Mitigation:** `FIELD_MAP` (Phase 1) pins
  the probe-confirmed paths and `test_normalize.py` asserts the resulting feed_url/title population —
  a wrong path fails immediately. Column names, semantics, and honest %s are unchanged (a location
  detail the spec explicitly delegates to `FIELD_MAP`).
- **R3 — Choropleth needs ISO mapping.** `jurisdiction_country` / catalog `jurisdiction_code` are
  ISO-2 (US, AU, CN…). `config.ISO_COUNTRY` (static ISO-2→ISO-3/name) feeds Plotly's choropleth and
  is **reused** by `invalid_jurisdiction_country`; unmappable values are shown in an honest "not
  mappable" footnote, never dropped silently.
- **R4 — Category left-join population.** `topic_categories.csv` (610) is left-joined on `topic_id`;
  unmapped → `"Uncategorized"`; `test_normalize.py` asserts ≈100% of the 405 sample topics map and
  the fallback path works. Population is measured, never assumed.
- **R5 — `topic_catalog.csv` must precede the institutions view.** Enforced by dependency order
  (Phase 0 → Phase 6); Phase 6 acceptance checks the file exists with 1,071 rows before v1a renders.
- **R6 — Streamlit filter perf over ~59K rows.** `richness_score` (and the predicate flags, computed
  once via `quality.predicate_flags` and cached) are precomputed; views filter via vectorized
  boolean masks; `metrics`/`quality` results are cached keyed by the `FilterState` signature; no
  per-row Python in views. Sub-second warm re-render target, verified in Phase 8.
- **R7 — venv Python version.** Goal/spec lock **3.12**; `docs/data-access.md` notes the shipped
  `.venv` is 3.10. **Mitigation:** Phase 0 confirms/recreates `.venv` on 3.12
  (`.venv/bin/python --version`); code avoids 3.12-only syntax so the suite also passes on 3.10 as a
  safety margin.
- **R8 — Cross-row anomalies.** `duplicate_entry_id` and `regulator_near_duplicate` are computed on
  the **full** frame in `quality.anomaly_report` (not per-filter), then surfaced; tests use a small
  multi-row frame. Avoids the trap of per-filter dedup giving wrong counts.

---

## G. Internal-consistency check (rubric 1, 2, 3, 4, 11)

- **Module coverage (3):** every spec §3.1 module maps to a phase — config/schema (P1), ingest/
  normalize (P2), load/metrics (P3), richness/quality (P4), filters/render (P5), gallery (P6),
  cockpit (P7); plus `tools/pull_topic_catalog.py` (P0). Nothing extra is built.
- **View coverage (4):** Gallery v0–v9 incl. **v1a (G4)** and **historical-depth (G5)** → Phase 6;
  Cockpit 7.1–7.7 → Phase 7; each with a verification step.
- **Dependency order (2):** 0→1→2→3→4→5→6/7→8; no phase needs a later one. The only later-phase edit
  is Phase 4 extending Phase 3's `load.py` to add `richness_score` (allowed — depends backward).
- **Constraints (8):** direct Artifacts API + sanctioned catalog GET only (P0 puller; no SDK); **no
  LLM** (all signals are the spec §5 formulas/rules); apps read local snapshot only (R1/R6); one
  shared `carver_showcase` pipeline feeding both apps (no per-app duplication).
- **Existing foundation (7):** Section A marks `annotations.jsonl`, `topic_categories.csv`, and the
  pullers DONE (no re-pull) and schedules only `topic_catalog.csv` as the missing data artifact.
- **No placeholders (11):** every named file is real or to-be-created; Phase 8 verifies both apps run
  and every view loads over the real 58,982-record snapshot.

This plan is executable, phase by phase, from the plan + the approved spec alone — no design
decision is left open.
