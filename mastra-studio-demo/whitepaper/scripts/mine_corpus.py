#!/usr/bin/env python3
"""
Single streaming pass over the pinned Carver snapshot to produce the figures
files for whitepaper sections 1 (dataset) and 2 (rebuild cost).

Read-only against ../carver-showcase/data. Emits:
  whitepaper/figures/section1.json  — scale, sectors, jurisdictions, freshness, intel layer
  whitepaper/figures/section2.json  — rebuild-cost: docs, obligations, citations, dates, penalties

Every number here is derived from the snapshot; the whitepaper bakes these in at build time.
Token/reading-cost is a clearly-labeled ESTIMATE (source docs live in S3, not in the snapshot).
"""
import json, re, csv, sys, os
from collections import Counter, defaultdict

DATA = "/home/ubuntu/work/scribble/code/repos/carver-showcase/data"
OUT = "/home/ubuntu/work/scribble/code/repos/carver-demos-docs-carver-whitepaper/mastra-studio-demo/whitepaper/figures"
ANNOT = os.path.join(DATA, "annotations.jsonl")

# Conservative average tokens per regulatory source document, used only for the
# labeled reading-cost estimate. Regulatory notices/rules commonly run several
# thousand tokens; 3,000 is deliberately conservative (understates the true cost).
TOKENS_PER_DOC_ESTIMATE = 3000

# --- topic_id -> top-level sector (from taxonomy CSVs) ---
topic_top = {}
with open(os.path.join(DATA, "topic_domains.csv")) as f:
    for row in csv.DictReader(f):
        topic_top[row["topic_id"]] = (row.get("top_level") or "").strip()

# Money regex for best-effort penalty-exposure extraction from free text.
MONEY = re.compile(
    r"(?:USD|US\$|\$|€|EUR|£|GBP)\s?[\d][\d,\.]*\s?(?:billion|bn|million|mn|m|k|thousand)?",
    re.IGNORECASE,
)

def first(lst):
    return lst[0] if isinstance(lst, list) and lst else None

# --- accumulators ---
total = 0
with_meta = 0
sector_counts = Counter()          # by impacted_business.industry (first)
sector_by_topic = Counter()        # by taxonomy top_level (fallback / cross-check)
jurisdiction_counts = Counter()
regulators = set()
year_counts = Counter()            # published year
tag_missing = 0

# intelligence layer
obligations_total = 0
recs_with_obligations = 0
obligations_by_sector = defaultdict(int)
reg_refs_total = 0
recs_with_refs = 0
critical_dates_recs = 0            # records with at least one concrete critical date
penalty_recs = 0                   # records with any penalties_consequences entry
penalty_money_recs = 0             # records where a monetary amount was parseable
penalty_money_mentions = 0
docs_by_sector = Counter()

DATE_FIELDS = ["effective_date", "compliance_date", "comment_deadline",
               "early_adoption_date", "updated_date"]

def sector_of(md):
    ib = md.get("impacted_business") or {}
    ind = first(ib.get("industry"))
    if ind:
        return ind.strip()
    return None

with open(ANNOT, encoding="utf-8") as f:
    for line in f:
        line = line.strip()
        if not line:
            continue
        try:
            d = json.loads(line)
        except json.JSONDecodeError:
            continue
        total += 1
        od = d.get("output_data") or {}
        md = od.get("metadata") or {}
        if not md:
            continue
        with_meta += 1

        # topic-based sector (taxonomy)
        tid = d.get("topic_id")
        top = topic_top.get(tid)
        if top:
            sector_by_topic[top] += 1

        # business-based sector
        sec = sector_of(md) or (top if top else "Uncategorized")
        sector_counts[sec] += 1
        docs_by_sector[sec] += 1

        # jurisdiction
        ib = md.get("impacted_business") or {}
        jur = first(ib.get("jurisdiction"))
        if jur:
            jurisdiction_counts[str(jur).strip()] += 1

        # regulator (from impacted or topic name is not here; use reg refs personnel not reliable)
        # published year
        rpd = od.get("reconciled_published_date") or {}
        dt = rpd.get("date")
        if isinstance(dt, str) and len(dt) >= 4 and dt[:4].isdigit():
            year_counts[dt[:4]] += 1

        # obligations
        isum = md.get("impact_summary") or {}
        kr = isum.get("key_requirements")
        if isinstance(kr, list) and kr:
            n = len(kr)
            obligations_total += n
            recs_with_obligations += 1
            obligations_by_sector[sec] += n

        # reg references
        rr = md.get("reg_references") or {}
        nref = 0
        for k in ("rules", "statutes", "other_ref"):
            v = rr.get(k)
            if isinstance(v, list):
                nref += len([x for x in v if x])
        if nref:
            reg_refs_total += nref
            recs_with_refs += 1

        # critical dates
        cd = md.get("critical_dates") or {}
        if any((cd.get(fld) or "").strip() for fld in DATE_FIELDS) or (cd.get("other_dates")):
            critical_dates_recs += 1

        # penalties (free text -> best-effort money extraction)
        pc = md.get("penalties_consequences")
        if isinstance(pc, list) and any(str(x).strip() for x in pc):
            penalty_recs += 1
            joined = " ".join(str(x) for x in pc)
            hits = MONEY.findall(joined)
            if hits:
                penalty_money_recs += 1
                penalty_money_mentions += len(hits)

        if total % 20000 == 0:
            print(f"...{total} records", file=sys.stderr, flush=True)

# --- snapshot meta ---
snap = json.load(open(os.path.join(DATA, "snapshot_meta.json")))
term = json.load(open(os.path.join(DATA, "term_stats_meta.json")))

def topn(counter, n):
    return [{"name": k, "count": v} for k, v in counter.most_common(n)]

section1 = {
    "snapshot_date": snap["snapshot_date"],
    "total_records": total,
    "records_with_metadata": with_meta,
    "distinct_entities": term["n_distinct_entities"],
    "entity_mentions": term["n_entity_mentions"],
    "distinct_tags": term["n_distinct_tags"],
    "tag_mentions": term["n_tag_mentions"],
    "classified_records": term["n_classified"],
    "sectors_top": topn(sector_counts, 14),
    "sectors_by_taxonomy_top": topn(sector_by_topic, 14),
    "jurisdictions_top": topn(jurisdiction_counts, 20),
    "distinct_jurisdictions": len(jurisdiction_counts),
    "distinct_sectors": len(sector_counts),
    "published_by_year": sorted(
        [{"year": y, "count": c} for y, c in year_counts.items()],
        key=lambda r: r["year"],
    ),
    "intelligence_layer": {
        "obligations_extracted": obligations_total,
        "records_with_obligations": recs_with_obligations,
        "reg_references_resolved": reg_refs_total,
        "records_with_reg_references": recs_with_refs,
        "records_with_critical_dates": critical_dates_recs,
        "records_with_penalties": penalty_recs,
    },
}

section2 = {
    "snapshot_date": snap["snapshot_date"],
    "documents_analyzed": total,
    "tokens_per_doc_estimate": TOKENS_PER_DOC_ESTIMATE,
    "estimated_source_read_tokens": total * TOKENS_PER_DOC_ESTIMATE,
    "obligations_extracted": obligations_total,
    "reg_references_resolved": reg_refs_total,
    "records_with_critical_dates": critical_dates_recs,
    "records_with_penalties": penalty_recs,
    "penalty_records_with_parseable_amount": penalty_money_recs,
    "penalty_money_mentions": penalty_money_mentions,
    "obligations_by_sector": [
        {"name": k, "obligations": v}
        for k, v in sorted(obligations_by_sector.items(), key=lambda kv: -kv[1])[:14]
    ],
    "docs_by_sector": topn(docs_by_sector, 14),
    "notes": {
        "source_tokens": "ESTIMATE ONLY. Full source documents are stored in S3, not in the "
                         "snapshot; reading cost = documents_analyzed x tokens_per_doc_estimate "
                         "(3,000 tokens/doc, deliberately conservative).",
        "penalties": "penalties_consequences is free-text narrative; monetary figures are a "
                     "best-effort regex extraction over currency mentions and are counts of "
                     "records/mentions, NOT a summed dollar total.",
    },
}

os.makedirs(OUT, exist_ok=True)
json.dump(section1, open(os.path.join(OUT, "section1.json"), "w"), indent=2)
json.dump(section2, open(os.path.join(OUT, "section2.json"), "w"), indent=2)
print(f"DONE. {total} records. figures written to {OUT}", file=sys.stderr)
