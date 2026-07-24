# docs-carver-whitepaper

## Overview

- **Start:** 2026-07-23 16:18 (local)
- **Worktree:** /home/ubuntu/work/scribble/code/repos/carver-demos-docs-carver-whitepaper
- **Branch:** flux/docs-carver-whitepaper
- **Baseline HEAD:** 1ae521f6 (🔀 merge: mastra-guardrail-port — grounded-vs-web agent demo + state-lending win)

## Goal

Build a whitepaper laying out the benefits of using a Carver-dataset-enabled agent for
regulatory use cases, grounded in the measured results of the mastra-studio-demo work:

- The one content win (probe 12, state-lending counterfactual swap): a Carver-grounded
  agent surfaces state-specific obligations (Colorado AI Act, California Holden Act) that
  both a memory-only baseline and a live web-search agent miss, triggered silently by the
  applicant's state from `lookupApplicant`.
- The operational win: comparable-or-better answers at 43–63% lower cost than web search,
  cache-independent, more reproducible, equal latency.
- The three mandatory caveats (4 hand-curated records, situation-aware query dependency,
  REVIEW-REQUIRED sources) and the honest record of the 11 probes that did NOT produce a
  content win — per repo doctrine: measure, don't assert; report negatives at equal volume.

Primary sources: `mastra-studio-demo/docs/DEMO.md`, `docs/continuing.md`,
`docs/corpus-gaps-for-jurisdiction-demos.md`, `docs/LESSONS.md` (lessons 6–8).

## Progress

### Update 2026-07-24 — spec + data pipeline done, building site

- **Spec** written & committed (`c3419d55`): external-facing interactive HTML whitepaper,
  two-pronged claim, executive-frame-then-asset structure.
- **Corpus mining** done (`whitepaper/scripts/mine_corpus.py`, one pass over the 1.8 GB
  2026-07-24 snapshot, 244,297 records). Verified schema: fields under `output_data.metadata.*`.
- **Figures** produced: `section1.json`, `section2.json`, consolidated into
  `whitepaper/figures/whitepaper-data.json` (adds measured §3 cost from DEMO.md Beat 4,
  §4 lending exemplar from curated records, §5 retrieval evidence). Key numbers:
  244,297 docs · 681,249 obligations · 711,026 citations · 141,317 with penalties ·
  75% published 2025–26. Freshness clipped to 2016–26 (dropped calendar-artifact years).
  Penalties kept as record counts, not a summed $ (free-text honesty guard).
- **Design system:** dataviz reference palette adopted.
- **Goal set** (/goal): ship a v1 of the site and report done; drive to completion, use
  right-sized subagents. In progress: dispatching the HTML build.
- Goal note: no new agent probes (retrieval-level §5 only, per approved spec).

### Update 2026-07-24 — v1 site shipped (goal met)

**Done.** V1 of the whitepaper site is built, verified, and committed to
`flux/docs-carver-whitepaper`.

- **Deliverable:** `mastra-studio-demo/whitepaper/index.html` — self-contained interactive HTML
  (inline CSS + hand-built inline SVG, no network requests, CSP-safe, light/dark, print stylesheet).
  Built by a right-sized Sonnet subagent from a locked brief + the consolidated data file.
- **Commits:** `84a4d98b` (mining pipeline + figures), `4fd65ad9` (site + README). Spec at `c3419d55`.
- **Verification (independent, not the subagent's word):**
  - Structure valid; single `<!DOCTYPE>`/`</html>`; zero external resource loads (only a
    harmless favicon 404).
  - Every headline number cross-checked against `figures/whitepaper-data.json` — all present,
    none fabricated (spot-checked `130` = Gambling sector count, `$130` = cost-chart axis tick).
  - All six honesty guards present with correct wording (parity-not-better, no speed claim,
    web cost = floor, penalties = counts, token estimate labeled, 4-record tail demo + ablation).
  - Rendered in headless Chromium: full-page dark + forced light — polished, cohesive, no
    horizontal overflow, charts legible in both themes.
- **Cleanup:** local http server stopped; stray screenshots + `.playwright-mcp/` removed from the
  MAIN repo (they landed there, not the worktree); `mine.log` gitignored.

**Not done (intentionally, needs user sign-off):** not pushed, not merged to `main`. The 4 curated
lending records remain REVIEW-REQUIRED (legal/data). Optional follow-ups: live topics-API
verification pass; widen §5 with real build:domain retrieval runs on more candidates.
