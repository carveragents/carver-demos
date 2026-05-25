# BRAM Response Agent Runbook

1. On BRAM notice received: read `policies/bram_response/rules.yaml`.
2. Halt actions listed under `halt_actions`.
3. Open a case file; collect evidence from data sources matching `required_evidence`.
4. Notify Credio Compliance lead within `internal_notification_hours` hours.
5. Submit response within `response_window_days` days.
