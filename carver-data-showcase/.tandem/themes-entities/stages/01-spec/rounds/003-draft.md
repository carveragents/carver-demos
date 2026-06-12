# Themes & Entities — Feature Spec (Stage 01 design / PRD)

**Status:** design/PRD for review. This document decides *what gets built, what each
piece does, every load-bearing decision, and how it plugs into the existing codebase*.
The dependency-ordered build sequence and the per-file / test-by-test change list are
**Stage 02** (the phased plan) and are intentionally out of scope here; this spec
decides enough that Stage 02 can produce them without re-deciding anything.

---

## 0. One-paragraph summary

The showcase already surfaces scores, jurisdictions, regulators, update-types,
richness, and a single-record drill-down. Two of the richest annotation fields —
`tags` (free-text thematic labels) and `entities` (named organisations / people /
places) — have no aggregate view. This feature adds a **"Themes & Entities"** surface
(a 9th Gallery tab + one new deck slide) showing **entities, typed** into a 6-bucket
breakdown plus an alias-merged "most-referenced bodies" leaderboard, and **tags as
themes** (a top-N bar + diversity tiles). Entity typing + alias resolution come from a
**one-time, offline OpenAI Batch job** (~$1, `gpt-4o-mini`, cached forever); tags stay
**pure deterministic frequency** (no LLM). The model is **never** called at render —
the apps read tiny precomputed CSV/JSON artifacts. The tab shows **full-corpus
aggregates** and intentionally does not honour the sidebar filters the other tabs use.

---

## 1. Problem, scope & placement

**Goal.** Turn the annotations' `tags` and `entities` fields into an honest,
corpus-wide stats surface that makes the dataset's *breadth of who and what it talks
about* tangible — "thousands of regulators, companies and people across 234K themes" —
with one model-typed entity breakdown and a clean themes view.

**Ships as.** Exactly two surfaces, sharing the same pure chart builders so they cannot
drift:
- A new **Gallery tab "Themes & Entities"** — the Gallery's **9th** tab.
- A new **deck slide** — the deck grows **8 → 9** slides.

**Verified data shape** (against the 211,489-record snapshot; tools recompute, so all
numbers track whatever snapshot is loaded — see §9):
- `tags` present on **88.5%** of records, `entities` on **92.5%**.
- **234,002** distinct tags (**1.54M** mentions, median **8**/record).
- **281,180** distinct entities (**~900K** mentions, median **3**/record).
- Both brutally long-tailed (~60–70% of distinct values appear once).
- Entities are **raw strings, not pre-typed** (0 of ~900K instances carry a type), e.g.
  `["Christopher P. Buttigieg", "EBA", "Malta Financial Services Authority", "MFSA"]`.
- The named-entity set is **regulator-heavy** (European Commission, ECB, FTC, ESMA, SEC,
  FDIC, EBA, EMA, FDA, IMF, FCA …), with companies (Mastercard, CIBanco), people, and
  places (Bolivia, Croatia) in the tail.

**Explicitly out of scope (this feature)** — see §10 for the full list:
- LLM treatment of **tags** (theme clustering / families) — a possible future follow-up.
- **Per-record entity filtering** / making the tab react to sidebar filters.
- Any change to the **Data-Quality Cockpit**, to **categories**, or to the data pull /
  Artifacts API route.

---

## 2. End-to-end architecture & data flow

A **three-tool offline pipeline** produces small artifacts the apps read. Each tool has
one responsibility, runs from the CLI, and is independently unit-testable. **No model
call lives on the app/render path** — the apps only read precomputed files.

```
data/annotations.jsonl                     (raw corpus, git-ignored, already pulled)
        │
        │  tools/extract_terms.py   ── stream once, count mentions (NO key, NO LLM)
        ▼
data/entity_mentions.csv  (entity,count)        data/tag_mentions.csv  (tag,count)
        │
        │  tools/classify_entities.py  ── OpenAI BATCH job, distinct entities only
        │                                 (reads OPENAI_API_KEY; incremental cache)
        ▼
data/entity_types.csv  (entity,type,canonical_name)     [tool-internal cache]
        │
        │  tools/build_term_stats.py  ── join mentions × types, dedupe cleanup +
        │                                alias merge, roll up (NO key, NO LLM)
        ▼
data/entity_type_breakdown.csv   data/entity_leaderboard.csv
data/tag_leaderboard.csv         data/term_stats_meta.json     [app-facing rollups]
        │
        │  carver_showcase/load.py :: load_term_stats()   (framework-agnostic; → dict|None)
        ▼
carver_showcase/charts.py  (3 new pure df→go.Figure builders)
        │
        ├──► apps/gallery.py     "Themes & Entities" tab  (tiles + 3 charts + caption)
        └──► carver_showcase/deck.py   one new slide       (same builders → can't drift)
```

### 2.1 `tools/extract_terms.py` — mention counting (deterministic)
- **Responsibility:** stream `data/annotations.jsonl` exactly once and emit raw mention
  counts. **No OpenAI key, no model.**
- **Input:** `data/annotations.jsonl` (the full raw corpus).
- **How:** reuse the existing streaming primitive `carver_showcase.ingest.load_snapshot`
  (the same generator `load.load_normalized` uses) so memory stays bounded — the parquet
  does **not** carry the tag/entity strings, only `n_tags`/`n_entities`, so the strings
  must come from the JSONL. For each envelope read `output_data.metadata.tags` and
  `output_data.metadata.entities` (each a flat `list[str]`; absent/`None` → skip),
  trimming whitespace and dropping empty strings, and accumulate two `collections.Counter`s.
- **Mention definition (pinned — see §3.1):** `count` is **total occurrences across the
  corpus** — the `Counter` is incremented once per list item, so a term appearing twice in
  one record's list adds 2. Within-record duplicates are rare, but the rule is fixed as
  **per-occurrence** so the breakdown/leaderboard weights are unambiguous.
- **Output:** `data/entity_mentions.csv` (`entity,count`) and `data/tag_mentions.csv`
  (`tag,count`), each written in a **fully deterministic total order**: `count` **descending,
  then `entity` (resp. `tag`) ascending** as a stable tie-break. This order is load-bearing
  — `classify_entities` chunks by consuming the file top-to-bottom, so the `chunk-{i}` →
  entity-list mapping (§4.4) is reproducible across separate processes **from the file
  alone**, with no reliance on in-memory state surviving.

### 2.2 `tools/classify_entities.py` — LLM entity typing (OpenAI Batch)
- **Responsibility:** assign each **distinct** entity a `type` (one of 6 buckets) and a
  `canonical_name`, via **one** OpenAI Batch job; cache results idempotently.
- **Input:** the `entity` column of `data/entity_mentions.csv` (distinct entities), minus
  any already present in `data/entity_types.csv` (the cache).
- **Output:** `data/entity_types.csv` (`entity,type,canonical_name`) — created on first
  run, **merged** (appended) on re-runs.
- **Secrets:** reads `OPENAI_API_KEY` from `.env` (`load_dotenv(ROOT/.env)` +
  `os.environ["OPENAI_API_KEY"]`), exactly as the pull tools read `CARVER_API_KEY`. This
  is the **only** module that imports `openai` or touches the key.
- Full design in **§4**.

### 2.3 `tools/build_term_stats.py` — rollup (deterministic)
- **Responsibility:** join mentions × types, apply the deterministic canonical cleanup +
  alias merge, and roll up the small artifacts the apps read. **No OpenAI key, no model.**
- **Inputs:** `entity_mentions.csv`, `tag_mentions.csv`, `entity_types.csv`.
- **Outputs:** `entity_type_breakdown.csv`, `entity_leaderboard.csv`, `tag_leaderboard.csv`,
  `term_stats_meta.json`.
- Rollup logic in **§3.5** and **§4.5**.

**Why three tools, not one:** the expensive/keyed step (classification) is isolated and
cached so the cheap deterministic steps (extract, rollup) can be re-run freely; and each
is trivially testable in isolation (§8.2).

---

## 3. Artifact schemas

Every file the pipeline writes **and** reads, with concrete columns/keys, types, and an
example row. All live under `data/` and are therefore git-ignored by the existing
`data/*.csv` / `data/*.json` / `data/*.jsonl` globs (no `.gitignore` change needed).

### 3.1 `data/entity_mentions.csv`  *(written by extract; read by classify + rollup)*
| column | type | meaning |
|---|---|---|
| `entity` | str | raw entity string exactly as it appears in the annotation |
| `count`  | int | **total occurrences (mentions) across the corpus** — a `Counter` over each record's `entities` list (per-occurrence; within-record duplicates, which are rare, each add 1). This is the single "mentions" weight reused by the breakdown and leaderboard (§3.4–3.5). |

Rows are ordered `count` desc, then `entity` asc (the deterministic total order §2.1 relies
on for reproducible chunking). Example: `European Central Bank,18223`

### 3.2 `data/tag_mentions.csv`  *(written by extract; read by rollup)*
| column | type | meaning |
|---|---|---|
| `tag`   | str | raw tag string |
| `count` | int | total occurrences (mentions) across the corpus — same per-occurrence `Counter` rule as §3.1. |

Rows are ordered `count` desc, then `tag` asc. Example: `anti-money laundering,9120`

### 3.3 `data/entity_types.csv`  *(written by classify; read by rollup)* — tool-internal cache
| column | type | meaning |
|---|---|---|
| `entity` | str | the distinct entity string (join key back to mentions) |
| `type` | str | one of the 6 buckets (§4.1); never blank — unclassifiable → `Other` |
| `canonical_name` | str | model's normalised display name for the entity |

Example: `ECB,Regulator / Supervisor,European Central Bank`

> This file can grow to a few hundred KB (~281K rows). It is **tool-internal** — the apps
> never read it. Only the three rollups + meta below reach the apps.

### 3.4 `data/entity_type_breakdown.csv`  *(written by rollup; read by apps)*
| column | type | meaning |
|---|---|---|
| `type` | str | bucket name (all 6 present, zero-filled if empty) |
| `mentions` | int | Σ mentions of all entities in this bucket |
| `distinct_entities` | int | count of distinct entities in this bucket |

Example: `Regulator / Supervisor,412005,38112`

### 3.5 `data/entity_leaderboard.csv`  *(written by rollup; read by apps)*
Alias-merged, ranked. Stores the top ~50 rows (charts show 20).
| column | type | meaning |
|---|---|---|
| `canonical_name` | str | display name of the merged body (most-mentioned variant) |
| `type` | str | bucket of the merged group |
| `mentions` | int | Σ mentions across all merged variants |

Example: `Securities and Exchange Commission,Regulator / Supervisor,53110`

### 3.6 `data/tag_leaderboard.csv`  *(written by rollup; read by apps)*
Top ~50 tags by frequency (charts show 20). Pure frequency — **no LLM**.
| column | type | meaning |
|---|---|---|
| `tag` | str | tag string |
| `count` | int | mentions |

Example: `data protection,7841`

### 3.7 `data/term_stats_meta.json`  *(written by rollup; read by apps)*
```json
{
  "n_distinct_entities": 281180,
  "n_entity_mentions": 900342,
  "n_distinct_tags": 234002,
  "n_tag_mentions": 1542118,
  "model": "gpt-4o-mini",
  "enriched_at": "2026-06-11T14:05:00Z",
  "n_classified": 281180
}
```

### 3.8 Precomputed vs. derived-live
- **Precomputed (by the tools, read as-is):** the 6-row breakdown, both leaderboards, and
  all `term_stats_meta.json` keys — distinct counts, total mentions, model + provenance.
- **Derived live in the apps from the parquet `n_tags`/`n_entities` columns:** the
  **per-record medians** (`median(n_entities)`, `median(n_tags)`) and **coverage %**
  (`(n_entities > 0).mean()`, `(n_tags > 0).mean()`). These are cheap operations on Int64
  columns already in memory; computing them live keeps a single source of truth for the
  per-record distribution (the same parquet the rest of the gallery reads).
  - *Assumption (explicit, immaterial):* the gallery's parquet has been curated by
    `drop_noise_update_types`, which drops a sub-0.01%-of-volume update-type tail; the
    median/coverage over it is materially identical to the raw corpus. The caption still
    reads "across the full corpus." (Distinct counts + totals come from `meta`, which the
    tools compute over the raw JSONL, so the big headline numbers are exact regardless.)

---

## 4. The LLM classification design (most load-bearing)

### 4.1 The 6-bucket taxonomy (locked; mutually exclusive; unclassifiable → `Other`)
The model assigns each entity to **exactly one** of these six buckets. No extra, renamed,
or split buckets. **Every example below is a real entity string confirmed present in the
current annotation snapshot** — verified by sampling `data/annotations.jsonl` (a
60,000-record pass; the per-example mention count from that sample is shown in parentheses)
and/or named in the verified-facts brief. No bucket's examples are deferred to a later
stage.

| Bucket | One-line definition | Verified corpus examples (sample mention count) |
|---|---|---|
| **`Regulator / Supervisor`** | A body that regulates/supervises a sector, **including central banks**. | Securities and Exchange Commission (890), Financial Conduct Authority (490), European Central Bank (central bank, 872), Deutsche Bundesbank (central bank, 344) |
| **`Government body`** | A government organ that is not primarily a financial supervisor: ministries, executive departments, legislatures, courts, law-enforcement. | U.S. Department of the Treasury (350), U.S. Department of Labor (249), U.S. Department of Housing and Urban Development (71), U.S. Department of the Interior (90) |
| **`International body`** | Intergovernmental and standard-setting organisations. | International Monetary Fund (393), Bank for International Settlements (447), Basel Committee on Banking Supervision (158), OECD (307) |
| **`Company`** | A commercial firm / private-sector organisation. | Mastercard, CIBanco (both verified against the full snapshot per the brief) |
| **`Person`** | A named individual (official, executive, etc.). | Christine Lagarde (103), Jerome H. Powell (91), Vanessa A. Countryman (178), Leonardo Villar (317) |
| **`Other`** | Places, and anything genuinely unclassifiable. | Saudi Arabia (129); Bolivia, Croatia (places, per the brief); garbled/unknown strings |

The taxonomy strings live in `config.py` as `ENTITY_TYPES` (ordered tuple) and
`ENTITY_TYPE_DEFINITIONS` (bucket → definition), so the classifier prompt, the parser
validation, and the chart colours all read the same source of truth.

### 4.2 Prompt shape (sketch — final copy is a Stage 02 detail)
Each request carries the **taxonomy once** (system/instruction message) plus a user
payload of ~50 entity strings, and must return a **structured JSON array**. Sketch:

- **System / instruction:** "You classify named entities from regulatory text into
  exactly one of these six types: `<the 6 buckets + one-line definitions>`. Return strict
  JSON only. For every input entity emit one object `{entity, type, canonical_name}` where
  `entity` is echoed verbatim, `type` is one of the six exact strings, and `canonical_name`
  is the entity's full, de-abbreviated, conventionally-cased name. If you cannot identify
  an entity, use `type: "Other"` and set `canonical_name` to the input string. Output the
  same number of objects as inputs, in order."
- **User payload:** a JSON array of the ~50 entity strings for this chunk.
- **Response (required schema), parsed against:**
  ```json
  [
    {"entity": "ECB", "type": "Regulator / Supervisor", "canonical_name": "European Central Bank"},
    {"entity": "Mastercard", "type": "Company", "canonical_name": "Mastercard"},
    {"entity": "Bolivia", "type": "Other", "canonical_name": "Bolivia"}
  ]
  ```
  Enforced via the model's structured-output / JSON mode; `temperature=0` for determinism.
- **Unknown / garbled entities:** the model is instructed to still emit a row for them,
  `type="Other"`, `canonical_name=entity` (never dropped — every input gets a row). Such a
  row is a **valid, complete** response (the model confidently labelling an unidentifiable
  string `Other`); it is *not* a malformed response and does **not** trigger a retry. This
  is distinct from the malformed/short responses handled in §4.3.

### 4.3 Response validation & retry (per chunk)
A chunk's response is **short / malformed** if any of: not valid JSON; **fewer objects than
entities sent** (a "short" response); an object missing `entity`/`type`/`canonical_name`; a
`type` not in the 6 buckets; or `entity` values that don't reconcile to the chunk's inputs.
Detection is per chunk via the stable `custom_id` (§4.4). The policy is **detect → retry →
fall back**, in that order — short/malformed output is **never** silently defaulted to
`Other` on first sight:

1. **Detect.** After parsing the Batch output, each chunk is validated against the schema +
   expected entity set. A chunk passes only if it returns a well-formed object for **every**
   entity it was sent (a `type="Other"` row from §4.2 counts as well-formed).
2. **Retry (bounded).** Any chunk that fails — and, within an otherwise-valid chunk, the
   specific subset of entities that are missing/invalid — is **collected and re-classified**
   through the synchronous `--sample` path, up to `MAX_RETRIES` (small, e.g. 2). Each retry
   re-sends only the unresolved entities with the same prompt; transient model/format
   failures typically resolve on the first retry.
3. **Fall back (only after retries are exhausted).** Entities **still** unresolved after
   `MAX_RETRIES` are the explicit fallback path: written as `type="Other",
   canonical_name=entity` so the corpus is always fully covered, and **logged with a count**
   (so an unusually large fallback set is visible, not silent).

This is unit-tested with a **stubbed client**: a stub returning short/malformed payloads
must trigger the retry path (assert the retry is attempted), and a stub that stays malformed
through `MAX_RETRIES` must produce the explicit `Other` fallback — all with no network.

### 4.4 Batch mechanics (ONE job, sharded — not one giant call)
1. **Compute the input set & chunk deterministically.** Read the distinct entities to
   classify as the `entity` column of `entity_mentions.csv` **in its on-disk order** (§2.1:
   `count` desc, `entity` asc), minus those already in `entity_types.csv`. Chunk by
   consuming that ordering top-to-bottom into groups of `ENTITY_CHUNK_SIZE` (~50). Because
   the source file order is fully deterministic, **`chunk-{i}` → entity-list is reproducible
   from the file alone** — it does not depend on any in-memory state surviving the process.
2. **Build** a single request file `data/entity_batch_requests.jsonl`: one line **per
   chunk**. Each line is a Batch request envelope
   `{custom_id, method:"POST", url:"/v1/chat/completions", body:{model, messages, ...}}`
   with `custom_id = f"chunk-{i:05d}"` (the index into the deterministic chunking above).
3. **Resume-or-submit (idempotent across process death).** Before submitting, check for a
   persisted in-flight sidecar **`data/entity_batch_state.json`** holding at least
   `{batch_id, input_file_path, model, input_row_count, input_sha256}` — where
   `input_sha256` is a content hash of the exact distinct-entity input set (so a changed
   input set is detected).
   - **No sidecar (or its hash ≠ the current input set):** upload
     `entity_batch_requests.jsonl` via the Files API (`purpose="batch"`), create ONE batch
     against `/v1/chat/completions` with `completion_window="24h"`, and **write the sidecar**
     with the returned `batch_id` *before* the first poll.
   - **Live sidecar matching the current input set:** **resume** — poll/fetch that existing
     `batch_id` instead of submitting a new job.
4. **Poll** the batch status until `completed`. A terminal `failed`/`expired` → **clear the
   sidecar**, surface the error, and allow a resubmit on the next run.
5. **Fetch + parse** the output file; for each line, look up `custom_id` → the chunk's
   entity list (re-derived per step 1), validate (§4.3), and collect
   `{entity,type,canonical_name}` rows.
6. **Map back & write/merge** into `entity_types.csv`, **then clear the sidecar** — only
   after the output is successfully fetched and merged.

This makes `classify_entities` **safely re-runnable**: at most **one live Batch job per
distinct-entity input set**. If the process dies (or the machine sleeps) between submit and
fetch, the next run reads the sidecar and resumes the in-flight job rather than submitting a
duplicate (re-spending ~$1 and re-waiting up to 24h). Exact sidecar serialization is a
Stage-02/impl detail; what is decided here is *what* is persisted, *when* it is read, and
*when* it is cleared.

> **Clarification (correct & honest):** *one Batch job ≠ one giant model call.* The job's
> input file holds ~5,624 request lines (§4.6); each line is an **independent** small
> completion classifying ~50 entities. Sharding at ~50 is for (a) **output-token safety**
> — a 50-object JSON array is small and reliably within output limits — and (b) **isolated
> retry** — one bad line never sinks the run. `ENTITY_CHUNK_SIZE` is a tunable constant.

**`--sample N` (synchronous dev path):** a `--sample N` flag classifies N entities (a few
chunks) via plain **synchronous Chat Completions** — no Files upload, no Batch, no polling.
It prints results (and is reused by the §4.3 retry). This is the loop used to iterate the
prompt before committing the full Batch run; it does **not** write the full cache.

### 4.5 Idempotent caching & deterministic alias merge
- **Idempotency (two layers):** the corpus is static, so the mapping is built **once**.
  (a) On any re-run, `classify_entities` classifies only entities **absent** from
  `entity_types.csv` (set difference on the `entity` column); an already-complete cache →
  no Batch job submitted. (b) For the window *during* a single async run, the
  `entity_batch_state.json` sidecar (§4.4) guarantees a process that dies between submit and
  fetch **resumes** the in-flight job rather than submitting a duplicate — so there is at
  most one live Batch job per distinct-entity input set, before *or* after the cache is
  written.
- **Alias merge (deterministic, at rollup time in `build_term_stats`):**
  - Each classification returns `{type, canonical_name}`. The leaderboard merges by a
    `merge_key = _clean_canonical(canonical_name)` where `_clean_canonical`:
    1. strips a leading `"U.S. "`,
    2. collapses internal whitespace runs to one space and trims surrounding whitespace,
    3. unifies punctuation (e.g. drops surrounding quotes / trailing `.`),
    4. casefolds **for the key only**.
  - Group by `merge_key`: `mentions = Σ count`; `type` = the type of the highest-mention
    member (deterministic tie-break by mentions then name); `canonical_name` (display) =
    the original `canonical_name` of the highest-mention member. So `SEC` /
    `Securities and Exchange Commission` / `U.S. Securities and Exchange Commission`
    collapse into one bar with the combined total.
  - **The 6-bucket breakdown is computed BEFORE/INDEPENDENT of merging** — it counts each
    distinct entity once into its `type` and sums mentions per type. Merging affects **only
    the leaderboard**, never the breakdown.
  - **Best-effort caveat (stated honestly in the spec and in a tab caption):** because each
    Batch request sees only its ~50 entities and has no global view, `canonical_name` is
    consistent *within* a request but only **best-effort across** requests; the
    deterministic cleanup catches near-identical forms (case/punctuation/`U.S. ` variants)
    but not every semantic synonym. This is acceptable for a "top bodies" leaderboard —
    the dominant variants of the most-referenced bodies merge — and is the reason no
    second LLM pass is added (YAGNI).

### 4.6 Cost / scale envelope
- ~**281,180** distinct entities ÷ ~50 per request = **~5,624** request lines in **one**
  Batch input file — well under the Batch API's **50,000-requests-per-file** limit.
- Model **`gpt-4o-mini`** (configurable `OPENAI_MODEL`), structured/JSON output,
  `temperature=0`. Batch pricing (~50% off sync) + tiny per-entity tokens ⇒ **~$1
  one-time**. Cached forever; never re-run at app load.

---

## 5. Charts & surfaces

### 5.1 Three pure `df→go.Figure` builders (added to `carver_showcase/charts.py`)
Same conventions as the existing builders: pure `pandas` + `plotly`, no Streamlit/kaleido,
and **defensive** — each returns `_empty_fig(...)` (the existing helper) when its frame is
`None`/empty/missing a column, so neither gallery nor deck crashes. Added to `__all__`.

1. **`fig_entity_type_breakdown(breakdown_df) -> go.Figure`** — the **6 buckets ranked by
   `mentions`** (horizontal bar, descending). Hover surfaces `distinct_entities`
   ("38,112 distinct"). Title "Entity types by mentions".
2. **`fig_entity_leaderboard(leaderboard_df, n=20) -> go.Figure`** — top-**N** canonical
   entities by `mentions` (horizontal bar), **coloured by `type`** using a discrete colour
   map (`ENTITY_TYPE_COLORS` in `config.py`, one colour per bucket), with a type legend.
   Title "Most-referenced bodies (top 20)".
3. **`fig_tag_leaderboard(tag_df, n=20) -> go.Figure`** — top-**N** tags by `count`
   (horizontal bar). Title "Top themes (tags)".

(Both `*_leaderboard` builders use `nlargest`/head as the existing `fig_*` builders do, so
the stored top-50 CSV can render any `n ≤ 50`.)

### 5.2 Headline metric tiles
Rendered by the gallery (`render.kpi_cards`) and the deck (`_draw_kpis`):
- **Distinct entities** and **distinct tags** — from `meta` (precomputed).
- **Total entity mentions** and **total tag mentions** — from `meta` (precomputed).
- **Median entities / record** and **Median tags / record** — derived live from the
  parquet (§3.8).
- **Entity coverage** (`% of records with ≥1 entity` ≈ 92.5%) and **Tag coverage**
  (`% of records with ≥1 tag` ≈ 88.5%) — derived live from the parquet
  (`(n_entities > 0).mean()`, `(n_tags > 0).mean()`), the headline coverage facts from the
  brief. (This is the single place coverage % is surfaced; §3.8 and §8.3 describe it as
  derived-live, and these two tiles are where it lands.)
- A **tag diversity** line (no LLM): distinct tags + total mentions + median tags/record
  (the "234K themes" headline).

### 5.3 Gallery "Themes & Entities" tab (the 9th tab)
- Appended to the `TABS` list in `apps/gallery.py` so it becomes the **9th** tab and the
  existing indexed tab bodies (`tabs[0]`…`tabs[7]`) are **unchanged** (low-churn,
  deliberate; exact ordering among aggregate tabs is cosmetic and a Stage 02 nicety).
- **Body:** header + an **"across the full corpus"** caption that states the tab shows
  full-corpus aggregates and **does not react to the sidebar filters** (§6); then the
  headline tiles (§5.2); then the three charts (breakdown, entity leaderboard, tag
  leaderboard); then the best-effort alias caveat (§4.5) as a small note.
- **Data source:** the tab reads the loaded `load_term_stats()` dict and the **unfiltered**
  `df_full` for the live medians/coverage — **not** the filtered `view`.
- **Graceful absence:** when `load_term_stats()` returns `None`, the tab label is **not
  added** to `TABS` at all (so a fresh checkout with no enrichment artifacts shows the
  original 8 tabs and still runs). See §7.

### 5.4 Deck slide (8 → 9)
A new `_slide_themes_entities(c, ctx, df, catalog_df)` built from the **same** shared
builders + `_draw_kpis`/`_draw_chart`/`_draw_callout`, so the deck cannot drift from the
gallery. Inserted before `_slide_about`.

**Concrete composition (decided here).** A fixed 960×540 16:9 page (existing slides fit
~two half-width charts) cannot hold three full charts legibly, so the deck slide shows a
**curated two-chart subset** while the gallery tab keeps all three:
- **Charts (2, at deck fidelity):** the **entity type breakdown** (`fig_entity_type_breakdown`)
  and the **most-referenced-bodies leaderboard** (`fig_entity_leaderboard`, **top ~12** here
  vs. 20 in the gallery, so the bars stay readable on the page). **Tags are NOT a third
  full chart on the deck** — tag richness rides as a KPI tile + a callout line.
- **Layout** (mirrors `_slide_overview`/`_slide_scores`; exact points are an impl detail):
  - `_draw_title("Themes & entities", "Who and what the corpus talks about")`.
  - One **KPI row** (`_draw_kpis`, ~y=100, h≈58): *Distinct entities · Distinct tags ·
    Entity coverage · Tag coverage · Median entities/rec* — carries the tag headline as a
    tile so tags are represented without a chart.
  - **Two half-width charts** side by side (`half = (PAGE_W - 2·MARGIN - 16)/2`, ~y=176,
    h≈250): breakdown **left**, leaderboard **right**.
  - A **full-width callout** (`_draw_callout`, ~y=434, h≈64): the **top themes** line
    (e.g. "Top themes: anti-money laundering · data protection · …", from `tag_leaderboard`)
    **plus** the best-effort alias caveat one-liner (§4.5).
- `_build_context` is extended to carry the term-stat numbers (distinct counts, totals,
  medians, coverage %, top buckets, top themes) so the KPI/callout text matches the charts.
- **Graceful absence:** `build_deck` composes its **active slide list** at runtime — the
  themes slide is included only when `load_term_stats()` returns data; otherwise the deck
  builds with the original 8 slides. (The existing `tests/test_deck.py` page-count assertion
  is updated in Stage 02 to count the active slide list rather than a fixed `len(SLIDES)`.)

---

## 6. Aggregate-only behaviour (explicit, conscious decision)
The lean parquet stores only `n_tags`/`n_entities` **counts**, not the per-record tag/entity
**strings**. Therefore the Themes & Entities surface shows **full-corpus aggregates** and
**intentionally does not honour** the sidebar filters the other tabs apply to `view`. A
caption states this plainly ("Stats across the full corpus — not affected by the sidebar
filters"). Making the tab filter-reactive (e.g. "entities for one jurisdiction") would
require **per-record entity storage + a join**, which is **deferred (YAGNI for v1)** and
named as such — this is a deliberate decision, not an omission.

---

## 7. Integration, loading & graceful degradation (exact touch-points)

| File | Change |
|---|---|
| `carver_showcase/config.py` | **+ path constants** `ENTITY_MENTIONS_CSV`, `TAG_MENTIONS_CSV`, `ENTITY_TYPES_CSV`, `ENTITY_TYPE_BREAKDOWN_CSV`, `ENTITY_LEADERBOARD_CSV`, `TAG_LEADERBOARD_CSV`, `TERM_STATS_META_JSON` (all under `DATA_DIR`); **+ taxonomy** `ENTITY_TYPES` (ordered tuple of the 6), `ENTITY_TYPE_DEFINITIONS`, `ENTITY_TYPE_COLORS`; **+ enrichment constants** `OPENAI_MODEL = "gpt-4o-mini"`, `ENTITY_CHUNK_SIZE = 50`, `ENTITY_LEADERBOARD_TOP_N = 20`, `TAG_LEADERBOARD_TOP_N = 20`. (Logic-free, matching the module's existing style.) |
| `carver_showcase/load.py` | **+ `load_term_stats(...) -> dict \| None`**, following `load_catalog` / `load_snapshot_meta` (framework-agnostic, no Streamlit). Reads the **3 rollup CSVs + `term_stats_meta.json`**; returns `{"breakdown": df, "entity_leaderboard": df, "tag_leaderboard": df, "meta": dict}` or **`None`** when the core artifacts are absent. It does **not** read `entity_types.csv` or the mention CSVs (tool-internal). |
| `carver_showcase/charts.py` | **+ 3 builders** (§5.1), added to `__all__`. |
| `apps/gallery.py` | Cache `load_term_stats()` via a `@st.cache_data` wrapper (e.g. `_load_term_stats()`); conditionally append `"Themes & Entities"` to `TABS`; add the tab body (§5.3). |
| `carver_showcase/deck.py` | **+ `_slide_themes_entities`**; extend `_build_context`; compose the active slide list in `build_deck` (§5.4). |
| `requirements.txt` | **+ `openai`** (pinned, per the repo's fully-pinned convention; exact version chosen at install in Stage 02). |
| `.gitignore` | **No change** — every new artifact lives under `data/` and is already ignored by `data/*.csv` / `data/*.json` / `data/*.jsonl`. |

**Graceful degradation (fresh checkout runs):** with no enrichment artifacts, the gallery
**hides** the tab (not appended to `TABS`) and the deck **skips** the slide; both run
exactly as today. The tiny artifacts are wrapped in `st.cache_data` at the app edge.

---

## 8. Cross-cutting decisions

### 8.1 Constraints provably honored
- **Gallery + deck ONLY — the Data-Quality Cockpit is untouched.** No change to
  `apps/cockpit.py` or its data path; the new loader/charts are additive and the cockpit
  imports none of them.
- **Categories stay internal.** The tab surfaces **tags** and **entities** (annotation
  content — fine externally) and **never** topic categories. (The existing gallery smoke
  test that asserts no Category filter remains valid.)
- **Secrets only in tools.** `OPENAI_API_KEY` is read **only** inside
  `tools/classify_entities.py`; `carver_showcase/*` and `apps/*` never import `openai` or
  reference the key. `extract_terms.py` / `build_term_stats.py` need no key.
- **Derived artifacts git-ignored; no commit.** All outputs are under `data/` (ignored);
  all work stays uncommitted (the user merges via their own flux workflow).
- **The project-wide no-LLM stance is deliberately lifted for THIS feature only**, and
  only for the **one-time, offline** entity enrichment — the model is **never** called at
  render. Tags remain pure deterministic frequency.

### 8.2 Testability (everything below runs with NO live OpenAI call)
- **`extract_terms`:** counting over a tiny temp JSONL → correct `entity,count` /
  `tag,count`; whitespace-trim / empty-string drop; missing-field and non-list
  `tags`/`entities` → skipped (not crashed).
- **`classify_entities` (stubbed client):** the **request-builder** (deterministic
  chunking into ~50 from the `entity_mentions.csv` order, `custom_id` format, request-body
  shape, taxonomy present); the **response-parser** (maps `custom_id` → entities; validates
  the schema); the **detect → retry → fall back** policy (§4.3) — a stub returning a
  short/malformed chunk triggers the bounded retry (assert the retry is attempted), and a
  stub that stays malformed through `MAX_RETRIES` yields the explicit `type="Other"`
  fallback; and the **resume-or-submit** sidecar logic (§4.4) — given a sidecar with a live
  `batch_id` matching the input hash the tool **resumes** (no new submit), a terminal
  `failed`/`expired` clears it, and a missing/mismatched sidecar submits fresh. The
  `--sample` synchronous path is exercised with the same stubbed client. The deterministic
  `entity_mentions.csv` ordering (§2.1) is asserted so chunking is reproducible.
- **`build_term_stats`:** mention-weighting (breakdown sums mentions, counts distinct
  entities once); **alias merge** by `canonical_name` + the deterministic `_clean_canonical`
  cleanup (`U.S. ` strip, case/punct/whitespace); and the invariant that **merging does not
  change the 6-bucket breakdown**.
- **3 chart builders:** each returns a `go.Figure` with ≥1 trace on a small frame, and the
  defensive `_empty_fig` path on empty/`None`/missing-column input (extends
  `tests/test_charts.py`).
- **Gallery smoke (`tests/test_gallery_smoke.py`):** the new tab is present + renders when
  artifacts exist, and is **gracefully absent** (no exception, tab hidden) when they are
  not.
- **Deck (`tests/test_deck.py`):** with kaleido stubbed and term stats present, the deck
  has the themes slide (page count = active-slide count); absent → builds without it.

### 8.3 Performance & honest-stats
- Artifacts are **tiny** (6-row breakdown; ~50-row leaderboards; a small meta JSON) and
  the multi-hundred-KB `entity_types.csv` is **tool-internal**, never app-loaded. All
  app-facing loads are wrapped in `st.cache_data`; **no model call at render**. Live
  medians/coverage are a single `.median()` / `.notna().mean()` over an in-memory Int64
  column.
- **Honest stats:** every headline number is computed from the loaded snapshot (the tools
  recompute distinct counts/mentions per snapshot; medians/coverage derive from the same
  parquet the rest of the gallery reads) — nothing is hard-coded.

---

## 9. Internal consistency, assumptions & open items

- **Fields relied on (all verified present):** `output_data.metadata.tags` and
  `output_data.metadata.entities` as flat `list[str]` (read today in
  `carver_showcase/normalize.py`); the parquet `n_tags` / `n_entities` Int64 columns
  (declared in `carver_showcase/schema.py`). No new field is assumed.
- **Assumptions (explicit):**
  1. Mention strings are sourced by **streaming `annotations.jsonl`** (the parquet does not
     carry them) — see §2.1.
  2. Live medians/coverage are over the **curated** gallery parquet; the dropped
     update-type noise is <0.01% of volume, so they are materially identical to the raw
     corpus (§3.8). Distinct counts/totals come from `meta` (computed over raw JSONL), so
     the big numbers are exact.
  3. The verified counts (281,180 entities / 234,002 tags, etc.) are point-in-time; the
     tools recompute them, so the surface tracks whatever snapshot is loaded.
- **Best-effort (named, not a TBD):** cross-request `canonical_name` consistency (§4.5).
- **No placeholders in load-bearing sections.** The only item deferred to Stage 02/impl is
  the **final prompt wording** and the exact `openai` pin — the taxonomy, the response
  schema, the batch mechanics, the artifact schemas, the chart builders, and the
  integration touch-points are **all decided here**.

---

## 10. Out of scope

**This feature (not built):**
- LLM treatment of **tags** (theme clustering / families) — possible future follow-up.
- **Per-record entity filtering** / making the tab honour sidebar filters (needs per-record
  entity storage + join — deferred, YAGNI for v1).
- Any change to the **Data-Quality Cockpit**, to **categories**, or to the existing data
  pull / Artifacts API route.

**This stage only (deferred to Stage 02 — the phased implementation plan):**
- The dependency-ordered build sequence and the explicit file-by-file create/edit list.
- Ready-to-run code, final function signatures beyond the illustrative sketches above, and
  the test-by-test enumeration.
- Final prompt copy at production fidelity (sketched in §4.2; the taxonomy, response
  schema, and batch mechanics are decided here).

---

## Appendix A — illustrative directory tree (new/changed)
```
carver-data-showcase/
├── tools/
│   ├── extract_terms.py        (new)  raw JSONL → entity_mentions.csv, tag_mentions.csv
│   ├── classify_entities.py    (new)  distinct entities → entity_types.csv  (OpenAI Batch)
│   └── build_term_stats.py     (new)  join + merge → breakdown / leaderboards / meta
├── carver_showcase/
│   ├── config.py               (edit) + paths, taxonomy, model/chunk constants
│   ├── load.py                 (edit) + load_term_stats()
│   ├── charts.py               (edit) + 3 builders
│   └── deck.py                 (edit) + _slide_themes_entities, slide-list compose
├── apps/
│   └── gallery.py              (edit) + "Themes & Entities" tab (conditional)
├── data/                       (all git-ignored)
│   ├── entity_mentions.csv          tag_mentions.csv
│   ├── entity_types.csv             (tool-internal cache)
│   ├── entity_type_breakdown.csv    entity_leaderboard.csv    tag_leaderboard.csv
│   ├── term_stats_meta.json
│   ├── entity_batch_requests.jsonl  entity_batch_output.jsonl  (Batch scratch)
│   └── entity_batch_state.json      (in-flight batch sidecar — resume across process death, §4.4)
├── tests/                      (edit) test_charts.py, test_gallery_smoke.py, test_deck.py
│                               (new)  test_extract_terms.py, test_classify_entities.py,
│                                      test_build_term_stats.py
└── requirements.txt            (edit) + openai
```

## Appendix B — representative artifact rows
```
# entity_mentions.csv
entity,count
European Central Bank,18223
ECB,12004
Mastercard,842

# entity_types.csv
entity,type,canonical_name
ECB,Regulator / Supervisor,European Central Bank
European Central Bank,Regulator / Supervisor,European Central Bank
Mastercard,Company,Mastercard
Bolivia,Other,Bolivia

# entity_type_breakdown.csv
type,mentions,distinct_entities
Regulator / Supervisor,412005,38112
International body,98221,4410
Government body,76330,9087
Company,61114,52900
Person,40552,33218
Other,211120,143453

# entity_leaderboard.csv  (after merge: ECB + European Central Bank collapse)
canonical_name,type,mentions
European Central Bank,Regulator / Supervisor,30227
Securities and Exchange Commission,Regulator / Supervisor,53110

# tag_leaderboard.csv
tag,count
anti-money laundering,9120
data protection,7841
```
*(Numbers in Appendix B are illustrative shapes, not asserted snapshot values; the tools
compute the real figures.)*
