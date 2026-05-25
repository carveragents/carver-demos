"""DP1 verification: sample one Carver entry and dump its full JSON.

Run once (or whenever DP1 needs to be re-verified). Output is human-inspected
to determine whether the SDK returns Appendix-A annotation fields directly,
or whether annotations must be fetched separately.

The script pulls:
  1. One entry via QueryEngine.to_dataframe() (the "entries" surface).
  2. The matching annotation via CarverFeedsAPIClient.get_annotations()
     (the separate "annotations" surface), if present.

Both shapes are emitted side-by-side so DP1 can be answered conclusively.

Usage:
    uv run python build/inspect_carver.py > data/dp1-sample-entry.json
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

from dotenv import load_dotenv


def main() -> int:
    # Load .env from repo root
    load_dotenv(Path(__file__).parent.parent / ".env")

    if not os.environ.get("CARVER_API_KEY"):
        print(
            "ERROR: CARVER_API_KEY not set. Create a .env file or export the var.",
            file=sys.stderr,
        )
        print("Get a key at https://app.carveragents.ai", file=sys.stderr)
        return 1

    # Import after env loaded — SDK reads CARVER_API_KEY at module-load time
    from carver_feeds import create_query_engine, get_client

    qe = create_query_engine()

    # to_dataframe() requires a topic filter; Banking is a known-good topic name.
    # The goal is to inspect ONE entry's full structure, not pull everything.
    df = qe.filter_by_topic(topic_name="Banking").to_dataframe()

    if len(df) == 0:
        print("ERROR: SDK returned zero entries. Check API key + connectivity.", file=sys.stderr)
        return 1

    entry = df.iloc[0].to_dict()

    # Also pull the annotation for this entry from the separate endpoint
    # (the entries dataframe does NOT include annotation fields; they live at
    #  /api/v1/core/annotations and are joined on feed_entry_id).
    annotation: list[dict] | dict | None = None
    annotation_error: str | None = None
    try:
        client = get_client()
        entry_id = entry.get("entry_id") or entry.get("id")
        if entry_id:
            annotation = client.get_annotations(feed_entry_ids=[str(entry_id)])
    except Exception as exc:  # pragma: no cover — diagnostic only
        annotation_error = f"{type(exc).__name__}: {exc}"

    output = {
        "entry_dataframe_row": entry,
        "entry_dataframe_columns": list(df.columns),
        "annotation_endpoint_result": annotation,
        "annotation_endpoint_error": annotation_error,
    }

    json.dump(output, sys.stdout, indent=2, default=str)
    return 0


if __name__ == "__main__":
    sys.exit(main())
