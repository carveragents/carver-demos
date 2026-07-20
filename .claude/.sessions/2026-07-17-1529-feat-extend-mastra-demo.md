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
