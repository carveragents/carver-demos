# Carver Demos — Documentation Index

This is the documentation hub for the carver-demos monorepo. For documentation specific to each demo, see the README.md and docs/ folder inside each demo subdirectory.

## Project-Wide

- **[LESSONS.md](./LESSONS.md)** — Key lessons learned across sessions working on this monorepo. Best practices for organizing demos, consolidating repos, and maintaining context in heterogeneous codebases.

## Individual Demos

Each demo is a self-contained project with its own documentation:

### policy-diffs

POC automating Mastercard B2B rulebook deltas → Credio policy updates.

- **README:** [`policy-diffs/README.md`](../policy-diffs/README.md) — What it does, setup, pipeline architecture, demo walkthrough.
- **Design:** [`policy-diffs/docs/superpowers/specs/2026-05-07-policy-diffs-poc-design.md`](../policy-diffs/docs/superpowers/specs/2026-05-07-policy-diffs-poc-design.md) — Full 6-stage pipeline spec, risk mitigation, success criteria.
- **Plan:** [`policy-diffs/docs/superpowers/plans/2026-05-07-policy-diffs-poc-phase-1.md`](../policy-diffs/docs/superpowers/plans/2026-05-07-policy-diffs-poc-phase-1.md) — Implementation plan.
- **Demo Runbook:** [`policy-diffs/docs/superpowers/demo-runbook.md`](../policy-diffs/docs/superpowers/demo-runbook.md) — 5-minute walkthrough script.
- **Credio Policies:** [`policy-diffs/credio-policies/README.md`](../policy-diffs/credio-policies/README.md) — Synthetic policy library structure.

### pred-oracle

Vertical compliance-intelligence platform for prediction-market operators.

- **README:** [`pred-oracle/README.md`](../pred-oracle/README.md) — Overview, V1 modules (α/β/γ), stage status, project structure.
- **Product Strategy:** [`pred-oracle/docs/product-strategy.md`](../pred-oracle/docs/product-strategy.md) — Canonical strategy doc. Read this first.
- **Development Guide:** [`pred-oracle/docs/development.md`](../pred-oracle/docs/development.md) — Setup, build, local preview.
- **Lessons Learned:** [`pred-oracle/docs/LESSONS.md`](../pred-oracle/docs/LESSONS.md) — Session notes and running insights.
- **Specs:** [`pred-oracle/docs/specs/`](../pred-oracle/docs/specs/) — Stage-by-stage acceptance criteria and schema docs.

### fincoach-demo

7-layer compliance demo (multi-layer agent deployment). See [`fincoach-demo/README.md`](../fincoach-demo/README.md).

### fincoach-demo-single-layer

Single-layer variant. See [`fincoach-demo-single-layer/README.md`](../fincoach-demo-single-layer/README.md).

### amicompliant

See [`amicompliant/`](../amicompliant/).

---

## For New Developers

1. **Start with the root README:** [`README.md`](../README.md) — Overview of all demos.
2. **Pick a demo and read its README** — Each one is self-contained and explains setup, goals, and structure.
3. **For deep dives:** Follow the links from each demo's README to its docs/ folder (design, plan, runbook, etc.).
4. **For monorepo practices:** Read [LESSONS.md](./LESSONS.md) — insights from consolidating these projects.
