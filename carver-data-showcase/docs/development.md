# Development

## Environment

| Item | Value |
|---|---|
| Language | Python |
| Interpreter | `.venv/` in repo root — **Python 3.10.17** |
| Core dependencies | `httpx` (direct API), `python-dotenv`, `pandas`. **No `carver-feeds-sdk`** — this showcase uses the direct Artifacts API. |
| Data access | Direct HTTP to the Carver **Artifacts API** (`X-API-Key`); see [data-access.md](data-access.md). |
| Secrets | `.env` in repo root with `CARVER_API_KEY` (git-ignored, no fallback) |

## First-time setup

```bash
.venv/bin/python -m pip install --upgrade pip
.venv/bin/python -m pip install -r requirements.txt   # includes kaleido + reportlab (deck renderer)
# create .env — see docs/data-access.md
```

Always invoke the repo venv explicitly (`.venv/bin/python …`) so you stay on the
3.10 interpreter.

## Running

```bash
# Pull the full annotation corpus (~211K records, ~2.5 min). This also rebuilds the
# parquet from the fresh JSONL and RE-RENDERS the deck (data/carver-state-of-data.pdf).
.venv/bin/python tools/pull_full.py

# Launch the Streamlit gallery
.venv/bin/streamlit run apps/gallery.py

# Re-render the deck on demand (otherwise it's regenerated automatically by pull_full;
# writes data/carver-state-of-data.pdf — ~2–3 min dominated by the choropleths)
.venv/bin/python tools/build_deck.py
```

The deck is git-ignored (`data/*.pdf`). On a fresh checkout (before any pull) the
gallery shows a caption in place of the download button; the button appears once the
deck file exists. A deck render failure during a pull warns but does not fail the pull.

## Testing

```bash
.venv/bin/python -m pytest -q          # full suite
.venv/bin/python -m pytest tests/test_charts.py tests/test_deck.py -q   # deck-related only
```

Tests are deterministic and offline: the deck tests monkeypatch `kaleido` so no
Chrome is launched, and data tests stub the HTTP layer (mirroring `pred-oracle`).

## Working conventions

- This is a **Flux-managed** repo: work happens in dated sessions
  (`/flux:session:start`) inside a git worktree under `.claude/worktrees/`.
- Session logs live in `.claude/.sessions/`.
- Run the code-review agent after each code change (see `CLAUDE.md`).
- Record durable learnings in [LESSONS.md](LESSONS.md), not in `CLAUDE.md`.

## Conventions worth inheriting from siblings

- **Snapshot, don't re-fetch.** Persist the pulled corpus to `.jsonl`/parquet,
  resumable from the last `offset`, for reproducible builds.
- **Page by `offset`** against the artifacts endpoint; keep `limit ≤ 10000` (larger
  pages 502); stop on the first short/empty page.
- **Treat `artifact.output_data` as the annotation**; flatten
  `output_data.metadata.*` / `output_data.classification.*` on ingest for predictable
  analytics columns, and carry envelope `topic_id` / `state` / `*_at` timestamps.
- **`load_dotenv(dotenv_path=...)`** — pass the path explicitly (bare `load_dotenv()`
  throws under heredoc/stdin). See [LESSONS.md](LESSONS.md).
