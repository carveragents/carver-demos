# tests/test_change_record.py
import json
from pathlib import Path

from pipeline.change_record import ChangeRecord, AffectedFile, save_change_record, load_change_record


def test_change_record_round_trip(tmp_path: Path):
    rec = ChangeRecord(
        change_id="2024-09_to_2025-05_10.2",
        transition_from="2024-09",
        transition_to="2025-05",
        section_id="10.2",
        section_title="BRAM Investigation Process",
        materiality="substantive",
        summary="180→120, video KYC.",
        section_before="180 days",
        section_after="120 days, video KYC",
        affected_files=[
            AffectedFile(
                path="policies/bram_response/rules.yaml",
                old_contents="response_window_days: 180\n",
                new_contents="response_window_days: 120\n",
                change_summary="Cut window",
            )
        ],
        rationale="Response window obligation changed.",
    )

    path = tmp_path / "rec.json"
    save_change_record(rec, path)
    loaded = load_change_record(path)

    assert loaded == rec
    raw = json.loads(path.read_text())
    assert raw["change_id"] == rec.change_id
