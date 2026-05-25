# Policy-diffs POC — Design

**Date:** 2026-05-07
**Audience:** Internal team building the POC; Credio is the customer who will see the demo.
**Status:** Approved design. Implementation plan to follow.

## 1. Problem

Credio (https://credio.xyz) sells AI agents that run risk and compliance operations for payment processors and fintechs. Their agents enforce card-network rules on behalf of those customers. When Mastercard updates its rulebooks, Credio's internal policy library — which the agents reference — must be updated. Today this is a manual, slow process; missing or late updates create compliance exposure.

This POC automates the workflow: detect what changed in a Mastercard B2B artifact between published versions, map each change to the affected Credio policies, and present a structured proposal of the resulting policy updates. A timeline view stitches the proposals together so a Credio reviewer can see the evolution at a glance.

The POC's purpose is **customer feedback**. The customer-facing surface is a static, browser-based reviewer — not raw `git diff` — so non-technical compliance reviewers can react to: (a) is the change detection right; (b) is the impact mapping plausible; (c) does the proposed Credio edit look like something they would accept. The proposed updates live inside per-change JSON records under `artifacts/spme/.../changes/`; the policy files in `credio-policies/policies/` stay pinned to the v1 baseline. No git branches, no PR substrate — the timeline view is the only customer surface.

## 2. Phased rollout

Three phases, each anchored on a different Mastercard B2B artifact. Each phase reuses the same pipeline + presentation layer; we refine quality, prompts, and presentation between phases.

| Phase | Artifact | Why this order |
|------|----------|----------------|
| 1 | **Security Rules and Procedures – Merchant Edition (SPME)** | Tightest fit to Credio's fraud/risk/BRAM agent surfaces. Smaller doc (~250 pages), yearly clean refreshes. Lets us validate the pipeline before scaling. |
| 2 | **Mastercard Rules** | The flagship rulebook. Broader scope (acquirer obligations, ECP/EFM, service providers). Stresses the pipeline — wider mappings, more sections. |
| 3 | **Chargeback Guide** | Narrow but deep on dispute resolution. Maps to Credio's disputes/chargebacks agent (their +35% win-rate claim). Largest doc (~1,100 pages). |

Quality bar must be met on phase N before phase N+1 starts.

## 3. Phase 1 scope (SPME)

- All 5 SPME version transitions covered end-to-end (6 distinct content versions on Wayback, 2022-06 → 2025-07, 5 transitions).
- For each transition: per-section LLM classification + mapping + per-file proposed edits, captured as `ChangeRecord` JSONs.
- Sequential cumulative state: transition N's proposer sees the Credio files as transition N-1's edits left them (tracked in-memory across one phase run). The working-tree policy files stay pinned to the v1 baseline.
- Static HTML timeline as the demo entry point, with drill-downs into per-transition feeds and per-change detail pages.
- A reusable cache of intermediate artifacts (extracted markdown, per-section diffs, classification summaries, mapping rationales, change records) — these are explicit outputs, not throwaways.

### SPME Wayback versions

```
v1  2022-06   TIK326NK…
v2  2023-05   GWBF7PZK…
v3  2023-09   RQUBCSRX…
v4  2024-02   UNT223G3…
v5  2024-09   XYEY74G7…
v6  2025-05   OTGAYCHJ…
```

Versions identified by digest from `web.archive.org` CDX. Snapshots within the same digest are deduplicated; `warc/revisit` rows are skipped.

## 4. Pipeline

Six stages, deterministic upstream, LLM downstream.

```
1. Fetch     →  2. Extract   →  3. Diff       →  4. Classify  →  5. Map      →  6. Propose
[curl]          [pymupdf +      [per-section    [LLM:           [LLM: which   [LLM: emit
[Wayback]       pdfplumber]     text diff]      summarize +     Credio        policy.md /
                                                materiality]    policies      rules.yaml
                                                                affected]     edits as patch]
```

### 4.1 Fetch
- Enumerate snapshots: `https://web.archive.org/cdx/search/cdx?url=<artifact>&output=json`.
- Dedupe rows by digest (keeping earliest timestamp). Skip `warc/revisit`.
- Download each unique version via the `id_` URL form: `https://web.archive.org/web/<TIMESTAMP>id_/<URL>`. Use `curl` (the Claude WebFetch tool can't reach Wayback directly; this is a known constraint).
- Cache PDFs locally under `artifacts/<artifact>/<version>.pdf`.

### 4.2 Extract
- `pymupdf` for body text and section headings.
- `pdfplumber` for tables (BRAM threshold tables, fraud KPI grids, etc.).
- Output: one markdown file per Mastercard *section* (chapter / subchapter), preserving heading hierarchy and original section IDs.
- Behind an `Extractor` adapter interface — drop-in replacement (LlamaParse, Reducto, vision-model extractors) possible if SPME tables come out garbled. We do not start with an LLM extractor; cost + non-determinism not justified for born-digital PDFs.
- Cached at `artifacts/<artifact>/<version>/sections/*.md`.

### 4.3 Diff
- For each pair `(v_n, v_{n+1})`, walk the section tree and emit a deterministic text diff per section.
- Skip unchanged sections.
- Output: `artifacts/<artifact>/<from>_to_<to>/section-diffs/*.diff` plus a JSON index of which sections changed.

### 4.4 Classify
- For each changed section, one LLM call: summarise the change in one paragraph; score *materiality* on a fixed scale (none / cosmetic / clarifying / substantive / breaking).
- Cosmetic changes (whitespace, typo fixes) are dropped from the downstream pipeline — they don't generate Credio noise but stay in the partials cache.
- Output: `artifacts/<artifact>/<from>_to_<to>/classified.jsonl`.

### 4.5 Map
- For each *substantive* or *breaking* section diff, one LLM call: list which Credio policy files are affected, with rationale and the specific Mastercard section IDs cited.
- The Credio policy repo is sent in the prompt so the LLM has the full target surface. Stable content is placed at the prompt prefix to benefit from OpenAI prompt caching.
- Output: `artifacts/<artifact>/<from>_to_<to>/mapping.jsonl`.

### 4.6 Propose
- For each affected Credio policy file, one LLM call: emit the new full contents of the file (format-aware — yaml or markdown), with retry + safe-fallback if YAML output fails to parse.
- The proposed `new_contents` updates the orchestrator's in-memory cumulative state so the next transition's proposer sees the file as the prior transition left it. The on-disk policy file stays pinned to the v1 baseline.
- A structured **change record** (JSON) is written for each change: title, materiality, plain-English summary, Mastercard section refs and quoted before/after, list of affected Credio files with their before/after content, and rationale. The presentation layer (§6) renders entirely from these records.

## 5. Synthetic Credio policy library

A tracked subdirectory `credio-policies/` within the main repo, representing what we believe Credio's internal compliance library looks like. The directory holds the v1 baseline (2022-06) and is never mutated by the pipeline — proposed updates live in change records, not in the working tree.

### 5.1 Layout

```
credio-policies/
├── README.md
├── policies/
│   ├── fraud_monitoring/
│   │   ├── policy.md      # narrative — compliance-readable
│   │   ├── rules.yaml     # thresholds + actions — agent-readable
│   │   └── source.yaml    # Mastercard section refs (provenance)
│   ├── bram_response/
│   ├── ecp_thresholds/
│   ├── kyb_acquirer/
│   ├── chargeback_handling/
│   ├── refund_policy/
│   ├── ato_detection/
│   └── content_moderation/
├── agents/
│   ├── fraud_ops/         # operational runbooks (lighter; reference policies/)
│   └── bram_response/
└── dist/
    ├── index.html         # → redirects to timeline.html
    ├── timeline.html      # Layer 1 (entry)
    ├── transitions/
    │   └── <from>_to_<to>.html   # Layer 2 (change-cards feed)
    ├── changes/
    │   └── <change-id>.html      # Layer 3 (tabbed detail)
    ├── assets/
    │   └── style.css
    └── policies/
        └── *.pdf          # rendered PDF copies of each policy.md (pandoc)
```

### 5.2 Baseline content
- ~8 hand-authored policies, anchored to SPME v1 (2022-06) content.
- LLM-assisted drafting; human-edited. Quality matters more than quantity for the demo — eight credible policies beat thirty sloppy ones.
- Each policy starts as `policy.md` (narrative) + `rules.yaml` (machine) + `source.yaml` (Mastercard section IDs that justify each rule).

### 5.3 Sequential cumulative state (no branches)
- The orchestrator holds an in-memory `policy_path -> current_contents` map across one phase run.
- Transition N's proposer reads from this map (or the v1 baseline on disk for first sight), so it sees the file as transition N-1's edits left it.
- After each proposal, the map is updated. The on-disk file is never mutated.
- Effect: the Credio side evolves cumulatively year-over-year for the LLM calls and the change records, while the tracked baseline stays clean for reviewers browsing the repo.

### 5.4 Rendered PDFs
- `policy.md` is canonical (clean text diffs feed the redline view). On the `render-pdfs` CLI command, `pandoc` regenerates `dist/policies/<policy>.pdf` from the v1 baseline `policy.md`. The PDF is what compliance teams distribute internally; including it makes the demo feel authentic.
- Rendered PDFs live in `dist/policies/` so they don't pollute markdown diffs.

## 6. Presentation layer

A static HTML site rendered server-side at the end of the pipeline, lives at `credio-policies/dist/` and opens from `file://`. Three nested layers, each serving a different reviewer.

### 6.1 Layer 1 — Timeline (`dist/timeline.html`)

The demo entry point. Vertical timeline of all transitions (5 in phase 1). Each row is a card showing:
- Date range (`2024-09 → 2025-05`)
- Mastercard artifact + version label (e.g. *SPME 2025 yearly refresh*)
- Materiality summary (counts of breaking / substantive / clarifying changes)
- Number of Credio policies affected
- Click → opens the corresponding transition page

Audience: exec / overview reviewers. Should be readable in under 30 seconds.

### 6.2 Layer 2 — Change-cards feed (`dist/transitions/<from>_to_<to>.html`)

For one transition, a feed of cards, one per non-cosmetic change. Each card shows:
- Plain-English title and summary of the change
- Materiality badge (colour-coded: breaking red, substantive orange, clarifying yellow)
- Cited Mastercard sections (e.g. `SPME §10.2`)
- Affected Credio policy folders
- Click → opens the corresponding detail page

Audience: compliance reviewers wanting to scan the impact set quickly.

### 6.3 Layer 3 — Detail page (`dist/changes/<change-id>.html`)

Tabbed view, three tabs:

**Tab 1: Side-by-side (default)** — Two columns. Left: the Mastercard SPME section, with word-level redline showing what changed. Right: the affected Credio file(s), each shown in its native format (markdown for `policy.md`, monospaced YAML for `rules.yaml`) with the corresponding redline. Multiple Credio files affected by one Mastercard change appear stacked on the right. Below both columns: a "Why these edits?" footer explaining the chain of reasoning.

**Tab 2: Redline (compliance view)** — The resulting Credio `policy.md` rendered as a Word-style track-changes document. Most familiar metaphor for compliance and legal reviewers. Citation footer at the bottom links to the Mastercard source.

**Tab 3: Raw diff** — Unified diff of the patch for engineers. Generated by `diff2html` (loaded from CDN) or a styled `<pre>` block. Provided for completeness; expected to be the least-used tab during a customer demo.

Tabs are anchor-based (`#tab-side-by-side`, `#tab-redline`, `#tab-raw`) — no JS framework, no client-side routing.

### 6.4 Rendering inputs

Every page in the presentation layer renders from inputs already produced by the pipeline:
- The change-record JSONs from §4.6 drive cards + detail pages.
- The classification summaries from §4.4 populate timeline materiality counts.
- The before/after content for redlines comes from each `ChangeRecord`'s `affected_files[*].old_contents` / `new_contents`.

No additional LLM calls are made at render time — the presentation is a deterministic transform of pipeline output.

## 7. Outputs (the demo deliverables)

| Output | Description |
|--------|-------------|
| **A. Presentation layer (primary)** | The static HTML site at `credio-policies/dist/`, tracked in the repo. The customer opens `dist/timeline.html` and drills in. This is the surface that drives the demo conversation. |
| **B. Change records** | Per-change JSON files under `artifacts/spme/<from>_to_<to>/changes/`. The durable audit trail of "what would change in which Credio file and why," anchored to a specific Mastercard SPME section. Drives the presentation layer; can be ingested into other downstream tools. |
| **C. Reusable partials** | Per-section markdown chunks, per-section diffs, classification summaries, mapping rationales — all cached under `artifacts/`. Each is independently reusable for future products (Mastercard rule search, change-feed, etc.). |

## 8. Repo layout (this project)

```
policy-diffs/
├── pipeline/             # Python pipeline modules — fetch, extract, diff, classify, map, propose
├── prompts/              # LLM prompts (versioned, testable in isolation)
├── presentation/         # Static-site renderer (Jinja2 templates → dist/)
├── credio-policies/      # Tracked subdirectory: synthetic baseline + rendered dist/ site
├── artifacts/            # Cached PDFs, extracted markdown, diffs, partials, change records
├── docs/superpowers/specs/
├── config/
│   └── models.yaml       # Per-stage LLM model + provider config
└── README.md
```

## 9. Tech stack

- **Language:** Python 3.12. `uv` for env / dependency management.
- **PDF extraction:** `pymupdf` for body + headings; `pdfplumber` for tables. Both behind an `Extractor` adapter interface.
- **LLM provider:** OpenAI via the official `openai` SDK.
- **LLM models:** Config-driven per stage (default model: `gpt-5.4-mini`). Model can be overridden per stage in `config/models.yaml`; e.g., a heavier model for mapping/proposal, a cheaper one for classification. Env vars override config for CI/local.
- **Prompt caching:** Stable prompt prefixes (Credio policy repo content, baseline SPME chunks) placed first to benefit from OpenAI's automatic prompt caching.
- **Presentation rendering:**
  - `jinja2` for HTML templating across all three layers.
  - `redlines` (Python) for word-level prose redline → `<ins>`/`<del>` markup.
  - `markdown-it-py` for rendering `policy.md` content within the redline view.
  - `pygments` for YAML syntax highlighting in detail pages.
  - `difflib` (stdlib) for YAML-level diffs.
  - `diff2html` via CDN for the "Raw diff" tab — fallback to a styled `<pre>` if offline demos are required.
  - Plain handwritten CSS in `dist/assets/style.css`. No JS framework, no build step. Pages open from `file://`.
- **PDF rendering for Credio policies:** `pandoc` (markdown → PDF).

## 10. Configuration

`config/models.yaml`:

```yaml
provider: openai
default_model: gpt-5.4-mini
stages:
  classify:
    model: gpt-5.4-mini
  map:
    model: gpt-5.4-mini       # may upgrade later if quality demands
  propose:
    model: gpt-5.4-mini
api_key_env: OPENAI_API_KEY
```

Stage-specific model and prompt selection lets us tune cost vs quality without code changes.

## 11. Phase 1 success criteria

- All 5 SPME transitions produce a passing, review-ready proposal: clean redline on at least one Credio file, valid YAML, no orphan citations, no TODOs.
- Each detail page cites specific Mastercard SPME section IDs and quotes the relevant Mastercard delta.
- Timeline page renders all 5 transitions with materiality counts and dates; clicking through the layers (timeline → cards → detail tabs) works without dead ends.
- Side-by-side and redline tabs render correctly for at least one example of each materiality class (clarifying / substantive / breaking).
- Pipeline + render runs end-to-end from a clean clone in under 15 minutes (with PDFs already cached) or under 30 minutes (cold).
- One internal demo dry-run with feedback before showing Credio.
- Non-cosmetic Mastercard section diffs covered: at least 80% mapped to a Credio policy (or explicitly marked "no Credio surface affected").

## 12. Risks & mitigations

| Risk | Mitigation |
|------|-----------|
| pymupdf/pdfplumber mangle SPME tables | Adapter interface lets us swap to LlamaParse / vision extractors without touching the pipeline. Spot-check one table per version on first run. |
| LLM hallucinates section IDs in mappings | Mapping prompt receives the actual extracted markdown for the diffed section — section IDs are echoed back from input. Validation step rejects mappings where cited section ID doesn't exist in the source. |
| Synthetic Credio policies are unconvincing | Hand-edit baseline by human reviewer before phase 1 demo. Customer feedback in phase 1 informs polish for phase 2. |
| OpenAI cost on full pipeline run | Materiality filter drops cosmetic changes before LLM mapping/proposal. Prompt caching on stable Credio repo prefix. Cached partials avoid re-running classification on the same diffs. |
| Wayback unavailability mid-run | Fetched PDFs cached locally on first hit; subsequent runs use the cache. |
| `redlines` produces ugly markup on real markdown (lists, headings, code) | One-hour spike against a sample policy before locking. Post-process with a small wrapper that handles block boundaries; fall back to per-block diffing if word-level breaks down. |
| Side-by-side detail layout breaks for changes that affect many Credio files | Stack the right column; cap visible files at 3 with a "show more" disclosure. |

## 13. Out of scope

- Phase 2 (Mastercard Rules) and Phase 3 (Chargeback Guide). Pipeline is artifact-agnostic but each phase brings new test cases and tuning.
- Real GitHub integration (any push-based PR creation, repo hosting, webhook automation).
- Re-introducing per-transition branches or PR substrate — replaced by the change-record + timeline model.
- Bidirectional sync (e.g., detecting when a Credio policy update implies a Mastercard rule we should re-check).
- Cross-network coverage (Visa rules, Amex, etc.).
- Production-grade observability, retries, queue infrastructure.
- A real Credio code base — the synthetic repo is for the demo only.
- Server-rendered or interactive presentation (e.g. live filtering, search). Phase 1 ships a fully static site.

## 14. Open future-use ideas (the partials)

The cached intermediate artifacts have value beyond this POC:

- **Mastercard rule search** — the per-section markdown is a clean, searchable corpus. Could power a small RAG-backed assistant for compliance teams.
- **Change-feed product** — the per-version classification stream is a Mastercard "release notes" feed Credio could resell or expose to its customers.
- **Audit trail** — the mapping rationales are a paper trail of *why* a Credio policy was changed, anchored to a Mastercard source. Useful for SOC 2 / ISO 42001 audits.
- **Policy gap detector** — invert the mapping: for any new Mastercard section, flag Credio surfaces that have no policy coverage at all.
- **Cross-network expansion** — the same pipeline shape works for Visa Core Rules, Amex network agreements, Discover etc.
- **Programmatic API/PR surface** — for engineering customers, an opt-in flow that materialises each transition as a real GitHub PR (with the presentation layer attached as a PR-comment summary). Not how Phase 1 ships, but the change-record JSONs are the substrate that would drive it.

## 15. Implementation handoff

Once this design is approved and committed, the next step is the `writing-plans` skill to break the build into concrete, ordered tasks: artifact fetcher → extractor → diff → classifier → mapper → proposer → repo bootstrapper → presentation renderer → demo dry-run.
