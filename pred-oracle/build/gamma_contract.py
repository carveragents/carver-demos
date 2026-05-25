"""γ contract-detail slice generator — parametric across curation picks."""

from __future__ import annotations

import json
import sys
from datetime import date
from pathlib import Path
from typing import Any, cast

import yaml  # type: ignore[import-untyped]

# Allow running as `python build/gamma_contract.py` from the repo root
_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from build import _fields, _heat  # noqa: E402


def _stream_corpus(corpus_path: Path) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    with corpus_path.open() as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            out.append(json.loads(line))
    return out


def _load_active_pick(
    pick_id: str, platform: str,
    kalshi_doc: dict[str, Any], polymarket_doc: dict[str, Any],
) -> dict[str, Any] | None:
    yaml_doc = kalshi_doc if platform == "kalshi" else polymarket_doc
    for pick in yaml_doc.get("picks") or []:
        if pick["id"] == pick_id:
            return cast(dict[str, Any], pick)
    return None


def _load_retrospective(pick_id: str, platform: str,
                        retrospectives_root: Path) -> dict[str, Any] | None:
    p = retrospectives_root / platform / "contracts" / f"{pick_id}.yml"
    if not p.exists():
        return None
    return cast(dict[str, Any], yaml.safe_load(p.read_text()))


def _entity_role(name: str) -> str:
    """Heuristic role tag for chip display."""
    name_l = name.lower()
    REGULATOR_HINTS = ("commission", "authority", "bureau", "department", "agency",
                       "office", "board", "ministry", "administration", "service",
                       "committee")
    if any(h in name_l for h in REGULATOR_HINTS):
        return "regulator"
    if "fed" in name_l or "treasury" in name_l or "reserve" in name_l:
        return "regulator"
    return "company"


def _parse_date(s: str) -> date | None:
    """Parse a YYYY-MM-DD (or ISO with time) date string. Returns None on failure."""
    if not s:
        return None
    try:
        return date.fromisoformat(s[:10])
    except ValueError:
        return None


def _window_for(
    listed_at: str, resolved_at: str, today: date, is_retrospective: bool,
) -> tuple[date | None, date | None]:
    """Compute timeline window per spec §4 Layer 1.

    Retrospective: [listed_at - 90d, resolved_at]
    Active:        [listed_at - 90d, today]
    """
    from datetime import timedelta
    listed = _parse_date(listed_at)
    if not listed:
        return (None, None)
    start = listed - timedelta(days=90)
    if is_retrospective:
        end = _parse_date(resolved_at) or today
    else:
        end = today
    return (start, end)


def _build_timeline(
    settlement_entities: list[str],
    corpus: list[dict[str, Any]],
    today: date,
    is_retrospective: bool,
    window_start: date | None,
    window_end: date | None,
) -> list[dict[str, Any]]:
    matches: list[tuple[dict[str, Any], str]] = []
    seen_titles: set[str] = set()
    for rec in corpus:
        if not _heat.is_substantive(rec):
            continue
        rec_entities = rec.get("entities") or []
        pub_iso = _fields.pub_date_iso(rec)
        pub = _parse_date(pub_iso)
        if pub is None:
            continue
        if window_start and pub < window_start:
            continue
        if window_end and pub > window_end:
            continue
        title_key = (rec.get("title") or "").strip().lower()
        if not title_key or title_key in seen_titles:
            continue
        for ce in settlement_entities:
            if _heat.entity_match([ce], rec_entities):
                matches.append((rec, ce))
                seen_titles.add(title_key)
                break

    matches.sort(key=lambda pair: _fields.pub_date_iso(pair[0]), reverse=True)

    timeline: list[dict[str, Any]] = []
    for rec, ce in matches:
        entry: dict[str, Any] = {
            "pub_date": _fields.pub_date_iso(rec),
            "title": rec.get("title") or "",
            "regulator": _fields.regulator_display(rec),
            "url": rec.get("link") or "",
            "urgency": _fields.urgency_score(rec),
            "impact": _fields.impact_score(rec),
            "matched_entity": ce,
            "carver_feed_entry_id": rec.get("feed_entry_id") or "",
        }
        if is_retrospective:
            entry["precedence_callout"] = {
                "news_date": None, "news_url": None, "days_ahead": None, "label": None,
            }
        timeline.append(entry)
    return timeline


def _build_contract_dto(
    pick_id: str, platform: str, kind: str,
    active_pick: dict[str, Any] | None, retro: dict[str, Any] | None,
    corpus: list[dict[str, Any]], today: date,
) -> dict[str, Any] | None:
    if kind == "active":
        if not active_pick or "cached" not in active_pick:
            return None
        c = active_pick["cached"]
        settlement = c.get("settlement_entities") or []
        primary_source = ""
        if platform == "kalshi" and c.get("ticker"):
            primary_source = f"https://kalshi.com/markets/{c['ticker']}"
        elif platform == "polymarket" and c.get("slug"):
            primary_source = f"https://polymarket.com/event/{c['slug']}"
        return {
            "id": pick_id, "platform": platform, "kind": "active",
            "title": c.get("title", ""),
            "external_id": c.get("external_id") or c.get("ticker") or c.get("slug") or "",
            "status": c.get("status", "active"),
            "listed_at": c.get("listed_at", ""),
            "expires_at": c.get("expires_at", ""),
            "resolved_at": "",
            "resolution_criteria": c.get("resolution_criteria", ""),
            "settlement_entities": [{"name": e, "role": _entity_role(e)} for e in settlement],
            "settlement_entities_flat": settlement,
            "source_urls": [],
            "primary_source_url": primary_source,
        }
    # retrospective
    if not retro:
        return None
    settlement = retro["settlement_entities"]
    return {
        "id": pick_id, "platform": platform, "kind": "retrospective",
        "title": retro["title"],
        "external_id": retro.get("id", ""),
        "status": retro.get("status", "resolved"),
        "listed_at": retro.get("listed_at", ""),
        "expires_at": "",
        "resolved_at": retro.get("resolved_at", ""),
        "resolution_criteria": retro.get("resolution_criteria", ""),
        "settlement_entities": [{"name": e, "role": _entity_role(e)} for e in settlement],
        "settlement_entities_flat": settlement,
        "source_urls": retro.get("source_urls", []),
        "primary_source_url": retro.get("source_urls", [""])[0] if retro.get("source_urls") else "",
    }


def generate(
    corpus_path: Path,
    gamma_curation_path: Path,
    kalshi_contracts_path: Path,
    polymarket_contracts_path: Path,
    retrospectives_root: Path,
    out_dir: Path,
    today: date | None = None,
) -> list[Path]:
    today = today or date.today()
    gamma = cast(dict[str, Any], yaml.safe_load(gamma_curation_path.read_text()))
    kalshi_doc = (
        cast(dict[str, Any], yaml.safe_load(kalshi_contracts_path.read_text()))
        if kalshi_contracts_path.exists() else {"picks": []}
    )
    polymarket_doc = (
        cast(dict[str, Any], yaml.safe_load(polymarket_contracts_path.read_text()))
        if polymarket_contracts_path.exists() else {"picks": []}
    )

    # Pre-filter to substantive records (low-relevance + "website error" /
    # "other" records carry noisy LLM-extracted entities). Same as α inbox.
    corpus = [r for r in _stream_corpus(corpus_path) if _heat.is_substantive(r)]
    tickets_index: dict[str, list[dict[str, Any]]] = {}
    for t in gamma.get("synthetic_listing_risk_tickets") or []:
        tickets_index.setdefault(t["contract_id"], []).append(t)

    out_dir.mkdir(parents=True, exist_ok=True)
    # Remove stale slice files for picks no longer in curation, so enrichment
    # doesn't process old contracts.
    expected_ids = {pick["id"] for pick in gamma.get("contract_detail_picks") or []}
    for existing in out_dir.glob("*.json"):
        if existing.stem not in expected_ids:
            existing.unlink()
    written: list[Path] = []
    for pick in gamma.get("contract_detail_picks") or []:
        pid, platform, kind = pick["id"], pick["platform"], pick["kind"]
        active_pick = (
            _load_active_pick(pid, platform, kalshi_doc, polymarket_doc)
            if kind == "active" else None
        )
        retro = (
            _load_retrospective(pid, platform, retrospectives_root)
            if kind == "retrospective" else None
        )
        dto = _build_contract_dto(pid, platform, kind, active_pick, retro, corpus, today)
        if dto is None:
            print(f"WARN: contract pick {pid!r} ({platform}, {kind}) had no source data; skipping",
                  file=sys.stderr)
            continue

        flat = dto["settlement_entities_flat"]
        is_retro = kind == "retrospective"
        window_start, window_end = _window_for(
            listed_at=dto.get("listed_at", ""),
            resolved_at=dto.get("resolved_at", ""),
            today=today,
            is_retrospective=is_retro,
        )
        timeline = _build_timeline(
            flat, corpus, today, is_retro, window_start, window_end,
        )
        heat = _heat.heat_score({"settlement_entities": flat}, corpus, today=today)
        sparkline = _heat.sparkline_buckets(
            {"settlement_entities": flat}, corpus, today=today, days=14,
        )
        dto["heat"] = heat
        dto["heat_history"] = sparkline

        dto.pop("settlement_entities_flat", None)

        slice_doc = {
            "scene": {"number": 2, "letter": "γ", "back_label": "← Dashboard", "back_href": "../"},
            "contract": dto,
            "timeline": timeline,
            "open_tickets": [
                {
                    "summary": t["summary"],
                    "severity": t["severity"],
                    "assignee_initials": t["assignee_initials"],
                    "is_demo": True,
                }
                for t in tickets_index.get(pid, [])
            ],
        }
        out_path = out_dir / f"{pid}.json"
        out_path.write_text(json.dumps(slice_doc, indent=2))
        written.append(out_path)
    return written


if __name__ == "__main__":
    REPO = Path(__file__).resolve().parent.parent
    paths = generate(
        corpus_path=REPO / "data" / "_scratch" / "artifacts.jsonl",
        gamma_curation_path=REPO / "data" / "gamma-curation.yml",
        kalshi_contracts_path=REPO / "data" / "platforms" / "kalshi" / "contracts.yml",
        polymarket_contracts_path=REPO / "data" / "platforms" / "polymarket" / "contracts.yml",
        retrospectives_root=REPO / "data" / "platforms",
        out_dir=REPO / "build" / "page_data" / "gamma" / "contracts",
    )
    print(f"Wrote {len(paths)} contract-detail slices")
