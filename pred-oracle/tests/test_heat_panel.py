"""Tests for build/_heat_panel.py — pure computation only."""
from __future__ import annotations


def test_tier_for_thresholds() -> None:
    from build._heat_panel import tier_for
    assert tier_for(0) == "dormant"
    assert tier_for(9.99) == "dormant"
    assert tier_for(10) == "watch"
    assert tier_for(29.99) == "watch"
    assert tier_for(30) == "active"
    assert tier_for(69.99) == "active"
    assert tier_for(70) == "critical"
    assert tier_for(150) == "critical"


def test_peer_percentile_handles_self_inclusion() -> None:
    from build._heat_panel import peer_percentile
    assert peer_percentile(50, [10, 20, 30, 50, 70]) == 80  # 4 of 5 ≤ 50
    assert peer_percentile(100, [10, 20, 30]) == 100        # above all peers
    assert peer_percentile(0, [10, 20, 30]) == 0            # value below all peers → 0th percentile


def test_peer_percentile_empty_peers_returns_zero() -> None:
    from build._heat_panel import peer_percentile
    assert peer_percentile(50, []) == 0


def test_urgency_weighted_sparkline_sums_urgency_per_day() -> None:
    from datetime import date

    from build._heat_panel import urgency_weighted_sparkline

    today = date(2026, 5, 20)
    records = [
        {"pub_date": "2026-05-20", "pub_date_valid": True, "scores": {"urgency": {"score": 8}}},
        {"pub_date": "2026-05-20", "pub_date_valid": True, "scores": {"urgency": {"score": 4}}},
        {"pub_date": "2026-05-18", "pub_date_valid": True, "scores": {"urgency": {"score": 6}}},
        {"pub_date": "2026-05-07", "pub_date_valid": True, "scores": {"urgency": {"score": 9}}},
    ]
    spark = urgency_weighted_sparkline(records, today=today, days=14)
    assert len(spark) == 14
    assert spark[-1] == 12  # today: 8 + 4
    assert spark[-3] == 6   # today - 2
    assert spark[0] == 9    # today - 13
    assert spark[5] == 0    # an idle day


def test_build_panel_assembles_all_fields(
    tmp_path, monkeypatch,
) -> None:
    from datetime import date
    from pathlib import Path

    from build._heat_panel import build

    fixture_cache = Path(__file__).parent / "fixtures" / "llm"

    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    panel = build(
        contract_id="ttb",
        heat_value=56.0,
        heat_value_7d_ago=37.7,
        peers=[10.0, 20.0, 40.0, 56.0, 80.0],
        records=[
            {"pub_date": "2025-04-29", "pub_date_valid": True,
             "scores": {"urgency": {"score": 8}}, "title": "X"},
        ],
        today=date(2025, 4, 30),
        cache_root=fixture_cache,
    )
    assert panel["value"] == 56.0
    assert panel["tier"] == "active"
    assert panel["delta_7d"] == 18.3
    assert panel["peer_percentile"] == 80  # 4 of 5 ≤ 56
    assert len(panel["urgency_weighted_sparkline"]) == 14
    assert "primary_drivers" in panel
    assert "explainer" in panel
