from pathlib import Path

from pipeline.change_record import AffectedFile, ChangeRecord, save_change_record
from presentation.render import render_site


# Minimal site config; the production config lives at config/sites/spme.yaml.
TEST_CONFIG = {
    "brand": {
        "client": "Credio",
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
    "overview": {
        "hero_eyebrow": "demo",
        "hero_title": "Test",
        "artifact_intro": "intro",
        "policies_intro": "intro",
        "provenance_note": "note",
    },
    "pipeline_steps": [
        {"title": "Detect", "body": "..."},
        {"title": "Classify", "body": "..."},
        {"title": "Propose", "body": "..."},
    ],
    "navigation": {"intro": "i", "paths": [{"title": "A", "body": "."}, {"title": "B", "body": "."}]},
    "disclaimers": ["d"],
    "acronyms": ["bram"],
    "glossary": [{"term": "SPME", "definition": "test"}],
}


def test_render_site_produces_three_layers(tmp_path: Path):
    artifacts = tmp_path / "artifacts" / "spme"
    transition_dir = artifacts / "2024-09_to_2025-05" / "changes"
    rec = ChangeRecord(
        change_id="2024-09_to_2025-05_10.2",
        transition_from="2024-09",
        transition_to="2025-05",
        section_id="10.2",
        section_title="BRAM Investigation Process",
        materiality="substantive",
        summary="180→120, video KYC.",
        section_before="…180 days…",
        section_after="…120 days, video KYC…",
        affected_files=[
            AffectedFile(
                path="policies/bram_response/rules.yaml",
                old_contents="response_window_days: 180\n",
                new_contents="response_window_days: 120\n",
                change_summary="Cut window",
            )
        ],
        rationale="Response window changed.",
    )
    save_change_record(rec, transition_dir / f"{rec.change_id}.json")

    dist = tmp_path / "dist"
    render_site(artifacts_root=artifacts, dist=dist, site_config=TEST_CONFIG)

    assert (dist / "timeline" / "index.html").exists()
    assert (dist / "transitions" / "2024-09_to_2025-05.html").exists()
    assert (dist / "changes" / "2024-09_to_2025-05_10.2.html").exists()
    timeline_html = (dist / "timeline" / "index.html").read_text()
    assert "2024-09" in timeline_html and "2025-05" in timeline_html
    assert "1 substantive" in timeline_html
