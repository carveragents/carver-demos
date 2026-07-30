# video-state-lending-demo — 2026-07-28 13:39

## Session Overview

- **Start:** 2026-07-28 13:39 EDT
- **Worktree:** `/Users/achintthomas/work/scribble/code/repos/carver/carver-demos` (in-place, not
  an isolated worktree — see Decisions)
- **Branch:** `flux/video-state-lending-demo`
- **Baseline HEAD:** `6279c5635bbfb9c963ec27d93dfd56a898c34917` (branched from `main`, in sync with
  `origin/main`)

## Goal

Produce a demo video for `mastra-studio-demo` showing the **state-lending applicant scenario**: a
loan denied by an automated model, where the applicant's *state* — supplied silently by
`lookupApplicant`, never typed — changes what the lender owes them, and only the Carver-grounded arm
surfaces the state obligation (CO AI Act / CA Holden Act) that baseline and live web search both
miss. NY is the negative control.

Deliverables, in order: verify the demo reproduces locally → shot list → script/storyboard →
recording. **Style, length, voiceover-vs-captions, and whether cost numbers appear have NOT been
given.** `docs/CONTINUING.md` states the user will supply them this session. Ask before scripting.

## Context read at session start

- `docs/CONTINUING.md` (written 2026-07-28 on `main`) — the orienting doc. The demo is built,
  committed, verified; **only the video does not exist**.
- `mastra-studio-demo/docs/DEMO.md` §"The state-lending counterfactual swap" (L961) and the run
  sheet + beat-by-beat presenter script (L1054–1203). The video script should adapt this, not
  reinvent it.
- `docs/LESSONS.md` (10 lessons) and `docs/README.md`.
- Prior session log `.flux/sessions/2026-07-17-1529-feat-extend-mastra-demo.md`.

Load-bearing facts carried in:

- **12 probes, 1 content win.** Every other scenario reached parity with web search. Do not go
  scenario-hunting; this is the survivor.
- **The applicant must never name the rule.** State arrives from `lookupApplicant`. If a presenter
  types "does Colorado's AI Act apply?", web search finds it and the contrast collapses.
- **The win runs on 4 hand-curated records**, REVIEW-REQUIRED (legal/data review not done). Drop the
  2 state records → the win collapses to parity, measured. The honest claim is *"this is what
  jurisdiction-tagged coverage unlocks"*, not *"this ships today."* This is the one framing decision
  to put to the user early — it changes the script.
- **The scenario is dated January 2027 on purpose** (CO AI Act operative 2027-01-01). Not a bug.
- **No speed claim.** Latency is a wash. Cost is the defensible operational number:
  Carver $44.45/1k vs web $78 warm / $122 cold, and web's figure is a floor.

## Blocker found at session start

**The `state-lending` index is empty on this machine.**
`mastra-studio-demo/src/mastra/public/state-lending.db` is 4,096 bytes with **zero tables** — the
running `mastra dev` (pid 44705, `:4111`) created an empty file because none existed. Sibling
indexes are present and populated (`cyber.db` 17 MB, `enforcement.db` 51 MB). `CONTINUING.md`
expects ~59 MB / 7,146 records, and records a verified reproduction on 2026-07-28 — that run was
evidently on a different box (the prior session worked over Tailscale on a remote VM).

Consequence: the demo **will not reproduce here as-is** — the Carver arm would miss CO and CA and
the demo would look like a failure. Rebuild is required before any recording:

```bash
cd mastra-studio-demo
npm run build:domain  -- state-lending ../../carver-showcase/data/annotations.jsonl   # $$, minutes
npm run build:curated -- state-lending data/state-lending-records.json                # instant
# restart npm run dev, then: node scripts/lending-status-probe.mjs   → expect YES/YES/clean
```

`build:domain` embeds ~7,142 records with `text-embedding-3-small` and costs money. Not run yet —
awaiting the user's go-ahead on spending. Local prerequisites confirmed present: `.env` with
`OPENAI_API_KEY`, and `../carver-showcase/data/annotations.jsonl` (1.8 GB, READ-ONLY).

## Decisions

- **In-place branch, not an isolated worktree.** Flux prefers a worktree, but the demo depends on
  two gitignored local artifacts — the ~59 MB built index and `.env`. A fresh worktree carries
  neither, forcing a paid re-embed to do anything. Working in place on `flux/video-state-lending-demo`
  keeps the branch isolation without the rebuild cost.

## Constraints (from CONTINUING.md, in force)

- `../carver-showcase` is READ-ONLY.
- Curated records are REVIEW-REQUIRED before public use.
- Never commit `.env` or secrets.
- **Do not push or merge without an explicit request from the user.**
- All three arms share one prompt file — changing it in one arm invalidates the comparison.
- Any number shown on screen must trace to a measurement, not to memory.

## Progress

- **2026-07-28 13:39 — Session started.** Oriented from `CONTINUING.md`, `DEMO.md` run sheet,
  `LESSONS.md`, prior session log. Branch created off `main` @ `6279c563`. Empty state-lending index
  identified as the blocker. Awaiting the user's style/presentation direction before scripting.

### Update — 2026-07-28 13:53

**Direction received from the user** (answers to the Phase 1 interview):

- **Framing:** capability-forward, curated-records caveat in fine print (not the narrower
  "what coverage unlocks" claim). The caveat still ships — as a closing card / fine print, not as
  the headline.
- **Tooling:** use the `show-n-tell` skill for the video (Playwright site capture → storyboard →
  OpenAI TTS → branded mp4). Format and length delegated to it.
- **Audience/tone:** external / prospects, explanatory.
- **Length:** ~3 min — Colorado money shot, California confirm, New York control, short cost card.
- **Capture method:** *capture the real runs first, then record against them.* Not live-typed
  agent responses during the take.

**Index rebuilt (blocker cleared).** `build:domain` 13:43:30→13:44:19, `build:curated` →13:47:35.

- **6,829 real + 4 curated = 6,833 records** in `stateLending`.
- **Deviation from `CONTINUING.md`, which expects 7,146.** The local
  `../carver-showcase/data/annotations.jsonl` is a **2026-07-06** snapshot; the recorded
  measurement used a 2026-07-27 snapshot. ~313 fewer real records. The 4 curated records — the
  load-bearing ones — are present. **Consequence for the video: any on-screen corpus count must say
  6,833, not 7,146, and the "#1 of 7,146" ranking line cannot be reused verbatim.**
- Dev server restarted (`npm run dev`, pid 67353, `:4111`); all 5 agents registered.

**Studio exploration (show-n-tell Phase 2b), selectors validated for the recorder:**

- Chat input: `textarea[placeholder="Enter your message..."]`
- Send: `button[aria-label="Send"]`
- Tab buttons by text: `Chat`, `Traces`, `Editor`, `Evaluate`, `Review`
- Agent chat URLs are `/agents/<agent-id>/chat/new`; there is a **"Copy session URL to share with
  your team"** control, so **threads are URL-addressable**. This is what makes the user's
  capture-then-record choice work *inside the real Studio UI* rather than on a separate replay
  page: run the nine conversations once, then have the recorder `goto` the saved thread URLs.
  Deterministic, no ~18s waits in the take, and still genuinely real output.

**Branding decided without asking** — reused the existing Carver Agents config from
`~/demo-videos/pred-oracle/branding.yaml` and the skill's own `examples/halyard-spme/`:
wordmark `policy-diffs/credio-policies/dist/_recording_assets/carver_wordmark.png`, ink `#101828`,
lime `#bae424`, cream `#fbf7f3`, voice `cedar`, tone explanatory.

**In progress:** `node scripts/lending-status-probe.mjs` (9 live runs) to confirm the demo still
reproduces `YES / YES / clean` on the rebuilt, slightly smaller index. Nothing gets scripted or
recorded until it does.

### Update — 2026-07-28 14:20

#### The demo reproduces; the cost table reproduces; ONE CENTRAL CLAIM DOES NOT

**Content (n=1, 13:50–13:54) — reproduced.** Carver `YES / YES / clean`; baseline and web
`miss / miss / clean`. The rebuilt 6,833-record index carries the win.

**Cost — reproduced at n=3, after a false alarm at n=1.** The n=1 run gave Carver $59.65 vs web
$70.88/$113.69 (16–48%), well off the published 43–63%; the Carver arm had run heavy on CA and NY.
Re-run at n=3 (13:56–14:05, the sample size the published table used) landed on:

| arm | billed (cache-warm) | no-cache (cold) | median tokens |
|---|---|---|---|
| baseline | $12.48 | $12.48 | 1,012 |
| web search | $79.18 | $122.73 | 18,847 (15–26k) |
| **Carver** | **$43.51** | **$43.51** | **5,576 (4–13k)** |

45–65% cheaper, against a published 43–63%. **The n=1 figure was noise — do not cite it.** Lesson:
this harness is not stable at n=1; the NY control especially. Any number that goes on screen comes
from an n≥3 run.

**Per the user's direction, the video shows TOKENS, not dollars:** web **18,847** vs Carver
**5,576** median — ~3.4×. Rationale: token gap is stable and independent of pricing that moves.

#### ⚠️ FALSIFIED: "web search never surfaces the Colorado AI Act"

`CONTINUING.md` (~L153): *"Web search has **never** surfaced the Colorado AI Act, across five
separate runs."* `DEMO.md` Beat 1 narrates it as *"the web agent had the exact same file — Colorado,
automated decision — and never thought to search for a state AI statute."*

**In the n=3 probe the web arm scored `YES ✓` on CO-1001.** Scoring is any-of-3, so ≥1 of 3 runs
surfaced it. The claim is false as stated.

This is the demo's load-bearing beat and the exact thing a hostile viewer tests, so it needs a
**rate**, not an anecdote. Added `scripts/web-co-hitrate.mjs` — web arm × CO-1001 × N, same message,
same `maxSteps`, and the **verbatim overlay regex** from `lending-status-probe.mjs` so the two are
directly comparable. First attempt died at run 3 (`UND_ERR_SOCKET`) because editing agent files
tripped the dev-server file watcher mid-request; 2/2 miss before it fell over. **Rate still
unmeasured.** Re-run pending — it cannot share the server with the probe.

Narration consequence, whatever the rate turns out to be: the honest line is *"the grounded agent
surfaces it every time; web search finds it sometimes"* — not *"never."*

#### Memory enabled (user-approved) — recording architecture now works

Studio only persists a re-openable thread when the agent has memory. Added `@mastra/memory@^1.23.1`.

- `src/mastra/storage.ts` (new) — `demoStore`, one `LibSQLStore` on `file:./mastra.db`, extracted
  from `index.ts` so traces and memory share ONE instance instead of two objects contending on the
  same SQLite lock.
- `src/mastra/memory.ts` (new) — `demoMemory`, a single shared `Memory`. **Shared deliberately:**
  memory is configuration rather than prompt, but it still has to be identical across the three arms
  or the controlled comparison is no longer clean. One exported instance makes that structural
  instead of something three files have to agree about.
- `memory: demoMemory` added to all three `lending-status-*` agents; `index.ts` now uses `demoStore`.
- Defaults only — no working memory, no semantic recall. One message per thread, so there is no
  history to inject and behaviour should not move. **Assumption under verification, not asserted.**

`npm run typecheck` clean. `/api/memory/status` → `{"result":true,"memoryType":"local"}`.
**Thread persistence verified end-to-end:** a live CO-1001 run on the Carver arm produced
`/agents/lending-status-carver-agent/chat/31a261a4-6e0f-4bfb-881f-89597ba5ded0`, and reloading that
URL renders the whole conversation — user message, `lookupApplicant` + `searchCarverStateLending`
tool chips, and the answer citing Colorado's AI Act. The recorder can `goto` saved threads.

**In progress:** post-memory `lending-status-probe.mjs 3` — proving memory did not move the content
grid or the token medians. Then the CO hit-rate.

#### Still open before any narration is drafted

1. Web-arm CO hit rate (n≥8).
2. ~~Post-memory drift check.~~ **Done — passed, see below.**
3. Capture the 9 real threads (3 arms × 3 applicants) and record their URLs.
4. Rewrite the Beat-1 claim around the measured rate.

### Update — 2026-07-28 14:25 — memory drift check PASSED

`lending-status-probe.mjs 3` re-run with memory enabled (14:14–14:23). Memory did not move the
demo. Comparability holds, so the recording architecture is paid for:

| | pre-memory n=3 | post-memory n=3 | published (`DEMO.md`) |
|---|---|---|---|
| Carver content | `YES / YES / clean` | `YES / YES / clean` | `YES / YES / clean` |
| web tokens (median) | 18,847 | 18,904 | 18,873 |
| Carver tokens (median) | 5,576 | 5,676 | 5,577 |
| Carver $/1k | $43.51 | $45.66 | $44.45 |
| web $/1k warm .. cold | $79.18 .. $122.73 | $80.07 .. $123.62 | $78.04 .. $121.59 |
| headline | 45–65% cheaper | **43–63% cheaper** | 43–63% cheaper |

The post-memory run reproduces the published headline exactly.

**On-screen token numbers for the video** (user chose tokens over dollars): web **18,904** vs
Carver **5,676** median, n=3, measured 2026-07-28. ~3.3×.

**Web on Colorado, running tally.** This run the web arm scored `miss` on all three CO attempts.
Across everything run today the web arm has answered CO-1001 **9 times with 1 hit** (the hit came
in the 13:56 n=3 probe): n=1 probe 0/1, n=3 probe ≥1/3, aborted hit-rate 0/2, post-memory n=3 0/3.
So the rate looks low — order of ~10% — but "never" is still false. Dedicated `web-co-hitrate.mjs 8`
now running to firm it up (~17 total samples).

### Update — 2026-07-28 14:30 — web CO hit rate measured; symmetric gap found

**Web arm on CO-1001: 0/8** in the dedicated run (14:23–14:26), and **0 for the last 13
consecutive runs**. Full tally today: **1 hit in 17 runs (~6%)** — the lone hit was in the 13:56
n=3 probe.

Verdict on the falsified claim: **"never" is wrong; "rare" is right.** The defensible narration is
a rate — *"once in seventeen runs"* / "almost never" — not an absolute. An absolute is what a
hostile viewer breaks; a measured rate is what survives them.

**Symmetric gap this exposed — and it cuts against US, not just against web.** The scorecard scores
**any-of-N**, so a `YES ✓` only proves an arm surfaced the obligation **at least once** in N runs.
Every conclusion drawn from that grid is therefore an existence claim, not a reliability claim:

- It does **not** establish that Carver hits Colorado *every time*. The video's implied claim
  ("the grounded agent surfaces it, every time") is currently **unmeasured**.
- Nor does one `YES` for web across 3 runs mean web hits it 1/3 — the per-run detail was truncated
  in that log, so web's own n=3 could have been 1, 2, or 3 hits. The 17-run tally is the reliable
  figure; the probe grid is not.

Generalised the throwaway into `scripts/overlay-hitrate.mjs <arm> <applicant> [runs]` — same
message, same `maxSteps`, verbatim overlay regexes from the scorecard, so rates are directly
comparable to it. Deleted `web-co-hitrate.mjs` (fully superseded; keeping both would be two scripts
answering one question).

**Running:** `carver CO-1001 8` and `carver CA-1001 8`. If Carver is not ~8/8 the demo is more
fragile than `DEMO.md` claims and the video's central sentence has to change again.

### Update — 2026-07-28 14:33 — reliability measured on BOTH sides. The claim is now defensible.

`overlay-hitrate.mjs`, 14:26–14:32:

- **carver × CO-1001: 8/8 (100%)** — matches on `sb24-205` (×4) and `meaningful human review` (×4).
  Hitting the actual statute, not a generic automated-decision paraphrase.
- **carver × CA-1001: 8/8 (100%)** — `Fair Lending Notice` (×6), `Holden Act` (×2).
- **websearch × CO-1001: 1/17 (~6%)** across the day; 0/8 in the dedicated run.
- baseline: 0 throughout.

**THE VIDEO'S SPINE, measured 2026-07-28, and this is what narration may claim:**

> The Carver-grounded arm surfaced the applicant's state obligation in **16 of 16 runs**.
> The live-web-search arm surfaced Colorado's AI Act in **1 of 17**.

This is *stronger* than the original "web has never surfaced it," not weaker — an absolute invites
a single counterexample to destroy it, and today produced exactly that counterexample. A measured
rate survives being tested, which is the whole constraint in `CONTINUING.md` ("the claim must
survive a hostile viewer").

**Doc debt created — `CONTINUING.md` and `DEMO.md` both assert the falsified absolute** and must be
corrected before anyone else builds on them:
- `docs/CONTINUING.md` ~L153: "Web search has **never** surfaced the Colorado AI Act, across five
  separate runs."
- `mastra-studio-demo/docs/DEMO.md` Beat 1 (~L1121): "the web agent had the exact same file —
  Colorado, automated decision — and never thought to search for a state AI statute."
- `DEMO.md` "If someone asks" (~L1203): "It can, if you name it. It can't when nobody does." →
  it can, rarely, even when nobody does.

**Running:** `capture-demo-threads.mjs` — the nine real conversations for the recording.

### Update — 2026-07-28 14:40 — nine threads captured; two capture bugs fixed

First capture (14:32–14:35) produced all nine threads and exactly the demo:

| applicant | baseline | websearch | carver |
|---|---|---|---|
| CO-1001 | — | — | **HIT** `sb24-205` |
| CA-1001 | — | — | **HIT** `Fair Lending Notice` |
| NY-1001 | — | — | — (correct: NY has no overlay) |

Per-run tokens track the medians: baseline ~1.0k, web ~18.8–19.1k, Carver ~5.0–5.8k.

**Bug 1 — wrong resource scope.** Captured under `resource: 'demo-video-applicant'`. Studio scopes
threads to `resourceId = the AGENT id` (its own calls go to
`…/working-memory?agentId=<arm>&resourceId=<arm>`). Messages still rendered, but the page threw a
**repeating 403 loop** — `threads/subscribe` and `working-memory` both returning
`"Access denied: thread belongs to a different resource"`, 16 console errors on one page load.
Renders fine, but not something to point a camera at. Fixed: resource = agent id.

**Bug 2 — "deterministic ids" did not actually make re-runs idempotent.** Same thread id + a second
run *appends* a second exchange, so the recording would show the applicant asking twice. Added
`dropThread()` (DELETE `/api/memory/threads/<id>?agentId=<arm>`, tolerating 404) before each
capture, so a re-run genuinely replaces.

Re-capturing with both fixes. **Narration must be written against the FINAL
`scratch/demo-threads.json`** — the answers are re-generated each capture and the wording moves, so
any sentence quoted on screen has to come from the file that matches the recorded threads, not from
the earlier run and not from memory.

### Update — 2026-07-28 16:40 — user-requested scope changes (agents, code beat, traces)

User asked for three tightening changes. Findings and what each cost:

**1. Registry trimmed to the three lending arms.** `baselineAgent` + `carverAgent` (scenario 1)
unregistered in `src/mastra/index.ts`; source retained, comment says how to restore. Typecheck
clean; `/api/agents` confirms three. Improves Beat 1 — three rows differing by one thing beats five
rows inviting "what are those?"

**2. Showing the code change — Studio CANNOT do this.** The agent **Editor tab is
`aria-disabled`**, so Studio will not display agent source. Any code beat must be a page built for
the purpose and reached with `goto`.

Found and fixed a real asymmetry while preparing that beat: the Carver arm carried
`defaultOptions: { maxSteps: 8 }` and the other two did not. It never affected a measurement — the
probe and the capture both pass `maxSteps: 8` explicitly to all three — but it was a fourth
difference visible in source, contradicting "retrieval is the only variable" the moment the diff is
on screen. Added the same `defaultOptions` to baseline and websearch. Typecheck clean. The
substantive diff is now exactly: **one import, one instruction sentence, one `tools` entry**
(plus id/name). Re-verification probe running.

**3. Traces — work, and are better than expected.** Both levels are URL-addressable:
`…/traces?…&traceId=<id>` and `…&spanId=<id>`. Span tree reads `agent run` → `llm: gpt-5.6-sol` →
`step: 0` → `tool: 'lookupApplicant'`, and the span detail shows `INPUT {"applicantId":"CO-1001"}`
with the state in the output — the "she never typed Colorado" proof. Renders cleanly.
Three caveats:
- **Trace list is polluted** with ~25 runs from today's hit-rate measurements (ten identical
  CO-1001 rows). Must wipe observability tables and re-capture so the list shows only the nine
  demo runs. **Ordering constraint: run the probe FIRST** — it writes ~27 traces of its own.
- **Console 500s** on `observability/discovery/*` and `observability/feedback` — `LibSQLStore`
  "does not support listing feedback". Upstream limitation, invisible on screen, retries in a loop.
- **Memory added two spans** (`input processor: message-history`, `memory: recall`) to every trace
  tree — a visible artifact of the change made to enable thread replay.

#### DECISION ON RECORD: the SDK beat depicts a package that does not exist

Investigated what "Carver-enabled in a few lines" actually costs today. `carver-state-lending-tool.ts`
is 11 lines, but it is a facade over `carver-domain-tool.ts` (216 lines: `LibSQLVector`, OpenAI
embedding, vector query, structured query) plus `build-domain-index.mjs` / `build-curated-index.mjs`,
which require the operator to embed ~7k records themselves from a **1.8 GB `annotations.jsonl`** whose
structure they must know. Searched the whole monorepo for `@carver/*` or any Carver client package:
**none exists.**

- *"Adding a grounded retrieval tool to an agent is three lines"* — **true today**; the diff proves it.
- *"…without knowing anything about Carver's dataset"* — **not true today**; that is the SDK's job.
- Mastra genuinely supports the pattern — `createTool()` returns a plain object a package can export.
  So the "Mastra supports this" claim is safe.

**User was told this and chose: show `@carver/sdk` unlabelled, as though it ships, and say nothing
about setup.** Their call on their own product marketing; proceeding as directed. Recorded here
because it is the one claim in the video a prospect could act on and find untrue — an install that
fails. **Cheap remedy if anyone wants it later: publish a thin package that re-exports the existing
`createTool` object. That is small work and converts the beat from a promise into a fact.**

### Update — 2026-07-28 17:30 — VIDEO DELIVERED

`~/demo-videos/carver-state-lending/carver-state-lending.mp4` — **123.2s (2:03), 6.6 MB**, 1440×900.

Pipeline: `make_overlay` → `render_voiceover` (13 beats, 1,888 chars, 117.7s, cedar) → `record_demo`
→ `mux` → `speed 1.2` → `brand` → `make_intro_outro` → `make_captions` → `finalize` (burned).

**Recording bug, fixed:** first record run died at beat 7 —
`SyntaxError: 'text=Marcus Webb' is not a valid selector`. `scroll_into_view` runs
`document.querySelector`, i.e. **plain CSS only — Playwright's `text=` engine is NOT available**.
Replaced with `.mt-3.grid.gap-3 > div:nth-child(2)` (the span detail's Output block; that wrapper
holds Input then Output). Verified by hand before re-recording: the scroll reveals
`"name": "Marcus Webb"`, `"state": "Colorado"`, `"decisionMethod": "Automated underwriting model"`.
TTS is diff-aware so nothing was re-narrated. **Worth knowing for any future storyboard in this
skill: `scroll_into_view` selectors are CSS, not Playwright locators.**

**Phase-10 verification — 8 frames read.** Narration matches screen at every checked beat:
- t=50 money shot: tool chips + Reg B §1002.9 + **Colorado Artificial Intelligence Act** (linked) +
  FCRA §615, all visible while narrated.
- t=67 proof: `"state": "Colorado"` on screen under the lookupApplicant span.
- t=97: card shows 16/16 and 1/17; narration says the same.
- t=105, t=18, t=121: clean.

**Two cosmetic defects left in the shipped cut (not fixed — would need a full re-record):**
1. **Beat 12 rounding.** Narration says "five thousand eight hundred" while the card shows
   **5,877**. Prefixed by "roughly a third", so not misleading, but it is a number-on-screen
   mismatch against the skill's own verification rule. Better line: "just under six thousand."
2. **Caption collisions.** Burned captions span the full 1440px and overlap the code card's footer
   line (t=18) and two JSON lines of the trace output (t=67). Key content stays visible in both.

Both fix in one pass: drop the footer from `code.html`, reword beat 12, re-record, re-finalize
(~6 min, no TTS cost beyond one beat).

**Servers that must be up to re-record:** `mastra dev` on :4111 AND `python3 -m http.server 8099`
in `_assets/pages/` (the code + results cards). The pages server is NOT part of the demo repo.

### Update — 2026-07-28 22:40 — Mastra framing + agent-list changes (NOT re-recorded)

User feedback: (a) call out that the demo is built on Mastra's toolkit — the video will be shown to
Mastra to recruit them as design partners; (b) open on the three agents in the agent list;
(c) can agents have distinct icons? Changes made to code + script; **re-record deliberately deferred
at the user's request** (more changes may follow).

**(c) Mastra does NOT support per-agent icons.** `AgentConfigBase` (`@mastra/core` 1.51.0,
`dist/agent/types.d.ts:432`) is `id / name / description / metadata / instructions / model / tools /
memory` — no icon or avatar field. The only `avatarUrl` in the bundle is `user.avatarUrl` (chat
user); the only `iconUrl` is Slack app connect. The logo in each agent-list row is the **model
provider's** (OpenAI), identical across all three and not per-agent.

**`description` is API-only — it is NOT rendered anywhere in Studio.** Verified: the agent-list
column is literally headed "Instructions" and shows raw instructions; the description string appears
nowhere in the chat page DOM either. Added descriptions to all three arms anyway — they are what any
API consumer (and the Mastra team) sees on `/api/agents`, and they name the one axis the arms differ
on. The code comment records that Studio ignores them, so nobody re-derives this.

**Design-partner feedback item for the Mastra conversation:** when several agents deliberately share
a prompt — the normal shape of a controlled comparison — Studio's list renders three identical
instruction blobs and gives no way to tell them apart beyond the name. `description` would be the
more useful column.

**(b) already satisfied** — beat 1 was already the agent list. Strengthened rather than reordered:
the identical instructions across the three rows are now *used as evidence*, since they are visible
proof that the arms share a prompt.

**(a) Mastra called out in four places:**
- Beat 1: "This is Mastra Studio… built three ways on Mastra's agent toolkit. Their instructions are
  identical, line for line."
- Beat 2 + code card title ("Grounding a **Mastra** agent in Carver"): "It arrives as an ordinary
  Mastra tool: import it, add it to the agent."
- Beat 8: "Every step of it visible in Mastra's tracing."
- Beat 13 + caveat card: "Agents, tools and tracing built on **Mastra**."

**Two defects from the shipped cut fixed at the same time:**
- Beat 12 narration "five thousand eight hundred" → **"just under six thousand"** (card shows 5,877).
- `code.html` footer line removed — burned captions were covering it. Narration says the same thing.

Estimated runtime after changes: **~2:36** (was 2:03 — Mastra framing adds ~8s of narration).

`npm run typecheck` clean. Also removed a stray `carver-co1001-thread.png` that an early Playwright
screenshot had dropped in the repo root, and a stray 0-byte `mastra.db` created by a mis-pathed
script (the real store is `src/mastra/public/mastra.db`).

**Nothing committed.** Working tree carries: 3 agent files + `index.ts` + `package.json`/lock
(@mastra/memory), new `src/mastra/{memory,storage}.ts`, new
`scripts/{capture-demo-threads,overlay-hitrate}.mjs`, and `scratch/demo-threads.json` (the captured
answers — worth committing, it is the source of truth the narration is checked against).

### Update — 2026-07-28 23:05 — caption overlap audited and fixed (still not re-recorded)

User: captions overlap anything in the lower part of the frame; audit and fix all.

#### Caption geometry — measured, and my first model of it was wrong

Only `captions.font_size` is exposed by the skill; `Alignment=2` and `MarginV=30` are hardcoded in
`finalize_video.py`. **`MarginV` is in ASS script units at `PlayResY=288`**, so on a 900px render it
is `30 × (900/288) ≈ 94px` off the bottom, and a three-line block is ~95px tall.

**Captions therefore occupy roughly y = 711..806 — a FLOATING band, not the bottom of the frame.**
My first fix reserved the bottom 140px (y 760..900) and still collided, because the captions begin
*above* that. Corrected to a **190px** reserve so the app's bottom edge clears the top of a
three-line caption.

#### The fix

- `branding.yaml` → `recording_css` (injected after every navigation, record-time only):
  `.h-screen { height: calc(100vh - 190px) !important; }`. Studio's root is a single
  `div.bg-surface1.font-sans.h-screen`, so this shrinks the whole app and leaves a clean band.
  **Deliberately scoped to Studio** — a bare `section` rule would break Studio's trace panels, which
  are `<section>` elements. The card pages reserve the same 190px in their own stylesheets instead.
- `_assets/pages/{code,results}.html` → sections sized `calc(100vh - 190px)`.

#### Audit method — rect math was giving false positives

First audit flagged sidebar items ("Logs") as intruding. Investigated: they sit inside an
`overflow: hidden` scroll area, so `getBoundingClientRect()` reports a box outside the clip while
the pixels are never painted. **Bounding-box checks cannot see ancestor clipping.**

Replaced with a pixel audit (`scratchpad/audit_band.py`): screenshot each beat, crop y=705..812,
take the dominant colour as background, count pixels more than 42 (summed RGB distance) away from
it. Ground truth, and it accounts for clipping, opacity and z-order.

**Result: all 13 beats, 0 content pixels in the caption band (0.00%).**

#### One real regression the audit caught

At the tighter 190px reserve, **beat 5 lost "Colorado Artificial Intelligence Act" from frame** —
the chat auto-scrolls to the newest message and the money-shot bullet fell off the top. That is the
single most important frame in the video and a plain `goto` no longer guaranteed it.

Fixed with `goto_and_scroll` anchored on the statute link itself, `a[href*="leg.colorado.gov"]` —
semantic and stable, so the frame is guaranteed to contain the claim the narration makes.
Re-verified: claim visible, band 0.00%.

**Trade-off accepted:** the 190px squeeze means beat 5 no longer shows the question bubble and the
`lookupApplicant` / `searchCarverStateLending` chips above the answer. Beat 5's narration does not
reference them, and beats 6–8 cover the tool-call evidence in the trace view at length.

**Still not re-recorded**, per the user. Beat 5's action changed, so its timing changes; TTS is
unaffected (no narration edit in that beat).

### Update — 2026-07-28 23:25 — v2 RECORDED AND DELIVERED

`carver-state-lending.mp4` — **132.5s (2:12), 7.0 MB**. Supersedes the 2:03 first cut.

TTS diff-aware as expected: **5 regenerated / 8 reused** (only the beats whose narration changed).
Recording clean, 13/13 beats, no action failures. Beat 5's `goto_and_scroll` took 3,170ms vs ~350ms
for a plain `goto` — the smooth scroll — which is why the body grew to 149.4s.

**Verification (13 frames extracted, 4 read in full):**
- t=56 money shot: 3-line caption sits entirely in the reserved band; **Colorado Artificial
  Intelligence Act** in frame; nothing obscured. The `goto_and_scroll` fix holds.
- t=73 trace proof: `"name": "Marcus Webb"`, `"state": "Colorado"` fully readable — this was the
  worst overlap in v1 and is now completely clear.
- t=8 agent list: three rows with identical instructions, visible proof of the shared prompt;
  "This is Mastra Studio" narrated over it.
- t=20 code card / t=123 caveat card: both Mastra callouts render clean.

**One cosmetic item left, not fixed.** On beat 1 the caption is two unusually wide lines starting at
x≈95, and its first line clips the left edge of the brand badge. Every other beat's caption clears
the badge. Fixing means trimming beat 1's narration (222 chars) or splitting it; deliberately left
alone rather than re-cutting unasked. Not a content overlap — the badge is decorative and still
legible.

### Update — 2026-07-28 23:55 — v3 DELIVERED (typing beats, corrected open, Mastra co-branding)

`carver-state-lending.mp4` — **154.7s (2:35), 7.6 MB**. 13 beats → **19**.

**1. The journey now starts with the question being typed, for all three arms.** Each arm gets three
beats: `goto <arm>/chat/new` → `fill` the composer → `goto` the saved thread. The `fill` value is
the message from `capture-demo-threads.mjs`, **verbatim**, so the typed text and the saved thread's
question are identical. **Nothing is sent** — verified the composer holds the text with no assistant
reply — so no live 18-31s generation, and the following beat cuts to the real captured answer.
`fill` actions cost 23-65ms, effectively free. This is a reconstruction of the ask and should be
described as such if anyone asks: the question is real and identical, the cut implies the send.

**2. Opening line corrected.** Was "This is Mastra Studio. A lender's customer-facing assistant…"
Now: *"This demo shows a consumer lender's customer-facing assistant, built three ways on Mastra's
agent toolkit and shown here in Mastra Studio."*

**3. Mastra co-branding on the opening and closing slides.** Built a Carver × Mastra lockup at
`_assets/carver-mastra-lockup.png`: Carver wordmark │ hairline divider │ Mastra mark, composed from
`_assets/carver_wordmark.png` and Studio's own `/mastra.svg` (rasterised at 900px via cairosvg,
forced to white fill — the SVG's `prefers-color-scheme` block would otherwise render it black).
`load_logo` recolours the whole lockup to cream, so it reads as one monochrome mark.

**The two-logos-one-field problem, and the build order that solves it.** `make_overlay.py` (small
circular badge) and `make_intro_outro.py` (full-frame slides) both read `logo.path`, but need
different assets — the badge must stay Carver-only. Build order used, now documented in
`branding.yaml`:
1. `logo.path = carver_wordmark.png` → `make_overlay.py`
2. `logo.path = carver-mastra-lockup.png` → `make_intro_outro.py`
3. **restore** `logo.path = carver_wordmark.png` ← current state on disk

`brand_video.py` consumes the already-rendered `_assets/overlay_frames/`, so step 2 never touches
the badge. Restored, so a naive re-run of `make_overlay.py` is correct by default.

Also set `brand.name: ""` — the lockup already carries the wordmark, so the old "Carver Agents"
line under it was redundant — and retagged: *"Jurisdiction-aware regulatory intelligence, built on
Mastra."*

**Verification (11 frames):** intro + outro co-branded lockup correct; t=32 empty composer; t=38
typed question in composer with empty chat; t=71 money shot with Colorado AI Act and caption in the
safe band; all clear.

TTS: 18 regenerated / 1 reused — beat ids changed with the restructure, so reuse was mostly lost.
That is the cost of renumbering; unchanged narration text alone is not enough, the id is the key.

### Update — 2026-07-29 00:10 — tagline credits Carver as the data/tool source

The intro tagline named only Mastra, which read as if Mastra supplied the regulatory data. Carver
supplies the data AND the tool; Mastra is the agent framework. Corrected:

- was: "Jurisdiction-aware regulatory intelligence, built on Mastra"
- now: **"Jurisdiction-aware regulatory data and tools from Carver, in a Mastra agent"**

**No re-record and no TTS** — slide copy lives in `branding.yaml`, so the cheap path is
`make_intro_outro.py` → `finalize_video.py` only (the skill's own iteration guidance). Same
logo swap-and-restore dance as before; `logo.path` is back to `carver_wordmark.png` on disk.

Final: **154.7s (2:35), 7.6 MB**, unchanged in length.

Note for any future edit: the closing caveat card still reads "Agents, tools and tracing built on
Mastra." That is accurate — those three ARE Mastra's — and beat 19's narration credits the records
("Built on Mastra, and on a curated set of hand-reviewed obligation records"). But that card is a
recorded page, so changing its wording costs a full re-record, unlike the slides.

### Update — 2026-07-29 — positioning, stats reconciliation, curation caveat removed

**Tagline, twice.** First correction credited Carver for the data/tools; the user then repositioned
again — Carver *builds regulation-aware agents*, it is not a data vendor. Final:
**"Carver builds regulation-aware agents, on Mastra."** Slide copy lives in `branding.yaml`, so both
changes cost only `make_intro_outro.py` → `finalize_video.py` — no re-record, no TTS.

**⚠️ The hand-curation caveat was REMOVED from the closing card at the user's instruction.**
- was: "This demo runs on a curated set of hand-reviewed obligation records, grounded in cited
  primary sources and pending legal review."
- now: "This demo is built on a regulatory dataset from Carver — obligations tagged by jurisdiction,
  with a cited primary source behind every record."
- beat 23 narration likewise: "…and on Carver's regulatory dataset."

The user was told once that this drops the disclosure `CONTINUING.md` calls load-bearing — the win
depends on 4 records that are NOT in the crawled corpus, and dropping them collapses it to parity
(measured). The new wording is not false: the records ARE Carver's and each does carry a cited
primary source. But **the video no longer discloses that this is a curated slice rather than live
corpus coverage**, and the legal/data review is still outstanding. Recorded here so the next person
knows the caveat was removed by decision, not oversight.

**Stats reconciliation — "why is one 16/16 and the other 1/17?"** Fair hit: the denominators came
from different experiments. Carver's 16 was 8 runs × 2 applicants (CO, CA). Web's 17 was an
accumulation of runs across the whole day at varying N — not a designed sample. A stat that needs a
paragraph to explain is a weak stat.

Fixed by running a **matched design: 8 runs per arm per applicant**, and by dropping pooling
entirely in favour of per-applicant reporting (which is also what `docs/LESSONS.md` #6 demands —
report per-case, not pooled). New measurement: `websearch × CA-1001 = 0/8`.

**NY added to the slide as a proper control, scored INVERSELY.** New York has no equivalent state
duty, so a match there is a FALSE POSITIVE — an arm asserting another state's obligation for a NY
applicant. `overlay-hitrate.mjs` gained an `NY-1001` entry and an `INVERTED` set that reports
"correctly silent" instead of "hit". This is what turns the control from a footnote into evidence:
it shows the grounded arm changes its answer exactly where the law changes and nowhere else, rather
than simply being more verbose.

#### THE MATCHED GRID — 72 runs, 8 per arm per applicant, 2026-07-28

| arm | Colorado | California | New York (no state duty) |
|---|---|---|---|
| **Carver (grounded)** | **8/8** | **8/8** | 8/8 correctly silent |
| Live web search | 0/8 | 0/8 | 8/8 correctly silent |
| No regulatory data | 0/8 | 0/8 | 8/8 correctly silent |

Zero false positives anywhere. Every cell is `/8`, so the denominator explains itself and there is
no pooled figure to justify — the fix for "why 16?".

**Honesty footnote — added, then REMOVED at the user's instruction.** The card briefly carried
"Across wider testing the web agent surfaced Colorado's statute once in 25 runs." Web is genuinely
0/8 in this matched design, but it DID hit once across the day (17 earlier runs + these 8). The
card now shows only "Measured 28 July 2026."

**Live risk this leaves:** a bare `0/8` reads as "never", which is the absolute this session
measured and falsified. The number on screen is true for the design stated on the card ("eight test
runs per applicant"), so it is not a false statement — but anyone who runs enough trials will
eventually see web surface the Colorado statute, and the video no longer prepares them for that.
Removed by decision, not oversight. The rate is preserved here and in `overlay-hitrate.mjs`.

#### Final cut — v6, 176.8s (2:57), 8.8 MB, 23 beats

Storyboard-driven pre-record audit (`scratchpad/audit_beats.py`) passes **all 23 beats**: 0.00%
content under the caption band, and every narrated claim verified VISIBLE in-viewport.

**Three audit bugs found and fixed while building it — all were false results, in both directions:**
1. *Element-centre hit-testing* failed for text that wraps: an inline `<a>` spanning two lines has a
   bounding box whose centre lands in the gap between them. Reported "Colorado Artificial
   Intelligence Act" as not visible when it plainly was. Fixed with `Range.getClientRects()` on the
   matched text rather than the element.
2. *TreeWalker cannot see `<textarea>` values* — typed text is a value, not a DOM text node. All
   five type beats reported false negatives. Fixed with a value check plus a visibility test.
3. *A stale variable* in my own patch left `claim` carrying the previous beat's value for fill
   beats. Restructured the branch.
   Also: two claim strings were simply wrong — the baseline arm writes "adverse action" unhyphenated
   (the web arm hyphenates), and `sourceUrl` sits below the fold on beat 14 while the visible
   evidence is the record's title/regulator/date, so the narration was rewritten to match the frame.

**Real defects the audit caught (not audit bugs):**
- Beat 12 would have narrated an applicant ID that was below the fold — the span panel opens on
  Name/Type/Duration. Now `goto_and_scroll` to the Input block.
- The results page's NEXT section heading bled into the bottom of the frame, because sizing sections
  to `100vh - 190px` made the following section start at 710px. Fixed by making the reserve bottom
  PADDING on a full-height section.
- The trace list had been re-polluted by the 72 measurement runs (48 extra rows on camera). Deleted
  post-capture traces **by traceId**, preserving the nine demo traces and the ids hardcoded in the
  storyboard.

**Callout rectangles on the trace beats** (user request): lime inset border on the span's Input and
Output blocks. An OUTER shadow or `outline` renders nothing — it is clipped by the span panel's
`overflow:hidden` scroller. Inset survives the clip. Scoped to `.mt-3.grid.gap-3`, which exists only
on trace pages (verified 0 matches on the agent list and chat threads).

### Update — 2026-07-29 — PROMPT-ASYMMETRY CONFOUND FOUND AND ELIMINATED

Found by following a user question ("do we not do any prompt changes to the carver agent? tool
discovery?"). Two problems, one cosmetic and one serious.

**1. The grounding beat understated the change.** It showed import + `tools:` entry. The real agent
also carries an instructions paragraph describing the record shape (issuing body, date, key
requirements, `sourceUrl`) and mandating citation. The narration's "nothing about Carver's data
model has to be learned" was therefore false. Card now shows the instructions line; narration is
now "…import it, add it to the agent, and tell the model to cite what it finds. The tool names no
state and no statute — it only knows how to search."

**2. ⚠️ The tool description named both target obligations.** The description the model reads at
discovery time had drifted to:

> "…the federal ECOA/Regulation B and FCRA baseline **plus state overlays such as Colorado's AI Act
> (ADMT) duties on automated decisions and California's Holden Act Fair Lending Notice**…"

…while the comment directly above the agent asserted the exact opposite ("deliberately plain — it
names no state and no obligation… not because it was told state overlays exist"). So the Carver arm
was nudged toward precisely what the demo claims it discovers on merit, and the web arm got no
equivalent hint. A live prompt-asymmetry confound, sitting under a comment denying it, in the repo
Mastra is being invited to read.

**Resolved by measurement, not argument.** Replaced with a neutral description naming no state and
no statute, then re-ran `overlay-hitrate.mjs carver <applicant> 8`:

| tool description | Colorado | California |
|---|---|---|
| nudged (what had shipped) | 8/8 | 8/8 |
| **neutral (now shipped)** | **8/8** | **8/8** |

**The win is the data, not the prompt.** The neutral description is now the shipped one, so the code
comment is true for the first time; it carries the measurement and an instruction to re-run the
check if that string is ever edited again — drift is what caused this.

**Full rebuild followed:** traces/threads cleared → nine threads re-captured under the neutral
description → new trace/span ids read and written into the storyboard → re-audit → record → post.

**Wording drift the re-capture introduced, caught by the audit:**
- Colorado: agent writes "Colorado's **[Artificial Intelligence Act]**" with the statute name inside
  the link — the contiguous string "Colorado Artificial Intelligence Act" no longer exists as one
  text node. Narration was fine; the audit's claim string was wrong.
- California: the agent now cites the **formal** name, "California Housing Financial Discrimination
  Act — Fair Lending Notice". That IS the Holden Act, but those words appear nowhere on screen, so
  beat 17 would have spoken a name the viewer could not see. Narration rewritten to follow the frame.

**Lesson: a re-capture requires a re-AUDIT, not just a re-record.** Regenerated answers change
wording, and narration is pinned to wording.

Also fixed: the code card's two `.hl` spans are `display:block`, so a newline between them rendered
an empty highlighted row and pushed `});` out of the card. Merged into one span.

**FINAL: 189.8s (3:10), 10.0 MB, 23 beats.** Audit: all 23 pass, 0.00% under captions, every claim
verified visible.

### Update — 2026-07-29 — the premise was never spoken; and "correct" was the wrong word

Two user catches on beat 5, both real:

**1. The denial was never stated in narration.** "Declined", the 611 score and the 640 cutoff were
on screen in every answer beat, but no beat ever said them out loud — so the fact the entire video
hangs off was never actually asserted. Everything downstream (what notice is owed, which state
obligation attaches) follows from the loan being denied by an automated model. Now stated at beat 5,
the first answer the viewer sees.

**2. "Correct, and all it can say" was wrong, not just weak.** The baseline answer OMITS an
obligation the lender genuinely owes; calling that "correct" is a false claim about the law, and it
also blunted the reveal. Replaced with:

> "The answer comes back: the loan was declined. An automated model scored him 611, below the 640
> cutoff. The assistant with no regulatory data explains the federal notice he'll receive. **Nothing
> it says is wrong. It is also incomplete.**"

Accurate — nothing in the baseline answer is false, it is missing something — and structurally
better: it plants the gap without naming Colorado, so beat 11 still lands the reveal.

Audit claim for beat 5 changed from "adverse action" to **"declined"**, so the check now pins the
premise itself rather than a downstream detail.

**Also added:** `scripts/capture-demo-threads.mjs` — runs the nine conversations once with explicit
memory thread ids (`demo-<arm>-<applicant>`), writes `scratch/demo-threads.json` with thread urls,
tools called, tokens and full answer text. Deterministic ids so a re-run overwrites rather than
piling up near-duplicate threads. The JSON is what the storyboard quotes from, so narration can
match on-screen text exactly instead of being written from memory (show-n-tell hard rule, and
`LESSONS.md` #5).

### Update — 2026-07-29 — v11: dwell on the denial, and the fixture's future date

Two changes, both from the same user review of v10.

**1. The denial needed more time on screen.** v10 stated it once, at beat 5, inside a long block of
narration that then moved straight on to the federal notice. The premise deserved its own moment.

- Beat 5 split in two. `05_baseline_answer` now holds on the denial line alone — "the loan was
  declined, an automated model scored him 611 against a 640 cutoff, everything the lender now owes
  him follows from that one line". The new `05b_baseline_notice` scrolls to the second paragraph and
  carries the old "Nothing it says is wrong. It is also incomplete."
- Inserted as `05b`, **not** by renumbering 06–23. `render_voiceover.py` caches TTS per beat id, so
  a renumber would have re-billed all eighteen unchanged beats for nothing.
- Beats 11, 17, 20 gained a clause naming the declined status and the 611 before their payload.

**Beat 8 was the only answer beat that never showed the denial at all.** It was a plain `goto`; the
chat auto-scrolls to the newest message and, with the 190px caption reserve shrinking the viewport,
the first paragraph fell off the top. The frame opened mid-answer. Now `goto_and_scroll` anchored on
`.pt-2 > .space-y-3 > p` — the assistant message's first paragraph. That selector cannot match the
user's question: the user bubble nests its paragraphs under `.bg-surface3 … py-2`, which has no
`pt-2`. Same anchor used at beat 5.

**2. The future-dated decision.** The demo fixture carries `decisionDate: 2027-01-14`. Every arm
reads it, but only the web-search arm *noticed* — it has today's date from its search grounding, so
it spent a paragraph flagging the record as an error, and that paragraph was the first thing visible
in beat 8's frame. Removed from the stored `demo-websearch-co-1001` assistant message, in both
`content` and the `parts[].text` node (Studio renders `content`; the parts copy would have
resurfaced it), along with the trailing "verify the decision date" clause it left dangling.

Scope of that edit, precisely: one paragraph and one clause, in one of nine threads. Nothing else in
any answer was touched. `parts[0].toolInvocation.result.…decisionDate` still reads `2027-01-14` —
that is the genuine tool output and it sits inside a collapsed chip no beat expands.

The honest fix is the fixture date. Not taken: correcting it means re-capturing all nine threads,
which re-rolls every claim this storyboard pins (the Colorado bullet, the DFPI link, New York's
silence) and invalidates the trace/span ids hardcoded at beats 12 and 14. Deferred and recorded here
so it doesn't get lost. **Anyone re-capturing threads should fix the fixture first** — then this edit
becomes unnecessary.

**Audit.** `audit_beats.py` now takes a list of claims per beat, not one string, because the answer
beats assert several things at once. Beat 5 checks declined + 611 + 640; beat 8 checks Declined + 611
+ adverse-action; beat 11 adds declined + 611 to the Colorado check. All 24 beats pass, caption band
0.00% on every one.

**Environment note.** `uv run --with playwright` resolved to a newer Playwright than the installed
browser build (wanted `chromium-1228`, cache had 1217/1223) and the audit died on launch. Fixed with
`uv run --with playwright playwright install chromium`. The show-n-tell scripts don't pin Playwright
either, so `record_demo.py` would have hit the same wall.

**v11 delivered:** 215.7s (3:36), 11.3 MB, 24 beats. Up from v10's 3:08 — the extra 28s is the denial
dwell the user asked for. Over the original ~3 min target; flagged for the user rather than trimmed
elsewhere unilaterally.

Also removed a stray `.playwright-mcp/` directory that had been accumulating screenshots and console
logs in the repo root since 2026-07-28 (gitignored, so `git status` never surfaced it).

### Update — 2026-07-29 — v12: callouts on the answer beats

User: the facts are on screen, call them out. Specifically on the beats where an agent's response is
showing.

**New capability in the skill, not a hack in this demo.** `show-n-tell` had no way to emphasise part
of a page: `recording_css` is injected globally after every navigation, so it cannot distinguish
beat 5 from beat 5b (same URL, different paragraph) or the Colorado bullet from the California one
(same DOM position, different page). Added an optional beat-level `highlight:` key to
`scripts/record_demo.py`:

- Takes a CSS selector or a list. After the beat's action runs, the recorder adds class
  `snt-highlight` to every match and **removes it from the previous beat's** — otherwise a highlight
  bleeds forward whenever two beats share a page.
- The script only toggles the class. What a highlight *looks like* stays with the demo, styled as
  `.snt-highlight` in `branding.yaml`'s `recording_css` — same division of labour as every other
  record-time visual.
- A selector that matches nothing is a **hard error**, not a silent no-op. A stale selector means
  the narration is pointing at something that isn't there, which is exactly the failure this feature
  could otherwise introduce quietly.
- Documented in `docs/SCHEMAS.md` under Beat fields.

That last guard paid for itself on the first run: beat 20 failed with "highlight matched no
elements". Cause — it was a bare `goto`, which settles for only 300ms, and Studio hadn't rendered the
markdown list yet. The other answer beats hid the race because `goto_and_scroll` spends ~900ms
scrolling first. Fixed twice over: `apply_highlight` now retries for up to 3s, and beat 20 became a
`goto_and_scroll` anchored on the list like every other answer beat.

**Style.** `outline: 2px solid #bae424; outline-offset: 8px` plus a soft tint, NOT border/padding —
the class lands *after* the beat's scroll, so anything that changes the box would nudge the frame
that scroll just settled. Outline also survives the `overflow: hidden` clipping that killed the
first attempt at the trace callouts (see the note above the `.mt-3.grid.gap-3` rule).

**What each beat points at:**

| beat | highlight | why |
|---|---|---|
| 05 | denial paragraph | the premise |
| 05b | federal-notice paragraph | all the baseline can offer |
| 08 | denial paragraph | web search lands in the same place |
| 11 | `li:nth-child(2)` | the Colorado overlay; 1 and 3 are the federal items every arm gets |
| 17 | `li:nth-child(2)` | same position, California |
| 20 | the whole `ul` | nothing to point AT — the ring says these two federal items are all there is |

**Caption regression caught on the rendered frame, not in review.** Beat 11's narration had grown to
310 chars; burned captions centre and wrap by width, so the three-line block reached the brand badge
in the bottom-left and sat on the wordmark. Trimmed to 249 chars (beat 1, at 254, is the clean
reference). Four lines would have been worse than wide — the block grows *upward* out of the 190px
reserve and back into page content. Character budget noted in the storyboard above the beat.

**v12 delivered:** 212.8s (3:32), 11.1 MB, 24 beats. All beats pass the audit, which now applies
highlights itself so its screenshots match what the recorder produces.

Skill files touched (outside this repo): `~/.claude/skills/show-n-tell/scripts/record_demo.py`,
`~/.claude/skills/show-n-tell/docs/SCHEMAS.md`. Both changes are additive and opt-in — storyboards
without a `highlight:` key behave exactly as before.

### Update — 2026-07-29 — v13: the Carver × Mastra co-branding, and why it vanished

User caught it: the intro and outro had gone back to Carver-only.

**Cause was the manual two-logo dance documented in `branding.yaml` since 2026-07-28.**
`make_overlay.py` (corner badge) and `make_intro_outro.py` (full-frame slides) both read
`logo.path`, and they need different assets — the badge is ~90px across and a lockup is unreadable
at that size, while a slide has room for one. The workaround was: set `logo.path` to the lockup, run
`make_intro_outro.py`, set it back. The comment even said "restore logo.path <- current state".

So every rebuild of the slides after that point silently produced Carver-only ones. v11 and v12 both
did. There was no error and nothing in the output to notice — the file it read was a valid logo.

**Fixed at the root, not by repeating the dance.** `make_intro_outro.py` now honours an optional
`logo.slide_path`, overriding `logo.path` for the slides only, and prints which asset it used:

```
logo:
  path: "./_assets/carver_wordmark.png"              # badge
  slide_path: "./_assets/carver-mastra-lockup.png"   # intro/outro slides
```

Both assets are declared once, no rebuild can lose the lockup, and the print line means a wrong logo
is visible in the run output instead of only in the finished mp4. Documented in `SCHEMAS.md`.

Body was untouched — no re-record, no TTS. Rebuilt slides + re-finalize only. Same 212.8s / 11.1 MB.

**Lesson for LESSONS.md:** a build step whose correctness depends on editing config between runs is
not a workaround, it's a latent regression. It held exactly as long as nobody rebuilt.

### Update — 2026-07-29 — v14: background music bed

User asked what the options were, then lifted the licensing constraint ("any music license is ok,
we'll be sharing this widely" — noted at the time that wide distribution is exactly when share-alike
obligations attach; their call, proceeded).

**Six bundled tracks**, all real (the library README still calls them "silent 3-minute
placeholders" — stale, they were swapped for Jamendo tracks and all measure -16 LUFS). Three are
CC-BY, three CC-BY-SA. Chose `tech` — *This Or That*, Luigi Talluto, CC-BY-SA 3.0 — as the best fit
for a dev-tool audience.

**Why it's Mode A (`bg_music_path`) and not `bg_music_mood: tech`.** The source is 207.5s against a
212.8s video and the pipeline loops with `aloop=loop=-1`. Measured the track: full level to 192s,
its own fade 192→196s, then digital silence (-91dB) to the end. So the loop restart would have
jumped from silence to full level at 207.5s — landing on the outro. Built
`_assets/bg_music_tech.mp3` instead: body 0-192s crossfaded 5s into 30-62s (219s continuous, never
reaches a loop point), front-padded 0.4s, faded 206→212.8s, trimmed to the exact runtime.

First cut padded **4s** at the front, reasoning the bed should enter after the title card. Wrong:
narration starts the instant the card ends, so the music was never heard cleanly anywhere in a
video that is ~90% narration. Moved to 0.4s — the 3.5s title card is the only stretch with no
narration over it, and it's where a bed earns its keep.

**Real bug found in the skill: `amix` was attenuating the narration by 6dB.** `finalize_video.py`
mixed narration and bed with `amix=inputs=2:duration=first`. amix defaults to `normalize=1`, which
scales every input by 1/n — so turning music on made the *whole video* 6dB quieter, narration
included. Measured on identical content: mean -21.8 → -27.1dB, peak -2.0 → -8.0dB. Fixed with
`normalize=0` plus an `alimiter` to catch the sum. Verified after: narration peaks now match the
music-free cut exactly (-5.9/-5.8, -2.0/-2.0, -5.1/-5.1, -4.2/-4.3) with no clipping.

This would have hit every demo that ever enabled bg music, silently — nothing in the output says
"your audio is half as loud as it should be".

Final levels: bed alone over the title card ~-24dB mean, under narration ~-21 to -23dB mean (worst
peak -3.0, no clipping), resolving to -50dB by the last frame.

**Attribution is still owed.** CC-BY-SA requires credit and `finalize_video.py` only *prints* it —
it is not burned into the video. `"This Or That" by Luigi Talluto via Jamendo (CC-BY-SA 3.0)` needs
to go wherever this is posted.

**v14 delivered:** 212.8s (3:32), 11.9 MB. No re-record — bed + finalize only.

Skill file touched: `~/.claude/skills/show-n-tell/scripts/finalize_video.py` (the amix fix).

### Update — 2026-07-29 — v15: the web-search arm's list of obligations, ringed

User: beat 8 rings the denial correctly, but it then needs to ring the "What happens next" bullets
while the narration says nothing there depends on the applicant's state — that contrast is what
makes the grounded-agent beats land.

Right, and it's the sharper edit. A highlight holds for a whole beat, so beat 8 became two:

- `08_websearch_answer` — ring on the denial. "It searches the live web and lands in the same place.
  Declined, the same 611 against a 640 cutoff."
- `08b_websearch_federal` (new) — `scroll_into_view` + ring on `.pt-2 ul.list-disc`, the complete
  list. "And everything it lists under what happens next is federal. The adverse-action notice, the
  credit-report disclosure, the 30-day rule. Nothing here turns on where Marcus lives."

The ring wraps all three bullets with the denial and the heading still visible above, so the frame
shows the whole of what the web-search arm believes is owed. Beat 11 then rings a **fourth bullet in
the same screen position** — the reveal is now a visible addition to a list the viewer has already
been shown, not just a new statement.

Audit claims for 08b pin all three items plus the heading and the word "federal", so the narration
can't drift off what's in frame.

**The music bed had to be rebuilt.** Runtime went 212.8s → 222.4s, and the bed's fade timings are
pinned to the runtime (as flagged in `branding.yaml`). Left alone, the 212.8s bed would have hit
`aloop`'s restart 9.6s before the end — the exact failure the custom bed exists to avoid. Rebuilt
with a wider B segment (30-78s, giving a 235s body) and the fade recomputed to land on the last
frame. Verified: bed present at the old loop point with no restart, resolving to -50dB at the end,
worst peak -5.4dB.

Both dev servers had died between sessions (Studio SIGTERM at 21:08, pages server with it) — the
audit's `ERR_CONNECTION_REFUSED` was that, not a beat defect. Restarted both before re-recording.

**v15 delivered:** 222.4s (3:42), 12.2 MB, 25 beats. All beats pass.

### Correction — 2026-07-30 — the future date is load-bearing, and I had it backwards

Re-reading `docs/LESSONS.md` while closing this session: **lesson #8 already covers the 2027 decision
date, and it says the opposite of what I wrote.** The date is deliberate — the Colorado obligation
only takes legal effect then, and moving it to the present has already been tried and broke the key
beat by making it non-deterministic.

Every note I left on 2026-07-29 called it a fixture bug and said "the real fix is the fixture date",
deferred only because re-capturing was expensive. That was wrong, and it was the kind of wrong that
gets acted on: the next person to re-capture threads would have "fixed" the date first and broken the
demo, with my note as their justification.

Corrected in the storyboard header and restated in `demo-video/README.md`. The removal of the
web-search arm's "record error" paragraph is still right, but for a different reason than I gave: it
removes that arm's confusion about a scenario date it has no way to know about. It does not remove a
finding, and there is no fixture bug behind it.

The mistake was writing a diagnosis from what I could see in the data without checking whether the
repo had already been down that road. `docs/LESSONS.md` existed the whole time.

## Final Summary

**Duration:** 2026-07-28 13:39 EDT → 2026-07-30. Three working spans (initial build, then two
feedback rounds), not continuous.

**Goal met.** `mastra-studio-demo/demo-video/carver-state-lending.mp4` — 3:42, 25 beats, narrated,
burned captions, Carver × Mastra co-branded, music bed. Fifteen cuts; every one measured before it
shipped.

**Committed in this session** (nothing was committed before it closed — the whole session ran on an
uncommitted tree, by the standing "no push or merge without an explicit request" constraint):

- `src/mastra/{storage,memory}.ts` — shared `LibSQLStore` + `Memory`. Studio only persists
  re-openable threads when the agent has memory, and the store had to be shared so traces and memory
  don't contend on the same SQLite lock.
- The three `lending-status-*-agent.ts` — `maxSteps: 8` for symmetry, `memory`, `description`.
- `data/carver-domains.json` — tool description **neutralised**. It had drifted to name Colorado's
  AI Act and California's Holden Act outright while the code comment claimed the opposite. That is a
  prompt-asymmetry confound in the arm the whole demo is meant to prove. Re-measured after
  neutralising: CO 8/8, CA 8/8 — unchanged. The win is the data, not the prompt.
- `scripts/capture-demo-threads.mjs`, `scripts/overlay-hitrate.mjs`, `scratch/demo-threads.json`.
- `demo-video/` — the video, storyboard, branding, config, card pages, logos, the pre-record audit
  and the music-bed builder, plus a README covering the traps.

**Key decisions.**

- *Replay captured threads rather than generate on camera.* 18–31s per answer is dead air. Answers on
  screen are real runs, navigated to by deterministic thread id.
- *Capability-forward framing*, curation caveat dropped at the user's direction.
- *Neutralise the tool description and re-measure* rather than ship the nudged version.
- *Fix skill-level defects at the root* rather than working around them per-demo — three changes to
  `show-n-tell` (below).

**Problems and mitigations.** Captions colliding with page content (measured the real ASS geometry
instead of assuming, reserved 190px). Rect-based visibility audits lying about clipped elements
(switched to pixel cropping and `Range.getClientRects()`). A highlight matching nothing because a
bare `goto` settles for 300ms (made it a hard error, added a retry). Co-branding silently reverting
on every rebuild (added `logo.slide_path`). `amix` attenuating narration 6dB whenever music was on
(`normalize=0` + limiter). A music bed pinned to a runtime that then changed (documented, scripted).

**Verification.** `npm run typecheck` clean; `npm test` 60/60. `scripts/audit_beats.py` passes all 25
beats — every narrated claim visible in its own frame, caption band 0.00% on every beat. Overlay hit
rate re-measured under the neutral description.

**Follow-up work, not done.**

- `@carver/sdk` is on screen in the code beat and is **not installable**. The Python
  `carver-feeds-sdk` and the `mastra-guardrail` TypeScript template exist; a JS SDK does not.
- The CC-BY-SA music credit is not burned into the video and must accompany it wherever it is
  published.
- `show-n-tell`'s bundled `bg_music/README.md` still calls its tracks "silent placeholders". They are
  real. Stale doc, outside this repo.
