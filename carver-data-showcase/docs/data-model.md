# The Carver Agents Annotation Dataset

This is the **subject of the demo**. Everything else in this repo exists to surface
the range, quality, and richness documented here.

A Carver annotation is the AI-generated, structured intelligence layer that Carver's
agents attach to a single raw regulatory **feed entry** (a press release, rule,
bulletin, enforcement action, etc.). Where a raw entry is just a title + link +
publication date, the annotation turns it into a machine-readable compliance object.

> **Schema note:** The public SDK/API reference documents a *simplified* annotation
> shape (`scores.{relevance,importance,confidence}`, `classification`, `summary`).
> The **production payload is far richer** — the structure below is verified against
> the live API. When the two disagree, trust the real payload.

> **Where this lives in the showcase:** we pull via the direct **Artifacts API**
> ([data-access.md](data-access.md)), where the annotation object below **is
> `artifact.output_data`** (identical shape). The artifact *envelope* adds
> `topic_id`, `state`, and `created_at`/`completed_at` timestamps — use those directly
> rather than re-deriving them. The block below documents `output_data`.

---

## Headline numbers (range)

Observed from the `pred-oracle` catalog + corpus pull:

| Dimension | Scale |
|---|---|
| Topics | **1,087** |
| Categories | **3** — Data protection & cybersecurity, Finance, Medical Devices |
| Distinct jurisdictions | **241** (US, AU, EU-27, CN, IN, US-CA, FR, US-TX, TR, KR, SG, …) |
| Annotation records (one PM-scoped pull) | **~54,959** |
| `update_type` values | enforcement, final rule, proposed rule, bulletin, press release, … |

These are the axes a "range" view can pivot on: category → topic → jurisdiction →
regulator → update_type → time.

---

## Full record shape

The annotation object — i.e. `artifact.output_data` from the Artifacts API (shown
here under an `annotation` wrapper, which is how the feeds view labels the same object):

```jsonc
{
  "annotation": {
    "entry_id": "c83abf6a-…",
    "scores": {
      "impact":    { "label": "high",   "score": 9,   "confidence": 0.95 },
      "urgency":   { "label": "medium", "score": 5,   "confidence": 0.9,  "basis": "past_deadline" },
      "relevance": { "label": "high",   "score": 9.0, "confidence": 0.925 }
    },
    "metadata": {
      "tags":     ["Alberta Securities Commission", "Enforcement", "Prospectus Exemption", …],
      "entities": ["2307755 Alberta Ltd.", "Daniel Rodolfo Astete", …],

      "actionables": {
        "policy_change":    "",
        "status_change":    "Inability to rely on crowdfunding exemption due to payment to principal",
        "process_change":   "Ensure strict adherence to prospectus and exemption filing requirements",
        "training_change":  "",
        "reporting_change": "File accurate and compliant reports of exempt distribution",
        "tech_data_change": "",
        "other_change":     "Respondents must prepare for and attend regulatory hearings"
      },

      "critical_dates": {
        "effective_date":   "2026-04-08",
        "compliance_date":  "",
        "comment_deadline": "",
        "early_adoption_date": "",
        "updated_date":     "",
        "pub_date_content": "2026-02-25",
        "other_dates": [
          { "date": "2023-12-18", "calendar": "gregorian", "description": "Date payment of $21,000 made to Astete" }
        ],
        // every *_date has a paired *_calendar field (gregorian, etc.)
      },

      "impact_summary": {
        "objective":        "To notify the respondent of a hearing regarding alleged illegal securities distributions…",
        "what_changed":     "The Alberta Securities Commission is initiating enforcement proceedings against…",
        "why_it_matters":   "…",
        "risk_impact":      "Non-compliance risks include enforcement actions, orders against principals…",
        "key_requirements": "…"
      },

      "impacted_business":  { "industry": "…", "jurisdiction": ["KR"], "type": "…" },
      "impacted_functions": "…",
      "penalties_consequences": "…",
      "reg_references":     { "rules": [...], "statutes": [...], "other_ref": [...] }
    },

    // ── classification: source-entry metadata + entry-level labels (raw-API only;
    //    flat exports hoist all of these to top-level) ──
    "classification": {
      "metadata": {
        "title":    "Monetary and Liquidity Aggregates (October 2025)",
        "summary":  "Monthly statistical release of monetary and liquidity aggregates data",
        "base_url": "bok.or.kr",
        "feed_url": "https://www.bok.or.kr/eng/bbs/E0000634/view.do?nttId=…",
        "language": ["en", …]
      },
      "update_type":    "press release",   // enforcement | final rule | proposed rule | bulletin | …
      "update_subtype": "statistical release",
      "regulatory_source": { /* regulator name / division / source identity */ },

      // jurisdiction lives HERE (NOT under metadata), each with LLM reasoning
      "jurisdiction": {
        "scope": "national", "country": "KR", "bloc": null, "locality": null,
        "region_code": null, "region_name": null, "locality_type": null,
        "reasoning": "The Bank of Korea is the national central bank and regulator of South Korea…"
      },
      "jurisdiction_tier": {          // ⚠ DEPRECATED — legacy field being REPLACED BY
        "tier": 2, "label": "international",   //   classification.jurisdiction by a backfill job
        "reasoning": "…"              //   (~2026-06-11). Build on jurisdiction, not this.
      }
    },

    // ── date normalized by the agent, WITH provenance ──
    "reconciled_published_date": {
      "date": "2025-12-16", "valid": true, "source": "LLM",
      "converted": false, "original_date": null, "original_calendar": "…"
    }
  },
  "feed_entry_id": "…",   // top-level join keys (presence depends on filter used)
  "topic_id": "…",
  "user_id": "…"
}
```

> **Verified live against SDK v0.5.0** (categories=3, topics=1,071, sample topic
> returned 673 annotations). `annotation` carries five keys: `scores`, `entry_id`,
> `metadata`, `classification`, `reconciled_published_date`. **`classification`** holds
> `metadata`, `update_type`, `update_subtype`, `jurisdiction`, `regulatory_source`
> (+ legacy `jurisdiction_tier`, **deprecated**, see below) — note `jurisdiction*` and
> `update_*` live under `classification`, **not** `metadata`.

> Field placement varies between the flat corpus export (pred-oracle flattens
> `metadata.*` + `classification.metadata.*` to top-level: `tags`, `entities`,
> `title`, `base_url`, `scores.impact.score`, …) and the raw API response (nested
> under `annotation.metadata` / `annotation.classification.metadata`). Normalize on
> ingest.

---

## Why each block matters (the demo's talking points)

| Block | What it demonstrates |
|---|---|
| `scores.{impact,urgency,relevance}` | **Quality** — three independent axes, each with a `label`, numeric `score`, and a model `confidence`; `urgency.basis` explains *why* (e.g. `past_deadline`). Not a single opaque relevance number. |
| `impact_summary` | **Richness** — five distinct analytical angles (objective / what changed / why it matters / risk / requirements), not one summary string. |
| `actionables` | **Richness** — change is decomposed into 7 operational lanes (policy, status, process, training, reporting, tech/data, other) — directly mappable to compliance workstreams. |
| `critical_dates` | **Quality** — calendar-aware extraction of effective / compliance / comment-deadline / early-adoption dates **plus** free-form `other_dates[]` with descriptions. |
| `entities` + `tags` | **Quality** — named-entity recognition (companies, people, regulators) and controlled tagging per entry. |
| `reg_references` | **Richness** — explicit links to the `rules`, `statutes`, and `other_ref` (attachments/sources) an entry touches. |
| `impacted_business` / `impacted_functions` | **Range** — who/what is affected (`impacted_business.jurisdiction` is a country-code list, e.g. `["KR"]`), normalized for filtering and roll-ups. |
| `classification.jurisdiction` | **Range + Quality** — structured geography (`scope`, `country`, `bloc`, `locality`, `region_*`) **with LLM `reasoning`**. Lives under `classification`, not `metadata`. |
| ~~`classification.jurisdiction_tier`~~ | **DEPRECATED** — being **replaced by `classification.jurisdiction`** via a backfill job (~2026-06-11). After it completes, `jurisdiction_tier` is gone and `jurisdiction` is its successor. Build on `jurisdiction`. |
| `classification.update_type` / `update_subtype` / `regulatory_source` | **Range** — pivot axes across the whole corpus (also under `classification`). |
| `reconciled_published_date` | **Quality** — publication date normalized with provenance (`source: "LLM"`) and calendar-conversion tracking (`converted`, `original_calendar`) — auditable, not a bare timestamp. |
| `classification.metadata` | **Provenance** — carries the source entry's `title`, `summary`, `base_url`/`feed_url`, and `language`, linking every annotation back to its origin. |

## Field-population reality (be honest in the demo)

From the 54,959-record audit (`pred-oracle/data/a6-field-population.md`): the
**scores trio and core join keys are ~100% populated**; analytical prose
(`impact_summary.*`, `impacted_business.*`) sits at **83–89%**; date sub-fields and
`reg_references` are sparser by nature (8–43%) because not every entry carries a
deadline or cites a statute. Some `update_type`s (e.g. `website error`) are
intentionally thin. A credible showcase reports coverage, it doesn't pretend 100%.
