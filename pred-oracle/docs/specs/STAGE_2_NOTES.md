# Stage 2 — γ Walkthrough Acceptance Log

**Completed:** 2026-05-20

## Acceptance criteria (from 40-gamma-walkthrough.md §5)

- [x] γ intro page renders; all CTAs valid.
- [x] All 3 pre-listing scans (TIKTOKBAN, Solana-ETF-2027, State-Kalshi) render full results with severity, entities ≥ 2 each, ≥ 1 events each.
- [x] Contract-watch dashboard shows 5 active contracts (3 fresh Kalshi + 2 fresh Polymarket cached blocks), all with sparklines, sorted heat desc.
- [x] ≥ 1 contract shows a clearly-rising sparkline (KXBTC-MAXPRICE-2026 with heat ≈ 617, dominating the active book).
- [x] All 5 contract-detail pages render. Retrospectives (tiktokban-25apr30, kxfeddecision-26mar, solana-etf-2025) carry the "retrospective" badge + source URLs.
- [x] (Spec edit from Task 5) Retrospective wow shifted from price-overlay to Carver-vs-news temporal-precedence math.
- [ ] **NOT MET** — Spec §5 calls for ≥3 "Pred-Oracle signal preceded news by N days" callouts per retrospective. Generator emits `precedence_callout` stubs (all fields `None`); template gates on `days_ahead` so nothing renders. Resolution: Stage 4 polish — hand-curate `precedence_overrides.yml` per retrospective with real news_date / news_url pairs.
- [ ] **REDUCED SCOPE** — Spec §2.3 asks for 10 contracts on the dashboard (5 Kalshi + 5 Polymarket). We ship 5 (3 fresh Kalshi + 2 fresh Polymarket cached blocks; 3 picks went stale on the live API). Increase by adding more picks to `data/platforms/*/contracts.yml` and re-running curated-pull.
- [ ] **NOT MET** — Spec §2.3 asks for a platform toggle ("All / Kalshi / Polymarket") on the dashboard. Slice JSON has `platform` per row but template has only heat-threshold chips. Resolution: add an Alpine `x-data` toggle to `dashboard.html` (no slice change needed).
- [x] Linked events on each contract page are real Carver records (verified by `carver_feed_entry_id` in the slice).
- [x] Open-ticket synthetic content carries the demo-data badge.
- [x] "Next scene" CTA on contract-detail navigates to `/beta/`.
- [ ] Carver leadership dry-run pending.
- [ ] (Deferred to Stage 4 polish) Mobile timeline reflow.

## Page inventory (post-build)

```
site/gamma/index.html
site/gamma/scan/index.html
site/gamma/dashboard/index.html
site/gamma/contracts/kxfeddecision-26mar/index.html
site/gamma/contracts/kxfeddecision-28jan/index.html
site/gamma/contracts/solana-etf-2025/index.html
site/gamma/contracts/tiktokban-25apr30/index.html
site/gamma/contracts/us-recession-in-2026/index.html
```

8 γ HTML pages; 19 total site HTML files (with α + landing + close + beta placeholder).

## Schema notes

- `data/platforms/{kalshi,polymarket}/contracts.yml` is a **pick-list** with embedded `cached` blocks. Refresh via `build/pull_{kalshi,polymarket}_curated.py --mode=fresh` is non-destructive: stale entries keep their cached metadata and gain `stale: true` + `stale_reason`.
- Retrospective contracts live in `data/platforms/{kalshi,polymarket}/contracts/{id}.yml` — hand-curated from Wayback / news sources. Mandatory `source_urls`. Three retros at Stage 2 ship: tiktokban-25apr30, kxfeddecision-26mar, solana-etf-2025.
- `data/gamma-curation.yml` carries `build_date` (deterministic) + the 3 pre-listing-scan defs + 5 contract-detail picks + synthetic listing-risk tickets.
- `build/_heat.py::heat_score(contract, records, today)` uses `severity * exp(-age / 14)` over the 90-day window. Entity match is case-insensitive substring (either direction).
- Dashboard slice JSON lands at `build/page_data/gamma/dashboard.json` (template-name matches slice-name; consistent with α convention).

## Curation lessons learned

- **`cached.settlement_entities` must be hand-curated.** The live Kalshi `/markets` API only returns a single `settlement_source` identifier; the Polymarket Gamma API returns nothing. Without manual entities, heat scoring returns 0.0 across the board. The contracts.yml comment block documents this.
- **`us-recession-in-2026` Polymarket slug returns no results on the Gamma API.** We hand-curated its `cached` block (treated as if the curated-pull succeeded) so the contract-detail page would render.
- **Two Kalshi picks (`kxnextiranleader-45jan01`, `kxtrumpcabinet-26`) and one Polymarket pick (`warmest-year-on-record-2026`) are stale.** They're left in the YAML with `stale: true` and no cached block; the dashboard skips them as documented (only picks with cached blocks render).

## Known gaps (deferred to Stage 4 polish)

- **Precedence callouts on retrospectives are stubs** — `news_date` + `news_url` are not populated by the generator. For real wow, hand-curate a `precedence_overrides.yml` per retrospective contract that lists key Carver events + matching news article dates, and merge in `gamma_contract._build_timeline`.
- **Mobile reflow** for the contract-detail two-pane layout.
- **Sparkline accessibility** — no `<title>` element; add for screen readers in Stage 4.
- **Heat decay tuning** — 14-day half-life chosen from data-prep spec; live deployments may want longer half-life for slow-burn regulatory pressure.
- **`pull_*_curated.py --mode=fresh` overwrites the manually-curated `cached.settlement_entities`.** Either move `settlement_entities` to a sibling override key, or have the pull merge instead of replace.

## Next stage prerequisites

- **β (Stage 3)** needs Polymarket's international footprint and the France ANJ event corpus. Verify Carver coverage on EU jurisdictions (FR, NL, MT, EU) before β planning.
