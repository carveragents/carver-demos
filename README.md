# Carver Demos

This repository is the home for all demo applications built on the [Carver Horizon](https://carver.ai) regulatory intelligence platform.

Each demo is self-contained in its own subdirectory with a dedicated README covering setup, usage, and architecture.

---

## Demos

| Demo | Description |
|---|---|
| [fincoach-demo](./fincoach-demo/) | A financial coaching chatbot that demonstrates real-time compliance policy updates via the Carver Horizon API — showing how AI agents stay current with regulatory enforcement signals without code changes |
| [policy-diffs](./policy-diffs/) | POC that converts Mastercard B2B artifact deltas into Credio policy update proposals — illustrating how Carver-driven regulatory diffs can be translated into actionable policy revisions |
| [pred-oracle](./pred-oracle/) | A vertical compliance-intelligence platform for prediction-market operators (Kalshi, Polymarket, CFTC-licensed DCMs) — re-aims Carver's `entry_annotation` regulatory data at GC / CCO / Listing-Risk teams inside platforms |

---

## Adding a New Demo

1. Create a new subdirectory (e.g. `my-demo/`)
2. Include a `README.md` that covers what the demo shows, setup steps, and project structure
3. Add an entry to the table above with a short description
