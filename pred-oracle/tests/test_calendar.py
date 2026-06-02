from __future__ import annotations
from build._calendar import extract_calendar_events, calendar_month


def test_extract_calendar_events_from_enriched_slices():
    slices = [
        {
            "contract": {"id": "c1", "title": "Contract 1", "platform": "kalshi",
                         "expires_at": "2026-12-31"},
            "timeline": [
                {
                    "pub_date": "2026-05-10",
                    "title": "Event A",
                    "effective_date": "2026-06-15",
                    "direction": "bullish",
                    "magnitude": "high",
                    "high_impact": True,
                    "relevance_score": 8,
                },
                {
                    "pub_date": "2026-05-12",
                    "title": "Event B",
                    "direction": "bearish",
                    "magnitude": "low",
                    "high_impact": False,
                    "relevance_score": 6,
                },
            ],
        }
    ]
    events = extract_calendar_events(slices)
    dated = [e for e in events if e.get("calendar_date")]
    assert any(e["calendar_date"] == "2026-06-15" for e in dated)
    assert any(e["calendar_date"] == "2026-12-31" for e in dated)


def test_calendar_month_structure():
    events = [
        {"calendar_date": "2026-06-15", "type": "effective_date",
         "title": "Rule effective", "contract_id": "c1"},
    ]
    month = calendar_month(2026, 6, events)
    assert month["year"] == 2026
    assert month["month"] == 6
    assert isinstance(month["weeks"], list)
    assert len(month["weeks"]) >= 4
