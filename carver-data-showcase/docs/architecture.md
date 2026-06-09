# Architecture & Context

## Status at init

This repo is **greenfield**. At init time it contains only a Python `.venv` (3.10)
and the docs you are reading. There is no application code yet — the architecture
below is the *intended* shape, to be confirmed/refined during brainstorming before
any build work starts.

## Where this sits

`carver-data-showcase` is one demo under the **`carver-demos/`** monorepo, a
collection of self-contained demos built on the Carver Horizon regulatory
intelligence platform. Siblings (for reference patterns, not dependencies):

| Sibling demo | Relevance to this repo |
|---|---|
| `pred-oracle` | Already pulled, audited, and curated ~55k annotation records; its `data/` audits are useful for field-coverage reference. NB: its `pull_annotations.py` uses the **SDK feeds route** — this showcase uses the **direct Artifacts API** instead (see below). |
| **`carver-dags` › `jurisdiction_enrichment`** | **Most relevant for data access.** `steps/fetch_artifacts.py` + `run_backfill.sh` are the reference implementation for the paginated direct-API pull this showcase uses. |
| `fincoach-demo` | Shows live Carver signals driving an AI agent's behavior. |
| `amicompliant` | Scores text against live Carver signals. |
| `policy-diffs` | Turns Carver regulatory deltas into reviewable policy updates. |

## Intended demo architecture

The goal is to **let the dataset speak** — make its range, quality, and richness
immediately visible. A typical shape:

```
Carver Artifacts API  ──(direct HTTP GET, X-API-Key,           ──►  pull/ingest layer
  /api/v1/artifacts/dags/{dag}/artifacts?artifact_type_id           │
  =annotations-v1, paginated by limit/offset)              normalize (output_data
                                                            = annotation; carry envelope
                                                            topic_id/state/timestamps)
                                                                  │
                                                          local corpus (.jsonl / parquet)
                                                                  │
                                              ┌───────────────────┼───────────────────┐
                                          aggregate           curate              present
                                       (by jurisdiction,   (hand-picked        (gallery / dashboard /
                                        regulator, type,    "wow" records)      record detail views)
                                        score, time)
```

> **Data access is the direct Artifacts API only** — not the `carver-feeds-sdk`.
> It's the only route that paginates and exposes the full 200k+ corpus in one ordered
> offset walk. See [data-access.md](data-access.md).

Three things any showcase should make tangible (mapped to the goal):

1. **Range** — pivot the corpus across 241 jurisdictions, 1,087 topics, 3
   categories, and many `update_type`s. Breadth views: maps, treemaps, time series.
2. **Quality** — show the structured scores (impact/urgency/relevance, each with
   confidence + basis), calendar-aware date extraction, and entity recognition on
   real records.
3. **Richness** — drill into a single annotation to reveal the full nested object:
   the 5-part `impact_summary`, 7-lane `actionables`, `critical_dates`,
   `reg_references`, impacted business/functions.

## Key design principles (carried from sibling demos' lessons)

- **Pull once, present many times.** Snapshot the corpus to a local file via the
  offset-paginated artifacts pull; don't hit the API on every render.
- **Normalize on ingest.** Treat `artifact.output_data` as the annotation; the rich
  fields nest under `output_data.metadata.*` / `output_data.classification.*`. Flatten
  to predictable top-level columns for analytics.
- **Report coverage honestly.** Field population varies (see
  [data-model.md](data-model.md)); a credible showcase surfaces real percentages.
- **Curate for the highlight reel.** Aggregate views show breadth; a small
  hand-picked set of vivid records shows depth.
