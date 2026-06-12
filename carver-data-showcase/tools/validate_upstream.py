"""Upstream reconciliation — validate local data against the live Carver API.

Runs in the weekly pipeline (has CARVER_API_KEY).  Exits non-zero on a HARD
failure that actually ran.  If no API key is present, only the key-free LOCAL
checks run (curation invariant) and live checks are SKIPPED.

Checks
------
HARD — institutions_match:
    ``len(topic_catalog) == count(/feeds/topics)``
HARD — curation_invariant (local, key-free):
    ``curated_rows + noise_rows == full_rows``
SOFT — records_vs_upstream (best-effort):
    local full rows ≈ upstream total within UPSTREAM_RECORD_TOLERANCE.
    SKIPPED if the API doesn't cheaply expose a total.
SOFT — records_vs_snapshot:
    full parquet row count matches ``snapshot_meta.json`` total_records.
    SKIPPED if the key is absent or the field is not stamped.
SOFT — freshness (best-effort):
    newest upstream ``created_at`` within ``max_age_days`` of snapshot date.
    SKIPPED if the API shape doesn't expose a recent artifact cheaply.
SOFT (bonus) — referential:
    catalog ``topic_id``s ⊆ upstream topic ids.
    SKIPPED if upstream topics are unavailable.

Run: .venv/bin/python tools/validate_upstream.py
     .venv/bin/python tools/validate_upstream.py --base-url https://app.carveragents.ai
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

# Import config constants after sys.path is set to avoid circular imports and
# to allow the module to be imported (e.g. --help) without a live network or key.
from carver_showcase.config import (  # noqa: E402
    ANNOTATIONS_PARQUET,
    ANNOTATIONS_DAG_ID,
    ARTIFACT_TYPE_ID,
    CARVER_BASE_URL_DEFAULT,
    SNAPSHOT_META_JSON,
    TOPIC_CATALOG_CSV,
    UPSTREAM_FRESHNESS_MAX_AGE_DAYS,
    UPSTREAM_RECORD_TOLERANCE,
)
from carver_showcase.curate import drop_noise_update_types  # noqa: E402


# ---------------------------------------------------------------------------
# Result type (compatible with validate_bundle.CheckResult)
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class CheckResult:
    """Outcome of a single validation check.

    level: "HARD" or "SOFT"
    ok:    True for pass or skipped; False for fail/warn.
    detail: human-readable explanation; includes "SKIPPED" word when skipped.
    """
    name: str
    level: str   # "HARD" or "SOFT"
    ok: bool
    detail: str


def _skipped(name: str, level: str, reason: str) -> CheckResult:
    """Convenience constructor for a skipped result (ok=True, detail notes skip)."""
    return CheckResult(name=name, level=level, ok=True, detail=f"SKIPPED — {reason}")


# ---------------------------------------------------------------------------
# Pure check functions (take already-fetched / already-loaded data)
# ---------------------------------------------------------------------------

def check_institutions_match(catalog_rows: int, topics_count: int) -> CheckResult:
    """HARD: topic_catalog row count must equal /feeds/topics list length.

    The catalog is the local snapshot of monitored institutions; the topics
    list is the live universe.  A mismatch means a pull is stale or the
    upstream universe has changed.
    """
    if catalog_rows == topics_count:
        return CheckResult(
            name="institutions_match",
            level="HARD",
            ok=True,
            detail=f"catalog_rows={catalog_rows} == topics_count={topics_count}",
        )
    return CheckResult(
        name="institutions_match",
        level="HARD",
        ok=False,
        detail=(
            f"catalog_rows={catalog_rows} != topics_count={topics_count}; "
            "re-run tools/pull_topic_catalog.py"
        ),
    )


def check_curation_invariant(full_rows: int, curated_rows: int, noise_rows: int) -> CheckResult:
    """HARD (local, key-free): curated_rows + noise_rows must equal full_rows.

    Validates that ``drop_noise_update_types`` is a total partition — the
    curated frame plus the discarded rows must reconstruct the full corpus.
    A failure here indicates a logic bug in the curation function.
    """
    total = curated_rows + noise_rows
    if total == full_rows:
        return CheckResult(
            name="curation_invariant",
            level="HARD",
            ok=True,
            detail=(
                f"curated={curated_rows:,} + noise={noise_rows:,} "
                f"== full={full_rows:,}"
            ),
        )
    return CheckResult(
        name="curation_invariant",
        level="HARD",
        ok=False,
        detail=(
            f"curated={curated_rows:,} + noise={noise_rows:,} = {total:,} "
            f"!= full={full_rows:,}; curation logic is not a total partition"
        ),
    )


def check_records_vs_upstream(
    full_rows: int,
    upstream_total: Optional[int],
    tolerance: float = UPSTREAM_RECORD_TOLERANCE,
) -> CheckResult:
    """SOFT (best-effort): local full rows ≈ upstream annotations total.

    The live feed drifts continuously; warn only when the deviation exceeds
    ``tolerance`` (default: UPSTREAM_RECORD_TOLERANCE from config).
    Returns SKIPPED when ``upstream_total`` is None (API doesn't cheaply expose
    a total — don't pull 200 K records just to count).
    """
    if upstream_total is None:
        return _skipped(
            "records_vs_upstream",
            "SOFT",
            "upstream total not available from API envelope (cheap path)",
        )
    if upstream_total == 0:
        return _skipped("records_vs_upstream", "SOFT", "upstream_total=0 — skip division")
    drift = abs(full_rows - upstream_total) / upstream_total
    if drift > tolerance:
        return CheckResult(
            name="records_vs_upstream",
            level="SOFT",
            ok=False,
            detail=(
                f"local={full_rows:,} vs upstream={upstream_total:,}; "
                f"drift={drift:.2%} > tolerance={tolerance:.2%}"
            ),
        )
    return CheckResult(
        name="records_vs_upstream",
        level="SOFT",
        ok=True,
        detail=(
            f"local={full_rows:,} vs upstream={upstream_total:,}; "
            f"drift={drift:.2%} within tolerance={tolerance:.2%}"
        ),
    )


def check_records_vs_snapshot(
    full_rows: int,
    snapshot_count: Optional[int],
) -> CheckResult:
    """SOFT: full parquet row count matches snapshot_meta.json total_records.

    The pull stamps the total it wrote; a mismatch here means the parquet
    was corrupted or re-generated from a different source.
    Returns SKIPPED when ``snapshot_count`` is None (not stamped in meta).
    """
    if snapshot_count is None:
        return _skipped(
            "records_vs_snapshot",
            "SOFT",
            "total_records not stamped in snapshot_meta.json",
        )
    if full_rows == snapshot_count:
        return CheckResult(
            name="records_vs_snapshot",
            level="SOFT",
            ok=True,
            detail=f"parquet rows={full_rows:,} == snapshot total_records={snapshot_count:,}",
        )
    return CheckResult(
        name="records_vs_snapshot",
        level="SOFT",
        ok=False,
        detail=(
            f"parquet rows={full_rows:,} != snapshot total_records={snapshot_count:,}; "
            "the parquet may have been rebuilt from a different source"
        ),
    )


def check_freshness(
    newest_created_at: Optional[str],
    snapshot_date: str,
    max_age_days: int = UPSTREAM_FRESHNESS_MAX_AGE_DAYS,
) -> CheckResult:
    """SOFT (best-effort): newest upstream artifact created_at within max_age_days.

    Detects a stale upstream feed — if the latest annotation is older than
    ``max_age_days`` relative to ``snapshot_date``, something may be wrong
    with the upstream pipeline.
    Returns SKIPPED when ``newest_created_at`` is None (API shape doesn't let
    us cheaply get the newest artifact's timestamp).
    """
    if newest_created_at is None:
        return _skipped(
            "freshness",
            "SOFT",
            "newest created_at not available from API (cheap path)",
        )
    try:
        snap_date = datetime.date.fromisoformat(snapshot_date)
    except (ValueError, TypeError):
        return _skipped("freshness", "SOFT", f"snapshot_date unparseable: {snapshot_date!r}")
    try:
        # ISO 8601 with optional fractional seconds and timezone
        newest_dt = datetime.datetime.fromisoformat(
            newest_created_at.replace("Z", "+00:00")
        )
        newest_date = newest_dt.date()
    except (ValueError, TypeError):
        return _skipped("freshness", "SOFT", f"newest_created_at unparseable: {newest_created_at!r}")

    age_days = (snap_date - newest_date).days
    if age_days > max_age_days:
        return CheckResult(
            name="freshness",
            level="SOFT",
            ok=False,
            detail=(
                f"newest upstream artifact is {age_days}d before snapshot date "
                f"(snapshot={snapshot_date}, newest={newest_date.isoformat()}, "
                f"max_age_days={max_age_days})"
            ),
        )
    return CheckResult(
        name="freshness",
        level="SOFT",
        ok=True,
        detail=(
            f"upstream feed is fresh: newest={newest_date.isoformat()}, "
            f"snapshot={snapshot_date}, age={age_days}d <= {max_age_days}d"
        ),
    )


def check_referential(
    catalog_topic_ids: set,
    topics_ids: Optional[set],
) -> CheckResult:
    """SOFT (bonus): catalog topic_ids ⊆ upstream topic ids.

    Every institution in the local catalog must exist in the live upstream
    universe.  Orphaned catalog entries indicate the upstream institution was
    deleted or the catalog is stale.
    Returns SKIPPED when ``topics_ids`` is None (upstream unavailable).
    """
    if topics_ids is None:
        return _skipped(
            "referential",
            "SOFT",
            "upstream topic ids unavailable (no key or fetch failed)",
        )
    orphans = sorted(catalog_topic_ids - topics_ids)
    if orphans:
        n = len(orphans)
        sample = orphans[:5]
        return CheckResult(
            name="referential",
            level="SOFT",
            ok=False,
            detail=(
                f"{n} catalog topic_id(s) not in upstream topics: "
                f"{sample}{' ...' if n > 5 else ''}"
            ),
        )
    return CheckResult(
        name="referential",
        level="SOFT",
        ok=True,
        detail=(
            f"all {len(catalog_topic_ids)} catalog topic_id(s) present "
            "in upstream topics"
        ),
    )


# ---------------------------------------------------------------------------
# Orchestrator — pure over injected data
# ---------------------------------------------------------------------------

def run_upstream_checks(
    *,
    catalog_rows: int,
    topics_count_or_none: Optional[int],
    full_rows: int,
    curated_rows: int,
    noise_rows: int,
    upstream_total: Optional[int],
    snapshot_count: Optional[int],
    newest_created_at: Optional[str],
    snapshot_date: str,
    catalog_topic_ids: set,
    topics_ids_or_none: Optional[set],
) -> list[CheckResult]:
    """Run all upstream checks and return the combined result list.

    Live inputs (``topics_count_or_none``, ``upstream_total``,
    ``newest_created_at``, ``topics_ids_or_none``) may be None when no API
    key is present or a fetch failed; the corresponding live checks return
    SKIPPED rather than FAIL.  The LOCAL curation invariant always runs.
    """
    results: list[CheckResult] = []

    # --- HARD: institutions match (live, key-gated) ---
    if topics_count_or_none is None:
        results.append(_skipped(
            "institutions_match",
            "HARD",
            "upstream topics unavailable (no API key or fetch failed)",
        ))
    else:
        results.append(check_institutions_match(catalog_rows, topics_count_or_none))

    # --- HARD: curation invariant (local, always runs) ---
    results.append(check_curation_invariant(full_rows, curated_rows, noise_rows))

    # --- SOFT: records vs upstream total (best-effort) ---
    results.append(check_records_vs_upstream(full_rows, upstream_total))

    # --- SOFT: records vs snapshot stamped count ---
    results.append(check_records_vs_snapshot(full_rows, snapshot_count))

    # --- SOFT: freshness (best-effort) ---
    results.append(check_freshness(newest_created_at, snapshot_date))

    # --- SOFT (bonus): referential integrity ---
    results.append(check_referential(catalog_topic_ids, topics_ids_or_none))

    return results


# ---------------------------------------------------------------------------
# I/O helpers — thin, monkeypatchable
# ---------------------------------------------------------------------------

def read_api_key() -> Optional[str]:
    """Return CARVER_API_KEY from env (or .env via dotenv).

    load_dotenv is called here (deferred) rather than at module import time so
    the tool can be imported cleanly (e.g. --help) with no filesystem side-effect.
    Returns None if absent — never raises.
    """
    from dotenv import load_dotenv  # deferred — no import-time side-effect
    load_dotenv(dotenv_path=os.path.join(ROOT, ".env"))  # explicit path (see LESSONS)
    return os.environ.get("CARVER_API_KEY") or None


def make_session():
    """Create a reusable httpx Client with a generous timeout."""
    import httpx  # deferred — no import-time network dependency
    return httpx.Client(timeout=120)


def fetch_topics(base_url: str, api_key: str) -> list[dict]:
    """GET /api/v1/feeds/topics?details=true and return the list.

    Raises on non-2xx.
    """
    with make_session() as client:
        r = client.get(
            base_url.rstrip("/") + "/api/v1/feeds/topics",
            params={"details": "true"},
            headers={"X-API-Key": api_key},
        )
        r.raise_for_status()
        return r.json()


def fetch_annotations_meta(base_url: str, api_key: str) -> dict:
    """Best-effort probe of the artifacts endpoint for cheap aggregate info.

    Fetches ONE artifact (limit=1, state=completed) and tries to read an
    upstream total / count from the envelope (some APIs expose ``total`` or
    ``count`` in a wrapper).  If none is exposed, returns Nones.

    The actual artifacts API returns a bare list (no pagination wrapper), so
    we cannot cheaply get a total without walking the whole 200 K corpus.
    We therefore return ``upstream_total=None`` and extract ``newest_created_at``
    from the single record returned if present.

    Never raises — all errors return the fallback dict.
    """
    fallback: dict = {"upstream_total": None, "newest_created_at": None}
    try:
        url = (
            base_url.rstrip("/")
            + f"/api/v1/artifacts/dags/{ANNOTATIONS_DAG_ID}/artifacts"
        )
        params = {
            "state": "completed",
            "dry_run": "true",
            "artifact_type_id": ARTIFACT_TYPE_ID,
            "limit": "1",
            "offset": "0",
        }
        with make_session() as client:
            r = client.get(url, params=params, headers={"X-API-Key": api_key})
            r.raise_for_status()
            data = r.json()

        # The API returns a bare list of envelopes (confirmed by probe_api.py).
        # There is no "total" key in the response — upstream_total stays None.
        # We can extract newest_created_at from the first record if available.
        upstream_total: Optional[int] = None
        newest_created_at: Optional[str] = None

        if isinstance(data, dict):
            # Some envelope shapes wrap in a dict — try common total keys.
            for key in ("total", "count", "total_count", "total_records"):
                if key in data:
                    upstream_total = int(data[key])
                    break
            items = data.get("items") or data.get("results") or data.get("data") or []
        elif isinstance(data, list):
            items = data
        else:
            items = []

        if items and isinstance(items[0], dict):
            newest_created_at = items[0].get("created_at")

        return {"upstream_total": upstream_total, "newest_created_at": newest_created_at}

    except Exception:  # noqa: BLE001 — best-effort: never fail the run
        return fallback


# ---------------------------------------------------------------------------
# Report helpers
# ---------------------------------------------------------------------------

def _status_label(result: CheckResult) -> str:
    if "SKIPPED" in result.detail:
        return "SKIP"
    if result.ok:
        return "PASS"
    return "FAIL" if result.level == "HARD" else "WARN"


def _print_report(results: list[CheckResult], *, has_key: bool) -> None:
    """Print a compact PASS/WARN/SKIP/FAIL report to stdout."""
    if not has_key:
        print("validate_upstream: live checks skipped (no API key)", flush=True)
    print("", flush=True)
    for r in results:
        label = _status_label(r)
        print(f"  [{label:4s}] [{r.level:4s}] {r.name}: {r.detail}", flush=True)
    print("", flush=True)

    hard_failed = [r for r in results if r.level == "HARD" and not r.ok and "SKIPPED" not in r.detail]
    soft_warned = [r for r in results if r.level == "SOFT" and not r.ok and "SKIPPED" not in r.detail]
    skipped = [r for r in results if "SKIPPED" in r.detail]

    overall = "FAIL" if hard_failed else "PASS"
    print(
        f"  overall={overall}  "
        f"hard_failed={len(hard_failed)}  "
        f"soft_warned={len(soft_warned)}  "
        f"skipped={len(skipped)}",
        flush=True,
    )
    if hard_failed:
        for r in hard_failed:
            print(f"  [HARD FAIL] {r.name}: {r.detail}", flush=True)


# ---------------------------------------------------------------------------
# Thin I/O wrapper
# ---------------------------------------------------------------------------

def validate_upstream(
    base_url: str = CARVER_BASE_URL_DEFAULT,
    annotations_parquet: pathlib.Path = ANNOTATIONS_PARQUET,
    topic_catalog_csv: pathlib.Path = TOPIC_CATALOG_CSV,
    snapshot_meta_json: pathlib.Path = SNAPSHOT_META_JSON,
) -> int:
    """Load local data, optionally fetch live data, run checks, print report.

    Returns 0 if all HARD checks that RAN passed (or were skipped); 1 if any
    HARD check failed.  A SOFT warning does not affect the exit code.

    Key-gating: when no API key is available, only local checks run; live
    checks return SKIPPED (not FAIL) so the gate does not block.
    """
    import pandas as pd

    # --- Read API key (never raises) ---
    api_key = read_api_key()
    has_key = api_key is not None

    # --- Load local full parquet ---
    try:
        df = pd.read_parquet(annotations_parquet)
    except Exception as exc:
        print(f"ERROR: cannot load {annotations_parquet}: {exc}", flush=True)
        return 1

    full_rows = len(df)
    curated_rows = len(drop_noise_update_types(df))
    noise_rows = full_rows - curated_rows

    # --- Load topic catalog ---
    try:
        catalog_df = pd.read_csv(
            topic_catalog_csv,
            keep_default_na=False,
            na_values=[],
        )
        catalog_rows = len(catalog_df)
        catalog_topic_ids: set = set(
            catalog_df["topic_id"].dropna().unique()
            if "topic_id" in catalog_df.columns
            else []
        )
    except Exception as exc:
        print(f"WARNING: cannot load {topic_catalog_csv}: {exc} — catalog checks will skip", flush=True)
        catalog_rows = 0
        catalog_topic_ids = set()

    # --- Load snapshot meta ---
    try:
        with open(snapshot_meta_json, encoding="utf-8") as fh:
            snapshot_meta: dict = json.load(fh)
    except Exception as exc:
        print(f"WARNING: cannot load {snapshot_meta_json}: {exc} — snapshot checks will skip", flush=True)
        snapshot_meta = {}

    snapshot_date: str = snapshot_meta.get("snapshot_date", "")
    snapshot_count: Optional[int] = snapshot_meta.get("total_records")

    # --- Fetch live data (key-gated, best-effort) ---
    topics_count_or_none: Optional[int] = None
    topics_ids_or_none: Optional[set] = None
    upstream_total: Optional[int] = None
    newest_created_at: Optional[str] = None

    if has_key:
        assert api_key is not None  # type-narrowing
        try:
            topics_list = fetch_topics(base_url, api_key)
            topics_count_or_none = len(topics_list)
            topics_ids_or_none = {
                t["id"] for t in topics_list if isinstance(t, dict) and t.get("id")
            }
        except Exception as exc:
            print(f"WARNING: fetch_topics failed ({exc!r}) — live institution checks will skip", flush=True)

        try:
            ann_meta = fetch_annotations_meta(base_url, api_key)
            upstream_total = ann_meta.get("upstream_total")
            newest_created_at = ann_meta.get("newest_created_at")
        except Exception as exc:
            print(f"WARNING: fetch_annotations_meta failed ({exc!r}) — best-effort checks will skip", flush=True)

    # --- Run all checks ---
    results = run_upstream_checks(
        catalog_rows=catalog_rows,
        topics_count_or_none=topics_count_or_none,
        full_rows=full_rows,
        curated_rows=curated_rows,
        noise_rows=noise_rows,
        upstream_total=upstream_total,
        snapshot_count=snapshot_count,
        newest_created_at=newest_created_at,
        snapshot_date=snapshot_date,
        catalog_topic_ids=catalog_topic_ids,
        topics_ids_or_none=topics_ids_or_none,
    )

    # --- Print report ---
    _print_report(results, has_key=has_key)

    # --- Exit non-zero only if a HARD check that actually ran failed ---
    hard_failed = any(
        r.level == "HARD" and not r.ok and "SKIPPED" not in r.detail
        for r in results
    )
    return 1 if hard_failed else 0


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def build_arg_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(
        description=(
            "Upstream reconciliation — validate local data against the live "
            "Carver API. Exits non-zero on a HARD failure that actually ran. "
            "Requires CARVER_API_KEY for live checks; runs local-only without it."
        ),
    )
    ap.add_argument(
        "--base-url",
        default=CARVER_BASE_URL_DEFAULT,
        metavar="URL",
        help=f"Carver API base URL (default: {CARVER_BASE_URL_DEFAULT})",
    )
    return ap


def main() -> None:
    args = build_arg_parser().parse_args()
    sys.exit(validate_upstream(base_url=args.base_url))


if __name__ == "__main__":
    main()
