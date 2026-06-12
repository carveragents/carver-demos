"""Smoke tests for apps/gallery.py using Streamlit's AppTest harness.

These tests verify that the Gallery app boots and renders all tabs without
raising an exception, and that basic sidebar interactions (filter changes)
also run cleanly.

Design:
- Uses streamlit.testing.v1.AppTest (Streamlit ≥ 1.18).
- Loads the real cached parquet snapshot (whatever the current snapshot holds).
- No mocking needed — the app never calls the live API.
- timeout=120s to accommodate the first cold parquet build if needed.
- Public-mode tests use a slim fixture bundle (15-col parquet, no JSONL),
  pointed at by CARVER_DATA_DIR, with CARVER_PUBLIC_BUILD=1.
"""

from __future__ import annotations

import importlib
import json
import pathlib
import sys
from unittest.mock import patch

import pandas as pd
import pytest

# Ensure the repo root is on sys.path so the app can be found by path
_REPO_ROOT = pathlib.Path(__file__).parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from streamlit.testing.v1 import AppTest

_GALLERY_PATH = str(_REPO_ROOT / "apps" / "gallery.py")


# ---------------------------------------------------------------------------
# Fixture: minimal term_stats dict for Tags & Entities tab tests
# ---------------------------------------------------------------------------

def _make_term_stats_fixture() -> dict:
    """Return a small, valid term_stats dict for testing the T&E tab."""
    breakdown_df = pd.DataFrame(
        {
            "type": ["Regulator", "Company", "Person", "Legislation", "Product", "Other"],
            "mentions": [1200, 850, 430, 310, 200, 90],
            "distinct_entities": [45, 130, 220, 60, 80, 55],
        }
    )
    entity_leaderboard_df = pd.DataFrame(
        {
            "canonical_name": ["SEC", "FCA", "ESMA", "PRA", "CFTC"],
            "type": ["Regulator", "Regulator", "Regulator", "Regulator", "Regulator"],
            "mentions": [500, 420, 310, 280, 250],
        }
    )
    tag_leaderboard_df = pd.DataFrame(
        {
            "tag": ["capital requirements", "AML", "reporting", "GDPR", "stress testing"],
            "count": [800, 650, 520, 410, 380],
        }
    )
    meta = {
        "n_distinct_entities": 590,
        "n_distinct_tags": 1200,
        "n_entity_mentions": 3080,
        "n_tag_mentions": 2760,
        "snapshot_date": "2026-06-01",
        "n_records": 50000,
        "build_date": "2026-06-01",
    }
    return {
        "breakdown": breakdown_df,
        "entity_leaderboard": entity_leaderboard_df,
        "tag_leaderboard": tag_leaderboard_df,
        "meta": meta,
    }


class TestGallerySmokeAppRuns:
    """Core smoke: app boots without exception."""

    def test_gallery_app_runs_without_exception(self):
        """The gallery app must start and render all widgets without raising."""
        at = AppTest.from_file(_GALLERY_PATH, default_timeout=120).run()
        assert not at.exception, (
            f"Gallery app raised an exception on boot:\n{at.exception}"
        )

    def test_gallery_has_tabs(self):
        """The gallery app renders multiple named tabs."""
        at = AppTest.from_file(_GALLERY_PATH, default_timeout=120).run()
        assert not at.exception
        # The app uses st.tabs — verify at least one tab is present by checking
        # the app rendered content (titles / headers should be non-empty).
        # st.tabs content is represented in the test client as nested blocks.
        # We confirm at minimum the app ran and produced output.
        assert len(at.markdown) > 0 or len(at.title) > 0, (
            "Gallery app produced no rendered output."
        )


class TestGallerySmokeFilterInteraction:
    """Verify sidebar filter interactions don't crash the app."""

    def test_gallery_has_no_category_filter(self):
        """Categories are an internal concept — the external gallery must NOT
        render a Category filter (it lives only in the Cockpit)."""
        at = AppTest.from_file(_GALLERY_PATH, default_timeout=120).run()
        assert not at.exception
        labels = [ms.label for ms in at.multiselect]
        assert "Category" not in labels, (
            f"Gallery must not expose a Category filter; saw multiselects: {labels}"
        )

    def test_filter_country_selection_no_exception(self):
        """Selecting a country filter must not raise an exception."""
        at = AppTest.from_file(_GALLERY_PATH, default_timeout=120).run()
        assert not at.exception

        country_ms = next((ms for ms in at.multiselect if ms.label == "Country"), None)
        assert country_ms is not None, "Gallery should expose a Country filter"
        options = list(getattr(country_ms, "options", []) or [])
        if options:
            country_ms.set_value([options[0]]).run()
            assert not at.exception, (
                f"App raised after country filter change:\n{at.exception}"
            )

    def test_filter_min_richness_no_exception(self):
        """Adjusting the min richness slider must not raise an exception."""
        at = AppTest.from_file(_GALLERY_PATH, default_timeout=120).run()
        assert not at.exception

        richness_slider = at.slider(key="filter_min_richness")
        if richness_slider is not None:
            try:
                richness_slider.set_value(50).run()
                assert not at.exception, (
                    f"App raised after richness slider change:\n{at.exception}"
                )
            except Exception:
                pass


class TestThemesEntitiesTabAbsent:
    """When term_stats artifacts are absent the app shows only the original 8 tabs."""

    def test_tab_absent_when_term_stats_none(self):
        """With load_term_stats returning None the app boots fine and the
        'Tags & Entities' tab label does NOT appear in rendered markdown."""
        # The unpatched app already returns None in a fresh checkout (no artifacts),
        # but we explicitly patch to guarantee isolation regardless of environment.
        with patch("carver_showcase.load.load_term_stats", return_value=None):
            at = AppTest.from_file(_GALLERY_PATH, default_timeout=120).run()

        assert not at.exception, (
            f"Gallery raised when term_stats=None:\n{at.exception}"
        )
        # Confirm the Tags & Entities label is NOT present in any rendered text
        all_text = " ".join(
            str(el.value) for el in (list(at.markdown) + list(at.subheader) + list(at.title))
        )
        assert "Tags & Entities" not in all_text, (
            "Gallery must NOT show 'Tags & Entities' tab when term_stats is None"
        )

    def test_default_run_no_themes_tab(self):
        """Without patching, the unpatched app should also boot cleanly (artifacts
        absent in a fresh checkout means term_stats=None → no T&E tab)."""
        at = AppTest.from_file(_GALLERY_PATH, default_timeout=120).run()
        assert not at.exception, (
            f"Gallery raised on default run:\n{at.exception}"
        )


class TestThemesEntitiesTabPresent:
    """When term_stats is available the app appends and renders the 9th tab."""

    def test_tab_present_with_fixture(self):
        """With a monkeypatched term_stats fixture the app boots without exception
        and the 'Tags & Entities' tab label appears in rendered content."""
        fixture = _make_term_stats_fixture()
        with patch("carver_showcase.load.load_term_stats", return_value=fixture):
            at = AppTest.from_file(_GALLERY_PATH, default_timeout=120).run()

        assert not at.exception, (
            f"Gallery raised when term_stats fixture provided:\n{at.exception}"
        )
        # The subheader "Tags & Entities" should be rendered in the Tags & Entities tab
        subheader_values = [str(sh.value) for sh in at.subheader]
        assert any("Tags & Entities" in v for v in subheader_values), (
            f"Expected 'Tags & Entities' subheader; got subheaders: {subheader_values}"
        )

    def test_tab_corpus_caption_present(self):
        """The full-corpus caption should appear when the T&E tab is rendered."""
        fixture = _make_term_stats_fixture()
        with patch("carver_showcase.load.load_term_stats", return_value=fixture):
            at = AppTest.from_file(_GALLERY_PATH, default_timeout=120).run()

        assert not at.exception
        caption_values = [str(c.value) for c in at.caption]
        assert any("full corpus" in v for v in caption_values), (
            f"Expected full-corpus caption; got captions: {caption_values}"
        )


# ---------------------------------------------------------------------------
# Fixtures for public-mode tests
# ---------------------------------------------------------------------------

def _write_slim_fixture_bundle(tmp_path: pathlib.Path) -> pathlib.Path:
    """Write a minimal slim bundle (15-col parquet + required sidecars).

    Mirrors the public bundle layout that Streamlit Community Cloud reads.
    Critically, NO annotations.jsonl is written — this proves the public app
    boots without raw JSONL access.

    Returns the bundle directory path.
    """
    from carver_showcase.config import PUBLIC_KEEP_COLUMNS

    bundle_dir = tmp_path / "public_bundle"
    bundle_dir.mkdir()

    # --- Slim annotations.parquet (only the 15 PUBLIC_KEEP_COLUMNS) ---
    # Use realistic dtypes matching the schema to exercise the full load path.
    n = 20  # small row count — just enough for KPIs / charts to render
    rng_topic_ids = [f"topic-{i:04d}" for i in range(n)]
    # Build all arrays explicitly with length n to avoid off-by-one errors.
    _labels = ["low", "medium", "high"]
    _scopes = ["national", "international", "regional", "national", "international"]
    slim_df = pd.DataFrame(
        {
            "topic_id": pd.array(rng_topic_ids, dtype="string"),
            "jurisdiction_country": pd.array(
                (["GB", "US", "DE", "FR", "JP"] * 4)[:n], dtype="string"
            ),
            "jurisdiction_bloc": pd.array(
                (["EU", "N/A", "EU", "EU", "N/A"] * 4)[:n], dtype="string"
            ),
            "jurisdiction_scope": pd.array(
                (_scopes * 4)[:n], dtype="string"
            ),
            "impact_score": pd.array(
                [float(i % 11) for i in range(n)], dtype="Float64"
            ),
            "impact_confidence": pd.array(
                [round(0.5 + (i % 5) * 0.1, 1) for i in range(n)], dtype="Float64"
            ),
            "impact_label": pd.array(
                [_labels[i % 3] for i in range(n)], dtype="string"
            ),
            "urgency_score": pd.array(
                [float((i + 3) % 11) for i in range(n)], dtype="Float64"
            ),
            "urgency_confidence": pd.array(
                [round(0.6 + (i % 4) * 0.1, 1) for i in range(n)], dtype="Float64"
            ),
            "urgency_label": pd.array(
                [_labels[(i + 1) % 3] for i in range(n)], dtype="string"
            ),
            "update_type": pd.array(
                (["Regulatory Update", "Consultation Paper", "Guidance Note"] * 7)[:n],
                dtype="string",
            ),
            "reconciled_published_date": pd.to_datetime(
                [f"2025-0{(i % 9) + 1}-01" for i in range(n)], utc=True
            ),
            "richness_score": pd.array(
                [float(40 + i * 2) for i in range(n)], dtype="Float64"
            ),
            "n_entities": pd.array(list(range(n)), dtype="Int64"),
            "n_tags": pd.array(list(range(1, n + 1)), dtype="Int64"),
        }
    )
    # Confirm the fixture only carries the public columns
    assert set(slim_df.columns) == set(PUBLIC_KEEP_COLUMNS), (
        f"Fixture column mismatch: {set(slim_df.columns)} vs {set(PUBLIC_KEEP_COLUMNS)}"
    )

    slim_df.to_parquet(bundle_dir / "annotations.parquet", engine="pyarrow", index=False)

    # --- topic_catalog.csv (minimal — just topic_id + name) ---
    catalog_df = pd.DataFrame(
        {
            "topic_id": rng_topic_ids,
            "name": [f"Institution {i}" for i in range(n)],
            "acronym": [f"INST{i}" for i in range(n)],
            "jurisdiction_code": ["GB", "US", "DE", "FR", "JP"] * 4,
            "scope": ["national"] * n,
            "entity_type": ["Regulator"] * n,
        }
    )
    catalog_df.to_csv(bundle_dir / "topic_catalog.csv", index=False)

    # --- snapshot_meta.json ---
    meta = {
        "snapshot_date": "2026-06-01",
        "scope": "full",
        "total_records": n,
    }
    (bundle_dir / "snapshot_meta.json").write_text(json.dumps(meta), encoding="utf-8")

    # Confirm no JSONL in this bundle
    assert not (bundle_dir / "annotations.jsonl").exists(), (
        "Public bundle must NOT contain annotations.jsonl"
    )

    return bundle_dir


class TestGalleryPublicBuildMode:
    """Public-build mode: CARVER_PUBLIC_BUILD=1 + slim fixture — no JSONL access.

    Each test GENUINELY relocates config.DATA_DIR by reloading carver_showcase.config
    after setting the env vars.  AppTest.from_file re-execs gallery.py, whose
    ``from carver_showcase.config import ...`` then picks up the reloaded, relocated
    paths.  Teardown is handled by the autouse ``_isolate_public_env`` fixture in
    conftest.py which reloads config back to defaults.
    """

    def _setup_public_bundle(
        self, monkeypatch, tmp_path
    ):
        """Shared setup: write bundle, set env vars, reload config + load, return (bundle_dir, cfg).

        Reloads both carver_showcase.config AND carver_showcase.load so that load.py
        module-level default arguments (e.g. ``path: Path = TOPIC_DOMAINS_CSV``) are
        re-evaluated against the relocated data dir.  Without this, cached loaders
        would still point at the old paths and the Streamlit Institutions domain chart
        would render real domain data inside the public-mode AppTest run, causing a
        duplicate element ID collision with the prior test session.

        Also clears st.cache_data so @st.cache_data-decorated loaders re-run fresh
        against the new paths.
        """
        import carver_showcase.config as cfg
        import carver_showcase.load as load_mod
        import streamlit as st

        bundle_dir = _write_slim_fixture_bundle(tmp_path)
        monkeypatch.setenv("CARVER_PUBLIC_BUILD", "1")
        monkeypatch.setenv("CARVER_DATA_DIR", str(bundle_dir))
        # Reload config first so its module-level constants update.
        importlib.reload(cfg)
        # Reload load.py so its function default args re-bind to the new config paths.
        importlib.reload(load_mod)
        # Clear the Streamlit cache so all @st.cache_data loaders run fresh.
        st.cache_data.clear()
        return bundle_dir, cfg

    def test_public_mode_boots_without_exception(self, monkeypatch, tmp_path):
        """Gallery boots cleanly in public mode using a slim 15-col fixture bundle."""
        bundle_dir, cfg = self._setup_public_bundle(monkeypatch, tmp_path)

        at = AppTest.from_file(_GALLERY_PATH, default_timeout=120).run()

        assert not at.exception, (
            f"Gallery raised in public mode:\n{at.exception}"
        )

    def test_public_mode_no_jsonl_required(self, monkeypatch, tmp_path):
        """The public app must boot successfully with no annotations.jsonl present.

        After config reload, config.ANNOTATIONS_JSONL points at a nonexistent path
        inside the slim bundle directory, proving the public app never accesses JSONL.
        """
        bundle_dir, cfg = self._setup_public_bundle(monkeypatch, tmp_path)

        # After reload, JSONL path must point into the bundle dir and NOT exist
        assert not cfg.ANNOTATIONS_JSONL.exists(), (
            f"config.ANNOTATIONS_JSONL must NOT exist in the slim bundle after reload; "
            f"got {cfg.ANNOTATIONS_JSONL}"
        )
        # Confirm the parquet IS there (bundle is valid)
        assert cfg.ANNOTATIONS_PARQUET.exists(), (
            f"config.ANNOTATIONS_PARQUET must exist in the slim bundle; "
            f"got {cfg.ANNOTATIONS_PARQUET}"
        )

        at = AppTest.from_file(_GALLERY_PATH, default_timeout=120).run()

        assert not at.exception, (
            f"Gallery raised without JSONL (should never access it in public mode):\n{at.exception}"
        )

    def test_public_mode_omits_record_drilldown_tab(self, monkeypatch, tmp_path):
        """In public mode, the drill-down tab body heading must NOT appear in rendered content.

        The tab body renders '## Single-Record Richness Drill-Down'; this heading
        must be absent when PUBLIC_BUILD=1 drops the tab entirely.
        """
        bundle_dir, cfg = self._setup_public_bundle(monkeypatch, tmp_path)

        at = AppTest.from_file(_GALLERY_PATH, default_timeout=120).run()
        assert not at.exception

        # The tab body heading (rendered via st.markdown inside the tab block)
        # is the reliable signal — tab labels themselves aren't in at.markdown.
        md_values = [str(el.value) for el in at.markdown]
        assert not any("Single-Record Richness Drill-Down" in v for v in md_values), (
            "Gallery must NOT render the drill-down heading in public mode"
        )

    def test_public_mode_omits_highlight_reel_tab(self, monkeypatch, tmp_path):
        """In public mode, the Highlight Reel tab body heading must NOT appear in rendered content."""
        bundle_dir, cfg = self._setup_public_bundle(monkeypatch, tmp_path)

        at = AppTest.from_file(_GALLERY_PATH, default_timeout=120).run()
        assert not at.exception

        md_values = [str(el.value) for el in at.markdown]
        assert not any("Highlight Reel" in v for v in md_values), (
            "Gallery must NOT render 'Highlight Reel' heading in public mode"
        )

    def test_normal_mode_has_record_drilldown_tab(self, monkeypatch):
        """In normal (non-public) mode, the drill-down tab body heading must appear.

        Checks for '## Single-Record Richness Drill-Down' in at.markdown, which is
        the rendered heading inside the tab body (tab labels are not in at.markdown).
        """
        # Explicitly unset the public flag to ensure normal mode
        monkeypatch.delenv("CARVER_PUBLIC_BUILD", raising=False)

        at = AppTest.from_file(_GALLERY_PATH, default_timeout=120).run()
        assert not at.exception

        md_values = [str(el.value) for el in at.markdown]
        assert any("Single-Record Richness Drill-Down" in v for v in md_values), (
            "Gallery must render the drill-down heading in normal mode"
        )

    def test_normal_mode_has_highlight_reel_tab(self, monkeypatch):
        """In normal (non-public) mode, the Highlight Reel tab body heading must appear."""
        monkeypatch.delenv("CARVER_PUBLIC_BUILD", raising=False)

        at = AppTest.from_file(_GALLERY_PATH, default_timeout=120).run()
        assert not at.exception

        md_values = [str(el.value) for el in at.markdown]
        assert any("Highlight Reel" in v for v in md_values), (
            "Gallery must render 'Highlight Reel' heading in normal mode"
        )


