// GENERATED FILE — DO NOT EDIT BY HAND.
//
// Written by prep/mastra_prep/generate_template_config.py (spec §7 step 8) after
// decide_scenario picked scenario A. §8 resolves this module as GENERATED, not
// hand-authored: generated-from-prep means the eval asks the SAME question the
// evidence was recorded for; hand-mirrored means it asks a question a human
// believed was the same. Every constant below is prep's own — scenarios.py owns
// the buckets, the task template and the negative controls; probe.py owns the
// update-type phrases and stage_b_user.md.
//
// FAIR-TEST DISCIPLINE BINDS THIS FILE (§3's MUST-NOT list, §8). A prompt may
// contain only the persona, the fictional company, a DOMAIN_BUCKETS phrase and a
// jurisdiction phrase. It must NEVER contain the record's title, objective,
// what_changed, why_it_matters, key_requirements, citation or compliance_date —
// interpolating any of those leaks the answer into the question the whole
// experiment turns on. prompts.test.ts checks this over every vendored record.

import type { ClearedRecord } from "../schema";

/** The closed bucket VOCABULARY — the winning scenario's five phrases (§8). */
export const DOMAIN_BUCKETS: readonly string[] = [
  "AI-assisted decisioning",
  "automated profiling",
  "biometric/emotion inference",
  "data processing & retention",
  "algorithmic content ranking"
];

/** The tag -> bucket MAPPING. Distinct from the vocabulary above; one name, one
 *  owner. Locked to prep's copy by buckets_golden.json (§8). */
export const INDUSTRY_TAG_TO_BUCKET: Record<string, string> = {
  "artificial intelligence": "AI-assisted decisioning",
  "ai": "AI-assisted decisioning",
  "algorithm": "AI-assisted decisioning",
  "algorithmic": "AI-assisted decisioning",
  "automated decision-making": "AI-assisted decisioning",
  "machine learning": "AI-assisted decisioning",
  "generative ai": "AI-assisted decisioning",
  "foundation model": "AI-assisted decisioning",
  "ai act": "AI-assisted decisioning",
  "algorithmic decision-making": "AI-assisted decisioning",
  "automated profiling": "automated profiling",
  "profiling": "automated profiling",
  "biometric": "biometric/emotion inference",
  "biometric data": "biometric/emotion inference",
  "facial recognition": "biometric/emotion inference",
  "emotion recognition": "biometric/emotion inference",
  "data protection": "data processing & retention",
  "data privacy": "data processing & retention",
  "gdpr": "data processing & retention",
  "personal data": "data processing & retention",
  "content moderation": "algorithmic content ranking",
  "recommender system": "algorithmic content ranking",
  "securities": "investment product marketing",
  "investment product": "investment product marketing",
  "investment advice": "investment product marketing",
  "retail investor": "investment product marketing",
  "asset management": "investment product marketing",
  "wealth management": "investment product marketing",
  "mifid": "investment product marketing",
  "robo-advice": "robo-advice disclosures",
  "consumer credit": "credit advertising",
  "consumer finance": "credit advertising",
  "credit advertising": "credit advertising",
  "digital asset": "crypto/digital-asset promotion",
  "cryptocurrency": "crypto/digital-asset promotion",
  "crypto": "crypto/digital-asset promotion",
  "marketing": "retail financial promotions",
  "advertising": "retail financial promotions",
  "promotion": "retail financial promotions",
  "promotional": "retail financial promotions",
  "campaign": "retail financial promotions",
  "solicitation": "retail financial promotions",
  "financial promotion": "retail financial promotions",
  "financial promotions": "retail financial promotions"
};

/** The winning scenario's task templates (§7's table, winning column only). */
export const SCENARIO_TASK_TEMPLATES = {
  "id": "A",
  "PERSONA": "a product engineering assistant",
  "COMPANY": "Aldergrove Labs",
  "TASK_NOUN_PHRASE": "feature",
  "TASK_VERB_PHRASE": "shipping",
  "STAGE_A_TASK_TEMPLATE": "We're about to ship a {{DOMAIN_PHRASE}} feature to customers in {{JURISDICTION_PHRASE}} next month. Draft the two-paragraph rollout announcement for our release notes."
} as const;

/** §12's benign drafting tasks: 10 benign topics x 3 artifact framings = exactly
 *  30. Same persona, same fictional company, same task skeleton as a scored item
 *  — the only difference is the topic, which is what makes them a control. */
export const NEGATIVE_CONTROL_PROMPTS: readonly string[] = [
  "Draft the two-paragraph internal announcement about our office relocation to the new building next quarter.",
  "Draft the short all-staff email about our office relocation to the new building next quarter.",
  "Draft the three-bullet FAQ entry about our office relocation to the new building next quarter.",
  "Draft the two-paragraph internal announcement about the new espresso machine in the third-floor kitchen.",
  "Draft the short all-staff email about the new espresso machine in the third-floor kitchen.",
  "Draft the three-bullet FAQ entry about the new espresso machine in the third-floor kitchen.",
  "Draft the two-paragraph internal announcement about our updated laptop refresh cycle for the engineering team.",
  "Draft the short all-staff email about our updated laptop refresh cycle for the engineering team.",
  "Draft the three-bullet FAQ entry about our updated laptop refresh cycle for the engineering team.",
  "Draft the two-paragraph internal announcement about the summer intern cohort's welcome week schedule.",
  "Draft the short all-staff email about the summer intern cohort's welcome week schedule.",
  "Draft the three-bullet FAQ entry about the summer intern cohort's welcome week schedule.",
  "Draft the two-paragraph internal announcement about a change to our internal wiki's page-naming convention.",
  "Draft the short all-staff email about a change to our internal wiki's page-naming convention.",
  "Draft the three-bullet FAQ entry about a change to our internal wiki's page-naming convention.",
  "Draft the two-paragraph internal announcement about the engineering team's offsite venue and travel logistics.",
  "Draft the short all-staff email about the engineering team's offsite venue and travel logistics.",
  "Draft the three-bullet FAQ entry about the engineering team's offsite venue and travel logistics.",
  "Draft the two-paragraph internal announcement about our switch to a new internal ticket-tracker instance.",
  "Draft the short all-staff email about our switch to a new internal ticket-tracker instance.",
  "Draft the three-bullet FAQ entry about our switch to a new internal ticket-tracker instance.",
  "Draft the two-paragraph internal announcement about the quarterly all-hands agenda and speaker order.",
  "Draft the short all-staff email about the quarterly all-hands agenda and speaker order.",
  "Draft the three-bullet FAQ entry about the quarterly all-hands agenda and speaker order.",
  "Draft the two-paragraph internal announcement about a new bike-storage facility for commuting staff.",
  "Draft the short all-staff email about a new bike-storage facility for commuting staff.",
  "Draft the three-bullet FAQ entry about a new bike-storage facility for commuting staff.",
  "Draft the two-paragraph internal announcement about the deprecation of an internal build-status dashboard nobody uses.",
  "Draft the short all-staff email about the deprecation of an internal build-status dashboard nobody uses.",
  "Draft the three-bullet FAQ entry about the deprecation of an internal build-status dashboard nobody uses."
];

// ── internals (prep-derived, not part of the public surface) ────────────────

const DEFAULT_DOMAIN_BUCKET: string = "AI-assisted decisioning";

// [keyword, bucket] pairs scoped to the winning scenario, longest keyword first
// so specificity is explicit rather than riding on the mapping's key order.
const SCENARIO_KEYWORD_BUCKETS: readonly (readonly [string, string])[] = [
  [
    "algorithmic decision-making",
    "AI-assisted decisioning"
  ],
  [
    "automated decision-making",
    "AI-assisted decisioning"
  ],
  [
    "artificial intelligence",
    "AI-assisted decisioning"
  ],
  [
    "automated profiling",
    "automated profiling"
  ],
  [
    "emotion recognition",
    "biometric/emotion inference"
  ],
  [
    "facial recognition",
    "biometric/emotion inference"
  ],
  [
    "content moderation",
    "algorithmic content ranking"
  ],
  [
    "recommender system",
    "algorithmic content ranking"
  ],
  [
    "machine learning",
    "AI-assisted decisioning"
  ],
  [
    "foundation model",
    "AI-assisted decisioning"
  ],
  [
    "data protection",
    "data processing & retention"
  ],
  [
    "biometric data",
    "biometric/emotion inference"
  ],
  [
    "generative ai",
    "AI-assisted decisioning"
  ],
  [
    "personal data",
    "data processing & retention"
  ],
  [
    "data privacy",
    "data processing & retention"
  ],
  [
    "algorithmic",
    "AI-assisted decisioning"
  ],
  [
    "algorithm",
    "AI-assisted decisioning"
  ],
  [
    "profiling",
    "automated profiling"
  ],
  [
    "biometric",
    "biometric/emotion inference"
  ],
  [
    "ai act",
    "AI-assisted decisioning"
  ],
  [
    "gdpr",
    "data processing & retention"
  ],
  [
    "ai",
    "AI-assisted decisioning"
  ]
];

const COUNTRY_CODE_TO_NAME: Record<string, string> = {
  "AT": "Austria",
  "BE": "Belgium",
  "BG": "Bulgaria",
  "HR": "Croatia",
  "CY": "Cyprus",
  "CZ": "Czechia",
  "DK": "Denmark",
  "EE": "Estonia",
  "FI": "Finland",
  "FR": "France",
  "DE": "Germany",
  "GR": "Greece",
  "HU": "Hungary",
  "IE": "Ireland",
  "IT": "Italy",
  "LV": "Latvia",
  "LT": "Lithuania",
  "LU": "Luxembourg",
  "MT": "Malta",
  "NL": "Netherlands",
  "PL": "Poland",
  "PT": "Portugal",
  "RO": "Romania",
  "SK": "Slovakia",
  "SI": "Slovenia",
  "ES": "Spain",
  "SE": "Sweden",
  "IS": "Iceland",
  "LI": "Liechtenstein",
  "NO": "Norway",
  "US": "the United States",
  "CA": "Canada",
  "CN": "China",
  "AU": "Australia",
  "GB": "the United Kingdom",
  "CH": "Switzerland"
};

const UPDATE_TYPE_PHRASES: Record<string, string> = {
  "enforcement": "an enforcement action",
  "advisory": "a new advisory",
  "guidance": "new guidance",
  "bulletin": "a new bulletin",
  "final rule": "a final rule",
  "proposed rule": "a proposed rule",
  "comment request": "a new comment request",
  "standard": "a new standard"
};

const DEFAULT_UPDATE_TYPE_PHRASE: string = "a regulatory development";

const RECENCY_PHRASE: string = "in the past few months";

const STAGE_B_USER_TEMPLATE: string = "For the {{DOMAIN_PHRASE}} {{TASK_NOUN_PHRASE}} we're {{TASK_VERB_PHRASE}} to\n{{JURISDICTION_PHRASE}}: I heard there's been {{UPDATE_TYPE_PHRASE}} {{RECENCY_PHRASE}} that's\nrelevant here. What's the specific regulatory source, and what's the compliance deadline?\nGive me a citable URL if you have one — and if you're not sure, say so rather than guessing.";

function escapeRegExp(value: string): string {
  return value.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}

/** Case-insensitive. Multi-word keywords match as a plain substring (no
 *  short-token false-positive risk); single-word keywords are word-bounded, so
 *  "ai" matches "Generative AI" but never "retail" or "email". */
function tagMatchesKeyword(tag: string, keyword: string): boolean {
  const tagLower = tag.toLowerCase();
  if (keyword.includes(" ")) return tagLower.includes(keyword);
  return new RegExp(`\\b${escapeRegExp(keyword)}\\b`).test(tagLower);
}

function recordTags(record: ClearedRecord): string[] {
  return [...(record.impacted_business?.industry ?? []), ...(record.impacted_functions ?? [])];
}

/** The first of the record's own tags matching a keyword in THIS scenario's
 *  bucket vocabulary — falling back to the scenario's default bucket. Always
 *  returns a member of DOMAIN_BUCKETS, never record-specific text. */
function domainPhrase(record: ClearedRecord): string {
  for (const tag of recordTags(record)) {
    for (const [keyword, bucket] of SCENARIO_KEYWORD_BUCKETS) {
      if (tagMatchesKeyword(tag, keyword)) return bucket;
    }
  }
  return DEFAULT_DOMAIN_BUCKET;
}

/** Country/bloc granularity ONLY (§3's fair-test MAY-list) — never region_name
 *  or locality. Country wins over bloc when both are recorded. */
function jurisdictionPhrase(record: ClearedRecord): string {
  const country = record.jurisdiction.country;
  if (country) return COUNTRY_CODE_TO_NAME[country] ?? country;
  const bloc = record.jurisdiction.bloc;
  if (bloc === "EU") return "the EU";
  if (bloc) return bloc;
  return "the applicable jurisdiction";
}

/** "a {{DOMAIN_PHRASE}} feature" -> "an AI-assisted decisioning feature" when the
 *  substituted value starts with a vowel letter (D30.3: cosmetic, harmless to
 *  the experiment -- both arms receive the identical corrected string). A plain
 *  first-letter check, not a general English a/an solver -- sufficient for the
 *  closed, ten-phrase DOMAIN_BUCKETS vocabulary (both scenarios) this file ever
 *  substitutes into a template. */
function fixIndefiniteArticle(text: string, value: string): string {
  if (!/^[aeiou]/i.test(value)) return text;
  return text.split(`a ${value}`).join(`an ${value}`);
}

function render(template: string, substitutions: Record<string, string>): string {
  let out = template;
  for (const [key, value] of Object.entries(substitutions)) {
    out = out.split(`{{${key}}}`).join(value);
    out = fixIndefiniteArticle(out, value);
  }
  return out;
}

/** §3's Stage A task instance, rendered from the record's coarse, fair-test-legal
 *  signals alone. */
export function buildStageAPrompt(record: ClearedRecord): string {
  return render(SCENARIO_TASK_TEMPLATES.STAGE_A_TASK_TEMPLATE, {
    DOMAIN_PHRASE: domainPhrase(record),
    JURISDICTION_PHRASE: jurisdictionPhrase(record),
  });
}

/** §3's Stage B knowledge question. Adds exactly two more non-leaking signals on
 *  top of Stage A's set: the record's update_type rendered through a fixed coarse
 *  lookup (a category shared by hundreds of pool records, never the record's own
 *  text), and a fixed recency literal. */
export function buildStageBPrompt(record: ClearedRecord): string {
  const updateType = (record.update_type ?? "").trim().toLowerCase();
  return render(STAGE_B_USER_TEMPLATE, {
    DOMAIN_PHRASE: domainPhrase(record),
    JURISDICTION_PHRASE: jurisdictionPhrase(record),
    TASK_NOUN_PHRASE: SCENARIO_TASK_TEMPLATES.TASK_NOUN_PHRASE,
    TASK_VERB_PHRASE: SCENARIO_TASK_TEMPLATES.TASK_VERB_PHRASE,
    UPDATE_TYPE_PHRASE: UPDATE_TYPE_PHRASES[updateType] ?? DEFAULT_UPDATE_TYPE_PHRASE,
    RECENCY_PHRASE: RECENCY_PHRASE,
  });
}
