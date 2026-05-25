# γ Contract Intelligence Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace γ contract-detail's broad entity matching and abstract heat score with LLM-judged relevance, thesis decomposition, narrative summary, and a proper vertical timeline — driven by 6 curated contracts with cached OpenAI responses committed to the repo.

**Architecture:** Add `build/_llm.py` (sync OpenAI wrapper with disk cache + graceful degradation), four focused enrichment modules (`_thesis.py`, `_relevance.py`, `_heat_panel.py`, `_narrative.py`), and an orchestrator (`gamma_contract_enrich.py`) that mutates each slice JSON post-`gamma_contract.generate()`. Dashboard ripple: shows all 6 contracts with active/resolved sections and tier-dot heat cells.

**Tech Stack:** Python 3.10, OpenAI SDK (`gpt-5-mini` fast / `gpt-5` deep), `python-dotenv`, pytest, Jinja2, Tailwind CDN, Alpine.js CDN.

**Spec:** [docs/superpowers/specs/2026-05-20-gamma-contract-intelligence-design.md](../specs/2026-05-20-gamma-contract-intelligence-design.md)

**Model routing for subagent dispatch:**

| Task | Model | Reason |
|---|---|---|
| 1. Curation trim                | haiku  | Mechanical YAML edits |
| 2. Deps + env + gitignore       | haiku  | Config |
| 3. `_llm.py` module             | sonnet | Async-equivalent + cache + degradation logic |
| 4. `_heat_panel` tiers          | haiku  | Pure functions + thresholds |
| 5. Window scoping               | haiku  | Single function, date math |
| 6. `_thesis.py`                 | sonnet | LLM + JSON schema + fallback |
| 7. `_relevance.py`              | sonnet | Dynamic schema based on thesis, batch logic |
| 8. Heat panel explainer + sparkline | sonnet | LLM + computed fields |
| 9. `_narrative.py`              | haiku  | Single LLM call + fallback |
| 10. `gamma_contract_enrich.py`  | sonnet | Multi-step coordination |
| 11. `generate_slices.py` wiring | haiku  | Small wiring |
| 12. Dashboard retro rows + tier | sonnet | Multi-source data load + sort |
| 13. Dashboard template          | haiku  | Jinja + Tailwind |
| 14. Contract detail template    | sonnet | Significant restructure |
| 15. Capture LLM cache + verify  | sonnet | E2E + visual verification |

---

## File Structure

**Create:**

- `build/_llm.py` — OpenAI client with disk cache, structured outputs, graceful degradation
- `build/_thesis.py` — Thesis decomposition: contract → list[condition]
- `build/_relevance.py` — Per-record relevance judgment + 1-line why
- `build/_heat_panel.py` — Tier vocabulary, peer percentile, delta, urgency-weighted sparkline, LLM explainer
- `build/_narrative.py` — 2-3 sentence storyline summary
- `build/gamma_contract_enrich.py` — Orchestrator that runs all enrichment over slice JSONs
- `build/_cache/llm/.gitkeep` — Empty marker so the cache dir is checked in
- `tests/fixtures/llm/.gitkeep` — Empty marker for test fixture cache
- `tests/test_llm.py`
- `tests/test_thesis.py`
- `tests/test_relevance.py`
- `tests/test_heat_panel.py`
- `tests/test_narrative.py`
- `tests/test_gamma_contract_enrich.py`

**Modify:**

- `data/gamma-curation.yml` — Drop 3 picks (kxelonmars-99, rihanna-album-before-gta-vi) from featured/detail; drop ticket referencing dropped ids
- `data/platforms/kalshi/contracts.yml` — Drop kxelonmars-99, kxnextiranleader-45jan01, kxtrumpcabinet-26 picks
- `data/platforms/polymarket/contracts.yml` — Drop rihanna-album-before-gta-vi, warmest-year-on-record-2026 picks
- `.env.example` — Add `OPENAI_API_KEY`, `PRED_ORACLE_LLM_MODEL_FAST`, `PRED_ORACLE_LLM_MODEL_DEEP`
- `.gitignore` — Carve-out `!build/_cache/llm/` and `!build/_cache/llm/**`
- `pyproject.toml` — Add `openai>=1.50.0` dependency
- `build/gamma_contract.py:64-118` — Add window scoping to `_build_timeline`
- `build/gamma_dashboard.py` — Load retrospectives; resolution-window heat; tier; sort by section
- `build/generate_slices.py` — Call `gamma_contract_enrich.enrich_all` after γ contract pass
- `build/templates/gamma/contract_detail.html` — Full restructure: heat panel, narrative, vertical timeline, legend, Alpine filter
- `build/templates/gamma/dashboard.html` — "Resolved" divider, tier dot, heat window subtitle
- `build/templates/gamma/_components/contract_row.html` — Tier dot in heat cell
- `tests/test_gamma_contract.py` — Update expectations for window scoping
- `tests/test_gamma_dashboard.py` — Update for retro rows + tier
- `tests/test_gamma_templates.py` — Update for restructured DOM
- `tests/test_generate_slices.py` — Update for enrich step
- `tests/test_retrospective_contracts.py` — Update for trimmed set

---

## Task 1: Trim contract curation to 6

**Files:**
- Modify: `data/gamma-curation.yml`
- Modify: `data/platforms/kalshi/contracts.yml`
- Modify: `data/platforms/polymarket/contracts.yml`
- Modify: `tests/test_retrospective_contracts.py` (only if assertions reference dropped ids)

- [ ] **Step 1: Edit `data/gamma-curation.yml`**

In `featured_kalshi` block, remove these two entries (keep the other three):

```yaml
  - series_ticker: "KXELONMARS"
  - series_ticker: "KXNEXTIRANLEADER"
```

In `featured_polymarket` block, remove:

```yaml
  - slug: "new-rhianna-album-before-gta-vi-926"
  - slug: "will-2026-be-warmest-year-on-record"
```

In `contract_detail_picks` block, remove (keep the other six):

```yaml
  - id: "kxelonmars-99"
    platform: "kalshi"
    kind: "active"
  - id: "rihanna-album-before-gta-vi"
    platform: "polymarket"
    kind: "active"
```

In `synthetic_listing_risk_tickets`, remove any ticket whose `contract_id` is one of the five dropped ids. After this trim the `kxfeddecision-26mar` ticket should remain.

- [ ] **Step 2: Edit `data/platforms/kalshi/contracts.yml`**

Remove the `picks` entries with `id: kxelonmars-99`, `id: kxnextiranleader-45jan01`, and `id: kxtrumpcabinet-26`. Keep `kxfeddecision-28jan`, `kxbtc-maxprice-2026`.

Note: `kxfeddecision-26mar` (retrospective) is NOT in this file; it lives at `data/platforms/kalshi/contracts/kxfeddecision-26mar.yml`. Don't touch the retrospective YAML files.

- [ ] **Step 3: Edit `data/platforms/polymarket/contracts.yml`**

Remove `picks` entries with `id: rihanna-album-before-gta-vi` and `id: warmest-year-on-record-2026`. Keep only `us-recession-in-2026`.

- [ ] **Step 4: Verify YAML loads + has expected counts**

Run:

```bash
python3 -c "
import yaml
g = yaml.safe_load(open('data/gamma-curation.yml'))
k = yaml.safe_load(open('data/platforms/kalshi/contracts.yml'))
p = yaml.safe_load(open('data/platforms/polymarket/contracts.yml'))
assert len(g['featured_kalshi']) == 3, len(g['featured_kalshi'])
assert len(g['featured_polymarket']) == 1, len(g['featured_polymarket'])
assert len(g['contract_detail_picks']) == 6, len(g['contract_detail_picks'])
assert len(k['picks']) == 2, len(k['picks'])
assert len(p['picks']) == 1, len(p['picks'])
print('OK')
"
```

Expected: `OK`

- [ ] **Step 5: Run existing tests, fix any that assert on dropped ids**

Run: `pytest tests/test_retrospective_contracts.py tests/test_gamma_curation.py tests/test_contracts_yml.py -v`

Update assertions only if they reference one of the five dropped ids. Do not change other assertions.

- [ ] **Step 6: Commit**

```bash
git add data/gamma-curation.yml data/platforms/kalshi/contracts.yml data/platforms/polymarket/contracts.yml tests/
git commit -m "feat(γ): trim contract set to 6 for LLM-enriched demo

Drops kxelonmars-99, rihanna-album-before-gta-vi, kxnextiranleader,
kxtrumpcabinet, warmest-year-on-record-2026. Caps cold-build LLM
cost and removes dashboard-row → 404 broken links."
```

---

## Task 2: Add OpenAI dep, env template, gitignore carve-out

**Files:**
- Modify: `pyproject.toml`
- Modify: `.env.example`
- Modify: `.gitignore`
- Create: `build/_cache/llm/.gitkeep`
- Create: `tests/fixtures/llm/.gitkeep`

- [ ] **Step 1: Add OpenAI dep to `pyproject.toml`**

In the `dependencies` list, add `openai` after `python-dotenv`:

```toml
dependencies = [
    "jinja2>=3.1.3",
    "markdown-it-py>=3.0.0",
    "pyyaml>=6.0.1",
    "httpx>=0.27.0",
    "carver-feeds-sdk>=0.1.0",
    "python-dotenv>=1.0.0",
    "openai>=1.50.0",
]
```

- [ ] **Step 2: Add LLM env vars to `.env.example`**

Append to `.env.example`:

```bash

# OpenAI API key — required only for refreshing the γ contract-intelligence
# LLM cache. Cached responses are committed to build/_cache/llm/, so demo
# builds work without this key.
OPENAI_API_KEY=sk-...

# Optional model overrides. Defaults to gpt-5-mini for high-volume
# per-record calls and gpt-5 for thesis decomposition / narrative.
# PRED_ORACLE_LLM_MODEL_FAST=gpt-5-mini
# PRED_ORACLE_LLM_MODEL_DEEP=gpt-5
```

- [ ] **Step 3: Add gitignore carve-out for LLM cache**

Append to `.gitignore`:

```
# LLM response cache — committed to keep demo builds deterministic
!build/_cache/
!build/_cache/llm/
!build/_cache/llm/**
```

- [ ] **Step 4: Create cache dir marker files**

```bash
mkdir -p build/_cache/llm tests/fixtures/llm
touch build/_cache/llm/.gitkeep tests/fixtures/llm/.gitkeep
```

- [ ] **Step 5: Install + verify import**

```bash
uv sync --dev
python3 -c "import openai; print(openai.__version__)"
```

Expected: a version ≥ `1.50.0`.

- [ ] **Step 6: Commit**

```bash
git add pyproject.toml .env.example .gitignore build/_cache/llm/.gitkeep tests/fixtures/llm/.gitkeep uv.lock
git commit -m "build: add openai dep, env template, llm cache dirs"
```

---

## Task 3: Implement `_llm.py` — OpenAI wrapper with cache + degradation

**Files:**
- Create: `build/_llm.py`
- Create: `tests/test_llm.py`

- [ ] **Step 1: Write failing test for cache hit path**

Create `tests/test_llm.py`:

```python
"""Tests for build/_llm.py."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest


def test_cache_hit_returns_cached_response_without_calling_openai(tmp_path: Path) -> None:
    from build import _llm

    cache_root = tmp_path / "cache"
    purpose_dir = cache_root / "thesis"
    purpose_dir.mkdir(parents=True)

    payload = {"conditions": [{"id": "A", "label": "Test", "summary": "x"}]}
    (purpose_dir / "ctr-1.json").write_text(json.dumps({
        "request": {"model": "gpt-5", "system": "s", "user": "u"},
        "response": payload,
    }))

    # No OPENAI_API_KEY needed: cache hit short-circuits before the client.
    result = _llm.complete_json(
        purpose="thesis", cache_key="ctr-1",
        model="gpt-5", system="s", user="u",
        schema={"type": "object"}, cache_root=cache_root,
    )
    assert result == payload


def test_cache_miss_without_api_key_returns_none(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from build import _llm
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    result = _llm.complete_json(
        purpose="thesis", cache_key="missing",
        model="gpt-5", system="s", user="u",
        schema={"type": "object"}, cache_root=tmp_path / "empty",
    )
    assert result is None


def test_cache_key_sha_is_stable(tmp_path: Path) -> None:
    from build._llm import cache_key_for

    k1 = cache_key_for(model="gpt-5", system="s", user="u",
                       schema={"type": "object", "properties": {"a": 1}})
    k2 = cache_key_for(model="gpt-5", system="s", user="u",
                       schema={"properties": {"a": 1}, "type": "object"})
    assert k1 == k2  # JSON serialization is sorted


def test_is_available_reflects_env_and_import(monkeypatch: pytest.MonkeyPatch) -> None:
    from build import _llm
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    assert _llm.is_available() is True
    monkeypatch.delenv("OPENAI_API_KEY")
    assert _llm.is_available() is False
```

- [ ] **Step 2: Run tests to verify failure**

Run: `pytest tests/test_llm.py -v`

Expected: All 4 tests fail with `ModuleNotFoundError: No module named 'build._llm'` (or similar).

- [ ] **Step 3: Implement `build/_llm.py`**

```python
"""OpenAI client wrapper with disk cache, structured outputs, and graceful
degradation. Synchronous API; parallelize at caller using ThreadPoolExecutor.

Cache layout: cache_root/<purpose>/<cache_key>.json. Each entry stores both
the request fingerprint and the response so a human can diff during review.

Env vars (loaded from `.env` via python-dotenv at module import):
- OPENAI_API_KEY      required for any live call
- PRED_ORACLE_LLM_MODEL_FAST   default 'gpt-5-mini'
- PRED_ORACLE_LLM_MODEL_DEEP   default 'gpt-5'
"""
from __future__ import annotations

import hashlib
import json
import os
import time
from pathlib import Path
from typing import Any

try:
    from dotenv import load_dotenv

    _REPO_ROOT = Path(__file__).resolve().parent.parent
    load_dotenv(_REPO_ROOT / ".env")
except ImportError:
    pass

try:
    from openai import OpenAI

    _OPENAI_INSTALLED = True
except ImportError:
    OpenAI = None  # type: ignore[assignment,misc]
    _OPENAI_INSTALLED = False


DEFAULT_CACHE_ROOT = Path(__file__).resolve().parent / "_cache" / "llm"
MODEL_FAST = os.environ.get("PRED_ORACLE_LLM_MODEL_FAST", "gpt-5-mini")
MODEL_DEEP = os.environ.get("PRED_ORACLE_LLM_MODEL_DEEP", "gpt-5")


def is_available() -> bool:
    """True if OPENAI_API_KEY is set AND openai package is importable."""
    return _OPENAI_INSTALLED and bool(os.environ.get("OPENAI_API_KEY"))


def cache_key_for(*, model: str, system: str, user: str, schema: dict[str, Any]) -> str:
    """Stable SHA-256 hash of the request inputs."""
    payload = json.dumps(
        {"model": model, "system": system, "user": user, "schema": schema},
        sort_keys=True,
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:32]


def complete_json(
    *,
    purpose: str,
    cache_key: str,
    model: str,
    system: str,
    user: str,
    schema: dict[str, Any],
    cache_root: Path | None = None,
    max_retries: int = 3,
) -> dict[str, Any] | None:
    """Return parsed JSON response, hitting disk cache before calling OpenAI.

    Returns None on any failure (no key, no install, all retries exhausted).
    Callers must handle None via documented fallbacks.
    """
    cache_root = cache_root or DEFAULT_CACHE_ROOT
    cache_path = cache_root / purpose / f"{cache_key}.json"
    if cache_path.exists():
        try:
            entry = json.loads(cache_path.read_text())
            return entry.get("response")  # type: ignore[no-any-return]
        except json.JSONDecodeError:
            pass  # corrupted cache → re-fetch

    if not is_available():
        return None

    assert OpenAI is not None  # for type-checker, guarded by is_available
    client = OpenAI()

    last_err: Exception | None = None
    for attempt in range(max_retries):
        try:
            resp = client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
                response_format={
                    "type": "json_schema",
                    "json_schema": {
                        "name": purpose,
                        "schema": schema,
                        "strict": True,
                    },
                },
            )
            content = resp.choices[0].message.content or "{}"
            parsed = json.loads(content)
            cache_path.parent.mkdir(parents=True, exist_ok=True)
            cache_path.write_text(json.dumps({
                "request": {"model": model, "system": system, "user": user, "schema": schema},
                "response": parsed,
            }, indent=2))
            return parsed  # type: ignore[no-any-return]
        except Exception as e:  # noqa: BLE001
            last_err = e
            time.sleep(2 ** attempt)

    print(f"WARN: llm call failed for purpose={purpose} key={cache_key}: {last_err}")
    return None
```

- [ ] **Step 4: Re-run tests, expect pass**

Run: `pytest tests/test_llm.py -v`

Expected: 4 passed.

- [ ] **Step 5: Run mypy strict on the new module**

Run: `mypy --strict build/_llm.py`

Expected: `Success: no issues found in 1 source file`. If mypy complains about `OpenAI = None`, the `type: ignore` comments above are pre-placed; verify they're present.

- [ ] **Step 6: Commit**

```bash
git add build/_llm.py tests/test_llm.py
git commit -m "feat(γ): add _llm.py OpenAI wrapper with disk cache + degradation"
```

---

## Task 4: Implement heat tier vocabulary in `_heat_panel.py`

**Files:**
- Create: `build/_heat_panel.py`
- Create: `tests/test_heat_panel.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_heat_panel.py`:

```python
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
    assert peer_percentile(0, [10, 20, 30]) == 33           # 1 of 3 ≤ 0


def test_peer_percentile_empty_peers_returns_zero() -> None:
    from build._heat_panel import peer_percentile
    assert peer_percentile(50, []) == 0


def test_urgency_weighted_sparkline_sums_urgency_per_day() -> None:
    from datetime import date
    from build._heat_panel import urgency_weighted_sparkline

    today = date(2026, 5, 20)
    records = [
        {"pub_date": "2026-05-20", "scores": {"urgency": {"score": 8}}},
        {"pub_date": "2026-05-20", "scores": {"urgency": {"score": 4}}},
        {"pub_date": "2026-05-18", "scores": {"urgency": {"score": 6}}},
        {"pub_date": "2026-05-07", "scores": {"urgency": {"score": 9}}},
    ]
    spark = urgency_weighted_sparkline(records, today=today, days=14)
    assert len(spark) == 14
    assert spark[-1] == 12  # today: 8 + 4
    assert spark[-3] == 6   # today - 2
    assert spark[0] == 9    # today - 13
    assert spark[5] == 0    # an idle day
```

- [ ] **Step 2: Run tests to verify failure**

Run: `pytest tests/test_heat_panel.py -v`

Expected: All 4 tests fail with `ModuleNotFoundError: No module named 'build._heat_panel'`.

- [ ] **Step 3: Implement `build/_heat_panel.py`**

```python
"""Heat tier vocabulary, peer percentile, urgency-weighted sparkline.

Pure computation; LLM-backed explainer lives in this same module but is
added in Task 8.
"""
from __future__ import annotations

from datetime import date
from typing import Any, Literal

from build import _fields

Tier = Literal["dormant", "watch", "active", "critical"]

_TIER_THRESHOLDS: list[tuple[float, Tier]] = [
    (70.0, "critical"),
    (30.0, "active"),
    (10.0, "watch"),
    (0.0, "dormant"),
]


def tier_for(value: float) -> Tier:
    """Map a heat score to one of dormant/watch/active/critical."""
    for threshold, tier in _TIER_THRESHOLDS:
        if value >= threshold:
            return tier
    return "dormant"


def peer_percentile(value: float, peers: list[float]) -> int:
    """Percentile rank (0-100) of `value` against `peers` (inclusive count).

    Returns 0 when peers is empty.
    """
    if not peers:
        return 0
    leq = sum(1 for p in peers if p <= value)
    return round(100 * leq / len(peers))


def urgency_weighted_sparkline(
    records: list[dict[str, Any]], *, today: date, days: int = 14,
) -> list[int]:
    """Sum of urgency per day for the past `days` (oldest first).

    Each record contributes its urgency score to the bucket of its pub_date.
    """
    buckets = [0] * days
    for rec in records:
        age = _fields.pub_date_age_days(rec, today=today)
        if age is None or age < 0 or age >= days:
            continue
        urgency = _fields.urgency_score(rec)
        buckets[days - 1 - age] += int(urgency)
    return buckets
```

- [ ] **Step 4: Re-run tests, expect pass**

Run: `pytest tests/test_heat_panel.py -v`

Expected: 4 passed.

- [ ] **Step 5: mypy strict**

Run: `mypy --strict build/_heat_panel.py`

Expected: Success.

- [ ] **Step 6: Commit**

```bash
git add build/_heat_panel.py tests/test_heat_panel.py
git commit -m "feat(γ): heat tier vocabulary, peer percentile, urgency sparkline"
```

---

## Task 5: Add window scoping to `_build_timeline`

**Files:**
- Modify: `build/gamma_contract.py:64-118`
- Modify: `tests/test_gamma_contract.py`

- [ ] **Step 1: Write failing test for window scoping**

Append to `tests/test_gamma_contract.py`:

```python
def test_retrospective_excludes_events_past_resolved_at(tmp_path: Path) -> None:
    """Retrospective contracts must not show timeline events after resolved_at."""
    from build.gamma_contract import generate

    corpus = tmp_path / "artifacts.jsonl"
    gamma_cur = tmp_path / "gamma-curation.yml"
    kalshi_yml = tmp_path / "kalshi.yml"
    poly_yml = tmp_path / "poly.yml"
    out_dir = tmp_path / "contracts"
    retros_root = tmp_path / "retros"
    (retros_root / "kalshi" / "contracts").mkdir(parents=True)
    _write_retro(retros_root / "kalshi" / "contracts" / "ttb.yml",
                 id="ttb", title="TikTok Ban",
                 settlement_entities=["TikTok"],
                 listed_at="2024-04-24",
                 resolved_at="2025-04-30")

    _write_corpus(corpus, [
        # in-window: should appear
        make_row(entities=["TikTok"], title="In window", pub_date="2025-03-01"),
        # before lead-in (90d before listed_at): should be dropped
        make_row(entities=["TikTok"], title="Too early", pub_date="2023-01-01"),
        # post-resolution: should be dropped
        make_row(entities=["TikTok"], title="After resolution", pub_date="2025-12-01"),
    ])
    _write_gamma_curation(gamma_cur,
        picks=[{"id": "ttb", "platform": "kalshi", "kind": "retrospective"}])
    _write_kalshi_contracts(kalshi_yml, [])
    poly_yml.write_text("schema_version: 1\npicks: []\n")

    generate(corpus_path=corpus, gamma_curation_path=gamma_cur,
             kalshi_contracts_path=kalshi_yml, polymarket_contracts_path=poly_yml,
             retrospectives_root=retros_root, out_dir=out_dir,
             today=date(2026, 5, 20))

    doc = json.loads((out_dir / "ttb.json").read_text())
    titles = [ev["title"] for ev in doc["timeline"]]
    assert "In window" in titles
    assert "Too early" not in titles
    assert "After resolution" not in titles


def test_active_excludes_events_before_lead_in(tmp_path: Path) -> None:
    from build.gamma_contract import generate

    corpus = tmp_path / "artifacts.jsonl"
    gamma_cur = tmp_path / "gamma-curation.yml"
    kalshi_yml = tmp_path / "kalshi.yml"
    poly_yml = tmp_path / "poly.yml"
    out_dir = tmp_path / "contracts"
    retros_root = tmp_path / "retros"
    (retros_root / "kalshi" / "contracts").mkdir(parents=True)

    _write_corpus(corpus, [
        make_row(entities=["FOMC"], title="In window", pub_date="2026-04-01"),
        make_row(entities=["FOMC"], title="Too early", pub_date="2025-01-01"),
    ])
    _write_gamma_curation(gamma_cur,
        picks=[{"id": "k1", "platform": "kalshi", "kind": "active"}])
    _write_kalshi_contracts(kalshi_yml, [{
        "id": "k1",
        "cached": {"title": "T", "ticker": "K1", "status": "active",
                   "listed_at": "2026-02-01", "expires_at": "2026-12-31",
                   "resolution_criteria": "r",
                   "settlement_entities": ["FOMC"]},
    }])
    poly_yml.write_text("schema_version: 1\npicks: []\n")

    generate(corpus_path=corpus, gamma_curation_path=gamma_cur,
             kalshi_contracts_path=kalshi_yml, polymarket_contracts_path=poly_yml,
             retrospectives_root=retros_root, out_dir=out_dir,
             today=date(2026, 5, 20))

    doc = json.loads((out_dir / "k1.json").read_text())
    titles = [ev["title"] for ev in doc["timeline"]]
    assert "In window" in titles
    assert "Too early" not in titles
```

Helper (add to top of file if not present):

```python
def _write_retro(p, **kwargs) -> None:
    base = {"schema_version": 1, "kind": "retrospective", "platform": "kalshi",
            "title": "T", "resolution_criteria": "r", "status": "resolved",
            "listed_at": "2025-01-01", "resolved_at": "2025-12-31",
            "settlement_entities": [], "source_urls": []}
    base.update(kwargs)
    p.write_text(yaml.safe_dump(base))
```

- [ ] **Step 2: Run tests to verify failure**

Run: `pytest tests/test_gamma_contract.py::test_retrospective_excludes_events_past_resolved_at tests/test_gamma_contract.py::test_active_excludes_events_before_lead_in -v`

Expected: Both fail (events outside window currently included).

- [ ] **Step 3: Update `_build_timeline` signature and add window logic**

In `build/gamma_contract.py`, replace `_build_timeline` (lines 64-118) with:

```python
def _parse_date(s: str) -> date | None:
    """Parse a YYYY-MM-DD (or ISO with time) date string. Returns None on failure."""
    if not s:
        return None
    try:
        return date.fromisoformat(s[:10])
    except ValueError:
        return None


def _window_for(
    listed_at: str, resolved_at: str, today: date, is_retrospective: bool,
) -> tuple[date | None, date | None]:
    """Compute timeline window per spec §4 Layer 1.

    Retrospective: [listed_at - 90d, resolved_at]
    Active:        [listed_at - 90d, today]
    """
    from datetime import timedelta
    listed = _parse_date(listed_at)
    if not listed:
        return (None, None)
    start = listed - timedelta(days=90)
    if is_retrospective:
        end = _parse_date(resolved_at) or today
    else:
        end = today
    return (start, end)


def _build_timeline(
    settlement_entities: list[str],
    corpus: list[dict[str, Any]],
    today: date,
    is_retrospective: bool,
    window_start: date | None,
    window_end: date | None,
) -> list[dict[str, Any]]:
    matches: list[tuple[dict[str, Any], str]] = []
    seen_titles: set[str] = set()
    for rec in corpus:
        if not _heat.is_substantive(rec):
            continue
        rec_entities = rec.get("entities") or []
        pub_iso = _fields.pub_date_iso(rec)
        pub = _parse_date(pub_iso)
        if pub is None:
            continue
        if window_start and pub < window_start:
            continue
        if window_end and pub > window_end:
            continue
        title_key = (rec.get("title") or "").strip().lower()
        if not title_key or title_key in seen_titles:
            continue
        for ce in settlement_entities:
            if _heat.entity_match([ce], rec_entities):
                matches.append((rec, ce))
                seen_titles.add(title_key)
                break

    matches.sort(key=lambda pair: _fields.pub_date_iso(pair[0]), reverse=True)

    timeline: list[dict[str, Any]] = []
    for rec, ce in matches:
        entry: dict[str, Any] = {
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
            entry["precedence_callout"] = {
                "news_date": None, "news_url": None, "days_ahead": None, "label": None,
            }
        timeline.append(entry)
    return timeline
```

Note the top-25 cap is **removed** — the relevance step in Task 7 will trim to 20 after LLM judgment.

- [ ] **Step 4: Update the call site to pass window**

In `build/gamma_contract.py`, find where `_build_timeline` is invoked inside `generate()` (around line 217) and replace with:

```python
        is_retro = kind == "retrospective"
        window_start, window_end = _window_for(
            listed_at=dto.get("listed_at", ""),
            resolved_at=dto.get("resolved_at", ""),
            today=today,
            is_retrospective=is_retro,
        )
        timeline = _build_timeline(
            flat, corpus, today, is_retro, window_start, window_end,
        )
```

- [ ] **Step 5: Run tests, expect pass**

Run: `pytest tests/test_gamma_contract.py -v`

Expected: All tests pass (existing + the 2 new). If any pre-existing test breaks, the most likely cause is an assertion about a record that's now outside the test contract's window — adjust the test's `listed_at` / `resolved_at` to keep the record inside the window.

- [ ] **Step 6: Run mypy + ruff**

Run: `mypy --strict build/gamma_contract.py && ruff check build/gamma_contract.py`

Expected: Both clean.

- [ ] **Step 7: Commit**

```bash
git add build/gamma_contract.py tests/test_gamma_contract.py
git commit -m "feat(γ): scope contract timeline to [listed_at-90d, resolved_at|today]"
```

---

## Task 6: Implement `_thesis.py` — resolution criteria → conditions

**Files:**
- Create: `build/_thesis.py`
- Create: `tests/test_thesis.py`
- Create: `tests/fixtures/llm/thesis/ttb.json` (test cache fixture)

- [ ] **Step 1: Write fixture cache file**

Create `tests/fixtures/llm/thesis/ttb.json`:

```json
{
  "request": {"model": "gpt-5", "system": "...", "user": "..."},
  "response": {
    "conditions": [
      {"id": "A", "label": "App-store unavailability",
       "summary": "TikTok unavailable in US Apple/Google stores by 2025-04-30."},
      {"id": "B", "label": "Federal divestiture order",
       "summary": "PAFACA enforcement order from DoC/DoJ in effect by 2025-04-30."}
    ]
  }
}
```

- [ ] **Step 2: Write failing tests**

Create `tests/test_thesis.py`:

```python
"""Tests for build/_thesis.py."""
from __future__ import annotations

from pathlib import Path

import pytest


FIXTURE_CACHE = Path(__file__).parent / "fixtures" / "llm"


def test_decompose_returns_cached_conditions(monkeypatch: pytest.MonkeyPatch) -> None:
    from build import _thesis

    monkeypatch.delenv("OPENAI_API_KEY", raising=False)  # cache hit only
    result = _thesis.decompose(
        contract_id="ttb",
        title="Will TikTok be banned",
        resolution_criteria="Resolves YES if TikTok unavailable...",
        settlement_entities=["TikTok", "ByteDance"],
        cache_root=FIXTURE_CACHE,
    )
    assert len(result) == 2
    assert result[0]["id"] == "A"
    assert result[1]["label"] == "Federal divestiture order"


def test_decompose_falls_back_when_no_cache_and_no_key(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    from build import _thesis

    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    result = _thesis.decompose(
        contract_id="missing",
        title="t", resolution_criteria="rc",
        settlement_entities=[],
        cache_root=tmp_path / "empty",
    )
    assert len(result) == 1
    assert result[0]["id"] == "A"
    assert result[0]["label"] == "Resolution criteria"
    assert "rc" in result[0]["summary"]
```

- [ ] **Step 3: Run tests to verify failure**

Run: `pytest tests/test_thesis.py -v`

Expected: Both fail with `ModuleNotFoundError`.

- [ ] **Step 4: Implement `build/_thesis.py`**

```python
"""Thesis decomposition for a γ contract.

One LLM call per contract: breaks resolution criteria into 1-3 atomic
conditions. Cached by contract id (stable across runs).
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, cast

from build import _llm


_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "conditions": {
            "type": "array",
            "minItems": 1,
            "maxItems": 3,
            "items": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "id": {"type": "string", "enum": ["A", "B", "C"]},
                    "label": {"type": "string"},
                    "summary": {"type": "string"},
                },
                "required": ["id", "label", "summary"],
            },
        },
    },
    "required": ["conditions"],
}

_SYSTEM = (
    "You are a regulatory analyst. Decompose a prediction-market contract's "
    "resolution criteria into 1-3 atomic conditions. Each condition should "
    "describe one independent path by which the contract can resolve YES. "
    "Return JSON matching the provided schema; labels ≤ 40 chars; summaries "
    "≤ 200 chars."
)


def decompose(
    *,
    contract_id: str,
    title: str,
    resolution_criteria: str,
    settlement_entities: list[str],
    cache_root: Path | None = None,
) -> list[dict[str, str]]:
    """Return list of condition dicts {id, label, summary}.

    Falls back to a single 'A: Resolution criteria' condition when LLM is
    unavailable AND cache misses.
    """
    user = (
        f"Title: {title}\n"
        f"Resolution criteria: {resolution_criteria}\n"
        f"Settlement entities: {settlement_entities}"
    )
    response = _llm.complete_json(
        purpose="thesis",
        cache_key=contract_id,
        model=_llm.MODEL_DEEP,
        system=_SYSTEM,
        user=user,
        schema=_SCHEMA,
        cache_root=cache_root,
    )
    if response is None:
        return [{
            "id": "A",
            "label": "Resolution criteria",
            "summary": resolution_criteria[:200],
        }]
    return cast(list[dict[str, str]], response["conditions"])
```

- [ ] **Step 5: Re-run tests, expect pass**

Run: `pytest tests/test_thesis.py -v`

Expected: 2 passed.

- [ ] **Step 6: mypy strict**

Run: `mypy --strict build/_thesis.py`

Expected: Success.

- [ ] **Step 7: Commit**

```bash
git add build/_thesis.py tests/test_thesis.py tests/fixtures/llm/thesis/
git commit -m "feat(γ): _thesis.py — decompose resolution criteria into conditions"
```

---

## Task 7: Implement `_relevance.py` — per-record relevance judgment

**Files:**
- Create: `build/_relevance.py`
- Create: `tests/test_relevance.py`
- Create: `tests/fixtures/llm/relevance/<sha>.json` (one fixture entry)

- [ ] **Step 1: Write failing tests**

Create `tests/test_relevance.py`:

```python
"""Tests for build/_relevance.py."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from build import _llm

FIXTURE_CACHE = Path(__file__).parent / "fixtures" / "llm"


def test_judge_uses_cache_drops_irrelevant_and_sorts(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    from build._relevance import judge_batch

    contract = {
        "id": "ttb", "title": "TikTok ban?", "resolution_criteria": "...",
        "settlement_entities": ["TikTok"],
    }
    conditions = [{"id": "A", "label": "x", "summary": "y"}]
    candidates = [
        {"feed_entry_id": "r1", "title": "PAFACA reauth", "pub_date": "2025-03-01",
         "scores": {"urgency": {"score": 8}}, "entities": ["TikTok"], "link": "u1"},
        {"feed_entry_id": "r2", "title": "Irrelevant", "pub_date": "2025-02-01",
         "scores": {"urgency": {"score": 6}}, "entities": ["TikTok"], "link": "u2"},
    ]

    # Pre-write cache entries for both candidates
    cache_dir = tmp_path / "cache" / "relevance"
    cache_dir.mkdir(parents=True)
    for cand, payload in [
        (candidates[0], {"relevant": True, "relevance_score": 9,
                         "one_line_why": "PAFACA reauth moves deadline",
                         "condition_tag": "A", "high_impact": True}),
        (candidates[1], {"relevant": False, "relevance_score": 0,
                         "one_line_why": "", "condition_tag": "background",
                         "high_impact": False}),
    ]:
        key = _llm.cache_key_for(
            model=_llm.MODEL_FAST,
            system=_relevance_system_prompt(),
            user=_relevance_user_prompt(contract, conditions, cand),
            schema=_relevance_schema(conditions),
        )
        (cache_dir / f"{key}.json").write_text(json.dumps({
            "request": {}, "response": payload,
        }))

    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    judged = judge_batch(
        contract=contract, conditions=conditions, candidates=candidates,
        cache_root=tmp_path / "cache",
    )
    assert len(judged) == 1
    assert judged[0]["feed_entry_id"] == "r1"
    assert judged[0]["one_line_why"] == "PAFACA reauth moves deadline"
    assert judged[0]["condition_tag"] == "A"


def _relevance_system_prompt() -> str:
    from build._relevance import SYSTEM_PROMPT
    return SYSTEM_PROMPT


def _relevance_user_prompt(contract, conditions, rec) -> str:
    from build._relevance import build_user_prompt
    return build_user_prompt(contract, conditions, rec)


def _relevance_schema(conditions) -> dict:
    from build._relevance import build_schema
    return build_schema(conditions)


def test_judge_falls_back_when_no_cache_and_no_key(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    from build._relevance import judge_batch

    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    contract = {"id": "x", "title": "t", "resolution_criteria": "r",
                "settlement_entities": ["E"]}
    conditions = [{"id": "A", "label": "x", "summary": "y"}]
    candidates = [
        {"feed_entry_id": "r1", "title": "X", "pub_date": "2025-01-01",
         "scores": {"urgency": {"score": 5}}, "entities": ["E"],
         "topic_name": "Topic-X", "link": "u"},
    ]
    judged = judge_batch(
        contract=contract, conditions=conditions, candidates=candidates,
        cache_root=tmp_path / "empty",
    )
    # Heuristic fallback keeps the record with a generated one_line_why
    assert len(judged) == 1
    assert "Topic-X" in judged[0]["one_line_why"] or "E" in judged[0]["one_line_why"]
    assert judged[0]["condition_tag"] == "background"
```

- [ ] **Step 2: Run tests, expect failure**

Run: `pytest tests/test_relevance.py -v`

Expected: Both fail with `ModuleNotFoundError`.

- [ ] **Step 3: Implement `build/_relevance.py`**

```python
"""Per-record relevance judgment via LLM.

For each candidate record (already entity-matched), ask the model whether
the record is relevant to the contract resolving YES/NO. Drop irrelevant,
tag each survivor with a condition_tag and a one_line_why. Sort by
relevance_score × urgency, keep top 20.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, cast

from build import _fields, _llm

SYSTEM_PROMPT = (
    "You are a regulatory analyst. Given a prediction-market contract and a "
    "single regulatory news record, decide if this record is relevant to "
    "whether the contract resolves YES or NO. Score relevance 0-10 (0 = "
    "off-topic, 10 = directly determinative). Return JSON matching the "
    "schema. one_line_why should be ≤160 chars and explain how this record "
    "moves resolution probability."
)


def build_user_prompt(
    contract: dict[str, Any],
    conditions: list[dict[str, str]],
    rec: dict[str, Any],
) -> str:
    return (
        f"Contract title: {contract.get('title', '')}\n"
        f"Resolution criteria: {contract.get('resolution_criteria', '')}\n"
        f"Conditions:\n"
        + "".join(f"  {c['id']}: {c['label']} — {c['summary']}\n" for c in conditions)
        + f"Settlement entities: {contract.get('settlement_entities', [])}\n\n"
        f"Record title: {rec.get('title', '')}\n"
        f"Record date: {_fields.pub_date_iso(rec)}\n"
        f"Record regulator: {_fields.regulator_display(rec)}\n"
        f"Record topic: {rec.get('topic_name', '')}\n"
        f"Record entities: {rec.get('entities', [])}"
    )


def build_schema(conditions: list[dict[str, str]]) -> dict[str, Any]:
    condition_ids = [c["id"] for c in conditions]
    return {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "relevant": {"type": "boolean"},
            "relevance_score": {"type": "integer", "minimum": 0, "maximum": 10},
            "one_line_why": {"type": "string"},
            "condition_tag": {"type": "string", "enum": condition_ids + ["background"]},
            "high_impact": {"type": "boolean"},
        },
        "required": ["relevant", "relevance_score", "one_line_why",
                     "condition_tag", "high_impact"],
    }


def _heuristic_judgment(rec: dict[str, Any]) -> dict[str, Any]:
    topic = (rec.get("topic_name") or "").strip()
    entities = rec.get("entities") or []
    matched = entities[0] if entities else ""
    parts = [p for p in (matched, topic) if p]
    why = " — ".join(parts) if parts else "Entity match"
    return {
        "relevant": True,
        "relevance_score": int(_fields.urgency_score(rec)),
        "one_line_why": why,
        "condition_tag": "background",
        "high_impact": _fields.urgency_score(rec) >= 7,
    }


def judge_batch(
    *,
    contract: dict[str, Any],
    conditions: list[dict[str, str]],
    candidates: list[dict[str, Any]],
    cache_root: Path | None = None,
    top_n: int = 20,
) -> list[dict[str, Any]]:
    """Score each candidate; drop irrelevant; sort by score × urgency; trim to top_n."""
    schema = build_schema(conditions)
    judged: list[dict[str, Any]] = []
    for rec in candidates:
        user = build_user_prompt(contract, conditions, rec)
        key = _llm.cache_key_for(
            model=_llm.MODEL_FAST, system=SYSTEM_PROMPT, user=user, schema=schema,
        )
        verdict = _llm.complete_json(
            purpose="relevance", cache_key=key, model=_llm.MODEL_FAST,
            system=SYSTEM_PROMPT, user=user, schema=schema, cache_root=cache_root,
        )
        if verdict is None:
            verdict = _heuristic_judgment(rec)
        if not verdict.get("relevant"):
            continue
        judged.append({
            **rec,
            "one_line_why": verdict["one_line_why"],
            "condition_tag": verdict["condition_tag"],
            "relevance_score": int(verdict["relevance_score"]),
            "high_impact": bool(verdict["high_impact"]),
        })

    def _rank(r: dict[str, Any]) -> float:
        return float(r["relevance_score"]) * float(_fields.urgency_score(r))

    judged.sort(key=_rank, reverse=True)
    judged = judged[:top_n]
    judged.sort(key=lambda r: _fields.pub_date_iso(r), reverse=True)
    return cast(list[dict[str, Any]], judged)
```

- [ ] **Step 4: Re-run tests, expect pass**

Run: `pytest tests/test_relevance.py -v`

Expected: 2 passed.

- [ ] **Step 5: mypy strict**

Run: `mypy --strict build/_relevance.py`

Expected: Success.

- [ ] **Step 6: Commit**

```bash
git add build/_relevance.py tests/test_relevance.py tests/fixtures/llm/relevance/
git commit -m "feat(γ): _relevance.py — LLM per-record relevance judgment"
```

---

## Task 8: Heat panel — LLM explainer + computed delta/percentile

**Files:**
- Modify: `build/_heat_panel.py` (append)
- Modify: `tests/test_heat_panel.py` (append)
- Create: `tests/fixtures/llm/heat_explainer/<contract_id>__<weekof>.json`

- [ ] **Step 1: Write failing test for `build()` orchestrator**

Append to `tests/test_heat_panel.py`:

```python
def test_build_panel_assembles_all_fields(
    tmp_path, monkeypatch,
) -> None:
    from datetime import date
    from build._heat_panel import build

    fixture_cache = tmp_path / "cache"
    explainer_dir = fixture_cache / "heat_explainer"
    explainer_dir.mkdir(parents=True)
    (explainer_dir / "ttb__2025W18.json").write_text(
        '{"request":{},"response":{'
        '"primary_drivers":["3 DoC enforcement bulletins","ByteDance shake-up"],'
        '"explainer":"Heat is elevated by Commerce activity rather than PAFACA."}}'
    )

    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    panel = build(
        contract_id="ttb",
        heat_value=56.0,
        heat_value_7d_ago=37.7,
        peers=[10.0, 20.0, 40.0, 56.0, 80.0],
        records=[
            {"pub_date": "2025-04-29", "scores": {"urgency": {"score": 8}},
             "title": "X"},
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
```

- [ ] **Step 2: Run, expect failure**

Run: `pytest tests/test_heat_panel.py::test_build_panel_assembles_all_fields -v`

Expected: Fails — `build` not defined.

- [ ] **Step 3: Append explainer + `build` to `build/_heat_panel.py`**

Add `Path` and `_llm` to the existing top-of-file imports so the new code uses normal imports:

```python
from pathlib import Path

from build import _fields, _llm
```

Then append at the bottom of the file:

```python
# --- LLM explainer + orchestrator ---


_EXPLAINER_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "primary_drivers": {
            "type": "array",
            "minItems": 1, "maxItems": 3,
            "items": {"type": "string"},
        },
        "explainer": {"type": "string"},
    },
    "required": ["primary_drivers", "explainer"],
}

_EXPLAINER_SYSTEM = (
    "You are a regulatory analyst. Given a contract's heat tier and its top "
    "recent matching records, write a one-sentence (≤220 char) explanation "
    "of what is driving heat at this level this week. Also list 1-3 short "
    "primary drivers (≤120 chars each). Return JSON matching the schema."
)


def _week_key(today: date) -> str:
    iso_year, iso_week, _ = today.isocalendar()
    return f"{iso_year}W{iso_week:02d}"


def build(
    *,
    contract_id: str,
    heat_value: float,
    heat_value_7d_ago: float,
    peers: list[float],
    records: list[dict[str, Any]],
    today: date,
    cache_root: Path | None = None,
) -> dict[str, Any]:
    """Assemble a heat_panel dict for the contract page + dashboard tier."""
    tier_label = tier_for(heat_value)
    delta_7d = round(heat_value - heat_value_7d_ago, 2)
    percentile = peer_percentile(heat_value, peers)
    sparkline = urgency_weighted_sparkline(records, today=today, days=14)

    top_for_explainer = sorted(
        records, key=lambda r: _fields.pub_date_iso(r), reverse=True,
    )[:10]
    user = (
        f"Tier: {tier_label}\n"
        f"Heat: {heat_value}\n"
        f"Delta_7d: {delta_7d}\n"
        f"Top records:\n"
        + "".join(
            f"- {_fields.pub_date_iso(r)} {r.get('title', '')[:80]}\n"
            for r in top_for_explainer
        )
    )
    week_key = _week_key(today)
    response = _llm.complete_json(
        purpose="heat_explainer",
        cache_key=f"{contract_id}__{week_key}",
        model=_llm.MODEL_FAST,
        system=_EXPLAINER_SYSTEM,
        user=user,
        schema=_EXPLAINER_SCHEMA,
        cache_root=cache_root,
    )
    if response is None:
        response = {
            "primary_drivers": [f"{len(records)} matching events in window"],
            "explainer": (
                f"Heat reflects {len(records)} matching events in the last "
                f"{14 if records else 90} days."
            ),
        }

    return {
        "value": heat_value,
        "tier": tier_label,
        "delta_7d": delta_7d,
        "peer_percentile": percentile,
        "urgency_weighted_sparkline": sparkline,
        "primary_drivers": response["primary_drivers"],
        "explainer": response["explainer"],
    }
```

- [ ] **Step 4: Run tests, expect pass**

Run: `pytest tests/test_heat_panel.py -v`

Expected: All passed.

- [ ] **Step 5: mypy strict**

Run: `mypy --strict build/_heat_panel.py`

Expected: Success.

- [ ] **Step 6: Commit**

```bash
git add build/_heat_panel.py tests/test_heat_panel.py tests/fixtures/llm/heat_explainer/
git commit -m "feat(γ): heat panel orchestrator with LLM explainer"
```

---

## Task 9: Implement `_narrative.py` — 2-3 sentence storyline

**Files:**
- Create: `build/_narrative.py`
- Create: `tests/test_narrative.py`
- Create: `tests/fixtures/llm/narrative/ttb__<hash>.json`

- [ ] **Step 1: Write failing tests**

Create `tests/test_narrative.py`:

```python
"""Tests for build/_narrative.py."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from build import _llm


def test_summarize_returns_cached_narrative(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    from build._narrative import summarize, _timeline_hash

    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    timeline = [{"pub_date": "2025-03-01", "title": "X", "condition_tag": "A",
                 "one_line_why": "Y"}]
    contract = {"id": "ttb", "title": "T", "kind": "retrospective"}
    h = _timeline_hash(timeline)
    cache_dir = tmp_path / "narrative"
    cache_dir.mkdir(parents=True)
    (cache_dir / f"ttb__{h}.json").write_text(json.dumps({
        "request": {},
        "response": {"text": "Between July 2024 and April 2025, the contract..."},
    }))
    result = summarize(contract=contract, timeline=timeline,
                       cache_root=tmp_path)
    assert "Between July" in result


def test_summarize_returns_empty_when_no_cache_and_no_key(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    from build._narrative import summarize

    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    result = summarize(
        contract={"id": "x", "title": "t", "kind": "active"},
        timeline=[], cache_root=tmp_path / "empty",
    )
    assert result == ""
```

- [ ] **Step 2: Run, expect failure**

Run: `pytest tests/test_narrative.py -v`

Expected: `ModuleNotFoundError`.

- [ ] **Step 3: Implement `build/_narrative.py`**

```python
"""2-3 sentence storyline summary of a contract's enriched timeline."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from build import _llm

_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "properties": {"text": {"type": "string"}},
    "required": ["text"],
}

_SYSTEM = (
    "You are a regulatory analyst. Write a 2-3 sentence storyline summary "
    "(≤500 chars total) of the regulatory pressure history for this "
    "prediction-market contract. For 'retrospective' kind, write past tense "
    "and reference the actual resolution. For 'active' kind, write present "
    "tense and note what's still pending. Return JSON {text: ...}."
)


def _timeline_hash(timeline: list[dict[str, Any]]) -> str:
    payload = json.dumps([
        {"d": ev.get("pub_date", ""), "t": ev.get("title", ""),
         "c": ev.get("condition_tag", "")}
        for ev in timeline
    ], sort_keys=True)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]


def summarize(
    *,
    contract: dict[str, Any],
    timeline: list[dict[str, Any]],
    cache_root: Path | None = None,
) -> str:
    """Return narrative text. Empty string if LLM unavailable + cache miss."""
    if not timeline:
        return ""
    h = _timeline_hash(timeline)
    user = (
        f"Contract: {contract.get('title', '')}\n"
        f"Kind: {contract.get('kind', '')}\n"
        f"Timeline ({len(timeline)} events):\n"
        + "".join(
            f"- {ev.get('pub_date', '')} [{ev.get('condition_tag', '?')}] "
            f"{ev.get('title', '')} — {ev.get('one_line_why', '')}\n"
            for ev in timeline
        )
    )
    response = _llm.complete_json(
        purpose="narrative",
        cache_key=f"{contract['id']}__{h}",
        model=_llm.MODEL_DEEP,
        system=_SYSTEM,
        user=user,
        schema=_SCHEMA,
        cache_root=cache_root,
    )
    if response is None:
        return ""
    return str(response.get("text", ""))
```

- [ ] **Step 4: Re-run tests, expect pass**

Run: `pytest tests/test_narrative.py -v`

Expected: 2 passed.

- [ ] **Step 5: mypy strict**

Run: `mypy --strict build/_narrative.py`

Expected: Success.

- [ ] **Step 6: Commit**

```bash
git add build/_narrative.py tests/test_narrative.py tests/fixtures/llm/narrative/
git commit -m "feat(γ): _narrative.py — 2-3 sentence storyline summary"
```

---

## Task 10: Implement `gamma_contract_enrich.py` orchestrator

**Files:**
- Create: `build/gamma_contract_enrich.py`
- Create: `tests/test_gamma_contract_enrich.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_gamma_contract_enrich.py`:

```python
"""Tests for build/gamma_contract_enrich.py."""
from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import pytest

FIXTURE_CACHE = Path(__file__).parent / "fixtures" / "llm"


def test_enrich_adds_all_required_fields(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    from build.gamma_contract_enrich import enrich_slice

    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    slice_doc = {
        "scene": {},
        "contract": {
            "id": "ttb", "kind": "retrospective", "platform": "kalshi",
            "title": "TikTok ban?",
            "resolution_criteria": "Resolves YES if TikTok unavailable...",
            "listed_at": "2024-04-24", "resolved_at": "2025-04-30",
            "settlement_entities": [{"name": "TikTok", "role": "company"}],
            "heat": 25.0,
            "heat_history": [0] * 14,
        },
        "timeline": [
            {"pub_date": "2025-03-01", "title": "PAFACA reauth",
             "regulator": "Congress", "url": "u", "urgency": 8, "impact": 7,
             "matched_entity": "TikTok", "carver_feed_entry_id": "f1",
             "entities": ["TikTok"], "topic_name": "Foreign investment",
             "scores": {"urgency": {"score": 8}}},
        ],
        "open_tickets": [],
    }
    corpus = []  # heat_panel uses timeline records directly

    enriched = enrich_slice(
        slice_doc=slice_doc, corpus=corpus, peer_heats=[10.0, 25.0, 40.0],
        today=date(2026, 5, 20), cache_root=FIXTURE_CACHE,
    )
    assert "conditions" in enriched["contract"]
    assert "narrative" in enriched["contract"]
    assert "heat_panel" in enriched
    assert enriched["heat_panel"]["tier"] in ("dormant", "watch", "active", "critical")
    assert all("one_line_why" in ev for ev in enriched["timeline"])
    assert all("condition_tag" in ev for ev in enriched["timeline"])
```

- [ ] **Step 2: Run, expect failure**

Run: `pytest tests/test_gamma_contract_enrich.py -v`

Expected: `ModuleNotFoundError`.

- [ ] **Step 3: Implement `build/gamma_contract_enrich.py`**

```python
"""γ contract slice enrichment orchestrator.

Mutates a slice JSON in place (or returns a new one) with the four
enrichment outputs: conditions, per-event one_line_why + condition_tag,
heat_panel, and narrative.

Designed to be safe under graceful degradation — every call has a fallback,
so a build without OPENAI_API_KEY still produces a renderable slice.
"""
from __future__ import annotations

import json
import sys
from concurrent.futures import ThreadPoolExecutor
from datetime import date, timedelta
from pathlib import Path
from typing import Any, cast

_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from build import _heat, _heat_panel, _llm, _narrative, _relevance, _thesis  # noqa: E402


def enrich_slice(
    *,
    slice_doc: dict[str, Any],
    corpus: list[dict[str, Any]],
    peer_heats: list[float],
    today: date,
    cache_root: Path | None = None,
) -> dict[str, Any]:
    contract = slice_doc["contract"]
    cid = contract["id"]
    settle = [e["name"] for e in contract.get("settlement_entities") or []]

    # 1. Thesis decomposition (1 LLM call, cached by contract id).
    conditions = _thesis.decompose(
        contract_id=cid,
        title=contract.get("title", ""),
        resolution_criteria=contract.get("resolution_criteria", ""),
        settlement_entities=settle,
        cache_root=cache_root,
    )
    contract["conditions"] = conditions

    # 2. Per-record relevance — pass the already-windowed timeline as candidates.
    contract_for_llm: dict[str, Any] = {
        "id": cid,
        "title": contract.get("title", ""),
        "resolution_criteria": contract.get("resolution_criteria", ""),
        "settlement_entities": settle,
    }
    candidates = _hydrate_candidates(slice_doc.get("timeline") or [], corpus)
    judged = _relevance.judge_batch(
        contract=contract_for_llm, conditions=conditions, candidates=candidates,
        cache_root=cache_root,
    )
    slice_doc["timeline"] = _project_timeline_fields(judged)

    # 3. Heat panel (uses judged records for sparkline + explainer).
    heat_7d_ago = _heat.heat_score(
        {"settlement_entities": settle}, corpus, today=today - timedelta(days=7),
    )
    slice_doc["heat_panel"] = _heat_panel.build(
        contract_id=cid,
        heat_value=float(contract.get("heat", 0.0)),
        heat_value_7d_ago=heat_7d_ago,
        peers=peer_heats,
        records=judged,
        today=today,
        cache_root=cache_root,
    )

    # 4. Narrative (uses judged timeline so the LLM sees one_line_why context).
    contract["narrative"] = _narrative.summarize(
        contract=contract, timeline=slice_doc["timeline"], cache_root=cache_root,
    )

    return slice_doc


def _hydrate_candidates(
    timeline: list[dict[str, Any]],
    corpus: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Look up each timeline entry's original corpus record by feed_entry_id."""
    by_id = {r.get("feed_entry_id"): r for r in corpus if r.get("feed_entry_id")}
    out: list[dict[str, Any]] = []
    for ev in timeline:
        rec = by_id.get(ev.get("carver_feed_entry_id"))
        if rec:
            out.append(rec)
    return out


def _project_timeline_fields(judged: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Map judged corpus records back to the timeline event shape."""
    from build import _fields
    out: list[dict[str, Any]] = []
    for rec in judged:
        out.append({
            "pub_date": _fields.pub_date_iso(rec),
            "title": rec.get("title") or "",
            "regulator": _fields.regulator_display(rec),
            "url": rec.get("link") or "",
            "urgency": _fields.urgency_score(rec),
            "impact": _fields.impact_score(rec),
            "matched_entity": rec.get("matched_entity", ""),
            "carver_feed_entry_id": rec.get("feed_entry_id") or "",
            "one_line_why": rec.get("one_line_why", ""),
            "condition_tag": rec.get("condition_tag", "background"),
            "relevance_score": rec.get("relevance_score", 0),
            "high_impact": rec.get("high_impact", False),
        })
    return out


def enrich_all(
    *,
    slice_dir: Path,
    corpus: list[dict[str, Any]],
    peer_heats: list[float],
    today: date,
    cache_root: Path | None = None,
    max_workers: int = 4,
) -> list[Path]:
    """Enrich every slice JSON under slice_dir in parallel."""
    slice_paths = sorted(slice_dir.glob("*.json"))

    def _process(p: Path) -> Path:
        doc = json.loads(p.read_text())
        enriched = enrich_slice(
            slice_doc=doc, corpus=corpus, peer_heats=peer_heats,
            today=today, cache_root=cache_root,
        )
        p.write_text(json.dumps(enriched, indent=2))
        return p

    with ThreadPoolExecutor(max_workers=max_workers) as ex:
        return list(ex.map(_process, slice_paths))


if __name__ == "__main__":
    print(f"is_available: {_llm.is_available()}")
```

- [ ] **Step 4: Re-run tests, expect pass**

Run: `pytest tests/test_gamma_contract_enrich.py -v`

Expected: Pass.

- [ ] **Step 5: mypy strict**

Run: `mypy --strict build/gamma_contract_enrich.py`

Expected: Success.

- [ ] **Step 6: Commit**

```bash
git add build/gamma_contract_enrich.py tests/test_gamma_contract_enrich.py
git commit -m "feat(γ): gamma_contract_enrich.py — orchestrate all enrichment"
```

---

## Task 11: Wire enrichment into `generate_slices.py`

**Files:**
- Modify: `build/generate_slices.py`
- Modify: `tests/test_generate_slices.py`

- [ ] **Step 1: Inspect current generate_slices.py to find γ contract step**

```bash
grep -n "gamma_contract\|gamma_dashboard\|gamma_scan" build/generate_slices.py
```

- [ ] **Step 2: Add enrichment call after gamma_contract.generate**

In `build/generate_slices.py`, after the γ contract generation block and before the next slice step, add:

```python
    # γ contract intelligence enrichment — adds conditions, narrative,
    # heat_panel, and per-event LLM relevance fields. Cached responses
    # under build/_cache/llm/ keep this near-free in CI.
    from build import gamma_contract_enrich

    # Peer heats for percentile = all dashboard rows' current heat.
    dashboard_path = PAGE_DATA / "gamma" / "dashboard.json"
    if dashboard_path.exists():
        dashboard = json.loads(dashboard_path.read_text())
        peer_heats = [row["heat"] for row in dashboard.get("rows", [])]
    else:
        peer_heats = []

    contracts_dir = PAGE_DATA / "gamma" / "contracts"
    if contracts_dir.exists():
        gamma_contract_enrich.enrich_all(
            slice_dir=contracts_dir,
            corpus=gamma_corpus,
            peer_heats=peer_heats,
            today=today,
        )
        print(f"  enriched {len(list(contracts_dir.glob('*.json')))} γ contract slices")
```

(Use the existing names for `PAGE_DATA`, `gamma_corpus`, and `today` already defined in the file. If they differ, match the local names.)

- [ ] **Step 3: Update existing slice test to expect enrichment fields**

If `tests/test_generate_slices.py` asserts on γ contract slice contents, add `assert "conditions" in contract` and `assert "heat_panel" in slice_doc` after the contract slice load.

- [ ] **Step 4: Run full slice generator**

```bash
python3 -m build.generate_slices
```

Expected: prints `enriched 6 γ contract slices` (or however many slices exist).

- [ ] **Step 5: Run slice-generator tests**

Run: `pytest tests/test_generate_slices.py -v`

Expected: pass.

- [ ] **Step 6: Commit**

```bash
git add build/generate_slices.py tests/test_generate_slices.py
git commit -m "feat(γ): wire contract intelligence enrichment into slice pipeline"
```

---

## Task 12: Expand γ dashboard to all 6 (retros + tier dots)

**Files:**
- Modify: `build/gamma_dashboard.py`
- Modify: `tests/test_gamma_dashboard.py`

- [ ] **Step 1: Write failing tests**

Add to `tests/test_gamma_dashboard.py`:

```python
def test_dashboard_includes_retrospective_rows_with_resolution_window_heat(
    tmp_path: Path,
) -> None:
    """Retrospective contracts appear as rows with heat scored against their life window."""
    from datetime import date
    from build.gamma_dashboard import generate

    corpus = tmp_path / "artifacts.jsonl"
    gamma_cur = tmp_path / "gamma-curation.yml"
    kalshi_yml = tmp_path / "kalshi.yml"
    poly_yml = tmp_path / "poly.yml"
    out_path = tmp_path / "dashboard.json"
    retros_root = tmp_path / "retros"
    (retros_root / "kalshi" / "contracts").mkdir(parents=True)
    _write_retro(retros_root / "kalshi" / "contracts" / "ttb.yml",
                 id="ttb", title="TikTok ban",
                 settlement_entities=["TikTok"],
                 listed_at="2024-04-24", resolved_at="2025-04-30",
                 status="resolved")
    _write_corpus(corpus, [
        make_row(entities=["TikTok"], title="In life window",
                 pub_date="2025-04-20",
                 scores={"urgency": {"score": 8, "label": "high"},
                         "impact": {"score": 7, "label": "medium"},
                         "relevance": {"score": 7, "label": "medium"}}),
        make_row(entities=["FOMC"], title="Active hit",
                 pub_date="2026-05-15"),
    ])
    _write_gamma_curation(gamma_cur,
        picks=[
            {"id": "k1", "platform": "kalshi", "kind": "active"},
            {"id": "ttb", "platform": "kalshi", "kind": "retrospective"},
        ])
    _write_kalshi_contracts(kalshi_yml, [{
        "id": "k1",
        "cached": {"title": "Active", "ticker": "K1", "status": "active",
                   "listed_at": "2026-01-01", "expires_at": "2026-12-31",
                   "resolution_criteria": "r", "settlement_entities": ["FOMC"]},
    }])
    poly_yml.write_text("schema_version: 1\npicks: []\n")

    result = generate(corpus_path=corpus, gamma_curation_path=gamma_cur,
                      kalshi_contracts_path=kalshi_yml,
                      polymarket_contracts_path=poly_yml,
                      out_path=out_path, today=date(2026, 5, 20),
                      retros_root=retros_root)
    rows = result["rows"]
    actives = [r for r in rows if r["kind"] == "active"]
    retros = [r for r in rows if r["kind"] == "retrospective"]
    assert len(actives) == 1
    assert len(retros) == 1
    assert retros[0]["status"] == "resolved"
    assert retros[0]["heat_window_label"] == "at resolution"
    assert actives[0]["heat_window_label"] == "current"
    assert retros[0]["heat"] > 0  # in-life-window record drives heat
    for row in rows:
        assert row["tier"] in ("dormant", "watch", "active", "critical")


def test_dashboard_tier_consistent_with_heat_panel(tmp_path: Path) -> None:
    """Same tier_for function used for dashboard and contract detail panel."""
    from datetime import date
    from build._heat_panel import tier_for
    from build.gamma_dashboard import generate

    corpus = tmp_path / "artifacts.jsonl"
    gamma_cur = tmp_path / "gamma-curation.yml"
    kalshi_yml = tmp_path / "kalshi.yml"
    poly_yml = tmp_path / "poly.yml"
    out_path = tmp_path / "dashboard.json"
    retros_root = tmp_path / "retros"
    retros_root.mkdir()
    _write_corpus(corpus, [make_row(entities=["FOMC"], pub_date="2026-05-19")])
    _write_gamma_curation(gamma_cur,
        picks=[{"id": "k1", "platform": "kalshi", "kind": "active"}])
    _write_kalshi_contracts(kalshi_yml, [{
        "id": "k1",
        "cached": {"title": "T", "ticker": "K1", "status": "active",
                   "listed_at": "2026-01-01", "expires_at": "2026-12-31",
                   "resolution_criteria": "r", "settlement_entities": ["FOMC"]},
    }])
    poly_yml.write_text("schema_version: 1\npicks: []\n")
    result = generate(corpus_path=corpus, gamma_curation_path=gamma_cur,
                      kalshi_contracts_path=kalshi_yml,
                      polymarket_contracts_path=poly_yml,
                      out_path=out_path, today=date(2026, 5, 20),
                      retros_root=retros_root)
    for row in result["rows"]:
        assert row["tier"] == tier_for(row["heat"])
```

Add the `_write_retro` helper at the top of the file (same as in Task 5).

- [ ] **Step 2: Run tests, expect failure**

Run: `pytest tests/test_gamma_dashboard.py -v`

Expected: New tests fail.

- [ ] **Step 3: Modify `build/gamma_dashboard.py` — load retros + tier**

In `build/gamma_dashboard.py`, after the active-row build loops, add a retro pass that reads `contract_detail_picks` entries with `kind: retrospective` and loads the corresponding YAML:

```python
def _build_retro_row(
    pick: dict[str, Any], retros_root: Path, corpus: list[dict[str, Any]],
    today: date, open_tickets_count: int,
) -> dict[str, Any] | None:
    """Build a dashboard row for a retrospective contract.

    Heat is scored against [resolved_at - 90d, resolved_at] — the
    'at resolution' window — rather than current corpus.
    """
    from datetime import timedelta
    p = retros_root / pick["platform"] / "contracts" / f"{pick['id']}.yml"
    if not p.exists():
        return None
    retro = cast(dict[str, Any], yaml.safe_load(p.read_text()))
    settle = retro["settlement_entities"]
    resolved = date.fromisoformat(retro["resolved_at"][:10])
    # Score heat as if "today" were resolved_at.
    heat_now = _heat.heat_score(
        {"settlement_entities": settle}, corpus, today=resolved,
    )
    heat_7d = _heat.heat_score(
        {"settlement_entities": settle}, corpus, today=resolved - timedelta(days=7),
    )
    sparkline = _heat.sparkline_buckets(
        {"settlement_entities": settle}, corpus, today=resolved, days=14,
    )
    match_count = _heat.matching_event_count(
        {"settlement_entities": settle}, corpus, today=resolved,
    )
    return {
        "id": pick["id"],
        "platform": pick["platform"],
        "title": retro["title"],
        "status": retro.get("status", "resolved"),
        "settlement_entities": settle,
        "heat": heat_now,
        "heat_delta_7d": round(heat_now - heat_7d, 2),
        "sparkline": sparkline,
        "matching_event_count": match_count,
        "last_event_pub_date": "",  # not surfaced for retros
        "open_tickets_count": open_tickets_count,
        "is_stale": False,
        "detail_href": f"contracts/{pick['id']}/",
        "heat_window_label": "at resolution",
        "tier": _heat_panel.tier_for(heat_now),
        "kind": "retrospective",
    }
```

Above the row-building, import `_heat_panel`:

```python
from build import _fields, _heat, _heat_panel
```

In `generate()`, after the active rows are built:

```python
    for pick in gamma.get("contract_detail_picks") or []:
        if pick.get("kind") != "retrospective":
            continue
        row = _build_retro_row(
            pick, retros_root, corpus, today,
            tickets_by_contract.get(pick["id"], 0),
        )
        if row:
            rows.append(row)
```

Add `retros_root` to `generate()`'s parameters:

```python
def generate(
    corpus_path: Path,
    gamma_curation_path: Path,
    kalshi_contracts_path: Path,
    polymarket_contracts_path: Path,
    out_path: Path,
    today: date | None = None,
    retros_root: Path | None = None,  # NEW
) -> dict[str, Any]:
    ...
    if retros_root is None:
        retros_root = Path(__file__).resolve().parent.parent / "data" / "platforms"
```

For active rows (existing `_build_contract_row`), at the end of the dict, add:

```python
        "heat_window_label": "current",
        "tier": _heat_panel.tier_for(heat_now),
        "kind": "active",
    }
```

In the sort step, change to two-section sort:

```python
    active = [r for r in rows if r["kind"] == "active"]
    retro = [r for r in rows if r["kind"] == "retrospective"]
    active.sort(key=lambda r: r["heat"], reverse=True)
    retro.sort(key=lambda r: r["id"], reverse=True)  # crude proxy for resolved_at desc
    rows = active + retro
```

For "rising," only use active rows: `rising = sorted(active, key=lambda r: r["heat_delta_7d"], reverse=True)[:2]`.

Update the call site at the bottom of the file (the `if __name__ == "__main__":` block) to pass `retros_root`.

- [ ] **Step 4: Re-run tests, expect pass**

Run: `pytest tests/test_gamma_dashboard.py -v`

Expected: pass.

- [ ] **Step 5: mypy + ruff**

Run: `mypy --strict build/gamma_dashboard.py && ruff check build/gamma_dashboard.py`

Expected: clean.

- [ ] **Step 6: Commit**

```bash
git add build/gamma_dashboard.py tests/test_gamma_dashboard.py
git commit -m "feat(γ): dashboard shows all 6 contracts with active/resolved sections"
```

---

## Task 13: Dashboard template — divider row + tier dot + heat window label

**Files:**
- Modify: `build/templates/gamma/dashboard.html`
- Modify: `build/templates/gamma/_components/contract_row.html`
- Modify: `tests/test_gamma_templates.py`

- [ ] **Step 1: Update `contract_row.html` heat cell**

Replace the heat `<td>` in `build/templates/gamma/_components/contract_row.html` (lines 2-13) with:

```html
  <td class="px-3 py-2 align-top">
    <div class="flex items-center gap-2">
      {% set tier_color = {
        'dormant': 'bg-slate-400',
        'watch':    'bg-sky-600',
        'active':   'bg-amber-600',
        'critical': 'bg-rose-600',
      }[row.tier] %}
      <span class="inline-block w-2 h-2 rounded-full {{ tier_color }}"
            title="{{ row.tier }}"></span>
      <span class="text-xl font-bold tabular-nums">{{ row.heat|round(0)|int }}</span>
      {% set values = row.sparkline %}
      {% include "gamma/_components/sparkline.html" %}
    </div>
    <div class="text-[10px] uppercase tracking-wider text-slate-400 mt-0.5">
      {{ row.heat_window_label }}
    </div>
    {% if row.heat_delta_7d != 0 %}
    <div class="text-xs {{ 'text-rose-600' if row.heat_delta_7d > 0 else 'text-slate-500' }}">
      {{ '+' if row.heat_delta_7d > 0 }}{{ row.heat_delta_7d|round(1) }} / 7d
    </div>
    {% endif %}
  </td>
```

- [ ] **Step 2: Add divider row to dashboard.html**

In `build/templates/gamma/dashboard.html`, replace the rows loop with two sections:

```jinja
{% set active_rows = rows | selectattr('kind', 'equalto', 'active') | list %}
{% set retro_rows  = rows | selectattr('kind', 'equalto', 'retrospective') | list %}

{% for row in active_rows %}
  {% include "gamma/_components/contract_row.html" %}
{% endfor %}

{% if retro_rows %}
<tr class="bg-slate-50 border-y border-slate-200">
  <td colspan="6" class="px-3 py-2 text-xs uppercase tracking-[0.18em] text-slate-500 font-semibold">
    Resolved (retrospective)
  </td>
</tr>
{% endif %}

{% for row in retro_rows %}
  {% include "gamma/_components/contract_row.html" %}
{% endfor %}
```

Adjust `colspan="6"` to match the actual number of `<th>` columns in the file.

- [ ] **Step 3: Update template tests**

Add to `tests/test_gamma_templates.py`:

```python
def test_dashboard_renders_active_resolved_sections() -> None:
    from jinja2 import Environment, FileSystemLoader, select_autoescape

    env = Environment(
        loader=FileSystemLoader("build/templates"),
        autoescape=select_autoescape(["html"]),
    )
    template = env.get_template("gamma/dashboard.html")
    rows = [
        {"id": "a", "title": "Active C", "kind": "active", "status": "active",
         "heat": 45.0, "heat_delta_7d": 2.0, "tier": "active",
         "heat_window_label": "current", "sparkline": [0]*14,
         "settlement_entities": ["FOMC"], "open_tickets_count": 0,
         "is_stale": False, "last_event_pub_date": "2026-05-15",
         "detail_href": "contracts/a/", "matching_event_count": 3},
        {"id": "r", "title": "Retro C", "kind": "retrospective", "status": "resolved",
         "heat": 60.0, "heat_delta_7d": 0.0, "tier": "active",
         "heat_window_label": "at resolution", "sparkline": [0]*14,
         "settlement_entities": ["TikTok"], "open_tickets_count": 0,
         "is_stale": False, "last_event_pub_date": "",
         "detail_href": "contracts/r/", "matching_event_count": 8},
    ]
    html = template.render(scene={"back_label": "← back", "back_href": "../"},
                           rows=rows, rising=[], base_url="")
    assert "Resolved (retrospective)" in html
    assert "at resolution" in html
    assert "current" in html
    assert "Active C" in html and "Retro C" in html
```

- [ ] **Step 4: Run template tests**

Run: `pytest tests/test_gamma_templates.py -v`

Expected: pass.

- [ ] **Step 5: Commit**

```bash
git add build/templates/gamma/dashboard.html build/templates/gamma/_components/contract_row.html tests/test_gamma_templates.py
git commit -m "feat(γ): dashboard divider + tier dot + heat window label"
```

---

## Task 14: Contract detail template — vertical timeline + heat panel + narrative + legend + Alpine filter

**Files:**
- Modify: `build/templates/gamma/contract_detail.html` (largely a rewrite)
- Modify: `tests/test_gamma_templates.py`

- [ ] **Step 1: Replace contract_detail.html**

Replace `build/templates/gamma/contract_detail.html` with the structure below. (Keep the existing header, retrospective aside, and resolution-criteria sections — only the heat block, timeline block, and add narrative + legend + alpine wrapper.)

```html
{% extends "base.html" %}
{% block title %}{{ contract.title }} — Pred-Oracle{% endblock %}
{% block content %}
<nav class="mb-4 text-sm">
  <a href="{{ base_url|default('') }}gamma/dashboard/" class="text-slate-500 hover:text-slate-900">{{ scene.back_label }}</a>
</nav>

<header class="mb-6">
  <div class="flex items-baseline gap-2 mb-1">
    <span class="text-xs uppercase tracking-[0.18em] text-blue-600 font-semibold">Listed contract</span>
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
  <div class="text-xs text-slate-500 mt-1">{% if contract.listed_at %}listed {{ contract.listed_at[:10] }}{% endif %}{% if contract.resolved_at %} · resolved {{ contract.resolved_at[:10] }}{% elif contract.expires_at %} · expires {{ contract.expires_at[:10] }}{% endif %}</div>
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

    {% if contract.conditions %}
    <section class="mb-6">
      <h2 class="text-sm font-semibold uppercase tracking-wider text-slate-500 mb-2">Conditions for YES</h2>
      <ol class="space-y-2 text-sm">
        {% for c in contract.conditions %}
        <li class="flex gap-3">
          {% set cond_color = {'A':'bg-indigo-600','B':'bg-emerald-600','C':'bg-violet-600'}[c.id] %}
          <span class="inline-flex items-center justify-center w-6 h-6 rounded-full {{ cond_color }} text-white text-xs font-bold flex-shrink-0">{{ c.id }}</span>
          <div>
            <div class="font-medium text-slate-900">{{ c.label }}</div>
            <div class="text-slate-600">{{ c.summary }}</div>
          </div>
        </li>
        {% endfor %}
      </ol>
    </section>
    {% endif %}

    <section class="mb-6">
      <h2 class="text-sm font-semibold uppercase tracking-wider text-slate-500 mb-2">Settlement entities</h2>
      <div class="flex flex-wrap gap-1.5">
        {% for entity in contract.settlement_entities %}
          {% include "gamma/_components/entity_chip.html" %}
        {% endfor %}
      </div>
    </section>

    {% if contract.narrative %}
    <section class="mb-6">
      <blockquote class="border-l-4 border-blue-400 bg-blue-50/40 px-4 py-3 text-sm text-slate-800 italic">
        {{ contract.narrative }}
      </blockquote>
    </section>
    {% endif %}

    <section x-data="{ filter: 'all' }">
      <div class="flex items-center justify-between mb-3">
        <h2 class="text-sm font-semibold uppercase tracking-wider text-slate-500">Regulatory timeline ({{ timeline|length }})</h2>
        {% if contract.conditions and contract.conditions|length > 1 %}
        <div role="tablist" class="flex gap-1 text-xs">
          <button @click="filter='all'" :class="filter==='all' ? 'bg-slate-800 text-white' : 'bg-slate-100 text-slate-700'" class="px-2 py-1 rounded">All</button>
          {% for c in contract.conditions %}
          <button @click="filter='{{ c.id }}'" :class="filter==='{{ c.id }}' ? 'bg-slate-800 text-white' : 'bg-slate-100 text-slate-700'" class="px-2 py-1 rounded">{{ c.id }} only</button>
          {% endfor %}
        </div>
        {% endif %}
      </div>

      {% if timeline %}
      <div class="mb-4 text-xs text-slate-500 flex flex-wrap gap-x-4 gap-y-1">
        <span class="font-medium">Condition:</span>
        {% for c in contract.conditions %}
          {% set cond_color = {'A':'bg-indigo-600','B':'bg-emerald-600','C':'bg-violet-600'}[c.id] %}
          <span class="inline-flex items-center gap-1"><span class="w-2 h-2 rounded-full {{ cond_color }}"></span>{{ c.id }}: {{ c.label }}</span>
        {% endfor %}
        <span class="inline-flex items-center gap-1"><span class="w-2 h-2 rounded-full bg-slate-400"></span>Background</span>
        <span class="ml-4 font-medium">Urgency:</span>
        <span class="inline-flex items-center gap-1"><span class="w-2 h-2 rounded-full bg-slate-300 ring-1 ring-slate-500"></span>low</span>
        <span class="inline-flex items-center gap-1"><span class="w-2 h-2 rounded-full bg-slate-300 ring-2 ring-slate-500"></span>med</span>
        <span class="inline-flex items-center gap-1"><span class="w-2 h-2 rounded-full bg-slate-300 ring-[3px] ring-slate-500"></span>high</span>
      </div>

      <ol class="relative">
        {% for ev in timeline %}
        {% set dot_color = {'A':'bg-indigo-600','B':'bg-emerald-600','C':'bg-violet-600','background':'bg-slate-400'}[ev.condition_tag|default('background')] %}
        {% set ring = 'ring-1' if ev.urgency < 5 else ('ring-2' if ev.urgency < 7 else 'ring-[3px]') %}
        <li class="grid grid-cols-[6.5rem_2rem_1fr] items-start transition-opacity"
            :class="(filter !== 'all' && '{{ ev.condition_tag|default('background') }}' !== filter) && 'opacity-30'">
          <time class="text-right pr-3 pt-1">
            <span class="block text-sm font-semibold tabular-nums text-slate-900">{{ ev.pub_date[:10] }}</span>
          </time>
          <div class="flex justify-center pt-2 relative">
            <span class="absolute top-0 bottom-0 left-1/2 w-px bg-slate-200 -z-10"></span>
            <span class="w-3 h-3 rounded-full {{ dot_color }} {{ ring }} ring-slate-300"></span>
          </div>
          <article class="pb-6 pl-2">
            <a href="{{ ev.url }}" target="_blank" rel="noopener noreferrer" class="font-medium text-slate-900 hover:text-blue-700">{{ ev.title }}</a>
            {% if ev.one_line_why %}
            <p class="text-sm text-slate-700 mt-1">{{ ev.one_line_why }}</p>
            {% endif %}
            <p class="text-xs text-slate-500 mt-1">{{ ev.regulator }} · matched <span class="font-medium">{{ ev.matched_entity }}</span> · urg {{ ev.urgency|round(0)|int }}</p>
          </article>
        </li>
        {% endfor %}
      </ol>
      {% else %}
      <p class="text-sm text-slate-500 italic">No matching Carver events found in window for this contract's settlement entities.</p>
      {% endif %}
    </section>
  </article>

  <aside class="lg:col-span-2 space-y-4">
    <div class="border border-slate-200 rounded-lg p-4 bg-slate-50/50">
      <h2 class="text-sm font-semibold uppercase tracking-wider text-slate-500 mb-2">Heat</h2>
      {% set tier_color = {'dormant':'text-slate-500','watch':'text-sky-700','active':'text-amber-700','critical':'text-rose-700'}[heat_panel.tier] %}
      <div class="text-3xl font-bold uppercase tracking-wide {{ tier_color }} leading-none">{{ heat_panel.tier }}</div>
      <div class="text-sm text-slate-600 mt-1 tabular-nums">
        {{ heat_panel.value|round(0)|int }}
        {% if heat_panel.delta_7d != 0 %} · {{ '+' if heat_panel.delta_7d > 0 }}{{ heat_panel.delta_7d|round(1) }} / 7d{% endif %}
        {% if heat_panel.peer_percentile %} · top {{ 100 - heat_panel.peer_percentile }}%{% endif %}
      </div>
      {% if heat_panel.explainer %}
      <p class="text-sm text-slate-700 mt-3">{{ heat_panel.explainer }}</p>
      {% endif %}
      <div class="mt-4">
        {% set values = heat_panel.urgency_weighted_sparkline %}
        {% include "gamma/_components/sparkline.html" %}
        <div class="flex justify-between text-[10px] uppercase tracking-wider text-slate-400 mt-1">
          <span>-14d</span><span>today</span>
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

- [ ] **Step 2: Update template tests for the new structure**

In `tests/test_gamma_templates.py`, update the `test_contract_detail_*` tests to assert on:

- "Conditions for YES" section appears when `contract.conditions` is non-empty
- "Regulatory timeline" header still present
- New legend row contains "Condition:" and "Urgency:"
- Heat block shows tier label (e.g. "ACTIVE" / "WATCH" rendered uppercase)
- Heat block shows the explainer text when `heat_panel.explainer` is set
- Alpine filter buttons render when there are ≥2 conditions

Use the fixture rendering pattern already in `tests/test_gamma_templates.py` (Jinja2 environment + a contract DTO with the new fields).

- [ ] **Step 3: Build and visually inspect**

```bash
python3 -m build.generate_slices && python3 -m build.generate
python3 -m http.server -d site 8000 &
SERVER_PID=$!
sleep 1
curl -s http://localhost:8000/gamma/contracts/tiktokban-25apr30/ > /tmp/page.html
grep -c "Conditions for YES" /tmp/page.html
grep -c "Regulatory timeline" /tmp/page.html
grep -c "ACTIVE\|WATCH\|DORMANT\|CRITICAL" /tmp/page.html
kill $SERVER_PID
```

Expected: each grep returns ≥ 1.

- [ ] **Step 4: Run template tests**

Run: `pytest tests/test_gamma_templates.py -v`

Expected: pass.

- [ ] **Step 5: Commit**

```bash
git add build/templates/gamma/contract_detail.html tests/test_gamma_templates.py
git commit -m "feat(γ): vertical timeline + heat panel + narrative + legend + filter"
```

---

## Task 15: Capture LLM cache + end-to-end verify tiktokban page

**Files:**
- Creates many files under: `build/_cache/llm/{thesis,relevance,heat_explainer,narrative}/`

- [ ] **Step 1: Confirm `.env` has `OPENAI_API_KEY` set**

```bash
grep -q "^OPENAI_API_KEY=sk-" .env && echo OK || echo "ADD KEY TO .env"
```

Expected: `OK`. If not, ask user to add the key — do not commit without it.

- [ ] **Step 2: Clear build outputs and run a cold-cache build**

```bash
rm -rf build/page_data site
time python3 -m build.generate_slices
```

Expected: prints `enriched 6 γ contract slices`. Walltime: ~3 minutes. Cache files appear under `build/_cache/llm/{thesis,relevance,heat_explainer,narrative}/`.

- [ ] **Step 3: Re-run with warm cache (should be near-instant)**

```bash
rm -rf build/page_data
time python3 -m build.generate_slices
```

Expected: walltime ≤ 5 seconds. No new cache files.

- [ ] **Step 4: Build the site and verify acceptance criteria**

```bash
python3 -m build.generate
ls site/gamma/contracts/ | sort
```

Expected output: exactly these 6 directories: `kxbtc-maxprice-2026 kxfeddecision-26mar kxfeddecision-28jan solana-etf-2025 tiktokban-25apr30 us-recession-in-2026` (each with `index.html`).

- [ ] **Step 5: Inspect tiktokban page against acceptance criteria**

```bash
python3 -m http.server -d site 8000 &
SERVER_PID=$!
sleep 1
PAGE=$(curl -s http://localhost:8000/gamma/contracts/tiktokban-25apr30/)
echo "$PAGE" | grep -c "Conditions for YES"
echo "$PAGE" | grep -c "Regulatory timeline"
echo "$PAGE" | grep -c "2025-04-30\|2025-04\|2025-03"   # in-window dates
echo "$PAGE" | grep -c "2025-12\|2026-"                  # post-resolution → must be 0
echo "$PAGE" | grep -c "one-line\|one_line\|hover:text-blue-700"  # event card rendering
echo "$PAGE" | grep -ic "active\|watch\|dormant\|critical"
echo "$PAGE" | grep -c "Condition:"  # legend
kill $SERVER_PID
```

Expected:
- "Conditions for YES" ≥ 1
- "Regulatory timeline" ≥ 1
- in-window dates ≥ 5
- post-resolution dates **== 0**
- tier label ≥ 1
- "Condition:" legend ≥ 1

- [ ] **Step 6: Run full test suite**

```bash
pytest -q
```

Expected: all pass.

- [ ] **Step 7: Commit LLM cache files**

```bash
git add build/_cache/llm/
git commit -m "feat(γ): commit LLM cache for deterministic demo builds"
```

- [ ] **Step 8: Final type / lint sweep**

```bash
mypy --strict build/
ruff check build/ tests/
```

Expected: clean.

- [ ] **Step 9: Commit any final fixes**

If steps 6 or 8 surface failures, fix them and commit with a descriptive message.

---

## Final Review

After all 15 tasks complete, dispatch a code-quality-reviewer subagent on the
full set of commits to verify:

1. **Acceptance criteria** from spec §11 — all 8 items met.
2. **Module boundaries** — no cross-talk; each enrichment module has a single responsibility.
3. **Graceful degradation** — confirm that deleting `.env` and rebuilding produces a renderable page (uses committed cache).
4. **Cache hygiene** — committed cache entries match the prompts in code (no stale entries from earlier prompt revisions).
5. **No leaked secrets** — `OPENAI_API_KEY` must not appear in any committed file under `build/_cache/`.

Then invoke superpowers:finishing-a-development-branch to complete the work.
