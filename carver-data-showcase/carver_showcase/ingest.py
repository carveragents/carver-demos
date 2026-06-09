"""Ingest layer for the Carver Annotation Data Showcase.

Two responsibilities, kept strictly separate:

1. `load_snapshot(path)` — memory-safe streaming of an on-disk JSONL snapshot.
2. `pull_snapshot(...)` / `pull_topic_catalog(...)` — thin wrappers around the
   direct Carver Artifacts API (mirroring the proven tools/pull_stratified.py
   pattern). These are ONE-TIME offline tools; they are NEVER called at app
   render time.

Design notes
------------
- `pull_snapshot` REFUSES an empty `topic_ids` list.  An empty `topic_ids_in`
  parameter is silently treated by the API as "no filter" and would pull the
  whole corpus — a real past bug documented in tools/pull_stratified.py.
- The optional `_transport` parameter lets tests inject an `httpx.MockTransport`
  without touching the network.
"""

from __future__ import annotations

import json
import pathlib
import time
from typing import Iterable, Iterator, Optional

import httpx

from carver_showcase.config import (
    ANNOTATIONS_DAG_ID,
    API_PAGE_SIZE,
    ARTIFACT_TYPE_ID,
    CARVER_BASE_URL_DEFAULT,
)


# ---------------------------------------------------------------------------
# Public: streaming loader
# ---------------------------------------------------------------------------


def load_snapshot(path: pathlib.Path) -> Iterator[dict]:
    """Yield one raw envelope dict per non-blank JSONL line.

    Memory-safe: lines are decoded one at a time; the file is never fully
    loaded into memory.  Safe to use on the 423 MB / 58,982-line snapshot.

    Parameters
    ----------
    path:
        Path to a JSONL file (one JSON object per line).

    Yields
    ------
    dict
        The parsed JSON object for each non-blank line.
    """
    with open(path, encoding="utf-8") as fh:
        for raw_line in fh:
            line = raw_line.strip()
            if line:
                yield json.loads(line)


# ---------------------------------------------------------------------------
# Public: one-time pull wrappers
# ---------------------------------------------------------------------------


def pull_snapshot(
    api_key: str,
    dag: str = ANNOTATIONS_DAG_ID,
    out_path: pathlib.Path = pathlib.Path("data/annotations.jsonl"),
    page_size: int = API_PAGE_SIZE,
    topic_ids: Optional[list[str]] = None,
    base_url: str = CARVER_BASE_URL_DEFAULT,
    artifact_type_id: str = ARTIFACT_TYPE_ID,
    *,
    _transport: Optional[httpx.BaseTransport] = None,
) -> int:
    """Pull completed annotation artifacts from the Carver Artifacts API.

    Pagination stops when a page is shorter than `page_size` (i.e. the last
    page).  Results are written as JSONL to `out_path` (one record per line).

    Parameters
    ----------
    api_key:
        Carver API key (``X-API-Key`` header).
    dag:
        DAG ID for the annotations DAG.
    out_path:
        Destination JSONL file.  Parent directory must already exist.
    page_size:
        Records per API request.
    topic_ids:
        When provided (a *non-empty* list), adds a ``topic_ids_in`` filter so
        only annotations for those topics are returned.  ``None`` means no
        filter (full corpus pull).  **An empty list raises ``ValueError``** —
        an empty ``topic_ids_in`` is treated as "no filter" by the API and
        would pull the whole corpus.
    base_url:
        Base URL of the Carver deployment.
    artifact_type_id:
        Artifact type string (default: ``annotations-v1``).
    _transport:
        Optional httpx transport override (for tests; do not use in production).

    Returns
    -------
    int
        Total number of records written.

    Raises
    ------
    ValueError
        If ``topic_ids`` is an empty list.
    """
    if topic_ids is not None and len(topic_ids) == 0:
        raise ValueError(
            "pull_snapshot called with an empty topic_ids list — refusing. "
            "An empty topic_ids_in filter is treated as 'no filter' by the API "
            "and would pull the whole corpus."
        )

    headers = {"X-API-Key": api_key}
    client_kwargs: dict = {"timeout": 300.0}
    if _transport is not None:
        client_kwargs["transport"] = _transport

    topic_filter = ""
    if topic_ids:
        topic_filter = "&topic_ids_in=" + ",".join(topic_ids)

    out_path = pathlib.Path(out_path)
    offset = 0
    total = 0

    with httpx.Client(**client_kwargs) as client:
        with open(out_path, "w", encoding="utf-8") as fh:
            while True:
                url = (
                    f"{base_url}/api/v1/artifacts/dags/{dag}/artifacts"
                    f"?state=completed"
                    f"&artifact_type_id={artifact_type_id}"
                    f"&limit={page_size}"
                    f"&offset={offset}"
                    f"{topic_filter}"
                )
                response = client.get(url, headers=headers)
                response.raise_for_status()
                records = response.json()

                if not records:
                    break

                for record in records:
                    fh.write(json.dumps(record) + "\n")

                total += len(records)
                offset += len(records)

                if len(records) < page_size:
                    break

                if _transport is None:
                    time.sleep(0.1)

    return total


def pull_topic_catalog(
    api_key: str,
    out_path: pathlib.Path = pathlib.Path("data/topic_catalog.jsonl"),
    base_url: str = CARVER_BASE_URL_DEFAULT,
    *,
    _transport: Optional[httpx.BaseTransport] = None,
) -> int:
    """Pull the full topics catalog from the Carver API.

    Writes each topic as a JSONL line to `out_path`.  This is a one-time
    offline tool used to build the topic→category map and the
    Monitored-institutions view.

    Parameters
    ----------
    api_key:
        Carver API key (``X-API-Key`` header).
    out_path:
        Destination JSONL file.
    base_url:
        Base URL of the Carver deployment.
    _transport:
        Optional httpx transport override (for tests).

    Returns
    -------
    int
        Total number of topics written.
    """
    headers = {"X-API-Key": api_key}
    client_kwargs: dict = {"timeout": 120.0}
    if _transport is not None:
        client_kwargs["transport"] = _transport

    out_path = pathlib.Path(out_path)
    url = f"{base_url}/api/v1/feeds/topics?details=true"

    with httpx.Client(**client_kwargs) as client:
        response = client.get(url, headers=headers)
        response.raise_for_status()
        topics = response.json()

    with open(out_path, "w", encoding="utf-8") as fh:
        for topic in topics:
            fh.write(json.dumps(topic) + "\n")

    return len(topics)
