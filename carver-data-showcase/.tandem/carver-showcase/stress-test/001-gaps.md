# Stress-test 001 — compiled gaps (stage 01-spec)

| # | Gap | Stage | Severity |
|---|---|---|---|
| G1 | Committed snapshot (60K contiguous slice) is ~99% Finance — **Medical Devices = 0 records, Data protection ≈ 2%** — so the spec's category→topic RANGE view (§6.2 v2) and category-sliced coverage (§7.1) cannot demonstrate range across the 3 categories (the #1 objective). | 01-spec | **High** |
| G2 | `category` source (A3) collapses to 100% "Uncategorized": not in the payload, null in the topic catalog field, and no sidecar is committed. A real topic→category map IS recoverable via `/api/v1/feeds/categories/{id}/topics` (direct GET, sanctioned). | 01-spec | **High** |
| G3 | §2.1 names `reconciled_published_date.value`; the real field is `date`. Minor accuracy fix. | 01-spec | Low |

**Resolution:** the data foundation has been rebuilt into a category-stratified snapshot and a
catalog-sourced category map already exists (`data/annotations.jsonl`, `data/topic_categories.csv`).
The spec must be refined to describe this new foundation and adopt catalog-sourced category.
Routed to `stages/01-spec/refinement.md`.
