"""Generate γ pre-listing scan slices.

One JSON per scan in curation.pre_listing_scans. Reads the artifacts corpus,
filters to events matching the scan's settlement_entities, ranks by urgency*recency,
emits the top 10.
"""

from __future__ import annotations

import json
import math
import sys
from collections import Counter
from datetime import date
from pathlib import Path
from typing import Any, cast

import yaml

# Allow running as `python build/gamma_scan.py` from the repo root
_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from build import _fields, _heat  # noqa: E402


def _stream_corpus(corpus_path: Path) -> Any:
    with corpus_path.open() as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            yield json.loads(line)


def _build_scan(
    scan: dict[str, Any],
    corpus: list[dict[str, Any]],
    today: date,
) -> dict[str, Any]:
    settle = scan["settlement_entities"]
    matches: list[tuple[dict[str, Any], str]] = []
    seen_titles: set[str] = set()
    for rec in corpus:
        # Drop noise: low-relevance, "website error" / "other" update types,
        # missing title/link. Same filter Stage 1 α uses on the inbox.
        if not _heat.is_substantive(rec):
            continue
        rec_entities = rec.get("entities") or []
        # Filter: valid date, not in the future, within scan window (90d).
        age = _fields.pub_date_age_days(rec, today=today)
        if age is None or age < 0 or age > _heat.DEFAULT_MAX_AGE_DAYS:
            continue
        # De-dupe by normalized title (corpus has repeats from feed reprocessing).
        title_key = (rec.get("title") or "").strip().lower()
        if not title_key or title_key in seen_titles:
            continue
        # Match this record to the first scan entity that overlaps with its
        # entities. We test one-entity-at-a-time (rather than calling
        # _heat.entity_match in bulk) so we can record which scan entity drove
        # the match for downstream display.
        for ce in settle:
            if _heat.entity_match([ce], rec_entities):
                matches.append((rec, ce))
                seen_titles.add(title_key)
                break

    def _rank(pair: tuple[dict[str, Any], str]) -> float:
        rec, _ce = pair
        age = _fields.pub_date_age_days(rec, today=today)
        if age is None or age < 0:
            return 0.0
        return _fields.urgency_score(rec) * math.exp(-age / 14.0)

    matches.sort(key=_rank, reverse=True)
    top = matches[:10]

    max_urg = max((_fields.urgency_score(r) for r, _ in matches), default=0.0)

    by_entity = Counter(ce for _, ce in matches)
    top_entity = by_entity.most_common(1)[0][0] if by_entity else ""

    recent_events = [
        {
            "title": rec.get("title") or "",
            "regulator": _fields.regulator_display(rec),
            "pub_date": _fields.pub_date_iso(rec),
            "urgency": _fields.urgency_score(rec),
            "link": rec.get("link") or "",
            "matched_entity": ce,
        }
        for rec, ce in top
    ]

    warnings: list[str] = []
    if not matches:
        warnings.append("No matching recent events found in the corpus.")

    return {
        "id": scan["id"],
        "title": scan["title"],
        "resolution_criteria": scan["resolution_criteria"],
        "platform_hint": scan["platform_hint"],
        "severity": int(scan.get("severity_hint", 5)),
        "severity_breakdown": {
            "matching_events_count": len(matches),
            "max_urgency": max_urg,
            "top_entity": top_entity,
        },
        "extracted_entities": [
            {"name": e, "source": "settlement_entities"} for e in settle
        ],
        "recent_events": recent_events,
        "warnings": warnings,
    }


def generate(
    corpus_path: Path,
    curation_path: Path,
    out_dir: Path,
    today: date | None = None,
) -> list[Path]:
    today = today or date.today()
    curation = cast(dict[str, Any], yaml.safe_load(curation_path.read_text()))
    scans = curation.get("pre_listing_scans") or []
    corpus = list(_stream_corpus(corpus_path))
    out_dir.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    for scan in scans:
        dto = _build_scan(scan, corpus=corpus, today=today)
        out_path = out_dir / f"{scan['id']}.json"
        out_path.write_text(json.dumps(dto, indent=2))
        written.append(out_path)
    return written


if __name__ == "__main__":
    REPO = Path(__file__).resolve().parent.parent
    paths = generate(
        corpus_path=REPO / "data" / "_scratch" / "artifacts.jsonl",
        curation_path=REPO / "data" / "gamma-curation.yml",
        out_dir=REPO / "build" / "page_data" / "gamma" / "pre-listing-scans",
    )
    print(f"Wrote {len(paths)} pre-listing scan slices")
