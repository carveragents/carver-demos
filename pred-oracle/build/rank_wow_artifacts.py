"""rank_wow_artifacts.py

Stream-read data/_scratch/artifacts.jsonl, score each record against
wow-moment criteria, and output:
  - data/wow-candidates.json        top-50 records with scores (OVERWRITES prior)
  - data/a8-prime-wow-summary.md    markdown report with top-15 table
  - stdout                          top-15 table

Schema note: artifacts corpus uses `classification_base_url` (not `base_url`),
has new fields (artifact_id, current_published_date, feed_id, etc.), and `link`
is populated 100% — no base_url fallback needed.
"""

from __future__ import annotations

import json
import re
from collections import Counter
from datetime import date
from pathlib import Path

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
BUILD_DATE = date(2026, 5, 19)
SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent
INPUT_FILE = REPO_ROOT / "data" / "_scratch" / "artifacts.jsonl"
OUTPUT_JSON = REPO_ROOT / "data" / "wow-candidates.json"
OUTPUT_MD = REPO_ROOT / "data" / "a8-prime-wow-summary.md"

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
    "binary option",
]

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


def _update_type_score(utype: str) -> float:
    return UPDATE_TYPE_SCORES.get(utype.strip().lower(), 0)


def _recency_score(pub_date_str: str) -> float:
    if not pub_date_str:
        return 0
    try:
        pd = date.fromisoformat(pub_date_str[:10])
    except ValueError:
        return 0
    days_old = (BUILD_DATE - pd).days
    if days_old < 0:
        return 10  # future-dated; treat as very recent
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
    if re.match(r"^US-[A-Z]{2}$", jcode):
        return 10
    if jcode.startswith("US"):
        return 8
    return 4  # international, non-empty


def _recognition_score(title: str, entities: list[str], regulator_name: str) -> float:
    haystack = (title + " " + " ".join(entities) + " " + regulator_name).lower()
    for term in PM_TERMS:
        if term in haystack:
            return 10
    return 0


def _is_excluded(record: dict) -> bool:
    utype = record.get("update_type", "").strip().lower()
    if utype == "website error":
        return True
    scores_block = record.get("scores", {})
    relevance_score = float(scores_block.get("relevance", {}).get("score", 0))
    if relevance_score < 5:
        return True
    title = record.get("title", "").strip()
    if not title:
        return True
    link = record.get("link", "").strip()
    if not link:
        return True
    if not record.get("pub_date_valid", False):
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
    regulator_name = record.get("regulator_name", "")
    jurisdiction_tier = record.get("jurisdiction_tier", {})
    jurisdiction_tier_label = jurisdiction_tier.get("label", "") if isinstance(jurisdiction_tier, dict) else ""

    rec_score = _recency_score(pub_date)
    ut_score = _update_type_score(utype)
    juris_score = _jurisdiction_score(jcode)
    recog_score = _recognition_score(title, entities, regulator_name)

    total = (
        0.30 * urgency_score
        + 0.20 * impact_score
        + 0.15 * rec_score
        + 0.15 * ut_score
        + 0.10 * juris_score
        + 0.10 * recog_score
    )

    ib = record.get("impacted_business", {})
    ib_jurisdictions = ib.get("jurisdiction", []) if isinstance(ib, dict) else []

    impact_summary = record.get("impact_summary", {})
    what_changed = (impact_summary.get("what_changed") or "")[:300] if isinstance(impact_summary, dict) else ""

    return {
        "artifact_id": record.get("artifact_id", ""),
        "feed_entry_id": record.get("feed_entry_id", ""),
        "topic_id": record.get("topic_id", ""),
        "topic_name": record.get("topic_name", ""),
        "title": title,
        "link": record.get("link", ""),
        "regulator_name": regulator_name,
        "pub_date": pub_date,
        "update_type": utype,
        "topic_jurisdiction_code": jcode,
        "jurisdiction_tier_label": jurisdiction_tier_label,
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

    print(f"Records read      : {total_read:,}")
    print(f"Records excluded  : {total_excluded:,}")
    print(f"Remaining scored  : {len(heap):,}")
    print(f"Top {TOP_N} selected.\n")

    OUTPUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    with OUTPUT_JSON.open("w", encoding="utf-8") as fh:
        json.dump(top50, fh, indent=2, ensure_ascii=False)
    print(f"Wrote {OUTPUT_JSON}")

    table_lines = _build_table(top50[:SUMMARY_N])
    print()
    for line in table_lines:
        print(line)

    md_content = _build_markdown(top50[:SUMMARY_N], table_lines, total_read, total_excluded, len(heap), top50)
    with OUTPUT_MD.open("w", encoding="utf-8") as fh:
        fh.write(md_content)
    print(f"\nWrote {OUTPUT_MD}")


def _build_table(candidates: list[dict]) -> list[str]:
    header = (
        f"{'#':>2}  {'Score':>5}  {'Pub Date':10}  {'U':>4}  {'I':>4}  "
        f"{'Rec':>4}  {'Type':<18}  {'Regulator':<38}  Title"
    )
    sep = "-" * 145
    rows = [header, sep]
    for idx, c in enumerate(candidates, 1):
        sc = c["score_components"]
        rec_flag = "*" if sc["recognition"] > 0 else " "
        utype_short = c["update_type"][:17]
        reg_short = c["regulator_name"][:37]
        title_short = c["title"][:58]
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
    top50: list[dict],
) -> str:
    # Jurisdiction breakdown of top-50
    us_fed = sum(1 for c in top50 if c["topic_jurisdiction_code"] == "US" or c["jurisdiction_tier_label"] == "us_federal")
    us_state = sum(1 for c in top50 if re.match(r"^US-[A-Z]{2}$", c["topic_jurisdiction_code"]))
    intl = sum(1 for c in top50 if c["jurisdiction_tier_label"] == "international" and not c["topic_jurisdiction_code"].startswith("US"))
    recognition_top50 = sum(1 for c in top50 if c["score_components"]["recognition"] > 0)

    regulator_counts = Counter(c["regulator_name"] for c in candidates)
    top_reg, top_reg_n = regulator_counts.most_common(1)[0]
    dominated = top_reg_n >= (SUMMARY_N * 0.5)
    recency_ok = sum(1 for c in candidates if c["score_components"]["recency"] >= 5)
    recognition_fired = sum(1 for c in candidates if c["score_components"]["recognition"] > 0)

    concerns: list[str] = []
    if dominated:
        concerns.append(
            f"**Regulator dominance**: top {SUMMARY_N} heavily skewed — "
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
            "Polymarket, or other PM-platform names directly in title/entities/regulator_name. "
            "Review full top-50 JSON for PM-named records scored lower due to urgency/impact constraints."
        )
    else:
        concerns.append(
            f"Recognition score fired on {recognition_fired}/{SUMMARY_N} top-15 entries — "
            "PM platform names appear in title, entities, or regulator_name."
        )

    md = f"""# A8’ — Wow-Moment Candidate Shortlist (Artifacts Corpus)

**Build date**: {BUILD_DATE}
**Source**: `data/_scratch/artifacts.jsonl`
**Records read**: {total_read:,}
**Excluded** (website-error / relevance<5 / no-title / no-link / invalid-pub-date): {total_excluded:,}
**Scored**: {total_scored:,}
**Output**: `data/wow-candidates.json` (top {TOP_N})

## Top-50 Jurisdiction Breakdown

| Bucket | Count |
|---|---|
| US federal (`topic_jurisdiction_code == "US"` or `jurisdiction_tier_label == "us_federal"`) | {us_fed} |
| US state (`US-XX`) | {us_state} |
| International | {intl} |
| Recognition bonus fired | {recognition_top50} |

## Scoring Formula

```
score = 0.30 * urgency + 0.20 * impact + 0.15 * recency + 0.15 * update_type + 0.10 * jurisdiction + 0.10 * recognition
```

`*` prefix in Title column = recognition score fired (PM platform name in title/entities/regulator_name).

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
        md += (
            f"- **Score**: {c['total_score']:.2f} "
            f"(U={c['urgency_score']}, I={c['impact_score']}, rec={c['score_components']['recency']})\n"
        )
        md += f"- **Link**: {c['link']}\n"
        if c["impact_summary_what_changed"]:
            md += f"- **What changed**: {c['impact_summary_what_changed']}\n"
        if c["entities_top5"]:
            md += f"- **Entities**: {', '.join(c['entities_top5'])}\n"
        md += "\n"

    return md


if __name__ == "__main__":
    main()
