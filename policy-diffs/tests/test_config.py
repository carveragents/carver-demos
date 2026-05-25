# tests/test_config.py
import os
import textwrap
from pathlib import Path

from pipeline.config import load_config


def test_load_config_reads_default_model_and_stages(tmp_path: Path, monkeypatch):
    cfg_file = tmp_path / "models.yaml"
    cfg_file.write_text(textwrap.dedent("""
        provider: openai
        default_model: gpt-5.4-mini
        stages:
          classify:
            model: gpt-5.4-mini
          map:
            model: gpt-5.4-large
        api_key_env: OPENAI_API_KEY
    """).strip())
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")

    cfg = load_config(cfg_file)

    assert cfg.provider == "openai"
    assert cfg.model_for("classify") == "gpt-5.4-mini"
    assert cfg.model_for("map") == "gpt-5.4-large"
    assert cfg.model_for("propose") == "gpt-5.4-mini"  # falls back to default
    assert cfg.api_key == "sk-test"


def test_load_config_raises_when_api_key_env_missing(tmp_path: Path, monkeypatch):
    cfg_file = tmp_path / "models.yaml"
    cfg_file.write_text("provider: openai\ndefault_model: gpt-5.4-mini\nstages: {}\napi_key_env: OPENAI_API_KEY\n")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    import pytest
    with pytest.raises(RuntimeError, match="OPENAI_API_KEY"):
        load_config(cfg_file)
