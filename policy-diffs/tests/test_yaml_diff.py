# tests/test_yaml_diff.py
from presentation.yaml_diff import render_yaml_diff


def test_render_yaml_diff_marks_added_and_removed_lines():
    before = "response_window_days: 180\nrequired_evidence:\n  - txn_monitoring\n"
    after = "response_window_days: 120\nrequired_evidence:\n  - txn_monitoring\n  - video_kyc\n"

    html = render_yaml_diff(before, after)

    assert "diff-line-removed" in html and "180" in html
    assert "diff-line-added" in html and "120" in html
    assert "video_kyc" in html
