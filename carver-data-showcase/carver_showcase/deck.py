"""Render the downloadable "State of Carver Data" PDF deck.

One slide per showcase view (Drill-Down and Highlight Reel excluded — they are
per-record, not summary, views), built from the **same chart builders the
gallery uses** (``carver_showcase.charts``) and the **same metrics**
(``carver_showcase.metrics``).  The deck therefore cannot drift from the website,
and — because it always loads the full, unfiltered frame — it shows the site "as
though no filters were selected".

Pipeline per chart: ``charts.fig_*`` → Plotly figure → PNG bytes (kaleido) →
placed on a reportlab canvas.  Pure-Python deps (reportlab + kaleido); no
browser automation, no network, no LLM.

Public entry point
------------------
``build_deck(output_path=DECK_PDF, df=None, catalog_df=None, meta=None) -> Path``
    Render the deck to ``output_path`` (written atomically).  Loads the full
    snapshot, catalog and provenance if not supplied.

Run standalone:  ``.venv/bin/python tools/build_deck.py``
"""

from __future__ import annotations

import datetime
import io
import logging
import os
import pathlib
from typing import Optional

import kaleido
from reportlab.lib.colors import HexColor
from reportlab.lib.utils import ImageReader, simpleSplit
from reportlab.pdfgen import canvas

from carver_showcase import charts
from carver_showcase.config import DECK_PDF, DECK_TITLE
from carver_showcase.curate import drop_noise_update_types
from carver_showcase.load import (
    load_term_stats,
    load_topic_domains,
)
from carver_showcase.metrics import breadth_summary, historical_depth, score_distributions

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Geometry (PowerPoint 16:9 in points: 13.333in × 7.5in) and palette
# ---------------------------------------------------------------------------

PAGE_W, PAGE_H = 960.0, 540.0
MARGIN = 48.0
RENDER_SCALE = 2  # PNG super-sampling for crisp charts

# Carver brand palette (matches the gallery theme + carveragents.ai).
INK = HexColor("#1f2124")      # charcoal — headlines, body, KPI values
BRAND = HexColor("#006638")    # deep theme green — kickers, labels, callout headings, KPI values
ACCENT = HexColor("#bae424")   # signature lime — accent rules & the cover band (never text)
MUTE = HexColor("#6b7280")     # secondary text
HAIR = HexColor("#e5e8ed")     # hairlines / rules (brand grey)
PANEL = HexColor("#eee8dd")    # callout panel background (warm beige)
WHITE = HexColor("#ffffff")    # crisp page background (charts render white-on-white seamlessly)

FONT = "Helvetica"
FONT_B = "Helvetica-Bold"


# ---------------------------------------------------------------------------
# Low-level drawing helpers (all take a top-anchored y for readability)
# ---------------------------------------------------------------------------


def _top(y_from_top: float) -> float:
    """Convert a distance-from-top into reportlab's bottom-origin y."""
    return PAGE_H - y_from_top


def _style_for_print(fig, title_size: int = 17):
    """Apply a clean, legible print theme to a Plotly figure (in place)."""
    fig.update_layout(
        template="plotly_white",
        font=dict(family="Helvetica, Arial, sans-serif", size=13, color="#1a2332"),
        title=dict(font=dict(size=title_size, color="#1a2332"), x=0.01, xanchor="left"),
        paper_bgcolor="white",
        plot_bgcolor="white",
        margin=dict(l=50, r=24, t=46, b=40),
    )
    return fig


def _fig_png(fig, w_pt: float, h_pt: float) -> Optional[ImageReader]:
    """Render a styled figure to a PNG ImageReader sized to the target box.

    Uses ``kaleido.calc_fig_sync`` against the persistent server started by
    ``build_deck`` (so all charts reuse ONE browser — rendering ~16 charts in
    seconds rather than relaunching Chrome per chart).  The figure is laid out
    at exactly the box's dimensions so it fills the box without letterboxing.
    Returns ``None`` on a render failure (the caller draws a placeholder), so one
    bad chart can never abort the whole deck.
    """
    _style_for_print(fig)
    opts = {"format": "png", "width": int(w_pt), "height": int(h_pt), "scale": RENDER_SCALE}
    last_exc: Optional[Exception] = None
    for attempt in range(2):  # retry once — the first call can race a not-yet-warm server
        try:
            return ImageReader(io.BytesIO(kaleido.calc_fig_sync(fig, opts=opts)))
        except Exception as exc:  # pragma: no cover - defensive
            last_exc = exc
            if attempt == 0:
                # Keep the first failure diagnosable — if a chart is genuinely broken
                # (not just a cold-server race) both attempts log here.
                logger.debug("Chart render attempt 1 failed (%r); retrying.", exc)
    logger.warning("Chart render failed (%r); drawing placeholder.", last_exc)
    return None


def _draw_chart(c: canvas.Canvas, fig, x: float, y_from_top: float, w: float, h: float) -> None:
    """Place a chart, filling the (x, top, w, h) box.  Falls back to a label."""
    reader = _fig_png(fig, w, h)
    y = _top(y_from_top + h)
    if reader is not None:
        c.drawImage(reader, x, y, width=w, height=h, mask="auto")
    else:
        c.setFillColor(PANEL)
        c.rect(x, y, w, h, fill=1, stroke=0)
        c.setFillColor(MUTE)
        c.setFont(FONT, 12)
        c.drawCentredString(x + w / 2, y + h / 2, "(chart unavailable)")


def _draw_title(c: canvas.Canvas, kicker: str, title: str) -> None:
    """Slide kicker (small caps brand label) + headline, with an accent rule."""
    c.setFillColor(BRAND)
    c.setFont(FONT_B, 11)
    c.drawString(MARGIN, _top(MARGIN + 4), kicker.upper())
    c.setFillColor(INK)
    c.setFont(FONT_B, 25)
    c.drawString(MARGIN, _top(MARGIN + 34), title)
    c.setStrokeColor(ACCENT)
    c.setLineWidth(2.5)
    c.line(MARGIN, _top(MARGIN + 46), MARGIN + 56, _top(MARGIN + 46))


def _draw_footer(c: canvas.Canvas, snapshot_date: str) -> None:
    """Footer rule + caption + page number.

    The page number comes from ``c.getPageNumber()`` (1-based, current page during
    drawing) so it stays correct automatically when slides are added or removed.
    """
    c.setStrokeColor(HAIR)
    c.setLineWidth(0.75)
    c.line(MARGIN, _top(PAGE_H - 30), PAGE_W - MARGIN, _top(PAGE_H - 30))
    c.setFillColor(MUTE)
    c.setFont(FONT, 8.5)
    c.drawString(
        MARGIN,
        _top(PAGE_H - 20),
        f"Carver  ·  {DECK_TITLE}  ·  snapshot {snapshot_date}  ·  computed live, nothing hard-coded",
    )
    c.drawRightString(PAGE_W - MARGIN, _top(PAGE_H - 20), f"{c.getPageNumber()}")


def _draw_kpis(c: canvas.Canvas, items: list[tuple[str, str]], y_from_top: float, h: float = 70.0) -> None:
    """A row of evenly-spaced KPI cards: big value over a small label."""
    if not items:
        return
    n = len(items)
    gap = 12.0
    total_w = PAGE_W - 2 * MARGIN
    card_w = (total_w - gap * (n - 1)) / n
    y = _top(y_from_top + h)
    for i, (label, value) in enumerate(items):
        x = MARGIN + i * (card_w + gap)
        c.setFillColor(PANEL)
        c.roundRect(x, y, card_w, h, 7, fill=1, stroke=0)
        c.setFillColor(BRAND)
        c.setFont(FONT_B, 23)
        c.drawCentredString(x + card_w / 2, y + h - 33, str(value))
        c.setFillColor(MUTE)
        c.setFont(FONT, 8.5)
        # wrap long labels onto up to two lines
        lines = simpleSplit(label, FONT, 8.5, card_w - 12)[:2]
        for j, ln in enumerate(lines):
            c.drawCentredString(x + card_w / 2, y + 16 - j * 10, ln)


def _draw_callout(c: canvas.Canvas, heading: str, lines: list[str], x: float, y_from_top: float,
                  w: float, h: float) -> None:
    """A panel with a heading and bullet/insight lines (auto-wrapped)."""
    y = _top(y_from_top + h)
    c.setFillColor(PANEL)
    c.roundRect(x, y, w, h, 7, fill=1, stroke=0)
    c.setFillColor(BRAND)
    c.setFont(FONT_B, 11)
    c.drawString(x + 14, y + h - 22, heading)
    c.setFillColor(INK)
    c.setFont(FONT, 10.5)
    cursor = y + h - 42
    for line in lines:
        for wrapped in simpleSplit(line, FONT, 10.5, w - 28):
            if cursor < y + 12:
                return
            c.drawString(x + 14, cursor, wrapped)
            cursor -= 15


def _draw_body_text(c: canvas.Canvas, paragraphs: list[tuple[str, str]], y_from_top: float) -> None:
    """Render (heading, body) paragraphs down the slide body (About slide)."""
    cursor = y_from_top
    max_w = PAGE_W - 2 * MARGIN
    for heading, body in paragraphs:
        if heading:
            c.setFillColor(BRAND)
            c.setFont(FONT_B, 12)
            c.drawString(MARGIN, _top(cursor), heading)
            cursor += 18
        c.setFillColor(INK)
        c.setFont(FONT, 11)
        for wrapped in simpleSplit(body, FONT, 11, max_w):
            c.drawString(MARGIN, _top(cursor), wrapped)
            cursor += 15
        cursor += 10


# ---------------------------------------------------------------------------
# Context: everything a slide might need, computed once.
# ---------------------------------------------------------------------------


def _pct(x) -> str:
    try:
        return f"{float(x):.0%}"
    except (TypeError, ValueError):
        return "—"


def _build_context(df, catalog_df, meta, term_stats=None, has_domains=False) -> dict:
    meta = meta or {}
    bs = breadth_summary(df)
    hd = historical_depth(df)
    dists = score_distributions(df)

    richness = df["richness_score"].dropna() if "richness_score" in df.columns else None
    richness_median = int(richness.median()) if richness is not None and not richness.empty else None
    score_cols = [c for c in ["impact_score", "urgency_score"] if c in df.columns]
    # scores-only — mirrors the gallery Overview KPI "% fully scored (impact+urgency)"
    pct_full = (
        float(df[score_cols].notna().all(axis=1).mean()) if len(score_cols) == 2 else 0.0
    )
    # impact score AND its confidence present — backs the scores-slide caption
    # ("an impact score (0–10) with an explicit confidence"). Impact-only because the
    # external deck mirrors the gallery's impact-only Score Distributions tab.
    impact_conf_cols = [c for c in ["impact_score", "impact_confidence"] if c in df.columns]
    pct_impact_conf = (
        float(df[impact_conf_cols].notna().all(axis=1).mean()) if len(impact_conf_cols) == 2 else 0.0
    )

    geo_counts, _ = charts.geo_country_counts(df)
    top_countries = geo_counts.head(5)[["name", "count"]].values.tolist() if not geo_counts.empty else []

    n_monitored = int(len(catalog_df)) if catalog_df is not None else 0
    n_with_records = 0
    inst_countries = 0
    if catalog_df is not None and not catalog_df.empty and "topic_id" in catalog_df.columns:
        data_ids = set(df["topic_id"].dropna().unique()) if "topic_id" in df.columns else set()
        n_with_records = len(set(catalog_df["topic_id"].dropna().unique()) & data_ids)
        ic, _ = charts.inst_country_counts(catalog_df)
        inst_countries = int(len(ic))

    # update-type long tail
    ut = charts.update_type_counts(df)
    ut_total = int(len(ut))
    ut_shown = min(20, ut_total)
    ut_tail_n = max(0, ut_total - ut_shown)
    ut_tail_records = int(ut.iloc[ut_shown:].sum()) if ut_tail_n > 0 else 0

    def _label_share(axis, band):
        lc = dists.get(axis, {}).get("label_counts", {})
        tot = sum(lc.values()) or 1
        return lc.get(band, 0) / tot

    # Domain breakdown — computed when catalog_df already has top_level merged
    domain_breakdown: list[tuple[str, int]] = []
    n_domain_classified: int = 0
    if has_domains and catalog_df is not None and "top_level" in catalog_df.columns:
        classified = catalog_df[catalog_df["top_level"].notna()]
        n_domain_classified = int(len(classified))
        if not classified.empty:
            vc = classified["top_level"].value_counts()
            domain_breakdown = [(str(k), int(v)) for k, v in vc.items()]

    ctx: dict = {
        "meta": meta,
        "snapshot_date": meta.get("snapshot_date") or datetime.date.today().isoformat(),
        "scope": meta.get("scope", "full"),
        "n_records": int(len(df)),
        "bs": bs,
        "hd": hd,
        "richness_median": richness_median,
        "pct_full": pct_full,
        "pct_impact_conf": pct_impact_conf,
        "top_countries": top_countries,
        "n_monitored": n_monitored,
        "n_with_records": n_with_records,
        "inst_countries": inst_countries,
        "ut_total": ut_total,
        "ut_shown": ut_shown,
        "ut_tail_n": ut_tail_n,
        "ut_tail_records": ut_tail_records,
        "impact_high": _label_share("impact", "high"),
        "term_stats": None,
        "domain_breakdown": domain_breakdown,
        "n_domain_classified": n_domain_classified,
    }

    if term_stats is not None:
        ts_meta = term_stats.get("meta", {})
        breakdown_df = term_stats.get("breakdown")
        entity_leaderboard_df = term_stats.get("entity_leaderboard")
        tag_df = term_stats.get("tag_leaderboard")

        entity_coverage = (
            float((df["n_entities"] > 0).mean()) if "n_entities" in df.columns else 0.0
        )
        tag_coverage = (
            float((df["n_tags"] > 0).mean()) if "n_tags" in df.columns else 0.0
        )
        median_entities = (
            int(df["n_entities"].median()) if "n_entities" in df.columns else 0
        )
        median_tags = (
            int(df["n_tags"].median()) if "n_tags" in df.columns else 0
        )

        # Top entity type buckets from the breakdown (for callout/caption)
        top_buckets: list[str] = []
        if breakdown_df is not None and not breakdown_df.empty and "type" in breakdown_df.columns:
            top_buckets = (
                breakdown_df.sort_values("mentions", ascending=False)["type"]
                .head(4)
                .tolist()
            )

        # Top tags: leading tags from the tag leaderboard
        top_themes = ""
        if tag_df is not None and not tag_df.empty and "tag" in tag_df.columns:
            top_themes = " · ".join(tag_df.nlargest(6, "count")["tag"].tolist())

        ctx["term_stats"] = {
            "n_distinct_entities": ts_meta.get("n_distinct_entities", 0),
            "n_distinct_tags": ts_meta.get("n_distinct_tags", 0),
            "n_entity_mentions": ts_meta.get("n_entity_mentions", 0),
            "n_tag_mentions": ts_meta.get("n_tag_mentions", 0),
            "entity_coverage": entity_coverage,
            "tag_coverage": tag_coverage,
            "median_entities": median_entities,
            "median_tags": median_tags,
            "breakdown_df": breakdown_df,
            "entity_leaderboard_df": entity_leaderboard_df,
            "top_buckets": top_buckets,
            "top_themes": top_themes,
        }

    return ctx


# ---------------------------------------------------------------------------
# Slides
# ---------------------------------------------------------------------------


def _slide_cover(c, ctx, df, catalog_df):
    bs, hd = ctx["bs"], ctx["hd"]
    # signature lime band down the left edge
    c.setFillColor(ACCENT)
    c.rect(0, 0, 12, PAGE_H, fill=1, stroke=0)

    c.setFillColor(BRAND)
    c.setFont(FONT_B, 13)
    c.drawString(MARGIN, _top(150), "CARVER  ·  REGULATORY ANNOTATION CORPUS")
    c.setFillColor(INK)
    c.setFont(FONT_B, 52)
    c.drawString(MARGIN, _top(210), "State of Carver Data")
    c.setFillColor(MUTE)
    c.setFont(FONT, 16)
    c.drawString(
        MARGIN,
        _top(244),
        "A point-in-time portrait of the Carver Agents regulatory-annotation dataset.",
    )

    scope_word = "complete snapshot" if ctx["scope"] == "full" else "representative sample"
    c.setFillColor(BRAND)
    c.setFont(FONT_B, 12)
    c.drawString(MARGIN, _top(280), f"Snapshot — {ctx['snapshot_date']} (UTC)  ·  {scope_word}")

    _draw_kpis(
        c,
        [
            ("Annotations", f"{ctx['n_records']:,}"),
            ("Institutions", f"{bs['n_topics']:,}"),
            ("Countries", f"{bs['n_countries']:,}"),
        ],
        y_from_top=320,
        h=78,
    )
    c.setFillColor(MUTE)
    c.setFont(FONT, 10)
    c.drawString(
        MARGIN,
        _top(430),
        "Every figure is computed live over the snapshot — nothing is hard-coded. "
        "This deck mirrors the showcase with no filters applied.",
    )
    _draw_footer(c, ctx["snapshot_date"])


def _slide_overview(c, ctx, df, catalog_df):
    _draw_title(c, "Overview", "The dataset at a glance")
    bs, hd = ctx["bs"], ctx["hd"]
    _draw_kpis(
        c,
        [
            ("Annotations", f"{ctx['n_records']:,}"),
            ("Institutions", f"{bs['n_topics']:,}"),
            ("Countries", f"{bs['n_countries']:,}"),
            ("Update types", f"{bs['n_update_types']:,}"),
        ],
        y_from_top=108,
        h=64,
    )
    span_years = round((hd["span_days"] or 0) / 365.25, 1) if hd["span_days"] else 0
    _draw_kpis(
        c,
        [
            ("Median richness", f"{ctx['richness_median']}/100" if ctx["richness_median"] is not None else "—"),
            ("Fully scored (impact+urgency)", _pct(ctx["pct_full"])),
            ("Earliest (1% floor)", str(hd["earliest_date"]) if hd["earliest_date"] else "—"),
            ("Latest record", str(hd["latest_date"]) if hd["latest_date"] else "—"),
            ("Data span", f"{span_years} yrs"),
        ],
        y_from_top=182,
        h=64,
    )
    # Recency of dated records — full width. (Impact label mix moved to the
    # Score distributions slide, where the scoring story belongs.)
    body_top = 262
    _draw_chart(c, charts.fig_recency_bar(hd), MARGIN, body_top, PAGE_W - 2 * MARGIN, 200)
    _draw_footer(c, ctx["snapshot_date"])


def _slide_geography(c, ctx, df, catalog_df):
    _draw_title(c, "Geography", "Global reach")
    _draw_chart(c, charts.fig_geo_choropleth(df), MARGIN, 104, PAGE_W - 2 * MARGIN - 232, 330)
    lines = [f"{ctx['bs']['n_countries']:,} jurisdictions present in the data.", ""]
    lines.append("Top countries by record count:")
    for name, count in ctx["top_countries"]:
        lines.append(f"  • {name} — {int(count):,}")
    _draw_callout(c, "Where the coverage is", lines, PAGE_W - MARGIN - 216, 104, 216, 330)
    _draw_footer(c, ctx["snapshot_date"])


def _slide_institutions(c, ctx, df, catalog_df):
    _draw_title(c, "Institutions", "The universe Carver monitors")
    _draw_chart(c, charts.fig_inst_choropleth(catalog_df), MARGIN, 104, PAGE_W - 2 * MARGIN - 232, 330)
    lines = [
        f"{ctx['n_monitored']:,} monitored institutions in Carver's catalog.",
        f"{ctx['n_with_records']:,} have annotations in this snapshot.",
        f"Mapped across {ctx['inst_countries']:,} countries.",
        "",
        "Each unit on the map is an institution (regulators, "
        "agencies, exchanges and standards bodies), not a record.",
    ]
    _draw_callout(c, "The monitored set", lines, PAGE_W - MARGIN - 216, 104, 216, 330)
    _draw_footer(c, ctx["snapshot_date"])


def _slide_institution_domains(c, ctx, df, catalog_df):
    """Slide: institutions by domain — top-level bar (left) + drill-down sunburst (right).

    Called only when ``has_domains=True`` in ``_compose_slides`` — i.e. when
    ``catalog_df`` already has ``top_level`` and ``sub_domain`` merged in.
    """
    _draw_title(c, "Institutions by domain", "What Carver monitors, by sector")
    gap = 16
    half = (PAGE_W - 2 * MARGIN - gap) / 2
    # Main-tier ranking on the left, full two-level drill-down donut on the right
    # (shared colours mean a domain matches across both).
    _draw_chart(c, charts.fig_inst_domain_bar(catalog_df), MARGIN, 104, half, 320)
    _draw_chart(c, charts.fig_inst_domain_sunburst(catalog_df), MARGIN + half + gap, 104, half, 320)

    n_monitored = ctx["n_monitored"]
    n_classified = ctx["n_domain_classified"]
    n_domains = len(ctx["domain_breakdown"])
    c.setFillColor(MUTE)
    c.setFont(FONT, 10.5)
    c.drawString(
        MARGIN,
        _top(104 + 320 + 22),
        f"{n_classified:,} of {n_monitored:,} monitored institutions classified across "
        f"{n_domains} top-level domains — LLM-derived, static, over the full monitored universe.",
    )
    _draw_footer(c, ctx["snapshot_date"])


def _slide_update_types(c, ctx, df, catalog_df):
    _draw_title(c, "Update types", "What is changing")
    _draw_chart(c, charts.fig_update_types(df, top_n=ctx["ut_shown"]), MARGIN, 104, PAGE_W - 2 * MARGIN - 232, 340)
    lines = [
        f"{ctx['ut_total']:,} distinct update-type values across the snapshot.",
        f"Top {ctx['ut_shown']} shown.",
    ]
    if ctx["ut_tail_n"] > 0:
        lines += [
            "",
            f"Long tail: {ctx['ut_tail_n']:,} more values "
            f"({ctx['ut_tail_records']:,} records) — a cardinality-sprawl "
            "data-quality story tracked in the Cockpit.",
        ]
    _draw_callout(c, "The long tail", lines, PAGE_W - MARGIN - 216, 104, 216, 340)
    _draw_footer(c, ctx["snapshot_date"])


def _slide_volume(c, ctx, df, catalog_df):
    _draw_title(c, "Volume over time", "Recency-weighted, a decade deep")
    hd = ctx["hd"]
    _draw_chart(c, charts.fig_volume(df, "YE", floor=True), MARGIN, 104, PAGE_W - 2 * MARGIN - 232, 340)
    rec = hd.get("recency", {})
    span_years = round((hd["span_days"] or 0) / 365.25, 1) if hd["span_days"] else 0
    lines = [
        f"Data span: {span_years} years (from the 1% date floor "
        f"{hd['earliest_date']} to {hd['latest_date']}).",
        "",
        f"{_pct(rec.get('pct_1y'))} of dated records fall within the last year,",
        f"{_pct(rec.get('pct_3y'))} within 3 years, {_pct(rec.get('pct_10y'))} within 10.",
        "",
        "Axis starts at the 1% floor so a sparse older tail "
        "doesn't overstate the span.",
    ]
    _draw_callout(c, "How to read it", lines, PAGE_W - MARGIN - 216, 104, 216, 340)
    _draw_footer(c, ctx["snapshot_date"])


def _slide_scores(c, ctx, df, catalog_df):
    # Impact-only, mirroring the gallery Score Distributions tab (urgency-score detail
    # lives in the Data-Quality Cockpit, not this external deck).
    _draw_title(c, "Score distributions", "Scored, not just labelled")
    # three-up: impact score histogram + confidence histogram + impact label mix.
    # (The label mix moved here from the Overview slide — it's a scoring story.)
    third = (PAGE_W - 2 * MARGIN - 2 * 16) / 3
    _draw_chart(c, charts.fig_score_histogram(df, "impact"), MARGIN, 104, third, 270)
    _draw_chart(c, charts.fig_confidence_histogram(df, "impact"), MARGIN + third + 16, 104, third, 270)
    _draw_chart(c, charts.fig_label_mix(df, "impact"), MARGIN + 2 * (third + 16), 104, third, 270)
    lines = [
        f"{_pct(ctx['pct_impact_conf'])} of records carry an impact score (0–10) with an "
        "explicit confidence.",
        f"  • {_pct(ctx['impact_high'])} of impact scores are labelled high.",
    ]
    _draw_callout(c, "What this proves", lines, MARGIN, 392, PAGE_W - 2 * MARGIN, 92)
    _draw_footer(c, ctx["snapshot_date"])


def _slide_themes_entities(c, ctx, df, catalog_df):
    _draw_title(c, "Tags & Entities", "What the corpus talks about")
    ts = ctx["term_stats"]  # caller guarantees this is not None

    # KPI row — 5 cards across the full body width
    _draw_kpis(
        c,
        [
            ("Distinct entities", f"{ts['n_distinct_entities']:,}"),
            ("Distinct tags", f"{ts['n_distinct_tags']:,}"),
            ("Entity coverage", _pct(ts["entity_coverage"])),
            ("Tag coverage", _pct(ts["tag_coverage"])),
            ("Median entities / rec", str(ts["median_entities"])),
        ],
        y_from_top=108,
        h=60,
    )

    # Two half-width charts side by side (mirroring _slide_overview)
    half = (PAGE_W - 2 * MARGIN - 16) / 2
    chart_top = 180
    chart_h = 216
    _draw_chart(
        c,
        charts.fig_entity_type_breakdown(ts["breakdown_df"]),
        MARGIN,
        chart_top,
        half,
        chart_h,
    )
    _draw_chart(
        c,
        charts.fig_entity_leaderboard(ts["entity_leaderboard_df"], n=12),
        MARGIN + half + 16,
        chart_top,
        half,
        chart_h,
    )

    # Full-width callout: top tags + alias caveat
    callout_lines: list[str] = []
    if ts["top_themes"]:
        callout_lines.append(ts["top_themes"])
    callout_lines.append(
        "Tag strings are LLM-free-text; aliases and near-duplicates "
        "may inflate distinct counts."
    )
    _draw_callout(
        c,
        "Top tags",
        callout_lines,
        MARGIN,
        y_from_top=410,
        w=PAGE_W - 2 * MARGIN,
        h=72,
    )
    _draw_footer(c, ctx["snapshot_date"])


def _slide_about(c, ctx, df, catalog_df):
    _draw_title(c, "About", "How to read this deck")
    paragraphs = [
        (
            "What this is",
            "A point-in-time, filter-free snapshot of the Carver regulatory-annotation "
            "corpus — one slide per view in the live showcase. Every number is computed "
            "live over the snapshot; nothing is hard-coded.",
        ),
        (
            "Richness score (0–100)",
            "A deterministic, rule-based measure of how much structured content an "
            "annotation carries (impact prose, actionables, critical dates, regulatory "
            "references, entities/tags, impacted business) — no LLM, fully reproducible. "
            "It measures completeness, not correctness.",
        ),
        (
            "Dates",
            "The advertised earliest date is a robust 1% quantile floor, so an ultra-sparse "
            "tail of very old records doesn't overstate the span. Dates outside 1990–"
            f"{datetime.date.today().year + 2} are treated as data-entry errors, excluded "
            "from these figures, and tracked as anomalies in the Data-Quality Cockpit.",
        ),
        (
            "Explore the live, interactive showcase",
            "Drill into any single record, filter by jurisdiction / institution / score, and "
            "browse the highlight reel in the live Carver Annotation Data Showcase. The "
            "showcase is access-controlled — contact Carver Agents (carveragents.ai) to "
            "request access.",
        ),
    ]
    _draw_body_text(c, paragraphs, y_from_top=110)
    _draw_footer(c, ctx["snapshot_date"])


def _slide_end(c, ctx, df, catalog_df):
    """Closing slide — a branded bookend to the cover, with a request-access CTA."""
    # signature lime band down the left edge (mirrors the cover)
    c.setFillColor(ACCENT)
    c.rect(0, 0, 12, PAGE_H, fill=1, stroke=0)

    c.setFillColor(BRAND)
    c.setFont(FONT_B, 13)
    c.drawString(MARGIN, _top(190), "CARVER  ·  REGULATORY ANNOTATION CORPUS")
    c.setFillColor(INK)
    c.setFont(FONT_B, 46)
    c.drawString(MARGIN, _top(248), "See it live")
    c.setFillColor(MUTE)
    c.setFont(FONT, 16)
    c.drawString(
        MARGIN,
        _top(284),
        "Explore the full, interactive corpus — drill into records, filter, and export.",
    )
    # Request-access CTA, in the deep brand green.
    c.setFillColor(BRAND)
    c.setFont(FONT_B, 15)
    c.drawString(
        MARGIN,
        _top(332),
        "Request access — contact Carver Agents at carveragents.ai",
    )
    _draw_footer(c, ctx["snapshot_date"])


# Base ordered slides — no optional slides.  SLIDES stays at 9 (incl. the closing
# slide) for the sanity test + import-time checks.
SLIDES = [
    _slide_cover,
    _slide_about,
    _slide_overview,
    _slide_geography,
    _slide_institutions,
    _slide_update_types,
    _slide_volume,
    _slide_scores,
    _slide_end,
]

# Pre-composed list for the themes-only path (no regulators).  Kept for
# backward compatibility and the existing slide-count tests.
_SLIDES_WITH_THEMES = [
    _slide_cover,
    _slide_about,
    _slide_overview,
    _slide_geography,
    _slide_institutions,
    _slide_themes_entities,
    _slide_update_types,
    _slide_volume,
    _slide_scores,
    _slide_end,
]


def _compose_slides(term_stats=None, has_domains=False) -> list:
    """Return the active ordered slide list, inserting optional slides after
    ``_slide_institutions`` in the order:
    [_slide_institution_domains, _slide_themes_entities].

    ``has_domains`` controls whether the domain sunburst slide is included.
    It is placed immediately after ``_slide_institutions`` and before the
    themes optional slide.
    """
    base = [
        _slide_cover,
        _slide_about,
        _slide_overview,
        _slide_geography,
        _slide_institutions,
    ]
    optional: list = []
    if has_domains:
        optional.append(_slide_institution_domains)
    if term_stats is not None:
        optional.append(_slide_themes_entities)
    tail = [
        _slide_update_types,
        _slide_volume,
        _slide_scores,
        _slide_end,
    ]
    return base + optional + tail


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------


def build_deck(
    output_path: pathlib.Path = DECK_PDF,
    df=None,
    catalog_df=None,
    meta: Optional[dict] = None,
) -> pathlib.Path:
    """Render the deck to ``output_path`` (written atomically). Returns the path.

    Loads the full snapshot, catalog and provenance when not supplied, so the
    deck always reflects the website with no filters applied.
    """
    if df is None or catalog_df is None or meta is None:
        # Imported lazily so importing this module doesn't pull the loader/IO.
        from carver_showcase.load import load_catalog, load_normalized, load_snapshot_meta

        if df is None:
            df = load_normalized()
        if catalog_df is None:
            catalog_df = load_catalog()
        if meta is None:
            meta = load_snapshot_meta()

    # The deck is an external artifact — apply the SAME update_type curation the
    # gallery does so the two stay consistent (the Cockpit keeps the full sprawl).
    df = drop_noise_update_types(df)

    # Merge domain taxonomy into catalog_df once (idempotent: skip if already present).
    domains = load_topic_domains()
    if not domains.empty and "top_level" not in catalog_df.columns and "topic_id" in catalog_df.columns:
        catalog_df = catalog_df.merge(
            domains[["topic_id", "top_level", "sub_domain"]],
            on="topic_id",
            how="left",
        )
    has_domains = (
        "top_level" in catalog_df.columns
        and catalog_df["top_level"].notna().any()
    )

    # Load optional enrichment artifacts and compose the active slide list.
    term_stats = load_term_stats()
    active_slides = _compose_slides(
        term_stats=term_stats,
        has_domains=has_domains,
    )

    output_path = pathlib.Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    tmp = output_path.with_suffix(output_path.suffix + ".tmp")

    ctx = _build_context(
        df, catalog_df, meta,
        term_stats=term_stats,
        has_domains=has_domains,
    )
    c = canvas.Canvas(str(tmp), pagesize=(PAGE_W, PAGE_H))
    c.setTitle(f"{DECK_TITLE} — {ctx['snapshot_date']}")
    c.setAuthor("Carver")

    # Quiet kaleido/choreographer's chatty INFO logs and reuse ONE browser for
    # every chart on the deck (otherwise each chart relaunches Chrome — minutes).
    for noisy in ("kaleido", "choreographer", "logistro"):
        logging.getLogger(noisy).setLevel(logging.WARNING)
    kaleido.start_sync_server(silence_warnings=True)
    try:
        for slide in active_slides:
            c.setFillColor(WHITE)
            c.rect(0, 0, PAGE_W, PAGE_H, fill=1, stroke=0)
            slide(c, ctx, df, catalog_df)
            c.showPage()
    finally:
        kaleido.stop_sync_server(silence_warnings=True)
    c.save()

    os.replace(tmp, output_path)
    logger.info("Deck written: %s (%d slides)", output_path, len(active_slides))
    return output_path
