# Coverage snapshot — 58,982 annotation records

> Read-only, deterministic. `""` / `[]` / null counted as MISSING.

## Distinct values
- **topic_id**: 405 distinct
- **country**: 111 distinct
- **update_type**: 56 distinct
- **regulator**: 3,219 distinct
- **scope**: 5 distinct
- **bloc**: 58 distinct
- **reconciled_published_date range**: 1947-12-25 … 2105-07-01

## Field population
| field | populated | % |
|---|---:|---:|
| `scores.impact.score` | 58,982 | 100.0% |
| `scores.impact.confidence` | 58,982 | 100.0% |
| `scores.urgency.score` | 58,982 | 100.0% |
| `scores.urgency.basis` | 58,959 | 100.0% |
| `scores.relevance.score` | 58,982 | 100.0% |
| `metadata.tags` | 52,417 | 88.9% |
| `metadata.entities` | 55,075 | 93.4% |
| `impact_summary.objective` | 51,973 | 88.1% |
| `impact_summary.what_changed` | 52,005 | 88.2% |
| `impact_summary.why_it_matters` | 51,990 | 88.1% |
| `impact_summary.risk_impact` | 51,937 | 88.1% |
| `impact_summary.key_requirements` | 48,337 | 82.0% |
| `critical_dates.effective_date` | 14,160 | 24.0% |
| `critical_dates.compliance_date` | 5,138 | 8.7% |
| `critical_dates.comment_deadline` | 3,644 | 6.2% |
| `critical_dates.other_dates` | 28,144 | 47.7% |
| `reg_references.rules` | 11,293 | 19.1% |
| `reg_references.statutes` | 19,719 | 33.4% |
| `impacted_business.industry` | 50,668 | 85.9% |
| `impacted_functions` | 50,831 | 86.2% |
| `penalties_consequences` | 36,789 | 62.4% |
| `classification.update_type` | 58,599 | 99.4% |
| `classification.update_subtype` | 58,959 | 100.0% |
| `classification.jurisdiction.country` | 47,501 | 80.5% |
| `classification.jurisdiction.scope` | 55,945 | 94.9% |
| `classification.regulatory_source.name` | 55,055 | 93.3% |
| `classification.metadata.title` | 56,386 | 95.6% |
| `classification.metadata.feed_url` | 31,809 | 53.9% |
| `reconciled_published_date.date` | 58,982 | 100.0% |
| `topic_id (envelope)` | 58,982 | 100.0% |
| `completed_at (envelope)` | 58,982 | 100.0% |
| `classification.jurisdiction_tier (DEPRECATED)` | 3,037 | 5.1% |

## Impact label distribution
- medium: 24,825 (42.1%)
- high: 19,777 (33.5%)
- low: 14,380 (24.4%)

## Urgency basis (top 10)
- no_future_date: 32,827 (55.7%)
- past_deadline: 23,226 (39.4%)
- future_deadline: 2,502 (4.2%)
- effective_immediately: 404 (0.7%)

## reconciled_published_date.valid
- valid=True: 58,973 (100.0%)
- valid=False: 9 (0.0%)
