#!/usr/bin/env python3
"""
Vectorize Carver feed entries and rank by cardiovascular device relevance.

Uses TF-IDF + cosine similarity (pure stdlib + math — no scikit-learn required)
to score each entry against a cardiovascular medical device reference query.

Outputs:
    public/data/regulatory_feed.json     → Phase1 Intelligence Feed (top items)
    public/data/regulatory_horizon.json  → Phase3 Regulatory Horizon (forward-looking)

Usage:
    python scripts/vectorize_feeds.py
    python scripts/vectorize_feeds.py --threshold 0.04 --feed-limit 15
"""

import argparse
import json
import math
import re
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

# ── Reference query ────────────────────────────────────────────────────────────
# Describes the device context + relevant regulatory landscape.
# Higher TF-IDF overlap with this text → more relevant entry.

CARDIO_QUERY = """
cardiac cardiovascular heart wearable monitor wrist ECG electrocardiogram
arrhythmia atrial fibrillation AF detection pulse rhythm
defibrillator ICD implantable cardioverter pacemaker CRT catheter stent valve coronary
medical device wearable continuous monitoring class IIb class II
510k predicate substantial equivalence de novo
CER clinical evaluation report PMCF post-market clinical follow-up
post-market surveillance PMS adverse event vigilance
EU MDR IVDR MHRA FDA CDRH TGA Swissmedic CDSCO
recall FSN field safety notice FSCA field safety corrective action
software algorithm AI ML adaptive
IEC 62304 ISO 14971 MEDDEV MDCG guidance directive regulation
"""

# ── TF-IDF helpers (pure Python) ───────────────────────────────────────────────
STOP_WORDS = {
    "a", "an", "the", "and", "or", "but", "in", "on", "at", "to", "for",
    "of", "with", "by", "from", "is", "are", "was", "were", "be", "been",
    "have", "has", "had", "do", "does", "did", "will", "would", "could",
    "should", "may", "might", "shall", "can", "not", "this", "that", "these",
    "those", "it", "its", "as", "if", "so", "we", "our", "their", "they",
    "he", "she", "his", "her", "which", "what", "who", "when", "where",
    "how", "all", "also", "more", "new", "other", "any", "each", "no",
    "than", "then", "into", "out", "up", "about", "after", "before",
    "between", "through", "during", "under", "over", "per",
}


def tokenize(text: str) -> list[str]:
    tokens = re.findall(r"\b[a-z0-9][a-z0-9]{1,}\b", text.lower())
    return [t for t in tokens if t not in STOP_WORDS]


def build_tfidf(docs: list[str]) -> tuple[list[dict[str, float]], dict[str, float]]:
    """
    Returns (vectors, idf_table) where each vector is {term: tfidf_weight}.
    Uses smooth IDF: log((N+1) / (df+1)) + 1  (same as sklearn's default).
    """
    N = len(docs)
    tokenized = [tokenize(d) for d in docs]

    # Document frequency
    df: Counter = Counter()
    for tokens in tokenized:
        df.update(set(tokens))

    idf = {term: math.log((N + 1) / (cnt + 1)) + 1.0 for term, cnt in df.items()}

    vectors: list[dict[str, float]] = []
    for tokens in tokenized:
        if not tokens:
            vectors.append({})
            continue
        tf = Counter(tokens)
        total = len(tokens)
        vec = {t: (tf[t] / total) * idf[t] for t in tf if t in idf}
        vectors.append(vec)

    return vectors, idf


def cosine_sim(v1: dict[str, float], v2: dict[str, float]) -> float:
    if not v1 or not v2:
        return 0.0
    dot = sum(v1.get(t, 0.0) * w for t, w in v2.items())
    n1 = math.sqrt(sum(w * w for w in v1.values()))
    n2 = math.sqrt(sum(w * w for w in v2.values()))
    if n1 == 0 or n2 == 0:
        return 0.0
    return dot / (n1 * n2)


# ── Entry text extraction ──────────────────────────────────────────────────────
def entry_text(entry: dict) -> str:
    ann = _ann(entry)
    cls_meta    = (ann.get("classification") or {}).get("metadata") or {}
    impact_sum  = ((ann.get("metadata") or {}).get("impact_summary") or {})
    tags        = " ".join((ann.get("metadata") or {}).get("tags") or [])
    parts = [
        entry.get("title", ""),
        entry.get("description", "") or entry.get("summary", ""),
        entry.get("content", "") or entry.get("body", ""),
        entry.get("_topic_name", ""),
        cls_meta.get("summary", ""),
        impact_sum.get("why_it_matters", ""),
        impact_sum.get("what_changed", ""),
        tags,
    ]
    return " ".join(str(p) for p in parts if p)


# ── Classification helpers ─────────────────────────────────────────────────────
RECALL_KEYWORDS    = {"recall", "fsn", "fsca", "field safety", "withdrawal", "correction"}
VIGILANCE_KEYWORDS = {"adverse event", "maude", "incident", "mdr report", "vigilance", "ae spike"}
STANDARD_KEYWORDS  = {"iec", "iso", "standard", "amendment", "harmonised", "harmonized"}
TRADE_KEYWORDS     = {"tariff", "hs code", "import duty", "customs", "trade"}

HORIZON_TYPES = {"guidance", "regulation", "directive", "standard", "consultation", "proposal"}

# Map annotation classification.update_type → our sourceType
UPDATE_TYPE_MAP = {
    "guidance":        "regulatory",
    "regulation":      "regulatory",
    "directive":       "regulatory",
    "consultation":    "regulatory",
    "recall":          "vigilance",
    "safety_notice":   "vigilance",
    "field_safety":    "vigilance",
    "fsca":            "vigilance",
    "adverse_event":   "vigilance",
    "standard":        "standards",
    "amendment":       "standards",
    "trade":           "trade",
    "tariff":          "trade",
}


def _ann(entry: dict) -> dict:
    """Safely return the annotation dict."""
    return entry.get("_annotation") or {}


def classify_source_type(entry: dict) -> str:
    # 1. Prefer annotation classification.update_type (AI-structured)
    update_type = (_ann(entry).get("classification") or {}).get("update_type", "").lower()
    if update_type in UPDATE_TYPE_MAP:
        return UPDATE_TYPE_MAP[update_type]

    # 2. Fall back to keyword matching on entry text (handles non-English too via title)
    text = entry_text(entry).lower()
    if any(k in text for k in RECALL_KEYWORDS):
        return "vigilance"
    if any(k in text for k in VIGILANCE_KEYWORDS):
        return "vigilance"
    if any(k in text for k in STANDARD_KEYWORDS):
        return "standards"
    if any(k in text for k in TRADE_KEYWORDS):
        return "trade"
    return "regulatory"


def classify_severity(entry: dict, score: float) -> str:
    ann = _ann(entry)
    scores = ann.get("scores") or {}

    # Use annotation impact + urgency scores (0-10 scale)
    impact_label  = (scores.get("impact")  or {}).get("label", "").lower()
    urgency_label = (scores.get("urgency") or {}).get("label", "").lower()
    impact_score  = (scores.get("impact")  or {}).get("score", 0)
    urgency_score = (scores.get("urgency") or {}).get("score", 0)

    if urgency_label == "high" or urgency_score >= 7:
        return "critical"
    if impact_label == "high" or impact_score >= 8:
        return "critical"
    if impact_label == "medium" or impact_score >= 5:
        return "high"

    # Fallback: title keywords
    text = entry_text(entry).lower()
    if any(k in text for k in {"recall", "class i recall", "class ii recall", "withdrawal", "urgent"}):
        return "critical"
    if score > 0.25:
        return "high"
    if score > 0.12:
        return "medium"
    return "low"


def infer_category(entry: dict) -> str:
    text = entry_text(entry).lower()
    if any(k in text for k in {"recall", "fsca", "fsn"}):
        return "Recall / Safety Notice"
    if any(k in text for k in {"guidance", "draft guidance"}):
        return "Guidance"
    if any(k in text for k in {"standard", "iec", "iso", "amendment"}):
        return "Standard Revision"
    if any(k in text for k in {"tariff", "hs code", "import", "trade"}):
        return "Trade & Tariff"
    if any(k in text for k in {"regulation", "directive", "mdr", "ivdr"}):
        return "Regulatory Change"
    if any(k in text for k in {"adverse event", "vigilance", "maude", "signal"}):
        return "Adverse Event Signal"
    return "Regulatory Update"


def _parse_entry_date(entry: dict) -> datetime | None:
    """Return the best available datetime for this entry, or None."""
    for field in ("published_date", "created_at", "updated_at"):
        date_str = entry.get(field)
        if not date_str:
            continue
        try:
            return datetime.fromisoformat(date_str.replace("Z", "+00:00"))
        except (ValueError, TypeError):
            pass
    return None


def time_ago(entry: dict) -> str:
    dt = _parse_entry_date(entry)
    if dt is None:
        return "recently"
    delta = datetime.now(timezone.utc) - dt
    h = int(delta.total_seconds() / 3600)
    if h < 1:
        return "just now"
    if h < 24:
        return f"{h}h ago"
    d = h // 24
    return f"{d}d ago"


def infer_deadline(entry: dict) -> str:
    ann           = _ann(entry)
    critical_dates = ((ann.get("metadata") or {}).get("critical_dates") or {})
    # Prefer structured dates from annotation
    for field in ("compliance_date", "effective_date", "comment_deadline", "early_adoption_date"):
        val = critical_dates.get(field, "")
        if val and val.strip():
            return val.strip()
    # Fall back to text pattern matching
    text = entry_text(entry).lower()
    for month in ["january", "february", "march", "april", "may", "june",
                  "july", "august", "september", "october", "november", "december"]:
        if month in text:
            m = re.search(rf"{month[:3]}\w*\s+\d{{4}}", text, re.I)
            if m:
                return m.group(0).title()
    for q in re.findall(r"q[1-4]\s*20\d\d", text, re.I):
        return q.upper()
    return "—"


def infer_horizon_type(entry: dict) -> tuple[str, str]:
    """Returns (type_label, tagClass)."""
    ann         = _ann(entry)
    update_type = ((ann.get("classification") or {}).get("update_type") or "").lower()
    TYPE_MAP = {
        "standard":     ("STANDARD",   "tag-blue"),
        "amendment":    ("STANDARD",   "tag-blue"),
        "guidance":     ("GUIDANCE",   "tag-green"),
        "consultation": ("GUIDANCE",   "tag-green"),
        "trade":        ("TRADE",      "tag-purple"),
        "tariff":       ("TRADE",      "tag-purple"),
        "recall":       ("ALERT",      "tag-red"),
        "safety_notice":("ALERT",      "tag-red"),
        "regulation":   ("REGULATION", "tag-amber"),
        "directive":    ("REGULATION", "tag-amber"),
    }
    if update_type in TYPE_MAP:
        return TYPE_MAP[update_type]
    # Keyword fallback
    text = entry_text(entry).lower()
    if any(k in text for k in {"iec", "iso", "standard", "amendment"}):
        return "STANDARD", "tag-blue"
    if any(k in text for k in {"tariff", "hs code", "import", "trade"}):
        return "TRADE", "tag-purple"
    if any(k in text for k in {"guidance", "draft guidance"}):
        return "GUIDANCE", "tag-green"
    if any(k in text for k in {"recall", "fsca", "fsn", "withdrawal"}):
        return "ALERT", "tag-red"
    return "REGULATION", "tag-amber"


def why_relevant(entry: dict, score: float) -> str:
    """Generate the 'why it matters for CardioWatch X1' sentence."""
    ann         = _ann(entry)
    impact_sum  = ((ann.get("metadata") or {}).get("impact_summary") or {})
    why         = impact_sum.get("why_it_matters", "")
    if why:
        return why
    cls_meta = (ann.get("classification") or {}).get("metadata") or {}
    summary = cls_meta.get("summary", "")
    if summary:
        return summary
    topic = entry.get("_topic_name", "regulatory body")
    juris = ", ".join(entry.get("_jurisdictions", ["INT"]))
    return (
        f"Published by {topic} ({juris}). "
        f"Cosine relevance {score:.2f} against cardiovascular device regulatory profile. "
        f"Review for impact on CardioWatch X1 CER / PMCF."
    )


def recommended_action(entry: dict) -> str:
    ann        = _ann(entry)
    actionables = ((ann.get("metadata") or {}).get("actionables") or {})
    # Pick the most specific actionable field available
    for key in ("process_change", "reporting_change", "policy_change", "tech_data_change", "training_change", "other_change"):
        val = actionables.get(key, "")
        if val and val.strip():
            return val.strip()
    src_type = classify_source_type(entry)
    if src_type == "vigilance":
        return "Review for shared failure modes with CardioWatch X1. Assess CER / PMCF impact."
    if src_type == "standards":
        return "Conduct gap analysis against current technical file. Flag for next CER update."
    if src_type == "trade":
        return "Alert commercial and regulatory affairs teams. Assess market-specific impact."
    return "Review for relevance to CardioWatch X1 regulatory strategy. Escalate if needed."


# ── Output formatters ──────────────────────────────────────────────────────────
_next_id = 100


def to_feed_item(entry: dict, score: float) -> dict:
    global _next_id
    _next_id += 1
    dt = _parse_entry_date(entry)
    return {
        "id":             _next_id,
        "severity":       classify_severity(entry, score),
        "time":           time_ago(entry),
        "published_date": dt.isoformat() if dt else None,
        "sourceType":     classify_source_type(entry),
        "title":          entry.get("title") or f"Update from {entry.get('_topic_name', 'regulator')}",
        "source":         entry.get("_topic_name") or entry.get("source", "Carver Feeds"),
        "why":            why_relevant(entry, score),
        "jurisdictions":  entry.get("_jurisdictions", ["INT"]),
        "action":         recommended_action(entry),
        "deadline":       infer_deadline(entry),
        "category":       infer_category(entry),
        "url":            entry.get("link") or entry.get("url") or "",
        "score":          round(score, 4),
        "_carver_id":     entry.get("id") or "",
    }


def to_horizon_item(entry: dict, score: float) -> dict:
    htype, tag_class = infer_horizon_type(entry)
    ann         = _ann(entry)
    impact_sum  = ((ann.get("metadata") or {}).get("impact_summary") or {})
    key_reqs    = ((ann.get("metadata") or {}).get("key_requirements") or [])
    actionables = ((ann.get("metadata") or {}).get("actionables") or {})
    cls_meta    = ((ann.get("classification") or {}).get("metadata") or {})
    title = entry.get("title") or cls_meta.get("title") or f"Update — {entry.get('_topic_name', '')}"

    # Build recommended steps from annotation actionables + fallback
    steps: list[str] = []
    for key in ("process_change", "reporting_change", "policy_change", "tech_data_change", "training_change"):
        val = actionables.get(key, "")
        if val and val.strip():
            steps.append(val.strip())
        if len(steps) >= 3:
            break
    if not steps:
        steps = [
            recommended_action(entry),
            f"Monitor {entry.get('_topic_name', 'regulatory body')} for follow-up publications.",
            "Update CER / technical file if scope confirmed.",
        ]

    return {
        "type":     htype,
        "tagClass": tag_class,
        "title":    title,
        "timeline": infer_deadline(entry),
        "impact":   (impact_sum.get("what_changed") or impact_sum.get("objective") or entry.get("description") or why_relevant(entry, score))[:300],
        "detail":   (impact_sum.get("why_it_matters") or cls_meta.get("summary") or why_relevant(entry, score))[:600],
        "steps":    steps,
        "jurisdictions": entry.get("_jurisdictions", ["INT"]),
        "url":           entry.get("link") or entry.get("url") or "",
        "score":         round(score, 4),
        "_carver_id":    entry.get("id") or "",
    }


# ── Is forward-looking? ────────────────────────────────────────────────────────
def is_horizon(entry: dict) -> bool:
    """True if the entry is forward-looking (proposal/guidance/upcoming standard)."""
    text = entry_text(entry).lower()
    return any(k in text for k in {
        "draft", "proposal", "proposed", "upcoming", "consultation",
        "effective", "transition", "deadline", "expected", "planned",
        "future", "will require", "will be required",
    })


# ── Main ───────────────────────────────────────────────────────────────────────
def main(threshold: float = 0.03, feed_limit: int = 12, horizon_limit: int = 8) -> None:
    raw_path = Path("public/data/carver_raw.json")
    if not raw_path.exists():
        print(f"ERROR: {raw_path} not found — run fetch_feeds.py first", file=sys.stderr)
        sys.exit(1)

    raw = json.loads(raw_path.read_text())
    entries: list[dict] = raw.get("entries", [])
    print(f"Loaded {len(entries)} raw entries from {raw_path}")

    if not entries:
        print("No entries to vectorize. Exiting.")
        sys.exit(0)

    # Build corpus: entry texts + reference query (appended last)
    texts = [entry_text(e) for e in entries]
    texts.append(CARDIO_QUERY)

    print(f"Building TF-IDF matrix over {len(texts)} documents …")
    vectors, _idf = build_tfidf(texts)

    query_vec    = vectors[-1]        # reference query vector
    entry_vecs   = vectors[:-1]       # one per entry

    # Score entries
    scored: list[tuple[dict, float]] = [
        (entries[i], cosine_sim(entry_vecs[i], query_vec))
        for i in range(len(entries))
    ]
    scored.sort(key=lambda x: x[1], reverse=True)

    # Filter by threshold
    relevant = [(e, s) for e, s in scored if s >= threshold]
    print(f"Entries above threshold {threshold}: {len(relevant)} / {len(entries)}")

    if not relevant:
        print("No relevant entries found — try lowering --threshold", file=sys.stderr)
        sys.exit(0)

    # Partition: horizon-type items go to Phase3, rest go to Phase1 feed
    horizon_pool = [(e, s) for e, s in relevant if is_horizon(e)]
    feed_pool    = [(e, s) for e, s in relevant if not is_horizon(e)]

    # If horizon pool is thin, pull extras from the feed pool tail
    if len(horizon_pool) < 3:
        horizon_pool += feed_pool[feed_limit:]
        feed_pool    = feed_pool[:feed_limit]

    feed_items    = [to_feed_item(e, s)    for e, s in feed_pool[:feed_limit]]
    horizon_items = [to_horizon_item(e, s) for e, s in horizon_pool[:horizon_limit]]

    # Cap future-dated annotations to today (annotation metadata can have bad effective_dates)
    now_iso = datetime.now(timezone.utc).isoformat()
    for item in feed_items:
        if item.get("published_date") and item["published_date"] > now_iso:
            item["published_date"] = now_iso
    # Feed is already in cosine score order (highest first) from scored.sort above

    print(f"Feed items:    {len(feed_items)}")
    print(f"Horizon items: {len(horizon_items)}")

    # Write outputs
    out_dir = Path("public/data")
    out_dir.mkdir(parents=True, exist_ok=True)

    feed_path    = out_dir / "regulatory_feed.json"
    horizon_path = out_dir / "regulatory_horizon.json"

    feed_path.write_text(json.dumps({
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source":       "Carver Feeds (vectorized)",
        "window_days":  raw.get("window_days", 30),
        "items":        feed_items,
    }, indent=2, default=str))

    horizon_path.write_text(json.dumps({
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source":       "Carver Feeds (vectorized)",
        "window_days":  raw.get("window_days", 30),
        "items":        horizon_items,
    }, indent=2, default=str))

    print(f"Saved → {feed_path}")
    print(f"Saved → {horizon_path}")

    # Print top 5 for sanity check
    print("\nTop 5 by relevance score:")
    for entry, score in scored[:5]:
        title = entry.get("title", "(no title)")[:70]
        topic = entry.get("_topic_name", "?")[:30]
        print(f"  {score:.4f}  [{topic}]  {title}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Vectorize Carver entries for cardiovascular device relevance")
    parser.add_argument("--threshold",     type=float, default=0.03,  help="Min cosine score to include (default: 0.03)")
    parser.add_argument("--feed-limit",    type=int,   default=12,    help="Max items for intelligence feed (default: 12)")
    parser.add_argument("--horizon-limit", type=int,   default=8,     help="Max items for regulatory horizon (default: 8)")
    args = parser.parse_args()
    main(threshold=args.threshold, feed_limit=args.feed_limit, horizon_limit=args.horizon_limit)
