# Trader Demo Data Integrity Fix

## Problem

The trader dashboard demo currently displays synthetic and fabricated data across multiple layers:

1. **3 of 6 active contracts don't exist** on any prediction market platform (`sec-eth-security-2026`, `kxuschina-tariffs-2026`, `fatf-travel-rule-2027`)
2. **All 8 price series are synthetic** — labeled `platform=synthetic`, timestamps from Jan–Apr 2024
3. **All 130 timeline events show neutral direction** — two bugs:
   - Code bug: `_relevance.judge_batch()` doesn't copy `direction`/`magnitude`/`timeline_shift` from LLM verdict to enriched record
   - Stale cache: 8,147 LLM relevance cache entries generated with old schema (no direction fields)
4. **Heat explainers are hallucinated** — all say "dormant/zero heat" despite computed heat values of 42–323
5. **Retrospective contract metadata is hand-written** instead of API-pulled

## Goal

Every number on screen is traceable to a real-world source or a documented, auditable derivation. Zero synthetic data.

## Scope

### Contracts — slim to real only

Remove the 3 fabricated contracts. Final portfolio:

**Active (3):**
- `kxbtc-maxprice-2026` — Kalshi, already in `contracts.yml` with API pull
- `kxfeddecision-28jan` — Kalshi, already in `contracts.yml` with API pull
- `us-recession-in-2026` — Polymarket, already in `contracts.yml` with API pull. Real slug: `us-recession-by-end-of-2026`

**Retrospective (2):**
- `solana-etf-2025` — Polymarket, resolved YES. Condition ID: `0xf106435e0c9a1b56fc1c0bea0ca3856a8d3a31b1c5f891f8c3600f4a66e74186`, CLOB tokens: `["40950322194820832807533485831393987792860704048110302763324386741027206308151", "77613029953598772381982336999913863065916454247916111678568891881569398156706"]`
- `tiktokban-25apr30` — Kalshi, resolved. Ticker: `TIKTOKBAN-25APR30`

### Prices — real API data only

- Wipe all synthetic price cache files
- Fetch real price history from Kalshi candlestick API and Polymarket CLOB price-history API
- Each cached file must have `platform=kalshi` or `platform=polymarket` (never `synthetic`)
- Timestamps must align with each contract's active period

### LLM enrichment — fix bugs, regenerate

- **Fix code bug**: In `_relevance.py` `judge_batch()`, copy `direction`, `magnitude`, `timeline_shift` from the LLM verdict dict into the enriched record
- **Wipe stale relevance cache**: Delete all 8,147 entries in `build/_cache/llm/relevance/`
- **Wipe stale heat_panel cache**: Delete all entries in `build/_cache/llm/heat_panel/`
- **Re-run enrichment** with the updated code (extended schema will be used for fresh LLM calls)
- **Verify** direction distribution is not 100% neutral after re-run

### Cleanup

- Delete standalone YAML files for removed contracts: `data/platforms/kalshi/contracts/kxuschina-tariffs-2026.yml`, `data/platforms/polymarket/contracts/fatf-travel-rule-2027.yml`, `data/platforms/polymarket/contracts/sec-eth-security-2026.yml`
- Delete stale page_data for removed contracts
- Update `trader-curation.yml` to reflect 3 active + 2 retrospective
- Rebuild site and verify all pages render correctly with reduced portfolio

### Retrospective metadata

- Pull real contract metadata for `solana-etf-2025` from Polymarket Gamma API
- Pull real contract metadata for `tiktokban-25apr30` from Kalshi API
- Update their standalone YAML files with API-sourced data + `last_pulled_at` timestamps

### Out of scope

- Positions are synthetic by design (demo positions, labeled DEMO) — no change needed
- Thesis decomposition and narrative caches appear reasonable — keep unless re-run invalidates them
- Adding new contracts to replace removed ones

## Tech details

- Kalshi public API: `https://trading-api.kalshi.com/trade-api/v2`
- Polymarket Gamma API: `https://gamma-api.polymarket.com`
- Polymarket CLOB API: `https://clob.polymarket.com`
- Carver artifacts API: existing `pull_artifacts.py` (50,021 records, already real)
- LLM: OpenAI gpt-5 / gpt-5-mini via `_llm.py`, key in `.env`
