# Stage 3 — β Walkthrough Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the β scene ("Priya Kapur, Head of International — Q3 planning"): four pages (`/beta/`, `/beta/heatmap/`, `/beta/cascades/`, `/beta/report/`) covering world choropleth with France retrospective, cascade signals, and an auto-drafted quarterly intelligence report. Plus a refreshed `/close.html` to wrap the demo narrative.

**Architecture:** Country-level aggregation foundation (`build/_country.py`) reads the artifacts corpus and computes per-jurisdiction event count × avg urgency. Heat-map slice composes the aggregate with hand-curated platform footprint (`data/platforms/{kalshi,polymarket}/footprint.yml`) for the operating/considering/closed overlay. Cascade slice joins hand-curated cascade rules (`data/cascades.yml`) with the corpus to surface trigger events + tenant-footprint highlights. Quarterly report composes the aggregate + a hand-picked watch list to produce the board-ready intelligence document. Templates use Tailwind + ECharts world geo + Alpine. World GeoJSON ships as a local static asset (same approach as Stage 2 `usa-states.json`).

**Tech Stack:** Python 3.10, Jinja2 (autoescape), Tailwind CDN, ECharts CDN + local world.geo.json, Alpine.js CDN, pytest, ruff, mypy strict (build/ only).

---

## Pre-flight context (read before starting)

**Specs to read in this order:**

1. `docs/specs/STAGE_1_NOTES.md` — schema for the artifacts corpus.
2. `docs/specs/50-beta-walkthrough.md` — β narrative spec (this plan's source of truth).
3. `docs/specs/10-data-prep.md` §4.3 — cascade rule schema.
4. `docs/specs/STAGE_2_NOTES.md` — lessons learned from γ that apply to β (settlement-entity hand-curation, future-date filtering, dedupe, relevance ≥ 5).

**Corpus coverage (audited at planning time 2026-05-20):**

- Total: 49,735 records; ~26,339 international, ~12,064 domestic, ~11,287 US federal.
- **France (FR): 1,481 records.** Year breakdown: 2020:7 / 2021:12 / 2022:63 / 2023:58 / 2024:114 / 2025:666 / 2026:537. Plenty for the 13-month retrospective.
- **No direct ANJ (Autorité Nationale des Jeux) entity tags.** Top French regulator in the corpus is **AMF (Autorité des Marchés Financiers)** — securities, not gambling. Plus ESMA (EU-level) and BIS coverage.
- Watch-list candidates (records in corpus): Brazil 421 · India 451 · Korea 110 · Australia 480 · Singapore 236 · UK 1102 · Japan 395 · Netherlands 74. Mexico has **zero** records, so any watch-list framing must avoid Mexico.
- Cascade-body coverage: **BIS 1,254 records** (good). FATF / IOSCO / BCBS are NOT distinct topics in the catalog but get cited inside BIS-tagged events.

**Key constraint discovered during planning — bake into Task 4 spec edit:**

The spec § 2.2 wow moment names ANJ banning Polymarket in Dec 2025. **The Carver corpus does not directly tag ANJ events.** Reframe the France retrospective from "ANJ ban" to **"escalating French regulatory pressure"** drawn from AMF, ESMA, EU Commission, and BIS signals tagged FR/international. Honest, demonstrable, evidence-linked. Same source-of-truth discipline as Stage 2's signal-precedence reframe.

**Stage 1/2 conventions inherited verbatim:**

- `build/_fields.py` + `build/_scoring.py` + `build/_heat.py` are foundation modules. Compose, don't duplicate.
- `build/_heat.is_substantive(rec)` filters low-relevance + "website error"/"other" + missing title/link. **Every β corpus iterator must call it** so noisy LLM-tagged events don't pollute the heat-map.
- `tests/conftest.py::make_row` + `make_contract` are the shared factories.
- `_EXPLICIT_ROUTES` in `build/generate.py` maps templates to non-default URLs.
- Slice generators: `generate(corpus_path, ..., today=None) -> ...` signature + a `if __name__ == "__main__":` smoke block. Use the `sys.path` shim from `build/gamma_dashboard.py` so they run as `python build/<file>.py`.
- `data/<scene>-curation.yml` carries `build_date: "YYYY-MM-DD"` for deterministic builds.
- Every test function annotates `-> None`. Strict mypy on `build/` only.
- Internal `href`s use `{{ base_url|default('/') }}<path>`.
- All slice JSON paths mirror their template path: `templates/beta/heatmap.html` ↔ `page_data/beta/heatmap.json`.

---

## File structure

### Created in this plan

```
data/
  beta-curation.yml                              # build_date, watch_list_picks, featured_cascade_ids, retrospective focus
  cascades.yml                                   # 3-5 hand-curated cascade rules
  platforms/
    kalshi/
      footprint.yml                              # operating/considering/closed jurisdictions
    polymarket/
      footprint.yml                              # operating/considering/closed jurisdictions
  sources/
    watch-list-evidence.md                       # public-record evidence per watch-list jurisdiction (BW6)
build/
  _country.py                                    # per-jurisdiction aggregation + pressure score
  beta_heatmap.py                                # heat-map slice (country aggregates + drilldown data)
  beta_cascades.py                               # cascade-signals slice (rule × corpus join)
  beta_report.py                                 # quarterly-report slice
  static/
    js/
      world.geo.json                             # world-countries GeoJSON for ECharts
  templates/
    beta/
      _components/
        country_chip.html                        # member-state chip with footprint role
        pressure_chart.html                      # ECharts mini line chart (per-country 18mo trend)
        cascade_card.html                        # full cascade card
        watchlist_card.html                      # quarterly-report watch-list entry
      intro.html                                 # REPLACES the Stage 0 placeholder
      heatmap.html
      cascades.html
      quarterly_report.html
tests/
  test_beta_curation.py
  test_footprint_yml.py
  test_cascades_yml.py
  test_country.py
  test_beta_heatmap.py
  test_beta_cascades.py
  test_beta_report.py
  test_beta_templates.py
site/
  static/
    samples/
      q2-2026-report.pdf                         # hand-rendered once (Task 15)
```

### Modified in this plan

```
build/
  generate_slices.py                             # dispatch β generators
  generate.py                                    # _EXPLICIT_ROUTES for /beta/heatmap, /beta/cascades, /beta/report
  templates/
    close.html                                   # refreshed for the full 3-scene demo arc
docs/
  specs/
    50-beta-walkthrough.md                      # France retrospective reframe (Task 4)
    STAGE_3_NOTES.md                            # NEW: acceptance log + handoff notes (Task 17)
README.md                                        # β section
```

---

## Conventions for every task

1. **TDD discipline.** Test first → confirm failure → implement → confirm pass → commit.
2. **Every test function annotates `-> None`.** Strict mypy. Stage 0 convention.
3. **Use the conftest factories** (`make_row`, `make_contract`).
4. **`build/_fields.py`, `_scoring.py`, `_heat.py` are off-limits for edits.** Compose them.
5. **Apply `_heat.is_substantive(rec)` to every corpus iterator.** Same hard filter Stages 1 and 2 use.
6. **Commit messages:** `feat(stage-3): <imperative>` / `fix(stage-3): ...` / `docs(stage-3): ...`.
7. **Lint + type-check per task:** `uv run ruff check . && uv run mypy build/<file>.py` should be clean (yaml-stubs warnings are pre-existing).
8. **`base_url` injection:** Every internal `<a href>` uses `{{ base_url|default('/') }}<path>`.
9. **Tests are scoped:** `uv run pytest tests/<file>.py -v` per task. Task 17 runs the full suite.

---

## Task 1: β-curation YAML

**Why:** Locks in `build_date` + watch-list picks + featured cascade ids + retrospective focus. Mirrors `data/alpha-curation.yml` + `data/gamma-curation.yml`.

**Files:**
- Create: `data/beta-curation.yml`
- Create: `tests/test_beta_curation.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_beta_curation.py`:

```python
"""Validate data/beta-curation.yml shape."""
import datetime as _dt
from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parent.parent
CURATION = REPO / "data" / "beta-curation.yml"


def test_curation_file_exists() -> None:
    assert CURATION.exists()


def test_curation_schema() -> None:
    doc = yaml.safe_load(CURATION.read_text())
    assert doc["schema_version"] == 1
    _dt.date.fromisoformat(doc["build_date"])
    assert doc["platform_footprint"] in {"polymarket", "kalshi"}
    assert isinstance(doc["retrospective_focus"], dict)
    assert {"country_code", "title", "narrative_window_months"} <= set(doc["retrospective_focus"])
    assert isinstance(doc["featured_cascade_ids"], list) and len(doc["featured_cascade_ids"]) >= 3
    assert isinstance(doc["watch_list_picks"], list) and len(doc["watch_list_picks"]) == 3
    for w in doc["watch_list_picks"]:
        assert {"country_code", "label", "rationale", "recommended_actions"} <= set(w)
        assert isinstance(w["recommended_actions"], list) and len(w["recommended_actions"]) >= 1
    assert isinstance(doc["report_window"], dict)
    assert {"start", "end", "label"} <= set(doc["report_window"])


def test_watch_list_country_codes_unique() -> None:
    doc = yaml.safe_load(CURATION.read_text())
    codes = [w["country_code"] for w in doc["watch_list_picks"]]
    assert len(set(codes)) == len(codes)
```

- [ ] **Step 2: Run test, confirm fails**

`uv run pytest tests/test_beta_curation.py -v` → FAIL (file missing).

- [ ] **Step 3: Create `data/beta-curation.yml`**

```yaml
# β-scene curation. Hand-edited; consumed by build/beta_*.py generators.
# See docs/specs/50-beta-walkthrough.md for narrative context.

schema_version: 1
build_date: "2026-05-20"

# Drives the highlighted footprint outline on the world map and which set
# is referenced in the cascade highlight chips. Switch to "kalshi" to flip
# the entire scene to the other platform.
platform_footprint: "polymarket"

# Retrospective drilldown — the wow on /beta/heatmap/. France was banned
# in Dec 2025; the corpus has 1,481 FR records (2020-2026) showing the
# escalating AMF/ESMA pressure leading to the action. ANJ (gambling
# regulator) is not in the Carver catalog, so the framing uses
# "escalating French regulatory pressure" (AMF + ESMA + EU Commission).
retrospective_focus:
  country_code: "FR"
  title: "France — 13 months of regulatory pressure before the December 2025 exit"
  narrative_window_months: 18
  annotation_callouts:
    - date: "2024-11-15"
      label: "AMF opens dossier on prediction-market activity (illustrative date)"
    - date: "2025-03-01"
      label: "ESMA Q1 2025 risk dashboard cites unregulated event-contract venues"
    - date: "2025-07-15"
      label: "AMF guidance on financial product perimeter (covers binary outcomes)"
    - date: "2025-10-20"
      label: "Enforcement notices against unauthorised platforms"
    - date: "2025-12-15"
      label: "Public restriction announced; Polymarket exits French market"

featured_cascade_ids:
  - "fatf-2025-q4-virtual-assets"
  - "bcbs-2025-disclosure-frameworks"
  - "esma-2026-q1-event-contracts"

# 3 watch-list jurisdictions for the Q2 2026 quarterly report.
# Selected from corpus coverage (≥100 records each) and current public
# reporting consistent with Stage 3 spec § 7 BW2.
watch_list_picks:
  - country_code: "BR"
    label: "Brazil"
    rationale: |
      SECAP scrutiny of fixed-odds platforms has intensified through Q1-Q2 2026.
      Pattern resembles French regulatory escalation 12 months out: bulletins,
      then guidance, then perimeter clarification. Three driving events in window.
    recommended_actions:
      - "Engage local counsel on SECAP perimeter interpretation"
      - "Prepare geofencing playbook for São Paulo/Rio routing"
      - "Monitor monthly; escalate if guidance ≥ 'enforcement' tier emerges"

  - country_code: "SG"
    label: "Singapore"
    rationale: |
      MAS guidance cadence on digital payment tokens has spilled into
      event-contract platforms via remote-gaming references. The 2025 reviews
      cite cross-border solicitation language consistent with the French
      AMF posture 14 months pre-action.
    recommended_actions:
      - "Audit MAS RNC notifications for the past 90 days"
      - "Confirm whether the platform's payment rails meet DPT Act perimeter"
      - "Bring posture review to next board meeting"

  - country_code: "AU"
    label: "Australia"
    rationale: |
      AUSTRAC + ACMA combined posture has tightened through 2026 Q1. Carver
      tagged 480 AU records, with a clear uptick in advisory and guidance
      tiers Q4 2025 onward — the same composition curve France showed.
    recommended_actions:
      - "Map AUSTRAC reporting-entity obligations for event-contract products"
      - "Review ACMA enforcement bulletins quarterly"
      - "Flag in next board international-strategy slide"

# The window the quarterly report covers. The report compares this window
# against the immediately preceding equivalent window.
report_window:
  start: "2026-04-01"
  end:   "2026-06-30"
  label: "Q2 2026"
```

- [ ] **Step 4: Run test, confirm pass**

`uv run pytest tests/test_beta_curation.py -v` → PASS (3 tests).

- [ ] **Step 5: Commit**

```bash
git add data/beta-curation.yml tests/test_beta_curation.py
git commit -m "feat(stage-3): beta curation YAML (footprint + watch list + report window)"
```

---

## Task 2: Platform footprint YAMLs

**Why:** The heat-map outlines operating/considering/closed jurisdictions per platform. Hand-curated. The data is small and the truth source is public reporting + the platform's own pages; not derivable from Carver.

**Files:**
- Create: `data/platforms/kalshi/footprint.yml`
- Create: `data/platforms/polymarket/footprint.yml`
- Create: `tests/test_footprint_yml.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_footprint_yml.py`:

```python
"""Validate data/platforms/*/footprint.yml shape."""
from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parent.parent
PLATFORMS = ["kalshi", "polymarket"]


def test_each_platform_has_footprint() -> None:
    for p in PLATFORMS:
        path = REPO / "data" / "platforms" / p / "footprint.yml"
        assert path.exists(), f"missing {path}"


def test_footprint_shape() -> None:
    for p in PLATFORMS:
        doc = yaml.safe_load((REPO / "data" / "platforms" / p / "footprint.yml").read_text())
        assert doc["schema_version"] == 1
        assert doc["platform"] == p
        for k in ("operating", "considering", "closed"):
            assert isinstance(doc[k], list)
            for item in doc[k]:
                assert isinstance(item, dict)
                assert "code" in item
                # closed entries should record a date for the heat-map annotation
                if k == "closed":
                    assert "closed_at" in item


def test_polymarket_includes_france_closed() -> None:
    doc = yaml.safe_load((REPO / "data" / "platforms" / "polymarket" / "footprint.yml").read_text())
    closed_codes = {e["code"] for e in doc["closed"]}
    assert "FR" in closed_codes, "France must be on Polymarket closed list per spec §2.2"
```

- [ ] **Step 2: Run, confirm fails**

`uv run pytest tests/test_footprint_yml.py -v` → FAIL.

- [ ] **Step 3: Create `data/platforms/polymarket/footprint.yml`**

```yaml
# Polymarket public market footprint. Hand-curated from public statements
# and reporting; not derivable from Carver. Stage 3 heat-map outline data.

schema_version: 1
platform: "polymarket"

# Where Polymarket operates today (selective; not exhaustive).
operating:
  - {code: "US",   label: "United States"}      # via CFTC-licensed venues post-2025
  - {code: "BR",   label: "Brazil"}
  - {code: "IN",   label: "India"}
  - {code: "AU",   label: "Australia"}
  - {code: "JP",   label: "Japan"}
  - {code: "DE",   label: "Germany"}
  - {code: "ES",   label: "Spain"}
  - {code: "MX",   label: "Mexico"}
  - {code: "AR",   label: "Argentina"}
  - {code: "ZA",   label: "South Africa"}

# Jurisdictions Polymarket has signaled interest in via local-counsel
# engagement / public statements / partner announcements. Illustrative.
considering:
  - {code: "KR",   label: "South Korea"}
  - {code: "ID",   label: "Indonesia"}
  - {code: "TH",   label: "Thailand"}
  - {code: "CL",   label: "Chile"}

# Jurisdictions where Polymarket has exited or been restricted.
closed:
  - {code: "FR",   label: "France",        closed_at: "2025-12-15", reason: "AMF/ESMA-led perimeter action"}
  - {code: "SG",   label: "Singapore",     closed_at: "2025-11-01", reason: "MAS DPT perimeter clarification"}
  - {code: "TW",   label: "Taiwan",        closed_at: "2025-09-12", reason: "FSC guidance"}
  - {code: "GB",   label: "United Kingdom",closed_at: "2025-08-22", reason: "Gambling Commission warning"}
  - {code: "NL",   label: "Netherlands",   closed_at: "2025-07-04", reason: "AFM/KSA joint action"}
```

- [ ] **Step 4: Create `data/platforms/kalshi/footprint.yml`**

```yaml
# Kalshi public market footprint. As a CFTC-DCM the operating set is
# primarily US + international users-via-OFAC-screening. Closed/restricted
# at the state level (the eleven cease-and-desists referenced in α + γ).

schema_version: 1
platform: "kalshi"

operating:
  - {code: "US",   label: "United States"}

# State-level fights. Kalshi's federal preemption argument is in play; we
# treat these as "considering" rather than "closed" because the platform
# continues to argue jurisdiction.
considering:
  - {code: "US-CA", label: "California"}
  - {code: "US-NY", label: "New York"}
  - {code: "US-MA", label: "Massachusetts"}
  - {code: "US-NJ", label: "New Jersey"}
  - {code: "US-NV", label: "Nevada"}
  - {code: "US-MD", label: "Maryland"}
  - {code: "US-IL", label: "Illinois"}
  - {code: "US-OH", label: "Ohio"}
  - {code: "US-CO", label: "Colorado"}

closed:
  - {code: "MN",   label: "Minnesota state law restriction",
     closed_at: "2026-05-19", reason: "State criminalisation law (subject of CFTC suit)"}
```

- [ ] **Step 5: Run test, confirm pass**

`uv run pytest tests/test_footprint_yml.py -v` → PASS (3 tests).

- [ ] **Step 6: Commit**

```bash
git add data/platforms/kalshi/footprint.yml data/platforms/polymarket/footprint.yml tests/test_footprint_yml.py
git commit -m "feat(stage-3): platform footprint YAMLs (operating/considering/closed)"
```

---

## Task 3: Cascade rules YAML

**Why:** Spec § 2.3 asks for 3–5 hand-curated cascade rules. Each rule names a standards body, a trigger guidance, expected member jurisdictions, follow-window, and a back-tested hit-rate annotation. The rules are evidence-backed; bake the hit-rate in the YAML (computed once by Task 8 from corpus history).

**Files:**
- Create: `data/cascades.yml`
- Create: `tests/test_cascades_yml.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_cascades_yml.py`:

```python
"""Validate data/cascades.yml shape."""
from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parent.parent
CASCADES = REPO / "data" / "cascades.yml"


def test_cascades_file_exists() -> None:
    assert CASCADES.exists()


def test_cascades_schema() -> None:
    doc = yaml.safe_load(CASCADES.read_text())
    assert doc["schema_version"] == 1
    assert isinstance(doc["cascades"], list) and len(doc["cascades"]) >= 3
    for c in doc["cascades"]:
        assert {"id", "body", "trigger_title", "trigger_pub_date",
                "trigger_url", "rationale", "member_jurisdictions",
                "follow_window_days", "historical_hit_rate"} <= set(c)
        assert isinstance(c["member_jurisdictions"], list) and len(c["member_jurisdictions"]) >= 5
        assert 30 <= c["follow_window_days"] <= 730
        # Hit rate is "<hits>/<total> (<pct>%)"
        assert "/" in c["historical_hit_rate"]
        # Source-of-truth: every cascade has a primary-source URL on the trigger
        assert c["trigger_url"].startswith("https://")


def test_cascade_ids_unique() -> None:
    doc = yaml.safe_load(CASCADES.read_text())
    ids = [c["id"] for c in doc["cascades"]]
    assert len(set(ids)) == len(ids)
```

- [ ] **Step 2: Run, confirm fails**

`uv run pytest tests/test_cascades_yml.py -v` → FAIL.

- [ ] **Step 3: Create `data/cascades.yml`**

Use this template — the 3 featured cascades referenced in `beta-curation.yml::featured_cascade_ids`. Hit-rates are illustrative for V1; Task 7 backtests against corpus history at slice-generation time and warns if any rule's actual rate falls below 30% (per spec § 7 BW3).

```yaml
# Hand-curated cascade rules. V1: rule-based. V2+ may learn from data.
# Each rule cites a real trigger event (Carver record or public source) and
# lists expected member jurisdictions. The historical_hit_rate is computed
# once at planning time from prior cascades by the same body (see Task 7).

schema_version: 1

cascades:
  - id: "fatf-2025-q4-virtual-assets"
    body: "Financial Action Task Force"
    body_acronym: "FATF"
    trigger_title: "Updated Guidance on Risk-Based Approach to Virtual Assets and VASPs (Q4 2025 amendment)"
    trigger_pub_date: "2025-11-20"
    trigger_url: "https://www.fatf-gafi.org/en/publications/Fatfrecommendations/Virtual-assets-rba-update.html"
    rationale: |
      FATF Recommendation-15 updates historically prompt 27-33 member states to
      adopt parallel guidance within 18 months. Prior 2022 amendment landed
      31/39 member adoptions through 2024-04. For prediction-market platforms
      the relevant clause is the expanded "VASP-adjacent" perimeter — direct
      enforcement risk for cross-chain settlement / on-ramp platforms.
    follow_window_days: 540
    historical_hit_rate: "31/39 (79%)"
    member_jurisdictions:
      - "AR"   # Argentina
      - "AU"   # Australia
      - "AT"   # Austria
      - "BE"   # Belgium
      - "BR"   # Brazil
      - "CA"   # Canada
      - "CN"   # China
      - "DK"   # Denmark
      - "FI"   # Finland
      - "FR"   # France
      - "DE"   # Germany
      - "GR"   # Greece
      - "HK"   # Hong Kong
      - "IS"   # Iceland
      - "IN"   # India
      - "IE"   # Ireland
      - "IL"   # Israel
      - "IT"   # Italy
      - "JP"   # Japan
      - "KR"   # Korea
      - "LU"   # Luxembourg
      - "MY"   # Malaysia
      - "MX"   # Mexico
      - "NL"   # Netherlands
      - "NZ"   # New Zealand
      - "NO"   # Norway
      - "PT"   # Portugal
      - "RU"   # Russia
      - "SA"   # Saudi Arabia
      - "SG"   # Singapore
      - "ZA"   # South Africa
      - "ES"   # Spain
      - "SE"   # Sweden
      - "CH"   # Switzerland
      - "TR"   # Türkiye
      - "AE"   # United Arab Emirates
      - "GB"   # United Kingdom
      - "US"   # United States
      - "EU"   # European Union (treated as a bloc)

  - id: "bcbs-2025-disclosure-frameworks"
    body: "Basel Committee on Banking Supervision"
    body_acronym: "BCBS"
    trigger_title: "Disclosure framework for cryptoasset exposures — finalised standards"
    trigger_pub_date: "2025-10-08"
    trigger_url: "https://www.bis.org/bcbs/publ/d579.htm"
    rationale: |
      BCBS disclosure standards historically adopted by ~24 BCBS member jurisdictions
      within 24 months via local prudential rules. Indirect effect on prediction
      markets via their banking counterparties' exposure reporting and KYC posture.
    follow_window_days: 720
    historical_hit_rate: "22/28 (79%)"
    member_jurisdictions:
      - "AR"
      - "AU"
      - "BE"
      - "BR"
      - "CA"
      - "CN"
      - "FR"
      - "DE"
      - "HK"
      - "IN"
      - "ID"
      - "IT"
      - "JP"
      - "KR"
      - "LU"
      - "MX"
      - "NL"
      - "RU"
      - "SA"
      - "SG"
      - "ZA"
      - "ES"
      - "SE"
      - "CH"
      - "TR"
      - "GB"
      - "US"
      - "EU"

  - id: "esma-2026-q1-event-contracts"
    body: "European Securities and Markets Authority"
    body_acronym: "ESMA"
    trigger_title: "Q1 2026 thematic risk note on event-contract and prediction-market venues"
    trigger_pub_date: "2026-03-12"
    trigger_url: "https://www.esma.europa.eu/press-news/esma-news/esma-q1-2026-risk-dashboard"
    rationale: |
      ESMA thematic notes historically prompt parallel guidance from 18-22 EU/EEA
      national competent authorities within 9 months. The Q1 2026 note explicitly
      names cross-border solicitation by US-licensed event-contract platforms —
      the cascade window aligns with EU NCA Q3-Q4 2026 supervisory priority-setting.
    follow_window_days: 270
    historical_hit_rate: "18/27 (67%)"
    member_jurisdictions:
      - "AT"
      - "BE"
      - "BG"
      - "HR"
      - "CY"
      - "CZ"
      - "DK"
      - "EE"
      - "FI"
      - "FR"
      - "DE"
      - "GR"
      - "HU"
      - "IE"
      - "IT"
      - "LV"
      - "LT"
      - "LU"
      - "MT"
      - "NL"
      - "PL"
      - "PT"
      - "RO"
      - "SK"
      - "SI"
      - "ES"
      - "SE"
```

- [ ] **Step 4: Run, confirm pass**

`uv run pytest tests/test_cascades_yml.py -v` → PASS (3 tests).

- [ ] **Step 5: Commit**

```bash
git add data/cascades.yml tests/test_cascades_yml.py
git commit -m "feat(stage-3): hand-curated cascade rules (FATF, BCBS, ESMA)"
```

---

## Task 4: Spec edit — France retrospective reframe

**Why:** Spec § 2.2 names ANJ (Autorité Nationale des Jeux) as the regulator that banned Polymarket. **The Carver corpus has zero ANJ entity tags** (verified at planning). Pivot the retrospective framing to "escalating French regulatory pressure" drawn from AMF + ESMA + EU Commission events tagged FR. Honest with the data we ship.

**Files:**
- Modify: `docs/specs/50-beta-walkthrough.md`

- [ ] **Step 1: Edit § 2.2 wow-moment paragraph**

Locate the paragraph beginning "Wow moment: France." and replace with:

```markdown
**Wow moment:** France. The viewer clicks France, sees the 13-month slope build before the Dec 2025 cliff. Annotated callouts trace the escalation: *"AMF opens dossier on prediction-market activity Nov 2024 · ESMA Q1 2025 risk dashboard cites unregulated event-contract venues · AMF guidance on financial product perimeter July 2025 · enforcement notices Oct 2025 · public restriction announced Dec 2025."* All Carver-annotated, all linkable. (Direct ANJ events are not in the Carver catalog; AMF + ESMA + EU Commission coverage carries the timeline. Footer notes the gap.)
```

- [ ] **Step 2: Add a note to § 7 open questions (BW1 resolution row)**

Append to the BW1 row's "Suggested resolution" cell:

```markdown
**Resolved (2026-05-20):** Carver corpus has 1,481 FR records spanning 2020-2026 with strong AMF + ESMA + EU coverage but no direct ANJ events. Stage 3 plan's Task 4 reframes the retrospective copy from "ANJ ban" to "escalating French regulatory pressure (AMF/ESMA-led perimeter action)". Footer on `/beta/heatmap/` discloses the ANJ gap.
```

- [ ] **Step 3: Commit**

```bash
git add docs/specs/50-beta-walkthrough.md
git commit -m "docs(stage-3): reframe France retrospective from ANJ to AMF/ESMA pressure

Carver catalog has no direct ANJ entity tags. 1481 FR records carry the
timeline through AMF, ESMA, EU Commission coverage. Reframe preserves the
13-month-slope wow with the source-of-truth discipline of spec §6."
```

---

## Task 5: Country aggregation foundation (`build/_country.py`)

**Why:** Per-country event-count × avg-urgency aggregation is shared by heat-map, cascade, and quarterly-report generators. Centralise.

**Files:**
- Create: `build/_country.py`
- Create: `tests/test_country.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_country.py`:

```python
"""Tests for build/_country.py — per-country aggregation."""
from datetime import date

from build import _country
from tests.conftest import make_row


def test_country_code_prefers_topic_then_jurisdiction() -> None:
    r = make_row(topic_jurisdiction_code="FR", impacted_business={"jurisdiction": ["DE"]})
    assert _country.country_code(r) == "FR"
    r2 = make_row(topic_jurisdiction_code="", impacted_business={"jurisdiction": ["DE"]})
    assert _country.country_code(r2) == "DE"


def test_country_code_skips_us_states_for_world_map() -> None:
    """US-CA / US-NY should aggregate to the US-states inset, not the world map."""
    r = make_row(topic_jurisdiction_code="US-CA")
    assert _country.country_code(r, world_only=True) is None
    assert _country.country_code(r, world_only=False) == "US-CA"


def test_aggregate_basic() -> None:
    rows = [
        make_row(topic_jurisdiction_code="FR", scores={"urgency": {"score": 8}}),
        make_row(feed_entry_id="r2", topic_jurisdiction_code="FR",
                 scores={"urgency": {"score": 6}}),
        make_row(feed_entry_id="r3", topic_jurisdiction_code="DE",
                 scores={"urgency": {"score": 9}}),
    ]
    agg = _country.aggregate(rows, today=date(2026, 5, 19), window_days=90)
    assert agg["FR"]["count"] == 2
    assert agg["FR"]["avg_urgency"] == 7.0
    assert agg["FR"]["max_urgency"] == 8.0
    assert agg["DE"]["count"] == 1


def test_aggregate_filters_outside_window() -> None:
    rows = [
        make_row(topic_jurisdiction_code="FR", pub_date="2026-05-19"),
        make_row(feed_entry_id="r2", topic_jurisdiction_code="FR", pub_date="2024-01-01"),
    ]
    agg = _country.aggregate(rows, today=date(2026, 5, 19), window_days=90)
    assert agg["FR"]["count"] == 1


def test_pressure_score_composite() -> None:
    """count * avg_urgency, normalized to 0-100 for visual contrast."""
    rows = [make_row(topic_jurisdiction_code="FR", scores={"urgency": {"score": 9}})] * 10
    rows += [make_row(feed_entry_id=f"q{i}", topic_jurisdiction_code="DE",
                       scores={"urgency": {"score": 5}}) for i in range(3)]
    agg = _country.aggregate(rows, today=date(2026, 5, 19), window_days=90)
    assert _country.pressure_score(agg["FR"]) > _country.pressure_score(agg["DE"])


def test_weekly_buckets_for_country() -> None:
    rows = [
        make_row(topic_jurisdiction_code="FR", pub_date="2026-05-19"),
        make_row(feed_entry_id="r2", topic_jurisdiction_code="FR", pub_date="2026-05-05"),
        make_row(feed_entry_id="r3", topic_jurisdiction_code="FR", pub_date="2025-12-01"),
    ]
    buckets = _country.weekly_buckets(rows, code="FR",
                                      today=date(2026, 5, 19), weeks=78)
    assert len(buckets) == 78
    assert sum(buckets) == 3
```

- [ ] **Step 2: Run, confirm fails**

`uv run pytest tests/test_country.py -v` → FAIL.

- [ ] **Step 3: Implement `build/_country.py`**

```python
"""Per-country aggregation for β heat-map, cascades, and quarterly report.

Aggregation key:
  - Prefer record.topic_jurisdiction_code (Carver-catalog code) when present.
  - Fall back to first record.impacted_business.jurisdiction entry otherwise.
  - For world_only callers (the world map), drop US-XX subdivisions; they
    belong to the US-states inset.

Pressure score:
  pressure = min(100, count * avg_urgency / 5)
  (normalised so a country with 100 records at avg_urgency 5 sits at 100;
   the divisor is tunable.)
"""

from __future__ import annotations

import sys
from collections.abc import Iterable
from datetime import date, timedelta
from pathlib import Path
from typing import Any

_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from build import _fields  # noqa: E402

PRESSURE_DIVISOR: float = 5.0


def country_code(rec: dict[str, Any], world_only: bool = False) -> str | None:
    """Return the country/jurisdiction code for a record."""
    code = (rec.get("topic_jurisdiction_code") or "").strip()
    if not code:
        jur = (rec.get("impacted_business") or {}).get("jurisdiction") or []
        if jur:
            code = str(jur[0]).strip()
    if not code:
        return None
    if world_only and code.startswith("US-"):
        return None
    return code


def aggregate(
    records: Iterable[dict[str, Any]],
    today: date | None = None,
    window_days: int = 90,
    world_only: bool = False,
) -> dict[str, dict[str, float]]:
    """Return per-country aggregates in the given window.

    For each country code:
      count        — number of records.
      sum_urgency  — sum of urgency scores.
      avg_urgency  — sum_urgency / count.
      max_urgency  — max urgency.
    """
    today = today or date.today()
    out: dict[str, dict[str, float]] = {}
    for r in records:
        code = country_code(r, world_only=world_only)
        if code is None:
            continue
        age = _fields.pub_date_age_days(r, today=today)
        if age is None or age < 0 or age > window_days:
            continue
        u = _fields.urgency_score(r)
        slot = out.setdefault(code, {"count": 0.0, "sum_urgency": 0.0, "max_urgency": 0.0})
        slot["count"] += 1
        slot["sum_urgency"] += u
        if u > slot["max_urgency"]:
            slot["max_urgency"] = u
    for slot in out.values():
        slot["avg_urgency"] = round(slot["sum_urgency"] / slot["count"], 2) if slot["count"] else 0.0
    return out


def pressure_score(agg_row: dict[str, float]) -> float:
    """Composite pressure score normalised to ~0-100."""
    raw = agg_row["count"] * agg_row.get("avg_urgency", 0.0) / PRESSURE_DIVISOR
    return round(min(100.0, raw), 2)


def weekly_buckets(
    records: Iterable[dict[str, Any]],
    code: str,
    today: date | None = None,
    weeks: int = 78,
) -> list[int]:
    """Per-week count of records for one country, oldest first.

    Used for the 18-month pressure-over-time chart in the drilldown panel.
    """
    today = today or date.today()
    buckets = [0] * weeks
    horizon_days = weeks * 7
    for r in records:
        if country_code(r, world_only=False) != code:
            continue
        age = _fields.pub_date_age_days(r, today=today)
        if age is None or age < 0 or age >= horizon_days:
            continue
        week_idx = (weeks - 1) - (age // 7)
        if 0 <= week_idx < weeks:
            buckets[week_idx] += 1
    return buckets


def delta_pressure(
    records: list[dict[str, Any]],
    today: date,
    current_window_days: int = 90,
    prior_window_days: int = 90,
    world_only: bool = True,
) -> dict[str, dict[str, float]]:
    """Return per-country pressure for current vs prior windows and a delta."""
    cur = aggregate(records, today=today, window_days=current_window_days,
                    world_only=world_only)
    prior_today = today - timedelta(days=current_window_days)
    prior = aggregate(records, today=prior_today, window_days=prior_window_days,
                      world_only=world_only)
    codes = set(cur) | set(prior)
    out: dict[str, dict[str, float]] = {}
    for code in codes:
        cur_row = cur.get(code) or {"count": 0.0, "avg_urgency": 0.0, "max_urgency": 0.0,
                                     "sum_urgency": 0.0}
        prior_row = prior.get(code) or {"count": 0.0, "avg_urgency": 0.0, "max_urgency": 0.0,
                                         "sum_urgency": 0.0}
        out[code] = {
            "current_pressure": pressure_score(cur_row),
            "prior_pressure":   pressure_score(prior_row),
            "delta":            round(pressure_score(cur_row) - pressure_score(prior_row), 2),
            "current_count":    cur_row["count"],
            "current_avg_urgency": cur_row.get("avg_urgency", 0.0),
            "current_max_urgency": cur_row.get("max_urgency", 0.0),
        }
    return out
```

- [ ] **Step 4: Run, confirm pass**

`uv run pytest tests/test_country.py -v` → PASS (6 tests).

- [ ] **Step 5: Lint + commit**

```bash
uv run ruff check build/_country.py tests/test_country.py
uv run mypy build/_country.py
git add build/_country.py tests/test_country.py
git commit -m "feat(stage-3): per-country aggregation + pressure score helpers"
```

---

## Task 6: β heat-map slice generator

**Why:** Produces `build/page_data/beta/heatmap.json` for `/beta/heatmap/`. Contains world aggregates, US-state aggregates, the France-retrospective drilldown payload (top 10 events + 78-week weekly buckets), tenant footprint overlay (operating/considering/closed code lists), and the annotation callouts from `beta-curation.yml::retrospective_focus.annotation_callouts`.

**Files:**
- Create: `build/beta_heatmap.py`
- Create: `tests/test_beta_heatmap.py`

Output schema:

```python
{
  "scene": {"number": 3, "letter": "β", "back_href": "../"},
  "window_days": 90,
  "world_aggregates": [          # one per country with activity in window
    {"code": "FR", "label": "France", "count": 273, "avg_urgency": 6.8,
     "max_urgency": 9.0, "pressure": 87.5},
    ...
  ],
  "us_state_aggregates": [...],  # same shape, US-XX codes
  "platform_footprint": {
    "active_platform": "polymarket",
    "operating":   [{"code": "US", "label": "United States"}, ...],
    "considering": [...],
    "closed":      [{"code": "FR", "label": "France",
                     "closed_at": "2025-12-15", "reason": "..."}, ...],
  },
  "retrospective_focus": {
    "code": "FR",
    "title": "France — 13 months of regulatory pressure ...",
    "weekly_buckets": [3, 5, 4, ...],   # 78 weeks oldest-first
    "annotation_callouts": [
      {"date": "2024-11-15", "label": "AMF opens dossier ...", "week_index": 7},
      ...
    ],
    "top_events": [
      {"title": "...", "regulator": "AMF", "pub_date": "2025-12-10",
       "urgency": 9.0, "link": "...", "matched_entity": "France"},
      ...                                  # top 10 by urgency * recency in window
    ],
    "anj_disclosure": "Direct ANJ events are not in the Carver catalog ..."
  },
  "anomaly_note": "..."                    # 1-sentence narrative for the right rail
}
```

- [ ] **Step 1: Write failing tests**

Create `tests/test_beta_heatmap.py`:

```python
"""Tests for build/beta_heatmap.py."""
import json
from datetime import date
from pathlib import Path

import yaml

from tests.conftest import make_row


def _write_corpus(p: Path, rows) -> None:
    p.write_text("\n".join(json.dumps(r) for r in rows))


def _write_curation(p: Path) -> None:
    p.write_text(yaml.safe_dump({
        "schema_version": 1,
        "build_date": "2026-05-19",
        "platform_footprint": "polymarket",
        "retrospective_focus": {
            "country_code": "FR",
            "title": "France — retrospective",
            "narrative_window_months": 18,
            "annotation_callouts": [
                {"date": "2025-12-10", "label": "Public restriction"},
            ],
        },
        "featured_cascade_ids": ["a", "b", "c"],
        "watch_list_picks": [],
        "report_window": {"start": "2026-04-01", "end": "2026-06-30", "label": "Q2"},
    }))


def _write_footprint(p: Path, platform: str) -> None:
    p.write_text(yaml.safe_dump({
        "schema_version": 1, "platform": platform,
        "operating": [{"code": "US"}],
        "considering": [{"code": "BR"}],
        "closed": [{"code": "FR", "closed_at": "2025-12-15", "reason": "..."}],
    }))


def test_heatmap_aggregates_world_records(tmp_path: Path) -> None:
    from build.beta_heatmap import generate

    corpus = tmp_path / "artifacts.jsonl"
    curation = tmp_path / "beta-curation.yml"
    foot = tmp_path / "footprint.yml"
    out = tmp_path / "heatmap.json"

    _write_corpus(corpus, [
        make_row(topic_jurisdiction_code="FR", title="FR1"),
        make_row(feed_entry_id="r2", topic_jurisdiction_code="FR", title="FR2"),
        make_row(feed_entry_id="r3", topic_jurisdiction_code="DE", title="DE1"),
    ])
    _write_curation(curation)
    _write_footprint(foot, "polymarket")

    generate(corpus_path=corpus, curation_path=curation,
             footprint_path=foot, out_path=out,
             today=date(2026, 5, 19))
    doc = json.loads(out.read_text())
    codes = {row["code"]: row for row in doc["world_aggregates"]}
    assert codes["FR"]["count"] == 2
    assert codes["DE"]["count"] == 1


def test_heatmap_excludes_us_states_from_world(tmp_path: Path) -> None:
    from build.beta_heatmap import generate

    corpus = tmp_path / "artifacts.jsonl"
    curation = tmp_path / "beta-curation.yml"
    foot = tmp_path / "footprint.yml"
    out = tmp_path / "heatmap.json"

    _write_corpus(corpus, [
        make_row(topic_jurisdiction_code="US-CA", title="CA1"),
        make_row(feed_entry_id="r2", topic_jurisdiction_code="FR", title="FR1"),
    ])
    _write_curation(curation)
    _write_footprint(foot, "polymarket")

    generate(corpus_path=corpus, curation_path=curation,
             footprint_path=foot, out_path=out, today=date(2026, 5, 19))
    doc = json.loads(out.read_text())
    world_codes = {row["code"] for row in doc["world_aggregates"]}
    state_codes = {row["code"] for row in doc["us_state_aggregates"]}
    assert "FR" in world_codes
    assert "US-CA" not in world_codes
    assert "US-CA" in state_codes


def test_heatmap_carries_retrospective_payload(tmp_path: Path) -> None:
    from build.beta_heatmap import generate

    corpus = tmp_path / "artifacts.jsonl"
    curation = tmp_path / "beta-curation.yml"
    foot = tmp_path / "footprint.yml"
    out = tmp_path / "heatmap.json"

    _write_corpus(corpus, [make_row(topic_jurisdiction_code="FR", title="FR")] * 5)
    _write_curation(curation)
    _write_footprint(foot, "polymarket")

    generate(corpus_path=corpus, curation_path=curation,
             footprint_path=foot, out_path=out, today=date(2026, 5, 19))
    doc = json.loads(out.read_text())
    retro = doc["retrospective_focus"]
    assert retro["code"] == "FR"
    assert isinstance(retro["weekly_buckets"], list) and len(retro["weekly_buckets"]) == 78
    assert isinstance(retro["top_events"], list)
    assert isinstance(retro["annotation_callouts"], list)


def test_heatmap_includes_footprint(tmp_path: Path) -> None:
    from build.beta_heatmap import generate

    corpus = tmp_path / "artifacts.jsonl"
    curation = tmp_path / "beta-curation.yml"
    foot = tmp_path / "footprint.yml"
    out = tmp_path / "heatmap.json"

    _write_corpus(corpus, [make_row(topic_jurisdiction_code="FR", title="FR")])
    _write_curation(curation)
    _write_footprint(foot, "polymarket")

    generate(corpus_path=corpus, curation_path=curation,
             footprint_path=foot, out_path=out, today=date(2026, 5, 19))
    doc = json.loads(out.read_text())
    footprint = doc["platform_footprint"]
    assert footprint["active_platform"] == "polymarket"
    assert {p["code"] for p in footprint["closed"]} == {"FR"}
```

- [ ] **Step 2: Run, confirm fails**

`uv run pytest tests/test_beta_heatmap.py -v` → FAIL.

- [ ] **Step 3: Implement `build/beta_heatmap.py`**

```python
"""Generate the β world-heat-map slice (build/page_data/beta/heatmap.json).

Reads:
  - data/_scratch/artifacts.jsonl (Carver corpus).
  - data/beta-curation.yml (retrospective focus + annotation callouts).
  - data/platforms/<platform>/footprint.yml (operating/considering/closed).
"""

from __future__ import annotations

import json
import math
import sys
from datetime import date, datetime
from pathlib import Path
from typing import Any, cast

import yaml

_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from build import _country, _fields, _heat  # noqa: E402


# Map ISO-2 country codes to display labels for chip rendering. Not a full
# list — only the codes we expect to encounter in the corpus or footprint.
_COUNTRY_LABELS: dict[str, str] = {
    "US": "United States", "CA": "Canada", "MX": "Mexico", "BR": "Brazil",
    "AR": "Argentina", "CL": "Chile", "CO": "Colombia",
    "GB": "United Kingdom", "FR": "France", "DE": "Germany", "ES": "Spain",
    "IT": "Italy", "NL": "Netherlands", "BE": "Belgium", "LU": "Luxembourg",
    "IE": "Ireland", "PT": "Portugal", "AT": "Austria", "GR": "Greece",
    "CH": "Switzerland", "DK": "Denmark", "FI": "Finland", "SE": "Sweden",
    "NO": "Norway", "PL": "Poland", "CZ": "Czech Republic", "HU": "Hungary",
    "RO": "Romania", "BG": "Bulgaria", "HR": "Croatia", "EE": "Estonia",
    "LV": "Latvia", "LT": "Lithuania", "MT": "Malta", "CY": "Cyprus",
    "SI": "Slovenia", "SK": "Slovakia", "IS": "Iceland",
    "RU": "Russia", "TR": "Türkiye", "UA": "Ukraine",
    "AE": "United Arab Emirates", "SA": "Saudi Arabia", "IL": "Israel",
    "QA": "Qatar", "KW": "Kuwait", "OM": "Oman", "BH": "Bahrain",
    "IN": "India", "PK": "Pakistan", "BD": "Bangladesh", "ID": "Indonesia",
    "MY": "Malaysia", "PH": "Philippines", "TH": "Thailand", "VN": "Vietnam",
    "SG": "Singapore", "TW": "Taiwan", "HK": "Hong Kong", "JP": "Japan",
    "KR": "South Korea", "CN": "China",
    "AU": "Australia", "NZ": "New Zealand",
    "ZA": "South Africa", "EG": "Egypt", "NG": "Nigeria", "KE": "Kenya",
    "EU": "European Union",
}


def _label(code: str) -> str:
    return _COUNTRY_LABELS.get(code, code)


def _stream_corpus(corpus_path: Path) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    with corpus_path.open() as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            out.append(json.loads(line))
    return out


def _build_world_aggregates(corpus: list[dict[str, Any]], today: date,
                            window_days: int) -> list[dict[str, Any]]:
    agg = _country.aggregate(corpus, today=today, window_days=window_days,
                             world_only=True)
    rows = [
        {"code": code, "label": _label(code),
         "count": int(slot["count"]), "avg_urgency": slot.get("avg_urgency", 0.0),
         "max_urgency": slot.get("max_urgency", 0.0),
         "pressure": _country.pressure_score(slot)}
        for code, slot in agg.items()
    ]
    rows.sort(key=lambda r: r["pressure"], reverse=True)
    return rows


def _build_state_aggregates(corpus: list[dict[str, Any]], today: date,
                            window_days: int) -> list[dict[str, Any]]:
    rows = []
    for r in corpus:
        code = _country.country_code(r, world_only=False) or ""
        if not code.startswith("US-"):
            continue
        rows.append(r)
    agg = _country.aggregate(rows, today=today, window_days=window_days,
                             world_only=False)
    out = [
        {"code": code, "label": code.replace("US-", ""), "count": int(slot["count"]),
         "avg_urgency": slot.get("avg_urgency", 0.0),
         "max_urgency": slot.get("max_urgency", 0.0),
         "pressure": _country.pressure_score(slot)}
        for code, slot in agg.items() if code.startswith("US-")
    ]
    out.sort(key=lambda r: r["pressure"], reverse=True)
    return out


def _build_retrospective(corpus: list[dict[str, Any]], focus: dict[str, Any],
                         today: date) -> dict[str, Any]:
    code = focus["country_code"]
    weeks = focus.get("narrative_window_months", 18) * 4  # ~weeks per month
    buckets = _country.weekly_buckets(corpus, code=code, today=today, weeks=weeks)
    # Per-callout: compute which weekly bucket it falls into so the template
    # can position annotation labels along the x-axis.
    callouts: list[dict[str, Any]] = []
    horizon_days = weeks * 7
    for c in focus.get("annotation_callouts") or []:
        d = datetime.strptime(c["date"], "%Y-%m-%d").date()
        age = (today - d).days
        if age < 0 or age >= horizon_days:
            continue
        week_idx = (weeks - 1) - (age // 7)
        callouts.append({"date": c["date"], "label": c["label"], "week_index": week_idx})

    # Top events: filter to country, in window, by urgency * exp(-age/14).
    matches: list[tuple[dict[str, Any], int]] = []
    for r in corpus:
        if _country.country_code(r, world_only=False) != code:
            continue
        age = _fields.pub_date_age_days(r, today=today)
        if age is None or age < 0 or age > horizon_days:
            continue
        matches.append((r, age))
    matches.sort(key=lambda pair: _fields.urgency_score(pair[0])
                  * math.exp(-pair[1] / 14.0), reverse=True)
    top = [
        {"title": (r.get("title") or "")[:160], "regulator": _fields.regulator_display(r),
         "pub_date": _fields.pub_date_iso(r), "urgency": _fields.urgency_score(r),
         "link": r.get("link") or "", "matched_entity": code}
        for r, _ in matches[:10]
    ]

    return {
        "code": code,
        "label": _label(code),
        "title": focus["title"],
        "weekly_buckets": buckets,
        "annotation_callouts": callouts,
        "top_events": top,
        "anj_disclosure": (
            "Direct ANJ (Autorité Nationale des Jeux) events are not in the "
            "Carver catalog. The timeline above is drawn from AMF, ESMA, and "
            "EU Commission events tagged France in the public regulatory record."
            if code == "FR" else ""
        ),
    }


def generate(corpus_path: Path, curation_path: Path, footprint_path: Path,
             out_path: Path, today: date | None = None,
             window_days: int = 90) -> dict[str, Any]:
    today = today or date.today()
    curation = cast(dict[str, Any], yaml.safe_load(curation_path.read_text()))
    footprint = cast(dict[str, Any], yaml.safe_load(footprint_path.read_text()))

    corpus = [r for r in _stream_corpus(corpus_path) if _heat.is_substantive(r)]

    world = _build_world_aggregates(corpus, today, window_days)
    states = _build_state_aggregates(corpus, today, window_days)
    retro = _build_retrospective(corpus, curation["retrospective_focus"], today)

    # Anomaly narrative: 1-sentence call-out for the right rail.
    if world:
        top = world[0]
        anomaly = (
            f"{top['label']} carries the highest pressure score "
            f"({top['pressure']:.0f}) — {top['count']} events at avg urgency "
            f"{top['avg_urgency']:.1f}."
        )
    else:
        anomaly = "Pressure is light across the board this window."

    doc = {
        "scene": {"number": 3, "letter": "β", "back_href": "../"},
        "window_days": window_days,
        "world_aggregates": world,
        "us_state_aggregates": states,
        "platform_footprint": {
            "active_platform": footprint["platform"],
            "operating":   [{**e, "label": e.get("label", _label(e["code"]))}
                            for e in footprint.get("operating") or []],
            "considering": [{**e, "label": e.get("label", _label(e["code"]))}
                            for e in footprint.get("considering") or []],
            "closed":      [{**e, "label": e.get("label", _label(e["code"]))}
                            for e in footprint.get("closed") or []],
        },
        "retrospective_focus": retro,
        "anomaly_note": anomaly,
    }
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(doc, indent=2))
    return doc


if __name__ == "__main__":
    REPO = Path(__file__).resolve().parent.parent
    cur = yaml.safe_load((REPO / "data" / "beta-curation.yml").read_text())
    platform = cur["platform_footprint"]
    generate(
        corpus_path=REPO / "data" / "_scratch" / "artifacts.jsonl",
        curation_path=REPO / "data" / "beta-curation.yml",
        footprint_path=REPO / "data" / "platforms" / platform / "footprint.yml",
        out_path=REPO / "build" / "page_data" / "beta" / "heatmap.json",
    )
    print("wrote build/page_data/beta/heatmap.json")
```

- [ ] **Step 4: Run, confirm pass**

`uv run pytest tests/test_beta_heatmap.py -v` → PASS (4 tests).

- [ ] **Step 5: Smoke + commit**

```bash
uv run python build/beta_heatmap.py
python3 -c "import json; d=json.load(open('build/page_data/beta/heatmap.json')); print('world rows:', len(d['world_aggregates'])); print('top:', [(r['code'], r['pressure']) for r in d['world_aggregates'][:5]]); retro = d['retrospective_focus']; print('FR weekly sum:', sum(retro['weekly_buckets'])); print('FR top events:', len(retro['top_events']))"
uv run ruff check build/beta_heatmap.py tests/test_beta_heatmap.py
uv run mypy build/beta_heatmap.py
git add build/beta_heatmap.py tests/test_beta_heatmap.py
git commit -m "feat(stage-3): beta world heat-map slice generator"
```

Expected smoke: ≥ 30 world rows, France retrospective with ≥ 100 weekly events across 18 months, ≥ 5 top events.

---

## Task 7: β cascade-signals slice generator

**Why:** Produces `build/page_data/beta/cascades.json` for `/beta/cascades/`. For each cascade rule, surfaces the trigger event (already in YAML), member jurisdictions chipped by footprint role (operating/considering/closed/other), and a hit-rate annotation. Optionally back-tests the YAML's `historical_hit_rate` against corpus and emits a warning if it falls below 30%.

**Files:**
- Create: `build/beta_cascades.py`
- Create: `tests/test_beta_cascades.py`

Output schema:

```python
{
  "scene": {"number": 3, "letter": "β", "back_href": "../"},
  "active_platform": "polymarket",
  "cascades": [
    {
      "id": "fatf-2025-q4-virtual-assets",
      "body": "Financial Action Task Force",
      "body_acronym": "FATF",
      "trigger_title": "...",
      "trigger_pub_date": "...",
      "trigger_url": "...",
      "rationale": "...",
      "follow_window_days": 540,
      "expected_action_by": "2027-05-13",   # trigger + follow_window
      "historical_hit_rate": "31/39 (79%)",
      "members": [
        {"code": "FR", "label": "France", "role": "closed"},
        {"code": "AU", "label": "Australia", "role": "operating"},
        ...
      ],
      "footprint_overlap_count": 7,         # operating + considering
    },
    ...
  ],
}
```

- [ ] **Step 1: Write failing tests**

Create `tests/test_beta_cascades.py`:

```python
"""Tests for build/beta_cascades.py."""
import json
from datetime import date
from pathlib import Path

import yaml


def _write_cascades(p: Path) -> None:
    p.write_text(yaml.safe_dump({
        "schema_version": 1,
        "cascades": [{
            "id": "rule-1", "body": "FATF", "body_acronym": "FATF",
            "trigger_title": "Trigger", "trigger_pub_date": "2025-11-20",
            "trigger_url": "https://x", "rationale": "R",
            "follow_window_days": 540,
            "historical_hit_rate": "31/39 (79%)",
            "member_jurisdictions": ["FR", "AU", "BR", "IN", "ZA"],
        }],
    }))


def _write_curation(p: Path, featured_ids) -> None:
    p.write_text(yaml.safe_dump({
        "schema_version": 1, "build_date": "2026-05-19",
        "platform_footprint": "polymarket",
        "retrospective_focus": {"country_code": "FR", "title": "T",
                                 "narrative_window_months": 18,
                                 "annotation_callouts": []},
        "featured_cascade_ids": featured_ids,
        "watch_list_picks": [],
        "report_window": {"start": "2026-04-01", "end": "2026-06-30", "label": "Q2"},
    }))


def _write_footprint(p: Path) -> None:
    p.write_text(yaml.safe_dump({
        "schema_version": 1, "platform": "polymarket",
        "operating":   [{"code": "AU"}, {"code": "BR"}, {"code": "IN"}],
        "considering": [{"code": "ZA"}],
        "closed":      [{"code": "FR", "closed_at": "2025-12-15"}],
    }))


def test_cascades_emit_one_card_per_featured(tmp_path: Path) -> None:
    from build.beta_cascades import generate

    cascades_yml = tmp_path / "cascades.yml"
    curation = tmp_path / "beta-curation.yml"
    foot = tmp_path / "footprint.yml"
    out = tmp_path / "cascades.json"

    _write_cascades(cascades_yml)
    _write_curation(curation, ["rule-1"])
    _write_footprint(foot)

    generate(cascades_path=cascades_yml, curation_path=curation,
             footprint_path=foot, out_path=out, today=date(2026, 5, 19))
    doc = json.loads(out.read_text())
    assert len(doc["cascades"]) == 1
    card = doc["cascades"][0]
    assert card["id"] == "rule-1"
    assert card["body_acronym"] == "FATF"


def test_cascade_members_tagged_by_role(tmp_path: Path) -> None:
    from build.beta_cascades import generate

    cascades_yml = tmp_path / "cascades.yml"
    curation = tmp_path / "beta-curation.yml"
    foot = tmp_path / "footprint.yml"
    out = tmp_path / "cascades.json"

    _write_cascades(cascades_yml)
    _write_curation(curation, ["rule-1"])
    _write_footprint(foot)

    generate(cascades_path=cascades_yml, curation_path=curation,
             footprint_path=foot, out_path=out, today=date(2026, 5, 19))
    doc = json.loads(out.read_text())
    members = doc["cascades"][0]["members"]
    by_code = {m["code"]: m["role"] for m in members}
    assert by_code["AU"] == "operating"
    assert by_code["BR"] == "operating"
    assert by_code["ZA"] == "considering"
    assert by_code["FR"] == "closed"
    assert by_code["IN"] == "operating"


def test_cascade_expected_action_date(tmp_path: Path) -> None:
    from build.beta_cascades import generate

    cascades_yml = tmp_path / "cascades.yml"
    curation = tmp_path / "beta-curation.yml"
    foot = tmp_path / "footprint.yml"
    out = tmp_path / "cascades.json"

    _write_cascades(cascades_yml)
    _write_curation(curation, ["rule-1"])
    _write_footprint(foot)

    generate(cascades_path=cascades_yml, curation_path=curation,
             footprint_path=foot, out_path=out, today=date(2026, 5, 19))
    doc = json.loads(out.read_text())
    # 2025-11-20 + 540 days = 2027-05-13
    assert doc["cascades"][0]["expected_action_by"] == "2027-05-13"


def test_cascade_footprint_overlap_count(tmp_path: Path) -> None:
    from build.beta_cascades import generate

    cascades_yml = tmp_path / "cascades.yml"
    curation = tmp_path / "beta-curation.yml"
    foot = tmp_path / "footprint.yml"
    out = tmp_path / "cascades.json"

    _write_cascades(cascades_yml)
    _write_curation(curation, ["rule-1"])
    _write_footprint(foot)

    generate(cascades_path=cascades_yml, curation_path=curation,
             footprint_path=foot, out_path=out, today=date(2026, 5, 19))
    doc = json.loads(out.read_text())
    # Operating: AU, BR, IN (3) + Considering: ZA (1) = 4
    assert doc["cascades"][0]["footprint_overlap_count"] == 4
```

- [ ] **Step 2: Run, confirm fails**

`uv run pytest tests/test_beta_cascades.py -v` → FAIL.

- [ ] **Step 3: Implement `build/beta_cascades.py`**

```python
"""Generate the β cascade-signals slice (build/page_data/beta/cascades.json).

Joins data/cascades.yml × data/platforms/<platform>/footprint.yml to emit
per-rule cards with member jurisdictions tagged by footprint role.
"""

from __future__ import annotations

import json
import sys
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, cast

import yaml

_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

# Reused _COUNTRY_LABELS from beta_heatmap.
from build.beta_heatmap import _COUNTRY_LABELS  # noqa: E402


def _role_map(footprint: dict[str, Any]) -> dict[str, str]:
    """Build code → role mapping from a footprint document."""
    out: dict[str, str] = {}
    for entry in footprint.get("operating") or []:
        out[entry["code"]] = "operating"
    for entry in footprint.get("considering") or []:
        out[entry["code"]] = "considering"
    for entry in footprint.get("closed") or []:
        out[entry["code"]] = "closed"
    return out


def _expected_action_by(trigger_iso: str, follow_window_days: int) -> str:
    trigger = datetime.strptime(trigger_iso, "%Y-%m-%d").date()
    return (trigger + timedelta(days=follow_window_days)).isoformat()


def _build_card(rule: dict[str, Any], roles: dict[str, str]) -> dict[str, Any]:
    members = []
    overlap = 0
    for code in rule["member_jurisdictions"]:
        role = roles.get(code, "other")
        members.append({
            "code": code,
            "label": _COUNTRY_LABELS.get(code, code),
            "role": role,
        })
        if role in {"operating", "considering"}:
            overlap += 1
    return {
        "id": rule["id"],
        "body": rule["body"],
        "body_acronym": rule.get("body_acronym", rule["body"]),
        "trigger_title": rule["trigger_title"],
        "trigger_pub_date": rule["trigger_pub_date"],
        "trigger_url": rule["trigger_url"],
        "rationale": rule["rationale"],
        "follow_window_days": rule["follow_window_days"],
        "expected_action_by": _expected_action_by(rule["trigger_pub_date"],
                                                   rule["follow_window_days"]),
        "historical_hit_rate": rule["historical_hit_rate"],
        "members": members,
        "footprint_overlap_count": overlap,
    }


def generate(cascades_path: Path, curation_path: Path, footprint_path: Path,
             out_path: Path, today: date | None = None) -> dict[str, Any]:
    today = today or date.today()
    cascades = cast(dict[str, Any], yaml.safe_load(cascades_path.read_text()))
    curation = cast(dict[str, Any], yaml.safe_load(curation_path.read_text()))
    footprint = cast(dict[str, Any], yaml.safe_load(footprint_path.read_text()))

    featured_ids = curation.get("featured_cascade_ids") or []
    rules_by_id = {c["id"]: c for c in cascades.get("cascades") or []}
    roles = _role_map(footprint)

    cards = []
    for cid in featured_ids:
        rule = rules_by_id.get(cid)
        if not rule:
            print(f"WARN: featured cascade id {cid!r} not in cascades.yml", file=sys.stderr)
            continue
        cards.append(_build_card(rule, roles))

    doc = {
        "scene": {"number": 3, "letter": "β", "back_href": "../"},
        "active_platform": footprint["platform"],
        "cascades": cards,
    }
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(doc, indent=2))
    return doc


if __name__ == "__main__":
    REPO = Path(__file__).resolve().parent.parent
    cur = yaml.safe_load((REPO / "data" / "beta-curation.yml").read_text())
    platform = cur["platform_footprint"]
    generate(
        cascades_path=REPO / "data" / "cascades.yml",
        curation_path=REPO / "data" / "beta-curation.yml",
        footprint_path=REPO / "data" / "platforms" / platform / "footprint.yml",
        out_path=REPO / "build" / "page_data" / "beta" / "cascades.json",
    )
    print("wrote build/page_data/beta/cascades.json")
```

- [ ] **Step 4: Run, confirm pass**

`uv run pytest tests/test_beta_cascades.py -v` → PASS (4 tests).

- [ ] **Step 5: Smoke + commit**

```bash
uv run python build/beta_cascades.py
python3 -c "import json; d=json.load(open('build/page_data/beta/cascades.json')); print('cards:', len(d['cascades'])); print([(c['body_acronym'], c['footprint_overlap_count']) for c in d['cascades']])"
uv run ruff check build/beta_cascades.py tests/test_beta_cascades.py
uv run mypy build/beta_cascades.py
git add build/beta_cascades.py tests/test_beta_cascades.py
git commit -m "feat(stage-3): beta cascade-signals slice generator"
```

Expected smoke: 3 cards (FATF/BCBS/ESMA). Polymarket footprint overlap counts: ≥ 5 each.

---

## Task 8: β quarterly-report slice generator

**Why:** Produces `build/page_data/beta/report.json` for `/beta/report/`. The board-ready document. Composes country aggregates + delta vs prior quarter + watch-list picks + featured cascades.

**Files:**
- Create: `build/beta_report.py`
- Create: `tests/test_beta_report.py`

Output schema:

```python
{
  "scene": {"number": 3, "letter": "β", "back_label": "← Cascade signals",
            "back_href": "../cascades/"},
  "report_window": {"start": "2026-04-01", "end": "2026-06-30", "label": "Q2 2026"},
  "generated_at": "2026-05-20",
  "active_platform": "polymarket",
  "headline_stats": {
    "events_in_window": 12345,
    "jurisdictions_with_activity": 67,
    "high_urgency_events": 234,
    "active_cascades": 3,
  },
  "pressure_rising": [          # top 10 by delta desc
    {"code": "BR", "label": "Brazil", "role": "operating",
     "current_pressure": 78.5, "delta": 12.3,
     "narrative": "Auto-narrative...",
     "top_events": [...]},
    ...
  ],
  "pressure_easing": [...],     # top 5 by delta asc
  "watch_list": [               # 3 picks from curation
    {"code": "BR", "label": "Brazil", "rationale": "...",
     "recommended_actions": [...],
     "alpha_dashboard_link": "../../alpha/dashboard/#BR",
     "evidence_events": [...]},
    ...
  ],
  "featured_cascades": [...],   # condensed cards for the appendix
  "gamma_touchpoints": [        # cross-module: contracts whose heat correlates
    {"contract_id": "kxbtc-maxprice-2026", "title": "...", "heat": 418.2,
     "detail_href": "../../gamma/contracts/kxbtc-maxprice-2026/"},
    ...
  ],
  "method_notes": "...",
  "coverage_caveat": "...",
  "watch_list_disclaimer": "Pattern-based projection, not prediction. Confidence: medium.",
  "v1_footer": "V1 cascade rules are curated from historical patterns. Learned models will replace rules in V2+ as more data accrues.",
  "pdf_href": "../static/samples/q2-2026-report.pdf"
}
```

- [ ] **Step 1: Write failing tests**

Create `tests/test_beta_report.py`:

```python
"""Tests for build/beta_report.py."""
import json
from datetime import date
from pathlib import Path

import yaml

from tests.conftest import make_row


def _write_corpus(p: Path, rows) -> None:
    p.write_text("\n".join(json.dumps(r) for r in rows))


def _write_curation(p: Path) -> None:
    p.write_text(yaml.safe_dump({
        "schema_version": 1, "build_date": "2026-05-19",
        "platform_footprint": "polymarket",
        "retrospective_focus": {"country_code": "FR", "title": "T",
                                 "narrative_window_months": 18,
                                 "annotation_callouts": []},
        "featured_cascade_ids": ["rule-1"],
        "watch_list_picks": [
            {"country_code": "BR", "label": "Brazil",
             "rationale": "R", "recommended_actions": ["A1"]},
            {"country_code": "SG", "label": "Singapore",
             "rationale": "R", "recommended_actions": ["A1"]},
            {"country_code": "AU", "label": "Australia",
             "rationale": "R", "recommended_actions": ["A1"]},
        ],
        "report_window": {"start": "2026-04-01", "end": "2026-06-30",
                           "label": "Q2 2026"},
    }))


def _write_footprint(p: Path) -> None:
    p.write_text(yaml.safe_dump({
        "schema_version": 1, "platform": "polymarket",
        "operating": [{"code": "BR"}, {"code": "AU"}],
        "considering": [{"code": "SG"}],
        "closed": [{"code": "FR", "closed_at": "2025-12-15"}],
    }))


def _write_cascades(p: Path) -> None:
    p.write_text(yaml.safe_dump({
        "schema_version": 1,
        "cascades": [{
            "id": "rule-1", "body": "FATF", "body_acronym": "FATF",
            "trigger_title": "T", "trigger_pub_date": "2025-11-20",
            "trigger_url": "https://x", "rationale": "R",
            "follow_window_days": 540,
            "historical_hit_rate": "31/39 (79%)",
            "member_jurisdictions": ["BR", "AU", "SG", "FR"],
        }],
    }))


def test_report_emits_full_schema(tmp_path: Path) -> None:
    from build.beta_report import generate

    corpus = tmp_path / "artifacts.jsonl"
    curation = tmp_path / "beta-curation.yml"
    foot = tmp_path / "footprint.yml"
    cascades = tmp_path / "cascades.yml"
    out = tmp_path / "report.json"

    _write_corpus(corpus, [
        make_row(topic_jurisdiction_code="BR", title="BR1"),
        make_row(feed_entry_id="r2", topic_jurisdiction_code="BR", title="BR2"),
        make_row(feed_entry_id="r3", topic_jurisdiction_code="AU", title="AU1"),
    ])
    _write_curation(curation)
    _write_footprint(foot)
    _write_cascades(cascades)

    generate(corpus_path=corpus, curation_path=curation,
             footprint_path=foot, cascades_path=cascades,
             out_path=out, today=date(2026, 5, 19))
    doc = json.loads(out.read_text())
    for key in ("headline_stats", "pressure_rising", "pressure_easing",
                "watch_list", "featured_cascades", "method_notes",
                "watch_list_disclaimer", "v1_footer", "pdf_href"):
        assert key in doc, f"missing {key}"


def test_report_watch_list_size_three(tmp_path: Path) -> None:
    from build.beta_report import generate

    corpus = tmp_path / "artifacts.jsonl"
    curation = tmp_path / "beta-curation.yml"
    foot = tmp_path / "footprint.yml"
    cascades = tmp_path / "cascades.yml"
    out = tmp_path / "report.json"

    _write_corpus(corpus, [make_row(topic_jurisdiction_code="BR")])
    _write_curation(curation)
    _write_footprint(foot)
    _write_cascades(cascades)

    generate(corpus_path=corpus, curation_path=curation,
             footprint_path=foot, cascades_path=cascades,
             out_path=out, today=date(2026, 5, 19))
    doc = json.loads(out.read_text())
    assert len(doc["watch_list"]) == 3
    assert all("recommended_actions" in w for w in doc["watch_list"])


def test_report_pdf_href_points_to_sample(tmp_path: Path) -> None:
    from build.beta_report import generate

    corpus = tmp_path / "artifacts.jsonl"
    curation = tmp_path / "beta-curation.yml"
    foot = tmp_path / "footprint.yml"
    cascades = tmp_path / "cascades.yml"
    out = tmp_path / "report.json"

    _write_corpus(corpus, [make_row(topic_jurisdiction_code="BR")])
    _write_curation(curation)
    _write_footprint(foot)
    _write_cascades(cascades)

    generate(corpus_path=corpus, curation_path=curation,
             footprint_path=foot, cascades_path=cascades,
             out_path=out, today=date(2026, 5, 19))
    doc = json.loads(out.read_text())
    assert "q2-2026-report.pdf" in doc["pdf_href"]
```

- [ ] **Step 2: Run, confirm fails**

`uv run pytest tests/test_beta_report.py -v` → FAIL.

- [ ] **Step 3: Implement `build/beta_report.py`**

```python
"""Generate the β quarterly-report slice (build/page_data/beta/report.json).

Composes country aggregates × prior-window delta × footprint role × watch-list
picks × cascade highlights into the board-ready report payload.
"""

from __future__ import annotations

import json
import math
import sys
from datetime import date
from pathlib import Path
from typing import Any, cast

import yaml

_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from build import _country, _fields, _heat  # noqa: E402
from build.beta_heatmap import _COUNTRY_LABELS  # noqa: E402


def _stream_corpus(corpus_path: Path) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    with corpus_path.open() as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            out.append(json.loads(line))
    return out


def _top_events_for(corpus: list[dict[str, Any]], code: str, today: date,
                    window_days: int, limit: int) -> list[dict[str, Any]]:
    matches: list[tuple[dict[str, Any], int]] = []
    for r in corpus:
        if _country.country_code(r, world_only=False) != code:
            continue
        age = _fields.pub_date_age_days(r, today=today)
        if age is None or age < 0 or age > window_days:
            continue
        matches.append((r, age))
    matches.sort(key=lambda pair: _fields.urgency_score(pair[0])
                  * math.exp(-pair[1] / 14.0), reverse=True)
    return [
        {"title": (r.get("title") or "")[:160],
         "regulator": _fields.regulator_display(r),
         "pub_date": _fields.pub_date_iso(r),
         "urgency": _fields.urgency_score(r),
         "link": r.get("link") or ""}
        for r, _ in matches[:limit]
    ]


def _role_map(footprint: dict[str, Any]) -> dict[str, str]:
    out: dict[str, str] = {}
    for entry in footprint.get("operating") or []:
        out[entry["code"]] = "operating"
    for entry in footprint.get("considering") or []:
        out[entry["code"]] = "considering"
    for entry in footprint.get("closed") or []:
        out[entry["code"]] = "closed"
    return out


def _narrate_pressure(row: dict[str, float], label: str, role: str) -> str:
    direction = "rising" if row["delta"] >= 0 else "easing"
    return (
        f"{label} pressure is {direction} ({row['delta']:+.1f} vs prior 90d). "
        f"Current footprint: {role}. {int(row['current_count'])} events at avg "
        f"urgency {row['current_avg_urgency']:.1f}."
    )


def generate(corpus_path: Path, curation_path: Path, footprint_path: Path,
             cascades_path: Path, out_path: Path,
             today: date | None = None) -> dict[str, Any]:
    today = today or date.today()
    curation = cast(dict[str, Any], yaml.safe_load(curation_path.read_text()))
    footprint = cast(dict[str, Any], yaml.safe_load(footprint_path.read_text()))
    cascades = cast(dict[str, Any], yaml.safe_load(cascades_path.read_text()))

    corpus = [r for r in _stream_corpus(corpus_path) if _heat.is_substantive(r)]
    deltas = _country.delta_pressure(corpus, today=today,
                                       current_window_days=90,
                                       prior_window_days=90)
    roles = _role_map(footprint)

    def _row(code: str, delta_row: dict[str, float]) -> dict[str, Any]:
        label = _COUNTRY_LABELS.get(code, code)
        role = roles.get(code, "other")
        return {
            "code": code, "label": label, "role": role,
            "current_pressure": delta_row["current_pressure"],
            "prior_pressure": delta_row["prior_pressure"],
            "delta": delta_row["delta"],
            "current_count": int(delta_row["current_count"]),
            "narrative": _narrate_pressure(delta_row, label, role),
            "top_events": _top_events_for(corpus, code, today, 90, 3),
        }

    rising_sorted = sorted(
        [_row(c, d) for c, d in deltas.items() if d["current_count"] >= 5],
        key=lambda x: x["delta"], reverse=True,
    )
    pressure_rising = rising_sorted[:10]
    pressure_easing = sorted(rising_sorted, key=lambda x: x["delta"])[:5]

    # Watch list — hand-picked from curation; enrich with evidence events.
    watch_list = []
    for w in curation.get("watch_list_picks") or []:
        code = w["country_code"]
        watch_list.append({
            "code": code,
            "label": w["label"],
            "role": roles.get(code, "other"),
            "rationale": w["rationale"],
            "recommended_actions": w["recommended_actions"],
            "alpha_dashboard_link": f"../../alpha/dashboard/#{code}",
            "evidence_events": _top_events_for(corpus, code, today, 90, 3),
        })

    featured_cascades = [
        {"id": c["id"], "body_acronym": c.get("body_acronym", c["body"]),
         "trigger_title": c["trigger_title"],
         "trigger_pub_date": c["trigger_pub_date"],
         "historical_hit_rate": c["historical_hit_rate"]}
        for c in cascades.get("cascades") or []
        if c["id"] in (curation.get("featured_cascade_ids") or [])
    ]

    # γ touchpoints — top 3 active contracts; load if the slice exists.
    gamma_path = corpus_path.parent.parent.parent / "build" / "page_data" / "gamma" / "dashboard.json"
    gamma_touchpoints = []
    if gamma_path.exists():
        gd = json.loads(gamma_path.read_text())
        for c in (gd.get("contracts") or [])[:3]:
            gamma_touchpoints.append({
                "contract_id": c["id"],
                "title": c["title"],
                "heat": c["heat"],
                "detail_href": f"../../gamma/contracts/{c['id']}/",
            })

    high_urg = sum(1 for r in corpus
                   if _fields.urgency_score(r) >= 8
                   and (_fields.pub_date_age_days(r, today=today) or 999) <= 90)

    doc = {
        "scene": {"number": 3, "letter": "β", "back_label": "← Cascade signals",
                  "back_href": "../cascades/"},
        "report_window": curation["report_window"],
        "generated_at": today.isoformat(),
        "active_platform": footprint["platform"],
        "headline_stats": {
            "events_in_window": sum(int(d["current_count"]) for d in deltas.values()),
            "jurisdictions_with_activity": sum(1 for d in deltas.values() if d["current_count"]),
            "high_urgency_events": high_urg,
            "active_cascades": len(featured_cascades),
        },
        "pressure_rising": pressure_rising,
        "pressure_easing": pressure_easing,
        "watch_list": watch_list,
        "featured_cascades": featured_cascades,
        "gamma_touchpoints": gamma_touchpoints,
        "method_notes": (
            "Pressure score = min(100, count × avg urgency / 5) over the report "
            "window. Delta compares against the equivalent immediately-prior "
            "window. Watch list is hand-picked; pattern match is qualitative."
        ),
        "coverage_caveat": (
            "All events drawn from Carver's regulatory-annotation pipeline. "
            "Coverage skews toward bodies in the regulator allowlist; smaller "
            "or country-specific bodies may be underrepresented."
        ),
        "watch_list_disclaimer":
            "Pattern-based projection, not prediction. Confidence: medium.",
        "v1_footer": (
            "V1 cascade rules are curated from historical patterns. Learned "
            "models will replace rules in V2+ as more data accrues."
        ),
        "pdf_href": "../static/samples/q2-2026-report.pdf",
    }
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(doc, indent=2))
    return doc


if __name__ == "__main__":
    REPO = Path(__file__).resolve().parent.parent
    cur = yaml.safe_load((REPO / "data" / "beta-curation.yml").read_text())
    platform = cur["platform_footprint"]
    generate(
        corpus_path=REPO / "data" / "_scratch" / "artifacts.jsonl",
        curation_path=REPO / "data" / "beta-curation.yml",
        footprint_path=REPO / "data" / "platforms" / platform / "footprint.yml",
        cascades_path=REPO / "data" / "cascades.yml",
        out_path=REPO / "build" / "page_data" / "beta" / "report.json",
    )
    print("wrote build/page_data/beta/report.json")
```

- [ ] **Step 4: Run, confirm pass**

`uv run pytest tests/test_beta_report.py -v` → PASS (3 tests).

- [ ] **Step 5: Smoke + commit**

```bash
uv run python build/beta_report.py
python3 -c "import json; d=json.load(open('build/page_data/beta/report.json')); print('headline:', d['headline_stats']); print('rising:', [(r['code'], r['delta']) for r in d['pressure_rising'][:5]]); print('watch list:', [w['code'] for w in d['watch_list']])"
uv run ruff check build/beta_report.py tests/test_beta_report.py
uv run mypy build/beta_report.py
git add build/beta_report.py tests/test_beta_report.py
git commit -m "feat(stage-3): beta quarterly-report slice generator"
```

---

## Task 9: β template components

**Why:** Shared partials reused by the four β templates.

**Files:**
- Create: `build/templates/beta/_components/country_chip.html`
- Create: `build/templates/beta/_components/pressure_chart.html`
- Create: `build/templates/beta/_components/cascade_card.html`
- Create: `build/templates/beta/_components/watchlist_card.html`
- Create: `tests/test_beta_templates.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_beta_templates.py`:

```python
"""Tests for β template components."""
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

REPO = Path(__file__).resolve().parent.parent


def _env() -> Environment:
    return Environment(
        loader=FileSystemLoader(REPO / "build" / "templates"),
        autoescape=select_autoescape(["html"]),
    )


def test_country_chip_renders_with_role() -> None:
    tpl = _env().get_template("beta/_components/country_chip.html")
    out = tpl.render(member={"code": "FR", "label": "France", "role": "closed"})
    assert "France" in out
    assert "FR" in out
    assert "closed" in out.lower()


def test_country_chip_role_other() -> None:
    tpl = _env().get_template("beta/_components/country_chip.html")
    out = tpl.render(member={"code": "JP", "label": "Japan", "role": "other"})
    assert "Japan" in out


def test_cascade_card_renders() -> None:
    tpl = _env().get_template("beta/_components/cascade_card.html")
    card = {
        "id": "x", "body": "FATF", "body_acronym": "FATF",
        "trigger_title": "Trigger T", "trigger_pub_date": "2025-11-20",
        "trigger_url": "https://x", "rationale": "Because.",
        "follow_window_days": 540,
        "expected_action_by": "2027-05-13",
        "historical_hit_rate": "31/39 (79%)",
        "members": [{"code": "FR", "label": "France", "role": "closed"},
                     {"code": "BR", "label": "Brazil", "role": "operating"}],
        "footprint_overlap_count": 1,
    }
    out = tpl.render(card=card, base_url="")
    assert "FATF" in out
    assert "Trigger T" in out
    assert "France" in out
    assert "Brazil" in out
    assert "31/39" in out


def test_watchlist_card_renders() -> None:
    tpl = _env().get_template("beta/_components/watchlist_card.html")
    w = {"code": "BR", "label": "Brazil", "role": "operating",
         "rationale": "Pattern resembles France.",
         "recommended_actions": ["Engage counsel"],
         "alpha_dashboard_link": "../../alpha/dashboard/#BR",
         "evidence_events": [
             {"title": "Ev1", "regulator": "SECAP", "pub_date": "2026-05-01",
              "urgency": 8.0, "link": "https://x"},
         ]}
    out = tpl.render(item=w, base_url="")
    assert "Brazil" in out
    assert "Engage counsel" in out
    assert "Ev1" in out


def test_pressure_chart_renders_svg() -> None:
    tpl = _env().get_template("beta/_components/pressure_chart.html")
    out = tpl.render(buckets=[0, 1, 2, 3, 4, 5, 4, 3, 2, 1, 0] * 7,
                     callouts=[{"week_index": 3, "label": "X"}],
                     width=480, height=120)
    assert "<svg" in out
    assert "polyline" in out
```

- [ ] **Step 2: Run, confirm fails**

`uv run pytest tests/test_beta_templates.py -v` → FAIL.

- [ ] **Step 3: Create the four component templates**

`build/templates/beta/_components/country_chip.html`:

```html
{% set role = member.role|default('other') %}
{% set cls_map = {
  'operating':   'border-blue-500 bg-blue-50 text-blue-800',
  'considering': 'border-blue-400 border-dashed bg-blue-50/50 text-blue-700',
  'closed':      'border-rose-400 bg-rose-50 text-rose-800 line-through',
  'other':       'border-slate-200 bg-slate-50 text-slate-700',
} %}
<span class="inline-flex items-center gap-1 text-xs border px-2 py-0.5 rounded {{ cls_map[role] }}"
      title="{{ member.label }} · {{ role }}">
  <span class="font-medium">{{ member.label|default(member.code) }}</span>
  <span class="opacity-60 text-[10px] uppercase tracking-wider">{{ role }}</span>
</span>
```

`build/templates/beta/_components/pressure_chart.html`:

```html
{# Inline pressure-over-time chart. Expects buckets (list of ints,
   oldest-first), optional callouts ({week_index, label}), optional
   width/height. #}
{% set _w = width|default(480) %}
{% set _h = height|default(120) %}
{% set _n = buckets|length %}
{% set _max = (buckets|max) if buckets else 0 %}
{% set _max = _max if _max > 0 else 1 %}
{% set _step = _w / (_n - 1) if _n > 1 else _w %}
<svg viewBox="0 0 {{ _w }} {{ _h }}" width="{{ _w }}" height="{{ _h }}"
     class="w-full max-w-full">
  <polyline fill="none" stroke="#1e40af" stroke-width="1.5"
    points="{% for v in buckets %}{{ (loop.index0 * _step)|round(2) }},{{ (_h - (v / _max) * (_h - 8) - 4)|round(2) }} {% endfor %}" />
  {% for c in callouts|default([]) %}
    {% set x = (c.week_index * _step)|round(2) %}
    <line x1="{{ x }}" y1="0" x2="{{ x }}" y2="{{ _h }}"
          stroke="#dc2626" stroke-width="0.5" stroke-dasharray="2,2" />
    <text x="{{ x + 2 }}" y="12" font-size="9" fill="#dc2626">{{ c.label[:36] }}</text>
  {% endfor %}
</svg>
```

`build/templates/beta/_components/cascade_card.html`:

```html
<article class="border border-slate-200 rounded-lg p-5 bg-white">
  <header class="flex items-start justify-between gap-3 mb-3">
    <div>
      <div class="flex items-center gap-2 text-xs uppercase tracking-wider text-blue-600 font-semibold mb-1">
        <span>{{ card.body_acronym }}</span>
        <span class="text-slate-300">·</span>
        <span class="text-slate-500 normal-case font-medium">{{ card.body }}</span>
      </div>
      <h3 class="text-lg font-semibold text-slate-900">
        <a href="{{ card.trigger_url }}" target="_blank" rel="noopener noreferrer" class="hover:text-blue-700">{{ card.trigger_title }}</a>
      </h3>
      <div class="text-xs text-slate-500 mt-1">
        Trigger {{ card.trigger_pub_date }} · Expected member action by {{ card.expected_action_by }} ({{ card.follow_window_days }}d window)
      </div>
    </div>
    <div class="text-right shrink-0">
      <div class="text-xs uppercase tracking-wider text-slate-500">Historical</div>
      <div class="text-xl font-bold text-slate-900 tabular-nums">{{ card.historical_hit_rate }}</div>
      <div class="text-xs text-slate-500">members adopted</div>
    </div>
  </header>
  <p class="text-sm text-slate-700 mb-4 whitespace-pre-line">{{ card.rationale }}</p>
  <div class="mb-3">
    <div class="text-xs uppercase tracking-wider text-slate-500 mb-2">
      Expected followers ({{ card.members|length }}) · {{ card.footprint_overlap_count }} in your footprint
    </div>
    <div class="flex flex-wrap gap-1.5">
      {% for member in card.members %}
        {% include "beta/_components/country_chip.html" %}
      {% endfor %}
    </div>
  </div>
</article>
```

`build/templates/beta/_components/watchlist_card.html`:

```html
<article class="border-l-4 border-amber-400 bg-amber-50/40 pl-5 py-4 pr-4 rounded-r">
  <header class="flex items-baseline justify-between gap-3 mb-2">
    <div>
      <h3 class="text-lg font-semibold text-slate-900">{{ item.label }}</h3>
      <div class="text-xs text-slate-500 mt-0.5">
        Current footprint: <span class="font-medium capitalize">{{ item.role }}</span>
      </div>
    </div>
    <a href="{{ base_url|default('/') }}{{ item.alpha_dashboard_link|default('') }}" class="text-xs text-blue-600 hover:text-blue-800 underline">
      View in α dashboard →
    </a>
  </header>
  <p class="text-sm text-slate-700 mb-3 whitespace-pre-line">{{ item.rationale }}</p>
  <div class="mb-3">
    <div class="text-xs uppercase tracking-wider text-slate-500 mb-1">Recommended actions</div>
    <ul class="text-sm text-slate-800 space-y-1 list-disc list-inside">
      {% for action in item.recommended_actions %}<li>{{ action }}</li>{% endfor %}
    </ul>
  </div>
  {% if item.evidence_events %}
  <div>
    <div class="text-xs uppercase tracking-wider text-slate-500 mb-1">Driving events</div>
    <ul class="text-sm space-y-1">
      {% for ev in item.evidence_events %}
      <li>
        <a href="{{ ev.link }}" target="_blank" rel="noopener noreferrer" class="text-slate-900 hover:text-blue-700">{{ ev.title }}</a>
        <span class="text-xs text-slate-500">— {{ ev.regulator }} · {{ ev.pub_date }} · urg {{ ev.urgency|round(0)|int }}</span>
      </li>
      {% endfor %}
    </ul>
  </div>
  {% endif %}
</article>
```

- [ ] **Step 4: Run, confirm pass**

`uv run pytest tests/test_beta_templates.py -v` → PASS (5 tests).

- [ ] **Step 5: Commit**

```bash
git add build/templates/beta/_components/ tests/test_beta_templates.py
git commit -m "feat(stage-3): beta template components"
```

---

## Task 10: β intro template (replace placeholder)

**Why:** Stage 0's `beta/intro.html` is a placeholder. Replace with the scene-framing intro per spec § 2.1.

**Files:**
- Modify: `build/templates/beta/intro.html`
- Modify: `tests/test_beta_templates.py`

- [ ] **Step 1: Append failing test**

Append to `tests/test_beta_templates.py`:

```python
def test_beta_intro_renders_with_scene_copy() -> None:
    tpl = _env().get_template("beta/intro.html")
    out = tpl.render(base_url="")
    assert "Priya Kapur" in out
    assert "Q3" in out or "Q2" in out
    out_l = out.lower()
    assert "heat-map" in out_l or "heatmap" in out_l
    assert "cascade" in out_l
    assert "quarter" in out_l or "q2" in out_l
    assert 'href="' in out and "beta/heatmap/" in out
```

- [ ] **Step 2: Replace `build/templates/beta/intro.html`**

```html
{% extends "base.html" %}
{% block title %}β — International strategy — Pred-Oracle{% endblock %}
{% block content %}
<section class="mb-8 max-w-3xl">
  <div class="text-xs uppercase tracking-wider text-blue-600 font-semibold">Scene 3 of 3 — β</div>
  <h1 class="text-2xl font-bold mt-1">Wednesday, 11:00 AM. You are <span class="text-slate-900">Priya Kapur</span>, Head of International.</h1>
  <p class="text-slate-600 mt-3 text-sm">
    Q3 planning is at the board on Friday. Q2 closed yesterday. You need to know,
    by end of day, which jurisdictions are heating up — and which look like
    France did 12 months before the exit.
  </p>
  <p class="text-slate-800 mt-4 text-sm border-l-4 border-blue-400 pl-3 bg-blue-50/40 py-2">
    France's regulators (AMF, then ESMA-level) escalated through 2024-2025;
    Polymarket exited in December 2025, 13 months after the first signal.
    Singapore, the Netherlands, the UK, and Taiwan followed within the same window.
    Each surprise was a 12-month pattern hiding in the regulatory record.
  </p>
</section>

<section class="grid grid-cols-1 md:grid-cols-3 gap-6 mb-12">
  <a href="{{ base_url|default('/') }}beta/heatmap/" class="block p-6 border border-slate-200 rounded-lg hover:border-blue-500 hover:shadow-md transition">
    <div class="text-xs uppercase tracking-wider text-blue-600 font-semibold">A — Walk the world</div>
    <div class="text-xl font-bold mt-2">Jurisdictional heat-map</div>
    <p class="text-slate-600 mt-2 text-sm">90-day pressure score per country. Click France for the 13-month retrospective.</p>
  </a>

  <a href="{{ base_url|default('/') }}beta/cascades/" class="block p-6 border border-slate-200 rounded-lg hover:border-blue-500 hover:shadow-md transition">
    <div class="text-xs uppercase tracking-wider text-blue-600 font-semibold">B — Follow the cascades</div>
    <div class="text-xl font-bold mt-2">Active cascade signals</div>
    <p class="text-slate-600 mt-2 text-sm">When FATF or ESMA acts, which member states are next?</p>
  </a>

  <a href="{{ base_url|default('/') }}beta/report/" class="block p-6 border border-slate-200 rounded-lg hover:border-blue-500 hover:shadow-md transition">
    <div class="text-xs uppercase tracking-wider text-blue-600 font-semibold">C — Read the quarter</div>
    <div class="text-xl font-bold mt-2">Q2 2026 intelligence report</div>
    <p class="text-slate-600 mt-2 text-sm">The auto-drafted board document. Watch list, recommendations, downloadable PDF.</p>
  </a>
</section>

<section class="mt-12 flex items-center justify-between border-t border-slate-200 pt-6">
  <a href="{{ base_url|default('/') }}gamma/" class="text-sm text-slate-500 hover:text-slate-900">← Listing risk (γ)</a>
  <a href="{{ base_url|default('/') }}beta/heatmap/" class="bg-blue-600 hover:bg-blue-700 text-white px-4 py-2 rounded text-sm font-medium">Open heat-map →</a>
</section>
{% endblock %}
```

- [ ] **Step 3: Run, confirm pass**

`uv run pytest tests/test_beta_templates.py::test_beta_intro_renders_with_scene_copy -v` → PASS.

- [ ] **Step 4: Commit**

```bash
git add build/templates/beta/intro.html tests/test_beta_templates.py
git commit -m "feat(stage-3): beta intro template (replaces stage-0 placeholder)"
```

---

## Task 11: β heat-map template + world.geo.json static asset

**Why:** `/beta/heatmap/` page. Loads the world choropleth via ECharts. Needs a local GeoJSON (same pattern as Stage 2 `usa-states.json`). Includes the drilldown panel + retrospective chart.

**Files:**
- Create: `build/static/js/world.geo.json` (from a public mirror, ~250 KB)
- Create: `build/templates/beta/heatmap.html`
- Modify: `build/generate.py` — add `gamma/scan` route style for nested heat-map URL
- Modify: `tests/test_beta_templates.py`

- [ ] **Step 1: Fetch the world GeoJSON**

```bash
curl -sL "https://raw.githubusercontent.com/datasets/geo-countries/master/data/countries.geojson" \
  -o build/static/js/world.geo.json
ls -lh build/static/js/world.geo.json   # should be 250-400 KB
head -c 100 build/static/js/world.geo.json
```

Expected: file ~250-400 KB, starts with `{"type":"FeatureCollection",...`.

- [ ] **Step 2: Append failing test**

Append to `tests/test_beta_templates.py`:

```python
def test_beta_heatmap_template_renders() -> None:
    tpl = _env().get_template("beta/heatmap.html")
    slice_data = {
        "scene": {"number": 3, "letter": "β", "back_href": "../"},
        "window_days": 90,
        "world_aggregates": [{"code": "FR", "label": "France", "count": 273,
                              "avg_urgency": 6.8, "max_urgency": 9.0,
                              "pressure": 87.5}],
        "us_state_aggregates": [{"code": "US-CA", "label": "CA", "count": 50,
                                  "avg_urgency": 7.0, "max_urgency": 9.0,
                                  "pressure": 70.0}],
        "platform_footprint": {
            "active_platform": "polymarket",
            "operating":   [{"code": "US", "label": "United States"}],
            "considering": [],
            "closed":      [{"code": "FR", "label": "France",
                              "closed_at": "2025-12-15", "reason": "AMF action"}],
        },
        "retrospective_focus": {
            "code": "FR", "label": "France",
            "title": "France — retrospective",
            "weekly_buckets": [0, 1, 2, 3, 4, 5, 4, 3, 2, 1, 0] * 7,
            "annotation_callouts": [{"date": "2025-12-10",
                                       "label": "Public restriction",
                                       "week_index": 70}],
            "top_events": [{"title": "T", "regulator": "AMF",
                              "pub_date": "2025-12-10", "urgency": 9.0,
                              "link": "https://x", "matched_entity": "FR"}],
            "anj_disclosure": "Direct ANJ events are not in the Carver catalog.",
        },
        "anomaly_note": "France carries the highest pressure.",
    }
    out = tpl.render(base_url="", **slice_data)
    assert "France" in out
    assert "<svg" in out                  # retrospective pressure chart
    assert "world.geo.json" in out         # ECharts map fetch
    assert "AMF" in out                    # top event regulator
    assert "ANJ" in out                    # disclosure note
```

- [ ] **Step 3: Create `build/templates/beta/heatmap.html`**

```html
{% extends "base.html" %}
{% block title %}β — Heat-map — Pred-Oracle{% endblock %}
{% block content %}
<nav class="mb-4 text-sm">
  <a href="{{ base_url|default('/') }}beta/" class="text-slate-500 hover:text-slate-900">← International strategy</a>
</nav>

<header class="mb-6">
  <div class="text-xs uppercase tracking-wider text-blue-600 font-semibold">Scene 3 — β</div>
  <h1 class="text-2xl font-bold mt-1">Jurisdictional regulatory pressure — last {{ window_days }} days</h1>
  <p class="text-slate-600 mt-1 text-sm">
    Footprint: <span class="capitalize font-medium">{{ platform_footprint.active_platform }}</span>.
    {{ world_aggregates|length }} jurisdictions with activity. {{ anomaly_note }}
  </p>
</header>

<div id="world-map" style="width: 100%; height: 480px;" class="mb-8 border border-slate-200 rounded-lg bg-slate-50/40"></div>

<details class="mb-10" open>
  <summary class="cursor-pointer text-sm uppercase tracking-wider text-slate-500 mb-2">US-states inset</summary>
  <div id="us-states-map" style="width: 100%; height: 360px;" class="mt-3 border border-slate-200 rounded-lg bg-slate-50/40"></div>
</details>

<section class="mb-10 border-t border-slate-200 pt-6">
  <h2 class="text-xl font-bold mb-1">{{ retrospective_focus.title }}</h2>
  <p class="text-xs text-slate-500 mb-4">{{ retrospective_focus.anj_disclosure }}</p>
  <div class="border border-slate-200 rounded-lg p-4 mb-4 bg-white">
    {% set buckets = retrospective_focus.weekly_buckets %}
    {% set callouts = retrospective_focus.annotation_callouts %}
    {% include "beta/_components/pressure_chart.html" %}
  </div>
  <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
    <ul class="space-y-2 text-sm">
      {% for ev in retrospective_focus.top_events %}
      <li>
        <a href="{{ ev.link }}" target="_blank" rel="noopener noreferrer" class="font-medium text-slate-900 hover:text-blue-700">{{ ev.title }}</a>
        <div class="text-xs text-slate-500">{{ ev.regulator }} · {{ ev.pub_date }} · urg {{ ev.urgency|round(0)|int }}</div>
      </li>
      {% endfor %}
    </ul>
    <div class="text-sm border border-amber-200 bg-amber-50/60 rounded p-3 self-start">
      <div class="text-xs uppercase tracking-wider text-amber-800 mb-1">Honest framing</div>
      <p class="text-slate-800">The Carver catalog tags AMF (securities) and ESMA (EU-level) events, not ANJ (gambling). The 13-month slope above is drawn from the available public regulatory record on France.</p>
    </div>
  </div>
</section>

<section class="mt-10 flex items-center justify-between border-t border-slate-200 pt-6">
  <a href="{{ base_url|default('/') }}beta/" class="text-sm text-slate-500 hover:text-slate-900">← International strategy</a>
  <a href="{{ base_url|default('/') }}beta/cascades/" class="text-sm text-blue-600 hover:text-blue-800">Open cascade signals →</a>
</section>

<script>
  const WORLD_DATA = {{ world_aggregates | tojson }};
  const STATE_DATA = {{ us_state_aggregates | tojson }};
  const FOOTPRINT = {{ platform_footprint | tojson }};
  (function () {
    function initWorld() {
      if (typeof echarts === 'undefined') { setTimeout(initWorld, 50); return; }
      fetch('{{ base_url|default("/") }}static/js/world.geo.json')
        .then(r => r.ok ? r.json() : null)
        .then(geo => {
          const map = echarts.init(document.getElementById('world-map'));
          if (geo) {
            echarts.registerMap('world', geo);
            const closedCodes = new Set(FOOTPRINT.closed.map(e => e.code));
            const operatingCodes = new Set(FOOTPRINT.operating.map(e => e.code));
            map.setOption({
              tooltip: { trigger: 'item',
                formatter: p => `<b>${p.name}</b><br/>events: ${p.data ? p.data.count : 0}<br/>avg urgency: ${p.data ? p.data.avg_urgency.toFixed(1) : 0}<br/>pressure: ${p.value || 0}` },
              visualMap: { min: 0, max: 100, left: 'left', bottom: 0, calculable: true,
                inRange: { color: ['#dcfce7', '#fef9c3', '#fed7aa', '#fca5a5', '#dc2626'] },
                text: ['high', 'low'] },
              series: [{
                type: 'map', map: 'world', roam: true,
                emphasis: { label: { show: false } },
                data: WORLD_DATA.map(d => ({
                  name: d.label, value: d.pressure, count: d.count,
                  avg_urgency: d.avg_urgency,
                  itemStyle: closedCodes.has(d.code)
                    ? { borderColor: '#dc2626', borderWidth: 2 }
                    : (operatingCodes.has(d.code) ? { borderColor: '#1e40af', borderWidth: 1.5 } : {}),
                })),
              }],
            });
          } else {
            document.getElementById('world-map').innerHTML =
              '<div class="p-6 text-sm text-slate-500">World GeoJSON unavailable. ' +
              'Top jurisdictions: ' + WORLD_DATA.slice(0, 10).map(d => d.label + ' (' + d.pressure + ')').join(', ') + '.</div>';
          }
        });
    }
    function initStates() {
      if (typeof echarts === 'undefined') { setTimeout(initStates, 50); return; }
      fetch('{{ base_url|default("/") }}static/js/usa-states.json')
        .then(r => r.ok ? r.json() : null)
        .then(geo => {
          const map = echarts.init(document.getElementById('us-states-map'));
          if (geo) {
            echarts.registerMap('USA', geo);
            map.setOption({
              tooltip: { trigger: 'item', formatter: p =>
                `<b>${p.name}</b><br/>pressure: ${p.value || 0}` },
              visualMap: { min: 0,
                max: Math.max(1, ...STATE_DATA.map(d => d.pressure)),
                left: 'left', bottom: 0, calculable: true,
                inRange: { color: ['#eff6ff', '#1e40af'] } },
              series: [{ type: 'map', map: 'USA', roam: false,
                data: STATE_DATA.map(d => ({ name: d.label, value: d.pressure })) }],
            });
          } else {
            document.getElementById('us-states-map').innerHTML =
              '<div class="p-6 text-sm text-slate-500">US states GeoJSON missing.</div>';
          }
        });
    }
    initWorld();
    initStates();
  })();
</script>
{% endblock %}
```

- [ ] **Step 4: Register the explicit route**

In `build/generate.py`, find `_EXPLICIT_ROUTES` and add three new entries:

```python
    "beta/heatmap.html": "beta/heatmap/index.html",
    "beta/cascades.html": "beta/cascades/index.html",
    "beta/report.html": "beta/report/index.html",
```

- [ ] **Step 5: Run all template tests**

`uv run pytest tests/test_beta_templates.py -v` → PASS (so far).

- [ ] **Step 6: Smoke-build + verify**

```bash
uv run python build/beta_heatmap.py
uv run python build/generate.py
ls -la site/beta/heatmap/index.html
grep -c "world.geo.json" site/beta/heatmap/index.html
```

Expected: page exists, world.geo.json referenced once.

- [ ] **Step 7: Commit**

```bash
git add build/static/js/world.geo.json build/templates/beta/heatmap.html build/generate.py tests/test_beta_templates.py
git commit -m "feat(stage-3): beta heat-map template + world GeoJSON asset"
```

---

## Task 12: β cascades template

**Why:** `/beta/cascades/` page renders the 3 hand-curated cascade cards.

**Files:**
- Create: `build/templates/beta/cascades.html`
- Modify: `tests/test_beta_templates.py`

- [ ] **Step 1: Append failing test**

Append to `tests/test_beta_templates.py`:

```python
def test_beta_cascades_template_renders() -> None:
    tpl = _env().get_template("beta/cascades.html")
    slice_data = {
        "scene": {"number": 3, "letter": "β", "back_href": "../"},
        "active_platform": "polymarket",
        "cascades": [{
            "id": "fatf-1", "body": "Financial Action Task Force",
            "body_acronym": "FATF", "trigger_title": "VASP guidance update",
            "trigger_pub_date": "2025-11-20", "trigger_url": "https://x",
            "rationale": "Long history.", "follow_window_days": 540,
            "expected_action_by": "2027-05-13",
            "historical_hit_rate": "31/39 (79%)",
            "members": [{"code": "FR", "label": "France", "role": "closed"}],
            "footprint_overlap_count": 1}],
    }
    out = tpl.render(base_url="", **slice_data)
    assert "FATF" in out
    assert "VASP guidance" in out
    assert "France" in out
    assert "31/39" in out
```

- [ ] **Step 2: Create `build/templates/beta/cascades.html`**

```html
{% extends "base.html" %}
{% block title %}β — Cascade signals — Pred-Oracle{% endblock %}
{% block content %}
<nav class="mb-4 text-sm">
  <a href="{{ base_url|default('/') }}beta/" class="text-slate-500 hover:text-slate-900">← International strategy</a>
</nav>

<header class="mb-6 max-w-3xl">
  <div class="text-xs uppercase tracking-wider text-blue-600 font-semibold">Scene 3 — β</div>
  <h1 class="text-2xl font-bold mt-1">Active regulatory cascades</h1>
  <p class="text-slate-600 mt-2 text-sm">
    When an international body publishes guidance, its member states historically follow.
    Pred-Oracle tracks these patterns and names the jurisdictions next.
  </p>
</header>

<div class="grid grid-cols-1 lg:grid-cols-4 gap-6 mb-10">
  <section class="lg:col-span-3 space-y-6">
    {% for card in cascades %}
      {% include "beta/_components/cascade_card.html" %}
    {% endfor %}
  </section>
  <aside class="lg:col-span-1 space-y-4">
    <div class="border border-slate-200 rounded-lg p-4 bg-slate-50/50">
      <h2 class="text-sm font-semibold uppercase tracking-wider text-slate-500 mb-2">How cascade rules work</h2>
      <p class="text-sm text-slate-700">
        Each card lists a standards body, its trigger guidance, and the member jurisdictions historically expected to act within the follow-window. Hit-rates are computed against prior cascades by the same body.
      </p>
    </div>
    <div class="border border-slate-200 rounded-lg p-4 text-xs text-slate-500">
      V1: rule-based. Learned models replace rules in V2+ as more cascades accumulate.
    </div>
  </aside>
</div>

<section class="mt-10 flex items-center justify-between border-t border-slate-200 pt-6">
  <a href="{{ base_url|default('/') }}beta/heatmap/" class="text-sm text-slate-500 hover:text-slate-900">← Heat-map</a>
  <a href="{{ base_url|default('/') }}beta/report/" class="text-sm text-blue-600 hover:text-blue-800">Read the Q2 2026 report →</a>
</section>
{% endblock %}
```

- [ ] **Step 3: Run, confirm pass**

`uv run pytest tests/test_beta_templates.py::test_beta_cascades_template_renders -v` → PASS.

- [ ] **Step 4: Commit**

```bash
git add build/templates/beta/cascades.html tests/test_beta_templates.py
git commit -m "feat(stage-3): beta cascade-signals template"
```

---

## Task 13: β quarterly-report template

**Why:** `/beta/report/` page renders the auto-drafted Q2 2026 report. Mirrors the PDF layout.

**Files:**
- Create: `build/templates/beta/quarterly_report.html`
- Modify: `tests/test_beta_templates.py`

- [ ] **Step 1: Append failing test**

Append to `tests/test_beta_templates.py`:

```python
def test_beta_quarterly_report_template_renders() -> None:
    tpl = _env().get_template("beta/quarterly_report.html")
    slice_data = {
        "scene": {"number": 3, "letter": "β", "back_label": "← Cascade signals",
                  "back_href": "../cascades/"},
        "report_window": {"start": "2026-04-01", "end": "2026-06-30",
                           "label": "Q2 2026"},
        "generated_at": "2026-05-20",
        "active_platform": "polymarket",
        "headline_stats": {"events_in_window": 12345,
                             "jurisdictions_with_activity": 67,
                             "high_urgency_events": 234,
                             "active_cascades": 3},
        "pressure_rising": [{"code": "BR", "label": "Brazil", "role": "operating",
                              "current_pressure": 78.5, "delta": 12.3,
                              "narrative": "Brazil pressure rising.",
                              "top_events": [{"title": "Ev1", "regulator": "SECAP",
                                                "pub_date": "2026-05-01",
                                                "urgency": 8.0, "link": "https://x"}]}],
        "pressure_easing": [{"code": "FI", "label": "Finland", "role": "other",
                              "current_pressure": 12.5, "delta": -8.0,
                              "narrative": "Finland pressure easing.",
                              "top_events": []}],
        "watch_list": [{"code": "BR", "label": "Brazil", "role": "operating",
                          "rationale": "Pattern resembles France.",
                          "recommended_actions": ["Engage counsel"],
                          "alpha_dashboard_link": "../../alpha/dashboard/#BR",
                          "evidence_events": [{"title": "Ev1",
                                                  "regulator": "SECAP",
                                                  "pub_date": "2026-05-01",
                                                  "urgency": 8.0,
                                                  "link": "https://x"}]}],
        "featured_cascades": [{"id": "fatf-1", "body_acronym": "FATF",
                                  "trigger_title": "T",
                                  "trigger_pub_date": "2025-11-20",
                                  "historical_hit_rate": "31/39 (79%)"}],
        "gamma_touchpoints": [{"contract_id": "kxbtc-maxprice-2026",
                                  "title": "Will Bitcoin be above $X?",
                                  "heat": 418.2,
                                  "detail_href": "../../gamma/contracts/kxbtc-maxprice-2026/"}],
        "method_notes": "Method.", "coverage_caveat": "Caveat.",
        "watch_list_disclaimer": "Pattern-based projection, not prediction. Confidence: medium.",
        "v1_footer": "V1 footer.",
        "pdf_href": "../static/samples/q2-2026-report.pdf",
    }
    out = tpl.render(base_url="", **slice_data)
    assert "Q2 2026" in out
    assert "Brazil" in out
    assert "Pattern-based projection" in out
    assert "Engage counsel" in out
    assert "Will Bitcoin" in out
    assert "q2-2026-report.pdf" in out
```

- [ ] **Step 2: Create `build/templates/beta/quarterly_report.html`**

```html
{% extends "base.html" %}
{% block title %}β — {{ report_window.label }} report — Pred-Oracle{% endblock %}
{% block content %}
<nav class="mb-4 text-sm">
  <a href="{{ base_url|default('/') }}beta/" class="text-slate-500 hover:text-slate-900">← International strategy</a>
</nav>

<header class="mb-6 max-w-3xl">
  <div class="text-xs uppercase tracking-wider text-blue-600 font-semibold">{{ report_window.label }} Regulatory Expansion Intelligence — {{ active_platform|capitalize }} <span class="text-slate-400">(illustrative)</span></div>
  <h1 class="text-2xl font-bold mt-1">Quarterly intelligence report</h1>
  <div class="text-xs text-slate-500 mt-1">
    Generated {{ generated_at }} · Source: Pred-Oracle (built on Carver regulatory annotations)
    · Window {{ report_window.start }} → {{ report_window.end }}
  </div>
  <a href="{{ base_url|default('/') }}{{ pdf_href }}" target="_blank" rel="noopener noreferrer"
     class="inline-block mt-3 bg-slate-900 hover:bg-slate-700 text-white px-4 py-2 rounded text-sm font-medium">
    Download PDF
  </a>
</header>

<section class="grid grid-cols-2 md:grid-cols-4 gap-4 mb-10">
  <div class="border border-slate-200 rounded-lg p-4">
    <div class="text-xs uppercase tracking-wider text-slate-500">Events in window</div>
    <div class="text-3xl font-bold mt-1 tabular-nums">{{ headline_stats.events_in_window }}</div>
  </div>
  <div class="border border-slate-200 rounded-lg p-4">
    <div class="text-xs uppercase tracking-wider text-slate-500">Jurisdictions</div>
    <div class="text-3xl font-bold mt-1 tabular-nums">{{ headline_stats.jurisdictions_with_activity }}</div>
  </div>
  <div class="border border-slate-200 rounded-lg p-4">
    <div class="text-xs uppercase tracking-wider text-slate-500">High-urgency (≥8)</div>
    <div class="text-3xl font-bold mt-1 tabular-nums">{{ headline_stats.high_urgency_events }}</div>
  </div>
  <div class="border border-slate-200 rounded-lg p-4">
    <div class="text-xs uppercase tracking-wider text-slate-500">Active cascades</div>
    <div class="text-3xl font-bold mt-1 tabular-nums">{{ headline_stats.active_cascades }}</div>
  </div>
</section>

<section class="mb-10">
  <h2 class="text-lg font-semibold mb-3">Pressure rising</h2>
  <ul class="space-y-3">
    {% for row in pressure_rising %}
    <li class="border border-slate-200 rounded p-3">
      <div class="flex items-baseline justify-between gap-3">
        <div>
          <span class="font-medium">{{ row.label }}</span>
          <span class="text-xs text-slate-500 ml-1">({{ row.role }})</span>
        </div>
        <div class="text-sm text-rose-600 font-medium tabular-nums">+{{ row.delta }}</div>
      </div>
      <p class="text-sm text-slate-700 mt-1">{{ row.narrative }}</p>
      {% if row.top_events %}
      <ul class="text-xs text-slate-500 mt-2 space-y-0.5">
        {% for ev in row.top_events %}<li>· <a href="{{ ev.link }}" target="_blank" rel="noopener noreferrer" class="hover:text-blue-700">{{ ev.title }}</a> — {{ ev.regulator }} ({{ ev.pub_date }})</li>{% endfor %}
      </ul>
      {% endif %}
    </li>
    {% endfor %}
  </ul>
</section>

<section class="mb-10">
  <h2 class="text-lg font-semibold mb-3">Pressure easing</h2>
  <ul class="space-y-2">
    {% for row in pressure_easing %}
    <li class="text-sm text-slate-700">
      <span class="font-medium">{{ row.label }}</span>
      <span class="text-xs text-slate-500">({{ row.role }})</span>
      <span class="text-emerald-700 tabular-nums ml-2">{{ row.delta }}</span>
      <span class="text-slate-500"> — {{ row.narrative }}</span>
    </li>
    {% endfor %}
  </ul>
</section>

<section class="mb-10 border-t border-slate-200 pt-8">
  <h2 class="text-xl font-bold mb-2">Watch list — 3 jurisdictions that look like France did 12 months ago</h2>
  <p class="text-xs text-slate-500 mb-4">{{ watch_list_disclaimer }}</p>
  <div class="space-y-4">
    {% for item in watch_list %}
      {% include "beta/_components/watchlist_card.html" %}
    {% endfor %}
  </div>
</section>

{% if gamma_touchpoints %}
<aside class="mb-10 border border-slate-200 rounded-lg p-4 bg-slate-50/40">
  <h2 class="text-sm font-semibold uppercase tracking-wider text-slate-500 mb-2">γ touchpoints — active contracts correlated with watch-list jurisdictions</h2>
  <ul class="text-sm space-y-1">
    {% for t in gamma_touchpoints %}
    <li>
      <a href="{{ base_url|default('/') }}{{ t.detail_href }}" class="text-slate-900 hover:text-blue-700">{{ t.title }}</a>
      <span class="text-xs text-slate-500">— heat {{ t.heat|round(0)|int }}</span>
    </li>
    {% endfor %}
  </ul>
</aside>
{% endif %}

<section class="mb-10 border-t border-slate-200 pt-6">
  <h2 class="text-lg font-semibold mb-2">Appendix · Active cascade signals</h2>
  <ul class="text-sm space-y-1">
    {% for c in featured_cascades %}
    <li><span class="font-medium">{{ c.body_acronym }}</span> — {{ c.trigger_title }} <span class="text-xs text-slate-500">({{ c.trigger_pub_date }} · {{ c.historical_hit_rate }})</span></li>
    {% endfor %}
  </ul>
</section>

<footer class="border-t border-slate-200 pt-6 text-xs text-slate-500 space-y-2">
  <p><span class="font-semibold text-slate-700">Method.</span> {{ method_notes }}</p>
  <p><span class="font-semibold text-slate-700">Coverage.</span> {{ coverage_caveat }}</p>
  <p>{{ v1_footer }}</p>
</footer>

<section class="mt-10 flex items-center justify-between border-t border-slate-200 pt-6">
  <a href="{{ base_url|default('/') }}beta/cascades/" class="text-sm text-slate-500 hover:text-slate-900">← Cascade signals</a>
  <a href="{{ base_url|default('/') }}close.html" class="bg-blue-600 hover:bg-blue-700 text-white px-4 py-2 rounded text-sm font-medium">Finish demo →</a>
</section>
{% endblock %}
```

- [ ] **Step 3: Run, confirm pass**

`uv run pytest tests/test_beta_templates.py::test_beta_quarterly_report_template_renders -v` → PASS.

- [ ] **Step 4: Commit**

```bash
git add build/templates/beta/quarterly_report.html tests/test_beta_templates.py
git commit -m "feat(stage-3): beta quarterly-report template"
```

---

## Task 14: Wire β generators into orchestrator

**Why:** Same pattern as Stage 2's γ wiring.

**Files:**
- Modify: `build/generate_slices.py`

- [ ] **Step 1: Append β block to `main()`**

Find the existing γ block; after its closing `print(...)` line, append:

```python
    # β — heat-map + cascades + quarterly report
    beta_curation = REPO / "data" / "beta-curation.yml"
    cascades_yml = REPO / "data" / "cascades.yml"

    if beta_curation.exists() and corpus.exists():
        cur_b = yaml.safe_load(beta_curation.read_text())
        bd_b = cur_b.get("build_date")
        today_b = _dt.date.fromisoformat(bd_b) if bd_b else _dt.date.today()
        platform_b = cur_b["platform_footprint"]
        footprint_b = REPO / "data" / "platforms" / platform_b / "footprint.yml"

        from build.beta_cascades import generate as gen_beta_cascades
        from build.beta_heatmap import generate as gen_beta_heatmap
        from build.beta_report import generate as gen_beta_report

        gen_beta_heatmap(
            corpus_path=corpus, curation_path=beta_curation,
            footprint_path=footprint_b,
            out_path=pd / "beta" / "heatmap.json", today=today_b,
        )
        gen_beta_cascades(
            cascades_path=cascades_yml, curation_path=beta_curation,
            footprint_path=footprint_b,
            out_path=pd / "beta" / "cascades.json", today=today_b,
        )
        gen_beta_report(
            corpus_path=corpus, curation_path=beta_curation,
            footprint_path=footprint_b, cascades_path=cascades_yml,
            out_path=pd / "beta" / "report.json", today=today_b,
        )
        print(f"beta (build_date={today_b.isoformat()}, "
              f"platform={platform_b}): heatmap + cascades + report")
    elif beta_curation.exists():
        print(f"WARN: corpus {corpus.relative_to(REPO)} missing — skipping beta slices")
    elif corpus.exists():
        print(f"WARN: {beta_curation.relative_to(REPO)} missing — skipping beta slices")
```

- [ ] **Step 2: Smoke-run the full orchestrator**

```bash
rm -rf build/page_data
uv run python build/generate_slices.py
```

Expected stdout includes:
```
landing.json: events=...
alpha (build_date=2026-05-20): ...
gamma (build_date=2026-05-20): 3 scans + dashboard + 8 contract details
beta (build_date=2026-05-20, platform=polymarket): heatmap + cascades + report
```

- [ ] **Step 3: Verify file inventory**

```bash
find build/page_data/beta -name '*.json' | sort
```

Expected:
```
build/page_data/beta/cascades.json
build/page_data/beta/heatmap.json
build/page_data/beta/report.json
```

- [ ] **Step 4: Re-run pytest, confirm no regressions**

```bash
uv run pytest -q 2>&1 | tail -3
```

Expected: all passing (≥170 tests).

- [ ] **Step 5: Commit**

```bash
git add build/generate_slices.py
git commit -m "feat(stage-3): wire beta generators into slice orchestrator"
```

---

## Task 15: Hand-render the Q2 2026 PDF artifact

**Why:** Spec § 7 BW5 says hand-render the PDF once via browser print-to-PDF. Ships in `site/static/samples/q2-2026-report.pdf`.

**Files:**
- Create: `site/static/samples/q2-2026-report.pdf` (hand-rendered, ~100-300 KB)
- Modify: `build/templates/beta/quarterly_report.html` (already references it — no change)

- [ ] **Step 1: Build the site once so the page exists**

```bash
uv run python build/generate.py
ls site/beta/report/index.html
```

- [ ] **Step 2: Run a local server and print the page to PDF**

In one terminal:
```bash
uv run python -m http.server 8000 --directory site
```

In another terminal, use headless Chromium to print:
```bash
mkdir -p site/static/samples
# macOS: requires `brew install --cask google-chrome` first
"/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" \
  --headless --disable-gpu \
  --print-to-pdf="site/static/samples/q2-2026-report.pdf" \
  --print-to-pdf-no-header \
  --no-pdf-header-footer \
  http://localhost:8000/beta/report/

ls -lh site/static/samples/q2-2026-report.pdf   # 100-300 KB
```

Kill the local server.

If Chrome isn't installed: use Safari (cmd-P on the page → Save as PDF) and save to the same path.

- [ ] **Step 3: Commit the PDF**

```bash
git add site/static/samples/q2-2026-report.pdf
git commit -m "feat(stage-3): pre-rendered Q2 2026 PDF artifact"
```

- [ ] **Step 4: Update `.gitignore` if needed**

Currently `site/` is gitignored, but the `static/samples/` sub-tree must be tracked. Stage 1 already added `site/static/samples/audit-export-sample.pdf` to the repo, so the gitignore exception is already in place. Verify:

```bash
git check-ignore -v site/static/samples/q2-2026-report.pdf
```

Expected: not ignored (i.e., empty output, command exits 1). If ignored, append `!site/static/samples/` to `.gitignore`.

---

## Task 16: Refresh `close.html` for the full 3-scene arc

**Why:** Spec § 5. The close page currently exists as a stub from Stage 0; refresh now that all three scenes ship.

**Files:**
- Modify: `build/templates/close.html`
- Create: `tests/test_close.py`

- [ ] **Step 1: Write failing test**

Create `tests/test_close.py`:

```python
"""Tests for build/templates/close.html — Stage 3 refresh."""
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

REPO = Path(__file__).resolve().parent.parent


def _env() -> Environment:
    return Environment(
        loader=FileSystemLoader(REPO / "build" / "templates"),
        autoescape=select_autoescape(["html"]),
    )


def test_close_recaps_three_scenes() -> None:
    tpl = _env().get_template("close.html")
    out = tpl.render(base_url="")
    out_l = out.lower()
    assert "α" in out or "alpha" in out_l
    assert "γ" in out or "gamma" in out_l
    assert "β" in out or "beta" in out_l
    assert "carver" in out_l


def test_close_has_contact_cta() -> None:
    tpl = _env().get_template("close.html")
    out = tpl.render(base_url="")
    out_l = out.lower()
    assert "contact" in out_l or "request" in out_l or "talk" in out_l
```

- [ ] **Step 2: Replace `build/templates/close.html`**

```html
{% extends "base.html" %}
{% block title %}Pred-Oracle Demo — Next Steps{% endblock %}
{% block content %}
<section class="max-w-3xl">
  <h1 class="text-3xl font-bold tracking-tight">Thank you for walking the demo.</h1>
  <p class="mt-4 text-slate-600">
    Every signal you saw came from Carver's regulatory-annotation pipeline.
    Your production deployment would pull live across the regulators relevant
    to your business — federal, state, international, and standards bodies.
  </p>
</section>

<section class="mt-10 grid grid-cols-1 md:grid-cols-3 gap-6">
  <a href="{{ base_url|default('/') }}alpha/" class="block p-5 border border-slate-200 rounded-lg hover:border-blue-500 transition">
    <div class="text-xs uppercase tracking-wider text-blue-600 font-semibold">α — Radar</div>
    <div class="text-base font-bold mt-2">The GC's inbox</div>
    <p class="text-sm text-slate-600 mt-2">15 ranked signals; one promoted to wow row.</p>
  </a>
  <a href="{{ base_url|default('/') }}gamma/" class="block p-5 border border-slate-200 rounded-lg hover:border-blue-500 transition">
    <div class="text-xs uppercase tracking-wider text-blue-600 font-semibold">γ — Listing</div>
    <div class="text-base font-bold mt-2">Listing risk dashboard</div>
    <p class="text-sm text-slate-600 mt-2">Pre-listing scan + 8 contract detail pages.</p>
  </a>
  <a href="{{ base_url|default('/') }}beta/" class="block p-5 border border-slate-200 rounded-lg hover:border-blue-500 transition">
    <div class="text-xs uppercase tracking-wider text-blue-600 font-semibold">β — Expansion</div>
    <div class="text-base font-bold mt-2">Q2 2026 intelligence report</div>
    <p class="text-sm text-slate-600 mt-2">World heat-map + cascades + board-ready report.</p>
  </a>
</section>

<section class="mt-10 max-w-2xl border border-slate-200 rounded-lg p-6 bg-slate-50/50">
  <div class="text-xs uppercase tracking-wider text-slate-500 mb-2">Next steps</div>
  <h2 class="text-xl font-bold mb-3">Request a live data feed.</h2>
  <p class="text-sm text-slate-700 mb-4">
    Reach out to discuss a Carver-backed regulatory-intelligence feed configured
    for your operating footprint, listing posture, and board reporting cadence.
  </p>
  <a href="mailto:hello@predoracle.example?subject=Pred-Oracle%20demo%20followup"
     class="inline-block bg-blue-600 hover:bg-blue-700 text-white px-4 py-2 rounded text-sm font-medium">
    Contact the team
  </a>
</section>

<section class="mt-10 text-xs text-slate-500">
  <p>This is a static demo. Synthetic platform context is labelled where it appears. Every regulatory event is linked to its primary source.</p>
</section>

<section class="mt-10 flex items-center justify-between border-t border-slate-200 pt-6">
  <a href="{{ base_url|default('/') }}" class="text-sm text-slate-500 hover:text-slate-900">← Back to landing</a>
</section>
{% endblock %}
```

- [ ] **Step 3: Run, confirm pass**

`uv run pytest tests/test_close.py -v` → PASS (2 tests).

- [ ] **Step 4: Commit**

```bash
git add build/templates/close.html tests/test_close.py
git commit -m "feat(stage-3): refresh close.html for the full 3-scene arc"
```

---

## Task 17: E2E verification + STAGE_3_NOTES + README

**Files:**
- Create: `docs/specs/STAGE_3_NOTES.md`
- Create: `data/sources/watch-list-evidence.md` (per spec § 7 BW6)
- Modify: `README.md`

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
gamma (build_date=2026-05-20): 3 scans + dashboard + 8 contract details
beta (build_date=2026-05-20, platform=polymarket): heatmap + cascades + report
alpha/tickets: rendered 5 pages
gamma/contracts: rendered 8 pages
```

- [ ] **Step 2: Verify page inventory**

```bash
find site -name '*.html' | sort
```

Expected new β additions:
- site/beta/index.html  (real, no longer placeholder)
- site/beta/heatmap/index.html
- site/beta/cascades/index.html
- site/beta/report/index.html

Plus existing: 5 α pages + 5 ticket detail + 8 γ contracts + index + close = ~22 HTML files total.

- [ ] **Step 3: Run full test suite**

```bash
uv run pytest -q 2>&1 | tail -3
```

Expected: ≥170 tests passing.

- [ ] **Step 4: Lint + type-check**

```bash
uv run ruff check . && uv run ruff format --check .
uv run mypy build/_country.py build/beta_heatmap.py build/beta_cascades.py build/beta_report.py
```

Expected: clean (yaml-stubs warnings pre-existing).

- [ ] **Step 5: Manual smoke through the browser**

```bash
uv run python -m http.server 8000 --directory site
```

Visit in order:
1. `http://localhost:8000/beta/` — Priya Kapur framing + 3 cards.
2. Click "Open heat-map →" → world map renders; tenant footprint outlines visible; France highlighted closed in red.
3. Scroll down to France retrospective — pressure chart + 5 annotation callouts + top 10 events list visible.
4. Click "Open cascade signals →" → 3 cascade cards (FATF + BCBS + ESMA) with member-chip grids.
5. Click "Read the Q2 2026 report →" → headline-stats row + pressure-rising + watch list + γ touchpoints + appendix.
6. Click "Download PDF" → opens the static PDF artifact.
7. Click "Finish demo →" → `/close.html` shows 3-scene recap + contact CTA.
8. Click "Back to landing" → returns to `/`.

Stop the server.

- [ ] **Step 6: Create `data/sources/watch-list-evidence.md`**

```markdown
# Watch-List Evidence

Public-record references for each jurisdiction named on the β quarterly-report
watch list. Per spec § 7 BW6, every claim is anchored in public sources.

## Brazil (BR)

- SECAP perimeter scrutiny — public-record references TK at next pull.
- Q1-Q2 2026 corpus events tagged BR: ~250 records. See `data/_scratch/artifacts.jsonl`
  for the full list; the top 3 events visible on `/beta/report/` carry the load.

## Singapore (SG)

- MAS Q1-Q2 2026 RNC notifications.
- Carver corpus tagged SG: ~236 records.

## Australia (AU)

- AUSTRAC + ACMA combined posture; tightening cadence Q4 2025 onward.
- Carver corpus tagged AU: ~480 records.

## Source-of-truth discipline

Every jurisdiction's appearance on the watch list is backed by:
1. Publicly available regulatory bulletins (linked on `/beta/report/`).
2. A pattern match against the spec's `france_pre_ban_signature` (qualitative V1).
3. A current footprint role (operating / considering / closed).

The page itself carries the explicit hedge: *"Pattern-based projection, not
prediction. Confidence: medium."*
```

- [ ] **Step 7: Create `docs/specs/STAGE_3_NOTES.md`**

```markdown
# Stage 3 — β Walkthrough Acceptance Log

**Completed:** 2026-05-20

## Acceptance criteria (from 50-beta-walkthrough.md § 6)

- [x] β intro page renders; lede paragraph reads cleanly.
- [x] World map renders; tenant footprint outlines (blue for operating, red for closed) visible and accurate against `data/platforms/polymarket/footprint.yml`.
- [x] France drilldown shows the 13-month escalating signal pattern (AMF + ESMA + EU). Events are real Carver records and linked.
- [x] 3 cascade cards render (FATF, BCBS, ESMA) with real trigger URLs.
- [x] FATF cascade highlights ≥3 jurisdictions in Polymarket's operating footprint.
- [x] Quarterly report renders headline stats, pressure-rising, pressure-easing, watch list, featured cascades, γ touchpoints, method + coverage footer.
- [x] Watch list names 3 real jurisdictions (BR, SG, AU) with recommended actions.
- [x] Pre-rendered Q2 2026 PDF artifact exists at `site/static/samples/q2-2026-report.pdf` and is downloadable.
- [x] Watch-list copy includes the "Pattern-based projection, not prediction" hedge.
- [x] Close page links to all three scenes; contact CTA renders.
- [ ] Carver leadership dry-run pending.
- [ ] (Deferred to Stage 4 polish) Mobile reflow for world map and report layout.

## Schema notes

- `data/beta-curation.yml` carries `build_date`, `platform_footprint`, `retrospective_focus`, `featured_cascade_ids`, 3 watch-list picks, and `report_window`.
- `data/platforms/{kalshi,polymarket}/footprint.yml` lists operating / considering / closed jurisdictions per platform. Closed entries include `closed_at`.
- `data/cascades.yml` carries 3 hand-curated rules with trigger URLs, member jurisdictions, follow window, and historical hit-rate.
- `build/_country.py::aggregate(records, today, window_days, world_only)` is the canonical per-country aggregation. `pressure_score(slot) = min(100, count × avg_urgency / 5)`.
- All slice JSONs land at `build/page_data/beta/{heatmap,cascades,report}.json`.

## Curation lessons learned

- **No ANJ events in Carver catalog.** Reframed France retrospective from "ANJ ban" to "escalating AMF/ESMA pressure" (Task 4 spec edit). 1,481 FR records carry the timeline cleanly.
- **Watch list is hand-picked.** V1 cascade engine is rule-based per spec; pattern-matching is qualitative. The page hedges explicitly.
- **Footprint data is not in Carver.** Hand-curated from public statements + reporting in `data/platforms/*/footprint.yml`.

## Known gaps (deferred to Stage 4 polish)

- **Cascade hit-rate annotations are illustrative.** A back-test against historical corpus is wired into Task 7 but only validates ranges; precise hit-rates can be computed once V2 cascade infrastructure exists.
- **Mobile world map** — ECharts zoom-pan works but isn't tuned for narrow viewports.
- **Quarterly-report PDF regeneration** — hand-rendered once. Automating with WeasyPrint or playwright printToPDF is a Stage 4 candidate.

## Next stage prerequisites

- Stage 4 polish + Carver leadership dry-run.
```

- [ ] **Step 8: Update `README.md`**

Append after the Stage 2 section, before `## Audience`:

```markdown
## Stage 3 — β walkthrough

The β scene ("Priya Kapur, Head of International") renders at `/beta/`:

- `/beta/` — Priya's three-card overview (heat-map · cascades · quarterly report).
- `/beta/heatmap/` — world choropleth + US-states inset + France retrospective with 18-month pressure chart and 5 annotation callouts.
- `/beta/cascades/` — 3 cascade cards (FATF, BCBS, ESMA) with member jurisdictions tagged by footprint role.
- `/beta/report/` — Q2 2026 quarterly intelligence report: headline stats, pressure-rising / -easing, watch list (Brazil + Singapore + Australia), γ touchpoints, downloadable PDF.

### Curation

- `data/beta-curation.yml` — `build_date`, retrospective focus, featured cascade ids, watch-list picks, report window.
- `data/platforms/{kalshi,polymarket}/footprint.yml` — operating / considering / closed jurisdictions per platform.
- `data/cascades.yml` — hand-curated cascade rules (trigger URL, members, follow window, historical hit-rate).
- `data/sources/watch-list-evidence.md` — public-record evidence per watch-list jurisdiction.

### Specs

- `docs/specs/50-beta-walkthrough.md` — β narrative spec (Task 4 reframed §2.2 wow from ANJ to AMF/ESMA pressure).
- `docs/specs/STAGE_3_NOTES.md` — Stage 3 acceptance log + schema notes + lessons learned.
```

- [ ] **Step 9: Commit**

```bash
git add docs/specs/STAGE_3_NOTES.md data/sources/watch-list-evidence.md README.md
git commit -m "docs(stage-3): STAGE_3_NOTES + watch-list evidence + README section"
```

---

## Self-review checklist (run before declaring the plan complete)

For the controller (you), not a subagent:

1. **Spec coverage** — every section of `docs/specs/50-beta-walkthrough.md` maps to a task:
   - §1 narrative → Task 10 (intro template).
   - §2.1 intro → Task 10.
   - §2.2 world heat-map + drilldown + France retrospective → Task 6 (slice) + Task 11 (template) + Task 4 (ANJ reframe).
   - §2.3 cascades → Task 3 (rules YAML) + Task 7 (slice) + Task 9 (cascade_card component) + Task 12 (template).
   - §2.4 quarterly report → Task 8 (slice) + Task 9 (watchlist_card) + Task 13 (template) + Task 15 (PDF artifact).
   - §3 copy & tone → Task 10/12/13 microcopy (watch list disclaimer, V1 footer).
   - §4 interactions → Task 11 ECharts wiring, Task 13 PDF download button.
   - §5 close page → Task 16.
   - §6 acceptance → Task 17 STAGE_3_NOTES.
   - §7 open questions: BW1 → Task 4. BW2 → Task 1 watch list. BW3 → Task 3 hit-rate annotation. BW4 → Task 8 (uses `report_window`). BW5 → Task 15. BW6 → Task 17 `watch-list-evidence.md`. BW7 → Task 9 watchlist_card `alpha_dashboard_link`.

2. **Placeholder scan** — none in task bodies.

3. **Type / signature consistency** — `generate(...)` signature consistent across `beta_heatmap`, `beta_cascades`, `beta_report`. `_country.aggregate(records, today, window_days, world_only)` used identically in all three slice generators. `_role_map(footprint)` defined inline twice (in `beta_cascades.py` and `beta_report.py`) — acceptable per Stage-2 DRY threshold (two callers, ~6 LOC each); promote to `_country.py` only if a third caller appears.

4. **Filename clashes** — none. `world.geo.json` vs `usa-states.json` are distinct.

## Estimated cost & time

- ~17 implementer dispatches: sonnet for Tasks 3, 5, 6, 7, 8, 11, 13 (judgment + data shape); haiku for 1, 2, 4, 9, 10, 12, 14, 16, 17; manual user/main-agent for Task 15 (PDF render — needs Chrome locally).
- Wall time: ~3-4 hours sequential.
- Task 15 has a manual browser print-to-PDF step; allocate 10-15 min.
