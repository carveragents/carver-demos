#!/usr/bin/env python3
"""
Preprocess PubMed literature and extract device clearance signals for Phase 5
(Evolution of State of the Art).

Outputs:
    public/data/sota_literature.json    — filtered, ranked PubMed articles
    public/data/sota_clearances.json    — new device clearance signals from Carver

Usage:
    python scripts/preprocess_literature.py
"""

import json
import math
import re
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

# ── Reference query — what matters for CardioWatch X1 state of the art ─────────
SOTA_QUERY = """
cardiac monitoring wearable continuous ambulatory ECG electrocardiogram
atrial fibrillation AF detection accuracy sensitivity specificity
rhythm arrhythmia PPG photoplethysmography pulse oximetry
implantable cardioverter defibrillator ICD pacemaker CRT
cardiac resynchronization therapy heart failure ejection fraction
diagnostic performance benchmark clinical outcome
systematic review meta-analysis randomized controlled trial evidence
wearable device algorithm machine learning deep learning performance
"""

# ── TF-IDF helpers (same pure-Python implementation as vectorize_feeds.py) ────

STOP_WORDS = {
    "a", "an", "the", "and", "or", "but", "in", "on", "at", "to", "for",
    "of", "with", "by", "from", "is", "are", "was", "were", "be", "been",
    "have", "has", "had", "do", "does", "did", "will", "would", "could",
    "should", "may", "might", "shall", "can", "not", "this", "that", "these",
    "those", "it", "its", "as", "if", "so", "we", "our", "their", "they",
    "he", "she", "his", "her", "which", "what", "who", "when", "where",
    "how", "all", "also", "more", "new", "other", "any", "each", "no",
    "than", "then", "into", "out", "up", "about", "after", "before",
    "between", "through", "during", "under", "over", "per", "vs",
}


def tokenize(text: str) -> list[str]:
    tokens = re.findall(r"\b[a-z0-9][a-z0-9]{1,}\b", text.lower())
    return [t for t in tokens if t not in STOP_WORDS]


def build_tfidf(docs: list[str]) -> tuple[list[dict], dict]:
    N = len(docs)
    tokenized = [tokenize(d) for d in docs]
    df: Counter = Counter()
    for tokens in tokenized:
        df.update(set(tokens))
    idf = {t: math.log((N + 1) / (cnt + 1)) + 1.0 for t, cnt in df.items()}
    vectors = []
    for tokens in tokenized:
        if not tokens:
            vectors.append({})
            continue
        tf = Counter(tokens)
        total = len(tokens)
        vec = {t: (tf[t] / total) * idf[t] for t in tf if t in idf}
        vectors.append(vec)
    return vectors, idf


def cosine_sim(v1: dict, v2: dict) -> float:
    if not v1 or not v2:
        return 0.0
    dot = sum(v1.get(t, 0.0) * w for t, w in v2.items())
    n1 = math.sqrt(sum(w * w for w in v1.values()))
    n2 = math.sqrt(sum(w * w for w in v2.values()))
    return dot / (n1 * n2) if n1 and n2 else 0.0


# ── Date normalisation ─────────────────────────────────────────────────────────

MONTH_MAP = {
    "jan": "01", "feb": "02", "mar": "03", "apr": "04",
    "may": "05", "jun": "06", "jul": "07", "aug": "08",
    "sep": "09", "oct": "10", "nov": "11", "dec": "12",
}


def normalise_pubmed_date(raw: str) -> str:
    """Return sortable YYYY-MM-DD from messy PubMed date strings."""
    if not raw:
        return "0000-00-00"
    s = raw.strip()
    # "2026 Mar 17"
    m = re.match(r"(\d{4})\s+([A-Za-z]+)\s+(\d{1,2})", s)
    if m:
        mo = MONTH_MAP.get(m.group(2).lower()[:3], "01")
        return f"{m.group(1)}-{mo}-{int(m.group(3)):02d}"
    # "2026 Mar"
    m = re.match(r"(\d{4})\s+([A-Za-z]+)", s)
    if m:
        mo = MONTH_MAP.get(m.group(2).lower()[:3], "01")
        return f"{m.group(1)}-{mo}-01"
    # "2026"
    m = re.match(r"(\d{4})", s)
    if m:
        return f"{m.group(1)}-01-01"
    return "0000-00-00"


def friendly_date(raw: str) -> str:
    """Return a human-readable date like 'Mar 2026'."""
    iso = normalise_pubmed_date(raw)
    try:
        dt = datetime.strptime(iso, "%Y-%m-%d")
        return dt.strftime("%b %Y") if iso > "0000" else raw
    except ValueError:
        return raw


# ── Article type classification ────────────────────────────────────────────────

def classify_article(article: dict) -> tuple[str, str, str]:
    """Returns (type_label, tag_class, priority) based on article_type_flags."""
    flags = set(article.get("article_type_flags") or [])
    if "systematic_review" in flags and "meta_analysis" in flags:
        return "SYSTEMATIC REVIEW + META-ANALYSIS", "tag-purple", "1"
    if "systematic_review" in flags:
        return "SYSTEMATIC REVIEW", "tag-purple", "2"
    if "meta_analysis" in flags:
        return "META-ANALYSIS", "tag-blue", "3"
    if "rct" in flags:
        return "RCT", "tag-green", "4"
    if "clinical_trial" in flags:
        return "CLINICAL TRIAL", "tag-teal", "5"
    return "REVIEW", "tag-gray", "6"


def article_text(article: dict) -> str:
    mesh = " ".join(article.get("mesh_terms") or [])
    return " ".join(filter(None, [
        article.get("title", ""),
        article.get("abstract", ""),
        mesh,
        article.get("journal", ""),
    ]))


# ── Clearance signal detection ─────────────────────────────────────────────────

CLEARANCE_KEYWORDS = {
    "approved for marketing", "510(k)", "de novo", "510k clearance",
    "ce marked", "ce certificate", "conformity assessment completed",
    "breakthrough device", "first-in-class", "novel device",
    "innovative product", "new device approved", "market authorisation",
    "premarket approval", "pma approved", "artg", "tga approval",
    "nmpa approval", "cdsco approval", "mhra registration",
}

CLEARANCE_REGULATOR_MAP = {
    "fda": "US 🇺🇸", "cdrh": "US 🇺🇸", "510k": "US 🇺🇸",
    "mhra": "UK 🇬🇧",
    "tga": "AU 🇦🇺", "artg": "AU 🇦🇺",
    "nmpa": "CN 🇨🇳",
    "cdsco": "IN 🇮🇳",
    "swissmedic": "CH 🇨🇭",
}


def is_clearance_signal(entry: dict) -> str | None:
    """Return regulator label if entry looks like a new device clearance, else None."""
    text = (
        (entry.get("title") or "") + " " +
        (entry.get("description") or "") + " " +
        (entry.get("_topic_name") or "")
    ).lower()
    if not any(kw in text for kw in CLEARANCE_KEYWORDS):
        return None
    for kw, label in CLEARANCE_REGULATOR_MAP.items():
        if kw in text:
            return label
    return "INT 🌐"


def normalise_clearance_date(entry: dict) -> str:
    for field in ("published_date", "created_at"):
        raw = entry.get(field, "")
        if not raw:
            continue
        try:
            dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))
            return dt.strftime("%b %d, %Y")
        except (ValueError, TypeError):
            pass
    return "—"


def clearance_sort_key(entry: dict) -> str:
    for field in ("published_date", "created_at"):
        raw = entry.get(field, "")
        if raw:
            return raw
    return ""


# ── Main ───────────────────────────────────────────────────────────────────────

def main() -> None:
    # ── 1. Load PubMed articles ────────────────────────────────────────────────
    data_dir = Path("medical-device-data/INT")
    article_files = sorted(data_dir.glob("*/articles.json"), reverse=True)
    if not article_files:
        print("ERROR: No articles.json found under medical-device-data/INT/", file=sys.stderr)
        sys.exit(1)

    article_path = article_files[0]
    print(f"Loading articles from {article_path} …")
    articles = json.loads(article_path.read_text())
    print(f"  {len(articles)} articles loaded")

    # ── 2. Score articles by relevance ─────────────────────────────────────────
    texts = [article_text(a) for a in articles]
    texts.append(SOTA_QUERY)
    print(f"Building TF-IDF over {len(texts)} documents …")
    vectors, _ = build_tfidf(texts)
    query_vec = vectors[-1]

    scored = [
        (articles[i], cosine_sim(vectors[i], query_vec))
        for i in range(len(articles))
    ]
    scored.sort(key=lambda x: x[1], reverse=True)

    THRESHOLD = 0.03
    MAX_ARTICLES = 150
    relevant = [(a, s) for a, s in scored if s >= THRESHOLD][:MAX_ARTICLES]
    print(f"  {len(relevant)} articles above threshold {THRESHOLD}")

    # ── 3. Build output records ────────────────────────────────────────────────
    output_articles = []
    for article, score in relevant:
        type_label, tag_class, _ = classify_article(article)
        pub_date_raw = article.get("publication_date") or ""
        pub_date_sort = normalise_pubmed_date(pub_date_raw)

        # Shorten author list (authors are "Last, First" strings)
        authors_raw = article.get("authors") or []
        if len(authors_raw) <= 3:
            author_str = ", ".join(str(a) for a in authors_raw)
        else:
            author_str = f"{authors_raw[0]} et al."

        output_articles.append({
            "pmid":             article.get("pmid", ""),
            "doi":              article.get("doi", ""),
            "title":            article.get("title", ""),
            "abstract":         (article.get("abstract") or "")[:1200],
            "journal":          article.get("journal", ""),
            "publication_date": pub_date_raw,
            "pub_date_sort":    pub_date_sort,
            "pub_date_display": friendly_date(pub_date_raw),
            "authors":          author_str,
            "mesh_terms":       (article.get("mesh_terms") or [])[:12],
            "type_label":       type_label,
            "tag_class":        tag_class,
            "article_type_flags": article.get("article_type_flags") or [],
            "pubmed_url":       article.get("pubmed_url", ""),
            "score":            round(score, 4),
        })

    # Sort final output by relevance score (highest first)
    output_articles.sort(key=lambda x: x["score"], reverse=True)

    # Stats
    flags_all = [f for a, _ in relevant for f in (a.get("article_type_flags") or [])]
    flags_counter = Counter(flags_all)

    out_lit = Path("public/data/sota_literature.json")
    out_lit.parent.mkdir(parents=True, exist_ok=True)
    out_lit.write_text(json.dumps({
        "generated_at":   datetime.now(timezone.utc).isoformat(),
        "source":         "PubMed",
        "search_query":   json.loads((article_path.parent / "metadata.json").read_text()).get("search_query", ""),
        "total_indexed":  len(articles),
        "total_relevant": len(relevant),
        "stats": {
            "systematic_review": flags_counter.get("systematic_review", 0),
            "meta_analysis":     flags_counter.get("meta_analysis", 0),
            "rct":               flags_counter.get("rct", 0),
            "clinical_trial":    flags_counter.get("clinical_trial", 0),
        },
        "articles": output_articles,
    }, indent=2, default=str))
    print(f"Saved → {out_lit}  ({len(output_articles)} articles)")

    # ── 4. Load PMA device clearances ─────────────────────────────────────────
    pma_dir = Path("medical-device-data/pma")
    pma_files = sorted(pma_dir.glob("*/clearances.json"), reverse=True)
    clearances = []

    if not pma_files:
        print("No clearances.json found under medical-device-data/pma/ — skipping")
    else:
        pma_path = pma_files[0]
        print(f"Loading PMA clearances from {pma_path} …")
        pma_records = json.loads(pma_path.read_text())
        print(f"  {len(pma_records)} PMA records loaded")

        # Clinically significant change categories (directly relevant to SotA)
        CLINICAL_REASONS = {
            "Change Design/Components/Specifications/Material",
            "Labeling Change - Indications/instructions/shelf life/tradename",
            "Labeling Change - PAS",
            "Special (Immediate Track)",
            "Postapproval Study Protocol",
            "Postapproval Study Protocol - OSB",
        }

        for rec in pma_records:
            date_raw = rec.get("decision_date") or rec.get("date_received") or ""
            # Format date for display
            try:
                dt = datetime.strptime(date_raw, "%Y-%m-%d")
                date_display = dt.strftime("%b %d, %Y")
            except (ValueError, TypeError):
                date_display = date_raw or "—"

            applicant    = rec.get("applicant") or ""
            generic_name = rec.get("generic_name") or ""
            supp_reason  = rec.get("supplement_reason") or ""
            supp_type    = rec.get("supplement_type") or ""
            is_clinical  = supp_reason in CLINICAL_REASONS or not supp_reason

            clearances.append({
                "title":           f"{applicant} — {generic_name}" if generic_name else applicant,
                "applicant":       applicant,
                "generic_name":    generic_name,
                "clearance_number": rec.get("source_record_id") or rec.get("clearance_number") or "",
                "product_code":    rec.get("product_code") or "",
                "regulator":       "US 🇺🇸",
                "supplement_type": supp_type,
                "supplement_reason": supp_reason,
                "is_clinical":     is_clinical,
                "date":            date_display,
                "date_sort":       date_raw,
                "url":             rec.get("clearance_url") or "",
                "description":     (rec.get("summary") or "")[:400],
                "source":          "FDA PMA",
            })

        clearances.sort(key=lambda x: x["date_sort"], reverse=True)
        clinical_count = sum(1 for c in clearances if c["is_clinical"])
        print(f"  {len(clearances)} total · {clinical_count} clinically significant")

    out_cl = Path("public/data/sota_clearances.json")
    out_cl.write_text(json.dumps({
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source":        "FDA_PMA",
        "total":         len(clearances),
        "clearances":    clearances,
    }, indent=2, default=str))
    print(f"Saved → {out_cl}  ({len(clearances)} clearances)")


if __name__ == "__main__":
    main()