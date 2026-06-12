"""Shared visual constants for the showcase apps.

The score-axis order and per-axis colors now live in ``carver_showcase.config``
(the logic-free constants module) so the framework-agnostic chart builders in
``carver_showcase.charts`` can share them without the app layer importing back
into a Streamlit module.  This module simply re-exports them so existing app
imports (``from apps.components.theme import AXIS_COLORS, SCORE_AXES``) keep
working — there is still exactly one source of truth.

Relevance is intentionally absent: it is a deprecated weighted sum of impact
and urgency, so neither app surfaces it as a scored axis.  Only the two
independent axes are shown.
"""

from carver_showcase.config import AXIS_COLORS, SCORE_AXES

__all__ = ["SCORE_AXES", "AXIS_COLORS"]
