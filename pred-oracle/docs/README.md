# Pred-Oracle — Documentation Index

This is the reference index for the Pred-Oracle repository. It points to the documents that contain the actual content — start here, jump from here.

> **Repo status:** Demo-spec phase. Strategy doc complete; demo specs drafted in [`specs/`](specs/); production specs deferred to [`specs/future/`](specs/future/). No application code yet. Python 3.10 runtime target.

---

## Orient yourself

| If you are... | Read this first |
|---|---|
| New to the project | [`product-strategy.md`](product-strategy.md) — canonical strategy doc, self-contained |
| The repo's top-level README reader | [`../README.md`](../README.md) — one-page summary and folder map |
| An agent / contributor working in this repo | [`../CLAUDE.md`](../CLAUDE.md) — conventions, sub-agents, superpowers usage |

---

## Documents

### Strategy

- [`product-strategy.md`](product-strategy.md) — **canonical strategy artifact**. Market context, the five product modules (α, β, γ, δ, ε), V1 scope, sequencing, pricing, the shared data spine, risks/assumptions, success metrics, and (in Appendix A) the Carver `entry_annotation` data-model schema that Pred-Oracle consumes. Read § 1, 2, 8, 9 for buy-in; § 3, 4, 5, 6 for spec/engineering scoping.

### Demo specs (active build target)

- [`specs/`](specs/) — specs for the **Pred-Oracle demo**: a static web walkthrough taking a prospect through α, γ, β use cases on real Carver data. Start at [`specs/README.md`](specs/README.md).
- [`specs/future/`](specs/future/) — production-grade V1 specs deferred until a paying design partner is signed. Not active.

### Development

- [`development.md`](development.md) — Python 3.10 environment, virtualenv usage, and the placeholders for tooling decisions that will be filled in when V1 scoping begins.

### Lessons & sessions

- [`LESSONS.md`](LESSONS.md) — running log of session notes and lessons learned. Keep current.

---

## Where future docs will live

| Path | Purpose | Trigger to create |
|---|---|---|
| `docs/personas/` | Buyer-persona deep-dives (GC, CCO, Head of International, Listing Risk) | When sales / design-partner motion needs deeper persona research |
| `docs/contracts/` | Worked examples of platform contracts that validate each module's use case | When validating module fit with a specific design partner |

---

## External references

The strategy doc cites these — most live in the sibling repo `../carver-dags/`:

- `../carver-dags/workflows/entry_annotation/` — the upstream Carver workflow Pred-Oracle consumes.
- `../carver-dags/workflows/entry_annotation/prompts.py` and `workflow.py` — source of the field schema documented in `product-strategy.md` Appendix A.
- `../carver-dags/workflows/entry_annotation/README.md` — workflow README.

Public research sources (regulatory filings, press releases, court rulings cited as use-case evidence) are listed in `product-strategy.md` Appendix C.
