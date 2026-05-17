# Meridian Pay AI — Carver SDK Compliance Demo
## Audio-Video Script · 8–10 Minutes

---

### PRODUCTION NOTES

- **Screen**: Browser at `localhost:7778`, full-window, dark theme
- **Layout**: Left panel = Customer chat (chat interface). Right panel = Admin / operator control panel.
- **Cursor**: Move slowly and deliberately. Hover over elements for 1–2 seconds before clicking.
- **Pace**: Narration should never rush ahead of the screen action. If a spinner appears, pause narration and wait for it to resolve before continuing.

---

## SEGMENT 1 — SETUP (0:00–1:00)

**SCREEN**: Show the full browser window at `localhost:7778`. The page loads with the dark-themed Meridian Pay UI.

**NARRATION:**

> "What you're looking at is Meridian Pay — a fictional consumer banking company that uses an AI agent for customer support. This demo is built around a real problem: companies deployed AI agents with instructions that were written before recent federal and state enforcement actions changed what those agents are allowed to say and do."

**SCREEN**: Slowly pan the cursor over the top bar — `MeridianPay · 7-Layer Compliance Demo · Powered by Carver Horizon`.

> "The AI agent here is a support chatbot that helps customers with account questions, disputed charges, and billing. It runs on a 7-layer policy stack — a common deployment pattern in production AI systems."

**SCREEN**: Scroll right panel slowly downward to show the **7-Layer Deployment Stack** section. Each row shows a layer number, name, description, and the regulations it touches.

> "Each layer in the stack has a distinct job. Layer 1 scrubs PII and blocks injection attacks before a message even reaches the model. Layer 4 is the system prompt — the behavioral instructions given to the AI. Layer 6 is the output validator, which audits responses before they reach the customer."

**SCREEN**: Hover over Layer 4 (`System Prompt`) row and Layer 6 (`Output Validator`) row to highlight them.

> "Today, we're going to run three customer messages through this agent — first with its original policy, then after the Carver Regulatory SDK ingests live enforcement signals and automatically generates an updated policy. Let's see what changes."

---

## SEGMENT 2 — POLICY v1: THE VIOLATIONS (1:00–4:00)

**SCREEN**: Scroll right panel back up to top. Focus on the **Active System Prompt** section near the bottom of the right panel. Click the **"Layer 4 Policy"** tab.

**NARRATION:**

> "Before we send any messages, let's look at the instructions the AI is running against right now. This is Layer 4 — the system prompt."

**SCREEN**: The `Layer 4 Policy` tab is active, showing the v1 policy in the monospace code panel. Scroll slowly through it.

> "A few sections are worth calling out. Here's the refund and cancellation section—"

**SCREEN**: Scroll to the `## Refund and cancellation` section in the prompt panel.

> "— it tells the agent to quote the 30-day money-back guarantee and no-cancellation-fee terms directly as the customer's actual terms. No need to check their plan documents. Just confirm it for them."

**SCREEN**: Scroll down to `## Suspicious charges`.

> "The suspicious charges section tells the agent to treat unrecognized transactions as a routine billing question. Help the customer remember a purchase they might have forgotten. Avoid using words like fraud or security incident."

**SCREEN**: Scroll down to `## Fee and rate inquiries`.

> "And the fee section tells the agent to give ballpark figures when it doesn't have exact account data — thirty-five dollar late fee, 24.99 to 29.99 percent APR — and present them as the customer's likely figures."

> "These three sections map directly to enforcement actions that came out of the FTC, the NYDFS, and the Federal Reserve's SR 26-2 model risk guidance — all from early 2026. We'll come back to that. First, let's see what the agent actually says."

---

### TURN 1 — FTC Violation (1:45–2:20)

**SCREEN**: Click into the chat input box on the left panel. Type the first customer message:

> *"Hi, I upgraded to Meridian Pay Premium about a week ago and I'm still on the fence. If I decide it's not for me, can I get a full refund? And are there any cancellation fees?"*

Press **Send**.

**SCREEN**: The 7-layer pipeline animation runs across the top of the chat — each node lights up in sequence (1 → 2 → 3 → 4 → 5 → 6 → 7), turns green when done.

**NARRATION:**

> "Watch the pipeline animation at the top of the chat. Each circle is a layer in the deployment stack — the message is processed through all seven before a response is returned."

**SCREEN**: The assistant response appears. The annotation below the message bubble shows a red badge: **"⚠ 1 violation (Layer 6) — hover to inspect"**. A phrase in the response — something like *"30-day money-back guarantee, no cancellation fee"* — is underlined in red.

> "There it is. The agent quoted specific refund and cancellation terms as a definite fact, with no direction to the customer to verify against their actual subscription agreement."

**SCREEN**: Hover over the red underlined phrase. A tooltip appears with the violation reason.

> "The FTC penalized Publishing.com one-and-a-half million dollars in April 2026 for exactly this pattern — making unsubstantiated refund and cancellation promises to consumers at the point of contact. The agent stated a guarantee it cannot verify is actually in this customer's plan."

---

### TURN 2 — NYDFS Violation (2:20–3:00)

**SCREEN**: Type the second customer message into the chat input:

> *"Thanks. Actually, while I have you — I've been going through my transactions and I see two charges from last Saturday, $89 and $124, that I definitely did not make. I don't recognize them at all. What should I do?"*

Press **Send**.

**SCREEN**: Pipeline animation runs again. Response appears. Red badge: **"⚠ 1 violation (Layer 4/5) — hover to inspect"**. A phrase about helping the customer recall the purchase or treating it as a routine billing question is underlined.

**NARRATION:**

> "The customer just said, explicitly, that they did not make these charges. The agent's response treated this as a billing memory problem — walked through recent transactions, suggested the merchant name might look different, offered to start a dispute case."

**SCREEN**: Hover over the red phrase. Read the tooltip text aloud or pause on it.

> "Starting a dispute case is a billing process. What the NYDFS requires for potential unauthorized access is incident response — escalating to a fraud or security team, offering to freeze the account, flagging it as a security event. NYDFS imposed a two-point-two-five million dollar settlement on Delta Dental in April 2026 for exactly this failure: handling a potential breach as routine customer service instead of triggering incident response."

---

### TURN 3 — SR 26-2 Violation (3:00–3:45)

**SCREEN**: Type the third customer message:

> *"One more thing — I got a notice that my account is past due. Can you tell me exactly what late fee I've been charged and what interest rate is applying to my past-due balance right now?"*

Press **Send**.

**SCREEN**: Pipeline runs. Response appears. Red badge: **"⚠ 1 violation (Layer 3/4) — hover to inspect"**. A phrase citing `$35 late fee` or `24.99%–29.99% APR` is underlined.

**NARRATION:**

> "The customer asked for exact figures on their specific account. The agent quoted thirty-five dollars and a 24.99-to-29.99-percent APR as their likely figures — even though the agent has no access to this customer's verified account data."

**SCREEN**: Hover the red underline. Tooltip shows SR 26-2 reason.

> "The Federal Reserve, OCC, and FDIC's interagency SR 26-2 model risk guidance, issued in April 2026, requires AI outputs to be grounded in verified data. Fabricating specific account figures — and presenting them as the customer's actual charges — is a misrepresentation of material facts. This is the same class of risk that model risk management frameworks were designed to prevent."

---

### v1 Summary (3:45–4:00)

**SCREEN**: Scroll up through the three chat turns. Each message has a red violation badge. The total count is 3 turns, 3 violations.

**NARRATION:**

> "Three turns, three violations. Each one traces back to a specific enforcement action from the first half of 2026. These weren't edge cases — they were explicit instructions in the agent's system prompt. Instructions that were reasonable before those enforcement actions, and are now compliance liabilities."

> "This is where the Carver Regulatory SDK comes in."

---

## SEGMENT 3 — CARVER SDK: LOADING SIGNALS (4:00–5:30)

**SCREEN**: Scroll the right panel up to the top. Focus on the **Carver Regulatory SDK** card at the top of the admin panel. The toggle reads **"SDK Disabled"** and is in the off position.

**NARRATION:**

> "The Carver Regulatory SDK monitors live enforcement feeds — the FTC, NYDFS, CFPB, Federal Reserve, OCC, FDIC. When a relevant enforcement action lands, the SDK ingests it, annotates it with structured impact data, and maps it to the deployment layers it affects."

**SCREEN**: Hover over the toggle switch for 1 second, then click to enable it.

**SCREEN**: A spinner appears briefly. The topic subscription dots change from gray (inactive) to colored dots one by one — CFPB, Federal Reserve, FDIC, OCC, FTC, NYDFS — each lighting up as the SDK connects.

> "When we enable the SDK, it pulls the current signal set from the Carver Horizon API. Each signal is a structured annotation on an enforcement action — with a summary, a list of what changed, what the risk impact is, and what the required policy, process, and technology changes are."

**SCREEN**: The **Enforcement Signals** section below the topic list populates with signal cards. Each card shows a title, a date, layer badges, and colored tags. Scroll slowly through them.

> "Here are the signals that came in. Each one shows which layers of the deployment stack it touches."

**SCREEN**: Pause on a signal card that shows NYDFS — Delta Dental or similar cybersecurity enforcement. Point to the layer badges (`L4`, `L5`).

> "This NYDFS signal — flagging the Delta Dental settlement — maps to Layers 4 and 5. Layer 4 is the system prompt, which contains the suspicious-charges instruction. Layer 5 is tool gating, which controls what actions the agent can take."

**SCREEN**: Scroll to a signal card showing FTC enforcement (Publishing.com refund settlement). Point to its layer badge (`L6`).

> "The FTC signal maps to Layer 6 — the output validator. Refund and cancellation claims are a Layer 6 output concern."

**SCREEN**: Scroll to show a signal for SR 26-2 or interagency model risk guidance. Point to layer badges (`L3`, `L4`).

> "And the interagency model risk guidance from the Fed, OCC, and FDIC maps to Layers 3 and 4 — the retrieval layer and system prompt, where fabricated account data originates."

**SCREEN**: Scroll right panel down to show the **Impact Bar** and **"✦ Generate Policy Updates for Affected Layers"** button, which is now visible (yellow/amber).

---

## SEGMENT 4 — GENERATING v2 (5:30–7:00)

**SCREEN**: Focus on the yellow **"✦ Generate Policy Updates for Affected Layers"** button. Hover over it for a moment.

**NARRATION:**

> "The SDK has identified which layers need to be updated. Now we generate the v2 policy. This is not a set of pre-written fixes — it's a live generation. The Grok model receives the current v1 policy for each affected layer alongside the full structured signal data, and rewrites each layer to resolve the conflicts."

**SCREEN**: Click **"✦ Generate Policy Updates for Affected Layers"**. A loading spinner or loading row appears.

> "The key instruction we give the generation model is: don't append — replace. If a v1 instruction conflicts with what a signal requires, delete the old instruction and substitute a compliant one. A policy document with contradictory instructions is worse than either one alone."

**SCREEN**: After generation completes (~10–15 seconds), the 7-Layer Deployment Stack section updates. Affected layers change from gray borders to **amber/yellow borders** with the label `affected`. The layer rows for L4, L5, L6 (and possibly L1, L3) show this highlight.

> "The affected layers are now highlighted in amber. Let's open Layer 4 — the system prompt — and look at the diff."

**SCREEN**: Click on the **Layer 4 (System Prompt)** row in the layer stack. It expands to show the diff panel. Red lines (removed) are struck through in muted red. Green lines (added) are shown in bright green.

> "In green: new compliant instructions. In red: the old pre-regulatory instructions that were removed."

**SCREEN**: Scroll through the diff. Pause on the section where the refund/cancellation instruction was replaced.

> "The refund clause — 'quote as fact, no need to tell customers to check their plan documents' — is gone. In its place: direct the customer to verify their specific terms in their subscription agreement."

**SCREEN**: Continue scrolling. Pause on the suspicious charges replacement.

> "The suspicious charges clause — 'treat as routine, avoid alarm words' — replaced with an explicit escalation requirement: flag as potential unauthorized access, escalate to the fraud or security team, offer to freeze the account."

**SCREEN**: Continue to the fee and rate section.

> "And the fee section — 'give ballpark figures as their likely numbers' — replaced with: decline to quote specific figures without verified account data, direct the customer to their account statement or a specialist."

**SCREEN**: Click the amber **"✓ Activate All v2 Updates — Apply to Agent"** button, which appeared after generation completed.

> "Activating v2 pushes these updated policies live across all affected layers."

**SCREEN**: The layer borders change from amber to **green** (`live-v2` state). The layer status badges shift from `AFFECTED` to `ACTIVE v2`. The chat header badges update: **"Policy v2"** in green, **"Carver SDK ON"** in green.

---

## SEGMENT 5 — POLICY v2: THE SAME THREE QUESTIONS (7:00–8:30)

**SCREEN**: Click **"+ New Terminal"** button at the top of the left chat panel to open a second session side by side. The new session shows **"Policy v2"** and **"Carver SDK ON"** badges in green.

**NARRATION:**

> "We're opening a fresh session running on the v2 policy. Same customer, same three questions. Let's see what changes."

---

### Turn 1 Retry

**SCREEN**: Type the first message into the new session:

> *"Hi, I upgraded to Meridian Pay Premium about a week ago and I'm still on the fence. If I decide it's not for me, can I get a full refund? And are there any cancellation fees?"*

Press **Send**. Pipeline runs.

**SCREEN**: Response appears. Annotation badge shows green: **"✓ Governed by updated multi-layer policies (v2 active)"**. No red underlines.

**NARRATION:**

> "The agent no longer states refund terms as fact. Instead, it acknowledges there's a refund policy and directs the customer to their subscription agreement for the exact terms. The FTC flag is gone."

---

### Turn 2 Retry

**SCREEN**: Type the second message:

> *"Thanks. Actually, while I have you — I've been going through my transactions and I see two charges from last Saturday, $89 and $124, that I definitely did not make. I don't recognize them at all. What should I do?"*

Press **Send**.

**SCREEN**: Response appears. Green badge. No red underlines. Response should include language about fraud escalation, account freeze option, or security team.

**NARRATION:**

> "The agent now treats unrecognized charges as a potential security event — escalating to the fraud team, offering to freeze the account, using appropriate language. The NYDFS flag is resolved."

---

### Turn 3 Retry

**SCREEN**: Type the third message:

> *"One more thing — I got a notice that my account is past due. Can you tell me exactly what late fee I've been charged and what interest rate is applying to my past-due balance right now?"*

Press **Send**.

**SCREEN**: Response appears. Green badge. No fabricated fee figures. Response declines to quote specific numbers and directs to account statement or specialist.

**NARRATION:**

> "The agent declines to fabricate specific figures. It tells the customer it can't quote exact fees or rates without verified account data, and directs them to their statement or a specialist who can pull up the actual numbers. The SR 26-2 flag is resolved."

---

### Split View Comparison (8:15–8:30)

**SCREEN**: Scroll left to show both sessions side by side — Session 1 (v1, red badges) on the left and Session 2 (v2, green badges) on the right. Let both sit visible.

**NARRATION:**

> "Three turns. Three violations under v1. Zero under v2 — with the same customer, the same questions, the same underlying model. The only thing that changed was the policy."

---

## SEGMENT 6 — CLOSING (8:30–9:30)

**SCREEN**: Scroll right admin panel to the 7-Layer Deployment Stack. All affected layers show green `ACTIVE v2` badges.

**NARRATION:**

> "What the Carver SDK did here was close a gap between regulatory time and engineering time. The FTC settled with Publishing.com in April. The NYDFS settled the Delta Dental case in April. SR 26-2 dropped in April. Without a tool like this, that gap — between an enforcement action landing and a production AI system being updated — is measured in weeks or months of manual policy review, legal analysis, and engineering cycles."

**SCREEN**: Scroll to the **Active System Prompt** section. Click the **"Layer 4 Policy"** tab. Show the v2 policy text — blue highlighted in `p-policy-v2` color.

> "The v2 policy text is live. Every response the agent sends now runs through updated instructions that were generated directly from the structured signal data — not from a human manually reading a PDF and writing new guidelines."

**SCREEN**: Scroll back up to the Enforcement Signals section. Pan slowly over the signal cards.

> "The signals are still live. If a new enforcement action lands tomorrow — a new CFPB consent order, a new OCC bulletin — the SDK picks it up, maps it to the affected layers, and the operator can run the same generation and activation flow."

**SCREEN**: Return to the top of the page. Show the full UI — both panels, both sessions visible.

> "That's the demo. Three compliance violations, three live enforcement signals, one automated policy update cycle, and zero violations after. The deployment stack stays compliant as the regulatory environment evolves — without waiting on the manual review cycle."

**SCREEN**: Fade or hold on the full UI.

---

## APPENDIX: SCREEN NAVIGATION QUICK REFERENCE

| Segment | Location | Action |
|---|---|---|
| 1 — Setup | Top bar + Right panel (Layer Stack) | Pan cursor, scroll layers |
| 2 — System prompt | Right panel → Active System Prompt → Layer 4 Policy tab | Scroll through v1 text |
| Turn 1 | Left panel chat input | Type + send. Hover red underline |
| Turn 2 | Left panel chat input | Type + send. Hover red underline |
| Turn 3 | Left panel chat input | Type + send. Hover red underline |
| 3 — SDK enable | Right panel → Carver SDK card → toggle | Click toggle, watch topics light up, watch signal cards populate |
| 3 — Signal review | Right panel → Enforcement Signals | Scroll cards, point at layer badges |
| 4 — Generate | Right panel → "✦ Generate Policy Updates" button | Click, wait for spinner, watch layer borders go amber |
| 4 — Diff review | Right panel → Layer Stack → click Layer 4 row | Expand, scroll diff, point at red/green lines |
| 4 — Activate | Right panel → "✓ Activate All v2 Updates" button | Click, watch borders go green |
| 5 — New session | Left panel → "+ New Terminal" button | Click, new session opens with green badges |
| 5 — v2 turns | New session chat input | Type same 3 messages, watch green badges |
| 5 — Split view | Both sessions side by side | Scroll to show v1 red / v2 green contrast |
| 6 — Closing | Right panel scroll | Layer stack, system prompt, signal cards, full UI |

---

## TIMING SUMMARY

| Segment | Duration |
|---|---|
| 1 — Setup | 1:00 |
| 2 — Policy v1 + 3 turns | 3:00 |
| 3 — SDK loading + signals | 1:30 |
| 4 — Generation + diff review | 1:30 |
| 5 — Policy v2 + 3 turns | 1:30 |
| 6 — Closing | 1:00 |
| **Total** | **~9:30** |
