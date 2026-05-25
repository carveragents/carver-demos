"""Tests for Polymarket Gamma-API market parsing."""

from build.pull_polymarket import parse_market


def test_parse_market_extracts_required_fields() -> None:
    sample = {
        "id": "12345",
        "slug": "solana-etf-approved-in-2025",
        "question": "Will the SEC approve a spot Solana ETF in 2025?",
        "description": "Resolves YES if the SEC...",
        "startDate": "2024-08-01T00:00:00Z",
        "endDate": "2025-12-31T23:59:59Z",
        "closed": True,
        "outcomePrices": "[0.85, 0.15]",  # preserved via payload; not extracted
        "tags": [{"label": "Crypto"}, {"label": "Regulation"}],
    }
    parsed = parse_market(sample)
    assert parsed["external_id"] == "12345"
    assert "Solana" in parsed["title"]
    assert parsed["status"] == "resolved"
    assert parsed["platform"] == "polymarket"
    assert parsed["payload"] == sample
