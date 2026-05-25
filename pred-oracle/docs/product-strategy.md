# Pred-Oracle: Product Strategy

**Status:** Strategy doc (pre-spec).
**Audience:** Carver leadership (for buy-in) and Carver product / engineering (to begin implementation specs).
**Created:** 2026-05-19.
**Owner:** TBD.

---

## How to read this doc

If you're here to decide whether to fund the build, read § 1 (Executive Summary), § 2 (Market Context), § 8 (Pricing & GTM), and § 9 (Risks & Assumptions). About 10 minutes.

If you're here to begin product spec or engineering scoping, read § 3 (The Carver Advantage), § 4 (Product Strategy — Five Modules), § 5 (Shared Data Spine), and § 6 (V1 Scope). About 25 minutes.

Appendices A–C are reference material: Carver data model field schema, specific platform contracts that validate the use cases, and research sources.

---

## 1. Executive Summary

**Pred-Oracle is a vertical compliance-intelligence SaaS for prediction-market operators**, built on top of Carver's existing `entry_annotation` regulatory-data pipeline. It re-aims that data at a new buyer — the General Counsel, Chief Compliance Officer, Head of International, and Listing-Risk teams *inside* CFTC-licensed prediction-market platforms (Kalshi, Polymarket, and the broader DCM / event-contract category) — to solve three acute pains:

1. **Defending the business** from state-level, federal, and international enforcement that's accelerating against prediction markets (Kalshi is litigating in 7+ US states; Polymarket has been banned in France, Singapore, Thailand, the UK, and the Netherlands inside 18 months).
2. **Monitoring regulatory exposure on listed contracts** — every contract on the platforms references regulatory entities (agencies, named companies, named rules), and parallel enforcement against those entities can blow up settlement or move pricing materially.
3. **Planning jurisdictional expansion** with structured signal rather than reactive news reading — both platforms now operate in 140+ jurisdictions and are flying blind on which will close next quarter.

**V1 scope** is three bundled modules over a shared data spine, with staged delivery:
- **α — Regulatory Risk Radar** (defensive event-triage for the platform itself)
- **γ — Listed-Asset Regulatory Risk** (event-triage for contracts the platform has listed)
- **β — Strategic Expansion Intelligence** (longitudinal jurisdiction × update_type analytics)

**Roadmap** modules deferred to V2+:
- **δ — Policy & Lobbying Intelligence**
- **ε — Regulatory Audit Workbench**

**Initial TAM:** Kalshi ($22B valuation, $7B/wk volume) and Polymarket ($15B valuation, ICE-backed). Extended TAM: PredictIt, Manifold, Cantor Fitzgerald's event-contract surface, Robinhood Events, Webull Predict, tribal gaming entrants moving into event contracts, and every future CFTC-licensed DCM.

**Why now.** Both flagship platforms became fully regulated CFTC DCMs in the last 18 months (Kalshi self-certifies under Reg 40.2 since 2020; Polymarket's Amended Order of Designation closed Nov 2025). State-level and international enforcement against them is escalating in parallel. Their compliance budgets are net-new; there is no incumbent vertical-compliance vendor in this category.

**Why Carver.** The `entry_annotation` pipeline already produces structured, multi-jurisdiction regulatory annotations with the exact fields these workflows need (`update_type`, `regulatory_source.name`, `jurisdiction_tier`, `impacted_business.type`, `entities`, `impact_score`, `urgency_score`, `effective_date`, `compliance_date`, `reg_references`). Building Pred-Oracle is ~70% productization of an existing asset and ~30% net-new workflow software.

---

## 2. Market Context

### 2.1 Why prediction-market operators have an acute compliance-intelligence problem

Prediction-market operators sit at the intersection of CFTC derivatives regulation, state-level gambling regulation, federal securities and consumer-protection law, and (for offshore-origin platforms) every foreign gambling, derivatives, and crypto regulator. No single existing compliance-intelligence product is tuned for that intersection.

**Kalshi (CFTC DCM since Nov 2020):**
- Self-certifies new contracts under CFTC Reg 40.2, naming a *Source Agency* per contract for settlement.
- Cease-and-desist orders or active litigation in Nevada, New Jersey, Maryland, Arizona, Connecticut, Montana, Ohio, Massachusetts, New York, Wisconsin.
- Recent wins (Kalshi v. CFTC on election contracts; Nevada/NJ preliminary injunctions on CEA field preemption) and recent losses (Nevada PI later dissolved; Maryland district court denied PI).
- Expanded to 140+ countries in October 2025.
- Series F at $22B in May 2026; weekly volume >$7B; sports drives ~89% of fee revenue.

**Polymarket (CFTC DCM via QCEX acquisition, Nov 2025):**
- Resolution layer is UMA's Optimistic Oracle, which has had multiple high-profile failures (the ~$237M Zelensky-suit market resolved NO despite mainstream press calling it a suit; a March 2025 oracle-manipulation incident flipped a $7M contract by capturing 25% of UMA voting power).
- Banned by France's ANJ (Dec 2025, 13 months after investigation opened), Singapore GRA, Thailand, UK, Netherlands KSA, and DNS-blocked in Hungary.
- ICE invested $1B + $600M tranches at $9B → $15B valuations; ICE contractually distributes Polymarket's outbound event-data.
- Sports-led volume since US relaunch; 24h volume $120M+ regularly, record $425M on Feb 28, 2026.

**The broader category** includes PredictIt, Manifold, Robinhood Events (Kalshi partnership), Webull Predict (Kalshi partnership), Cantor Fitzgerald's prediction surface, Drift Protocol's on-chain prediction layer, and forthcoming DCMs from established exchanges. All of them face structurally similar regulatory exposure.

### 2.2 The gap in current vendor coverage

The incumbent regulatory- and policy-intelligence vendors (FiscalNote, Bloomberg Government, Politico Pro, Westlaw Edge, Reg-Track, etc.) serve banks, asset managers, pharma, telecom, and Big Tech. **None of them is tuned for the prediction-market intersection**, where the relevant regulators include state gambling commissions, tribal gaming authorities, the CFTC's event-contract docket specifically, and foreign gambling regulators that don't sit in the standard derivatives-compliance corpus.

This is the wedge.

---

## 3. The Carver Advantage

Carver's `entry_annotation` workflow (lives at `../carver-dags/workflows/entry_annotation/` in the sibling repo) produces, for every regulatory update ingested, a structured JSON document with the following fields (see Appendix A for the full schema):

- **Classification:** `update_type` (final rule / proposed rule / enforcement / guidance / press release / etc.), `update_subtype` (regulatory_body / enforcement_agency / standards_body / industry_association / etc.), `jurisdiction_tier` (us_federal / international / domestic).
- **Source:** `regulatory_source.name`, `regulatory_source.division_office`, `regulatory_source.other_agency`.
- **Critical dates:** `pub_date_content`, `effective_date`, `early_adoption_date`, `compliance_date`, `comment_deadline`, `other_dates`. Hijri-calendar support included.
- **Impacted business:** `organization`, `jurisdiction` (ISO codes), `industry`, `type`, `size`.
- **Impact summary:** `objective`, `what_changed`, `why_it_matters`, `key_requirements`, `risk_impact`.
- **Impacted functions:** Compliance, Risk Management, Legal, Operations, Trading, etc.
- **Actionables:** policy_change, process_change, reporting_change, tech_data_change, training_change.
- **Penalties & consequences.**
- **Regulatory references:** past releases, statutes, rules, precedents, personnel — with URLs.
- **Tags and entities** — deduplicated list of named people, organizations, and bodies.
- **Scores:** `impact_score` (0–10), `urgency_score` (0–10), derived `relevance_score`.

**Why these fields map cleanly to prediction-market operator workflows:**

| Carver field | Pred-Oracle use |
|---|---|
| `update_type` + `regulatory_source.name` | "Which regulator just did what" — primary filter for every alert. |
| `update_subtype` | Distinguishes binding rules from advocacy noise. Critical for triage. |
| `jurisdiction_tier` + `jurisdiction` (ISO codes) | Per-jurisdiction filtering for state-radar (α) and expansion heat-map (β). |
| `entities` + `impacted_business.organization` | Drives listed-asset risk (γ): which of *our* listed contracts mention these entities? |
| `impacted_business.industry` + `.type` | Lets us tag updates as "applies to prediction markets / event contracts / derivatives exchanges / sportsbooks / crypto exchanges / etc." |
| `urgency_score` + `effective_date` + `comment_deadline` | Drives alert prioritization and deadline-based escalation. |
| `impact_score` | Drives noise suppression — low-impact updates go to digest, high-impact updates page the on-call GC. |
| `reg_references` | Audit trail and citation provenance for ε (later) and γ (now). |

**Coverage assumption.** Per the brainstorming session, Carver covers a "fair number" of relevant regulators across US federal, US non-financial, US state, and international. The product should degrade gracefully on coverage gaps; gap-closing should be a coordinated workstream between Pred-Oracle product and the Carver data team. See § 9.1.

**Latency assumption.** Same-day (1–24h) from regulator publication to Pred-Oracle visibility. This rules out HFT-grade trading-signal positioning but is well within tolerance for compliance/GC workflows, which operate on hour-to-day cadences.

**Historical depth assumption.** <1 year of annotated history at this writing. Forward-looking product framing is honest; "predictive patterns from past reg signals" would require either (a) re-running the annotation pipeline on archival source content, or (b) accumulating ~2 more years of forward data. Acknowledge and don't oversell. See § 9.3.

---

## 4. Product Strategy — Five Modules

Each module below specifies: buyer, pain solved, user-facing surface, Carver fields consumed, differentiation, pricing direction, and build-position.

### 4.1 α — Regulatory Risk Radar (V1, wedge)

**Buyer.** General Counsel / Chief Compliance Officer at the prediction-market platform. Procurement out of legal/compliance budget.

**Pain solved.** "Did a regulator just do something that affects *us* (this platform)?" Today, this is answered by the GC team via Google Alerts, Twitter, journalist tips, and law-firm panels — slow, lossy, and unstructured. Kalshi spent days reacting to each new state cease-and-desist order; Polymarket had ~13 months of escalating ANJ signals before the actual France ban dropped.

**User-facing surface.**
- **Inbox / triage queue.** Every Carver-ingested update that matches a filter expression keyed to the platform (entity-name match against Kalshi/Polymarket/their staff/their competitors; `impacted_business.type` matches "prediction markets", "event contracts", "sports betting", "sweepstakes", "derivatives exchanges", etc.; `update_type` ∈ {enforcement, proposed rule, final rule, advisory, guidance}) is dropped into a triage queue with `urgency_score` and `impact_score` rolled into a combined priority.
- **Multi-channel alerting.** Slack/email/SMS pushes for high-urgency items. Configurable per-user (GC pages on-call only above urgency 8; CCO sees daily digest at urgency 5+; junior counsel sees the full inbox).
- **Per-jurisdiction dashboard.** 50 US states × federal × N international jurisdictions × `update_type` × time. Each cell is the count of in-scope updates and a drill-down into the documents.
- **Triage workflow.** Statuses (Acknowledged / In Legal Review / Counsel Response Drafted / Escalated / Closed). Comment threads on each item. Assignee. Due-date tied to the regulatory update's `effective_date` or `comment_deadline`.
- **Auto-generated audit log.** Every triaged update with status transitions, decisions made, and outcomes. Exportable for CFTC disclosure, SOC2, and litigation discovery.

**Carver fields consumed.** `update_type`, `update_subtype`, `regulatory_source.name`, `jurisdiction_tier`, `jurisdiction`, `entities`, `impacted_business.type`, `urgency_score`, `impact_score`, `effective_date`, `comment_deadline`, `penalties_consequences`, `metadata.feed_url` (for the "open primary source" link).

**Differentiation vs. FiscalNote / Bloomberg Government / Politico Pro.**
- Tuned to prediction-market intersection (state gambling regulators, tribal authorities, CFTC event-contract dockets, foreign gambling regulators). The incumbents thin out here.
- `impacted_business.type` taxonomy includes prediction-market-relevant categories ("event contracts", "sweepstakes", "derivatives exchanges") that incumbents don't carry.
- Bundle pricing — α + γ + β as one tool, vs. incumbent + a half-dozen ad-hoc tools.

**Pricing direction.** $250k–$1M ARR per platform, scaled by seats and jurisdiction breadth. Comparable: FiscalNote enterprise deals are $100–500k+; Bloomberg Government starts ~$5k/seat and scales rapidly.

**Build position.** V1, first deliverable. The entire shared data spine must work for α to work; γ and β are derivative views off the same spine.

---

### 4.2 γ — Listed-Asset Regulatory Risk (V1, fast-follower)

**Buyer.** Head of Listing / Head of Trading Risk at the prediction-market platform.

**Pain solved.** Every contract listed on Kalshi/Polymarket references regulatory entities (named agencies, named companies, named rules). Parallel regulatory action against those entities can move pricing materially or, in worst cases, blow up settlement. Today, the platforms react after the fact via Twitter and journalists. Kalshi's TIKTOKBAN-25APR30 contract was at the mercy of CFIUS, Commerce, FCC, and federal court rulings. Polymarket's Solana-ETF market swung 45% → 85% on SEC 19b-4 signals. Both platforms need structured early warning.

**User-facing surface.**
- **Pre-listing scan.** Before a new contract goes live, listing team submits the contract's title and YES/NO resolution criteria. Pred-Oracle parses out the named entities and regulators (via Carver's `entities` and `regulatory_source.name` corpus) and returns a "regulatory exposure report" — recent and pending updates touching each entity, with severity scoring.
- **Live monitoring.** For every active contract on the platform, Pred-Oracle watches for incoming Carver updates whose `entities` or `regulatory_source.name` intersect the contract's resolution entities. When one fires, a ticket is opened on the listing-risk team's queue.
- **Contract-watch dashboard.** All listed contracts with a "regulatory heat" score (count of touching updates × urgency × impact, decayed over time). Sortable for the trading-risk team's morning review.

**Carver fields consumed.** Same as α, plus `metadata.title` and `reg_references` for cross-document linking.

**Differentiation.** No incumbent does this. The closest analogues are bespoke entity-monitoring services from law firms or financial-intelligence vendors (Sayari, Castellum, Sigma Ratings) — none tuned to prediction-market resolution.

**Pricing direction.** Per-listing-team seat or per-contract surcharge. Bundles with α at ~30–60% incremental ARR uplift.

**Build position.** V1, ships ~3–6 months after α. Shares the event-store data spine and entity-extraction pipeline. The net-new work is (a) the platform's listed-contract catalog ingestion, (b) the contract → entity parsing layer, (c) the contract-watch UI.

---

### 4.3 β — Strategic Expansion Intelligence (V1, analytics layer)

**Buyer.** Head of International / Corp Dev at the platform. Also consumed by the CEO and Board in quarterly review.

**Pain solved.** Both Kalshi (140+ countries since Oct 2025) and Polymarket (USDC-native global distribution) need to know which of their open jurisdictions will close next quarter and which currently-closed jurisdictions will open. France ANJ took 13 months from open-investigation to Polymarket ban; structured tracking of ANJ's escalating enforcement cadence over those 13 months would have given Polymarket a multi-month head start on geofencing and lobbying. Same pattern repeats for Singapore, Thailand, UK, Netherlands.

**User-facing surface.**
- **Heat-map view.** Jurisdiction × `update_type` × `urgency_score` × `impacted_business.type` over time. Each cell is the count of in-scope updates with average urgency. Drilldown into the documents. Filter by date range, jurisdiction tier, agency.
- **Quarterly intelligence report (auto-drafted).** "10 jurisdictions where regulatory pressure is increasing; 5 where it's decreasing; 3 to watch." Each call-out backed by specific Carver documents. Exportable for board meetings.
- **Predictive cascades.** When an international body (FATF, IOSCO, BCBS, EU) publishes guidance, surface the historical pattern of member-state adoption — leading indicators for the next country-level action. (V1 implementation: rule-based; V2+: learned from historical cascade patterns once enough data accrues.)

**Carver fields consumed.** `jurisdiction_tier`, `jurisdiction`, `update_type`, `update_subtype`, `urgency_score`, `impact_score`, `effective_date`, `impacted_business.industry`, `regulatory_source.name`, `tags`.

**Differentiation.** Same data spine as α and γ, but a longitudinal/aggregation read path. The competitive landscape here is generic policy-intel tools (which don't carry prediction-market taxonomies) and bespoke geopolitical-risk firms (which are slow and unstructured).

**Pricing direction.** $100–250k ARR add-on, or standalone for platforms that only want expansion intelligence.

**Build position.** V1, ships ~6–9 months after α. Lowest data-spine impact — most of the work is the heat-map UI, the cascade-pattern rules, and the report generation. The underlying event store and entity/jurisdiction taxonomies are shared.

---

### 4.4 δ — Policy & Lobbying Intelligence (Roadmap)

**Buyer.** Head of Policy / Government Relations at the platform. At Kalshi, Tarek Mansour himself; at Polymarket, the post-DCM policy hire being built out.

**Pain solved.** Both platforms have policy strategies that depend on filing comment letters at the right moments, identifying Congressional testimony opportunities, and tracking which competitors and adversaries are positioning where. Today these workflows are mostly manual.

**User-facing surface.**
- **Upcoming-action calendar.** Every CFTC / Congressional / state-legislative action touching prediction markets, derivatives, event contracts, gambling, crypto. Tied to `comment_deadline` and `effective_date` from Carver.
- **Comment-letter drafting assistant.** Given a Carver-ingested NPRM or consultation, auto-draft a comment-letter outline keyed to the platform's stated positions. (LLM-generated, GC-reviewed.)
- **Stakeholder map.** Who else is filing comments, what positions are forming, which trade associations are aligning. Built from `entities` and personnel extraction.

**Why roadmap, not V1.** Different rhythm (months vs. hours), different buyer hierarchy (smaller team, harder procurement path), and the comment-letter drafting layer is meaningful net-new work. Better to nail V1 with the GC/CCO buyer first, then expand into policy/GR teams as the relationship deepens.

**Pricing direction.** $50–150k ARR add-on. Low seat count, high-value users.

**Build position.** V2, after V1 is selling and Carver has earned platform trust.

---

### 4.5 ε — Regulatory Audit Workbench (Roadmap)

**Buyer.** Head of Compliance / Audit at the platform.

**Pain solved.** "When the CFTC asks us in 2027 why we listed contract X in 2026, can we show them the regulatory rationale at the time?" CFTC DCMs are required to maintain extensive records; SOC2 audits care about evidence trails; litigation discovery can require exhibiting the regulatory context.

**User-facing surface.**
- **Per-contract regulatory dossier.** For every contract the platform has ever listed, a structured export of the Carver-ingested regulatory events that touched it, with primary-source citations and timestamps.
- **On-demand audit export.** Filtered by date range, agency, contract, entity. PDF / structured JSON / CSV.
- **Long-term archive.** Immutable storage of all Carver-ingested updates that fed any prior triage, with provenance.

**Why roadmap, not V1.** Quiet pain. The platforms are not yet feeling acute pressure from regulator audits or discovery requests — they will, but not today. Premature to lead with this. Strong V2+ retention play once V1 is sticky.

**Pricing direction.** $30–100k ARR bundle add-on. Stickier than other modules — audit/compliance archives have very low churn.

**Build position.** V3, after V2 (δ) and after enough V1 history has accrued to make the archive valuable.

---

## 5. Shared Data Spine

All five modules sit on a single architectural foundation. This is the case for bundling — they share data, taxonomies, and infrastructure.

### 5.1 Event store

The atomic unit is a **regulatory event** = one Carver-ingested update with its full annotation payload, plus Pred-Oracle-internal enrichments (entity-resolution against platform-customer catalogs, custom tags per platform, triage status, assignee, status history).

### 5.2 Filter language

Every module is fundamentally a filter expression over the event store plus a UI surface. The filter language must support:
- Entity matching (against platform-customer entity catalogs).
- `update_type` and `update_subtype` enumeration matches.
- `jurisdiction_tier` and `jurisdiction` ISO-code matches.
- `impacted_business.type` / `.industry` taxonomy matches.
- Numeric thresholds on `urgency_score`, `impact_score`.
- Date-range and date-arithmetic on `effective_date`, `compliance_date`, `comment_deadline`, `pub_date_content`.
- Boolean composition (AND / OR / NOT).
- Named, savable filter expressions (becomes the "watchlist" UX).

### 5.3 Customer catalogs

Each platform-customer brings:
- **Their own identity catalog** (their entity name, key personnel names, competitor names, subsidiaries).
- **Their listed-contract catalog** (titles, resolution criteria, listing dates, settlement entities) — feeds γ.
- **Their jurisdictional footprint** (where they currently operate, where they're considering entering) — feeds α (geographic filtering) and β (expansion analytics).

### 5.4 Surfaces

- **Web app** — primary user surface. Dashboards, queues, heat-maps.
- **Slack / email / SMS** — alerting integrations.
- **Webhook / API** — outbound for the platform's own systems (e.g., their GRC tool, Jira, internal ops dashboards).
- **Quarterly report generator** — PDF export for β.
- **Audit export** — for ε later.

### 5.5 Why the architecture justifies bundling

Building α + γ + β as one product means:
- One event store ingesting from Carver.
- One entity-resolution layer.
- One filter expression engine.
- One alerting/notification system.
- One auth / RBAC / tenancy model.

Splitting into three independent products would triple the infrastructure for negligible product gain. δ and ε reuse the same spine when built.

---

## 6. V1 Scope (α + γ + β)

### 6.1 Explicit V1 boundaries

**In scope:**
- Event store ingesting Carver `entry_annotation` outputs.
- Multi-tenant data model (one tenant per platform customer).
- Web app with role-based views for GC, Listing Risk, International / Corp Dev.
- Slack and email alerting; webhook outbound.
- Filter expression engine with savable watchlists.
- α full functionality (triage queue, multi-channel alerts, per-jurisdiction dashboard, audit log).
- γ full functionality (pre-listing scan, live contract monitoring, contract-watch dashboard).
- β analytics views (heat-map, quarterly report generator).
- Customer catalog ingestion: entity catalog (CSV upload + API), listed-contract catalog (CSV upload + Polymarket/Kalshi API integrations if feasible), jurisdictional-footprint catalog.

**Out of scope (deferred):**
- δ comment-letter drafting and stakeholder mapping.
- ε per-contract audit dossier and long-term archive.
- HFT-grade real-time trading signal (Carver latency rules this out anyway).
- Carver coverage expansion to specific regulators identified as gaps (separate coordinated workstream with Carver data team).
- White-label / embedded SDK for the platforms' end-user products (this is the "data vendor play" that we explicitly chose not to lead with — but doesn't preclude later as a V3+ offering).

### 6.2 Build sequence

1. **Months 0–6: α.** Event store, filter engine, alerting, triage workflow, per-jurisdiction dashboard, audit log. Launch with 2 design-partner platforms.
2. **Months 4–9: γ.** Layered on the α spine. Pre-listing scan, live monitoring, contract-watch. Requires listed-contract ingestion path.
3. **Months 7–12: β.** Heat-map, quarterly report generator, predictive cascade rules. Requires longitudinal data accrual — works better with more months of Carver history flowing through the event store.

The sequencing is data-driven: α needs the spine to be right, γ extends it minimally, β is the longitudinal layer that benefits from accrued history.

### 6.3 Design-partner strategy

Sign 2 design partners early (one Kalshi-class, one Polymarket-class — or two from a slightly broader set including PredictIt, Cantor, Manifold, Robinhood Events). Deeply discounted V1 ARR ($50–100k) in exchange for:
- Weekly product-feedback calls.
- Letting Pred-Oracle ingest their entity catalog and listed-contract catalog from day one.
- Reference logo and case-study rights at GA.

### 6.4 Open questions for product / engineering

1. **Carver coverage audit.** Which regulators relevant to prediction markets are *not* currently ingested? State gambling commissions specifically? Tribal gaming authorities? Foreign gambling regulators beyond ANJ/KSA? Where are the gaps? *(Requires sync with Carver data team — see § 9.1.)*
2. **Listed-contract ingestion.** Does Kalshi/Polymarket expose a public API for their full listed-contract catalog, or does γ require manual CSV upload per customer? What's the latency on contract listings → Pred-Oracle ingestion?
3. **Entity catalog normalization.** Carver's `entities` field is "deduplicated, sorted, flat list" per document. Pred-Oracle needs cross-document entity resolution (the same "Tarek Mansour" across thousands of documents). Build, buy, or use Carver's existing infrastructure if any?
4. **Multi-tenant auth + data isolation.** What's Carver's existing tenancy / RBAC posture? Does Pred-Oracle inherit a Carver-platform identity layer or build standalone?
5. **Webhook / API outbound for customer integrations.** What's the rate-limit / SLA model?
6. **Quarterly-report generation for β.** PDF generator built in-house, or use an existing Carver reporting infrastructure?
7. **Re-running annotation on archival content** to extend history beyond <1 year. Is this feasible? Cost? Coordination with Carver data team? *(Bears on β's predictive-cascades quality.)*

---

## 7. Roadmap — δ and ε

### 7.1 δ — Policy & Lobbying Intelligence

Trigger to start: V1 customers (2 platforms) have renewed at least once, and either platform asks for comment-letter or policy-tracking functionality. Estimated V2 build: 4–6 months once started. Net-new components: comment-letter drafting LLM workflows, stakeholder-network graph from entity extraction, policy-position taxonomy.

### 7.2 ε — Regulatory Audit Workbench

Trigger to start: First V1 customer faces a CFTC or state-regulator audit / data request that an audit-export feature would have streamlined. Or: a SOC2 audit on a customer surfaces evidence-of-compliance gaps Pred-Oracle could fill. Estimated V3 build: 2–4 months. Net-new components: long-term immutable archive (S3 + write-once), PDF/structured export, per-contract dossier composer.

---

## 8. Pricing & GTM

### 8.1 Pricing tiers (initial direction)

| Tier | Modules | ARR | Buyer-of-record |
|---|---|---|---|
| Wedge | α | $250–500k | GC / CCO |
| Bundle | α + γ + β | $500k–1.5M | GC / CCO + Listing Risk + Head of International |
| Enterprise | α + γ + β + δ + ε | $1–2.5M | C-suite (multi-team) |

Pricing scales on (a) seat count, (b) jurisdiction breadth (cost ramps with number of monitored jurisdictions), (c) listed-contract volume (γ economics).

### 8.2 Sales motion

Direct enterprise sale into GC / CCO. The brand asset (Carver-as-regulatory-intelligence) opens the door; the demo of α's triage queue with the platform's own entity matched against a recent state C&D closes it.

Initial sales motion is founder-led + 1 enterprise AE. Sales cycle: 3–6 months for V1 design partners, 4–9 months for follow-on customers.

### 8.3 TAM extension paths

1. **Adjacent verticals.** Same product fits sports-betting operators expanding into event contracts, crypto-derivatives exchanges, tokenization platforms hitting securities-regulator radar. ~10× the prediction-market-only TAM.
2. **Reverse-distribution: Carver-as-input-to-platform-product.** Once the GC/Compliance buyer relationship exists, the platforms become natural distribution channels for the original "data vendor" play (Approach A from the brainstorming session) — they may want Pred-Oracle's curated feeds embedded in their own user-facing products.
3. **Settlement oracle (Approach B from brainstorming).** Only once Carver decides to take on settlement liability — and that decision is materially easier to make once Carver has years of pilot experience with the platforms via Pred-Oracle.

---

## 9. Risks & Assumptions

### 9.1 Carver coverage gaps

**Risk.** Pred-Oracle's value proposition depends on Carver ingesting the regulators that matter to prediction-market operators. The "fair number" of regulators currently covered may have gaps in state gambling commissions, tribal authorities, foreign gambling regulators, or specific niche bodies (e.g., FATF/IOSCO/BCBS lower-level publications).

**Mitigation.** Day-one Carver-data-team coordination: audit coverage against a prediction-market-operator-relevant target list, prioritize fills. Pred-Oracle product surfaces "coverage status by jurisdiction" transparently so customers know what's monitored and what isn't.

### 9.2 Incumbent competitor response

**Risk.** FiscalNote, Bloomberg Government, or a similar incumbent decides prediction markets is a vertical worth serving and ships a competing product.

**Mitigation.** Pred-Oracle's specific advantage is (a) the structured field schema tuned to this vertical (incumbents have wider but shallower data), (b) speed-to-market (Carver can ship V1 in months while incumbents reposition large existing products), (c) bundled workflow (α + γ + β as one tool, where incumbents would have to assemble multi-product responses). Lead with the vertical specificity; bundle pricing closes the gap on data breadth.

### 9.3 Historical-data limitation

**Risk.** With <1 year of annotated history, the "predictive cascades" layer in β and any pattern-mining in γ rest on thin priors. Customers expecting hindsight-validated predictive claims will be disappointed.

**Mitigation.** Frame β's predictive layer honestly as rule-based / forward-looking in V1, with learned patterns in V2+ once 2–3 years of history accrues. If feasible, fund a Carver-side workstream to re-annotate archival regulator content to extend history backward by 3–5 years; this dramatically strengthens β.

### 9.4 Buyer-procurement complexity

**Risk.** Selling into GC/Compliance at a fast-moving fintech can have procurement complexity (security review, legal review of data terms, multi-stakeholder approval). Cycles longer than product-team budget would expect.

**Mitigation.** Design-partner pricing absorbs sales-cycle risk for the first 2 customers. From there, repeatable security-review packets, standard data-processing agreements, and SOC2 / ISO 27001 progress all compress later cycles.

### 9.5 Carver brand stretch

**Risk.** Pred-Oracle is Carver's first vertical-compliance product; if it underdelivers it damages Carver's broader data-vendor positioning.

**Mitigation.** Either ship under a clear sub-brand (Pred-Oracle is the working name and works as a sub-brand) or hold high quality bar on V1 launch. Avoid premature partnership announcements until at least one design partner is in production use.

### 9.6 Naming consideration

The word "Oracle" has specific meaning in the prediction-market context (UMA Optimistic Oracle, Chainlink, etc., all of which provide settlement data). "Pred-Oracle" could be misread as a settlement-oracle product (which it explicitly is not — that would be Approach B from the brainstorming). Worth revisiting the name before external launch. Internal use is fine.

---

## 10. Success Metrics

### 10.1 V1 milestones

- **Month 3:** α MVP live with internal Carver users acting as proxy customers (Carver's own regulatory-tracking team if it has one).
- **Month 6:** α GA with 2 design partners signed and onboarded.
- **Month 9:** γ live with design partners; first cross-module retention case study.
- **Month 12:** β live; first $1M+ ARR customer signed (Kalshi or Polymarket scale).

### 10.2 North-star metric

**Triaged-update throughput per customer per week.** Measures the actual workflow value Pred-Oracle delivers — how many regulatory updates the GC/Compliance team triaged via Pred-Oracle, with status transitions and outcomes. If this number is high and growing, Pred-Oracle is replacing the manual workflow it's supposed to replace.

### 10.3 Leading indicators (months 0–6)

- Carver-coverage completeness against the prediction-market-relevant regulator target list (target: 80%+ by month 6).
- Time from regulator publication to Pred-Oracle visibility (target: <12h median, <24h p95).
- Design-partner alert relevance — % of alerts that the GC team rates "actionable" vs. "noise" (target: >70% actionable).
- Design-partner triage time — median time from alert fired to status transition out of "new" (target: <2 hours for urgency 8+).

### 10.4 Lagging indicators (months 6–12)

- Logo retention (target: 100% V1 design-partner retention into year 2).
- Net revenue retention (target: 120%+ as design partners expand to bundle + new seats).
- Sales-cycle length (target: <6 months for follow-on customers by month 12).

---

## Appendix A: Carver Data Model Reference

The complete schema of one annotated regulatory entry, as produced by the `entry_annotation` workflow in `../carver-dags/workflows/entry_annotation/`. Drawn from `workflows/entry_annotation/prompts.py` and `workflow.py` in that repo.

```jsonc
{
  // From get_classification_prompt
  "metadata": {
    "title": "<official title>",
    "summary": "<≤80 char one-liner>",
    "base_url": "<e.g., sec.gov>",
    "feed_url": "<direct primary-source URL>",
    "language": ["<ISO 639-1, e.g., 'en'>"],
    "extraction_note": ["<doc quality notes>"]
  },
  "regulatory_source": {
    "name": "<official agency name>",
    "division_office": "<supervision/enforcement/etc.>",
    "other_agency": ["<for joint releases>"]
  },
  "update_type": "<final rule | proposed rule | comment request | guidance | enforcement | standard | advisory | bulletin | press release | speech | trend report | insights | event announcement | newsletter | website error | other>",
  "update_subtype": "<regulatory_body | cybersecurity_agency | enforcement_agency | standards_body | industry_association | media_analytics | other>",
  "jurisdiction_tier": {
    "tier": "<1|2|3>",
    "label": "<us_federal | international | domestic>",
    "reasoning": "<one sentence>"
  },

  // From get_metadata_extraction_prompt
  "critical_dates": {
    "pub_date_content": "<ISO or partial>",
    "pub_date_calendar": "<gregorian|islamic>",
    "updated_date": "...",
    "effective_date": "...",
    "early_adoption_date": "...",
    "compliance_date": "...",
    "comment_deadline": "...",
    "other_dates": [{ "date": "...", "calendar": "...", "description": "..." }]
  },
  "impacted_business": {
    "organization": ["..."],
    "jurisdiction": ["<ISO codes>"],
    "industry": ["<Title Case, e.g., Retail Banking, Crypto>"],
    "type": ["<Plural Title Case, e.g., Banks, Asset Managers>"],
    "size": ["<All | Large | Medium | Small | Micro | regulatory-threshold name>"],
    "other_notes": ["..."]
  },
  "impact_summary": {
    "objective": "...",
    "what_changed": "...",
    "why_it_matters": "...",
    "key_requirements": ["..."],
    "risk_impact": "..."
  },
  "impacted_functions": ["<Compliance | Risk Management | Legal | etc.>"],
  "actionables": {
    "status_change": "...",
    "policy_change": "...",
    "process_change": "...",
    "reporting_change": "...",
    "tech_data_change": "...",
    "training_change": "...",
    "other_change": "..."
  },
  "penalties_consequences": ["..."],
  "reg_references": {
    "past_release": ["<text (URL)>"],
    "statutes": ["..."],
    "rules": ["..."],
    "precedents": ["..."],
    "personnel": ["<name, title>"],
    "other_ref": ["..."]
  },
  "tags": ["..."],
  "entities": ["<deduplicated, sorted: orgs, people, bodies — NO regulations/rules/acts>"],

  // From get_scoring_prompt
  "scores": {
    "impact":  { "score": 0-10, "label": "high|medium|low", "confidence": 0-1 },
    "urgency": { "score": 0-10, "label": "high|medium|low", "confidence": 0-1 },
    "relevance": { "score": 0-10, "label": "...", "confidence": 0-1 }
  }
}
```

---

## Appendix B: Specific Platform Contracts that Validate the Use Cases

### B.1 Kalshi

- **TIKTOKBAN-25APR30** ("Will TikTok be banned by Apr 30, 2025?"). Pricing depended on FCC, CFIUS, Commerce, and court actions — γ use case for the listing team.
- **Government shutdown markets (Jan 31, 2026).** Sub-markets on which agencies stop work required a per-agency view of contingency plans — γ use case.
- **KXFEDDECISION-26MAR / KXLARGECUT-26** (Fed rate decisions). Settlement clean (FOMC statement), but pricing sensitive to FOMC speeches, regional Fed signals, Treasury actions — γ use case for market makers, β for tracking Fed cycle as a recurring source.
- **FDA drug-approval contracts** (referenced in Kalshi's science-and-tech category). PDUFA dates, AdComm meetings — natural γ use case.
- **State-level cease-and-desist orders** against Kalshi in NV, NJ, MA, NY, MD, CT, AZ, OH, MT, WI. α use case — exactly the events Pred-Oracle should surface as enforcement actions targeting prediction markets.

### B.2 Polymarket

- **"Solana ETF approved in 2025?"** Price swung 45% → 85% on SEC chair signals and 19b-4 movements. γ use case.
- **Fed rate decision dashboards.** Same pattern as Kalshi — β for cycle tracking.
- **Zelensky-suit market (~$237M).** Resolution failed because UMA found "no credible reporting consensus." Not Pred-Oracle's direct play (settlement is Approach B), but the failure mode highlights why platforms might eventually want a settlement-grade citation feed downstream of Pred-Oracle.
- **France ANJ ban (Dec 2025).** 13 months of escalating signals before the actual ban. α + β use case — a Pred-Oracle customer would have seen the cadence escalating from `update_type=advisory` to `update_type=enforcement` over those 13 months.

---

## Appendix C: Research Sources (May 2026)

### Kalshi
- Series F announcement (Crowdfund Insider, May 2026): https://www.crowdfundinsider.com/2026/05/277962-prediction-markets-kalshi-hits-22b-valuation-in-latest-funding-round/
- Kalshi v. CFTC (D.D.C. Sept 2024, D.C. Cir. Oct 2024): https://law.justia.com/cases/federal/appellate-courts/cadc/24-5205/24-5205-2024-10-02.html
- CFTC Prediction Markets Advisory: https://www.cftc.gov/PressRoom/PressReleases/9185-26
- State C&D landscape (Stinson): https://www.stinson.com/newsroom-publications-sportsbooks-or-commodity-exchanges-the-rising-legal-tensions-between-sports-betting-and-prediction-markets
- Robinhood / Webull partnership (Sportico): https://www.sportico.com/business/sports-betting/2025/robinhood-custom-sports-parlays-1234879283/
- Mansour vision (Stratechery): https://stratechery.com/2026/an-interview-with-kalshi-ceo-tarek-monsour-about-prediction-markets/

### Polymarket
- QCEX acquisition (PR Newswire): https://www.prnewswire.com/news-releases/polymarket-acquires-cftc-licensed-exchange-and-clearinghouse-qcex-for-112-million-302509626.html
- CFTC Amended Order of Designation (PR Newswire): https://www.prnewswire.com/news-releases/polymarket-receives-cftc-approval-of-amended-order-of-designation-enabling-intermediated-us-market-access-302625833.html
- FBI raid (NBC News): https://www.nbcnews.com/tech/tech-news/fbi-raids-polymarket-ceo-shayne-coplans-apartment-seizes-phone-source-rcna180180
- ICE investment: https://ir.theice.com/press/news-details/2025/ICE-Announces-Strategic-Investment-in-Polymarket/default.aspx
- France ANJ ban (DL News): https://www.dlnews.com/articles/regulation/france-to-ban-users-access-to-polymarket-website-report/
- UMA Optimistic Oracle docs: https://docs.polymarket.com/developers/resolution/UMA
- Zelensky suit resolution (Decrypt): https://decrypt.co/329210/polymarket-rules-no-237m-bet-zelenskyys
- Oracle manipulation (Orochi Network): https://orochi.network/blog/oracle-manipulation-in-polymarket-2025
- Solana ETF market: https://polymarket.com/event/solana-etf-approved-in-2025/solana-etf-approved-in-2025

### Carver internal references
- `entry_annotation` workflow: `../carver-dags/workflows/entry_annotation/`
- Prompt schema: `../carver-dags/workflows/entry_annotation/prompts.py`
- Workflow definition: `../carver-dags/workflows/entry_annotation/workflow.py`
- README: `../carver-dags/workflows/entry_annotation/README.md`

---

## Document maintenance

This doc is the canonical strategy artifact for Pred-Oracle. When V1 spec begins, individual module specs should go under `docs/specs/` (e.g., `docs/specs/alpha-regulatory-risk-radar.md`). When buyer personas are deepened, they go under `docs/personas/`. Keep this strategy doc as the single source-of-truth for the *why*; the specs are the source-of-truth for the *what* and *how*.
