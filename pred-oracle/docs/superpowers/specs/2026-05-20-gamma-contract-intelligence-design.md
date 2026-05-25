# γ Contract-Detail Intelligence Pass — Design

> **Status:** approved 2026-05-20. Implementation plan to follow at
> `docs/superpowers/plans/2026-05-20-gamma-contract-intelligence.md`.
>
> **Scope:** improvements to `/gamma/contracts/<id>/` driven by user feedback
> on `/gamma/contracts/tiktokban-25apr30/`. Heat-tier vocabulary ripples to
> the γ dashboard heat column for consistency. α and β scenes are untouched.

---

## 1. Goal

Make the contract-detail page intuitive and information-dense for a regulatory
analyst, by:

1. Scoping data to the contract's actual life window (no post-resolution noise).
2. Using OpenAI LLM calls to (a) judge per-record relevance to the contract's
   *thesis* (not just entity overlap), (b) decompose the resolution criteria
   into atomic conditions, (c) generate a 1-line "why this matters" for each
   timeline event, (d) explain the heat score, and (e) summarize the
   regulatory storyline.
3. Replacing the flat event list with a proper vertical timeline anchored to
   thesis conditions, with a color/ring legend that's actually visible.
4. Replacing the abstract heat number with a tier label + 1-line explainer.

---

## 2. Current behavior (what we're fixing)

| User complaint | Root cause | Module |
|---|---|---|
| Timeline shows events *after* the resolution date | `_build_timeline` filters only `age >= 0` from `today` — contract life window is ignored | `build/gamma_contract.py:78` |
| Matching is too broad — any shared entity is a match | `entity_match` is whole-word entity overlap with no content/thesis check | `build/_heat.py:61` |
| Timeline doesn't read like a timeline | Renders as `<ul>` with left-border accents, date as sub-text | `build/templates/gamma/contract_detail.html:50` |
| No "why this is relevant" per event | Not computed; only `matched_entity` is stored | `build/gamma_contract.py:106` |
| Grey vs red coloring unexplained | `urgency >= 7` → rose; no legend on the page | `build/templates/gamma/contract_detail.html:54` |
| Heat number and trend opaque | `Σ severity × exp(-age/14)` with no peer/delta/explanation; sparkline is raw record count | `build/_heat.py:100-133` |

---

## 3. Architecture

### 3.0 Curation prerequisite — trim the contract set to 6

Before adding LLM enrichment, the curation is trimmed so the demo only ships
contracts with strong regulatory signal. This caps cold-build LLM spend and
removes broken dashboard links.

**Kept (6 detail pages, all 6 on dashboard so the presenter can pick freely
during a demo):**

| ID | Platform | Kind | Dashboard heat basis |
|---|---|---|---|
| `tiktokban-25apr30`       | kalshi      | retrospective | peak heat in life window |
| `kxfeddecision-26mar`     | kalshi      | retrospective | peak heat in life window |
| `solana-etf-2025`         | polymarket  | retrospective | peak heat in life window |
| `kxfeddecision-28jan`     | kalshi      | active        | current 90-day window |
| `kxbtc-maxprice-2026`     | kalshi      | active        | current 90-day window |
| `us-recession-in-2026`    | polymarket  | active        | current 90-day window |

**Dropped:**

- `kxelonmars-99` — low regulatory signal (entertainment/space)
- `rihanna-album-before-gta-vi` — off-strategy
- `kxnextiranleader-45jan01` — no detail page existed; geopolitical, thin corpus
- `kxtrumpcabinet-26` — no detail page existed
- `warmest-year-on-record-2026` — no detail page existed; climate, off-strategy

**Dashboard treatment of retrospectives:**

- Retrospective rows render alongside active rows in the same table.
- `status` column shows the existing badge: `active` → emerald,
  `resolved` → slate. (Template already handles this.)
- Heat for retrospectives is computed against `[resolved_at - 90d, resolved_at]`
  — the contract's *resolution-window heat*. This is a more meaningful signal
  than today's corpus pressure (which is post-resolution noise) and makes the
  retrospective rows compelling demo entry points.
- A new field `heat_window_label` is added to each row: `"current"` for active,
  `"at resolution"` for retrospective. Rendered as a small subtitle under the
  heat number so the audience knows the heat numbers aren't directly comparable.
- Sort order: active rows first by heat desc, then retrospective rows by
  `resolved_at` desc. Visually separated by a thin divider row labelled
  "Resolved (retrospective)".

**Files touched:**

- `data/gamma-curation.yml` — drop entries from `featured_kalshi`,
  `featured_polymarket`, `contract_detail_picks`, and any
  `synthetic_listing_risk_tickets` referencing dropped ids.
- `data/platforms/kalshi/contracts.yml` — drop the matching `picks` entries.
- `data/platforms/polymarket/contracts.yml` — drop the matching `picks`.
- `build/gamma_dashboard.py` — load retrospectives from
  `data/platforms/{kalshi,polymarket}/contracts/*.yml` for picks listed as
  retrospective in `contract_detail_picks`, build rows for them, and
  apply the resolution-window heat calculation.
- `build/templates/gamma/dashboard.html` — add the "Resolved" divider row
  and the `heat_window_label` subtitle in the heat cell.

### 3.1 Module map (new + modified)

**New modules:**

- `build/_llm.py` — OpenAI client wrapper with disk cache, structured outputs,
  in-process concurrency, and graceful degradation when no API key is set.
- `build/_thesis.py` — pure functions for thesis decomposition (calls
  `_llm.complete_json`) and condition-tagging.
- `build/_relevance.py` — per-record relevance judgment (calls
  `_llm.complete_json`).
- `build/_heat_panel.py` — tier computation, peer percentile, delta, and
  LLM-generated explainer.
- `build/_narrative.py` — 2-3 sentence summary block.
- `build/gamma_contract_enrich.py` — orchestrator: takes a slice JSON +
  corpus, returns the enriched slice. Mutates in place during the build.

**Modified modules:**

- `build/gamma_contract.py`
  - `_build_timeline`: add `window_start`, `window_end` parameters. For
    retrospective: `[listed_at - 90d, resolved_at]`. For active:
    `[listed_at - 90d, today]`.
  - Top-25 cap removed; the relevance step drops records to ~15-20 itself.
- `build/generate_slices.py`
  - After γ contract slices are written, call
    `gamma_contract_enrich.enrich_all(slices, corpus)` to add enrichment.
- `build/gamma_dashboard.py`
  - Replace bare heat numbers with `{value, tier}` pairs using the same
    `_heat_panel.tier_for(value)` function.
- `build/templates/gamma/contract_detail.html` — replaced layout (see §6).
- `build/templates/gamma/_components/contract_row.html` — heat cell gets a
  tier dot.

**Build cache:**

- `build/_cache/llm/` — committed to git. Subdirectories per call type
  (`relevance/`, `thesis/`, `heat_explainer/`, `narrative/`).

### 3.2 Data flow

```
data/_scratch/artifacts.jsonl   data/gamma-curation.yml   data/platforms/.../*.yml
        │                              │                          │
        ▼                              ▼                          ▼
                 build/gamma_contract.py (existing)
                              │
                              ▼
              build/page_data/gamma/contracts/<id>.json   ← un-enriched slice
                              │
                              ▼
                build/gamma_contract_enrich.py (new)
                ├── _thesis.decompose(contract)              → conditions[]
                ├── _relevance.judge_batch(candidates,         → drops + tags +
                │        contract, conditions)                  one_line_why
                ├── _heat_panel.build(matches, peers)         → tier, delta,
                │                                              percentile,
                │                                              explainer
                ├── _narrative.summarize(contract, timeline)  → 2-3 sentences
                └── (writes back to slice JSON)
                              │
                              ▼
              build/generate.py (existing) renders Jinja2 → site/...
```

All LLM calls go through `_llm.complete_json` and hit the disk cache before
the network.

---

## 4. Six change layers (the work itself)

### Layer 1 — Window scoping (no LLM, low risk)

In `gamma_contract.py::_build_timeline`:

- Parameter additions: `window_start: date | None`, `window_end: date | None`.
- For retrospective contracts: `window_start = listed_at - 90d`,
  `window_end = resolved_at`.
- For active contracts: `window_start = listed_at - 90d`, `window_end = today`.
- Records with `pub_date` outside `[window_start, window_end]` are skipped.

For the per-page `heat_score()` call we keep the existing 90-day trailing
window — that's a *current* pressure measure, distinct from the historical
timeline. The dashboard already uses this same 90-day measure, so both stay
consistent.

### Layer 2 — Matching upgrade (LLM-judged)

Two stages, in `_relevance.py`:

**Stage A — cheap pre-filter** (unchanged from today):
- `_heat.entity_match` whole-word overlap → ~50-100 candidates per contract.

**Stage B — LLM judge** per candidate, via `gpt-5-mini`:

Prompt template (system + user, abridged):

```
You are a regulatory analyst. Given a prediction-market contract and a single
regulatory news record, decide if this record is relevant to whether the
contract resolves YES or NO. Return JSON matching the schema.

Contract:
  Title:                {contract.title}
  Resolution criteria:  {contract.resolution_criteria}
  Conditions:           {conditions}        ← from Layer 3
  Settlement entities:  {contract.settlement_entities}

Record:
  Title:       {rec.title}
  Date:        {rec.pub_date}
  Regulator:   {rec.regulator}
  Topic:       {rec.topic_name}
  Summary:     {rec.summary_or_first_500_chars}
  Entities:    {rec.entities}
```

Response schema (enforced via `response_format`):

```json
{
  "type": "object",
  "properties": {
    "relevant": {"type": "boolean"},
    "relevance_score": {"type": "integer", "minimum": 0, "maximum": 10},
    "one_line_why": {"type": "string", "maxLength": 160},
    "condition_tag": {"type": "string", "enum": ["A", "B", "C", "background"]},
    "high_impact": {"type": "boolean"}
  },
  "required": ["relevant", "relevance_score", "one_line_why",
               "condition_tag", "high_impact"]
}
```

Notes:
- `condition_tag` values are constrained to the conditions returned in §4.3 +
  the literal `"background"`. (If §4.3 returned 1 condition, only `"A"` and
  `"background"` are valid; if 3, `"A" | "B" | "C" | "background"`.)
- Drop records with `relevant: false`.
- Sort remaining by `relevance_score * urgency`, keep top 20.
- Each call cached as
  `build/_cache/llm/relevance/<sha256(prompt+schema+model)>.json`.

### Layer 3 — Thesis decomposition (LLM, one call per contract, `gpt-5`)

`_thesis.decompose(contract)`:

- Input: `title`, `resolution_criteria`, `settlement_entities`.
- Output schema:
  ```json
  {
    "type": "object",
    "properties": {
      "conditions": {
        "type": "array",
        "minItems": 1,
        "maxItems": 3,
        "items": {
          "type": "object",
          "properties": {
            "id": {"type": "string", "enum": ["A", "B", "C"]},
            "label": {"type": "string", "maxLength": 40},
            "summary": {"type": "string", "maxLength": 200}
          },
          "required": ["id", "label", "summary"]
        }
      }
    },
    "required": ["conditions"]
  }
  ```
- Example output for `tiktokban-25apr30`:
  ```json
  {
    "conditions": [
      {"id": "A", "label": "App-store unavailability",
       "summary": "TikTok unavailable in US Apple/Google stores by 2025-04-30."},
      {"id": "B", "label": "Federal divestiture order",
       "summary": "PAFACA enforcement order from DoC/DoJ in effect by 2025-04-30."}
    ]
  }
  ```
- Cached as `build/_cache/llm/thesis/<contract_id>.json` (no SHA — contract
  inputs change rarely and the cache key is the readable contract id for
  debuggability).

### Layer 4 — Heat reframing

`_heat_panel.py`:

**Tier vocabulary** — single source of truth, used by detail page and dashboard:

| Tier | Range | Color |
|---|---|---|
| `dormant`  | < 10        | slate-400 |
| `watch`    | 10 ≤ x < 30 | sky-600 |
| `active`   | 30 ≤ x < 70 | amber-600 |
| `critical` | x ≥ 70      | rose-600 |

Function: `tier_for(value: float) -> Literal["dormant","watch","active","critical"]`.

**Computed fields** (no LLM):
- `value` — current heat score (unchanged formula).
- `tier` — per table above.
- `delta_7d` — `heat_score(today) - heat_score(today - 7)`.
- `peer_percentile` — value's percentile among all contract heat scores in
  the current build (γ dashboard already loads all of them).
- `urgency_weighted_sparkline` — list of length 14. For each day,
  `Σ urgency` of matching records on that day (replaces today's raw count).

**LLM explainer** — `gpt-5-mini`, one call per contract:

Response schema:

```json
{
  "type": "object",
  "properties": {
    "primary_drivers": {
      "type": "array",
      "minItems": 1, "maxItems": 3,
      "items": {"type": "string", "maxLength": 120}
    },
    "explainer": {"type": "string", "maxLength": 220}
  },
  "required": ["primary_drivers", "explainer"]
}
```

Input: top 10 most-recently-matching records + `tier` + `delta_7d`. Asks the
model to explain *why* heat is at that tier this week — one sentence on what's
driving it. Cached as `build/_cache/llm/heat_explainer/<contract_id>__<weekof>.json`
(week-of-year suffix lets heat staleness be visible in the cache key).

**Visual** (right rail of contract detail page):

```
┌─────────────────────────────┐
│  ACTIVE                     │  ← uppercase tier, tier color, 2xl bold
│  56  ·  +18 / 7d  ·  top 12%│  ← value · delta · percentile, tabular-nums
│                             │
│  Heat is elevated by        │  ← LLM explainer, 2 lines max
│  enforcement activity at    │
│  Commerce and ByteDance...  │
│                             │
│  ▁▁▂▃▂▅▇█▅▄▃▂▁▁             │  ← urgency-weighted sparkline
│  -14d              today    │  ← labeled x axis
└─────────────────────────────┘
```

The same tier appears on the γ dashboard as a small colored dot to the left of
the heat number.

### Layer 5 — Narrative summary block (LLM, `gpt-5`, one call per contract)

`_narrative.summarize()`:

- Input: contract metadata + enriched timeline (titles, dates, condition_tags,
  one_line_why).
- Output: 2-3 sentence string, ≤500 chars.
- Tone differs for retrospective vs active (encoded in the prompt).
- Cached as `build/_cache/llm/narrative/<contract_id>__<timeline_hash>.json`.

Rendered as an italic blockquote above the timeline section.

### Layer 6 — Visual restructure of timeline

`build/templates/gamma/contract_detail.html`:

**Condition dot colors** (kept distinct from heat-tier colors to avoid confusion):

| Condition tag | Color (Tailwind) |
|---|---|
| `A` | indigo-600 |
| `B` | emerald-600 |
| `C` | violet-600 |
| `background` | slate-400 |

**Vertical timeline structure:**

```html
<ol class="relative">                          <!-- center rail via ::before -->
  <li class="grid grid-cols-[7rem_2rem_1fr]">
    <time class="text-right pr-4">             <!-- LHS date column -->
      <span class="block font-semibold tabular-nums">2025-04-04</span>
      <span class="block text-xs text-slate-500">Fri</span>
    </time>
    <div class="flex justify-center">           <!-- dot + rail -->
      <span class="w-3 h-3 rounded-full ring-{thin|med|thick} ring-{tier-color}
                   bg-{condition-color}"></span>
    </div>
    <article class="pb-6">                       <!-- RHS card -->
      <a class="font-medium">{{ event.title }}</a>
      <p class="text-sm text-slate-700 mt-1">{{ event.one_line_why }}</p>
      <p class="text-xs text-slate-500 mt-1">
        {{ event.regulator }} · matched {{ event.matched_entity }}
        <span class="urgency-badge">urg {{ event.urgency }}</span>
      </p>
    </article>
  </li>
  ...
</ol>
```

Center rail via `ol::before { content: ''; position: absolute; left: 7rem + 1rem;
top: 0; bottom: 0; width: 1px; background: #e2e8f0; }`.

**Legend** — small pinned strip above the timeline:

```
Condition:  ●  A: App-store unavailability    ●  B: Federal divestiture order    ●  Background
Urgency:    ○ low    ◎ medium    ⬤ high
```

(Plain dots styled with the same Tailwind classes; condition dots use
condition colors, urgency dots use ring weights for consistency with the
timeline dots.)

**Alpine filter toggle** above the timeline:

```html
<div x-data="{ filter: 'all' }">
  <div role="tablist" class="...">
    <button @click="filter='all'" :class="filter==='all' && 'active'">All</button>
    <button @click="filter='A'">Condition A only</button>
    <button @click="filter='B'">Condition B only</button>
  </div>
  <ol ...>
    {% for ev in timeline %}
    <li :class="(filter !== 'all' && '{{ ev.condition_tag }}' !== filter) && 'opacity-30'">
      ...
    </li>
    {% endfor %}
  </ol>
</div>
```

Dimmed (not removed) so the time axis is preserved.

---

## 5. OpenAI integration — `build/_llm.py`

### 5.1 Public surface

```python
def complete_json(
    *,
    purpose: str,                 # e.g. "relevance" — controls cache subdir
    cache_key: str,               # e.g. "<contract_id>__<record_id>" or sha256
    model: str,                   # resolved from env defaults if None
    system: str,
    user: str,
    schema: dict[str, Any],       # JSON schema for response_format
    max_retries: int = 3,
) -> dict[str, Any] | None:       # None when graceful degradation kicks in
    ...

def is_available() -> bool:
    """True if OPENAI_API_KEY is set and the SDK is importable."""
```

### 5.2 Env vars

| Var | Default | Required? |
|---|---|---|
| `OPENAI_API_KEY` | — | yes for any LLM call; absent → graceful degradation |
| `PRED_ORACLE_LLM_MODEL_FAST` | `gpt-5-mini` | no |
| `PRED_ORACLE_LLM_MODEL_DEEP` | `gpt-5` | no |
| `PRED_ORACLE_LLM_CONCURRENCY` | `8` | no |

Loaded via `python-dotenv` from the repo root `.env`.

### 5.3 Caching

- Path: `build/_cache/llm/<purpose>/<cache_key>.json`.
- For variable inputs (relevance per record), `cache_key = sha256(model + "\n" +
  system + "\n" + user + "\n" + json.dumps(schema, sort_keys=True))`.
- For stable inputs (thesis per contract), `cache_key = contract_id`.
- Cache entries store both the request fingerprint and the response so a
  human can diff entries during review.
- Cache committed to git under `build/_cache/llm/` — `.gitignore` carve-out
  ensures it's tracked even though sibling `_cache/` subdirs are ignored.

### 5.4 Concurrency + retry

- `asyncio.Semaphore(PRED_ORACLE_LLM_CONCURRENCY)` around each call.
- Exponential backoff on 429 / 5xx: `1s, 2s, 4s`.
- On final failure: log, return `None`, caller falls back to heuristic.

### 5.5 Graceful degradation

If `OPENAI_API_KEY` is missing or `openai` import fails:

| Layer | Fallback |
|---|---|
| Relevance | Keep all entity-matched records. `one_line_why = "{matched_entity} — {topic_name}"`. `condition_tag = "background"`. `relevance_score = urgency`. |
| Thesis | `conditions = [{"id": "A", "label": "Resolution criteria", "summary": contract.resolution_criteria[:200]}]`. |
| Heat explainer | Static text: "Heat reflects {N} matching events in the last 90 days." |
| Narrative | Omit the block entirely. |

CI without a key still builds + tests pass. The cached responses
in-repo mean even without a key the demo renders the *intelligent* version.

---

## 6. Enriched slice JSON shape

New fields on the existing slice (extensions, not replacements):

```json
{
  "scene": { ... },
  "contract": {
    ...existing fields...,
    "conditions": [
      {"id": "A", "label": "App-store unavailability", "summary": "..."},
      {"id": "B", "label": "Federal divestiture order", "summary": "..."}
    ],
    "narrative": "Between July 2024 and April 2025, ..."
  },
  "heat_panel": {
    "value": 56.0,
    "tier": "active",
    "delta_7d": 18.3,
    "peer_percentile": 88,
    "urgency_weighted_sparkline": [0, 0, 2, 5, 3, 8, 12, ...],
    "primary_drivers": ["3 enforcement-tier DoC bulletins this week",
                        "ByteDance partnership shake-up"],
    "explainer": "Heat is elevated by enforcement activity at..."
  },
  "timeline": [
    {
      ...existing fields (pub_date, title, regulator, url, urgency, ...),
      "one_line_why": "PAFACA reauthorization clears House — moves deadline.",
      "condition_tag": "B",
      "relevance_score": 8,
      "high_impact": true
    },
    ...
  ],
  "open_tickets": [ ... ]
}
```

The old top-level `contract.heat` and `contract.heat_history` fields stay
populated for backwards compatibility with the dashboard renderer (which still
reads the simple value). The dashboard rows additionally read
`heat_panel.tier` from a separate dashboard-level enrichment pass (see §3.1).

---

## 7. Build pipeline integration

`generate_slices.py` — order of operations:

1. `gamma_contract.generate(...)` — writes un-enriched slices to disk
   (unchanged).
2. **NEW:** `gamma_contract_enrich.enrich_all(slice_dir, corpus)` —
   reads each slice JSON, mutates it in place with enriched fields, writes
   back.
3. Other α/β slice generators run as today.
4. Dashboard enrichment: `gamma_dashboard.attach_tiers(slices)` — adds
   `tier` to each dashboard row using `_heat_panel.tier_for`.

**Build-time expectations** (6 contracts per §3.0):

| Cache state | Wall-clock | LLM calls |
|---|---|---|
| Warm cache (committed)                   | ~0s incremental cost                            | 0 |
| Cold cache (fresh checkout, key present) | ~30s × 6 contracts ÷ 8 concurrent ≈ **3 min**   | ~168 |
| Cold cache + no key                      | ~0s (graceful degradation)                      | 0 |

Per-contract LLM call breakdown: 1 thesis (`gpt-5`) + ~25 relevance
(`gpt-5-mini`) + 1 heat explainer (`gpt-5-mini`) + 1 narrative (`gpt-5`)
= ~28 calls. Cache is committed, so cold builds are rare.

---

## 8. Testing

| File | What it covers |
|---|---|
| `tests/test_llm_cache.py`         | Round-trip with stub OpenAI client; verifies cache hit/miss, cache key stability |
| `tests/test_llm_degradation.py`   | With no `OPENAI_API_KEY`, every `_llm.complete_json` call returns `None` and callers produce the documented fallback |
| `tests/test_window_scoping.py`    | Retrospective contract excludes records past `resolved_at`; active contract excludes future records |
| `tests/test_heat_panel.py`        | `tier_for` thresholds, `delta_7d`, `peer_percentile` math; sparkline weighting |
| `tests/test_thesis.py`            | Cached LLM response → expected conditions list; missing cache + no key → 1-condition fallback |
| `tests/test_gamma_contract_enrichment.py` | Full enrichment of a slice fixture using cached LLM responses; output matches golden JSON |
| `tests/test_gamma_templates.py`   | Existing tests updated for new heat-panel and timeline DOM shape |
| `tests/test_gamma_dashboard.py`   | Dashboard rows include tier; tier color matches table in §4.4 |

All LLM-dependent tests use **committed** cache entries — no live API calls
in CI.

---

## 9. Out of scope (explicitly deferred)

- Counterfactual callouts ("if event X hadn't happened, this would've resolved YES")
- Comparable-contract clustering across the listed book
- Per-condition probability inflection estimates
- Streaming LLM output to the build console
- Migrating α / β to use LLM-judged relevance (focused γ pass only)

---

## 10. Risks and known unknowns

- **LLM cost on cold cache.** A first build from a fresh checkout without
  the committed cache costs ~$0.50-1.00 with the chosen models. Mitigation:
  cache is committed and the model versions are pinned via env defaults; we
  only re-spend tokens when a contract is added or its inputs change.
- **Model drift.** If we bump the model default later, every cache entry
  becomes stale. Mitigation: model name is part of the cache key, so old
  entries stay valid for old runs; switching models is an explicit
  invalidation event.
- **Condition_tag validity.** The relevance schema's enum depends on the
  thesis output. We resolve this by serializing thesis first, then passing
  the allowed enum into the relevance schema at runtime.
- **Cache size in git.** Estimated ~200 records × 8 contracts × ~600 bytes
  per response ≈ ~1 MB total. Acceptable.
- **Demo determinism if the prompt changes.** Prompt is part of the cache
  key, so any prompt edit forces a re-spend. Reviewers should treat prompt
  edits as schema migrations.

---

## 11. Acceptance criteria

**Curation (§3.0):**

0. `data/gamma-curation.yml::contract_detail_picks` contains exactly the
   6 entries listed in §3.0. The γ dashboard renders **all 6** as rows
   (3 active above a "Resolved (retrospective)" divider, then 3 resolved),
   every row links to a detail page that exists, and the heat cell on
   retrospective rows shows an "at resolution" subtitle.

**Contract detail page** (`/gamma/contracts/tiktokban-25apr30/` is the
representative case):

1. Show no timeline events with `pub_date > 2025-04-30` or `< 2024-01-24`
   (listed_at 2024-04-24 minus 90 days).
2. Show ≤ 20 timeline events, each with a non-empty `one_line_why` and a
   `condition_tag` ∈ {A, B, background}.
3. Show a 2-3 sentence narrative block above the timeline.
4. Show a heat panel with a tier label, value, delta, percentile, explainer,
   and urgency-weighted sparkline.
5. Show a visible legend above the timeline mapping dot color → condition
   and ring weight → urgency tier.
6. Render correctly when `OPENAI_API_KEY` is unset (cached responses are
   used; fallbacks for any uncached call).
7. γ dashboard heat cells show a tier dot matching the same `tier_for`
   function used on the detail page.
