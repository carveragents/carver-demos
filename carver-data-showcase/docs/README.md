# Carver Data Showcase — Project Reference

A demo that showcases the **range, quality, and richness of the Carver agents
annotation dataset**. This file is a **map** — it points to where information lives.
It does not duplicate content. Start here, then jump.

> **Status:** greenfield at init. Only a `.venv` + these docs exist. Brainstorm the
> demo shape before building.

## Jump to what you need

| I want to… | Go to |
|---|---|
| Understand the **annotation dataset** (the whole point) — schema, scale, what each field proves | [data-model.md](data-model.md) |
| **Pull the data** — direct Artifacts API, `X-API-Key`, offset-paginated pull loop | [data-access.md](data-access.md) |
| Understand the **intended architecture** and how this fits the `carver-demos` family | [architecture.md](architecture.md) |
| **Set up, run, and test** locally | [development.md](development.md) |
| Avoid known **pitfalls** / read session history | [LESSONS.md](LESSONS.md) |
| Read Claude Code working rules for this repo | [../CLAUDE.md](../CLAUDE.md) |

## The 60-second orientation

- **What it showcases:** the structured intelligence Carver's agents attach to each
  regulatory feed entry — impact/urgency/relevance scores (with confidence),
  `impact_summary`, `actionables`, `critical_dates`, `entities`, `reg_references`,
  and more. Full schema → [data-model.md](data-model.md).
- **Scale to show:** ~1,087 topics · 241 jurisdictions · 3 categories · tens of
  thousands of annotation records. Numbers → [data-model.md](data-model.md).
- **Data source:** the Carver **Artifacts API** via **direct HTTP** (`X-API-Key`,
  `artifact_type_id=annotations-v1`, offset-paginated). **Not the `carver-feeds-sdk`.**
  How → [data-access.md](data-access.md).
- **Best data-access reference:** `carver-dags`'s `jurisdiction_enrichment` workflow
  (`fetch_artifacts.py` + `run_backfill.sh`) — the paginated direct-API pull. For
  field-coverage audits, `pred-oracle/data/`. Pointers in
  [architecture.md](architecture.md) and [data-access.md](data-access.md).

## External / source-of-truth references

| Reference | Location |
|---|---|
| **Paginated direct-API pull (reference impl)** | `carver/carver-dags/workflows/jurisdiction_enrichment/steps/fetch_artifacts.py` + `run_backfill.sh` |
| Annotations DAG id + `annotations-v1` config | `carver/carver-dags/workflows/jurisdiction_enrichment/configs/production/config.completed.json` |
| Artifacts-endpoint probes / samples | `carver/carver-demos/pred-oracle/build/probe_artifacts_*.py` |
| Real corpus audits & field coverage | `carver/carver-demos/pred-oracle/data/` |
| Carver Feeds **API** reference (general) | `carver/carver-feeds-sdk/docs/api-reference.md` |
| `carver-demos` family overview | `carver/carver-demos/README.md` |
| Carver platform | <https://app.carveragents.ai> · API docs: <https://app.carveragents.ai/api-docs/> |
