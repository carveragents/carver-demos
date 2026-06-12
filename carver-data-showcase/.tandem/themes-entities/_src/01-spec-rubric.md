# Rubric — Stage 01 SPEC (Themes & Entities)

The checker judges every draft against these criteria. A draft is APPROVED only when all are
satisfied (or any gap is explicitly and correctly justified as out-of-scope / deferred to Stage
02). This stage is the **design/PRD**: the phased build plan and per-file/test-by-test list are
deferred to Stage 02 and are NOT judged here — but the spec must decide enough design that Stage
02 can produce them without re-deciding (judged under criteria 1, 2, 3, 9, 11).

1. **Problem, scope & placement** — States the goal (turn `tags`/`entities` into an honest
   corpus-wide stats surface) and that it ships as a new Gallery "Themes & Entities" tab + one new
   deck slide. Names what is explicitly out of scope (LLM on tags, per-record filtering, any
   Cockpit/category change, re-pulling data).

2. **End-to-end pipeline & boundaries** — Specifies the three-tool flow (`extract_terms` →
   `classify_entities` → `build_term_stats`) with each tool's single responsibility, inputs, and
   outputs, and shows the full path raw JSONL → mention CSVs → entity_types → rollup artifacts →
   loaders → charts → tab/slide. Tools are small and independently testable. No model call lives
   on the app/render path.

3. **Artifact schemas are concrete** — Enumerates the actual columns/keys (with types + an example
   row) of every file written/read: `entity_mentions.csv`, `tag_mentions.csv`, `entity_types.csv`,
   `entity_type_breakdown.csv`, `entity_leaderboard.csv`, `tag_leaderboard.csv`, and
   `term_stats_meta.json`. States which numbers are precomputed vs derived live from the parquet
   `n_tags`/`n_entities` columns (per-record medians, coverage %).

4. **Entities use the LLM; tags do NOT** — The design is unambiguous that only entities are
   model-typed/de-duplicated, and tag stats are pure deterministic frequency (top-N + diversity
   tiles). No tag-clustering is built; it is named as a future follow-up.

5. **6-bucket taxonomy is fully specified** — Lists exactly the six locked buckets
   (`Regulator / Supervisor` incl. central banks, `Government body`, `International body`,
   `Company`, `Person`, `Other`), each with a one-line definition and ≥2 real corpus examples, and
   the unclassifiable → `Other` rule. No extra or renamed buckets.

6. **Classification design is build-ready** — Specifies the prompt shape (taxonomy carried per
   request, ~50-entity payload, required structured JSON `[{entity,type,canonical_name}]`); how a
   malformed/short chunk response is detected and retried; and stable mapping back to entities via
   a per-request `custom_id`. The response schema is concrete enough to parse against.

7. **Batch mechanics are correct & honest** — Describes ONE OpenAI **Batch** job built from a
   single request `.jsonl` of ~5,600 lines at ~50 entities each (`CHUNK_SIZE` tunable), submit →
   poll → fetch, plus a synchronous `--sample N` dev path. Explicitly clarifies that one batch job
   is NOT one giant model call — chunking is output-token safety + isolated retry. States the
   ~$1 / `gpt-4o-mini` / <50K-requests cost-scale envelope.

8. **Idempotent caching + deterministic alias merge** — Re-runs classify only entities missing
   from `entity_types.csv` (static corpus → built once). The leaderboard merges by `canonical_name`
   with a DETERMINISTIC cleanup pass (strip leading `U.S. `, unify punctuation/case/whitespace),
   and the spec states that merging affects only the leaderboard, not the 6-bucket breakdown, and
   names the best-effort caveat on cross-request canonical naming.

9. **Charts & surfaces are defined** — Defines the three pure `df→go.Figure` builders
   (`fig_entity_type_breakdown` by mentions w/ distinct in hover; `fig_entity_leaderboard` top-N
   canonical coloured by type; `fig_tag_leaderboard` top-N themes), the headline metric tiles, the
   Gallery tab layout (9th tab; tiles + 3 charts + "across the full corpus" caption), and the new
   deck slide (8→9) reusing the SAME builders so gallery/deck cannot drift.

10. **Aggregate-only behaviour is explicit** — The spec states the tab shows full-corpus
    aggregates and intentionally does NOT react to the sidebar filters the other tabs honour
    (because the lean parquet holds only `n_tags`/`n_entities`), with per-record filtering named as
    deferred. This is presented as a conscious decision, not an omission.

11. **Integration, loading & graceful degradation** — Names the exact touch-points (`config.py`
    constants + taxonomy/model/chunk; `load.py` `load_term_stats()` à la `load_catalog`;
    `apps/gallery.py` TABS + tab body; `deck.py` slide; `requirements.txt` += `openai`) and
    specifies that ABSENT artifacts → Gallery hides the tab + deck skips the slide, so a fresh
    checkout still runs. `st.cache_data` for the tiny artifacts.

12. **Constraints provably honored** — The design is Gallery + deck ONLY (no Cockpit touch),
    keeps categories internal (tags/entities are fine externally), reads `OPENAI_API_KEY` only
    inside the tools (never app/charts), keeps `annotations.jsonl` + derived artifacts git-ignored,
    and assumes no commit. The earlier project-wide no-LLM rule is correctly noted as deliberately
    lifted for THIS feature's offline entity enrichment.

13. **Testability** — Names what is unit-tested with NO live OpenAI call (extract counting;
    request-builder + response-parser incl. malformed→`Other` via a stubbed client; rollup
    mention-weighting + alias merge + cleanup; the 3 chart builders; a Gallery smoke test for the
    new tab present/renders + graceful-when-absent). Concrete enough for Stage 02 to enumerate
    tests from.

14. **Internal consistency & explicit assumptions** — Self-consistent; no contradictions between
    pipeline, artifact schemas, charts, and integration; relies only on fields that exist in the
    verified payload (`output_data.metadata.{tags,entities}` as flat string lists); states
    assumptions explicitly; decisions concrete enough that Stage 02 can build on them without
    re-litigating. No placeholders/TBDs in load-bearing sections.
