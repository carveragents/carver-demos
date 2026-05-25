"""Tests for build/templates/close.html — Stage 3 refresh."""
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

REPO = Path(__file__).resolve().parent.parent


def _env() -> Environment:
    return Environment(
        loader=FileSystemLoader(REPO / "build" / "templates"),
        autoescape=select_autoescape(["html"]),
    )


def test_close_recaps_three_scenes() -> None:
    tpl = _env().get_template("close.html")
    out = tpl.render(base_url="")
    out_l = out.lower()
    assert "α" in out or "alpha" in out_l
    assert "γ" in out or "gamma" in out_l
    assert "β" in out or "beta" in out_l
    assert "carver" in out_l


def test_close_has_contact_cta() -> None:
    tpl = _env().get_template("close.html")
    out = tpl.render(base_url="")
    out_l = out.lower()
    assert "contact" in out_l or "request" in out_l or "talk" in out_l
