# tests/test_redline.py
from presentation.redline import render_prose_redline


def test_render_prose_redline_marks_changes():
    before = "Acquirer must respond within 180 days."
    after = "Acquirer must respond within 120 days, including video-KYC."

    html = render_prose_redline(before, after)

    assert "<del" in html and "180" in html
    assert "<ins" in html and "120" in html
    assert "video-KYC" in html


def test_render_prose_redline_handles_no_changes():
    text = "Acquirer must respond within 180 days."
    html = render_prose_redline(text, text)
    assert "<ins" not in html and "<del" not in html
