# Project Lessons Learned

## SESSIONS

- 2026-05-25-1138-move-existing-demos

---

## LESSONS

### 1. Validate file purpose before organizing — don't assume artifacts are assets

**Problem:** When consolidating repositories, loose files in a project root often look like they should be organized (especially if they're grouped by naming pattern). Easy to assume they're assets that need a proper home.

**Mitigation:** Before reorganizing or consolidating files, check three things: (1) Is the file `.gitignored` in the original repo? (2) Does the file have zero code references (`grep -r` across docs/code/templates)? (3) Is the file used by the application or just a development artifact? If all three are "ignored, unreferenced, unused," it's probably scratch and should not be tracked.

**Lesson:** Development scratch and actual assets look similar at first glance. A quick `.gitignore` + grep check prevents unnecessary organization work and keeps the repo clean. If files were intentionally excluded, respect that intent unless you have a strong reason to track them now.

### 2. Preserve project-specific context when consolidating repos into a monorepo

**Problem:** When moving standalone repositories into a monorepo subdirectory, it's tempting to strip away project-specific config files (like `.claude/`, `.superpowers/`) to "clean up" the root. But these files often contain crucial guidance for AI agents and developers working on that specific project.

**Mitigation:** Always preserve project-local configuration that might be referenced later:
- `CLAUDE.md` or equivalent (agent system prompts, coding standards for that project)
- `.claude/settings.json` (project-specific Claude Code settings)
- `.superpowers/` (project-specific skill definitions)
- `docs/LESSONS.md` or project-local lesson files (contextual decisions)

**Lesson:** In a monorepo with heterogeneous projects, each demo/component is different. Keeping its local config prevents loss of context and avoids the need to recreate guidance later. The parent repo's `.claude/` and each subdirectory's `.claude/` serve different purposes and should coexist without conflict.
