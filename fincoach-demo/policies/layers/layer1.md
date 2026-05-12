# meridian_input_guardrails.yaml
version: 2026.05
applies_to: customer_support_agent
regulatory_basis:
  - GLBA Safeguards Rule §314.4(c) — access controls on customer data
  - CFPB June 2023 Chatbot Guidance §III.B — protecting consumer information
  - PCI-DSS 4.0 Req 3.4 — primary account number masking

detectors:
  - id: pan_detection
    pattern: credit_card_number
    action: redact_and_log
    replacement: "[CARD_REDACTED]"
    severity: high
    
  - id: ssn_detection
    pattern: us_ssn
    action: redact_and_alert
    replacement: "[SSN_REDACTED]"
    alert_channel: security_ops
    
  - id: prompt_injection
    detector: classifier_v3
    threshold: 0.85
    action: block_with_refusal
    refusal_template: "I can only help with account-related questions."
    
  - id: jailbreak_attempt
    patterns:
      - "ignore previous instructions"
      - "you are now"
      - "pretend you are"
      - "system prompt"
    action: block_and_escalate
    
  - id: abusive_language
    classifier: toxicity_v2
    threshold: 0.9
    action: warn_then_disconnect
    warning_template: "I'm here to help with your account. Let's keep our conversation respectful."

logging:
  retention_days: 2555  # 7 years per GLBA
  pii_redacted_before_storage: true