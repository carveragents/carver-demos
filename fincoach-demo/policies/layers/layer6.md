{
  "validator": "meridian_output_validator_v2026.05",
  "regulatory_basis": [
    "UDAAP — no deceptive statements",
    "Reg E — accurate transaction info",
    "TILA — accurate fee/rate disclosures",
    "Moffatt v. Air Canada — no inventing policies",
    "FTC Act §5 — no unsubstantiated claims"
  ],
  "validators": [
    {
      "id": "grounding_check",
      "type": "llm_judge",
      "model": "validator_judge_v3",
      "checks": "every factual claim in response is supported by retrieved context",
      "on_fail": "regenerate_with_constraint_or_handoff",
      "severity": "blocking"
    },
    {
      "id": "policy_invention_check",
      "type": "llm_judge",
      "checks": "response does not describe any policy, fee, timeline, or term not present in retrieved documents",
      "examples_of_violations": [
        "We offer a 100% refund within 30 days (if not in retrieved docs)",
        "Your card will arrive in 2 business days (if not specified)",
        "There's no fee for this (if not confirmed)"
      ],
      "on_fail": "regenerate_with_constraint_or_handoff",
      "severity": "blocking"
    },
    {
      "id": "commitment_check",
      "type": "rules_plus_llm",
      "rules": [
        "no dollar amounts unless retrieved",
        "no specific dates unless retrieved",
        "no percentages unless retrieved",
        "no use of: 'guaranteed', 'always', 'never fail', 'definitely will'"
      ],
      "on_fail": "rewrite_to_remove_commitment",
      "severity": "blocking"
    },
    {
      "id": "advice_avoidance_check",
      "type": "llm_judge",
      "checks": "response does not provide investment, legal, tax, or financial planning advice",
      "trigger_patterns": [
        "you should invest",
        "your best option is",
        "I recommend",
        "this is legal",
        "you don't need a lawyer"
      ],
      "on_fail": "replace_with_advice_refusal",
      "severity": "blocking"
    },
    {
      "id": "complaint_rights_check",
      "type": "rules",
      "rule": "if conversation involves a complaint and CFPB/regulator option was not mentioned within last 3 turns, add disclosure",
      "on_fail": "append_disclosure",
      "severity": "warning"
    },
    {
      "id": "fair_lending_language_check",
      "type": "llm_judge",
      "checks": "response does not reference protected characteristics in ways that could imply discrimination",
      "on_fail": "block_and_escalate_to_compliance",
      "severity": "blocking"
    },
    {
      "id": "tone_check",
      "type": "classifier",
      "model": "tone_classifier_v2",
      "checks": "response is not condescending, dismissive, or inflammatory",
      "on_fail": "regenerate",
      "severity": "warning"
    },
    {
      "id": "competitor_mention_check",
      "type": "regex_plus_classifier",
      "blocked_terms": ["[competitor names]"],
      "on_fail": "rewrite_neutral",
      "severity": "blocking"
    }
  ],
  "validation_logging": {
    "all_validator_decisions": "logged",
    "blocked_responses": "retained_for_audit_7_years",
    "retention_basis": "GLBA + state recordkeeping"
  }
}