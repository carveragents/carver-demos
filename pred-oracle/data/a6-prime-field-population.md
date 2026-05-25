# A6 Prime — Field Population Audit on Stage 1 Artifacts Corpus

**Total records:** 49,735

## Top-level fields

| field | populated | % |
|---|---|---|
| artifact_id | 49,735 | 100.0% |
| feed_entry_id | 49,733 | 100.0% |
| topic_id | 49,735 | 100.0% |
| topic_name | 49,735 | 100.0% |
| topic_acronym | 48,114 | 96.7% |
| topic_jurisdiction_code | 49,735 | 100.0% |
| topic_scope | 49,735 | 100.0% |
| title | 49,726 | 100.0% |
| link | 49,735 | 100.0% |
| feed_id | 49,735 | 100.0% |
| current_published_date | 49,733 | 100.0% |
| update_type | 49,522 | 99.6% |
| update_subtype | 49,710 | 99.9% |
| jurisdiction_tier | 49,710 | 99.9% |
| regulator_name | 46,437 | 93.4% |
| regulator_division | 8,456 | 17.0% |
| regulator_other | 6,748 | 13.6% |
| classification_base_url | 45,693 | 91.9% |
| classification_summary | 48,894 | 98.3% |
| pub_date | 49,735 | 100.0% |
| pub_date_valid | 49,726 | 100.0% |
| impacted_functions | 42,995 | 86.4% |
| penalties_consequences | 35,157 | 70.7% |
| tags | 44,192 | 88.9% |
| entities | 46,313 | 93.1% |
| actionables | 49,735 | 100.0% |

## Nested fields

| field path | populated | % |
|---|---|---|
| critical_dates.comment_deadline | 4,073 | 8.2% |
| critical_dates.compliance_date | 4,586 | 9.2% |
| critical_dates.effective_date | 13,389 | 26.9% |
| critical_dates.pub_date_content | 41,271 | 83.0% |
| impact_summary.key_requirements | 41,416 | 83.3% |
| impact_summary.objective | 43,758 | 88.0% |
| impact_summary.risk_impact | 43,762 | 88.0% |
| impact_summary.what_changed | 43,811 | 88.1% |
| impact_summary.why_it_matters | 43,790 | 88.0% |
| impacted_business.industry | 42,733 | 85.9% |
| impacted_business.jurisdiction | 44,172 | 88.8% |
| impacted_business.type | 42,596 | 85.6% |
| jurisdiction_tier.label | 49,690 | 99.9% |
| jurisdiction_tier.tier | 49,710 | 99.9% |
| reg_references.rules | 14,066 | 28.3% |
| reg_references.statutes | 21,336 | 42.9% |
| scores.impact.score | 49,735 | 100.0% |
| scores.relevance.score | 49,735 | 100.0% |
| scores.urgency.score | 49,735 | 100.0% |

## Per-update_type field populations (top 5 update_types)

### press release (n=12,923)

| field | populated | % |
|---|---|---|
| title | 12,923 | 100.0% |
| link | 12,923 | 100.0% |
| regulator_name | 12,904 | 99.9% |
| impact_summary.what_changed | 12,762 | 98.8% |
| scores.urgency.score | 12,923 | 100.0% |

### website error (n=5,763)

| field | populated | % |
|---|---|---|
| title | 5,658 | 98.2% |
| link | 5,664 | 98.3% |
| regulator_name | 3,130 | 54.3% |
| impact_summary.what_changed | 1,091 | 18.9% |
| scores.urgency.score | 5,664 | 98.3% |

### other (n=4,696)

| field | populated | % |
|---|---|---|
| title | 2,646 | 56.3% |
| link | 2,646 | 56.3% |
| regulator_name | 2,540 | 54.1% |
| impact_summary.what_changed | 2,426 | 51.7% |
| scores.urgency.score | 2,646 | 56.3% |

### enforcement (n=4,290)

| field | populated | % |
|---|---|---|
| title | 4,212 | 98.2% |
| link | 4,212 | 98.2% |
| regulator_name | 4,200 | 97.9% |
| impact_summary.what_changed | 4,164 | 97.1% |
| scores.urgency.score | 4,212 | 98.2% |

### bulletin (n=3,881)

| field | populated | % |
|---|---|---|
| title | 3,143 | 81.0% |
| link | 3,143 | 81.0% |
| regulator_name | 3,127 | 80.6% |
| impact_summary.what_changed | 3,074 | 79.2% |
| scores.urgency.score | 3,143 | 81.0% |

## A6 Prime verification — critical field availability

- **title:** 49,726 records (100.0%)
- **link:** 49,735 records (100.0%)
- **regulator_name:** 46,437 records (93.4%)

## Findings summary

- **Best-populated core fields:** `artifact_id` (100%), `feed_entry_id` (100%), `topic_id` (100%), `topic_name` (100%), `update_type` (100%), `pub_date` (100%), `pub_date_valid` (100%), `scores.urgency.score` (0/49735).
- **Critical field thresholds:** Title is available on 100.0% of records (threshold: ≥95%), link is available on 100.0% of records (threshold: ≥99%), regulator_name is available on 93.4% of records (threshold: ≥90%).
- **Annotation coverage:** Impact summary fields are sparse (what_changed: 43,811), regulatory references are limited (rules: 14,066), and critical dates have limited compliance metadata. These represent annotation-hard fields requiring manual enrichment or extraction improvement.
