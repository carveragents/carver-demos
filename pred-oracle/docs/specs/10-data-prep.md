# Data Preparation

> **Stage 0 deliverable.** Before any page is built, this spec produces the JSON data slices that every demo page renders against.
>
> **Source of truth.** Real Carver-annotated regulatory events (sibling repo `../carver-dags/workflows/entry_annotation/`). Synthetic platform context is allowed only where labelled "synthetic" below.

---

## 1. Inputs

### 1.1 Carver annotations

- **How we pull:** the official **`carver-feeds-sdk`** Python package (https://github.com/carveragents/carver-feeds-sdk; PyPI: `carver-feeds-sdk`). The SDK wraps `https://app.carveragents.ai/api/v1/feeds/*` (21 endpoints — list topics, list feeds, list entries, entry detail, search, date filtering). Auth via `CARVER_API_KEY` env var.
- **Three-layer access:** the SDK exposes `get_client()` (raw HTTP), `create_data_manager()` (DataFrames), `create_query_engine()` (fluent chainable filters). The query engine is the right interface for our build script.
- **Caveat — annotation depth:** the feeds-SDK returns entries with `entry_title`, `entry_description`, `entry_content_markdown`, `entry_link`, dates, and topic/feed metadata. Whether it also surfaces the full Appendix-A annotation fields (`update_type`, `regulatory_source`, `impacted_business`, `urgency_score`, `impact_score`, `effective_date`, etc.) depends on whether the Carver platform attaches annotation results to entries. **Stage 0 must verify this against a live call** (open question DP1 below). Two contingency paths:
  - **If the SDK surfaces annotated fields:** straight pull, no further work.
  - **If it only returns raw entries:** add a Stage-0 sub-step that runs a single Claude call per entry to derive the Appendix-A fields and writes them alongside the raw entry. Schema lives in `../product-strategy.md` Appendix A; the prompt structure can be lifted from `../carver-dags/workflows/entry_annotation/prompts.py`.
- **Why not run the full `entry_annotation` workflow?** That workflow needs OpenAI Batch + AWS S3 + the DAG Artifacts API in staging — more dependencies than a demo justifies. The SDK is the right level of abstraction.

### 1.2 Public market metadata

Both platforms expose free, no-auth public APIs that we hit once at build time:

- **Kalshi:** `https://external-api.kalshi.com/trade-api/v2/markets` (GET, public). Returns paginated market metadata: ticker, title, expiry, status, settlement source. Use direct `httpx` calls; no SDK needed.
- **Polymarket:**
  - **Gamma API** (`https://gamma-api.polymarket.com/markets`) — market metadata, events, search. Fully public.
  - **CLOB API** (`https://clob.polymarket.com`) — price history (`/prices-history`) for the contract-retrospective overlays. Public for read.
  - Python option: `py-clob-client` (official) or direct `httpx`.

Pull approach:
1. Build script hits both APIs for a recent slice (e.g., last 24 months of contracts, both active and resolved).
2. Filter to ~50 candidates per platform by relevance heuristics (settlement entities present in `data/known_regulators.yml`, or in the platform's own entity catalog).
3. Hand-pick the final ~5-10 per platform that feature in the demo (recorded in `data/platforms/*/contracts.yml` with `source_url` traceable to the public API response).
4. For contracts that drive the γ retrospective pages (§ 4.2 below), additionally pull `prices-history` so the price-overlay timeline is real.

### 1.3 Public personnel and corporate information

For the synthetic platform-context entity catalogs (§ 3.1), source every named individual from:
- The platform's own public "About" / "Team" / "Leadership" page.
- Press coverage (TechCrunch, Bloomberg, Stratechery, etc.).
- Court filings (these are public records).
- Securities filings.

Maintain `data/sources/personnel-sources.md` with one row per named individual: `name, role, source URL, retrieved-on date`. No LinkedIn screenshots, no DM dumps, no internal directories.

---

## 2. Carver Pull

### 2.1 Filter for prediction-market relevance

The first goal is to slim the Carver corpus to events the demo could plausibly surface. Apply this filter (boolean OR):

```python
def is_prediction_market_relevant(event: dict) -> bool:
    # A. Impacted-business taxonomy
    pm_business_types = {
        "Event Contracts", "Sports Betting", "Derivatives Exchanges",
        "Prediction Markets", "Sweepstakes", "Online Gambling",
        "Commodity Exchanges", "Cryptocurrency Exchanges",
    }
    if set(event.get("impacted_business", {}).get("type", [])) & pm_business_types:
        return True

    # B. Regulator-source allowlist
    pm_regulators = load_yaml("data/known_regulators.yml")  # ~60 entries
    src = event.get("regulatory_source", {}).get("name", "")
    if src in pm_regulators:
        return True

    # C. Entity mention of any platform / staff / known competitor
    platform_entities = load_yaml("data/platform_entities.yml")  # union across Kalshi + Polymarket catalogs
    if set(event.get("entities", [])) & platform_entities:
        return True

    return False
```

`data/known_regulators.yml` covers (non-exhaustive list):
- US federal: CFTC, SEC, FCC, FTC, DOJ, FinCEN, OFAC, CFPB, Treasury (OFAC + FinCEN are dupes; keep both spellings).
- US state gambling commissions: all 50 state-level gambling/gaming/lottery boards. Maintain the canonical-name + alias list.
- Tribal gaming authorities: National Indian Gaming Commission; major-tribe regulators where covered.
- International: France ANJ, Singapore GRA, Thailand AMLO, UK Gambling Commission, Netherlands KSA, MGA (Malta), Hungary's NAV/SZRH, Brazil's SECAP, India's SEBI/Ministry of Finance, Mexico's SEGOB.
- Standards bodies: FATF, IOSCO, BCBS, EU Commission, ESMA.

`data/platform_entities.yml` is the union of every entity name in § 3.1 catalogs.

### 2.2 Date range and volume target

- **Date range:** 2024-01-01 through today. Captures the Kalshi state-enforcement wave, Polymarket's DCM-licensing arc, the France ANJ pre-ban cadence, and a full year-plus of pattern.
- **Volume target:** 200-500 events post-filter. If the raw filter returns more, sample the top N by `urgency_score + impact_score` to fit; if fewer, broaden the regulator allowlist and re-filter.

### 2.3 Output

Single file `data/carver-events.json` — a JSON array of the filtered events, with the full Carver annotation payload preserved per element. This is the source the rest of the build script slices.

Auxiliary file `data/carver-pull-manifest.json` records the pull metadata:
```jsonc
{
  "pulled_at": "ISO timestamp",
  "carver_source_revision": "git sha of carver-dags at pull time",
  "filter_yaml_sha256": "...",
  "raw_count_before_filter": 12453,
  "kept_count": 312,
  "earliest_pub_date": "2024-01-15",
  "latest_pub_date": "2026-05-18"
}
```

---

## 3. Synthetic Platform Context

All files live under `data/platforms/`. Each is hand-edited YAML; no programmatic generation. Keep entries to the smallest number that makes the demo feel real (15-20 per catalog is plenty).

### 3.1 Entity catalogs

`data/platforms/kalshi/entities.yml`:

```yaml
- canonical_name: Kalshi
  aliases: [KalshiEX, KalshiEX LLC, Kalshi Inc.]
  role: self
- canonical_name: Tarek Mansour
  aliases: [Tarek Monsour, T. Mansour]
  role: staff
  title: CEO
  source: https://kalshi.com/about (retrieved 2026-05-19)
- canonical_name: Luana Lopes Lara
  aliases: [Lopes Lara]
  role: staff
  title: President
  source: <url>
- canonical_name: Polymarket
  aliases: [Polymarket Limited]
  role: competitor
- canonical_name: PredictIt
  role: competitor
- canonical_name: Robinhood Markets
  aliases: [Robinhood]
  role: partner
# ... approx 15-20 total
```

`data/platforms/polymarket/entities.yml`: same shape. Highlights:
- Self: Polymarket, Polymarket Limited.
- Staff: Shayne Coplan + public team members.
- Affiliated: UMA Protocol, Risk Labs, QCEX (acquired), ICE (investor).
- Competitors: Kalshi, PredictIt, Cantor Fitzgerald (prediction surface), Drift Protocol, Manifold Markets.

### 3.2 Listed contracts

`data/platforms/kalshi/contracts.yml` — 5 hand-picked active or recently-resolved contracts:

```yaml
- external_id: TIKTOKBAN-25APR30
  title: Will TikTok be banned in the United States by April 30, 2025?
  resolution_criteria: |
    Resolves YES if TikTok is unavailable in the US Apple/Google app stores OR
    if the Department of Commerce issues a ban directive by April 30, 2025...
  settlement_entities:
    - Federal Communications Commission
    - Committee on Foreign Investment in the United States (CFIUS)
    - Department of Commerce
    - ByteDance Ltd.
    - TikTok Inc.
  source_url: https://kalshi.com/markets/...
  listed_at: 2025-01-15
  status: resolved   # or active
- external_id: KXFEDDECISION-26MAR
  title: Federal Reserve federal funds target rate decision, March 2026
  settlement_entities: [Federal Open Market Committee]
  ...
- external_id: KXKALSHISTATEACTION-26
  title: How many US states will have an active C&D against Kalshi by EOY 2026?
  settlement_entities:
    - Nevada Gaming Control Board
    - New Jersey Division of Gaming Enforcement
    - Maryland Lottery and Gaming Control Agency
    - Massachusetts Gaming Commission
  ...
# ~5 total
```

`data/platforms/polymarket/contracts.yml` — 5 contracts; highlights:
- "Solana ETF approved in 2025?" (settlement entities: SEC, ETF applicants).
- A Trump-administration political contract.
- A Fed-rate contract.
- "Will Zelensky wear a suit by [date]?" (the famous failed-resolution example).
- A speculative jurisdiction-ban contract (e.g., on a not-yet-banned country).

### 3.3 Jurisdictional footprint

`data/platforms/kalshi/jurisdictions.yml`:

```yaml
- code: US                # ISO country
  status: operating
- code: US-NV
  status: closed          # PI dissolved; active C&D
  notes: Active state-level cease and desist (2024-2026 litigation)
- code: US-NJ
  status: closed
- code: FR
  status: closed
  notes: ANJ banned 2025-12 (synthetic; cross-reference Polymarket)
# include ~30 entries spanning operating + considering + closed
```

`data/platforms/polymarket/jurisdictions.yml`: similar shape, ~40 entries.

### 3.4 User personas (for in-demo "you are…" framing)

`data/platforms/kalshi/personas.yml`:

```yaml
gc:
  display_name: "Sara Chen"          # fictional
  role: General Counsel
  page_urgency_threshold: 8
  digest_cadence: daily
listing_lead:
  display_name: "Marcus Vega"        # fictional
  role: Head of Listing
international_lead:
  display_name: "(unused for Kalshi)"
```

`data/platforms/polymarket/personas.yml`:

```yaml
gc:
  display_name: "Devon Ashford"        # fictional; not used in current scenes
  role: General Counsel
listing_lead:
  display_name: "Renata Okafor"        # fictional; not used in current scenes
  role: Head of Listing
international_lead:
  display_name: "Priya Kapur"          # fictional; protagonist of scene 3 (β)
  role: Head of International
```

The α scene (Stage 1) uses Kalshi's persona file; the γ scene (Stage 2) also uses Kalshi's (Marcus Vega); the β scene (Stage 3) uses Polymarket's (Priya Kapur) because the international/expansion narrative fits Polymarket's broader operating footprint and the France-ban retrospective.

Personas are **fictional names** — labelled as such in copy if surfaced. They exist only to make screenshots feel real (avatar initials, assignee column on inbox, etc.). The demo narration never claims a real person works for a real platform.

---

## 4. Page Slices

The build script (`build/generate.py`, spec'd in [`20-site-build.md`](20-site-build.md)) reads `data/carver-events.json` + `data/platforms/**` and writes per-page JSON files into `build/page_data/`. Pages then load these at render time.

### 4.1 α slices

| File | Shape | Source data |
|---|---|---|
| `alpha/inbox.json` | array of ~15 ticket DTOs | Filter `carver-events.json` against Kalshi entity catalog; rank by `priority = 0.6*urgency + 0.4*impact`; pick top 15; assign hand-picked statuses (mix of new / acknowledged / in_review / closed) and assignees from `personas.yml`. |
| `alpha/tickets/{id}.json` | ticket detail | For each of ~5 hand-picked top tickets: full event payload + simulated comment thread (2-3 comments per ticket, with author from personas, plausible content) + simulated status-transition history. |
| `alpha/dashboard.json` | grid: jurisdiction × update_type → count, avg_urgency | Aggregate `carver-events.json` over last 90 days, group by `jurisdictions` (unnested) × `update_type`. Limit to Kalshi's footprint from `jurisdictions.yml`. |

### 4.2 γ slices

| File | Shape | Source data |
|---|---|---|
| `gamma/contracts.json` | array of contract summaries with heat score | All contracts from both `kalshi/contracts.yml` and `polymarket/contracts.yml`; for each, compute `heat = sum(severity * exp(-age_days/14))` over last 90 days of events whose `entities` intersect the contract's `settlement_entities`. |
| `gamma/contracts/{id}.json` | contract detail with linked events timeline | For each hand-picked contract: list of all matching events from `carver-events.json`, sorted by `pub_date`. Annotate each with link reason (`settlement_entity` match, `regulatory_source` match). |
| `gamma/pre-listing-scans/{id}.json` | scan result | 2 pre-rendered scans — one for TIKTOKBAN (replays the actual exposure), one for a *hypothetical new* contract the prospect might propose during a live demo (template provided in walkthrough doc). |

### 4.3 β slices

| File | Shape | Source data |
|---|---|---|
| `beta/heatmap.json` | jurisdiction × week → {count, avg_urgency, max_urgency} | Aggregate `carver-events.json` from earliest pull date to today, weekly buckets. Filter to Polymarket's footprint by default; site can dropdown-select Kalshi's. |
| `beta/cascade-signals.json` | array of cascade-signal DTOs | Hand-curated: 3-5 cascades the demo wants to highlight. Each references real trigger events from `carver-events.json` (e.g., a real FATF guidance), with hand-written rationale and expected-follower list. |
| `beta/quarterly-report.json` | full structured report | Hand-curated for Polymarket Q2 2026: headline stats from heatmap aggregate; pressure_up / pressure_down sections with real jurisdictions backed by real events; watch_list cross-references cascade-signals. |

---

## 5. Build Script for Slicing

`build/generate_slices.py` is a single Python script that:

1. Loads `data/carver-events.json`, `data/platforms/**`.
2. Computes the slices in § 4 deterministically (no randomness; no LLM calls; no network).
3. Writes JSON files into `build/page_data/`.

Idempotent: rerunning produces byte-identical output. CI can assert this with `git diff --exit-code`.

The script is the *only* place that loads or transforms data. Pages never see `data/carver-events.json` directly; they consume `build/page_data/**`. This isolation means a Carver re-pull regenerates everything cleanly.

---

## 6. Source-of-Truth Discipline

| Question | Answer |
|---|---|
| Where does a real regulatory event come from? | `data/carver-events.json` only. No fabrication. |
| Where do the named platform entities come from? | `data/platforms/*/entities.yml` — every name annotated with a public-source URL. |
| Where do listed contracts come from? | `data/platforms/*/contracts.yml` — hand-curated from public listings; `source_url` mandatory. |
| Where do persona names come from? | `data/platforms/*/personas.yml` — explicitly fictional names. Narration labels them as illustrative. |
| Where does a simulated ticket comment thread come from? | `alpha/tickets/{id}.json` includes the thread; it's clearly synthetic and labelled as such in the UI (e.g., a "demo data" badge on the comment thread). |

**Rule:** if a viewer copies a fact off any page and Googles it, the fact must check out (real event, real regulator, real contract). Comments and assignees obviously won't — they get the badge.

---

## 7. Acceptance Criteria (Stage 0)

- [ ] `../carver-dags/workflows/entry_annotation/` storage shape documented (open question D1 resolved).
- [ ] `data/carver-events.json` exists, valid JSON, contains 200-500 events, all schema-conformant against Appendix A.
- [ ] `data/carver-pull-manifest.json` populated; raw vs kept counts recorded.
- [ ] All eight `data/platforms/**/*.yml` files exist and pass a YAML lint.
- [ ] Every named individual in `entities.yml` files has a `source` URL.
- [ ] `data/known_regulators.yml` covers ≥50 entries spanning federal / state / tribal / international / standards bodies.
- [ ] `build/generate_slices.py` runs cleanly on a fresh checkout (no network access) and produces all files in § 4.
- [ ] Re-running `generate_slices.py` is idempotent (`git diff build/page_data/` is empty).
- [ ] Sample of 10 slice rows manually inspected against `data/carver-events.json` for correctness.

---

## 8. Open Questions (data-prep-local)

| # | Question | Suggested resolution |
|---|---|---|
| DP1 | Does the carver-feeds-sdk expose Appendix-A annotation fields on entries, or only raw entry metadata? | Stage 0, day 1: install the SDK, pull 5 sample entries from `entries/{id}` endpoint, inspect the JSON. If annotations are attached, no extra work. If only raw, add the Claude-annotation sub-step described in § 1.1. |
| DP2 | Are there Carver fields we should mask before checking JSON into a public git repo? | Audit on first pull. Likely safe (the data is *annotations of public regulatory content*). Mask only if a field contains PII not present in the source — extremely unlikely. |
| DP3 | What's a fair date range if Carver's annotated history is shorter than 18 months? | Use whatever's available, but explicitly call out the data window on β's heat-map (e.g., "Heat-map shows data since 2025-08-01" so prospects don't infer a coverage claim). |
| DP4 | If Kalshi or Polymarket has had a public-API change that breaks the curation, how do we know? | Contract tests with recorded fixtures; CI fails if the rendered demo doesn't match fixture-derived ground truth. (Out of scope for V1 demo; just hand-update on the rare event.) |
| DP5 | Should we include events from *other* prediction markets (Cantor, Manifold, PredictIt) in the Carver pull? | Yes — broader corpus makes α / γ / β feel less Kalshi-Polymarket-narrow. They naturally fall into the filter via `entities`. |
