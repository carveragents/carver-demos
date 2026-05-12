# meridian_tool_manifest.yaml
version: 2026.05
regulatory_basis:
  - SOC 2 CC6.1 — least privilege access
  - GLBA Safeguards §314.4(c)(1) — access controls
  - Internal control framework — segregation of duties

available_tools:
  - name: lookup_transaction
    scope: customer_own_account_only
    auth_required: session_authenticated
    rate_limit: 30_per_session
    audit_log: full
    
  - name: get_account_balance
    scope: customer_own_account_only
    auth_required: session_authenticated
    audit_log: full
    
  - name: initiate_card_replacement
    scope: customer_own_card_only
    auth_required: session_authenticated_plus_step_up
    cost_tier: low  # mailing cost only
    audit_log: full
    confirmation_required: true
    
  - name: open_dispute_case
    scope: customer_own_transaction_only
    auth_required: session_authenticated
    creates: dispute_case_record
    follow_up_required: true
    audit_log: full
    
  - name: escalate_to_human
    scope: any
    auth_required: session_authenticated
    routing: based_on_topic_classification
    audit_log: full
    handoff_includes: conversation_transcript
    
  - name: lookup_policy_document
    scope: customer_facing_corpus_only
    auth_required: none
    audit_log: query_only

explicitly_unavailable_tools:
  # These tools exist in the broader Meridian Pay system but are NOT exposed to the agent
  - waive_fee  # only humans with fee_waiver_authority role can call this
  - issue_refund  # only humans with refund_authority role
  - close_account
  - modify_credit_limit
  - approve_loan
  - send_promotional_offer  # marketing-restricted under UDAAP
  - access_other_customer_data
  - export_customer_data
  - modify_transaction_history

tool_response_handling:
  - rule: confirm_before_acting
    applies_to: [initiate_card_replacement, open_dispute_case]
    pattern: |
      Before calling this tool, the agent must summarize the action in plain 
      language and receive explicit customer confirmation.
  
  - rule: never_simulate
    description: |
      If a tool call fails, the agent must say so honestly. Never fabricate 
      a success response. Never pretend an action was taken.
    enforcement: hard