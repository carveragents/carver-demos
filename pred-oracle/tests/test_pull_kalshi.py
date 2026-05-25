"""Tests for Kalshi market-list parsing."""

from build.pull_kalshi import parse_market


def test_parse_market_extracts_required_fields() -> None:
    sample = {
        "ticker": "TIKTOKBAN-25APR30",
        "title": "Will TikTok be banned in the United States by April 30, 2025?",
        "subtitle": "",
        "open_time": "2025-01-15T00:00:00Z",
        "close_time": "2025-04-30T23:59:59Z",
        "status": "settled",
        "result": "no",
        "settlement_source": "Department of Commerce",
    }
    parsed = parse_market(sample)
    assert parsed["external_id"] == "TIKTOKBAN-25APR30"
    assert "TikTok" in parsed["title"]
    assert parsed["listed_at"].startswith("2025-01-15")
    assert parsed["status"] == "resolved"
    assert parsed["payload"] == sample
