"""rank_wow_candidates.py

Stream-read data/_scratch/annotations.jsonl, score each record against
wow-moment criteria, and output:
  - data/wow-candidates.json   top-50 records with scores
  - data/a8-wow-summary.md     markdown report with top-15 table
  - stdout                     top-15 table
"""

from __future__ import annotations

import json
import re
from datetime import date
from pathlib import Path

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
BUILD_DATE = date(2026, 5, 19)
SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent
INPUT_FILE = REPO_ROOT / "data" / "_scratch" / "annotations.jsonl"
OUTPUT_JSON = REPO_ROOT / "data" / "wow-candidates.json"
OUTPUT_MD = REPO_ROOT / "data" / "a8-wow-summary.md"

TOP_N = 50
SUMMARY_N = 15

PM_TERMS = [
    "kalshi",
    "polymarket",
    "forecastex",
    "predictit",
    "electronx",
    "railbird",
    "fanduel",
    "draftkings",
    "event contract",
    "prediction market",
    "sportsbook",
    "sweepstakes casino",
]

# update_type -> score
UPDATE_TYPE_SCORES: dict[str, float] = {
    "enforcement": 10,
    "final rule": 10,
    "advisory": 8,
    "proposed rule": 8,
    "comment request": 6,
    "guidance": 6,
    "bulletin": 4,
    "event announcement": 4,
    "press release": 2,
    "speech": 2,
    "trend report": 2,
    "newsletter": 2,
    "insights": 2,
    "website error": 0,
    "other": 0,
    "": 0,
}

# Normalise any variant strings not in the table to 0


def _update_type_score(utype: str) -> float:
    utype = utype.strip().lower()
    return UPDATE_TYPE_SCORES.get(utype, 0)


def _recency_score(pub_date_str: str) -> float:
    if not pub_date_str:
        return 0
    try:
        pd = date.fromisoformat(pub_date_str[:10])
    except ValueError:
        return 0
    days_old = (BUILD_DATE - pd).days
    if days_old < 0:
        # future-dated; treat as very recent
        return 10
    if days_old <= 7:
        return 10
    if days_old <= 30:
        return 8
    if days_old <= 60:
        return 5
    if days_old <= 90:
        return 2
    return 0


def _jurisdiction_score(jcode: str) -> float:
    if not jcode:
        return 0
    # US state codes are "US-XX"
    if re.match(r"^US-[A-Z]{2}$", jcode):
        return 10
    if jcode.startswith("US"):
        return 8
    # International (non-US, non-empty)
    return 4


def _recognition_score(title: str, entities: list[str]) -> float:
    haystack = (title + " " + " ".join(entities)).lower()
    for term in PM_TERMS:
        if term in haystack:
            return 10
    return 0


def _is_excluded(record: dict) -> bool:
    utype = record.get("update_type", "").strip().lower()
    if utype == "website error":
        return True
    link = record.get("link", "").strip()
    base_url = record.get("base_url", "").strip()
    if not link and not base_url:
        return True
    return False


def _score_record(record: dict) -> dict | None:
    if _is_excluded(record):
        return None

    scores_block = record.get("scores", {})
    urgency_score = float(scores_block.get("urgency", {}).get("score", 0))
    impact_score = float(scores_block.get("impact", {}).get("score", 0))
    relevance_score = float(scores_block.get("relevance", {}).get("score", 0))

    pub_date = record.get("pub_date", "")
    utype = record.get("update_type", "")
    jcode = record.get("topic_jurisdiction_code", "")
    title = record.get("title", "")
    entities = record.get("entities", [])

    rec_score = _recency_score(pub_date)
    ut_score = _update_type_score(utype)
    juris_score = _jurisdiction_score(jcode)
    recog_score = _recognition_score(title, entities)

    total = (
        0.30 * urgency_score
        + 0.20 * impact_score
        + 0.15 * rec_score
        + 0.15 * ut_score
        + 0.10 * juris_score
        + 0.10 * recog_score
    )

    # Impacted business jurisdiction
    ib = record.get("impacted_business", {})
    if isinstance(ib, dict):
        ib_jurisdictions = ib.get("jurisdiction", [])
    else:
        ib_jurisdictions = []

    # Impact summary "what_changed" truncated
    impact_summary = record.get("impact_summary", {})
    if isinstance(impact_summary, dict):
        what_changed = (impact_summary.get("what_changed") or "")[:300]
    else:
        what_changed = ""

    return {
        "feed_entry_id": record.get("feed_entry_id", ""),
        "topic_id": record.get("topic_id", ""),
        "topic_name": record.get("topic_name", ""),
        "title": title,
        "link": record.get("link", ""),
        "base_url": record.get("base_url", ""),
        "regulator_name": record.get("regulator_name", ""),
        "pub_date": pub_date,
        "update_type": utype,
        "topic_jurisdiction_code": jcode,
        "impacted_business_jurisdiction": ib_jurisdictions,
        "urgency_score": urgency_score,
        "impact_score": impact_score,
        "relevance_score": relevance_score,
        "total_score": round(total, 4),
        "score_components": {
            "urgency": urgency_score,
            "impact": impact_score,
            "recency": rec_score,
            "update_type": ut_score,
            "jurisdiction": juris_score,
            "recognition": recog_score,
        },
        "impact_summary_what_changed": what_changed,
        "entities_top5": entities[:5],
    }


def main() -> None:
    print(f"Reading {INPUT_FILE} …")
    heap: list[dict] = []
    total_read = 0
    total_excluded = 0

    with INPUT_FILE.open("r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            total_read += 1
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                total_excluded += 1
                continue

            scored = _score_record(record)
            if scored is None:
                total_excluded += 1
                continue

            heap.append(scored)

    heap.sort(key=lambda r: r["total_score"], reverse=True)
    top50 = heap[:TOP_N]

    print(f"Records read: {total_read:,}")
    print(f"Records excluded (website-error / no-link): {total_excluded:,}")
    print(f"Remaining scored: {len(heap):,}")
    print(f"Top {TOP_N} selected.\n")

    # Write JSON output
    OUTPUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    with OUTPUT_JSON.open("w", encoding="utf-8") as fh:
        json.dump(top50, fh, indent=2, ensure_ascii=False)
    print(f"Wrote {OUTPUT_JSON}")

    # Build table
    table_lines = _build_table(top50[:SUMMARY_N])

    # Print table
    print()
    for line in table_lines:
        print(line)

    # Write markdown report
    md_content = _build_markdown(top50[:SUMMARY_N], table_lines, total_read, total_excluded, len(heap))
    with OUTPUT_MD.open("w", encoding="utf-8") as fh:
        fh.write(md_content)
    print(f"\nWrote {OUTPUT_MD}")


def _build_table(candidates: list[dict]) -> list[str]:
    header = (
        f"{'#':>2}  {'Score':>5}  {'Pub Date':10}  {'U':>4}  {'I':>4}  "
        f"{'Rec':>4}  {'Type':<18}  {'Regulator':<38}  Title"
    )
    sep = "-" * 140
    rows = [header, sep]
    for idx, c in enumerate(candidates, 1):
        sc = c["score_components"]
        rec_flag = "*" if sc["recognition"] > 0 else " "
        utype_short = c["update_type"][:17]
        reg_short = c["regulator_name"][:37]
        title_short = c["title"][:55]
        row = (
            f"{idx:>2}  {c['total_score']:>5.2f}  {c['pub_date']:10}  "
            f"{sc['urgency']:>4.1f}  {sc['impact']:>4.1f}  "
            f"{sc['recency']:>4.1f}  {utype_short:<18}  {reg_short:<38}  "
            f"{rec_flag}{title_short}"
        )
        rows.append(row)
    return rows


def _build_markdown(
    candidates: list[dict],
    table_lines: list[str],
    total_read: int,
    total_excluded: int,
    total_scored: int,
) -> str:
    # Assess concerns
    from collections import Counter

    regulator_counts = Counter(c["regulator_name"] for c in candidates)
    top_reg, top_reg_n = regulator_counts.most_common(1)[0]
    dominated = top_reg_n >= (SUMMARY_N * 0.5)

    recency_ok = sum(1 for c in candidates if c["score_components"]["recency"] >= 5)
    recognition_fired = sum(1 for c in candidates if c["score_components"]["recognition"] > 0)

    concerns: list[str] = []
    if dominated:
        concerns.append(
            f"**Regulator dominance**: top {SUMMARY_N} is heavily skewed — "
            f"{top_reg!r} appears {top_reg_n}/{SUMMARY_N} times. "
            "Curation should pick across regulators for inbox variety."
        )
    else:
        concerns.append(
            f"Regulator spread looks healthy; top regulator ({top_reg!r}) has {top_reg_n}/{SUMMARY_N} entries."
        )

    if recency_ok < (SUMMARY_N * 0.5):
        concerns.append(
            f"**Recency thin**: only {recency_ok}/{SUMMARY_N} top entries are ≤60 days old "
            "(recency_score ≥ 5). The 90-day window has sparse very-recent material."
        )
    else:
        concerns.append(
            f"Recency looks good: {recency_ok}/{SUMMARY_N} entries are within 60 days."
        )

    if recognition_fired == 0:
        concerns.append(
            "**Recognition score did not fire** on any top-15 entry — none mention Kalshi, "
            "Polymarket, or other PM-platform names directly in title/entities. "
            "The full top-50 JSON contains PM-named records; they are scored lower due to "
            "urgency/impact constraints. Recommend manual review of top-50."
        )
    else:
        concerns.append(
            f"Recognition score fired on {recognition_fired}/{SUMMARY_N} top entries — "
            "PM platform names appear in title or entities."
        )

    table_block = "\n".join(f"    {l}" for l in table_lines)

    md = f"""# A8 — Wow-Moment Candidate Shortlist

**Build date**: {BUILD_DATE}
**Source**: `data/_scratch/annotations.jsonl`
**Records read**: {total_read:,}
**Excluded** (website-error / no-link): {total_excluded:,}
**Scored**: {total_scored:,}
**Output**: `data/wow-candidates.json` (top {TOP_N})

## Scoring Formula

```
score = 0.30 * urgency + 0.20 * impact + 0.15 * recency + 0.15 * update_type + 0.10 * jurisdiction + 0.10 * recognition
```

`*` prefix in Title column = recognition score fired (PM platform name in title/entities).

## Top-{SUMMARY_N} Table

```
{chr(10).join(table_lines)}
```

## Observations & Concerns

{chr(10).join(f'- {c}' for c in concerns)}

## Top Picks — Curation Notes

"""
    for idx, c in enumerate(candidates[:5], 1):
        md += f"### {idx}. {c['title']}\n"
        md += f"- **Regulator**: {c['regulator_name']}\n"
        md += f"- **Date**: {c['pub_date']} | **Type**: {c['update_type']}\n"
        md += f"- **Score**: {c['total_score']:.2f} (U={c['urgency_score']}, I={c['impact_score']}, rec={c['score_components']['recency']})\n"
        md += f"- **Link**: {c['link'] or c['base_url']}\n"
        if c["impact_summary_what_changed"]:
            md += f"- **What changed**: {c['impact_summary_what_changed']}\n"
        if c["entities_top5"]:
            md += f"- **Entities**: {', '.join(c['entities_top5'])}\n"
        md += "\n"

    return md


if __name__ == "__main__":
    main()
