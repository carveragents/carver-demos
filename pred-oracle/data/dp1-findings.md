# DP1 Resolution

**Question:** Does `carver-feeds-sdk` surface Appendix-A annotation fields on entries, or only raw entry metadata?

**Verified:** 2026-05-19

**SDK version:** `carver-feeds-sdk` 0.5.0 (from `uv.lock`)

## How this was verified

Intended flow: run `build/inspect_carver.py` against the live Carver Feeds API and inspect `df.iloc[0].to_dict()`.

Actual flow: **the live call was blocked** because the `CARVER_API_KEY` in the worktree `.env` returns HTTP 401 (`{"error": "Authentication failed", "message": "Invalid API key"}`) against `https://app.carveragents.ai/api/v1/feeds/topics`. The key is 32 chars; an X-API-Key header is sent correctly; the server rejects it.

DP1 was therefore answered from **authoritative SDK-internal evidence** rather than a live response:

1. `carver_feeds.data_manager.DataManager.get_topic_entries_df` (the function backing `QueryEngine.to_dataframe()`) declares the exact column set returned for entries (`.venv/lib/python3.11/site-packages/carver_feeds/data_manager.py`, lines 270-388, `expected_columns` list).
2. `carver_feeds.carver_api.CarverFeedsAPIClient.get_annotations` (same package, `carver_api.py` lines 349-445) is a **separate** method targeting `/api/v1/core/annotations` whose docstring documents the annotation payload shape.
3. The carver-feeds-skill `api_reference.md` confirms the entry column list at line 128.
4. The Appendix-A schema is defined by `../../../carver-dags/workflows/entry_annotation/prompts.py` (the canonical annotator prompts) — keys: `update_type`, `regulatory_source.{name,division_office,...}`, `critical_dates.{effective_date,comment_deadline,compliance_date}`, `impacted_business.{sectors,entities,geographies}`, `impact_summary.{objective,what_changed,why_it_matters,actionables,penalties_consequences}`, `entities`, `scores.{impact_score,urgency_score,relevance_score}`, `summary`.

## Sample fields observed (entries surface, schema-derived)

Top-level keys returned by `QueryEngine.filter_by_topic(...).to_dataframe().iloc[0].to_dict()`:

- `entry_id` (renamed from `id` in hierarchical views; `id` in flat entries)
- `entry_title` (renamed from `title` in hierarchical views; `title` in flat entries)
- `entry_link` (renamed from `link` in hierarchical views; `link` in flat entries)
- `entry_content_markdown` — populated only when `fetch_content=True` (requires S3 credentials)
- `description`
- `feed_id`, `topic_id`
- `content_status`, `content_timestamp`
- `s3_content_md_path`, `s3_content_html_path`, `s3_aggregated_content_md_path`
- `published_at` (mapped from API's `published_date`)
- `created_at`, `is_active`
- `extracted_metadata_full` — raw `extracted_metadata` blob from the API; contains S3 paths and content-extraction status, **not** annotation fields

**None** of the Appendix-A annotation fields (`update_type`, `regulatory_source`, `impacted_business`, `scores`, `critical_dates`, `entities`, `summary`, `impact_summary`) appear on the entries dataframe.

However, the SDK **does** expose annotations through a **separate** endpoint: `CarverFeedsAPIClient.get_annotations(feed_entry_ids=[...] | topic_ids=[...] | user_ids=[...])` returns a list of `{feed_entry_id, topic_id, user_id, annotation: {classification, metadata, scores, summary}}` — i.e., the full Appendix-A payload, but joined on `feed_entry_id` rather than baked into the entries dataframe.

## Resolution: A (with caveat)

The SDK **does** surface Appendix-A annotations — just not via the entries dataframe. They live on a separate, dedicated annotations endpoint that takes a list of entry IDs and returns the matching annotation payloads. No client-side Claude annotation step is required; Carver has already done it server-side.

This is functionally **Case A** (SDK is sufficient — no Claude annotation roundtrip needed in Task 5), with the implementation caveat that Task 5 will issue **two SDK calls per pull**: one for entries, one for annotations, then join on `feed_entry_id`.

(This is not literal Case A as written — Case A in the prompt assumes annotations are baked into `df.iloc[0]`. They are not. But Case B is the wrong choice too: Case B assumes we need our own Claude annotation step. We do not — Carver supplies the annotations, just on a different endpoint. The cost and shape of Task 5 match Case A, not Case B.)

**Chosen path: A (two-endpoint variant)**

## Implications for Task 5

- Task 5 pull script must call **both** surfaces:
  1. `qe.filter_by_topic(topic_name=...).to_dataframe()` — yields entries (id, title, link, dates, content paths).
  2. `client.get_annotations(feed_entry_ids=[...])` — yields annotations keyed by `feed_entry_id`. Batch IDs in groups (TBD page size; SDK uses `feed_entry_ids_in=` comma-joined; default `DEFAULT_PAGE_LIMIT` applies).
  3. Join on `feed_entry_id` to produce the slice JSON consumed by the landing-page templates.
- **No Anthropic SDK / Claude annotation roundtrip** is required. Cost is bounded by Carver API calls only.
- If `fetch_content=True` is needed (for `entry_content_markdown`), Task 5 also needs S3 credentials in `.env` (`CARVER_AWS_*` or whatever the SDK expects — re-check `s3_client.py` before that step). The landing page slice may not need full markdown bodies — confirm against the slice schema in Task 8.
- The selector logic (filtering to prediction-market-adjacent regulators) lands in Task 5 too; it operates on the joined dataframe (entry metadata + annotation classification/scores).

## Blockers for live re-verification

- `CARVER_API_KEY` in `.env` is invalid. Replace it with a working key from `https://app.carveragents.ai`, then re-run:
  ```
  uv run python build/inspect_carver.py > data/dp1-sample-entry.json
  ```
  The script will emit a real sample (entry row + matching annotation) and overwrite the schema-derived placeholder.
- The script also requires the SDK to have access to **at least one** topic (currently hard-coded to "Banking" for the inspection probe — any topic works; the goal is to sample one entry).

## Open questions deferred to Task 5

- Page size for `get_annotations(feed_entry_ids_in=...)` — does the comma-joined IN-list have a server-side length cap? (SDK doesn't document one; assume <=100 IDs/request, paginate if needed.)
- Whether `fetch_content=True` is required for the landing slice (decided in Task 8, not here).
- Whether annotations exist for **every** entry, or only a subset (e.g., entries where the workflow has run successfully). Task 5 should treat missing annotations as a soft failure and log, not crash.
