# Stage 3 — β Walkthrough Acceptance Log

**Completed:** 2026-05-20

## Acceptance criteria (from 50-beta-walkthrough.md § 6)

- [x] β intro page renders; lede paragraph reads cleanly.
- [x] World map renders; tenant footprint outlines (blue for operating, red for closed) visible and accurate against `data/platforms/polymarket/footprint.yml`.
- [x] France drilldown shows the 13-month escalating signal pattern (AMF + ESMA + EU). Events are real Carver records and linked.
- [x] 3 cascade cards render (FATF, BCBS, ESMA) with real trigger URLs.
- [x] FATF cascade highlights ≥3 jurisdictions in Polymarket's operating footprint.
- [x] Quarterly report renders headline stats, pressure-rising, pressure-easing, watch list, featured cascades, γ touchpoints, method + coverage footer.
- [x] Watch list names 3 real jurisdictions (BR, SG, AU) with recommended actions.
- [x] Pre-rendered Q2 2026 PDF artifact exists at `site/static/samples/q2-2026-report.pdf` and is downloadable.
- [x] Watch-list copy includes the "Pattern-based projection, not prediction" hedge.
- [x] Close page links to all three scenes; contact CTA renders.
- [ ] Carver leadership dry-run pending.
- [ ] (Deferred to Stage 4 polish) Mobile reflow for world map and report layout.

## Schema notes

- `data/beta-curation.yml` carries `build_date`, `platform_footprint`, `retrospective_focus`, `featured_cascade_ids`, 3 watch-list picks, and `report_window`.
- `data/platforms/{kalshi,polymarket}/footprint.yml` lists operating / considering / closed jurisdictions per platform. Closed entries include `closed_at`.
- `data/cascades.yml` carries 3 hand-curated rules with trigger URLs, member jurisdictions, follow window, and historical hit-rate.
- `build/_country.py::aggregate(records, today, window_days, world_only)` is the canonical per-country aggregation. `pressure_score(slot) = min(100, count × avg_urgency / 5)`.
- All slice JSONs land at `build/page_data/beta/{heatmap,cascades,report}.json`.

## Routing note

The plan registered `beta/report.html → beta/report/index.html` in `_EXPLICIT_ROUTES` (Task 11) but named the template `quarterly_report.html` (Task 13). Resolved during implementation by naming the template `beta/report.html` to match both the route and the `report.json` slice file produced by Task 8.

## Math corrections during implementation

- Task 6 `narrative_window_months → weeks`: plan used `* 4` (= 72 weeks for 18 months); test expected exactly 78 weekly buckets. Corrected to `round(months * 52 / 12) = 78`.
- Task 7 `expected_action_by` for FATF (2025-11-20 + 540 days): plan example said `2027-05-13`; actual `date(2025, 11, 20) + timedelta(540) = 2027-05-14`. Corrected.

## Curation lessons learned

- **No ANJ events in Carver catalog.** Reframed France retrospective from "ANJ ban" to "escalating AMF/ESMA pressure" (Task 4 spec edit). 1,481 FR records carry the timeline cleanly.
- **Watch list is hand-picked.** V1 cascade engine is rule-based per spec; pattern-matching is qualitative. The page hedges explicitly.
- **Footprint data is not in Carver.** Hand-curated from public statements + reporting in `data/platforms/*/footprint.yml`.
- **World GeoJSON sourcing.** The `datasets/geo-countries` repo now ships a 14MB ne_10m file. Use the 110m Natural Earth alternative (`martynafford/natural-earth-geojson`) and prune properties to keep the asset at ~400 KB. ECharts expects feature `properties.name`; the 110m source uses `NAME`, so a one-pass normalisation at fetch time populates `name` from `NAME` / `ADMIN`.

## Known gaps (deferred to Stage 4 polish)

- **Cascade hit-rate annotations are illustrative.** A back-test against historical corpus is suggested by spec § 7 BW3 but is not yet wired; the YAML carries the historical rate as a string verbatim. Precise hit-rates can be computed once V2 cascade infrastructure exists.
- **Mobile world map** — ECharts zoom-pan works but isn't tuned for narrow viewports.
- **Quarterly-report PDF regeneration** — hand-rendered once. Automating with WeasyPrint or playwright printToPDF is a Stage 4 candidate.

## Next stage prerequisites

- Stage 4 polish + Carver leadership dry-run.
