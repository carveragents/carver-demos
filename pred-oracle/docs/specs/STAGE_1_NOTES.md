# Stage 1 Readiness Notes

> **Updated 2026-05-19** after the Stage 1 data analysis. The earlier 618-event Stage 0 pull is obsolete. Stage 1 uses the **DAG Artifacts API** (not `/api/v1/core/annotations` or the SDK entries+annotations join).

## 1. The Stage 1 corpus

| | Stage 0 (obsolete) | A5 attempt (annotations endpoint) | **A5' final (artifacts API)** |
|---|---|---|---|
| Source file | `data/carver-events.json` | (discarded) | **`data/_scratch/artifacts.jsonl`** |
| Endpoint | SDK `to_dataframe()` + `get_annotations` | `/api/v1/core/annotations` | `/api/v1/artifacts/dags/{dag_id}/artifacts` |
| Pagination | client-side, capped at 10K | broken (server ignores params) | **server-side `limit`+`offset`** |
| Record count | 618 | 54,959 | **49,735** |
| Link coverage | n/a | 39.6% | **100%** |
| Wall time | (capped) | 7m 53s | **2m 40s** |
| Filter "website error" garbage | n/a | n/a | filter `update_type` downstream |

Use `data/_scratch/artifacts.jsonl` as the Stage 1 corpus. Do NOT use the older `data/carver-events.json`.

## 2. The right endpoint (load-bearing)

```python
GET https://app.carveragents.ai/api/v1/artifacts/dags/{SOURCE_DAG}/artifacts
    ?dag_ids_in={SOURCE_DAG}
    &state=completed                              # NOT dag_state — that returns 0
    &topic_id_in={comma_joined_topic_uuids}
    &created_after={iso8601_utc_Z}
    &limit=10000
    &offset={offset}

SOURCE_DAG = "7f61eee4-1c56-44cc-b7fb-bbfcbda6a5ad"   # entry_annotation source DAG
```

Header: `X-API-Key: <CARVER_API_KEY>`.

Page until response is empty or `< limit` records.

Reference implementation: `build/pull_artifacts.py` (Stage 1 canonical pull script).

## 3. Slice-naming convention (unchanged from Stage 0)

- `build/templates/alpha/inbox.html` ↔ `build/page_data/alpha/inbox.json`
- `build/templates/alpha/tickets/detail.html` ↔ `build/page_data/alpha/tickets/detail.json`

Code: `build/generate.py::_load_slice`. Do not flatten slashes to underscores.

## 4. Normalized record schema

See `build/pull_artifacts.py` for the canonical mapping. Audited in `data/a6-prime-field-population.md`. Highlights:

| Field | Source | Populated | Notes |
|---|---|---|---|
| `artifact_id` | `id` top-level | 100% | stable record id |
| `feed_entry_id` | `input_data.feed_entry_id` | ~100% | joins to entry-level records if needed |
| `topic_id` + topic catalog fields | join via `data/regulator-topics.yml` | 100% | regulator name from topic table is a fallback |
| `title` | `input_data.extracted_metadata.title` | **100%** | |
| `link` | `input_data.extracted_metadata.url` | **100%** | canonical primary-source URL |
| `regulator_name` | `output_data.classification.regulatory_source.name` | 93.4% | resolves B1 — use directly |
| `regulator_division` | `output_data.classification.regulatory_source.division_office` | 17.0% | render conditionally |
| `update_type` | `output_data.classification.update_type` | 99.6% | inbox sort/group |
| `update_subtype` | `output_data.classification.update_subtype` | 99.9% | |
| `jurisdiction_tier.label` | `output_data.classification.jurisdiction_tier.label` | 99.9% | "us_federal" / "domestic" / "international" |
| `pub_date` | `output_data.reconciled_published_date.date` | 100% | LLM-reconciled |
| `pub_date_valid` | as above | 100% | |
| `scores.{urgency,impact,relevance}.score` | as-is, nested `{label,score,confidence,basis?}` | 100% | sorting/filtering primary |
| `impact_summary.{what_changed,why_it_matters,objective,risk_impact}` | `output_data.metadata.impact_summary` | 88% | ticket-detail body |
| `impact_summary.key_requirements` | as above | 83% | list, not string |
| `critical_dates.effective_date` | `output_data.metadata.critical_dates` | 26.9% | render conditionally |
| `critical_dates.{compliance_date,comment_deadline}` | as above | 8-9% | render conditionally |
| `impacted_business.jurisdiction` | `output_data.metadata.impacted_business` | 88.8% | choropleth source |

## 5. Hard filter rules for any Stage 1 slice generator

```python
EXCLUDE if update_type == "website error"   # ~5,763 records — title/regulator/content sparse
EXCLUDE if update_type == "other"           # ~4,696 records — fields populated only ~56%
EXCLUDE if scores.relevance.score < 5       # off-topic noise
EXCLUDE if not pub_date_valid
EXCLUDE if not title or not link
```

After exclusions: **~15,759 substantive records** across the corpus (per A8').

## 6. Choropleth — 90-day window confirmed

Per `data/a9-prime-choropleth-density.md`:

- 90-day window: 54 US states with activity, 15+ with 100+ events. **Strong cluster.**
- Top: US-CA (519), US-NY (273), US-MA (242), US-DE (222), US-CT (219), US-OR (172), US-NJ (160), US-CO (143), US-IL (140), US-WA (131), US-VT (121), US-NM (119), US-AZ (113), US-MD (109), US-MI (99).
- Use 90-day window for `/alpha/dashboard/`.

## 7. Wow-moment top picks

Per `data/wow-candidates.json` (top 50 ranked) and `data/a8-prime-wow-summary.md`:

**Recommended α-scene top inbox row:** rank #4 — **CFTC Sues Minnesota to Block State Law** (pub_date 2026-05-19, urgency 9, impact 9, enforcement, `link` to CFTC press release). The CFTC suing states to block criminalization of prediction markets is the *unmistakable* wow story for the Sara Chen persona.

Alternative algorithmic #1: DFPI crypto-kiosk shutdown (urgency 10, impact 10) — fintech but not PM-specific. Use as a typical inbox row, not the top.

Strong supporting picks (have all the markers): #2 CFTC Amendments to Market Maker Program — FEX (ForecastEx-specific), #5 ETRON | ElectronX self-certifying CAISO Core Liquidity Provider, #14 SEC enforcement, #12-13 California DOJ proposed Protections.

Top 50 jurisdiction mix: 26 US federal + 15 US state + 9 international.

## 8. Top topics by artifact volume (Stage 1 corpus)

For Stage 1 ranking and reference:

| # | Topic | Artifacts |
|---|---|---|
| 1 | U.S. Securities and Exchange Commission | 2,498 |
| 2 | Federal Trade Commission | 1,909 |
| 3 | Financial Supervisory Commission (TW) | 1,780 |
| 4 | هيئة السوق المالية (SA) | 1,579 |
| 5 | Autorité des Marchés Financiers (FR) | 1,481 |
| 6 | ESMA | 1,469 |
| 7 | Επιτροπή Κεφαλαιαγοράς (GR) | 1,340 |
| 8 | Bank for International Settlements | 1,254 |
| 9 | Securities and Futures Commission (HK) | 1,104 |
| 10 | Financial Conduct Authority (GB) | 1,102 |
| (CFTC) | Commodity Futures Trading Commission | 1,088 (rank ~11) |

The β scene benefits from the international tail.

## 9. Stage 2 prerequisite still open

`data/platforms/{kalshi,polymarket}/contracts.yml` doesn't exist. Stage 2 (γ) needs it. Out of scope for Stage 1.

## 10. Demo data freshness

Re-run `uv run python build/pull_artifacts.py` periodically. Manifest at `data/_scratch/a5-prime-manifest.json` records `pulled_at`.
