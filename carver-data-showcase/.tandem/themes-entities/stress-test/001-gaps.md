# Stress-test 001 — compiled gaps (stage-tagged)

All four are **stage `01-spec`** scope (none deferrable to 02-plan, none out-of-scope). Routed to
`stages/01-spec/refinement.md` for a refinement cycle.

| # | Gap | Severity | Spec refs | Stage |
|---|-----|----------|-----------|-------|
| GAP-1 | **Async-batch resumability.** An interrupted poll/fetch of a *successfully submitted* Batch job leaves nothing in `entity_types.csv`, so a re-run submits a **duplicate** Batch job (re-cost, re-wait). Plus the `custom_id → entity-list` map is only "re-derivable from deterministic chunking," but `entity_mentions.csv` has no pinned tie-break, so re-derivation can drift. The classify tool needs: persist the submitted `batch_id` (+ enough to recover the chunk→entity map) so a re-run **resumes** polling/fetching an in-flight job instead of resubmitting; and pin a deterministic total order for chunking. | High | §4.4, §4.5, §3.1 | 01-spec |
| GAP-2 | **Deck slide composition undecided.** §5.4 implies all 3 charts + tiles + callout on one fixed 960×540 slide but never decides the slide's concrete content/layout; existing deck slides fit ~2 half-width charts. "Define the deck slide / what each surface shows" is Stage-01 scope (task §4). Decide what the slide shows (all three vs a curated subset; where tags/diversity sit) and a legible arrangement. | Medium | §5.4, task §4 | 01-spec |
| GAP-3 | **Coverage % surfacing inconsistent.** §3.8/§8.3 say coverage % (tags 88.5% / entities 92.5%) is "derived live in the apps," but the §5.2 tile inventory omits it — computed but never displayed. Resolve: either add a coverage tile/line (§5.2) or drop the derived-live coverage claim. `goal.md` flags coverage as a headline fact. | Low | §3.8, §5.2, §8.3 | 01-spec |
| GAP-4 | **"mentions" definition ambiguous.** §3.1 defines `count` as "number of records that mention it" while §2.1 accumulates a `Counter` over each record's entity list (per-occurrence). Make the two agree and state precisely whether a within-record duplicate counts once or per-occurrence (load-bearing: it's the leaderboard/breakdown weight). | Low | §3.1, §2.1 | 01-spec |

**Decision:** REFINE stage `01-spec` (no downstream stage exists yet, so no cascade). After
re-convergence, re-stress-test; if clean, advance to `02-plan`.
