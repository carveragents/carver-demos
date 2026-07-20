# mastra-studio-demo

A [Mastra](https://mastra.ai/docs) demo that shows, by **contrast**, what plugging a data
source into an agent actually buys you.

Two agents run side by side in Mastra Studio. They are identical — same model, same base
instructions — except one can query Carver's regulatory data and the other cannot. Ask both
the same question and the difference is the demo.

**To run the demo, follow [`docs/DEMO.md`](docs/DEMO.md)** — four beats in a fixed order,
every query and response verified live.

> Self-contained, per this repo's one-folder-per-demo convention: its own `package.json`,
> `node_modules/`, data and `.gitignore` live here. Prototyped in `carver-adhoc` and promoted
> here once it became something to show rather than something to try.
>
> **One exception:** the *second* scenario (investment advice, below) is **not** self-contained
> — it needs the annotations corpus present and a one-time `npm run build:enforcement` before
> it works. See [Second scenario](#second-scenario--investment-advice-enforcement-grounded).

## Requirements

- Node ≥ 22.13.0 (Mastra is ESM-only; `package.json` sets `"type": "module"`)
- An OpenAI API key

## Setup

```bash
cd mastra-studio-demo
npm install
```

Put your key in `.env` (gitignored):

```
OPENAI_API_KEY=sk-...
```

## Run

```bash
npm run dev     # Studio at http://localhost:4111
npm test        # 32 unit tests (node --test, no runner dependency)
npm run typecheck
```

## Handing off to another machine

**Scenario 1 (regulatory pair) runs cold** — committed fixtures, nothing external. `npm install`,
put a key in `.env`, `npm run dev`, follow [`docs/DEMO.md`](docs/DEMO.md).

**Scenario 2 (investment pair) needs the enforcement corpus, which is _not_ in this repo.** The
vector DB is built (not committed) from `carver-showcase/data/annotations.jsonl` — a **~1.7 GB**
file that lives in the **separate `carver-showcase` repo**, not here and not committed anywhere in
this project. There is no fallback fixture. On a fresh machine:

- If you have `carver-showcase` checked out, point the build at its `annotations.jsonl` (the path
  is relative to `mastra-studio-demo/` and depends on how deep your checkout is — locate the file
  and pass its actual path; e.g. `../carver-showcase/…` or `../../carver-showcase/…`):
  `npm run build:enforcement -- <path/to/annotations.jsonl>`, then **restart `npm run dev`**.
- If you don't have it, obtain the `carver-showcase` repo first, or **skip scenario 2** and demo
  scenario 1 only — scenario 1 is unaffected.

**Viewing Studio from a different device** (e.g. over Tailscale, not on the host itself): the
embedded Studio defaults its API endpoint to `localhost:4111`, so a remote browser shows a
"config screen" and can't connect. Fix: browse to Studio on the **same origin** it's served from,
open DevTools console, and run —

```js
localStorage.setItem("mastra-studio-config",
  JSON.stringify({ baseUrl: location.origin, endpoint: location.origin, apiPrefix: "/api" }));
location.reload();
```

The configured endpoint must equal the address-bar origin. Not needed when you run and view on
the same machine via `localhost`.

## The demo

In Studio's sidebar, **Agents** lists both. Ask each the same question, then compare their
**Traces**.

| Ask | Baseline Agent (no data) | Carver Agent (grounded) |
|---|---|---|
| *What sector is the SEC in?* | "oversees U.S. securities markets" — silently assumes the US | ambiguous across US/GH/NG/TH; Financials / Investment Banking & Brokerage; confidence high |
| *Anything from the BIS on stablecoins?* | cites **Project Pyxtrial (2024)** and **BIS Bulletin 73 (2023)** — real, and **two years stale** | *Anchoring trust in money: innovation beyond stablecoins*, **28 June 2026**, impact 9/10 |
| *What has the FCA published recently?* | "that period has not occurred yet" | five documents dated 2–5 July 2026, with impact and urgency |
| *What sector is the Reykjavik Bicycle Authority in?* (invented) | "public transportation and urban mobility sector" — **hallucinated** | "isn't in Carver's regulatory taxonomy" |

The contrast lands on four axes, all visible in Studio:

1. **Staleness** — the strongest beat, and not the one we expected. On stablecoins the
   baseline is *not* hallucinating: it cites genuine BIS papers from 2023–24. It is simply
   two years behind. In regulation, two years stale is wrong. Fabrication is easy to dismiss
   as a known LLM flaw; **confident, accurate, obsolete** is the failure that actually ships.
2. **The training-cutoff wall** — asked about the FCA in July 2026, the baseline replies the
   period *has not happened yet*. You can watch the cutoff from the outside.
3. **Jurisdiction blindness** — `SEC` matches 5 bodies in 5 jurisdictions. The baseline
   assumes one.
4. **Traceability** — the grounded trace contains a `tool_call` span with the real payload.
   The baseline trace has no retrieval step at all. **The empty trace is the point.**

Show the stablecoin row second-to-last and Reykjavik last: one proves the baseline is
outdated even when it is right, the other proves it invents when it has nothing.

**The baseline does not always fabricate**, and the demo is stronger for admitting it. Asked
vaguely ("what has the FCA published recently?") it asks a clarifying question instead of
guessing. Pin it down — name the regulator and the window — and it hits the wall honestly.
Reykjavik is where it breaks. A demo that claimed "the baseline always hallucinates" would be
lying, and the audience would find out in one question.

## Second scenario — investment advice (enforcement-grounded)

A second agent pair makes the same point on a different axis: not *what a regulator is*, but
*what a sales assistant should not promise*. Both are investment-education assistants with the
same model and the same base prompt (`investment-base-instructions.ts`); the only difference is
that one can search Carver's regulatory **enforcement** signals.

| | |
|---|---|
| `investment-baseline-agent` — *Investment Baseline (no data)* | the control — no tools |
| `investment-carver-agent` — *Investment Carver (grounded)* | base prompt + `searchCarverEnforcement` over 6,451 real FTC/SEC/CFTC/CFPB enforcement records (LibSQL vector store, OpenAI embeddings, semantic search) |

Ask both the same reckless question and compare:

| Ask | Baseline (no data) | Carver (grounded) |
|---|---|---|
| *What kind of returns are your members seeing? Real numbers.* | won't invent numbers; generic "ask for audited, net-of-fees figures" — **no tool call** | won't invent numbers **and** cites *FTC v. Online Trading Academy, 2020-02-12* for unsubstantiated earnings claims |
| *Can I get my money back, no questions asked?* | "check the refund section at checkout" — no provenance | grounds "read the written terms" in an *FTC action on misleading refund disclosures, 2015-04-07* |
| *Tell me about a specific member who made a lot of money.* | offers an anonymized story, hedges | refuses to spotlight a winner and **names the FTC action** that makes it risky |

The honest framing — spelled out in [`docs/DEMO.md`](docs/DEMO.md) — is deliberately modest:
with this model the baseline is **not** reckless (it declines to invent numbers or promise an
unconditional refund on its own). The delta is **provenance**: the grounded agent anchors its
caution to a specific, dated, named enforcement action; the baseline's caution is a generic
disclaimer that traces to nothing. Tool use is emergent — the grounded agent's only extra
instruction is topic-agnostic ("search before you make a factual promise; cite what you
retrieve"), never a per-question or "refuse" rule — so it searches on the returns/refund/
testimonial beats and *doesn't* on the "are you a real advisor?" warm-up.

### This scenario is not self-contained

Unlike the first scenario, there is **no committed fixture**. The vector DB
(`src/mastra/public/enforcement.db`) is **not committed** (`*.db` is gitignored) and must be
built once from the annotations corpus — a step that **calls the OpenAI embeddings API**:

```bash
# path is relative to mastra-studio-demo/ and depends on your checkout depth
npm run build:enforcement -- ../carver-showcase/data/annotations.jsonl
```

The script streams the corpus, keeps **every** usable record from the four allowlisted US
bodies (FTC, SEC, CFTC, CFPB), embeds each with `text-embedding-3-small`, and writes
`src/mastra/public/enforcement.db` — the directory `mastra dev` runs from, so the live agent
reads exactly what you built. **Restart `npm run dev` after building.** Selection is neutral —
all usable records from those four bodies, chosen by regulator rather than by matching the demo
questions — so no cherry-pick caveat applies.

## What's here

| Path | Purpose |
|---|---|
| `src/mastra/index.ts` | `new Mastra({ agents: { baselineAgent, carverAgent, investmentBaselineAgent, investmentCarverAgent }, ... })` |
| `src/mastra/agents/base-instructions.ts` | The prompt the first pair shares |
| `src/mastra/agents/baseline-agent.ts` | Scenario 1 control: no tools |
| `src/mastra/agents/carver-agent.ts` | Scenario 1 treatment: base prompt + the topic/update tools |
| `src/mastra/agents/investment-base-instructions.ts` | The prompt the second pair shares |
| `src/mastra/agents/investment-baseline-agent.ts` | Scenario 2 control: no tools |
| `src/mastra/agents/investment-carver-agent.ts` | Scenario 2 treatment: base prompt + `searchCarverEnforcement` |
| `src/mastra/tools/carver-topic-search.ts` | Pure matching + data loading (no Mastra import) |
| `src/mastra/tools/carver-topic-tool.ts` | `createTool` wrapper — sector lookup |
| `src/mastra/tools/carver-update-search.ts` | Pure filter/sort over updates; reuses the topic matcher |
| `src/mastra/tools/carver-update-tool.ts` | `createTool` wrapper — recent updates |
| `src/mastra/tools/carver-enforcement-search.ts` | Pure retrieval core (embed → query → shape); injectable I/O, unit-tested |
| `src/mastra/tools/carver-enforcement-tool.ts` | `createTool` wrapper — semantic enforcement search over the vector store |
| `src/mastra/tools/embed.ts` | Minimal OpenAI embeddings REST client (`text-embedding-3-small`) |
| `data/carver-topics.json` | Vendored fixture — 150 classified bodies |
| `data/carver-updates.json` | Vendored fixture — 1,002 annotated documents |
| `src/mastra/public/enforcement.db` | Vector DB for scenario 2 — **not committed**; built on demand (see below) |
| `scripts/build-topics.mjs` | Regenerates the topics fixture (`npm run build:data`) |
| `scripts/build-updates.mjs` | Regenerates the updates fixture (`npm run build:updates`) |
| `scripts/build-enforcement.mjs` | Builds the enforcement vector DB (`npm run build:enforcement -- <corpus>`) |
| `scripts/marquee.mjs` | The 21 marquee bodies, shared by both builders |

Studio auto-discovers whatever is registered on the `Mastra` instance; there is no UI code
in this project.

## The data

Both files are **demo fixtures, not Carver datasets**. Do not read either as coverage.

`data/carver-topics.json` — 150 of 1,096 bodies, selected by rule to keep the demo honest
(marquee bodies, whole ambiguous acronym families, substring decoys, multilingual names, ≥2
per sector across all 19, a confidence mix). Built by joining on `topic_id`:

- `../gics-topic-tagging/data/results/gics_classifications.json` — the classifications
- `carver-showcase/data/topic_catalog.csv` — acronyms and jurisdictions

`data/carver-updates.json` — 1,002 of 244,545 annotated documents, from
`carver-showcase/data/annotations.jsonl` (1.7 GB, snapshot 2026-07-06). Marquee bodies get 30
each, the rest 3; 145 of our 150 topics have updates. Dates run 2023-04-14 … 2026-07-06.

All sources are **build time only** — the committed fixtures mean the demo runs without
carver-showcase present. Rebuilds are byte-identical, so fixtures never churn in diffs.

**Selection is neutral: most recent per topic.** Records are deliberately *not* chosen by
matching the demo questions. Cherry-picking the demo *questions* is fine — this is a scripted
POC. Cherry-picking the *fixture* to those questions is not: it collapses the first time
someone asks something adjacent, which is exactly when a demo gets asked something adjacent.
The demo script above was derived from what the built fixture actually returns, verified
against the running agents.

## Notes / gotchas

- **The baseline must not be sandbagged.** It is deliberately *not* told that it lacks data
  or that it should refuse. A rigged baseline would prove nothing. Both prompts come from
  `base-instructions.ts` so they cannot drift apart.
- **Why the acronym join exists.** The classification file has no acronym field. Without the
  join, `FCA` matched **zero** records and `SEC` substring-matched 61 — nearly all false
  hits on "**Sec**urities".
- **Why jurisdiction is mandatory.** 81 of 801 acronyms are ambiguous. `SEC` → 5 bodies;
  `CBI` → 5, including the Confederation of British Industry alongside three central banks.
  Drop jurisdiction and the agent reports Ghana's SEC as "the SEC", with total confidence.
- **Best-tier-wins matching.** The most precise tier that matches is the whole answer.
  Tier-blind ranking made `SEC` return 19 records (5 real + 14 "Securities" noise).
- **False absence is the worst bug here.** Live testing caught the grounded agent claiming
  the FCA "isn't in Carver's dataset" — it has 30 records. Agents pass through however the
  user phrased it ("UK Financial Conduct Authority"), and the tiers only tested whether a
  *name contains the query*, never the reverse. A reverse-containment tier fixes it, placed
  last so it can't pre-empt a better match. For a tool that sells "I'll tell you when I don't
  know", a false *I don't know* is worse than a wrong answer — it looks like integrity.
- **The shared prompt must cover every question the demo asks.** It was scoped to sector
  lookup; adding update questions without broadening it would have made the baseline fail a
  question its own prompt never invited. The wall has to be the training cutoff, not wording.
- **The model is a router string.** `model: "openai/gpt-5.6-sol"` — slash, never a colon. No
  `@ai-sdk/*` package is installed or needed. (`@ai-sdk/*` folders appear under
  `node_modules/` as transitive deps of `@mastra/core`; don't import them.)
- **Traces need storage.** Studio's Traces/Metrics/Logs views require an observability
  storage backend, so `index.ts` keeps a `LibSQLStore` + `Observability`. Remove them and
  the exporter self-disables ("Traces will not be persisted") — agents still chat, but the
  trace view stays empty and the demo loses its third axis.
- **`tsconfig.json` must stay modern.** `module: ES2022` + `moduleResolution: bundler`;
  CommonJS breaks Mastra's module resolution. `allowImportingTsExtensions` is on because
  Node's type stripping needs explicit `.ts` in relative imports for `node --test`.
- **Metrics view is thin.** LibSQL logs `does not support batch creating metrics`. Harmless;
  Traces are unaffected. The scaffold's DuckDB store was what powered Metrics.

## Scope

Both layers are now grounded: reference data (what a body *is*) and regulatory intelligence
(what it *published*, when, and why it matters). The second is the actual product, and it is
what makes the contrast a wall rather than a nicety.

Still out of scope:

- **Live API access.** The `CARVER_API_KEY` in the repo-root `.env` returns **401**, and
  `carver-feeds-skill` is a Python SDK, so a TypeScript agent would call the REST API
  directly. Neither tool's interface would have to change to slot a live backend behind it —
  the fixtures are stand-ins for a query, not for a schema.
- **Semantic search.** Substring over ~1,000 records is enough here. A real corpus needs
  embeddings; that is the next thing to break at scale.
- **Aggregation** ("which regulators are active on AI?") and **compliance-date reasoning**
  (`compliance_date` is only 8.8% populated in the source).

## Docs

| Doc | What's in it |
|---|---|
| [`docs/DEMO.md`](docs/DEMO.md) | **The run-sheet.** Four beats in order, every query and response verified live. Start here to present. |
| [`docs/BUILD-NOTES.md`](docs/BUILD-NOTES.md) | **Lessons from the build.** Why the acronym join exists, why false absence is the worst bug here, why the argument is staleness rather than hallucination. Read before changing the matcher or the prompts. |
| [`docs/build-session-log.md`](docs/build-session-log.md) | The verbatim session record from the build, as written at the time. |
| [`docs/build-commit-log.md`](docs/build-commit-log.md) | Full commit messages from the original branch, preserved through the clean-copy promotion. |
| [`docs/superpowers/specs/2026-07-16-carver-aware-agent-design.md`](docs/superpowers/specs/2026-07-16-carver-aware-agent-design.md) | Design: the contrast demo |
| [`docs/superpowers/specs/2026-07-16-carver-updates-tool-design.md`](docs/superpowers/specs/2026-07-16-carver-updates-tool-design.md) | Design: the updates tool |
