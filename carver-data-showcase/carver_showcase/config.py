"""Constants for the Carver Annotation Data Showcase pipeline.

Logic-free: this module declares only named constants and lookup tables.
No functions, no I/O, no imports beyond stdlib and pycountry.
"""

import datetime
import pathlib

import pycountry

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

DATA_DIR = pathlib.Path(__file__).parent.parent / "data"

ANNOTATIONS_JSONL = DATA_DIR / "annotations.jsonl"
ANNOTATIONS_PARQUET = DATA_DIR / "annotations.parquet"
TOPIC_CATEGORIES_CSV = DATA_DIR / "topic_categories.csv"
TOPIC_CATALOG_CSV = DATA_DIR / "topic_catalog.csv"

# ---------------------------------------------------------------------------
# API parameters
# ---------------------------------------------------------------------------

CARVER_BASE_URL_DEFAULT = "https://app.carveragents.ai"
ANNOTATIONS_DAG_ID = "7f61eee4-1c56-44cc-b7fb-bbfcbda6a5ad"
ARTIFACT_TYPE_ID = "annotations-v1"
API_PAGE_SIZE = 10_000

# ---------------------------------------------------------------------------
# Normalization rules
# ---------------------------------------------------------------------------

# Placeholder values treated as missing (case-insensitive comparison at normalize time).
PLACEHOLDERS: frozenset[str] = frozenset(
    {"", "n/a", "null", "none", "-", "unknown", "n.a.", "na", "tbd", "tba"}
)

# ---------------------------------------------------------------------------
# Score and confidence ranges (Assumption A1, spec §2.1)
# ---------------------------------------------------------------------------

SCORE_RANGE: tuple[int, int] = (0, 10)
CONFIDENCE_RANGE: tuple[int, int] = (0, 1)

# ---------------------------------------------------------------------------
# Label bands: checking convention (Assumption A2, spec §2.1)
# Each tuple is (inclusive_lower, exclusive_upper) except high which includes 10.
# low = [0,4), medium = [4,7), high = [7,10]
# ---------------------------------------------------------------------------

LABEL_BANDS: dict[str, tuple[float, float]] = {
    "low": (0, 4),
    "medium": (4, 7),
    "high": (7, 10),
}

# ---------------------------------------------------------------------------
# Plausible date window (spec §5.3 / §8 — implausible_pub_date anomaly)
# Probe found extremes 1947-12-25 … 2105-07-01; design uses 1990-01-01 .. today+2y.
# ---------------------------------------------------------------------------

_TODAY = datetime.date.today()
PLAUSIBLE_DATE_WINDOW: tuple[datetime.date, datetime.date] = (
    datetime.date(1990, 1, 1),
    datetime.date(_TODAY.year + 2, _TODAY.month, _TODAY.day),
)

# ---------------------------------------------------------------------------
# Richness score weights (spec §5.2) — MUST sum to 1.0
# ---------------------------------------------------------------------------

RICHNESS_WEIGHTS: dict[str, float] = {
    "prose": 0.30,
    "actionables": 0.20,
    "critical_dates": 0.15,
    "reg_refs": 0.15,
    "entities_tags": 0.10,
    "impacted": 0.10,
}

# ---------------------------------------------------------------------------
# Prose length threshold (spec §5.3 — short_prose predicate)
# ---------------------------------------------------------------------------

MIN_PROSE_CHARS: int = 40

# ---------------------------------------------------------------------------
# Rare update_type cutoff (spec §5.3 — update_type_rare predicate)
# update_type values whose snapshot frequency < this are flagged as rare.
# ---------------------------------------------------------------------------

RARE_UPDATE_TYPE_CUTOFF: int = 10

# ---------------------------------------------------------------------------
# Actionable lanes (7) — spec §2.1 output_data.metadata.actionables
# ---------------------------------------------------------------------------

ACTIONABLE_LANES: tuple[str, ...] = (
    "policy_change",
    "status_change",
    "process_change",
    "training_change",
    "reporting_change",
    "tech_data_change",
    "other_change",
)

# ---------------------------------------------------------------------------
# Regulatory reference lanes (6) — spec §2.1 output_data.metadata.reg_references
# ---------------------------------------------------------------------------

REG_REF_LANES: tuple[str, ...] = (
    "rules",
    "statutes",
    "other_ref",
    "personnel",
    "precedents",
    "past_release",
)

# ---------------------------------------------------------------------------
# Impact summary parts (5) — spec §2.1 output_data.metadata.impact_summary
# ---------------------------------------------------------------------------

IMPACT_SUMMARY_PARTS: tuple[str, ...] = (
    "objective",
    "what_changed",
    "why_it_matters",
    "risk_impact",
    "key_requirements",
)

# ---------------------------------------------------------------------------
# ISO country lookup: ISO-2 code -> {iso3, name}
# Built from pycountry at module load time (no network; bundled data).
# ---------------------------------------------------------------------------

ISO_COUNTRY: dict[str, dict[str, str]] = {
    c.alpha_2: {"iso3": c.alpha_3, "name": c.name}
    for c in pycountry.countries
}
