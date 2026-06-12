# Stage 01 — SPEC: Themes & Entities (Gallery tab + deck slide)

## What to produce (this stage)

A detailed **feature spec / design doc** for the Themes & Entities feature: the one-time
OpenAI Batch entity-enrichment pipeline, the derived stat artifacts, the shared chart
builders, and the new Gallery tab + deck slide that consume them. This stage produces the
**design** — "what gets built, what each piece does, every load-bearing decision, and how it
plugs into the existing codebase" — NOT the dependency-ordered build sequence and NOT the
per-file/test-by-test change list (those are Stage 02, the phased implementation plan, which
references this approved spec).

Concretely, **decide and specify in this spec**:

1. **End-to-end architecture & data flow** — the three-tool enrichment pipeline and how its
   outputs reach the apps. Name each tool, its single responsibility, inputs, and outputs:
   - `tools/extract_terms.py` — stream `data/annotations.jsonl` once; emit raw mention counts
     `data/entity_mentions.csv` (`entity,count`) and `data/tag_mentions.csv` (`tag,count`).
   - `tools/classify_entities.py` — read distinct entities; run the OpenAI **Batch** job
     (chunked ~50/request, structured `{entity,type,canonical_name}` output); write/merge
     `data/entity_types.csv`. Incremental cache (skip already-classified on re-run); a sync
     `--sample N` dev mode.
   - `tools/build_term_stats.py` — join mentions × types, apply the deterministic canonical
     cleanup + alias merge, and roll up the small artifacts the apps read:
     `data/entity_type_breakdown.csv`, `data/entity_leaderboard.csv`, `data/tag_leaderboard.csv`,
     and `data/term_stats_meta.json` (distinct counts + totals + enrichment provenance).
   Show the flow as raw JSONL → mention CSVs → (LLM) entity_types → rollup artifacts → loaders →
   charts → tab/slide.

2. **Artifact schemas** — enumerate the concrete columns/keys of every file the pipeline writes
   AND reads, with types and an example row: the two mention CSVs, `entity_types.csv`, the three
   rollup CSVs (e.g. breakdown = `type,mentions,distinct_entities`; leaderboard =
   `canonical_name,type,mentions`; tag leaderboard = `tag,count`), and `term_stats_meta.json`
   (e.g. `n_distinct_entities`, `n_entity_mentions`, `n_distinct_tags`, `n_tag_mentions`,
   `model`, `enriched_at`, `n_classified`). State which artifacts are precomputed vs which
   headline numbers (per-record medians, coverage %) are derived live from the parquet
   `n_tags`/`n_entities` columns.

3. **The LLM classification design** — the most load-bearing part:
   - The **6-bucket taxonomy** with a one-line definition + 2-3 real corpus examples per bucket,
     and the rule that anything unclassifiable → `Other`.
   - The **prompt shape**: a system/instruction carrying the taxonomy once per request, a user
     payload of ~50 entity strings, and a required structured JSON response
     `[{entity, type, canonical_name}]`. State how unknown/garbled entities are handled and how a
     malformed/short response for a chunk is detected and retried.
   - The **Batch mechanics**: build the request `.jsonl`, submit one job, poll for completion,
     download + parse results, map back to entities by a stable per-request `custom_id`. State the
     `--sample N` synchronous path for prompt iteration. Clarify ONE batch job ≠ one giant request
     (chunking is output-token safety + isolated retry).
   - **Caching / idempotency**: re-runs only classify entities absent from `entity_types.csv`;
     the corpus is static so the mapping is built once and reused.
   - **Alias resolution**: how `canonical_name` + the deterministic cleanup (strip leading `U.S. `,
     unify punctuation/case/whitespace, trim) produce the merged leaderboard, and the explicit
     caveat that cross-request canonical naming is best-effort.
   - **Cost/scale envelope**: ~281K distinct entities, ~5,600 requests, ~$1 one-time on
     `gpt-4o-mini`, well under the Batch API's 50K-requests/file limit.

4. **Charts & surfaces** — define the three pure `df→go.Figure` builders to add to
   `carver_showcase/charts.py` and what each must show:
   - `fig_entity_type_breakdown` — the 6 buckets ranked by **mentions** (distinct-entity count in
     hover).
   - `fig_entity_leaderboard` — top ~20 canonical entities, **coloured by type**.
   - `fig_tag_leaderboard` — top ~20 themes.
   Plus the **headline metric tiles** (distinct entities/tags, total mentions, per-record medians).
   Then define the **Gallery "Themes & Entities" tab** (the 9th tab; tiles + 3 charts + the
   "across the full corpus" caption) and the **deck slide** (8→9) built from the same builders.
   State that the tab shows full-corpus stats and intentionally does NOT honour sidebar filters.

5. **Integration, loading & graceful degradation** — name the exact existing touch-points:
   `carver_showcase/config.py` (new path constants + the taxonomy + model/chunk constants);
   `carver_showcase/load.py` (`load_term_stats()` following `load_catalog`/`load_snapshot_meta`,
   returning the small tables or `None`); `apps/gallery.py` (extend the `TABS` list + add the tab
   body); `carver_showcase/deck.py` (one new slide). Specify that when the enrichment artifacts
   are ABSENT, the Gallery hides the tab and the deck skips the slide (a fresh checkout still
   runs). State the `requirements.txt` addition (`openai`) and that `OPENAI_API_KEY` is read only
   in the tools.

6. **Cross-cutting decisions** — testability (what is unit-tested with NO live OpenAI call:
   `extract_terms` counting, `classify_entities` request-builder + response-parser incl. the
   malformed→`Other` path with a stubbed client, `build_term_stats` mention-weighting + alias
   merge + cleanup, the 3 chart builders, and a Gallery smoke test for the new tab present +
   renders + graceful-when-absent); performance (artifacts are tiny, loaded via `st.cache_data`,
   no model call at render); honest-stats stance (real counts/percentages from the snapshot);
   and the constraints this design must honour (Gallery+deck only — NOT the cockpit; categories
   stay internal; no commit; secrets only in tools).

You MAY include a short illustrative directory tree, a couple of representative artifact rows,
and an example prompt/response pair to pin conventions, but the full file-by-file build list and
the test-by-test list are Stage 02 deliverables.

## Product context

See `goal.md` (carried into every stage) for the dataset shape, the verified field facts, why
the LLM is now in scope for entities, and the eight locked decisions plus inherited project
constraints. The annotations snapshot is already pulled to `data/annotations.jsonl`; `tags` and
`entities` are flat string lists under `output_data.metadata.*`. The existing codebase already
has the shared `carver_showcase/charts.py` builder pattern, `load.py` artifact loaders, a
`config.py` of `DATA_DIR` path constants, an 8-tab `apps/gallery.py`, and an 8-slide
`carver_showcase/deck.py` — this feature extends all of them; it does not restructure them.

## Hard constraints (must be honored by the design)

- **Entities use the LLM; tags do NOT.** Tag stats are deterministic frequency only.
- **One-time, cached, offline enrichment** — the model is NEVER called at app render; apps read
  precomputed artifacts.
- **6-bucket taxonomy exactly as locked**; alias-merged leaderboard via `canonical_name` +
  deterministic cleanup.
- **OpenAI Batch API**, one job, ~50 entities/request, `gpt-4o-mini`, sync `--sample` for dev.
- **Gallery + deck ONLY — do NOT touch the Cockpit.** Categories stay internal. No commit.
- **Secrets only in tools** (`OPENAI_API_KEY` from `.env`); derived artifacts stay git-ignored.
- **Full-corpus aggregate stats** — the tab does not react to sidebar filters (caption says so).

## Out of scope (this feature)

- LLM treatment of tags (tag clustering / theme families) — a possible future follow-up.
- Per-record entity filtering / making the tab react to sidebar filters.
- Any change to the Cockpit, to categories, or to the existing data pull.
- Re-pulling data or changing the Artifacts API route.

## Out of scope (this stage only — deferred to Stage 02)

- The dependency-ordered phased build plan and the explicit file-by-file creation/edit list.
- Ready-to-run code, final function signatures beyond illustrative sketches, and the
  test-by-test enumeration.
- The exact prompt wording at final-copy fidelity (sketch it; final tuning is a Stage 02/impl
  detail) — but DO decide the taxonomy definitions, the response schema, and the batch mechanics.

The spec MUST decide enough design (named tools + artifacts + their schemas, the classification
design, the chart builders, the integration touch-points, the deterministic alias-merge rules,
and the testing surface) that Stage 02 can produce the phased plan and file list without
re-deciding any of it.
