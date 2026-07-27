# Regulatory-Intelligence Advantage — whitepaper (v1)

Self-contained interactive HTML whitepaper making the external-facing case for
Carver-dataset-grounded agents on regulatory use cases. Two-pronged: operational cost
advantage on head queries, correctness advantage on silent-trigger tail queries.

- **`index.html`** — the deliverable. Open directly in a browser, or export to PDF from
  the browser's print dialog (a print stylesheet is included). Fully self-contained
  (inline CSS + inline SVG, no network requests). Light/dark aware.
- **`figures/whitepaper-data.json`** — single source of truth for every number in the page.
- **`scripts/`** — regeneration pipeline (read-only against `../../../carver-showcase/data`).

## Regenerate the figures

```bash
# 1. Mine the pinned snapshot (one streaming pass over annotations.jsonl → section1/2.json)
python3 scripts/mine_corpus.py

# 2. Merge with the measured demo numbers (§3 cost), lending exemplar (§4), retrieval (§5)
python3 scripts/consolidate.py
```

Snapshot pinned: **2026-07-24**, 244,297 records. Section 3 cost numbers are transcribed
from `../docs/DEMO.md` Beat 4 (measured 2026-07-23). Section 4/5 use the curated
`../data/state-lending-records.json` and the retrieval results recorded in DEMO.md.

## Honesty guards baked into the copy (do not weaken in future edits)

- Head-query answer quality is **parity**, not "better" — the head advantage is operational only.
- **No speed-win claim** (latency is a wash).
- Web-search cost is stated as a **floor** (hosted-tool internal tokens are unmetered).
- Penalties are a **record count**, never a summed dollar liability total.
- The 732.9M source-read tokens is a **labeled estimate** (3,000 tokens/doc, conservative).
- The tail win runs on **4 curated records** — a demonstration of what jurisdiction-tagged
  coverage unlocks, with the ablation stated; not a production-wide capability claim.
- The §3 comparison discloses fee asymmetry: web arm includes the search-tool fee, Carver
  arm models no Carver fee — stated as pricing headroom ($33.59/1k warm, $77.14/1k cold),
  never as an unqualified "cheaper".
- Per-check figures are per **QUESTION ANSWERED** (chat-style query), not per production
  interaction reviewed.
- Replay economics ($22.57/1k) and drift-as-snapshot-diff are labeled **PROJECTED**,
  excluded from headline claims.
- The five web runs are described as a **consistent, systematic miss** — never as
  run-to-run variance.
