# v2 LLM Enrichment Ideas

v1 is intentionally deterministic: no model calls, no embeddings, no fuzzy matching. Every signal
is a formula, threshold, or rule applied to the structured fields in the annotation payload. This
makes v1 fast, reproducible, and honest — but it leaves a number of valuable enhancements on the
table that genuinely need an LLM or embedding model to do well. This document is the capture
point for those ideas so they are not lost.

Each entry names:
- **What it would do** — the user-facing capability.
- **Why it needs an LLM** — what deterministic logic cannot do here.
- **What v1 does instead** — the honest, in-scope substitute.

---

## 1. Semantic search over annotations (embeddings)

**What it would do.** A user types a natural-language query ("capital requirements for tier-1
banks after Basel IV") and retrieves the most semantically relevant annotation records, ranked
by vector similarity.

**Why it needs an LLM.** Keyword/structured-field filtering (the v1 approach) can narrow by
category, update_type, or regulator, but cannot capture semantic intent. Two records about "Basel
III" and "CRD V capital buffers" would both match a query conceptually but share no exact keyword.
Meaningful retrieval requires dense embeddings of the annotation's `impact_summary`, `title`, and
`tags` fields, plus a similarity search index.

**What v1 does instead.** A conjunctive structured-filter sidebar: category, jurisdiction,
regulator, update_type, score ranges, date range, and minimum richness score. All filters are
exact or range-based. Users narrow the 58,982-record corpus with precision but not semantic
intent.

---

## 2. Natural-language quality critique per record

**What it would do.** For any record in the cleanup queue, an LLM reads the populated annotation
fields and generates a short natural-language explanation of why the record looks weak — e.g.
"The impact summary is present but does not mention any specific regulatory instrument; the
effective date is missing and the comment deadline has already passed."

**Why it needs an LLM.** Predicate flags are binary (missing, short, out-of-range), and their
names are terse identifiers. Translating a failing-predicate set into actionable prose that a
data-ops analyst can act on — without the analyst having to read the raw annotation — requires
understanding the content, not just checking field presence.

**What v1 does instead.** Nine named quality predicates are computed deterministically
(`predicate_flags`). The cleanup queue shows the list of predicate names that fired for each
record and surfaces `feed_url` as a triage link. The analyst can click through to the source to
understand the context.

---

## 3. Auto-summarized gap explanations in the Cockpit

**What it would do.** The coverage matrix (Cockpit §7.1) shows population percentages for each
field sliced by category, update_type, or jurisdiction. A v2 Cockpit view would use an LLM to
generate a concise narrative summary of the most notable gaps — e.g. "Medical Devices
annotations are missing `feed_url` at 61%, compared with 44% in Finance, likely due to the
high proportion of PDF-sourced regulatory guidance in that category."

**Why it needs an LLM.** Pattern-naming from a coverage matrix requires reading structure
(percentages, slice labels) and generating coherent prose hypotheses. A deterministic rule can
flag fields below a threshold; it cannot explain the pattern or connect it to domain knowledge.

**What v1 does instead.** The coverage matrix renders counts and percentages with heatmap
coloring (red = sparse). The QA operator reads the matrix directly and applies their own domain
knowledge to prioritize.

---

## 4. Regulator-name canonicalization via embeddings or fuzzy matching

**What it would do.** The corpus contains 3,219 distinct raw `regulator_name` values, many of
which refer to the same body under slightly different spellings — "Financial Conduct Authority",
"FCA", "UK Financial Conduct Authority (FCA)", "Financial Conduct Auth.". A v2 canonicalization
step would use sentence embeddings or a fine-tuned LLM to cluster these into canonical entities
and assign a stable regulator ID, building a reference table.

**Why it needs an LLM.** Exact-match deduplication misses abbreviation variants and reordered
tokens. Rule-based suffix stripping and lowercasing (the v1 approach) can collapse minor
punctuation/casing differences but cannot resolve abbreviation↔full-name or multilingual
equivalence (e.g. "BaFin" ↔ "Bundesanstalt für Finanzdienstleistungsaufsicht").

**What v1 does instead.** A deterministic canonicalization — lowercase, strip punctuation and
whitespace, drop common legal suffixes (`"authority"`, `"board"`, `"commission"`, `"inc"`,
`"ltd"`) — collapses the most trivial variants. Records whose canonical form matches another
raw name are surfaced as `regulator_near_duplicate` anomalies (11th rule in `anomaly_report`).
The count and a drill-down frame are shown in Cockpit §7.3; no canonical entity table is built.

---

## 5. `update_type` taxonomy consolidation via semantic clustering

**What it would do.** The corpus has 56 distinct `update_type` values, many of which are
semantically redundant (e.g. "Guidance" / "Final Guidance" / "Technical Guidance"). A v2 step
would embed the raw values and cluster them into a consolidated taxonomy of ~10–15 meaningful
event types, then back-fill the canonical type onto each record.

**Why it needs an LLM.** Human-readable type labels have no stable lexical structure; two labels
that share no tokens can be semantically identical, while two labels that share a token can be
meaningfully distinct. Embedding-based clustering or an LLM-based taxonomy-mapper is needed.

**What v1 does instead.** The raw `update_type` distribution is shown as-is (top-N + explicit
long-tail count in Gallery §6.2 v3). The `update_type_rare` anomaly rule flags types whose
frequency falls below `config.RARE_UPDATE_TYPE_CUTOFF`, surfacing the sprawl without resolving
it. The 56-type count is reported honestly.

---

## 6. Topic-to-category auto-classification

**What it would do.** New topics added to the Carver monitoring universe that have not yet been
assigned a category in the catalog could be automatically classified into Finance, Data
protection & cybersecurity, Medical Devices (or other categories) based on the topic's name,
acronym, and the content of its annotations.

**Why it needs an LLM.** The v1 classification source is the explicit catalog assignment from
`GET /api/v1/feeds/categories/{id}/topics` (most-specific rule). For uncatalogued topics the
assignment is absent; inferring it from text requires reading the topic name and annotation
content, which is a language understanding task.

**What v1 does instead.** `normalize_frame` left-joins on `topic_id` from `topic_categories.csv`
(610 entries covering the three showcased categories). Topics absent from the join resolve to
`"Uncategorized"` — a truthful label that is visible in the breadth views rather than a silent
fabricated assignment. The "Uncategorized" share is reported, not hidden.

---

## 7. Semantic duplicate detection beyond exact `entry_id` match

**What it would do.** Two records with different `entry_id` values may represent the same
regulatory event published at two different URLs (e.g. an agency's own site and an official
gazette re-publish). A v2 deduplication step would use embedding similarity over `title`,
`regulator_name`, `update_type`, `jurisdiction_country`, and `reconciled_published_date` to
detect near-duplicate annotations — records that should probably be merged or suppressed.

**Why it needs an LLM.** Title-text similarity alone is unreliable (different phrasings of the
same event); multi-field fuzzy scoring over mixed types is expensive to tune and fragile.
Embedding the concatenated key fields and thresholding cosine distance is the right approach.

**What v1 does instead.** The `duplicate_entry_id` anomaly rule flags records where the same
`entry_id` appears more than once in the snapshot (an exact deduplication signal). Cross-row
semantic similarity is not computed. The exact-duplicate count and drill-down frame are
surfaced in Cockpit §7.3.

---

## 8. "Ask the corpus" natural-language Q&A

**What it would do.** A conversational interface over the 58,982-record corpus: a user asks
"Which regulators issued the most guidance on AI in 2025?" or "Show me all Medical Devices
annotations from the EU with a comment deadline in the next 60 days" and receives a natural-
language answer with a supporting table — combining structured-query generation and
conversational synthesis in a single interface.

**Why it needs an LLM.** Structured-filter composition from free-form natural language requires
a language model to parse intent, map to filter dimensions, generate a query, and narrate the
result. The retrieval half could be structured (SQL/pandas); the narration and intent-parsing
halves require a model.

**What v1 does instead.** The Gallery sidebar filters expose the same dimensions
(category, jurisdiction, regulator, update_type, score ranges, date range, richness score) as
independently selectable controls. The user composes their own query through the UI. No
conversational interface exists.

---

## 9. Label/score calibration explanation and re-scoring suggestions

**What it would do.** The corpus has a measurable rate of `label_score_mismatch` (label says
"high" but score is 3.2; or label says "low" but score is 7.8 — detected by comparing the stored
label against the `[0,4)/[4,7)/[7,10]` band convention). A v2 LLM step would read the annotation
content for flagged records and generate a short explanation of whether the label or the score is
likely wrong, and why — providing actionable calibration signal to the model team.

**Why it needs an LLM.** The v1 rule detects the mismatch deterministically but cannot adjudicate
which side is incorrect. Deciding whether a "high-label / low-score" record reflects a scoring
model calibration error or a labeling error requires reading the content — the impact summary,
the actionables, the regulatory context — and applying domain judgment.

**What v1 does instead.** The `label_score_mismatch` anomaly rule counts all mismatches across
the three score axes (impact, urgency, relevance) and surfaces the offending records in Cockpit
§7.3. The per-axis label-vs-score heatmap in Gallery §6.2 v7 makes the distribution pattern
visually apparent. No content-based explanation or re-scoring suggestion is generated.

---

## 10. Entity normalization and resolution

**What it would do.** The `entities` field contains named people, regulatory bodies, legislation
titles, and companies mentioned in annotation records. These are unstructured free-text mentions.
A v2 entity-normalization step would link each mention to a canonical entity (a person,
a known regulator, a piece of legislation by official title + citation) using named-entity
recognition and entity linking, building a structured entity graph over the corpus.

**Why it needs an LLM.** Free-text entity mentions do not have a stable format. "Secretary
Gensler", "Gary Gensler", and "SEC Chair Gensler" are the same person; "CRD V", "Capital
Requirements Directive V", and "Directive 2019/878/EU" are the same instrument. Resolving these
requires reading context and matching against a knowledge base — an NER + entity-linking task.

**What v1 does instead.** `entities` is normalized as a list of raw strings. The count
(`n_entities`) contributes to the richness score formula (§5.2) and is displayed in the
single-record drill-down and highlight reel. No canonicalization, deduplication, or cross-record
entity graph is built.

---

*This document captures enhancements that are out of scope for v1 (deterministic, no LLM),
not deferred due to effort alone. Each item was explicitly identified during the v1 build as a
place where a language model would add genuine value beyond what a formula or rule can provide.*
