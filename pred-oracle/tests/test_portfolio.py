from __future__ import annotations
from build._portfolio import net_direction, portfolio_row


def test_net_direction_bullish_majority():
    events = [
        {"direction": "bullish", "pub_date": "2026-05-10"},
        {"direction": "bullish", "pub_date": "2026-05-11"},
        {"direction": "bullish", "pub_date": "2026-05-12"},
        {"direction": "bearish", "pub_date": "2026-05-13"},
    ]
    assert net_direction(events, window_days=30) == "Bullish"


def test_net_direction_mixed_on_close_split():
    events = [
        {"direction": "bullish", "pub_date": "2026-05-10"},
        {"direction": "bullish", "pub_date": "2026-05-11"},
        {"direction": "bearish", "pub_date": "2026-05-12"},
        {"direction": "bearish", "pub_date": "2026-05-13"},
    ]
    assert net_direction(events, window_days=30) == "Mixed"


def test_net_direction_bearish():
    events = [
        {"direction": "bearish", "pub_date": "2026-05-10"},
        {"direction": "bearish", "pub_date": "2026-05-11"},
        {"direction": "bearish", "pub_date": "2026-05-12"},
    ]
    assert net_direction(events, window_days=30) == "Bearish"


def test_net_direction_empty():
    assert net_direction([], window_days=30) == "Mixed"


def test_portfolio_row_shape():
    slice_doc = {
        "contract": {
            "id": "test",
            "platform": "kalshi",
            "title": "Test contract",
            "kind": "active",
            "expires_at": "2026-12-31",
            "heat": 42.5,
        },
        "position": {"side": "YES", "size": 100, "entry_price": 0.50},
        "timeline": [
            {
                "pub_date": "2026-05-10",
                "title": "Event one",
                "direction": "bullish",
                "magnitude": "high",
                "mechanism": "Binding Action",
            }
        ],
        "heat_panel": {
            "value": 42.5,
            "tier": "active",
            "delta_7d": 5.3,
            "peer_percentile": 72,
        },
    }
    row = portfolio_row(slice_doc, today="2026-05-25")
    assert row["contract_id"] == "test"
    assert row["heat_tier"] == "active"
    assert row["net_direction"] in ("Bullish", "Bearish", "Mixed")
    assert row["event_count_90d"] >= 0
    assert "latest_event" in row
