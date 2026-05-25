# tests/test_pdf_render.py
import shutil
from pathlib import Path

import pytest

from pipeline.pdf_render import render_policy_pdf


pytestmark = pytest.mark.skipif(not shutil.which("pandoc"), reason="pandoc not installed")


def test_render_policy_pdf_produces_output(tmp_path: Path):
    md = tmp_path / "policy.md"
    md.write_text("# Title\n\nbody text\n")
    out = tmp_path / "policy.pdf"

    render_policy_pdf(md, out)

    assert out.exists() and out.stat().st_size > 0
