# tests/test_credio_baseline.py
from pathlib import Path

import pytest
import yaml

ROOT = Path("credio-policies")
EXPECTED_POLICIES = [
    "fraud_monitoring",
    "bram_response",
    "ecp_thresholds",
    "kyb_acquirer",
    "chargeback_handling",
    "refund_policy",
    "ato_detection",
    "content_moderation",
]


@pytest.mark.parametrize("name", EXPECTED_POLICIES)
def test_policy_has_three_required_files(name):
    folder = ROOT / "policies" / name
    assert (folder / "policy.md").exists(), f"{name} missing policy.md"
    assert (folder / "rules.yaml").exists(), f"{name} missing rules.yaml"
    assert (folder / "source.yaml").exists(), f"{name} missing source.yaml"


@pytest.mark.parametrize("name", EXPECTED_POLICIES)
def test_rules_yaml_is_valid(name):
    data = yaml.safe_load((ROOT / "policies" / name / "rules.yaml").read_text())
    assert isinstance(data, dict) and data, f"{name} rules.yaml empty or not a mapping"


@pytest.mark.parametrize("name", EXPECTED_POLICIES)
def test_source_yaml_cites_at_least_one_section(name):
    data = yaml.safe_load((ROOT / "policies" / name / "source.yaml").read_text())
    assert "sections" in data and len(data["sections"]) >= 1
