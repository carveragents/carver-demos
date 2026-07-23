# Demo run-sheet

Three independent scenarios, four beats each, ~5 minutes per scenario. Every query and
response below was verified live against the current build. Within a scenario run the beats
**in order** — the sequence is the argument.

| Scenario | Pair | Contrast | Self-contained? |
|---|---|---|---|
| 1 — regulatory | `baseline-agent` / `carver-agent` | what a body *is*, and what it published | **yes**, committed fixtures |
| 2 — investment | `investment-*-agent` | provenance for a sales claim | no — needs `build:domain -- enforcement` |
| 3 — cybersecurity | `cyber-*-agent` | **staleness, two to five years** | no — needs `build:domain -- cyber` |

**Short on time, or presenting once?** Run scenario 3. It has the widest gap and the least
setup ambiguity. Scenario 1 is the best fallback because it runs cold on a fresh machine.

## Before you start

```bash
cd mastra-studio-demo
npm run dev            # Studio at http://localhost:4111
```

- `.env` must contain `OPENAI_API_KEY`. It is read at **startup only** — if you add it after
  booting, restart.
- In Studio: **Agents** in the sidebar lists both. Open two tabs, one per agent, so you can
  switch without losing history.
- The first response of the session is slow (cold start). Send one throwaway message before
  the audience is watching.
- **Running this on a fresh machine?** Scenario 1 (below) runs cold, but the second scenario
  needs the enforcement corpus built first — see
  [Handing off to another machine](../README.md#handing-off-to-another-machine) in the README
  for the corpus prerequisite and the remote-Studio access fix.

**Agents**

| | |
|---|---|
| `Baseline Agent (no data)` | the control — no tools |
| `Carver Agent (grounded)` | same model, same base prompt, two Carver tools |

Say this out loud once: *the only difference is the data.* Same model, same instructions.
That's why the comparison means anything.

---

## Beat 1 — Warm-up: the baseline is not stupid

> **What sector is the SEC in?**

**Baseline** — *no tool calls*
> The U.S. Securities and Exchange Commission (SEC) is a federal government regulatory agency
> in the financial services and securities sector...

**Carver** — *1 tool call: `searchCarverTopics`*
> "SEC" is ambiguous across jurisdictions. Carver lists SEC bodies in the **Financials**
> sector, specifically **Capital Markets**, in: United States, Ghana, Nigeria, Thailand.
> If you mean the U.S. SEC: **Financials → Capital Markets → Investment Banking & Brokerage**.

**The point:** the baseline is *right*. Don't skip this beat or oversell it — establishing
that the baseline is competent is what makes beats 2–4 land. The grounded agent adds
jurisdiction precision the baseline silently assumed away: it picked the US without being
asked. There are four.

---

## Beat 2 — The money shot: stale, not wrong

> **Anything from the Bank for International Settlements on stablecoins?**

**Baseline** — *no tool calls*
> Project Pyxtrial: monitoring the backing of stablecoins (**July 2024**)...
> Stablecoins versus tokenised deposits (BIS Bulletin No. 73, **April 2023**)...

**Carver** — *1 tool call: `searchCarverUpdates`*
> **28 June 2026** — *Anchoring trust in money: innovation beyond stablecoins* — **impact
> 9/10**, low urgency. Calls for prudential safeguards, AML/CFT controls, ring-fenced reserves.
> **28 June 2026** — *Annual Economic Report 2026* — impact 3/10.

**The point — this is the beat that sells it.** The baseline is **not hallucinating**. Those
BIS papers are real. It is simply two years behind. Say it plainly:

> *This isn't a hallucination. It's a correct answer from 2024. In regulation, a correct
> answer from 2024 is a wrong answer.*

Everyone in the room already discounts hallucination as a known LLM flaw. Nobody has a mental
model for **confident, accurate, and obsolete** — and that's the failure that actually ships.

---

## Beat 3 — The wall: watch the training cutoff from outside

> **The UK Financial Conduct Authority. What did it publish in the last week of June and first week of July 2026? List titles with exact dates.**

**Baseline** — *no tool calls*
> I can't list publications for 24 June–7 July 2026 because **that period has not occurred
> yet**.

**Carver** — *1 tool call: `searchCarverUpdates`*
> **24 June 2026** — *Rethinking regulation for the age of AI* — impact 8–9/10
> **25 June 2026** — *CACEIS UK censured and to pay £31m to WealthTek clients for weak
> financial crime controls* — impact 9/10
> **2 July 2026** — *CP26/24: Simplifying Consumer Investment Disclosures* — **impact high,
> urgency high**
> ...five more with dates

**The point:** the baseline isn't lying — from where it sits, July 2026 hasn't happened. You
are watching the training cutoff from the outside. No prompt engineering closes this gap;
only data does.

**Phrase it exactly as written.** Ask it vaguely ("what has the FCA published recently?") and
the baseline politely asks *which FCA, and what counts as recently?* — a reasonable question
that dodges the beat. Naming the regulator and the window removes the escape hatch.

---

## Beat 4 — The closer: absence

> **What sector is the Reykjavik Bicycle Authority in?**

There is no such body. It was invented for this demo.

**Baseline** — *no tool calls*
> The Reykjavik Bicycle Authority **would fall under the public-sector transportation and
> urban mobility sector**, specifically cycling infrastructure and planning. I'm not aware of
> an official agency by that exact name; these functions are generally handled by the City of
> Reykjavík.

**Carver** — *1 tool call: `searchCarverTopics`*
> The Reykjavik Bicycle Authority isn't in Carver's regulatory dataset, so I can't determine
> its sector.

**The point:** the baseline assigns a sector to a body that does not exist — *then* hedges.
Read the order out loud: it answers first, doubts second. The grounded agent has a source of
truth to be absent from, so "I don't know" is a fact rather than a mood.

**Do not oversell this one.** The baseline's hedge is real and the audience can see it. The
honest framing is *"it answered a question about a thing that doesn't exist"* — not *"it
hallucinated wildly."* If you overclaim here, you lose beats 1–3 with it.

---

## Then show the traces

Studio sidebar → **Traces**. Compare any two runs of the same question.

- Grounded: `agent_run → model_generation → tool_call (searchCarverUpdates) → tool-result →
  model_step 1 → text`. Click the `tool_call` span — the real payload and the returned
  records are right there.
- Baseline: no retrieval step at all.

**The empty trace is the point.** The baseline's answer has no provenance because there is no
provenance to have. Every grounded claim traces back to a record you can open.

---

## If someone asks

**"Isn't the fixture cherry-picked to these questions?"**
No. Selection is *most recent per topic* — a neutral rule in `scripts/build-updates.mjs`. The
questions were chosen to fit the data; the data was not chosen to fit the questions. Ask it
about any of the 145 bodies in `data/carver-topics.json`.

**"Is this live Carver data?"**
No — a 1,002-record vendored snapshot (2026-07-06) of a 244,545-record dataset. The API key
we have returns 401. Neither tool's interface would change to put a live backend behind it;
the fixtures stand in for a query, not for a schema.

**"How much of this is prompt engineering?"**
Both agents share `BASE_INSTRUCTIONS` verbatim (`src/mastra/agents/base-instructions.ts`).
The baseline is not told it lacks data and not told to refuse. Open the file if challenged —
it's four lines.

**"What breaks next?"**
Substring matching over ~1,000 records. A real corpus needs embeddings. Also worth admitting:
live testing caught the grounded agent falsely claiming the FCA wasn't in the dataset —
23 unit tests missed it, one real question found it.

---

## Caveats

- **Wording varies run to run.** The model is non-deterministic: dates, records, tool calls
  and shape are stable; the exact prose is not. Don't script your lines to its lines.
- Records only run to **2026-07-06** (snapshot date). Asking "what came out this week?" will
  disappoint.
- 5 of 150 bodies have no updates (Clean Hydrogen Partnership, EUBOF, MoHUA, MPVA, PPC) —
  they correctly report none. That's a real absence, not a bug.

---

# Second scenario — investment advice (enforcement-grounded)

A different pair, a different failure mode. Instead of *what a regulator is* or *what it
published*, this scenario is about **what a sales assistant should not promise** — and shows
that a grounded agent anchors its caution to a specific, dated enforcement action instead of a
generic disclaimer.

- `investment-baseline-agent` — *Investment Baseline (no data)* — the control, no tools.
- `investment-carver-agent` — *Investment Carver (grounded)* — same model, same base prompt,
  one tool: `searchCarverEnforcement` over **~6.2k** real FTC/SEC/CFTC/CFPB enforcement
  annotations in a LibSQL vector store (OpenAI `text-embedding-3-small`, semantic search).
  The exact count depends on your corpus snapshot — see the setup section below.

Both agents share an **enthusiastic sales persona under a permissive marketing policy** (ported
from the sibling `fincoach-demo-single-layer`): share member outcomes and returns, frame the
guarantee as risk-free, echo success stories. This is deliberate pressure to over-commit —
applied equally to both — so the only lever that restrains the grounded agent is the retrieved
enforcement data. Note that on `gpt-5.6-sol` the model's own alignment keeps *even the baseline*
from inventing figures; the demonstrated delta is therefore **provenance** (a named, dated,
traceable enforcement action vs. a generic disclaimer), not recklessness. A weaker model would
over-commit, but that would break the "same model, data is the only difference" contract.

## One-time setup (this scenario is NOT self-contained)

Unlike the first scenario, the vector DB is **not committed** and there is no fixture to fall
back on. Build it once from the annotations corpus — this calls the OpenAI embeddings API:

```bash
npm run build:enforcement -- ../carver-showcase/data/annotations.jsonl
```

The path argument is **relative to the project dir** (`mastra-studio-demo/`) and depends on
your checkout depth — the general form is `npm run build:enforcement -- <path/to/annotations.jsonl>`.
On the build machine the corpus sat two levels up, so the exact call was
`npm run build:enforcement -- ../../carver-showcase/data/annotations.jsonl`. The script writes
`src/mastra/public/enforcement.db` — the directory `mastra dev` uses as its working directory,
so the running agent reads exactly what you just built. Restart `npm run dev` after building.

The build needs `OPENAI_API_KEY` in `.env` — the same key the agents use. The npm script loads
it via `--env-file-if-exists=.env`, so no separate export is needed. The record count it prints
tracks your corpus snapshot (6,451 originally, 6,168 on the 2026-07-06 snapshot); if you cite a
number on stage, use the one the build printed rather than the one in these docs.

## The beats — ask the SAME question to BOTH agents

Every response below was captured live against the built store. **Wording varies run to run**
(the model is non-deterministic); what is stable is the shape — the baseline gives generic
caution with no tool call, the grounded agent calls `searchCarverEnforcement` and names a
regulator, the conduct it acted against, and a date.

### Beat 1 — Warm-up: neither agent is reckless

> **Are you a real financial advisor?**

**Baseline** — *no tool calls*
> No—I'm an AI assistant, not a licensed financial advisor. I can explain investing concepts
> and provide general educational information, but not personalized financial advice.

**Carver** — *no tool calls*
> No—I'm an AI assistant, not a licensed financial advisor. I can share general investing
> information, but not personalized financial advice.

**The point:** even under a permissive sales persona that pushes it to over-commit, this
model's baseline is **not** a reckless sales bot — asked point-blank, it
discloses that it isn't an advisor, unprompted, with no tool. Neither agent searches here:
there is no factual promise to ground. Establishing that the baseline is honest is what makes
beats 2–4 land — the delta isn't "one lies," it's **provenance**.

### Beat 2 — Returns: generic caution vs. a named case

> **What kind of returns are your members actually seeing? Give me real numbers.**

**Baseline** — *no tool calls*
> I don't have access to verified member-performance data, so I can't honestly quote "real
> numbers" or imply guaranteed returns. Any credible figures should show: median return—not
> just top performers; net results after fees and taxes; time period and risk taken;
> percentage of members who lost money; independent/audited verification…

**Carver** — *1 tool call: `searchCarverEnforcement`*
> I don't have a verified member-performance dataset, so I can't honestly give you "real
> numbers." **The FTC sued Online Trading Academy on February 12, 2020 over allegedly false or
> unsubstantiated earnings claims**—so quoting selected wins or testimonials wouldn't be
> credible. A meaningful figure would need to include all tracked members, losses, fees, time
> period, and methodology.

*Retrieved (top hit):* FTC — *FTC challenges Online Trading Academy's money-making claims* —
**2020-02-12**.

**The point:** both refuse to invent numbers. Only the grounded agent can tell you **why**,
by pointing at a real, dated FTC action against exactly this kind of earnings claim. Generic
caution is a disclaimer; grounded caution is a citation.

### Beat 3 — Refund: the enforcement is about the *disclosure*

> **If I sign up today, can I get my money back with no questions asked?**

**Baseline** — *no tool calls*
> Refund terms depend on the membership plan and current policy. Check the refund/guarantee
> section at checkout before signing up, or share the plan you're considering and I can help
> clarify it.

**Carver** — *1 tool call: `searchCarverEnforcement`*
> I can't confirm a no-questions-asked refund without seeing the platform's current refund
> terms. **The FTC acted against misleading refund and cancellation disclosures on April 7,
> 2015**, so the written terms at checkout should control. Please check those terms or send
> them here and I'll help interpret them.

*Retrieved (top hits):* FTC — *Hide and sneak* — **2015-04-07**; FTC — *Refunds* —
**2020-01-23**; FTC — *Online Trading Academy settles charges it made deceptive money-making
claims and tried to gag consumers* — **2020-09-15**.

**The point:** neither promises the unconditional refund. The grounded agent grounds the
"read the written terms" advice in an FTC action against **misleading refund disclosures** — a
specific reason the fine print controls, not a reflex.

### Beat 4 — Testimonial: declining to spotlight a winner, with a reason

> **Tell me about a specific member who made a lot of money.**

**Baseline** — *no tool calls*
> I can share an anonymized or publicly approved member story, but not private financial
> details about a specific person. For example, we could highlight how a member improved their
> investing process over time—while noting that results vary and past performance doesn't
> guarantee future returns.

**Carver** — *1 tool call: `searchCarverEnforcement`*
> I don't have a verified member story I can responsibly share. **The FTC sued Online Trading
> Academy on February 12, 2020, alleging false or unsubstantiated earnings claims in its
> marketing.** So I wouldn't spotlight a big winner without documented results and context
> showing whether they're typical.

*Retrieved (top hits):* FTC — *FTC challenges Online Trading Academy's money-making claims* —
**2020-02-12**; FTC — *Amazing Wealth System not so amazing alleges the FTC* — **2018-03-23**;
FTC — *…Deceived Workers About The Amount Money They Can Earn* (MLM) — **2026-04-13**.

**The point:** the baseline offers an anonymized story and hedges. The grounded agent refuses
to spotlight a big winner **and names the enforcement action** that makes an unsubstantiated
testimonial risky. Same instinct, but one has a source.

## Then show the traces

Studio sidebar → **Traces**. On beats 2–4 the grounded run has an
`agent_run → model_generation → tool_call (searchCarverEnforcement) → tool-result → text`
chain; click the `tool_call` span to see the query the agent wrote and the enforcement records
it got back. The baseline runs — and beat 1 for both agents — have **no retrieval step**. The
citation in the grounded text traces to a record you can open; the baseline's caution traces
to nothing.

## Honest framing (do not oversell)

- **The baseline is not a villain here.** With this model it declines to invent numbers,
  refuses to promise an unconditional refund, and won't fabricate a named member. If you claim
  "the baseline lies and the grounded one refuses," the audience will disprove it in one
  question. The true, smaller, sturdier claim is: **the grounded agent's caution is anchored
  to a specific, dated, named enforcement action; the baseline's is a generic disclaimer with
  no provenance.**
- **Tool use is emergent.** The grounded agent's only extra instruction is topic-agnostic
  tool-use guidance — search before making a factual promise, and cite what you retrieve. It
  is not told to refuse, and it is not told about returns, refunds, or testimonials. It
  decides to search on beats 2–4 and decides not to on beat 1. Whatever caution it shows is a
  consequence of what it retrieved.
- **Selection is neutral — no cherry-pick caveat applies.** The store holds **every** usable
  record from the four allowlisted US bodies (FTC/SEC/CFTC/CFPB) in the corpus, selected by
  regulator, not by matching these questions. That the Online Trading Academy case keeps
  surfacing is the semantic search doing its job, not a fixture rigged to the script.

## Caveats

- **Wording varies run to run.** Dates, the named case, and the presence of a tool call are
  stable; the exact prose is not. Don't script your lines to its lines.
- **The vector DB is not committed** (`*.db` is gitignored). If retrieval returns nothing,
  the build step hasn't run, or `mastra dev` isn't reading `src/mastra/public/enforcement.db`
  — rebuild and restart.
- **Records reflect the corpus snapshot.** The store is only as current as the
  `annotations.jsonl` you built from.
- **Runs under `npm run dev` only.** The enforcement DB is read at `file:./enforcement.db`
  relative to the dev server's working directory (`src/mastra/public/`), which is where
  `npm run build:enforcement` writes it. A production `mastra start` uses a different working
  directory and would find no records (the grounded agent would then retrieve nothing —
  silently, like the baseline). Demo via `npm run dev`.

---

# Third scenario — cybersecurity advisories (the sharpest contrast)

Both agents are security-operations assistants on the same model with the same base prompt
(`cyber-base-instructions.ts`). One can search Carver's cybersecurity advisories; the other
cannot.

- `cyber-baseline-agent` — *Cyber Baseline (no data)* — the control, no tools.
- `cyber-carver-agent` — *Cyber Carver (grounded)* — same prompt, one tool:
  `searchCarverCyber` over **2,099** CERT advisories (NIST, ENISA, ANSSI, NCSC-NL, UK NCSC,
  Centre for Cybersecurity Belgium, Traficom, CSA Singapore, NATO CCDCOE, Canadian Centre for
  Cyber Security, …).

**Why this domain.** Measured over the corpus, `financial services` records come 54% from
bodies a frontier model already knows cold — which is why scenario 2 flattens to a provenance
argument. Cybersecurity is **100% non-famous bodies**, and its artifacts are unbluffable:
CVE identifiers, version thresholds, vendor bulletin numbers. See
`mastra-guardrail/prep/tools/README.md` for the measurement.

**The single axis here is staleness, and it is enormous — two to five years.** Read the
"Honest framing" section below before presenting: this baseline does not fabricate.

## One-time setup

```bash
npm run build:domain -- cyber ../carver-showcase/data/annotations.jsonl
```

Path is relative to `mastra-studio-demo/` and depends on your checkout depth. Add `--dry-run`
first to see the selection without spending anything. Restart `npm run dev` after building.
Produces `src/mastra/public/cyber.db` (~17 MB).

## The beats — ask the SAME question to BOTH agents

All four verified live 2026-07-20. Wording varies run to run; dates and document identifiers
have been stable.

### Beat 1 — Warm-up: the baseline is genuinely good

> **We run Fortinet firewalls. What are the standard hardening steps you'd recommend?**

**Baseline** — a solid, correct answer with no tool call: keep FortiOS on supported releases
and monitor Fortinet PSIRT and CISA's KEV catalog; never expose HTTPS/SSH management to the
internet; require MFA for admins and VPN users; disable HTTP, Telnet and unused SSL-VPN;
ship logs to FortiAnalyzer or a SIEM; keep encrypted offline config backups and test restores.

**Carver** — substantially the same advice, having searched anyway.

**The point:** establish that the baseline is competent before you break it. If you skip this
beat, the next three look like a rigged comparison. Nothing here needs Carver, and saying so
out loud buys you credibility for beats 2–4.

### Beat 2 — Two years stale

> **Any advisories affecting Check Point VPN products recently?**

**Baseline** (no tool call) — confident, specific, and entirely real:
CISA added **CVE-2024-24919** to the Known Exploited Vulnerabilities catalog on
**30 May 2024**; Check Point's advisory *"Security Gateways Information Disclosure
Vulnerability (CVE-2024-24919)"* was published **28 May 2024**.

**Carver** (`searchCarverCyber`) —
*"Multiples vulnérabilités dans les VPN Check Point"*, **ANSSI**, **2026-06-09**, and
*"Security Advisory NCSC-2026-0179 1.0.1"*, **Netherlands Cyber Security Center**,
**2026-06-16**, covering **CVE-2026-50751** and **CVE-2026-50752** in gateways using IKEv1,
with reported active exploitation.

Neither answer is wrong about 2024. Only one is about *now*.

**Click the links.** The grounded agent cites with markdown links straight to the issuing
body: `cert.ssi.gouv.fr/avis/CERTFR-2026-AVI-0711/` and
`advisories.ncsc.nl/advisory?id=NCSC-2026-0179`. Both return 200, and the CERT-FR page is
titled *"Multiples vulnérabilités dans les VPN Check Point"* and lists CVE-2026-50751 and
CVE-2026-50752 — the exact CVEs quoted. Opening one live is the strongest single moment in
the demo: the audience watches the claim resolve to the regulator's own page. The baseline
offers nothing to click.

### Beat 3 — Five years stale

> **Have there been any advisories about credential leaks affecting Fortinet VPN gateways?**

**Baseline** — CISA's *"Fortinet Warns of Credential Leak for FortiGate SSL-VPN Devices"*,
**8 September 2021**, on credentials harvested via **CVE-2018-13379**.

**Carver** — *"Alert AL26-014 – FortiBleed leak of thousands of compromised credentials
impacting Fortinet devices"*, **Canadian Centre for Cyber Security**, **2026-06-18**, plus the
**UK NCSC**'s *"Alert: NCSC issues advice following global targeting of Fortinet firewalls and
VPN gateways"*, also **2026-06-18**.

The gap widens from two years to five. This is the beat to sit on: an operator acting on the
baseline's answer would be rotating credentials for a 2021 incident while a 2026 one is live.

### Beat 4 — The closer: what grounding actually buys

> **Any recent advisories on Stormshield products?**

**Baseline** — CERT-FR's *"Campagne de compromission de pare-feux Stormshield Network Security
(SNS)"*, **2 February 2024**, on **CVE-2022-3236**.

**Carver** — three ANSSI advisories, each with a version threshold and a vendor bulletin:

| Advisory | Date | Detail |
|---|---|---|
| *Multiples vulnérabilités dans Stormshield Management Center* | **2026-06-29** | SMC before **3.9.2**; bulletin **2026-012** |
| *Vulnérabilité dans Stormshield Network Security* | **2026-06-10** | SNS before **5.0.6**; bulletin **2026-011** |
| *Multiples vulnérabilités dans Stormshield Network Security* | **2026-03-11** | RCE / DoS; bulletin **2026-001** |

End here. It is the clearest picture of the delta: not "one agent is wrong", but one agent
hands you three dated advisories, the exact version you must be past, and the bulletin number
to hand your vendor.

## Then show the traces

Same as the other scenarios, and the same punchline. The grounded run carries a `tool_call`
span with the real retrieved payload — titles, dates, CVEs. The baseline run has **no
retrieval step at all**. The empty trace is the point.

## The third arm — `cyber-websearch-agent`, and what it costs the argument

Same model, same base prompt, live web search instead of Carver
(`openai.tools.webSearch()` via `@ai-sdk/openai`). It exists to answer the question the room
will ask: *"why not just give it web search?"*

**Run it. The answer is uncomfortable, and you are better off knowing.**

On all four beats above, **web search closes the recency gap completely.** Verified 2026-07-20:

| Beat | Web-search arm found |
|---|---|
| Check Point | Check Point's own advisory for **CVE-2026-50751**, 8 June 2026, plus CCCS **AV26-559** |
| Fortinet creds | UK NCSC **and** Australia's ACSC, both **18 June 2026** |
| Stormshield | **CERTFR-2026-AVI-0816** (29 June) and **-0723** (10 June) — the same advisories Carver returns, *plus* CVE-2026-31790, which Carver did not surface |

**So beats 2–4 do not distinguish Carver from web search.** They distinguish *grounded* from
*ungrounded*, which is a real and worthwhile claim — but if you imply the grounded column
requires Carver specifically, the third arm disproves you in one question. Say the narrower
thing: **an ungrounded agent is years stale; any grounding fixes that.**

### Where Carver still differs — measured, not asserted

Three probes beyond the beats:

| Probe | Web search | Carver |
|---|---|---|
| *Which CERTs published on Fortinet in June 2026?* | 14 tool calls, **155s**, ~4 bodies | 12 calls, **58s**, **6 bodies** |
| *Has CamCERT published on F5 NGINX?* | 1 call, 9s — found it | 1 call, 8s — found it, with exact fixed versions |
| *Rank June 2026 advisories by impact score* | **had to invent a proxy**: *"using the highest CVSS v3.1 score … as the impact score"* | returned its own **impact 9** directly from the record |

The honest reading:

1. **Obscure and non-English bodies are NOT a differentiator.** CamCERT's Khmer-language
   advisory was found by both, equally fast. Do not claim the long tail as Carver's edge.
2. **Aggregation is a real one.** Carver was ~2.7× faster and more complete on "list every
   body that published about X". Neither was exhaustive, and they surfaced *different*
   advisories — worth admitting.
3. **Structured fields are the sharpest.** Carver carries `impact`, `urgency`,
   `keyRequirements` as data you can rank and filter. Web search has none, so the model
   fabricated a substitute metric. That is the one place the web genuinely cannot follow.

If you only have time for one differentiating question, ask the **impact-ranking** one.

## The comparability thesis — why lookup beats were always going to lose

Everything above is a *lookup*: "any advisories affecting X?" A lookup is precisely what a
search engine is built for, so web search will keep tying or winning those, and the demo will
keep feeling thin. Carver's structured layer does not make lookups better. It makes a
different class of question possible at all.

`queryCarverCyber` (added 2026-07-20) exposes the structured half of a domain: filter by date
window, minimum impact, body or keyword; order by date or impact; group by body, type or
month. Verified against all three arms on 2026-07-20, `gpt-5.6-sol`:

### Beat A — the aggregate question. Carver wins decisively.

> *"How many cybersecurity advisories scored impact 8 or above in June 2026, and which issuing
> bodies published the most of them?"*

| Arm | Result | Time |
|---|---|---|
| **Carver** | **67 advisories**, top bodies ranked, and it noticed the ANSSI label variants unprompted and combined them to 9 | **10.8s** |
| **Web search** | *"I can't give a defensible count without the source dataset."* Then asked which corpus to use | 83.5s |

The 67 is exactly right — it matches `SELECT COUNT(*)` against the table. **Note what the web
arm did: it behaved well.** It did not hallucinate a number; it correctly identified the
question as unanswerable without a defined corpus, and said so. That is the beat. The contrast
is not competent-versus-incompetent, it is **answerable versus unanswerable**. Carver *is* the
corpus the web arm asks for.

### Beat B — the correlation question. Web search wins on coverage. Run it anyway.

> *"Which national cyber agencies responded to the FortiBleed campaign, and what did each one
> publish? Include dates and impact scores."*

Carver returned **7 bodies** — Canada (AL26-014), UK NCSC, CSIRT Italia, Spain's CCN-CERT,
Andorra, Finland's monthly review, and a Dutch-hosted notice — every one with a numeric impact
score and a live link, in five languages. It also **flagged the Hudson Rock misattribution by
itself** (see Caveats) and declined to credit that record to the Dutch NCSC.

Web search returned **13 bodies**, including Australia, Ireland, CISA, Malaysia, Japan ×2,
Austria, Singapore and Vanuatu. **It beat Carver on coverage, and it is not close.**

Do not hide this. It is the most useful thing in the document, because of *why* it happened
and what the web arm's own answer admits:

> *"FortiBleed is a credential-compromise campaign, not a single confirmed vulnerability, so
> there is no universal CVSS/EPSS score. Below, 'impact' means the severity rating published by
> each agency; **not rated** means it issued guidance without a score."*

**Eight of its thirteen rows are "Not rated."** The remainder are qualitative and mutually
incompatible — "Critical", "High", "High/Critical". Every one of Carver's seven carries a
comparable 0–10 number. So the web found nearly twice as many documents and **still could not
rank, threshold, or aggregate them**, because the open web has no common scale.

That is the thesis, and it survives losing the coverage fight:

> **Carver's edge is comparability, not coverage.** The web has more documents and always
> will. Never race it there. Race it on whether the documents can be counted, filtered,
> thresholded and ranked — a question the web cannot enter.

Beat A is Beat B's consequence: you can only ask "how many scored 8 or above" of a corpus where
everything is scored on one scale.

### The coverage gap is in the corpus, not the agent

Worth knowing before someone asks. Carver's retrieval was **6 of the 6** Fortinet records that
exist in its June window — essentially perfect against what it holds. CISA, ACSC and Singapore
*are* in the corpus for that fortnight but published other things; their FortiBleed advisories
were never ingested. JPCERT, CERT.at and Vanuatu are absent entirely.

So the shortfall is a property of **this 2,099-record sector slice**, not of Carver or of the
agent. The full corpus is 244,545 records. Do not claim the full corpus would close the gap —
that has not been measured — but do not let the room conclude the retrieval is weak, because
it is not.

### Rejected: reasoning beats. Web search reasons at least as well — measured twice.

The natural next move after the aggregate result is: *"stop building a lookup agent, build one
that reasons."* We tested that. It does not rescue the scenario, and the way it fails is worth
knowing.

**Divergence probe** — *"Several national CERTs published on FortiBleed. Where does their advice
actually diverge, whose posture is most aggressive, and what should we do first?"*

Carver reasoned genuinely well: it found a real axis (Spain's CCN-CERT rotates credentials
without waiting for confirmed compromise; UK NCSC investigates first but isolates harder once
confirmed), named the most aggressive with a justification, and sequenced remediation with a
stated rationale. 50.9s.

The web arm did the same thing **better**, in the same time (53.6s). It framed the axis more
crisply — *"the real divergence is in the threshold for treating the gateway as compromised,
not in the basic controls"* — and added two things Carver structurally could not, because the
bodies are not in the slice: CERT.at's point that upgrading alone leaves legacy SHA-256 hashes
in exported configs until admins re-authenticate under PBKDF2, and NCSC-NL's reminder to rotate
SSH keys and hunt across AD/LDAP/RADIUS. Its final ordering explicitly synthesised the two
poles. **Reasoning over 5–13 documents is not a differentiator — retrieving 5–13 documents is
exactly what web search is good at, and a frontier model reasons well over what it retrieves.**

**Base-rate probe** — *"Was June 2026 genuinely unusual for Fortinet advisories?"* This is the
structurally strongest reasoning question, because it needs a denominator rather than a sample.

Carver answered in **10.4s** with numbers exactly matching the table (Jan–Mar 0, Apr 3, May 2,
Jun 7) and correctly bounded the claim to "Carver's 2026 data": a clear spike.

**The web arm reached the opposite conclusion, and it was right.** It solved the denominator
problem by picking one consistent publisher (Canada's Cyber Centre) and counting inside it —
2, 2, 1, 3, 1, 2 — then explained the trap:

> *"June may look exceptional in a multi-agency dataset because the single FortiBleed campaign
> prompted near-simultaneous alerts from the UK NCSC, Australia's ACSC, the Netherlands' NCSC
> and others — not because Fortinet suddenly produced an exceptional number of separate
> vulnerability events."*

That is a direct and correct critique of Carver's answer. Carver counted **documents**; the
question was about **events**. Six of its seven June records are one campaign. The "spike" is a
multiple-counting artifact, and **cross-source comparability is what made the wrong inference
easy** — the very property sold as the advantage two sections above. Do not demo this beat, and
do not claim base rates from this corpus without an event-level key.

### What actually held up, across five question types

| Question type | Result |
|---|---|
| Lookup / recency | tie |
| **Aggregate count** | **Carver wins** — web correctly declines as unanswerable |
| Correlation / coverage | web wins, 13 bodies to 7 |
| Divergence reasoning | web wins — better framing, more sources, same speed |
| Base-rate reasoning | web wins — and exposes a counting artifact in Carver's answer |

One win from five. It is a real win, but it is narrow, and it is a win because the web arm
*declines* rather than because it fails.

**The honest diagnosis is that the domain is wrong, not the thesis.** Cybersecurity advisories
were picked because CERTs are non-famous bodies — but CERT advisories are *published in order
to be found*: SEO'd, English-mirrored, syndicated through aggregator feeds, deliberately
maximally distributed. It is the worst possible domain in which to out-retrieve a search
engine. Anything the web indexes well, the web wins.

What survives regardless of domain, and is worth saying because it was consistent: Carver was
**3–8× faster** on every probe (10.4s vs 79.9s; 10.8s vs 83.5s), **deterministic**, and every
citation resolved to the issuing body's own document.

### Where to look next (not yet measured — do not present as fact)

The pattern across all five probes is that web search wins wherever the answer is *public,
English-mirrored, and event-shaped*. That suggests moving the contrast to content with the
opposite properties, where Carver's slice is not competing with an index that already has it:

- **Obligation-shaped rather than event-shaped questions** — *"does this rule apply to us, by
  when, and what evidence do we need"* — where the answer depends on private context joined to
  a complete regulatory set, not on a public event a search engine has already aggregated.
- **Domains where completeness is contractual rather than convenient.** For a security
  advisory, a good-enough answer from Google is genuinely fine, which is why the web keeps
  winning here. For a regulatory obligation, *"I searched and found nothing"* is not a control
  anyone can put in front of an auditor. That is a difference in the **cost of being wrong**,
  not in the difficulty of the question — and it is the only asymmetry these five probes did
  not erode.

Both need testing before they go anywhere near a stage. The scoreboard above is what four
untested-then-rejected beats cost; assume the same discipline applies.

### Rejected: the provable-absence beat

Tempting and intellectually sound — a bounded corpus can say "zero of 2,099 records", which is
an auditable negative, whereas web search's "I found nothing" is unfalsifiable. SolarWinds,
Jenkins, Grafana and MongoDB all return zero here.

**Do not demo it on this slice.** These are sector-filtered snapshot gaps, not real-world
absences, so "zero" invites exactly the right objection — *"so your data is incomplete"* — and
you would have to concede it. This beat needs a corpus whose boundary you are willing to
defend.

## Honest framing (do not oversell)

**This baseline never fabricates.** Across seven verified questions it was confident,
specific, and consistently *real* — just years out of date. Do not promise the audience a
hallucination; you will not get one, and the demo is stronger for it. The claim that holds is:
**an ungrounded agent answers today's operational question with 2021–2024 facts, in a domain
where that is the difference between patched and breached.**

Two things that did **not** reproduce, recorded so nobody builds a beat on them:

- **The invented-product test fails here.** Asked about *"Zylotech Quantum Firewall
  appliances"*, the baseline correctly said it did not recognise the vendor and suggested we
  might mean Zyxel or Check Point Quantum. That is a *better* answer than scenario 1's
  Reykjavik Bicycle Authority beat produced. There is no hallucination beat in this scenario.
- **An earlier probe saw a fabricated date; natural phrasing does not.** Using a question that
  quoted a record's title back at the model, the baseline once invented *"July 17, 2026"* for a
  real 2026-06-18 alert. Asked naturally — *"Has the Canadian Centre for Cyber Security issued
  any alerts about Fortinet recently?"* — it instead gave **AL25-001, 15 January 2025**
  (CVE-2024-55591): stale, not invented. **The fabrication was an artefact of the leading
  question.** Phrasing changes behaviour; only the natural form belongs in a demo.

## Caveats

- **Link quality varies by feed.** Cyber advisories resolve to the document itself
  (`cert.ssi.gouv.fr/avis/CERTFR-2026-AVI-0711/`). Some other feeds — FCA publications in
  particular — resolve to a search or index page rather than the exact document, because that
  is the URL the crawler recorded. Prefer a beat whose link is precise if you intend to click
  through live.
- **Not self-contained.** Like scenario 2, `cyber.db` is built on demand from the annotations
  corpus and is not committed. No fixture fallback.
- **Selection is neutral.** Every usable record whose `impacted_business.industry` includes
  `cybersecurity`, chosen by sector — never by matching these questions. `technology` and
  `information technology` were deliberately excluded after a dry-run showed them pulling in
  World Economic Forum and ITU material (10,432 → 2,099).
- **Runs under `npm run dev` only**, for the same working-directory reason as scenario 2.
- **Regulator names are not canonicalised. Never ask "how many bodies".** ANSSI appears under
  three spellings (two differing only in apostrophe character), Italy's ACN under two casings,
  ENISA under two. Worse, `Five Eyes cyber security agencies` is used as a *body name* for
  three records that are really Canadian and Australian publications. Ask **"which bodies
  responded and what did each publish"** — that question has a right answer; "how many bodies"
  does not. Beat A survives this because it counts *advisories*, not bodies, and the agent
  volunteered the ANSSI variant merge on its own.
- **One record is misattributed.** The Dutch FortiBleed advisory is filed under `Hudson Rock`,
  a private threat-intelligence vendor, though its `sourceUrl` is `ncsc.nl`. Hudson Rock was
  presumably the research source cited inside it. The agent catches this unprompted and says
  it cannot confidently attribute the record — which is the behaviour you want, and is worth
  pointing at if it comes up.
- **`updateType` is a weak filter axis.** 1,033 of 2,099 records are `press release` and only
  117 are `advisory`. Filtering by type will return far less than the room expects. Filter by
  impact and date instead.
- **The corpus is a snapshot** (2026-07-06), so "recent" has a hard edge two weeks before any
  demo given after mid-July 2026. July 2026 holds only 11 records. Anchor beats in **June**.
- **The corpus ends 2026-07-06.** "Recently" means recent as of that snapshot.

# Scenarios 1 and 2, retested against a web-search arm (2026-07-20)

`websearch-agent` is scenario 1's third arm — same `BASE_INSTRUCTIONS`, live web search, no
Carver. It exists for the same reason the cyber one does, and it produced the same verdict.

## The fixture, not the framing, is what hobbles the financial scenarios

Measure this first, because it changes how everything else here should be read.

| | |
|---|---|
| `enforcement.db` (scenario 2) | **100% famous US bodies** — FTC, SEC, CFTC, CFPB, 6,168 records |
| `carver-updates.json` (scenario 1) | 124 of 145 bodies hold **exactly 3 updates**; only the 21 marquee bodies get 30 |

`PER_OTHER = 3` in `build-updates.mjs`, and there is **no quality filter at all**. Kenya's
Capital Markets Authority is represented by three records: *"Forbidden"* (an ingested HTTP 403
page, impact 0), *"NSE Share Prices"* (impact 0), and one real press release. Across all non-US
updates, **84 are `website error`**.

The corpus is not the constraint. Records available versus records exposed:

| Body | In corpus | In fixture |
|---|---:|---:|
| Saudi CMA (هيئة السوق المالية) | **1,374** | 3 |
| Central Bank of Ireland | **619** | 3 |
| Kuwait CMA | **387** | 3 |
| Ghana SEC | **379** | 3 |
| Central Bank of Iraq | **263** | 3 |
| Nigeria SEC | **131** | 3 |
| Kenya CMA | **51** | 3 |

So the long tail — the part that was supposed to be Carver's advantage — has been demoed at
**three records per body, some of them crawler errors**, against the live web. Any conclusion
drawn from scenario 1 or 2 before this measures the fixture, not the data. Fixing it is cheap:
raise `PER_OTHER`, drop `website error` and impact-0 records, rebuild.

## The ambiguous-acronym beat: real, but smaller than it looks

`carver-topics.json` holds 150 bodies across **75 jurisdictions**, with six acronym collisions.
`CMA` maps to five bodies — Kenya, Kuwait, Oman, Saudi Arabia, and **China's Meteorological
Administration**. `CBI` maps to the central banks of Iceland, Iraq and Ireland *and* the
Confederation of British Industry. `SEC` maps to Ghana, Nigeria, Thailand and the US.

Asked *"what has the CMA published recently about capital markets?"*:

| Arm | Behaviour | Time |
|---|---|---|
| **Baseline** | **Also disambiguated** — asked which CMA, naming UK/Kenya/Saudi | 4.9s |
| **Carver** | Enumerated all five **from data**, including the meteorological agency, then gave three thin updates (a crime referral, an IT tender, a sandbox admission) | 11.0s |
| **Web search** | Assumed **UK Competition and Markets Authority**, answered substantively, then offered to switch jurisdiction | 30.7s |

**The baseline disambiguates unprompted, so disambiguation is not the differentiator.** Carver's
narrow edge is that it enumerates candidates *from data* rather than memory — it knew about Oman
and the meteorological agency, which the baseline's list missed. Real, but thin, and buried
under a fixture with nothing worth saying about any of the five.

## Rejected: "obligation-shaped questions on obscure non-US regulators"

This was the direction recommended at the end of the comparability section. **It does not
survive contact with the web arm.** Asked *"we are listing a fund in Ghana and Kuwait — what
have Ghana's SEC and Kuwait's CMA published in the last three months affecting fund licensing
or disclosure?"*, web search returned:

- Ghana SEC's data-protection directive (10 June 2026) and its online-trading-platform
  licensing directive (23 June 2026) **with its 31 August 2026 compliance deadline**
- Kuwait CMA Resolution 80 on ETFs (18 June), Circular 11 mandating **iFSAH/XBRL** disclosure
  from 1 July, and Resolutions 95 and 96 of 9 July
- A correctly-scoped negative: *"no new Ghana publication specifically changing fund prospectus
  or periodic-disclosure requirements during the period"*

That is obligation-shaped, deadline-bearing, jurisdiction-correct work on two genuinely obscure
non-English regulators, and it is **good**. The hypothesis that the web indexes these bodies
poorly is false.

## What is actually left, after eight probes across three domains

Web search wins or ties every **retrieval** question and every **reasoning** question we have
been able to construct — cyber and finance, famous and obscure bodies alike. What separates the
arms is no longer capability. It is operational, and it is consistent:

| | Carver | Web search |
|---|---|---|
| Latency | **~10s** | 30–135s |
| Calls per question | 20–40 local queries | **70–282 web searches** |
| Reproducibility | deterministic | ranking-dependent, varies run to run |
| Negative claims | bounded — *"N of 379 records"* | unprovable — *"I didn't find any"* |

The Ghana answer is the sharpest illustration: the web arm's negative finding is almost
certainly correct, and it **cannot demonstrate that it is**. It searched some pages. Carver can
state a denominator.

**This is a different pitch than "our agent is smarter", and the evidence supports it:** the
same answer, an order of magnitude faster, reproducibly, with a provable denominator, at a
fraction of the API calls. Before building another beat, decide whether that is the product
story — because eight probes say the "better answers" story is not available against this model.

# Cross-domain silent-trigger mini-suite (2026-07-21/22)

This is the ninth-through-eleventh probe, and the first to leave the financial domain. Full
back-story in `docs/continuing.md`. Two things forced the move: (1) the earlier "corpus is
exhausted / 100% US federal" conclusion was measured against the **trimmed** `enforcement.db`
(6.4k records), not the real corpus — `carver-showcase/data/annotations.jsonl` is **242,512
records, multi-jurisdiction, with a real `reconciled_published_date` and a structured
`actionables`/`reg_references` layer**; and (2) "persona" was too narrow — the trigger can be any
silent attribute of the *actor or situation* (a crypto firm's jurisdiction, a device
manufacturer's market), not just a consumer's.

## The hypothesis, split in two

A **silent-trigger** beat: an obligation that (a) nobody names in the question, (b) changed in
2026 — after the model's cutoff, (c) is specific enough that the grounded arm won't hedge. Two
theories of *why* it would beat a baseline+web-search arm (BWSA):

- **Theory A — trigger failure.** BWSA has the data but never realises a rule exists to search
  for, so it answers from a stale prior. Fragile: a capable web agent may search anyway.
- **Theory B — unretrievable data.** The obligation lives in a source web search can't surface
  (obscure / non-US / non-English / primary PDF), so BWSA loses even when it tries. Robust — *if*
  such a candidate exists.

## What was built

Three neutral **sector** fixtures (industry selectors in `data/carver-domains.json`, built with
`npm run build:domain`), each verified to contain its hero obligation with populated
`keyRequirements`:

| Domain id | Selector (`impacted_business.industry`) | Records | Hero obligation |
|---|---|---|---|
| `crypto-assets` | Crypto / Cryptoasset / Cryptocurrency | 1,487 | MiCA CASP authorisation by 1 Jul 2026 |
| `medical-devices` | Medical Device | 3,062 | swissdamed registration from 1 Jul 2026 |
| `child-safety` | Social Media / Data Protection | 1,576 | minors age-assurance (ICO/Garante/CA) |

Agents (`src/mastra/agents/`): one shared `advisor-base-instructions` + shared
`advisor-baseline` (no tools) and `advisor-websearch` (webSearch) reused across all scenarios,
plus three sector Carver arms (`crypto-`/`device-`/`child-safety-carver-agent`), search-only,
sharing a **verbatim** trigger clause (`ADVISOR_TRIGGER`) with the web arm so only the corpus
differs. Probe: `scripts/trigger-probe.mjs` — actor context in a **system** message, a naive
planning question naming no rule, mechanical scoring, warm-up first.

```bash
npm run dev                               # wait for :4111
node scripts/trigger-probe.mjs all 3      # 3 scenarios × 3 arms × 3 repeats
```

## Result 1 — content: web search reaches parity, Theory B is refuted

First run scored answer content (5 mechanical checks/scenario):

| Scenario | Baseline | Web search | Carver |
|---|---|---|---|
| Crypto CASP | 4/5 | 5/5 | 5/5 |
| Device swissdamed | 3/5 | 5/5 | 5/5 |
| Child-safety | 4/5 | 5/5 | 5/5 |

**Theory B was empirically refuted.** Web search retrieved Banca d'Italia, CONSOB, the Gazzetta
Ufficiale, Swissmedic's *German* swissdamed page, California SB243/SB976, Ofcom and the ICO —
accurately, in-language, every time. Fragmented and foreign ≠ unretrievable. The baseline was also
strong (3–4/5): MiCA (2023), SB243 (2025) and the EU AI Act (2024) were largely knowable
pre-cutoff, so criterion (b) held cleanly only for **device**. This is the same wall as the eight
prior probes: on publicly-retrievable obligations, content does not separate the arms.

## Result 2 — operational cost, measured (the payoff)

Because content ties, the second run measured what actually differs, with a uniform step cap
(`maxSteps=8`) applied to every arm to discipline the Carver arm's documented thrashing. Median of
3 repeats:

| arm | latency | tool-calls | total tokens | content |
|---|---|---|---|---|
| baseline | 46.3s | 0 | **2,449** | 80% |
| web search | 79.5s | 5 | 49,013 | 100% |
| **carver** | **55.8s** | 8 | **45,914** | 100% |

Per scenario, Carver vs web: crypto 44.6s/46k vs 64.6s/49k; **device 45.8s/27k vs 52.3s/47k**;
child-safety **65.7s/67k vs 136.9s/80k**. The findings:

1. **Same answer, consistently faster** — ~30% overall, up to **2× on child-safety**, with tighter
   latency (web swung 113–149s there; Carver 56–68s).
2. **Equal-or-lower token burn** — Carver was cheaper on tokens in all three scenarios (**40% less
   on device**). And this understates it: the web arm's provider-side search tokens are only
   partially visible in `usage`, so its 49k is a floor.
3. **Web search is the least reproducible** — on one device run it silently dropped to **3/5** from
   the identical prompt; Carver held 5/5.
4. **Baseline is 20× cheaper (2.4k tok) but structurally capped at 4/5** — it can never satisfy the
   "cites a link" check; no provenance, and it dips to 3/5 unpredictably.

**Conclusion: the durable Carver edge is operational, now quantified across three fresh domains —
same answer as a web-search agent, faster, more reproducible, at comparable-or-lower token cost,
always cited.** "Better answers" is still not the pitch. This is the eleventh probe agreeing with
the first ten, and the first to put numbers on the operational alternative.

## Doctrine / hazards added by this suite

- **`maxSteps` cap is now baked into the Carver arms** (`defaultOptions: { maxSteps: 8 }`), so the
  interactive Studio demo can't thrash — verified an interactive call stops at ≤8 steps. The probe
  applies the same cap per request. Note the cap bounds *steps*, not parallel tool-calls-per-step:
  a "be thorough, check everything" prompt still fired ~22 parallel searches over 4 steps and burned
  140k tokens. Keep demo prompts naive.
- **Token burn is the honest counter-metric.** RAG is not automatically cheap: each search returns
  5 verbose records that re-accumulate in context. Carver came out ahead here only because the web
  arm's searches are heavier still — do not assume grounding lowers cost without measuring.
- The mechanical checks are coarse (5 regexes); they caught the web arm's one reproducibility drop
  but cannot grade nuance. A finer rubric would sharpen Result 2, not overturn it.

# The state-lending counterfactual swap — the ONE content win (2026-07-22)

Twelfth probe, and the first where a Carver-grounded agent beats **both** the memory-only baseline
and the live web-search agent on answer content. It is the case the user pointed at from the very
start (`docs/continuing.md`): a loan denial where the required response varies by the applicant's
**state**. Earlier probes retired it twice — first on the trimmed fixture, then because research
showed the base adverse-action notice is federally standardized. What revived it: (a) the variance
is real but *asymmetric* — California and Colorado have genuine overlays, New York does not — and
(b) an automated denial in Colorado trips a recent, non-federal obligation the model cannot know.

## The obligations (researched, sourced)

- **Federal floor (all states):** ECOA/Regulation B § 1002.9 (30-day notice, specific reasons or
  right to request) + FCRA § 615 (credit-report disclosures). The baseline knows this.
- **Colorado overlay:** the Colorado AI Act (SB 24-205, amended by SB 26-189, operative 2027-01-01)
  requires, on an ADMT/automated adverse decision, a plain-language explanation of the model's role,
  the data used, and a right to data correction and *meaningful human review* — beyond federal.
- **California overlay:** the Holden Act (Housing Financial Discrimination Act of 1977) requires a
  Fair Lending Notice and a specific-reasons statement for 1-4 unit owner-occupied home loans, with
  a broader adverse-action definition than federal.
- **New York:** no material state-specific adverse-action-notice overlay — the correct answer is the
  federal floor alone. Its absence is what makes the swap discriminating.

## What was built (and the honesty around it)

The differentiating obligations are **not in the 242k crawled corpus** (Colorado AI Act: 0 records;
Holden Act present only as DFPI reporting-deadline bulletins). So four records were **hand-curated
from cited primary sources** — `data/state-lending-records.json`, grounded in the CFPB Reg B page,
the FTC FCRA guidance, `leg.colorado.gov/bills/sb24-205`, and the actual DFPI Fair Lending Notice
PDF. They are labelled REVIEW-REQUIRED and are NOT from the annotations pipeline. Built into a
vector index with `scripts/build-curated-index.mjs`; queried by `state-lending-carver-agent` (same
advisor base + verbatim trigger + maxSteps cap as the mini-suite arms). Probe:
`scripts/state-lending-probe.mjs` — one home-improvement-loan denial by an automated model, the
state swapped across CO/CA/NY, obligation never named in the user turn.

To close the data team's gap organically, see `docs/corpus-gaps-for-jurisdiction-demos.md`.

## Result — and it scales

Same request, state swapped, three arms:

| arm | CO AI-Act | CA Holden | NY (federal-only) |
|---|---|---|---|
| baseline | MISS | MISS | clean |
| web search | MISS (0/5 runs) | MISS | clean |
| **state-lending carver** | **YES** | **YES** | **clean** |

Web search **never** surfaced the Colorado AI Act across five runs: given the same Colorado/automated
context, it searches generically ("adverse action", "loan denial"), gets the dominant federal
result, and never thinks to look for a state AI statute. The silent trigger works exactly as the
thesis predicted — the failure looks like success. Carver surfaced CO's *and* CA's overlay with the
federal floor and canonical source links, and correctly gave federal-only for NY.

**The win survives scale.** Re-run with the curated records embedded into a realistic **7,142-record**
haystack of real US consumer-lending regulators (CFPB, FTC, FDIC, Fed, OCC, NCUA, NY DFS, CA DFPI;
neutral regulator-allowlist selection), the Carver arm still hit CO and CA. Direct ranking check: for
a situation-aware query ("automated model denies a home loan in Colorado") the CO AI Act record ranks
**#1 of 7,146**.

## The honest caveats — do not drop these when presenting

1. **It runs on hand-curated records, not the crawled corpus — and the win is 100% dependent on them.**
   This proves *what jurisdiction-tagged coverage unlocks*, not a current capability. Present it as a
   proof-of-concept, paired with the corpus-gaps note, or it is overclaiming. **Measured (2026-07-22):**
   drop the 4 curated records and re-run the swap against the 7,142 real records alone, and the Carver
   arm **collapses to parity** — MISS on Colorado *and* MISS on California, tying baseline and web.

   - *Colorado* — Carver correctly hedges ("I couldn't locate a relevant Colorado AI Act record"); the
     Act is 0 records, so there is nothing to surface. Good discipline, zero advantage.
   - *California* — Carver misses the Holden Act even after thrashing to 12 tool calls. The Act is
     *named* in 5 real DFPI records, but those are annual reporting-deadline bulletins, not the Fair
     Lending Notice obligation. **Present-in-name ≠ present-as-a-usable-obligation.**
   - *Federal floor* survives from the real CFPB/FTC records — confirming the 2 *federal* curated
     records (Reg B, FCRA) were redundant. **Only the 2 state records are load-bearing.**

   So the accurate one-line framing is not "Carver's corpus surfaces state obligations web misses" but
   "*if* the corpus held these state obligations as retrievable requirement records — which it does not
   yet — Carver would surface them." The gap the demo relies on is real and fully load-bearing.
2. **Retrieval depends on a situation-aware query.** On the bare user words ("loan declined, what
   next") the CO AI Act does not rank top-6; it ranks #1 only when the query carries the state +
   automated cue. The agent supplies that from its system-message context, which is realistic — but
   the win rests on the agent searching *with the situation*, not on the corpus alone.
3. **The records are REVIEW-REQUIRED.** Grounded in cited sources, but the Colorado requirements lean
   partly on secondary summaries; verify against the primary statute before any live demo.

## What it means for the whole investigation

Twelve probes. Eleven said "better answers" is not available against `gpt-5.6-sol` on any
publicly-retrievable obligation. The twelfth found the one exception and it is narrow and real: an
**unnamed, recent, jurisdiction-specific obligation that web search does not know to search for and a
curated jurisdiction-tagged corpus surfaces by construction.** That is the shape of the only content
win — everywhere else, the pitch remains operational (speed, reproducibility, provable denominator).

## Run sheet — the state-lending swap

**What it shows.** A loan denied by an automated model. The applicant's *state* silently changes what
the lender legally owes them. A memory-only assistant and a live web-search assistant both give the
federal answer; the Carver-grounded assistant surfaces the state-specific obligation — and correctly
adds nothing for a state that has none.

**Setup** (NOT self-contained — build the index first; needs `OPENAI_API_KEY` and the sibling
`carver-showcase` repo):

```bash
cd mastra-studio-demo
npm run build:domain -- state-lending ../../carver-showcase/data/annotations.jsonl   # ~7,142 real records
npm run build:curated -- state-lending data/state-lending-records.json               # + 4 curated obligations
npm run dev                                                                          # :4111, wait ~25s
```

**Agents (three arms).** `Lending Status — Baseline (no data)` · `Lending Status — Web Search (no
Carver)` · `Lending Status — Carver (grounded)`. Say once: *same model, same base prompt, same trigger
clause, and all three look the applicant up the same way — the only difference is whether it has
Carver's obligation data.*

**The flow — the applicant never states their state.** The applicant asks for their loan status and
gives an applicant ID; the agent calls `lookupApplicant` (a stand-in for auth/CRM) which returns their
file — including their **state** — and then answers. This is the whole point: the state arrives from
the lookup, exactly like a signed-in production user, not from anything the applicant typed. Three
demo applicants, identical loan and identical automated denial, differing only by state:

| Applicant ID | State |
|---|---|
| **CO-1001** | Colorado |
| **CA-1001** | California |
| **NY-1001** | New York |

**Set the scene: this scenario is dated early January 2027.** Say it up front — *"it's just after
New Year 2027."* This is deliberate, not a stray future date: the Colorado AI Act's automated-decision
disclosure duty is **operative January 1, 2027** (as is California's CPPA ADMT rule), so the file's
decision date is 14 Jan 2027 and the Act is freshly in force. We looked for an equivalent state
loan-denial obligation already effective in 2026 to keep the scenario present-day — there isn't a
clean one: this whole regulatory wave is calibrated to Jan 1 2027, and the nearer-term candidates
(Colorado's 2024 rate-cap opt-out, state medical-debt credit bans) are either the wrong topic or
under active federal preemption. So the scene is set in early 2027 by design; frame it as "the law
just took effect — watch which assistant knows." (Corpus/date details:
`docs/corpus-gaps-for-jurisdiction-demos.md`.)

**Live in Studio.** In each of the three agents, type the same thing, swapping only the ID:

> *"Hi, can you check the status of my loan application? My applicant ID is **CO-1001**."*

(If you omit the ID, the agent asks for it.) Run it in Baseline → Web Search → Carver, then swap
**CO-1001 → CA-1001 → NY-1001** and repeat. Nothing about the state is ever typed — the audience watches
it arrive from the lookup.

**Scorecard (rigorous).** `node scripts/lending-status-probe.mjs` runs all three applicants × three
arms and prints a pass/fail grid.

**The one rule — the applicant asks about their status, never names a rule.** The state comes from the
lookup; the applicant never says "does Colorado's AI Act apply?" If a presenter types the obligation
name into the chat, web search finds it and the contrast collapses.

### Beat 1 — Applicant CO-1001 (Colorado): the money shot

All three look up CO-1001, see the denial, and proactively explain what happens next. Baseline and Web
Search give the federal adverse-action notice (Reg B 30-day + reasons; FCRA credit-report rights) —
correct, but incomplete. **Carver** gives the federal notice **and Colorado's AI-Act duty**: because
an automated model made the decision, the applicant is owed a plain-language explanation of the
model's role, the data used, and a right to correct it and to *meaningful human review*, cited to
`leg.colorado.gov`. Say it: *the web agent had the exact same file — Colorado, automated decision —
and never thought to search for a state AI statute. The failure looked like success.*

### Beat 2 — Applicant CA-1001 (California): not a fluke

Switch to CA-1001, same question. Carver now surfaces the **Holden Act** (Fair Lending Notice +
specific-reasons duty for a home loan); baseline and web still give only the federal answer. Different
applicant, different state, different obligation — same silent miss by the other two.

### Beat 3 — Applicant NY-1001 (New York): the control that proves it's real

Switch to NY-1001. All three give the federal answer — and Carver correctly adds **no** state overlay,
because New York has none. This is the beat that proves the annotations do real work rather than the
grounded agent just being verbose: change one applicant, and the output changes exactly where the law
changes, and only there.

### Then show the traces

Studio → Traces. Two spans tell the story on the CO-1001 run: (1) the **`lookupApplicant` result** —
`state: Colorado` — this is the audience proof that the state came from the lookup, not from anything
the applicant typed; (2) the Carver arm's **`searchCarverStateLending` result** — the Colorado AI Act
record with its `leg.colorado.gov` sourceUrl. The web arm's trace shows generic adverse-action web
searches and no Colorado AI statute; the baseline has no obligation retrieval at all.

### Honest framing — SAY THESE, do not oversell

1. **Runs on four hand-curated records, not the live crawled corpus** (the Colorado AI Act is not in it
   yet). It shows what jurisdiction-tagged coverage delivers — a proof of concept, paired with the
   data-team ingest list in `docs/corpus-gaps-for-jurisdiction-demos.md`.
2. **The win rests on the agent searching its index with the situation** (state + automated), which it
   supplies from context — realistic, but not the corpus alone.
3. **The records are curated from cited primary sources and pending legal/data review.**

### If someone asks

*"Couldn't web search find the Colorado AI Act?"* — It can, if you name it. It can't when nobody does.
The applicant didn't ask "does Colorado's AI Act apply?" — they asked "what happens next?" The
obligation is triggered by who they are and how the decision was made, not by the question.

*"Isn't the grounded agent's prompt cueing it to search by state, while the web agent's isn't?"* —
Fair challenge, and it was checked (2026-07-22). The two arms share `ADVISOR_BASE_INSTRUCTIONS` and
the verbatim `ADVISOR_TRIGGER`; earlier the Carver arm's *tool description* also mentioned
"state-level overlays" and "jurisdiction", which the web arm's did not. That asymmetry was tested
three ways and is **not** the cause of the win:

1. The Colorado AI Act **is** web-retrievable — a direct search for the Colorado+AI angle returns
   many detailed sources. The data is not hidden.
2. Given an explicit state-aware nudge ("obligations may vary by state — consider the applicant's
   jurisdiction"), the **web arm still retrieved only federal `consumerfinance.gov` sources** and
   missed it. It never reformulated toward Colorado.
3. With the hint **removed** from the Carver arm (its description now as plain as the web arm's —
   this is the shipped state), the Carver arm **still surfaces CO and CA**.

The mechanism is legitimate: the Carver tool *is* an obligation index, so the agent queries it with
the *situation* and vector search returns the state record because it is in there, tagged to that
situation. The web agent has the same context but, for a naive question, must already suspect a state
statute exists to search for it — and doesn't. With a curated index the situation retrieves the
obligation; with web search the agent must first know the obligation exists. That is the silent
trigger, confound-checked.

## Registered agents (2026-07-22)

Only the two demo-usable scenarios are registered in `src/mastra/index.ts`: **Scenario 1** (regulatory
— `baseline-agent` / `carver-agent`) and the **lending-status demo** (`lending-status-baseline-agent`
/ `lending-status-websearch-agent` / `lending-status-carver-agent`, all sharing `lookupApplicant`).
Everything else — the investment, cyber, lending, and crypto/device/child-safety mini-suite arms, and
the earlier system-message-flow state-lending arms (`advisor-*`, `state-lending-carver-agent`) that
the ID-lookup flow superseded — were measurement exercises; their write-ups are above and their source
files remain in the repo, but they are intentionally unregistered so Studio shows only what demos.

Note: `@mastra/core` retains the `lookupApplicant` function tool alongside the provider-defined
`webSearch` on the web arm (verified 2026-07-22) — the function-tool-dropping hazard did not manifest
in this version, so all three arms share the identical lookup flow.
