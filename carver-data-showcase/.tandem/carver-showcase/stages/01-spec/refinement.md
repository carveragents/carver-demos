# Refinement — stage 01-spec (cycle 2)

Cycle 1 (G1–G3) is approved. A client-lens stress-test (`stress-test/002-*.md`) surfaced two
additive gaps a buyer explicitly asks about. Close BOTH. Do NOT re-open settled design — these are
additions to the Gallery (plus a small Cockpit angle) using data that already exists. Keep
everything else as-is.

## GAP G4 (High) — a "Monitored institutions" catalog view (country × regulator-type)

**Need.** A buyer asks: "the full list of monitored institutions, with a country and regulator-type
breakdown." The spec currently has no view for this, though the data is fully available.

**Add to the design:**
1. **Data source (one-time, sanctioned direct GET — no SDK, no LLM).** Pull the topics catalog
   (`GET /api/v1/feeds/topics?details=true`) once to **`data/topic_catalog.csv`** covering ALL
   **1,071** monitored institutions with: `topic_id`, `name`, `acronym`, `category`
   (priority-assigned per cycle 1), `jurisdiction_code` (country, 98.6% pop), `entity_type`
   (regulator-type, 98.7%), `govt_body` (bool, 1,001/1,071 True), `scope`
   (National 584 / State 322 / International 107 / Local 29 / Regional 14), `sectors`, `industries`.
   This supersedes/extends the cycle-1 `topic_categories.csv` (the category map can be derived from
   this same file). State it as a deterministic catalog join, population measured.
2. **Gallery view — "Monitored institutions" (RANGE).** A searchable, filterable table of the
   institutions with: name, acronym, country, regulator-type, scope, category, and **records in this
   sample** (joined from the snapshot by `topic_id`; 0 where the institution isn't in the slice).
   Plus breakdown charts: institutions **by country**, **by regulator-type** (`entity_type` /
   `govt_body`), **by scope**. CSV-exportable.
3. **Honest scope (load-bearing).** Distinguish three populations clearly: **monitored universe
   = 1,071** institutions (catalog), **categorized = 610**, **present in this 58,982-record sample
   = 405** topics. The view shows the full monitored universe with a per-institution sample-record
   count, never implying the sample equals the universe.
4. **Cockpit angle (small).** Institutions with missing `jurisdiction_code`/`entity_type`
   (≈1.4% each) or **0 records in the sample** are QA/coverage targets — add as a coverage note,
   not a new heavy view.

## GAP G5 (Medium) — surface historical depth honestly

**Need.** A buyer asks: "earliest record date and overall historical coverage depth." The raw
earliest/latest are garbage (1947-12-25 / 2105-07-01); a naive answer misleads.

**Add to the design:**
1. **Gallery overview KPIs (§6.2 view 0) — a "historical depth" block:** earliest **plausible**
   record date, the **date span**, and a **recency distribution** (e.g. % of records within the
   last 1 / 3 / 7 years), all computed **excluding** implausible dates
   (`config.PLAUSIBLE_DATE_WINDOW`, already defined). Ground numbers: plausible range **1990 →
   2026** (99.8% of records); recency-skewed — median **2025-07**, p10 **2019**, p90 **2026-03**;
   bulk 2025 (24,010) / 2026 (12,511) / 2024 (6,784), thinning to a sparse tail to the 1990s.
2. **Honesty rule.** The headline "earliest record" uses the earliest **plausible** date; the raw
   extremes (1947 / 2105) appear ONLY via the existing `implausible_pub_date` anomaly (§5.3/§7.3),
   never as the advertised depth. State the recency skew plainly (this is a recent-history feed with
   a thin deep tail), so a buyer isn't misled into expecting uniform multi-decade depth.

## Out of scope for this refinement
Only G4 + G5. Do not touch module boundaries, the normalized schema, the deterministic
formulas/predicates, or Stage-02-deferred items. The institutions view and historical-depth KPIs
reuse the catalog data + existing date handling — additive, not a redesign.
