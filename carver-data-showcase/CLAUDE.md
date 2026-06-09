# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

**NEVER** update this file during a working session, we have other files to track project learnings and documentation references.

## Project Overview

A demo that showcases the **range, quality, and richness of the Carver agents annotation dataset** — the AI-generated, deeply structured insights Carver attaches to every regulatory feed entry (impact/urgency/relevance scores, actionables, critical dates, impacted business/functions, entities, and regulatory references) across 1,000+ topics and 240+ jurisdictions. Data is accessed via the **direct Carver Artifacts API** (`/api/v1/artifacts/dags/{dag}/artifacts`, `artifact_type_id=annotations-v1`, offset-paginated) — **not** the `carver-feeds-sdk`. This repo is a sibling under `carver-demos/` and is greenfield at init time.

## Specialized Sub-Agents Available

**ALWAYS** 
1. Use the appropriate specialized sub-agents available for the task being worked on. 
2. Provide the specialized sub-agents with the current working session goal. 
3. Run the Python Code Reviewer agent after each code change and have the Python Expert fix any issues found.

- **python-code-reviewer**: Review any new or modified Python code for quality, maintainability, and adherence to best practices. 
- **python-expert**: Write and test all Python code for the library.

## Superpowers Skills

**ALWAYS** use the relevant superpowers skills as needed. If there is even a small chance a skill applies to the task at hand, invoke it before proceeding — skills tell you *how* to approach the work. In particular:

1. **brainstorming** — before any creative or design work (new features, behavior changes) and before entering plan mode.
2. **writing-plans** — to turn an approved spec into a step-by-step, testable implementation plan.
3. **test-driven-development** — when implementing any feature or bugfix, before writing implementation code.
4. **systematic-debugging** — for any bug, test failure, or unexpected behavior, before proposing fixes.
5. **requesting-code-review** / **receiving-code-review** — when completing work and when acting on review feedback.
6. **verification-before-completion** — before claiming any work is complete, fixed, or passing.

Superpowers skills override default behavior, but **explicit user instructions always take precedence**.

## Model Selection

**ALWAYS** use the right-sized model for each task — match capability to complexity rather than defaulting everything to one tier:

- **Haiku** — simple, mechanical, well-scoped work (formatting, renames, file moves, quick lookups, boilerplate).
- **Sonnet** — routine implementation and standard coding tasks.
- **Opus** — complex reasoning: architecture and design, planning, debugging tricky issues, security-sensitive or high-impact changes, and code review.

Apply the same right-sizing when dispatching sub-agents or workflow agents: set each agent's model to fit its task (downgrade for cheap, parallel, or mechanical work; upgrade for hard reasoning), instead of running every agent on the same tier.

## Important Reference Files

- Starting point to understand the project is: [docs/README.md](docs/README.md)
- Important lessons learned and pitfalls to avoid: [docs/LESSONS.md](docs/LESSONS.md)
