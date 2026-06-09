# Real coverage & anomaly findings (orchestrator grounding)

Computed deterministically over the full **60,000-record** snapshot
(`tools/coverage_probe.py` → `data/coverage_snapshot.md`). NOT part of the maker/checker
loop — this is orchestrator grounding used to (a) form sharp stress-test questions and
(b) feed concrete numbers into the 02-plan task. Stress-test ANSWERS still come only from
the approved spec artifact; these numbers only shape the QUESTIONS.

## Strengths (external Showcase Gallery story)
- **Scores trio + urgency.basis ≈ 100%** populated (impact/urgency/relevance score &
  confidence all 60,000/60,000; urgency.basis 99.96%).
- **Breadth in this 60K slice:** 403 topics · 118 distinct countries · 42 blocs · 5
  jurisdiction scopes · 3,109 regulator names · 111 update_types.
- **Rich analytical prose well-populated:** impact_summary.{objective/what_changed/
  why_it_matters/risk_impact} ~85%, key_requirements 78%; tags 86%, entities 92%;
  impacted_business.industry 83%, impacted_functions 83%; penalties 56%.
- **Sparser-by-nature fields (honest):** effective_date 25%, compliance_date 8%,
  comment_deadline 6.5%, other_dates 45%; reg_references.rules 22%, statutes 35%.
- Impact label mix: medium 42% / low 29% / high 29%. Urgency basis: no_future_date 60%,
  past_deadline 37%, future_deadline 2%, effective_immediately 0.8%.

## Data-quality findings (internal Data-Quality Cockpit story)
1. **Implausible publication dates.** `reconciled_published_date` spans
   **1947-12-25 … 2105-07-01**. A 2105 date is non-physical; pre-internet dates are
   suspect. → cockpit needs an out-of-plausible-range date check.
2. **`update_type` sprawl: 111 distinct.** Public docs imply ~a handful (enforcement,
   final rule, proposed rule, bulletin, press release…). 111 strongly suggests
   inconsistent / near-duplicate / free-text-leaked labels. → cardinality/consistency
   check + a "rare update_type" review list.
3. **Regulator-name sprawl: 3,109 distinct.** Almost certainly near-duplicates /
   inconsistent naming for the same body. → normalization/dedup candidate surface.
4. **Incomplete deprecation backfill.** `classification.jurisdiction_tier` still present
   in **1,513 records (2.5%)** — the backfill (~2026-06-11) is mostly but NOT fully done.
   → cockpit should report residual legacy-field count (a concrete migration gap).
5. **`feed_url` only 50%.** Half the records cannot be linked back to source for triage.
   → flag as a triage-linkability limitation; gap-queue rows without feed_url are harder
   to action.
6. **Explicitly invalid / missing keys.** 9 records `reconciled_published_date.valid=False`;
   33 records missing envelope `topic_id` (99.9% present); update_type missing in 0.7%;
   jurisdiction.country missing in 12%.

## Sampling caveat (must be stated honestly in the showcase)
The 60K snapshot is a **contiguous offset slice**, not a uniform random sample: it covers
**403 of the ~1,087** topics. Corpus-wide breadth claims (241 jurisdictions, 1,087 topics)
describe the FULL dataset; this showcase computes its live metrics over the 60K slice and
should say so. → stress-test the spec on whether it states the snapshot's scope honestly.
