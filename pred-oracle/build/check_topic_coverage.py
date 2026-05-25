#!/usr/bin/env python3
"""
Validate topic_id coverage: check if event topic_ids resolve to recognizable regulator names.
Loads carver-events.json and carver-topics.json, analyzes resolution rates and topic names.
"""

import json
from collections import Counter
from pathlib import Path
import re

# Load data
events_path = Path("data/carver-events.json")
topics_path = Path("data/carver-topics.json")

with open(events_path) as f:
    events = json.load(f)

with open(topics_path) as f:
    topics = json.load(f)

# Build topics_by_id mapping
topics_by_id = {topic["id"]: topic["name"] for topic in topics}

# Track hits, misses, and missing topic_ids
hits = 0
misses = 0
missing_topic_ids = set()
resolved_names = []

for event in events:
    topic_id = event.get("topic_id")
    if topic_id in topics_by_id:
        hits += 1
        resolved_names.append(topics_by_id[topic_id])
    else:
        misses += 1
        missing_topic_ids.add(topic_id)

# Count occurrences of each topic name
topic_counts = Counter(resolved_names)
top_20 = topic_counts.most_common(20)
distinct_topics = len(topic_counts)

# Heuristic to detect regulator-like names
def looks_like_regulator(name: str) -> bool:
    """Check if name contains uppercase acronym or regulator keywords."""
    # Check for uppercase acronyms (e.g., SEC, CFTC, FCA, BofE)
    if re.search(r'\b[A-Z]{2,}\b', name):
        return True
    # Check for regulator keywords
    keywords = [
        "commission", "authority", "bureau", "department",
        "agency", "office", "board", "ministry", "regulator",
        "central bank", "reserve", "bank", "administration"
    ]
    name_lower = name.lower()
    return any(keyword in name_lower for keyword in keywords)

# Analyze top 20
regulator_count = 0
for _, count in top_20:
    # Using the topic name from the original list
    pass

top_20_with_regulator = []
for i, (name, count) in enumerate(top_20, 1):
    is_regulator = looks_like_regulator(name)
    if is_regulator:
        regulator_count += 1
    top_20_with_regulator.append((i, name, count, is_regulator))

# Determine verdict
hit_rate = hits / len(events) if len(events) > 0 else 0
regulator_ratio = regulator_count / 20 if len(top_20) == 20 else regulator_count / len(top_20)

if misses == 0:
    verdict = "yes, clean join"
elif regulator_ratio >= 0.75 and hit_rate > 0.95:
    verdict = "yes but messy (some non-regulator topics in the mix)"
else:
    verdict = "no, significant misses"

# Print to stdout
print("=" * 80)
print("TOPIC_ID COVERAGE ANALYSIS")
print("=" * 80)
print(f"\nHit Rate: {hits}/{len(events)} ({hit_rate*100:.1f}%)")
print(f"Miss Rate: {misses}/{len(events)} ({misses/len(events)*100:.1f}%)")
print(f"Distinct Topic Names: {distinct_topics}")
print(f"\nTop 20 Topic Names (by event count):")
print("-" * 80)
print(f"{'Rank':<6} {'Topic Name':<50} {'Count':<8} {'Regulator?':<12}")
print("-" * 80)
for rank, name, count, is_reg in top_20_with_regulator:
    reg_str = "Yes" if is_reg else "No"
    print(f"{rank:<6} {name:<50} {count:<8} {reg_str:<12}")

if missing_topic_ids:
    print(f"\nMissing Topic IDs ({len(missing_topic_ids)} unique):")
    sample_size = min(10, len(missing_topic_ids))
    for tid in list(missing_topic_ids)[:sample_size]:
        print(f"  - {tid}")
    if len(missing_topic_ids) > 10:
        print(f"  ... and {len(missing_topic_ids) - 10} more")

print(f"\nVerdict: {verdict}")
print("=" * 80)

# Write markdown report
report_path = Path("data/a3-topic-id-coverage.md")
with open(report_path, "w") as f:
    f.write("# Topic ID Coverage Analysis\n\n")
    f.write("## Summary\n\n")
    f.write(f"- **Hit Rate**: {hits}/{len(events)} ({hit_rate*100:.1f}%)\n")
    f.write(f"- **Miss Rate**: {misses}/{len(events)} ({misses/len(events)*100:.1f}%)\n")
    f.write(f"- **Distinct Topic Names**: {distinct_topics}\n\n")

    f.write("## Top 20 Topic Names\n\n")
    f.write("| Rank | Topic Name | Count | Looks Like Regulator? |\n")
    f.write("|------|------------|-------|----------------------|\n")
    for rank, name, count, is_reg in top_20_with_regulator:
        reg_str = "Yes" if is_reg else "No"
        f.write(f"| {rank} | {name} | {count} | {reg_str} |\n")

    if missing_topic_ids:
        f.write(f"\n## Missing Topic IDs ({len(missing_topic_ids)} unique)\n\n")
        sample_size = min(10, len(missing_topic_ids))
        for tid in list(missing_topic_ids)[:sample_size]:
            f.write(f"- {tid}\n")
        if len(missing_topic_ids) > 10:
            f.write(f"\n... and {len(missing_topic_ids) - 10} more\n")

    f.write(f"\n## Verdict\n\n")
    f.write(f"**{verdict}**\n\n")
    if verdict == "yes, clean join":
        f.write(
            "All event topic_ids resolve successfully to topic names. The approach of using "
            "topic_id → topic_name to populate the regulator-name field is reliable and requires no cleanup.\n"
        )
    elif verdict == "yes but messy (some non-regulator topics in the mix)":
        f.write(
            f"High resolution rate ({hit_rate*100:.1f}%) with {regulator_count}/20 top topics appearing regulator-like. "
            "The approach is generally sound but may require filtering for non-regulator topics in the final data pipeline.\n"
        )
    else:
        f.write(
            f"Significant miss rate ({misses/len(events)*100:.1f}%) or low regulator representation. "
            "This approach may be incomplete without supplementary lookup methods or data enrichment.\n"
        )

print(f"\nReport written to {report_path}")
