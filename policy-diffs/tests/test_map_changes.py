# tests/test_map_changes.py
from pipeline.map_changes import map_delta, MappingRecord, PolicyCatalogEntry
from pipeline.classify import ClassificationRecord


def test_map_delta_returns_affected_policies(mocker):
    mock_llm = mocker.MagicMock()
    mock_llm.complete_json.return_value = {
        "section_id": "10.2",
        "affected_policies": [
            {"policy": "bram_response", "rationale": "Response window obligation changes."},
            {"policy": "kyb_acquirer", "rationale": "New video-KYC requirement adds an acquirer obligation."},
        ],
    }

    catalog = [
        PolicyCatalogEntry(name="bram_response", description="BRAM investigation response", cited_sections=["10.2"]),
        PolicyCatalogEntry(name="fraud_monitoring", description="Fraud thresholds", cited_sections=["3.7"]),
        PolicyCatalogEntry(name="kyb_acquirer", description="Acquirer KYB obligations", cited_sections=["2.1"]),
    ]
    classification = ClassificationRecord(
        section_id="10.2",
        title="BRAM Investigation Process",
        summary="Response window cut; video KYC added.",
        materiality="substantive",
    )

    rec = map_delta(classification, before="…180 days…", after="…120 days; video KYC…", catalog=catalog, llm=mock_llm)

    assert isinstance(rec, MappingRecord)
    assert {p.policy for p in rec.affected_policies} == {"bram_response", "kyb_acquirer"}


def test_map_delta_handles_empty_affected(mocker):
    mock_llm = mocker.MagicMock()
    mock_llm.complete_json.return_value = {
        "section_id": "99.9",
        "affected_policies": [],
        "rationale": "Section concerns physical card embossing; no Credio surface.",
    }

    catalog = [PolicyCatalogEntry(name="x", description="", cited_sections=[])]
    classification = ClassificationRecord(
        section_id="99.9", title="Embossing", summary="", materiality="substantive"
    )
    rec = map_delta(classification, before="", after="", catalog=catalog, llm=mock_llm)
    assert rec.affected_policies == []
    assert rec.rationale and "physical card" in rec.rationale
