# Build notes — mastra-studio-demo

Where this demo came from, what we learned building it, and which of those lessons will bite
again.

**Provenance.** Prototyped in [`carver-adhoc`](../../../carver-adhoc) as
`projects/hello-mastra` on branch `flux/mastra-studio-ui` — 8 commits on 2026-07-16 — then
promoted here as a clean copy once it became something to show rather than something to try.
That branch and its worktree were deleted afterwards, so **this file is the surviving record**
of the build: the session log and the commit-message reasoning are reproduced below rather
than left to die with the branch.

---

## Lessons

The durable part. Roughly ordered by how much they cost to learn.

### Data and matching

- **The classification data has no acronym field.** Lookup by `FCA` matched **zero** records;
  `SEC` substring-matched **61**, nearly all false hits on "**Sec**urities". Acronyms come
  from joining `topic_catalog.csv` on `topic_id` (97% join, 83% acronyms). Without that join
  the whole premise fails quietly — it returns results, just wrong ones.
- **81 of 801 acronyms are ambiguous, so jurisdiction is mandatory in output.** `SEC` → 5
  bodies across GH/NG/TH/US/TH. `CBI` → 5, including the *Confederation of British Industry*
  sitting alongside three central banks. Drop jurisdiction and the agent confidently reports
  Ghana's SEC as "the SEC".
- **Best-tier-wins matching.** The most precise tier that matches *is* the whole answer
  (exact acronym > exact name > prefix > substring > reverse-substring). TDD caught the
  alternative: tier-blind ranking returned **19** records for `SEC` (5 real + 14 "Securities"
  noise).
- **False absence is the worst bug this codebase can have.** Live testing caught the grounded
  agent stating the FCA *"isn't in Carver's dataset"* — it has 30 records. The tiers only ever
  asked *does the record name contain the query*, never the reverse, and agents pass through
  however the user phrased it ("**UK** Financial Conduct Authority"). For a tool whose entire
  pitch is *"I'll tell you when I don't know"*, a false **I don't know** is worse than a wrong
  answer, because it looks like integrity. Fixed with a last-place reverse-containment tier.
  **23 unit tests missed this; one live question found it.**

### The demo argument

- **Staleness beats hallucination.** The headline beat is not what the design predicted.
  Asked about BIS stablecoin work, the ungrounded agent cites *Project Pyxtrial* (2024) and
  *BIS Bulletin 73* (2023) — **real papers**. It isn't fabricating; it's two years behind.
  Everyone already discounts hallucination as a known LLM flaw. Nobody has a mental model for
  **confident, accurate, and obsolete** — and that's the failure that actually ships.
- **The baseline does not always fabricate, and the demo is stronger for admitting it.** Ask
  vaguely and it asks a clarifying question. Pin it down and it says *"that period has not
  occurred yet"* — an honest cutoff report. Only an invented body (the Reykjavik Bicycle
  Authority) triggers invention, and even there it now hedges. A demo claiming "the baseline
  always hallucinates" would be false and would collapse under one audience question.
- **Most of the dataset postdates the model.** 125,882 annotation records dated 2026, 56,584
  in 2025. That's what turns a soft precision contrast into a hard epistemic wall — no prompt
  closes it, only data.
- **Never sandbag the baseline.** Both agents share `BASE_INSTRUCTIONS` verbatim so the
  prompts cannot drift. The baseline is *not* told it lacks data and *not* told to refuse.
  **The shared prompt must keep pace with capability:** it was once scoped to sector lookup
  only, and adding update questions without broadening it would have made the baseline fail a
  question its own prompt never invited. The wall has to be the training cutoff, not our
  wording.
- **Cherry-pick the questions, never the fixture.** Choosing demo questions to fit the data is
  fine for a scripted POC. Selecting *records* to match those questions is not — it collapses
  the first time someone asks something adjacent, which is exactly what demos get asked. The
  fixture rule is neutral (most recent per topic); the run-sheet was derived from what the
  fixture actually returns, verified live.

### Toolchain

- **Traces need storage.** Studio's Traces/Metrics/Logs require an observability storage
  backend. Without it `MastraStorageExporter` silently self-disables ("Traces will not be
  persisted") — agents still chat, the trace view just stays empty, and the demo loses an
  axis. Hence the `LibSQLStore` + `Observability` in `src/mastra/index.ts`.
- **The model is a router string:** `model: "openai/gpt-5.6-sol"` — slash, never a colon. No
  `@ai-sdk/*` package is installed or needed (they appear under `node_modules/` as transitive
  deps of `@mastra/core`; don't import them).
- **The LLM sees the `tools: { key }` object key as the tool name**, not the tool's `id`. Keep
  the export name and the key identical.
- **tsconfig must stay modern.** `module: ES2022` + `moduleResolution: bundler`; CommonJS
  breaks Mastra's module resolution. `allowImportingTsExtensions` is on because Node's type
  stripping needs explicit `.ts` in relative imports for `node --test` — valid only because
  `noEmit: true`.
- **Metrics view is thin.** LibSQL logs `does not support batch creating metrics`. Harmless;
  Traces unaffected. The scaffold's DuckDB store was what powered Metrics.
- **`.env` is read at startup only.** Add the key after booting and you must restart.
- **Dev servers get reaped when idle.** Start `npm run dev` yourself right before presenting;
  send one throwaway message first, because the first response of a session is slow.

### Cross-repo paths

- **Never hardcode depth to a sibling repo.** `build-topics.mjs` reached the GICS
  classifications via `../gics-topic-tagging/...`, which was correct in `carver-adhoc` and
  meaningless here. Because the demo runs off *committed fixtures*, the break was invisible —
  nothing failed until someone tried to regenerate. Both builders now search upward
  (`findUpward`) instead of counting. This has already bitten twice: once for worktree depth,
  once for the move to `carver-demos`.

### Out of reach

- **The Carver API key returns 401** (expired/revoked) — no live feed access, hence vendored
  fixtures.
- **`carver-feeds-skill` is a Python SDK**, so a TypeScript agent cannot reuse it; it would
  have to call the REST API directly. Neither tool's interface would change to put a live
  backend behind it — the fixtures stand in for a query, not for a schema.

---

## Timeline

| When | What |
|---|---|
| 19:01 | Session opened. Goal: bare hello-world Mastra project, Studio running locally. |
| 19:20 | Scaffolded via `npm create mastra@latest -- --default`, stripped to one agent + one tool. Verified `openai/gpt-5.6-sol` against the docs source — it is a valid direct-provider model, not only a `crossmodel/` gateway one. |
| 19:34 | Verified end-to-end with a real key: agent answers, trace shows `agent_run → model_generation → tool_call → text`. |
| 20:15 | Extended to Carver-awareness, demonstrated by contrast (two agents, one grounded). Topic fixture vendored; 10 tests. |
| 21:30 | Added the annotations layer ("what changed, when, why") — the updates tool, fixture and second design. 23 tests. |
| — | Live verification caught the false-absence bug. Fixed, re-verified, run-sheet derived from real output. |
| — | Demo delivered. Promoted to `carver-demos` as `mastra-studio-demo`. |

---

## Original commit log

The 8 commits from `flux/mastra-studio-ui`, preserved because the promotion was a clean copy
and the branch was deleted. Hashes refer to the now-deleted `carver-adhoc` branch and will not
resolve.

```
7d0159c ✨ feat: minimal Mastra Studio project (hello-mastra)
87ddc06 ✨ feat: vendor Carver topic fixture for the grounded agent
96b8c5c ✨ feat: contrast demo — grounded vs ungrounded agent
b3053dd 📝 docs: document the contrast demo and session findings
0452869 ✨ feat: vendor Carver regulatory updates + searchUpdates matcher
4b69fd1 ✨ feat: searchCarverUpdates tool + fix false-absence in the matcher
3d39ea2 📝 docs: document the staleness contrast and the false-absence lesson
f3ee8cc 📝 docs: add demo run-sheet
```

Their full messages are reproduced in [`build-commit-log.md`](build-commit-log.md).

---

## See also

- [`DEMO.md`](DEMO.md) — the run-sheet: four beats, verified live
- [`superpowers/specs/2026-07-16-carver-aware-agent-design.md`](superpowers/specs/2026-07-16-carver-aware-agent-design.md) — contrast demo design
- [`superpowers/specs/2026-07-16-carver-updates-tool-design.md`](superpowers/specs/2026-07-16-carver-updates-tool-design.md) — updates tool design
- [`../README.md`](../README.md) — what the demo is and how to run it
