# Stress-test 002 — compiled gaps (stage 01-spec, cycle 2)

| # | Gap | Stage | Severity |
|---|---|---|---|
| G4 | No committed **"monitored institutions" catalog view** with a country × regulator-type (× scope) breakdown. The data exists in the topics catalog (1,071 institutions: `name`, `jurisdiction_code`, `entity_type`, `govt_body`, `scope`, `acronym`), reachable via a sanctioned direct GET. A buyer explicitly asks for this. | 01-spec | **High** |
| G5 | No explicit **historical-depth** metric (earliest *plausible* record date, span, recency distribution) and no framing of the strong recency skew. Raw earliest (1947) / latest (2105) are garbage; a headline must use plausible dates with the extremes shown only as anomalies. | 01-spec | Medium |

Both are additive Gallery features (plus a small QA angle in the Cockpit). Routed to
`stages/01-spec/refinement.md` (cycle 2).
