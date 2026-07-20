"""Tests for mastra_prep.logging_ — the progress channel (spec §1, §3).

`logging_.py` is a LEAF module (test_imports.py::test_no_circular_imports
enforces its intra-package import set is empty).
"""
from __future__ import annotations

import logging
import subprocess
import sys
from pathlib import Path

from mastra_prep.logging_ import configure_logging, log

PREP_DIR = Path(__file__).resolve().parents[1]


def test_log_emits_at_info(caplog):
    with caplog.at_level(logging.INFO, logger="mastra_prep"):
        log("hello from the curation loop")

    records = [r for r in caplog.records if r.name == "mastra_prep"]
    assert len(records) == 1
    assert records[0].levelno == logging.INFO
    assert records[0].getMessage() == "hello from the curation loop"


def test_log_does_not_emit_below_info(caplog):
    """A message logged via `log()` must not appear if the effective level is above INFO."""
    with caplog.at_level(logging.ERROR, logger="mastra_prep"):
        log("should be filtered out")

    records = [r for r in caplog.records if r.name == "mastra_prep"]
    assert records == []


def test_configure_logging_is_idempotent():
    """Calling configure_logging() twice must not stack a second handler.

    Run in a bare subprocess rather than in-process: pytest's own logging
    plugin re-attaches its own `LogCaptureHandler` to the root logger at the
    start of every test's "call" phase — *after* any in-process fixture setup
    runs — so asserting on `logging.getLogger().handlers` from inside a pytest
    test body would be measuring pytest's handler, not `configure_logging()`'s
    effect. A subprocess with no pytest plugin loaded gives an honest count.
    """
    script = (
        "import logging\n"
        "from mastra_prep.logging_ import configure_logging\n"
        "configure_logging()\n"
        "first = len(logging.getLogger().handlers)\n"
        "configure_logging()\n"
        "second = len(logging.getLogger().handlers)\n"
        "print(first, second)\n"
    )
    result = subprocess.run(
        [sys.executable, "-c", script],
        cwd=PREP_DIR,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    first, second = (int(n) for n in result.stdout.split())

    assert first == 1, "configure_logging() should install exactly one handler"
    assert second == first, "a second call must not stack a further handler"
