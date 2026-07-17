# Carver updates tool — design

**Date:** 2026-07-16
**Status:** approved
**Builds on:** [2026-07-16-carver-aware-agent-design.md](2026-07-16-carver-aware-agent-design.md)

## Goal

Give the grounded agent a second capability: **what a regulator published recently**, sourced
from Carver's annotation dataset. This upgrades the demo's central argument from *"the
grounded agent is more precise"* to *"the baseline cannot know this at all."*

## Why this is a stronger contrast than the topic lookup

The existing sector-lookup contrast is soft. A bare LLM plausibly knows the SEC is in
Financials, so grounding buys jurisdiction precision and provenance — real, but arguable.

Recent regulatory activity is a **hard epistemic wall**. The dataset is overwhelmingly newer
than any model's training cutoff:

| Year | Records |
|---|---:|
| 2026 | 125,882 |
| 2025 | 56,584 |
| 2024 | 18,809 |

There is no fluency path to "what did the FCA publish in June 2026". The baseline's only
options are refusal or fabrication — and the Reykjavik case already established which one it
reaches for.

## Source data

`carver-showcase/data/annotations.jsonl` — 1.7 GB, 244,545 records, snapshot 2026-07-06. One
record per regulatory document, LLM-annotated. The fields that matter:

| Field | Populated | Use |
|---|---:|---|
| `classification.metadata.title` | 95.4% | What the document is |
| `reconciled_published_date.date` | 100% | The date — the whole point |
| `scores.impact.{label,score}` | 100% | Triage signal |
| `scores.urgency.label` | 100% | Triage signal |
| `metadata.impact_summary.what_changed` | 87.8% | The substance |
| `metadata.impact_summary.why_it_matters` | 87.8% | The substance |
| `metadata.impact_summary.key_requirements` | 80.0% | Obligations |
| `classification.regulatory_source.name` | 93.7% | Attribution |
| `classification.jurisdiction.country` | 75.7% | Disambiguation |
| `metadata.tags` | 88.5% | Keyword surface |

**The join is already done.** Records carry `topic_id`; our existing 150-topic fixture kept
`topicId`. 145 of 150 topics have annotations (40,627 total). The acronym/jurisdiction work
from the previous design carries over untouched.

## Architecture

Mirrors the existing split exactly — pure logic separate from the Mastra wrapper, so tests
never load the framework.

```
data/carver-updates.json          vendored fixture (~900 KB)
  ↑ scripts/build-updates.mjs     deterministic, byte-identical rebuilds
src/mastra/tools/
  carver-update-search.ts         pure: load + filter + sort        ← tested
  carver-update-tool.ts           createTool + Zod schemas
  carver-topic-search.ts          (existing) matcher — REUSED for name resolution
src/mastra/agents/carver-agent.ts two tools now
```

### Name resolution reuses the tested matcher

`searchCarverUpdates` does **not** make the agent chain two tool calls. It resolves the
`regulator` argument through the existing `searchTopics` best-tier-wins matcher to get
`topicId`s, then filters updates by them.

This is the load-bearing decision. It means acronym handling, and the ambiguity behaviour
that took real work to get right, come free and stay consistent between both tools. Ask for
"the SEC" and the updates tool can still surface that five jurisdictions match, because that
logic already exists and is already under test.

## Fixture selection

Vendoring all 40,627 records for our topics would be ~38 MB. This is a canned POC demo, so
the fixture stays lean.

| Rule | Records |
|---|---:|
| Marquee 21 regulators × 30 most recent | ~630 |
| Remaining 124 topics × 3 most recent | ~372 |
| **Total** | **~1,000 (~900 KB)** |

**Selection is neutral: recent-first, per topic.** Records are *not* selected by matching the
planned demo questions. Cherry-picking the demo *questions* is fine — it is a scripted POC.
Cherry-picking the *fixture* to those questions is not: it would collapse the first time
anyone asked something adjacent, which is exactly when a demo gets asked something adjacent.

The demo script is therefore derived from what the built fixture actually supports, verified
live against the running agent — not from what the design hoped would work.

### Filters

- Drop records with missing/unparseable dates (109 across our topics).
- Drop records dated in the future relative to the snapshot (~113; forward-dated junk).
- Truncate `keyRequirements` to 3 and `whatChanged`/`whyItMatters` to keep records ~900 B.

### Known gaps

5 of our 150 topics have zero annotations: Clean Hydrogen Partnership, EUBOF, MoHUA, MPVA,
PPC. They correctly report no updates — a real absence, not a bug.

## Tool

```ts
searchCarverUpdates({
  regulator: string,   // resolved via searchTopics
  keyword?: string,    // optional, over title + tags + whatChanged
  limit?: number,      // default 5
})
→ {
  matchCount: number,           // true total, before limit
  ambiguousRegulators?: [...],  // set when the name resolves to >1 jurisdiction
  updates: [{ title, date, updateType, regulator, country,
              impact, impactScore, urgency, whatChanged, whyItMatters,
              keyRequirements, tags }]
}
```

`topicId` is stripped from output, as in the topic tool — it is a join key, not information.

Sort: **date descending**. "Recent" is the entire proposition; any other default order
undercuts it.

## The honesty fix this forces

`BASE_INSTRUCTIONS` currently reads:

> "...answers questions about financial and government regulatory bodies — which sector or
> industry a given body belongs to."

That scopes the shared prompt to *sector lookup*. Ask both agents "what did the FCA publish
in June?" under that prompt and the baseline is failing a question its own instructions never
invited. That is sandbagging, and it would invalidate the comparison.

The shared prompt broadens to cover recent regulatory activity as well, so the baseline gets
a fair shot at the question and **still** cannot answer it. The wall must be the training
cutoff, not a prompt we wrote. This is the same principle as the original design's "the
baseline must not be sandbagged" — the prompt has to keep pace as the demo grows.

## Testing

TDD on the pure functions in `carver-update-search.ts`. No Mastra import, no network.

1. Returns updates for a regulator, newest first
2. Keyword filters over title
3. Keyword filters over tags
4. Keyword filters over whatChanged
5. Keyword is case-insensitive
6. An ambiguous regulator reports every jurisdiction rather than picking one
7. A regulator with no annotations returns zero, not an error
8. An unknown regulator returns zero, not a guess
9. `limit` truncates `updates` but `matchCount` reports the true total
10. Empty regulator returns zero

## Error handling

Fixture loads once at module scope. A missing or malformed file throws at `mastra dev` boot,
not mid-demo — same as the topic tool.

## Out of scope

- Live API access (`CARVER_API_KEY` still returns 401)
- Semantic/vector search — substring over a ~1,000-record fixture is sufficient here
- Aggregation across regulators ("who is active on AI?")
- Compliance-date reasoning (`compliance_date` is only 8.8% populated)

## The demo, escalating

1. **Sector lookup** — baseline plausible, grounded precise and jurisdiction-aware
2. **"What's new at the FCA?"** — baseline *cannot know*; grounded cites dated documents
3. **Reykjavik Bicycle Authority** — baseline fabricates; grounded reports absence
