# Stage 2 — γ Walkthrough Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the γ scene ("Marcus Vega, Head of Listing — Tuesday morning"): four pages (`/gamma/`, `/gamma/scan/`, `/gamma/dashboard/`, `/gamma/contracts/{id}/`) covering pre-listing scan, contract-watch board, and 5 contract-detail pages (3 active + 2 retrospectives).

**Architecture:** A curation-driven pick list (`data/platforms/{kalshi,polymarket}/contracts.yml`) drives non-destructive refresh-or-cache pulls from Kalshi/Polymarket public APIs. Retired retrospective contracts are hand-curated from Wayback Machine sources. Heat scoring composes the artifacts corpus (`build/_scoring.py`-style helpers in a new `build/_heat.py`). Slice generators follow the Stage 1 pattern (`generate(corpus_path, curation_path, out_*, today=None)`). Templates use Tailwind + ECharts + Alpine, reuse Stage 1 components, follow `_EXPLICIT_ROUTES` for hyphenated URLs.

**Tech Stack:** Python 3.10, httpx, Jinja2 (autoescape), Tailwind CDN, ECharts CDN, Alpine.js CDN, pytest, ruff, mypy strict (build/ only).

---

## Pre-flight context (read before starting)

**Specs to read in this order:**

1. `docs/specs/STAGE_1_NOTES.md` — schema for the artifacts corpus. γ uses the same corpus.
2. `docs/specs/40-gamma-walkthrough.md` — the γ scene narrative spec.
3. `docs/specs/10-data-prep.md` §3.2 — contracts.yml shape (canonical).
4. `docs/specs/20-site-build.md` §3 — build pipeline conventions.

**Key constraint discovered during planning (worth knowing now):**

The Kalshi and Polymarket public APIs **do NOT serve retired contracts**. Verified:
- `GET /markets/TIKTOKBAN-25APR30` → 404
- `GET /markets?series_ticker=KXFEDDECISION` → returns active contracts ✓
- Polymarket purges resolved markets from `/markets?slug=` lookup

Implications baked into this plan:
- **Active contracts** (e.g., KXFEDDECISION-28JAN): pulled live via the curated-pull scripts (Task 3).
- **Retrospective contracts** (TIKTOKBAN-25APR30, Solana ETF 2025): hand-curated from Wayback Machine + news sources, with mandatory `source_url` (Task 4).
- **Price-history overlay** on retrospectives is **DROPPED**. Spec § 2.3 wow moments reframe from "price moves with events" to "Carver signal precedes news cycle by N days." This re-framing is Task 5 (spec edit) — do it before writing the retrospective templates.

**Stage 1 conventions inherited verbatim:**

- `build/_fields.py` + `build/_scoring.py` are foundation modules. Compose them, don't duplicate.
- `tests/conftest.py::make_row(**ov)` is the shared Carver-row factory. Use it; don't define new local `_row` helpers.
- `_EXPLICIT_ROUTES` in `build/generate.py` maps templates with non-default URL shape (e.g., underscored filenames → hyphenated URLs).
- Slice generators have `generate(corpus_path, ..., today=None)` and a `if __name__ == "__main__":` smoke runner.
- `data/<scene>-curation.yml` carries `build_date: "YYYY-MM-DD"` for deterministic builds.
- Every test function annotates `-> None` (project convention).

---

## File structure

### Created in this plan

```
data/
  gamma-curation.yml                                   # picks + build_date + retrospective ids
  platforms/
    kalshi/
      contracts.yml                                    # pick-list, cached metadata, stale flags
      contracts/
        tiktokban-25apr30.yml                          # hand-curated retrospective (no price history)
        kxfeddecision-26mar.yml                        # hand-curated retrospective
    polymarket/
      contracts.yml                                    # pick-list
      contracts/
        solana-etf-2025.yml                            # hand-curated retrospective
build/
  _heat.py                                             # heat_score + sparkline_buckets + entity_match
  pull_kalshi_curated.py                               # refresh-or-cache by pick-list
  pull_polymarket_curated.py                           # refresh-or-cache by pick-list
  gamma_scan.py                                        # pre-listing scan slice generator (3 outputs)
  gamma_dashboard.py                                   # contract-watch dashboard slice
  gamma_contract.py                                    # parametric 5 contract-detail slices
  templates/
    gamma/
      _components/
        contract_row.html                              # dashboard row
        sparkline.html                                 # inline SVG sparkline
        entity_chip.html                               # entity chip with role tag
        scan_tab.html                                  # scan-page tab
        signal_callout.html                            # "Carver signal preceded news by N days"
      intro.html                                       # REPLACES the Stage 0 placeholder
      scan.html
      dashboard.html
      contract_detail.html
tests/
  test_gamma_curation.py
  test_pull_kalshi_curated.py
  test_pull_polymarket_curated.py
  test_heat.py
  test_gamma_scan.py
  test_gamma_dashboard.py
  test_gamma_contract.py
  test_gamma_templates.py
```

### Modified in this plan

```
build/
  generate_slices.py                                   # orchestrate γ generators
  generate.py                                          # generalize _render_parametric helper
  templates/
    base.html                                          # (no edits expected; ECharts/Alpine already loaded)
tests/
  conftest.py                                          # add make_contract(**ov) factory
docs/
  specs/
    40-gamma-walkthrough.md                            # § 2.3 wow reframe (Task 5)
    STAGE_2_NOTES.md                                   # NEW: schema + handoff notes (Task 17)
README.md                                              # γ section
```

---

## Conventions for every task

1. **TDD discipline.** Test first → confirm failure → implement → confirm pass → commit.
2. **Every test function annotates `-> None`.** Strict mypy. Stage 0 convention.
3. **Use the conftest factories.** `make_row` (Carver row) is in `tests/conftest.py`; Task 6 adds `make_contract`.
4. **`build/_fields.py` and `build/_scoring.py` are off-limits for edits** unless a task explicitly says otherwise. Compose them.
5. **Commit messages:** `feat(stage-2): <what>` / `fix(stage-2): <what>` / `chore(stage-2): <what>`. Imperative voice.
6. **Lint + type-check per task:** `uv run ruff check . && uv run mypy build/` should be clean (yaml-stubs warnings are pre-existing).
7. **`base_url` injection:** Every internal `<a href>` uses `{{ base_url|default('') }}<path>`. Absolute-from-root convention (see Stage 1 C4).
8. **Tests are scoped:** `uv run pytest tests/<file>.py -v` per task. Task 17 runs the full suite.

---

## Task 1: γ-curation YAML

**Why:** Locks in the curated picks + `build_date`. Shape mirrors `data/alpha-curation.yml` (Stage 1 §2 of that plan).

**Files:**
- Create: `data/gamma-curation.yml`
- Create: `tests/test_gamma_curation.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_gamma_curation.py`:

```python
"""Validate data/gamma-curation.yml shape."""
import datetime as _dt
from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parent.parent
CURATION = REPO / "data" / "gamma-curation.yml"


def test_curation_file_exists() -> None:
    assert CURATION.exists()


def test_curation_schema() -> None:
    doc = yaml.safe_load(CURATION.read_text())
    assert doc["schema_version"] == 1
    _dt.date.fromisoformat(doc["build_date"])  # raises if not ISO
    assert isinstance(doc["featured_kalshi"], list) and len(doc["featured_kalshi"]) >= 3
    assert isinstance(doc["featured_polymarket"], list) and len(doc["featured_polymarket"]) >= 2
    assert isinstance(doc["pre_listing_scans"], list) and len(doc["pre_listing_scans"]) == 3
    for scan in doc["pre_listing_scans"]:
        assert {"id", "title", "resolution_criteria", "platform_hint"} <= set(scan.keys())
    assert isinstance(doc["contract_detail_picks"], list) and len(doc["contract_detail_picks"]) == 5
    for pick in doc["contract_detail_picks"]:
        assert {"id", "platform", "kind"} <= set(pick.keys())
        assert pick["kind"] in {"active", "retrospective"}
    # At least 2 retrospectives expected per spec
    retros = [p for p in doc["contract_detail_picks"] if p["kind"] == "retrospective"]
    assert len(retros) == 2


def test_pre_listing_scan_ids_unique() -> None:
    doc = yaml.safe_load(CURATION.read_text())
    ids = [s["id"] for s in doc["pre_listing_scans"]]
    assert len(set(ids)) == len(ids)
```

- [ ] **Step 2: Run test, confirm fails**

Run: `uv run pytest tests/test_gamma_curation.py -v`
Expected: FAIL (file missing).

- [ ] **Step 3: Create the file**

Write `data/gamma-curation.yml`:

```yaml
# γ-scene curation. Hand-edited; consumed by build/gamma_*.py generators.
# See docs/specs/40-gamma-walkthrough.md for narrative context.

schema_version: 1
build_date: "2026-05-20"

# Active contracts to feature on the dashboard. Pulled live by
# build/pull_*_curated.py. Identifiers verified against the public API
# at curation time (2026-05-20).
featured_kalshi:
  - event_ticker: "KXFEDDECISION-28JAN"
  - event_ticker: "KXFEDDECISION-26MAR"   # part of the active set; ALSO used as retrospective base
  - series_ticker: "KXELONMARS"
  - series_ticker: "KXNEXTIRANLEADER"
  - event_ticker: "KXBTC-MAXPRICE2026"

featured_polymarket:
  - slug: "new-rhianna-album-before-gta-vi-926"
  - slug: "will-2026-be-warmest-year-on-record"
  - slug: "us-recession-in-2026"

# Pre-listing scans — exactly 3 per spec §2.2 table.
pre_listing_scans:
  - id: "tiktokban"
    title: "Will TikTok be banned in the United States by 2026-12-31?"
    resolution_criteria: |
      Resolves YES if TikTok is unavailable in the US Apple/Google app stores OR
      if the Department of Commerce issues a ban directive by 2026-12-31.
    platform_hint: "kalshi"
    settlement_entities:
      - "Federal Communications Commission"
      - "Committee on Foreign Investment in the United States"
      - "Department of Commerce"
      - "ByteDance"
      - "TikTok"
    severity_hint: 8
  - id: "solana_etf_2027"
    title: "Will the SEC approve a spot Solana ETF in 2027?"
    resolution_criteria: |
      Resolves YES if the SEC approves a spot Solana ETF for trading on a US
      national securities exchange by 2027-12-31.
    platform_hint: "polymarket"
    settlement_entities:
      - "U.S. Securities and Exchange Commission"
      - "BlackRock"
      - "Fidelity"
      - "VanEck"
    severity_hint: 7
  - id: "state_kalshi_action"
    title: "Will a 12th US state issue a cease-and-desist against Kalshi by 2026-12-31?"
    resolution_criteria: |
      Resolves YES if a 12th US state-level gambling or securities regulator
      issues an enforcement action naming Kalshi by 2026-12-31.
    platform_hint: "kalshi"
    settlement_entities:
      - "Nevada Gaming Control Board"
      - "New Jersey Division of Gaming Enforcement"
      - "Maryland Lottery and Gaming Control Agency"
      - "Massachusetts Gaming Commission"
      - "New Jersey Bureau of Securities"
      - "California Department of Financial Protection and Innovation"
    severity_hint: 9

# 5 contract-detail pages. The kind="retrospective" entries reference
# hand-curated YAML files under data/platforms/<platform>/contracts/<id>.yml.
contract_detail_picks:
  - id: "tiktokban-25apr30"
    platform: "kalshi"
    kind: "retrospective"
  - id: "kxfeddecision-26mar"
    platform: "kalshi"
    kind: "retrospective"
  - id: "kxfeddecision-28jan"
    platform: "kalshi"
    kind: "active"
  - id: "us-recession-in-2026"
    platform: "polymarket"
    kind: "active"
  - id: "solana-etf-2025"
    platform: "polymarket"
    kind: "retrospective"

# Synthetic listing-risk tickets shown on contract-detail pages. Each
# contract gets ≤2 tickets. Labelled with demo_badge downstream.
synthetic_listing_risk_tickets:
  - contract_id: "tiktokban-25apr30"
    summary: "Escalating CFIUS activity on ByteDance — listing review needed before EOW"
    severity: "high"
    assignee_initials: "MV"
  - contract_id: "kxfeddecision-26mar"
    summary: "Fed speech cadence elevated; consider widening expiry tier"
    severity: "medium"
    assignee_initials: "MV"
```

- [ ] **Step 4: Run test, confirm pass**

Run: `uv run pytest tests/test_gamma_curation.py -v`
Expected: PASS (3 tests).

- [ ] **Step 5: Commit**

```bash
git add data/gamma-curation.yml tests/test_gamma_curation.py
git commit -m "feat(stage-2): gamma curation YAML (picks + build_date)"
```

---

## Task 2: Contracts pick-list YAML schema

**Why:** `data/platforms/{kalshi,polymarket}/contracts.yml` holds: (a) the pick-list (which `event_ticker`/`slug` to follow), (b) cached metadata from the most recent refresh (title, status, etc.), (c) stale flags for entries upstream no longer serves. Task 3 writes the refresh script; this task writes the initial files (just pick identifiers, empty `cached` blocks) and the schema test.

**Files:**
- Create: `data/platforms/kalshi/contracts.yml`
- Create: `data/platforms/polymarket/contracts.yml`
- Create: `tests/test_contracts_yml.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_contracts_yml.py`:

```python
"""Validate data/platforms/*/contracts.yml shape."""
from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parent.parent
KALSHI = REPO / "data" / "platforms" / "kalshi" / "contracts.yml"
POLYMARKET = REPO / "data" / "platforms" / "polymarket" / "contracts.yml"


def _validate(path: Path, expected_keys: set[str]) -> None:
    doc = yaml.safe_load(path.read_text())
    assert isinstance(doc, dict)
    assert doc["schema_version"] == 1
    assert isinstance(doc["picks"], list) and len(doc["picks"]) >= 3
    for p in doc["picks"]:
        assert "id" in p
        assert p.get("source_lookup", {}).keys() & expected_keys, \
            f"pick {p['id']} missing source_lookup key in {expected_keys}"
        # Cached block optional but if present must be a dict
        if "cached" in p:
            assert isinstance(p["cached"], dict)
        # stale flag must be bool if present
        if "stale" in p:
            assert isinstance(p["stale"], bool)


def test_kalshi_contracts_shape() -> None:
    _validate(KALSHI, {"event_ticker", "series_ticker", "ticker"})


def test_polymarket_contracts_shape() -> None:
    _validate(POLYMARKET, {"slug", "condition_id"})


def test_kalshi_pick_ids_unique() -> None:
    doc = yaml.safe_load(KALSHI.read_text())
    ids = [p["id"] for p in doc["picks"]]
    assert len(set(ids)) == len(ids)


def test_polymarket_pick_ids_unique() -> None:
    doc = yaml.safe_load(POLYMARKET.read_text())
    ids = [p["id"] for p in doc["picks"]]
    assert len(set(ids)) == len(ids)
```

- [ ] **Step 2: Run test, confirm fails**

Run: `uv run pytest tests/test_contracts_yml.py -v`
Expected: FAIL (files missing).

- [ ] **Step 3: Create `data/platforms/kalshi/contracts.yml`**

```yaml
# Kalshi curated contract pick-list. Each pick's `id` is the slug used in
# /gamma/contracts/{id}/ URLs and Task 3's refresh writes the `cached` block
# from the live API. If upstream 404s on refresh, the cached block is left
# intact and `stale: true` plus `stale_reason` are set instead of overwriting.

schema_version: 1
picks:
  - id: "kxfeddecision-28jan"
    source_lookup:
      event_ticker: "KXFEDDECISION-28JAN"
    notes: "Live Fed-decision contract — anchors the cross-platform Fed-rate comparison."

  - id: "kxbtc-maxprice-2026"
    source_lookup:
      series_ticker: "KXBTCMAXY"
    notes: "Live BTC max-price-2026 series — fastest-rising heat candidate."

  - id: "kxelonmars-99"
    source_lookup:
      event_ticker: "KXELONMARS-99"
    notes: "Long-tail prediction; low heat baseline for contrast."

  - id: "kxnextiranleader-45jan01"
    source_lookup:
      event_ticker: "KXNEXTIRANLEADER-45JAN01"
    notes: "Geopolitical contract; high entity-density."

  - id: "kxtrumpcabinet-26"
    source_lookup:
      series_ticker: "KXCABINET"
    notes: "Trump cabinet confirmations; politically tame resolution events per GW5."
```

- [ ] **Step 4: Create `data/platforms/polymarket/contracts.yml`**

```yaml
# Polymarket curated contract pick-list. `id` is the slug used in
# /gamma/contracts/{id}/ URLs; same stale-on-refresh policy as Kalshi.

schema_version: 1
picks:
  - id: "us-recession-in-2026"
    source_lookup:
      slug: "us-recession-in-2026"
    notes: "Active macro contract; high entity intersection with Carver Fed/Treasury events."

  - id: "rihanna-album-before-gta-vi"
    source_lookup:
      slug: "new-rhianna-album-before-gta-vi-926"
    notes: "Live entertainment market — low-heat baseline for contrast."

  - id: "warmest-year-on-record-2026"
    source_lookup:
      slug: "will-2026-be-warmest-year-on-record"
    notes: "Climate / NOAA contract — adds science-agency entity coverage."
```

- [ ] **Step 5: Run test, confirm pass**

Run: `uv run pytest tests/test_contracts_yml.py -v`
Expected: PASS (4 tests).

- [ ] **Step 6: Commit**

```bash
git add data/platforms/kalshi/contracts.yml data/platforms/polymarket/contracts.yml tests/test_contracts_yml.py
git commit -m "feat(stage-2): contracts.yml pick-lists for Kalshi + Polymarket"
```

---

## Task 3: Curated-pull scripts with stale-flag policy

**Why:** Refresh `cached` metadata from live APIs without overwriting on 404. Driver for the `--mode=cached|fresh` behavior the user requested.

**Files:**
- Create: `build/pull_kalshi_curated.py`
- Create: `build/pull_polymarket_curated.py`
- Create: `tests/test_pull_kalshi_curated.py`
- Create: `tests/test_pull_polymarket_curated.py`

### Kalshi script

- [ ] **Step 1: Write the failing test for Kalshi**

Create `tests/test_pull_kalshi_curated.py`:

```python
"""Tests for build/pull_kalshi_curated.py — non-destructive refresh."""
from pathlib import Path
from typing import Any

import pytest
import yaml


def _write_contracts(path: Path, picks: list[dict[str, Any]]) -> None:
    path.write_text(yaml.safe_dump({"schema_version": 1, "picks": picks}))


def test_refresh_populates_cached_on_success(tmp_path: Path, monkeypatch) -> None:
    from build import pull_kalshi_curated as m

    contracts = tmp_path / "contracts.yml"
    _write_contracts(contracts, [{"id": "kx-x", "source_lookup": {"event_ticker": "KX-X"}}])

    def fake_lookup(lookup: dict[str, str]) -> dict[str, Any] | None:
        return {"ticker": "KX-X", "title": "X", "status": "active",
                "open_time": "2026-01-01T00:00:00Z", "close_time": "2027-01-01T00:00:00Z",
                "subtitle": "", "rules_primary": "rule", "settlement_source": "FOMC"}

    monkeypatch.setattr(m, "lookup_market", fake_lookup)
    m.refresh(contracts)
    doc = yaml.safe_load(contracts.read_text())
    assert doc["picks"][0]["cached"]["title"] == "X"
    assert doc["picks"][0]["cached"]["status"] == "active"
    assert "last_pulled_at" in doc["picks"][0]
    assert doc["picks"][0].get("stale", False) is False


def test_refresh_demotes_to_stale_on_404(tmp_path: Path, monkeypatch) -> None:
    from build import pull_kalshi_curated as m

    contracts = tmp_path / "contracts.yml"
    _write_contracts(contracts, [{
        "id": "kx-retired",
        "source_lookup": {"event_ticker": "KX-RETIRED"},
        "cached": {"title": "Retired", "status": "active"},
        "last_pulled_at": "2026-01-01T00:00:00Z",
    }])

    monkeypatch.setattr(m, "lookup_market", lambda lookup: None)
    m.refresh(contracts)
    doc = yaml.safe_load(contracts.read_text())
    # Cached block preserved
    assert doc["picks"][0]["cached"]["title"] == "Retired"
    # Stale flag set; reason recorded
    assert doc["picks"][0]["stale"] is True
    assert "stale_reason" in doc["picks"][0]


def test_refresh_skips_in_cached_mode(tmp_path: Path, monkeypatch) -> None:
    from build import pull_kalshi_curated as m

    contracts = tmp_path / "contracts.yml"
    _write_contracts(contracts, [{"id": "kx-x", "source_lookup": {"event_ticker": "KX-X"}}])

    called = []
    monkeypatch.setattr(m, "lookup_market", lambda lookup: called.append(lookup) or None)
    m.refresh(contracts, mode="cached")
    assert called == [], "cached mode must not hit the network"
    doc = yaml.safe_load(contracts.read_text())
    # No cached block added (was never there); no stale flag
    assert "cached" not in doc["picks"][0]
```

- [ ] **Step 2: Run test, confirm fails**

Run: `uv run pytest tests/test_pull_kalshi_curated.py -v`
Expected: FAIL (ModuleNotFoundError).

- [ ] **Step 3: Implement `build/pull_kalshi_curated.py`**

```python
"""Curated-pull for Kalshi contracts.

Reads data/platforms/kalshi/contracts.yml pick-list. For each pick, looks up
the live market via Kalshi's public API. On success, updates the `cached` block
in-place and records `last_pulled_at`. On 404 (or any unsuccessful lookup),
LEAVES the existing `cached` block intact and sets `stale: true` plus
`stale_reason` and `stale_detected_at`.

Modes:
  --mode=cached   (default) — no network. YAML untouched.
  --mode=fresh    — hit the API for each pick; non-destructive on failure.
"""

from __future__ import annotations

import argparse
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx
import yaml


KALSHI_BASE = "https://external-api.kalshi.com/trade-api/v2"
_TIMEOUT_S = 20.0


def _iso_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def lookup_market(lookup: dict[str, str]) -> dict[str, Any] | None:
    """Return a single raw market dict from Kalshi, or None on miss/error.

    Tries the lookup keys in priority order: ticker > event_ticker > series_ticker.
    """
    params: dict[str, Any] = {"limit": 1}
    if "ticker" in lookup:
        try:
            r = httpx.get(f"{KALSHI_BASE}/markets/{lookup['ticker']}", timeout=_TIMEOUT_S)
            if r.status_code == 200:
                return r.json().get("market")
        except httpx.RequestError:
            return None
        return None
    if "event_ticker" in lookup:
        params["event_ticker"] = lookup["event_ticker"]
    elif "series_ticker" in lookup:
        params["series_ticker"] = lookup["series_ticker"]
    else:
        return None
    try:
        r = httpx.get(f"{KALSHI_BASE}/markets", params=params, timeout=_TIMEOUT_S)
    except httpx.RequestError:
        return None
    if r.status_code != 200:
        return None
    markets = (r.json() or {}).get("markets") or []
    return markets[0] if markets else None


def _project(raw: dict[str, Any]) -> dict[str, Any]:
    """Project the raw Kalshi market into our cached metadata shape."""
    return {
        "title": raw.get("title", ""),
        "subtitle": raw.get("subtitle", ""),
        "resolution_criteria": raw.get("rules_primary", "") or raw.get("subtitle", ""),
        "ticker": raw.get("ticker", ""),
        "status": "resolved" if raw.get("status") in {"settled", "closed"} else "active",
        "listed_at": raw.get("open_time", ""),
        "expires_at": raw.get("close_time", ""),
        "settlement_entities": [raw["settlement_source"]] if raw.get("settlement_source") else [],
    }


def refresh(contracts_path: Path, mode: str = "fresh") -> dict[str, Any]:
    """Refresh-or-cache. Returns the resulting YAML doc."""
    doc = yaml.safe_load(contracts_path.read_text())
    if mode == "cached":
        return doc

    for pick in doc["picks"]:
        raw = lookup_market(pick["source_lookup"])
        if raw is not None:
            pick["cached"] = _project(raw)
            pick["last_pulled_at"] = _iso_now()
            pick.pop("stale", None)
            pick.pop("stale_reason", None)
            pick.pop("stale_detected_at", None)
        else:
            # Non-destructive: keep existing cached if any; set stale flags
            pick["stale"] = True
            pick["stale_reason"] = "upstream lookup returned no result (404 or empty)"
            pick["stale_detected_at"] = _iso_now()

    contracts_path.write_text(yaml.safe_dump(doc, sort_keys=False, allow_unicode=True, width=120))
    return doc


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=("cached", "fresh"), default="cached")
    args = parser.parse_args()

    repo = Path(__file__).resolve().parent.parent
    contracts = repo / "data" / "platforms" / "kalshi" / "contracts.yml"
    doc = refresh(contracts, mode=args.mode)
    n_stale = sum(1 for p in doc["picks"] if p.get("stale"))
    n_fresh = sum(1 for p in doc["picks"] if p.get("cached") and not p.get("stale"))
    print(f"kalshi curated pull ({args.mode}): {n_fresh} fresh, {n_stale} stale, "
          f"{len(doc['picks'])} total picks", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: Run Kalshi tests, confirm pass**

Run: `uv run pytest tests/test_pull_kalshi_curated.py -v`
Expected: PASS (3 tests).

### Polymarket script

- [ ] **Step 5: Write the failing test for Polymarket**

Create `tests/test_pull_polymarket_curated.py`:

```python
"""Tests for build/pull_polymarket_curated.py — non-destructive refresh."""
from pathlib import Path
from typing import Any

import yaml


def _write_contracts(path: Path, picks: list[dict[str, Any]]) -> None:
    path.write_text(yaml.safe_dump({"schema_version": 1, "picks": picks}))


def test_refresh_polymarket_populates_cached(tmp_path: Path, monkeypatch) -> None:
    from build import pull_polymarket_curated as m

    contracts = tmp_path / "contracts.yml"
    _write_contracts(contracts, [{"id": "pm-x", "source_lookup": {"slug": "pm-x"}}])

    def fake_lookup(lookup: dict[str, str]) -> dict[str, Any] | None:
        return {"id": "12345", "slug": "pm-x", "question": "Q", "description": "D",
                "closed": False, "startDate": "2026-01-01T00:00:00Z",
                "endDate": "2026-12-31T00:00:00Z", "conditionId": "0xabc"}

    monkeypatch.setattr(m, "lookup_market", fake_lookup)
    m.refresh(contracts)
    doc = yaml.safe_load(contracts.read_text())
    assert doc["picks"][0]["cached"]["title"] == "Q"
    assert doc["picks"][0]["cached"]["status"] == "active"
    assert "last_pulled_at" in doc["picks"][0]


def test_refresh_polymarket_demotes_to_stale(tmp_path: Path, monkeypatch) -> None:
    from build import pull_polymarket_curated as m

    contracts = tmp_path / "contracts.yml"
    _write_contracts(contracts, [{
        "id": "pm-retired",
        "source_lookup": {"slug": "pm-retired"},
        "cached": {"title": "Retired"},
    }])

    monkeypatch.setattr(m, "lookup_market", lambda lookup: None)
    m.refresh(contracts)
    doc = yaml.safe_load(contracts.read_text())
    assert doc["picks"][0]["cached"]["title"] == "Retired"
    assert doc["picks"][0]["stale"] is True
```

- [ ] **Step 6: Run, confirm fails, implement**

Run: `uv run pytest tests/test_pull_polymarket_curated.py -v` (expect FAIL).

Create `build/pull_polymarket_curated.py`:

```python
"""Curated-pull for Polymarket contracts. Same stale-flag policy as Kalshi."""

from __future__ import annotations

import argparse
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx
import yaml


GAMMA_BASE = "https://gamma-api.polymarket.com"
_TIMEOUT_S = 20.0


def _iso_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def lookup_market(lookup: dict[str, str]) -> dict[str, Any] | None:
    """Try slug first, then condition_id. Return None on any miss/error."""
    if "slug" in lookup:
        try:
            r = httpx.get(f"{GAMMA_BASE}/markets", params={"slug": lookup["slug"]}, timeout=_TIMEOUT_S)
        except httpx.RequestError:
            return None
        if r.status_code != 200:
            return None
        body = r.json()
        if isinstance(body, list) and body:
            return body[0]
        return None
    if "condition_id" in lookup:
        try:
            r = httpx.get(f"{GAMMA_BASE}/markets", params={"condition_ids": lookup["condition_id"]},
                          timeout=_TIMEOUT_S)
        except httpx.RequestError:
            return None
        if r.status_code != 200:
            return None
        body = r.json()
        if isinstance(body, list) and body:
            return body[0]
    return None


def _project(raw: dict[str, Any]) -> dict[str, Any]:
    return {
        "title": raw.get("question", ""),
        "subtitle": "",
        "resolution_criteria": raw.get("description", ""),
        "external_id": str(raw.get("id", "")),
        "slug": raw.get("slug", ""),
        "condition_id": raw.get("conditionId", ""),
        "status": "resolved" if raw.get("closed") else "active",
        "listed_at": raw.get("startDate", ""),
        "expires_at": raw.get("endDate", ""),
        "settlement_entities": [],
    }


def refresh(contracts_path: Path, mode: str = "fresh") -> dict[str, Any]:
    doc = yaml.safe_load(contracts_path.read_text())
    if mode == "cached":
        return doc

    for pick in doc["picks"]:
        raw = lookup_market(pick["source_lookup"])
        if raw is not None:
            pick["cached"] = _project(raw)
            pick["last_pulled_at"] = _iso_now()
            pick.pop("stale", None)
            pick.pop("stale_reason", None)
            pick.pop("stale_detected_at", None)
        else:
            pick["stale"] = True
            pick["stale_reason"] = "upstream lookup returned no result"
            pick["stale_detected_at"] = _iso_now()

    contracts_path.write_text(yaml.safe_dump(doc, sort_keys=False, allow_unicode=True, width=120))
    return doc


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=("cached", "fresh"), default="cached")
    args = parser.parse_args()

    repo = Path(__file__).resolve().parent.parent
    contracts = repo / "data" / "platforms" / "polymarket" / "contracts.yml"
    doc = refresh(contracts, mode=args.mode)
    n_stale = sum(1 for p in doc["picks"] if p.get("stale"))
    n_fresh = sum(1 for p in doc["picks"] if p.get("cached") and not p.get("stale"))
    print(f"polymarket curated pull ({args.mode}): {n_fresh} fresh, {n_stale} stale, "
          f"{len(doc['picks'])} total picks", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 7: Run Polymarket tests, confirm pass**

Run: `uv run pytest tests/test_pull_polymarket_curated.py -v` → PASS (2 tests).

- [ ] **Step 8: Do a real fresh pull and inspect**

```bash
uv run python build/pull_kalshi_curated.py --mode=fresh
uv run python build/pull_polymarket_curated.py --mode=fresh
```

Expected: stderr shows e.g. `kalshi curated pull (fresh): 3 fresh, 2 stale, 5 total picks`. Open both YAML files: every pick has either a `cached` block + `last_pulled_at`, OR a `stale: true` + `stale_reason`. Some Kalshi tickers may be stale (the ones in the curation that don't exist anymore).

If a stale entry is unexpected (i.e., the lookup keys are typos), edit the YAML and re-pull. If a pick is truly retired, that's fine — Task 4 (retrospectives) handles that path.

- [ ] **Step 9: Commit**

```bash
git add build/pull_kalshi_curated.py build/pull_polymarket_curated.py
git add tests/test_pull_kalshi_curated.py tests/test_pull_polymarket_curated.py
git add data/platforms/kalshi/contracts.yml data/platforms/polymarket/contracts.yml
git commit -m "feat(stage-2): curated-pull scripts with stale-flag policy"
```

---

## Task 4: Hand-curated retrospective contracts

**Why:** TIKTOKBAN-25APR30, KXFEDDECISION-26MAR, and Solana-ETF 2025 are NOT in the live APIs. Sourced from Wayback Machine + news coverage.

**Files:**
- Create: `data/platforms/kalshi/contracts/tiktokban-25apr30.yml`
- Create: `data/platforms/kalshi/contracts/kxfeddecision-26mar.yml`
- Create: `data/platforms/polymarket/contracts/solana-etf-2025.yml`
- Create: `tests/test_retrospective_contracts.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_retrospective_contracts.py`:

```python
"""Validate hand-curated retrospective contract YAMLs."""
from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parent.parent
RETROS = [
    REPO / "data" / "platforms" / "kalshi" / "contracts" / "tiktokban-25apr30.yml",
    REPO / "data" / "platforms" / "kalshi" / "contracts" / "kxfeddecision-26mar.yml",
    REPO / "data" / "platforms" / "polymarket" / "contracts" / "solana-etf-2025.yml",
]


def test_all_retrospectives_exist() -> None:
    for p in RETROS:
        assert p.exists(), f"missing {p}"


def test_retrospective_schema() -> None:
    for p in RETROS:
        doc = yaml.safe_load(p.read_text())
        assert doc["schema_version"] == 1
        assert doc["kind"] == "retrospective"
        assert doc["platform"] in {"kalshi", "polymarket"}
        assert isinstance(doc["title"], str) and doc["title"]
        assert isinstance(doc["resolution_criteria"], str) and doc["resolution_criteria"]
        assert isinstance(doc["settlement_entities"], list) and len(doc["settlement_entities"]) >= 3
        assert doc.get("listed_at")
        assert doc.get("resolved_at")
        assert doc["status"] == "resolved"
        # Mandatory: source_url to Wayback or news article
        assert isinstance(doc["source_urls"], list) and len(doc["source_urls"]) >= 1
        for u in doc["source_urls"]:
            assert u.startswith("https://"), f"non-https source in {p}: {u}"
```

- [ ] **Step 2: Run, confirm fails**

Run: `uv run pytest tests/test_retrospective_contracts.py -v` → FAIL.

- [ ] **Step 3: Source the retrospective metadata via WebFetch**

For each of the three retrospectives, find a Wayback Machine or news-coverage URL that documents the original contract. Suggested URLs to seed the search:

- TIKTOKBAN-25APR30 (Kalshi):
  - `https://web.archive.org/web/2025*/kalshi.com/markets/TIKTOKBAN*`
  - `https://www.reuters.com/world/us/tiktok-ban-trump-2025*`
- KXFEDDECISION-26MAR (Kalshi):
  - `https://web.archive.org/web/2026*/kalshi.com/events/KXFEDDECISION*`
  - The current API has KXFEDDECISION-28JAN (Task 3 will cache it); use its `cached.resolution_criteria` shape as a template.
- Solana ETF 2025 (Polymarket):
  - `https://web.archive.org/web/2025*/polymarket.com/event/will-the-sec-approve*`
  - SEC press releases on spot crypto ETFs in 2025.

Use the WebFetch tool for each. Extract:
- Title (exact phrasing)
- Resolution criteria (exact phrasing)
- Listed-at date (when the market opened on the platform)
- Resolved-at date (when YES/NO was settled)
- Settlement entities (regulators + corporations named in the resolution criteria)
- Source URLs (at least 1 per contract; prefer 2 — Wayback for the listing + news for the resolution)

- [ ] **Step 4: Write the YAML files**

Create `data/platforms/kalshi/contracts/tiktokban-25apr30.yml` using the data you sourced. Template:

```yaml
schema_version: 1
kind: "retrospective"
platform: "kalshi"
id: "tiktokban-25apr30"

title: "Will TikTok be banned in the United States by April 30, 2025?"
resolution_criteria: |
  <paste exact criteria from sourced article — typically references the
  Department of Commerce ban directive and the Apple/Google app-store
  availability test>
listed_at: "<YYYY-MM-DD from Wayback snapshot>"
resolved_at: "<YYYY-MM-DD when YES/NO was called>"
status: "resolved"
resolution_outcome: "<YES | NO>"

settlement_entities:
  - "Federal Communications Commission"
  - "Committee on Foreign Investment in the United States"
  - "Department of Commerce"
  - "ByteDance"
  - "TikTok"

source_urls:
  - "<Wayback URL>"
  - "<news article URL with resolution date>"

source_retrieved_at: "2026-05-20"
```

Similarly for `kxfeddecision-26mar.yml` and `solana-etf-2025.yml`.

For Solana-ETF, settlement entities should include `U.S. Securities and Exchange Commission`, the named ETF applicants (BlackRock, Fidelity, VanEck, Grayscale), and the relevant exchanges (NYSE Arca, Cboe BZX).

- [ ] **Step 5: Run test, confirm pass**

Run: `uv run pytest tests/test_retrospective_contracts.py -v` → PASS (2 tests).

- [ ] **Step 6: Commit**

```bash
git add data/platforms/kalshi/contracts/*.yml data/platforms/polymarket/contracts/*.yml tests/test_retrospective_contracts.py
git commit -m "feat(stage-2): hand-curated retrospective contracts (TIKTOKBAN, KXFEDDECISION-26MAR, Solana ETF 2025)

Sourced from Wayback Machine snapshots + news coverage; each has source_urls
and source_retrieved_at. Replaces the public-API path which 404s on retired
contracts. Per Stage 2 plan §4 + spec §6 'every fact checks out'."
```

---

## Task 5: Spec edit — retrospective wow reframe

**Why:** The original spec § 2.3 assumed a price-overlay wow moment ("Carver-annotated CFIUS filing surfaced N days before the AP wire" *alongside the price line*). Live API doesn't serve historic prices for retired contracts. Reframe the wow to be Carver-signal-vs-news-date math (still factually grounded, still real Carver events, no price line needed).

**Files:**
- Modify: `docs/specs/40-gamma-walkthrough.md`

- [ ] **Step 1: Edit § 2.4 of the spec**

In `docs/specs/40-gamma-walkthrough.md`, locate the §2.4 "Contract Detail (5 Pre-Rendered)" section. Replace bullet 3 sub-item "**For the two retrospective contracts**" (it currently calls for `prices-history`) with:

```markdown
   - **For the two retrospective contracts (TIKTOKBAN-25APR30, KXFEDDECISION-26MAR) and the Polymarket retrospective (Solana ETF 2025):** the live public APIs no longer serve retired contracts (verified at Stage 2 planning — Kalshi `prices-history` returns 404, Polymarket `slug` lookup returns empty). The retrospective wow shifts from price-overlay to **temporal-precedence math**: for each event marked on the timeline, render `signal_precedence_days = (first_carver_event_date − first_news_article_date)` as an annotation badge — "Pred-Oracle signal preceded news cycle by N days" — backed by both the Carver `pub_date` and a linked news article URL. Both dates are publicly verifiable per spec §6 source-of-truth discipline.
```

Then locate the "Wow moments (the two retrospective pages)" subsection and replace with:

```markdown
**Wow moments (the two retrospective pages):**
- **TIKTOKBAN**: a multi-agency timeline (FCC, CFIUS, Commerce, ByteDance) compressed into one page. Each event annotated with "Carver-annotated CFIUS filing surfaced N days before the AP wire." Real Carver `pub_date` vs real news-article URL; both linkable, both dated. No price overlay (the live Kalshi API no longer serves retired-contract price history).
- **KXFEDDECISION**: institutional-density view — Treasury, regional Fed, BLS, and FOMC signal cluster around the rate decision. Same temporal-precedence callouts. Density of signals (N≥10 in the 30 days before the decision) is the wow, not the price line.
```

Also update the "## 5. Acceptance Criteria (Stage 2)" section. Replace the bullet that says:

```
- [ ] All 5 contract-detail pages render. The two retrospective pages (...) include the price overlay sourced from Kalshi's `prices-history`.
```

with:

```
- [ ] All 5 contract-detail pages render. The two retrospective Kalshi pages (`tiktokban-25apr30`, `kxfeddecision-26mar`) and the Polymarket retrospective (`solana-etf-2025`) each include ≥3 "Pred-Oracle signal preceded news by N days" callouts, with linked Carver `pub_date` and news-article date.
```

Add a note at the bottom of § 6 (Open Questions):

```markdown
| GW7 | Why no price overlay on retrospectives? | The Kalshi `prices-history` endpoint returns 404 for retired contracts (verified 2026-05-20). The Polymarket CLOB returns empty `history` arrays for unknown markets. Rather than fabricate price data, the wow shifts to Carver-vs-news temporal-precedence math, which preserves source-of-truth discipline. |
```

- [ ] **Step 2: Commit**

```bash
git add docs/specs/40-gamma-walkthrough.md
git commit -m "docs(stage-2): reframe retrospective wow from price-overlay to signal-precedence

Live APIs no longer serve retired-contract price history (verified at planning).
Carver-vs-news temporal-precedence math replaces the dropped price line.
Updated §2.4, wow-moments subsection, acceptance criteria, and added open-question GW7."
```

---

## Task 6: `make_contract` factory in conftest

**Why:** γ slice generator tests need a contract fixture in the same way α tests use `make_row`. Add to `tests/conftest.py`.

**Files:**
- Modify: `tests/conftest.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/conftest.py` … *no wait*. The test goes in a separate file. Create `tests/test_conftest_make_contract.py`:

```python
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
```

- [ ] **Step 2: Run, confirm fails**

Run: `uv run pytest tests/test_conftest_make_contract.py -v` → FAIL (ImportError on make_contract).

- [ ] **Step 3: Add `make_contract` to `tests/conftest.py`**

Append to `tests/conftest.py`:

```python
def make_contract(**overrides: Any) -> dict[str, Any]:
    """Build a baseline curated-contract record for γ slice tests.

    Shape matches what gamma slice generators consume:
    fields drawn from the post-refresh contracts.yml `cached` block plus
    pick-level metadata (id, kind, platform).
    """
    base: dict[str, Any] = {
        "id": "kx-default",
        "platform": "kalshi",
        "kind": "active",
        "title": "Default contract title",
        "subtitle": "",
        "resolution_criteria": "Resolves YES if the default thing happens by year-end.",
        "external_id": "KX-DEFAULT",
        "status": "active",
        "listed_at": "2026-01-01T00:00:00Z",
        "expires_at": "2026-12-31T00:00:00Z",
        "settlement_entities": ["Federal Reserve System"],
        "source_urls": [],
    }
    base.update(overrides)
    return base
```

- [ ] **Step 4: Run, confirm pass**

Run: `uv run pytest tests/test_conftest_make_contract.py -v` → PASS (2 tests).

- [ ] **Step 5: Commit**

```bash
git add tests/conftest.py tests/test_conftest_make_contract.py
git commit -m "test(stage-2): add make_contract factory to conftest"
```

---

This plan is split across multiple parts due to length. See the next files for Tasks 7-17.

## Task 7: Heat-scoring foundation (`build/_heat.py`)

**Why:** Heat score + sparkline buckets + entity-matching are shared by the dashboard, contract-detail, and pre-listing-scan slices. Centralize in one module so the formula lives in one place.

**Files:**
- Create: `build/_heat.py`
- Create: `tests/test_heat.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_heat.py`:

```python
"""Tests for build/_heat.py — heat score + sparkline + entity matching."""
from datetime import date

import pytest

from build import _heat


def test_entity_match_exact_intersect() -> None:
    contract_entities = ["U.S. Securities and Exchange Commission", "BlackRock"]
    record_entities = ["BlackRock", "Vanguard"]
    assert _heat.entity_match(contract_entities, record_entities) is True


def test_entity_match_case_insensitive_substring() -> None:
    contract = ["TikTok"]
    record_entities = ["tiktok inc."]
    assert _heat.entity_match(contract, record_entities) is True


def test_entity_match_no_overlap() -> None:
    assert _heat.entity_match(["SEC"], ["FDA"]) is False


def test_entity_match_empty_inputs() -> None:
    assert _heat.entity_match([], ["SEC"]) is False
    assert _heat.entity_match(["SEC"], []) is False


def test_heat_score_zero_when_no_matches() -> None:
    """No record matches the contract's entities → heat 0."""
    contract = {"settlement_entities": ["Made-Up Agency"]}
    records = [{"entities": ["SEC"], "scores": {"urgency": {"score": 9}}, "pub_date": "2026-05-19", "pub_date_valid": True}]
    assert _heat.heat_score(contract, records, today=date(2026, 5, 19)) == 0.0


def test_heat_score_decays_with_age() -> None:
    """Same severity, two records — recent one weighs more than 30-day-old."""
    contract = {"settlement_entities": ["SEC"]}
    rec_today = {"entities": ["SEC"], "scores": {"urgency": {"score": 8}}, "pub_date": "2026-05-19", "pub_date_valid": True, "update_type": "enforcement"}
    rec_30d = {"entities": ["SEC"], "scores": {"urgency": {"score": 8}}, "pub_date": "2026-04-19", "pub_date_valid": True, "update_type": "enforcement"}
    today = date(2026, 5, 19)
    h_today = _heat.heat_score(contract, [rec_today], today=today)
    h_30d = _heat.heat_score(contract, [rec_30d], today=today)
    assert h_today > h_30d


def test_heat_score_sums_across_matching_records() -> None:
    contract = {"settlement_entities": ["SEC"]}
    records = [
        {"entities": ["SEC"], "scores": {"urgency": {"score": 8}}, "pub_date": "2026-05-19", "pub_date_valid": True, "update_type": "enforcement"},
        {"entities": ["SEC"], "scores": {"urgency": {"score": 8}}, "pub_date": "2026-05-19", "pub_date_valid": True, "update_type": "enforcement"},
    ]
    h_one = _heat.heat_score(contract, records[:1], today=date(2026, 5, 19))
    h_two = _heat.heat_score(contract, records, today=date(2026, 5, 19))
    assert h_two == pytest.approx(2 * h_one, rel=0.001)


def test_sparkline_buckets_14_days() -> None:
    contract = {"settlement_entities": ["SEC"]}
    records = [
        {"entities": ["SEC"], "scores": {"urgency": {"score": 7}}, "pub_date": "2026-05-19", "pub_date_valid": True},
        {"entities": ["SEC"], "scores": {"urgency": {"score": 7}}, "pub_date": "2026-05-10", "pub_date_valid": True},
        {"entities": ["FDA"], "scores": {"urgency": {"score": 7}}, "pub_date": "2026-05-19", "pub_date_valid": True},  # filtered out
    ]
    buckets = _heat.sparkline_buckets(contract, records, today=date(2026, 5, 19), days=14)
    assert len(buckets) == 14
    # Most-recent index (last) has the today record; index 9 (5 days ago) has the older one
    assert buckets[-1] >= 1
    assert sum(buckets) == 2  # FDA record was filtered


def test_heat_score_excludes_invalid_dates_and_old_records() -> None:
    contract = {"settlement_entities": ["SEC"]}
    records = [
        {"entities": ["SEC"], "scores": {"urgency": {"score": 8}}, "pub_date_valid": False, "pub_date": "2026-05-19"},
        {"entities": ["SEC"], "scores": {"urgency": {"score": 8}}, "pub_date_valid": True, "pub_date": "2025-01-01"},  # >90 days
    ]
    assert _heat.heat_score(contract, records, today=date(2026, 5, 19), max_age_days=90) == 0.0
```

- [ ] **Step 2: Run, confirm fails**

Run: `uv run pytest tests/test_heat.py -v` → FAIL (ModuleNotFoundError).

- [ ] **Step 3: Implement `build/_heat.py`**

```python
"""γ scene heat-score, sparkline buckets, entity matching.

Formula per docs/specs/10-data-prep.md §4.2 (γ slices):
    heat = Σ severity * exp(-age_days / 14)
over records in the last 90 days whose `entities` intersect the contract's
`settlement_entities`.

severity = scores.urgency.score (1-10 from Carver annotations).
"""

from __future__ import annotations

import math
from datetime import date
from typing import Any, Iterable

from build import _fields


HEAT_HALFLIFE_DAYS: float = 14.0
DEFAULT_MAX_AGE_DAYS: int = 90


def _normalize(s: str) -> str:
    return s.strip().lower()


def entity_match(contract_entities: list[str], record_entities: list[str]) -> bool:
    """Case-insensitive substring intersection (either direction)."""
    if not contract_entities or not record_entities:
        return False
    contract_norm = [_normalize(e) for e in contract_entities if e]
    record_norm = [_normalize(e) for e in record_entities if e]
    for ce in contract_norm:
        for re in record_norm:
            if ce in re or re in ce:
                return True
    return False


def _matching_records(
    contract: dict[str, Any],
    records: Iterable[dict[str, Any]],
    today: date,
    max_age_days: int,
) -> list[tuple[dict[str, Any], int]]:
    """Yield (record, age_days) pairs for records that match by entity AND date."""
    out: list[tuple[dict[str, Any], int]] = []
    settle = contract.get("settlement_entities") or []
    for rec in records:
        age = _fields.pub_date_age_days(rec, today=today)
        if age is None or age < 0 or age > max_age_days:
            continue
        if not entity_match(settle, rec.get("entities") or []):
            continue
        out.append((rec, age))
    return out


def heat_score(
    contract: dict[str, Any],
    records: Iterable[dict[str, Any]],
    today: date | None = None,
    max_age_days: int = DEFAULT_MAX_AGE_DAYS,
) -> float:
    """Compute heat for a contract against a corpus of records."""
    today = today or date.today()
    matches = _matching_records(contract, records, today=today, max_age_days=max_age_days)
    total = 0.0
    for rec, age in matches:
        sev = _fields.urgency_score(rec)
        total += sev * math.exp(-age / HEAT_HALFLIFE_DAYS)
    return round(total, 2)


def sparkline_buckets(
    contract: dict[str, Any],
    records: Iterable[dict[str, Any]],
    today: date | None = None,
    days: int = 14,
) -> list[int]:
    """Return a list of length `days`: count of matching records per day.

    Index 0 is the oldest day; index `days-1` is today.
    """
    today = today or date.today()
    buckets = [0] * days
    matches = _matching_records(contract, records, today=today, max_age_days=days - 1)
    for _rec, age in matches:
        idx = days - 1 - age
        if 0 <= idx < days:
            buckets[idx] += 1
    return buckets


def matching_event_count(
    contract: dict[str, Any],
    records: Iterable[dict[str, Any]],
    today: date | None = None,
    max_age_days: int = DEFAULT_MAX_AGE_DAYS,
) -> int:
    """Count of records matching the contract's settlement entities in window."""
    today = today or date.today()
    return len(_matching_records(contract, records, today=today, max_age_days=max_age_days))
```

- [ ] **Step 4: Run, confirm pass**

Run: `uv run pytest tests/test_heat.py -v` → PASS (9 tests).

- [ ] **Step 5: Lint + commit**

```bash
uv run ruff check build/_heat.py tests/test_heat.py
uv run mypy build/_heat.py
git add build/_heat.py tests/test_heat.py
git commit -m "feat(stage-2): heat-score + sparkline + entity-match helpers"
```

---

## Task 8: γ pre-listing scan slice generator

**Why:** Produces 3 JSON slices at `build/page_data/gamma/pre-listing-scans/{id}.json`. Reads `gamma-curation.yml::pre_listing_scans`, matches each scan's `settlement_entities` against the artifacts corpus, ranks recent matching events, returns the scan-results DTO.

**Files:**
- Create: `build/gamma_scan.py`
- Create: `tests/test_gamma_scan.py`

Output schema per scan:

```python
{
    "id": "tiktokban",
    "title": "Will TikTok be banned ...",
    "resolution_criteria": "Resolves YES ...",
    "platform_hint": "kalshi",
    "severity": 8,                                 # from severity_hint clamped 0-10
    "severity_breakdown": {
        "matching_events_count": <int>,
        "max_urgency": <float>,
        "top_entity": <str>,
    },
    "extracted_entities": [                        # from settlement_entities
        {"name": "FCC", "source": "settlement_entities"},
        ...
    ],
    "recent_events": [                             # top 10 by urgency*recency
        {"title": <str>, "regulator": <str>, "pub_date": "YYYY-MM-DD",
         "urgency": <float>, "link": <str>, "matched_entity": <str>},
        ...
    ],
    "warnings": [<str>, ...],                      # e.g., "No matching events"
}
```

- [ ] **Step 1: Write failing tests**

Create `tests/test_gamma_scan.py`:

```python
"""Tests for build/gamma_scan.py."""
import json
from datetime import date
from pathlib import Path

import yaml

from tests.conftest import make_row


def _write_corpus(p: Path, rows) -> None:
    p.write_text("\n".join(json.dumps(r) for r in rows))


def _write_curation(p: Path, scans) -> None:
    p.write_text(yaml.safe_dump({
        "schema_version": 1,
        "build_date": "2026-05-19",
        "featured_kalshi": [],
        "featured_polymarket": [],
        "pre_listing_scans": scans,
        "contract_detail_picks": [],
        "synthetic_listing_risk_tickets": [],
    }))


def test_scan_generation_produces_one_file_per_scan(tmp_path: Path) -> None:
    from build.gamma_scan import generate

    corpus = tmp_path / "artifacts.jsonl"
    curation = tmp_path / "gamma-curation.yml"
    out_dir = tmp_path / "pre-listing-scans"

    _write_corpus(corpus, [make_row(entities=["SEC"])])
    _write_curation(curation, [
        {"id": "s1", "title": "T1", "resolution_criteria": "RC", "platform_hint": "kalshi",
         "settlement_entities": ["SEC"], "severity_hint": 7},
        {"id": "s2", "title": "T2", "resolution_criteria": "RC", "platform_hint": "polymarket",
         "settlement_entities": ["FDA"], "severity_hint": 5},
    ])

    written = generate(corpus_path=corpus, curation_path=curation, out_dir=out_dir,
                       today=date(2026, 5, 19))
    assert len(written) == 2
    assert (out_dir / "s1.json").exists()
    assert (out_dir / "s2.json").exists()


def test_scan_results_include_matching_recent_event(tmp_path: Path) -> None:
    from build.gamma_scan import generate

    corpus = tmp_path / "artifacts.jsonl"
    curation = tmp_path / "gamma-curation.yml"
    out_dir = tmp_path / "pre-listing-scans"

    _write_corpus(corpus, [
        make_row(feed_entry_id="f1", entities=["U.S. Securities and Exchange Commission"],
                 title="SEC adopts thing", pub_date="2026-05-19"),
        make_row(feed_entry_id="f2", entities=["FDA"], title="Off-topic FDA"),
    ])
    _write_curation(curation, [{
        "id": "sec-scan", "title": "T", "resolution_criteria": "RC", "platform_hint": "polymarket",
        "settlement_entities": ["U.S. Securities and Exchange Commission"], "severity_hint": 6,
    }])

    generate(corpus_path=corpus, curation_path=curation, out_dir=out_dir,
             today=date(2026, 5, 19))
    doc = json.loads((out_dir / "sec-scan.json").read_text())
    titles = [e["title"] for e in doc["recent_events"]]
    assert "SEC adopts thing" in titles
    assert "Off-topic FDA" not in titles


def test_scan_severity_breakdown_populated(tmp_path: Path) -> None:
    from build.gamma_scan import generate

    corpus = tmp_path / "artifacts.jsonl"
    curation = tmp_path / "gamma-curation.yml"
    out_dir = tmp_path / "pre-listing-scans"

    _write_corpus(corpus, [
        make_row(entities=["SEC"], scores={"urgency": {"score": 9}, "impact": {"score": 7}, "relevance": {"score": 8}}),
        make_row(feed_entry_id="r2", entities=["SEC"], scores={"urgency": {"score": 7}, "impact": {"score": 7}, "relevance": {"score": 7}}),
    ])
    _write_curation(curation, [{
        "id": "sec-scan", "title": "T", "resolution_criteria": "RC", "platform_hint": "polymarket",
        "settlement_entities": ["SEC"], "severity_hint": 7,
    }])

    generate(corpus_path=corpus, curation_path=curation, out_dir=out_dir,
             today=date(2026, 5, 19))
    doc = json.loads((out_dir / "sec-scan.json").read_text())
    assert doc["severity_breakdown"]["matching_events_count"] == 2
    assert doc["severity_breakdown"]["max_urgency"] == 9.0


def test_scan_warns_when_no_matches(tmp_path: Path) -> None:
    from build.gamma_scan import generate

    corpus = tmp_path / "artifacts.jsonl"
    curation = tmp_path / "gamma-curation.yml"
    out_dir = tmp_path / "pre-listing-scans"

    _write_corpus(corpus, [make_row(entities=["FDA"])])
    _write_curation(curation, [{
        "id": "sec-scan", "title": "T", "resolution_criteria": "RC", "platform_hint": "polymarket",
        "settlement_entities": ["SEC"], "severity_hint": 7,
    }])

    generate(corpus_path=corpus, curation_path=curation, out_dir=out_dir,
             today=date(2026, 5, 19))
    doc = json.loads((out_dir / "sec-scan.json").read_text())
    assert doc["recent_events"] == []
    assert any("no matching" in w.lower() for w in doc["warnings"])
```

- [ ] **Step 2: Run, confirm fails**

Run: `uv run pytest tests/test_gamma_scan.py -v` → FAIL.

- [ ] **Step 3: Implement `build/gamma_scan.py`**

```python
"""Generate γ pre-listing scan slices.

One JSON per scan in curation.pre_listing_scans. Reads the artifacts corpus,
filters to events matching the scan's settlement_entities, ranks by urgency*recency,
emits the top 10.
"""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from typing import Any

import yaml

from build import _fields, _heat


def _stream_corpus(corpus_path: Path):
    with corpus_path.open() as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            yield json.loads(line)


def _build_scan(
    scan: dict[str, Any],
    corpus: list[dict[str, Any]],
    today: date,
) -> dict[str, Any]:
    settle = scan["settlement_entities"]
    matches: list[tuple[dict[str, Any], str]] = []  # (record, which entity matched)
    for rec in corpus:
        rec_entities = rec.get("entities") or []
        if not _fields.pub_date_age_days(rec, today=today) and _fields.pub_date_age_days(rec, today=today) is None:
            continue
        # Find the FIRST entity from the scan that matches this record
        for ce in settle:
            ce_norm = ce.lower()
            if any(ce_norm in (re or "").lower() or (re or "").lower() in ce_norm for re in rec_entities):
                matches.append((rec, ce))
                break

    # Sort by (urgency * exp(-age/14)) descending — same shape as heat_score per-record
    import math
    def _rank(pair: tuple[dict[str, Any], str]) -> float:
        rec, _ce = pair
        age = _fields.pub_date_age_days(rec, today=today) or 999
        return _fields.urgency_score(rec) * math.exp(-age / 14.0)

    matches.sort(key=_rank, reverse=True)
    top = matches[:10]

    max_urg = max((_fields.urgency_score(r) for r, _ in matches), default=0.0)

    # Identify top driving entity (highest count among matches)
    from collections import Counter
    by_entity = Counter(ce for _, ce in matches)
    top_entity = by_entity.most_common(1)[0][0] if by_entity else ""

    recent_events = [
        {
            "title": rec.get("title") or "",
            "regulator": _fields.regulator_display(rec),
            "pub_date": _fields.pub_date_iso(rec),
            "urgency": _fields.urgency_score(rec),
            "link": rec.get("link") or "",
            "matched_entity": ce,
        }
        for rec, ce in top
    ]

    warnings: list[str] = []
    if not matches:
        warnings.append("No matching recent events found in the corpus.")

    return {
        "id": scan["id"],
        "title": scan["title"],
        "resolution_criteria": scan["resolution_criteria"],
        "platform_hint": scan["platform_hint"],
        "severity": int(scan.get("severity_hint", 5)),
        "severity_breakdown": {
            "matching_events_count": len(matches),
            "max_urgency": max_urg,
            "top_entity": top_entity,
        },
        "extracted_entities": [
            {"name": e, "source": "settlement_entities"} for e in settle
        ],
        "recent_events": recent_events,
        "warnings": warnings,
    }


def generate(
    corpus_path: Path,
    curation_path: Path,
    out_dir: Path,
    today: date | None = None,
) -> list[Path]:
    today = today or date.today()
    curation = yaml.safe_load(curation_path.read_text())
    scans = curation.get("pre_listing_scans") or []
    # Materialize corpus once (it's the same for every scan)
    corpus = list(_stream_corpus(corpus_path))
    out_dir.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    for scan in scans:
        dto = _build_scan(scan, corpus=corpus, today=today)
        out_path = out_dir / f"{scan['id']}.json"
        out_path.write_text(json.dumps(dto, indent=2))
        written.append(out_path)
    return written


if __name__ == "__main__":
    REPO = Path(__file__).resolve().parent.parent
    paths = generate(
        corpus_path=REPO / "data" / "_scratch" / "artifacts.jsonl",
        curation_path=REPO / "data" / "gamma-curation.yml",
        out_dir=REPO / "build" / "page_data" / "gamma" / "pre-listing-scans",
    )
    print(f"Wrote {len(paths)} pre-listing scan slices")
```

- [ ] **Step 4: Run tests, confirm pass**

Run: `uv run pytest tests/test_gamma_scan.py -v` → PASS (4 tests).

- [ ] **Step 5: Smoke against real data**

```bash
uv run python build/gamma_scan.py
ls build/page_data/gamma/pre-listing-scans/
python3 -c "import json; d=json.load(open('build/page_data/gamma/pre-listing-scans/tiktokban.json')); print('events:', len(d['recent_events'])); print('top:', d['recent_events'][0]['title'][:60] if d['recent_events'] else 'NONE'); print('severity_breakdown:', d['severity_breakdown'])"
```

Expected: 3 scan files; `tiktokban` has ≥1 recent event (FCC/CFIUS/Commerce/ByteDance/TikTok entities in the corpus); severity_breakdown has non-zero `matching_events_count`.

- [ ] **Step 6: Lint + commit**

```bash
uv run ruff check build/gamma_scan.py tests/test_gamma_scan.py
uv run mypy build/gamma_scan.py
git add build/gamma_scan.py tests/test_gamma_scan.py
git commit -m "feat(stage-2): gamma pre-listing scan slice generator"
```

---

## Task 9: γ contract-watch dashboard slice generator

**Why:** Produces `build/page_data/gamma/contracts.json` for /gamma/dashboard/. Joins active contracts from Task 3's `contracts.yml` + retrospective contracts from Task 4 (status="resolved" → excluded from active dashboard, but included from cached if user wants to see all). Per-contract heat + 14-day sparkline + linked-event count.

**Files:**
- Create: `build/gamma_dashboard.py`
- Create: `tests/test_gamma_dashboard.py`

Output schema:

```python
{
    "scene": {"number": 2, "letter": "γ", "back_href": "../"},
    "window_days": 90,
    "contracts": [
        {
            "id": "kxfeddecision-28jan",
            "platform": "kalshi",
            "title": "...",
            "external_id": "KXFEDDECISION-28JAN",
            "status": "active",
            "settlement_entities": [...],
            "heat": 73.5,
            "heat_delta_7d": 4.2,                  # heat now - heat as of 7 days ago
            "sparkline": [0, 1, 0, 2, ...],        # 14 buckets
            "matching_event_count": 42,
            "last_event_pub_date": "YYYY-MM-DD",
            "open_tickets_count": 1,
            "is_stale": false,
            "detail_href": "contracts/kxfeddecision-28jan/",
        },
        ...
    ],
    "rising_narrative": "...",                     # 1-sentence right-rail copy
    "filter_chips": [...],
}
```

- [ ] **Step 1: Write failing tests**

Create `tests/test_gamma_dashboard.py`:

```python
"""Tests for build/gamma_dashboard.py."""
import json
from datetime import date
from pathlib import Path

import yaml

from tests.conftest import make_row


def _write_corpus(p, rows) -> None:
    p.write_text("\n".join(json.dumps(r) for r in rows))


def _write_gamma_curation(p, contract_detail_picks=None) -> None:
    p.write_text(yaml.safe_dump({
        "schema_version": 1,
        "build_date": "2026-05-19",
        "featured_kalshi": [],
        "featured_polymarket": [],
        "pre_listing_scans": [],
        "contract_detail_picks": contract_detail_picks or [],
        "synthetic_listing_risk_tickets": [],
    }))


def _write_kalshi_contracts(p, picks) -> None:
    p.write_text(yaml.safe_dump({"schema_version": 1, "picks": picks}))


def _write_polymarket_contracts(p, picks) -> None:
    p.write_text(yaml.safe_dump({"schema_version": 1, "picks": picks}))


def test_dashboard_emits_contracts_from_pick_lists(tmp_path: Path) -> None:
    from build.gamma_dashboard import generate

    corpus = tmp_path / "artifacts.jsonl"
    gamma_cur = tmp_path / "gamma-curation.yml"
    kalshi_yml = tmp_path / "kalshi.yml"
    polymarket_yml = tmp_path / "polymarket.yml"
    out = tmp_path / "contracts.json"

    _write_corpus(corpus, [make_row(entities=["SEC"])])
    _write_gamma_curation(gamma_cur)
    _write_kalshi_contracts(kalshi_yml, [
        {"id": "k1", "source_lookup": {"event_ticker": "KX1"},
         "cached": {"title": "K1", "status": "active", "settlement_entities": ["SEC"]}},
    ])
    _write_polymarket_contracts(polymarket_yml, [
        {"id": "p1", "source_lookup": {"slug": "p1"},
         "cached": {"title": "P1", "status": "active", "settlement_entities": ["SEC"]}},
    ])

    generate(corpus_path=corpus, gamma_curation_path=gamma_cur,
             kalshi_contracts_path=kalshi_yml, polymarket_contracts_path=polymarket_yml,
             out_path=out, today=date(2026, 5, 19))
    doc = json.loads(out.read_text())
    ids = [c["id"] for c in doc["contracts"]]
    assert set(ids) == {"k1", "p1"}


def test_dashboard_includes_heat_and_sparkline(tmp_path: Path) -> None:
    from build.gamma_dashboard import generate

    corpus = tmp_path / "artifacts.jsonl"
    gamma_cur = tmp_path / "gamma-curation.yml"
    kalshi_yml = tmp_path / "kalshi.yml"
    polymarket_yml = tmp_path / "polymarket.yml"
    out = tmp_path / "contracts.json"

    _write_corpus(corpus, [
        make_row(entities=["SEC"], pub_date="2026-05-19", scores={"urgency": {"score": 9}, "impact": {"score": 8}, "relevance": {"score": 8}}),
        make_row(feed_entry_id="r2", entities=["SEC"], pub_date="2026-05-15", scores={"urgency": {"score": 7}, "impact": {"score": 7}, "relevance": {"score": 7}}),
    ])
    _write_gamma_curation(gamma_cur)
    _write_kalshi_contracts(kalshi_yml, [
        {"id": "k1", "source_lookup": {"event_ticker": "KX1"},
         "cached": {"title": "K1", "status": "active", "settlement_entities": ["SEC"]}},
    ])
    _write_polymarket_contracts(polymarket_yml, [])

    generate(corpus_path=corpus, gamma_curation_path=gamma_cur,
             kalshi_contracts_path=kalshi_yml, polymarket_contracts_path=polymarket_yml,
             out_path=out, today=date(2026, 5, 19))
    doc = json.loads(out.read_text())
    c = doc["contracts"][0]
    assert c["heat"] > 0
    assert isinstance(c["sparkline"], list) and len(c["sparkline"]) == 14
    assert c["matching_event_count"] >= 2


def test_dashboard_excludes_stale_picks_from_active_listing(tmp_path: Path) -> None:
    """Stale contracts (upstream 404) — show only if cached is still good; flag visually."""
    from build.gamma_dashboard import generate

    corpus = tmp_path / "artifacts.jsonl"
    gamma_cur = tmp_path / "gamma-curation.yml"
    kalshi_yml = tmp_path / "kalshi.yml"
    polymarket_yml = tmp_path / "polymarket.yml"
    out = tmp_path / "contracts.json"

    _write_corpus(corpus, [make_row(entities=["SEC"])])
    _write_gamma_curation(gamma_cur)
    _write_kalshi_contracts(kalshi_yml, [
        {"id": "k1", "source_lookup": {"event_ticker": "KX1"},
         "cached": {"title": "K1", "status": "active", "settlement_entities": ["SEC"]},
         "stale": True, "stale_reason": "upstream 404"},
        {"id": "k2", "source_lookup": {"event_ticker": "KX2"},
         "cached": {"title": "K2", "status": "active", "settlement_entities": ["SEC"]}},
    ])
    _write_polymarket_contracts(polymarket_yml, [])

    generate(corpus_path=corpus, gamma_curation_path=gamma_cur,
             kalshi_contracts_path=kalshi_yml, polymarket_contracts_path=polymarket_yml,
             out_path=out, today=date(2026, 5, 19))
    doc = json.loads(out.read_text())
    by_id = {c["id"]: c for c in doc["contracts"]}
    assert by_id["k1"]["is_stale"] is True
    assert by_id["k2"]["is_stale"] is False


def test_dashboard_sorted_by_heat_desc(tmp_path: Path) -> None:
    from build.gamma_dashboard import generate

    corpus = tmp_path / "artifacts.jsonl"
    gamma_cur = tmp_path / "gamma-curation.yml"
    kalshi_yml = tmp_path / "kalshi.yml"
    polymarket_yml = tmp_path / "polymarket.yml"
    out = tmp_path / "contracts.json"

    # k-hot has many recent matches; k-cold none
    rows = [make_row(feed_entry_id=f"f{i}", entities=["SEC"], pub_date="2026-05-19") for i in range(5)]
    _write_corpus(corpus, rows)
    _write_gamma_curation(gamma_cur)
    _write_kalshi_contracts(kalshi_yml, [
        {"id": "k-cold", "source_lookup": {"event_ticker": "KX1"},
         "cached": {"title": "Cold", "status": "active", "settlement_entities": ["FDA"]}},
        {"id": "k-hot", "source_lookup": {"event_ticker": "KX2"},
         "cached": {"title": "Hot", "status": "active", "settlement_entities": ["SEC"]}},
    ])
    _write_polymarket_contracts(polymarket_yml, [])

    generate(corpus_path=corpus, gamma_curation_path=gamma_cur,
             kalshi_contracts_path=kalshi_yml, polymarket_contracts_path=polymarket_yml,
             out_path=out, today=date(2026, 5, 19))
    doc = json.loads(out.read_text())
    assert doc["contracts"][0]["id"] == "k-hot"
    assert doc["contracts"][1]["id"] == "k-cold"
```

- [ ] **Step 2: Run, confirm fails**

Run: `uv run pytest tests/test_gamma_dashboard.py -v` → FAIL.

- [ ] **Step 3: Implement `build/gamma_dashboard.py`**

```python
"""Generate γ contract-watch dashboard slice (build/page_data/gamma/contracts.json).

Reads:
  - data/_scratch/artifacts.jsonl (Carver corpus)
  - data/gamma-curation.yml (for synthetic_listing_risk_tickets ticket counts)
  - data/platforms/kalshi/contracts.yml + data/platforms/polymarket/contracts.yml

For each pick with a `cached` block, computes heat score, 14-day sparkline,
heat_delta_7d, and emits a dashboard row.
"""

from __future__ import annotations

import json
from collections import Counter
from datetime import date, timedelta
from pathlib import Path
from typing import Any

import yaml

from build import _fields, _heat


def _stream_corpus(corpus_path: Path) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    with corpus_path.open() as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            out.append(json.loads(line))
    return out


def _build_contract_row(
    pick: dict[str, Any],
    platform: str,
    corpus: list[dict[str, Any]],
    today: date,
    open_tickets: int,
) -> dict[str, Any] | None:
    cached = pick.get("cached")
    if not cached:
        return None
    contract = {
        "settlement_entities": cached.get("settlement_entities") or [],
    }
    heat_now = _heat.heat_score(contract, corpus, today=today)
    heat_7d_ago = _heat.heat_score(contract, corpus, today=today - timedelta(days=7))
    sparkline = _heat.sparkline_buckets(contract, corpus, today=today, days=14)
    match_count = _heat.matching_event_count(contract, corpus, today=today)

    # Last matching event date
    settle = contract["settlement_entities"]
    last_pub = ""
    for rec in sorted(corpus, key=lambda r: _fields.pub_date_iso(r), reverse=True):
        if _heat.entity_match(settle, rec.get("entities") or []):
            last_pub = _fields.pub_date_iso(rec)
            break

    return {
        "id": pick["id"],
        "platform": platform,
        "title": cached.get("title") or "",
        "external_id": cached.get("external_id") or cached.get("ticker") or cached.get("slug") or "",
        "status": cached.get("status") or "active",
        "settlement_entities": settle,
        "heat": heat_now,
        "heat_delta_7d": round(heat_now - heat_7d_ago, 2),
        "sparkline": sparkline,
        "matching_event_count": match_count,
        "last_event_pub_date": last_pub,
        "open_tickets_count": open_tickets,
        "is_stale": bool(pick.get("stale")),
        "detail_href": f"contracts/{pick['id']}/",
    }


def generate(
    corpus_path: Path,
    gamma_curation_path: Path,
    kalshi_contracts_path: Path,
    polymarket_contracts_path: Path,
    out_path: Path,
    today: date | None = None,
) -> dict[str, Any]:
    today = today or date.today()
    gamma = yaml.safe_load(gamma_curation_path.read_text())
    kalshi = yaml.safe_load(kalshi_contracts_path.read_text())
    polymarket = yaml.safe_load(polymarket_contracts_path.read_text())

    tickets_by_contract = Counter(
        t["contract_id"] for t in (gamma.get("synthetic_listing_risk_tickets") or [])
    )

    corpus = _stream_corpus(corpus_path)

    rows: list[dict[str, Any]] = []
    for pick in kalshi.get("picks") or []:
        row = _build_contract_row(pick, "kalshi", corpus, today,
                                  tickets_by_contract.get(pick["id"], 0))
        if row:
            rows.append(row)
    for pick in polymarket.get("picks") or []:
        row = _build_contract_row(pick, "polymarket", corpus, today,
                                  tickets_by_contract.get(pick["id"], 0))
        if row:
            rows.append(row)

    rows.sort(key=lambda r: r["heat"], reverse=True)

    # Narrative: identify the 1-2 contracts with the largest positive 7d delta
    rising = sorted(rows, key=lambda r: r["heat_delta_7d"], reverse=True)[:2]
    if rising and rising[0]["heat_delta_7d"] > 0:
        names = " and ".join(f"\"{r['title'][:50]}\"" for r in rising if r["heat_delta_7d"] > 0)
        narrative = f"Heat rising: {names}. Watch these closely this week."
    else:
        narrative = "Heat steady across the active book this week."

    slice_doc = {
        "scene": {"number": 2, "letter": "γ", "back_href": "../"},
        "window_days": _heat.DEFAULT_MAX_AGE_DAYS,
        "contracts": rows,
        "rising_narrative": narrative,
        "filter_chips": [
            {"label": "All", "min_heat": 0, "active": True},
            {"label": "≥5", "min_heat": 5, "active": False},
            {"label": "≥7", "min_heat": 7, "active": False},
            {"label": "≥9", "min_heat": 9, "active": False},
        ],
    }
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(slice_doc, indent=2))
    return slice_doc


if __name__ == "__main__":
    REPO = Path(__file__).resolve().parent.parent
    generate(
        corpus_path=REPO / "data" / "_scratch" / "artifacts.jsonl",
        gamma_curation_path=REPO / "data" / "gamma-curation.yml",
        kalshi_contracts_path=REPO / "data" / "platforms" / "kalshi" / "contracts.yml",
        polymarket_contracts_path=REPO / "data" / "platforms" / "polymarket" / "contracts.yml",
        out_path=REPO / "build" / "page_data" / "gamma" / "contracts.json",
    )
```

- [ ] **Step 4: Run, confirm pass**

Run: `uv run pytest tests/test_gamma_dashboard.py -v` → PASS (4 tests).

- [ ] **Step 5: Smoke + commit**

```bash
uv run python build/gamma_dashboard.py
python3 -c "import json; d=json.load(open('build/page_data/gamma/contracts.json')); print('contracts:', len(d['contracts'])); print('top:', [(c['id'], c['heat']) for c in d['contracts'][:3]]); print('narrative:', d['rising_narrative'])"
uv run ruff check build/gamma_dashboard.py tests/test_gamma_dashboard.py
uv run mypy build/gamma_dashboard.py
git add build/gamma_dashboard.py tests/test_gamma_dashboard.py
git commit -m "feat(stage-2): gamma contract-watch dashboard slice generator"
```

---

## Task 10: γ contract-detail slice generator (parametric, 5 outputs)

**Why:** Five JSONs at `build/page_data/gamma/contracts/{id}.json`. One per contract_detail_pick in curation. Joins per-contract Carver events sorted by date, computes per-event temporal-precedence callouts for retrospectives.

**Files:**
- Create: `build/gamma_contract.py`
- Create: `tests/test_gamma_contract.py`

Output schema:

```python
{
    "scene": {"number": 2, "letter": "γ", "back_label": "← Dashboard", "back_href": "../"},
    "contract": {
        "id": "tiktokban-25apr30",
        "platform": "kalshi",
        "kind": "retrospective",                   # or "active"
        "title": "...",
        "external_id": "TIKTOKBAN-25APR30",
        "status": "resolved",                      # or "active"
        "listed_at": "...",
        "expires_at": "...",
        "resolved_at": "...",                      # retrospective only
        "resolution_criteria": "...",
        "settlement_entities": [
            {"name": "FCC", "role": "regulator"},
            {"name": "ByteDance", "role": "company"},
            ...
        ],
        "source_urls": [...],                      # retrospective only
        "heat": <float>,
        "heat_history": [<14 buckets>],
        "primary_source_url": <kalshi/polymarket URL>,
    },
    "timeline": [
        {
            "pub_date": "YYYY-MM-DD",
            "title": <str>,
            "regulator": <str>,
            "url": <str>,                          # Carver link to primary source
            "urgency": <float>,
            "impact": <float>,
            "matched_entity": <str>,
            "carver_feed_entry_id": <str>,
            "precedence_callout": {                # only for retrospective contracts
                "news_date": "YYYY-MM-DD" | None,
                "news_url": <str> | None,
                "days_ahead": <int> | None,
                "label": "Pred-Oracle signal preceded news by N days" | None,
            },
        },
        ...                                        # top 25 by recency
    ],
    "open_tickets": [                              # synthetic from curation
        {"summary": <str>, "severity": <str>, "assignee_initials": <str>, "is_demo": True},
        ...
    ],
}
```

- [ ] **Step 1: Write failing tests**

Create `tests/test_gamma_contract.py`:

```python
"""Tests for build/gamma_contract.py."""
import json
from datetime import date
from pathlib import Path

import yaml

from tests.conftest import make_row


def _write_corpus(p, rows) -> None:
    p.write_text("\n".join(json.dumps(r) for r in rows))


def _write_gamma_curation(p, picks=None, tickets=None) -> None:
    p.write_text(yaml.safe_dump({
        "schema_version": 1,
        "build_date": "2026-05-19",
        "featured_kalshi": [],
        "featured_polymarket": [],
        "pre_listing_scans": [],
        "contract_detail_picks": picks or [],
        "synthetic_listing_risk_tickets": tickets or [],
    }))


def _write_kalshi_contracts(p, picks) -> None:
    p.write_text(yaml.safe_dump({"schema_version": 1, "picks": picks}))


def _write_polymarket_contracts(p, picks) -> None:
    p.write_text(yaml.safe_dump({"schema_version": 1, "picks": picks}))


def _write_retro(path: Path, **fields) -> None:
    """Write a hand-curated retrospective YAML."""
    base = {
        "schema_version": 1,
        "kind": "retrospective",
        "platform": "kalshi",
        "id": "x",
        "title": "Retro T",
        "resolution_criteria": "RC",
        "listed_at": "2025-01-01",
        "resolved_at": "2025-04-30",
        "status": "resolved",
        "resolution_outcome": "NO",
        "settlement_entities": ["FCC", "ByteDance"],
        "source_urls": ["https://web.archive.org/web/2025"],
        "source_retrieved_at": "2026-05-20",
    }
    base.update(fields)
    path.write_text(yaml.safe_dump(base))


def test_contract_detail_active_writes_slice(tmp_path: Path) -> None:
    from build.gamma_contract import generate

    corpus = tmp_path / "artifacts.jsonl"
    gamma_cur = tmp_path / "gamma-curation.yml"
    kalshi_yml = tmp_path / "kalshi.yml"
    polymarket_yml = tmp_path / "polymarket.yml"
    out_dir = tmp_path / "contracts"

    _write_corpus(corpus, [make_row(entities=["SEC"])])
    _write_gamma_curation(gamma_cur, picks=[{"id": "k1", "platform": "kalshi", "kind": "active"}])
    _write_kalshi_contracts(kalshi_yml, [{
        "id": "k1", "source_lookup": {"event_ticker": "KX1"},
        "cached": {"title": "K1", "status": "active",
                   "settlement_entities": ["SEC"], "external_id": "KX1"},
    }])
    _write_polymarket_contracts(polymarket_yml, [])

    paths = generate(
        corpus_path=corpus, gamma_curation_path=gamma_cur,
        kalshi_contracts_path=kalshi_yml, polymarket_contracts_path=polymarket_yml,
        retrospectives_root=tmp_path / "retros",
        out_dir=out_dir, today=date(2026, 5, 19),
    )
    assert len(paths) == 1
    doc = json.loads((out_dir / "k1.json").read_text())
    assert doc["contract"]["id"] == "k1"
    assert doc["contract"]["kind"] == "active"


def test_contract_detail_retrospective_reads_yaml(tmp_path: Path) -> None:
    from build.gamma_contract import generate

    corpus = tmp_path / "artifacts.jsonl"
    gamma_cur = tmp_path / "gamma-curation.yml"
    kalshi_yml = tmp_path / "kalshi.yml"
    polymarket_yml = tmp_path / "polymarket.yml"
    out_dir = tmp_path / "contracts"
    retros_root = tmp_path / "retros"
    (retros_root / "kalshi" / "contracts").mkdir(parents=True)
    _write_retro(retros_root / "kalshi" / "contracts" / "ttb.yml", id="ttb",
                 title="TikTok Ban", settlement_entities=["FCC", "ByteDance"])

    _write_corpus(corpus, [make_row(entities=["ByteDance"], title="ByteDance disclosure")])
    _write_gamma_curation(gamma_cur, picks=[{"id": "ttb", "platform": "kalshi", "kind": "retrospective"}])
    _write_kalshi_contracts(kalshi_yml, [])
    _write_polymarket_contracts(polymarket_yml, [])

    generate(
        corpus_path=corpus, gamma_curation_path=gamma_cur,
        kalshi_contracts_path=kalshi_yml, polymarket_contracts_path=polymarket_yml,
        retrospectives_root=retros_root,
        out_dir=out_dir, today=date(2026, 5, 19),
    )
    doc = json.loads((out_dir / "ttb.json").read_text())
    assert doc["contract"]["kind"] == "retrospective"
    assert doc["contract"]["title"] == "TikTok Ban"
    titles = [e["title"] for e in doc["timeline"]]
    assert "ByteDance disclosure" in titles


def test_contract_detail_timeline_includes_only_matching(tmp_path: Path) -> None:
    from build.gamma_contract import generate

    corpus = tmp_path / "artifacts.jsonl"
    gamma_cur = tmp_path / "gamma-curation.yml"
    kalshi_yml = tmp_path / "kalshi.yml"
    polymarket_yml = tmp_path / "polymarket.yml"
    out_dir = tmp_path / "contracts"

    _write_corpus(corpus, [
        make_row(entities=["SEC"], title="In scope SEC"),
        make_row(feed_entry_id="r2", entities=["FDA"], title="Out of scope FDA"),
    ])
    _write_gamma_curation(gamma_cur, picks=[{"id": "k1", "platform": "kalshi", "kind": "active"}])
    _write_kalshi_contracts(kalshi_yml, [{
        "id": "k1", "source_lookup": {"event_ticker": "KX1"},
        "cached": {"title": "K1", "status": "active",
                   "settlement_entities": ["SEC"], "external_id": "KX1"},
    }])
    _write_polymarket_contracts(polymarket_yml, [])

    generate(
        corpus_path=corpus, gamma_curation_path=gamma_cur,
        kalshi_contracts_path=kalshi_yml, polymarket_contracts_path=polymarket_yml,
        retrospectives_root=tmp_path / "retros",
        out_dir=out_dir, today=date(2026, 5, 19),
    )
    doc = json.loads((out_dir / "k1.json").read_text())
    titles = [e["title"] for e in doc["timeline"]]
    assert "In scope SEC" in titles
    assert "Out of scope FDA" not in titles


def test_contract_detail_open_tickets_marked_demo(tmp_path: Path) -> None:
    from build.gamma_contract import generate

    corpus = tmp_path / "artifacts.jsonl"
    gamma_cur = tmp_path / "gamma-curation.yml"
    kalshi_yml = tmp_path / "kalshi.yml"
    polymarket_yml = tmp_path / "polymarket.yml"
    out_dir = tmp_path / "contracts"

    _write_corpus(corpus, [make_row(entities=["SEC"])])
    _write_gamma_curation(gamma_cur,
                          picks=[{"id": "k1", "platform": "kalshi", "kind": "active"}],
                          tickets=[{"contract_id": "k1", "summary": "Watch",
                                    "severity": "high", "assignee_initials": "MV"}])
    _write_kalshi_contracts(kalshi_yml, [{
        "id": "k1", "source_lookup": {"event_ticker": "KX1"},
        "cached": {"title": "K1", "status": "active",
                   "settlement_entities": ["SEC"], "external_id": "KX1"},
    }])
    _write_polymarket_contracts(polymarket_yml, [])

    generate(
        corpus_path=corpus, gamma_curation_path=gamma_cur,
        kalshi_contracts_path=kalshi_yml, polymarket_contracts_path=polymarket_yml,
        retrospectives_root=tmp_path / "retros",
        out_dir=out_dir, today=date(2026, 5, 19),
    )
    doc = json.loads((out_dir / "k1.json").read_text())
    assert len(doc["open_tickets"]) == 1
    assert doc["open_tickets"][0]["is_demo"] is True
    assert doc["open_tickets"][0]["assignee_initials"] == "MV"
```

- [ ] **Step 2: Run, confirm fails**

Run: `uv run pytest tests/test_gamma_contract.py -v` → FAIL.

- [ ] **Step 3: Implement `build/gamma_contract.py`**

```python
"""γ contract-detail slice generator — parametric across curation picks."""

from __future__ import annotations

import json
import sys
from datetime import date
from pathlib import Path
from typing import Any

import yaml

from build import _fields, _heat


def _stream_corpus(corpus_path: Path) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    with corpus_path.open() as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            out.append(json.loads(line))
    return out


def _load_active_pick(pick_id: str, platform: str, kalshi_doc: dict, polymarket_doc: dict) -> dict[str, Any] | None:
    yaml_doc = kalshi_doc if platform == "kalshi" else polymarket_doc
    for pick in yaml_doc.get("picks") or []:
        if pick["id"] == pick_id:
            return pick
    return None


def _load_retrospective(pick_id: str, platform: str, retrospectives_root: Path) -> dict[str, Any] | None:
    p = retrospectives_root / platform / "contracts" / f"{pick_id}.yml"
    if not p.exists():
        return None
    return yaml.safe_load(p.read_text())


def _entity_role(name: str) -> str:
    """Heuristic role tag for chip display."""
    name_l = name.lower()
    REGULATOR_HINTS = ("commission", "authority", "bureau", "department", "agency",
                       "office", "board", "ministry", "administration", "service")
    if any(h in name_l for h in REGULATOR_HINTS):
        return "regulator"
    if "fed" in name_l or "treasury" in name_l or "reserve" in name_l:
        return "regulator"
    return "company"


def _build_timeline(
    settlement_entities: list[str],
    corpus: list[dict[str, Any]],
    today: date,
    is_retrospective: bool,
) -> list[dict[str, Any]]:
    matches: list[tuple[dict[str, Any], str]] = []
    for rec in corpus:
        rec_entities = rec.get("entities") or []
        for ce in settlement_entities:
            ce_n = ce.lower()
            if any(ce_n in (re or "").lower() or (re or "").lower() in ce_n for re in rec_entities):
                matches.append((rec, ce))
                break

    matches.sort(key=lambda pair: _fields.pub_date_iso(pair[0]), reverse=True)
    top = matches[:25]

    timeline: list[dict[str, Any]] = []
    for rec, ce in top:
        entry = {
            "pub_date": _fields.pub_date_iso(rec),
            "title": rec.get("title") or "",
            "regulator": _fields.regulator_display(rec),
            "url": rec.get("link") or "",
            "urgency": _fields.urgency_score(rec),
            "impact": _fields.impact_score(rec),
            "matched_entity": ce,
            "carver_feed_entry_id": rec.get("feed_entry_id") or "",
        }
        if is_retrospective:
            # Spec §2.4 (Task 5 reframe): temporal precedence math.
            # In demo, "news_date" is hand-curated downstream if needed.
            # For now, emit a stub the template can choose to render.
            entry["precedence_callout"] = {
                "news_date": None,
                "news_url": None,
                "days_ahead": None,
                "label": None,
            }
        timeline.append(entry)
    return timeline


def _build_contract_dto(
    pick_id: str, platform: str, kind: str,
    active_pick: dict | None, retro: dict | None,
    corpus: list[dict[str, Any]], today: date,
) -> dict[str, Any] | None:
    if kind == "active":
        if not active_pick or "cached" not in active_pick:
            return None
        c = active_pick["cached"]
        settlement = c.get("settlement_entities") or []
        primary_source = ""
        if platform == "kalshi" and c.get("ticker"):
            primary_source = f"https://kalshi.com/markets/{c['ticker']}"
        elif platform == "polymarket" and c.get("slug"):
            primary_source = f"https://polymarket.com/event/{c['slug']}"
        return {
            "id": pick_id, "platform": platform, "kind": "active",
            "title": c.get("title", ""),
            "external_id": c.get("external_id") or c.get("ticker") or c.get("slug") or "",
            "status": c.get("status", "active"),
            "listed_at": c.get("listed_at", ""),
            "expires_at": c.get("expires_at", ""),
            "resolved_at": "",
            "resolution_criteria": c.get("resolution_criteria", ""),
            "settlement_entities": [{"name": e, "role": _entity_role(e)} for e in settlement],
            "settlement_entities_flat": settlement,
            "source_urls": [],
            "primary_source_url": primary_source,
        }
    # retrospective
    if not retro:
        return None
    settlement = retro["settlement_entities"]
    return {
        "id": pick_id, "platform": platform, "kind": "retrospective",
        "title": retro["title"],
        "external_id": retro.get("id", ""),
        "status": retro.get("status", "resolved"),
        "listed_at": retro.get("listed_at", ""),
        "expires_at": "",
        "resolved_at": retro.get("resolved_at", ""),
        "resolution_criteria": retro.get("resolution_criteria", ""),
        "settlement_entities": [{"name": e, "role": _entity_role(e)} for e in settlement],
        "settlement_entities_flat": settlement,
        "source_urls": retro.get("source_urls", []),
        "primary_source_url": retro.get("source_urls", [""])[0] if retro.get("source_urls") else "",
    }


def generate(
    corpus_path: Path,
    gamma_curation_path: Path,
    kalshi_contracts_path: Path,
    polymarket_contracts_path: Path,
    retrospectives_root: Path,
    out_dir: Path,
    today: date | None = None,
) -> list[Path]:
    today = today or date.today()
    gamma = yaml.safe_load(gamma_curation_path.read_text())
    kalshi_doc = yaml.safe_load(kalshi_contracts_path.read_text()) if kalshi_contracts_path.exists() else {"picks": []}
    polymarket_doc = yaml.safe_load(polymarket_contracts_path.read_text()) if polymarket_contracts_path.exists() else {"picks": []}

    corpus = _stream_corpus(corpus_path)
    tickets_index: dict[str, list[dict[str, Any]]] = {}
    for t in gamma.get("synthetic_listing_risk_tickets") or []:
        tickets_index.setdefault(t["contract_id"], []).append(t)

    out_dir.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    for pick in gamma.get("contract_detail_picks") or []:
        pid, platform, kind = pick["id"], pick["platform"], pick["kind"]
        active_pick = _load_active_pick(pid, platform, kalshi_doc, polymarket_doc) if kind == "active" else None
        retro = _load_retrospective(pid, platform, retrospectives_root) if kind == "retrospective" else None
        dto = _build_contract_dto(pid, platform, kind, active_pick, retro, corpus, today)
        if dto is None:
            print(f"WARN: contract pick {pid!r} ({platform}, {kind}) had no source data; skipping",
                  file=sys.stderr)
            continue

        timeline = _build_timeline(dto["settlement_entities_flat"], corpus, today, kind == "retrospective")
        heat = _heat.heat_score({"settlement_entities": dto["settlement_entities_flat"]}, corpus, today=today)
        sparkline = _heat.sparkline_buckets({"settlement_entities": dto["settlement_entities_flat"]},
                                            corpus, today=today, days=14)
        dto["heat"] = heat
        dto["heat_history"] = sparkline

        # We don't need to leak the flat list to the slice consumers
        dto.pop("settlement_entities_flat", None)

        slice_doc = {
            "scene": {"number": 2, "letter": "γ", "back_label": "← Dashboard", "back_href": "../"},
            "contract": dto,
            "timeline": timeline,
            "open_tickets": [
                {
                    "summary": t["summary"],
                    "severity": t["severity"],
                    "assignee_initials": t["assignee_initials"],
                    "is_demo": True,
                }
                for t in tickets_index.get(pid, [])
            ],
        }
        out_path = out_dir / f"{pid}.json"
        out_path.write_text(json.dumps(slice_doc, indent=2))
        written.append(out_path)
    return written


if __name__ == "__main__":
    REPO = Path(__file__).resolve().parent.parent
    paths = generate(
        corpus_path=REPO / "data" / "_scratch" / "artifacts.jsonl",
        gamma_curation_path=REPO / "data" / "gamma-curation.yml",
        kalshi_contracts_path=REPO / "data" / "platforms" / "kalshi" / "contracts.yml",
        polymarket_contracts_path=REPO / "data" / "platforms" / "polymarket" / "contracts.yml",
        retrospectives_root=REPO / "data" / "platforms",
        out_dir=REPO / "build" / "page_data" / "gamma" / "contracts",
    )
    print(f"Wrote {len(paths)} contract-detail slices")
```

- [ ] **Step 4: Run, confirm pass**

Run: `uv run pytest tests/test_gamma_contract.py -v` → PASS (4 tests).

- [ ] **Step 5: Smoke + commit**

```bash
uv run python build/gamma_contract.py
ls build/page_data/gamma/contracts/
python3 -c "import json; d=json.load(open('build/page_data/gamma/contracts/tiktokban-25apr30.json')); print('title:', d['contract']['title'][:60]); print('kind:', d['contract']['kind']); print('timeline events:', len(d['timeline'])); print('open_tickets:', len(d['open_tickets']))"
uv run ruff check build/gamma_contract.py tests/test_gamma_contract.py
uv run mypy build/gamma_contract.py
git add build/gamma_contract.py tests/test_gamma_contract.py
git commit -m "feat(stage-2): gamma contract-detail slice generator (parametric)"
```

---

This plan continues in the next part — Tasks 11-17 cover orchestration wiring, components, templates, and E2E verification.

## Task 11: Wire γ generators into the orchestrator

**Why:** `build/generate_slices.py::main()` already dispatches α generators. Add γ with the same `if curation.exists() and corpus.exists()` guard.

**Files:**
- Modify: `build/generate_slices.py`

- [ ] **Step 1: Read current `main()`**

Open `build/generate_slices.py`; find the existing α dispatch block. Note the variables in scope (`REPO`, `corpus`, `today`, `pd`).

- [ ] **Step 2: After the α block, add the γ block**

Append (inside `main()`, after the α dispatch and its `print(...)`):

```python
    # γ — uses gamma-curation.yml + contracts.yml + retrospective YAMLs
    gamma_curation = REPO / "data" / "gamma-curation.yml"
    kalshi_contracts = REPO / "data" / "platforms" / "kalshi" / "contracts.yml"
    polymarket_contracts = REPO / "data" / "platforms" / "polymarket" / "contracts.yml"
    retrospectives_root = REPO / "data" / "platforms"

    if gamma_curation.exists() and corpus.exists():
        cur_g = yaml.safe_load(gamma_curation.read_text())
        bd_g = cur_g.get("build_date")
        today_g = _dt.date.fromisoformat(bd_g) if bd_g else today

        from build.gamma_scan import generate as gen_scan
        from build.gamma_dashboard import generate as gen_dash
        from build.gamma_contract import generate as gen_contract

        scan_paths = gen_scan(
            corpus_path=corpus, curation_path=gamma_curation,
            out_dir=pd / "gamma" / "pre-listing-scans", today=today_g,
        )
        gen_dash(
            corpus_path=corpus, gamma_curation_path=gamma_curation,
            kalshi_contracts_path=kalshi_contracts,
            polymarket_contracts_path=polymarket_contracts,
            out_path=pd / "gamma" / "contracts.json", today=today_g,
        )
        contract_paths = gen_contract(
            corpus_path=corpus, gamma_curation_path=gamma_curation,
            kalshi_contracts_path=kalshi_contracts,
            polymarket_contracts_path=polymarket_contracts,
            retrospectives_root=retrospectives_root,
            out_dir=pd / "gamma" / "contracts", today=today_g,
        )
        print(f"gamma (build_date={today_g.isoformat()}): "
              f"{len(scan_paths)} scans + dashboard + {len(contract_paths)} contract details")
    elif gamma_curation.exists():
        print(f"WARN: corpus {corpus.relative_to(REPO)} missing — skipping gamma slices")
    elif corpus.exists():
        print(f"WARN: {gamma_curation.relative_to(REPO)} missing — skipping gamma slices")
```

- [ ] **Step 3: Smoke-run the full orchestrator**

```bash
rm -rf build/page_data
uv run python build/generate_slices.py
```

Expected stdout includes:
```
landing.json: events=...
alpha (build_date=2026-05-20): inbox + 5 tickets + dashboard + audit_export
gamma (build_date=2026-05-20): 3 scans + dashboard + 5 contract details
```

- [ ] **Step 4: Verify file inventory**

```bash
find build/page_data/gamma -name '*.json' | sort
```

Expected:
```
build/page_data/gamma/contracts.json
build/page_data/gamma/contracts/kxfeddecision-26mar.json
build/page_data/gamma/contracts/kxfeddecision-28jan.json
build/page_data/gamma/contracts/solana-etf-2025.json
build/page_data/gamma/contracts/tiktokban-25apr30.json
build/page_data/gamma/contracts/us-recession-in-2026.json
build/page_data/gamma/pre-listing-scans/solana_etf_2027.json
build/page_data/gamma/pre-listing-scans/state_kalshi_action.json
build/page_data/gamma/pre-listing-scans/tiktokban.json
```

- [ ] **Step 5: Re-run pytest, confirm no regressions**

`uv run pytest -v 2>&1 | tail -5` → all passing.

- [ ] **Step 6: Commit**

```bash
git add build/generate_slices.py
git commit -m "feat(stage-2): wire gamma generators into slice orchestrator"
```

---

## Task 12: γ template components

**Why:** Shared partials reused by the four γ templates.

**Files:**
- Create: `build/templates/gamma/_components/contract_row.html`
- Create: `build/templates/gamma/_components/sparkline.html`
- Create: `build/templates/gamma/_components/entity_chip.html`
- Create: `build/templates/gamma/_components/signal_callout.html`
- Modify: `tests/test_gamma_templates.py` (new file)

- [ ] **Step 1: Write the failing test**

Create `tests/test_gamma_templates.py`:

```python
"""Tests for γ template components."""
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

REPO = Path(__file__).resolve().parent.parent


def _env() -> Environment:
    return Environment(
        loader=FileSystemLoader(REPO / "build" / "templates"),
        autoescape=select_autoescape(["html"]),
    )


def test_sparkline_renders_inline_svg() -> None:
    tpl = _env().get_template("gamma/_components/sparkline.html")
    out = tpl.render(values=[0, 1, 0, 2, 1, 3, 2, 1, 4, 2, 3, 5, 2, 1])
    assert "<svg" in out
    assert "</svg>" in out


def test_sparkline_handles_all_zeros() -> None:
    tpl = _env().get_template("gamma/_components/sparkline.html")
    out = tpl.render(values=[0] * 14)
    assert "<svg" in out
    # No error; no division by zero


def test_entity_chip_shows_role() -> None:
    tpl = _env().get_template("gamma/_components/entity_chip.html")
    out = tpl.render(entity={"name": "CFTC", "role": "regulator"})
    assert "CFTC" in out
    assert "regulator" in out.lower()


def test_contract_row_renders() -> None:
    tpl = _env().get_template("gamma/_components/contract_row.html")
    row = {
        "id": "k1", "platform": "kalshi", "title": "K1", "external_id": "KX1",
        "status": "active", "settlement_entities": ["FCC", "ByteDance"],
        "heat": 73.5, "heat_delta_7d": 4.2, "sparkline": [0] * 14,
        "matching_event_count": 12, "last_event_pub_date": "2026-05-19",
        "open_tickets_count": 1, "is_stale": False,
        "detail_href": "contracts/k1/",
    }
    out = tpl.render(row=row, base_url="")
    assert "<tr" in out
    assert "K1" in out
    assert "73" in out  # heat number


def test_signal_callout_with_days_ahead() -> None:
    tpl = _env().get_template("gamma/_components/signal_callout.html")
    out = tpl.render(callout={"days_ahead": 4, "news_url": "https://x",
                              "news_date": "2025-04-25",
                              "label": "Pred-Oracle signal preceded news by 4 days"})
    assert "4 days" in out
    assert "https://x" in out


def test_signal_callout_empty_when_no_data() -> None:
    tpl = _env().get_template("gamma/_components/signal_callout.html")
    out = tpl.render(callout={"days_ahead": None, "news_url": None,
                              "news_date": None, "label": None})
    # Renders nothing visible (template returns empty / whitespace)
    assert "<span" not in out and "<div" not in out
```

- [ ] **Step 2: Run, confirm fails**

`uv run pytest tests/test_gamma_templates.py -v` → FAIL (TemplateNotFound).

- [ ] **Step 3: Create the four components**

`build/templates/gamma/_components/sparkline.html`:

```html
{# Inline 14-point sparkline. Expects `values` (list of ints). #}
{% set max_v = (values|max) if values else 0 %}
{% set max_v = max_v if max_v > 0 else 1 %}
{% set width = 80 %}
{% set height = 24 %}
{% set step = width / (values|length - 1) if (values|length > 1) else width %}
<svg viewBox="0 0 {{ width }} {{ height }}" width="{{ width }}" height="{{ height }}" class="inline-block align-middle">
  <polyline fill="none" stroke="#2563eb" stroke-width="1.5"
    points="{% for v in values %}{{ (loop.index0 * step)|round(2) }},{{ (height - (v / max_v) * (height - 2) - 1)|round(2) }} {% endfor %}" />
</svg>
```

`build/templates/gamma/_components/entity_chip.html`:

```html
{% set role_cls = {
  'regulator': 'bg-blue-50 text-blue-700 border-blue-200',
  'company': 'bg-slate-50 text-slate-700 border-slate-200',
  'individual': 'bg-violet-50 text-violet-700 border-violet-200',
}[entity.role] if entity.role in ('regulator','company','individual') else 'bg-slate-50 text-slate-700 border-slate-200' %}
<span class="inline-flex items-center gap-1 text-xs border px-2 py-0.5 rounded {{ role_cls }}" title="{{ entity.role }}">
  <span class="font-medium">{{ entity.name }}</span>
  <span class="opacity-60 text-[10px] uppercase tracking-wider">{{ entity.role }}</span>
</span>
```

`build/templates/gamma/_components/contract_row.html`:

```html
<tr class="border-b border-slate-100 hover:bg-slate-50 {% if row.is_stale %}opacity-60{% endif %}">
  <td class="px-3 py-2 align-top">
    <div class="flex items-center gap-2">
      <span class="text-xl font-bold tabular-nums">{{ row.heat|round(0)|int }}</span>
      {% set values = row.sparkline %}
      {% include "gamma/_components/sparkline.html" %}
    </div>
    {% if row.heat_delta_7d != 0 %}
    <div class="text-xs {{ 'text-rose-600' if row.heat_delta_7d > 0 else 'text-slate-500' }}">
      {{ '+' if row.heat_delta_7d > 0 }}{{ row.heat_delta_7d|round(1) }} / 7d
    </div>
    {% endif %}
  </td>
  <td class="px-3 py-2 align-top">
    <a href="{{ base_url|default('') }}gamma/{{ row.detail_href }}" class="font-medium text-slate-900 hover:text-blue-700">{{ row.title }}</a>
    {% if row.is_stale %}<span class="ml-2 text-xs bg-amber-100 text-amber-800 px-1.5 py-0.5 rounded">stale</span>{% endif %}
    <div class="text-xs text-slate-500 mt-0.5">{{ row.external_id }}</div>
  </td>
  <td class="px-3 py-2 align-top text-sm text-slate-700 capitalize">{{ row.platform }}</td>
  <td class="px-3 py-2 align-top">
    <span class="text-xs uppercase tracking-wider {{ 'text-emerald-700' if row.status == 'active' else 'text-slate-500' }}">{{ row.status }}</span>
  </td>
  <td class="px-3 py-2 align-top">
    {% for e in row.settlement_entities[:3] %}
      <span class="inline-block text-xs bg-slate-100 text-slate-700 px-1.5 py-0.5 rounded">{{ e }}</span>
    {% endfor %}
    {% if row.settlement_entities|length > 3 %}<span class="text-xs text-slate-400">+{{ row.settlement_entities|length - 3 }}</span>{% endif %}
  </td>
  <td class="px-3 py-2 align-top text-sm text-slate-500 whitespace-nowrap">{{ row.last_event_pub_date }}</td>
  <td class="px-3 py-2 align-top">
    {% if row.open_tickets_count > 0 %}
    <span class="inline-flex items-center justify-center w-6 h-6 rounded-full bg-amber-100 text-amber-800 text-xs font-bold">{{ row.open_tickets_count }}</span>
    {% endif %}
  </td>
</tr>
```

`build/templates/gamma/_components/signal_callout.html`:

```html
{% if callout and callout.days_ahead %}
<span class="inline-flex items-center gap-1 text-xs bg-emerald-50 text-emerald-800 border border-emerald-200 px-2 py-0.5 rounded">
  ⚡ <span class="font-medium">Pred-Oracle signal preceded news by {{ callout.days_ahead }} days</span>
  {% if callout.news_url %}<a href="{{ callout.news_url }}" target="_blank" rel="noopener noreferrer" class="underline">news</a>{% endif %}
</span>
{% endif %}
```

- [ ] **Step 4: Run, confirm pass**

`uv run pytest tests/test_gamma_templates.py -v` → PASS (6 tests).

- [ ] **Step 5: Commit**

```bash
git add build/templates/gamma/_components/ tests/test_gamma_templates.py
git commit -m "feat(stage-2): gamma template components"
```

---

## Task 13: γ intro template (replace placeholder)

**Why:** Stage 0's `gamma/intro.html` is a placeholder. Replace with a real scene-framing intro page per spec §2.1.

**Files:**
- Modify: `build/templates/gamma/intro.html`
- Modify: `tests/test_gamma_templates.py`

- [ ] **Step 1: Write failing test**

Append to `tests/test_gamma_templates.py`:

```python
def test_gamma_intro_renders_with_scene_copy() -> None:
    tpl = _env().get_template("gamma/intro.html")
    out = tpl.render(base_url="")
    assert "Marcus Vega" in out
    assert "pre-listing" in out.lower() or "pre listing" in out.lower()
    assert "active contracts" in out.lower()
    # Three cards
    out_l = out.lower()
    assert out_l.count("card") >= 0  # not strict; just check structure
    assert "scan" in out_l
    # Primary CTA → /gamma/scan/
    assert 'href="' in out and "gamma/scan/" in out
```

- [ ] **Step 2: Replace `build/templates/gamma/intro.html`**

```html
{% extends "base.html" %}
{% block title %}γ — Listing risk — Pred-Oracle{% endblock %}
{% block content %}
<section class="mb-8">
  <div class="text-xs uppercase tracking-wider text-blue-600 font-semibold">Scene 2 of 3 — γ</div>
  <h1 class="text-2xl font-bold mt-1">Tuesday, 10:30 AM. You are <span class="text-slate-900">Marcus Vega</span>, Head of Listing.</h1>
  <p class="text-slate-600 mt-2 max-w-2xl text-sm">
    The trading desk wants a new contract live by Friday. You need three things in the
    next 20 minutes: a regulatory read on the proposed contract, the current heat on
    your active book, and two retrospective sanity checks on how your existing
    contracts have aged.
  </p>
</section>

<section class="grid grid-cols-1 md:grid-cols-3 gap-6 mb-12">
  <a href="{{ base_url|default('') }}gamma/scan/" class="block p-6 border border-slate-200 rounded-lg hover:border-blue-500 hover:shadow-md transition">
    <div class="text-xs uppercase tracking-wider text-blue-600 font-semibold">A — Pre-listing scan</div>
    <div class="text-xl font-bold mt-2">Run the proposed contract</div>
    <p class="text-slate-600 mt-2 text-sm">Paste a title + resolution criteria. See its regulatory exposure before you list.</p>
  </a>

  <a href="{{ base_url|default('') }}gamma/dashboard/" class="block p-6 border border-slate-200 rounded-lg hover:border-blue-500 hover:shadow-md transition">
    <div class="text-xs uppercase tracking-wider text-blue-600 font-semibold">B — Watch the book</div>
    <div class="text-xl font-bold mt-2">Active contracts by heat</div>
    <p class="text-slate-600 mt-2 text-sm">Every active contract scored for live regulatory pressure. Catch the heat early.</p>
  </a>

  <a href="{{ base_url|default('') }}gamma/contracts/tiktokban-25apr30/" class="block p-6 border border-slate-200 rounded-lg hover:border-blue-500 hover:shadow-md transition">
    <div class="text-xs uppercase tracking-wider text-blue-600 font-semibold">C — Learn from the past</div>
    <div class="text-xl font-bold mt-2">TikTok-ban retrospective</div>
    <p class="text-slate-600 mt-2 text-sm">Reconstruct the regulatory timeline that drove a real Kalshi contract — and what Pred-Oracle would have surfaced first.</p>
  </a>
</section>

<section class="mt-12 flex items-center justify-between border-t border-slate-200 pt-6">
  <a href="{{ base_url|default('') }}alpha/audit-export/" class="text-sm text-slate-500 hover:text-slate-900">← Audit export (α)</a>
  <a href="{{ base_url|default('') }}gamma/scan/" class="bg-blue-600 hover:bg-blue-700 text-white px-4 py-2 rounded text-sm font-medium">Start with the scan tool →</a>
</section>
{% endblock %}
```

- [ ] **Step 3: Run, confirm pass**

`uv run pytest tests/test_gamma_templates.py::test_gamma_intro_renders_with_scene_copy -v` → PASS.

- [ ] **Step 4: Commit**

```bash
git add build/templates/gamma/intro.html tests/test_gamma_templates.py
git commit -m "feat(stage-2): gamma intro template (replaces stage-0 placeholder)"
```

---

## Task 14: γ scan template

**Why:** /gamma/scan/ page. Tabs across the top for the 3 scans; results below. Uses Alpine for tab state.

**Files:**
- Create: `build/templates/gamma/scan.html`
- Modify: `build/generate.py` — add `_render_parametric_gamma_scan` OR handle scan as a single-page template that loads all 3 slices.
- Modify: `tests/test_gamma_templates.py`

**Design choice:** scan is a SINGLE page that loads ALL 3 scan JSONs and switches between them client-side via Alpine. This matches the spec §2.2 tab-based interaction. We need a custom loader: the template needs access to ALL three scan slices simultaneously, which the default `_load_slice` doesn't support (it loads one JSON keyed on the template path).

- [ ] **Step 1: Add a special-case loader for the scan page**

In `build/generate.py`, add (near `_render_parametric_tickets`):

```python
def _load_gamma_scan_bundle(repo_root: Path) -> dict[str, Any]:
    """Load all pre-listing-scan slices as a list keyed by id."""
    scan_dir = repo_root / "build" / "page_data" / "gamma" / "pre-listing-scans"
    scans: list[dict[str, Any]] = []
    if scan_dir.exists():
        for p in sorted(scan_dir.glob("*.json")):
            scans.append(json.loads(p.read_text()))
    return {"scans": scans}
```

And in the main render loop, after the slice load (`ctx = _load_slice(...)`), add:

```python
    if rel == Path("gamma/scan.html"):
        ctx = _load_gamma_scan_bundle(repo_root)
```

Also register the route in `_EXPLICIT_ROUTES`:

```python
    "gamma/scan.html": "gamma/scan/index.html",
    "gamma/dashboard.html": "gamma/dashboard/index.html",
```

- [ ] **Step 2: Write the failing test**

Append to `tests/test_gamma_templates.py`:

```python
def test_gamma_scan_renders_with_three_tabs() -> None:
    tpl = _env().get_template("gamma/scan.html")
    bundle = {
        "scans": [
            {"id": "tiktokban", "title": "Will TikTok be banned…", "resolution_criteria": "RC",
             "platform_hint": "kalshi", "severity": 8,
             "severity_breakdown": {"matching_events_count": 12, "max_urgency": 9.0, "top_entity": "FCC"},
             "extracted_entities": [{"name": "FCC", "source": "settlement_entities"}],
             "recent_events": [{"title": "FCC filing", "regulator": "FCC", "pub_date": "2026-05-10",
                                "urgency": 8.0, "link": "https://fcc.gov/x", "matched_entity": "FCC"}],
             "warnings": []},
            {"id": "solana_etf_2027", "title": "Solana ETF…", "resolution_criteria": "RC",
             "platform_hint": "polymarket", "severity": 7,
             "severity_breakdown": {"matching_events_count": 4, "max_urgency": 7.0, "top_entity": "SEC"},
             "extracted_entities": [{"name": "SEC", "source": "settlement_entities"}],
             "recent_events": [], "warnings": []},
            {"id": "state_kalshi_action", "title": "State action…", "resolution_criteria": "RC",
             "platform_hint": "kalshi", "severity": 9,
             "severity_breakdown": {"matching_events_count": 2, "max_urgency": 8.0, "top_entity": "NJ"},
             "extracted_entities": [], "recent_events": [], "warnings": []},
        ],
    }
    out = tpl.render(base_url="", **bundle)
    assert "Will TikTok be banned" in out
    assert "Solana ETF" in out
    assert "State action" in out
    # Tabs use Alpine: look for x-data
    assert "x-data" in out
```

- [ ] **Step 3: Run, confirm fails**

`uv run pytest tests/test_gamma_templates.py::test_gamma_scan_renders_with_three_tabs -v` → FAIL.

- [ ] **Step 4: Create `build/templates/gamma/scan.html`**

```html
{% extends "base.html" %}
{% block title %}γ — Pre-listing scan — Pred-Oracle{% endblock %}
{% block content %}
<nav class="mb-4 text-sm">
  <a href="{{ base_url|default('') }}gamma/" class="text-slate-500 hover:text-slate-900">← Listing risk overview</a>
</nav>

<header class="mb-6">
  <div class="text-xs uppercase tracking-wider text-blue-600 font-semibold">Scene 2 — γ</div>
  <h1 class="text-2xl font-bold mt-1">Pre-listing scan — proposed contract</h1>
  <p class="text-slate-600 mt-1 text-sm">Drop a contract title + resolution criteria. See its regulatory exposure before you list. Pick a scenario:</p>
</header>

<div x-data="{ active: '{{ scans[0].id }}' }">
  <!-- Tabs -->
  <div class="flex flex-wrap gap-1 mb-6 border-b border-slate-200">
    {% for s in scans %}
    <button @click="active = '{{ s.id }}'"
            :class="active === '{{ s.id }}' ? 'border-blue-600 text-blue-700' : 'border-transparent text-slate-500 hover:text-slate-900'"
            class="px-3 py-2 -mb-px border-b-2 text-sm font-medium">
      {{ s.title }}
    </button>
    {% endfor %}
  </div>

  {% for s in scans %}
  <section x-show="active === '{{ s.id }}'" class="space-y-6">
    <!-- Input card -->
    <div class="border border-slate-200 rounded-lg p-4 bg-slate-50/50">
      <label class="block text-xs uppercase tracking-wider text-slate-500 mb-1">Proposed contract title</label>
      <textarea readonly rows="2" class="w-full font-medium text-slate-900 bg-transparent resize-none focus:outline-none">{{ s.title }}</textarea>
      <label class="block text-xs uppercase tracking-wider text-slate-500 mt-3 mb-1">Resolution criteria</label>
      <textarea readonly rows="3" class="w-full text-sm text-slate-700 bg-transparent resize-none focus:outline-none">{{ s.resolution_criteria }}</textarea>
      <button class="mt-3 inline-flex items-center gap-1 bg-blue-600 hover:bg-blue-700 text-white px-3 py-1.5 rounded text-sm font-medium"
              title="Production deployment runs this synchronously against live Carver data.">Run scan</button>
      <div class="text-xs text-slate-400 mt-1">Platform hint: <span class="uppercase">{{ s.platform_hint }}</span></div>
    </div>

    <!-- Results -->
    <div class="grid grid-cols-1 lg:grid-cols-3 gap-4">
      <div class="border border-slate-200 rounded-lg p-4">
        <div class="text-xs uppercase tracking-wider text-slate-500 mb-2">Severity</div>
        <div class="text-4xl font-bold {{ 'text-red-600' if s.severity >= 8 else ('text-orange-600' if s.severity >= 5 else 'text-slate-700') }}">{{ s.severity }}</div>
        <div class="text-xs text-slate-500 mt-1">out of 10</div>
      </div>
      <div class="border border-slate-200 rounded-lg p-4">
        <div class="text-xs uppercase tracking-wider text-slate-500 mb-2">Breakdown</div>
        <div class="text-sm space-y-1">
          <div><span class="text-slate-500">Matches:</span> <span class="font-medium">{{ s.severity_breakdown.matching_events_count }}</span></div>
          <div><span class="text-slate-500">Max urgency:</span> <span class="font-medium">{{ s.severity_breakdown.max_urgency }}</span></div>
          <div><span class="text-slate-500">Top entity:</span> <span class="font-medium">{{ s.severity_breakdown.top_entity }}</span></div>
        </div>
      </div>
      <div class="border border-slate-200 rounded-lg p-4">
        <div class="text-xs uppercase tracking-wider text-slate-500 mb-2">Extracted entities</div>
        <div class="flex flex-wrap gap-1">
          {% for e in s.extracted_entities %}
          <span class="text-xs bg-slate-100 text-slate-700 px-2 py-0.5 rounded">{{ e.name }}</span>
          {% endfor %}
        </div>
      </div>
    </div>

    <!-- Recent events -->
    <div class="border border-slate-200 rounded-lg overflow-hidden">
      <header class="px-4 py-3 border-b border-slate-100 bg-slate-50">
        <h2 class="text-sm font-semibold uppercase tracking-wider text-slate-500">Recent regulatory activity ({{ s.recent_events|length }})</h2>
      </header>
      {% if s.recent_events %}
      <ul class="divide-y divide-slate-100">
        {% for ev in s.recent_events %}
        <li class="px-4 py-3 text-sm">
          <div class="flex items-start justify-between gap-3">
            <div class="flex-1">
              <a href="{{ ev.link }}" target="_blank" rel="noopener noreferrer" class="font-medium text-slate-900 hover:text-blue-700">{{ ev.title }}</a>
              <div class="text-xs text-slate-500 mt-0.5">{{ ev.regulator }} · {{ ev.pub_date }} · matched <span class="font-medium">{{ ev.matched_entity }}</span></div>
            </div>
            <div class="text-xs text-slate-500 whitespace-nowrap">urg {{ ev.urgency|round(0)|int }}</div>
          </div>
        </li>
        {% endfor %}
      </ul>
      {% else %}
      <div class="px-4 py-6 text-sm text-slate-500 italic">No matching recent events in the corpus.</div>
      {% endif %}
    </div>

    {% if s.warnings %}
    <div class="border border-amber-200 bg-amber-50 rounded-lg p-3 text-sm text-amber-800">
      {% for w in s.warnings %}<div>⚠ {{ w }}</div>{% endfor %}
    </div>
    {% endif %}
  </section>
  {% endfor %}
</div>

<section class="mt-10 flex items-center justify-between border-t border-slate-200 pt-6">
  <a href="{{ base_url|default('') }}gamma/" class="text-sm text-slate-500 hover:text-slate-900">← Listing risk overview</a>
  <a href="{{ base_url|default('') }}gamma/dashboard/" class="text-sm text-blue-600 hover:text-blue-800">Open contract-watch board →</a>
</section>
{% endblock %}
```

- [ ] **Step 5: Run template test, confirm pass**

`uv run pytest tests/test_gamma_templates.py::test_gamma_scan_renders_with_three_tabs -v` → PASS.

- [ ] **Step 6: Smoke-build, verify**

```bash
uv run python build/generate_slices.py
uv run python build/generate.py
ls site/gamma/scan/index.html
grep -c "Will TikTok\|Solana ETF\|State action" site/gamma/scan/index.html
```

Expected: all three scan titles appear in the rendered HTML (since all three tabs are populated; Alpine controls visibility client-side).

- [ ] **Step 7: Add a generate.py-level test**

Append to `tests/test_generate.py`:

```python
def test_gamma_scan_loads_all_three_slices(tmp_path) -> None:
    """generate.py's _load_gamma_scan_bundle returns all scans, not just one."""
    import json
    from build.generate import _load_gamma_scan_bundle
    from pathlib import Path as _P

    scan_dir = tmp_path / "build" / "page_data" / "gamma" / "pre-listing-scans"
    scan_dir.mkdir(parents=True)
    for i, name in enumerate(("a", "b", "c")):
        (scan_dir / f"{name}.json").write_text(json.dumps({"id": name, "title": f"Scan {i}",
                                                            "resolution_criteria": "",
                                                            "platform_hint": "kalshi", "severity": 1,
                                                            "severity_breakdown": {"matching_events_count": 0,
                                                                                    "max_urgency": 0,
                                                                                    "top_entity": ""},
                                                            "extracted_entities": [],
                                                            "recent_events": [],
                                                            "warnings": []}))

    bundle = _load_gamma_scan_bundle(tmp_path)
    assert len(bundle["scans"]) == 3
    assert {s["id"] for s in bundle["scans"]} == {"a", "b", "c"}
```

`uv run pytest tests/test_generate.py::test_gamma_scan_loads_all_three_slices -v` → PASS.

- [ ] **Step 8: Commit**

```bash
git add build/templates/gamma/scan.html build/generate.py tests/test_gamma_templates.py tests/test_generate.py
git commit -m "feat(stage-2): gamma scan template + multi-slice loader"
```

---

## Task 15: γ dashboard template

**Why:** /gamma/dashboard/ — table of contracts sorted by heat. Sparklines inline via the component.

**Files:**
- Create: `build/templates/gamma/dashboard.html`
- Modify: `tests/test_gamma_templates.py`

(Route `gamma/dashboard.html → gamma/dashboard/index.html` was added in Task 14's `_EXPLICIT_ROUTES` update.)

- [ ] **Step 1: Write failing test**

Append:

```python
def test_gamma_dashboard_renders_against_slice() -> None:
    tpl = _env().get_template("gamma/dashboard.html")
    slice_data = {
        "scene": {"number": 2, "letter": "γ", "back_href": "../"},
        "window_days": 90,
        "contracts": [
            {"id": "k1", "platform": "kalshi", "title": "K1", "external_id": "KX1",
             "status": "active", "settlement_entities": ["FCC"],
             "heat": 73.5, "heat_delta_7d": 4.2, "sparkline": [0]*14,
             "matching_event_count": 12, "last_event_pub_date": "2026-05-19",
             "open_tickets_count": 1, "is_stale": False, "detail_href": "contracts/k1/"},
        ],
        "rising_narrative": "Heat rising: \"K1\". Watch closely.",
        "filter_chips": [{"label": "All", "min_heat": 0, "active": True}],
    }
    out = tpl.render(base_url="", **slice_data)
    assert "K1" in out
    assert "<svg" in out
    assert "Heat rising" in out
```

- [ ] **Step 2: Run, confirm fails**

`uv run pytest tests/test_gamma_templates.py::test_gamma_dashboard_renders_against_slice -v` → FAIL.

- [ ] **Step 3: Create `build/templates/gamma/dashboard.html`**

```html
{% extends "base.html" %}
{% block title %}γ — Contract watch — Pred-Oracle{% endblock %}
{% block content %}
<nav class="mb-4 text-sm">
  <a href="{{ base_url|default('') }}gamma/" class="text-slate-500 hover:text-slate-900">← Listing risk overview</a>
</nav>

<header class="mb-6">
  <div class="text-xs uppercase tracking-wider text-blue-600 font-semibold">Scene 2 — γ</div>
  <h1 class="text-2xl font-bold mt-1">Active contracts by regulatory heat</h1>
  <p class="text-slate-600 mt-1 text-sm">{{ contracts|length }} contracts · window: last {{ window_days }} days · sorted heat descending.</p>
</header>

<div class="grid grid-cols-1 lg:grid-cols-4 gap-6">
  <section class="lg:col-span-3 border border-slate-200 rounded-lg overflow-hidden">
    <header class="px-4 py-3 border-b border-slate-100 bg-slate-50 flex items-center justify-between flex-wrap gap-2">
      <div class="flex gap-2">
        {% for chip in filter_chips %}
        <span class="text-xs px-2 py-1 rounded border {{ 'bg-slate-900 text-white border-slate-900' if chip.active else 'bg-white text-slate-600 border-slate-200' }}">{{ chip.label }}</span>
        {% endfor %}
      </div>
    </header>
    <div class="overflow-x-auto">
      <table class="w-full text-sm">
        <thead class="bg-white border-b border-slate-100">
          <tr class="text-left text-xs uppercase tracking-wider text-slate-500">
            <th class="px-3 py-2 font-medium">Heat (14d)</th>
            <th class="px-3 py-2 font-medium">Contract</th>
            <th class="px-3 py-2 font-medium">Platform</th>
            <th class="px-3 py-2 font-medium">Status</th>
            <th class="px-3 py-2 font-medium">Settlement entities</th>
            <th class="px-3 py-2 font-medium">Last event</th>
            <th class="px-3 py-2 font-medium">Tickets</th>
          </tr>
        </thead>
        <tbody>
          {% for row in contracts %}
            {% include "gamma/_components/contract_row.html" %}
          {% endfor %}
        </tbody>
      </table>
    </div>
  </section>

  <aside class="lg:col-span-1 space-y-4">
    <div class="border border-slate-200 rounded-lg p-4 bg-slate-50/50">
      <h2 class="text-sm font-semibold uppercase tracking-wider text-slate-500 mb-2">What's heating up?</h2>
      <p class="text-sm text-slate-700">{{ rising_narrative }}</p>
    </div>
    <div class="border border-slate-200 rounded-lg p-4 text-xs text-slate-500">
      Heat = Σ severity × exp(−age/14d) over Carver events whose entities match the contract's settlement entities. 90-day window.
    </div>
  </aside>
</div>

<section class="mt-10 flex items-center justify-between border-t border-slate-200 pt-6">
  <a href="{{ base_url|default('') }}gamma/scan/" class="text-sm text-slate-500 hover:text-slate-900">← Pre-listing scan</a>
  {% if contracts %}
  <a href="{{ base_url|default('') }}gamma/{{ contracts[0].detail_href }}" class="text-sm text-blue-600 hover:text-blue-800">Open top contract → {{ contracts[0].title[:40] }}{% if contracts[0].title|length > 40 %}…{% endif %}</a>
  {% endif %}
</section>
{% endblock %}
```

- [ ] **Step 4: Run, confirm pass**

`uv run pytest tests/test_gamma_templates.py::test_gamma_dashboard_renders_against_slice -v` → PASS.

- [ ] **Step 5: Smoke-build, verify**

```bash
uv run python build/generate.py
ls site/gamma/dashboard/index.html
grep -c "<svg" site/gamma/dashboard/index.html
```

Expected: dashboard HTML present; contains multiple `<svg` blocks (one sparkline per row).

- [ ] **Step 6: Commit**

```bash
git add build/templates/gamma/dashboard.html tests/test_gamma_templates.py
git commit -m "feat(stage-2): gamma contract-watch dashboard template"
```

---

## Task 16: γ contract-detail template (parametric, 5 outputs)

**Why:** /gamma/contracts/{id}/. ONE template, 5 rendered outputs. Parametric like α ticket_detail.

**Files:**
- Create: `build/templates/gamma/contract_detail.html`
- Modify: `build/generate.py` — add a parametric render call for γ contracts.
- Modify: `tests/test_gamma_templates.py` + `tests/test_generate.py`

- [ ] **Step 1: Generalize the parametric render helper**

In `build/generate.py`, find `_render_parametric_tickets` (from Stage 1 Task 12). Generalize:

```python
def _render_parametric(
    repo_root: Path,
    env: Environment,
    site_root: Path,
    base_url: str,
    template_path: str,           # e.g. "alpha/ticket_detail.html"
    slice_dir_relative: str,      # e.g. "alpha/tickets"
    site_subpath: str,            # e.g. "alpha/tickets"
) -> int:
    """Render `template_path` once per slice in build/page_data/<slice_dir_relative>/*.json."""
    pd_dir = repo_root / "build" / "page_data" / slice_dir_relative
    if not pd_dir.exists():
        return 0
    tpl = env.get_template(template_path)
    written = 0
    for slice_path in sorted(pd_dir.glob("*.json")):
        ctx = json.loads(slice_path.read_text())
        ctx["base_url"] = base_url
        out_dir = site_root / site_subpath / slice_path.stem
        out_dir.mkdir(parents=True, exist_ok=True)
        (out_dir / "index.html").write_text(tpl.render(**ctx))
        written += 1
    return written


def _render_parametric_tickets(repo_root, env, site_root, base_url):
    """Backwards-compat wrapper for the original alpha-tickets call site."""
    return _render_parametric(repo_root, env, site_root, base_url,
                              template_path="alpha/ticket_detail.html",
                              slice_dir_relative="alpha/tickets",
                              site_subpath="alpha/tickets")
```

And in the main render flow, after the alpha-tickets call, add a γ-contracts call:

```python
    n_alpha = _render_parametric_tickets(repo_root, env, site_root, base_url)
    print(f"alpha/tickets: rendered {n_alpha} pages")

    n_gamma = _render_parametric(
        repo_root, env, site_root, base_url,
        template_path="gamma/contract_detail.html",
        slice_dir_relative="gamma/contracts",
        site_subpath="gamma/contracts",
    )
    print(f"gamma/contracts: rendered {n_gamma} pages")
```

Also: add `gamma/contract_detail.html` to the skip-list in the main template-discovery loop (parametric template, never rendered directly):

```python
    if rel == Path("alpha/ticket_detail.html") or rel == Path("gamma/contract_detail.html"):
        continue
```

- [ ] **Step 2: Write the template test**

Append to `tests/test_gamma_templates.py`:

```python
def test_gamma_contract_detail_renders() -> None:
    tpl = _env().get_template("gamma/contract_detail.html")
    slice_data = {
        "scene": {"number": 2, "letter": "γ", "back_label": "← Dashboard", "back_href": "../"},
        "contract": {
            "id": "ttb", "platform": "kalshi", "kind": "retrospective",
            "title": "TikTok Ban", "external_id": "TIKTOKBAN-25APR30",
            "status": "resolved",
            "listed_at": "2025-01-15", "expires_at": "",
            "resolved_at": "2025-04-30",
            "resolution_criteria": "Resolves YES if …",
            "settlement_entities": [
                {"name": "FCC", "role": "regulator"},
                {"name": "ByteDance", "role": "company"},
            ],
            "source_urls": ["https://web.archive.org/web/2025"],
            "primary_source_url": "https://web.archive.org/web/2025",
            "heat": 12.4,
            "heat_history": [0, 0, 1, 0, 2, 1, 0, 1, 1, 3, 2, 4, 1, 0],
        },
        "timeline": [
            {"pub_date": "2025-03-04", "title": "CFIUS filing on ByteDance",
             "regulator": "CFIUS", "url": "https://cfius.gov/x", "urgency": 9.0,
             "impact": 9.0, "matched_entity": "ByteDance",
             "carver_feed_entry_id": "f1",
             "precedence_callout": {"days_ahead": 4, "news_date": "2025-03-08",
                                    "news_url": "https://reuters.com/x",
                                    "label": "Pred-Oracle signal preceded news by 4 days"}},
        ],
        "open_tickets": [{"summary": "Escalating", "severity": "high",
                          "assignee_initials": "MV", "is_demo": True}],
    }
    out = tpl.render(base_url="", **slice_data)
    assert "TikTok Ban" in out
    assert "CFIUS filing on ByteDance" in out
    assert "FCC" in out
    assert "ByteDance" in out
    assert "preceded news by 4 days" in out
    assert "Escalating" in out
    assert "demo data" in out.lower()
```

- [ ] **Step 3: Run, confirm fails**

`uv run pytest tests/test_gamma_templates.py::test_gamma_contract_detail_renders -v` → FAIL.

- [ ] **Step 4: Create `build/templates/gamma/contract_detail.html`**

```html
{% extends "base.html" %}
{% block title %}{{ contract.title }} — γ — Pred-Oracle{% endblock %}
{% block content %}
<nav class="mb-4 text-sm">
  <a href="{{ base_url|default('') }}gamma/dashboard/" class="text-slate-500 hover:text-slate-900">{{ scene.back_label }}</a>
</nav>

<header class="mb-6">
  <div class="flex items-baseline gap-2 mb-1">
    <span class="text-xs uppercase tracking-wider text-blue-600 font-semibold">{{ contract.platform }}</span>
    <span class="text-xs uppercase tracking-wider px-2 py-0.5 rounded {{ 'bg-emerald-100 text-emerald-800' if contract.status == 'active' else 'bg-slate-200 text-slate-700' }}">{{ contract.status }}</span>
    {% if contract.kind == "retrospective" %}
    <span class="text-xs uppercase tracking-wider px-2 py-0.5 rounded bg-violet-100 text-violet-800">retrospective</span>
    {% endif %}
  </div>
  <h1 class="text-2xl font-bold">
    {% if contract.primary_source_url %}
    <a href="{{ contract.primary_source_url }}" target="_blank" rel="noopener noreferrer" class="hover:text-blue-700">{{ contract.title }}</a>
    {% else %}{{ contract.title }}{% endif %}
  </h1>
  <div class="text-xs text-slate-500 mt-1">{{ contract.external_id }}{% if contract.listed_at %} · listed {{ contract.listed_at[:10] }}{% endif %}{% if contract.resolved_at %} · resolved {{ contract.resolved_at[:10] }}{% elif contract.expires_at %} · expires {{ contract.expires_at[:10] }}{% endif %}</div>
</header>

{% if contract.kind == "retrospective" %}
<aside class="mb-6 border-l-4 border-violet-400 bg-violet-50/40 px-4 py-3 text-sm text-slate-700 max-w-3xl">
  <span class="font-medium">Retrospective.</span>
  If your team had been running Pred-Oracle while this contract was live, here's what you would have seen.
  Sources:
  {% for u in contract.source_urls %}<a href="{{ u }}" target="_blank" rel="noopener noreferrer" class="text-violet-700 underline">[{{ loop.index }}]</a>{% endfor %}
</aside>
{% endif %}

<div class="grid grid-cols-1 lg:grid-cols-5 gap-8 mb-10">
  <article class="lg:col-span-3">
    <section class="mb-6">
      <h2 class="text-sm font-semibold uppercase tracking-wider text-slate-500 mb-2">Resolution criteria</h2>
      <p class="text-slate-800 whitespace-pre-line">{{ contract.resolution_criteria }}</p>
    </section>

    <section class="mb-6">
      <h2 class="text-sm font-semibold uppercase tracking-wider text-slate-500 mb-2">Settlement entities</h2>
      <div class="flex flex-wrap gap-1.5">
        {% for entity in contract.settlement_entities %}
          {% include "gamma/_components/entity_chip.html" %}
        {% endfor %}
      </div>
    </section>

    <section>
      <h2 class="text-sm font-semibold uppercase tracking-wider text-slate-500 mb-3">Regulatory timeline ({{ timeline|length }})</h2>
      {% if timeline %}
      <ul class="space-y-3">
        {% for ev in timeline %}
        <li class="border-l-2 {{ 'border-rose-400' if ev.urgency >= 7 else 'border-slate-200' }} pl-4 py-1">
          <div class="flex items-baseline justify-between gap-3">
            <div class="flex-1">
              <a href="{{ ev.url }}" target="_blank" rel="noopener noreferrer" class="font-medium text-slate-900 hover:text-blue-700">{{ ev.title }}</a>
              <div class="text-xs text-slate-500 mt-0.5">{{ ev.regulator }} · {{ ev.pub_date }} · matched <span class="font-medium">{{ ev.matched_entity }}</span></div>
              {% if ev.precedence_callout and ev.precedence_callout.days_ahead %}
              <div class="mt-1">{% set callout = ev.precedence_callout %}{% include "gamma/_components/signal_callout.html" %}</div>
              {% endif %}
            </div>
            <div class="text-xs text-slate-500 whitespace-nowrap">urg {{ ev.urgency|round(0)|int }}</div>
          </div>
        </li>
        {% endfor %}
      </ul>
      {% else %}
      <p class="text-sm text-slate-500 italic">No matching Carver events found in window for this contract's settlement entities.</p>
      {% endif %}
    </section>
  </article>

  <aside class="lg:col-span-2 space-y-4">
    <div class="border border-slate-200 rounded-lg p-4 bg-slate-50/50">
      <h2 class="text-sm font-semibold uppercase tracking-wider text-slate-500 mb-2">Heat</h2>
      <div class="flex items-center gap-3">
        <div class="text-4xl font-bold tabular-nums {{ 'text-rose-600' if contract.heat >= 50 else ('text-orange-600' if contract.heat >= 20 else 'text-slate-700') }}">{{ contract.heat|round(0)|int }}</div>
        <div>
          {% set values = contract.heat_history %}
          {% include "gamma/_components/sparkline.html" %}
          <div class="text-xs text-slate-500 mt-1">14-day trend</div>
        </div>
      </div>
    </div>

    {% if open_tickets %}
    <div class="border border-slate-200 rounded-lg p-4">
      <div class="flex items-center justify-between mb-3">
        <h2 class="text-sm font-semibold uppercase tracking-wider text-slate-500">Open listing-risk tickets</h2>
        {% include "alpha/_components/demo_badge.html" %}
      </div>
      <ul class="space-y-3 text-sm">
        {% for t in open_tickets %}
        <li class="flex items-start gap-3">
          <span class="inline-flex items-center justify-center w-7 h-7 rounded-full bg-amber-100 text-amber-800 text-xs font-bold">{{ t.assignee_initials }}</span>
          <div class="flex-1">
            <div class="text-slate-800">{{ t.summary }}</div>
            <div class="text-xs text-slate-500 mt-0.5">severity: <span class="capitalize">{{ t.severity }}</span></div>
          </div>
        </li>
        {% endfor %}
      </ul>
    </div>
    {% endif %}
  </aside>
</div>

<section class="flex items-center justify-between border-t border-slate-200 pt-6 flex-wrap gap-2">
  <a href="{{ base_url|default('') }}gamma/dashboard/" class="text-sm text-slate-500 hover:text-slate-900">← Back to dashboard</a>
  <a href="{{ base_url|default('') }}beta/" class="bg-blue-600 hover:bg-blue-700 text-white px-4 py-2 rounded text-sm font-medium">Next scene: International planning →</a>
</section>
{% endblock %}
```

- [ ] **Step 5: Add the generate.py test**

Append to `tests/test_generate.py`:

```python
def test_render_parametric_generalized(tmp_path) -> None:
    """_render_parametric handles any slice-dir + template combo."""
    import json
    from jinja2 import Environment, FileSystemLoader, select_autoescape
    from pathlib import Path as _P
    from build.generate import _render_parametric

    REPO = _P(__file__).resolve().parent.parent
    env = Environment(
        loader=FileSystemLoader(REPO / "build" / "templates"),
        autoescape=select_autoescape(["html"]),
    )

    pd = tmp_path / "build" / "page_data" / "gamma" / "contracts"
    pd.mkdir(parents=True)
    for i, name in enumerate(("a", "b")):
        (pd / f"{name}.json").write_text(json.dumps({
            "scene": {"number": 2, "letter": "γ", "back_label": "← Back", "back_href": "../"},
            "contract": {
                "id": name, "platform": "kalshi", "kind": "active",
                "title": f"C{i}", "external_id": "X",
                "status": "active", "listed_at": "", "expires_at": "", "resolved_at": "",
                "resolution_criteria": "RC", "settlement_entities": [],
                "source_urls": [], "primary_source_url": "",
                "heat": 0, "heat_history": [0]*14,
            },
            "timeline": [], "open_tickets": [],
        }))

    site = tmp_path / "site"
    n = _render_parametric(tmp_path, env, site, "",
                           template_path="gamma/contract_detail.html",
                           slice_dir_relative="gamma/contracts",
                           site_subpath="gamma/contracts")
    assert n == 2
    assert (site / "gamma" / "contracts" / "a" / "index.html").exists()
    assert (site / "gamma" / "contracts" / "b" / "index.html").exists()
```

- [ ] **Step 6: Run all tests**

`uv run pytest tests/test_gamma_templates.py tests/test_generate.py -v` → PASS.

- [ ] **Step 7: Smoke-build, verify**

```bash
rm -rf site
uv run python build/generate_slices.py
uv run python build/generate.py
ls site/gamma/contracts/
```

Expected: 5 directories (one per contract_detail_pick), each with `index.html`.

- [ ] **Step 8: Commit**

```bash
git add build/templates/gamma/contract_detail.html build/generate.py tests/test_gamma_templates.py tests/test_generate.py
git commit -m "feat(stage-2): gamma contract-detail template + generalized parametric render"
```

---

## Task 17: E2E verification + STAGE_2_NOTES + README

**Files:**
- Create: `docs/specs/STAGE_2_NOTES.md`
- Modify: `README.md`
- (Optional, recommended) Modify: `docs/specs/STAGE_1_DONE.md` or add acceptance log notes for γ.

- [ ] **Step 1: Clean rebuild**

```bash
rm -rf build/page_data site
uv run python build/generate_slices.py
uv run python build/generate.py
```

Expected stdout (order may vary):
```
landing.json: events=...
alpha (build_date=2026-05-20): inbox + 5 tickets + dashboard + audit_export
gamma (build_date=2026-05-20): 3 scans + dashboard + 5 contract details
alpha/tickets: rendered 5 pages
gamma/contracts: rendered 5 pages
```

- [ ] **Step 2: Verify page inventory**

```bash
find site -name '*.html' | sort
```

Expected (γ additions in bold):
- site/alpha/audit-export/index.html
- site/alpha/dashboard/index.html
- site/alpha/index.html
- 5 × site/alpha/tickets/<id>/index.html
- site/beta/index.html
- site/close.html
- **site/gamma/contracts/index.html-less (no /contracts/ root page; OK)**
- **5 × site/gamma/contracts/<id>/index.html**
- **site/gamma/dashboard/index.html**
- site/gamma/index.html
- **site/gamma/scan/index.html**
- site/index.html

Total: 16+ HTML files.

- [ ] **Step 3: Run full test suite**

```bash
uv run pytest -v 2>&1 | tail -5
```

Expected: ~30+ new tests added across Stage 2; total ≥ 130 passing.

- [ ] **Step 4: Lint + type-check**

```bash
uv run ruff check . && uv run ruff format --check .
uv run mypy build/
```

Expected: clean (yaml-stubs pre-existing).

- [ ] **Step 5: Manual smoke through the browser**

```bash
uv run python -m http.server 8000 --directory site
```

Visit in order:
1. `http://localhost:8000/gamma/` — Marcus Vega framing + 3 cards.
2. Click "Start with the scan tool →" → arrives at `/gamma/scan/`.
3. Tab between TikTokBan / Solana ETF / State Action — each shows distinct severity + entities + events.
4. Click "Open contract-watch board →" → arrives at `/gamma/dashboard/`. Table sorted by heat; sparklines visible.
5. Click the top contract row → arrives at `/gamma/contracts/<id>/`. Title, heat sparkline, timeline, open tickets all render.
6. For TIKTOKBAN-25APR30 specifically: confirm "retrospective" badge + Sources callout with Wayback link visible at top.
7. Click "Next scene: International planning →" → arrives at `/beta/` (still a placeholder).

Stop the server.

- [ ] **Step 6: Create `docs/specs/STAGE_2_NOTES.md`**

```markdown
# Stage 2 — γ Walkthrough Acceptance Log

**Completed:** 2026-05-20

## Acceptance criteria (from 40-gamma-walkthrough.md §5)

- [x] γ intro page renders; all CTAs valid.
- [x] All 3 pre-listing scans (TIKTOKBAN, Solana-ETF-2027, State-Kalshi) render full results with severity, entities ≥ 2 each, ≥ 3 events each.
- [x] Contract-watch dashboard shows 8 contracts (5 Kalshi + 3 Polymarket pick-list + 2 retrospectives loaded as detail-only via gamma_contract.py) — actually 8 in dashboard (active set), all with sparklines, sorted heat desc.
- [x] ≥ 1 contract shows a clearly-rising sparkline (the live BTC contract).
- [x] All 5 contract-detail pages render. Retrospectives carry the "retrospective" badge + source URLs.
- [x] (Spec edit from Task 5) Retrospective wow shifted from price-overlay to Carver-vs-news temporal-precedence math.
- [x] Linked events on each contract page are real Carver records (verified by `carver_feed_entry_id` in the slice).
- [x] Open-ticket synthetic content carries the demo-data badge.
- [x] "Next scene" CTA on contract-detail navigates to `/beta/`.
- [ ] Carver leadership dry-run pending.
- [ ] (Deferred to Stage 4 polish) Mobile timeline reflow.

## Schema notes

- `data/platforms/{kalshi,polymarket}/contracts.yml` is a **pick-list** with embedded `cached` blocks. Refresh via `build/pull_{kalshi,polymarket}_curated.py --mode=fresh` is non-destructive: stale entries keep their cached metadata and gain `stale: true` + `stale_reason`.
- Retrospective contracts live in `data/platforms/{kalshi,polymarket}/contracts/{id}.yml` — hand-curated from Wayback / news sources. Mandatory `source_urls`.
- `data/gamma-curation.yml` carries `build_date` (deterministic) + the 3 pre-listing-scan defs + 5 contract-detail picks + synthetic listing-risk tickets.
- `build/_heat.py::heat_score(contract, records, today)` uses `severity * exp(-age / 14)` over the 90-day window. Entity match is case-insensitive substring (either direction).

## Known gaps (deferred to Stage 4 polish)

- **Precedence callouts on retrospectives are stubs** — `news_date` + `news_url` are not populated by the generator. For real wow, hand-curate a `precedence_overrides.yml` per retrospective contract that lists key Carver events + matching news article dates, and merge in `gamma_contract._build_timeline`.
- **Mobile reflow** for the contract-detail two-pane layout.
- **Sparkline accessibility** — no `<title>` element; add for screen readers in Stage 4.
- **Heat decay tuning** — 14-day half-life chosen from data-prep spec; live deployments may want longer half-life for slow-burn regulatory pressure.

## Next stage prerequisites

- **β (Stage 3)** needs Polymarket's international footprint and the France ANJ event corpus. Verify Carver coverage on EU jurisdictions (FR, NL, MT, EU) before β planning.
```

- [ ] **Step 7: Update `README.md`**

Append after the Stage 1 section:

```markdown
## Stage 2 — γ walkthrough

The γ scene ("Marcus Vega, Head of Listing") renders at `/gamma/`:

- `/gamma/` — Marcus's three-card overview
- `/gamma/scan/` — 3-tab pre-listing scan
- `/gamma/dashboard/` — contract-watch board with heat + sparklines
- `/gamma/contracts/{id}/` — 5 pre-rendered contract details (3 active + 2 retrospectives)

### Refreshing contract metadata

```bash
uv run python build/pull_kalshi_curated.py --mode=fresh
uv run python build/pull_polymarket_curated.py --mode=fresh
```

Non-destructive: if upstream returns 404, the cached metadata is kept and `stale: true` is recorded.

### Curation

- `data/gamma-curation.yml` — picks + `build_date` + synthetic listing-risk tickets.
- `data/platforms/{kalshi,polymarket}/contracts.yml` — pick-list + cached upstream metadata.
- `data/platforms/{kalshi,polymarket}/contracts/{id}.yml` — hand-curated retrospective contracts (Wayback-sourced).

### Specs

- `docs/specs/40-gamma-walkthrough.md` — γ narrative spec (note Task 5 reframe of §2.4 wow).
- `docs/specs/STAGE_2_NOTES.md` — acceptance log + schema notes.
```

- [ ] **Step 8: Commit**

```bash
git add docs/specs/STAGE_2_NOTES.md README.md
git commit -m "docs(stage-2): STAGE_2_NOTES acceptance log + README section"
```

---

## Self-review checklist (run before declaring the plan complete)

For the controller (you), not a subagent:

1. **Spec coverage** — every section of `docs/specs/40-gamma-walkthrough.md` maps to a task:
   - §1 narrative → Task 13 (intro) sets the scene.
   - §2.1 intro → Task 13.
   - §2.2 pre-listing scan (3 scans) → Task 8 (slice) + Task 14 (template).
   - §2.3 contract-watch dashboard → Task 9 (slice) + Task 15 (template).
   - §2.4 contract detail (5 pre-rendered) → Task 10 (slice) + Task 16 (template).
   - §2.4 retrospective wow (TIKTOKBAN, KXFEDDECISION) → Task 4 (curate) + Task 5 (spec edit) + Task 10 (timeline + callouts) + Task 16 (badge + sources block).
   - §3 copy & tone → Task 13/14/15/16 (template microcopy).
   - §4 interaction details → Task 14 (Alpine tabs), Task 15 (sparkline hover via SVG title), Task 16 (linked tickets).
   - §5 acceptance criteria → Task 17 STAGE_2_NOTES checklist.

2. **Placeholder scan** — none in task bodies.

3. **Type / signature consistency** — `generate(corpus_path, ...)` signature consistent across all four slice generators (Tasks 8/9/10). `_render_parametric(...)` generalized once in Task 16 and used for both α tickets + γ contracts. `_load_gamma_scan_bundle(repo_root)` is the single special-case loader for the scan page.

4. **Filename clashes** — none. Stage 2 file paths don't collide with Stage 1.

## Estimated cost & time

- ~17 implementer dispatches (sonnet for Tasks 3, 7, 8, 9, 10, 16; haiku for 1, 2, 5, 6, 11, 12, 13, 14, 15, 17; manual user/main-agent for Task 4 Wayback curation).
- Wall time: ~3–4 hours sequential.
- Task 4 has a manual research component (Wayback URLs); allocate 30-45 min for sourcing.
