"""
Carver Feeds SDK integration for FinCoach demo.

Fetches enforcement-type annotations from the FTC and SEC topics,
filters for signals relevant to AI-assisted sales platforms, and returns
structured signals for injection into the agent's system prompt.
"""

import logging
import os
from dataclasses import dataclass, field

from carver_feeds.carver_api import CarverFeedsAPIClient

logger = logging.getLogger(__name__)

# Topic IDs to subscribe to
TOPIC_IDS = {
    "FTC": "bfc3cb59-b0ea-4726-867f-42155f156529",
    "SEC": "0364883a-c054-41d8-9168-1f9a983ceca9",
}

CARVER_BASE_URL = "https://app.carveragents.ai"

# Tags that make an enforcement signal relevant to an AI-powered sales/education platform.
# Intentionally specific — generic "advertising" or "consumer protection" alone don't qualify.
RELEVANT_TAGS = {
    "earnings claims", "deceptive earnings claims", "false earnings claims",
    "testimonials", "artificial intelligence",
    "refund policy", "refund guarantee",
    "deceptive advertising", "income claims",
    "multi-level marketing", "mlm",
    "deceptive practices",
}


@dataclass
class EnforcementSignal:
    entry_id: str
    title: str
    summary: str
    update_type: str
    topic_name: str
    topic_id: str
    published_at: str      # ISO date string e.g. "2026-04-13"
    link: str
    tags: list[str] = field(default_factory=list)
    entities: list[str] = field(default_factory=list)
    has_ai_tag: bool = False


def _get_client() -> CarverFeedsAPIClient:
    api_key = os.environ.get("REGWATCH_API_KEY")
    if not api_key:
        raise ValueError("REGWATCH_API_KEY not set in environment")
    return CarverFeedsAPIClient(base_url=CARVER_BASE_URL, api_key=api_key)


def _parse_date(date_info) -> str:
    """Extract ISO date string from reconciled_published_date field."""
    if not date_info:
        return ""
    if isinstance(date_info, dict):
        return date_info.get("date", "") or ""
    return str(date_info)


def _is_relevant(tags: list[str]) -> bool:
    """Return True if the signal is relevant to an AI-powered sales platform."""
    tags_lower = {t.lower() for t in tags}
    return bool(tags_lower & RELEVANT_TAGS)


def fetch_enforcements() -> list[EnforcementSignal]:
    """
    Fetch enforcement-type signals from FTC + SEC topics via the Carver SDK.

    Returns a list of relevant EnforcementSignal objects, sorted newest first,
    capped at 10 total to keep the demo focused.
    """
    client = _get_client()
    signals: list[EnforcementSignal] = []
    seen_entry_ids: set[str] = set()

    for topic_name, topic_id in TOPIC_IDS.items():
        try:
            logger.info(f"Fetching annotations for {topic_name} topic ({topic_id})...")
            annotations = client.get_annotations(topic_ids=[topic_id])

            for ann_record in annotations:
                annotation = ann_record.get("annotation", {})
                classification = annotation.get("classification", {})
                update_type = classification.get("update_type", "")

                if update_type != "enforcement":
                    continue

                entry_id = ann_record.get("feed_entry_id", "")
                if not entry_id or entry_id in seen_entry_ids:
                    continue

                # Extract fields from classification.metadata
                cls_meta = classification.get("metadata", {})
                title = cls_meta.get("title") or "Untitled Enforcement Action"
                summary = cls_meta.get("summary") or ""
                link = cls_meta.get("feed_url") or ""

                # Extract tags and entities from annotation.metadata
                ann_meta = annotation.get("metadata", {})
                tags = ann_meta.get("tags") or []
                entities = ann_meta.get("entities") or []

                # Only keep signals relevant to our demo scenario
                if not _is_relevant(tags):
                    continue

                published_at = _parse_date(annotation.get("reconciled_published_date"))
                has_ai_tag = any("artificial intel" in t.lower() or t.lower() == "ai" for t in tags)

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
                )
                signals.append(signal)
                seen_entry_ids.add(entry_id)
                logger.info(f"  [{topic_name}] {title[:80]}")

        except Exception as e:
            logger.error(f"Error fetching {topic_name} enforcements: {e}")

    # Sort: most recent first, cap at 8 for the demo
    signals.sort(key=lambda s: s.published_at or "", reverse=True)
    signals = signals[:8]
    logger.info(f"Total relevant enforcement signals: {len(signals)}")
    return signals


def format_enforcements_for_prompt(signals: list[EnforcementSignal]) -> str:
    """
    Format enforcement signals as an override block injected into the agent's
    system prompt. Explicitly supersedes specific parts of the base instructions
    that conflict with active regulatory enforcement actions.
    """
    if not signals:
        return ""

    lines = [
        "--- REGULATORY OVERRIDE (Carver Horizon · Live Enforcement Feed) ---",
        "",
        "The following enforcement actions have been automatically detected as",
        "applicable to this platform. They OVERRIDE the corresponding parts of",
        "your base instructions where there is a conflict:",
        "",
    ]

    for i, sig in enumerate(signals, 1):
        lines.append(f"[{i}] {sig.topic_name} Enforcement — {sig.title}")
        if sig.published_at:
            lines.append(f"    Issued: {sig.published_at}")
        if sig.summary:
            lines.append(f"    Summary: {sig.summary}")
        if sig.has_ai_tag:
            lines.append("    * This action explicitly names AI-generated content as a violation factor.")
        if sig.tags:
            lines.append(f"    Violations cited: {', '.join(sig.tags[:6])}")
        if sig.link:
            lines.append(f"    Source: {sig.link}")
        lines.append("")

    lines += [
        "OVERRIDES TO YOUR BASE INSTRUCTIONS:",
        "",
        "Base instruction: 'share member success stories concretely'",
        "→ OVERRIDDEN: Do NOT give specific return figures or income amounts.",
        "  Reason: FTC enforcement actions cited above penalise specific earnings",
        "  claims that lack substantiation (e.g. '20–50% returns', '$4,200/month').",
        "",
        "Base instruction: 'be warm, confident, and specific'",
        "→ OVERRIDDEN on income claims: Redirect income questions to methodology.",
        "  You may still be specific about course content, signal mechanics, etc.",
        "",
        "Base instruction: 'share member success stories'",
        "→ OVERRIDDEN: Any testimonials must include: 'individual results vary",
        "  significantly; these members may have received benefits for sharing'.",
        "",
        "Base instruction: 'subscription comes with a satisfaction guarantee'",
        "→ OVERRIDDEN: Do not describe the guarantee without noting that terms",
        "  and restrictions apply. Direct users to full terms for details.",
        "",
        "NEW REQUIREMENT (not in base instructions):",
        "→ Disclose at the start of every conversation that you are an AI assistant.",
        "  Reason: FTC enforcement explicitly called out undisclosed AI in the",
        "  Publishing.com case (April 2026).",
        "",
        "--- END REGULATORY OVERRIDE ---",
    ]

    return "\n".join(lines)
