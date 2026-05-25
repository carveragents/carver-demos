# Carver Demos

This repository is the home for all demo applications built on the [Carver Horizon](https://carver.ai) regulatory intelligence platform.

Each demo is self-contained in its own subdirectory with a dedicated README covering setup, usage, and architecture.

---

## Demos

| Demo | Description |
|---|---|
| [fincoach-demo](./fincoach-demo/) | A financial coaching chatbot that demonstrates real-time compliance policy updates via the Carver Horizon API — showing how AI agents stay current with regulatory enforcement signals without code changes (7-layer agent architecture) |
| [fincoach-demo-single-layer](./fincoach-demo-single-layer/) | Single-layer variant of the FinCoach demo — same dynamic policy regeneration from live Carver enforcement signals, but with a simplified single-agent design and admin controls to toggle the SDK, generate v2 policies, and activate/reset at runtime |
| [amicompliant](./amicompliant/) | Prompt sanitisation and evaluation tool that scores user-submitted text against live Carver regulatory signals — surfaces compliance risks, suggests prompt diffs to address them, and demonstrates the Horizon API as a content-validation layer for AI applications |
| [policy-diffs](./policy-diffs/) | POC that converts Mastercard B2B artifact deltas into Credio policy update proposals — illustrating how Carver-driven regulatory diffs can be translated into actionable policy revisions |
| [pred-oracle](./pred-oracle/) | A vertical compliance-intelligence platform for prediction-market operators (Kalshi, Polymarket, CFTC-licensed DCMs) — re-aims Carver's `entry_annotation` regulatory data at GC / CCO / Listing-Risk teams inside platforms |

---

## Adding a New Demo

1. Create a new subdirectory (e.g. `my-demo/`)
2. Include a `README.md` that covers what the demo shows, setup steps, and project structure
3. Add an entry to the table above with a short description
