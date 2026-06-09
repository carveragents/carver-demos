"""Smoke test for apps/cockpit.py.

Uses Streamlit's headless AppTest runner to verify the entire cockpit
runs without raising an exception. No live API calls — the app reads the
cached parquet + catalog CSVs only.
"""

from streamlit.testing.v1 import AppTest


def test_cockpit_app_runs_without_exception():
    """The cockpit app loads and renders all tabs without any Python exception."""
    at = AppTest.from_file("apps/cockpit.py", default_timeout=90).run()
    assert not at.exception, (
        f"Cockpit raised an exception: {at.exception}"
    )
