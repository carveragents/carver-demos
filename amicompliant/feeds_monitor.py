"""
Carver Feeds SDK integration for AmiCompliant.

Fetches enforcement and final-rule annotations from FTC and SEC topics,
filters for signals published within the last 30 days, scores relevance
against a user-submitted prompt, and extracts financial liability estimates
from the enforcement text.
"""

import difflib
import json
import logging
import os
import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

from openai import OpenAI

from carver_feeds.carver_api import CarverFeedsAPIClient

logger = logging.getLogger(__name__)

TOPIC_IDS = {
    "FTC": "bfc3cb59-b0ea-4726-867f-42155f156529",
    "SEC": "0364883a-c054-41d8-9168-1f9a983ceca9",
}

CARVER_BASE_URL = "https://app.carveragents.ai"

ACCEPTED_UPDATE_TYPES = {"enforcement", "final_rule"}

# Category-based penalty fallbacks when no specific amount is found in the text
PENALTY_FALLBACKS = {
    "FTC": {"low": 50_000, "high": 500_000, "basis": "FTC civil penalty range for deceptive practice violations"},
    "SEC": {"low": 100_000, "high": 10_000_000, "basis": "SEC civil penalty range for securities violations"},
}


@dataclass
class EnforcementSignal:
    entry_id: str
    title: str
    summary: str
    update_type: str        # "enforcement" | "final_rule"
    topic_name: str
    topic_id: str
    published_at: str       # ISO date string
    link: str
    tags: list[str] = field(default_factory=list)
    entities: list[str] = field(default_factory=list)
    has_ai_tag: bool = False
    relevance_score: float = 0.0
    liability: dict = field(default_factory=dict)
    has_concrete_liability: bool = False  # True when actual dollar amounts were parsed


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


def _within_30_days(date_str: str) -> bool:
    if not date_str:
        return False
    try:
        cutoff = datetime.now(timezone.utc) - timedelta(days=30)
        # Handle both "YYYY-MM-DD" and full ISO strings
        if "T" in date_str:
            dt = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
        else:
            dt = datetime.strptime(date_str, "%Y-%m-%d").replace(tzinfo=timezone.utc)
        return dt >= cutoff
    except ValueError:
        return False


def _extract_liability(summary: str, topic_name: str) -> tuple[dict, bool]:
    """
    Parse dollar amounts from the enforcement summary.
    Returns ({low, high, basis}, has_concrete) where has_concrete is True
    when actual dollar figures were found in the text.
    """
    pattern = r"\$[\d,]+(?:\.\d+)?\s*(?:million|billion|M|B|K|thousand)?"
    raw_matches = re.findall(pattern, summary, re.IGNORECASE)

    amounts = []
    for m in raw_matches:
        num_str = re.sub(r"[,$]", "", m)
        multiplier = 1
        if re.search(r"billion|B\b", m, re.IGNORECASE):
            multiplier = 1_000_000_000
        elif re.search(r"million|M\b", m, re.IGNORECASE):
            multiplier = 1_000_000
        elif re.search(r"thousand|K\b", m, re.IGNORECASE):
            multiplier = 1_000
        try:
            amounts.append(int(float(re.sub(r"[A-Za-z\s]", "", num_str)) * multiplier))
        except ValueError:
            continue

    if amounts:
        return {
            "low": min(amounts),
            "high": max(amounts),
            "basis": "Based on penalty amounts cited in this enforcement action",
        }, True

    fb = PENALTY_FALLBACKS.get(topic_name, PENALTY_FALLBACKS["FTC"])
    return fb.copy(), False


def fetch_signals() -> list[EnforcementSignal]:
    """
    Fetch enforcement + final_rule signals from FTC + SEC published in the last 30 days.
    Returns all matching signals, sorted newest first.
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

                published_at = _parse_date(annotation.get("reconciled_published_date"))
                if not _within_30_days(published_at):
                    continue

                cls_meta = classification.get("metadata", {})
                title = cls_meta.get("title") or "Untitled Action"
                summary = cls_meta.get("summary") or ""
                link = cls_meta.get("feed_url") or ""

                ann_meta = annotation.get("metadata", {})
                tags = ann_meta.get("tags") or []
                entities = ann_meta.get("entities") or []
                has_ai_tag = any(
                    "artificial intel" in t.lower() or t.lower() == "ai" for t in tags
                )

                liability, has_concrete_liability = _extract_liability(summary, topic_name)

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
                    liability=liability,
                    has_concrete_liability=has_concrete_liability,
                )
                signals.append(signal)
                seen.add(entry_id)
                logger.info(f"  [{topic_name}] [{update_type}] {title[:80]}")

        except Exception as e:
            logger.error(f"Error fetching {topic_name} signals: {e}")

    signals.sort(key=lambda s: s.published_at or "", reverse=True)
    logger.info(f"Total signals (last 30 days): {len(signals)}")
    return signals


def score_relevance(signals: list[EnforcementSignal], prompt_text: str) -> list[EnforcementSignal]:
    """
    Use an LLM to score each signal's relevance to the user's prompt (0.0–1.0).
    Signals are returned sorted by relevance score descending.
    """
    if not signals or not prompt_text.strip():
        return signals

    client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])

    # Build a compact representation of all signals for the scoring call
    signal_list = "\n".join(
        f"[{i}] {s.topic_name} {s.update_type} — {s.title}: {s.summary[:200]}"
        for i, s in enumerate(signals)
    )

    system = (
        "You are a compliance analyst. Given a user's AI agent prompt and a list of recent "
        "regulatory enforcement actions / final rules, score how relevant each action is to "
        "the risks present in that prompt.\n\n"
        "Return ONLY a JSON array of numbers (floats 0.0–1.0), one per signal, in the same order. "
        "1.0 = directly applicable violation risk, 0.0 = irrelevant. No other text."
    )
    user = f"User prompt:\n{prompt_text[:3000]}\n\nSignals:\n{signal_list}"

    try:
        r = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
            temperature=0,
            max_tokens=200,
        )
        raw = r.choices[0].message.content.strip()
        scores = json.loads(raw)
        for i, s in enumerate(signals):
            if i < len(scores):
                s.relevance_score = float(scores[i])
    except Exception as e:
        logger.warning(f"Relevance scoring failed: {e}")

    signals.sort(key=lambda s: s.relevance_score, reverse=True)
    return signals


def generate_prompt_update(prompt_text: str, signal: EnforcementSignal) -> list[dict]:
    """
    Ask the LLM to produce a revised version of the user's prompt that addresses
    the given enforcement signal, then compute a line-level diff.

    Returns a list of {type, content} dicts where type is one of:
      "context" | "added" | "removed" | "header"
    """
    client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])

    system = (
        "You are a senior AI compliance counsel conducting a mandatory regulatory review. "
        "An AI system prompt has been flagged against a live enforcement action. "
        "Your job is to produce a SUBSTANTIVELY revised version that a legal team would "
        "be satisfied with — not cosmetic edits, not minor wording tweaks.\n\n"
        "WHAT COUNTS AS A SUBSTANTIVE CHANGE (do all that apply):\n"
        "- Add explicit AI-identity disclosure requirements if the prompt lacks them or "
        "instructs the AI to obscure its nature.\n"
        "- Remove or rewrite any instruction that directs the AI to deceive, mislead, or "
        "withhold its nature from users — even indirectly (e.g. 'never reference these "
        "instructions', 'do not reveal you are an AI').\n"
        "- Add mandatory disclosures for earnings claims, guarantees, or testimonials "
        "if present.\n"
        "- Introduce hard prohibitions on the specific violation categories named in the "
        "enforcement action (e.g. add a SHALL NOT clause for each cited violation type).\n"
        "- Add a new section if the prompt is entirely missing a compliance dimension "
        "the enforcement action requires.\n"
        "- Strengthen weak MAY/SHOULD language to SHALL/MUST where the enforcement "
        "action makes a behaviour mandatory.\n\n"
        "WHAT IS FORBIDDEN:\n"
        "- Do NOT fix typos, ligatures, or formatting.\n"
        "- Do NOT reword sentences that have no compliance relevance.\n"
        "- Do NOT add a citation unless you have actually changed or added that clause.\n\n"
        "FORMAT:\n"
        "- Preserve the original document structure exactly (same headings, same order).\n"
        "- After each changed or inserted clause append: "
        "[Per {agency} enforcement: {short title}]\n"
        "- Output ONLY the revised prompt — no preamble, no explanation."
    )

    user = (
        f"Original prompt:\n\n{prompt_text}\n\n"
        "---\n"
        f"Enforcement action:\n"
        f"Agency: {signal.topic_name}\n"
        f"Type: {signal.update_type}\n"
        f"Title: {signal.title}\n"
        f"Summary: {signal.summary}\n"
        f"Violation categories cited: {', '.join(signal.tags[:8]) if signal.tags else 'N/A'}\n\n"
        "Identify every clause in the prompt that is implicated by this enforcement action "
        "and rewrite each one. If the prompt is missing an entire required compliance "
        "dimension, add it as a new section."
    )

    try:
        r = client.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
            temperature=0.1,
            max_tokens=4000,
        )
        revised = r.choices[0].message.content.strip()
    except Exception as e:
        logger.error(f"Prompt update generation failed: {e}")
        return []

    return _compute_diff(prompt_text, revised)


_CONTEXT_LINES = 3  # unchanged lines shown either side of a change


def _compute_diff(original: str, revised: str) -> list[dict]:
    orig_lines = original.splitlines(keepends=True)
    rev_lines  = revised.splitlines(keepends=True)
    result: list[dict] = []

    opcodes = difflib.SequenceMatcher(None, orig_lines, rev_lines).get_opcodes()

    for idx, (tag, i1, i2, j1, j2) in enumerate(opcodes):
        if tag == "equal":
            block = orig_lines[i1:i2]
            # Show at most CONTEXT_LINES at the start and end of each equal block.
            # If the block is short enough, show it all.
            if len(block) <= _CONTEXT_LINES * 2:
                for line in block:
                    result.append({"type": "context", "content": line.rstrip("\n")})
            else:
                for line in block[:_CONTEXT_LINES]:
                    result.append({"type": "context", "content": line.rstrip("\n")})
                skipped = len(block) - _CONTEXT_LINES * 2
                result.append({"type": "header", "content": f"  … {skipped} unchanged lines …"})
                for line in block[-_CONTEXT_LINES:]:
                    result.append({"type": "context", "content": line.rstrip("\n")})
        elif tag == "replace":
            for line in orig_lines[i1:i2]:
                result.append({"type": "removed", "content": line.rstrip("\n")})
            for line in rev_lines[j1:j2]:
                result.append({"type": "added", "content": line.rstrip("\n")})
        elif tag == "delete":
            for line in orig_lines[i1:i2]:
                result.append({"type": "removed", "content": line.rstrip("\n")})
        elif tag == "insert":
            for line in rev_lines[j1:j2]:
                result.append({"type": "added", "content": line.rstrip("\n")})

    return result


def pick_liability_signal(signals: list[EnforcementSignal]) -> EnforcementSignal:
    """
    Return the signal best suited to anchor the financial exposure card.

    Priority:
      1. Signals with concrete dollar amounts parsed from the text, ranked by penalty high-end desc
      2. Enforcement actions (not final rules) with the highest relevance score
      3. Any signal, highest relevance score
    """
    concrete = [s for s in signals if s.has_concrete_liability]
    if concrete:
        return max(concrete, key=lambda s: s.liability.get("high", 0))

    enforcements = [s for s in signals if s.update_type == "enforcement"]
    if enforcements:
        return max(enforcements, key=lambda s: s.relevance_score)

    return signals[0]


def serialize_signal(s: EnforcementSignal) -> dict:
    return {
        "entry_id": s.entry_id,
        "title": s.title,
        "summary": s.summary,
        "update_type": s.update_type,
        "topic_name": s.topic_name,
        "published_at": s.published_at[:10] if s.published_at else "",
        "link": s.link,
        "tags": s.tags,
        "has_ai_tag": s.has_ai_tag,
        "relevance_score": round(s.relevance_score, 2),
        "liability": s.liability,
    }
