"""Smoke test: confirms pytest + the venv resolve correctly."""


def test_python_version() -> None:
    import sys

    assert sys.version_info >= (3, 10), f"Python {sys.version_info} too old"


def test_core_imports() -> None:
    import carver_feeds  # noqa: F401
    import httpx
    import jinja2
    import yaml  # noqa: F401

    assert jinja2.__version__
    assert httpx.__version__
