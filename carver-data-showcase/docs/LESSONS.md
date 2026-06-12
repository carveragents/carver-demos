# SESSIONS

# LESSONS

## Carver annotation dataset (verified against live SDK v0.5.0)

- **Field placement:** in the raw API, `jurisdiction`, `jurisdiction_tier`,
  `update_type`, `update_subtype`, and `regulatory_source` live under
  **`annotation.classification`**, NOT `annotation.metadata`. pred-oracle's flattened
  `.jsonl` export hoists everything to top-level and hides this — trust the live API.
- **`jurisdiction_tier` is DEPRECATED — being replaced by `jurisdiction`.** A backfill
  job (~2026-06-11) swaps `classification.jurisdiction_tier` for
  `classification.jurisdiction` (`{scope, country, bloc, locality, region_*,
  reasoning}`). After it completes, `jurisdiction_tier` is gone. Build on
  `jurisdiction`.
- **`load_dotenv()` gotcha:** with no args it throws `AssertionError` when run via
  `python - <<heredoc` (stdin) because `find_dotenv()` can't walk the stack. Always
  pass `dotenv_path=` explicitly, or run from a real `.py` file.

## v1 build — data foundation (verified 2026-06-09, live API)

- **The contiguous offset walk is Finance-dominated.** Pulling the annotations DAG by
  plain `limit`/`offset` (no filter) returns a block that is **~99% Finance** —
  Medical Devices = **0 records**, Data protection ≈ 2% in the first 60K. It cannot
  demonstrate range *across the 3 categories*. Pull a **category-stratified** snapshot
  instead, using the artifacts endpoint's `topic_ids_in=<uuid,uuid>` filter per category.
- **`topic_ids_in=` (empty) pulls the WHOLE corpus.** An empty topic-id filter is treated
  as "no filter" by the API and walks every record unbounded (a real runaway we hit).
  Guard: never call the pull with an empty id list; cap total records.
- **Categories: the catalog, not the payload.** `category` is NOT in `output_data`
  (0/58,982) and the topics catalog's per-topic `category`/`categories` fields are null.
  Recover topic→category from `GET /api/v1/feeds/categories` + `GET
  /api/v1/feeds/categories/{id}/topics` (sanctioned direct GETs, per data-access.md).
- **Categories overlap — DP and MD are SUBSETS of Finance.** All 54 Data-protection and
  all 24 Medical-Devices topics are also in Finance (610). Finance's `topic_count` (610)
  equals the total distinct categorized topics. Assign each topic its **most-specific**
  category (MD > DP > Finance, smallest-first `setdefault`) for a clean partition
  (MD 24 / DP 53 / Finance 533).
- **Topic catalog is a range goldmine.** `GET /api/v1/feeds/topics?details=true` returns
  all **1,071** monitored institutions with `name`, `acronym`, `jurisdiction_code` (98.6%),
  `entity_type` (98.7%), `govt_body`, `scope`, `sectors`, `industries` — perfect for an
  "institutions" view (country × regulator-type breakdown).
- **FIELD_MAP path corrections (trust the live payload over docs prose):** `title`,
  `feed_url`, `summary`, **and `language`** all live under
  `output_data.classification.metadata.*` (NOT `input_data.extracted_metadata`).
  `language` is a **list** (`["en"]`) → take the first code. `regulator_other_agency` is a
  **list** → join to a scalar. Jurisdiction has `region_code`/`region_name` (no bare
  `region`). `reconciled_published_date` uses key **`date`** (not `value`).
- **Garbage dates exist.** `reconciled_published_date` spans **1947-12-25 … 2105-07-01**;
  parse with `errors="coerce"` (NaT, never throw) and exclude dates outside a plausible
  window (e.g. 1990 … today+2y) from "earliest record / historical depth" — surface the
  extremes only as an anomaly. Data is recency-skewed (≈90% within ~7y, bulk 2024-2026).
- **Honest field coverage (58,982 stratified snapshot):** scores trio ≈100%; prose
  (impact_summary) 82-88%; tags/entities 89/93%; penalties 62%; dates 6-24%; reg-refs
  19-33%; `feed_url` 54%; `jurisdiction.country` 80.5%; **`jurisdiction_tier` residual
  5.1% (3,037 records)** — backfill still incomplete, MD/DP carry more debt. For a boolean
  `has_*` flag, "coverage" = its **true-rate** (not `notna()`, which is always 100%).
- **Quality signals that need pre-computed columns:** `short_prose` needs a `min_prose_len`
  column (the lean frame drops the prose text); `unparseable_date` needs `n_unparseable_dates`
  computed in `normalize` (after the dtype cast, empty vs garbage dates both become NaT).
- **Drill-down vs lean frame:** keep the analytics parquet lean (counts/flags/scalars, ~15 MB
  from 423 MB JSONL) for fast filtering; fetch a single record's full nested annotation on
  demand via an `artifact_id → byte-offset` index over the JSONL (seek + readline).

## v1.1 — full-corpus refresh + external-ready Gallery

- **Full corpus = 211,489 records.** A no-filter offset walk (`tools/pull_full.py`) paginates
  the whole corpus cleanly in ~21 pages of 10K (~1.5 GB JSONL, ~55 MB parquet, ~2.5 min to
  rebuild). The category mix is the *honest* live distribution: **Finance 139,347 (66%) ·
  Uncategorized 53,160 (25%) · Data protection 10,132 · Medical Devices 8,850**. The earlier
  58,982 stratified sample (`pull_stratified.py`, Finance capped at 40K) deliberately distorted
  this for visual balance — fine for a teaser, wrong for "complete stats."
- **`topic_ids_in` with 610 IDs → HTTP 414 (URI too large).** A category-filtered probe blew
  the URL length limit. The whole-corpus walk needs no filter, so this only matters for
  category-scoped pulls (chunk the topic-id list if you ever need them).
- **Don't hard-code counts in the UI — compute them live.** Every headline number (records,
  per-category counts, topics, countries, the scope banner, "N distinct update types") now
  derives from the loaded frame + catalog at render time, so a data refresh can never leave a
  stale figure in an info box. Snapshot provenance (pull date + scope) is the one thing the data
  can't self-report: `tools/pull_full.py` writes `data/snapshot_meta.json`, and
  `load_snapshot_meta()` falls back to the parquet mtime so the "point-in-time as of <date>"
  note always renders.
- **`Uncategorized` is ~25% and that's honest.** Topics outside the three showcased categories
  (461 catalog topics + any non-catalog topic) fall through `normalize_frame` to `Uncategorized`.
  Showing it is more truthful than hiding it; the scope banner says "plus any uncategorized
  topics." A small count delta between views (53,160 by-category vs 53,127 in the category×topic
  sunburst) is just the handful of rows with a null `topic_id` that the groupby drops.
- **Relevance is display-only deprecated.** It stays in the schema/normalize/metrics/quality
  pipeline (and the tests that cover them), but is removed from every *view* — `SCORE_AXES`,
  the score/calibration tabs, the drill-down gauges, the sidebar slider, and the cockpit
  coverage/score panels. Driving the axis count off `len(SCORE_AXES)` (not a hard-coded `3`)
  makes the column layouts collapse to two automatically.
- **Sandbox blocks `sleep`.** A `until grep …; do sleep 5; done` poll loop in Bash (even
  `run_in_background`) dies immediately. To wait on a long background job, rely on the harness
  completion notification, not a sleep-poll.

## v1.2 — downloadable PDF deck (2026-06-10)

- **kaleido 1.x relaunches Chrome on EVERY `fig.to_image` call.** With ~11 charts per deck,
  a naïve loop takes 4+ minutes because each call cold-starts a new browser. Fix: call
  `kaleido.start_sync_server()` once before the slide loop and `kaleido.stop_sync_server()`
  in the `finally` block. All charts then reuse one persistent browser and the whole deck
  renders in well under a minute (choropleths and the institution sunburst still dominate,
  but the overhead is per-chart render cost, not per-process launch).
  Reference: `carver_showcase/deck.py: build_deck()`.
- **Keep the deck in sync with the site by sharing ONE chart-builder module, not by
  re-implementing charts.** `carver_showcase/charts.py` contains every Plotly figure builder
  as pure `df → go.Figure` functions (no Streamlit, no kaleido). Both `apps/gallery.py` and
  `carver_showcase/deck.py` call the same builders, so the deck cannot silently drift from the
  website. The deck always passes the full unfiltered frame; the gallery passes its
  sidebar-filtered `view` — "deck = site with no filters" falls out automatically.

## v1.3 — map readability (2026-06-10)

- **Both choropleths are log-scaled, not linear.** Country counts are brutally
  right-skewed: the US alone is ~40% of all records and ~300x the median country (the
  institution catalog is similar, ~34% / 107x). On a *linear* colour ramp the US pins
  at full saturation and every other country collapses into the bottom ~10% of the
  palette (reads as white). Colouring on `log10(count)` spreads the long tail across
  the full palette while keeping the US darkest; the colorbar is relabelled in real
  counts (`1 · 10 · 100 · 1K · 10K · 54K`) so the legend stays honest. Shared builder:
  `carver_showcase/charts.py: _log_choropleth()` (+ `_log_ticks`, `_human_count`); both
  `fig_geo_choropleth` and `fig_inst_choropleth` delegate to it, so gallery and deck
  move together. `_human_count` picks its unit just below each boundary (999.5, 999_500)
  so a value never rounds *across* a unit — 999,999 reads "1M", not "1000K".
- **Categories are internal-only — surfaced in the Cockpit, never the external Gallery
  or deck.** The Gallery and deck show no category filter, column, composition chart, or
  prose; the Cockpit keeps all of it. Because `apps/components/filters.py:sidebar_filters`
  and `apps/components/render.py:scope_banner` are **shared by both apps**, the category
  bits are *gated by a flag*, not deleted: `sidebar_filters(df, include_category=False)`
  and `scope_banner(df, …, show_categories=False)` from the Gallery; the Cockpit uses the
  defaults (`True`). `FilterState.category` + the `apply_filters` category logic stay
  intact (a no-op when the field is empty) — do NOT remove them or the Cockpit's Category
  filter breaks. The deck's Overview slide swaps the old category-composition chart for
  `fig_label_mix(df, "impact")`. The `category` column still loads into the Gallery frame
  (it's part of the normalize contract); it's simply never displayed.

## v1.4 — Themes & Entities (LLM entity typing, 2026-06-10)

- **The no-LLM rule was deliberately lifted for ONE offline step.** Entity typing +
  de-duplication run as a one-time OpenAI **Batch** job (`tools/classify_entities.py`,
  `gpt-4o-mini`); the model is NEVER called at render — apps read precomputed rollup
  artifacts. Tags stay pure deterministic frequency. Pipeline:
  `extract_terms` (stream JSONL → mention CSVs) → `classify_entities` (Batch →
  `entity_types.csv`) → `build_term_stats` (join + alias-merge → breakdown / leaderboards /
  meta). Real run: 281,180 distinct entities, **5,624 chunks of ~50**, ~**24 min**, ~**$1.50**.
- **`pandas.read_csv` silently turns text tokens into `NaN` — a real entity is literally
  `"NA"`.** Default `na_values` maps `NA`/`null`/`NaN`/`None`/`N/A` to float `NaN`, so a text
  column (`entity`, `canonical_name`, `tag`) crashes downstream string ops (`'float' has no
  attribute 'startswith'`). Fixtures never caught it; the full corpus did. **Read every
  TEXT-column CSV with `keep_default_na=False, na_values=[]`** and cast numeric columns to
  `int` explicitly. Applies to `build_term_stats.py` AND `load.py`.
- **OpenAI Batch error paths are invisible unless you look.** A half-failed batch looks
  identical to a clean one: per-request failures land as non-200 `response.status_code` /
  top-level `error` in the OUTPUT file, and never-run requests land in a separate
  `error_file_id` (not the output file); a `completed` batch can even have a null
  `output_file_id`. Surface all three (count + WARN), guard the null, and make the classifier
  **resumable** — persist `{batch_id, input_sha256}` to a sidecar written BEFORE the first
  poll and cleared only AFTER merge, so an interrupted poll resumes the same job instead of
  re-spending. (186/281,180 entities, 0.07%, fell back to `Other` after bounded retries.)
- **Alias merge via the model's `canonical_name` works well.** Acronyms expand consistently
  (`SEC`/`ECB`/`ESMA`/`FDA`/`BaFin` → full names), so merging the leaderboard by a cleaned
  `canonical_name` key collapses variants: `SEC` went from ~1,538 raw to **4,018** combined.
  The 6-bucket breakdown is computed INDEPENDENT of the merge (merge only affects the
  leaderboard) — pin that invariant with a test.
- **By distinct entity vs by mention tell opposite stories — show both.** Of 281K distinct
  entities, **Person is 40.9%** (the long tail is individual names mentioned once or twice);
  but the leaderboard (top canonical bodies) is all regulators. The breakdown chart is
  **mention-weighted** (Person 283K > Government 170K > Regulator 158K mentions) with
  `distinct_entities` in the hover — so the same chart carries both the "diverse cast" and
  "references concentrate on regulators/bodies" stories honestly. Per-type leaderboard colour
  needs `categoryorder="array"` + `categoryarray=<global mentions order>`, else Plotly's
  per-trace first-encounter ordering clusters bars by type instead of global rank.
- **Coverage is higher on the curated frame and that's honest.** Entity/tag coverage reads
  **99%/98%** on the gallery+deck (noise-curated) frame vs 92.5%/88.5% on the raw corpus —
  the dropped crawl-error update-types were largely entity-less. Computed live from the loaded
  parquet (`(n_entities>0).mean()`), never hard-coded.
- **The tab/slide are full-corpus aggregates and intentionally do NOT honour sidebar filters**
  (the lean parquet stores only `n_tags`/`n_entities`, not the strings). A caption says so.
  Per-record entity filtering is deferred (would need per-record entity storage + a join).

## v1.5 — Regulator dedup + Institution filter

- **The inflated "Regulators" KPI was free-text sprawl, not real breadth.** The raw
  `regulator_name` field has **11,441** distinct strings over ~198K rows; deterministic
  lowercase+punct-strip barely dents it (10,715) because the inflation is semantic —
  abbreviation/full/`U.S.`-prefix variants, parentheticals, and native-language vs English
  duplicates of the SAME body (`金融監督管理委員會` / `Financial Supervisory Commission`). An
  LLM pass (canonical English name + an `is_regulator` flag) collapses it to **~6,710**
  distinct public bodies on the curated frame. Mirrors the entity-typing pipeline exactly.
- **Do NOT reuse the Cockpit's `quality.canonicalize_regulator` as a *counting identity*.**
  That helper strips institution-type nouns as whole words (commission, board, authority,
  agency, department, ministry, office, bureau, division, council…) because it was tuned for
  the Cockpit's near-duplicate *anomaly heuristic*, where aggressive stripping is fine. Used as
  the dedup KEY it **over-merges genuinely distinct regulators** — 143 collision keys, e.g.
  `'financial'` ← {Financial Services Agency (JP), Financial Services Authority, Financial
  Services Commission (KR), Financial Commission}; `'of finance'` ← {Ministry/Department/Division
  of Finance}. Use a **light** key for counting (lowercase + strip-punct + collapse whitespace,
  NO suffix strip) → 6,944 vs 6,832 distinct. Only a **holistic/integration review** caught this
  — the unit tests supplied the `key` by hand, so the seam looked green while the production
  number was biased downward. Lesson: when a value is computed by composing functions across
  files, at least one test must exercise the REAL composition, not a hand-fed intermediate.
- **`is_regulator` is a product decision — surface the boundary, don't pick it silently.**
  A strict "regulators/supervisors/central-banks only" prompt drops 3,347 names → 4,995; a
  public-sector-inclusive prompt (also government departments + intergovernmental / standard-
  setting bodies; drop only companies/news/individuals/private trade associations) drops 1,061
  → 6,710. The strict version dropped defensible bodies (U.S. Treasury, UN, OECD, WHO, NAIC), so
  it was surfaced to the user with concrete borderline cases before finalizing. Because the
  artifact stores `canonical + is_regulator` and the merge key is derived **at load time**, a
  boundary change only needs a prompt re-run (no schema change), and a *key* change needs no
  re-run at all.
- **OpenAI Batch can sit `in_progress` at 0/N for over an hour (queue-starved).** A 458-request
  batch showed `completed=0` after 74 min while a same-shaped 5,624-request entity batch had
  finished in ~24 min — completion time is OpenAI's queue, not job size. For small jobs a
  **synchronous** transport is more reliable: added `--sync-full` (sequential) and `--workers N`
  (ThreadPoolExecutor; workers are pure, ALL cache writes stay on the main thread via
  `as_completed` so checkpointing is race-free and idempotent). 11,441 names ran in ~12 min at
  6 workers, rate-limited by pool size + SDK `max_retries`/backoff + a small inter-chunk sleep.
  Checkpoint per chunk → fully resumable (a kill mid-run resumes from the cache). Same prompt /
  validation / retry / fallback shared across all three transports.
- **Institution filter: filter on the opaque id, display the catalog name.** "Institutions" are
  `topic_id` UUIDs in the frame; names live in `topic_catalog.csv`. The sidebar multiselect
  options are `topic_id`s with a `format_func` → `"{name} ({acronym}) — {country}"`, so
  `apply_filters` stays pure and catalog-free (just `isin` on `topic_id`). An optional
  `catalog_df=None` param means the Cockpit's `sidebar_filters(_full_df)` call renders no
  Institution filter and is byte-for-byte unaffected. Build the label map in ONE catalog pass
  (`to_dict("records")`, first-occurrence-wins) — never per-row `.loc`, which returns a DataFrame
  on duplicate ids and yields garbled labels.

## v1.6 — Institution domain sunburst (2026-06-11)

- **The `tags` field is a trap: present on every topic, empty on all 1,071.** Planned to derive
  institution "domains" from `tags`; a read-only probe of `/feeds/topics?details=true` showed
  `tags` is `[]` everywhere. The real signal lives in `sectors` (770/1071), `industries`,
  `sub_entity_type` (666 distinct), `entity_type`, `scope`, and a 62–245-char `description`
  (always present). Lesson: probe the live field distribution before designing a pipeline on a
  field's *existence* — a non-null column can still be uniformly empty.
- **gpt-4o-mini is under-powered for a nuanced multi-class taxonomy; right-size UP.** Mapping each
  institution into an 11-domain / **27-leaf** taxonomy with conditional routing rules is a
  reasoning task. Mini **ignored explicit instructions** (left central banks — incl. the National
  Bank of Belgium — in the cross-sector fallback despite "a central bank is NEVER 'Other
  Government'") and was **unstable run-to-run**: ~17% of labels (180/1071) flipped between two
  identical-input runs even at `temperature=0` (chunk-neighbour context bias), and "Other
  Government" stayed at ~342/1071. Swapping ONLY the model to **gpt-4o** (`config.DOMAIN_MODEL`,
  same prompt/taxonomy) cut the fallback to **138 (13%)**, routed all 7 central-bank/financial-
  supervisor cases → Finance, and populated all 11 domains. The simpler regulator/entity jobs stay
  on mini. This job gets its own `DOMAIN_MODEL` constant just like it has its own `DOMAIN_CHUNK_SIZE`.
- **Triaging the catch-all bucket beats blindly re-prompting.** Before expanding the taxonomy, a
  keyword triage of the 358 "Other Government" rows split them into: **45% misroutes to domains we
  already had** (central banks→Finance, environment agencies→Environment & Energy, food/drug→
  Healthcare…) — a *prompt* fix; **26% four genuinely-new clusters** each ≥~20 (Justice & Public
  Safety, Transport & Infrastructure, Education/Labour/Social, Science/Research/Standards) — *new
  buckets*; **29% true general-government residual** (parliaments, audit, municipal govts, the AU/
  ASEAN/APEC unions) — correctly stays. So the headline 33% grey wedge was mostly mis-routing, not
  real breadth; sizing the sub-clusters first told us exactly which new top-levels were worth adding.
- **Render the deterministic counterpart, not the LLM output, as the chart authority.** The sunburst
  trusts `top_level` from the catalog merge, but `load.load_topic_domains` always *re-derives*
  `top_level` from `config.INSTITUTION_DOMAIN_PARENT` (and coerces unknown leaves → fallback), so the
  LLM can never mis-nest a leaf under the wrong parent. `px.sunburst(color="top_level")` with 11
  families needs `color_discrete_sequence=Dark24` — the default 10-colour cycle would repeat a hue.
- **`color="<category>"` splits `px.bar` into one trace per category — `autorange="reversed"` no
  longer ranks it.** The single-trace leaderboards order bars via `yaxis=dict(autorange="reversed")`
  on pre-sorted data, but the domain bar colours by `top_level` (to match the sunburst via a shared
  `DOMAIN_COLOR_MAP`), which splits it into 11 one-bar traces and leaves the axis in data order
  (largest at the *bottom*). Fix: `yaxis=dict(categoryorder="total ascending")`, which is robust to
  the trace split and puts the largest domain at the top.

## v1.7 — Regulators removed from the showcase surfaces (2026-06-12)

- **Remove from the surfaces, keep the library.** The user cut the "Regulators" feature from all
  external surfaces — the Overview KPI, the Regulators tab, the sidebar Regulator filter, and the
  deck Regulators slide (deck 11→10 slides). But the underlying LLM-dedup pipeline and its tests
  (`tools/canonicalize_regulators.py`, `regulator_stats.py`, `breadth_summary`'s regulator params,
  `fig_regulator_*`, `load_regulator_*`, `data/regulator_canonical.csv`) were intentionally LEFT in
  place — UI-only removal. So the suite churn was confined to the app/deck tests; the regulator
  library tests stayed green untouched, and the feature can be re-wired without re-running the LLM.
- **Gate a shared component, don't delete from it.** The sidebar Regulator widget lives in the
  Cockpit-shared `sidebar_filters`. Per the "never change Cockpit behaviour" rule, it was gated
  behind a new `include_regulator: bool = True` param (gallery passes `False`, Cockpit keeps the
  default `True`) — the same flag pattern already used for `include_category` and the Institution
  `catalog_df`. `FilterState`/`apply_filters` were left untouched (still carry/handle
  `regulator_name`), so the no-op default `[]` is all the gallery needs.
- **`AppTest(default_timeout=90)` fails under concurrent CPU load — that's a flake, not a
  regression.** The cockpit smoke test (`streamlit.testing.v1.AppTest`) timed out once in a full-suite
  run that I had launched *concurrently with* a `build_deck` (kaleido/Chrome) rebuild + a gallery
  restart; it passed in 32s in isolation and on a clean re-run. Lesson: don't run the deck build or
  other Chrome/kaleido-heavy work alongside the test suite — the AppTest timeout is the canary, and
  a timeout there means "machine was busy," not "code broke." Verify in isolation before chasing it.

## v2.0 — Public deployment (aggregate-only bundle + validation gate, 2026-06-12)

- **Trust boundary: the operator validates+gates+commits; Streamlit just serves.** The public app
  reads only a committed `data/public/` bundle — zero secrets, no API/OpenAI, no raw data. The weekly
  loop is `pull → export_public_bundle → validate_upstream + validate_bundle → commit iff both exit 0
  → push`. The guarantee that "only validated data ships" is the **blocking gate** (`validate && git
  commit`): a HARD failure exits non-zero → the commit never runs → the last good bundle stays live.
- **Aggregate-only is three independent layers, not one check.** (1) `export_public_bundle.py`
  curates then slims to the 15-col `PUBLIC_KEEP_COLUMNS` allowlist (no content, no record ids);
  (2) the runtime loader allowlist (`load_normalized(keep_columns=...)` intersection) means the app
  *physically can't* read a content column even from a bad bundle; (3) `validate_bundle.py` HARD-gates
  on allowlist ⊆ + a content denylist + a string-length cap (catches a renamed/added rich-text column
  the name checks miss). Defense-in-depth because any single layer can be bypassed by a mistake.
- **Module-level path constants don't follow a runtime env relocation — and function default args are
  worse.** `config.DATA_DIR` reads `CARVER_DATA_DIR` at import, so relocating it in-process needs
  `importlib.reload(config)`. But `load.py` binds defaults like `path=TOPIC_DOMAINS_CSV` at *function
  definition*, so you must ALSO `importlib.reload(load)` — else cached loaders keep the old paths and
  an AppTest silently loads real data (the public-mode smoke test passed for the wrong reason until
  fixed). Lesson: an env-relocatable data dir needs the env set *before process start* (production is
  fine — Streamlit Cloud sets it); in-process tests need an autouse conftest fixture that reloads both
  modules and restores the env, or they pollute the suite.
- **Reconciliation thresholds must be relative — a fail-on-any-orphan HARD gate wedges the weekly
  loop.** `topic_id ∈ catalog` started as fail-on-any-orphan; the real data has 26 orphan topic_ids
  (2.51%) from a catalog that lags the annotation pull — benign, and the gallery already renders
  missing names gracefully. A HARD gate there would block every weekly publish. Fixed to tolerance-
  based (`PUBLIC_ORPHAN_TOPIC_TOLERANCE`), matching the rest of the validator's relative-threshold
  philosophy. The orphan share is still surfaced in the report as a stale-catalog signal.
- **The end-to-end run is the real test.** The unit suite was green, but only running
  `export → validate_bundle` against the live `data/` surfaced (a) the orphan-tolerance issue and
  (b) that the export shipped the full 211,489 rows instead of the curated 186,201 — the bundle now
  curates (`drop_noise_update_types`) before slimming. Prove the gate on real data before declaring done.
