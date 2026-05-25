# Stage 1 Data Analysis Plan

> Investigations to size and characterize the Carver corpus before writing the Stage 1 implementation plan. Resolves B0 (corpus completeness) and B1 (regulator-name source).

## Approach

Annotations + topics only — no entries pull. Annotations carry the content (`impact_summary`, `critical_dates`, `impacted_business`, `entities`), the classification (`update_type`), the scores, the summary, **and** title + link (per user confirmation). Joining annotation rows on `topic_id` to the topics catalog yields the regulator name, resolving B1.

## SDK constraint

`client.get_annotations()` takes no pagination params — it sends one GET and returns the response as-is. A0 probes whether the raw `/api/v1/core/annotations` endpoint accepts `limit` / `offset` directly. If yes, we use it (10K-at-a-time per user direction). If not, we fall back to per-topic pulls.

## Investigations

### A0 — Annotations pagination probe (FIRST)

- **Q:** Does `/api/v1/core/annotations` accept `limit` / `offset` / `cursor` query params?
- **Do:** Hit the raw endpoint with `httpx` + `X-API-Key`. Try `?topic_ids_in=<one-id>&limit=10000&offset=0`, then `&offset=10000`. Inspect headers for `X-Total-Count`, `Link`. Document response shape.
- **Output:** `data/a0-pagination-probe.md`.
- **Model:** haiku.

### A1 — Topics + categories catalog

- **Q:** Full catalog. Are topics regulators? Does `list_topics(details=True)` give us more than `get_topics_df()`?
- **Do:**
  - `dm.get_topics_df()` → `data/carver-topics.json`
  - `client.list_topics(details=True)` → `data/carver-topics-detailed.json`
  - `dm.get_categories_df()` → `data/carver-categories.json`
- **Output:** three JSON files + summary stdout (counts, sample records).
- **Model:** haiku.

### A2 — Topic classification (manual, by main agent)

- **Q:** For each topic, classify as `regulator | non-regulator | ambiguous` and `pm_relevant: true | false`.
- **Do:** Read A1's catalog; tag every row by name + description; emit `data/regulator-topics.yml`.
- **Done by:** main agent (judgment call, has session context).

### A3 — topic_id coverage on current 618

- **Q:** Do all 618 events' `topic_id`s appear in the catalog and resolve to recognizable regulator names?
- **Do:** Left-join `data/carver-events.json` × topics catalog on `topic_id`. Hit rate, top 20 resolved names with counts.
- **Output:** `data/a3-topic-id-coverage.md`.
- **Model:** haiku.

### A5 — Full annotation pull

- **Q:** What's the actual corpus size pulling annotations for all PM-relevant topics from A2?
- **Do:** Per A0's verdict — either paged raw endpoint (`limit=10000&offset=N`) or per-topic `get_annotations(topic_ids=[t])` loop. Join each row to topics_df for `topic_name`. Normalize. Write to `data/_scratch/annotations.json`.
- **Output:** one normalized record per annotation: `{feed_entry_id, topic_id, topic_name, classification, metadata, scores, summary}` plus title + link if present on the annotation surface.
- **Model:** sonnet (pagination, error handling, normalization — non-trivial).

### A6 — Field-population audit at scale

- **Q:** Confirm/refute STAGE_1_NOTES gaps (`regulatory_source` empty, `summary` empty, etc.) on the full corpus.
- **Do:** Field-coverage report on A5 output.
- **Output:** `data/a6-field-population.md`.
- **Model:** haiku.

### A7 — Title / link field discovery on annotations

- **Q:** Which annotation fields carry title and link? (User confirmed they exist on the annotation surface.)
- **Do:** Inspect 10 random A5 records; find the field paths; document.
- **Output:** added to `data/a6-field-population.md` (single doc; same audit pass).
- **Model:** haiku (folded into A6).

### A8 — Wow-moment shortlist

- **Q:** Which annotations meet α wow criteria (urgency.score ≥ 8, ≤ 60 days old by `critical_dates.pub_date_content`, US state or CFTC, news-recognizable)?
- **Do:** Score + rank; top 25 → `data/wow-candidates.json`.
- **Model:** sonnet (ranking heuristic).

### A9 — Choropleth density

- **Q:** Per-US-state event counts in 90-day and 180-day windows.
- **Do:** Aggregate by `impacted_business.jurisdiction`; tabulate.
- **Output:** `data/a9-choropleth-density.md`.
- **Model:** haiku.

## Sequencing

```
A0 ─┐
A1 ─┴─► A2 (main agent) ─► A5 ─► A6 (+A7), A8, A9  (parallel)
A3 ◄── A1
```

## Model routing summary

| Step | Model | Why |
|---|---|---|
| A0 | haiku | one probe script, mechanical |
| A1 | haiku | three SDK calls, write JSON |
| A2 | main agent | judgment / classification |
| A3 | haiku | left-join + report |
| A5 | sonnet | pagination + normalization, integration concerns |
| A6 (incl. A7) | haiku | field-coverage report |
| A8 | sonnet | ranking heuristic design |
| A9 | haiku | aggregation report |

## Deliverables

- `data/a0-pagination-probe.md`
- `data/carver-topics.json`, `carver-topics-detailed.json`, `carver-categories.json`
- `data/regulator-topics.yml`
- `data/a3-topic-id-coverage.md`
- `data/_scratch/annotations.json`
- `data/a6-field-population.md` (covers A6 + A7)
- `data/wow-candidates.json`
- `data/a9-choropleth-density.md`
- Updated `docs/specs/STAGE_1_NOTES.md`
- Proposal (not commit) for rewritten `build/pull_carver.py` — annotations + topics only

## Out of scope

- Implementing α scene templates / slices.
- Re-pulling Kalshi / Polymarket.
- Writing the Stage 1 implementation plan (separate doc after this lands).
