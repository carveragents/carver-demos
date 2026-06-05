"""
Multi-layer policy management for Meridian Pay demo.

Manages 7 independent compliance policy layers, each corresponding to a
layer in the agent deployment stack. Enforcement signals map to specific
layers and generate targeted v2 updates with per-layer diffs.
"""

import difflib
import logging
import os
from dataclasses import dataclass, field
from pathlib import Path

from openai import OpenAI

logger = logging.getLogger(__name__)

POLICIES_DIR = Path(__file__).parent / "policies" / "layers"

LAYER_NAMES = {
    1: "Input Guardrails",
    2: "Topic / Intent Router",
    3: "Retrieval Layer",
    4: "System Prompt",
    5: "Tool Gating",
    6: "Output Validator",
    7: "Post-Processor",
}

LAYER_FILES = {
    1: "layer1.md",
    2: "layer2.md",
    3: "layer3.md",
    4: "layer4.md",
    5: "layer5.md",
    6: "layer6.md",
    7: "layer7.md",
}

_CONTEXT_LINES = 3


@dataclass
class DiffLine:
    type: str   # "context" | "added" | "removed" | "header"
    content: str


@dataclass
class LayerPolicy:
    layer_id: int
    name: str
    v1: str = ""
    v2: str = ""
    diff: list[DiffLine] = field(default_factory=list)
    is_affected: bool = False
    active_version: str = "v1"


# Module-level state: layer_id → LayerPolicy
_layers: dict[int, LayerPolicy] = {}


def load_all_v1() -> None:
    """Load v1 content for all 7 layers from disk."""
    global _layers
    _layers = {}
    for layer_id, filename in LAYER_FILES.items():
        path = POLICIES_DIR / filename
        content = path.read_text()
        _layers[layer_id] = LayerPolicy(
            layer_id=layer_id,
            name=LAYER_NAMES[layer_id],
            v1=content,
        )
    logger.info(f"Loaded {len(_layers)} layer policies")


def get_layer_policy(layer_id: int) -> str:
    layer = _layers.get(layer_id)
    if not layer:
        return ""
    return layer.v2 if (layer.active_version == "v2" and layer.v2) else layer.v1


def get_active_policy() -> str:
    """Return Layer 4 (System Prompt) — the text the agent runs against."""
    if not _layers:
        load_all_v1()
    return get_layer_policy(4)


def get_state() -> dict:
    return {
        "active_version": "v2" if any(
            l.active_version == "v2" for l in _layers.values()
        ) else "v1",
        "layers": [
            {
                "layer_id": l.layer_id,
                "name": l.name,
                "active_version": l.active_version,
                "is_affected": l.is_affected,
                "v1": l.v1,
                "v2": l.v2,
                "diff": [{"type": d.type, "content": d.content} for d in l.diff],
            }
            for l in _layers.values()
        ],
        # Legacy scalar fields used by agent.py / system prompt viewer
        "v1": get_layer_policy(4),
        "v2": (_layers[4].v2 if 4 in _layers else ""),
        "diff": [],
    }


def mark_affected_layers(layer_ids: list[int]) -> None:
    for layer_id, layer in _layers.items():
        layer.is_affected = layer_id in layer_ids


def activate_all_v2() -> None:
    for layer in _layers.values():
        if layer.v2:
            layer.active_version = "v2"
    logger.info("v2 activated for all updated layers")


def reset_all_to_v1() -> None:
    for layer in _layers.values():
        layer.active_version = "v1"
        layer.v2 = ""
        layer.diff = []
        layer.is_affected = False
    logger.info("All layers reset to v1")


def generate_layer_updates(signals_by_layer: dict[int, list]) -> dict:
    """
    For each layer that has at least one enforcement signal, generate a v2
    update using Claude and compute the diff. Returns updated state dict.
    """
    if not _layers:
        load_all_v1()

    client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])
    affected = [lid for lid, sigs in signals_by_layer.items() if sigs]
    logger.info(f"Generating v2 for layers: {affected}")

    for layer_id in affected:
        layer = _layers.get(layer_id)
        if not layer:
            continue

        signals = signals_by_layer[layer_id]
        context = _format_signals(signals, layer_id, layer.name)

        # Build citation hint from actual signals
        signal_citations = "; ".join(
            f"{s.topic_name} {s.update_type.replace('_',' ').title()} — {s.title[:60]} ({s.published_at[:7] if s.published_at else 'n/d'})"
            for s in signals[:3]
        )

        system = (
            "You are a senior compliance officer at a consumer banking company. "
            f"You are rewriting Layer {layer_id} ({layer.name}) of a 7-layer AI agent "
            "deployment policy to comply with the regulatory enforcement actions and "
            "guidance listed in the user message.\n\n"
            "STEP 1 — Extract requirements: For each signal, identify what specific "
            "agent BEHAVIOR it prohibits or requires.\n\n"
            "STEP 2 — Audit each v1 section: For every section or bullet, ask:\n"
            "  (a) What behavior does this instruction prescribe?\n"
            "  (b) Does any signal require the OPPOSITE or incompatible behavior?\n"
            "  If YES → DELETE the old instruction and REPLACE it with a compliant "
            "  version. Do NOT keep both — a document with conflicting instructions "
            "  is worse than either alone.\n"
            "  If NO → keep the section verbatim.\n\n"
            "  Conflict patterns to watch for:\n"
            "  - 'State X as fact / no need to verify' + signal requiring substantiation"
            " → REPLACE with 'direct customer to verify X in their plan documents'\n"
            "  - 'Treat as routine / avoid alarm words' + signal requiring incident "
            "response for security events → REPLACE with escalation requirement\n"
            "  - 'Give estimates when exact data unavailable' + signal prohibiting "
            "misrepresentation of material facts → REPLACE with 'decline to quote "
            "specific figures without verified account data'\n\n"
            "STEP 3 — Fill gaps: Where signals require conduct not addressed in v1, "
            "add a new section in the appropriate position.\n\n"
            "Additional rules:\n"
            "- The signals are the ONLY basis for changes.\n"
            "- Do not import rules that belong to other deployment layers.\n"
            f"- After every rewritten or added clause, cite the signal, e.g. "
            f"[Updated per {signal_citations}].\n"
            "- Update the version field to 2026.06.\n"
            "- Output ONLY the final v2 policy document — no preamble, no reasoning."
        )

        user = (
            f"Current Layer {layer_id} — {layer.name} policy (v1):\n\n{layer.v1}\n\n"
            f"Regulatory signals requiring updates to this layer:\n\n{context}"
        )

        try:
            resp = client.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
                temperature=0,
                max_tokens=2000,
            )
            v2_text = resp.choices[0].message.content.strip()
            layer.v2 = v2_text
            layer.diff = _compute_diff(layer.v1, v2_text)
            layer.is_affected = True
            logger.info(f"  Layer {layer_id}: {len(v2_text)} chars, {len(layer.diff)} diff lines")
        except Exception as e:
            logger.error(f"  Layer {layer_id} generation failed: {e}")

    return get_state()


def _format_signals(signals: list, layer_id: int, layer_name: str) -> str:
    lines = [f"Signals requiring updates to Layer {layer_id} ({layer_name}):\n"]
    for i, sig in enumerate(signals, 1):
        type_label = sig.update_type.replace("_", " ").title()
        lines.append(f"[{i}] {sig.topic_name} {type_label} — {sig.title}")
        if sig.published_at:
            lines.append(f"    Issued: {sig.published_at}")
        if sig.summary:
            lines.append(f"    Summary: {sig.summary}")
        if sig.what_changed:
            lines.append(f"    What changed: {sig.what_changed}")
        if sig.why_it_matters:
            lines.append(f"    Why it matters: {sig.why_it_matters}")
        if sig.risk_impact:
            lines.append(f"    Risk impact: {sig.risk_impact}")
        if sig.key_requirements:
            lines.append("    Key requirements:")
            for req in sig.key_requirements[:6]:
                lines.append(f"      - {req}")
        if sig.policy_change:
            lines.append(f"    Policy change required: {sig.policy_change}")
        if sig.tech_data_change:
            lines.append(f"    Technology/data change required: {sig.tech_data_change}")
        if sig.process_change:
            lines.append(f"    Process change required: {sig.process_change}")
        if sig.training_change:
            lines.append(f"    Training change required: {sig.training_change}")
        if sig.tags:
            lines.append(f"    Violation categories: {', '.join(sig.tags[:6])}")
        lines.append("")
    return "\n".join(lines)


def _compute_diff(v1: str, v2: str) -> list[DiffLine]:
    v1_lines = v1.splitlines(keepends=True)
    v2_lines = v2.splitlines(keepends=True)
    result: list[DiffLine] = []
    opcodes = difflib.SequenceMatcher(None, v1_lines, v2_lines).get_opcodes()

    for tag, i1, i2, j1, j2 in opcodes:
        if tag == "equal":
            block = v1_lines[i1:i2]
            if len(block) <= _CONTEXT_LINES * 2:
                for line in block:
                    result.append(DiffLine("context", line.rstrip("\n")))
            else:
                for line in block[:_CONTEXT_LINES]:
                    result.append(DiffLine("context", line.rstrip("\n")))
                result.append(DiffLine("header", f"  … {len(block) - _CONTEXT_LINES*2} unchanged lines …"))
                for line in block[-_CONTEXT_LINES:]:
                    result.append(DiffLine("context", line.rstrip("\n")))
        elif tag == "replace":
            for line in v1_lines[i1:i2]:
                result.append(DiffLine("removed", line.rstrip("\n")))
            for line in v2_lines[j1:j2]:
                result.append(DiffLine("added", line.rstrip("\n")))
        elif tag == "delete":
            for line in v1_lines[i1:i2]:
                result.append(DiffLine("removed", line.rstrip("\n")))
        elif tag == "insert":
            for line in v2_lines[j1:j2]:
                result.append(DiffLine("added", line.rstrip("\n")))

    return result
