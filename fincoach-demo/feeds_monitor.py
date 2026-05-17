"""
Carver Feeds SDK integration for Meridian Pay demo.

Fetches enforcement, final-rule, and guidance annotations from six regulators
directly applicable to a consumer banking AI assistant deployment, and computes
which of the 7 deployment layers each signal affects.

Topic IDs confirmed via production server query (May 2026):
  CFPB  5bab5721-56e6-41ad-a6a8-54b534ee7f0b   65 entries / 90 days
  Fed   36ff9f0e-2651-4dbb-9b42-c45eef8233e6  444 entries / 90 days
  FDIC  c4e695da-7b78-45eb-9f51-57b350946019  150 entries / 90 days
  OCC   ef0553d6-b0a2-4d50-b097-ff1ed48a30b9  126 entries / 90 days
  FTC   bfc3cb59-b0ea-4726-867f-42155f156529  796 entries / 90 days
  NYDFS 6c32e3fe-0709-4c6e-bcfb-066da7a57d72  321 entries / 90 days
"""

import logging
import os
from dataclasses import dataclass, field

from carver_feeds.carver_api import CarverFeedsAPIClient

logger = logging.getLogger(__name__)

TOPIC_IDS = {
    "CFPB":  "5bab5721-56e6-41ad-a6a8-54b534ee7f0b",
    "Fed":   "36ff9f0e-2651-4dbb-9b42-c45eef8233e6",
    "FDIC":  "c4e695da-7b78-45eb-9f51-57b350946019",
    "OCC":   "ef0553d6-b0a2-4d50-b097-ff1ed48a30b9",
    "FTC":   "bfc3cb59-b0ea-4726-867f-42155f156529",
    "NYDFS": "6c32e3fe-0709-4c6e-bcfb-066da7a57d72",
}

CARVER_BASE_URL = "https://app.carveragents.ai"

ACCEPTED_UPDATE_TYPES = {"enforcement", "final_rule", "guidance", "proposed_rule"}

# Tags that match signals relevant to a consumer banking AI chatbot deployment.
# Kept specific to avoid pulling in non-fintech FTC/CFPB cases.
RELEVANT_TAGS = {
    # Model risk / AI governance (SR 26-2, Fed/OCC/FDIC interagency guidance)
    "model risk management", "model risk", "artificial intelligence",
    "machine learning", "ai governance", "sr 11-7", "sr 26-2",
    # Cybersecurity / data / PII (NYDFS 23 NYCRR 500, GLBA Safeguards)
    "cybersecurity", "data security", "data breach", "personal information",
    "privacy", "pii", "glba", "safeguards rule", "23 nycrr 500",
    "incident reporting", "consumer data protection",
    # UDAAP / consumer harm in financial products
    "udaap", "deceptive practices", "unfair practices", "abusive practices",
    "consumer restitution", "federal trade commission act",
    "debt collection", "credit reporting", "negative option",
    # Payment / fintech scope (CFPB Wise, Reg E)
    "remittance", "payment firms", "electronic fund transfer",
    "reg e", "error resolution", "dispute resolution", "efta",
    "banking", "banking compliance", "financial institution",
    "prepaid card", "debit card", "money transfer", "payment", "fintech",
    # Fair lending / ECOA
    "fair lending", "ecoa", "equal credit opportunity", "discrimination",
    # Chatbot / AI disclosure
    "chatbot", "ai disclosure", "undisclosed ai", "automated system",
    # Scope / advice
    "unauthorized advice", "investment advice", "complaint handling",
}

# Tags that disqualify a signal regardless of RELEVANT_TAGS matches.
DISQUALIFYING_TAGS = {
    # Non-fintech FTC enforcement (product labeling, manufacturing, antitrust)
    "made in usa", "country of origin", "manufacturing", "labeling",
    "merchandise", "textile", "apparel", "food safety",
    "antitrust", "merger", "divestiture", "anticompetitive",
    "telemarketing", "robocall", "do not call",
    # Non-banking CFPB content
    "medical debt", "wildfire", "natural disaster", "maui",
    "mortgage credit product",
    # NYDFS non-banking
    "virtual currency", "climate change",
}


def _is_relevant(tags: list[str]) -> bool:
    tags_lower = {t.lower() for t in tags}
    if tags_lower & DISQUALIFYING_TAGS:
        return False
    return bool(tags_lower & RELEVANT_TAGS)

# Which tag subsets indicate impact on each deployment layer.
# Mapped against tags confirmed present in CFPB/Fed/FDIC/OCC/FTC/NYDFS feeds.
LAYER_TAG_MAP: dict[int, set[str]] = {
    1: {  # Input Guardrails — PII scrub, data exfiltration detect
        "cybersecurity", "data security", "data breach", "personal information",
        "privacy", "pii", "glba", "safeguards rule", "23 nycrr 500",
        "incident reporting", "consumer data protection",
        "model risk management",
    },
    2: {  # Topic / Intent Router — allowlist, advice scope
        "unauthorized advice", "investment advice", "unlicensed",
        "fair lending", "ecoa", "equal credit opportunity",
        "consumer complaint", "complaint handling",
    },
    3: {  # Retrieval Layer — grounding, accuracy
        "model risk management", "model risk", "sr 26-2", "sr 11-7",
        "false claims", "misleading", "deceptive practices",
        "ai governance", "machine learning", "banking compliance",
    },
    4: {  # System Prompt — role, behavior, identity
        "artificial intelligence", "chatbot", "ai disclosure", "undisclosed ai",
        "automated system", "model risk management", "ai governance",
        "deceptive practices", "udaap", "abusive practices", "banking compliance",
        # Data security signals must also update the system prompt — an agent
        # instructed to send data externally is itself a compliance gap
        "consumer data protection", "data security", "privacy", "pii",
        "cybersecurity", "incident reporting",
    },
    5: {  # Tool Gating — access control, least privilege
        "cybersecurity", "data security", "data breach", "glba",
        "incident reporting", "consumer data protection",
        "model risk management", "unauthorized access",
        "reg e", "electronic fund transfer", "error resolution",
    },
    6: {  # Output Validator — UDAAP, payment compliance, fair lending
        "udaap", "deceptive practices", "unfair practices", "abusive practices",
        "consumer restitution", "federal trade commission act",
        "remittance", "payment firms", "compliance",
        "fair lending", "ecoa", "equal credit opportunity", "discrimination",
        "reg e", "error resolution", "debt collection", "credit reporting",
    },
    7: {  # Post-Processor — disclosures, redaction
        "privacy", "pii", "consumer rights", "disclosure requirements",
        "complaint handling", "consumer complaint",
        "reg e", "electronic fund transfer", "efta",
        "artificial intelligence", "chatbot", "ai disclosure",
    },
}

LAYER_NAMES = {
    1: "Input Guardrails",
    2: "Topic / Intent Router",
    3: "Retrieval Layer",
    4: "System Prompt",
    5: "Tool Gating",
    6: "Output Validator",
    7: "Post-Processor",
}

LAYER_REGULATORS = {
    1: ["GLBA", "CFPB", "PCI-DSS"],
    2: ["CFPB", "SEC / FINRA"],
    3: ["CFPB", "Reg E"],
    4: ["General"],
    5: ["GLBA", "SOC 2", "UDAAP"],
    6: ["UDAAP", "FTC", "Reg E", "TILA"],
    7: ["CFPB", "Reg E", "TILA"],
}


@dataclass
class EnforcementSignal:
    entry_id: str
    title: str
    summary: str
    update_type: str
    topic_name: str
    topic_id: str
    published_at: str
    link: str
    tags: list[str] = field(default_factory=list)
    entities: list[str] = field(default_factory=list)
    has_ai_tag: bool = False
    affected_layers: list[int] = field(default_factory=list)
    # Rich annotation fields
    what_changed: str = ""
    why_it_matters: str = ""
    risk_impact: str = ""
    key_requirements: list[str] = field(default_factory=list)
    policy_change: str = ""
    tech_data_change: str = ""
    process_change: str = ""
    training_change: str = ""


def _get_client() -> CarverFeedsAPIClient:
    api_key = os.environ.get("REGWATCH_API_KEY")
    if not api_key:
        raise ValueError("REGWATCH_API_KEY not set in environment")
    return CarverFeedsAPIClient(base_url=CARVER_BASE_URL, api_key=api_key)


def _parse_date(date_info) -> str:
    if not date_info:
        return ""
    if isinstance(date_info, dict):
        return date_info.get("date", "") or ""
    return str(date_info)


def _compute_affected_layers(tags: list[str]) -> list[int]:
    tags_lower = {t.lower() for t in tags}
    return sorted(lid for lid, ltags in LAYER_TAG_MAP.items() if tags_lower & ltags)


def fetch_signals() -> list[EnforcementSignal]:
    """
    Fetch enforcement and final_rule signals from FTC + SEC topics.
    Returns signals relevant to a consumer banking AI deployment, sorted newest first.
    """
    client = _get_client()
    signals: list[EnforcementSignal] = []
    seen: set[str] = set()

    for topic_name, topic_id in TOPIC_IDS.items():
        try:
            logger.info(f"Fetching annotations for {topic_name} ({topic_id})...")
            annotations = client.get_annotations(topic_ids=[topic_id])

            for ann_record in annotations:
                annotation = ann_record.get("annotation", {})
                classification = annotation.get("classification", {})
                update_type = classification.get("update_type", "")

                if update_type not in ACCEPTED_UPDATE_TYPES:
                    continue

                entry_id = ann_record.get("feed_entry_id", "")
                if not entry_id or entry_id in seen:
                    continue

                cls_meta = classification.get("metadata", {})
                title = cls_meta.get("title") or "Untitled Action"
                summary = cls_meta.get("summary") or ""
                link = cls_meta.get("feed_url") or ""

                # Deduplicate by URL — multiple Carver annotations can point to
                # the same source document (e.g. OCC monthly enforcement page)
                if link and link in seen:
                    continue

                ann_meta = annotation.get("metadata", {})
                tags = ann_meta.get("tags") or []
                entities = ann_meta.get("entities") or []

                if not _is_relevant(tags):
                    continue

                published_at = _parse_date(annotation.get("reconciled_published_date"))
                has_ai_tag = any("artificial intel" in t.lower() or t.lower() == "ai" for t in tags)
                affected_layers = _compute_affected_layers(tags)

                impact = ann_meta.get("impact_summary") or {}
                actionables = ann_meta.get("actionables") or {}

                signal = EnforcementSignal(
                    entry_id=entry_id,
                    title=title,
                    summary=summary,
                    update_type=update_type,
                    topic_name=topic_name,
                    topic_id=topic_id,
                    published_at=published_at,
                    link=link,
                    tags=tags,
                    entities=entities,
                    has_ai_tag=has_ai_tag,
                    affected_layers=affected_layers,
                    what_changed=impact.get("what_changed") or "",
                    why_it_matters=impact.get("why_it_matters") or "",
                    risk_impact=impact.get("risk_impact") or "",
                    key_requirements=impact.get("key_requirements") or [],
                    policy_change=actionables.get("policy_change") or "",
                    tech_data_change=actionables.get("tech_data_change") or "",
                    process_change=actionables.get("process_change") or "",
                    training_change=actionables.get("training_change") or "",
                )
                signals.append(signal)
                seen.add(entry_id)
                if link:
                    seen.add(link)
                logger.info(
                    f"  [{topic_name}] [{update_type}] {title[:70]} "
                    f"→ layers {affected_layers}"
                )

        except Exception as e:
            logger.error(f"Error fetching {topic_name} signals: {e}")

    signals.sort(key=lambda s: s.published_at or "", reverse=True)
    signals = signals[:12]
    logger.info(f"Total relevant signals: {len(signals)}")
    return signals


def signals_by_layer(signals: list[EnforcementSignal]) -> dict[int, list[EnforcementSignal]]:
    """Group signals by the layers they affect."""
    by_layer: dict[int, list[EnforcementSignal]] = {i: [] for i in range(1, 8)}
    for sig in signals:
        for layer_id in sig.affected_layers:
            by_layer[layer_id].append(sig)
    return by_layer
