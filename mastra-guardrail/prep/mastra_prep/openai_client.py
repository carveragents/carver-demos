"""The ONLY place a key is read anywhere in `prep/` (spec §3, §15; goal #9).

`OPENAI_API_KEY` is the only secret this project has, in either half -- no Carver
key, no Anthropic key, no Mastra token. Every other module receives an already-
constructed client via dependency injection; nothing else calls `os.environ` for
a credential.

LEAF module: imports nothing else from `mastra_prep`
(`tests/test_imports.py::test_no_circular_imports` enforces this).

Constructing a client here never calls the API -- `make_client()` returns an
`openai.OpenAI` instance and nothing more. The first (and only) network call
against it happens in `probe.py`/`judge.py`, both of which take the client as an
injected argument rather than constructing their own.
"""
from __future__ import annotations

import logging
import os

from dotenv import load_dotenv
from openai import OpenAI

logger = logging.getLogger(__name__)


def load_env(dotenv_path: str) -> None:
    """Load `dotenv_path` into the process environment.

    A missing file is NOT fatal -- `OPENAI_API_KEY` may already be set in the
    shell environment (e.g. CI, a pre-configured dev box) -- so this logs a
    WARNING naming the path and proceeds rather than raising. Never overrides a
    variable already present in the environment (`override=False`), so an
    explicitly-exported shell value always wins over the file.

    `python-dotenv`'s own return value conflates two different situations --
    it reports "nothing loaded" both when the file is missing AND when it
    exists but is empty/comments-only/fully shadowed by `override=False` --
    so the warning is gated on `os.path.exists` directly rather than on
    `load_dotenv`'s return value, to keep the two cases worded correctly.
    """
    file_exists = os.path.exists(dotenv_path)
    load_dotenv(dotenv_path=dotenv_path, override=False)
    if not file_exists:
        logger.warning(
            "no .env file found at %s; relying on the shell environment for OPENAI_API_KEY",
            dotenv_path,
        )


def make_client() -> OpenAI:
    """Construct (never call) an `openai.OpenAI` client from `OPENAI_API_KEY`.

    Raises `KeyError` with a clear, variable-naming message if the key is
    absent OR blank -- the SDK's own default error only checks for `None`,
    so an `OPENAI_API_KEY=` line (the single most common misconfiguration
    after a missing variable) would otherwise silently produce a client that
    fails opaquely on its first real call instead of failing here, loudly,
    at construction. This function performs zero I/O beyond reading the
    environment: no request is ever issued here.
    """
    api_key = os.environ.get("OPENAI_API_KEY", "").strip()
    if not api_key:
        raise KeyError(
            "OPENAI_API_KEY is not set (or is blank). Set it in prep/.env "
            "(see .env.example) or export it in your shell -- it is the only "
            "secret this project reads (no Carver key, no Anthropic key, no "
            "Mastra token)."
        )
    return OpenAI(api_key=api_key)
