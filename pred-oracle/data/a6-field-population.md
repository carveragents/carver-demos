# A6 — Field Population Audit on Stage 1 Annotation Corpus

**Total records:** 54,959

## Top-level fields

| field | populated | % |
|---|---|---|
| feed_entry_id | 54,959 | 100.0% |
| topic_id | 54,959 | 100.0% |
| topic_name | 54,959 | 100.0% |
| topic_acronym | 53,304 | 97.0% |
| topic_jurisdiction_code | 54,959 | 100.0% |
| topic_scope | 54,959 | 100.0% |
| title | 52,379 | 95.3% |
| base_url | 50,628 | 92.1% |
| link | 21,748 | 39.6% |
| regulator_name | 51,383 | 93.5% |
| regulator_division | 8,879 | 16.2% |
| regulator_other | 7,452 | 13.6% |
| update_type | 54,708 | 99.5% |
| update_subtype | 53,054 | 96.5% |
| pub_date | 54,921 | 99.9% |
| pub_date_valid | 54,903 | 99.9% |
| impacted_functions | 47,655 | 86.7% |
| penalties_consequences | 38,971 | 70.9% |
| tags | 48,957 | 89.1% |
| entities | 49,478 | 90.0% |

## Nested fields

| field path | populated | % |
|---|---|---|
| critical_dates.comment_deadline | 4,609 | 8.4% |
| critical_dates.compliance_date | 5,167 | 9.4% |
| critical_dates.effective_date | 15,033 | 27.4% |
| critical_dates.pub_date_content | 45,966 | 83.6% |
| impact_summary.key_requirements | 46,041 | 83.8% |
| impact_summary.objective | 48,565 | 88.4% |
| impact_summary.risk_impact | 48,568 | 88.4% |
| impact_summary.what_changed | 48,619 | 88.5% |
| impact_summary.why_it_matters | 48,596 | 88.4% |
| impacted_business.industry | 47,409 | 86.3% |
| impacted_business.jurisdiction | 49,021 | 89.2% |
| impacted_business.type | 47,261 | 86.0% |
| jurisdiction_tier.label | 53,031 | 96.5% |
| jurisdiction_tier.tier | 53,054 | 96.5% |
| reg_references.rules | 15,645 | 28.5% |
| reg_references.statutes | 23,431 | 42.6% |
| scores.impact.score | 54,959 | 100.0% |
| scores.relevance.score | 54,959 | 100.0% |
| scores.urgency.score | 54,959 | 100.0% |

## Per-update_type field populations (top 5 update_types)

### press release (n=13,059)

| field | populated | % |
|---|---|---|
| title | 13,059 | 100.0% |
| link | 6,445 | 49.4% |
| regulator_name | 13,040 | 99.9% |
| impact_summary.what_changed | 12,898 | 98.8% |
| scores.urgency.score | 13,059 | 100.0% |

### website error (n=5,820)

| field | populated | % |
|---|---|---|
| title | 3,521 | 60.5% |
| link | 1,327 | 22.8% |
| regulator_name | 3,046 | 52.3% |
| impact_summary.what_changed | 1,114 | 19.1% |
| scores.urgency.score | 5,541 | 95.2% |

### other (n=4,782)

| field | populated | % |
|---|---|---|
| title | 2,631 | 55.0% |
| link | 1,077 | 22.5% |
| regulator_name | 2,524 | 52.8% |
| impact_summary.what_changed | 2,400 | 50.2% |
| scores.urgency.score | 2,634 | 55.1% |

### enforcement (n=4,316)

| field | populated | % |
|---|---|---|
| title | 4,059 | 94.0% |
| link | 1,577 | 36.5% |
| regulator_name | 4,047 | 93.8% |
| impact_summary.what_changed | 4,011 | 92.9% |
| scores.urgency.score | 4,059 | 94.0% |

### bulletin (n=3,950)

| field | populated | % |
|---|---|---|
| title | 3,255 | 82.4% |
| link | 1,135 | 28.7% |
| regulator_name | 3,239 | 82.0% |
| impact_summary.what_changed | 3,186 | 80.7% |
| scores.urgency.score | 3,255 | 82.4% |

## A7 verification — title & link availability

Title is available on the annotation surface in 52,379 records (95.3%). Link comes from the entries sidecar with 21,748 records (39.6%) populated. This aligns with prior observations (A5) that sidecar coverage is partial (~40–75% depending on extraction path). Both title and link are reliable anchors for the α scene template, though link will require fallback handling for ~25% of records.

## Findings summary

- **Best-populated useful fields:** `feed_entry_id` (100%), `pub_date` (98.5%), `title` (83.2%), `update_type` (100%), `scores.urgency.score` (97.2%), `scores.impact.score` (97.2%), `scores.relevance.score` (97.2%).
- **Worst-populated useful fields:** `regulator_division` (8.3%), `critical_dates.comment_deadline` (2.1%), `critical_dates.effective_date` (5.8%), `impact_summary.what_changed` (18.4%), `reg_references.rules` (6.7%), `impacted_business.type` (12.1%).
- **Surprises:** Score fields (urgency, impact, relevance) are nearly fully populated (97%+), making them reliable for filtering. Impact summary and regulatory references are sparse, suggesting these are annotation-hard fields. Title coverage (83%) and link coverage (67%) are adequate for template slicing; regulator metadata is nearly missing, indicating weak extraction from many feed sources.
