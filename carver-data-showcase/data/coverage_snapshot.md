# Coverage snapshot — 211,489 annotation records

> Read-only, deterministic. `""` / `[]` / null counted as MISSING.

## Distinct values
- **topic_id**: 1,046 distinct
- **country**: 158 distinct
- **update_type**: 114 distinct
- **regulator**: 11,442 distinct
- **scope**: 5 distinct
- **bloc**: 116 distinct
- **reconciled_published_date range**: 1442-07-01 … 2569-04-30

## Field population
| field | populated | % |
|---|---:|---:|
| `scores.impact.score` | 211,489 | 100.0% |
| `scores.impact.confidence` | 211,489 | 100.0% |
| `scores.urgency.score` | 211,489 | 100.0% |
| `scores.urgency.basis` | 211,335 | 99.9% |
| `scores.relevance.score` | 211,489 | 100.0% |
| `metadata.tags` | 187,200 | 88.5% |
| `metadata.entities` | 195,707 | 92.5% |
| `impact_summary.objective` | 185,636 | 87.8% |
| `impact_summary.what_changed` | 185,731 | 87.8% |
| `impact_summary.why_it_matters` | 185,692 | 87.8% |
| `impact_summary.risk_impact` | 185,565 | 87.7% |
| `impact_summary.key_requirements` | 169,132 | 80.0% |
| `critical_dates.effective_date` | 50,632 | 23.9% |
| `critical_dates.compliance_date` | 18,514 | 8.8% |
| `critical_dates.comment_deadline` | 12,807 | 6.1% |
| `critical_dates.other_dates` | 99,302 | 47.0% |
| `reg_references.rules` | 35,338 | 16.7% |
| `reg_references.statutes` | 60,479 | 28.6% |
| `impacted_business.industry` | 177,798 | 84.1% |
| `impacted_functions` | 180,141 | 85.2% |
| `penalties_consequences` | 121,597 | 57.5% |
| `classification.update_type` | 211,055 | 99.8% |
| `classification.update_subtype` | 211,335 | 99.9% |
| `classification.jurisdiction.country` | 160,172 | 75.7% |
| `classification.jurisdiction.scope` | 190,437 | 90.0% |
| `classification.regulatory_source.name` | 198,176 | 93.7% |
| `classification.metadata.title` | 201,817 | 95.4% |
| `classification.metadata.feed_url` | 110,819 | 52.4% |
| `reconciled_published_date.date` | 211,489 | 100.0% |
| `topic_id (envelope)` | 211,456 | 100.0% |
| `completed_at (envelope)` | 211,489 | 100.0% |
| `classification.jurisdiction_tier (DEPRECATED)` | 20,995 | 9.9% |

## Impact label distribution
- medium: 94,722 (44.8%)
- high: 58,712 (27.8%)
- low: 58,055 (27.5%)

## Urgency basis (top 10)
- no_future_date: 109,546 (51.8%)
- past_deadline: 82,644 (39.1%)
- future_deadline: 18,003 (8.5%)
- effective_immediately: 1,142 (0.5%)

## reconciled_published_date.valid
- valid=True: 211,472 (100.0%)
- valid=False: 17 (0.0%)
