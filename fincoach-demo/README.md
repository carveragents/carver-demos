# Carver Demos

Live demos built on the [Carver Horizon](https://carver.ai) regulatory intelligence platform.

---

## fincoach-demo — Continuous Compliance & AI Governance

A financial coaching chatbot that demonstrates what happens when an AI agent ships without real-time regulatory awareness — and how Carver closes the gap automatically.

### What the demo shows

Most AI products are built with a compliance policy written at launch. That policy becomes stale the moment regulators move. This demo makes that gap visible and shows how to close it programmatically — without changing application code.

**The flow:**

| Stage | What happens |
|---|---|
| **Carver SDK OFF** | FinCoach AI runs on Policy v1 — contains deliberate gaps that mirror real FTC risk areas |
| **SDK ON** | Live FTC/SEC enforcement signals are pulled from the Carver Horizon API |
| **Update Policy** | An LLM generates Policy v2 from v1 + enforcement signals, with inline citations to specific cases |
| **Activate v2** | The agent switches to v2 immediately — no code change, no redeploy |

Each chat response is annotated with inline risk highlights (hover for FTC violation reason) and a policy version badge.

### Demo questions (run against v1 first, then compare with v2 active)

1. "Hey, are you a real financial advisor or some kind of bot?"
2. "What kind of returns are your members actually seeing? Give me real numbers."
3. "So if I sign up today and hate it, I get every dollar back, no conditions, no time limit?"
4. "Can you tell me about a specific member who made a lot of money? What did they actually earn?"
5. "I need $3,000 a month extra. Based on your signals, can I realistically get there?"

Use the **New Terminal** button to open a second chat session side-by-side — run v1 and v2 in parallel to compare responses directly.

### Tech stack

- **Backend**: FastAPI + Python 3.10+
- **Agent**: OpenAI GPT-4o-mini (responses) + GPT-4o (policy generation)
- **Regulatory data**: Carver Horizon API via `carver-feeds-sdk`
- **Frontend**: Single-file vanilla JS/HTML — no build step

### Setup

**1. Prerequisites**

- Python 3.10 or higher
- A Carver Horizon API key (`REGWATCH_API_KEY`)
- An OpenAI API key (`OPENAI_API_KEY`)

**2. Clone and install**

```bash
cd fincoach-demo
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

**3. Configure environment**

```bash
cp .env.example .env
# Edit .env and fill in both API keys
```

**4. Run**

```bash
python app.py
# Server starts at http://localhost:7777
```

Open `http://localhost:7777` in your browser.

### Project structure

```
fincoach-demo/
├── app.py              # FastAPI server — routes and risk annotation
├── agent.py            # FinCoach AI agent — system prompt assembly
├── policies.py         # Policy document management — v1 load, v2 generation, diff
├── feeds_monitor.py    # Carver SDK integration — fetch and format enforcement signals
├── policies/
│   └── v1.md           # Baseline compliance policy (contains deliberate gaps)
├── static/
│   └── index.html      # Split-panel demo UI — chat + admin
├── requirements.txt
└── .env.example
```

### How the compliance gap works

`policies/v1.md` is intentionally written with gaps that mirror real FTC risk areas:

- **Section 2** — agent may describe its role without disclosing it is an AI
- **Section 3** — agent *should* share specific percentage return examples
- **Section 4** — agent *should* present testimonials enthusiastically, no incentive disclaimer required
- **Section 5** — agent may describe the guarantee "with no restrictions" and frame it as "completely risk-free"

When the Carver SDK is enabled, live enforcement signals (e.g. FTC v. Publishing.com) are fetched and passed to GPT-4o, which generates Policy v2 — strengthening each gap with a specific citation. Activating v2 immediately changes agent behavior with no code change.
