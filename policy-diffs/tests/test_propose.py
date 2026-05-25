# tests/test_propose.py
from pipeline.propose import propose_edit, FileEdit


def test_propose_edit_returns_new_contents(mocker):
    mock_llm = mocker.MagicMock()
    mock_llm.complete_json.return_value = {
        "new_contents": "response_window_days: 120\n",
        "change_summary": "Reduce BRAM response window to 120 days.",
    }

    edit = propose_edit(
        policy_path="policies/bram_response/rules.yaml",
        current_contents="response_window_days: 180\n",
        section_id="10.2",
        section_before="…180 days…",
        section_after="…120 days…",
        rationale="Response window obligation changed.",
        llm=mock_llm,
    )

    assert isinstance(edit, FileEdit)
    assert edit.policy_path == "policies/bram_response/rules.yaml"
    assert "120" in edit.new_contents and "180" not in edit.new_contents
    assert edit.change_summary


def test_propose_edit_truncates_long_section_text(mocker):
    mock_llm = mocker.MagicMock()
    mock_llm.complete_json.return_value = {
        "new_contents": "irrelevant",
        "change_summary": "x",
    }
    long_text = "A" * 50000

    propose_edit(
        policy_path="policies/x/policy.md",  # markdown path — no YAML validation
        current_contents="key: val\n",
        section_id="13.1.2",
        section_before=long_text,
        section_after=long_text,
        rationale="test",
        llm=mock_llm,
    )

    user_msg = mock_llm.complete_json.call_args.kwargs["user"]
    assert "[... section truncated" in user_msg
    assert len(user_msg) < 30000  # well under raw 100KB


def test_propose_edit_retries_on_invalid_yaml(mocker):
    mock_llm = mocker.MagicMock()
    mock_llm.complete_json.side_effect = [
        # First call: invalid YAML (bare text appended)
        {"new_contents": "key: val\n\nMastercard SPME §10.2", "change_summary": "x"},
        # Retry: valid YAML
        {"new_contents": "key: val2\n", "change_summary": "fixed"},
    ]

    edit = propose_edit(
        policy_path="policies/x/rules.yaml",
        current_contents="key: val\n",
        section_id="10.2",
        section_before="...",
        section_after="...",
        rationale="test",
        llm=mock_llm,
    )

    assert mock_llm.complete_json.call_count == 2
    assert "val2" in edit.new_contents
    # Confirm valid YAML
    import yaml
    assert isinstance(yaml.safe_load(edit.new_contents), dict)


def test_propose_edit_falls_back_when_yaml_invalid_twice(mocker):
    mock_llm = mocker.MagicMock()
    mock_llm.complete_json.side_effect = [
        {"new_contents": "key: val\n\nMastercard SPME §10.2", "change_summary": "x"},
        {"new_contents": "still: bad\norphan", "change_summary": "x"},
    ]

    edit = propose_edit(
        policy_path="policies/x/rules.yaml",
        current_contents="key: val\n",
        section_id="10.2",
        section_before="...",
        section_after="...",
        rationale="test",
        llm=mock_llm,
    )

    assert edit.new_contents == "key: val\n"  # fallback to current
    assert "Skipped" in edit.change_summary
