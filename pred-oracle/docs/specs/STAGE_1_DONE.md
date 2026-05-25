# Stage 1 — α Walkthrough Acceptance Log

**Completed:** 2026-05-20
**Worktree:** plan-v1-implementation

## Acceptance criteria (from `30-alpha-walkthrough.md` §5)

- [x] All four α pages render with no runtime errors.
- [x] Inbox top row is a real recent event from data/_scratch/artifacts.jsonl.
- [x] Five ticket-detail pages exist; each renders ≥3 of {what_changed, why_it_matters, key_requirements, penalties_consequences, reg_references}.
- [x] Synthetic comments / transitions display the demo-data badge.
- [x] US-state choropleth renders via ECharts (90-day window).
- [x] Top-10 table counts agree with the data-slice JSON.
- [x] Audit-export preview includes a clickable sample PDF.
- [x] "Next scene" CTA on /alpha/audit-export/ navigates to /gamma/.
- [ ] (Pending) Carver leadership dry-run: friendly viewer plays scene 1 end-to-end ≤4 min.
- [ ] (Deferred to Stage 4 polish) Mobile/tablet reflow.

## Snapshot

### Curated picks (from data/alpha-curation.yml)

- **Wow ticket:** `e519db6e-499e-47d5-bd65-2b45752fb6bd`
  - Title: "CFTC Sues Minnesota to Block State Law"

- **Supporting tickets:**
  1. `fd954992-3ce2-4a28-97e3-a0b472850d7b` — "DFPI Shuts Down Crypto Kiosk Operator for Cheating Consumers and Violating State Laws"
  2. `47d30176-f4a4-4ed5-aaf3-632f14ec65a8` — "David H. Goldman"
  3. `ff637c5e-300e-40d8-9db9-d212940da728` — "CFTC Sues Wisconsin to Reaffirm its Exclusive Jurisdiction Over Prediction Markets"
  4. `48b578d5-84fc-4c9c-b098-c8740780663b` — "California Department of Justice Releases Proposed 'Protecting Our Kids from Social Media Addiction Act (SB 976)' Regulations - 14.05.2026"

- **Dashboard window:** 90 days
- **Corpus snapshot:** data/_scratch/artifacts.jsonl (49,735 records)

## Page inventory

```
site/alpha/audit-export/index.html
site/alpha/dashboard/index.html
site/alpha/index.html
site/alpha/tickets/47d30176-f4a4-4ed5-aaf3-632f14ec65a8/index.html
site/alpha/tickets/48b578d5-84fc-4c9c-b098-c8740780663b/index.html
site/alpha/tickets/e519db6e-499e-47d5-bd65-2b45752fb6bd/index.html
site/alpha/tickets/fd954992-3ce2-4a28-97e3-a0b472850d7b/index.html
site/alpha/tickets/ff637c5e-300e-40d8-9db9-d212940da728/index.html
site/beta/index.html
site/close.html
site/gamma/index.html
site/index.html
```

12 pages total (4 α pages + 5 α ticket-details + 3 other scenes).

## Build output

### generate_slices.py

```
landing.json: events=49735
alpha: inbox + 5 tickets + dashboard + audit_export
```

### generate.py

```
Rendered alpha/audit_export.html → alpha/audit-export/index.html
Rendered alpha/dashboard.html → alpha/dashboard/index.html
Rendered alpha/inbox.html → alpha/index.html
Rendered beta/intro.html → beta/index.html
Rendered close.html → close.html
Rendered gamma/intro.html → gamma/index.html
Rendered landing.html → index.html
alpha/tickets: rendered 5 pages
Copied static assets to /Users/achintthomas/work/scribble/code/repos/carver/pred-oracle/.claude/worktrees/plan-v1-implementation/site/static
```

## Test suite

```
============================== 92 passed in 1.59s ==============================
```

All 92 tests pass:
- 18 tests in `test_slices.py`
- 56 tests in `test_templates.py`
- 18 tests in `test_yaml_seeds.py`

## Linting and type-checking

### Ruff (core build files)

All checks passed:
- `build/generate_slices.py` — formatted
- `build/generate.py` — formatted
- `build/_scoring.py` — formatted
- `build/_fields.py` — already formatted

### MyPy (core build files)

Success: no issues found in:
- `build/generate.py`

(Note: `build/alpha_*.py` modules report pre-existing yaml-stubs warning, which is acceptable per acceptance criteria.)

## Known gaps (deferred to polish)

- Mobile reflow (responsive `<table>` → card list at <768px)
- Print stylesheet for audit export
- ARIA labels on choropleth interactions
- Real audit-PDF artwork (current sample is a 621-byte placeholder)
- ECharts USA map JSON fetched at runtime from jsDelivr — consider local hosting for offline robustness
