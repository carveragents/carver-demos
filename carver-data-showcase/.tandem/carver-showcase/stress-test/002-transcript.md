# Stress-test 002 — stage 01-spec (post-refinement-1, client-lens)

Two questions posed by a potential client (relayed by the user). Answered only from the
refined approved artifact (`stages/01-spec/artifact.md`, round 2) + `goal.md`; grounded probes
used only to confirm whether the data could support an answer the spec doesn't currently commit to.

**Q1 (client). "Provide the full list of monitored institutions, with a country and
regulator-type breakdown."**
A: **NOT covered — GAP (G4).** The spec presents jurisdiction breadth, category→topic, update_type
mix, and counts of distinct `regulator_name` values, but it commits to **no view that lists the
monitored institutions** (the topics/regulated bodies) with a **country × regulator-type**
breakdown. A probe confirms the data is fully available from the topics catalog (a sanctioned
direct GET): **1,071 institutions**, `jurisdiction_code` 98.6% populated (US 59, AU 43, EU-27 bloc
28, CN 25, IN 24, US-CA 23, FR 20, KR 17, SG 16…), `entity_type` 98.7% (Regulator 564, Independent
Statutory Authority 102, Central Bank 73, Govt Agency 31, Ministry 26…), `govt_body` True 1,001/
1,071, scope National 584 / State 322 / International 107 / Local 29 / Regional 14. The showcase
should answer this directly; today it can't.

**Q2 (client). "What's the earliest record date and the overall historical coverage depth?"**
A: **Partially covered — GAP (G5).** The spec has Volume-over-time (§6.2 v4) and a coverage-over-time
trend (§7.6), and flags implausible dates (§5.3), but it surfaces **no explicit historical-depth
metric** (earliest *plausible* record, span, recency distribution) and doesn't frame the strong
**recency skew**. A naive answer would also be WRONG: the raw range is **1947-12-25 … 2105-07-01**
(109 pre-1990, 10 post-2026 — garbage). Honest depth: plausible range **1990 → 2026** (99.8% of
records), but median **2025-07**, p10 2019, p90 2026-03; bulk in 2025 (24,010) / 2026 (12,511) /
2024 (6,784), thinning to a sparse tail to the 1990s. The overview should state the earliest
*plausible* date + historical depth + recency profile, not the garbage extreme.

## Verdict
Two confirmed in-scope GAPs (G4 institutions catalog view; G5 historical-depth KPI + honest
framing). Both are additive Gallery features whose data already exists. Route to refinement cycle 2.
