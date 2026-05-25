# Acme Pay Policy Library

Internal compliance rulebook referenced by Acme Pay's risk and compliance agents.
*Acme Pay is a fictional company; the policies here are synthetic baselines used
solely to demonstrate how the policy-diffs agent surfaces and proposes edits.*

Each `policies/<area>/` folder contains:
- `policy.md`   — narrative, distributed to compliance staff (also rendered to PDF in `dist/`)
- `rules.yaml`  — machine-actionable thresholds and required actions
- `source.yaml` — Mastercard rule citations that justify the policy

Branches: each non-`main` branch represents a proposed update against an upstream Mastercard refresh.

> **Note:** the parent directory name (`credio-policies/`) is an internal legacy
> identifier kept for path stability — it is not user-visible. All customer-facing
> brand strings (rendered demo, config, READMEs, prompts, code, tests, docs) use
> **Acme Pay**.
