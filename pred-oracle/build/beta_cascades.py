"""Generate the β cascade-signals slice (build/page_data/beta/cascades.json).

Joins data/cascades.yml × data/platforms/<platform>/footprint.yml to emit
per-rule cards with member jurisdictions tagged by footprint role.
"""

from __future__ import annotations

import json
import re
import sys
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, cast

import yaml  # type: ignore[import-untyped]

_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

# Reused _COUNTRY_LABELS from beta_heatmap.
from build.beta_heatmap import _COUNTRY_LABELS  # noqa: E402


def _role_map(footprint: dict[str, Any]) -> dict[str, str]:
    """Build code → role mapping from a footprint document."""
    out: dict[str, str] = {}
    for entry in footprint.get("operating") or []:
        out[entry["code"]] = "operating"
    for entry in footprint.get("considering") or []:
        out[entry["code"]] = "considering"
    for entry in footprint.get("closed") or []:
        out[entry["code"]] = "closed"
    return out


def _expected_action_by(trigger_iso: str, follow_window_days: int) -> str:
    trigger = datetime.strptime(trigger_iso, "%Y-%m-%d").date()
    return (trigger + timedelta(days=follow_window_days)).isoformat()


_HIT_RATE_RE = re.compile(r"(\d+)\s*/\s*(\d+)\s*\(\s*(\d+)\s*%\s*\)")


def _parse_hit_rate(s: str) -> tuple[int, int, int]:
    """Parse '31/39 (79%)' into (adopted, total, pct). Returns zeros on miss."""
    m = _HIT_RATE_RE.search(s or "")
    if not m:
        return (0, 0, 0)
    return (int(m.group(1)), int(m.group(2)), int(m.group(3)))


def _build_card(rule: dict[str, Any], roles: dict[str, str]) -> dict[str, Any]:
    members = []
    overlap = 0
    for code in rule["member_jurisdictions"]:
        role = roles.get(code, "other")
        members.append({
            "code": code,
            "label": _COUNTRY_LABELS.get(code, code),
            "role": role,
        })
        if role in {"operating", "considering"}:
            overlap += 1
    adopted, total, pct = _parse_hit_rate(rule["historical_hit_rate"])
    return {
        "id": rule["id"],
        "body": rule["body"],
        "body_acronym": rule.get("body_acronym", rule["body"]),
        "trigger_title": rule["trigger_title"],
        "trigger_pub_date": rule["trigger_pub_date"],
        "trigger_url": rule["trigger_url"],
        "rationale": rule["rationale"],
        "follow_window_days": rule["follow_window_days"],
        "expected_action_by": _expected_action_by(rule["trigger_pub_date"],
                                                   rule["follow_window_days"]),
        "historical_hit_rate": rule["historical_hit_rate"],
        "hit_rate_adopted": adopted,
        "hit_rate_total": total,
        "hit_rate_pct": pct,
        "members": members,
        "footprint_overlap_count": overlap,
    }


def generate(cascades_path: Path, curation_path: Path, footprint_path: Path,
             out_path: Path, today: date | None = None) -> dict[str, Any]:
    today = today or date.today()
    cascades = cast(dict[str, Any], yaml.safe_load(cascades_path.read_text()))
    curation = cast(dict[str, Any], yaml.safe_load(curation_path.read_text()))
    footprint = cast(dict[str, Any], yaml.safe_load(footprint_path.read_text()))

    featured_ids = curation.get("featured_cascade_ids") or []
    rules_by_id = {c["id"]: c for c in cascades.get("cascades") or []}
    roles = _role_map(footprint)

    cards = []
    for cid in featured_ids:
        rule = rules_by_id.get(cid)
        if not rule:
            print(f"WARN: featured cascade id {cid!r} not in cascades.yml", file=sys.stderr)
            continue
        cards.append(_build_card(rule, roles))

    doc: dict[str, Any] = {
        "scene": {"number": 3, "letter": "β", "back_href": "../"},
        "active_platform": footprint["platform"],
        "cascades": cards,
    }
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(doc, indent=2))
    return doc


if __name__ == "__main__":
    REPO = Path(__file__).resolve().parent.parent
    cur = yaml.safe_load((REPO / "data" / "beta-curation.yml").read_text())
    platform = cur["platform_footprint"]
    generate(
        cascades_path=REPO / "data" / "cascades.yml",
        curation_path=REPO / "data" / "beta-curation.yml",
        footprint_path=REPO / "data" / "platforms" / platform / "footprint.yml",
        out_path=REPO / "build" / "page_data" / "beta" / "cascades.json",
    )
    print("wrote build/page_data/beta/cascades.json")
