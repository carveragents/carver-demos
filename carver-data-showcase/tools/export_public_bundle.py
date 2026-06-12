"""Export the aggregate-only public bundle to data/public/.

Produces a slim annotations parquet (PUBLIC_KEEP_COLUMNS only) and copies the
already-aggregate sidecar files verbatim.  The public app reads exclusively
from data/public/ (via CARVER_DATA_DIR=data/public), so all filenames stay
identical to the full-data layout — no loader changes are required.

Run:
    .venv/bin/python tools/export_public_bundle.py
    .venv/bin/python tools/export_public_bundle.py --src data/annotations.parquet --out data/public
"""
from __future__ import annotations

import argparse
import logging
import os
import pathlib
import shutil
import sys
from typing import Optional

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

import pandas as pd

from carver_showcase.config import (
    ANNOTATIONS_PARQUET,
    DATA_DIR,
    DECK_PDF,
    ENTITY_LEADERBOARD_CSV,
    ENTITY_TYPE_BREAKDOWN_CSV,
    PUBLIC_KEEP_COLUMNS,
    SNAPSHOT_META_JSON,
    TAG_LEADERBOARD_CSV,
    TERM_STATS_META_JSON,
    TOPIC_CATALOG_CSV,
    TOPIC_DOMAINS_CSV,
)
from carver_showcase.curate import drop_noise_update_types
from carver_showcase.load import load_normalized

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Sidecar list: aggregate files copied verbatim into the public bundle.
# Excludes:
#   - annotations.parquet  (written by slim_frame, not copied)
#   - topic_categories.csv (internal-only; must never be surfaced externally)
# ---------------------------------------------------------------------------

PUBLIC_SIDECARS: list[pathlib.Path] = [
    TOPIC_CATALOG_CSV,
    TOPIC_DOMAINS_CSV,
    ENTITY_TYPE_BREAKDOWN_CSV,
    ENTITY_LEADERBOARD_CSV,
    TAG_LEADERBOARD_CSV,
    TERM_STATS_META_JSON,
    SNAPSHOT_META_JSON,
    DECK_PDF,
]


# ---------------------------------------------------------------------------
# Pure helpers
# ---------------------------------------------------------------------------


def slim_frame(df: pd.DataFrame) -> pd.DataFrame:
    """Return df restricted to PUBLIC_KEEP_COLUMNS, in declared order.

    PURE — no I/O.

    Parameters
    ----------
    df:
        Normalized annotations DataFrame (all columns from the full schema).

    Returns
    -------
    pd.DataFrame
        Exactly the columns in PUBLIC_KEEP_COLUMNS, in that order.
        Row count is preserved.

    Raises
    ------
    ValueError
        If any column in PUBLIC_KEEP_COLUMNS is absent from df.  A missing keep
        column means the upstream schema changed — fail loud rather than silently
        shipping a partial bundle.
    """
    missing = [col for col in PUBLIC_KEEP_COLUMNS if col not in df.columns]
    if missing:
        raise ValueError(
            f"slim_frame: upstream schema is missing required PUBLIC_KEEP_COLUMNS: {missing}. "
            f"The annotations parquet must be rebuilt before exporting the public bundle."
        )
    return df[list(PUBLIC_KEEP_COLUMNS)]


def copy_sidecars(
    sidecars: list[pathlib.Path],
    out_dir: pathlib.Path,
) -> tuple[list[str], list[str]]:
    """Copy each sidecar that exists into out_dir using its basename.

    Lenient: logs a warning for missing files and continues.  Completeness is
    enforced by validate_bundle.py, not here.

    Parameters
    ----------
    sidecars:
        Source Path objects to copy.
    out_dir:
        Destination directory (must already exist).

    Returns
    -------
    tuple[list[str], list[str]]
        (copied, missing) — lists of basenames.
    """
    copied: list[str] = []
    missing: list[str] = []

    for src in sidecars:
        src = pathlib.Path(src)
        if not src.exists():
            logger.warning("Sidecar not found, skipping: %s", src)
            missing.append(src.name)
            continue
        shutil.copy2(src, out_dir / src.name)
        copied.append(src.name)

    return copied, missing


# ---------------------------------------------------------------------------
# Thin I/O wrapper
# ---------------------------------------------------------------------------


def build_public_bundle(
    src_parquet: pathlib.Path = ANNOTATIONS_PARQUET,
    out_dir: pathlib.Path = DATA_DIR / "public",
    sidecars: Optional[list[pathlib.Path]] = None,
) -> dict:
    """Build the aggregate-only public bundle.

    Loads the full normalized frame from src_parquet, strips it to the 15
    PUBLIC_KEEP_COLUMNS, writes the slim parquet to out_dir, and copies all
    present sidecar files verbatim.

    Parameters
    ----------
    src_parquet:
        Path to the full normalized annotations parquet.
    out_dir:
        Destination directory for the public bundle (created if absent).
    sidecars:
        List of sidecar Paths to copy.  Defaults to PUBLIC_SIDECARS.

    Returns
    -------
    dict
        Summary with keys: rows, columns, out_dir, sidecars_copied,
        sidecars_missing.
    """
    if sidecars is None:
        sidecars = PUBLIC_SIDECARS

    src_parquet = pathlib.Path(src_parquet)
    out_dir = pathlib.Path(out_dir)

    logger.info("Loading normalized frame from %s", src_parquet)
    df = load_normalized(parquet_path=src_parquet)
    full_rows = len(df)

    # Curate first (drop noise update_types), then slim to public columns.
    # drop_noise_update_types is idempotent and pure (only needs update_type).
    curated = drop_noise_update_types(df)
    curated_rows = len(curated)
    logger.info(
        "Curation: %d → %d rows (dropped %d noise update_type records)",
        full_rows,
        curated_rows,
        full_rows - curated_rows,
    )

    slim = slim_frame(curated)

    out_dir.mkdir(parents=True, exist_ok=True)

    slim_path = out_dir / "annotations.parquet"
    slim.to_parquet(slim_path, engine="pyarrow", index=False)
    logger.info("Slim parquet written: %s  (shape=%s)", slim_path, slim.shape)

    sidecars_copied, sidecars_missing = copy_sidecars(sidecars, out_dir)

    summary = {
        "rows": len(slim),
        "full_rows": full_rows,
        "curated_rows": curated_rows,
        "columns": len(slim.columns),
        "out_dir": out_dir,
        "sidecars_copied": sidecars_copied,
        "sidecars_missing": sidecars_missing,
    }

    logger.info(
        "Public bundle complete: %d rows (curated from %d) × %d cols | "
        "sidecars copied=%d missing=%d | out=%s",
        summary["rows"],
        summary["full_rows"],
        summary["columns"],
        len(sidecars_copied),
        len(sidecars_missing),
        out_dir,
    )
    return summary


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def build_arg_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(
        description=(
            "Export the aggregate-only public bundle to data/public/. "
            "Produces a slim annotations parquet (15 columns) and copies all "
            "aggregate sidecars verbatim. "
            "Set CARVER_DATA_DIR=data/public to point the app at this bundle."
        ),
    )
    ap.add_argument(
        "--src",
        default=str(ANNOTATIONS_PARQUET),
        metavar="PARQUET",
        help=f"Source normalized annotations parquet (default: {ANNOTATIONS_PARQUET})",
    )
    ap.add_argument(
        "--out",
        default=str(DATA_DIR / "public"),
        metavar="DIR",
        help=f"Output directory for the public bundle (default: {DATA_DIR / 'public'})",
    )
    return ap


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    args = build_arg_parser().parse_args()
    src_parquet = pathlib.Path(args.src)
    out_dir = pathlib.Path(args.out)

    summary = build_public_bundle(src_parquet=src_parquet, out_dir=out_dir)

    print(
        f"Public bundle written to: {summary['out_dir']}\n"
        f"  rows (curated): {summary['rows']:,} "
        f"(from {summary['full_rows']:,} full → {summary['curated_rows']:,} curated)\n"
        f"  columns:         {summary['columns']}\n"
        f"  sidecars copied: {summary['sidecars_copied']}\n"
        f"  sidecars missing: {summary['sidecars_missing']}"
    )


if __name__ == "__main__":
    main()
