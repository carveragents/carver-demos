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
