# Trader Dashboard Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a Carver-enhanced trader dashboard — a static demo site showing per-contract regulatory intelligence for prediction market traders.

**Architecture:** Static site (Jinja2 templates + Tailwind + ECharts + Alpine.js) built from Carver corpus + LLM enrichments + real probability data from Kalshi/Polymarket APIs. Follows the exact same slice → enrich → render pipeline as the existing gamma demo. New modules extend (not replace) the existing build infrastructure.

**Tech Stack:** Python 3.10, Jinja2, PyYAML, httpx, OpenAI API (gpt-5/gpt-5-mini), Tailwind CDN, ECharts 5.5, Alpine.js 3.13. Runtime: `uv run`. Tests: `pytest`.

**Design Spec:** `docs/superpowers/specs/2026-05-25-trader-dashboard-design.md`

---

## File Map

### New data files
- `data/trader-curation.yml` — portfolio picks, synthetic positions, build config
- `data/platforms/polymarket/contracts/sec-eth-security-2026.yml` — retrospective-style YAML for new contract
- `data/platforms/polymarket/contracts/fatf-travel-rule-2027.yml` — new contract
- `data/platforms/kalshi/contracts/kxuschina-tariffs-2026.yml` — new contract

### New build modules
- `build/_mechanism.py` — deterministic mechanism classifier (update_type → binding/signal/context)
- `build/_prices.py` — fetch + cache probability time series from Kalshi/Polymarket APIs
- `build/trader_contract.py` — slice generator (corpus → per-contract JSON)
- `build/trader_contract_enrich.py` — enrichment orchestrator (adds LLM fields to slices)
- `build/_portfolio.py` — portfolio-level aggregation (net direction, sort/filter data)
- `build/_calendar.py` — calendar data extraction (future-dated events across contracts)
- `build/trader_site.py` — Jinja2 renderer for all trader pages

### Modified build modules
- `build/_relevance.py` — extend output schema with direction, magnitude, timeline_shift
- `build/generate_slices.py` — add trader slice generation block
- `build/generate.py` — add trader template routing

### New templates
- `build/templates/trader/_base.html` — trader layout (extends site base.html, adds trader nav)
- `build/templates/trader/list.html` — portfolio list view
- `build/templates/trader/calendar.html` — portfolio calendar view
- `build/templates/trader/briefing.html` — contract briefing (active + retrospective)
- `build/templates/trader/retrospectives.html` — case studies landing

### New test files
- `tests/test_mechanism.py`
- `tests/test_relevance_direction.py`
- `tests/test_prices.py`
- `tests/test_trader_contract.py`
- `tests/test_trader_contract_enrich.py`
- `tests/test_portfolio.py`
- `tests/test_calendar.py`
- `tests/test_trader_curation.py`
- `tests/test_trader_templates.py`

---

## Task 1: Contract Data Files

**Files:**
- Create: `data/platforms/kalshi/contracts/kxuschina-tariffs-2026.yml`
- Create: `data/platforms/polymarket/contracts/sec-eth-security-2026.yml`
- Create: `data/platforms/polymarket/contracts/fatf-travel-rule-2027.yml`
- Create: `data/trader-curation.yml`
- Create: `tests/test_trader_curation.py`

These are the 3 new contracts and the trader portfolio curation file. Each contract YAML follows the existing schema from `data/platforms/polymarket/contracts/solana-etf-2025.yml`.

- [ ] **Step 1: Create the Kalshi tariffs contract YAML**

```yaml
# data/platforms/kalshi/contracts/kxuschina-tariffs-2026.yml
schema_version: 1
kind: "active"
platform: "kalshi"
id: "kxuschina-tariffs-2026"

title: "Will US tariffs on Chinese goods exceed 60% average effective rate in 2026?"
resolution_criteria: |
  Resolves YES if the Office of the United States Trade Representative publishes
  an official notice, or the Department of Commerce issues a Federal Register
  determination, establishing that the average effective US tariff rate on imports
  from China exceeds 60.0% at any point between 2026-01-01 and 2026-12-31.

listed_at: "2026-02-01"
expires_at: "2026-12-31"
status: "active"

settlement_entities:
  - "Office of the United States Trade Representative"
  - "Department of Commerce"
  - "Bureau of Industry and Security"
  - "Office of Foreign Assets Control"
  - "Department of the Treasury"

source_urls:
  - "https://ustr.gov/"
  - "https://www.commerce.gov/"

source_retrieved_at: "2026-05-25"
```

- [ ] **Step 2: Create the Polymarket SEC/ETH contract YAML**

```yaml
# data/platforms/polymarket/contracts/sec-eth-security-2026.yml
schema_version: 1
kind: "active"
platform: "polymarket"
id: "sec-eth-security-2026"

title: "Will the SEC officially classify Ether as a security by 2026-12-31?"
resolution_criteria: |
  Resolves YES if the U.S. Securities and Exchange Commission issues a formal
  order, final rule, or sustained civil enforcement judgment concluding that
  Ether (ETH) is a security under the Securities Act of 1933 or the Securities
  Exchange Act of 1934, on or before 2026-12-31.

listed_at: "2025-06-01"
expires_at: "2026-12-31"
status: "active"

settlement_entities:
  - "U.S. Securities and Exchange Commission"
  - "Commodity Futures Trading Commission"
  - "Coinbase"
  - "Consensys"
  - "Ethereum Foundation"

source_urls:
  - "https://www.sec.gov/"

source_retrieved_at: "2026-05-25"
```

- [ ] **Step 3: Create the Polymarket FATF contract YAML**

```yaml
# data/platforms/polymarket/contracts/fatf-travel-rule-2027.yml
schema_version: 1
kind: "active"
platform: "polymarket"
id: "fatf-travel-rule-2027"

title: "Will 25+ FATF member states formally adopt updated VASP Travel Rule guidance by 2027-06-30?"
resolution_criteria: |
  Resolves YES if 25 or more of the 39 FATF full-member jurisdictions have
  officially transposed the Q4 2025 FATF Recommendation-15 update (expanded
  VASP-adjacent perimeter) into domestic law, regulation, or supervisory
  guidance, as confirmed by FATF's own mutual evaluation or implementation
  monitoring report, by 2027-06-30.

listed_at: "2025-12-01"
expires_at: "2027-06-30"
status: "active"

settlement_entities:
  - "Financial Action Task Force"
  - "European Securities and Markets Authority"
  - "European Commission"
  - "Financial Crimes Enforcement Network"
  - "Bank for International Settlements"

source_urls:
  - "https://www.fatf-gafi.org/"

source_retrieved_at: "2026-05-25"
```

- [ ] **Step 4: Create the trader curation YAML**

```yaml
# data/trader-curation.yml
schema_version: 1
build_date: "2026-05-25"

portfolio:
  - id: kxbtc-maxprice-2026
    platform: kalshi
    kind: active
    position: {side: "YES", size: 200, entry_price: 0.54}
  - id: kxfeddecision-28jan
    platform: kalshi
    kind: active
    position: {side: "NO", size: 100, entry_price: 0.71}
  - id: us-recession-in-2026
    platform: polymarket
    kind: active
    position: {side: "YES", size: 500, entry_price: 0.18}
  - id: sec-eth-security-2026
    platform: polymarket
    kind: active
    position: {side: "YES", size: 150, entry_price: 0.33}
  - id: kxuschina-tariffs-2026
    platform: kalshi
    kind: active
    position: {side: "YES", size: 300, entry_price: 0.47}
  - id: fatf-travel-rule-2027
    platform: polymarket
    kind: active
    position: {side: "YES", size: 100, entry_price: 0.61}

retrospectives:
  - id: solana-etf-2025
    platform: polymarket
  - id: tiktokban-25apr30
    platform: kalshi
```

- [ ] **Step 5: Write curation validation test**

```python
# tests/test_trader_curation.py
from __future__ import annotations
from pathlib import Path
import yaml

REPO = Path(__file__).resolve().parent.parent
CURATION = REPO / "data" / "trader-curation.yml"


def test_trader_curation_loads():
    doc = yaml.safe_load(CURATION.read_text())
    assert doc["schema_version"] == 1
    assert "portfolio" in doc
    assert "retrospectives" in doc


def test_portfolio_has_six_contracts():
    doc = yaml.safe_load(CURATION.read_text())
    assert len(doc["portfolio"]) == 6


def test_portfolio_entries_have_required_keys():
    doc = yaml.safe_load(CURATION.read_text())
    for entry in doc["portfolio"]:
        assert "id" in entry
        assert "platform" in entry
        assert entry["platform"] in ("kalshi", "polymarket")
        assert "kind" in entry
        assert "position" in entry
        pos = entry["position"]
        assert pos["side"] in ("YES", "NO")
        assert isinstance(pos["size"], int)
        assert isinstance(pos["entry_price"], (int, float))


def test_retrospectives_has_two_entries():
    doc = yaml.safe_load(CURATION.read_text())
    assert len(doc["retrospectives"]) == 2


def test_new_contract_yamls_exist():
    for path in [
        REPO / "data" / "platforms" / "kalshi" / "contracts" / "kxuschina-tariffs-2026.yml",
        REPO / "data" / "platforms" / "polymarket" / "contracts" / "sec-eth-security-2026.yml",
        REPO / "data" / "platforms" / "polymarket" / "contracts" / "fatf-travel-rule-2027.yml",
    ]:
        assert path.exists(), f"Missing: {path}"
        doc = yaml.safe_load(path.read_text())
        assert doc["schema_version"] == 1
        assert isinstance(doc["settlement_entities"], list)
        assert len(doc["settlement_entities"]) >= 3
```

- [ ] **Step 6: Run tests**

Run: `cd pred-oracle && uv run pytest tests/test_trader_curation.py -v`
Expected: all 5 tests PASS

- [ ] **Step 7: Commit**

```bash
git add data/trader-curation.yml \
  data/platforms/kalshi/contracts/kxuschina-tariffs-2026.yml \
  data/platforms/polymarket/contracts/sec-eth-security-2026.yml \
  data/platforms/polymarket/contracts/fatf-travel-rule-2027.yml \
  tests/test_trader_curation.py
git commit -m "feat(trader): add contract YAMLs and curation file for trader dashboard"
```

---

## Task 2: Mechanism Classifier

**Files:**
- Create: `build/_mechanism.py`
- Create: `tests/test_mechanism.py`

Pure deterministic lookup from `update_type` to mechanism label. No LLM, no external deps.

- [ ] **Step 1: Write failing tests**

```python
# tests/test_mechanism.py
from __future__ import annotations

from build._mechanism import classify, BINDING_ACTION, SIGNAL, CONTEXT


def test_enforcement_is_binding():
    assert classify("enforcement") == BINDING_ACTION


def test_final_rule_is_binding():
    assert classify("final rule") == BINDING_ACTION


def test_proposed_rule_is_signal():
    assert classify("proposed rule") == SIGNAL


def test_advisory_is_signal():
    assert classify("advisory") == SIGNAL


def test_guidance_is_signal():
    assert classify("guidance") == SIGNAL


def test_comment_request_is_signal():
    assert classify("comment request") == SIGNAL


def test_speech_is_context():
    assert classify("speech") == CONTEXT


def test_press_release_is_context():
    assert classify("press release") == CONTEXT


def test_bulletin_is_context():
    assert classify("bulletin") == CONTEXT


def test_trend_report_is_context():
    assert classify("trend report") == CONTEXT


def test_standard_is_context():
    assert classify("standard") == CONTEXT


def test_insights_is_context():
    assert classify("insights") == CONTEXT


def test_event_announcement_is_context():
    assert classify("event announcement") == CONTEXT


def test_newsletter_is_context():
    assert classify("newsletter") == CONTEXT


def test_unknown_defaults_to_context():
    assert classify("something_new") == CONTEXT


def test_empty_string_defaults_to_context():
    assert classify("") == CONTEXT
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd pred-oracle && uv run pytest tests/test_mechanism.py -v`
Expected: ImportError — `build._mechanism` does not exist

- [ ] **Step 3: Implement the module**

```python
# build/_mechanism.py
"""Deterministic mechanism classification from Carver update_type."""
from __future__ import annotations

BINDING_ACTION = "Binding Action"
SIGNAL = "Signal"
CONTEXT = "Context"

_LOOKUP: dict[str, str] = {
    "enforcement": BINDING_ACTION,
    "final rule": BINDING_ACTION,
    "proposed rule": SIGNAL,
    "advisory": SIGNAL,
    "guidance": SIGNAL,
    "comment request": SIGNAL,
    "speech": CONTEXT,
    "press release": CONTEXT,
    "bulletin": CONTEXT,
    "trend report": CONTEXT,
    "standard": CONTEXT,
    "insights": CONTEXT,
    "event announcement": CONTEXT,
    "newsletter": CONTEXT,
}


def classify(update_type: str) -> str:
    return _LOOKUP.get(update_type, CONTEXT)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd pred-oracle && uv run pytest tests/test_mechanism.py -v`
Expected: all 16 tests PASS

- [ ] **Step 5: Commit**

```bash
git add build/_mechanism.py tests/test_mechanism.py
git commit -m "feat(trader): add deterministic mechanism classifier"
```

---

## Task 3: Extend Relevance Schema with Directional Impact

**Files:**
- Modify: `build/_relevance.py` — extend `SYSTEM_PROMPT`, `build_schema()`, `_heuristic_judgment()`
- Create: `tests/test_relevance_direction.py`

The existing relevance LLM call is extended to also return `direction`, `magnitude`, and `timeline_shift`. This is the same call (not a new one) — just a wider output schema. The cache key changes because the schema changes, so new LLM calls will be made for trader contracts while gamma contracts keep their existing cache.

- [ ] **Step 1: Write test for the extended schema**

```python
# tests/test_relevance_direction.py
from __future__ import annotations

from build._relevance import build_schema, _heuristic_judgment


def test_schema_includes_direction_field():
    conditions = [{"id": "A", "label": "test", "summary": "test summary"}]
    schema = build_schema(conditions)
    props = schema["properties"]
    assert "direction" in props
    assert set(props["direction"]["enum"]) == {"bullish", "bearish", "neutral"}


def test_schema_includes_magnitude_field():
    conditions = [{"id": "A", "label": "test", "summary": "test summary"}]
    schema = build_schema(conditions)
    props = schema["properties"]
    assert "magnitude" in props
    assert set(props["magnitude"]["enum"]) == {"high", "medium", "low"}


def test_schema_includes_timeline_shift_field():
    conditions = [{"id": "A", "label": "test", "summary": "test summary"}]
    schema = build_schema(conditions)
    props = schema["properties"]
    assert "timeline_shift" in props
    assert set(props["timeline_shift"]["enum"]) == {"sooner", "later", "none"}


def test_all_new_fields_are_required():
    conditions = [{"id": "A", "label": "test", "summary": "test summary"}]
    schema = build_schema(conditions)
    required = schema["required"]
    assert "direction" in required
    assert "magnitude" in required
    assert "timeline_shift" in required


def test_heuristic_includes_direction_fields():
    rec = {
        "scores": {"urgency": {"score": 7, "label": "high"}},
        "entities": ["SEC"],
        "topic_name": "SEC",
    }
    result = _heuristic_judgment(rec)
    assert result["direction"] == "neutral"
    assert result["magnitude"] == "low"
    assert result["timeline_shift"] == "none"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd pred-oracle && uv run pytest tests/test_relevance_direction.py -v`
Expected: FAIL — schema does not have `direction` key, heuristic does not return `direction`

- [ ] **Step 3: Modify `build/_relevance.py`**

Three changes to the existing file:

**Change A — Update `SYSTEM_PROMPT`:** Append to the existing system prompt string:

```
" Also judge directionality: does this event make YES resolution more likely (bullish), less likely (bearish), or neither (neutral)? Judge magnitude: high = materially changes probability, medium = notable but not decisive, low = incremental signal. Judge timeline shift: does this event suggest resolution will come sooner or later than expected, or no change (none)?"
```

**Change B — Extend `build_schema()`:** Add three new properties to the schema dict's `"properties"` and add them to `"required"`:

```python
"direction": {
    "type": "string",
    "enum": ["bullish", "bearish", "neutral"],
},
"magnitude": {
    "type": "string",
    "enum": ["high", "medium", "low"],
},
"timeline_shift": {
    "type": "string",
    "enum": ["sooner", "later", "none"],
},
```

Add `"direction"`, `"magnitude"`, `"timeline_shift"` to the `"required"` list.

**Change C — Extend `_heuristic_judgment()`:** Add three keys to the returned dict:

```python
"direction": "neutral",
"magnitude": "low",
"timeline_shift": "none",
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd pred-oracle && uv run pytest tests/test_relevance_direction.py -v`
Expected: all 5 tests PASS

- [ ] **Step 5: Run existing relevance tests to check for regressions**

Run: `cd pred-oracle && uv run pytest tests/ -k relevance -v`
Expected: all existing relevance tests still PASS (the heuristic fallback tests may need updating if they assert exact dict shape — check and fix if needed)

- [ ] **Step 6: Commit**

```bash
git add build/_relevance.py tests/test_relevance_direction.py
git commit -m "feat(trader): extend relevance schema with direction, magnitude, timeline_shift"
```

---

## Task 4: Price Fetcher

**Files:**
- Create: `build/_prices.py`
- Create: `tests/test_prices.py`

Fetches and caches probability time series from Kalshi and Polymarket public APIs. Uses `httpx` (already in dependencies). Cache pattern mirrors `_llm.py` — JSON files committed to git under `build/_cache/prices/`.

- [ ] **Step 1: Write tests**

```python
# tests/test_prices.py
from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch, MagicMock

from build._prices import (
    normalize_kalshi_candles,
    normalize_polymarket_history,
    load_cached,
    save_cache,
    PriceData,
)


def test_normalize_kalshi_candles():
    raw = [
        {"end_period_ts": 1700000000, "price": {"close": "0.5500"}, "volume": "10"},
        {"end_period_ts": 1700086400, "price": {"close": "0.6200"}, "volume": "5"},
    ]
    result = normalize_kalshi_candles(raw)
    assert len(result) == 2
    assert result[0] == {"t": 1700000000, "p": 0.55}
    assert result[1] == {"t": 1700086400, "p": 0.62}


def test_normalize_polymarket_history():
    raw = [
        {"t": 1700000000, "p": 0.45},
        {"t": 1700086400, "p": 0.51},
    ]
    result = normalize_polymarket_history(raw)
    assert result == raw


def test_cache_round_trip(tmp_path: Path):
    data = PriceData(
        contract_id="test-contract",
        platform="kalshi",
        ticker="TEST-TICKER",
        fetched_at="2026-05-25",
        series=[{"t": 1700000000, "p": 0.55}],
    )
    save_cache(data, cache_dir=tmp_path)
    loaded = load_cached("test-contract", cache_dir=tmp_path)
    assert loaded is not None
    assert loaded.contract_id == "test-contract"
    assert loaded.series == [{"t": 1700000000, "p": 0.55}]


def test_load_cached_returns_none_when_missing(tmp_path: Path):
    result = load_cached("nonexistent", cache_dir=tmp_path)
    assert result is None
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd pred-oracle && uv run pytest tests/test_prices.py -v`
Expected: ImportError — `build._prices` does not exist

- [ ] **Step 3: Implement `build/_prices.py`**

```python
# build/_prices.py
"""Fetch + cache probability time series from Kalshi and Polymarket APIs."""
from __future__ import annotations

import json
from dataclasses import dataclass, asdict
from datetime import date
from pathlib import Path
from typing import Any

import httpx

DEFAULT_CACHE_DIR = Path(__file__).resolve().parent / "_cache" / "prices"

KALSHI_BASE = "https://external-api.kalshi.com/trade-api/v2"
KALSHI_HISTORICAL_BASE = "https://external-api.kalshi.com/trade-api/v2/historical"
POLYMARKET_CLOB_BASE = "https://clob.polymarket.com"
POLYMARKET_GAMMA_BASE = "https://gamma-api.polymarket.com"


@dataclass
class PriceData:
    contract_id: str
    platform: str
    ticker: str
    fetched_at: str
    series: list[dict[str, Any]]


def normalize_kalshi_candles(candles: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {"t": c["end_period_ts"], "p": float(c["price"]["close"])}
        for c in candles
        if "price" in c and "close" in c["price"]
    ]


def normalize_polymarket_history(history: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [{"t": h["t"], "p": h["p"]} for h in history]


def save_cache(data: PriceData, *, cache_dir: Path = DEFAULT_CACHE_DIR) -> Path:
    cache_dir.mkdir(parents=True, exist_ok=True)
    path = cache_dir / f"{data.contract_id}.json"
    path.write_text(json.dumps(asdict(data), indent=2))
    return path


def load_cached(
    contract_id: str, *, cache_dir: Path = DEFAULT_CACHE_DIR,
) -> PriceData | None:
    path = cache_dir / f"{contract_id}.json"
    if not path.exists():
        return None
    raw = json.loads(path.read_text())
    return PriceData(**raw)


def fetch_kalshi(
    *,
    ticker: str,
    start_ts: int,
    end_ts: int,
    is_historical: bool = False,
) -> list[dict[str, Any]]:
    if is_historical:
        url = f"{KALSHI_HISTORICAL_BASE}/markets/{ticker}/candlesticks"
    else:
        url = f"{KALSHI_BASE}/series/{ticker}/markets/{ticker}/candlesticks"
    params = {"period_interval": 1440, "start_ts": start_ts, "end_ts": end_ts}
    resp = httpx.get(url, params=params, timeout=30)
    resp.raise_for_status()
    return resp.json().get("candlesticks", [])


def fetch_polymarket(
    *, slug: str, condition_id: str = "",
) -> list[dict[str, Any]]:
    gamma_resp = httpx.get(
        f"{POLYMARKET_GAMMA_BASE}/markets",
        params={"slug": slug},
        timeout=30,
    )
    gamma_resp.raise_for_status()
    markets = gamma_resp.json()
    if not markets:
        return []
    market = markets[0] if isinstance(markets, list) else markets
    token_ids = market.get("clobTokenIds", [])
    if not token_ids:
        return []
    token_id = token_ids[0]
    price_resp = httpx.get(
        f"{POLYMARKET_CLOB_BASE}/prices-history",
        params={"market": token_id, "interval": "max", "fidelity": 720},
        timeout=30,
    )
    price_resp.raise_for_status()
    return price_resp.json().get("history", [])


def fetch_and_cache(
    *,
    contract_id: str,
    platform: str,
    ticker: str,
    slug: str = "",
    start_ts: int = 0,
    end_ts: int = 0,
    is_historical: bool = False,
    cache_dir: Path = DEFAULT_CACHE_DIR,
) -> PriceData:
    cached = load_cached(contract_id, cache_dir=cache_dir)
    if cached is not None:
        return cached

    if platform == "kalshi":
        raw = fetch_kalshi(
            ticker=ticker, start_ts=start_ts, end_ts=end_ts,
            is_historical=is_historical,
        )
        series = normalize_kalshi_candles(raw)
    elif platform == "polymarket":
        raw = fetch_polymarket(slug=slug or contract_id)
        series = normalize_polymarket_history(raw)
    else:
        series = []

    data = PriceData(
        contract_id=contract_id,
        platform=platform,
        ticker=ticker,
        fetched_at=date.today().isoformat(),
        series=series,
    )
    save_cache(data, cache_dir=cache_dir)
    return data
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd pred-oracle && uv run pytest tests/test_prices.py -v`
Expected: all 4 tests PASS

- [ ] **Step 5: Commit**

```bash
git add build/_prices.py tests/test_prices.py
git commit -m "feat(trader): add price fetcher with Kalshi/Polymarket API support"
```

---

## Task 5: Trader Contract Slice Generator

**Files:**
- Create: `build/trader_contract.py`
- Create: `tests/test_trader_contract.py`

Mirrors `build/gamma_contract.py` but reads from `data/trader-curation.yml`. Produces one JSON slice per portfolio contract under `build/page_data/trader/contracts/`. Reuses `_heat.entity_match`, `_heat.heat_score`, `_heat.sparkline_buckets`, `_fields.*`.

- [ ] **Step 1: Write tests**

```python
# tests/test_trader_contract.py
from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import yaml

from conftest import make_row


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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd pred-oracle && uv run pytest tests/test_trader_contract.py -v`
Expected: ImportError — `build.trader_contract` does not exist

- [ ] **Step 3: Implement `build/trader_contract.py`**

Follow the exact same pattern as `build/gamma_contract.py`. Key differences:
- Reads `data/trader-curation.yml` instead of `data/gamma-curation.yml`
- Includes `position` dict in each slice (from curation YAML)
- No `open_tickets` or `scene` fields (trader demo doesn't use those)
- Output shape:

```python
{
    "contract": {
        "id", "platform", "kind", "title", "subtitle", "external_id",
        "status", "listed_at", "expires_at", "resolved_at",
        "resolution_criteria", "resolution_outcome",
        "settlement_entities": [{"name": str, "role": str}],
        "source_urls", "primary_source_url",
        "heat": float,
        "heat_history": list[int],
    },
    "position": {"side": str, "size": int, "entry_price": float},
    "timeline": [
        {
            "pub_date", "title", "regulator", "url",
            "urgency", "impact", "matched_entity",
            "carver_feed_entry_id",
        }
    ],
}
```

Use `gamma_contract.py` as the reference implementation — reuse `_stream_corpus`, `_entity_role`, `_parse_date`, `_window_for`, `_build_timeline` logic (import from `gamma_contract` or duplicate — prefer duplication if it keeps the modules independent). The `generate()` function signature:

```python
def generate(
    *,
    corpus_path: Path,
    trader_curation_path: Path,
    kalshi_contracts_path: Path,
    polymarket_contracts_path: Path,
    retrospectives_root: Path,
    out_dir: Path,
    today: date | None = None,
) -> list[Path]
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd pred-oracle && uv run pytest tests/test_trader_contract.py -v`
Expected: both tests PASS

- [ ] **Step 5: Commit**

```bash
git add build/trader_contract.py tests/test_trader_contract.py
git commit -m "feat(trader): add trader contract slice generator"
```

---

## Task 6: Trader Contract Enrichment Orchestrator

**Files:**
- Create: `build/trader_contract_enrich.py`
- Create: `tests/test_trader_contract_enrich.py`

Mirrors `build/gamma_contract_enrich.py`. Same 4-step pipeline (thesis → relevance → heat_panel → narrative) but the enriched timeline events now include `direction`, `magnitude`, `timeline_shift` (from the extended relevance schema) and `mechanism` (from `_mechanism.py`).

- [ ] **Step 1: Write tests**

```python
# tests/test_trader_contract_enrich.py
from __future__ import annotations

from datetime import date
from build._mechanism import classify, BINDING_ACTION, SIGNAL, CONTEXT


def _make_slice_doc():
    return {
        "contract": {
            "id": "test-contract",
            "platform": "kalshi",
            "kind": "active",
            "title": "Will test happen?",
            "resolution_criteria": "Resolves YES if test happens.",
            "settlement_entities": [{"name": "Test Entity", "role": "regulator"}],
        },
        "position": {"side": "YES", "size": 100, "entry_price": 0.50},
        "timeline": [
            {
                "pub_date": "2026-05-10",
                "title": "Test enforcement",
                "regulator": "Test Entity",
                "url": "https://example.com",
                "urgency": 8.0,
                "impact": 7.0,
                "matched_entity": "Test Entity",
                "carver_feed_entry_id": "e1",
            }
        ],
    }


def test_mechanism_applied_to_enriched_timeline():
    assert classify("enforcement") == BINDING_ACTION
    assert classify("proposed rule") == SIGNAL
    assert classify("speech") == CONTEXT


def test_project_timeline_fields_includes_direction():
    from build.trader_contract_enrich import _project_timeline_fields

    judged = [
        {
            "pub_date": "2026-05-10",
            "pub_date_valid": True,
            "title": "Test",
            "link": "https://x",
            "regulator_name": "Test Entity",
            "regulator_division": "",
            "topic_name": "Test Entity",
            "update_type": "enforcement",
            "entities": ["Test Entity"],
            "scores": {"urgency": {"score": 8}, "impact": {"score": 7}},
            "feed_entry_id": "e1",
            "relevant": True,
            "relevance_score": 8,
            "one_line_why": "Direct enforcement",
            "condition_tag": "A",
            "high_impact": True,
            "direction": "bullish",
            "magnitude": "high",
            "timeline_shift": "sooner",
        }
    ]
    result = _project_timeline_fields(judged)
    assert len(result) == 1
    event = result[0]
    assert event["direction"] == "bullish"
    assert event["magnitude"] == "high"
    assert event["timeline_shift"] == "sooner"
    assert event["mechanism"] == BINDING_ACTION
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd pred-oracle && uv run pytest tests/test_trader_contract_enrich.py -v`
Expected: ImportError on `_project_timeline_fields`

- [ ] **Step 3: Implement `build/trader_contract_enrich.py`**

Mirror `gamma_contract_enrich.py` exactly. The only differences:

1. `_project_timeline_fields()` adds three extra keys to each event dict:
   - `"direction"`: from the LLM judgment (or `"neutral"` fallback)
   - `"magnitude"`: from the LLM judgment (or `"low"` fallback)
   - `"timeline_shift"`: from the LLM judgment (or `"none"` fallback)
   - `"mechanism"`: from `_mechanism.classify(rec.get("update_type", ""))`

2. No `open_tickets` handling (trader slices don't have tickets).

The `enrich_slice` and `enrich_all` signatures are identical to `gamma_contract_enrich.py`:

```python
def enrich_slice(
    *,
    slice_doc: dict[str, Any],
    corpus: list[dict[str, Any]],
    peer_heats: list[float],
    today: date,
    cache_root: Path | None = None,
) -> dict[str, Any]

def enrich_all(
    *,
    slice_dir: Path,
    corpus: list[dict[str, Any]],
    peer_heats: list[float],
    today: date,
    cache_root: Path | None = None,
    max_workers: int = 4,
) -> list[Path]
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd pred-oracle && uv run pytest tests/test_trader_contract_enrich.py -v`
Expected: all tests PASS

- [ ] **Step 5: Commit**

```bash
git add build/trader_contract_enrich.py tests/test_trader_contract_enrich.py
git commit -m "feat(trader): add trader contract enrichment orchestrator"
```

---

## Task 7: Portfolio Aggregator and Calendar Builder

**Files:**
- Create: `build/_portfolio.py`
- Create: `build/_calendar.py`
- Create: `tests/test_portfolio.py`
- Create: `tests/test_calendar.py`

Portfolio aggregates enriched slice data into portfolio-level sort/filter data. Calendar extracts future-dated events across all contracts.

- [ ] **Step 1: Write portfolio tests**

```python
# tests/test_portfolio.py
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
```

- [ ] **Step 2: Write calendar tests**

```python
# tests/test_calendar.py
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
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `cd pred-oracle && uv run pytest tests/test_portfolio.py tests/test_calendar.py -v`
Expected: ImportError — modules don't exist

- [ ] **Step 4: Implement `build/_portfolio.py`**

```python
# build/_portfolio.py
"""Portfolio-level aggregation for the trader dashboard."""
from __future__ import annotations

from datetime import date, timedelta
from typing import Any


def net_direction(
    events: list[dict[str, Any]], *, window_days: int = 30, today: str = "",
) -> str:
    if not today:
        today = date.today().isoformat()
    cutoff = (date.fromisoformat(today) - timedelta(days=window_days)).isoformat()
    recent = [e for e in events if e.get("pub_date", "") >= cutoff]
    bullish = sum(1 for e in recent if e.get("direction") == "bullish")
    bearish = sum(1 for e in recent if e.get("direction") == "bearish")
    if bullish == 0 and bearish == 0:
        return "Mixed"
    if bullish > bearish * 1.5:
        return "Bullish"
    if bearish > bullish * 1.5:
        return "Bearish"
    return "Mixed"


def _next_catalyst(timeline: list[dict[str, Any]], today: str) -> dict[str, Any] | None:
    candidates = []
    for ev in timeline:
        for field in ("effective_date", "comment_deadline"):
            dt = ev.get(field, "")
            if dt and dt > today:
                candidates.append({"date": dt, "field": field, "title": ev.get("title", "")})
    if not candidates:
        return None
    candidates.sort(key=lambda c: c["date"])
    return candidates[0]


def portfolio_row(slice_doc: dict[str, Any], *, today: str = "") -> dict[str, Any]:
    if not today:
        today = date.today().isoformat()
    contract = slice_doc["contract"]
    timeline = slice_doc.get("timeline", [])
    heat_panel = slice_doc.get("heat_panel", {})
    position = slice_doc.get("position", {})

    latest = timeline[0] if timeline else None
    catalyst = _next_catalyst(timeline, today)
    event_count = len(timeline)

    return {
        "contract_id": contract["id"],
        "platform": contract.get("platform", ""),
        "title": contract.get("title", ""),
        "kind": contract.get("kind", "active"),
        "expires_at": contract.get("expires_at", ""),
        "heat_value": heat_panel.get("value", 0),
        "heat_tier": heat_panel.get("tier", "dormant"),
        "heat_delta_7d": heat_panel.get("delta_7d", 0),
        "peer_percentile": heat_panel.get("peer_percentile", 0),
        "net_direction": net_direction(timeline, today=today),
        "event_count_90d": event_count,
        "next_catalyst": catalyst,
        "latest_event": {
            "pub_date": latest.get("pub_date", ""),
            "title": latest.get("title", ""),
            "direction": latest.get("direction", "neutral"),
            "magnitude": latest.get("magnitude", "low"),
        } if latest else None,
        "position": position,
        "detail_href": f"contracts/{contract['id']}/",
    }


def build_portfolio(
    slice_docs: list[dict[str, Any]], *, today: str = "",
) -> list[dict[str, Any]]:
    rows = [portfolio_row(doc, today=today) for doc in slice_docs]
    rows.sort(key=lambda r: r["heat_value"], reverse=True)
    return rows
```

- [ ] **Step 5: Implement `build/_calendar.py`**

```python
# build/_calendar.py
"""Calendar data extraction for the trader dashboard."""
from __future__ import annotations

import calendar as _cal
from datetime import date
from typing import Any


def extract_calendar_events(
    slice_docs: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []

    for doc in slice_docs:
        cid = doc["contract"]["id"]
        ctitle = doc["contract"].get("title", "")
        platform = doc["contract"].get("platform", "")

        expires = doc["contract"].get("expires_at", "")
        if expires:
            events.append({
                "calendar_date": expires[:10],
                "type": "settlement",
                "title": f"Settlement: {ctitle}",
                "contract_id": cid,
                "platform": platform,
                "color": "blue",
            })

        for ev in doc.get("timeline", []):
            for field, etype, color in [
                ("effective_date", "effective_date", "purple"),
                ("comment_deadline", "comment_deadline", "green"),
            ]:
                dt = ev.get(field, "")
                if dt:
                    events.append({
                        "calendar_date": dt[:10],
                        "type": etype,
                        "title": ev.get("title", ""),
                        "contract_id": cid,
                        "platform": platform,
                        "color": color,
                        "direction": ev.get("direction", "neutral"),
                        "magnitude": ev.get("magnitude", "low"),
                    })

            pub = ev.get("pub_date", "")
            if pub:
                is_high = ev.get("high_impact", False)
                events.append({
                    "calendar_date": pub[:10],
                    "type": "regulatory_event",
                    "title": ev.get("title", ""),
                    "contract_id": cid,
                    "platform": platform,
                    "color": "red" if is_high else "amber",
                    "direction": ev.get("direction", "neutral"),
                    "magnitude": ev.get("magnitude", "low"),
                    "high_impact": is_high,
                    "relevance_score": ev.get("relevance_score", 0),
                })

    return events


def calendar_month(
    year: int, month: int, events: list[dict[str, Any]],
) -> dict[str, Any]:
    weeks: list[list[dict[str, Any] | None]] = []
    cal = _cal.Calendar(firstweekday=6)
    for week in cal.monthdayscalendar(year, month):
        week_data: list[dict[str, Any] | None] = []
        for day in week:
            if day == 0:
                week_data.append(None)
            else:
                iso = f"{year:04d}-{month:02d}-{day:02d}"
                day_events = [e for e in events if e["calendar_date"] == iso]
                week_data.append({
                    "day": day,
                    "date": iso,
                    "events": day_events,
                    "busy": len(day_events) >= 3,
                })
        weeks.append(week_data)

    return {"year": year, "month": month, "weeks": weeks}
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `cd pred-oracle && uv run pytest tests/test_portfolio.py tests/test_calendar.py -v`
Expected: all tests PASS

- [ ] **Step 7: Commit**

```bash
git add build/_portfolio.py build/_calendar.py tests/test_portfolio.py tests/test_calendar.py
git commit -m "feat(trader): add portfolio aggregator and calendar data builder"
```

---

## Task 8: Wire into generate_slices.py

**Files:**
- Modify: `build/generate_slices.py` — add trader slice generation block after the gamma block

- [ ] **Step 1: Add trader block to `generate_slices.py`**

Add a new block after the gamma block (after line ~215, before the beta block). Follow the exact pattern of the gamma block:

```python
    # Trader dashboard — uses trader-curation.yml + contracts.yml + retrospective YAMLs
    trader_curation = REPO / "data" / "trader-curation.yml"

    if trader_curation.exists() and corpus.exists():
        cur_t = yaml.safe_load(trader_curation.read_text())
        bd_t = cur_t.get("build_date")
        today_t = _dt.date.fromisoformat(bd_t) if bd_t else _dt.date.today()

        from build.trader_contract import generate as gen_trader_contract
        from build import trader_contract_enrich

        trader_contract_paths = gen_trader_contract(
            corpus_path=corpus,
            trader_curation_path=trader_curation,
            kalshi_contracts_path=kalshi_contracts,
            polymarket_contracts_path=polymarket_contracts,
            retrospectives_root=retrospectives_root,
            out_dir=pd / "trader" / "contracts",
            today=today_t,
        )
        print(
            f"trader (build_date={today_t.isoformat()}): "
            f"{len(trader_contract_paths)} contract details"
        )

        # Trader contract enrichment
        trader_corpus: list[dict[str, Any]] = []
        if corpus.exists():
            with corpus.open() as _f:
                for _line in _f:
                    _line = _line.strip()
                    if _line:
                        trader_corpus.append(json.loads(_line))

        # Peer heats from all trader contracts
        trader_contracts_dir = pd / "trader" / "contracts"
        trader_peer_heats = []
        if trader_contracts_dir.exists():
            for p in trader_contracts_dir.glob("*.json"):
                doc = json.loads(p.read_text())
                trader_peer_heats.append(doc.get("contract", {}).get("heat", 0))

        if trader_contracts_dir.exists():
            trader_contract_enrich.enrich_all(
                slice_dir=trader_contracts_dir,
                corpus=trader_corpus,
                peer_heats=trader_peer_heats,
                today=today_t,
            )
            print(f"  enriched {len(list(trader_contracts_dir.glob('*.json')))} trader contract slices")

        # Portfolio + calendar aggregation
        from build._portfolio import build_portfolio
        from build._calendar import extract_calendar_events, calendar_month

        enriched_slices = []
        for p in sorted(trader_contracts_dir.glob("*.json")):
            enriched_slices.append(json.loads(p.read_text()))

        portfolio_data = build_portfolio(enriched_slices, today=today_t.isoformat())
        (pd / "trader" / "portfolio.json").parent.mkdir(parents=True, exist_ok=True)
        (pd / "trader" / "portfolio.json").write_text(json.dumps(portfolio_data, indent=2))

        all_cal_events = extract_calendar_events(enriched_slices)
        cal_months = []
        for offset in [-1, 0, 1]:
            m = today_t.month + offset
            y = today_t.year
            if m < 1:
                m += 12
                y -= 1
            elif m > 12:
                m -= 12
                y += 1
            cal_months.append(calendar_month(y, m, all_cal_events))
        cal_data = {"months": cal_months, "events": all_cal_events, "today": today_t.isoformat()}
        (pd / "trader" / "calendar.json").write_text(json.dumps(cal_data, indent=2))

        # Retrospective slices (reuse gamma enriched data if available)
        retro_dir = pd / "trader" / "retrospectives"
        retro_dir.mkdir(parents=True, exist_ok=True)
        for retro in cur_t.get("retrospectives", []):
            gamma_slice = pd / "gamma" / "contracts" / f"{retro['id']}.json"
            if gamma_slice.exists():
                import shutil
                shutil.copy(gamma_slice, retro_dir / f"{retro['id']}.json")

        print(f"  portfolio.json + calendar.json + {len(cur_t.get('retrospectives', []))} retrospectives")

    elif trader_curation.exists():
        print(f"WARN: corpus {corpus.relative_to(REPO)} missing — skipping trader slices")
```

- [ ] **Step 2: Verify existing `make slice` still works**

Run: `cd pred-oracle && uv run python build/generate_slices.py`
Expected: existing alpha/gamma/beta slices generate as before, plus new trader slice output lines. If corpus is missing, a WARN is printed (not an error).

- [ ] **Step 3: Commit**

```bash
git add build/generate_slices.py
git commit -m "feat(trader): wire trader slice generation into build pipeline"
```

---

## Task 9: Trader Templates

**Files:**
- Create: `build/templates/trader/_base.html`
- Create: `build/templates/trader/list.html`
- Create: `build/templates/trader/briefing.html`
- Create: `build/templates/trader/calendar.html`
- Create: `build/templates/trader/retrospectives.html`
- Create: `tests/test_trader_templates.py`

All templates extend the trader `_base.html`, which itself extends the site `base.html`. They use Tailwind utility classes, ECharts for charts, and Alpine.js for interactivity.

- [ ] **Step 1: Create trader base template**

```html
{# build/templates/trader/_base.html #}
{% extends "base.html" %}

{% block title %}Carver Trader — {% block page_title %}Portfolio{% endblock %}{% endblock %}
{% block meta_description %}Carver-enhanced regulatory intelligence for prediction market traders.{% endblock %}

{% block content %}
<nav class="flex items-center justify-between mb-8 border-b border-slate-200 pb-4">
  <div class="flex items-center gap-6">
    <a href="{{ base_url|default('/') }}trader/"
       class="text-sm font-medium {% if active_nav == 'list' or active_nav == 'calendar' %}text-ink{% else %}text-slate-500 hover:text-ink{% endif %} transition">
      Portfolio
    </a>
    <a href="{{ base_url|default('/') }}trader/retrospectives/"
       class="text-sm font-medium {% if active_nav == 'retrospectives' %}text-ink{% else %}text-slate-500 hover:text-ink{% endif %} transition">
      Case Studies
    </a>
  </div>
  <div class="flex items-center gap-2 text-xs text-slate-400">
    <span class="w-1.5 h-1.5 rounded-full bg-lime-400"></span>
    <span>Alex's Portfolio</span>
    <span class="ml-2 px-1.5 py-0.5 bg-amber-100 text-amber-700 rounded text-[10px] font-medium">DEMO</span>
  </div>
</nav>

{% block trader_content %}{% endblock %}
{% endblock %}
```

- [ ] **Step 2: Create portfolio list template**

Create `build/templates/trader/list.html` extending `trader/_base.html`:

Key features:
- `{% set active_nav = "list" %}`
- Toggle link to calendar view
- Sort dropdown and filter chips (Alpine.js `x-data` for client-side state)
- `{% for row in rows %}` loop rendering each contract row with:
  - Heat tier badge (color from `row.heat_tier`)
  - Contract title with platform chip
  - Price display: `YES {{ row.yes_price }}¢ / NO {{ row.no_price }}¢`
  - Net direction arrow + label
  - Heat value + 7d delta
  - Event count badge
  - Next catalyst with countdown
  - Latest event snippet with direction badge
- Position display with demo badge
- Client-side JS for sort/filter using Alpine.js `x-data="{ sort: 'heat', platform: 'all', tier: 'all' }"`

Each row links to `{{ row.detail_href }}`.

Template variable: `rows` — list of portfolio row dicts from `_portfolio.build_portfolio()`.

- [ ] **Step 3: Create contract briefing template**

Create `build/templates/trader/briefing.html` extending `trader/_base.html`:

Key features:
- `{% set active_nav = "" %}` (none highlighted — we're in a detail page)
- Back link: `← Portfolio`
- **Above the fold:**
  - Contract header: title, platform chip, heat badge, expiry date
  - Price buttons: YES/NO with payout math
  - Position display with demo badge
  - Resolution banner (only for retrospective: `{% if contract.kind == "retrospective" %}`)
  - Probability chart placeholder `<div id="price-chart" class="h-64">` with ECharts init in `{% block extra_body %}`
- **Below the fold (two-column grid `lg:grid-cols-5`):**
  - Left (col-span-3):
    - Thesis tracker: `{% for cond in contract.conditions %}` with progress bars
    - Regulatory timeline: `{% for ev in timeline %}` with direction/magnitude/mechanism/timeline_shift badges
    - Narrative card
  - Right (col-span-2):
    - Momentum panel (heat value, tier, delta, percentile, sparkline, drivers, explainer)
    - Upcoming catalysts list

**ECharts initialization** (in `{% block extra_body %}`):
- Line chart with `price_series` data (from `prices.series` in template context)
- `markLine` for each timeline event, color-coded by direction
- Tooltip on hover showing event title + one_line_why

Template variables: `contract`, `timeline`, `heat_panel`, `position`, `prices` (price series data).

- [ ] **Step 4: Create calendar template**

Create `build/templates/trader/calendar.html` extending `trader/_base.html`:

Key features:
- `{% set active_nav = "calendar" %}`
- Toggle link back to list view
- Month navigation (prev/next) using Alpine.js `x-data="{ currentMonth: 1 }"`
- Calendar grid: 7 columns (Sun-Sat), one row per week
- Each day cell shows colored dots for events:
  - Red dot: `event.color == "red"` (high-impact)
  - Amber dot: `event.color == "amber"` (medium-impact)
  - Blue marker: `event.type == "settlement"`
  - Green marker: `event.type == "comment_deadline"`
  - Purple marker: `event.type == "effective_date"`
- Click expands event details below calendar
- "Busy week" highlight for weeks with 3+ events
- Regulatory event ticker strip at bottom
- Data coverage footnote

Template variables: `months` (list of calendar_month dicts), `today`, `all_events`.

- [ ] **Step 5: Create retrospectives landing template**

Create `build/templates/trader/retrospectives.html` extending `trader/_base.html`:

Key features:
- `{% set active_nav = "retrospectives" %}`
- Intro text: framing paragraph about case studies
- Two cards (one per retrospective): title, platform chip, resolution badge, 1-line summary, link to detail page
- Each card links to `retrospectives/{{ retro.id }}/`

Template variables: `retrospectives` — list of retrospective slice dicts.

- [ ] **Step 6: Write template smoke tests**

```python
# tests/test_trader_templates.py
from __future__ import annotations

from pathlib import Path
from jinja2 import Environment, FileSystemLoader


TEMPLATES_DIR = Path(__file__).resolve().parent.parent / "build" / "templates"


def _env():
    return Environment(
        loader=FileSystemLoader(str(TEMPLATES_DIR)),
        autoescape=True,
    )


def test_trader_base_renders():
    env = _env()
    tmpl = env.get_template("trader/_base.html")
    html = tmpl.render(base_url="/", active_nav="list")
    assert "Alex's Portfolio" in html
    assert "Portfolio" in html
    assert "Case Studies" in html


def test_trader_list_renders():
    env = _env()
    tmpl = env.get_template("trader/list.html")
    html = tmpl.render(
        base_url="/",
        rows=[{
            "contract_id": "test",
            "platform": "kalshi",
            "title": "Test contract",
            "heat_tier": "active",
            "heat_value": 42.5,
            "heat_delta_7d": 5.3,
            "net_direction": "Bullish",
            "event_count_90d": 12,
            "next_catalyst": None,
            "latest_event": {
                "pub_date": "2026-05-10",
                "title": "Test event",
                "direction": "bullish",
                "magnitude": "high",
            },
            "position": {"side": "YES", "size": 100, "entry_price": 0.50},
            "detail_href": "contracts/test/",
            "yes_price": 62,
            "no_price": 38,
        }],
    )
    assert "Test contract" in html
    assert "Bullish" in html


def test_trader_briefing_renders():
    env = _env()
    tmpl = env.get_template("trader/briefing.html")
    html = tmpl.render(
        base_url="/",
        contract={
            "id": "test",
            "platform": "kalshi",
            "kind": "active",
            "title": "Test contract",
            "expires_at": "2026-12-31",
            "resolution_criteria": "Test criteria",
            "settlement_entities": [{"name": "SEC", "role": "regulator"}],
            "conditions": [{"id": "A", "label": "Test", "summary": "Test summary"}],
            "narrative": "Test narrative.",
        },
        timeline=[{
            "pub_date": "2026-05-10",
            "title": "Test event",
            "regulator": "SEC",
            "url": "https://example.com",
            "direction": "bullish",
            "magnitude": "high",
            "mechanism": "Binding Action",
            "timeline_shift": "none",
            "condition_tag": "A",
            "one_line_why": "Direct impact on resolution.",
        }],
        heat_panel={
            "value": 42.5, "tier": "active", "delta_7d": 5.3,
            "peer_percentile": 72, "urgency_weighted_sparkline": [0] * 14,
            "primary_drivers": ["Test driver"], "explainer": "Test explainer.",
        },
        position={"side": "YES", "size": 100, "entry_price": 0.50},
        prices={"series": []},
    )
    assert "Test contract" in html
    assert "Binding Action" in html
```

- [ ] **Step 7: Run template tests**

Run: `cd pred-oracle && uv run pytest tests/test_trader_templates.py -v`
Expected: all 3 tests PASS

- [ ] **Step 8: Commit**

```bash
git add build/templates/trader/
git add tests/test_trader_templates.py
git commit -m "feat(trader): add all trader dashboard Jinja2 templates"
```

---

## Task 10: Wire Templates into Site Renderer

**Files:**
- Modify: `build/generate.py` — add trader template routing

- [ ] **Step 1: Add trader routes to `generate.py`**

Add to `_EXPLICIT_ROUTES`:
```python
"trader/list.html": "trader/index.html",
"trader/calendar.html": "trader/calendar/index.html",
"trader/retrospectives.html": "trader/retrospectives/index.html",
```

Add a new parametric rendering call (after the gamma parametric block):
```python
# Trader contract briefings
_render_parametric(
    env=env, out_dir=out_dir, base_url=base_url,
    template_name="trader/briefing.html",
    data_glob="trader/contracts/*.json",
    out_pattern="trader/contracts/{stem}/index.html",
    repo_root=repo_root,
)

# Trader retrospectives
_render_parametric(
    env=env, out_dir=out_dir, base_url=base_url,
    template_name="trader/briefing.html",
    data_glob="trader/retrospectives/*.json",
    out_pattern="trader/retrospectives/{stem}/index.html",
    repo_root=repo_root,
)
```

Add price data loading: for each trader contract/retrospective slice, load the corresponding price cache file from `build/_cache/prices/{contract_id}.json` and inject it as `prices` in the template context. If no cache exists, pass `prices={"series": []}`.

Add portfolio data loading: for `trader/list.html`, load `build/page_data/trader/portfolio.json` and inject as `rows`. For each row, compute `yes_price` and `no_price` from the latest price data (or use placeholder values).

Add calendar data loading: for `trader/calendar.html`, load `build/page_data/trader/calendar.json`.

- [ ] **Step 2: Verify `make build` works end-to-end**

Run: `cd pred-oracle && make build`
Expected: all existing pages render + new trader pages appear under `site/trader/`. Check for:
- `site/trader/index.html` (portfolio list)
- `site/trader/calendar/index.html` (calendar view)
- `site/trader/contracts/{id}/index.html` (6 briefing pages)
- `site/trader/retrospectives/index.html` (case studies landing)
- `site/trader/retrospectives/{id}/index.html` (2 retrospective pages)

- [ ] **Step 3: Commit**

```bash
git add build/generate.py
git commit -m "feat(trader): wire trader templates into site renderer"
```

---

## Task 11: Fetch Price Data and Final Integration Test

**Files:**
- Create: `build/pull_prices.py` — CLI script to fetch and cache price data for all trader contracts
- Modify: `Makefile` — add `pull-prices` target

- [ ] **Step 1: Create price pull script**

```python
# build/pull_prices.py
"""Fetch probability time series for all trader contracts."""
from __future__ import annotations

import sys
from datetime import date, datetime
from pathlib import Path

import yaml

_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from build._prices import fetch_and_cache


def main() -> None:
    REPO = Path(__file__).resolve().parent.parent
    curation = yaml.safe_load(
        (REPO / "data" / "trader-curation.yml").read_text()
    )

    kalshi_doc = yaml.safe_load(
        (REPO / "data" / "platforms" / "kalshi" / "contracts.yml").read_text()
    )
    poly_doc = yaml.safe_load(
        (REPO / "data" / "platforms" / "polymarket" / "contracts.yml").read_text()
    )

    kalshi_picks = {p["id"]: p for p in kalshi_doc.get("picks", [])}
    poly_picks = {p["id"]: p for p in poly_doc.get("picks", [])}

    all_contracts = curation["portfolio"] + curation.get("retrospectives", [])

    for entry in all_contracts:
        cid = entry["id"]
        platform = entry["platform"]

        if platform == "kalshi":
            pick = kalshi_picks.get(cid)
            if not pick:
                # Check retrospective YAMLs
                retro_path = REPO / "data" / "platforms" / "kalshi" / "contracts" / f"{cid}.yml"
                if retro_path.exists():
                    retro = yaml.safe_load(retro_path.read_text())
                    ticker = cid.upper()
                    listed = retro.get("listed_at", "2025-01-01")
                    start_ts = int(datetime.fromisoformat(listed + "T00:00:00").timestamp())
                    resolved = retro.get("resolved_at", "")
                    end_ts = int(datetime.fromisoformat(
                        (resolved or date.today().isoformat()) + "T23:59:59"
                    ).timestamp())
                    data = fetch_and_cache(
                        contract_id=cid, platform="kalshi", ticker=ticker,
                        start_ts=start_ts, end_ts=end_ts,
                        is_historical=bool(resolved),
                    )
                    print(f"  {cid}: {len(data.series)} price points")
                    continue
                print(f"  WARN: {cid} not found in kalshi picks or retrospectives")
                continue
            cached = pick["cached"]
            ticker = cached.get("ticker", "")
            listed = cached.get("listed_at", "2025-01-01T00:00:00Z")
            start_ts = int(datetime.fromisoformat(listed.replace("Z", "+00:00")).timestamp())
            end_ts = int(datetime.now().timestamp())
            data = fetch_and_cache(
                contract_id=cid, platform="kalshi", ticker=ticker,
                start_ts=start_ts, end_ts=end_ts,
            )
        elif platform == "polymarket":
            pick = poly_picks.get(cid)
            slug = cid
            if pick:
                slug = pick.get("source_lookup", {}).get("slug", cid)
            # Check retrospective YAMLs too
            retro_path = REPO / "data" / "platforms" / "polymarket" / "contracts" / f"{cid}.yml"
            is_historical = retro_path.exists() and yaml.safe_load(
                retro_path.read_text()
            ).get("status") == "resolved"
            data = fetch_and_cache(
                contract_id=cid, platform="polymarket", ticker=slug, slug=slug,
            )
        else:
            print(f"  WARN: unknown platform {platform} for {cid}")
            continue

        print(f"  {cid}: {len(data.series)} price points")


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Add Makefile target**

Add to the `Makefile`:

```makefile
pull-prices:
	uv run python build/pull_prices.py
```

Add `pull-prices` to the `pull:` prerequisite list:

```makefile
pull: pull-carver pull-kalshi pull-polymarket pull-prices
```

- [ ] **Step 3: Run price fetch**

Run: `cd pred-oracle && make pull-prices`
Expected: price data fetched and cached in `build/_cache/prices/`. Each contract should print a line with the number of price points. If any API call fails, the script warns but continues.

- [ ] **Step 4: Run full build and verify**

Run: `cd pred-oracle && make build`
Expected: all pages generate, including trader pages with price data.

- [ ] **Step 5: Run full test suite**

Run: `cd pred-oracle && make test`
Expected: all tests PASS (existing + new)

- [ ] **Step 6: Run linter**

Run: `cd pred-oracle && make lint`
Expected: no lint errors. Fix any issues before committing.

- [ ] **Step 7: Serve and verify in browser**

Run: `cd pred-oracle && make serve`
Expected: site served at http://localhost:8000. Navigate to:
- `/trader/` — portfolio list with 6 contracts, sort/filter working
- `/trader/calendar/` — calendar view with date markers
- `/trader/contracts/{any-id}/` — contract briefing with probability chart + regulatory timeline
- `/trader/retrospectives/` — case studies landing with 2 cards
- `/trader/retrospectives/solana-etf-2025/` — full retrospective with resolution banner

- [ ] **Step 8: Commit everything**

```bash
git add build/pull_prices.py Makefile build/_cache/prices/
git commit -m "feat(trader): add price fetcher, Makefile target, and cached price data"
```

- [ ] **Step 9: Final commit — all trader dashboard files**

Verify nothing is unstaged:
```bash
git status
```
If any files remain, stage and commit with:
```bash
git add -A
git commit -m "feat(trader): complete trader dashboard demo"
```

---

## Dependency Graph

```
Task 1 (data files)
  │
  ├── Task 2 (mechanism) ──────────────────────────┐
  │                                                 │
  ├── Task 3 (relevance extension) ─────────────────┤
  │                                                 │
  ├── Task 4 (price fetcher) ───────────────────────┤
  │                                                 │
  └── Task 5 (slice generator) ─────────────────────┤
                                                    │
                                    Task 6 (enrichment orchestrator)
                                           │
                                    Task 7 (portfolio + calendar)
                                           │
                                    Task 8 (wire generate_slices.py)
                                           │
                              ┌────────────┴────────────┐
                              │                         │
                       Task 9 (templates)        Task 11 (prices + integration)
                              │
                       Task 10 (wire generate.py)
```

Tasks 2, 3, 4 can run in parallel (independent modules). Task 5 depends on Task 1. Task 6 depends on 2, 3, 5. Task 7 depends on 6. Tasks 8-11 are sequential.
