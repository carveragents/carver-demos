# Demo run-sheet

Four beats, ~5 minutes. Every query and response below was verified live against the current
build. Run them **in this order** — the sequence is the argument.

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
  one tool: `searchCarverEnforcement` over **6,451** real FTC/SEC/CFTC/CFPB enforcement
  annotations in a LibSQL vector store (OpenAI `text-embedding-3-small`, semantic search).

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

**The point:** this model's baseline is **not** a reckless sales bot — asked point-blank, it
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
