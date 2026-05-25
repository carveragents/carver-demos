# Phase 1 Demo Runbook (SPME)

## Goal

A 5-minute walkthrough that lets a Credio reviewer answer:

1. **Is the change detection right?** — were the right Mastercard SPME deltas surfaced, and are the materiality scores honest?
2. **Is the impact mapping plausible?** — do the affected Credio policies match what a real compliance person would update?
3. **Would they accept the proposed Credio edit?** — does the new `policy.md` / `rules.yaml` read like a clean, citation-grounded update?

If the answer to all three is "mostly yes" — the POC has done its job and we move to Phase 2 (Mastercard Rules).

## Setup (once, before the meeting)

```bash
# Confirm clean state
cd /path/to/policy-diffs
uv sync
cp .env.example .env  # if not done
# Edit .env, populate OPENAI_API_KEY
set -a; source .env; set +a

# Run the full pipeline (~20–30 min, ~$5–$15 LLM cost)
uv run python -m pipeline.cli run-phase --artifact spme
uv run python -m pipeline.cli render-site --artifact spme
uv run python -m pipeline.cli render-pdfs

# Open the demo
open credio-policies/dist/timeline.html
```

After this, change records under `artifacts/spme/<from>_to_<to>/changes/` capture every proposed edit, and the static demo site is at `credio-policies/dist/`. The policy files in `credio-policies/policies/` stay pinned to the v1 baseline; proposed updates live inside the change records and are visible through the timeline → detail walk-through.

## Walkthrough script (5 minutes)

### 1 · Land on the timeline (30s)

> "This is what we built. Five SPME version transitions across three years. Each row is one Mastercard publication update, with materiality counts colour-coded — red for breaking changes, orange for substantive, yellow for clarifying."

Point out:
- Date range covered (2022-06 → 2025-05, six published versions of SPME)
- The materiality breakdown — most refreshes have a mix; not every change is breaking

### 2 · Drill into the most-loaded transition (1m)

Pick whichever transition has the most red/breaking badges (likely the 2024-09 → 2025-05 yearly refresh).

> "Click into a transition and you see the change-cards feed. Each card is one Mastercard section that changed, summarised in plain English, with the Mastercard section ID and the Credio policy folders it affects."

Point out:
- The summary is one paragraph, written by the classifier from the actual SPME diff
- The cited section IDs trace back to real Mastercard text — nothing is invented
- One card may affect multiple Credio policies (the mapper tries to be precise)

### 3 · Open the headline change (2m)

Click into the first breaking change.

> "Here's the detail page. Three tabs."

**Side-by-side tab (default):**

> "Left column is the Mastercard SPME section, with word-level redline showing exactly what Mastercard changed. Right column is each affected Credio file — the YAML thresholds and the markdown narrative — also redlined. The 'Why these edits?' footer ties them together: this is what changed and why we changed our policy."

**Redline tab:**

> "This is what compliance reviewers see — the Credio policy.md as a Word-style track-changes document. No engineering vocabulary. No diff syntax. Just the policy in red and green."

**Raw diff tab:**

> "And for engineers, here's the underlying patch in unified-diff format."

### 4 · Look at one updated policy (1m)

The proposed *after* state for a policy lives inside its change record and the detail page's Redline tab. The rendered PDFs in `credio-policies/dist/policies/<area>.pdf` are the baseline (v1) policies that compliance distributes today.

> "The yaml is what Credio's agents actually consume. The markdown is what compliance distributes. The Redline tab shows what each Mastercard refresh would change in the policy if accepted — same content as the markdown, formatted as track-changes."

### 5 · Phases 2 and 3 preview (30s)

> "Same pipeline, different artifacts. Phase 2 will run against Mastercard Rules — broader scope, more sections. Phase 3 will run against the Chargeback Guide — narrowest, deepest. The pipeline doesn't change; the prompts and the synthetic Credio repo do."

## What to listen for

Capture in the feedback template below as you go:

- **Misclassified changes:** which substantive cards should have been clarifying (or vice versa)?
- **Missed mappings:** Mastercard changes that affect a Credio policy we didn't touch.
- **Wrong mappings:** Mastercard changes mapped to a Credio policy that shouldn't be affected.
- **Bad LLM proposals:** policy edits that are factually wrong, contradict existing policy text, or read like SPME translation rather than internal compliance writing.
- **Presentation issues:** anything in the static site that's confusing, broken-looking, or misses the point.
- **Phase 2 / 3 wishes:** what they'd want us to surface against Mastercard Rules and the Chargeback Guide.

## Captured feedback template

```
DATE:
REVIEWER:
TRANSITION (s) reviewed:

Misclassified changes:
-

Missed mappings:
-

Wrong mappings:
-

Bad LLM proposals:
-

Presentation issues:
-

Things they want for phase 2:
-

Open questions / pushback:
-
```

## Internal dry-run requirement

Do not show this to Credio until at least one internal reviewer has walked the demo end-to-end and the feedback template has been filled out. Time-box the dry-run to 30 minutes; integrate notes into either prompt edits, baseline policy edits, or presentation tweaks.
