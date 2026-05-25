# Fraud Ops Agent Runbook

1. On a flagged transaction event: read `policies/fraud_monitoring/rules.yaml`.
2. Compute the merchant's rolling fraud-to-sales ratio.
3. If ratio ≥ `fraud_to_sales_ratio_threshold` AND count ≥ `min_count_per_month`,
   escalate to human review.
4. Document the case ID + supporting transactions in the case file.
5. If escalation is approved, notify the acquirer per the policy actions list.
