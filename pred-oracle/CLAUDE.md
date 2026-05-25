# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

**NEVER** update this file during a working session, we have other files to track project learnings and documentation references.

## Project Overview

Pred-Oracle is a vertical compliance-intelligence platform for prediction-market operators (Kalshi, Polymarket, and the broader CFTC-licensed DCM / event-contract category), built on top of Carver's existing `entry_annotation` regulatory-annotation pipeline. The repo is currently in **strategy / pre-spec** phase — the canonical artifact is `docs/product-strategy.md`; no application code exists yet. Target runtime is Python 3.10.

## Specialized Sub-Agents Available

**ALWAYS**
1. Use the appropriate specialized sub-agents available for the task being worked on.
2. Provide the specialized sub-agents with the current working session goal.
3. Run the code review agent after each code change and have the appropriate coding agents fix any issues found.

## Superpowers

This project uses the `superpowers` skill family. Invoke the relevant superpower skill before starting any non-trivial task — especially `brainstorming` (before any creative/design work), `writing-plans` (before multi-step implementation), `test-driven-development` (before writing implementation code), `systematic-debugging` (before proposing fixes), and `verification-before-completion` (before claiming work done).

## Important Reference Files

- Starting point to understand the project is: [docs/README.md](docs/README.md)
- Important lessons learned and pitfalls to avoid: [docs/LESSONS.md](docs/LESSONS.md)
