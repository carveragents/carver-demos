# Halyard Pay · Policy Updates

A self-contained demo of an AI compliance agent reviewing **five Mastercard SPME releases** (June 2022 → May 2025) and proposing corresponding updates to a hypothetical payment processor's internal policies.

Powered by [Carver Agents](https://carveragents.ai). Halyard Pay is a fictional company; all policies shown are synthetic baselines.

---

## How to experience the demo

There are two ways to go through it:

### 1. Interactive walkthrough — recommended

Open **[`index.html`](./index.html)** in any modern browser.

The site is fully offline-capable; no server required. Bundled inside:

- Five SPME release transitions, each opening into a per-change detail page
- Side-by-side, redline, and raw-diff views for every proposed change
- The original Mastercard PDFs, deep-linked at the exact source page for any cited section
- Eight Halyard Pay policy pages with per-policy mini-timelines

### 2. Five-minute video walkthrough

Watch **[`demo-video.mp4`](./demo-video.mp4)** for a narrated tour of the site.

The video covers the overview, timeline, two verified change examples (§7.2 Ongoing Monitoring, §2.2.3 Service Provider Compliance), and one low-confidence example where the agent flags the extraction for human verification (§8.6.5).

---

## What the agent did

| Stat | Value |
|---|---|
| Releases reviewed | 5 |
| Proposed revisions | 214 |
| Breaking changes | 15 |
| Policies affected | 8 |

The agent runs three stages on each pair of consecutive SPME releases: **detect** changed sections, **classify** severity (breaking / substantive / clarifying / cosmetic), and **propose** corresponding edits to the eight Halyard Pay policies.

---

## What this is *not*

- The Halyard Pay policies are synthetic baselines, not real production text
- All proposed edits are agent-generated and have not been reviewed or approved by anyone
- Nothing in this demo is binding, legal advice, or a recommended course of action
- Mastercard publications are republished under fair-use review purposes from publicly archived versions
