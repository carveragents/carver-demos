"""Unit tests for carver_showcase.deck — PDF deck builder.

Strategy: monkeypatch kaleido's sync rendering calls so no Chrome is launched.
All chart renders return a tiny valid 1×1 PNG.  Tests verify:
- build_deck() produces a real PDF file with exactly len(SLIDES) pages.
- The PDF starts with the ``%PDF-`` magic bytes.
- Resilience: if a chart render raises, the deck still builds without exception
  and still has the correct page count.

Page counting: pypdf is not in this project's deps.  We use a byte-level heuristic
(count ``/Type /Page`` or ``/Type/Page`` occurrences in the PDF bytes).
"""

from __future__ import annotations

import io
import pathlib

import pandas as pd
import pytest

import carver_showcase.deck as deck_module
from carver_showcase.deck import SLIDES, _SLIDES_WITH_THEMES, _compose_slides, build_deck

# ---------------------------------------------------------------------------
# Tiny 1×1 RGBA PNG (hand-crafted, no Pillow needed at test time)
# ---------------------------------------------------------------------------

_TINY_PNG = (
    b'\x89PNG\r\n\x1a\n'
    b'\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06'
    b'\x00\x00\x00\x1f\x15\xc4\x89'
    b'\x00\x00\x00\nIDATx\x9cc\x00\x01\x00\x00\x05\x00\x01\r\n-\xb4'
    b'\x00\x00\x00\x00IEND\xaeB`\x82'
)


def _count_pages(pdf_bytes: bytes) -> int:
    """Count pages in a PDF using a byte-level heuristic.

    Counts occurrences of the ``/Type /Page`` or ``/Type/Page`` tokens
    that mark individual page objects (not the Pages tree root, which
    carries ``/Type /Pages``).
    """
    # /Type /Page (not /Pages) — the two most common serialisations
    count = pdf_bytes.count(b"/Type /Page") + pdf_bytes.count(b"/Type/Page")
    # reportlab sometimes writes /Type/Pages for the root — subtract those
    count -= pdf_bytes.count(b"/Type /Pages") + pdf_bytes.count(b"/Type/Pages")
    return max(count, 0)


# ---------------------------------------------------------------------------
# Local fixtures (duplicated here for simplicity, not added to conftest.py)
# ---------------------------------------------------------------------------


def _make_df() -> pd.DataFrame:
    n = 15
    dates = pd.to_datetime(
        [
            "2021-03-01", "2021-09-15", "2022-01-10", "2022-06-20", "2022-11-30",
            "2023-02-14", "2023-07-04", "2023-12-01", "2024-03-08", "2024-08-18",
            "2025-01-05", "2025-04-22", "2025-09-09", "2026-01-15", "2026-05-28",
        ],
        utc=True,
    )
    topic_ids = ["t1", "t2", "t3", "t1", "t2", "t3", "t4", "t1", "t2", "t3",
                 "t4", "t1", "t2", "t3", "t4"]
    categories = ["Finance"] * 7 + ["Medical Devices"] * 4 + ["Data Protection"] * 4
    countries = ["US", "GB", "DE", "US", "GB", "FR", "DE", "US", "AU", "GB",
                 "US", "DE", "FR", "AU", "US"]
    blocs = ["G7", "EU", "EU", "G7", "EU", None, "EU", "G7", "APAC", "EU",
             "G7", "EU", "EU", "APAC", "G7"]
    scopes = ["national"] * 13 + ["supranational"] * 2
    update_types = [
        "Regulatory Update", "Guidance", "Consultation", "Regulatory Update",
        "Guidance", "Final Rule", "Regulatory Update", "Consultation",
        "Guidance", "Regulatory Update", "Final Rule", "Guidance",
        "Consultation", "Regulatory Update", "Guidance",
    ]
    urgency_bases = [
        "future_deadline", "no_future_date", "past_deadline", "future_deadline",
        "no_future_date", "effective_immediately", "future_deadline",
        "no_future_date", "past_deadline", "future_deadline",
        "no_future_date", "effective_immediately", "future_deadline",
        "no_future_date", "past_deadline",
    ]
    impact_scores = [8.0, 5.0, 3.0, 7.5, 6.0, 4.0, 9.0, 2.0, 8.5, 5.5,
                     7.0, 3.5, 6.5, 8.0, 4.5]
    urgency_scores = [7.0, 4.5, 2.0, 6.0, 5.5, 3.0, 8.0, 2.5, 7.5, 4.0,
                      6.5, 3.0, 5.0, 7.0, 4.0]
    impact_confs = [0.9, 0.7, 0.6, 0.85, 0.75, 0.65, 0.95, 0.55,
                    0.88, 0.72, 0.80, 0.60, 0.78, 0.90, 0.68]
    urgency_confs = [0.8, 0.75, 0.5, 0.82, 0.70, 0.60, 0.88, 0.52,
                     0.84, 0.66, 0.78, 0.58, 0.72, 0.86, 0.64]
    impact_labels = ["high"] * 5 + ["medium"] * 5 + ["low"] * 5
    urgency_labels = ["high"] * 4 + ["medium"] * 6 + ["low"] * 5
    richness = [70, 50, 30, 65, 55, 40, 80, 25, 75, 45, 60, 35, 58, 72, 42]
    regulator_names = ["SEC", "FCA", "BaFin", "SEC", "FCA", "AMF", "BaFin",
                       "SEC", "APRA", "FCA", "SEC", "BaFin", "AMF", "APRA", "SEC"]

    return pd.DataFrame(
        {
            "topic_id": pd.array(topic_ids, dtype="string"),
            "category": pd.array(categories, dtype="string"),
            "jurisdiction_country": pd.array(countries, dtype="string"),
            "jurisdiction_bloc": pd.array(blocs, dtype="string"),
            "jurisdiction_scope": pd.array(scopes, dtype="string"),
            "update_type": pd.array(update_types, dtype="string"),
            "urgency_basis": pd.array(urgency_bases, dtype="string"),
            "impact_score": pd.array(impact_scores, dtype="Float64"),
            "urgency_score": pd.array(urgency_scores, dtype="Float64"),
            "impact_confidence": pd.array(impact_confs, dtype="Float64"),
            "urgency_confidence": pd.array(urgency_confs, dtype="Float64"),
            "impact_label": pd.array(impact_labels, dtype="string"),
            "urgency_label": pd.array(urgency_labels, dtype="string"),
            "richness_score": pd.array(richness, dtype="Float64"),
            "reconciled_published_date": dates,
            "regulator_name": pd.array(regulator_names, dtype="string"),
        }
    )


def _make_catalog() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "topic_id": pd.array(
                ["t1", "t2", "t3", "t4", "t5", "t6", "t7", "t8"], dtype="string"
            ),
            "name": pd.array(
                [
                    "US Federal Reserve", "FCA UK", "BaFin Germany",
                    "California DBO", "ECB Euro", "Unknown Multi",
                    "SEC USA", "APRA Australia",
                ],
                dtype="string",
            ),
            "jurisdiction_code": pd.array(
                ["US", "GB", "DE", "US-CA", "EU", "-", "US", "AU"], dtype="string"
            ),
            "entity_type": pd.array(
                [
                    "Central Bank", "Regulator", "Regulator",
                    "Central Bank;Regulator", "Central Bank",
                    "Regulator", "Regulator", "Prudential Regulator",
                ],
                dtype="string",
            ),
            "scope": pd.array(
                ["national", "national", "national", "state", "supranational",
                 "national", "national", "national"],
                dtype="string",
            ),
        }
    )


def _make_meta(df: pd.DataFrame) -> dict:
    return {
        "snapshot_date": "2026-06-10",
        "scope": "full",
        "total_records": len(df),
    }


# ---------------------------------------------------------------------------
# Shared monkeypatch helpers
# ---------------------------------------------------------------------------


def _patch_kaleido_ok(monkeypatch):
    """Patch kaleido so renders return a 1×1 PNG without launching Chrome."""
    monkeypatch.setattr(deck_module.kaleido, "calc_fig_sync", lambda fig, opts=None: _TINY_PNG)
    monkeypatch.setattr(deck_module.kaleido, "start_sync_server", lambda **kw: None)
    monkeypatch.setattr(deck_module.kaleido, "stop_sync_server", lambda **kw: None)


def _patch_no_term_stats(monkeypatch):
    """Patch load_term_stats to return None (no enrichment run)."""
    monkeypatch.setattr(deck_module, "load_term_stats", lambda: None)


def _make_term_stats_fixture() -> dict:
    """Return a minimal term_stats dict for testing the 9-slide path."""
    breakdown_df = pd.DataFrame(
        {
            "type": ["Regulator", "Company", "Person", "Legislation", "Concept", "Other"],
            "mentions": [500, 300, 200, 150, 100, 50],
            "distinct_entities": [30, 50, 20, 15, 10, 5],
        }
    )
    entity_leaderboard_df = pd.DataFrame(
        {
            "canonical_name": [f"Entity {i}" for i in range(1, 16)],
            "type": (["Regulator"] * 5 + ["Company"] * 5 + ["Person"] * 5),
            "mentions": list(range(100, 85, -1)),
        }
    )
    tag_leaderboard_df = pd.DataFrame(
        {
            "tag": ["Compliance", "Monetary policy", "Cybersecurity",
                    "Capital requirements", "AML", "Stress testing"],
            "count": [400, 350, 300, 250, 200, 150],
        }
    )
    meta = {
        "n_distinct_entities": 130,
        "n_entity_mentions": 1300,
        "n_distinct_tags": 85,
        "n_tag_mentions": 1750,
        "model": "gpt-4o-mini",
        "enriched_at": "2026-06-10T00:00:00+00:00",
        "n_classified": 130,
    }
    return {
        "breakdown": breakdown_df,
        "entity_leaderboard": entity_leaderboard_df,
        "tag_leaderboard": tag_leaderboard_df,
        "meta": meta,
    }


def _patch_term_stats_ok(monkeypatch):
    """Patch load_term_stats to return a small fixture dict."""
    fixture = _make_term_stats_fixture()
    monkeypatch.setattr(deck_module, "load_term_stats", lambda: fixture)



# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestBuildDeck:
    def test_returns_path(self, tmp_path, monkeypatch):
        """build_deck() must return the output path."""
        _patch_kaleido_ok(monkeypatch)
        _patch_no_term_stats(monkeypatch)
        df = _make_df()
        catalog = _make_catalog()
        meta = _make_meta(df)
        result = build_deck(output_path=tmp_path / "deck.pdf", df=df, catalog_df=catalog, meta=meta)
        assert isinstance(result, pathlib.Path)

    def test_file_exists(self, tmp_path, monkeypatch):
        """The output file must exist after build_deck() returns."""
        _patch_kaleido_ok(monkeypatch)
        _patch_no_term_stats(monkeypatch)
        df = _make_df()
        catalog = _make_catalog()
        meta = _make_meta(df)
        out = tmp_path / "deck.pdf"
        build_deck(output_path=out, df=df, catalog_df=catalog, meta=meta)
        assert out.exists(), "Output PDF was not created"

    def test_file_has_minimum_size(self, tmp_path, monkeypatch):
        """The PDF must be larger than 2 000 bytes."""
        _patch_kaleido_ok(monkeypatch)
        _patch_no_term_stats(monkeypatch)
        df = _make_df()
        catalog = _make_catalog()
        meta = _make_meta(df)
        out = tmp_path / "deck.pdf"
        build_deck(output_path=out, df=df, catalog_df=catalog, meta=meta)
        assert out.stat().st_size > 2000, (
            f"PDF is suspiciously small: {out.stat().st_size} bytes"
        )

    def test_pdf_magic_bytes(self, tmp_path, monkeypatch):
        """The file must start with the PDF magic bytes ``%PDF-``."""
        _patch_kaleido_ok(monkeypatch)
        _patch_no_term_stats(monkeypatch)
        df = _make_df()
        catalog = _make_catalog()
        meta = _make_meta(df)
        out = tmp_path / "deck.pdf"
        build_deck(output_path=out, df=df, catalog_df=catalog, meta=meta)
        data = out.read_bytes()
        assert data[:5] == b"%PDF-", f"File does not start with %PDF-: {data[:8]!r}"

    def test_correct_page_count_without_term_stats(self, tmp_path, monkeypatch):
        """Without term stats, the deck must have exactly len(SLIDES) = 9 pages."""
        _patch_kaleido_ok(monkeypatch)
        _patch_no_term_stats(monkeypatch)
        df = _make_df()
        catalog = _make_catalog()
        meta = _make_meta(df)
        out = tmp_path / "deck.pdf"
        build_deck(output_path=out, df=df, catalog_df=catalog, meta=meta)
        data = out.read_bytes()
        n_pages = _count_pages(data)
        expected = len(SLIDES)
        assert n_pages == expected, (
            f"Expected {expected} pages (no term stats), heuristic counted {n_pages}."
        )

    def test_slide_count(self):
        """Sanity: one slide per external view — Cover, About, Overview, Geography,
        Institutions, Update Types, Volume, Scores, End = 9.
        (Urgency Basis and Category Structure were moved to the internal Cockpit;
        Drill-Down / Highlight Reel are per-record views, never in the deck.)"""
        assert len(SLIDES) == 9, f"Expected 9 slides, got {len(SLIDES)}"

    def test_slide_count_with_themes(self):
        """When term stats are present (no regulators), the _SLIDES_WITH_THEMES constant has 10 entries."""
        assert len(_SLIDES_WITH_THEMES) == 10, (
            f"Expected 10 slides with themes, got {len(_SLIDES_WITH_THEMES)}"
        )

    def test_compose_slides_base(self):
        """_compose_slides with no optional artifacts returns 9 slides (incl. the end slide)."""
        slides = _compose_slides(term_stats=None)
        assert len(slides) == 9, f"Expected 9 base slides, got {len(slides)}"

    def test_compose_slides_order_base(self):
        """Base slides are in the expected order (institutions before update_types,
        the closing slide last)."""
        from carver_showcase.deck import (
            _slide_cover, _slide_about, _slide_overview, _slide_geography,
            _slide_institutions, _slide_update_types, _slide_volume, _slide_scores,
            _slide_end,
        )
        slides = _compose_slides(term_stats=None)
        assert slides == [
            _slide_cover, _slide_about, _slide_overview, _slide_geography,
            _slide_institutions, _slide_update_types, _slide_volume, _slide_scores,
            _slide_end,
        ]


class TestBuildDeckWithTermStats:
    """Tests for the 9-slide path when term stats (enrichment) are available."""

    def test_correct_page_count_with_term_stats(self, tmp_path, monkeypatch):
        """With term stats present, the deck must have exactly 10 pages."""
        _patch_kaleido_ok(monkeypatch)
        _patch_term_stats_ok(monkeypatch)
        df = _make_df()
        catalog = _make_catalog()
        meta = _make_meta(df)
        out = tmp_path / "deck_with_themes.pdf"
        build_deck(output_path=out, df=df, catalog_df=catalog, meta=meta)
        data = out.read_bytes()
        n_pages = _count_pages(data)
        expected = len(_SLIDES_WITH_THEMES)
        assert n_pages == expected, (
            f"Expected {expected} pages (with term stats), heuristic counted {n_pages}."
        )

    def test_deck_builds_without_exception_with_term_stats(self, tmp_path, monkeypatch):
        """build_deck() must not raise when term stats are present."""
        _patch_kaleido_ok(monkeypatch)
        _patch_term_stats_ok(monkeypatch)
        df = _make_df()
        catalog = _make_catalog()
        meta = _make_meta(df)
        out = tmp_path / "deck_themes_no_exc.pdf"
        build_deck(output_path=out, df=df, catalog_df=catalog, meta=meta)
        assert out.exists(), "PDF was not written with term stats present"
        data = out.read_bytes()
        assert data[:5] == b"%PDF-"

    def test_deck_builds_without_exception_without_term_stats(self, tmp_path, monkeypatch):
        """build_deck() must not raise when term stats are absent (load returns None)."""
        _patch_kaleido_ok(monkeypatch)
        _patch_no_term_stats(monkeypatch)
        df = _make_df()
        catalog = _make_catalog()
        meta = _make_meta(df)
        out = tmp_path / "deck_no_themes_no_exc.pdf"
        build_deck(output_path=out, df=df, catalog_df=catalog, meta=meta)
        assert out.exists(), "PDF was not written without term stats"
        data = out.read_bytes()
        assert data[:5] == b"%PDF-"


class TestBuildDeckRenderFailureResilience:
    """Even if every chart render raises, build_deck must not raise and must
    produce a valid PDF with the right page count."""

    def test_deck_builds_when_render_raises(self, tmp_path, monkeypatch):
        """build_deck() must complete without raising when calc_fig_sync always raises."""

        def _raising_render(fig, opts=None):
            raise RuntimeError("Simulated kaleido failure")

        monkeypatch.setattr(deck_module.kaleido, "calc_fig_sync", _raising_render)
        monkeypatch.setattr(deck_module.kaleido, "start_sync_server", lambda **kw: None)
        monkeypatch.setattr(deck_module.kaleido, "stop_sync_server", lambda **kw: None)
        _patch_no_term_stats(monkeypatch)

        df = _make_df()
        catalog = _make_catalog()
        meta = _make_meta(df)
        out = tmp_path / "deck_fallback.pdf"

        # Must NOT raise
        build_deck(output_path=out, df=df, catalog_df=catalog, meta=meta)

        assert out.exists(), "PDF was not written even with render fallback"
        data = out.read_bytes()
        assert data[:5] == b"%PDF-"

        n_pages = _count_pages(data)
        expected = len(SLIDES)
        assert n_pages == expected, (
            f"Fallback deck has {n_pages} pages, expected {expected}"
        )


# ---------------------------------------------------------------------------
# Helpers for domain tests
# ---------------------------------------------------------------------------


def _make_catalog_with_domains() -> pd.DataFrame:
    """Catalog that already has top_level and sub_domain merged in."""
    base = _make_catalog()
    domains = {
        "t1": ("Finance", "Banking"),
        "t2": ("Finance", "Securities"),
        "t3": ("Finance", "Banking"),
        "t4": ("Insurance", "Life Insurance"),
        "t5": ("Finance", "Banking"),
        "t6": ("Insurance", "General Insurance"),
        "t7": ("Finance", "Securities"),
        "t8": ("Insurance", "Life Insurance"),
    }
    base["top_level"] = base["topic_id"].map(lambda t: domains.get(t, (None, None))[0])
    base["sub_domain"] = base["topic_id"].map(lambda t: domains.get(t, (None, None))[1])
    return base


class TestInstitutionDomainsSlide:
    """Tests for the _slide_institution_domains optional slide."""

    def test_compose_slides_domains_false_omits_slide(self):
        """has_domains=False (default) must NOT include _slide_institution_domains."""
        from carver_showcase.deck import _slide_institution_domains
        slides = _compose_slides(has_domains=False)
        assert _slide_institution_domains not in slides, (
            "Domain slide must be omitted when has_domains=False"
        )

    def test_compose_slides_domains_true_includes_slide(self):
        """has_domains=True must include _slide_institution_domains."""
        from carver_showcase.deck import _slide_institution_domains
        slides = _compose_slides(has_domains=True)
        assert _slide_institution_domains in slides, (
            "Domain slide must be present when has_domains=True"
        )

    def test_compose_slides_domains_after_institutions(self):
        """_slide_institution_domains must be immediately after _slide_institutions."""
        from carver_showcase.deck import _slide_institutions, _slide_institution_domains
        slides = _compose_slides(has_domains=True)
        inst_idx = slides.index(_slide_institutions)
        assert slides[inst_idx + 1] is _slide_institution_domains, (
            "Domain slide must immediately follow Institutions slide"
        )

    def test_compose_slides_count_with_domains_only(self):
        """has_domains=True adds exactly 1 slide to the base count."""
        base = _compose_slides(has_domains=False)
        with_domains = _compose_slides(has_domains=True)
        assert len(with_domains) == len(base) + 1, (
            f"Expected {len(base) + 1} slides with domains, got {len(with_domains)}"
        )

    def test_build_context_domain_breakdown_populated(self):
        """_build_context populates domain_breakdown when has_domains=True."""
        from carver_showcase.deck import _build_context
        df = _make_df()
        catalog = _make_catalog_with_domains()
        meta = _make_meta(df)
        ctx = _build_context(df, catalog, meta, has_domains=True)
        assert ctx["domain_breakdown"], "domain_breakdown must be non-empty when has_domains=True"
        assert ctx["n_domain_classified"] > 0, "n_domain_classified must be > 0"
        # domain_breakdown is a list of (top_level, count) tuples sorted descending
        counts = [count for _, count in ctx["domain_breakdown"]]
        assert counts == sorted(counts, reverse=True), (
            "domain_breakdown must be sorted by count descending"
        )

    def test_build_context_domain_breakdown_empty_when_no_domains(self):
        """_build_context returns empty domain_breakdown when has_domains=False."""
        from carver_showcase.deck import _build_context
        df = _make_df()
        catalog = _make_catalog()
        meta = _make_meta(df)
        ctx = _build_context(df, catalog, meta, has_domains=False)
        assert ctx["domain_breakdown"] == [], "domain_breakdown must be empty when has_domains=False"
        assert ctx["n_domain_classified"] == 0

    def test_slide_renders_without_exception(self, tmp_path, monkeypatch):
        """_slide_institution_domains must render without raising."""
        _patch_kaleido_ok(monkeypatch)
        _patch_no_term_stats(monkeypatch)

        # Patch load_topic_domains so build_deck merges real domain data
        catalog_with_domains = _make_catalog_with_domains()
        monkeypatch.setattr(deck_module, "load_topic_domains", lambda: pd.DataFrame(
            {
                "topic_id": ["t1", "t2", "t3", "t4", "t5", "t6", "t7", "t8"],
                "top_level": ["Finance", "Finance", "Finance", "Insurance",
                              "Finance", "Insurance", "Finance", "Insurance"],
                "sub_domain": ["Banking", "Securities", "Banking", "Life Insurance",
                               "Banking", "General Insurance", "Securities", "Life Insurance"],
            }
        ))

        df = _make_df()
        catalog = _make_catalog()
        meta = _make_meta(df)
        out = tmp_path / "deck_domains.pdf"
        build_deck(output_path=out, df=df, catalog_df=catalog, meta=meta)
        assert out.exists(), "PDF was not written with domain slide"
        data = out.read_bytes()
        assert data[:5] == b"%PDF-"

    def test_build_deck_no_domain_slide_when_csv_absent(self, tmp_path, monkeypatch):
        """When load_topic_domains returns empty DataFrame, domain slide is omitted."""
        _patch_kaleido_ok(monkeypatch)
        _patch_no_term_stats(monkeypatch)
        monkeypatch.setattr(deck_module, "load_topic_domains", lambda: pd.DataFrame())

        df = _make_df()
        catalog = _make_catalog()
        meta = _make_meta(df)
        out = tmp_path / "deck_no_domains.pdf"
        build_deck(output_path=out, df=df, catalog_df=catalog, meta=meta)
        data = out.read_bytes()
        n_pages = _count_pages(data)
        assert n_pages == len(SLIDES), (
            f"Expected {len(SLIDES)} pages (no domains), got {n_pages}"
        )
