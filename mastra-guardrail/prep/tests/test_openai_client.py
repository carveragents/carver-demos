"""Tests for `mastra_prep.openai_client` (spec §3, §15).

This is the ONLY place a key is read anywhere in `prep/` (goal #9): `OPENAI_API_KEY`,
and nothing else -- no Carver key, no Anthropic key, no Mastra token.

Hard constraint (goal, this task): ZERO billed API calls. `make_client()` only
CONSTRUCTS an `openai.OpenAI` client -- it must never call the API, and every test
here must pass with no key set in the real environment (each test controls its own
`OPENAI_API_KEY` via `monkeypatch`, never relying on -- or leaking into -- the
ambient shell environment).
"""
from __future__ import annotations

import logging
import os

import pytest
from openai import OpenAI

from mastra_prep.openai_client import load_env, make_client


@pytest.fixture(autouse=True)
def _isolated_openai_api_key(monkeypatch):
    """Every test starts with NO `OPENAI_API_KEY` in the environment, regardless
    of what the real shell happens to export -- so `make_client`'s absent-key
    path is actually exercised or explicitly overridden per test."""
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)


def test_load_env_missing_file_logs_warning_and_proceeds(tmp_path, caplog):
    """`.env` missing -> WARNING logged, no exception (the key may already be
    in the shell env -- a missing dotenv file is not fatal)."""
    missing_path = tmp_path / "does_not_exist.env"

    with caplog.at_level(logging.WARNING):
        load_env(str(missing_path))  # must not raise

    assert any(
        record.levelno == logging.WARNING and str(missing_path) in record.message
        for record in caplog.records
    )


def test_load_env_loads_existing_file_into_environment(tmp_path):
    env_path = tmp_path / ".env"
    env_path.write_text("OPENAI_API_KEY=sk-from-dotenv\n", encoding="utf-8")

    load_env(str(env_path))

    assert os.environ["OPENAI_API_KEY"] == "sk-from-dotenv"


def test_load_env_existing_but_empty_file_does_not_warn_missing(tmp_path, caplog):
    """An existing-but-empty `.env` is a different situation from a MISSING
    one -- `python-dotenv` itself reports "nothing loaded" for both, but the
    warning here is worded for a missing file specifically, so it must not
    fire when the file is actually present."""
    env_path = tmp_path / ".env"
    env_path.write_text("", encoding="utf-8")

    with caplog.at_level(logging.WARNING):
        load_env(str(env_path))

    assert not any(str(env_path) in record.message for record in caplog.records)


def test_load_env_never_overrides_an_explicit_shell_value(tmp_path, monkeypatch):
    """`override=False` (spec §15's documented behavior): a value already
    exported in the shell survives even when the `.env` file disagrees --
    verified here, not just asserted in a docstring."""
    monkeypatch.setenv("OPENAI_API_KEY", "sk-from-shell")
    env_path = tmp_path / ".env"
    env_path.write_text("OPENAI_API_KEY=sk-from-dotenv\n", encoding="utf-8")

    load_env(str(env_path))

    assert os.environ["OPENAI_API_KEY"] == "sk-from-shell"


def test_make_client_raises_keyerror_when_key_absent():
    with pytest.raises(KeyError):
        make_client()


def test_make_client_raises_keyerror_when_key_is_blank(monkeypatch):
    """`OPENAI_API_KEY=` (present but empty) is the single most common
    misconfiguration after a missing variable -- `"OPENAI_API_KEY" not in
    os.environ` alone would miss it and hand back a client that fails
    opaquely on its first real call instead of failing here, loudly."""
    monkeypatch.setenv("OPENAI_API_KEY", "")

    with pytest.raises(KeyError, match="OPENAI_API_KEY"):
        make_client()


def test_make_client_raises_keyerror_when_key_is_whitespace_only(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "   ")

    with pytest.raises(KeyError, match="OPENAI_API_KEY"):
        make_client()


def test_make_client_returns_client_without_calling_api(monkeypatch):
    """Construction only -- zero network calls. A client built here must be a
    real `openai.OpenAI` instance carrying exactly the injected key, and this
    test (like every test in this module) never issues a request."""
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-fake-key")

    client = make_client()

    assert isinstance(client, OpenAI)
    assert client.api_key == "sk-test-fake-key"


def test_make_client_error_message_names_the_variable():
    """A 'clear message' (spec §15) -- names OPENAI_API_KEY, not a generic string."""
    with pytest.raises(KeyError, match="OPENAI_API_KEY"):
        make_client()
