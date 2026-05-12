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
    update using gpt-4o and compute the diff. Returns updated state dict.
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

        system = (
            "You are a senior compliance officer at a consumer banking company. "
            f"You are updating Layer {layer_id} ({layer.name}) of a 7-layer AI agent "
            "deployment policy in response to recent regulatory enforcement actions "
            "and final rules. Requirements:\n"
            "1. Preserve the overall document structure and heading format.\n"
            "2. REMOVE or REPLACE any clauses in v1 that the enforcement actions show "
            "are non-compliant. Do not just add to a bad clause — rewrite or delete it.\n"
            "3. Strengthen or modify other existing rules where enforcement actions "
            "reveal compliance gaps.\n"
            "4. Add new rules for conduct not addressed in v1 but required by the "
            "enforcement actions.\n"
            "5. Specific fixes required for this layer based on the enforcement signals:\n"
            "   - If v1 instructs the agent to tell consumers their account WILL be sent "
            "to collections or reported to credit bureaus: REMOVE that instruction entirely "
            "and replace with 'escalate to a human specialist and provide CFPB contact info' "
            "[Required per CFPB UDAAP enforcement, 2026].\n"
            "   - If v1 describes subscription cancellation as 'easy', 'straightforward', "
            "or 'a few clicks' without disclosure language: REPLACE with language requiring "
            "the agent to direct customers to review cancellation terms before confirming "
            "[Required per FTC negative option rule enforcement, 2026].\n"
            "   - If v1 allows sharing account data for unverified 'internal team' requests: "
            "REPLACE with strict session-authenticated account-holder only access "
            "[Required per NYDFS 23 NYCRR 500 cybersecurity enforcement, 2026].\n"
            "6. Append an inline citation after each changed or added rule, e.g. "
            "[Updated per FTC enforcement, 2026].\n"
            "7. Update the version field to 2026.06.\n"
            "8. Output ONLY the updated policy document — no preamble, no explanation."
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
                temperature=0.2,
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
