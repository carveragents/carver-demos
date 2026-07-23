"""The progress channel used throughout `prep/` (spec §1, §3's curation loop, §7's trial, §15).

LEAF module: imports nothing else from `mastra_prep`
(`tests/test_imports.py::test_no_circular_imports` enforces this).

Named with a trailing underscore so it never shadows stdlib `logging`
(`tests/test_imports.py::test_no_stdlib_shadowing` enforces this too) — a
sibling module doing `import logging` inside this package must always reach
the stdlib module, never this file.
"""
from __future__ import annotations

import logging

_LOGGER_NAME = "mastra_prep"


def log(message: str) -> None:
    """Emit a progress message at INFO level on the shared `mastra_prep` logger.

    A thin wrapper — the point is one obvious call site, not a new API surface.
    Used throughout `prep/` so a long sweep (~400 records) prints something
    every batch rather than looking indistinguishable from a hang.
    """
    logging.getLogger(_LOGGER_NAME).info(message)


def configure_logging() -> None:
    """Configure default logging output. Called once by `run_prep.py::main`.

    Idempotent: `logging.basicConfig()` is a no-op once the root logger already
    has a handler, so calling this more than once does not stack duplicate
    handlers or re-emit every line twice.
    """
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
