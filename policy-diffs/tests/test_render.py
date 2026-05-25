# tests/test_render.py
from pathlib import Path

from presentation.render import make_env, render_change, render_timeline, render_transition


# Minimal site config for unit tests — full config lives at config/sites/spme.yaml.
TEST_CONFIG = {
    "brand": {
        "client": "Acme Pay",
        "product": "Policy Updates",
        "tagline": "Powered by Carver Agents",
        "footer_note": "Test footer",
    },
    "artifact": {
        "short": "SPME",
        "long": "Mastercard SPME",
        "full_name": "Test Artifact",
        "publisher": "Mastercard",
        "citation": "Mastercard SPME",
        "sources_subdir": "spme",
    },
}


def test_make_env_loads_base_template():
    env = make_env()
    tmpl = env.get_template("_base.html.j2")
    assert tmpl is not None


def test_render_timeline_writes_html(tmp_path: Path):
    out = tmp_path / "timeline.html"
    render_timeline(
        out_path=out,
        config=TEST_CONFIG,
        start_date="2022-06",
        end_date="2025-05",
        transitions=[
            {
                "from_date": "2024-09",
                "to_date": "2025-05",
                "from_date_label": "Sep 2024",
                "to_date_label": "May 2025",
                "label": "Sep 2024 → May 2025",
                "slug": "2024-09_to_2025-05",
                "change_count": 4,
                "affected_policy_count": 5,
                "materiality_counts": {"breaking": 1, "substantive": 3, "clarifying": 0, "cosmetic": 0},
                "pct": {"breaking": 25.0, "substantive": 75.0, "clarifying": 0, "cosmetic": 0},
            }
        ],
        total_changes=4,
        total_breaking=1,
        total_policies=5,
        assets_prefix="../",
    )

    html = out.read_text()
    assert "Sep 2024 → May 2025" in html
    assert 'href="../transitions/2024-09_to_2025-05.html"' in html
    assert "1 breaking" in html and "3 substantive" in html
    assert "Policy update review" in html
    # Test config doesn't define a navigation block, so we don't assert on those


def test_render_transition_lists_changes(tmp_path: Path):
    out = tmp_path / "transitions" / "2024-09_to_2025-05.html"
    change = {
        "change_id": "2024-09_to_2025-05_10.2",
        "title": "BRAM response window tightened",
        "summary": "180→120 days; video KYC added.",
        "materiality": "substantive",
        "section_id": "10.2",
        "affected_paths": ["policies/bram_response/rules.yaml"],
        "policy_keys": ["bram_response"],
        "policy_display": [{"slug": "bram_response", "name": "BRAM Response"}],
        "search_text": "bram response window tightened 180 120 days video kyc",
    }
    render_transition(
        out_path=out,
        config=TEST_CONFIG,
        slug="2024-09_to_2025-05",
        from_date="2024-09",
        to_date="2025-05",
        changes=[change],
        groups=[{"materiality": "substantive", "changes": [change]}],
        materiality_counts={"breaking": 0, "substantive": 1, "clarifying": 0, "cosmetic": 0},
        policies=[{"slug": "bram_response", "name": "BRAM Response"}],
        assets_prefix="../",
    )

    html = out.read_text()
    assert "BRAM response window tightened" in html
    assert "10.2" in html
    assert 'href="../changes/2024-09_to_2025-05_10.2.html"' in html
    assert 'id="q"' in html  # search input
    assert "Sep 2024 → May 2025" in html
    assert "BRAM Response" in html  # human-readable policy name


def test_render_change_includes_three_tabs(tmp_path: Path):
    out = tmp_path / "changes" / "2024-09_to_2025-05_10.2.html"
    render_change(
        out_path=out,
        config=TEST_CONFIG,
        change={
            "change_id": "2024-09_to_2025-05_10.2",
            "title": "BRAM response window tightened",
            "summary": "180→120 days; video KYC added.",
            "materiality": "substantive",
            "section_id": "10.2",
            "transition_slug": "2024-09_to_2025-05",
            "transition_label": "Sep 2024 → May 2025",
            "section_compare": {
                "mode": "redline",
                "html": "<p>Acquirer must respond within <del class='del'>180</del><ins class='ins'>120</ins> days.</p>",
            },
            "affected_files": [
                {
                    "path": "policies/bram_response/rules.yaml",
                    "kind": "yaml",
                    "diff_html": "<pre class='yaml-diff'>diff html</pre>",
                    "full_redline_html": "",
                }
            ],
            "unified_diff": "--- a\n+++ b\n@@ ...",
            "rationale": "Window obligation changed.",
        },
        assets_prefix="../",
    )

    html = out.read_text()
    assert 'id="side-by-side"' in html
    assert 'id="redline"' in html
    assert 'id="raw-diff"' in html
    assert "BRAM response window tightened" in html
    assert "Window obligation changed." in html
