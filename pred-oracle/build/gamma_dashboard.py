"""Generate γ contract-watch dashboard slice (build/page_data/gamma/contracts.json).

Reads:
  - data/_scratch/artifacts.jsonl (Carver corpus)
  - data/gamma-curation.yml (for synthetic_listing_risk_tickets ticket counts)
  - data/platforms/kalshi/contracts.yml + data/platforms/polymarket/contracts.yml

For each pick with a `cached` block, computes heat score, 14-day sparkline,
heat_delta_7d, and emits a dashboard row.
"""

from __future__ import annotations

import json
import sys
from collections import Counter
from datetime import date, timedelta
from pathlib import Path
from typing import Any, cast

import yaml

# Allow running as `python build/gamma_dashboard.py` from the repo root
_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from build import _fields, _heat, _heat_panel  # noqa: E402


def _stream_corpus(corpus_path: Path) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    with corpus_path.open() as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            out.append(json.loads(line))
    return out


def _build_contract_row(
    pick: dict[str, Any],
    platform: str,
    corpus: list[dict[str, Any]],
    today: date,
    open_tickets: int,
) -> dict[str, Any] | None:
    cached = pick.get("cached")
    if not cached:
        return None
    contract = {
        "settlement_entities": cached.get("settlement_entities") or [],
    }
    heat_now = _heat.heat_score(contract, corpus, today=today)
    heat_7d_ago = _heat.heat_score(contract, corpus, today=today - timedelta(days=7))
    sparkline = _heat.sparkline_buckets(contract, corpus, today=today, days=14)
    match_count = _heat.matching_event_count(contract, corpus, today=today)

    settle = contract["settlement_entities"]
    last_pub = ""
    # Sort by pub_date desc, but exclude future-dated records (corpus has
    # some LLM-parsed dates in 2027-12 etc. that would otherwise win).
    today_iso = today.isoformat()
    for rec in sorted(corpus, key=lambda r: _fields.pub_date_iso(r), reverse=True):
        pub_iso = _fields.pub_date_iso(rec)
        if not pub_iso or pub_iso > today_iso:
            continue
        if _heat.entity_match(settle, rec.get("entities") or []):
            last_pub = pub_iso
            break

    return {
        "id": pick["id"],
        "platform": platform,
        "title": cached.get("title") or "",
        "external_id": (
            cached.get("external_id") or cached.get("ticker") or cached.get("slug") or ""
        ),
        "status": cached.get("status") or "active",
        "settlement_entities": settle,
        "heat": heat_now,
        "heat_delta_7d": round(heat_now - heat_7d_ago, 2),
        "sparkline": sparkline,
        "matching_event_count": match_count,
        "last_event_pub_date": last_pub,
        "open_tickets_count": open_tickets,
        "is_stale": bool(pick.get("stale")),
        "detail_href": f"contracts/{pick['id']}/",
        "heat_window_label": "current",
        "tier": _heat_panel.tier_for(heat_now),
        "kind": "active",
    }


def _build_retro_row(
    pick: dict[str, Any],
    retros_root: Path,
    corpus: list[dict[str, Any]],
    today: date,
    open_tickets_count: int,
) -> dict[str, Any] | None:
    """Build a dashboard row for a retrospective contract.

    Heat is scored against [resolved_at - 90d, resolved_at] — the
    'at resolution' window — rather than current corpus.
    """
    p = retros_root / pick["platform"] / "contracts" / f"{pick['id']}.yml"
    if not p.exists():
        return None
    retro = cast(dict[str, Any], yaml.safe_load(p.read_text()))
    settle = retro["settlement_entities"]
    resolved = date.fromisoformat(retro["resolved_at"][:10])
    # Score heat as if "today" were resolved_at.
    heat_now = _heat.heat_score(
        {"settlement_entities": settle}, corpus, today=resolved,
    )
    heat_7d = _heat.heat_score(
        {"settlement_entities": settle}, corpus, today=resolved - timedelta(days=7),
    )
    sparkline = _heat.sparkline_buckets(
        {"settlement_entities": settle}, corpus, today=resolved, days=14,
    )
    match_count = _heat.matching_event_count(
        {"settlement_entities": settle}, corpus, today=resolved,
    )
    return {
        "id": pick["id"],
        "platform": pick["platform"],
        "title": retro["title"],
        "status": retro.get("status", "resolved"),
        "settlement_entities": settle,
        "heat": heat_now,
        "heat_delta_7d": round(heat_now - heat_7d, 2),
        "sparkline": sparkline,
        "matching_event_count": match_count,
        "last_event_pub_date": "",
        "open_tickets_count": open_tickets_count,
        "is_stale": False,
        "detail_href": f"contracts/{pick['id']}/",
        "heat_window_label": "at resolution",
        "tier": _heat_panel.tier_for(heat_now),
        "kind": "retrospective",
    }


def generate(
    corpus_path: Path,
    gamma_curation_path: Path,
    kalshi_contracts_path: Path,
    polymarket_contracts_path: Path,
    out_path: Path,
    today: date | None = None,
    retros_root: Path | None = None,
) -> dict[str, Any]:
    today = today or date.today()
    if retros_root is None:
        retros_root = Path(__file__).resolve().parent.parent / "data" / "platforms"
    gamma = cast(dict[str, Any], yaml.safe_load(gamma_curation_path.read_text()))
    kalshi = cast(dict[str, Any], yaml.safe_load(kalshi_contracts_path.read_text()))
    polymarket = cast(dict[str, Any], yaml.safe_load(polymarket_contracts_path.read_text()))

    tickets_by_contract = Counter(
        t["contract_id"] for t in (gamma.get("synthetic_listing_risk_tickets") or [])
    )

    # Pre-filter the corpus to substantive records only (drops low-relevance
    # records and "website error" / "other" update types, which carry noisy
    # LLM-extracted entity annotations that inflate heat). Matches Stage 1 α.
    corpus = [r for r in _stream_corpus(corpus_path) if _heat.is_substantive(r)]

    rows: list[dict[str, Any]] = []
    for pick in kalshi.get("picks") or []:
        row = _build_contract_row(pick, "kalshi", corpus, today,
                                  tickets_by_contract.get(pick["id"], 0))
        if row:
            rows.append(row)
    for pick in polymarket.get("picks") or []:
        row = _build_contract_row(pick, "polymarket", corpus, today,
                                  tickets_by_contract.get(pick["id"], 0))
        if row:
            rows.append(row)

    for pick in gamma.get("contract_detail_picks") or []:
        if pick.get("kind") != "retrospective":
            continue
        row = _build_retro_row(
            pick, retros_root, corpus, today,
            tickets_by_contract.get(pick["id"], 0),
        )
        if row:
            rows.append(row)

    # Section-aware sort: actives by heat desc, retros by id desc, actives first.
    active_rows = [r for r in rows if r["kind"] == "active"]
    retro_rows = [r for r in rows if r["kind"] == "retrospective"]
    active_rows.sort(key=lambda r: r["heat"], reverse=True)
    retro_rows.sort(key=lambda r: r["id"], reverse=True)
    rows = active_rows + retro_rows

    rising = sorted(active_rows, key=lambda r: r["heat_delta_7d"], reverse=True)[:2]
    if rising and rising[0]["heat_delta_7d"] > 0:
        names = " and ".join(f"\"{r['title'][:50]}\"" for r in rising if r["heat_delta_7d"] > 0)
        narrative = f"Heat rising: {names}. Watch these closely this week."
    else:
        narrative = "Heat steady across the active book this week."

    slice_doc = {
        "scene": {"number": 2, "letter": "γ", "back_href": "../"},
        "window_days": _heat.DEFAULT_MAX_AGE_DAYS,
        "contracts": rows,
        "rows": rows,
        "rising_narrative": narrative,
        "filter_chips": [
            {"label": "All", "min_heat": 0, "active": True},
            {"label": "≥5", "min_heat": 5, "active": False},
            {"label": "≥7", "min_heat": 7, "active": False},
            {"label": "≥9", "min_heat": 9, "active": False},
        ],
    }
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(slice_doc, indent=2))
    return slice_doc


if __name__ == "__main__":
    REPO = Path(__file__).resolve().parent.parent
    generate(
        corpus_path=REPO / "data" / "_scratch" / "artifacts.jsonl",
        gamma_curation_path=REPO / "data" / "gamma-curation.yml",
        kalshi_contracts_path=REPO / "data" / "platforms" / "kalshi" / "contracts.yml",
        polymarket_contracts_path=REPO / "data" / "platforms" / "polymarket" / "contracts.yml",
        out_path=REPO / "build" / "page_data" / "gamma" / "dashboard.json",
    )
