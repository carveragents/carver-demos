"""Offline bundle gate — validates data/public/ before publish.

Loads the slim public bundle (annotations.parquet, topic_catalog.csv,
snapshot_meta.json, deck PDF) and runs a set of HARD and SOFT checks.
Exits non-zero on any HARD failure so the weekly ``validate && git commit``
gate blocks bad or leaky data.

No API key required — pure offline computation.

Run:
    .venv/bin/python tools/validate_bundle.py
    .venv/bin/python tools/validate_bundle.py --bundle-dir data/public
"""
from __future__ import annotations

import argparse
import datetime
import json
import os
import pathlib
import sys
from dataclasses import dataclass
from typing import Optional

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

import pandas as pd

from carver_showcase.config import (
    DATA_DIR,
    PLAUSIBLE_DATE_WINDOW,
    PUBLIC_CONTENT_DENYLIST,
    PUBLIC_DECK_MIN_BYTES,
    PUBLIC_KEEP_COLUMNS,
    PUBLIC_ORPHAN_TOPIC_TOLERANCE,
    PUBLIC_ROWCOUNT_DROP_TOLERANCE,
    PUBLIC_STRING_MAXLEN,
)

# ---------------------------------------------------------------------------
# Result type
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class CheckResult:
    """Outcome of a single validation check."""
    name: str
    level: str   # "HARD" or "SOFT"
    ok: bool
    detail: str


# ---------------------------------------------------------------------------
# HARD checks — pure functions over already-loaded data
# ---------------------------------------------------------------------------

def check_no_extra_columns(df: pd.DataFrame) -> CheckResult:
    """Columns in df must be a subset of PUBLIC_KEEP_COLUMNS.

    Catches any content column that slipped into the slim frame.
    """
    allowed = set(PUBLIC_KEEP_COLUMNS)
    extra = sorted(set(df.columns) - allowed)
    if extra:
        return CheckResult(
            name="no_extra_columns",
            level="HARD",
            ok=False,
            detail=f"Extra columns not in PUBLIC_KEEP_COLUMNS: {extra}",
        )
    return CheckResult(name="no_extra_columns", level="HARD", ok=True, detail="")


def check_no_denylist_columns(df: pd.DataFrame) -> CheckResult:
    """No column in df may appear in PUBLIC_CONTENT_DENYLIST.

    Belt-and-suspenders leak gate in addition to the allowlist check.
    """
    leaked = sorted(set(df.columns) & PUBLIC_CONTENT_DENYLIST)
    if leaked:
        return CheckResult(
            name="no_denylist_columns",
            level="HARD",
            ok=False,
            detail=f"Denylist (content) columns present: {leaked}",
        )
    return CheckResult(name="no_denylist_columns", level="HARD", ok=True, detail="")


def check_string_lengths(df: pd.DataFrame) -> CheckResult:
    """Every string/object column must have max(str-len) < PUBLIC_STRING_MAXLEN.

    A rich-text column that slipped in would be caught here — content prose
    (title, summary) is far longer than the 64-byte ceiling.
    """
    offenders: list[str] = []
    for col in df.columns:
        dtype_s = str(df[col].dtype).lower()
        is_string_like = df[col].dtype == object or "string" in dtype_s or dtype_s == "str"
        if is_string_like:
            try:
                max_len = df[col].dropna().astype(str).str.len().max()
            except Exception:
                continue
            if pd.notna(max_len) and max_len >= PUBLIC_STRING_MAXLEN:
                offenders.append(f"{col} (max_len={int(max_len)})")
    if offenders:
        return CheckResult(
            name="string_lengths",
            level="HARD",
            ok=False,
            detail=f"String columns exceed PUBLIC_STRING_MAXLEN={PUBLIC_STRING_MAXLEN}: {offenders}",
        )
    return CheckResult(name="string_lengths", level="HARD", ok=True, detail="")


def check_schema_present(df: pd.DataFrame) -> CheckResult:
    """Every PUBLIC_KEEP_COLUMNS column must be present in the slim bundle.

    A bundle produced with a stale exporter that dropped a required column
    should be caught here before the public app tries to use it.
    """
    missing = [col for col in PUBLIC_KEEP_COLUMNS if col not in df.columns]
    if missing:
        return CheckResult(
            name="schema_present",
            level="HARD",
            ok=False,
            detail=f"Required PUBLIC_KEEP_COLUMNS missing from parquet: {missing}",
        )
    return CheckResult(name="schema_present", level="HARD", ok=True, detail="")


def check_not_empty(df: pd.DataFrame) -> CheckResult:
    """The slim frame must have at least one row."""
    if len(df) == 0:
        return CheckResult(
            name="not_empty",
            level="HARD",
            ok=False,
            detail="annotations.parquet has zero rows",
        )
    return CheckResult(name="not_empty", level="HARD", ok=True, detail="")


def check_no_null_columns(df: pd.DataFrame) -> CheckResult:
    """No PUBLIC_KEEP_COLUMNS column may be 100% null.

    A fully-null keep column indicates an upstream export bug or a naming
    mismatch; either way the column is useless and the bundle is incomplete.
    """
    # Only inspect columns that are present (schema_present check handles absent ones)
    offenders = [
        col for col in PUBLIC_KEEP_COLUMNS
        if col in df.columns and df[col].isna().all()
    ]
    if offenders:
        return CheckResult(
            name="no_null_columns",
            level="HARD",
            ok=False,
            detail=f"KEEP columns are 100% null: {offenders}",
        )
    return CheckResult(name="no_null_columns", level="HARD", ok=True, detail="")


def check_rowcount_vs_baseline(
    df: pd.DataFrame, baseline: Optional[dict]
) -> CheckResult:
    """Row count must not collapse vs the baseline.

    A drop of more than PUBLIC_ROWCOUNT_DROP_TOLERANCE (20%) relative to the
    previous passing run fails hard.  If no baseline exists (first run), the
    check passes unconditionally.
    """
    if baseline is None or "rows" not in baseline:
        return CheckResult(
            name="rowcount_vs_baseline",
            level="HARD",
            ok=True,
            detail="no baseline — first run, skip",
        )
    baseline_rows: int = baseline["rows"]
    current_rows: int = len(df)
    if baseline_rows == 0:
        return CheckResult(
            name="rowcount_vs_baseline",
            level="HARD",
            ok=True,
            detail="baseline rows=0 — skip division",
        )
    drop_frac = (baseline_rows - current_rows) / baseline_rows
    if drop_frac > PUBLIC_ROWCOUNT_DROP_TOLERANCE:
        return CheckResult(
            name="rowcount_vs_baseline",
            level="HARD",
            ok=False,
            detail=(
                f"Row count dropped {drop_frac:.1%} "
                f"(baseline={baseline_rows:,}, now={current_rows:,}); "
                f"tolerance={PUBLIC_ROWCOUNT_DROP_TOLERANCE:.0%}"
            ),
        )
    return CheckResult(
        name="rowcount_vs_baseline",
        level="HARD",
        ok=True,
        detail=f"rows={current_rows:,} (baseline={baseline_rows:,}, drop={drop_frac:.1%})",
    )


def check_snapshot_advanced(
    snapshot_meta: dict, baseline: Optional[dict]
) -> CheckResult:
    """Snapshot date must not regress vs the baseline snapshot date.

    HARD failure only on strict regression (new < old).  Equal dates produce a
    SOFT-style warning embedded as ok=True with a detail note (the snapshot may
    not have advanced because the pipeline ran twice in one day — not a blocker).
    If no baseline or either date is absent, the check passes.
    """
    if baseline is None or "snapshot_date" not in baseline:
        return CheckResult(
            name="snapshot_advanced",
            level="HARD",
            ok=True,
            detail="no baseline — first run, skip",
        )
    try:
        current_date = datetime.date.fromisoformat(snapshot_meta.get("snapshot_date", ""))
        baseline_date = datetime.date.fromisoformat(baseline["snapshot_date"])
    except (ValueError, TypeError):
        return CheckResult(
            name="snapshot_advanced",
            level="HARD",
            ok=True,
            detail="snapshot_date unparseable — skip comparison",
        )
    if current_date < baseline_date:
        return CheckResult(
            name="snapshot_advanced",
            level="HARD",
            ok=False,
            detail=(
                f"Snapshot date regressed: current={current_date} < baseline={baseline_date}"
            ),
        )
    if current_date == baseline_date:
        return CheckResult(
            name="snapshot_advanced",
            level="HARD",
            ok=True,  # not a hard blocker — SOFT-style note
            detail=f"snapshot_date unchanged: {current_date} (same as baseline — not a HARD failure)",
        )
    return CheckResult(
        name="snapshot_advanced",
        level="HARD",
        ok=True,
        detail=f"snapshot_date advanced: {baseline_date} → {current_date}",
    )


def check_topic_ids_in_catalog(
    df: pd.DataFrame,
    catalog_df: pd.DataFrame,
    tolerance: float = PUBLIC_ORPHAN_TOPIC_TOLERANCE,
) -> CheckResult:
    """Orphan topic_ids fail HARD only when their share exceeds the tolerance.

    The live feed adds institutions continuously, so a catalog that lags the
    annotation pull will routinely orphan a few topic_ids.  The gallery renders
    missing catalog names gracefully.  HARD-fail only when the orphan share of
    DISTINCT topic_ids exceeds ``tolerance`` (default: PUBLIC_ORPHAN_TOPIC_TOLERANCE).
    The orphan count and share are always included in the detail string so they
    are visible in the report even when passing.
    """
    if "topic_id" not in df.columns or "topic_id" not in catalog_df.columns:
        return CheckResult(
            name="topic_ids_in_catalog",
            level="HARD",
            ok=True,
            detail="topic_id missing from df or catalog — skip",
        )
    annotation_ids: set = set(df["topic_id"].dropna().unique())
    catalog_ids: set = set(catalog_df["topic_id"].dropna().unique())
    orphans = sorted(annotation_ids - catalog_ids)
    n_total = len(annotation_ids)
    n_orphans = len(orphans)
    orphan_share = n_orphans / n_total if n_total > 0 else 0.0
    sample = orphans[:5]
    sample_str = f"{sample}{' ...' if n_orphans > 5 else ''}" if orphans else "none"
    detail = (
        f"{n_orphans} orphan topic_id(s) / {n_total} distinct "
        f"({orphan_share:.2%}); sample={sample_str}; tolerance={tolerance:.2%}"
    )
    if orphan_share > tolerance:
        return CheckResult(
            name="topic_ids_in_catalog",
            level="HARD",
            ok=False,
            detail=detail,
        )
    return CheckResult(
        name="topic_ids_in_catalog",
        level="HARD",
        ok=True,
        detail=detail,
    )


def check_deck_pdf(path: pathlib.Path) -> CheckResult:
    """Deck PDF must exist, start with the %PDF- magic bytes, and be > 20 KB.

    Dep-free: we read only the first 5 bytes and the file size — no page
    parsing.  A zero-byte placeholder or a non-PDF file (e.g. an accidental
    text write) would be caught here.
    """
    path = pathlib.Path(path)
    if not path.exists():
        return CheckResult(
            name="deck_pdf",
            level="HARD",
            ok=False,
            detail=f"Deck PDF not found: {path}",
        )
    size = path.stat().st_size
    try:
        with open(path, "rb") as fh:
            magic = fh.read(5)
    except OSError as exc:
        return CheckResult(
            name="deck_pdf",
            level="HARD",
            ok=False,
            detail=f"Cannot read deck PDF: {exc}",
        )
    if magic != b"%PDF-":
        return CheckResult(
            name="deck_pdf",
            level="HARD",
            ok=False,
            detail=f"Deck PDF does not start with %PDF- magic bytes (got {magic!r}): {path}",
        )
    min_size = PUBLIC_DECK_MIN_BYTES
    if size <= min_size:
        return CheckResult(
            name="deck_pdf",
            level="HARD",
            ok=False,
            detail=f"Deck PDF is too small: {size} bytes (minimum {min_size}): {path}",
        )
    return CheckResult(
        name="deck_pdf",
        level="HARD",
        ok=True,
        detail=f"PDF ok: {size:,} bytes",
    )


def check_sidecars_present(bundle_dir: pathlib.Path) -> CheckResult:
    """Required sidecar files must exist in the bundle directory.

    Minimum required: topic_catalog.csv, snapshot_meta.json.
    All other public sidecars are checked as well; missing ones are listed in
    the detail but only the two required files produce a HARD failure.
    """
    bundle_dir = pathlib.Path(bundle_dir)
    required = ["topic_catalog.csv", "snapshot_meta.json"]
    optional = [
        "topic_domains.csv",
        "entity_leaderboard.csv",
        "tag_leaderboard.csv",
        "entity_type_breakdown.csv",
        "term_stats_meta.json",
    ]
    missing_required = [f for f in required if not (bundle_dir / f).exists()]
    missing_optional = [f for f in optional if not (bundle_dir / f).exists()]

    if missing_required:
        detail_parts = [f"REQUIRED missing: {missing_required}"]
        if missing_optional:
            detail_parts.append(f"optional missing: {missing_optional}")
        return CheckResult(
            name="sidecars_present",
            level="HARD",
            ok=False,
            detail="; ".join(detail_parts),
        )
    detail = "required sidecars present"
    if missing_optional:
        detail += f"; optional missing: {missing_optional}"
    return CheckResult(name="sidecars_present", level="HARD", ok=True, detail=detail)


# ---------------------------------------------------------------------------
# SOFT checks — drift vs baseline
# ---------------------------------------------------------------------------

_SOFT_DRIFT_TOLERANCE: float = 0.15  # 15% relative drift before a SOFT warning


def _relative_drift(current: float, baseline_val: float) -> float:
    """Return |current - baseline_val| / |baseline_val|, or 0.0 if baseline is 0."""
    if baseline_val == 0:
        return 0.0
    return abs(current - baseline_val) / abs(baseline_val)


def check_distinct_counts_drift(
    df: pd.DataFrame, baseline: Optional[dict]
) -> list[CheckResult]:
    """Distinct-count drift for institutions, countries, and update_types."""
    results: list[CheckResult] = []
    if baseline is None:
        results.append(CheckResult(
            name="distinct_counts_drift",
            level="SOFT",
            ok=True,
            detail="no baseline — skip",
        ))
        return results

    metrics = {
        "institutions": ("topic_id", "distinct_institutions"),
        "countries": ("jurisdiction_country", "distinct_countries"),
        "update_types": ("update_type", "distinct_update_types"),
    }
    for label, (col, baseline_key) in metrics.items():
        if col not in df.columns or baseline_key not in baseline:
            results.append(CheckResult(
                name=f"distinct_{label}_drift",
                level="SOFT",
                ok=True,
                detail=f"column '{col}' or baseline key '{baseline_key}' absent — skip",
            ))
            continue
        current_val = int(df[col].nunique())
        baseline_val = float(baseline[baseline_key])
        drift = _relative_drift(current_val, baseline_val)
        if drift > _SOFT_DRIFT_TOLERANCE:
            results.append(CheckResult(
                name=f"distinct_{label}_drift",
                level="SOFT",
                ok=False,
                detail=(
                    f"distinct {label} drifted {drift:.1%} "
                    f"(baseline={baseline_val:.0f}, now={current_val}); "
                    f"tolerance={_SOFT_DRIFT_TOLERANCE:.0%}"
                ),
            ))
        else:
            results.append(CheckResult(
                name=f"distinct_{label}_drift",
                level="SOFT",
                ok=True,
                detail=f"distinct {label}: {current_val} (baseline={baseline_val:.0f}, drift={drift:.1%})",
            ))
    return results


def check_null_rate_drift(
    df: pd.DataFrame, baseline: Optional[dict]
) -> list[CheckResult]:
    """Null-rate drift per PUBLIC_KEEP_COLUMNS column."""
    results: list[CheckResult] = []
    if baseline is None or "null_rates" not in baseline:
        results.append(CheckResult(
            name="null_rate_drift",
            level="SOFT",
            ok=True,
            detail="no baseline null_rates — skip",
        ))
        return results

    baseline_rates: dict = baseline["null_rates"]
    offenders: list[str] = []
    for col in PUBLIC_KEEP_COLUMNS:
        if col not in df.columns or col not in baseline_rates:
            continue
        current_rate = float(df[col].isna().mean())
        base_rate = float(baseline_rates[col])
        drift = abs(current_rate - base_rate)
        if drift > _SOFT_DRIFT_TOLERANCE:
            offenders.append(f"{col} (Δ={drift:.2f})")
    if offenders:
        results.append(CheckResult(
            name="null_rate_drift",
            level="SOFT",
            ok=False,
            detail=f"null-rate drift >15%: {offenders}",
        ))
    else:
        results.append(CheckResult(
            name="null_rate_drift",
            level="SOFT",
            ok=True,
            detail="null rates within tolerance",
        ))
    return results


def check_score_means_drift(
    df: pd.DataFrame, baseline: Optional[dict]
) -> list[CheckResult]:
    """Mean impact/urgency score drift vs baseline."""
    results: list[CheckResult] = []
    if baseline is None or "score_means" not in baseline:
        results.append(CheckResult(
            name="score_means_drift",
            level="SOFT",
            ok=True,
            detail="no baseline score_means — skip",
        ))
        return results

    baseline_means: dict = baseline["score_means"]
    offenders: list[str] = []
    for col in ("impact_score", "urgency_score"):
        if col not in df.columns or col not in baseline_means:
            continue
        current_mean = float(df[col].mean()) if len(df) > 0 else 0.0
        base_mean = float(baseline_means[col])
        drift = _relative_drift(current_mean, base_mean)
        if drift > _SOFT_DRIFT_TOLERANCE:
            offenders.append(f"{col} (drift={drift:.1%}, now={current_mean:.2f}, baseline={base_mean:.2f})")
    if offenders:
        results.append(CheckResult(
            name="score_means_drift",
            level="SOFT",
            ok=False,
            detail=f"score mean drift >15%: {offenders}",
        ))
    else:
        results.append(CheckResult(
            name="score_means_drift",
            level="SOFT",
            ok=True,
            detail="score means within tolerance",
        ))
    return results


def check_out_of_window_date_share(
    df: pd.DataFrame, baseline: Optional[dict]
) -> CheckResult:
    """Out-of-PLAUSIBLE_DATE_WINDOW pub-date share drift vs baseline.

    Computes the fraction of reconciled_published_date values outside the
    PLAUSIBLE_DATE_WINDOW and warns if it drifts significantly vs baseline.
    """
    col = "reconciled_published_date"
    if col not in df.columns:
        return CheckResult(
            name="out_of_window_date_share",
            level="SOFT",
            ok=True,
            detail=f"column '{col}' absent — skip",
        )
    low, high = PLAUSIBLE_DATE_WINDOW
    try:
        dates = pd.to_datetime(df[col], errors="coerce").dt.date
        n_total = len(dates)
        n_out = int(((dates < low) | (dates > high)).sum())
        current_share = n_out / n_total if n_total > 0 else 0.0
    except Exception:
        return CheckResult(
            name="out_of_window_date_share",
            level="SOFT",
            ok=True,
            detail="date parsing failed — skip",
        )

    if baseline is None or "out_of_window_date_share" not in baseline:
        return CheckResult(
            name="out_of_window_date_share",
            level="SOFT",
            ok=True,
            detail=f"out-of-window share={current_share:.3%} (no baseline to compare)",
        )

    base_share = float(baseline["out_of_window_date_share"])
    drift = abs(current_share - base_share)
    if drift > _SOFT_DRIFT_TOLERANCE:
        return CheckResult(
            name="out_of_window_date_share",
            level="SOFT",
            ok=False,
            detail=(
                f"out-of-window date share drifted {drift:.2%} "
                f"(baseline={base_share:.3%}, now={current_share:.3%})"
            ),
        )
    return CheckResult(
        name="out_of_window_date_share",
        level="SOFT",
        ok=True,
        detail=f"out-of-window date share={current_share:.3%} (drift={drift:.2%})",
    )


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------

def run_checks(
    df: pd.DataFrame,
    catalog_df: pd.DataFrame,
    snapshot_meta: dict,
    baseline: Optional[dict],
    bundle_dir: pathlib.Path,
) -> list[CheckResult]:
    """Run all HARD and SOFT checks and return the combined result list."""
    results: list[CheckResult] = []

    # HARD checks
    results.append(check_schema_present(df))
    results.append(check_no_extra_columns(df))
    results.append(check_no_denylist_columns(df))
    results.append(check_string_lengths(df))
    results.append(check_not_empty(df))
    results.append(check_no_null_columns(df))
    results.append(check_rowcount_vs_baseline(df, baseline))
    results.append(check_snapshot_advanced(snapshot_meta, baseline))
    results.append(check_topic_ids_in_catalog(df, catalog_df))
    results.append(check_deck_pdf(pathlib.Path(bundle_dir) / "carver-state-of-data.pdf"))
    results.append(check_sidecars_present(bundle_dir))

    # SOFT checks
    results.extend(check_distinct_counts_drift(df, baseline))
    results.extend(check_null_rate_drift(df, baseline))
    results.extend(check_score_means_drift(df, baseline))
    results.append(check_out_of_window_date_share(df, baseline))

    return results


def summarize(results: list[CheckResult]) -> dict:
    """Summarise the check results into counts and overall gate status."""
    hard_checks = [r for r in results if r.level == "HARD"]
    soft_checks = [r for r in results if r.level == "SOFT"]
    hard_failed = any(not r.ok for r in hard_checks)
    return {
        "total": len(results),
        "hard_total": len(hard_checks),
        "hard_passed": sum(1 for r in hard_checks if r.ok),
        "hard_failed_count": sum(1 for r in hard_checks if not r.ok),
        "soft_total": len(soft_checks),
        "soft_warned": sum(1 for r in soft_checks if not r.ok),
        "hard_failed": hard_failed,
    }


# ---------------------------------------------------------------------------
# Baseline computation
# ---------------------------------------------------------------------------

def current_baseline(df: pd.DataFrame, snapshot_meta: dict) -> dict:
    """Compute the baseline stats dict for the current bundle.

    The returned dict is written to baseline.json on a passing run.
    """
    null_rates: dict[str, float] = {}
    for col in PUBLIC_KEEP_COLUMNS:
        if col in df.columns:
            null_rates[col] = float(df[col].isna().mean())

    score_means: dict[str, float] = {}
    for col in ("impact_score", "urgency_score"):
        if col in df.columns:
            val = df[col].mean()
            score_means[col] = float(val) if pd.notna(val) else 0.0

    # Out-of-window date share
    col = "reconciled_published_date"
    out_of_window_share = 0.0
    if col in df.columns:
        try:
            low, high = PLAUSIBLE_DATE_WINDOW
            dates = pd.to_datetime(df[col], errors="coerce").dt.date
            n_total = len(dates)
            n_out = int(((dates < low) | (dates > high)).sum())
            out_of_window_share = n_out / n_total if n_total > 0 else 0.0
        except Exception:
            pass

    snapshot_date: str = snapshot_meta.get("snapshot_date", "")

    return {
        "rows": len(df),
        "distinct_institutions": int(df["topic_id"].nunique()) if "topic_id" in df.columns else 0,
        "distinct_countries": int(df["jurisdiction_country"].nunique()) if "jurisdiction_country" in df.columns else 0,
        "distinct_update_types": int(df["update_type"].nunique()) if "update_type" in df.columns else 0,
        "null_rates": null_rates,
        "score_means": score_means,
        "out_of_window_date_share": out_of_window_share,
        "snapshot_date": snapshot_date,
    }


# ---------------------------------------------------------------------------
# Report writer
# ---------------------------------------------------------------------------

def _status_icon(result: CheckResult) -> str:
    if result.ok:
        return "PASS"
    return "FAIL" if result.level == "HARD" else "WARN"


def write_report(results: list[CheckResult], summary: dict, report_path: pathlib.Path) -> None:
    """Write a Markdown PASS/WARN/FAIL table to report_path."""
    lines: list[str] = [
        "# Bundle Validation Report",
        "",
        f"Generated: {datetime.datetime.now(datetime.timezone.utc).isoformat()}",
        "",
        f"**Overall:** {'FAIL' if summary['hard_failed'] else 'PASS'}  "
        f"| hard_failed={summary['hard_failed_count']}  "
        f"| soft_warned={summary['soft_warned']}",
        "",
        "## Check Results",
        "",
        "| Status | Level | Check | Detail |",
        "| ------ | ----- | ----- | ------ |",
    ]
    for r in results:
        status = _status_icon(r)
        detail = r.detail.replace("|", "\\|")
        lines.append(f"| {status} | {r.level} | {r.name} | {detail} |")

    lines += [
        "",
        "## Summary",
        "",
        f"- Hard checks: {summary['hard_passed']} / {summary['hard_total']} passed",
        f"- Soft checks: {summary['soft_warned']} warned out of {summary['soft_total']}",
    ]

    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


# ---------------------------------------------------------------------------
# Thin I/O wrapper
# ---------------------------------------------------------------------------

def validate_bundle(
    bundle_dir: pathlib.Path = DATA_DIR / "public",
) -> int:
    """Load the public bundle, run all checks, write report + baseline.

    Parameters
    ----------
    bundle_dir:
        Directory containing the slim public bundle.

    Returns
    -------
    int
        0 if all HARD checks pass; 1 if any HARD check fails.
    """
    bundle_dir = pathlib.Path(bundle_dir)
    print(f"validate_bundle: checking {bundle_dir}", flush=True)

    # --- Load annotations parquet ---
    parquet_path = bundle_dir / "annotations.parquet"
    try:
        df = pd.read_parquet(parquet_path)
    except Exception as exc:
        print(f"ERROR: cannot load {parquet_path}: {exc}", flush=True)
        return 1

    # --- Load topic catalog ---
    catalog_path = bundle_dir / "topic_catalog.csv"
    try:
        catalog_df = pd.read_csv(catalog_path, keep_default_na=False, na_values=[])
    except Exception as exc:
        print(f"WARNING: cannot load {catalog_path}: {exc} — topic_id checks will skip", flush=True)
        catalog_df = pd.DataFrame(columns=["topic_id"])

    # --- Load snapshot meta ---
    meta_path = bundle_dir / "snapshot_meta.json"
    try:
        with open(meta_path, encoding="utf-8") as fh:
            snapshot_meta: dict = json.load(fh)
    except Exception as exc:
        print(f"WARNING: cannot load {meta_path}: {exc} — snapshot checks will skip", flush=True)
        snapshot_meta = {}

    # --- Load existing baseline (None if absent) ---
    baseline_path = bundle_dir / "baseline.json"
    baseline: Optional[dict] = None
    if baseline_path.exists():
        try:
            with open(baseline_path, encoding="utf-8") as fh:
                baseline = json.load(fh)
        except Exception as exc:
            print(f"WARNING: cannot load {baseline_path}: {exc} — treating as first run", flush=True)

    # --- Run all checks ---
    results = run_checks(df, catalog_df, snapshot_meta, baseline, bundle_dir)
    summary = summarize(results)

    # --- Write validation report ---
    report_path = bundle_dir / "validation_report.md"
    write_report(results, summary, report_path)
    print(f"Report written: {report_path}", flush=True)

    # --- Print summary ---
    overall = "FAIL" if summary["hard_failed"] else "PASS"
    print(
        f"  overall={overall}  "
        f"hard_failed={summary['hard_failed_count']}  "
        f"soft_warned={summary['soft_warned']}",
        flush=True,
    )
    for r in results:
        if not r.ok:
            print(f"  [{r.level}] {r.name}: {r.detail}", flush=True)

    # --- Update baseline only on a clean (no hard failure) run ---
    exit_code = 1 if summary["hard_failed"] else 0
    if exit_code == 0:
        new_baseline = current_baseline(df, snapshot_meta)
        with open(baseline_path, "w", encoding="utf-8") as fh:
            json.dump(new_baseline, fh, indent=2)
        print(f"Baseline updated: {baseline_path}", flush=True)

    return exit_code


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def build_arg_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(
        description=(
            "Offline bundle gate — validates data/public/ before publish. "
            "Exits non-zero on any HARD failure so the weekly validate && git commit "
            "gate blocks bad or leaky data. No API key required."
        ),
    )
    ap.add_argument(
        "--bundle-dir",
        default=str(DATA_DIR / "public"),
        metavar="DIR",
        help=f"Public bundle directory to validate (default: {DATA_DIR / 'public'})",
    )
    return ap


def main() -> None:
    args = build_arg_parser().parse_args()
    sys.exit(validate_bundle(pathlib.Path(args.bundle_dir)))


if __name__ == "__main__":
    main()
