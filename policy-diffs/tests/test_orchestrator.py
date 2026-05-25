from pathlib import Path
from unittest.mock import MagicMock

import pytest

from pipeline.orchestrator import Orchestrator
from pipeline.config import Config


@pytest.fixture
def cfg():
    return Config(provider="openai", default_model="gpt-5.4-mini", stage_models={}, api_key="sk-test")


@pytest.fixture
def fake_credio_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "credio-policies"
    (repo / "policies" / "bram_response").mkdir(parents=True)
    (repo / "policies" / "bram_response" / "rules.yaml").write_text("response_window_days: 180\n")
    (repo / "policies" / "bram_response" / "policy.md").write_text("# BRAM\n\n180 days.\n")
    (repo / "policies" / "bram_response" / "source.yaml").write_text("sections: [{id: '10.2'}]\n")
    return repo


def test_run_transition_emits_change_record(cfg, fake_credio_repo, tmp_path, mocker):
    fake_llm = MagicMock()
    fake_llm.complete_json.side_effect = [
        {"section_id": "10.2", "title": "BRAM", "summary": "180→120; video KYC", "materiality": "substantive"},
        {"section_id": "10.2", "affected_policies": [{"policy": "bram_response", "rationale": "window changed"}]},
        {"new_contents": "response_window_days: 120\n", "change_summary": "Cut window"},
        {"new_contents": "# BRAM\n\n120 days.\n", "change_summary": "Update prose"},
    ]
    mocker.patch("pipeline.llm.LLMClient", return_value=fake_llm)

    artifacts_dir = tmp_path / "artifacts"
    orch = Orchestrator(
        cfg=cfg,
        credio_repo=fake_credio_repo,
        artifacts_dir=artifacts_dir,
        llm=fake_llm,
    )

    from pipeline.diff import SectionDelta
    deltas = [SectionDelta(
        section_id="10.2", title="BRAM", kind="modified",
        before="…180 days…", after="…120 days; video KYC…",
    )]

    result = orch.run_transition(
        transition_from="2024-09",
        transition_to="2025-05",
        deltas=deltas,
    )

    assert len(result.change_records) == 1
    rec = result.change_records[0]
    assert rec.section_id == "10.2"
    assert any(f.path == "policies/bram_response/rules.yaml" for f in rec.affected_files)

    rec_path = artifacts_dir / "spme" / "2024-09_to_2025-05" / "changes" / "2024-09_to_2025-05_10.2.json"
    assert rec_path.exists()


def test_run_transition_warns_on_hallucinated_policy(cfg, fake_credio_repo, tmp_path, mocker, capsys):
    fake_llm = MagicMock()
    fake_llm.complete_json.side_effect = [
        {"section_id": "10.2", "title": "BRAM", "summary": "x", "materiality": "substantive"},
        {"section_id": "10.2", "affected_policies": [{"policy": "made_up_policy", "rationale": "fake"}]},
    ]
    artifacts_dir = tmp_path / "artifacts"
    orch = Orchestrator(cfg=cfg, credio_repo=fake_credio_repo, artifacts_dir=artifacts_dir, llm=fake_llm)

    from pipeline.diff import SectionDelta
    deltas = [SectionDelta(section_id="10.2", title="BRAM", kind="modified",
                           before="…", after="…")]

    result = orch.run_transition(
        transition_from="2024-09", transition_to="2025-05",
        deltas=deltas,
    )

    captured = capsys.readouterr()
    assert "made_up_policy" in captured.err
    assert result.change_records == []


def test_run_transition_does_not_mutate_disk(cfg, fake_credio_repo, tmp_path, mocker):
    """Working tree files stay pinned to v1 baseline; cumulative state is in-memory only."""
    fake_llm = MagicMock()
    fake_llm.complete_json.side_effect = [
        {"section_id": "10.2", "title": "BRAM", "summary": "x", "materiality": "substantive"},
        {"section_id": "10.2", "affected_policies": [{"policy": "bram_response", "rationale": "x"}]},
        {"new_contents": "response_window_days: 120\n", "change_summary": "Cut"},
        {"new_contents": "# BRAM\n\n120 days.\n", "change_summary": "Update"},
    ]
    artifacts_dir = tmp_path / "artifacts"
    orch = Orchestrator(cfg=cfg, credio_repo=fake_credio_repo, artifacts_dir=artifacts_dir, llm=fake_llm)

    from pipeline.diff import SectionDelta
    deltas = [SectionDelta(section_id="10.2", title="BRAM", kind="modified",
                           before="180 days", after="120 days")]

    orch.run_transition(transition_from="2024-09", transition_to="2025-05", deltas=deltas)

    # Disk files unchanged (still v1 baseline)
    assert (fake_credio_repo / "policies" / "bram_response" / "rules.yaml").read_text() == "response_window_days: 180\n"
    assert (fake_credio_repo / "policies" / "bram_response" / "policy.md").read_text() == "# BRAM\n\n180 days.\n"
    # In-memory state captured the edits
    assert "120" in orch._state["policies/bram_response/rules.yaml"]


def test_sequential_transitions_share_cumulative_state(cfg, fake_credio_repo, tmp_path, mocker):
    """Transition N's proposer sees the file as transition N-1 left it (not the v1 baseline)."""
    fake_llm = MagicMock()
    fake_llm.complete_json.side_effect = [
        # Transition 1: classify, map, propose rules.yaml, propose policy.md
        {"section_id": "10.2", "title": "BRAM", "summary": "x", "materiality": "substantive"},
        {"section_id": "10.2", "affected_policies": [{"policy": "bram_response", "rationale": "x"}]},
        {"new_contents": "response_window_days: 120\n", "change_summary": "Cut to 120"},
        {"new_contents": "# BRAM\n\n120 days.\n", "change_summary": "Update prose"},
        # Transition 2: classify, map, propose rules.yaml, propose policy.md
        {"section_id": "10.3", "title": "BRAM2", "summary": "y", "materiality": "substantive"},
        {"section_id": "10.3", "affected_policies": [{"policy": "bram_response", "rationale": "y"}]},
        {"new_contents": "response_window_days: 90\n", "change_summary": "Cut to 90"},
        {"new_contents": "# BRAM\n\n90 days.\n", "change_summary": "Update prose again"},
    ]
    orch = Orchestrator(cfg=cfg, credio_repo=fake_credio_repo, artifacts_dir=tmp_path / "artifacts", llm=fake_llm)

    from pipeline.diff import SectionDelta
    d1 = [SectionDelta("10.2", "BRAM", "modified", "180 days", "120 days")]
    d2 = [SectionDelta("10.3", "BRAM2", "modified", "120 days", "90 days")]

    orch.run_transition(transition_from="2023-01", transition_to="2024-01", deltas=d1)
    orch.run_transition(transition_from="2024-01", transition_to="2025-01", deltas=d2)

    # Transition 2's propose calls (calls 7 + 8) must have received the post-transition-1 contents,
    # not the disk baseline. Confirm by inspecting current_contents in those calls.
    call7 = fake_llm.complete_json.call_args_list[6]  # propose rules.yaml in transition 2
    assert "120" in call7.kwargs["user"]
    assert "180" not in call7.kwargs["user"]
