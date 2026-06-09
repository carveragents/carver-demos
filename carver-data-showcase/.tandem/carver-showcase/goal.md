Carver Annotation Data Showcase v1 — two Streamlit prototypes over one shared data pipeline that demonstrate the range, quality, and richness of the Carver agents annotation dataset to (A) external data clients and (B) Carver's internal data-quality team, from a real 30K-100K-record snapshot pulled via the direct Artifacts API, with NO LLM enrichment calls.

## Overall brief (carried into every stage)

**What the dataset is.** A Carver annotation is the AI-generated, deeply-structured
intelligence layer Carver's agents attach to a single raw regulatory feed entry (a rule,
bulletin, enforcement action, press release, …). Where the raw entry is just title + link +
date, the annotation turns it into a machine-readable compliance object: three independent
scores (`impact`, `urgency`, `relevance`), each with a `label`, numeric `score`, and model
`confidence` (urgency also carries a `basis`); a 5-part `impact_summary`
(objective / what_changed / why_it_matters / risk_impact / key_requirements); 7 lanes of
`actionables` (policy / status / process / training / reporting / tech_data / other);
calendar-aware `critical_dates` (effective / compliance / comment_deadline / early_adoption
+ free-form `other_dates[]`, each with a paired `*_calendar`); `entities` + `tags`;
`reg_references` (rules / statutes / other_ref / personnel / precedents / past_release);
`impacted_business` (industry / type / jurisdiction / other_notes) and `impacted_functions`;
`penalties_consequences`; a structured `classification` (`update_type`, `update_subtype`,
`regulatory_source.{name,division_office,other_agency}`, and `jurisdiction`
{scope, country, bloc, locality, region_*, reasoning}); and a `reconciled_published_date`
with provenance (`source`, `converted`, `original_calendar`).

**Scale on offer.** ~1,087 topics · 3 categories (Data protection & cybersecurity, Finance,
Medical Devices) · 241 jurisdictions · many `update_type`s · tens of thousands of records.

**Two audiences, two prototypes, one pipeline:**
- **(A) Showcase Gallery — external clients** (data merchants, firms wanting regulatory feeds):
  sell the feed by making range + quality + richness immediately tangible and explorable.
- **(B) Data-Quality Cockpit — internal QA team**: assess data quality for cleanup — surface
  missing / unclear / incomplete / inconsistent fields, coverage by slice, anomalies, and a
  triage queue.
- Both read the SAME normalized snapshot produced by one shared ingest -> normalize -> metrics
  pipeline.

**Locked decisions (do not relitigate):**
1. **Delivery = Streamlit** (interactive, live sidebar filtering; `streamlit run`).
2. **Two prototypes split by audience** (A external, B internal), sharing one pipeline.
3. **Data access = the direct Carver Artifacts API only** (offset-paginated,
   `artifact_type_id=annotations-v1`, DAG `7f61eee4-1c56-44cc-b7fb-bbfcbda6a5ad`, `X-API-Key`).
   NOT the `carver-feeds-sdk`. Snapshot once to `data/annotations.jsonl`
   (already pulled, ~50-60K records — squarely inside the required 30K-100K band).
   `artifact.output_data` IS the annotation; carry envelope `topic_id`/`state`/`*_at`.
4. **Build on `classification.jurisdiction`** — `classification.jurisdiction_tier` is deprecated
   and already absent from current records (backfill ~2026-06-11 has begun).
5. **NO LLM calls anywhere for enrichment.** All scoring/curation/quality logic is deterministic
   (rules, thresholds, counts). Any enhancement that would need an LLM is OUT of scope for v1 and
   gets recorded in `docs/v2-llm-enrichment-ideas.md`, not built.
6. **Honest coverage.** Field population varies (scores+join keys ~100%; analytical prose
   ~83-89%; dates/refs sparser 8-43%). Report real percentages; never fake completeness.
7. **Stack:** Python 3.12 venv (`.venv/`), `httpx` + `python-dotenv` for the pull, `pandas`
   for normalization, `streamlit` + a charting lib (Plotly or Altair) for the apps. Tests with
   `pytest`, stubbing any HTTP. Secrets in git-ignored `.env` (`CARVER_API_KEY`).

**North star:** let the dataset speak. Aggregate views prove breadth; single-record drill-downs
prove depth; the QA cockpit proves Carver is honest about its own coverage. The showcase must be
credible to a buyer AND useful to the team that has to clean the data.
