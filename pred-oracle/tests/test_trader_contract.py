# tests/test_trader_contract.py
from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import yaml

from tests.conftest import make_row


def _write_corpus(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w") as f:
        for r in rows:
            f.write(json.dumps(r) + "\n")


def _write_trader_curation(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    doc = {
        "schema_version": 1,
        "build_date": "2026-05-25",
        "portfolio": [
            {
                "id": "test-contract",
                "platform": "kalshi",
                "kind": "active",
                "position": {"side": "YES", "size": 100, "entry_price": 0.50},
            }
        ],
        "retrospectives": [],
    }
    path.write_text(yaml.dump(doc))


def _write_kalshi_contracts(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    doc = {
        "schema_version": 1,
        "picks": [
            {
                "id": "test-contract",
                "source_lookup": {"event_ticker": "TEST"},
                "cached": {
                    "title": "Will test thing happen?",
                    "subtitle": "",
                    "resolution_criteria": "Resolves YES if test thing happens.",
                    "ticker": "TEST-TICKER",
                    "status": "active",
                    "listed_at": "2026-01-01T00:00:00Z",
                    "expires_at": "2026-12-31T00:00:00Z",
                    "settlement_entities": ["Test Entity"],
                },
                "last_pulled_at": "2026-05-25T00:00:00Z",
            }
        ],
    }
    path.write_text(yaml.dump(doc))


def _write_polymarket_contracts(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    doc = {"schema_version": 1, "picks": []}
    path.write_text(yaml.dump(doc))


def test_generate_produces_slice_file(tmp_path: Path):
    corpus_path = tmp_path / "corpus.jsonl"
    _write_corpus(corpus_path, [
        make_row(
            feed_entry_id="e1",
            title="Test Entity enforcement action",
            entities=["Test Entity"],
            pub_date="2026-05-10",
            pub_date_valid=True,
        ),
    ])
    _write_trader_curation(tmp_path / "trader-curation.yml")
    _write_kalshi_contracts(tmp_path / "kalshi" / "contracts.yml")
    _write_polymarket_contracts(tmp_path / "polymarket" / "contracts.yml")

    from build.trader_contract import generate

    paths = generate(
        corpus_path=corpus_path,
        trader_curation_path=tmp_path / "trader-curation.yml",
        kalshi_contracts_path=tmp_path / "kalshi" / "contracts.yml",
        polymarket_contracts_path=tmp_path / "polymarket" / "contracts.yml",
        retrospectives_root=tmp_path,
        out_dir=tmp_path / "out",
        today=date(2026, 5, 25),
    )
    assert len(paths) == 1
    assert paths[0].name == "test-contract.json"

    doc = json.loads(paths[0].read_text())
    assert doc["contract"]["id"] == "test-contract"
    assert doc["contract"]["title"] == "Will test thing happen?"
    assert isinstance(doc["timeline"], list)
    assert isinstance(doc["contract"]["heat"], (int, float))


def test_generate_includes_position_data(tmp_path: Path):
    corpus_path = tmp_path / "corpus.jsonl"
    _write_corpus(corpus_path, [make_row(entities=["Test Entity"])])
    _write_trader_curation(tmp_path / "trader-curation.yml")
    _write_kalshi_contracts(tmp_path / "kalshi" / "contracts.yml")
    _write_polymarket_contracts(tmp_path / "polymarket" / "contracts.yml")

    from build.trader_contract import generate

    paths = generate(
        corpus_path=corpus_path,
        trader_curation_path=tmp_path / "trader-curation.yml",
        kalshi_contracts_path=tmp_path / "kalshi" / "contracts.yml",
        polymarket_contracts_path=tmp_path / "polymarket" / "contracts.yml",
        retrospectives_root=tmp_path,
        out_dir=tmp_path / "out",
        today=date(2026, 5, 25),
    )
    doc = json.loads(paths[0].read_text())
    assert doc["position"]["side"] == "YES"
    assert doc["position"]["size"] == 100
    assert doc["position"]["entry_price"] == 0.50
