"""Trader contract-detail slice generator — reads from data/trader-curation.yml."""

from __future__ import annotations

import json
import sys
from datetime import date
from pathlib import Path
from typing import Any, cast

import yaml  # type: ignore[import-untyped]

# Allow running as `python build/trader_contract.py` from the repo root
_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from build import _fields, _heat  # noqa: E402

# Re-use helpers from gamma_contract — they are stable and have full test coverage.
from build.gamma_contract import (  # noqa: E402
    _build_timeline,
    _entity_role,
    _load_active_pick,
    _load_retrospective,
    _parse_date,
    _stream_corpus,
    _window_for,
)


def _build_contract_dto(
    pick_id: str,
    platform: str,
    kind: str,
    active_pick: dict[str, Any] | None,
    retro: dict[str, Any] | None,
    individual_yml: dict[str, Any] | None,
) -> dict[str, Any] | None:
    """Build the contract DTO for a trader portfolio entry.

    Resolution order for active contracts:
      1. active_pick from contracts.yml picks list
      2. individual_yml from data/platforms/{platform}/contracts/{id}.yml
    Retrospectives always use the individual YAML file.
    """
    if kind == "active":
        if active_pick and "cached" in active_pick:
            c = active_pick["cached"]
            settlement = c.get("settlement_entities") or []
            primary_source = ""
            if platform == "kalshi" and c.get("ticker"):
                primary_source = f"https://kalshi.com/markets/{c['ticker']}"
            elif platform == "polymarket" and c.get("slug"):
                primary_source = f"https://polymarket.com/event/{c['slug']}"
            return {
                "id": pick_id,
                "platform": platform,
                "kind": "active",
                "title": c.get("title", ""),
                "subtitle": c.get("subtitle", ""),
                "external_id": c.get("external_id") or c.get("ticker") or c.get("slug") or "",
                "status": c.get("status", "active"),
                "listed_at": c.get("listed_at", ""),
                "expires_at": c.get("expires_at", ""),
                "resolved_at": "",
                "resolution_criteria": c.get("resolution_criteria", ""),
                "resolution_outcome": "",
                "settlement_entities": [{"name": e, "role": _entity_role(e)} for e in settlement],
                "settlement_entities_flat": settlement,
                "source_urls": [],
                "primary_source_url": primary_source,
            }
        # Fall back to individual YAML (new contracts not yet in contracts.yml picks)
        if individual_yml:
            return _dto_from_individual_yml(pick_id, platform, kind, individual_yml)
        return None

    # retrospective
    if retro:
        return _dto_from_individual_yml(pick_id, platform, "retrospective", retro)
    return None


def _dto_from_individual_yml(
    pick_id: str,
    platform: str,
    kind: str,
    doc: dict[str, Any],
) -> dict[str, Any]:
    """Build a contract DTO from a standalone contract YAML file."""
    settlement = doc.get("settlement_entities") or []
    source_urls = doc.get("source_urls") or []
    primary_source = source_urls[0] if source_urls else ""
    return {
        "id": pick_id,
        "platform": platform,
        "kind": kind,
        "title": doc.get("title", ""),
        "subtitle": doc.get("subtitle", ""),
        "external_id": doc.get("id") or pick_id,
        "status": doc.get("status", "active" if kind == "active" else "resolved"),
        "listed_at": doc.get("listed_at", ""),
        "expires_at": doc.get("expires_at", ""),
        "resolved_at": doc.get("resolved_at", ""),
        "resolution_criteria": doc.get("resolution_criteria", ""),
        "resolution_outcome": doc.get("resolution_outcome", ""),
        "settlement_entities": [{"name": e, "role": _entity_role(e)} for e in settlement],
        "settlement_entities_flat": settlement,
        "source_urls": source_urls,
        "primary_source_url": primary_source,
    }


def generate(
    *,
    corpus_path: Path,
    trader_curation_path: Path,
    kalshi_contracts_path: Path,
    polymarket_contracts_path: Path,
    retrospectives_root: Path,
    out_dir: Path,
    today: date | None = None,
) -> list[Path]:
    today = today or date.today()
    trader = cast(dict[str, Any], yaml.safe_load(trader_curation_path.read_text()))
    kalshi_doc = (
        cast(dict[str, Any], yaml.safe_load(kalshi_contracts_path.read_text()))
        if kalshi_contracts_path.exists() else {"picks": []}
    )
    polymarket_doc = (
        cast(dict[str, Any], yaml.safe_load(polymarket_contracts_path.read_text()))
        if polymarket_contracts_path.exists() else {"picks": []}
    )

    corpus = [r for r in _stream_corpus(corpus_path) if _heat.is_substantive(r)]

    out_dir.mkdir(parents=True, exist_ok=True)

    # Remove stale slice files for picks no longer in the portfolio
    all_ids = {entry["id"] for entry in (trader.get("portfolio") or [])}
    all_ids |= {entry["id"] for entry in (trader.get("retrospectives") or [])}
    for existing in out_dir.glob("*.json"):
        if existing.stem not in all_ids:
            existing.unlink()

    written: list[Path] = []

    # Process portfolio (active) entries
    for entry in trader.get("portfolio") or []:
        pid, platform, kind = entry["id"], entry["platform"], entry["kind"]
        position = entry.get("position") or {}

        active_pick = _load_active_pick(pid, platform, kalshi_doc, polymarket_doc)
        # For contracts not found in contracts.yml, try individual YAML
        individual_yml = (
            _load_retrospective(pid, platform, retrospectives_root)
            if active_pick is None else None
        )

        dto = _build_contract_dto(pid, platform, kind, active_pick, None, individual_yml)
        if dto is None:
            print(
                f"WARN: portfolio entry {pid!r} ({platform}, {kind}) had no source data; skipping",
                file=sys.stderr,
            )
            continue

        _write_slice(pid, platform, kind, dto, position, corpus, today, out_dir, written)

    # Process retrospective entries
    for entry in trader.get("retrospectives") or []:
        pid, platform = entry["id"], entry["platform"]
        kind = "retrospective"
        position = entry.get("position") or {}

        retro = _load_retrospective(pid, platform, retrospectives_root)
        dto = _build_contract_dto(pid, platform, kind, None, retro, None)
        if dto is None:
            print(
                f"WARN: retrospective {pid!r} ({platform}) had no source data; skipping",
                file=sys.stderr,
            )
            continue

        _write_slice(pid, platform, kind, dto, position, corpus, today, out_dir, written)

    return written


def _write_slice(
    pid: str,
    platform: str,
    kind: str,
    dto: dict[str, Any],
    position: dict[str, Any],
    corpus: list[dict[str, Any]],
    today: date,
    out_dir: Path,
    written: list[Path],
) -> None:
    flat = dto["settlement_entities_flat"]
    is_retro = kind == "retrospective"
    window_start, window_end = _window_for(
        listed_at=dto.get("listed_at", ""),
        resolved_at=dto.get("resolved_at", ""),
        today=today,
        is_retrospective=is_retro,
    )
    timeline = _build_timeline(flat, corpus, today, is_retro, window_start, window_end)
    heat = _heat.heat_score({"settlement_entities": flat}, corpus, today=today)
    sparkline = _heat.sparkline_buckets(
        {"settlement_entities": flat}, corpus, today=today, days=14,
    )
    dto["heat"] = heat
    dto["heat_history"] = sparkline
    dto.pop("settlement_entities_flat", None)

    slice_doc: dict[str, Any] = {
        "contract": dto,
        "position": position,
        "timeline": timeline,
    }
    out_path = out_dir / f"{pid}.json"
    out_path.write_text(json.dumps(slice_doc, indent=2))
    written.append(out_path)


if __name__ == "__main__":
    REPO = Path(__file__).resolve().parent.parent
    paths = generate(
        corpus_path=REPO / "data" / "_scratch" / "artifacts.jsonl",
        trader_curation_path=REPO / "data" / "trader-curation.yml",
        kalshi_contracts_path=REPO / "data" / "platforms" / "kalshi" / "contracts.yml",
        polymarket_contracts_path=REPO / "data" / "platforms" / "polymarket" / "contracts.yml",
        retrospectives_root=REPO / "data" / "platforms",
        out_dir=REPO / "build" / "page_data" / "trader" / "contracts",
    )
    print(f"Wrote {len(paths)} trader contract-detail slices")
