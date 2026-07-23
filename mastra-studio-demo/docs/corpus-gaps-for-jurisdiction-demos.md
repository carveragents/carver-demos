# Corpus gaps for jurisdiction-variance demos — note for the data team

Written 2026-07-22 on `feat-mastra-guardrail-port`. Context: the sharpest demo we found
(`docs/DEMO.md` → state-lending counterfactual swap) shows a Carver-grounded agent surfacing a
*state-specific* loan-denial obligation that both a memory-only baseline and a live web-search
agent miss — because the applicant's **state** silently triggers an obligation nobody named in the
question. It works today only on a **hand-curated 4-record index** (`data/state-lending-records.json`)
because the differentiating obligations are **not in the crawled corpus**. This note lists what to
add so they enter organically.

## The structural gap

The corpus is deep on regulator **publications** (press releases, bulletins, enforcement actions,
speeches, guidance) but thin on **codified statutes and rules** — the actual obligation text with
its requirements. Jurisdiction-variance demos need the latter, tagged by jurisdiction, with
`impact_summary.key_requirements` populated. Two things to prioritise:

1. **Ingest primary codified law** (state statutes/regulations, federal eCFR), not just coverage of
   it. The canonical URL is the whole value — see `docs/DEMO.md` "citation integrity": LLMs and even
   crawlers emit wrong/dead URLs for these; the maintained pointer is the asset.
2. **Populate the `jurisdiction` field** (US-CO, US-CA, US-NY, …) on these records. The trimmed
   fixture shape drops it today; the full annotations schema has `impacted_business.jurisdiction`,
   but codified-law records need it set reliably.

## Specific sources to add (the four obligations in the demo)

| Obligation | Issuing body (regulatory_source) | Canonical URL(s) to crawl |
|---|---|---|
| **Colorado AI Act** — ADMT disclosure on an automated adverse (e.g. lending) decision: plain-language explanation of the model's role, principal reasons, data types/sources, right to access/correct data, right to meaningful human review. Operative 2027-01-01. | Colorado General Assembly; Colorado Attorney General | `https://leg.colorado.gov/bills/sb24-205` · `https://leg.colorado.gov/bills/sb26-189` · Colorado AG ADMT rulemaking pages (rules due 2027-01-01) at `https://coag.gov/` |
| **California Holden Act** (Housing Financial Discrimination Act of 1977) — Fair Lending Notice + statement of specific reasons for adverse action on 1-4 unit owner-occupied housing finance (broader adverse-action definition than federal). | California Department of Financial Protection and Innovation (DFPI) | `https://dfpi.ca.gov/wp-content/uploads/sites/337/2021/10/DFPI-1977-FAIR-LENDING-NOTICE.pdf` · CA Health & Safety Code §§ 35800 et seq. |
| **Regulation B § 1002.9** — federal adverse-action notice (30-day, specific reasons or right to request, ECOA notice). | Consumer Financial Protection Bureau | `https://www.consumerfinance.gov/rules-policy/regulations/1002/9/` |
| **FCRA § 615** — adverse-action notice when a consumer report is used (CRA identification, free-report right, score + key factors). | FTC / CFPB | `https://www.ftc.gov/business-guidance/resources/using-consumer-reports-credit-decisions-what-know-about-adverse-action-risk-based-pricing-notices` |

## Topic coverage — which of these bodies Carver already tracks

Checked against the full Carver topic catalog (`carver-showcase/data/topic_catalog.csv`, 1,060 topics
— the backend topic universe; the live topics API 401s from this environment, so this is the vendored
snapshot). **Three of the four source bodies are already topics; only the Colorado statute source is
missing:**

| Source body | Already a Carver topic? | Implication |
|---|---|---|
| **CFPB** (`consumerfinance.gov`) | ✅ yes (~446 records crawled) | No new topic. Capture Reg B § 1002.9 as an obligation record with `keyRequirements`. |
| **FTC** (`ftc.gov`) | ✅ yes | No new topic. Capture the FCRA § 615 adverse-action guidance as an obligation record. |
| **California DFPI** (`dfpi.ca.gov`) | ✅ yes (~440 records crawled) | No new topic. Capture the Holden Act Fair Lending Notice obligation. |
| **Colorado Attorney General** (`coag.gov`) | ✅ yes | No new topic. The operative ADMT disclosure *rules* (due 2027-01-01) will publish here — this path covers the Colorado obligation without touching the legislature. |
| **Colorado General Assembly** (`leg.colorado.gov`) | ❌ **NO — not a topic** | To crawl the AI Act *statute itself* (SB 24-205 / SB 26-189), **add `leg.colorado.gov` as a new topic** (`jurisdiction: US-CO`). Otherwise rely on the `coag.gov` topic above for the rules. |

So for CFPB / FTC / DFPI the obligations can flow **organically** — those bodies are crawled today; the
specific obligation documents just are not captured as requirement records yet (they exist only as
*publications* — press releases, bulletins). The one genuinely new topic needed for the primary
statute is **`leg.colorado.gov`**.

This matches a corpus-wide pattern: **Carver tracks regulators and executive agencies, not state
legislatures.** Colorado has 14 topics — all executive (Banking Board, Division of Banking/Securities,
AG, PUC, Insurance…) and **no legislature**; across the entire 1,060-topic catalog only two state
legislatures appear at all (Connecticut General Assembly, New Jersey Legislature). That is why primary
statute/bill text does not get crawled and why the Colorado AI Act shows **0 records** in the 242k
corpus even though the Colorado AG is tracked.

## Broader recommendation (to make jurisdiction demos repeatable)

To generalise beyond this one scenario, add these source *classes*, jurisdiction-tagged, with
requirements extracted:

- **State legislature primary law**: `leg.colorado.gov`, `leginfo.legislature.ca.gov`,
  `nysenate.gov` / `legislation.nysenate.gov`, and equivalents — the bill/statute text with the
  canonical URL (which is unguessable and LLMs get wrong — see the citation-integrity finding).
- **State financial / AI regulators' rule & guidance pages**: CA DFPI, NY DFS, state banking and
  attorney-general offices — the *rules*, not just the press releases.
- **Federal codified regs as obligation records**: eCFR / `consumerfinance.gov/rules-policy/…` — one
  record per section, `keyRequirements` populated.

The test of success: a record for "what a lender must disclose when an automated model denies a
Colorado home loan" that carries `jurisdiction: US-CO`, populated `keyRequirements`, and the
`leg.colorado.gov` canonical URL — retrievable by semantic search on the *situation* without the
user naming the statute.
