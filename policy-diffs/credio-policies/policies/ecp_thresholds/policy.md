# Excessive Chargeback Program (ECP) Thresholds

Mastercard's Excessive Chargeback Program (ECP) identifies merchants whose chargeback
activity exceeds defined monthly ratios relative to their transaction volume. Acme Pay
monitors merchant chargeback-to-transaction ratios on a monthly basis and escalates
merchants that breach program tiers to the appropriate remediation track.

## Program tiers

Two tiers define the escalation ladder:
- **Standard**: chargeback-to-transaction ratio of 1.5% (0.015) or greater and at
  least 100 chargebacks in the month.
- **Excessive**: ratio of 3.0% (0.03) or greater in the same measurement period.

## Required actions

1. Calculate each merchant's chargeback-to-transaction ratio at month close.
2. Assign the merchant to the applicable tier if thresholds are met.
3. Open an ECP case and notify the merchant within five business days.
4. Track the merchant's progress on a monthly basis until they exit the program.
5. Escalate to chargeback agent for automated case management.

Source authority: Mastercard SPME §11.4.
