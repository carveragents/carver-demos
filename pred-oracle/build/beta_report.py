"""Generate the β quarterly-report slice (build/page_data/beta/report.json).

Composes country aggregates × prior-window delta × footprint role × watch-list
picks × cascade highlights into the board-ready report payload.
"""

from __future__ import annotations

import json
import math
import sys
from datetime import date
from pathlib import Path
from typing import Any, cast

import yaml  # type: ignore[import-untyped]

_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from build import _country, _fields, _heat  # noqa: E402
from build.beta_heatmap import _COUNTRY_LABELS  # noqa: E402


def _stream_corpus(corpus_path: Path) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    with corpus_path.open() as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            out.append(json.loads(line))
    return out


def _top_events_for(corpus: list[dict[str, Any]], code: str, today: date,
                    window_days: int, limit: int) -> list[dict[str, Any]]:
    matches: list[tuple[dict[str, Any], int]] = []
    for r in corpus:
        if _country.country_code(r, world_only=False) != code:
            continue
        age = _fields.pub_date_age_days(r, today=today)
        if age is None or age < 0 or age > window_days:
            continue
        matches.append((r, age))
    matches.sort(key=lambda pair: _fields.urgency_score(pair[0])
                  * math.exp(-pair[1] / 14.0), reverse=True)
    return [
        {"title": (r.get("title") or "")[:160],
         "regulator": _fields.regulator_display(r),
         "pub_date": _fields.pub_date_iso(r),
         "urgency": _fields.urgency_score(r),
         "link": r.get("link") or ""}
        for r, _ in matches[:limit]
    ]


def _role_map(footprint: dict[str, Any]) -> dict[str, str]:
    out: dict[str, str] = {}
    for entry in footprint.get("operating") or []:
        out[entry["code"]] = "operating"
    for entry in footprint.get("considering") or []:
        out[entry["code"]] = "considering"
    for entry in footprint.get("closed") or []:
        out[entry["code"]] = "closed"
    return out


def _narrate_pressure(row: dict[str, float], label: str, role: str) -> str:
    direction = "rising" if row["delta"] >= 0 else "easing"
    return (
        f"{label} pressure is {direction} ({row['delta']:+.1f} vs prior 90d). "
        f"Current footprint: {role}. {int(row['current_count'])} events at avg "
        f"urgency {row['current_avg_urgency']:.1f}."
    )


def generate(corpus_path: Path, curation_path: Path, footprint_path: Path,
             cascades_path: Path, out_path: Path,
             today: date | None = None) -> dict[str, Any]:
    today = today or date.today()
    curation = cast(dict[str, Any], yaml.safe_load(curation_path.read_text()))
    footprint = cast(dict[str, Any], yaml.safe_load(footprint_path.read_text()))
    cascades = cast(dict[str, Any], yaml.safe_load(cascades_path.read_text()))

    corpus = [r for r in _stream_corpus(corpus_path) if _heat.is_substantive(r)]
    deltas = _country.delta_pressure(corpus, today=today,
                                     current_window_days=90,
                                     prior_window_days=90)
    roles = _role_map(footprint)

    def _row(code: str, delta_row: dict[str, float]) -> dict[str, Any]:
        label = _COUNTRY_LABELS.get(code, code)
        role = roles.get(code, "other")
        return {
            "code": code, "label": label, "role": role,
            "current_pressure": delta_row["current_pressure"],
            "prior_pressure": delta_row["prior_pressure"],
            "delta": delta_row["delta"],
            "current_count": int(delta_row["current_count"]),
            "narrative": _narrate_pressure(delta_row, label, role),
            "top_events": _top_events_for(corpus, code, today, 90, 3),
        }

    rising_sorted = sorted(
        [_row(c, d) for c, d in deltas.items() if d["current_count"] >= 5],
        key=lambda x: x["delta"], reverse=True,
    )
    pressure_rising = rising_sorted[:10]
    pressure_easing = sorted(rising_sorted, key=lambda x: x["delta"])[:5]

    watch_list = []
    for w in curation.get("watch_list_picks") or []:
        code = w["country_code"]
        watch_list.append({
            "code": code,
            "label": w["label"],
            "role": roles.get(code, "other"),
            "rationale": w["rationale"],
            "recommended_actions": w["recommended_actions"],
            "alpha_dashboard_link": f"alpha/dashboard/#{code}",
            "evidence_events": _top_events_for(corpus, code, today, 90, 3),
        })

    featured_cascades = [
        {"id": c["id"], "body_acronym": c.get("body_acronym", c["body"]),
         "trigger_title": c["trigger_title"],
         "trigger_pub_date": c["trigger_pub_date"],
         "historical_hit_rate": c["historical_hit_rate"]}
        for c in cascades.get("cascades") or []
        if c["id"] in (curation.get("featured_cascade_ids") or [])
    ]

    gamma_path = (corpus_path.parent.parent.parent
                  / "build" / "page_data" / "gamma" / "dashboard.json")
    gamma_touchpoints: list[dict[str, Any]] = []
    if gamma_path.exists():
        gd = json.loads(gamma_path.read_text())
        for c in (gd.get("contracts") or [])[:3]:
            gamma_touchpoints.append({
                "contract_id": c["id"],
                "title": c["title"],
                "heat": c["heat"],
                "detail_href": f"gamma/contracts/{c['id']}/",
            })

    high_urg = sum(1 for r in corpus
                   if _fields.urgency_score(r) >= 8
                   and (_fields.pub_date_age_days(r, today=today) or 999) <= 90)

    doc: dict[str, Any] = {
        "scene": {"number": 3, "letter": "β", "back_label": "← Cascade signals",
                  "back_href": "../cascades/"},
        "report_window": curation["report_window"],
        "generated_at": today.isoformat(),
        "active_platform": footprint["platform"],
        "headline_stats": {
            "events_in_window": sum(int(d["current_count"]) for d in deltas.values()),
            "jurisdictions_with_activity": sum(
                1 for d in deltas.values() if d["current_count"]
            ),
            "high_urgency_events": high_urg,
            "active_cascades": len(featured_cascades),
        },
        "pressure_rising": pressure_rising,
        "pressure_easing": pressure_easing,
        "watch_list": watch_list,
        "featured_cascades": featured_cascades,
        "gamma_touchpoints": gamma_touchpoints,
        "method_notes": (
            "Pressure score = min(100, count × avg urgency / 5) over the report "
            "window. Delta compares against the equivalent immediately-prior "
            "window. Watch list is hand-picked; pattern match is qualitative."
        ),
        "coverage_caveat": (
            "All events drawn from Carver's regulatory-annotation pipeline. "
            "Coverage skews toward bodies in the regulator allowlist; smaller "
            "or country-specific bodies may be underrepresented."
        ),
        "watch_list_disclaimer":
            "Pattern-based projection, not prediction. Confidence: medium.",
        "v1_footer": (
            "V1 cascade rules are curated from historical patterns. Learned "
            "models will replace rules in V2+ as more data accrues."
        ),
        "pdf_href": "static/samples/q2-2026-report.pdf",
    }
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(doc, indent=2))
    return doc


if __name__ == "__main__":
    REPO = Path(__file__).resolve().parent.parent
    cur = yaml.safe_load((REPO / "data" / "beta-curation.yml").read_text())
    platform = cur["platform_footprint"]
    generate(
        corpus_path=REPO / "data" / "_scratch" / "artifacts.jsonl",
        curation_path=REPO / "data" / "beta-curation.yml",
        footprint_path=REPO / "data" / "platforms" / platform / "footprint.yml",
        cascades_path=REPO / "data" / "cascades.yml",
        out_path=REPO / "build" / "page_data" / "beta" / "report.json",
    )
    print("wrote build/page_data/beta/report.json")
