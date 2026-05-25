# Stage 0 Implementation Plan — Data + Scaffolding

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` (recommended) or `superpowers:executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship the Pred-Oracle demo's Stage 0 — a publicly-deployable static site with a landing page, three scene placeholder tiles, and a working data pipeline that pulls real Carver regulatory entries plus Kalshi/Polymarket public-API contract metadata at build time.

**Architecture:** Python 3.10 build script (`build/`) reads YAML platform-context + JSON Carver pull (`data/`), writes per-page slice JSON (`build/page_data/`), then Jinja2-renders templates into `site/`. GitHub Actions publishes `site/` to GitHub Pages on push to `main`. No backend, no auth, no JS bundler.

**Tech Stack:** Python 3.10, `uv` (dep management), Jinja2, Tailwind CSS via CDN, Apache ECharts via CDN (placeholder use only in Stage 0), `httpx`, `carver-feeds-sdk`, `pyyaml`, `markdown-it-py`, `pytest` + `pytest-asyncio` + `beautifulsoup4` (HTML assertion), `ruff` (lint+format), GitHub Actions.

**Prerequisites (one-time, not tracked as plan tasks):**
- `CARVER_API_KEY` env var available (the user must provide; get from https://app.carveragents.ai).
- Python 3.10 installed at `/usr/local/opt/python@3.10/bin/python3.10` (verified at repo init).
- `uv` installed: `curl -LsSf https://astral.sh/uv/install.sh | sh`.

**Spec references this plan implements:**
- [`docs/specs/00-demo-scope.md`](../../specs/00-demo-scope.md) — Stage 0 narrative + success criteria.
- [`docs/specs/10-data-prep.md`](../../specs/10-data-prep.md) — Carver pull strategy, YAML schemas, slice contract.
- [`docs/specs/20-site-build.md`](../../specs/20-site-build.md) — Tech stack, repo layout, template conventions, deploy.

**What this plan does NOT cover (other stages):**
- α / γ / β scene pages, slices, or assets. Stage 0 produces *empty placeholders* for those routes.
- Pre-rendered ticket details, contract retrospectives, heat-maps, quarterly reports.
- DP1 resolution drives stages 1-3 data-shape, but the verification step lives in this plan (Task 4) — the *response* to DP1 (raw-only vs annotated) is documented in `data/carver-pull-manifest.json` for the next stage to consume.

---

## Task Map

| # | Task | Outcome |
|---|---|---|
| 1 | Project bootstrap | `pyproject.toml`, `.gitignore`, repo skeleton, `uv sync` works |
| 2 | Test scaffolding | `pytest` runs with one passing sanity test |
| 3 | YAML seed catalogs | `data/known_regulators.yml`, `data/platforms/{kalshi,polymarket}/*.yml` with starter entries |
| 4 | Carver SDK + DP1 verification | `build/inspect_carver.py` script; documented finding in `data/dp1-findings.md` |
| 5 | Carver pull module | `build/pull_carver.py` produces `data/carver-events.json` + manifest |
| 6 | Kalshi pull module | `build/pull_kalshi.py` writes `data/platforms/kalshi/contracts_raw.json` |
| 7 | Polymarket pull module | `build/pull_polymarket.py` writes `data/platforms/polymarket/contracts_raw.json` |
| 8 | Landing-page slice | `build/generate_slices.py` writes `build/page_data/landing.json` with headline counts |
| 9 | Base + landing templates | `build/templates/base.html`, `build/templates/landing.html` render valid HTML |
| 10 | Scene placeholder templates | `build/templates/{alpha,gamma,beta}/intro.html` + `close.html` placeholder pages |
| 11 | Static assets | Tailwind/ECharts/Lucide CDN refs, custom `site.css`, navigation JS, logo placeholder |
| 12 | Build orchestrator | `build/generate.py` walks templates, writes `site/` deterministically |
| 13 | Makefile | `make pull`, `make slice`, `make build`, `make serve`, `make clean` work |
| 14 | GitHub Actions deploy | `.github/workflows/deploy.yml` publishes `site/` to `gh-pages` branch |
| 15 | Stage-0 acceptance dry-run | Smoke test + manual Lighthouse + URL verified live |

Approximately 75-90 sub-steps total. Each step is 2-5 minutes of focused work.

---

### Task 1: Project bootstrap

**Files:**
- Create: `pyproject.toml`
- Create: `.gitignore`
- Create: `build/__init__.py`
- Create: `data/.gitkeep`
- Create: `tests/__init__.py`

- [ ] **Step 1.1: Write `.gitignore`**

Replace any existing `.gitignore` with:

```gitignore
# Python
__pycache__/
*.py[cod]
*$py.class
.venv/
.uv/
.pytest_cache/
.mypy_cache/
.ruff_cache/
*.egg-info/

# Build outputs
build/page_data/
site/

# Environment
.env
.env.local

# Editor
.DS_Store
.idea/
.vscode/

# Demo data with potentially-sensitive snapshots (kept in repo for reproducibility per 20-site-build §2)
# carver-events.json IS checked in; see 10-data-prep §1.1 caveats
```

- [ ] **Step 1.2: Write `pyproject.toml`**

```toml
[project]
name = "pred-oracle"
version = "0.0.1"
description = "Pred-Oracle demo site"
requires-python = ">=3.10,<3.13"
dependencies = [
    "jinja2>=3.1.3",
    "markdown-it-py>=3.0.0",
    "pyyaml>=6.0.1",
    "httpx>=0.27.0",
    "carver-feeds-sdk>=0.1.0",
    "python-dotenv>=1.0.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.0.0",
    "pytest-asyncio>=0.23.0",
    "beautifulsoup4>=4.12.0",
    "ruff>=0.4.0",
    "mypy>=1.10.0",
]

[tool.pytest.ini_options]
testpaths = ["tests"]
asyncio_mode = "auto"

[tool.ruff]
line-length = 100
target-version = "py310"

[tool.ruff.lint]
select = ["E", "F", "I", "B", "UP"]

[tool.mypy]
python_version = "3.10"
strict = true
```

- [ ] **Step 1.3: Create empty module init files**

```bash
mkdir -p build data tests
touch build/__init__.py tests/__init__.py data/.gitkeep
```

- [ ] **Step 1.4: Sync dependencies**

Run: `uv sync --extra dev`
Expected: `Resolved N packages` followed by `Installed N packages`. No errors.

If `carver-feeds-sdk` fails to resolve from PyPI, fall back to: `uv add 'carver-feeds-sdk @ git+https://github.com/carveragents/carver-feeds-sdk'` and re-run.

- [ ] **Step 1.5: Smoke-test the venv**

Run: `uv run python -c "import jinja2, httpx, yaml, carver_feeds; print('ok')"`
Expected: `ok`

- [ ] **Step 1.6: Commit**

```bash
git add .gitignore pyproject.toml uv.lock build/__init__.py tests/__init__.py data/.gitkeep
git commit -m "Stage 0 Task 1: project bootstrap (uv + pyproject)"
```

---

### Task 2: Test scaffolding

**Files:**
- Create: `tests/test_sanity.py`

- [ ] **Step 2.1: Write a sanity test**

`tests/test_sanity.py`:

```python
"""Smoke test: confirms pytest + the venv resolve correctly."""


def test_python_version() -> None:
    import sys
    assert sys.version_info >= (3, 10), f"Python {sys.version_info} too old"


def test_core_imports() -> None:
    import jinja2
    import httpx
    import yaml
    import carver_feeds  # noqa: F401

    assert jinja2.__version__
    assert httpx.__version__
```

- [ ] **Step 2.2: Run the test**

Run: `uv run pytest tests/test_sanity.py -v`
Expected: `2 passed`. Both tests green.

- [ ] **Step 2.3: Commit**

```bash
git add tests/test_sanity.py
git commit -m "Stage 0 Task 2: pytest sanity test"
```

---

### Task 3: YAML seed catalogs

**Files:**
- Create: `data/known_regulators.yml`
- Create: `data/platforms/kalshi/entities.yml`
- Create: `data/platforms/kalshi/jurisdictions.yml`
- Create: `data/platforms/kalshi/personas.yml`
- Create: `data/platforms/polymarket/entities.yml`
- Create: `data/platforms/polymarket/jurisdictions.yml`
- Create: `data/platforms/polymarket/personas.yml`
- Create: `data/sources/personnel-sources.md`
- Test: `tests/test_yaml_seeds.py`

These are hand-edited YAML files. Per [`10-data-prep.md`](../../specs/10-data-prep.md) § 3, each named individual must have a public-source URL.

- [ ] **Step 3.1: Write the test that validates the YAML structure**

`tests/test_yaml_seeds.py`:

```python
"""YAML seed catalogs lint + minimal structural checks."""

from pathlib import Path

import pytest
import yaml

DATA = Path(__file__).parent.parent / "data"


def test_known_regulators_loads() -> None:
    items = yaml.safe_load((DATA / "known_regulators.yml").read_text())
    assert isinstance(items, list)
    assert len(items) >= 50, f"Need >= 50 regulators per 10-data-prep §2.1; got {len(items)}"
    for item in items:
        assert "canonical_name" in item
        assert isinstance(item.get("aliases", []), list)


@pytest.mark.parametrize("platform", ["kalshi", "polymarket"])
def test_entity_catalog_well_formed(platform: str) -> None:
    items = yaml.safe_load((DATA / "platforms" / platform / "entities.yml").read_text())
    assert isinstance(items, list)
    assert 10 <= len(items) <= 30, f"{platform} entities: {len(items)} (want 10-30)"
    self_entries = [e for e in items if e.get("role") == "self"]
    assert len(self_entries) >= 1, f"{platform} catalog needs at least one role=self entry"
    # Staff entries need a source URL
    for item in items:
        if item.get("role") == "staff":
            assert item.get("source"), f"Staff entry {item['canonical_name']} missing source URL"


@pytest.mark.parametrize("platform", ["kalshi", "polymarket"])
def test_jurisdictions_well_formed(platform: str) -> None:
    items = yaml.safe_load((DATA / "platforms" / platform / "jurisdictions.yml").read_text())
    assert isinstance(items, list)
    valid_statuses = {"operating", "considering", "closed", "excluded"}
    for item in items:
        assert item.get("code"), "Each jurisdiction needs an ISO code"
        assert item.get("status") in valid_statuses


@pytest.mark.parametrize("platform", ["kalshi", "polymarket"])
def test_personas_well_formed(platform: str) -> None:
    obj = yaml.safe_load((DATA / "platforms" / platform / "personas.yml").read_text())
    assert isinstance(obj, dict)
    for key in ("gc", "listing_lead", "international_lead"):
        assert key in obj, f"{platform} personas missing {key}"
        assert obj[key].get("display_name")
```

- [ ] **Step 3.2: Run the test (should fail — files don't exist yet)**

Run: `uv run pytest tests/test_yaml_seeds.py -v`
Expected: FAIL with `FileNotFoundError`.

- [ ] **Step 3.3: Write `data/known_regulators.yml`**

Minimum 50 entries. Use this skeleton, expand to cover the lists in `10-data-prep.md` § 2.1:

```yaml
# US federal
- canonical_name: Commodity Futures Trading Commission
  aliases: [CFTC]
- canonical_name: Securities and Exchange Commission
  aliases: [SEC]
- canonical_name: Federal Communications Commission
  aliases: [FCC]
- canonical_name: Federal Trade Commission
  aliases: [FTC]
- canonical_name: Department of Justice
  aliases: [DOJ]
- canonical_name: Financial Crimes Enforcement Network
  aliases: [FinCEN]
- canonical_name: Office of Foreign Assets Control
  aliases: [OFAC]
- canonical_name: Consumer Financial Protection Bureau
  aliases: [CFPB]
- canonical_name: Department of the Treasury
  aliases: [Treasury, US Treasury]
- canonical_name: Federal Reserve
  aliases: [Fed, Board of Governors, FOMC, Federal Open Market Committee]
- canonical_name: Department of Commerce
  aliases: [Commerce, DoC]
- canonical_name: Committee on Foreign Investment in the United States
  aliases: [CFIUS]

# US state gambling regulators (at least 12 to cover Kalshi enforcement geography)
- canonical_name: Nevada Gaming Control Board
  aliases: [NGCB, Nevada GCB]
- canonical_name: New Jersey Division of Gaming Enforcement
  aliases: [NJ DGE]
- canonical_name: Maryland Lottery and Gaming Control Agency
  aliases: [MLGCA, Maryland Lottery and Gaming]
- canonical_name: Massachusetts Gaming Commission
  aliases: [MGC, Mass Gaming]
- canonical_name: New York State Gaming Commission
  aliases: [NYSGC]
- canonical_name: Arizona Department of Gaming
  aliases: [AZ DG]
- canonical_name: Connecticut Department of Consumer Protection
  aliases: [CT DCP]
- canonical_name: Ohio Casino Control Commission
  aliases: [OCCC]
- canonical_name: Montana Gambling Control Division
  aliases: [MT GCD]
- canonical_name: Wisconsin Department of Administration Division of Gaming
  aliases: [WI Gaming]
- canonical_name: North Dakota Attorney General Gaming Division
  aliases: [ND Gaming]
- canonical_name: Pennsylvania Gaming Control Board
  aliases: [PGCB]

# Tribal
- canonical_name: National Indian Gaming Commission
  aliases: [NIGC]

# International (cover all 5 Polymarket-banning jurisdictions + adjacent)
- canonical_name: Autorité Nationale des Jeux
  aliases: [ANJ, France ANJ]
- canonical_name: Gambling Regulatory Authority of Singapore
  aliases: [GRA, GRA Singapore]
- canonical_name: Anti-Money Laundering Office Thailand
  aliases: [AMLO]
- canonical_name: UK Gambling Commission
  aliases: [UKGC]
- canonical_name: Kansspelautoriteit
  aliases: [KSA, Netherlands KSA]
- canonical_name: Malta Gaming Authority
  aliases: [MGA]
- canonical_name: Hungarian Gambling Authority
  aliases: [SZRH]
- canonical_name: Secretaria de Avaliação, Planejamento, Energia e Loteria
  aliases: [SECAP, Brazil SECAP]
- canonical_name: Securities and Exchange Board of India
  aliases: [SEBI]
- canonical_name: Australian Transaction Reports and Analysis Centre
  aliases: [AUSTRAC]

# Standards bodies
- canonical_name: Financial Action Task Force
  aliases: [FATF]
- canonical_name: International Organization of Securities Commissions
  aliases: [IOSCO]
- canonical_name: Basel Committee on Banking Supervision
  aliases: [BCBS]
- canonical_name: European Securities and Markets Authority
  aliases: [ESMA]
- canonical_name: European Commission
  aliases: [EC]

# Expand to >= 50 by adding remaining US state gambling regulators (PA, IL, MI, IN, etc.)
# and additional foreign regulators (Germany, Spain, Italy, Belgium, Sweden, Canada provinces).
```

The above is ~36 entries; add ~15-20 more from the lists in `10-data-prep.md` § 2.1 to hit the >=50 threshold.

- [ ] **Step 3.4: Write `data/platforms/kalshi/entities.yml`** (15-20 entries)

```yaml
- canonical_name: Kalshi
  aliases: [KalshiEX, KalshiEX LLC, Kalshi Inc.]
  role: self
- canonical_name: Tarek Mansour
  aliases: [Tarek Monsour, T. Mansour]
  role: staff
  title: CEO
  source: https://kalshi.com/about
  retrieved: 2026-05-19
- canonical_name: Luana Lopes Lara
  aliases: [Lopes Lara]
  role: staff
  title: Co-founder
  source: https://kalshi.com/about
  retrieved: 2026-05-19
# Add ~12 more entries: competitors (Polymarket, PredictIt, Manifold, Cantor Fitzgerald,
# Robinhood Markets, Webull), upstream regulators (CFTC, NGCB, NJ DGE — these duplicate
# known_regulators but appear in entities.yml as platform-relevant), and known adjacent
# entities (CME Group, ICE, DraftKings, FanDuel).
```

Every `role: staff` entry must have a `source` URL.

- [ ] **Step 3.5: Write `data/platforms/polymarket/entities.yml`** (15-20 entries)

Follow the same pattern. Highlights to include: Polymarket self + aliases; Shayne Coplan (CEO with source); UMA Protocol; Risk Labs; QCEX (acquired); ICE (investor); Kalshi (competitor); PredictIt; Cantor Fitzgerald; Drift Protocol; Manifold Markets.

- [ ] **Step 3.6: Write jurisdiction files**

`data/platforms/kalshi/jurisdictions.yml` (~30 entries):

```yaml
- code: US
  status: operating
- code: US-NV
  status: closed
  notes: Active state cease and desist; 2024-2026 litigation
- code: US-NJ
  status: closed
- code: US-MD
  status: closed
- code: US-MA
  status: operating
  notes: Cease and desist litigated
- code: US-NY
  status: operating
- code: US-AZ
  status: operating
- code: US-CT
  status: operating
- code: US-OH
  status: operating
- code: US-MT
  status: operating
- code: US-WI
  status: operating
- code: US-ND
  status: operating
# Add ~18 more: a mix of operating/considering/closed states + ~12 international codes
# (CA, GB, AU, NZ, JP, KR, BR, MX, IN, SG, DE, FR).
```

`data/platforms/polymarket/jurisdictions.yml` (~40 entries) — include the 5 explicitly-closed: FR, SG, TH, GB, NL.

- [ ] **Step 3.7: Write persona files**

`data/platforms/kalshi/personas.yml`:

```yaml
gc:
  display_name: "Sara Chen"
  role: General Counsel
  page_urgency_threshold: 8
  digest_cadence: daily
listing_lead:
  display_name: "Marcus Vega"
  role: Head of Listing
international_lead:
  display_name: "(unused for Kalshi)"
  role: Head of International
```

`data/platforms/polymarket/personas.yml`:

```yaml
gc:
  display_name: "Devon Ashford"
  role: General Counsel
listing_lead:
  display_name: "Renata Okafor"
  role: Head of Listing
international_lead:
  display_name: "Priya Kapur"
  role: Head of International
```

- [ ] **Step 3.8: Write `data/sources/personnel-sources.md`**

```markdown
# Personnel Sources

Every named individual in `data/platforms/*/entities.yml` whose role is `staff` must appear in this log with a public source URL and retrieval date.

| Person | Role | Platform | Source | Retrieved |
|---|---|---|---|---|
| Tarek Mansour | CEO | Kalshi | https://kalshi.com/about | 2026-05-19 |
| Luana Lopes Lara | Co-founder | Kalshi | https://kalshi.com/about | 2026-05-19 |
| Shayne Coplan | CEO | Polymarket | https://polymarket.com/about | 2026-05-19 |

Fictional persona names (Sara Chen, Marcus Vega, Devon Ashford, Renata Okafor, Priya Kapur) are not in this log — they are explicit demo placeholders, never claimed as real employees of any platform.
```

- [ ] **Step 3.9: Run the YAML tests**

Run: `uv run pytest tests/test_yaml_seeds.py -v`
Expected: `7 passed` (1 known_regulators + 2 entities + 2 jurisdictions + 2 personas).

If any fail, expand the YAML to meet the threshold and re-run.

- [ ] **Step 3.10: Commit**

```bash
git add data/ tests/test_yaml_seeds.py
git commit -m "Stage 0 Task 3: YAML seed catalogs (regulators, entities, jurisdictions, personas)"
```

---

### Task 4: Carver SDK inspection + DP1 verification

**Files:**
- Create: `build/inspect_carver.py`
- Create: `data/dp1-findings.md`

This is an investigative task. It runs once to answer DP1: does the carver-feeds-sdk surface Appendix-A annotation fields on entries, or only raw entry metadata? The script outputs a sample entry; the engineer eyeballs the JSON and writes the finding into `data/dp1-findings.md`.

- [ ] **Step 4.1: Write the inspection script**

`build/inspect_carver.py`:

```python
"""DP1 verification: sample one Carver entry and dump its full JSON.

Run once (or whenever DP1 needs to be re-verified). Output is human-inspected
to determine whether the SDK returns Appendix-A annotation fields directly.

Usage:
    uv run python build/inspect_carver.py > data/dp1-sample-entry.json
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

from dotenv import load_dotenv


def main() -> int:
    # Load .env from repo root
    load_dotenv(Path(__file__).parent.parent / ".env")

    if not os.environ.get("CARVER_API_KEY"):
        print("ERROR: CARVER_API_KEY not set. Create a .env file or export the var.", file=sys.stderr)
        print("Get a key at https://app.carveragents.ai", file=sys.stderr)
        return 1

    # Import after env loaded — SDK reads CARVER_API_KEY at import time in some versions
    from carver_feeds import create_query_engine

    qe = create_query_engine()

    # Pull ONE entry. We don't care which; we just need to see what fields it carries.
    df = qe.to_dataframe()  # may be slow first time per skill doc

    if len(df) == 0:
        print("ERROR: SDK returned zero entries. Check API key + connectivity.", file=sys.stderr)
        return 1

    sample = df.iloc[0].to_dict()
    json.dump(sample, sys.stdout, indent=2, default=str)
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 4.2: Provide the API key**

Create `.env` at repo root with:

```bash
CARVER_API_KEY=<your-key-here>
```

(`.env` is gitignored per Task 1.)

- [ ] **Step 4.3: Run the inspection**

Run: `uv run python build/inspect_carver.py > data/dp1-sample-entry.json`
Expected: a JSON object containing fields. Inspect manually.

- [ ] **Step 4.4: Document the finding**

Write `data/dp1-findings.md` based on what you saw:

```markdown
# DP1 Resolution

**Question:** Does `carver-feeds-sdk` surface Appendix-A annotation fields on entries, or only raw entry metadata?

**Verified:** 2026-05-19 (date of inspection)

**Sample fields observed (from `data/dp1-sample-entry.json`):**
- [list the field names returned by the SDK]

**Resolution: [PICK ONE]**

### Case A — SDK returns annotated fields
If the sample includes `update_type`, `regulatory_source`, `impacted_business`, `scores` (or equivalent), then the SDK is sufficient. Carver pull script (Task 5) maps these directly to the projected columns in `regulatory_events`-equivalent slice JSON. No additional annotation step.

### Case B — SDK returns only raw entry metadata
If the sample is essentially RSS-like (`entry_title`, `entry_description`, `entry_content_markdown`, `entry_link`, dates, topic/feed), then Task 5 needs a sub-step that runs a Claude call per filtered entry to derive Appendix-A fields. Use Anthropic Python SDK; model `claude-sonnet-4-6` (fast enough for hundreds of entries; cheaper than opus). Prompt skeleton lifts from `../carver-dags/workflows/entry_annotation/prompts.py`.

### Case C — Hybrid
Some annotated fields surface, others don't. Document which are present, which need Claude derivation. Task 5 maps present fields directly; derives missing fields.

**Chosen path:** [A | B | C]

**Implications for Task 5:**
- [list any changes to the pull script per the chosen case]
```

This file is committed and read by Task 5.

- [ ] **Step 4.5: Commit**

```bash
git add build/inspect_carver.py data/dp1-findings.md data/dp1-sample-entry.json
git commit -m "Stage 0 Task 4: Carver SDK DP1 verification"
```

---

### Task 5: Carver pull module

**Files:**
- Create: `build/pull_carver.py`
- Create: `tests/test_pull_carver.py`

This is the script that produces `data/carver-events.json`. Behavior depends on DP1 (Task 4) outcome.

- [ ] **Step 5.1: Write the filter test (DP1-agnostic, tests pure-function logic)**

`tests/test_pull_carver.py`:

```python
"""Tests for the prediction-market-relevance filter and projection logic."""

from pathlib import Path

import pytest
import yaml

from build.pull_carver import is_prediction_market_relevant, load_filter_inputs


@pytest.fixture(scope="module")
def filter_inputs() -> tuple[set[str], set[str]]:
    return load_filter_inputs(Path(__file__).parent.parent / "data")


def test_filter_matches_business_type(filter_inputs: tuple[set[str], set[str]]) -> None:
    regulators, entities = filter_inputs
    entry = {
        "impacted_business": {"type": ["Event Contracts"]},
        "regulatory_source": {"name": "Some Obscure Agency"},
        "entities": [],
    }
    assert is_prediction_market_relevant(entry, regulators, entities) is True


def test_filter_matches_regulator_allowlist(filter_inputs: tuple[set[str], set[str]]) -> None:
    regulators, entities = filter_inputs
    entry = {
        "impacted_business": {"type": ["Banking"]},
        "regulatory_source": {"name": "Commodity Futures Trading Commission"},
        "entities": [],
    }
    assert is_prediction_market_relevant(entry, regulators, entities) is True


def test_filter_matches_platform_entity(filter_inputs: tuple[set[str], set[str]]) -> None:
    regulators, entities = filter_inputs
    entry = {
        "impacted_business": {"type": ["Banking"]},
        "regulatory_source": {"name": "Some Obscure Agency"},
        "entities": ["Kalshi"],
    }
    assert is_prediction_market_relevant(entry, regulators, entities) is True


def test_filter_rejects_unrelated(filter_inputs: tuple[set[str], set[str]]) -> None:
    regulators, entities = filter_inputs
    entry = {
        "impacted_business": {"type": ["Telecom"]},
        "regulatory_source": {"name": "Some Telecom Regulator"},
        "entities": ["Unrelated Co."],
    }
    assert is_prediction_market_relevant(entry, regulators, entities) is False


def test_load_filter_inputs_loads_seeds() -> None:
    regulators, entities = load_filter_inputs(Path(__file__).parent.parent / "data")
    assert len(regulators) >= 50
    assert "Kalshi" in entities
```

- [ ] **Step 5.2: Run tests to verify they fail (module doesn't exist)**

Run: `uv run pytest tests/test_pull_carver.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'build.pull_carver'`.

- [ ] **Step 5.3: Implement `build/pull_carver.py` — pure logic first**

```python
"""Carver Feeds API pull, prediction-market-relevance filter, and annotation
projection. Produces `data/carver-events.json` + `data/carver-pull-manifest.json`.

Per DP1 (data/dp1-findings.md):
- Case A: SDK returns annotated fields → projection is direct copy.
- Case B: SDK returns raw entries → derive Appendix-A fields via Claude.
- Case C: hybrid → present fields direct, missing fields derived.

This module exposes:
- `is_prediction_market_relevant(entry, regulators, entities) -> bool`
- `load_filter_inputs(data_dir: Path) -> (regulators: set[str], entities: set[str])`
- `pull_carver_events(date_from, date_to, limit) -> list[dict]` (called by main)
- `main()` orchestrates pull → filter → project → write
"""

from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml
from dotenv import load_dotenv


PM_BUSINESS_TYPES = {
    "Event Contracts",
    "Sports Betting",
    "Derivatives Exchanges",
    "Prediction Markets",
    "Sweepstakes",
    "Online Gambling",
    "Commodity Exchanges",
    "Cryptocurrency Exchanges",
}


def load_filter_inputs(data_dir: Path) -> tuple[set[str], set[str]]:
    """Load regulator allowlist and platform-entity set used by the filter."""
    regulators: set[str] = set()
    for reg in yaml.safe_load((data_dir / "known_regulators.yml").read_text()):
        regulators.add(reg["canonical_name"])
        regulators.update(reg.get("aliases", []))

    entities: set[str] = set()
    for platform_dir in (data_dir / "platforms").iterdir():
        if not platform_dir.is_dir():
            continue
        entities_file = platform_dir / "entities.yml"
        if not entities_file.exists():
            continue
        for ent in yaml.safe_load(entities_file.read_text()):
            entities.add(ent["canonical_name"])
            entities.update(ent.get("aliases", []))

    return regulators, entities


def is_prediction_market_relevant(
    entry: dict[str, Any],
    regulators: set[str],
    entities: set[str],
) -> bool:
    """Boolean OR over the three filter clauses from 10-data-prep §2.1."""
    # Clause A: impacted-business taxonomy
    business = entry.get("impacted_business") or {}
    types = business.get("type") or []
    if set(types) & PM_BUSINESS_TYPES:
        return True

    # Clause B: regulator-source allowlist
    source = entry.get("regulatory_source") or {}
    src_name = source.get("name") or ""
    if src_name in regulators:
        return True

    # Clause C: entity mention of any platform / staff / known competitor
    entry_entities = entry.get("entities") or []
    if set(entry_entities) & entities:
        return True

    return False


def pull_carver_events(
    date_from: str, date_to: str, limit: int = 10000
) -> list[dict[str, Any]]:
    """Pull entries from the carver-feeds-sdk between dates. Returns raw list.

    Per DP1: if the SDK surfaces annotated fields, each entry already has the
    Appendix-A structure. If not, the caller (main) runs the derivation step.
    """
    from carver_feeds import create_query_engine

    qe = create_query_engine()
    qe = qe.filter_by_date(
        start_date=datetime.fromisoformat(date_from),
        end_date=datetime.fromisoformat(date_to),
    )
    df = qe.to_dataframe()
    return df.head(limit).to_dict(orient="records")


def derive_appendix_a(entry: dict[str, Any]) -> dict[str, Any]:
    """Case B/C: derive Appendix-A annotation via Claude call.

    Stub: a real implementation lives behind the Anthropic SDK call.
    For Stage 0, this is invoked only if DP1 finding is B or C.
    """
    raise NotImplementedError(
        "Implement Claude annotation if DP1 finding is B or C. "
        "See data/dp1-findings.md for the chosen path."
    )


def main() -> int:
    load_dotenv(Path(__file__).parent.parent / ".env")
    if not os.environ.get("CARVER_API_KEY"):
        print("ERROR: CARVER_API_KEY not set", file=sys.stderr)
        return 1

    repo_root = Path(__file__).parent.parent
    data_dir = repo_root / "data"

    regulators, entities = load_filter_inputs(data_dir)
    print(f"Loaded {len(regulators)} regulator names, {len(entities)} platform entities")

    date_from = os.environ.get("PRED_ORACLE_PULL_FROM", "2024-01-01")
    date_to = os.environ.get("PRED_ORACLE_PULL_TO", datetime.now(timezone.utc).date().isoformat())

    raw_entries = pull_carver_events(date_from, date_to)
    print(f"Pulled {len(raw_entries)} raw entries from carver-feeds-sdk")

    filtered = [e for e in raw_entries if is_prediction_market_relevant(e, regulators, entities)]
    print(f"Filtered to {len(filtered)} prediction-market-relevant entries")

    # Optionally derive Appendix-A fields per DP1
    dp1_case = os.environ.get("PRED_ORACLE_DP1_CASE", "A")
    if dp1_case in ("B", "C"):
        filtered = [derive_appendix_a(e) for e in filtered]

    out_path = data_dir / "carver-events.json"
    out_path.write_text(json.dumps(filtered, indent=2, default=str))

    manifest = {
        "pulled_at": datetime.now(timezone.utc).isoformat(),
        "carver_sdk_version": _sdk_version(),
        "date_from": date_from,
        "date_to": date_to,
        "raw_count_before_filter": len(raw_entries),
        "kept_count": len(filtered),
        "dp1_case": dp1_case,
    }
    (data_dir / "carver-pull-manifest.json").write_text(json.dumps(manifest, indent=2))
    print(f"Wrote {out_path} + manifest")
    return 0


def _sdk_version() -> str:
    try:
        import carver_feeds
        return getattr(carver_feeds, "__version__", "unknown")
    except Exception:
        return "unknown"


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 5.4: Run the unit tests**

Run: `uv run pytest tests/test_pull_carver.py -v`
Expected: `5 passed`.

- [ ] **Step 5.5: Run the actual pull (integration)**

Run: `uv run python build/pull_carver.py`
Expected output: pulls succeed; produces `data/carver-events.json` (200-500 entries ideally) + `data/carver-pull-manifest.json`.

If volume is wrong (<100 or >2000), adjust:
- Too few: widen the regulator allowlist or business-type set.
- Too many: narrow the date range via env vars.

- [ ] **Step 5.6: Commit**

```bash
git add build/pull_carver.py tests/test_pull_carver.py data/carver-events.json data/carver-pull-manifest.json
git commit -m "Stage 0 Task 5: Carver feeds pull + filter + manifest"
```

---

### Task 6: Kalshi pull module

**Files:**
- Create: `build/pull_kalshi.py`
- Create: `tests/test_pull_kalshi.py`

Hits `https://external-api.kalshi.com/trade-api/v2/markets`. Writes `data/platforms/kalshi/contracts_raw.json`.

- [ ] **Step 6.1: Write the response-parsing test**

`tests/test_pull_kalshi.py`:

```python
"""Tests for Kalshi market-list parsing."""

import json
from pathlib import Path

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
```

- [ ] **Step 6.2: Run test (fails — module missing)**

Run: `uv run pytest tests/test_pull_kalshi.py -v`
Expected: FAIL `ModuleNotFoundError`.

- [ ] **Step 6.3: Implement `build/pull_kalshi.py`**

```python
"""Pull listed-market metadata from Kalshi's public API.

API: https://external-api.kalshi.com/trade-api/v2/markets
No auth required for read endpoints (per docs.kalshi.com).
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import httpx


KALSHI_MARKETS_URL = "https://external-api.kalshi.com/trade-api/v2/markets"


def parse_market(raw: dict[str, Any]) -> dict[str, Any]:
    """Project a Kalshi market dict into Pred-Oracle's contract schema."""
    status_map = {
        "open": "active",
        "active": "active",
        "settled": "resolved",
        "closed": "resolved",
    }
    return {
        "external_id": raw.get("ticker", ""),
        "title": raw.get("title", ""),
        "subtitle": raw.get("subtitle", ""),
        "resolution_criteria": raw.get("rules_primary", raw.get("subtitle", "")),
        "listed_at": raw.get("open_time", ""),
        "expires_at": raw.get("close_time", ""),
        "status": status_map.get(raw.get("status", ""), "active"),
        "settlement_entities": [raw["settlement_source"]] if raw.get("settlement_source") else [],
        "platform": "kalshi",
        "payload": raw,
    }


def fetch_markets(limit: int = 200) -> list[dict[str, Any]]:
    """Hit Kalshi's public markets endpoint with pagination."""
    out: list[dict[str, Any]] = []
    cursor: str | None = None
    page_size = 100

    while len(out) < limit:
        params: dict[str, Any] = {"limit": page_size}
        if cursor:
            params["cursor"] = cursor
        resp = httpx.get(KALSHI_MARKETS_URL, params=params, timeout=30.0)
        resp.raise_for_status()
        body = resp.json()
        markets = body.get("markets", [])
        if not markets:
            break
        out.extend(markets)
        cursor = body.get("cursor")
        if not cursor:
            break
    return out[:limit]


def main() -> int:
    repo_root = Path(__file__).parent.parent
    out_dir = repo_root / "data" / "platforms" / "kalshi"
    out_dir.mkdir(parents=True, exist_ok=True)

    markets = fetch_markets(limit=200)
    parsed = [parse_market(m) for m in markets]
    out_path = out_dir / "contracts_raw.json"
    out_path.write_text(json.dumps(parsed, indent=2))
    print(f"Wrote {len(parsed)} Kalshi markets to {out_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 6.4: Run unit tests**

Run: `uv run pytest tests/test_pull_kalshi.py -v`
Expected: PASS.

- [ ] **Step 6.5: Run integration pull**

Run: `uv run python build/pull_kalshi.py`
Expected: `Wrote 200 Kalshi markets to data/platforms/kalshi/contracts_raw.json`.

If the schema returned by Kalshi has shifted (field renames), update `parse_market` accordingly. Field names in the test should match production API.

- [ ] **Step 6.6: Commit**

```bash
git add build/pull_kalshi.py tests/test_pull_kalshi.py data/platforms/kalshi/contracts_raw.json
git commit -m "Stage 0 Task 6: Kalshi public-API pull"
```

---

### Task 7: Polymarket pull module

**Files:**
- Create: `build/pull_polymarket.py`
- Create: `tests/test_pull_polymarket.py`

Hits `https://gamma-api.polymarket.com/markets`. Writes `data/platforms/polymarket/contracts_raw.json`.

- [ ] **Step 7.1: Write the response-parsing test**

`tests/test_pull_polymarket.py`:

```python
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
        "outcomePrices": "[0.85, 0.15]",
        "tags": [{"label": "Crypto"}, {"label": "Regulation"}],
    }
    parsed = parse_market(sample)
    assert parsed["external_id"] == "12345"
    assert "Solana" in parsed["title"]
    assert parsed["status"] == "resolved"  # closed=True maps to resolved
    assert parsed["platform"] == "polymarket"
    assert parsed["payload"] == sample
```

- [ ] **Step 7.2: Run test (fails)**

Run: `uv run pytest tests/test_pull_polymarket.py -v`
Expected: FAIL `ModuleNotFoundError`.

- [ ] **Step 7.3: Implement `build/pull_polymarket.py`**

```python
"""Pull market metadata from Polymarket Gamma API."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import httpx


GAMMA_MARKETS_URL = "https://gamma-api.polymarket.com/markets"


def parse_market(raw: dict[str, Any]) -> dict[str, Any]:
    return {
        "external_id": str(raw.get("id", "")),
        "title": raw.get("question", ""),
        "subtitle": "",
        "resolution_criteria": raw.get("description", ""),
        "listed_at": raw.get("startDate", ""),
        "expires_at": raw.get("endDate", ""),
        "status": "resolved" if raw.get("closed") else "active",
        "settlement_entities": [],  # Polymarket doesn't tag a single settlement source
        "platform": "polymarket",
        "payload": raw,
    }


def fetch_markets(limit: int = 200) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    offset = 0
    page_size = 100

    while len(out) < limit:
        resp = httpx.get(
            GAMMA_MARKETS_URL,
            params={"limit": page_size, "offset": offset, "order": "startDate", "ascending": "false"},
            timeout=30.0,
        )
        resp.raise_for_status()
        body = resp.json()
        if not isinstance(body, list) or not body:
            break
        out.extend(body)
        if len(body) < page_size:
            break
        offset += page_size
    return out[:limit]


def main() -> int:
    repo_root = Path(__file__).parent.parent
    out_dir = repo_root / "data" / "platforms" / "polymarket"
    out_dir.mkdir(parents=True, exist_ok=True)

    markets = fetch_markets(limit=200)
    parsed = [parse_market(m) for m in markets]
    out_path = out_dir / "contracts_raw.json"
    out_path.write_text(json.dumps(parsed, indent=2))
    print(f"Wrote {len(parsed)} Polymarket markets to {out_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 7.4: Run unit tests**

Run: `uv run pytest tests/test_pull_polymarket.py -v`
Expected: PASS.

- [ ] **Step 7.5: Run integration pull**

Run: `uv run python build/pull_polymarket.py`
Expected: `Wrote 200 Polymarket markets to data/platforms/polymarket/contracts_raw.json`.

Adjust `parse_market` field names if the Gamma API has shifted. Source of truth: a live call to `curl -s 'https://gamma-api.polymarket.com/markets?limit=1' | jq '.[0]'`.

- [ ] **Step 7.6: Commit**

```bash
git add build/pull_polymarket.py tests/test_pull_polymarket.py data/platforms/polymarket/contracts_raw.json
git commit -m "Stage 0 Task 7: Polymarket public-API pull"
```

---

### Task 8: Landing-page slice generator

**Files:**
- Create: `build/generate_slices.py`
- Create: `tests/test_generate_slices.py`

In Stage 0, the only slice is `landing.json` (headline stats). Stages 1-3 add scene-specific slices.

- [ ] **Step 8.1: Write the slice test**

`tests/test_generate_slices.py`:

```python
"""Tests for the slice generator."""

import json
from pathlib import Path

from build.generate_slices import generate_landing_slice


def test_landing_slice_has_required_fields(tmp_path: Path) -> None:
    # Minimal fixture
    fixture = tmp_path / "carver-events.json"
    fixture.write_text(json.dumps([
        {"pub_date": "2025-01-15", "jurisdictions": ["US"], "regulatory_source": {"name": "CFTC"}},
        {"pub_date": "2025-06-01", "jurisdictions": ["FR"], "regulatory_source": {"name": "ANJ"}},
    ]))
    out = generate_landing_slice(fixture)
    assert out["events_count"] == 2
    assert out["jurisdictions_count"] == 2
    assert out["earliest_pub_date"] == "2025-01-15"
    assert out["latest_pub_date"] == "2025-06-01"
    assert out["unique_regulators_count"] == 2
```

- [ ] **Step 8.2: Run test (fails)**

Run: `uv run pytest tests/test_generate_slices.py -v`
Expected: FAIL `ModuleNotFoundError`.

- [ ] **Step 8.3: Implement `build/generate_slices.py`**

```python
"""Slice generator: data/ + carver-events.json → build/page_data/.

Stage 0 produces only `landing.json` (headline stats for the landing page).
Later stages add per-scene slices.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any


def generate_landing_slice(carver_events_path: Path) -> dict[str, Any]:
    events: list[dict[str, Any]] = json.loads(carver_events_path.read_text())

    jurisdictions: set[str] = set()
    regulators: set[str] = set()
    pub_dates: list[str] = []

    for e in events:
        for j in e.get("jurisdictions") or []:
            jurisdictions.add(j)
        src = (e.get("regulatory_source") or {}).get("name")
        if src:
            regulators.add(src)
        if e.get("pub_date"):
            pub_dates.append(str(e["pub_date"]))

    pub_dates.sort()
    return {
        "events_count": len(events),
        "jurisdictions_count": len(jurisdictions),
        "unique_regulators_count": len(regulators),
        "earliest_pub_date": pub_dates[0] if pub_dates else None,
        "latest_pub_date": pub_dates[-1] if pub_dates else None,
    }


def main() -> int:
    repo_root = Path(__file__).parent.parent
    out_dir = repo_root / "build" / "page_data"
    out_dir.mkdir(parents=True, exist_ok=True)

    landing = generate_landing_slice(repo_root / "data" / "carver-events.json")
    (out_dir / "landing.json").write_text(json.dumps(landing, indent=2))
    print(f"Wrote build/page_data/landing.json: {landing}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 8.4: Run unit test**

Run: `uv run pytest tests/test_generate_slices.py -v`
Expected: PASS.

- [ ] **Step 8.5: Run integration**

Run: `uv run python build/generate_slices.py`
Expected: writes `build/page_data/landing.json` with real counts. Inspect; verify counts are plausible.

- [ ] **Step 8.6: Commit**

```bash
git add build/generate_slices.py tests/test_generate_slices.py
git commit -m "Stage 0 Task 8: landing-page slice generator"
```

---

### Task 9: Base + landing templates

**Files:**
- Create: `build/templates/base.html`
- Create: `build/templates/landing.html`
- Create: `tests/test_templates.py`

- [ ] **Step 9.1: Write the rendering test**

`tests/test_templates.py`:

```python
"""Tests that templates render to valid expected HTML."""

import json
from pathlib import Path

import pytest
from bs4 import BeautifulSoup
from jinja2 import Environment, FileSystemLoader

TEMPLATES = Path(__file__).parent.parent / "build" / "templates"


@pytest.fixture
def env() -> Environment:
    return Environment(loader=FileSystemLoader(str(TEMPLATES)), autoescape=True)


def test_landing_renders_with_required_elements(env: Environment) -> None:
    ctx = {
        "events_count": 312,
        "jurisdictions_count": 38,
        "unique_regulators_count": 47,
        "earliest_pub_date": "2024-01-15",
        "latest_pub_date": "2026-05-18",
    }
    html = env.get_template("landing.html").render(**ctx)
    soup = BeautifulSoup(html, "html.parser")

    # Headline copy present
    assert soup.find("h1") is not None

    # Three scene tiles
    tiles = soup.find_all(class_="scene-tile")
    assert len(tiles) == 3, f"Expected 3 scene tiles; found {len(tiles)}"

    # Tailwind CDN script present
    scripts = [s.get("src", "") for s in soup.find_all("script")]
    assert any("cdn.tailwindcss.com" in s for s in scripts)

    # Counts surfaced
    assert "312" in html
    assert "38" in html


def test_base_template_has_required_chrome(env: Environment) -> None:
    # Base is extended via {% extends %} — render a minimal child to verify
    child = env.from_string(
        "{% extends 'base.html' %}{% block content %}<p>x</p>{% endblock %}"
    )
    html = child.render(events_count=0, jurisdictions_count=0, unique_regulators_count=0,
                        earliest_pub_date=None, latest_pub_date=None)
    soup = BeautifulSoup(html, "html.parser")
    assert soup.find("nav") is not None
    assert soup.find("footer") is not None
    # Demo disclaimer in footer
    assert "demo" in soup.find("footer").get_text().lower()
```

- [ ] **Step 9.2: Run tests (fails — templates missing)**

Run: `uv run pytest tests/test_templates.py -v`
Expected: FAIL `TemplateNotFound: base.html`.

- [ ] **Step 9.3: Write `build/templates/base.html`**

```jinja
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <meta name="description" content="{% block meta_description %}Pred-Oracle — vertical compliance intelligence for prediction-market operators.{% endblock %}">
  <title>{% block title %}Pred-Oracle{% endblock %}</title>

  <script src="https://cdn.tailwindcss.com"></script>
  <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
  <link rel="stylesheet" href="/static/css/site.css">

  {% block extra_head %}{% endblock %}
</head>
<body class="font-sans bg-white text-slate-900 antialiased">
  <nav class="border-b border-slate-200 bg-white sticky top-0 z-10">
    <div class="max-w-6xl mx-auto px-4 py-4 flex items-center justify-between">
      <a href="/" class="font-bold text-lg tracking-tight">Pred-Oracle</a>
      <span class="text-xs uppercase tracking-wider text-slate-500 bg-slate-100 px-2 py-1 rounded">Demo</span>
    </div>
  </nav>

  <main class="max-w-6xl mx-auto px-4 py-12">
    {% block content %}{% endblock %}
  </main>

  <footer class="border-t border-slate-200 mt-24 py-8 text-sm text-slate-500">
    <div class="max-w-6xl mx-auto px-4">
      Pred-Oracle demo built on Carver regulatory annotations. Synthetic platform context labelled where applicable. Real persons / events linked to public sources.
    </div>
  </footer>

  {% block extra_body %}{% endblock %}
</body>
</html>
```

- [ ] **Step 9.4: Write `build/templates/landing.html`**

```jinja
{% extends "base.html" %}

{% block title %}Pred-Oracle — Regulatory Intelligence for Prediction Markets{% endblock %}

{% block content %}
<section class="mb-16 max-w-3xl">
  <h1 class="text-4xl font-bold tracking-tight leading-tight">
    Your business sits at the intersection of the CFTC, 50 state gambling commissions,
    the SEC, and every foreign regulator that touches event contracts.
  </h1>
  <p class="mt-6 text-xl text-slate-600">
    Pred-Oracle is the regulatory-intelligence layer built for that intersection.
  </p>
  <p class="mt-4 text-sm text-slate-500">
    Backed by
    <span class="font-semibold text-slate-700">{{ events_count|default(0) }}</span> annotated regulatory events
    across <span class="font-semibold text-slate-700">{{ jurisdictions_count|default(0) }}</span> jurisdictions and
    <span class="font-semibold text-slate-700">{{ unique_regulators_count|default(0) }}</span> regulatory bodies
    {% if earliest_pub_date and latest_pub_date %}
      ({{ earliest_pub_date }} → {{ latest_pub_date }}).
    {% endif %}
  </p>
</section>

<section>
  <h2 class="text-sm uppercase tracking-wider text-slate-500 mb-4">
    Walk three scenes — about 15 minutes
  </h2>
  <div class="grid grid-cols-1 md:grid-cols-3 gap-6">
    <a href="/alpha/" class="scene-tile block p-6 border border-slate-200 rounded-lg hover:border-blue-500 hover:shadow-md transition">
      <div class="text-xs uppercase tracking-wider text-blue-600 font-semibold">Scene 1 — α</div>
      <div class="text-xl font-bold mt-2">The GC's Monday morning</div>
      <p class="text-slate-600 mt-2 text-sm">Triage real regulatory signals before they hit the news cycle.</p>
      <div class="mt-4 text-xs text-slate-400">Coming soon</div>
    </a>

    <a href="/gamma/" class="scene-tile block p-6 border border-slate-200 rounded-lg hover:border-blue-500 hover:shadow-md transition">
      <div class="text-xs uppercase tracking-wider text-blue-600 font-semibold">Scene 2 — γ</div>
      <div class="text-xl font-bold mt-2">Before you list, look</div>
      <p class="text-slate-600 mt-2 text-sm">Pre-listing scan plus the regulatory timeline behind a real contract.</p>
      <div class="mt-4 text-xs text-slate-400">Coming soon</div>
    </a>

    <a href="/beta/" class="scene-tile block p-6 border border-slate-200 rounded-lg hover:border-blue-500 hover:shadow-md transition">
      <div class="text-xs uppercase tracking-wider text-blue-600 font-semibold">Scene 3 — β</div>
      <div class="text-xl font-bold mt-2">Q3 planning, without the surprise</div>
      <p class="text-slate-600 mt-2 text-sm">Heat-map and quarterly intelligence for jurisdictional strategy.</p>
      <div class="mt-4 text-xs text-slate-400">Coming soon</div>
    </a>
  </div>
</section>
{% endblock %}
```

- [ ] **Step 9.5: Run tests**

Run: `uv run pytest tests/test_templates.py -v`
Expected: PASS.

- [ ] **Step 9.6: Commit**

```bash
git add build/templates/base.html build/templates/landing.html tests/test_templates.py
git commit -m "Stage 0 Task 9: base + landing templates"
```

---

### Task 10: Scene placeholder + close templates

**Files:**
- Create: `build/templates/alpha/intro.html`
- Create: `build/templates/gamma/intro.html`
- Create: `build/templates/beta/intro.html`
- Create: `build/templates/close.html`

These are tile-deep "coming soon" pages for Stage 0 so the navigation works end-to-end. Stages 1-3 replace these with real scene content.

- [ ] **Step 10.1: Add a placeholder-render test**

Append to `tests/test_templates.py`:

```python
@pytest.mark.parametrize("scene", ["alpha", "gamma", "beta"])
def test_scene_intros_render(env: Environment, scene: str) -> None:
    html = env.get_template(f"{scene}/intro.html").render()
    assert "Coming soon" in html or "Placeholder" in html or "Pred-Oracle" in html
    soup = BeautifulSoup(html, "html.parser")
    assert soup.find("a", href="/") is not None  # back-to-landing link


def test_close_renders(env: Environment) -> None:
    html = env.get_template("close.html").render()
    assert "thank" in html.lower() or "contact" in html.lower() or "next steps" in html.lower()
```

- [ ] **Step 10.2: Run tests (fail — templates missing)**

Run: `uv run pytest tests/test_templates.py -v`
Expected: FAIL `TemplateNotFound` on the 4 new templates.

- [ ] **Step 10.3: Write the three scene-intro placeholders**

Each follows this skeleton, swapping `{{ scene }}` and copy. E.g., `build/templates/alpha/intro.html`:

```jinja
{% extends "base.html" %}
{% block title %}Scene 1 — α — Pred-Oracle{% endblock %}
{% block content %}
<section class="max-w-3xl">
  <div class="text-xs uppercase tracking-wider text-blue-600 font-semibold">Scene 1 — α</div>
  <h1 class="text-3xl font-bold mt-2">The GC's Monday morning</h1>
  <p class="mt-4 text-slate-600">
    This scene is under construction. Stage 1 of the demo build adds the triage queue,
    ticket detail, jurisdictional dashboard, and audit-log export preview.
  </p>
  <p class="mt-8">
    <a href="/" class="text-blue-600 hover:underline">← Back to landing</a>
  </p>
</section>
{% endblock %}
```

`build/templates/gamma/intro.html` and `build/templates/beta/intro.html` are the same shape with scene-2 / scene-3 copy from `docs/specs/00-demo-scope.md` § 2.3 and § 2.4.

- [ ] **Step 10.4: Write `build/templates/close.html`**

```jinja
{% extends "base.html" %}
{% block title %}Pred-Oracle Demo — Next Steps{% endblock %}
{% block content %}
<section class="max-w-2xl">
  <h1 class="text-3xl font-bold">Thank you for walking the demo.</h1>
  <p class="mt-4 text-slate-600">
    Every signal you saw came from Carver's regulatory-annotation pipeline. Your production
    deployment would pull live across the regulators relevant to your business.
  </p>
  <div class="mt-8 p-6 border border-slate-200 rounded-lg">
    <div class="text-sm uppercase tracking-wider text-slate-500">Next steps</div>
    <p class="mt-2">Reach out to discuss a live data feed and design-partner terms.</p>
  </div>
  <p class="mt-8">
    <a href="/" class="text-blue-600 hover:underline">← Back to landing</a>
  </p>
</section>
{% endblock %}
```

- [ ] **Step 10.5: Run tests**

Run: `uv run pytest tests/test_templates.py -v`
Expected: PASS on all template tests.

- [ ] **Step 10.6: Commit**

```bash
git add build/templates/alpha/intro.html build/templates/gamma/intro.html build/templates/beta/intro.html build/templates/close.html tests/test_templates.py
git commit -m "Stage 0 Task 10: scene placeholders + close page"
```

---

### Task 11: Static assets

**Files:**
- Create: `build/static/css/site.css`
- Create: `build/static/js/site.js`
- Create: `build/static/img/.gitkeep`

Stage 0's CSS / JS is minimal. Tailwind handles 99% of styling via CDN.

- [ ] **Step 11.1: Write `build/static/css/site.css`**

```css
/* Custom utilities that go beyond Tailwind defaults.
 * Tailwind CDN inlines defaults; this file overrides or adds. */

:root {
  --brand-primary: #0f172a;
  --brand-accent: #2563eb;
}

body {
  font-family: 'Inter', system-ui, -apple-system, BlinkMacSystemFont, sans-serif;
}

/* Smooth focus rings for accessibility */
:focus-visible {
  outline: 2px solid var(--brand-accent);
  outline-offset: 2px;
  border-radius: 4px;
}

/* Print rules for the future quarterly-report page */
@media print {
  nav, footer { display: none; }
  main { max-width: none; padding: 0; }
}
```

- [ ] **Step 11.2: Write `build/static/js/site.js`**

```javascript
// Stage 0 needs no client-side JS. This file exists so the static dir
// has a stable structure for later stages to extend.
console.debug('Pred-Oracle demo loaded.');
```

- [ ] **Step 11.3: Add img placeholder**

```bash
mkdir -p build/static/img
touch build/static/img/.gitkeep
```

- [ ] **Step 11.4: Commit**

```bash
git add build/static/
git commit -m "Stage 0 Task 11: static asset scaffold"
```

---

### Task 12: Build orchestrator

**Files:**
- Create: `build/generate.py`
- Create: `tests/test_generate.py`

Walks `build/templates/`, renders each via Jinja2 with the matching slice, writes to `site/`.

- [ ] **Step 12.1: Write integration test**

`tests/test_generate.py`:

```python
"""Integration test: generate.py produces a complete site/ directory."""

import shutil
from pathlib import Path

from build.generate import build_site


def test_build_produces_all_pages(tmp_path: Path) -> None:
    repo_root = Path(__file__).parent.parent
    site_out = tmp_path / "site"

    build_site(repo_root=repo_root, out_dir=site_out)

    # Top-level pages exist
    assert (site_out / "index.html").exists()
    assert (site_out / "close.html").exists()

    # Scene placeholders exist
    for scene in ("alpha", "gamma", "beta"):
        assert (site_out / scene / "index.html").exists(), f"{scene}/index.html missing"

    # Static assets copied
    assert (site_out / "static" / "css" / "site.css").exists()
    assert (site_out / "static" / "js" / "site.js").exists()
```

- [ ] **Step 12.2: Run test (fails)**

Run: `uv run pytest tests/test_generate.py -v`
Expected: FAIL `ModuleNotFoundError`.

- [ ] **Step 12.3: Implement `build/generate.py`**

```python
"""Site builder: render Jinja2 templates with their slice JSON into site/.

Mapping convention:
- templates/landing.html       → site/index.html       (loads page_data/landing.json)
- templates/close.html         → site/close.html
- templates/<scene>/intro.html → site/<scene>/index.html
- templates/<scene>/<page>.html → site/<scene>/<page>/index.html

Static dir copied verbatim: build/static/ → site/static/.
"""

from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader, select_autoescape


def _load_slice(repo_root: Path, slice_name: str) -> dict[str, Any]:
    slice_path = repo_root / "build" / "page_data" / f"{slice_name}.json"
    if slice_path.exists():
        return json.loads(slice_path.read_text())
    return {}


def _route_for_template(rel_path: Path) -> Path:
    """Map a template relative path to its site output relative path.

    landing.html → index.html
    close.html → close.html
    alpha/intro.html → alpha/index.html
    alpha/inbox.html → alpha/inbox/index.html  (future stages)
    """
    parts = rel_path.parts
    stem = rel_path.stem

    if rel_path == Path("landing.html"):
        return Path("index.html")
    if len(parts) == 1:
        return rel_path  # e.g., close.html
    # Subdirectory case
    if stem == "intro":
        return Path(*parts[:-1]) / "index.html"
    return Path(*parts[:-1]) / stem / "index.html"


def build_site(repo_root: Path, out_dir: Path) -> None:
    templates_dir = repo_root / "build" / "templates"
    static_dir = repo_root / "build" / "static"

    if out_dir.exists():
        shutil.rmtree(out_dir)
    out_dir.mkdir(parents=True)

    env = Environment(
        loader=FileSystemLoader(str(templates_dir)),
        autoescape=select_autoescape(["html"]),
    )

    for tpl_path in templates_dir.rglob("*.html"):
        rel = tpl_path.relative_to(templates_dir)
        # Skip partials (_components)
        if any(p.startswith("_") for p in rel.parts):
            continue
        slice_name = rel.with_suffix("").as_posix().replace("/", "_")
        # Special-case landing slice name
        if rel == Path("landing.html"):
            slice_name = "landing"
        ctx = _load_slice(repo_root, slice_name)

        rendered = env.get_template(rel.as_posix()).render(**ctx)
        out_path = out_dir / _route_for_template(rel)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(rendered)
        print(f"Rendered {rel} → {out_path.relative_to(out_dir)}")

    # Copy static dir
    shutil.copytree(static_dir, out_dir / "static", dirs_exist_ok=True)
    print(f"Copied static assets to {out_dir / 'static'}")


def main() -> int:
    repo_root = Path(__file__).parent.parent
    build_site(repo_root, repo_root / "site")
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 12.4: Run tests**

Run: `uv run pytest tests/test_generate.py -v`
Expected: PASS.

- [ ] **Step 12.5: Run actual build**

Run: `uv run python build/generate.py`
Expected: writes `site/` with `index.html`, `close.html`, `alpha/index.html`, `gamma/index.html`, `beta/index.html`, `static/` copied. Inspect `site/` tree.

- [ ] **Step 12.6: Local preview**

Run: `cd site && python -m http.server 8000` (in another terminal)
Open `http://localhost:8000` in a browser. Verify landing page renders with counts, three tiles are visible and clickable, scene pages load with placeholder copy. `Ctrl-C` the server when done.

- [ ] **Step 12.7: Commit**

```bash
git add build/generate.py tests/test_generate.py
git commit -m "Stage 0 Task 12: build orchestrator"
```

---

### Task 13: Makefile

**Files:**
- Create: `Makefile`

- [ ] **Step 13.1: Write the Makefile**

```makefile
.PHONY: pull pull-carver pull-kalshi pull-polymarket slice build serve clean test lint

# Pull all data sources (run rarely; outputs are checked in)
pull: pull-carver pull-kalshi pull-polymarket

pull-carver:
	uv run python build/pull_carver.py

pull-kalshi:
	uv run python build/pull_kalshi.py

pull-polymarket:
	uv run python build/pull_polymarket.py

# Compute page slices from data/ (run after data/ edits)
slice:
	uv run python build/generate_slices.py

# Build deployable site/ (default daily command)
build: slice
	uv run python build/generate.py

# Local preview
serve: build
	cd site && python -m http.server 8000

# Run tests
test:
	uv run pytest -v

# Lint
lint:
	uv run ruff check build tests
	uv run ruff format --check build tests

# Clean generated output
clean:
	rm -rf build/page_data site .pytest_cache .ruff_cache .mypy_cache
```

- [ ] **Step 13.2: Verify make targets**

Run: `make clean && make build && ls site/`
Expected: clean wipes, build produces, listing shows `index.html`, `close.html`, `alpha/`, `gamma/`, `beta/`, `static/`.

- [ ] **Step 13.3: Verify test target**

Run: `make test`
Expected: all pytest tests pass.

- [ ] **Step 13.4: Commit**

```bash
git add Makefile
git commit -m "Stage 0 Task 13: Makefile"
```

---

### Task 14: GitHub Actions deploy workflow

**Files:**
- Create: `.github/workflows/deploy.yml`

- [ ] **Step 14.1: Write the workflow**

```yaml
name: Build and Deploy

on:
  push:
    branches: [main]
  pull_request:
    branches: [main]

jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Set up Python 3.10
        uses: actions/setup-python@v5
        with:
          python-version: "3.10"

      - name: Install uv
        run: pip install uv

      - name: Sync dependencies
        run: uv sync --extra dev

      - name: Lint
        run: |
          uv run ruff check build tests
          uv run ruff format --check build tests

      - name: Test
        run: uv run pytest -v

      - name: Build site
        run: make build

      - name: Upload artifact
        if: github.ref == 'refs/heads/main'
        uses: actions/upload-pages-artifact@v3
        with:
          path: site

  deploy:
    if: github.ref == 'refs/heads/main'
    needs: build
    runs-on: ubuntu-latest
    permissions:
      pages: write
      id-token: write
    environment:
      name: github-pages
      url: ${{ steps.deployment.outputs.page_url }}
    steps:
      - name: Deploy to GitHub Pages
        id: deployment
        uses: actions/deploy-pages@v4
```

- [ ] **Step 14.2: Configure GitHub Pages in repo settings**

In the GitHub UI: Settings → Pages → Source = "GitHub Actions". (One-time setup; cannot be scripted from here.)

- [ ] **Step 14.3: Commit and push**

```bash
mkdir -p .github/workflows
git add .github/workflows/deploy.yml
git commit -m "Stage 0 Task 14: GitHub Actions deploy workflow"
```

Push to your fork / branch later (Task 15 verifies deploy).

---

### Task 15: Stage 0 acceptance dry-run

**Files:**
- Modify: `docs/specs/00-demo-scope.md` (mark Stage 0 done if all checks pass)

This task validates the Stage 0 acceptance criteria from [`docs/specs/20-site-build.md`](../../specs/20-site-build.md) § 9.

- [ ] **Step 15.1: Clean-checkout reproducibility**

```bash
git clean -fdx -e .env -e data/  # keep .env + already-pulled data
uv sync --extra dev
time make build
```

Expected: complete in < 5 minutes. (Cold cache may be slower the first time; record actual.)

- [ ] **Step 15.2: All tests pass**

Run: `make test`
Expected: 100% passing. No skipped tests except those gated on missing API keys (acceptable).

- [ ] **Step 15.3: Lint clean**

Run: `make lint`
Expected: no errors. Fix any reported issues.

- [ ] **Step 15.4: Local preview review**

Run: `make serve` and open `localhost:8000`. Click through:
- Landing → tile → scene placeholder → back to landing.
- Verify the headline counts on landing render real numbers (not 0).
- Inspect mobile responsive layout (Chrome DevTools device emulation).

- [ ] **Step 15.5: Push and verify GH Pages deploys**

Once on `main`, push and watch the GitHub Actions tab. The deploy job should publish to `https://<org>.github.io/pred-oracle/`. Open the URL; verify it matches local.

- [ ] **Step 15.6: Lighthouse audit**

In Chrome DevTools on the deployed landing page, run a Lighthouse audit (Performance + Accessibility + SEO).
Expected: each category ≥ 90.

Common fixes if a category is < 90:
- Performance: defer / async non-critical scripts; add `<link rel="preconnect">` for CDN domains.
- Accessibility: add `alt` attrs; ensure color contrast on text over slate-100 backgrounds; add `aria-label` to icon-only links.
- SEO: ensure `<meta name="description">`, `<title>`, and a `robots` meta are set.

- [ ] **Step 15.7: Document Stage 0 completion**

Append to `docs/specs/00-demo-scope.md` § 5 staging table, on the Stage 0 row, in the "Done when" column: `✅ 2026-MM-DD — deployed at <url>; Lighthouse <P>/<A>/<S>; build time <m:ss>.`

- [ ] **Step 15.8: Commit acceptance markers**

```bash
git add docs/specs/00-demo-scope.md
git commit -m "Stage 0 Task 15: acceptance dry-run passed; Stage 0 ready"
```

---

## Stage 0 → Stage 1 Handoff

Stage 0 is done when Task 15 is complete. At that point, the next plan
(`2026-MM-DD-stage-1-alpha.md`) can be written. It reads:

- `data/carver-events.json` — the full annotated corpus.
- `data/dp1-findings.md` — chosen annotation path (drives α slice generation).
- `data/platforms/kalshi/contracts_raw.json` — usable as input to γ later.

If DP1 finding is Case B (raw entries, need Claude), Task 5 of Stage 1 will
add the per-entry Claude annotation step. Plan accordingly.

---

## Self-Review Checklist

Before declaring this plan ready:

- [ ] Every task has files-touched + at least one test + a commit step.
- [ ] No placeholders ("TODO", "TBD", "implement appropriate") in any task body.
- [ ] All cited spec sections (`docs/specs/*.md`) exist and contain the referenced content.
- [ ] Test function names and module paths are consistent across tasks.
- [ ] The implementation order doesn't reference functions before they're defined (Task 4 sets up DP1 finding, which Task 5 reads).
- [ ] No task requires a service we haven't acknowledged in prerequisites.
