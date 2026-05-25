# Account-Takeover (ATO) Detection

Account-takeover fraud occurs when a malicious actor gains unauthorized access to
a cardholder's account and initiates transactions without the cardholder's consent.
Acme Pay implements real-time risk scoring on authentication events and enforces a
mandatory 3DS (3-D Secure) challenge for any session where the computed risk score
meets or exceeds the defined threshold.

## Detection signals

The risk model incorporates multiple behavioral signals: geographic anomalies
inconsistent with a cardholder's established pattern, changes to device fingerprint,
transaction velocity breaches, and indicators of credential-stuffing activity.

## Required actions

1. Evaluate each authentication event against the defined signal list in real time.
2. Compute a normalized risk score between 0.0 and 1.0.
3. If the risk score is 0.5 or greater, trigger a mandatory 3DS challenge before
   authorizing the transaction.
4. Log all ATO signals and outcomes in the case management system.
5. Escalate persistent high-risk accounts to the ATO response team for manual review.

Source authority: Mastercard SPME §6.2.
