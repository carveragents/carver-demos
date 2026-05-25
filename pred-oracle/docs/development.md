# Development Environment

## Runtime

- **Python 3.10** (pinned). A virtualenv is already created at `.venv/` (Python 3.10.17 against the Homebrew `python@3.10` install).

## Activating the environment

```bash
source .venv/bin/activate
python --version   # should report 3.10.x
```

## Status

Stage 0 of the demo build is implemented. The repo now contains:

- `pyproject.toml` (uv-managed deps; Python 3.10).
- `Makefile` with targets: `pull`, `slice`, `build`, `serve`, `test`, `lint`, `clean`.
- `build/` — Python build scripts + Jinja2 templates + static assets.
- `data/` — real Carver-annotated regulatory data (~618 events) + per-platform YAML catalogs.
- `tests/` — pytest suite (37 tests as of Stage 0).
- `.github/workflows/deploy.yml` — CI: lint + test + GH Pages deploy.

## Setup

```bash
# Install uv (if not present)
curl -LsSf https://astral.sh/uv/install.sh | sh

# Sync dependencies
uv sync --extra dev

# (Optional) Set up `.env` for Carver re-pull
cp .env.example .env  # then edit with your CARVER_API_KEY
```

## Common commands

| Command | What it does |
|---|---|
| `make build` | Generate slices + render templates → `site/`. Daily command. |
| `make serve` | Build + start `python -m http.server` at localhost:8000. |
| `make test` | Run pytest suite. |
| `make lint` | `ruff check` + `ruff format --check`. |
| `make pull` | Re-pull from Carver + Kalshi + Polymarket (rare; needs `.env`). |
| `make clean` | Wipe `site/`, `build/page_data/`, and pytest caches. |

## Deploy

The CI workflow (`.github/workflows/deploy.yml`) auto-deploys `site/` to GitHub Pages on push to `main`. One-time setup: in repo Settings → Pages → Source, select "GitHub Actions". The deployed URL will be `https://<org>.github.io/<repo>/`.

Local preview uses `make serve`. GH Pages uses `PRED_ORACLE_BASE_URL=/<repo>/` (set in CI).
