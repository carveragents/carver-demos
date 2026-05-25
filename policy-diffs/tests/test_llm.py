# tests/test_llm.py
from unittest.mock import MagicMock

import pytest

from pipeline.config import Config
from pipeline.llm import LLMClient


@pytest.fixture
def cfg():
    return Config(
        provider="openai",
        default_model="gpt-5.4-mini",
        stage_models={"map": "gpt-5.4-large"},
        api_key="sk-test",
    )


def test_complete_uses_per_stage_model(cfg, mocker):
    fake_openai = MagicMock()
    fake_openai.chat.completions.create.return_value = MagicMock(
        choices=[MagicMock(message=MagicMock(content='{"materiality":"substantive"}'))]
    )
    mocker.patch("pipeline.llm.OpenAI", return_value=fake_openai)

    client = LLMClient(cfg)
    out = client.complete_json(
        stage="map",
        system="you are an analyst",
        user="diff here",
        json_schema={"type": "object"},
    )

    assert out == {"materiality": "substantive"}
    call_kwargs = fake_openai.chat.completions.create.call_args.kwargs
    assert call_kwargs["model"] == "gpt-5.4-large"


def test_complete_uses_default_model_for_unspecified_stage(cfg, mocker):
    fake_openai = MagicMock()
    fake_openai.chat.completions.create.return_value = MagicMock(
        choices=[MagicMock(message=MagicMock(content='{}'))]
    )
    mocker.patch("pipeline.llm.OpenAI", return_value=fake_openai)

    client = LLMClient(cfg)
    client.complete_json(stage="classify", system="s", user="u", json_schema={"type": "object"})

    assert fake_openai.chat.completions.create.call_args.kwargs["model"] == "gpt-5.4-mini"
