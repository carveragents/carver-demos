"""Aggregate jurisdiction event counts from Stage 1 artifacts corpus."""

import json
from datetime import datetime
from collections import defaultdict
from pathlib import Path


def parse_date(s):
    """Parse ISO date string."""
    if not s or not isinstance(s, str):
        return None
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00")).replace(tzinfo=None)
    except (ValueError, AttributeError):
        return None


def is_us_state(code):
    """Check if code is US-XX format."""
    return isinstance(code, str) and len(code) == 5 and code.startswith("US-")


def aggregate(input_file, today):
    """Stream-read and aggregate jurisdiction counts by window."""
    windows = {d: {"imp": defaultdict(int), "top": defaultdict(int)} for d in [30, 90, 180]}
    rec_count = valid = skip = 0

    with open(input_file) as f:
        for line in f:
            rec_count += 1
            try:
                r = json.loads(line)
            except json.JSONDecodeError:
                skip += 1
                continue

            # Exclusion criteria from A8
            if r.get("update_type") == "website error":
                skip += 1
                continue

            if not r.get("pub_date_valid") or not r.get("pub_date"):
                skip += 1
                continue

            pub_date = parse_date(r.get("pub_date"))
            if pub_date is None or (today - pub_date).days < 0:
                skip += 1
                continue

            valid += 1
            age = (today - pub_date).days
            imp_juris = r.get("impacted_business", {}).get("jurisdiction", [])
            top_juris = r.get("topic_jurisdiction_code", "")

            for d in [30, 90, 180]:
                if age <= d:
                    for j in imp_juris:
                        if isinstance(j, str):
                            windows[d]["imp"][j] += 1
                    if top_juris:
                        windows[d]["top"][top_juris] += 1

    return windows, rec_count, valid, skip


def top_15(d):
    """Get top 15 entries by count."""
    return sorted(d.items(), key=lambda x: x[1], reverse=True)[:15]


def is_cluster(d):
    """Check if cluster condition met: 8+ states with ≥5 events."""
    return sum(1 for v in d.values() if v >= 5) >= 8


def render_section(days, imp, top):
    """Render a window section."""
    lines = [f"## {days}-Day Window", ""]
    for name, data in [("impacted_business.jurisdiction", imp), ("topic_jurisdiction_code", top)]:
        t15 = top_15(data)
        lines.append(f"### Top 15 US States ({name})")
        lines.append("")
        lines.append("| Jurisdiction | Count |")
        lines.append("|---|---|")
        lines.extend(f"| {code} | {count} |" for code, count in t15)
        lines.append("")
    imp_tot, top_tot = sum(imp.values()), sum(top.values())
    lines.extend([
        f"**Total US-state events (impacted):** {imp_tot}",
        f"**Total US-state events (topic):** {top_tot}",
        f"**Distinct US states (impacted):** {len(imp)}",
        f"**Distinct US states (topic):** {len(top)}",
        f"**Cluster verdict:** {'✓ Cluster detected' if is_cluster(imp) or is_cluster(top) else '✗ No cluster'}",
        "",
    ])
    return "\n".join(lines)


def main():
    repo_root = Path(__file__).parent.parent
    today = datetime(2026, 5, 19)
    windows, rec_count, valid, skip = aggregate(
        repo_root / "data/_scratch/artifacts.jsonl",
        today
    )

    report = [
        "# Choropleth Density Analysis — US States (Stage 1 Artifacts)",
        "",
        f"**Build date:** {today.strftime('%Y-%m-%d')}",
        f"**Total records:** {rec_count:,}",
        f"**Valid records:** {valid:,}",
        f"**Skipped records:** {skip:,}",
        "",
    ]

    for d in [30, 90, 180]:
        imp = {k: v for k, v in windows[d]["imp"].items() if is_us_state(k)}
        top = {k: v for k, v in windows[d]["top"].items() if is_us_state(k)}
        report.append(render_section(d, imp, top))

    fed = windows[90]["top"].get("US", 0) + windows[90]["imp"].get("US", 0)
    st_imp = sum(v for k, v in windows[90]["imp"].items() if is_us_state(k))
    st_top = sum(v for k, v in windows[90]["top"].items() if is_us_state(k))

    report.extend([
        "## US-Federal vs US-State (90-Day Window)",
        "",
        f"**US (federal):** {fed}",
        f"**US-XX (state, impacted):** {st_imp}",
        f"**US-XX (state, topic):** {st_top}",
        "",
    ])

    (repo_root / "data/a9-prime-choropleth-density.md").write_text("\n".join(report))
    print(f"Report written to data/a9-prime-choropleth-density.md")


if __name__ == "__main__":
    main()
