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
