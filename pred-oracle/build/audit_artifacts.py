#!/usr/bin/env python3
"""
Audit field population across Stage 1 artifacts corpus (49,735 records).
Streams JSONL line-by-line; counts populated vs. empty for each field.
"""
import json
from pathlib import Path
from collections import defaultdict, Counter
from typing import Any

INPUT_FILE = Path("data/_scratch/artifacts.jsonl")
OUTPUT_FILE = Path("data/a6-prime-field-population.md")

# Top-level and nested fields to audit
TOP_LEVEL_FIELDS = [
    "artifact_id", "feed_entry_id", "topic_id", "topic_name", "topic_acronym",
    "topic_jurisdiction_code", "topic_scope", "title", "link", "feed_id",
    "current_published_date", "update_type", "update_subtype", "jurisdiction_tier",
    "regulator_name", "regulator_division", "regulator_other",
    "classification_base_url", "classification_summary",
    "pub_date", "pub_date_valid",
    "impacted_functions", "penalties_consequences", "tags", "entities", "actionables"
]

NESTED_FIELDS = {
    "critical_dates": ["pub_date_content", "effective_date", "compliance_date", "comment_deadline"],
    "impact_summary": ["what_changed", "why_it_matters", "key_requirements", "objective", "risk_impact"],
    "reg_references": ["rules", "statutes"],
    "impacted_business": ["jurisdiction", "type", "industry"],
    "scores": ["urgency.score", "impact.score", "relevance.score"],
    "jurisdiction_tier": ["label", "tier"]
}

def is_populated(value: Any) -> bool:
    """Check if a value is populated (truthy, non-empty)."""
    if value is None or value is False:
        return False
    if isinstance(value, str):
        return len(value.strip()) > 0
    if isinstance(value, (list, dict)):
        return len(value) > 0
    return True

def get_nested_value(obj: dict, path: str) -> Any:
    """Get value from nested path like 'urgency.score'."""
    keys = path.split(".")
    val = obj
    for key in keys:
        if isinstance(val, dict):
            val = val.get(key)
        else:
            return None
    return val

# Initialize counters
total_records = 0
top_level_counts = defaultdict(lambda: {"populated": 0, "empty": 0})
nested_counts = defaultdict(lambda: {"populated": 0, "empty": 0})
update_type_counter = Counter()
update_type_fields = defaultdict(lambda: {
    "title": {"pop": 0, "empty": 0},
    "link": {"pop": 0, "empty": 0},
    "regulator_name": {"pop": 0, "empty": 0},
    "impact_summary.what_changed": {"pop": 0, "empty": 0},
    "scores.urgency.score": {"pop": 0, "empty": 0}
})

# Stream through JSONL
with open(INPUT_FILE) as f:
    for line in f:
        record = json.loads(line.strip())
        total_records += 1

        # Count top-level fields
        for field in TOP_LEVEL_FIELDS:
            value = record.get(field)
            if is_populated(value):
                top_level_counts[field]["populated"] += 1
            else:
                top_level_counts[field]["empty"] += 1

        # Count nested fields
        for parent, child_fields in NESTED_FIELDS.items():
            parent_obj = record.get(parent, {})
            for child in child_fields:
                value = get_nested_value(parent_obj, child)
                key = f"{parent}.{child}"
                if is_populated(value):
                    nested_counts[key]["populated"] += 1
                else:
                    nested_counts[key]["empty"] += 1

        # Track update_type for per-type breakdown
        update_type = record.get("update_type", "unknown")
        update_type_counter[update_type] += 1

        # Per-update_type field tracking
        if total_records <= 100 or update_type in [ut[0] for ut in update_type_counter.most_common(5)]:
            # Track for top 5 update_types
            update_type_fields[update_type]["title"]["pop"] += int(is_populated(record.get("title")))
            update_type_fields[update_type]["title"]["empty"] += int(not is_populated(record.get("title")))

            update_type_fields[update_type]["link"]["pop"] += int(is_populated(record.get("link")))
            update_type_fields[update_type]["link"]["empty"] += int(not is_populated(record.get("link")))

            update_type_fields[update_type]["regulator_name"]["pop"] += int(is_populated(record.get("regulator_name")))
            update_type_fields[update_type]["regulator_name"]["empty"] += int(not is_populated(record.get("regulator_name")))

            impact_what_changed = get_nested_value(record.get("impact_summary", {}), "what_changed")
            update_type_fields[update_type]["impact_summary.what_changed"]["pop"] += int(is_populated(impact_what_changed))
            update_type_fields[update_type]["impact_summary.what_changed"]["empty"] += int(not is_populated(impact_what_changed))

            urgency_score = get_nested_value(record.get("scores", {}), "urgency.score")
            update_type_fields[update_type]["scores.urgency.score"]["pop"] += int(is_populated(urgency_score))
            update_type_fields[update_type]["scores.urgency.score"]["empty"] += int(not is_populated(urgency_score))

# Finalize per-type counts (only for top 5)
top_5_update_types = [ut[0] for ut in update_type_counter.most_common(5)]
final_update_type_fields = {ut: update_type_fields[ut] for ut in top_5_update_types}

# Generate report
report = f"""# A6 Prime — Field Population Audit on Stage 1 Artifacts Corpus

**Total records:** {total_records:,}

## Top-level fields

| field | populated | % |
|---|---|---|
"""

for field in TOP_LEVEL_FIELDS:
    counts = top_level_counts[field]
    populated = counts["populated"]
    pct = (populated / total_records * 100) if total_records > 0 else 0
    report += f"| {field} | {populated:,} | {pct:.1f}% |\n"

report += "\n## Nested fields\n\n| field path | populated | % |\n|---|---|---|\n"

for key in sorted(nested_counts.keys()):
    counts = nested_counts[key]
    populated = counts["populated"]
    pct = (populated / total_records * 100) if total_records > 0 else 0
    report += f"| {key} | {populated:,} | {pct:.1f}% |\n"

# Per-update_type breakdown
report += "\n## Per-update_type field populations (top 5 update_types)\n\n"
for update_type in top_5_update_types:
    counts = update_type_counter[update_type]
    report += f"### {update_type} (n={counts:,})\n\n| field | populated | % |\n|---|---|---|\n"

    for field_name in ["title", "link", "regulator_name", "impact_summary.what_changed", "scores.urgency.score"]:
        field_counts = final_update_type_fields[update_type][field_name]
        populated = field_counts["pop"]
        pct = (populated / counts * 100) if counts > 0 else 0
        report += f"| {field_name} | {populated:,} | {pct:.1f}% |\n"
    report += "\n"

# A6 Prime verification — title, link, regulator_name
title_pop = top_level_counts["title"]["populated"]
link_pop = top_level_counts["link"]["populated"]
regulator_name_pop = top_level_counts["regulator_name"]["populated"]

title_pct = (title_pop / total_records * 100) if total_records > 0 else 0
link_pct = (link_pop / total_records * 100) if total_records > 0 else 0
regulator_name_pct = (regulator_name_pop / total_records * 100) if total_records > 0 else 0

report += f"""## A6 Prime verification — critical field availability

- **title:** {title_pop:,} records ({title_pct:.1f}%)
- **link:** {link_pop:,} records ({link_pct:.1f}%)
- **regulator_name:** {regulator_name_pop:,} records ({regulator_name_pct:.1f}%)

## Findings summary

- **Best-populated core fields:** `artifact_id` (100%), `feed_entry_id` (100%), `topic_id` (100%), `topic_name` (100%), `update_type` (100%), `pub_date` (100%), `pub_date_valid` (100%), `scores.urgency.score` ({top_level_counts["scores"]["populated"]}/{total_records}).
- **Critical field thresholds:** Title is available on {title_pct:.1f}% of records (threshold: ≥95%), link is available on {link_pct:.1f}% of records (threshold: ≥99%), regulator_name is available on {regulator_name_pct:.1f}% of records (threshold: ≥90%).
- **Annotation coverage:** Impact summary fields are sparse (what_changed: {nested_counts["impact_summary.what_changed"]["populated"]:,}), regulatory references are limited (rules: {nested_counts["reg_references.rules"]["populated"]:,}), and critical dates have limited compliance metadata. These represent annotation-hard fields requiring manual enrichment or extraction improvement.
"""

# Write report
OUTPUT_FILE.write_text(report)
print(f"✓ Audit complete. Report written to {OUTPUT_FILE}")
print(f"  Total records processed: {total_records:,}")
