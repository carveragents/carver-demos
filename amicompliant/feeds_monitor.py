"""
Carver Feeds SDK integration for AmiCompliant.

Fetches enforcement and final-rule annotations from FTC and SEC topics,
filters for signals published within the last 30 days, scores relevance
against a user-submitted prompt, and extracts financial liability estimates
from the enforcement text.
"""

from __future__ import annotations

import difflib
import json
import logging
import os
import re
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from functools import lru_cache
from pathlib import Path

from openai import OpenAI

from carver_feeds.carver_api import CarverFeedsAPIClient

logger = logging.getLogger(__name__)

CARVER_BASE_URL = "https://app.carveragents.ai"

ACCEPTED_UPDATE_TYPES = {"enforcement", "final_rule"}

_BASE_DIR = Path(__file__).parent
_INDUSTRIES_PATH = _BASE_DIR / "industries.json"
_RANKING_CONFIG_PATH = _BASE_DIR / "ranking_config.json"
_PROMPTS_DIR = _BASE_DIR / "prompts"

# Cache embeddings across requests so repeated evaluations against the same
# 30-day signal set don't re-pay the embedding cost.
_EMBEDDING_CACHE: dict[str, list[float]] = {}

# Generic penalty fallback used when an agency does not have a specific entry.
_DEFAULT_PENALTY_FALLBACK = {
    "low": 50_000,
    "high": 1_000_000,
    "basis": "Typical civil penalty range for regulatory violations",
}

# Per-agency penalty fallbacks when no specific amount is found in the text.
PENALTY_FALLBACKS = {
    "FTC": {"low": 50_000, "high": 500_000, "basis": "FTC civil penalty range for deceptive practice violations"},
    "SEC": {"low": 100_000, "high": 10_000_000, "basis": "SEC civil penalty range for securities violations"},
}


@lru_cache(maxsize=1)
def load_industries() -> dict:
    """Load and cache the industry → topics config."""
    with open(_INDUSTRIES_PATH) as f:
        return json.load(f)


def load_ranking_config() -> dict:
    """Load ranking weights every call (cheap, lets you edit without restart)."""
    try:
        with open(_RANKING_CONFIG_PATH) as f:
            cfg = json.load(f)
    except FileNotFoundError:
        cfg = {}
    return {
        "llm_weight": float(cfg.get("llm_weight", 0.5)),
        "vector_weight": float(cfg.get("vector_weight", 0.5)),
        "second_signal_min_score": float(cfg.get("second_signal_min_score", 0.3)),
        "liability_min_relevance": float(cfg.get("liability_min_relevance", 0.3)),
        "embedding_model": cfg.get("embedding_model", "text-embedding-3-small"),
    }


def public_industries() -> list[dict]:
    """Industry metadata safe to expose to the browser (no topic IDs)."""
    out = []
    for key, cfg in load_industries().items():
        out.append({
            "key": key,
            "label": cfg.get("label", key),
            "icon": cfg.get("icon", ""),
            "description": cfg.get("description", ""),
            "agencies": [t["name"] for t in cfg.get("topics", []) if t.get("topic_id") and t["topic_id"] != "TODO"],
        })
    return out


def _industry_topics(industry_key: str) -> list[dict]:
    industries = load_industries()
    if industry_key not in industries:
        raise ValueError(f"Unknown industry: {industry_key}")
    return [t for t in industries[industry_key].get("topics", []) if t.get("topic_id") and t["topic_id"] != "TODO"]


def _load_prompt(name: str) -> str:
    return (_PROMPTS_DIR / name).read_text()


def _render(template: str, **kwargs) -> str:
    """Simple {var} substitution that ignores unrelated literal braces."""
    out = template
    for k, v in kwargs.items():
        out = out.replace("{" + k + "}", str(v))
    return out


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
    relevance_score: float = 0.0   # blended: llm_weight * llm + vector_weight * vector
    llm_score: float = 0.0
    vector_score: float = 0.0
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

    fb = PENALTY_FALLBACKS.get(topic_name, _DEFAULT_PENALTY_FALLBACK)
    return fb.copy(), False


_FETCH_RETRIES = 2          # additional attempts after the first
_FETCH_BACKOFF_SECONDS = 1.0


def _get_annotations_with_retry(client, topic_id: str, topic_name: str):
    """Retry get_annotations to absorb transient API blips."""
    last_err = None
    for attempt in range(_FETCH_RETRIES + 1):
        try:
            return client.get_annotations(topic_ids=[topic_id])
        except Exception as e:
            last_err = e
            if attempt < _FETCH_RETRIES:
                logger.warning(
                    f"[{topic_name}] fetch attempt {attempt + 1} failed: {e} — retrying"
                )
                time.sleep(_FETCH_BACKOFF_SECONDS * (attempt + 1))
    raise last_err


def fetch_signals(industry_key: str) -> list[EnforcementSignal]:
    """
    Fetch enforcement + final_rule signals from the topics configured for the
    given industry, published in the last 30 days. Sorted newest first.

    If every topic fetch fails, raises RuntimeError so the API surfaces a
    visible error rather than reporting a misleading "0 found" result.
    """
    client = _get_client()
    signals: list[EnforcementSignal] = []
    seen: set[str] = set()

    topics = _industry_topics(industry_key)
    if not topics:
        logger.warning(f"No active topics configured for industry '{industry_key}'")
        return []

    failures: list[tuple[str, str]] = []   # (topic_name, error_str)
    successes = 0

    for topic in topics:
        topic_name = topic["name"]
        topic_id = topic["topic_id"]
        try:
            logger.info(f"Fetching annotations for {topic_name} ({topic_id})...")
            annotations = _get_annotations_with_retry(client, topic_id, topic_name)
            successes += 1

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
            logger.error(f"Error fetching {topic_name} signals after retries: {e}")
            failures.append((topic_name, str(e)))

    # If every configured topic failed, surface an error instead of returning
    # an empty list (which the UI would mis-render as "0 relevant signals").
    if successes == 0 and failures:
        names = ", ".join(n for n, _ in failures)
        first_err = failures[0][1]
        raise RuntimeError(
            f"All regulatory feed fetches failed ({names}). First error: {first_err}"
        )

    if failures:
        logger.warning(
            f"Partial fetch: {successes} succeeded, {len(failures)} failed "
            f"({', '.join(n for n, _ in failures)})"
        )

    signals.sort(key=lambda s: s.published_at or "", reverse=True)
    logger.info(f"Total signals (last 30 days): {len(signals)}")
    return signals


def _embed_texts(texts: list[str], model: str) -> list[list[float]]:
    """Batch embed texts. Returns one vector per input, in order."""
    if not texts:
        return []
    client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])
    r = client.embeddings.create(model=model, input=texts)
    return [d.embedding for d in r.data]


def _cosine(a: list[float], b: list[float]) -> float:
    if not a or not b:
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    na = sum(x * x for x in a) ** 0.5
    nb = sum(y * y for y in b) ** 0.5
    if na == 0 or nb == 0:
        return 0.0
    return dot / (na * nb)


def _embed_signals(signals: list[EnforcementSignal], model: str) -> dict[str, list[float]]:
    """Return entry_id → embedding, using the module cache for already-seen signals."""
    needed = [s for s in signals if s.entry_id not in _EMBEDDING_CACHE]
    if needed:
        texts = [f"{s.title}. {s.summary}"[:2000] for s in needed]
        try:
            vectors = _embed_texts(texts, model)
            for s, v in zip(needed, vectors):
                _EMBEDDING_CACHE[s.entry_id] = v
        except Exception as e:
            logger.warning(f"Signal embedding failed: {e}")
            for s in needed:
                _EMBEDDING_CACHE.setdefault(s.entry_id, [])
    return {s.entry_id: _EMBEDDING_CACHE.get(s.entry_id, []) for s in signals}


def _vector_score_signals(
    signals: list[EnforcementSignal],
    business_context_query: str,
    model: str,
) -> dict[str, float]:
    """Cosine similarity between each signal embedding and the business-context query."""
    if not signals or not business_context_query.strip():
        return {s.entry_id: 0.0 for s in signals}
    try:
        query_vec = _embed_texts([business_context_query[:2000]], model)[0]
    except Exception as e:
        logger.warning(f"Business-context embedding failed: {e}")
        return {s.entry_id: 0.0 for s in signals}
    sig_vecs = _embed_signals(signals, model)
    raw = {sid: _cosine(query_vec, v) for sid, v in sig_vecs.items()}
    # Map cosine [-1, 1] → [0, 1]. With OpenAI embeddings cosines are
    # typically positive, but clamp defensively.
    return {sid: max(0.0, min(1.0, (c + 1.0) / 2.0)) for sid, c in raw.items()}


def score_relevance(
    signals: list[EnforcementSignal],
    prompt_text: str,
    industry_key: str,
    user_context: str = "",
) -> list[EnforcementSignal]:
    """
    Use an LLM to score each signal's relevance to the user's prompt (0.0–1.0).
    Signals are returned sorted by relevance score descending.
    """
    if not signals or not prompt_text.strip():
        return signals

    industries = load_industries()
    industry_cfg = industries.get(industry_key, {})
    industry_label = industry_cfg.get("label", industry_key)
    industry_description = industry_cfg.get("description", "")

    if user_context.strip():
        user_context_block = (
            "Additional context from the user about the AI agent's purpose:\n"
            f"{user_context.strip()}"
        )
    else:
        user_context_block = "(No additional context supplied by the user.)"

    signal_list = "\n".join(
        f"[{i}] {s.topic_name} {s.update_type} — {s.title}: {s.summary[:200]}"
        for i, s in enumerate(signals)
    )

    rendered = _render(
        _load_prompt("relevance_check.txt"),
        industry_label=industry_label,
        industry_description=industry_description,
        user_context_block=user_context_block,
        policy_text=prompt_text[:3000],
        signal_list=signal_list,
    )

    # ---- Pass 1: LLM-based qualitative scoring -----------------------------
    client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])
    try:
        r = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": rendered}],
            temperature=0,
            max_tokens=400,
        )
        raw = r.choices[0].message.content.strip()
        if raw.startswith("```"):
            raw = re.sub(r"^```[a-zA-Z]*\n?|\n?```$", "", raw).strip()
        scores = json.loads(raw)
        for i, s in enumerate(signals):
            if i < len(scores):
                s.llm_score = max(0.0, min(1.0, float(scores[i])))
    except Exception as e:
        logger.warning(f"LLM relevance scoring failed: {e}")

    # ---- Pass 2: Vector-based ranking against business context -------------
    ranking_cfg = load_ranking_config()
    business_context_query = " | ".join(
        p for p in (user_context.strip(), industry_description) if p
    )
    vec_scores = _vector_score_signals(signals, business_context_query, ranking_cfg["embedding_model"])
    for s in signals:
        s.vector_score = vec_scores.get(s.entry_id, 0.0)

    # ---- Blend ------------------------------------------------------------
    w_llm = ranking_cfg["llm_weight"]
    w_vec = ranking_cfg["vector_weight"]
    total = w_llm + w_vec or 1.0
    for s in signals:
        s.relevance_score = (w_llm * s.llm_score + w_vec * s.vector_score) / total

    signals.sort(key=lambda s: s.relevance_score, reverse=True)
    return signals


# ---------------------------------------------------------------------------
# Compliance score (deterministic) + rationale (LLM)
# ---------------------------------------------------------------------------

def compute_compliance_score(signals: list[EnforcementSignal]) -> tuple[int, str]:
    """
    Deterministic exposure score derived from the top-3 relevance scores,
    weighted 0.5 / 0.3 / 0.2. Returns (score 0-100, bucket label).
    """
    if not signals:
        return 0, "Low"
    weights = [0.5, 0.3, 0.2]
    top = sorted((s.relevance_score for s in signals), reverse=True)[:3]
    while len(top) < 3:
        top.append(0.0)
    score = round(sum(w * v for w, v in zip(weights, top)) * 100)
    score = max(0, min(100, score))
    if score >= 75:
        bucket = "High"
    elif score >= 50:
        bucket = "Elevated"
    elif score >= 25:
        bucket = "Moderate"
    else:
        bucket = "Low"
    return score, bucket


def generate_compliance_rationale(
    prompt_text: str,
    signals: list[EnforcementSignal],
    score: int,
    bucket: str,
    industry_key: str,
) -> str:
    """One-paragraph LLM rationale explaining the compliance score."""
    if not signals:
        return "No regulatory signals were found that intersect with this prompt."

    industries = load_industries()
    industry_label = industries.get(industry_key, {}).get("label", industry_key)

    top = signals[:3]
    top_signals_block = "\n".join(
        f"- [{s.topic_name}] {s.title}  (relevance {s.relevance_score:.2f})\n"
        f"  {s.summary[:300]}"
        for s in top
    )

    rendered = _render(
        _load_prompt("compliance_rationale.txt"),
        industry_label=industry_label,
        score=score,
        bucket=bucket,
        top_signals_block=top_signals_block,
        policy_text=prompt_text[:3000],
    )

    client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])
    try:
        r = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": rendered}],
            temperature=0.2,
            max_tokens=300,
        )
        return r.choices[0].message.content.strip()
    except Exception as e:
        logger.warning(f"Compliance rationale generation failed: {e}")
        return ""


def generate_prompt_update(prompt_text: str, signals: list[EnforcementSignal]) -> list[dict]:
    """
    Ask the LLM to produce a revised policy that addresses one or more
    enforcement signals, with source attribution per change. Returns a
    line-level diff.

    Each diff entry is {type, content} where type is one of:
      "context" | "added" | "removed" | "header"
    """
    if not signals:
        return []

    signals_block = "\n\n".join(
        f"[S{i+1}] Agency: {s.topic_name}\n"
        f"      Type: {s.update_type}\n"
        f"      Title: {s.title}\n"
        f"      Summary: {s.summary}\n"
        f"      Violation categories: {', '.join(s.tags[:8]) if s.tags else 'N/A'}"
        for i, s in enumerate(signals)
    )

    rendered = _render(
        _load_prompt("suggest_update.txt"),
        n_signals=len(signals),
        policy_text=prompt_text,
        signals_block=signals_block,
    )

    client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])
    try:
        r = client.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "user", "content": rendered}],
            temperature=0.1,
            max_tokens=4000,
        )
        revised = r.choices[0].message.content.strip()
    except Exception as e:
        logger.error(f"Policy update generation failed: {e}")
        return []

    return _compute_diff(prompt_text, revised)


_CONTEXT_LINES = 3  # unchanged lines shown either side of a change run


def _compute_diff(original: str, revised: str) -> list[dict]:
    """
    Produce an inline, line-by-line diff using difflib.ndiff so that
    removed and added lines are interleaved at the point of change
    (rather than batched as remove-then-add blocks). Long runs of
    untouched lines are collapsed with context on either side.
    """
    orig_lines = original.splitlines()
    rev_lines  = revised.splitlines()

    # ndiff yields lines prefixed with "  ", "- ", "+ ", or "? "
    raw: list[tuple[str, str]] = []
    for line in difflib.ndiff(orig_lines, rev_lines):
        if not line:
            continue
        tag = line[:2]
        content = line[2:]
        if tag == "  ":
            raw.append(("context", content))
        elif tag == "- ":
            raw.append(("removed", content))
        elif tag == "+ ":
            raw.append(("added", content))
        # "? " hint lines are visual diff markers — drop them.

    # Collapse long runs of untouched lines, keeping CONTEXT_LINES on each side.
    result: list[dict] = []
    n = len(raw)
    i = 0
    while i < n:
        if raw[i][0] != "context":
            result.append({"type": raw[i][0], "content": raw[i][1]})
            i += 1
            continue
        # Gather a run of context
        j = i
        while j < n and raw[j][0] == "context":
            j += 1
        run = raw[i:j]
        is_first = (len(result) == 0)
        is_last = (j == n)
        if len(run) <= _CONTEXT_LINES * 2:
            for _, c in run:
                result.append({"type": "context", "content": c})
        else:
            head = 0 if is_first else _CONTEXT_LINES
            tail = 0 if is_last else _CONTEXT_LINES
            for _, c in run[:head]:
                result.append({"type": "context", "content": c})
            skipped = len(run) - head - tail
            if skipped > 0:
                result.append({"type": "header", "content": f"  … {skipped} unchanged lines …"})
            for _, c in run[-tail:] if tail else []:
                result.append({"type": "context", "content": c})
        i = j

    return result


def compute_liability(
    cited_signals: list[EnforcementSignal],
    min_relevance: float,
) -> dict | None:
    """
    Compute a financial exposure range anchored to the signals that drove the
    diff. Returns {low, high, basis, sources: [...]} or None when the top
    cited signal does not clear the relevance threshold.

    Logic:
      - If the top cited signal is below `min_relevance`, return None
        (better to hide the card than anchor to an irrelevant action).
      - Prefer concrete dollar amounts parsed from the cited signals.
        With two cited signals, low = min(lows), high = max(highs).
      - If no cited signal has concrete amounts, fall back to the per-agency
        PENALTY_FALLBACKS for the top cited signal's agency, clearly labeled.
    """
    if not cited_signals:
        return None
    if cited_signals[0].relevance_score < min_relevance:
        return None

    with_concrete = [s for s in cited_signals if s.has_concrete_liability]

    if with_concrete:
        lows = [s.liability.get("low", 0) for s in with_concrete]
        highs = [s.liability.get("high", 0) for s in with_concrete]
        if len(with_concrete) == 1:
            basis = (
                f"Based on penalty amounts cited in the top-ranked "
                f"{with_concrete[0].topic_name} action used for this recommendation."
            )
        else:
            basis = (
                "Based on penalty amounts cited across the top-ranked "
                "enforcement actions used for this recommendation."
            )
        return {
            "low": min(lows),
            "high": max(highs),
            "basis": basis,
            "sources": [
                {
                    "topic_name": s.topic_name,
                    "title": s.title,
                    "link": s.link,
                    "update_type": s.update_type,
                }
                for s in with_concrete
            ],
        }

    # Fallback: agency-range for the top cited signal's agency, labelled as such.
    top = cited_signals[0]
    fb = PENALTY_FALLBACKS.get(top.topic_name, _DEFAULT_PENALTY_FALLBACK).copy()
    fb["basis"] = (
        f"Category fallback — no specific dollar amount was published in the "
        f"top cited action; using the typical {top.topic_name} civil penalty range."
    )
    fb["sources"] = [
        {
            "topic_name": top.topic_name,
            "title": top.title,
            "link": top.link,
            "update_type": top.update_type,
        }
    ]
    return fb


def compute_sector_ceiling(signals: list[EnforcementSignal]) -> dict | None:
    """
    Return contextual info on the LARGEST concrete-dollar action in the
    current evaluation set, regardless of how relevant it is to this policy.
    Clearly labelled in the UI as sector context, not exposure.
    """
    with_concrete = [s for s in signals if s.has_concrete_liability]
    if not with_concrete:
        return None
    top = max(with_concrete, key=lambda s: s.liability.get("high", 0))
    return {
        "amount_high": top.liability.get("high", 0),
        "amount_low": top.liability.get("low", 0),
        "topic_name": top.topic_name,
        "title": top.title,
        "link": top.link,
        "update_type": top.update_type,
        "published_at": top.published_at[:10] if top.published_at else "",
    }


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
        "llm_score": round(s.llm_score, 2),
        "vector_score": round(s.vector_score, 2),
        "liability": s.liability,
    }
