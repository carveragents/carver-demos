"""Classify Carver topics by prediction-market relevance.

Reads data/carver-topics-detailed.json and writes data/regulator-topics.yml.

Heuristic tiers, in priority order:
  T1 — sub_entity_type carries an explicit PM-adjacent label (Securities & Market,
       Derivatives, Futures, Commodity, Gaming, Gambling, Lottery, AML/CFT, FIU).
  T2 — name matches a state-level Securities / Gaming / Lottery / Banking pattern.
  T3 — acronym is in a curated whitelist of known PM-adjacent bodies.
  T4 — name or description contains a PM-domain phrase
       (prediction market, event contract, sportsbook, sports betting, etc.).

Bias broad. False positives are cheap — A5's annotation-level filter narrows.
False negatives are expensive — we'd never pull those annotations.
"""

from __future__ import annotations

import json
import re
from collections import Counter
from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parent.parent
TOPICS_FILE = REPO / "data" / "carver-topics-detailed.json"
OUT_FILE = REPO / "data" / "regulator-topics.yml"

# T1 — sub_entity_type substrings (case-insensitive)
SUB_ENTITY_PM_LABELS = [
    "Securities & Market", "Securities and Market",
    "Derivative", "Futures",
    "Commodit",  # Commodity / Commodities
    "Gaming", "Gambling", "Lottery", "Sports Betting", "Sweepstake",
    "Financial Intelligence", "AML/CFT", "AML / CFT",
]

# T2 — name patterns for state-level / regional PM-adjacent bodies
STATE_NAME_PATTERNS = [
    r"\bSecurities\s+(Department|Commission|Division|Bureau|Board|Regulator|Authority)\b",
    r"\bDepartment of Securities\b",
    r"\bDivision of Securities\b",
    r"\bBureau of Securities\b",
    r"\bGaming\s+(Commission|Control|Board|Authority|Regulator|Enforcement)\b",
    r"\bGambling\s+(Commission|Control|Board|Authority)\b",
    r"\bLottery\s+(Commission|Authority|Board)\b",
    r"\bDivision of Gaming\b",
    r"\bDivision of Gambling\b",
    r"\bRacing\s+(Commission|Board)\b",
    r"\bCorporation Commission\b",  # several state Corp Commissions regulate securities
    r"\bDepartment of Banking\b",
    r"\bDepartment of Financial",  # Financial Institutions / Protection / Regulation
    r"\bOffice of Financial Regulation\b",
    r"\bSecretary of State\b",  # several states' SOS handles securities filings
    r"\bAttorney General\b",  # frequent consumer-protection enforcement
]

# T3 — curated acronym whitelist
KNOWN_PM_ACRONYMS = {
    # US federal
    "CFTC", "SEC", "FINRA", "MSRB", "CFPB", "OCC", "NFA", "FinCEN", "FINCEN",
    "IRS", "FTC", "FRB", "FDIC", "NCUA", "PCAOB", "OFAC", "Treasury",
    # International securities/derivatives
    "ESMA", "FCA", "PRA", "BaFin", "AMF",  # AMF = France or Quebec
    "ASIC", "MAS", "SFC", "CySEC", "IOSCO", "FMA", "FSC", "ASC",
    # Gambling-specific (international)
    "ANJ", "AGCO", "UKGC", "MGA", "KSA", "DCMS",
    # Bank/payment supervisors that touch event-contract platforms via AML
    "BIS", "FATF",
}

# T4 — domain phrases (must be a phrase, not a single ambiguous word)
PM_DOMAIN_PHRASES = [
    "prediction market", "event contract", "binary option",
    "sportsbook", "sports betting", "sports bet", "sports-bet",
    "fantasy sport",
    "wager", "wagering",
    "gambling", "gaming",  # rare in finance-corpus text but valid signal
    "lottery", "sweepstake",
    "commodity exchange", "derivative",
    "broker-dealer", "broker dealer",
    "money services business",
]

# Negative filter: skip these even if they trigger above (clearly not PM-relevant)
NEGATIVE_NAME_PATTERNS = [
    r"\bAlcohol(\s|ic)\b",  # ABC boards
    r"\bTobacco\b",
    r"\bCannabis\b", r"\bMarijuana\b",
    r"\bAir Resources\b", r"\bEnvironmental\b", r"\bRecycle",
    r"\bAgricult", r"\bFood and Drug\b", r"\bPublic Health\b",
    r"\bMotor Vehicles\b", r"\bDept of Transportation\b",
    r"\bElection\b",
    r"\bWildlife\b", r"\bParks\b",
    r"\bOcean", r"\bAtmospheric\b",
    r"\bHomeland Security\b", r"\bImmigration\b",
    r"\bDrug Abuse\b",
    r"\bEnergy\b", r"\bUtilities\b",
    r"\bRailroad\b",
]


def _any_match(patterns: list[str], text: str) -> str | None:
    for p in patterns:
        if re.search(p, text, re.IGNORECASE):
            return p
    return None


def classify(topic: dict) -> tuple[bool, list[str]]:
    reasons: list[str] = []
    name = topic.get("name") or ""
    acronym = (topic.get("acronym") or "").strip()
    description = topic.get("description") or ""
    sectors = topic.get("sectors") or ""
    industries = topic.get("industries") or ""
    functions = topic.get("functions") or ""
    sub_entity_type = topic.get("sub_entity_type") or ""

    # T1 — sub_entity_type label
    for label in SUB_ENTITY_PM_LABELS:
        if label.lower() in sub_entity_type.lower():
            reasons.append(f"t1_sub_entity:{label}")
            break

    # T2 — state-name pattern
    p = _any_match(STATE_NAME_PATTERNS, name)
    if p:
        reasons.append(f"t2_name:{p}")

    # T3 — acronym
    if acronym and acronym in KNOWN_PM_ACRONYMS:
        reasons.append(f"t3_acronym:{acronym}")

    # T4 — domain phrase in name+description+sectors+industries+functions
    haystack = " ".join([name, description, sectors, industries, functions]).lower()
    for phrase in PM_DOMAIN_PHRASES:
        if phrase in haystack:
            reasons.append(f"t4_phrase:{phrase}")
            break

    if not reasons:
        return (False, [])

    # Negative filter
    neg = _any_match(NEGATIVE_NAME_PATTERNS, name)
    if neg:
        # If T1 (explicit sub_entity_type) fired, override the negative — trust structured signal.
        # Otherwise reject as a false positive.
        if not any(r.startswith("t1_sub_entity") for r in reasons):
            return (False, [f"rejected_by_negative:{neg}"])

    return (True, reasons)


def main() -> None:
    topics = json.loads(TOPICS_FILE.read_text())
    print(f"Loaded {len(topics)} topics")

    classified = []
    for t in topics:
        pm, reasons = classify(t)
        classified.append({
            "topic_id": t["id"],
            "name": t.get("name"),
            "acronym": t.get("acronym"),
            "jurisdiction_code": t.get("jurisdiction_code"),
            "scope": t.get("scope"),
            "entity_type": t.get("entity_type"),
            "sub_entity_type": t.get("sub_entity_type"),
            "is_active": t.get("is_active"),
            "pm_relevant": pm,
            "relevance_reasons": reasons,
        })

    pm_topics = [c for c in classified if c["pm_relevant"]]
    print(f"\nPM-relevant: {len(pm_topics)} / {len(classified)}")

    # Breakdown by scope
    print("\nPM-relevant by scope:")
    for k, v in Counter(c.get("scope") or "<empty>" for c in pm_topics).most_common():
        print(f"  {k}: {v}")

    # Breakdown by jurisdiction code (top 30)
    print("\nPM-relevant by jurisdiction_code (top 30):")
    for k, v in Counter(c.get("jurisdiction_code") or "<empty>" for c in pm_topics).most_common(30):
        print(f"  {k}: {v}")

    # US-state breakdown
    us_state = [c for c in pm_topics if (c.get("jurisdiction_code") or "").startswith("US-")]
    print(f"\nPM-relevant US-state topics: {len(us_state)}")
    for c in sorted(us_state, key=lambda x: x.get("jurisdiction_code") or ""):
        print(f"  {c.get('jurisdiction_code'):<7} {c.get('acronym') or '—':<10} {c.get('name')}")

    # US-federal breakdown
    us_fed = [c for c in pm_topics if c.get("jurisdiction_code") == "US"]
    print(f"\nPM-relevant US-federal topics: {len(us_fed)}")
    for c in sorted(us_fed, key=lambda x: x.get("name") or ""):
        print(f"  {c.get('acronym') or '—':<10} {c.get('name')}")

    # Sample rejections-by-negative for inspection
    rejections = [
        c for c in classified
        if not c["pm_relevant"]
        and any(r.startswith("rejected_by_negative") for r in c.get("relevance_reasons", []))
    ]
    print(f"\nRejected-by-negative-filter (sample 15): {len(rejections)} total")
    for c in rejections[:15]:
        print(f"  - {c.get('jurisdiction_code'):<8} {c.get('name')}  reasons={c['relevance_reasons']}")

    OUT_FILE.write_text(yaml.safe_dump(classified, sort_keys=False, allow_unicode=True, width=120))
    print(f"\nWrote {OUT_FILE.relative_to(REPO)}")


if __name__ == "__main__":
    main()
