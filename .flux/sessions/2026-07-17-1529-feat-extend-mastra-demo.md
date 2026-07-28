# feat-extend-mastra-demo — 2026-07-17 15:29

## Session Overview

- **Start:** 2026-07-17 15:29
- **Branch:** `feat-extend-mastra-demo`
- **Focus:** Extend the `mastra-studio-demo` (grounded vs ungrounded agent contrast). Specific
  direction to be provided by the user during the session.

## Goals

- Extend the existing `mastra-studio-demo` per direction from the user (TBD).
- Preserve the demo's core invariants while extending:
  - Baseline must not be sandbagged — both agents share `BASE_INSTRUCTIONS` verbatim.
  - Fixture selection stays neutral (most-recent-per-topic), not cherry-picked to questions.
  - Keep tests green and `npm run typecheck` clean.
- Keep `docs/DEMO.md` and `docs/BUILD-NOTES.md` in sync with any behavioral change.

## Context (from session start)

- Demo is currently **complete and verified**: clean tree, tests present, no TODOs.
- Two agents, same model (`openai/gpt-5.6-sol`) + same base prompt; Carver Agent has two
  tools (`searchCarverTopics`, `searchCarverUpdates`), Baseline has none.
- 4-beat argument: staleness (money shot), training-cutoff wall, jurisdiction blindness,
  traceability (empty trace).
- Fixtures: `data/carver-topics.json` (150 bodies), `data/carver-updates.json` (1,002 docs),
  snapshot 2026-07-06, rebuildable but committed so the demo runs standalone.
- Out of scope so far: live API (key 401s), semantic search, aggregation, compliance-date.
- **Read before touching matcher/prompts:** `mastra-studio-demo/docs/BUILD-NOTES.md`.

## Progress

- Session started; awaiting specific direction for the extension.
- **2026-07-17 ~15:35 — Environment verified, both agents live.**
  - `.env` with `OPENAI_API_KEY` placed at `mastra-studio-demo/.env` (gitignored).
  - `npm install` (534 pkgs). `npm run typecheck` clean. `npm test` → 23/23 pass.
  - Studio running: `npm run dev` in background, http://localhost:4111 (log:
    `scratchpad/mastra-dev.log`). Registered agents: `baseline-agent`, `carver-agent`.
  - Beat 1 ("What sector is the SEC in?"): baseline answers tool-free (assumes US);
    carver fires `searchCarverTopics` → 4 jurisdictions (US/GH/NG/TH). ✅
  - Beat 3 (FCA late-June/early-July 2026): carver fires `searchCarverUpdates` → real dated
    records with impact/urgency. ✅ Both tools wired and working.
- **2026-07-17 ~15:55 — Diagnosed "Mastra config screen" when accessing Studio remotely.**
  - Symptom: over Tailscale, Studio shows "Failed to load studio — could not reach the Mastra
    server at http://localhost:4111" (the connect/endpoint form).
  - Root cause: `mastra dev`'s embedded Studio bakes its API endpoint default to
    `http://localhost:4111` (not `window.location.origin`). Loaded from a remote origin, the
    browser's `localhost` is the *viewer's* machine → fetch fails.
  - Dead end: running a 2nd `mastra studio -p 4112 --server-host <tailscale-ip>` makes UI and
    API different origins → hits **credentialed CORS**: `/api/auth/capabilities` uses
    credentials:'include', server replies `Access-Control-Allow-Origin: *`, which browsers
    forbid for credentialed requests. So cross-origin can't work without server CORS changes.
  - **Fix (same-origin):** load the `mastra dev` Studio at the SAME host you're browsing, e.g.
    `http://100.78.210.42:4111`, and set its endpoint to that same address so UI origin == API
    origin. Config lives in `localStorage["mastra-studio-config"]`
    (`{baseUrl,endpoint,apiPrefix:"/api"}`). Verified via Playwright: seeding that key → both
    agents render, no error. The configured endpoint MUST equal the address-bar origin.
  - Note: `mastra dev` binds `*:4111` (public IP 137.184.172.251 exposed); Tailscale
    (100.78.210.42) keeps it private. Box: openclaw-achint (DO droplet).
  - **Gotcha (per-origin config):** this box's Tailscale name is `jarvis-openclaw` (=
    100.78.210.42; `tailscale status`). User accesses from laptop (`achints-macbook-pro`) via
    `http://jarvis-openclaw:4111`. `jarvis-openclaw:4111` and `100.78.210.42:4111` are the SAME
    server but DIFFERENT browser origins; `mastra-studio-config` is per-origin. Setting the
    endpoint to the IP while browsing the name = cross-origin = blank screen.
  - **Bulletproof recipe (no host to mistype):** on the Studio origin, DevTools Console:
    `localStorage.setItem("mastra-studio-config", JSON.stringify({baseUrl:location.origin,endpoint:location.origin,apiPrefix:"/api"})); location.reload();`
    Verified: 0 console errors, both agents render. User confirmed Studio works.
- **2026-07-17 ~16:07 — Synced transcript from origin/main.** Fast-forwarded branch
  `b0ccfcb9..963c7c89` (no own commits yet), bringing
  `mastra-studio-demo/scratch/ai-compliance-transcript.txt` (8.4 KB) with real history.
  - Content: scripted AI-compliance demo (Vin Rao). Rogue investment-education agent
    (unsubstantiated 15–30% returns, no-questions-asked refunds, invented member numbers) →
    Carver SDK pulls FTC/SEC **enforcement signals** (e.g. publishing.com deceptive-earnings)
    → **policy diff** → compliant **v2 policy/agent** on the same questions.
  - Note: this is a *policy-enforcement* story (closer to `policy-diffs`), distinct from the
    current demo's grounded-vs-ungrounded *retrieval* contrast.
  - Direction from user: **context only for now**; specific direction to follow.

---

## Session Summary (ended 2026-07-23)

**Duration:** 2026-07-17 → 2026-07-23 (multi-day). **Note:** session started on `feat-extend-mastra-demo`
but all work landed on branch **`feat-mastra-guardrail-port`** (the guardrail port branch); nothing pushed.

### Git summary
- **26 commits** on `feat-mastra-guardrail-port` vs `main` (whole session). ~14 in the final stretch
  (the state-lending demo + operational-cost measurement).
- **Final state of this conversation's work:** 20 files added, 8 modified (all under `mastra-studio-demo/`).
- **Final git status:** clean working tree. **Not pushed.**
- Key added files: `src/mastra/tools/lookup-applicant-tool.ts`, `agents/lending-status-*.ts`,
  `agents/{advisor-*,crypto/device/child-safety-carver}.ts`, `data/state-lending-records.json`,
  `scripts/{lending-status-probe,trigger-probe,build-curated-index,state-lending-probe}.mjs`,
  `docs/corpus-gaps-for-jurisdiction-demos.md`.

### Key accomplishments
1. **Found the ONE content-win scenario in 12 probes** — a Carver-grounded agent beating BOTH baseline
   and live web search on answer content. Everywhere else the honest pitch is operational, not "better
   answers" (cross-domain mini-suite: web reaches content parity).
2. **The winning "lending-status" demo** — signed-in applicant asks for loan status + gives an applicant
   ID → `lookupApplicant` (auth/CRM stand-in) returns their file incl. **state** → the Carver arm surfaces
   the state-specific obligation baseline/web miss: **CO-1001** Colorado AI Act, **CA-1001** Holden Act,
   **NY-1001** federal-only (control). State never typed; visible in the trace.
3. **Operational cost measured** at real gpt-5.6-sol rates: Carver gives the better answer for **43–63%
   less than web search** ($44.45/1k vs $78 warm–$122 cold), cache-independent; latency a wash.

### Features implemented
- `lookupApplicant` tool (3 profiles, state the only variable, forgiving ID normalize).
- Registry pruned to 5 demo-usable agents (scenario-1 pair + 3 lending-status arms); ~12 measurement
  agents intentionally unregistered (source retained).
- `build-curated-index.mjs` (embed a reviewed records file into a vector index, distinct from the crawler).
- Probes: `lending-status-probe.mjs` (content + cache-split tokens + $ cost, billed vs cold), `trigger-probe.mjs`.

### Problems encountered & solutions
- **Web arm + function tool:** feared `@mastra/core` drops function tools mixed with provider `webSearch`;
  verified it does NOT in this version — all 3 arms share `lookupApplicant`.
- **Future decline date (2027-01-14) not explainable:** searched for a present-in-force substitute — none
  clean (automated-decision-disclosure wave is uniformly Jan 1 2027; medical-debt bans preempted). Kept
  2027 and framed the scenario deliberately as "early Jan 2027"; verified CO beat deterministic at 2027 date.
- **Prompt-asymmetry confound:** neutralized the Carver tool description; confirmed web still misses even
  when nudged → win isn't a prompt artifact.
- **Broken install:** `@ai-sdk/openai` declared but missing from node_modules (broke every web-search agent).

### Important findings / caveats (MUST travel with the win)
- The win runs on **4 hand-curated records** (`data/state-lending-records.json`), NOT the crawled corpus
  (CO AI Act = 0 of 242k). Drop them → win collapses to parity (measured). Only the **2 state records** are
  load-bearing. Records are REVIEW-REQUIRED.
- Web's cost figure is a **floor** (excludes OpenAI's internal web_search fetch/rank tokens — unexposed by
  any API, so a separate key would NOT help a tokens comparison).

### Dependencies / config
- Installed `@ai-sdk/openai@4.0.17` (was missing); kept `package.json` caret at `^4.0.16`.
- Added `build:curated` npm script. Registered `state-lending`/`crypto-assets`/`medical-devices`/`child-safety`
  domains in `data/carver-domains.json`. New `.db` fixtures are gitignored (rebuild via `build:domain`/`build:curated`).

### What wasn't completed
- Nothing pushed; no PR/merge.
- Curated records not yet legally/data-reviewed.
- Corpus doesn't hold these obligations organically — data-team ingest list in
  `docs/corpus-gaps-for-jurisdiction-demos.md` (add `leg.colorado.gov` as a topic, etc.).

### Tips for future developers
- Resume from `docs/continuing.md` and `docs/DEMO.md` ("The state-lending counterfactual swap" + Beat 4).
- Re-run: `npm run dev` then `node scripts/lending-status-probe.mjs 3`. Rebuild index:
  `npm run build:domain -- state-lending ../../carver-showcase/data/annotations.jsonl` then
  `npm run build:curated -- state-lending data/state-lending-records.json`.
- Persistent memory written: `carver-lending-demo`, `carver-corpus-gaps`.
- `sqlite3` CLI absent — query the corpus via node + `@libsql/client`, or stream the JSONL.
