# Credio Policy Library

Internal compliance rulebook referenced by Credio's risk and compliance agents.
Each `policies/<area>/` folder contains:
- `policy.md`   — narrative, distributed to compliance staff (also rendered to PDF in `dist/`)
- `rules.yaml`  — machine-actionable thresholds and required actions
- `source.yaml` — Mastercard rule citations that justify the policy

Branches: each non-`main` branch represents a proposed update against an upstream Mastercard refresh.
