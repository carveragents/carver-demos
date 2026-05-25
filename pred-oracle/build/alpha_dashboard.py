"""Generate α dashboard slice (build/page_data/alpha/dashboard.json).

Aggregates the artifacts corpus to US-state and update-type counts in the
dashboard_window_days window. Filters out website-error/other update types.
"""

from __future__ import annotations

import json
import sys
from collections import Counter, defaultdict
from collections.abc import Iterator
from datetime import date
from pathlib import Path
from typing import Any

import yaml

# Allow running as `python build/alpha_dashboard.py` from the repo root
_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from build import _fields, _scoring  # noqa: E402

_US_STATE_NAMES: dict[str, str] = {
    "US-AL": "Alabama", "US-AK": "Alaska", "US-AZ": "Arizona", "US-AR": "Arkansas",
    "US-CA": "California", "US-CO": "Colorado", "US-CT": "Connecticut", "US-DE": "Delaware",
    "US-FL": "Florida", "US-GA": "Georgia", "US-HI": "Hawaii", "US-ID": "Idaho",
    "US-IL": "Illinois", "US-IN": "Indiana", "US-IA": "Iowa", "US-KS": "Kansas",
    "US-KY": "Kentucky", "US-LA": "Louisiana", "US-ME": "Maine", "US-MD": "Maryland",
    "US-MA": "Massachusetts", "US-MI": "Michigan", "US-MN": "Minnesota", "US-MS": "Mississippi",
    "US-MO": "Missouri", "US-MT": "Montana", "US-NE": "Nebraska", "US-NV": "Nevada",
    "US-NH": "New Hampshire", "US-NJ": "New Jersey", "US-NM": "New Mexico", "US-NY": "New York",
    "US-NC": "North Carolina", "US-ND": "North Dakota", "US-OH": "Ohio", "US-OK": "Oklahoma",
    "US-OR": "Oregon", "US-PA": "Pennsylvania", "US-RI": "Rhode Island", "US-SC": "South Carolina",
    "US-SD": "South Dakota", "US-TN": "Tennessee", "US-TX": "Texas", "US-UT": "Utah",
    "US-VT": "Vermont", "US-VA": "Virginia", "US-WA": "Washington", "US-WV": "West Virginia",
    "US-WI": "Wisconsin", "US-WY": "Wyoming", "US-DC": "District of Columbia",
    "US-PR": "Puerto Rico",
    "US-VI": "U.S. Virgin Islands",
    "US-GU": "Guam",
    "US-AS": "American Samoa",
    "US-MP": "Northern Mariana Islands",
}


def _iter_window(corpus_path: Path, window_days: int, today: date) -> Iterator[dict[str, Any]]:
    """Stream corpus records that pass the dashboard filter window."""
    with corpus_path.open() as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            rec = json.loads(line)
            if rec.get("update_type") in _scoring.EXCLUDED_UPDATE_TYPES:
                continue
            if not rec.get("pub_date_valid"):
                continue
            age = _fields.pub_date_age_days(rec, today=today)
            if age is None or age < 0 or age > window_days:
                continue
            yield rec


def generate(
    corpus_path: Path,
    curation_path: Path,
    out_path: Path,
    today: date | None = None,
) -> dict[str, Any]:
    """Write the α dashboard slice. Returns the dict for inspection."""
    today = today or date.today()
    curation = yaml.safe_load(curation_path.read_text())
    window_days = int(curation["dashboard_window_days"])

    state_count: Counter[str] = Counter()
    state_urgencies: dict[str, list[float]] = defaultdict(list)
    update_count: Counter[str] = Counter()
    intl_count: Counter[str] = Counter()
    us_fed_count = 0

    for rec in _iter_window(corpus_path, window_days=window_days, today=today):
        update_count[rec.get("update_type") or ""] += 1
        urg = _fields.urgency_score(rec)
        jurisdiction_list = _fields.jurisdictions(rec)
        for j in jurisdiction_list:
            if j.startswith("US-") and len(j) == 5:
                state_count[j] += 1
                state_urgencies[j].append(urg)
            elif j == "US":
                us_fed_count += 1
            elif len(j) == 2 and j.isalpha():
                # Bare 2-letter code: could be a US-state postal abbreviation OR an
                # ISO country code. Disambiguate against _US_STATE_NAMES.
                if f"US-{j}" in _US_STATE_NAMES:
                    state_count[f"US-{j}"] += 1
                    state_urgencies[f"US-{j}"].append(urg)
                else:
                    intl_count[j] += 1

    us_states_dto = [
        {
            "code": j[3:],  # strip "US-" prefix for ECharts ("CA" not "US-CA")
            "label": _US_STATE_NAMES.get(j, j),
            "count": n,
            "max_urgency": max(state_urgencies[j]) if state_urgencies[j] else 0,
        }
        for j, n in state_count.most_common()
    ]

    top_10 = [
        {
            "code": j,
            "label": _US_STATE_NAMES.get(j, j),
            "count": n,
            "max_urgency": max(state_urgencies[j]) if state_urgencies[j] else 0,
            "avg_urgency": round(sum(state_urgencies[j]) / len(state_urgencies[j]), 2)
            if state_urgencies[j] else 0,
        }
        for j, n in state_count.most_common(10)
    ]

    update_types_dto = [
        {"label": k or "(unspecified)", "count": v}
        for k, v in update_count.most_common()
    ]

    international = [
        {"code": code, "label": code, "count": n}
        for code, n in intl_count.most_common() if n >= 5
    ]

    slice_doc = {
        "scene": {"number": 1, "letter": "α", "back_href": "../"},
        "window": {"days": window_days, "label": f"last {window_days} days"},
        "us_states": us_states_dto,
        "top_10": top_10,
        "update_types": update_types_dto,
        "international": international,
        "totals": {
            "us_federal": us_fed_count,
            "us_state_sum": sum(state_count.values()),
            "international": sum(intl_count.values()),
        },
    }

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(slice_doc, indent=2))
    return slice_doc


if __name__ == "__main__":
    generate(
        corpus_path=_REPO_ROOT / "data" / "_scratch" / "artifacts.jsonl",
        curation_path=_REPO_ROOT / "data" / "alpha-curation.yml",
        out_path=_REPO_ROOT / "build" / "page_data" / "alpha" / "dashboard.json",
    )
