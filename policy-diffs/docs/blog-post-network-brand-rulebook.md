# Tracking a network brand's rulebook with an AI agent

Every payment processor running on Mastercard rails has somebody whose job, in part, is reading Mastercard's Security Rules and Procedures publication. Mastercard calls it SPME. It's about 800 pages, written by lawyers, and a new release lands every four to six months.

Each release contains changes a compliance team has to find. A new acquirer obligation. A validation cadence that used to be annual and is now biennial. A program rename that quietly redefines who counts as an in-scope service provider. Those changes ripple downstream into the processor's own policies: fraud monitoring rules, merchant onboarding controls, service-provider validation schedules.

Most teams do this by hand. Previous PDF on one monitor, the new one on the other, an analyst hunting for what changed and trying to work out which internal policies are now out of step. The deadlines are external. The cost of a missed material change is not the cost of a typo.

We built a demo of what this looks like when an AI agent does the first pass.

## What we built

Five Mastercard SPME releases, from June 2022 through May 2025. For each pair of consecutive releases, the agent does three things. It detects every section that changed. It assigns each change a materiality grade: breaking, substantive, clarifying, or cosmetic. And it drafts a corresponding edit to the payment processor's internal policies. The processor here is fictional; we called it Halyard Pay and gave it synthetic baseline policies, so the proposals you'll see are illustrative, not legally meaningful.

Across the full timeline the agent produced 214 proposed revisions, 15 of them flagged as breaking, touching 8 policy areas. Those numbers are specific because the demo is. In a real compliance estate the totals would be different on day one and they'd shift every quarter.

The output is a website you can click through. A five-minute narrated walkthrough sits on the same page. Both are linked at the bottom of this post.

## What's interesting in the demo itself

### Materiality is graded

Not every change in the rule text matters in practice. Mastercard rewrites paragraphs constantly. Some of those rewrites change a real obligation; most are cleanup. The agent grades every change it finds, and that grade is what tells a reviewer whether to read the diff line by line or just skim it.

In the first transition the demo covers, June 2022 to May 2023, the agent flagged 4 changes as breaking and 44 as substantive, across 7 affected policies. That's what a compliance lead actually wants on a Monday morning. How many things matter, how bad, and where to look first.

### Every claim links back to the source

For each proposed change, the detail page cites the SPME section number and links straight to the Mastercard PDF, opened at the exact page where that section lives. We did this because an AI proposal nobody can verify is worse than no proposal. A reviewer is one click from the original Mastercard text. They can disagree with the agent if they want, and they should.

A second use for the same links: when the agent gets something wrong, and it will, the audit trail is already there.

### The agent flags what it might have gotten wrong

Here's the piece we cared about most. Section 8.6.5, Chargeback Responsibility, in the June 2022 release. A page running-header in the source PDF confused the section detector, and body text from a neighbouring section bled into 8.6.5. The agent's confidence score caught the inconsistency, and the change page opens with a yellow extraction-warning callout that tells the reviewer the source extraction looks suspect before they read any of the agent's actual claim.

Across the 214 proposals in the demo, 22 carry this kind of self-doubt flag. The reviewer sees the warning first.

## Why this is a regulatory risk intelligence problem

A card network's rulebook isn't statutory regulation. But from inside a payment processor, it looks and feels the same. The text is published by an external authority on a cadence outside your control. It updates without warning to your release schedule. Missing something has real costs: fines, loss of network access, MATCH-list exposure, reputational damage with the network itself. Swap SPME out for FedNow operating procedures, OCC interagency guidance, or the FFIEC IT handbook, and the work is the same.

This is the same problem our [previous post on programmatic AI compliance](https://carveragents.ai/programmatic-ai-compliance/what-happens-when-you-turn-off-the-guardrails-on-an-ai-agent) takes at the framework level. *Continuous policy maintenance is the steady state, not the audit moment.* The demo runs that idea against one concrete signal stream, in a form a compliance reviewer can audit as they go.

## What this is a step toward

The state to get to is a payment processor whose policy estate quietly stays current against the rule streams it depends on, with reviewers spending their time only on the items the agent isn't sure about. That keeps people on judgment calls instead of file-by-file comparisons. The current demo runs against one rulebook from one network. Most regulated payments businesses are supposed to be tracking a dozen authoritative texts already, and the same pattern applies to each.

## Try it

- Click through the [interactive site](https://carveragents.github.io/carver-briefs/policy-diffs/). Five releases, every change, every PDF page anchor.
- Watch the [five-minute narrated walkthrough](#).


