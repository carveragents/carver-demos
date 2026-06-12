"""Constants for the Carver Annotation Data Showcase pipeline.

Logic-free: this module declares only named constants and lookup tables.
No functions, no I/O, no imports beyond stdlib and pycountry.
"""

import datetime
import os
import pathlib

import pycountry

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

DATA_DIR = pathlib.Path(
    os.environ.get("CARVER_DATA_DIR") or (pathlib.Path(__file__).parent.parent / "data")
)

ANNOTATIONS_JSONL = DATA_DIR / "annotations.jsonl"
ANNOTATIONS_PARQUET = DATA_DIR / "annotations.parquet"
TOPIC_CATEGORIES_CSV = DATA_DIR / "topic_categories.csv"
TOPIC_CATALOG_CSV = DATA_DIR / "topic_catalog.csv"
# Snapshot provenance (pull date + scope + per-category counts), written by the
# pull tool so the apps can show an honest "point-in-time as of <date>" note.
SNAPSHOT_META_JSON = DATA_DIR / "snapshot_meta.json"

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

# Historical-depth DISPLAY floor (presentation only — NOT anomaly detection).
# The advertised "earliest record" uses this low quantile of the in-window dates
# instead of the hard minimum, so an ultra-sparse tail of very old (but in-window)
# records doesn't define the headline span. A robust quantile is used rather than
# a mean±σ rule because the date distribution is a heavily right-loaded spike
# (median ~now, skew ≈ -4), where moments are meaningless. Anomaly detection still
# uses PLAUSIBLE_DATE_WINDOW; the true min/max are reported alongside for honesty.
HISTORICAL_DEPTH_FLOOR_QUANTILE: float = 0.01

# Recency windows (years) reported by historical_depth — the share of dated records
# within the last N years, surfaced as KPIs on the Overview tab and the deck.
RECENCY_WINDOWS_YEARS: tuple[int, ...] = (1, 2, 3, 5, 10)

# ---------------------------------------------------------------------------
# Carver brand palette (sampled from carveragents.ai) — the single source of
# truth for the gallery theme, the chart builders, and the deck so all three
# match the marketing site.  Signature look: warm off-white surfaces, charcoal
# ink, and a lime-green accent (every CTA on the site is lime), with a secondary
# blue and support green.
# ---------------------------------------------------------------------------

CARVER_LIME = "#bae424"        # signature accent (CTAs, highlights, primary)
CARVER_LIME_DEEP = "#8aa80f"   # darker lime — legible on off-white for text/thin marks
CARVER_CHARCOAL = "#1f2124"    # dark surfaces + primary ink
CARVER_SLATE = "#1b2a38"       # secondary dark / deep text
CARVER_OFFWHITE = "#fbf7f3"    # warm background
CARVER_BEIGE = "#eee8dd"       # secondary surface (cards, panels, sidebar)
CARVER_BLUE = "#116df8"        # secondary accent (links, secondary series)
CARVER_GREEN = "#08b54f"       # support green
CARVER_MUTE = "#6b7280"        # secondary / caption text
CARVER_HONEYDEW = "#e2ffd9"    # pale lime — low end of the sequential scale
CARVER_GREEN_DEEP = "#006638"  # deep green — high end of the sequential scale

# Brand-anchored qualitative palette for categorical charts that need several
# distinguishable hues (leads with the brand colours, then extends with
# harmonious, CVD-aware hues — no two adjacent darks).
CARVER_QUALITATIVE: list[str] = [
    CARVER_LIME,       # lime
    CARVER_CHARCOAL,   # charcoal
    CARVER_BLUE,       # blue
    CARVER_GREEN,      # green
    "#f2a900",         # amber
    "#7e57c2",         # purple
    "#00897b",         # teal
    "#d6705a",         # rust
    "#c2185b",         # magenta
    "#5d6d7e",         # steel
    CARVER_LIME_DEEP,  # olive-lime
]

# ---------------------------------------------------------------------------
# Score axes + per-axis colors (single source of truth, shared by the apps and
# the chart builders).  Relevance is intentionally absent: it is a deprecated
# weighted sum of impact and urgency, so neither app nor the deck surfaces it.
# apps/components/theme.py re-exports these for the app layer.
# Rebranded to the Carver palette (impact = charcoal, urgency = lime).
# ---------------------------------------------------------------------------

SCORE_AXES: list[str] = ["impact", "urgency"]

AXIS_COLORS: dict[str, str] = {
    "impact": CARVER_CHARCOAL,   # charcoal
    "urgency": CARVER_LIME,      # lime
}

# ---------------------------------------------------------------------------
# Generated deck artifact (the downloadable "State of Carver Data" PDF).
# Re-rendered by tools/build_deck.py (and after every tools/pull_full.py run);
# the gallery serves it from disk via a download button.
# ---------------------------------------------------------------------------

DECK_PDF = DATA_DIR / "carver-state-of-data.pdf"
DECK_TITLE = "State of Carver Data"

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
# External-gallery update_type curation (GALLERY + DECK ONLY — never the Cockpit).
# The public showcase drops update_type "noise" so it doesn't appear in the
# dataset, KPIs, charts, or filters:
#   1. any value contributing less than GALLERY_UPDATE_TYPE_MIN_SHARE of total
#      volume (the long tail of ~96 one-off `other (…)` variants), and
#   2. explicitly-named crawl-junk values that sit ABOVE that threshold but are
#      not real regulatory update types (DENYLIST).
# The Data-Quality Cockpit keeps the full, uncurated sprawl for QA — these
# constants are consumed only by carver_showcase.curate, which only the gallery
# and the deck call.
# ---------------------------------------------------------------------------

GALLERY_UPDATE_TYPE_MIN_SHARE: float = 0.0001  # 0.01% of total records

GALLERY_UPDATE_TYPE_DENYLIST: frozenset[str] = frozenset(
    {
        "website error",             # crawl / website error, not a regulatory update type
        "other (invalid document)",  # unparseable / invalid crawl artifact
    }
)

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

# ---------------------------------------------------------------------------
# Entity types and definitions (for term stats enrichment)
# ---------------------------------------------------------------------------

ENTITY_TYPES: tuple[str, ...] = (
    "Regulator / Supervisor",
    "Government body",
    "International body",
    "Company",
    "Person",
    "Other",
)

ENTITY_TYPE_DEFINITIONS: dict[str, str] = {
    "Regulator / Supervisor": "A body that regulates or supervises a sector, including central banks.",
    "Government body": "A government organ that is not primarily a financial supervisor: ministries, executive departments, legislatures, courts, law-enforcement.",
    "International body": "Intergovernmental and standard-setting organisations.",
    "Company": "A commercial firm or private-sector organisation.",
    "Person": "A named individual (official, executive, etc.).",
    "Other": "Places, and anything genuinely unclassifiable.",
}

# Brand-anchored, visually-distinct hues (one per entity type). The most
# important type (the regulators/supervisors the corpus is about) takes the
# brand charcoal; the rest are CVD-aware and distinct.  Lime is reserved for
# interactive accents, not entity fills (it reads too close to the green here).
ENTITY_TYPE_COLORS: dict[str, str] = {
    "Regulator / Supervisor": CARVER_CHARCOAL,  # charcoal
    "Government body": CARVER_BLUE,             # blue
    "International body": CARVER_GREEN,         # green
    "Company": "#f2a900",                       # amber
    "Person": "#7e57c2",                        # purple
    "Other": "#9aa0a6",                         # gray
}

# ---------------------------------------------------------------------------
# Term stats enrichment paths (entity and tag extraction, classification, charts)
# ---------------------------------------------------------------------------

ENTITY_MENTIONS_CSV = DATA_DIR / "entity_mentions.csv"
TAG_MENTIONS_CSV = DATA_DIR / "tag_mentions.csv"
ENTITY_TYPES_CSV = DATA_DIR / "entity_types.csv"
ENTITY_TYPE_BREAKDOWN_CSV = DATA_DIR / "entity_type_breakdown.csv"
ENTITY_LEADERBOARD_CSV = DATA_DIR / "entity_leaderboard.csv"
TAG_LEADERBOARD_CSV = DATA_DIR / "tag_leaderboard.csv"
TERM_STATS_META_JSON = DATA_DIR / "term_stats_meta.json"
ENTITY_BATCH_REQUESTS_JSONL = DATA_DIR / "entity_batch_requests.jsonl"
ENTITY_BATCH_OUTPUT_JSONL = DATA_DIR / "entity_batch_output.jsonl"
ENTITY_BATCH_STATE_JSON = DATA_DIR / "entity_batch_state.json"

# ---------------------------------------------------------------------------
# Term stats enrichment parameters
# ---------------------------------------------------------------------------

OPENAI_MODEL: str = "gpt-4o-mini"
ENTITY_CHUNK_SIZE: int = 50
MAX_RETRIES: int = 2
ENTITY_LEADERBOARD_TOP_N: int = 20
TAG_LEADERBOARD_TOP_N: int = 20
REGULATOR_LEADERBOARD_TOP_N: int = 20

# ---------------------------------------------------------------------------
# Regulator canonicalization (GALLERY + DECK ONLY — never the Cockpit).
# An OpenAI pass collapses the ~11.4k raw, multilingual `regulator_name`
# variants to a deduplicated canonical English name AND flags an `is_regulator`
# boolean: true for any governmental / public-sector body (regulators,
# supervisors, central banks, ministries/departments/agencies, and
# intergovernmental / standard-setting organisations), false only for clearly
# private-sector entities (companies, news/media outlets, named individuals,
# trade associations).  The Overview "Regulators" KPI then counts distinct
# public bodies, excluding private-sector sources.  Mirrors the entity-typing
# pipeline; tools/canonicalize_regulators.py is the ONLY consumer that imports
# openai / reads OPENAI_API_KEY.  Reuses OPENAI_MODEL and MAX_RETRIES above.
# ---------------------------------------------------------------------------

REGULATOR_CONTEXT_CSV = DATA_DIR / "regulator_context.csv"          # debug/reproducible input
REGULATOR_CANONICAL_CSV = DATA_DIR / "regulator_canonical.csv"      # raw -> canonical + is_regulator
REGULATOR_BATCH_REQUESTS_JSONL = DATA_DIR / "regulator_batch_requests.jsonl"
REGULATOR_BATCH_OUTPUT_JSONL = DATA_DIR / "regulator_batch_output.jsonl"
REGULATOR_BATCH_STATE_JSON = DATA_DIR / "regulator_batch_state.json"

# Overview/deck "Regulators" KPI counts only deduped bodies with >= this many
# mentions (row-count in the passed DataFrame, so it's filter-aware).
# Drops the long tail of one/two-off names from the headline figure.
REGULATOR_MIN_MENTIONS: int = 3   # count only bodies with 3+ mentions in the view

# Richer per-name context => smaller chunks than the entity job (50).
REGULATOR_CHUNK_SIZE: int = 25

# Caps on the per-name context attached to each distinct regulator name, to
# bound request tokens while preserving the disambiguating signal.
REGULATOR_CTX_TOP_COUNTRIES: int = 3
REGULATOR_CTX_MAX_DIVISIONS: int = 2
REGULATOR_CTX_MAX_DOMAINS: int = 2
REGULATOR_CTX_MAX_TITLES: int = 2
REGULATOR_CTX_TITLE_MAXLEN: int = 120

# ---------------------------------------------------------------------------
# Institution domain classification (GALLERY + DECK ONLY — never the Cockpit).
# The raw topic `tags` field is empty on every institution, so a domain can't be
# read off a single column. An OpenAI pass (tools/classify_domains.py, the 3rd
# and final OPENAI_API_KEY consumer alongside classify_entities and
# canonicalize_regulators) synthesizes each monitored institution's descriptive
# attributes — name, sectors, industries, sub_entity_type, entity_type, scope,
# description — into ONE leaf from the fixed two-level taxonomy below. The leaf's
# parent (top-level domain) is derived deterministically from the taxonomy, so
# the LLM can never mis-nest a leaf. The Institutions tab + deck slide render a
# two-ring sunburst donut (inner ring = top-level, outer ring = sub-domain) over
# the full monitored universe.
#
# This is a DISTINCT, externally-safe taxonomy — NOT the internal-only derived
# `category` (Finance / Data protection / Medical Devices / Uncategorized), which
# must never be surfaced in the gallery or deck.
# ---------------------------------------------------------------------------

# Two-level taxonomy: top-level domain -> ordered tuple of leaf sub-domains.
# The LLM chooses exactly one LEAF per institution; the parent is looked up.
# 11 top-level domains / 27 leaves. "Other Government / Cross-sector" is the
# fallback for genuine general-government bodies (legislatures, whole-of-
# government ministries, audit institutions, municipal/national governments,
# e-government portals, and multi-purpose political/economic unions) that fit no
# specific domain.
INSTITUTION_DOMAIN_TAXONOMY: dict[str, tuple[str, ...]] = {
    "Finance": (
        "Banking & Central Banking",
        "Securities & Capital Markets",
        "Insurance",
        "Payments & Market Infrastructure",
        "Asset Management & Pensions",
        "Consumer Finance & Credit",
        "Tax & Revenue",
    ),
    "Technology": (
        "Data Protection & Privacy",
        "Cybersecurity",
        "Telecoms & Digital Services",
    ),
    "Healthcare & Life Sciences": (
        "Public Health",
        "Medical Devices & Pharma",
    ),
    "Environment & Energy": (
        "Environment & Climate",
        "Energy & Utilities",
    ),
    "Trade, Corporate & Professional": (
        "Corporate & Business Registration",
        "Professional Services & Accounting",
        "Trade & Competition",
    ),
    "Justice & Public Safety": (
        "Justice & Courts",
        "Law Enforcement & Public Safety",
    ),
    "Transport & Infrastructure": (
        "Transport & Aviation",
        "Infrastructure, Housing & Construction",
    ),
    "Education, Labour & Social": (
        "Labour & Employment",
        "Education & Social Welfare",
    ),
    "Science, Research & Standards": (
        "Research & Innovation",
        "Statistics, Standards & Weather",
    ),
    "Gambling & Gaming": (
        "Gambling & Gaming",
    ),
    "Other Government": (
        "Other Government / Cross-sector",
    ),
}

# Flat ordered tuple of every leaf — the closed set the LLM must choose from.
INSTITUTION_DOMAIN_LEAVES: tuple[str, ...] = tuple(
    leaf for leaves in INSTITUTION_DOMAIN_TAXONOMY.values() for leaf in leaves
)

# leaf sub-domain -> top-level domain (single source of truth for the parent ring).
INSTITUTION_DOMAIN_PARENT: dict[str, str] = {
    leaf: top
    for top, leaves in INSTITUTION_DOMAIN_TAXONOMY.items()
    for leaf in leaves
}

# Catch-all leaf for institutions that fit no specific domain (and the safe
# fallback when the LLM returns an out-of-taxonomy or missing value).
DOMAIN_FALLBACK_LEAF: str = "Other Government / Cross-sector"

# Reproducible LLM input (one row per institution, all context fields) and the
# classification output (raw topic -> leaf + top-level + optional secondary).
TOPIC_DOMAIN_CONTEXT_CSV = DATA_DIR / "topic_domain_context.csv"
TOPIC_DOMAINS_CSV = DATA_DIR / "topic_domains.csv"

# Richer per-topic context (free-text description) => modest chunk size. Smaller
# chunks reduce cross-institution "neighbour" bias (a batch full of general-
# government bodies was observed to pull ambiguous financial bodies toward the
# cross-sector fallback). Reuses MAX_RETRIES above.
DOMAIN_CHUNK_SIZE: int = 20

# The domain job uses a STRONGER model than the other enrichment jobs. Mapping an
# institution into an 11-domain / 27-leaf taxonomy with nuanced routing rules is a
# reasoning task; gpt-4o-mini was observed to ignore explicit rules (e.g. leaving a
# central bank in the cross-sector fallback) and to classify unstably run-to-run.
# This is a one-time offline pass over ~1.1k institutions (~54 calls), so the
# upgrade is cheap. Right-sized per CLAUDE.md: mini for the simpler regulator job,
# gpt-4o for this harder one.
DOMAIN_MODEL: str = "gpt-4o"

# ---------------------------------------------------------------------------
# Public deployment constants (see docs/superpowers/specs/2026-06-12-public-deployment-design.md)
#
# These constants power the public bundle export (tools/export_public_bundle.py)
# and the offline bundle validator (tools/validate_bundle.py).
#
# Trust boundary: the public app reads only data/public/, never raw annotations.
# The validators act as a blocking gate: a hard FAIL prevents the commit, so a
# leaky or malformed bundle can never reach Streamlit.  All constants here are
# pure data — no functions, no I/O.
# ---------------------------------------------------------------------------

# Subdirectory under DATA_DIR where the public bundle lives.
# The slim parquet and all aggregate sidecars are committed here; Streamlit
# Community Cloud reads from this directory with CARVER_DATA_DIR=data/public.
PUBLIC_DATA_SUBDIR: str = "public"

# The slim annotations frame shipped in the public bundle — exactly these columns,
# in this order.  Every name must be a member of schema.NORMALIZED_COLUMNS.
# Identifiers (artifact_id, entry_id, source_id), all content prose (title,
# summary, feed_url, base_url, *_reasoning, regulator_*), detailed date columns,
# richness-constituent has_*/n_reg_* columns, and category (internal) are all
# dropped.  Each row becomes (institution, jurisdiction, scores, pub-date, counts).
PUBLIC_KEEP_COLUMNS: tuple[str, ...] = (
    "topic_id",
    "jurisdiction_country", "jurisdiction_bloc", "jurisdiction_scope",
    "impact_score", "impact_confidence", "impact_label",
    "urgency_score", "urgency_confidence", "urgency_label",
    "update_type",
    "reconciled_published_date",
    "richness_score",
    "n_entities", "n_tags",
)

# Column names that must NEVER appear in the public bundle (belt-and-suspenders
# leak gate — the validator checks for these explicitly).
PUBLIC_CONTENT_DENYLIST: frozenset[str] = frozenset(
    {
        "title",
        "summary",
        "feed_url",
        "base_url",
        "jurisdiction_reasoning",
        "regulator_name",
        "regulator_division",
        "regulator_other_agency",
        "artifact_id",
        "entry_id",
        "source_id",
    }
)

# Maximum allowed byte-length of any string value in a public-frame string column.
# Content prose (title, summary) is far longer; values exceeding this in a
# supposedly-slim column signal a leak of content that must be caught at the gate.
PUBLIC_STRING_MAXLEN: int = 64

# Hard failure threshold: if the public bundle row count drops by more than this
# fraction vs the baseline, the validator exits non-zero (collapsed data gate).
PUBLIC_ROWCOUNT_DROP_TOLERANCE: float = 0.20

# Orphan topic_id tolerance: the live feed adds institutions continuously, so the
# catalog may lag the annotation pull by a handful of new topic_ids.  The gallery
# renders missing catalog names gracefully.  HARD-fail only when the orphan SHARE
# of DISTINCT topic_ids exceeds this fraction; a few stragglers (<= 3%) are fine.
# Set to 3% (not 2%) to accommodate real-world catalog lag: observed ~2.5% (26/1036
# institutions) on the current corpus with institutions added since the last catalog pull.
PUBLIC_ORPHAN_TOPIC_TOLERANCE: float = 0.03

# Soft warning threshold: local full-row count vs the upstream annotations total
# is expected to differ by at most this fraction (live feed drifts slightly).
UPSTREAM_RECORD_TOLERANCE: float = 0.01

# Minimum byte size of the public deck PDF (used by check_deck_pdf in validate_bundle).
PUBLIC_DECK_MIN_BYTES: int = 20_000

# Maximum age (days) of the newest upstream artifact relative to snapshot date,
# used by check_freshness in validate_upstream.
UPSTREAM_FRESHNESS_MAX_AGE_DAYS: int = 7
