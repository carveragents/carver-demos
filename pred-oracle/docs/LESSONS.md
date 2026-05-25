# SESSIONS

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
