"""Streaming JSONL reader over `../carver-showcase/data/annotations.jsonl` (spec §2).

LEAF module: imports nothing else from `mastra_prep`
(`tests/test_imports.py::test_no_circular_imports` enforces this).

The target file is ~1.8GB, one JSON object per line. `../carver-showcase` is
strictly read-only input; never written. `stream_annotations` therefore never
`json.load()`s or `.readlines()`s the whole file — it holds at most one line
resident in memory at a time via `open()` + line iteration.
"""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Iterator

logger = logging.getLogger(__name__)


def stream_annotations(path: str | Path) -> Iterator[dict]:
    """Yield one parsed JSON object per line. Never loads the file into memory.

    Malformed lines are skipped with a logged WARNING (line number + first 80
    chars); the stream continues. Raises FileNotFoundError if path does not
    exist.
    """
    with open(path, "r", encoding="utf-8") as f:
        for lineno, line in enumerate(f, start=1):
            line = line.strip()
            if not line:
                continue
            try:
                yield json.loads(line)
            except json.JSONDecodeError:
                logger.warning("skipping malformed JSON at line %d: %.80s", lineno, line)
