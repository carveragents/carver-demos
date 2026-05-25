"""Generate the β world-heat-map slice (build/page_data/beta/heatmap.json).

Reads:
  - data/_scratch/artifacts.jsonl (Carver corpus).
  - data/beta-curation.yml (retrospective focus + annotation callouts).
  - data/platforms/<platform>/footprint.yml (operating/considering/closed).
"""

from __future__ import annotations

import json
import math
import sys
from datetime import date, datetime
from pathlib import Path
from typing import Any, cast

import yaml  # type: ignore[import-untyped]

_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from build import _country, _fields, _heat  # noqa: E402
from build.alpha_dashboard import _US_STATE_NAMES  # noqa: E402

_COUNTRY_LABELS: dict[str, str] = {
    # Values intentionally match the `name` property in
    # build/static/js/world.geo.json (Natural Earth 110m) so ECharts can
    # match data rows to map features by name. Diverging from the geojson
    # leaves countries un-colored on the map.
    "US": "United States of America", "CA": "Canada", "MX": "Mexico", "BR": "Brazil",
    "AR": "Argentina", "CL": "Chile", "CO": "Colombia",
    "GB": "United Kingdom", "FR": "France", "DE": "Germany", "ES": "Spain",
    "IT": "Italy", "NL": "Netherlands", "BE": "Belgium", "LU": "Luxembourg",
    "IE": "Ireland", "PT": "Portugal", "AT": "Austria", "GR": "Greece",
    "CH": "Switzerland", "DK": "Denmark", "FI": "Finland", "SE": "Sweden",
    "NO": "Norway", "PL": "Poland", "CZ": "Czechia", "HU": "Hungary",
    "RO": "Romania", "BG": "Bulgaria", "HR": "Croatia", "EE": "Estonia",
    "LV": "Latvia", "LT": "Lithuania", "MT": "Malta", "CY": "Cyprus",
    "SI": "Slovenia", "SK": "Slovakia", "IS": "Iceland",
    "RU": "Russia", "TR": "Turkey", "UA": "Ukraine",
    "AE": "United Arab Emirates", "SA": "Saudi Arabia", "IL": "Israel",
    "QA": "Qatar", "KW": "Kuwait", "OM": "Oman", "BH": "Bahrain",
    "IN": "India", "PK": "Pakistan", "BD": "Bangladesh", "ID": "Indonesia",
    "MY": "Malaysia", "PH": "Philippines", "TH": "Thailand", "VN": "Vietnam",
    "SG": "Singapore", "TW": "Taiwan", "HK": "Hong Kong", "JP": "Japan",
    "KR": "South Korea", "CN": "China",
    "AU": "Australia", "NZ": "New Zealand",
    "ZA": "South Africa", "EG": "Egypt", "NG": "Nigeria", "KE": "Kenya",
    "EU": "European Union",
}


def _label(code: str) -> str:
    return _COUNTRY_LABELS.get(code, code)


def _stream_corpus(corpus_path: Path) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    with corpus_path.open() as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            out.append(json.loads(line))
    return out


def _build_world_aggregates(corpus: list[dict[str, Any]], today: date,
                            window_days: int) -> list[dict[str, Any]]:
    agg = _country.aggregate(corpus, today=today, window_days=window_days,
                             world_only=True)
    rows = [
        {"code": code, "label": _label(code),
         "count": int(slot["count"]), "avg_urgency": slot.get("avg_urgency", 0.0),
         "max_urgency": slot.get("max_urgency", 0.0),
         "pressure": _country.pressure_score(slot)}
        for code, slot in agg.items()
    ]
    rows.sort(key=lambda r: cast(float, r["pressure"]), reverse=True)
    return rows


def _build_state_aggregates(corpus: list[dict[str, Any]], today: date,
                            window_days: int) -> list[dict[str, Any]]:
    rows = []
    for r in corpus:
        code = _country.country_code(r, world_only=False) or ""
        if not code.startswith("US-"):
            continue
        rows.append(r)
    agg = _country.aggregate(rows, today=today, window_days=window_days,
                             world_only=False)
    # Label must match the `name` property in build/static/js/usa-states.json
    # (full state name like "California") so ECharts can match data to features.
    out = [
        {"code": code,
         "label": _US_STATE_NAMES.get(code, code.replace("US-", "")),
         "count": int(slot["count"]),
         "avg_urgency": slot.get("avg_urgency", 0.0),
         "max_urgency": slot.get("max_urgency", 0.0),
         "pressure": _country.pressure_score(slot)}
        for code, slot in agg.items() if code.startswith("US-")
    ]
    out.sort(key=lambda r: cast(float, r["pressure"]), reverse=True)
    return out


def _build_retrospective(corpus: list[dict[str, Any]], focus: dict[str, Any],
                         today: date) -> dict[str, Any]:
    code = focus["country_code"]
    months = focus.get("narrative_window_months", 18)
    weeks = round(months * 52 / 12)  # 18 months → 78 weeks
    buckets = _country.weekly_buckets(corpus, code=code, today=today, weeks=weeks)
    callouts: list[dict[str, Any]] = []
    horizon_days = weeks * 7
    for c in focus.get("annotation_callouts") or []:
        c_date = datetime.strptime(c["date"], "%Y-%m-%d").date()
        c_age = (today - c_date).days
        if c_age < 0 or c_age >= horizon_days:
            continue
        week_idx = (weeks - 1) - (c_age // 7)
        callouts.append({"date": c["date"], "label": c["label"], "week_index": week_idx})

    matches: list[tuple[dict[str, Any], int]] = []
    for r in corpus:
        if _country.country_code(r, world_only=False) != code:
            continue
        age_or_none = _fields.pub_date_age_days(r, today=today)
        if age_or_none is None or age_or_none < 0 or age_or_none > horizon_days:
            continue
        age: int = age_or_none
        matches.append((r, age))
    matches.sort(key=lambda pair: _fields.urgency_score(pair[0])
                  * math.exp(-pair[1] / 14.0), reverse=True)
    top = [
        {"title": (r.get("title") or "")[:160], "regulator": _fields.regulator_display(r),
         "pub_date": _fields.pub_date_iso(r), "urgency": _fields.urgency_score(r),
         "link": r.get("link") or "", "matched_entity": code}
        for r, _ in matches[:10]
    ]

    return {
        "code": code,
        "label": _label(code),
        "title": focus["title"],
        "weekly_buckets": buckets,
        "annotation_callouts": callouts,
        "top_events": top,
        "anj_disclosure": (
            "Direct ANJ (Autorité Nationale des Jeux) events are not in the "
            "Carver catalog. The timeline above is drawn from AMF, ESMA, and "
            "EU Commission events tagged France in the public regulatory record."
            if code == "FR" else ""
        ),
    }


def generate(corpus_path: Path, curation_path: Path, footprint_path: Path,
             out_path: Path, today: date | None = None,
             window_days: int = 90) -> dict[str, Any]:
    today = today or date.today()
    curation = cast(dict[str, Any], yaml.safe_load(curation_path.read_text()))
    footprint = cast(dict[str, Any], yaml.safe_load(footprint_path.read_text()))

    corpus = [r for r in _stream_corpus(corpus_path) if _heat.is_substantive(r)]

    world = _build_world_aggregates(corpus, today, window_days)
    states = _build_state_aggregates(corpus, today, window_days)
    retro = _build_retrospective(corpus, curation["retrospective_focus"], today)

    if world:
        top = world[0]
        anomaly = (
            f"{top['label']} carries the highest pressure score "
            f"({top['pressure']:.0f}) — {top['count']} events at avg urgency "
            f"{top['avg_urgency']:.1f}."
        )
    else:
        anomaly = "Pressure is light across the board this window."

    doc = {
        "scene": {"number": 3, "letter": "β", "back_href": "../"},
        "window_days": window_days,
        "world_aggregates": world,
        "us_state_aggregates": states,
        "platform_footprint": {
            "active_platform": footprint["platform"],
            "operating":   [{**e, "label": e.get("label", _label(e["code"]))}
                            for e in footprint.get("operating") or []],
            "considering": [{**e, "label": e.get("label", _label(e["code"]))}
                            for e in footprint.get("considering") or []],
            "closed":      [{**e, "label": e.get("label", _label(e["code"]))}
                            for e in footprint.get("closed") or []],
        },
        "retrospective_focus": retro,
        "anomaly_note": anomaly,
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
        out_path=REPO / "build" / "page_data" / "beta" / "heatmap.json",
    )
    print("wrote build/page_data/beta/heatmap.json")
