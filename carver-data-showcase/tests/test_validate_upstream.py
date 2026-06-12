"""Tests for tools/validate_upstream.py — upstream reconciliation (Task 6).

No network calls.  All API data is injected directly into the pure check
functions or via monkeypatching the fetcher functions.

Covers:
  - check_institutions_match: equal → pass; off-by-one → HARD FAIL.
  - check_curation_invariant: holds → pass; broken → HARD FAIL.
  - check_records_vs_upstream: within tolerance → pass; beyond → WARN; None → SKIPPED.
  - check_records_vs_snapshot: match → pass; mismatch → SOFT FAIL; None → SKIPPED.
  - check_freshness: recent → pass; stale → WARN; None → SKIPPED.
  - check_referential: all present → pass; orphans → WARN; None → SKIPPED.
  - run_upstream_checks: all-None live inputs → only curation invariant is HARD;
    live ones SKIPPED; exit logic (0 when invariant holds, 1 when broken).
  - validate_upstream: monkeypatched read_api_key → None → local-only path → exit 0
    on a consistent local fixture.
  - validate_upstream: monkeypatched fetchers → canned topics → institutions
    match/mismatch HARD path (no network).
"""
from __future__ import annotations

import importlib
import json
import pathlib
import sys

import pandas as pd
import pytest

# ---------------------------------------------------------------------------
# Module import helpers
# ---------------------------------------------------------------------------

ROOT = pathlib.Path(__file__).parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _mod():
    return importlib.import_module("tools.validate_upstream")


# ---------------------------------------------------------------------------
# Fixture helpers
# ---------------------------------------------------------------------------

def _make_full_df(n: int = 100, *, include_noise: bool = True) -> pd.DataFrame:
    """Build a minimal full-corpus DataFrame with an update_type column.

    Half the rows (when include_noise=True) use the 'website error' denylist
    value so drop_noise_update_types will remove them.  The other half use
    'Regulatory Update' which is well above the frequency threshold.
    """
    rows = []
    for i in range(n):
        ut = "website error" if (include_noise and i % 2 == 0) else "Regulatory Update"
        rows.append({"topic_id": f"topic-{i:04d}", "update_type": ut})
    return pd.DataFrame(rows)


def _write_parquet(df: pd.DataFrame, path: pathlib.Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(path, index=False)


def _write_catalog(topic_ids: list[str], path: pathlib.Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    catalog = pd.DataFrame({"topic_id": topic_ids, "name": [f"Inst {t}" for t in topic_ids]})
    catalog.to_csv(path, index=False)


def _write_snapshot_meta(path: pathlib.Path, *, total_records: int, snapshot_date: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    meta = {
        "snapshot_date": snapshot_date,
        "pulled_at_utc": "2026-01-01T00:00:00+00:00",
        "scope": "full",
        "total_records": total_records,
        "source": "test",
    }
    path.write_text(json.dumps(meta), encoding="utf-8")


# ---------------------------------------------------------------------------
# check_institutions_match
# ---------------------------------------------------------------------------

class TestCheckInstitutionsMatch:
    def test_equal_passes(self):
        result = _mod().check_institutions_match(1071, 1071)
        assert result.ok is True
        assert result.level == "HARD"

    def test_off_by_one_fails(self):
        result = _mod().check_institutions_match(1071, 1072)
        assert result.ok is False
        assert result.level == "HARD"
        assert "1071" in result.detail
        assert "1072" in result.detail

    def test_off_by_one_other_direction_fails(self):
        result = _mod().check_institutions_match(1072, 1071)
        assert result.ok is False
        assert result.level == "HARD"

    def test_zero_equal_passes(self):
        result = _mod().check_institutions_match(0, 0)
        assert result.ok is True


# ---------------------------------------------------------------------------
# check_curation_invariant
# ---------------------------------------------------------------------------

class TestCheckCurationInvariant:
    def test_holds_passes(self):
        result = _mod().check_curation_invariant(100, 60, 40)
        assert result.ok is True
        assert result.level == "HARD"

    def test_broken_fails(self):
        # curated + noise = 99 != 100
        result = _mod().check_curation_invariant(100, 60, 39)
        assert result.ok is False
        assert result.level == "HARD"
        assert "60" in result.detail
        assert "39" in result.detail

    def test_all_curated_passes(self):
        result = _mod().check_curation_invariant(50, 50, 0)
        assert result.ok is True

    def test_all_noise_passes(self):
        result = _mod().check_curation_invariant(50, 0, 50)
        assert result.ok is True

    def test_overcounting_fails(self):
        # curated + noise = 101 != 100
        result = _mod().check_curation_invariant(100, 60, 41)
        assert result.ok is False


# ---------------------------------------------------------------------------
# check_records_vs_upstream
# ---------------------------------------------------------------------------

class TestCheckRecordsVsUpstream:
    def test_within_tolerance_passes(self):
        # 1% tolerance; 0.5% drift → pass
        result = _mod().check_records_vs_upstream(100_000, 100_499, tolerance=0.01)
        assert result.ok is True
        assert result.level == "SOFT"

    def test_at_tolerance_boundary_passes(self):
        # exactly 1% → pass (not strictly greater-than)
        result = _mod().check_records_vs_upstream(99_000, 100_000, tolerance=0.01)
        assert result.ok is True

    def test_beyond_tolerance_warns(self):
        # 2% drift > 1% tolerance → WARN (SOFT, ok=False)
        result = _mod().check_records_vs_upstream(98_000, 100_000, tolerance=0.01)
        assert result.ok is False
        assert result.level == "SOFT"
        assert "drift" in result.detail.lower()

    def test_none_upstream_skipped(self):
        result = _mod().check_records_vs_upstream(100_000, None)
        assert result.ok is True
        assert "SKIPPED" in result.detail

    def test_zero_upstream_skipped(self):
        result = _mod().check_records_vs_upstream(100_000, 0)
        assert result.ok is True
        assert "SKIPPED" in result.detail


# ---------------------------------------------------------------------------
# check_records_vs_snapshot
# ---------------------------------------------------------------------------

class TestCheckRecordsVsSnapshot:
    def test_match_passes(self):
        result = _mod().check_records_vs_snapshot(211489, 211489)
        assert result.ok is True
        assert result.level == "SOFT"

    def test_mismatch_fails(self):
        result = _mod().check_records_vs_snapshot(211000, 211489)
        assert result.ok is False
        assert result.level == "SOFT"
        # numbers are comma-formatted in the detail string
        assert "211,000" in result.detail or "211000" in result.detail
        assert "211,489" in result.detail or "211489" in result.detail

    def test_none_snapshot_skipped(self):
        result = _mod().check_records_vs_snapshot(100, None)
        assert result.ok is True
        assert "SKIPPED" in result.detail


# ---------------------------------------------------------------------------
# check_freshness
# ---------------------------------------------------------------------------

class TestCheckFreshness:
    def test_recent_passes(self):
        # snapshot 2026-01-10, newest 2026-01-08 → 2 days old → pass (max=7)
        result = _mod().check_freshness("2026-01-08T12:00:00Z", "2026-01-10", max_age_days=7)
        assert result.ok is True
        assert result.level == "SOFT"

    def test_same_day_passes(self):
        result = _mod().check_freshness("2026-01-10T00:00:00Z", "2026-01-10", max_age_days=7)
        assert result.ok is True

    def test_stale_warns(self):
        # snapshot 2026-01-20, newest 2026-01-01 → 19 days old → WARN
        result = _mod().check_freshness("2026-01-01T12:00:00Z", "2026-01-20", max_age_days=7)
        assert result.ok is False
        assert result.level == "SOFT"
        assert "19d" in result.detail

    def test_exactly_at_limit_passes(self):
        # exactly max_age_days → pass (not strictly greater)
        result = _mod().check_freshness("2026-01-03T00:00:00.000Z", "2026-01-10", max_age_days=7)
        assert result.ok is True

    def test_none_created_at_skipped(self):
        result = _mod().check_freshness(None, "2026-01-10")
        assert result.ok is True
        assert "SKIPPED" in result.detail

    def test_bad_snapshot_date_skipped(self):
        result = _mod().check_freshness("2026-01-08T12:00:00Z", "not-a-date")
        assert result.ok is True
        assert "SKIPPED" in result.detail

    def test_bad_created_at_skipped(self):
        result = _mod().check_freshness("not-a-timestamp", "2026-01-10")
        assert result.ok is True
        assert "SKIPPED" in result.detail

    def test_fractional_seconds_z_suffix(self):
        # The API returns ISO 8601 with fractional seconds and Z
        result = _mod().check_freshness("2026-01-08T10:23:45.123Z", "2026-01-10", max_age_days=7)
        assert result.ok is True


# ---------------------------------------------------------------------------
# check_referential
# ---------------------------------------------------------------------------

class TestCheckReferential:
    def test_all_present_passes(self):
        catalog_ids = {"t1", "t2", "t3"}
        upstream_ids = {"t1", "t2", "t3", "t4"}
        result = _mod().check_referential(catalog_ids, upstream_ids)
        assert result.ok is True
        assert result.level == "SOFT"

    def test_exact_match_passes(self):
        ids = {"t1", "t2"}
        result = _mod().check_referential(ids, ids)
        assert result.ok is True

    def test_orphans_warns(self):
        catalog_ids = {"t1", "t2", "t-orphan"}
        upstream_ids = {"t1", "t2", "t3"}
        result = _mod().check_referential(catalog_ids, upstream_ids)
        assert result.ok is False
        assert result.level == "SOFT"
        assert "t-orphan" in result.detail

    def test_none_upstream_skipped(self):
        result = _mod().check_referential({"t1"}, None)
        assert result.ok is True
        assert "SKIPPED" in result.detail

    def test_empty_catalog_passes(self):
        result = _mod().check_referential(set(), {"t1", "t2"})
        assert result.ok is True


# ---------------------------------------------------------------------------
# run_upstream_checks — all-None live inputs (no-key path)
# ---------------------------------------------------------------------------

class TestRunUpstreamChecksNoKey:
    """When all live inputs are None, live checks skip; curation invariant runs."""

    def _run(self, *, full=100, curated=60, noise=40):
        return _mod().run_upstream_checks(
            catalog_rows=1071,
            topics_count_or_none=None,
            full_rows=full,
            curated_rows=curated,
            noise_rows=noise,
            upstream_total=None,
            snapshot_count=None,
            newest_created_at=None,
            snapshot_date="2026-01-01",
            catalog_topic_ids={"t1", "t2"},
            topics_ids_or_none=None,
        )

    def test_invariant_passes_overall_exit_zero(self):
        results = self._run(full=100, curated=60, noise=40)
        # curation_invariant must HARD-pass
        inv = next(r for r in results if r.name == "curation_invariant")
        assert inv.ok is True
        # No HARD failure that actually ran → exit 0 logic
        hard_failed = any(
            r.level == "HARD" and not r.ok and "SKIPPED" not in r.detail
            for r in results
        )
        assert not hard_failed

    def test_invariant_broken_exit_one(self):
        results = self._run(full=100, curated=60, noise=39)  # 99 != 100
        inv = next(r for r in results if r.name == "curation_invariant")
        assert inv.ok is False
        hard_failed = any(
            r.level == "HARD" and not r.ok and "SKIPPED" not in r.detail
            for r in results
        )
        assert hard_failed

    def test_institutions_match_skipped(self):
        results = self._run()
        inst = next(r for r in results if r.name == "institutions_match")
        assert inst.ok is True
        assert "SKIPPED" in inst.detail

    def test_all_live_checks_skipped(self):
        results = self._run()
        live_checks = {"institutions_match", "records_vs_upstream", "freshness", "referential"}
        for r in results:
            if r.name in live_checks:
                assert "SKIPPED" in r.detail, f"{r.name} should be SKIPPED but detail={r.detail!r}"

    def test_records_vs_snapshot_skipped_when_none(self):
        results = self._run()
        snap = next(r for r in results if r.name == "records_vs_snapshot")
        assert "SKIPPED" in snap.detail


# ---------------------------------------------------------------------------
# run_upstream_checks — with live inputs (key-present path)
# ---------------------------------------------------------------------------

class TestRunUpstreamChecksWithKey:
    """Canned live inputs to exercise the key-present HARD path."""

    def _run(
        self,
        *,
        catalog_rows=5,
        topics_count=5,
        full=100,
        curated=60,
        noise=40,
        upstream_total=None,
        snapshot_count=None,
        newest_created_at=None,
        snapshot_date="2026-01-10",
        catalog_ids=None,
        topics_ids=None,
    ):
        if catalog_ids is None:
            catalog_ids = {f"t{i}" for i in range(catalog_rows)}
        if topics_ids is None:
            topics_ids = {f"t{i}" for i in range(topics_count)}
        return _mod().run_upstream_checks(
            catalog_rows=catalog_rows,
            topics_count_or_none=topics_count,
            full_rows=full,
            curated_rows=curated,
            noise_rows=noise,
            upstream_total=upstream_total,
            snapshot_count=snapshot_count,
            newest_created_at=newest_created_at,
            snapshot_date=snapshot_date,
            catalog_topic_ids=catalog_ids,
            topics_ids_or_none=topics_ids,
        )

    def test_institutions_match_passes(self):
        results = self._run(catalog_rows=5, topics_count=5)
        inst = next(r for r in results if r.name == "institutions_match")
        assert inst.ok is True
        assert inst.level == "HARD"
        assert "SKIPPED" not in inst.detail

    def test_institutions_mismatch_hard_fail(self):
        results = self._run(catalog_rows=5, topics_count=6)
        inst = next(r for r in results if r.name == "institutions_match")
        assert inst.ok is False
        assert inst.level == "HARD"

    def test_all_pass_no_hard_failure(self):
        results = self._run(
            catalog_rows=5,
            topics_count=5,
            full=100,
            curated=60,
            noise=40,
            upstream_total=None,
            snapshot_count=100,
            newest_created_at="2026-01-09T00:00:00Z",
            snapshot_date="2026-01-10",
        )
        hard_failed = any(
            r.level == "HARD" and not r.ok and "SKIPPED" not in r.detail
            for r in results
        )
        assert not hard_failed

    def test_curation_invariant_hard_fail_overrides(self):
        # Even with all live checks passing, a broken invariant → HARD FAIL
        results = self._run(
            catalog_rows=5,
            topics_count=5,
            full=100,
            curated=60,
            noise=39,  # 99 != 100
        )
        hard_failed = any(
            r.level == "HARD" and not r.ok and "SKIPPED" not in r.detail
            for r in results
        )
        assert hard_failed


# ---------------------------------------------------------------------------
# validate_upstream — no-key monkeypatch path with local fixture
# ---------------------------------------------------------------------------

class TestValidateUpstreamNoKey:
    """validate_upstream with no API key → local-only path → exit 0 on consistent fixture."""

    def _make_fixture(self, tmp_path: pathlib.Path, *, n: int = 100) -> dict[str, pathlib.Path]:
        """Write a consistent local fixture (parquet + catalog + snapshot_meta)."""
        df = _make_full_df(n, include_noise=True)
        parquet_path = tmp_path / "annotations.parquet"
        catalog_path = tmp_path / "topic_catalog.csv"
        meta_path = tmp_path / "snapshot_meta.json"

        _write_parquet(df, parquet_path)
        # Catalog has the same topic_ids as the parquet
        topic_ids = list(df["topic_id"].unique())
        _write_catalog(topic_ids, catalog_path)
        _write_snapshot_meta(meta_path, total_records=n, snapshot_date="2026-01-10")

        return {
            "parquet": parquet_path,
            "catalog": catalog_path,
            "meta": meta_path,
        }

    def test_no_key_exits_zero_on_consistent_fixture(
        self, tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
    ):
        mod = _mod()
        paths = self._make_fixture(tmp_path)
        monkeypatch.setattr(mod, "read_api_key", lambda: None)

        exit_code = mod.validate_upstream(
            annotations_parquet=paths["parquet"],
            topic_catalog_csv=paths["catalog"],
            snapshot_meta_json=paths["meta"],
        )
        assert exit_code == 0

    def test_no_key_exits_zero_even_with_soft_mismatch(
        self, tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
    ):
        """Snapshot meta total != parquet rows → SOFT warn, still exit 0."""
        mod = _mod()
        df = _make_full_df(100, include_noise=True)
        parquet_path = tmp_path / "annotations.parquet"
        catalog_path = tmp_path / "topic_catalog.csv"
        meta_path = tmp_path / "snapshot_meta.json"
        _write_parquet(df, parquet_path)
        _write_catalog(list(df["topic_id"].unique()), catalog_path)
        # Deliberately wrong total_records
        _write_snapshot_meta(meta_path, total_records=99999, snapshot_date="2026-01-10")

        monkeypatch.setattr(mod, "read_api_key", lambda: None)

        exit_code = mod.validate_upstream(
            annotations_parquet=parquet_path,
            topic_catalog_csv=catalog_path,
            snapshot_meta_json=meta_path,
        )
        # SOFT failure → exit 0
        assert exit_code == 0

    def test_missing_parquet_exits_one(
        self, tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
    ):
        mod = _mod()
        monkeypatch.setattr(mod, "read_api_key", lambda: None)

        exit_code = mod.validate_upstream(
            annotations_parquet=tmp_path / "missing.parquet",
            topic_catalog_csv=tmp_path / "catalog.csv",
            snapshot_meta_json=tmp_path / "meta.json",
        )
        assert exit_code == 1


# ---------------------------------------------------------------------------
# validate_upstream — monkeypatched fetchers (key-present path, no network)
# ---------------------------------------------------------------------------

class TestValidateUpstreamWithCannedFetchers:
    """Monkeypatch fetch_topics + fetch_annotations_meta to exercise key-present path."""

    _N = 100  # fixture size

    def _make_fixture(self, tmp_path: pathlib.Path) -> dict[str, pathlib.Path]:
        df = _make_full_df(self._N, include_noise=True)
        parquet_path = tmp_path / "annotations.parquet"
        catalog_path = tmp_path / "topic_catalog.csv"
        meta_path = tmp_path / "snapshot_meta.json"
        _write_parquet(df, parquet_path)
        topic_ids = list(df["topic_id"].unique())
        _write_catalog(topic_ids, catalog_path)
        # total_records matches parquet rows
        _write_snapshot_meta(meta_path, total_records=self._N, snapshot_date="2026-01-10")
        return {
            "parquet": parquet_path,
            "catalog": catalog_path,
            "meta": meta_path,
            "topic_ids": topic_ids,
        }

    def test_matching_topics_exits_zero(
        self, tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
    ):
        mod = _mod()
        paths = self._make_fixture(tmp_path)

        # Canned topics list — same length as catalog (matches)
        canned_topics = [{"id": tid} for tid in paths["topic_ids"]]
        monkeypatch.setattr(mod, "read_api_key", lambda: "fake-key")
        monkeypatch.setattr(mod, "fetch_topics", lambda base, key: canned_topics)
        monkeypatch.setattr(
            mod, "fetch_annotations_meta",
            lambda base, key: {"upstream_total": None, "newest_created_at": "2026-01-09T12:00:00Z"},
        )

        exit_code = mod.validate_upstream(
            annotations_parquet=paths["parquet"],
            topic_catalog_csv=paths["catalog"],
            snapshot_meta_json=paths["meta"],
        )
        assert exit_code == 0

    def test_mismatched_topics_exits_one(
        self, tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
    ):
        mod = _mod()
        paths = self._make_fixture(tmp_path)

        # Canned topics list — one MORE than catalog → institutions_match HARD FAIL
        canned_topics = [{"id": tid} for tid in paths["topic_ids"]] + [{"id": "extra-topic"}]
        monkeypatch.setattr(mod, "read_api_key", lambda: "fake-key")
        monkeypatch.setattr(mod, "fetch_topics", lambda base, key: canned_topics)
        monkeypatch.setattr(
            mod, "fetch_annotations_meta",
            lambda base, key: {"upstream_total": None, "newest_created_at": None},
        )

        exit_code = mod.validate_upstream(
            annotations_parquet=paths["parquet"],
            topic_catalog_csv=paths["catalog"],
            snapshot_meta_json=paths["meta"],
        )
        assert exit_code == 1

    def test_fetch_topics_failure_skips_gracefully(
        self, tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
    ):
        """If fetch_topics raises, institutions_match is SKIPPED (not FAIL)."""
        mod = _mod()
        paths = self._make_fixture(tmp_path)

        def _raise(*args, **kwargs):
            raise RuntimeError("network error")

        monkeypatch.setattr(mod, "read_api_key", lambda: "fake-key")
        monkeypatch.setattr(mod, "fetch_topics", _raise)
        monkeypatch.setattr(
            mod, "fetch_annotations_meta",
            lambda base, key: {"upstream_total": None, "newest_created_at": None},
        )

        exit_code = mod.validate_upstream(
            annotations_parquet=paths["parquet"],
            topic_catalog_csv=paths["catalog"],
            snapshot_meta_json=paths["meta"],
        )
        # fetch failure → SKIPPED → not a HARD failure → exit 0
        assert exit_code == 0

    def test_upstream_total_warn_does_not_change_exit_code(
        self, tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
    ):
        """A SOFT warning on records_vs_upstream must NOT cause exit 1."""
        mod = _mod()
        paths = self._make_fixture(tmp_path)
        canned_topics = [{"id": tid} for tid in paths["topic_ids"]]
        monkeypatch.setattr(mod, "read_api_key", lambda: "fake-key")
        monkeypatch.setattr(mod, "fetch_topics", lambda base, key: canned_topics)
        # upstream_total wildly different → SOFT WARN
        monkeypatch.setattr(
            mod, "fetch_annotations_meta",
            lambda base, key: {
                "upstream_total": self._N * 10,  # 900% drift
                "newest_created_at": "2026-01-09T00:00:00Z",
            },
        )

        exit_code = mod.validate_upstream(
            annotations_parquet=paths["parquet"],
            topic_catalog_csv=paths["catalog"],
            snapshot_meta_json=paths["meta"],
        )
        # SOFT warn only → exit 0
        assert exit_code == 0
