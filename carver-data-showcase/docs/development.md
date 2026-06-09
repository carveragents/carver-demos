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
.venv/bin/python -m pip install httpx python-dotenv pandas
# create .env — see docs/data-access.md
```

Always invoke the repo venv explicitly (`.venv/bin/python …`) so you stay on the
3.10 interpreter.

## Running

No entry point exists yet (greenfield). Once built, document the run command here
and point to it from `docs/README.md`. Until then, the working surface is the data
pull described in [data-access.md](data-access.md).

## Testing

No test suite yet. When adding one, mirror `pred-oracle`'s approach (`pytest`,
fixtures that stub the HTTP layer so tests don't hit the live API). Reference:
`carver-demos/pred-oracle/tests/`.

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
