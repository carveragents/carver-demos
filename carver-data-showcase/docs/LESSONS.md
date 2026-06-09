# SESSIONS

# LESSONS

## Carver annotation dataset (verified against live SDK v0.5.0)

- **Field placement:** in the raw API, `jurisdiction`, `jurisdiction_tier`,
  `update_type`, `update_subtype`, and `regulatory_source` live under
  **`annotation.classification`**, NOT `annotation.metadata`. pred-oracle's flattened
  `.jsonl` export hoists everything to top-level and hides this — trust the live API.
- **`jurisdiction_tier` is DEPRECATED — being replaced by `jurisdiction`.** A backfill
  job (~2026-06-11) swaps `classification.jurisdiction_tier` for
  `classification.jurisdiction` (`{scope, country, bloc, locality, region_*,
  reasoning}`). After it completes, `jurisdiction_tier` is gone. Build on
  `jurisdiction`.
- **`load_dotenv()` gotcha:** with no args it throws `AssertionError` when run via
  `python - <<heredoc` (stdin) because `find_dotenv()` can't walk the stack. Always
  pass `dotenv_path=` explicitly, or run from a real `.py` file.
