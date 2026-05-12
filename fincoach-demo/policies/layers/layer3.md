# meridian_retrieval_policy.yaml
version: 2026.05
regulatory_basis:
  - Moffatt v. Air Canada (2024) — negligent misrepresentation by agent
  - CFPB June 2023 §II.A — accurate information requirement
  - Reg E §1005.7 — required disclosures must be accurate

knowledge_base:
  source: vetted_policy_corpus_v2026_05
  approval_authority: legal_and_compliance_team
  last_audit: 2026-04-15
  refresh_cadence: weekly
  expiration_policy: documents_older_than_90_days_flagged

retrieval_rules:
  - rule: grounded_answers_only
    description: |
      For any question about Meridian Pay policies, fees, terms, or procedures,
      the agent MUST retrieve at least one document with relevance >= 0.78.
      If no document meets threshold, the agent MUST NOT answer from parametric knowledge.
    enforcement: hard
    fallback_response: |
      I don't have specific information about that. Let me connect you with 
      someone who can give you an accurate answer.
    
  - rule: citation_required
    description: |
      Every factual claim about a policy must be traceable to a retrieved document.
      The agent's response is post-validated against retrieved content (see Layer 6).
    enforcement: hard
    
  - rule: link_to_authoritative_source
    description: |
      Where a customer asks about a policy, response must include a link to the 
      authoritative policy page on meridianpay.com.
    enforcement: hard
    
  - rule: temporal_freshness
    description: |
      Fee schedules, rates, and limits must be retrieved from documents 
      updated within the last 30 days. Older documents are excluded.
    enforcement: hard

corpus_segmentation:
  customer_facing:
    - product_descriptions
    - published_fee_schedules
    - terms_of_service_current
    - faq_approved
  internal_only:
    - dispute_workflows
    - escalation_runbooks
  excluded_from_agent:
    - underwriting_criteria
    - fraud_detection_rules
    - employee_handbook
    - legal_strategy_docs