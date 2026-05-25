# Fraud Monitoring

Acme Pay monitors merchant fraud activity on a monthly basis to detect patterns that
exceed Mastercard's acceptable fraud-to-sales thresholds. A merchant whose rolling
monthly fraud-to-sales ratio meets or exceeds 1.5% (0.015) and whose fraud count
reaches at least 100 transactions in that same month triggers mandatory escalation
under this policy.

## When this policy applies

This policy applies to all merchants processed through Acme Pay's acquiring platform
where Mastercard is the applicable card network. It governs both card-present and
card-not-present transaction streams.

## Required actions

1. Compute the merchant's rolling fraud-to-sales ratio each calendar month.
2. If the ratio meets or exceeds the threshold AND the minimum count is reached,
   escalate the merchant account to human review immediately.
3. Notify the acquiring compliance officer and document the case ID with supporting
   transaction data.
4. Track case progress until the account returns to threshold compliance or is
   terminated.

Source authority: Mastercard SPME §3.7.
