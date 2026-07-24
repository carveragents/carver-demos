# Design: Carver Regulatory-Intelligence Whitepaper

**Date:** 2026-07-24
**Branch:** `flux/docs-carver-whitepaper`
**Status:** Design — awaiting user review before implementation planning

## 1. Purpose & audience

A single self-contained interactive HTML whitepaper making the external-facing case that agents
grounded in the Carver regulatory dataset outperform baseline + web-search agents on two fronts:

- **(a) Correctness on the tail** — silent-trigger regulatory obligations (e.g. a state AI-Act
  disclosure duty fired by an automated loan denial) that both a memory-only baseline and a live
  web-search agent miss, where getting advice wrong/incomplete carries liability and reputation cost.
- **(b) Operational advantage on the head** — on everyday queries, Carver agents match a frontier
  model + full web search on answer quality while costing 43–63% less, with cache-independent,
  more-reproducible, equal-latency behaviour.

**Audience:** external prospects / customers, leadership-level and tech-aware. Persuasive but every
number defensible. Internal caveats are reframed as a coverage roadmap, not hidden.

**Structure:** Executive-frame-then-asset (option C). Two-pronged claim + two headline stats in the
first 300 words; body follows asset-first order.

## 2. Deliverable

- Self-contained interactive HTML at `mastra-studio-demo/whitepaper/index.html`.
- Inline SVG charts only — no external libraries, CSP-safe, light/dark aware, print stylesheet for
  clean PDF export.
- Publishable as a **private** Artifact for review (external distribution is the user's decision, not
  automatic). No impersonation of any real org/person; Carver's own product framing only.
- ~12–15 minute read.

### Document outline

- **Executive summary (1 screen).** Two-pronged claim up front. Two headline stat callouts:
  (a) the state-lending miss (baseline AND web both fail to surface the Colorado AI Act / California
  Holden Act obligation); (b) 43–63% lower cost per 1k runs than web search. Closes on "don't wait
  for a tail event — you're already overpaying on the head."
- **§1 The dataset.** Snapshot scale & composition: record count, jurisdictions, regulators, sector
  breakdown, freshness curve (published-date distribution → "continuously updated"), and the
  structured-intelligence layer (obligations extracted, reg references, critical dates, penalties).
- **§2 The cost of starting from scratch.** Rebuild-cost, quantified per sector: source-document
  token volume an agent would need to read, count of extracted requirements/obligations, aggregate
  documented penalty exposure. Thesis: "this intelligence already exists — mined, structured, current."
- **§3 Operational advantage on the head.** Head-query economics from the measured three-arm run:
  cost-per-1k comparison, cache-independence, reproducibility, token burn. Answer-quality parity is
  stated honestly (that is what was measured); the advantage is operational.
- **§4 Correctness on the tail.** The lending story as narrative (three identical applicants, three
  states, one variable). The silent-trigger mechanism: the obligation is never named in the query, so
  web search fails *silently* — the failure looks like success. Liability/reputation framing.
- **§5 The class this generalizes to.** Corpus-mined candidate silent-trigger obligations +
  retrieval-level evidence: a situation-aware Carver query ranks the right obligation #1/top-3 in a
  realistic multi-thousand-record haystack while a plain query misses it.
- **§6 Methodology & coverage roadmap.** How measurements were made (symmetric prompts, mechanical
  scoring, cache-adjusted costing, hosted-tool floor caveat), what is snapshot-pinned, and the
  curated-record caveat framed as a coverage roadmap.

## 3. Data pipeline

All mining runs read-only against `../carver-showcase/data/` (snapshot pinned via `snapshot_meta.json`).
Scripts live in `mastra-studio-demo/whitepaper/scripts/`, each emitting a JSON "figures file" consumed
at **build time** — the HTML contains no runtime data fetch; every number is baked in with the
snapshot date printed beside it.

**Pinned snapshot (verified 2026-07-24):**
- `snapshot_meta.json`: 244,297 records, scope "full", pulled 2026-07-24.
- `term_stats_meta.json`: 367,198 distinct entities / 1,192,351 mentions; 253,771 distinct tags /
  1,747,344 mentions; 388,146 classified.
- `annotations.jsonl` ≈ 1.8 GB — stream it (no `sqlite3` CLI available; `python3` streaming confirmed).

**Verified record schema (paths the scripts depend on):**
- `output_data.metadata.impact_summary.key_requirements` → list of extracted obligations (the
  "obligations already mined" count).
- `output_data.metadata.impacted_business.industry` (list) and `.jurisdiction` (list) → sector &
  jurisdiction rollups.
- `output_data.metadata.reg_references.{rules,statutes,other_ref}` → citation density.
- `output_data.metadata.critical_dates.{effective_date,compliance_date,...}` → deadline coverage.
- `output_data.metadata.penalties_consequences` → **free-text narrative list, NOT structured amounts.**
- `output_data.reconciled_published_date.date` → freshness histogram.
- Sector taxonomy: `topic_catalog.csv` + `topic_domains.csv` (top_level/sub_domain), joined on
  `topic_id`. Tag leaderboard: `tag_leaderboard.csv`.

**Per-section derivation:**
- **§1** — single streaming pass over `annotations.jsonl` aggregating by industry, jurisdiction,
  regulator, and published-date. Sector taxonomy from the CSVs. Cross-check headline totals against
  `carver-state-of-data.pdf`; if the fresh snapshot diverges, cite the snapshot and note the PDF is
  superseded.
- **§2** — same pass: per-sector source-document token estimate (**chars/4, labeled an estimate**),
  count of `key_requirements` entries, `critical_dates` coverage, and a **best-effort** penalty-exposure
  figure. Because `penalties_consequences` is free text, monetary exposure = regex extraction of
  currency mentions ($, €, £, etc.), summed only over records with a parseable amount, with the
  extraction method and the excluded-record count stated. Never present it as an exact total.
- **§3** — no new runs. Numbers lifted verbatim from `docs/DEMO.md` Beat 4 (cost table $44.45 vs
  $78–122, cache-warm/cold band, latency wash, reproducibility). Figures file re-states them so the
  self-check can diff against source.
- **§5** — mine ~5 candidate silent-trigger obligations (jurisdiction-specific × recent × persona-
  fired). Re-use the existing `build:domain`/ranking rig (same protocol as the 7,146-record test) to
  show each ranks #1/top-3 for a situation-aware query. **Publish only candidates that pass**; log any
  dropped so the section is not silently cherry-picked.

**Output contract:** one JSON figures file per section script (e.g. `figures/section1.json`). Build
step inlines them. A self-check asserts every numeric string rendered in the HTML traces to a figures
file (no hand-typed stats).

## 4. Visual system

Per the `dataviz` skill (loaded before any chart code): small consistent palette, light/dark aware,
accessible. Planned marks:
- Executive-summary **stat tiles** for the two headline numbers.
- §1 sector breakdown → horizontal bars; freshness → area/line over published-date.
- §3 cost comparison → grouped bar with the web cache-warm→cold range shown as a band vs Carver's flat
  bar (visualizing cache-independence).
- §4 **hero visual** → three-panel CO/CA/NY comparison (identical inputs, divergent obligation surfaced).
- §5 retrieval rank → small ranked-position chart per candidate (Carver #1 vs web miss).
- Print stylesheet preserves layout for PDF.

## 5. Claims policy (external-facing)

- Every number traces to a measured run or the pinned snapshot; snapshot date shown.
- Head-query answer quality stated as **parity** (measured), advantage framed as operational — no
  overclaim contradicting the 11 non-winning probes.
- The lending win framed as "what jurisdiction-tagged coverage unlocks" — a demonstration on 4
  curated records, not an implied production-wide capability. This is §6's coverage-roadmap framing.
- Web-search cost stated as a **floor** (hosted-tool internal tokens are unmeasurable — lesson 7).
- Penalty-exposure figure always labeled an estimate with stated extraction method.
- No fabricated/paraphrased/unreviewed records anywhere; `../carver-showcase` stays read-only.

## 6. Verification & session hygiene

- Figures files diffed against source-of-truth docs; DEMO.md numbers must match exactly.
- Self-check: every rendered stat appears in a figures file.
- Cross-check §1 headline totals vs `carver-state-of-data.pdf`.
- Flux session updated at milestones; atomic commits (scripts / figures / document).

## 7. Out of scope

- No new agent-vs-agent probes (middle-path chosen: retrieval-level evidence only for §5).
- No live topics-API call (local snapshot chosen); optional pre-publish verification pass against the
  API if the user later provides access.
- No changes to `../carver-showcase` or the existing demo agents.
