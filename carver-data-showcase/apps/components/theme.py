"""Shared visual constants for the showcase apps.

One source of truth for the score-axis order and the per-axis colors so the
Gallery and the Cockpit can't drift to slightly different palettes.
"""

# The three scored axes, in canonical display order.
SCORE_AXES = ["impact", "urgency", "relevance"]

# One canonical color per score axis, used by both apps' distribution charts.
AXIS_COLORS = {
    "impact": "#d32f2f",     # red
    "urgency": "#f57c00",    # orange
    "relevance": "#1976d2",  # blue
}
