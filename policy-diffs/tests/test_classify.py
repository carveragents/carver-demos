# tests/test_classify.py
from pipeline.classify import classify_delta, ClassificationRecord
from pipeline.diff import SectionDelta


def test_classify_delta_returns_record(mocker):
    mock_llm = mocker.MagicMock()
    mock_llm.complete_json.return_value = {
        "section_id": "10.2",
        "title": "BRAM Investigation Process",
        "summary": "Response window reduced from 180 to 120 days; new video-KYC evidence requirement added.",
        "materiality": "substantive",
    }

    delta = SectionDelta(
        section_id="10.2",
        title="BRAM Investigation Process",
        kind="modified",
        before="180 days",
        after="120 days, video KYC required",
    )

    rec = classify_delta(delta, llm=mock_llm)

    assert isinstance(rec, ClassificationRecord)
    assert rec.section_id == "10.2"
    assert rec.materiality == "substantive"
    assert "180" in rec.summary or "120" in rec.summary

    call = mock_llm.complete_json.call_args.kwargs
    assert call["stage"] == "classify"
    assert "180 days" in call["user"] and "120 days" in call["user"]
