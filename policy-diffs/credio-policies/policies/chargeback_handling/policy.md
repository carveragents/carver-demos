# Chargeback Handling

Chargebacks are cardholder-initiated disputes against a transaction. Halyard Pay, as the
acquirer, is responsible for managing the full dispute lifecycle on behalf of its
merchants from initial first presentment through arbitration. Each stage of the
lifecycle has specific evidence requirements and strict response deadlines imposed
by Mastercard network rules.

## Lifecycle overview

Disputes progress through a defined set of states: first presentment, chargeback,
second presentment (re-presentment), pre-arbitration, and arbitration. Failure to
respond within the applicable timeframe at any stage results in an automatic ruling
against the acquirer.

## Required actions

1. Acknowledge each incoming chargeback within one business day of receipt.
2. Gather required evidence for the relevant lifecycle state.
3. Submit a second presentment (re-presentment) where merchant liability can be
   contested, including compelling evidence.
4. Escalate to pre-arbitration and arbitration only after second presentment is
   rejected by the issuer.
5. Maintain complete case records for audit and regulatory reporting.

Source authority: Mastercard SPME §10.1.
