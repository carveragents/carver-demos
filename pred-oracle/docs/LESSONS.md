# SESSIONS

- 2026-06-02-trader-export (Trader demo scene export + relative-link portability + catalyst links + README documentation)

# LESSONS

## Model selection for subagent dispatch — 2026-05-19

When dispatching subagents via the `Agent` tool, explicitly set the `model` parameter. Omitting it inherits the parent session's model (often Opus), which is wasteful for mechanical work.

| Task type | Model |
|---|---|
| Mechanical implementation (1-2 files, clear spec — configs, simple tests, scaffold templates) | `haiku` |
| Standard implementation (single module + integration concerns — API pulls, slice generators, build orchestrator) | `sonnet` |
| Investigation / architectural judgment (e.g., DP1 verification, design choices, schema reconciliation) | `opus` |
| Spec-compliance reviews (mechanical diff vs spec) | `haiku` |
| Code-quality reviews (judgment, but well-scoped) | `sonnet` |
| Final cross-cutting review of a whole stage / branch | `opus` |

Per `superpowers:subagent-driven-development` skill: *"Use the least powerful model that can handle each role to conserve cost and increase speed."* Bias toward Sonnet when unsure rather than Haiku; bias toward Opus for any role where misjudgment cascades.

## Playwright screenshot paths — 2026-05-26

Always save Playwright `browser_take_screenshot` output to `build/screenshots/<descriptive-name>.png`. Never use a bare filename (resolves to CWD) or `../` paths (scatters files outside the project root).

```python
# Good
filename="build/screenshots/ac26-calendar-panel.png"

# Bad — lands in CWD or parent directory
filename="ac26-calendar-panel.png"
filename="../calendar-panel.png"
```

`build/screenshots/` is gitignored via the `*.png` rule in `.gitignore`. The directory is committed as an empty placeholder.

## Date-sensitive build steps contaminate curated snapshots — 2026-06-02

**Problem:** `make build` (and `make serve`) run `generate_slices.py` to regenerate date-specific content like `latest_pub_date` in `landing.json`. This drifts the committed, curated demo snapshot from its intended date. A demo recorded on 2026-05-28 may show "as of 2026-06-02" if rebuilt later.

**Mitigation:** Document prominently in the README that `make build`/`make serve` are date-sensitive. For preserving a curated snapshot's date, serve the pre-built `site/` output directly (`cd site && python3 -m http.server`) instead of rebuilding, or run `generate.py` alone (never `make build`) to re-render without re-slicing.

**Lesson:** Date-dependent content should be gated separately from the main build. Alternatively, cache the slice result and reuse it unless explicitly requested. The goal is "reproduce the committed curated snapshot" without side effects like date drift.

## Portable static sites require explicit link normalization for file:// protocol — 2026-06-02

**Problem:** The `file://` protocol doesn't auto-serve `dir/index.html` when navigating to `dir/` (unlike HTTP servers). Links like `../trader/` open a directory listing, not the index, breaking single-file-open portability.

**Mitigation:** After template rendering, apply a regex pass (`_fileify_links`) to rewrite all directory-style links to explicit `index.html` paths: `../trader/` → `../trader/index.html`. This is non-invasive (no template changes) and composable (applies site-wide in one pass).

**Lesson:** For truly portable demos that work over `file://`, HTTP at any path, or any domain subpath, use relative + fileified links as the default. Absolute prefixes are opt-in via environment variable for fixed-subpath deployments (e.g., GitHub Pages under a subdomain). The fileify approach catches an edge case that would otherwise require site structure changes or server-side rewrites.
