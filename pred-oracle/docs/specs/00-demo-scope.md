# Demo Scope

> **What this is:** the spec for the **Pred-Oracle demo** — a static site that walks a prospect through the three V1 use cases using real Carver-annotated regulatory data and a small amount of hand-curated platform context.
>
> **What this is not:** the production product. Production specs are in [`future/`](future/) and explicitly deferred.

---

## 1. Goal & Audience

**Goal.** Produce a polished, narrated, browser-deployable walkthrough that convinces a prediction-market-platform decision maker (GC, CCO, Head of Listing, or Head of International) that Pred-Oracle would solve a concrete pain they have *today*, using *real* signals their current tooling didn't surface.

**Primary audience for the demo (the people who view it):**

| Persona | They need to see |
|---|---|
| **GC / CCO** at a CFTC-licensed DCM | A regulatory event affecting *their* business that landed in α before anyone forwarded it via Slack. |
| **Head of Listing / Trading Risk** | A concrete listed contract (e.g., TIKTOKBAN, Solana ETF) with its real regulatory exposure surfaced ahead of news. |
| **Head of International / Corp Dev** | A multi-month signal cascade in a jurisdiction (e.g., France ANJ pre-ban) that would have been visible 12+ months early on β's heat-map. |

**Operator audience (the people running the demo):**

- Carver leadership (giving the demo).
- A handful of Pred-Oracle / Carver staff who may step a prospect through it remotely.

---

## 2. Narrative Arc (15-minute walkthrough)

The site is structured as a guided tour. A landing page sets the scene; navigation is forward-only by default with clear "next" CTAs. Each scene is a self-contained mini-narrative.

```
Landing  →  Scene 1 (α)         →  Scene 2 (γ)            →  Scene 3 (β)        →  Close
                                                                                 (CTA)
~1 min      ~4-5 min                ~4-5 min                  ~4-5 min            ~1 min
```

### 2.1 Landing (~1 min)

One page. Headline: *"Your business sits at the intersection of CFTC, 50 state gambling commissions, the SEC, and every foreign regulator that touches event contracts. Here's the regulatory intelligence built for that intersection."*

Three tiles below, one per scene, with a one-line preview of what they'll see. Each tile is a "Start scene N" CTA.

### 2.2 Scene 1 — α (the GC's Monday morning)

**Frame:** "It's 9:00 AM on Monday. You're the GC at [Kalshi-class platform]. Open Pred-Oracle."

Pages: inbox → ticket detail → jurisdictional dashboard → audit-export preview.

**Wow moment:** the inbox shows a *real* recent enforcement signal (e.g., a real Nevada Gaming Control Board action against Kalshi, or a fresh CFTC advisory) that the prospect probably either hasn't seen or saw a week late — sourced from real Carver annotations, scored, and triaged.

### 2.3 Scene 2 — γ (the Listing Team's pre-flight check)

**Frame:** "You're considering listing a new contract: *Will TikTok be banned by 2026-12-31?* Should you?"

Pages: pre-listing scan → contract-watch dashboard → contract detail (Solana ETF historic case).

**Wow moment:** the Solana ETF contract detail shows, on a timeline, the actual SEC/CFTC events that moved Polymarket pricing 45% → 85% — overlaid with the Carver-annotated signals that *preceded* the news cycle by days.

### 2.4 Scene 3 — β (the International team's Q3 planning)

**Frame:** "You're the Head of International at [Polymarket-class platform]. Q3 planning is next week. Open Pred-Oracle's expansion view."

Pages: world heat-map → cascade signals → quarterly intelligence report (mock).

**Wow moment:** the France case study. Heat-map shows the multi-month cadence of ANJ signals escalating before the Dec 2025 ban; cascade-signal page projects similar escalation patterns currently happening in 2-3 other named jurisdictions; the auto-drafted "watch list" in the quarterly report calls them out.

### 2.5 Close (~1 min)

One page. Recap of the three scenes. A line on what's *under the hood*: "Every signal you just saw came from Carver's regulatory-annotation pipeline. Your production deployment would pull live; this demo is a snapshot." CTA: contact form / calendar link / "request live data feed."

---

## 3. Success Criteria

Demo is "done" when **all** apply:

- [ ] Carver leadership can drive the 15-min end-to-end walkthrough without code, terminal, or live-system dependencies — just a browser.
- [ ] Every page renders real Carver-annotated data (no Lorem Ipsum, no obvious placeholder values). Synthetic platform context (entity catalogs, listed contracts) is sourced from public information about Kalshi / Polymarket / their executives.
- [ ] Each scene has at least one "wow moment" rooted in a *real* event the prospect can verify against public news.
- [ ] Build is reproducible from a clean checkout in <5 minutes: one command produces the deployable `site/` directory.
- [ ] Deployable to a publicly-reachable URL (e.g., GitHub Pages, Netlify, Vercel free tier). Optional shared-link gating is fine; OIDC SSO and tenancy are not in scope.
- [ ] Mobile-readable (responsive layout). Doesn't need to be touch-optimized; needs to look professional on a tablet.
- [ ] The "view source" experience is intentional — anyone curious about how the demo works should be able to inspect a clean `site/` folder of HTML + a few JSON files + Tailwind/ECharts CDN scripts.
- [ ] No real platform-internal data: every "Kalshi entity catalog" entry is sourced from public listings, press, or LinkedIn; every listed contract is one that publicly trades.

---

## 4. Out of Scope (Explicit)

These appear in [`future/`](future/) but are **not** part of the demo:

- Multi-tenancy, RLS, tenant catalogs, RBAC.
- Authentication (OIDC, local accounts, sessions).
- Live Carver ingestion (HTTP push, HMAC, idempotency). The demo is built from a one-time offline pull.
- Live Kalshi / Polymarket API integration. Listed contracts are hand-picked from public listings; no polling.
- Slack / email / SMS / outbound webhook integrations. Mocked visually only — "this is what would alert" with a screenshot of a Slack message.
- ARQ / Redis / background workers. Build is a one-shot script.
- PostgreSQL. Data lives as JSON files in the repo.
- WeasyPrint PDF generation. The "downloadable quarterly report" is a single hand-built PDF artifact (or rendered HTML if PDF is too much work).
- Comments, mentions, ticket lifecycle transitions. Pages show *snapshots* of state, not interactive workflows.
- Search, filtering, pagination beyond what's needed to make the page feel real (a few filter chips that scroll the visible list).
- Real-time anything.

If a prospect asks about any of the above during the demo: *"Production deployment handles that; this is the static walkthrough."* Then point at the relevant `future/` doc for details.

---

## 5. Staging

The build is staged so each scene can ship independently. Each stage is a working demo on its own; later stages add scenes.

| Stage | What ships | Done when |
|---|---|---|
| **0 — Data + scaffolding** | Carver pull complete; site shell, navigation, landing page deployed. | One-time Carver pull script run; landing page on the public URL with all three "Start scene" tiles linking to "coming soon" placeholders.<br><br>✅ Local 2026-05-19 — build time 0.5s; tests 36/36; lint clean; site builds with real Carver data (618 events, 63 jurisdictions). GH Pages deploy pending push to main (requires user authorization). |
| **1 — α scene** | α inbox + ticket detail + jurisdictional dashboard + audit-export preview. | Scene 1 plays end-to-end; placeholder tiles for 2 & 3 still present. Demoable as a "GC inbox" tour on its own. |
| **2 — γ scene** | Pre-listing scan + contract-watch dashboard + contract detail (Solana ETF). | Scene 2 plays end-to-end; γ tile no longer placeholder. |
| **3 — β scene** | Heat-map + cascade signals + quarterly report. | Scene 3 plays end-to-end. Full 15-min demo intact. |
| **4 — Polish** | Mobile responsive review, copy edit, design pass, replace any pasted-in or low-fidelity artwork. | Carver leadership signs off after a real internal dry-run. |

Each stage is a separable git branch / PR. The user-visible URL updates with each merge.

---

## 6. Constraints Recap

Sourced from project decisions (2026-05-19):

1. **Demo, not full product.** No SaaS infrastructure.
2. **No realtime platform-API integration.** At most a one-time pull of *free / public / API-accessible* Kalshi / Polymarket data; otherwise hand-curate from public listings.
3. **Real Carver data, mapped to real prediction-market platform problems.** Synthetic platform context is allowed in *limited, sensible* quantities (entity catalogs, jurisdictional footprints, ~5-10 listed contracts per platform).
4. **Output: static web pages.** No backend services, no databases, no auth.
5. **Walkthrough format.** Forward-leaning narrative, not a feature catalog.

---

## 7. Open Questions (demo-local)

| # | Question | Suggested resolution |
|---|---|---|
| D1 | What's the actual format Carver outputs annotations in, and is there a programmatic way to pull a filtered slice from this repo's worktree? | **RESOLVED 2026-05-19.** Use the `carver-feeds-sdk` Python package (https://github.com/carveragents/carver-feeds-sdk, PyPI `carver-feeds-sdk`). Authenticated via `CARVER_API_KEY`. Whether annotated Appendix-A fields are surfaced through the SDK is verified at Stage 0; if not, a Claude-annotation sub-step runs over raw entries. See [`10-data-prep.md`](10-data-prep.md) § 1.1. |
| D2 | Are Kalshi's and Polymarket's public APIs accessible without auth, and do their terms allow caching market metadata for demo use? | **RESOLVED 2026-05-19.** Both expose free, no-auth public read APIs. Kalshi: `https://external-api.kalshi.com/trade-api/v2/markets` and `/prices-history`. Polymarket: `https://gamma-api.polymarket.com/markets` and `https://clob.polymarket.com`. One-time API pull at build time; ~50 candidates per platform; hand-pick 5-10 each. See [`10-data-prep.md`](10-data-prep.md) § 1.2. |
| D3 | Where does the demo deploy? | **RESOLVED 2026-05-19.** GitHub Pages, public. Workflow sketch in [`20-site-build.md`](20-site-build.md) § 6.1. |
| D4 | Will the demo show *Kalshi* and *Polymarket* by name, or genericize as "your platform"? | Both. Use real names in the data fixtures (e.g., "Kalshi entity catalog") so the wow moments hit, but the narrative copy uses "your platform" / "you" framing so any prediction-market prospect imagines themselves. |
| D5 | What's the privacy / legal posture on showing real regulatory events about named individuals (e.g., Kalshi staff names in entity catalog)? | Use only names already public in news coverage, SEC filings, LinkedIn, or company "About" pages. Keep an internal source-log of every name used. |
| D6 | Should the demo include narration audio / voice-over? | Out of scope for the static-site spec. If desired, layer with the `show-n-tell` skill on top of the deployed site in a separate pass. |
