# meridian_topic_router.yaml
version: 2026.05
regulatory_basis:
  - CFPB June 2023 Chatbot Guidance §II — limiting chatbot scope
  - State money transmitter licensing — no unauthorized advice
  - SEC Reg BI / FINRA — not a registered investment advisor

allowed_topics:
  - card_replacement
  - transaction_lookup_own_account
  - dispute_initiation
  - account_balance_inquiry
  - statement_request
  - contact_info_update
  - app_navigation_help
  - hours_and_locations
  - general_product_questions

restricted_topics:
  - id: investment_advice
    trigger_terms: ["should I invest", "is this a good investment", "what stock", "crypto recommendation"]
    response: hard_refusal
    refusal_template: |
      I can't provide investment advice. For investment questions, please 
      consult a licensed financial advisor.
    
  - id: legal_advice
    trigger_terms: ["sue", "lawsuit", "is this legal", "my rights", "discrimination"]
    response: soft_refusal_with_escalation
    escalation_path: complaints_team
    refusal_template: |
      I can't provide legal advice, but I want to make sure you're heard. 
      I'm connecting you with someone who can help.
    
  - id: fee_waiver_decisions
    trigger_terms: ["waive my fee", "refund this fee", "cancel the charge"]
    response: escalate_only
    escalation_path: human_agent
    never_commit: true  # critical: do not promise outcome
    handoff_template: |
      Let me get you to someone who can review this fee with you.
    
  - id: complaint_filing
    trigger_terms: ["file a complaint", "report to CFPB", "regulatory complaint"]
    response: facilitate_and_disclose
    required_disclosure: |
      You have the right to file a complaint with the CFPB at consumerfinance.gov/complaint
      or with your state regulator. I can also open an internal complaint case for you.
    # CFPB explicitly prohibits discouraging complaints
    
  - id: account_closure
    response: escalate_only
    escalation_path: retention_team
    
  - id: credit_decisions
    response: hard_refusal
    refusal_template: |
      Credit decisions need to be handled by our lending team. Let me transfer you.

prohibited_outputs:
  - rate_quotes_not_in_kb
  - approval_promises
  - timeline_commitments_beyond_24h
  - comparisons_to_competitors
  - personal_opinions_on_products