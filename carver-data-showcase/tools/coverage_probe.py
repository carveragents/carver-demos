"""Real field-coverage snapshot over the pulled annotation corpus.

Read-only, deterministic grounding for the showcase's "honest coverage" story and for
the tandem stress-test. Streams data/annotations.jsonl, treats "" / [] / null as
MISSING, and reports population % per field plus distinct-value counts and a few
distributions. No LLM, no app logic.

Run: .venv/bin/python tools/coverage_probe.py
Writes a markdown summary to data/coverage_snapshot.md and prints it.
"""

import json
import os
from collections import Counter

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
JSONL = os.path.join(ROOT, "data", "annotations.jsonl")
OUT = os.path.join(ROOT, "data", "coverage_snapshot.md")


def present(v) -> bool:
    """A value counts as populated unless it is None, '', [], {}, or whitespace."""
    if v is None:
        return False
    if isinstance(v, str):
        return v.strip() != ""
    if isinstance(v, (list, dict)):
        return len(v) > 0
    return True


def iter_annotations(path):
    with open(path) as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            env = json.loads(line)
            yield env, env.get("output_data", {}) or {}


# Fields to measure, addressed by a function over (envelope, annotation).
def g(d, *path):
    cur = d
    for p in path:
        if not isinstance(cur, dict):
            return None
        cur = cur.get(p)
    return cur


FIELDS = {
    # scores
    "scores.impact.score": lambda e, a: g(a, "scores", "impact", "score"),
    "scores.impact.confidence": lambda e, a: g(a, "scores", "impact", "confidence"),
    "scores.urgency.score": lambda e, a: g(a, "scores", "urgency", "score"),
    "scores.urgency.basis": lambda e, a: g(a, "scores", "urgency", "basis"),
    "scores.relevance.score": lambda e, a: g(a, "scores", "relevance", "score"),
    # metadata richness
    "metadata.tags": lambda e, a: g(a, "metadata", "tags"),
    "metadata.entities": lambda e, a: g(a, "metadata", "entities"),
    "impact_summary.objective": lambda e, a: g(a, "metadata", "impact_summary", "objective"),
    "impact_summary.what_changed": lambda e, a: g(a, "metadata", "impact_summary", "what_changed"),
    "impact_summary.why_it_matters": lambda e, a: g(a, "metadata", "impact_summary", "why_it_matters"),
    "impact_summary.risk_impact": lambda e, a: g(a, "metadata", "impact_summary", "risk_impact"),
    "impact_summary.key_requirements": lambda e, a: g(a, "metadata", "impact_summary", "key_requirements"),
    "critical_dates.effective_date": lambda e, a: g(a, "metadata", "critical_dates", "effective_date"),
    "critical_dates.compliance_date": lambda e, a: g(a, "metadata", "critical_dates", "compliance_date"),
    "critical_dates.comment_deadline": lambda e, a: g(a, "metadata", "critical_dates", "comment_deadline"),
    "critical_dates.other_dates": lambda e, a: g(a, "metadata", "critical_dates", "other_dates"),
    "reg_references.rules": lambda e, a: g(a, "metadata", "reg_references", "rules"),
    "reg_references.statutes": lambda e, a: g(a, "metadata", "reg_references", "statutes"),
    "impacted_business.industry": lambda e, a: g(a, "metadata", "impacted_business", "industry"),
    "impacted_functions": lambda e, a: g(a, "metadata", "impacted_functions"),
    "penalties_consequences": lambda e, a: g(a, "metadata", "penalties_consequences"),
    # classification
    "classification.update_type": lambda e, a: g(a, "classification", "update_type"),
    "classification.update_subtype": lambda e, a: g(a, "classification", "update_subtype"),
    "classification.jurisdiction.country": lambda e, a: g(a, "classification", "jurisdiction", "country"),
    "classification.jurisdiction.scope": lambda e, a: g(a, "classification", "jurisdiction", "scope"),
    "classification.regulatory_source.name": lambda e, a: g(a, "classification", "regulatory_source", "name"),
    "classification.metadata.title": lambda e, a: g(a, "classification", "metadata", "title"),
    "classification.metadata.feed_url": lambda e, a: g(a, "classification", "metadata", "feed_url"),
    # provenance / envelope
    "reconciled_published_date.date": lambda e, a: g(a, "reconciled_published_date", "date"),
    "topic_id (envelope)": lambda e, a: e.get("topic_id"),
    "completed_at (envelope)": lambda e, a: e.get("completed_at"),
    # legacy
    "classification.jurisdiction_tier (DEPRECATED)": lambda e, a: g(a, "classification", "jurisdiction_tier"),
}


def main():
    total = 0
    pop = Counter()
    distinct = {k: set() for k in ["topic_id", "country", "update_type", "regulator", "scope", "bloc"]}
    impact_labels = Counter()
    urgency_basis = Counter()
    dates = []
    recon_valid = Counter()

    for env, a in iter_annotations(JSONL):
        total += 1
        for name, fn in FIELDS.items():
            if present(fn(env, a)):
                pop[name] += 1
        distinct["topic_id"].add(env.get("topic_id"))
        distinct["country"].add(g(a, "classification", "jurisdiction", "country"))
        distinct["update_type"].add(g(a, "classification", "update_type"))
        distinct["regulator"].add(g(a, "classification", "regulatory_source", "name"))
        distinct["scope"].add(g(a, "classification", "jurisdiction", "scope"))
        distinct["bloc"].add(g(a, "classification", "jurisdiction", "bloc"))
        il = g(a, "scores", "impact", "label")
        if present(il):
            impact_labels[il] += 1
        ub = g(a, "scores", "urgency", "basis")
        if present(ub):
            urgency_basis[ub] += 1
        d = g(a, "reconciled_published_date", "date")
        if present(d):
            dates.append(d)
        rv = g(a, "reconciled_published_date", "valid")
        recon_valid[str(rv)] += 1

    def pct(n):
        return f"{100.0 * n / total:.1f}%" if total else "n/a"

    lines = []
    lines.append(f"# Coverage snapshot — {total:,} annotation records\n")
    lines.append("> Read-only, deterministic. `\"\"` / `[]` / null counted as MISSING.\n")
    lines.append("## Distinct values")
    for k in ["topic_id", "country", "update_type", "regulator", "scope", "bloc"]:
        vals = {v for v in distinct[k] if present(v)}
        lines.append(f"- **{k}**: {len(vals):,} distinct")
    if dates:
        lines.append(f"- **reconciled_published_date range**: {min(dates)} … {max(dates)}")
    lines.append("")
    lines.append("## Field population")
    lines.append("| field | populated | % |")
    lines.append("|---|---:|---:|")
    for name in FIELDS:
        lines.append(f"| `{name}` | {pop[name]:,} | {pct(pop[name])} |")
    lines.append("")
    lines.append("## Impact label distribution")
    for lab, n in impact_labels.most_common():
        lines.append(f"- {lab}: {n:,} ({pct(n)})")
    lines.append("")
    lines.append("## Urgency basis (top 10)")
    for b, n in urgency_basis.most_common(10):
        lines.append(f"- {b}: {n:,} ({pct(n)})")
    lines.append("")
    lines.append("## reconciled_published_date.valid")
    for v, n in recon_valid.most_common():
        lines.append(f"- valid={v}: {n:,} ({pct(n)})")
    lines.append("")

    report = "\n".join(lines)
    with open(OUT, "w") as fh:
        fh.write(report)
    print(report)
    print(f"\n[written to {OUT}]")


if __name__ == "__main__":
    main()
