"""Deterministic mechanism classification from Carver update_type."""
from __future__ import annotations

BINDING_ACTION = "Binding Action"
SIGNAL = "Signal"
CONTEXT = "Context"

_LOOKUP: dict[str, str] = {
    "enforcement": BINDING_ACTION,
    "final rule": BINDING_ACTION,
    "proposed rule": SIGNAL,
    "advisory": SIGNAL,
    "guidance": SIGNAL,
    "comment request": SIGNAL,
    "speech": CONTEXT,
    "press release": CONTEXT,
    "bulletin": CONTEXT,
    "trend report": CONTEXT,
    "standard": CONTEXT,
    "insights": CONTEXT,
    "event announcement": CONTEXT,
    "newsletter": CONTEXT,
}


def classify(update_type: str) -> str:
    return _LOOKUP.get(update_type, CONTEXT)
