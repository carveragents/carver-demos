# Trader Demo Data Integrity Fix — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Eliminate all synthetic data from the trader demo — every number on screen must trace to a real platform API or a documented derivation from real Carver data.

**Architecture:** 6-task sequence: (1) slim portfolio to verified contracts, (2) update tests, (3) fix the direction-propagation code bug, (4) wipe stale caches and pull real prices, (5) re-run enrichment pipeline, (6) rebuild site and validate. Tasks 1–3 are code changes with tests. Task 4 runs external APIs. Task 5 runs LLM enrichment. Task 6 verifies the site renders correctly with real data.

**Tech Stack:** Python 3.10, uv, pytest, OpenAI (gpt-5/gpt-5-mini), Kalshi public API, Polymarket Gamma/CLOB API, Jinja2

**Working directory:** `/Users/achintthomas/work/scribble/code/repos/carver/carver-demos/.claude/worktrees/feat-trader-demos/pred-oracle`

**Environment:** `.env` with `OPENAI_API_KEY` and `CARVER_API_KEY` is at the worktree root: `/Users/achintthomas/work/scribble/code/repos/carver/carver-demos/.claude/worktrees/feat-trader-demos/.env`

---

## File Map

| File | Action | Responsibility |
|---|---|---|
| `data/trader-curation.yml` | Modify | Remove 3 fake contracts, keep 3 active + 2 retrospective |
| `data/platforms/kalshi/contracts/kxuschina-tariffs-2026.yml` | Delete | Fabricated contract |
| `data/platforms/polymarket/contracts/sec-eth-security-2026.yml` | Delete | Fabricated contract |
| `data/platforms/polymarket/contracts/fatf-travel-rule-2027.yml` | Delete | Fabricated contract |
| `data/platforms/polymarket/contracts.yml` | Modify | Add real `condition_id` + `clob_token_ids` for recession; add `source_lookup.slug` fix |
| `data/platforms/polymarket/contracts/solana-etf-2025.yml` | Modify | Add real Polymarket condition_id + CLOB token IDs |
| `build/_relevance.py:124-138` | Modify | Fix `judge_batch()` to copy direction/magnitude/timeline_shift from verdict |
| `build/_prices.py:58-73` | Modify | Fix `fetch_kalshi()` to handle historical market tickers correctly |
| `tests/test_trader_curation.py` | Modify | Update expected counts: 3 portfolio, 2 retrospectives, remove fake YAML assertions |
| `tests/test_relevance_direction.py` | Modify | Add test for direction propagation through `judge_batch()` |
| `tests/test_trader_templates.py` | Modify | Update list template test to use 3 rows instead of 6 |

---

### Task 1: Slim portfolio to real contracts only

**Files:**
- Modify: `data/trader-curation.yml`
- Delete: `data/platforms/kalshi/contracts/kxuschina-tariffs-2026.yml`
- Delete: `data/platforms/polymarket/contracts/sec-eth-security-2026.yml`
- Delete: `data/platforms/polymarket/contracts/fatf-travel-rule-2027.yml`
- Modify: `data/platforms/polymarket/contracts.yml`
- Modify: `data/platforms/polymarket/contracts/solana-etf-2025.yml`

- [ ] **Step 1: Update `data/trader-curation.yml`**

Replace the entire file with:

```yaml
schema_version: 1
build_date: "2026-05-26"

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

retrospectives:
  - id: solana-etf-2025
    platform: polymarket
  - id: tiktokban-25apr30
    platform: kalshi
```

- [ ] **Step 2: Delete the 3 fabricated contract YAMLs**

```bash
rm data/platforms/kalshi/contracts/kxuschina-tariffs-2026.yml
rm data/platforms/polymarket/contracts/sec-eth-security-2026.yml
rm data/platforms/polymarket/contracts/fatf-travel-rule-2027.yml
```

- [ ] **Step 3: Add real Polymarket identifiers to `data/platforms/polymarket/contracts.yml`**

Add `condition_id` and `clob_token_ids` to the `us-recession-in-2026` cached block. Also fix the `source_lookup.slug` to the real Polymarket slug (the market was found at `us-recession-by-end-of-2026` but the existing slug `us-recession-in-2026` may also resolve — keep the existing slug but add the condition_id that the search found):

In `data/platforms/polymarket/contracts.yml`, inside the `cached:` block of `us-recession-in-2026`, add after `slug: us-recession-in-2026`:

```yaml
    condition_id: '0xfdc73f10edf0266756686f35b5712cffa828b0940fc015e0426c76c934c2105d'
    clob_token_ids:
      - '100379208559626151022751801118534484742123694725746262280150222742563282755057'
      - '113732820231608904682346496304917888352004831436510840986547065248348999143469'
```

- [ ] **Step 4: Add real Polymarket identifiers to `data/platforms/polymarket/contracts/solana-etf-2025.yml`**

Add these fields after `resolution_outcome: "YES"`:

```yaml
condition_id: '0xf106435e0c9a1b56fc1c0bea0ca3856a8d3a31b1c5f891f8c3600f4a66e74186'
clob_token_ids:
  - '40950322194820832807533485831393987792860704048110302763324386741027206308151'
  - '77613029953598772381982336999913863065916454247916111678568891881569398156706'
polymarket_slug: 'solana-etf-approved-in-2025'
```

- [ ] **Step 5: Delete stale page_data for removed contracts**

```bash
rm -f build/page_data/trader/contracts/sec-eth-security-2026.json
rm -f build/page_data/trader/contracts/kxuschina-tariffs-2026.json
rm -f build/page_data/trader/contracts/fatf-travel-rule-2027.json
rm -f build/_cache/prices/sec-eth-security-2026.json
rm -f build/_cache/prices/kxuschina-tariffs-2026.json
rm -f build/_cache/prices/fatf-travel-rule-2027.json
```

- [ ] **Step 6: Commit**

```bash
git add -A data/trader-curation.yml \
  data/platforms/kalshi/contracts/ \
  data/platforms/polymarket/contracts.yml \
  data/platforms/polymarket/contracts/ \
  build/page_data/trader/contracts/ \
  build/_cache/prices/
git commit -m "chore: slim trader portfolio to verified platform contracts

Remove sec-eth-security-2026, kxuschina-tariffs-2026, fatf-travel-rule-2027
(no real platform equivalents). Add real Polymarket condition_id + CLOB token
IDs for us-recession-in-2026 and solana-etf-2025."
```

---

### Task 2: Update tests for slimmed portfolio

**Files:**
- Modify: `tests/test_trader_curation.py`
- Modify: `tests/test_trader_templates.py`

- [ ] **Step 1: Update `tests/test_trader_curation.py`**

Replace the entire file with:

```python
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


def test_portfolio_has_three_contracts():
    doc = yaml.safe_load(CURATION.read_text())
    assert len(doc["portfolio"]) == 3


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


def test_all_portfolio_contracts_exist_in_contracts_yml():
    """Every active portfolio entry must exist in a contracts.yml picks list."""
    doc = yaml.safe_load(CURATION.read_text())
    kalshi = yaml.safe_load(
        (REPO / "data" / "platforms" / "kalshi" / "contracts.yml").read_text()
    )
    poly = yaml.safe_load(
        (REPO / "data" / "platforms" / "polymarket" / "contracts.yml").read_text()
    )
    pick_ids = set()
    for p in kalshi.get("picks", []):
        pick_ids.add(p["id"])
    for p in poly.get("picks", []):
        pick_ids.add(p["id"])
    for entry in doc["portfolio"]:
        assert entry["id"] in pick_ids, (
            f"{entry['id']} not found in any contracts.yml — must be API-pulled"
        )


def test_retrospective_yamls_exist():
    doc = yaml.safe_load(CURATION.read_text())
    for entry in doc["retrospectives"]:
        platform = entry["platform"]
        path = REPO / "data" / "platforms" / platform / "contracts" / f"{entry['id']}.yml"
        assert path.exists(), f"Missing retrospective YAML: {path}"
```

- [ ] **Step 2: Find and update the list template test in `tests/test_trader_templates.py`**

The test file has a `_make_row()` helper and tests that use it. Find tests that construct a hardcoded number of rows (e.g., passing 6 rows) and update them to use 3 rows. Specifically, any test that creates a fixed list like `rows = [_make_row(...) for _ in range(6)]` should change to `range(3)`. The sort test that needs multiple rows for sorting to be meaningful should use 3 distinct rows.

No structural changes are needed — just update the row count if any test hardcodes 6.

- [ ] **Step 3: Run tests to verify**

```bash
uv run pytest tests/test_trader_curation.py tests/test_trader_templates.py -v
```

Expected: All pass. The new `test_all_portfolio_contracts_exist_in_contracts_yml` validates that no fabricated contracts remain.

- [ ] **Step 4: Commit**

```bash
git add tests/test_trader_curation.py tests/test_trader_templates.py
git commit -m "test: update trader tests for slimmed portfolio (3 active + 2 retro)"
```

---

### Task 3: Fix direction propagation bug in `_relevance.py`

**Files:**
- Modify: `build/_relevance.py:124-138`
- Modify: `tests/test_relevance_direction.py`

- [ ] **Step 1: Write the failing test**

Add this test to `tests/test_relevance_direction.py`:

```python
from unittest.mock import patch

def test_judge_batch_propagates_direction_from_verdict():
    """Regression: judge_batch must copy direction/magnitude/timeline_shift
    from the LLM verdict into the enriched record dict."""
    contract = {
        "id": "test",
        "title": "Test",
        "resolution_criteria": "Test",
        "settlement_entities": ["SEC"],
    }
    conditions = [{"id": "A", "label": "test", "summary": "test"}]
    candidate = {
        "title": "SEC enforcement action",
        "feed_entry_id": "rec-1",
        "link": "https://example.com",
        "scores": {"urgency": {"score": 7, "label": "high"},
                   "relevance": {"score": 6, "label": "medium"}},
        "entities": ["SEC"],
        "topic_name": "SEC",
    }
    fake_verdict = {
        "relevant": True,
        "relevance_score": 8,
        "one_line_why": "Direct enforcement",
        "condition_tag": "A",
        "high_impact": True,
        "direction": "bearish",
        "magnitude": "high",
        "timeline_shift": "sooner",
    }
    with patch("build._relevance._llm.cache_key_for", return_value="fake-key"), \
         patch("build._relevance._llm.complete_json", return_value=fake_verdict):
        from build._relevance import judge_batch
        results = judge_batch(
            contract=contract,
            conditions=conditions,
            candidates=[candidate],
        )
    assert len(results) == 1
    rec = results[0]
    assert rec["direction"] == "bearish"
    assert rec["magnitude"] == "high"
    assert rec["timeline_shift"] == "sooner"
```

- [ ] **Step 2: Run test to verify it fails**

```bash
uv run pytest tests/test_relevance_direction.py::test_judge_batch_propagates_direction_from_verdict -v
```

Expected: FAIL — `assert rec["direction"] == "bearish"` fails because current code doesn't copy these fields (the record will have whatever was on the original `candidate` dict or be missing entirely, and `_project_timeline_fields` defaults to `"neutral"`).

- [ ] **Step 3: Fix `judge_batch()` in `build/_relevance.py`**

In `build/_relevance.py`, find the `enriched = {` block inside `judge_batch()` (around line 124). Currently it only copies 4 fields from the verdict. Add the 3 missing fields:

Change this block (lines 124-131):

```python
        enriched = {
            **rec,
            "one_line_why": verdict.get("one_line_why") or "",
            "condition_tag": verdict.get("condition_tag", "background"),
            "relevance_score": int(verdict.get("relevance_score", 0)),
            "high_impact": bool(verdict.get("high_impact", False)),
        }
```

To:

```python
        enriched = {
            **rec,
            "one_line_why": verdict.get("one_line_why") or "",
            "condition_tag": verdict.get("condition_tag", "background"),
            "relevance_score": int(verdict.get("relevance_score", 0)),
            "high_impact": bool(verdict.get("high_impact", False)),
            "direction": verdict.get("direction", "neutral"),
            "magnitude": verdict.get("magnitude", "low"),
            "timeline_shift": verdict.get("timeline_shift", "none"),
        }
```

- [ ] **Step 4: Run test to verify it passes**

```bash
uv run pytest tests/test_relevance_direction.py -v
```

Expected: All 6 tests pass (5 existing + 1 new).

- [ ] **Step 5: Commit**

```bash
git add build/_relevance.py tests/test_relevance_direction.py
git commit -m "fix: propagate direction/magnitude/timeline_shift from LLM verdict in judge_batch"
```

---

### Task 4: Wipe synthetic caches and pull real prices

**Files:**
- Modify: `build/_prices.py` (if Kalshi historical fetch needs fixing)
- Modify: `build/pull_prices.py` (ensure it uses condition_id for Polymarket resolved markets)
- Cache directories: `build/_cache/prices/`, `build/_cache/llm/relevance/`, `build/_cache/llm/heat_panel/`

- [ ] **Step 1: Wipe all synthetic price caches**

```bash
rm -rf build/_cache/prices/
```

- [ ] **Step 2: Wipe stale LLM caches**

The relevance cache has 8,147 entries all from the old schema (missing direction fields). The heat_panel cache has explainers that hallucinate "zero heat". Both must be regenerated.

```bash
rm -rf build/_cache/llm/relevance/
rm -rf build/_cache/llm/heat_panel/
```

Note: Do NOT wipe `build/_cache/llm/thesis/` or `build/_cache/llm/narrative/` — these were audited and contain valid responses. They will be re-used if the contract IDs match, or regenerated for contracts that changed.

- [ ] **Step 3: Update `build/pull_prices.py` to use Polymarket condition_id for resolved markets**

The current `fetch_polymarket()` in `_prices.py` looks up the slug via the Gamma API, but the Gamma API doesn't serve resolved markets. For retrospectives with known `clob_token_ids`, we can fetch price history directly from the CLOB API.

In `build/pull_prices.py`, update the polymarket branch inside the `for entry in all_contracts:` loop. Find the `elif platform == "polymarket":` block (around line 78) and replace it with:

```python
        elif platform == "polymarket":
            pick = poly_picks.get(cid)
            slug = cid
            condition_id = ""
            if pick:
                slug = pick.get("source_lookup", {}).get("slug", cid)
                condition_id = pick.get("cached", {}).get("condition_id", "")
            # For resolved markets or those with standalone YAMLs, check for clob_token_ids
            if not condition_id:
                retro_path = REPO / "data" / "platforms" / "polymarket" / "contracts" / f"{cid}.yml"
                if retro_path.exists():
                    retro = yaml.safe_load(retro_path.read_text())
                    condition_id = retro.get("condition_id", "")
                    clob_tokens = retro.get("clob_token_ids", [])
                    if clob_tokens:
                        slug = retro.get("polymarket_slug", cid)
            try:
                data = fetch_and_cache(
                    contract_id=cid, platform="polymarket", ticker=slug, slug=slug,
                )
                print(f"  {cid}: {len(data.series)} price points")
            except Exception as e:
                print(f"  WARN: {cid} fetch failed: {e}")
```

- [ ] **Step 4: Update `build/_prices.py` `fetch_polymarket()` to accept a direct `token_id` override**

In `build/_prices.py`, modify `fetch_polymarket()` to accept an optional `token_id` parameter. When provided, skip the Gamma API lookup and go straight to the CLOB price-history endpoint:

Change the signature and body of `fetch_polymarket()` (starting at line 75):

```python
def fetch_polymarket(
    *, slug: str, condition_id: str = "", token_id: str = "",
) -> list[dict[str, Any]]:
    if token_id:
        price_resp = httpx.get(
            f"{POLYMARKET_CLOB_BASE}/prices-history",
            params={"market": token_id, "interval": "max", "fidelity": 720},
            timeout=30,
        )
        price_resp.raise_for_status()
        return price_resp.json().get("history", [])
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
```

Also update `fetch_and_cache()` to pass `token_id` through. Add a `token_id: str = ""` parameter to `fetch_and_cache()` and pass it to `fetch_polymarket()`:

In `fetch_and_cache()` signature (line 101), add `token_id: str = ""`:

```python
def fetch_and_cache(
    *,
    contract_id: str,
    platform: str,
    ticker: str,
    slug: str = "",
    token_id: str = "",
    start_ts: int = 0,
    end_ts: int = 0,
    is_historical: bool = False,
    cache_dir: Path = DEFAULT_CACHE_DIR,
) -> PriceData:
```

And in the polymarket branch (around line 123), pass token_id:

```python
    elif platform == "polymarket":
        raw = fetch_polymarket(slug=slug or contract_id, token_id=token_id)
        series = normalize_polymarket_history(raw)
```

- [ ] **Step 5: Update `build/pull_prices.py` polymarket branch to pass `token_id` for resolved markets**

Update the polymarket branch in `pull_prices.py` to extract the first CLOB token ID and pass it:

```python
        elif platform == "polymarket":
            pick = poly_picks.get(cid)
            slug = cid
            token_id = ""
            if pick:
                slug = pick.get("source_lookup", {}).get("slug", cid)
                cached = pick.get("cached", {})
                clob_tokens = cached.get("clob_token_ids", [])
                if clob_tokens:
                    token_id = clob_tokens[0]
            if not token_id:
                retro_path = REPO / "data" / "platforms" / "polymarket" / "contracts" / f"{cid}.yml"
                if retro_path.exists():
                    retro = yaml.safe_load(retro_path.read_text())
                    clob_tokens = retro.get("clob_token_ids", [])
                    if clob_tokens:
                        token_id = clob_tokens[0]
                    slug = retro.get("polymarket_slug", slug)
            try:
                data = fetch_and_cache(
                    contract_id=cid, platform="polymarket", ticker=slug, slug=slug,
                    token_id=token_id,
                )
                print(f"  {cid}: {len(data.series)} price points (platform={data.platform})")
            except Exception as e:
                print(f"  WARN: {cid} fetch failed: {e}")
```

- [ ] **Step 6: Run price pull**

```bash
uv run python build/pull_prices.py
```

Expected: Each contract prints a line with the number of price points and `platform=kalshi` or `platform=polymarket`. No `synthetic` entries.

- [ ] **Step 7: Verify no synthetic prices remain**

```bash
python3 -c "
import json, os
for f in sorted(os.listdir('build/_cache/prices')):
    d = json.load(open(f'build/_cache/prices/{f}'))
    assert d['platform'] != 'synthetic', f'{f} is still synthetic!'
    print(f'{d[\"contract_id\"]:30s} platform={d[\"platform\"]:12s} pts={len(d[\"series\"])}')
print('All prices are real.')
"
```

Expected: All 5 entries show `platform=kalshi` or `platform=polymarket`. If any Polymarket fetch fails for resolved markets (404 from Gamma), the `token_id` direct path should handle it.

- [ ] **Step 8: Commit**

```bash
git add build/_prices.py build/pull_prices.py build/_cache/prices/
git commit -m "fix: replace synthetic prices with real Kalshi/Polymarket API data

Wipe all synthetic price caches. Add token_id direct-fetch path for
Polymarket resolved markets. Pull real prices for all 5 contracts."
```

---

### Task 5: Re-run enrichment pipeline with fixed code

**Files:**
- No code changes — this task runs the pipeline with the fixes from Tasks 1-4
- Requires: `OPENAI_API_KEY` in `.env`

- [ ] **Step 1: Verify OpenAI key is available**

```bash
cd /Users/achintthomas/work/scribble/code/repos/carver/carver-demos/.claude/worktrees/feat-trader-demos/pred-oracle
python3 -c "
import sys; sys.path.insert(0, 'build')
from build._llm import is_available
print('LLM available:', is_available())
"
```

Expected: `LLM available: True`. If False, check that `.env` at the worktree root contains `OPENAI_API_KEY`.

- [ ] **Step 2: Run full slice generation + enrichment**

```bash
uv run python build/generate_slices.py
```

This will:
1. Generate 5 trader contract slices (3 active + 2 retrospective)
2. Run LLM enrichment (thesis, relevance with direction, heat_panel, narrative) for each
3. Build portfolio.json and calendar.json from the enriched slices

Expected output includes lines like:
```
trader (build_date=2026-05-26): 5 contract details
  enriched 5 trader contract slices
  portfolio.json + calendar.json + 2 retrospectives
```

The relevance enrichment will make fresh LLM calls (~5 contracts × 20 events = ~100 calls to gpt-5-mini). This may take 2-5 minutes.

- [ ] **Step 3: Verify direction distribution is not 100% neutral**

```bash
python3 -c "
import json, os
for f in sorted(os.listdir('build/page_data/trader/contracts/')):
    d = json.load(open(f'build/page_data/trader/contracts/{f}'))
    tl = d['timeline']
    dirs = {}
    for ev in tl:
        dr = ev.get('direction', 'neutral')
        dirs[dr] = dirs.get(dr, 0) + 1
    cid = d['contract']['id']
    total = len(tl)
    neutral_pct = dirs.get('neutral', 0) / total * 100 if total else 0
    print(f'{cid:30s} events={total:2d} dirs={dirs} neutral%={neutral_pct:.0f}%')
"
```

Expected: At least some events should have `direction=bullish` or `direction=bearish`. If still 100% neutral, check the LLM cache — `ls build/_cache/llm/relevance/ | wc -l` should show newly created files (count will be much lower than the previous 8,147 since we only have 5 contracts now).

- [ ] **Step 4: Verify heat explainers are coherent**

```bash
python3 -c "
import json, os
for f in sorted(os.listdir('build/page_data/trader/contracts/')):
    d = json.load(open(f'build/page_data/trader/contracts/{f}'))
    hp = d.get('heat_panel', {})
    cid = d['contract']['id']
    val = hp.get('value', 0)
    tier = hp.get('tier', '?')
    explainer = hp.get('explainer', '')[:200]
    # Sanity: if heat > 50, explainer should NOT say 'dormant' or 'zero'
    if val > 50:
        assert 'dormant' not in explainer.lower(), f'{cid}: heat={val} but explainer says dormant'
        assert 'zero' not in explainer.lower() or 'non-zero' in explainer.lower(), f'{cid}: heat={val} but explainer says zero'
    print(f'{cid:30s} heat={val:7.1f} tier={tier:10s}')
    print(f'  explainer: {explainer}')
    print()
print('Heat explainers are coherent.')
"
```

Expected: No assertion errors. Explainers should reference actual regulatory activity, not claim dormancy.

- [ ] **Step 5: Commit enriched data**

```bash
git add build/page_data/trader/ build/_cache/llm/
git commit -m "data: re-run trader enrichment with direction bug fix

Fresh LLM relevance judgments with direction/magnitude/timeline_shift.
Fresh heat explainers matching actual heat values.
3 active + 2 retrospective contracts, all real data."
```

---

### Task 6: Rebuild site and validate

**Files:**
- No code changes — this task builds the site and validates the output

- [ ] **Step 1: Build the site**

```bash
uv run python build/generate.py
```

Expected: Renders trader pages without errors. Output includes:
```
trader/contracts: rendered 5 pages
trader/retrospectives: rendered 2 pages
```

(Some retrospectives may not render if gamma enriched data isn't available — that's OK for now.)

- [ ] **Step 2: Start the dev server**

```bash
cd site && python3 -m http.server 8000 &
cd ..
```

- [ ] **Step 3: Validate portfolio list page**

Open `http://localhost:8000/trader/` and verify:
- Exactly 3 contract cards shown (not 6)
- Each card has YES/NO prices in cents (not "50¢/50¢" placeholder)
- Heat values are non-zero with appropriate tier badges
- Direction shows actual directional signal (at least one Bullish or Bearish, not all Mixed)
- Sort buttons (Heat, Direction, Events) reorder cards correctly
- Platform filter shows Kalshi (2) and Polymarket (1)

- [ ] **Step 4: Validate contract briefing pages**

Click into each of the 3 active contracts and verify:
- Probability chart renders with dual YES/NO trendlines (real data, not flat synthetic lines)
- Timeline events have direction badges (not all neutral)
- Thesis tracker shows conditions
- Narrative text is present and coherent

- [ ] **Step 5: Validate calendar page**

Navigate to Calendar view and verify:
- Calendar renders with events for the current month
- Event dots are clickable with detail panel

- [ ] **Step 6: Validate retrospective pages**

Navigate to Case Studies and verify:
- Solana ETF and TikTok Ban cards are present
- Clicking through shows the briefing page with historical data

- [ ] **Step 7: Run all tests**

```bash
uv run pytest -v
```

Expected: All tests pass. If any tests reference 6 contracts or the removed contract IDs, they need updating (should have been caught in Task 2).

- [ ] **Step 8: Final data integrity check**

```bash
python3 -c "
import json, os

# Check prices: no synthetic
for f in os.listdir('build/_cache/prices'):
    d = json.load(open(f'build/_cache/prices/{f}'))
    assert d['platform'] != 'synthetic', f'FAIL: {f} is synthetic'

# Check directions: not 100% neutral
total_events = 0
non_neutral = 0
for f in os.listdir('build/page_data/trader/contracts/'):
    d = json.load(open(f'build/page_data/trader/contracts/{f}'))
    for ev in d['timeline']:
        total_events += 1
        if ev.get('direction') != 'neutral':
            non_neutral += 1

# Check portfolio: exactly 3 rows
portfolio = json.load(open('build/page_data/trader/portfolio.json'))
assert len(portfolio) == 3, f'Expected 3 portfolio rows, got {len(portfolio)}'

# Check no removed contracts remain
for cid in ['sec-eth-security-2026', 'kxuschina-tariffs-2026', 'fatf-travel-rule-2027']:
    assert not os.path.exists(f'build/page_data/trader/contracts/{cid}.json'), f'FAIL: {cid} still exists'
    assert not os.path.exists(f'build/_cache/prices/{cid}.json'), f'FAIL: {cid} price cache still exists'

print(f'Portfolio: {len(portfolio)} contracts')
print(f'Events: {total_events} total, {non_neutral} non-neutral ({non_neutral/total_events*100:.0f}%)')
print(f'Removed contracts: verified absent')
print('ALL DATA INTEGRITY CHECKS PASSED')
"
```

Expected: All assertions pass. Direction non-neutral percentage should be > 0%.

- [ ] **Step 9: Commit site build**

```bash
git add site/
git commit -m "build: rebuild trader site with real data only"
```

---

## Self-Review Checklist

| Spec requirement | Covered by |
|---|---|
| Remove 3 fabricated contracts | Task 1 Steps 1-2 |
| Delete standalone YAMLs | Task 1 Step 2 |
| Add real Polymarket identifiers | Task 1 Steps 3-4 |
| Delete stale page_data | Task 1 Step 5 |
| Fix direction code bug | Task 3 Step 3 |
| Wipe stale relevance cache | Task 4 Step 2 |
| Wipe stale heat_panel cache | Task 4 Step 2 |
| Pull real prices | Task 4 Steps 1, 6-7 |
| Re-run enrichment | Task 5 Step 2 |
| Verify direction not 100% neutral | Task 5 Step 3 |
| Verify heat explainers coherent | Task 5 Step 4 |
| Rebuild site | Task 6 Step 1 |
| Validate all pages | Task 6 Steps 3-6 |
| Run all tests | Task 6 Step 7 |
| Final integrity check | Task 6 Step 8 |
| Retrospective metadata from APIs | Task 1 Step 4 (Polymarket); Kalshi retro already in contracts.yml system |
| Update tests for slimmed portfolio | Task 2 |

**Placeholder scan:** No TBD/TODO/placeholder found.

**Type consistency:** `direction`, `magnitude`, `timeline_shift` field names consistent across `_relevance.py`, `trader_contract_enrich.py`, `_portfolio.py`, templates, and tests. `token_id` parameter name consistent in `_prices.py` and `pull_prices.py`.
