"""Sanity check for the make_contract factory."""
from tests.conftest import make_contract


def test_make_contract_returns_minimal_active_contract() -> None:
    c = make_contract()
    assert c["id"]
    assert c["platform"] in {"kalshi", "polymarket"}
    assert c["kind"] in {"active", "retrospective"}
    assert c["status"] in {"active", "resolved"}
    assert isinstance(c["settlement_entities"], list)


def test_make_contract_overrides_apply() -> None:
    c = make_contract(id="x-1", platform="polymarket", kind="retrospective",
                      title="Custom", settlement_entities=["SEC"])
    assert c["id"] == "x-1"
    assert c["platform"] == "polymarket"
    assert c["kind"] == "retrospective"
    assert c["title"] == "Custom"
    assert c["settlement_entities"] == ["SEC"]
