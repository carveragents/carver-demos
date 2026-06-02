# Pred-Oracle Backlog

Items requiring action outside the build pipeline (backend coordination, data sourcing, etc.).

## Carver Catalog & Data Coverage

### Add NRC to Carver catalog (backend team)

**Status:** Blocked on backend
**Owner:** TBD (backend team)

The U.S. Nuclear Regulatory Commission is not in Carver's topic catalog
(`data/carver-topics.json`). Confirmed by checking all 1,087 catalog topics on
2026-05-27 — no topic with "NRC" or "Nuclear Regulatory Commission" exists.
Only foreign nuclear regulators (Australia, UAE, India, Japan) and the IAEA
are tracked.

**Impact on trader demo:**
- The `nrc-nuclear-reactor-2026` contract ("US grants license for new nuclear
  reactor in 2026?") has no real signal coverage. It currently shows DORMANT
  with 5 timeline events that are tangential (California AG opposing Trump's
  nuclear policy changes, plus a false-positive about California oil pipelines).
- The actual events that would drive this contract — NRC licensing decisions,
  applicant filings from TerraPower/NuScale/SMR LLC — are invisible to Carver.

**Ask:** Add U.S. Nuclear Regulatory Commission to the Carver topic catalog
and begin ingesting filings from nrc.gov (Operating Reactor Licensing,
Combined Construction and Operating License applications, etc.).

### Enable DOE + FERC topics (after NRC is added)

**Status:** Pending (depends on NRC catalog addition)
**Owner:** Pred-Oracle (us)

After NRC is added to Carver, mark these additional topics as `pm_relevant`
in `data/regulator-topics.yml` and re-pull artifacts:

- **United States Department of Energy** (already in Carver catalog; ~36
  records visible via cross-references but topic not flagged pm_relevant)
- **Federal Energy Regulatory Commission (FERC)** (already in Carver catalog;
  not pulled)
- **U.S. Nuclear Regulatory Commission** (once added by backend)

These three regulators together cover the regulatory surface area for nuclear
reactor licensing, energy infrastructure approvals, and grid-scale projects.

**Why this matters:** Re-running the pipeline after these are pulled will
give the NRC reactor contract real signal coverage. Without NRC specifically,
DOE/FERC alone won't fully resolve the demo gap (NRC is the licensing
authority), but they add meaningful context (DOE construction permits,
FERC interconnection approvals).
