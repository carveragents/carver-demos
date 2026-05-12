# meridian_post_processor.yaml
version: 2026.05
regulatory_basis:
  - Reg E §1005.7 — required disclosures
  - TILA disclosures
  - CFPB June 2023 §IV — chatbot identity disclosure
  - State money transmitter consumer notices

transformations:
  - id: chatbot_identity_disclosure
    rule: |
      First response in any new conversation must include identification as an 
      AI assistant and offer to transfer to a human.
    template: |
      "I'm Meridian Pay's AI assistant — happy to help. If you'd rather speak 
      with a person at any point, just say so."
    
  - id: dispute_disclosure_append
    trigger: response_contains_dispute_acceptance
    append: |
      "We'll investigate within 10 business days as required by federal law. 
      You'll get an update by email."
    regulatory_citation: Reg E §1005.11(c)
    
  - id: pii_final_redaction
    rule: any_residual_PII_in_output_is_redacted
    patterns: [ssn, full_pan, dob]
    
  - id: link_canonicalization
    rule: all_external_links_must_resolve_to_meridianpay.com
    on_violation: strip_link
    
  - id: required_complaint_pathway
    trigger: conversation_involves_complaint_signal
    append_once: |
      "If you'd like to escalate this externally, you can file with the CFPB at 
      consumerfinance.gov/complaint."
    
  - id: end_of_conversation_summary
    trigger: handoff_or_resolution
    behavior: |
      Send the customer a written summary of what was discussed and any actions 
      taken. Required for dispute initiations and card actions.
    regulatory_citation: GLBA recordkeeping + UDAAP transparency
    
  - id: human_review_flag_high_value
    trigger: dispute_amount_over_500_or_fraud_indicated
    action: route_to_human_review_before_send
    
  - id: jurisdiction_specific_appendage
    trigger: customer_state_in_known_list
    NY: "New York residents: you can also contact the NYDFS at dfs.ny.gov"
    CA: "California residents: see our privacy notice at meridianpay.com/ca-privacy"
    # ... etc

audit_artifacts_generated:
  per_conversation:
    - full_transcript
    - retrieved_documents_used
    - tools_called
    - validator_decisions
    - post_processor_transformations_applied
    - human_handoffs
  retention: 7_years
  immutable: true
  access: compliance_team + legal + customer_on_request