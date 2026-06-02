"""OpenAI client wrapper with disk cache, structured outputs, and graceful
degradation. Synchronous API; parallelize at caller using ThreadPoolExecutor.

Cache layout: cache_root/<purpose>/<cache_key>.json. Each entry stores both
the request fingerprint and the response so a human can diff during review.

Env vars (loaded from `.env` via python-dotenv at module import):
- OPENAI_API_KEY      required for any live call
- PRED_ORACLE_LLM_MODEL_FAST   default 'gpt-5-mini'
- PRED_ORACLE_LLM_MODEL_DEEP   default 'gpt-5'
"""
from __future__ import annotations

import hashlib
import json
import os
import time
from pathlib import Path
from typing import Any

try:
    from dotenv import load_dotenv

    _REPO_ROOT = Path(__file__).resolve().parent.parent
    # .env lives at the worktree root (one level above pred-oracle/)
    _env_path = _REPO_ROOT / ".env"
    if not _env_path.exists():
        _env_path = _REPO_ROOT.parent / ".env"
    load_dotenv(_env_path)
except ImportError:
    pass

try:
    from openai import OpenAI

    _OPENAI_INSTALLED = True
except ImportError:
    OpenAI = None  # type: ignore[assignment,misc]
    _OPENAI_INSTALLED = False


DEFAULT_CACHE_ROOT = Path(__file__).resolve().parent / "_cache" / "llm"
MODEL_FAST = os.environ.get("PRED_ORACLE_LLM_MODEL_FAST", "gpt-5-mini")
MODEL_DEEP = os.environ.get("PRED_ORACLE_LLM_MODEL_DEEP", "gpt-5")


def is_available() -> bool:
    """True if OPENAI_API_KEY is set AND openai package is importable."""
    return _OPENAI_INSTALLED and bool(os.environ.get("OPENAI_API_KEY"))


def cache_key_for(*, model: str, system: str, user: str, schema: dict[str, Any]) -> str:
    """Stable SHA-256 hash of the request inputs."""
    payload = json.dumps(
        {"model": model, "system": system, "user": user, "schema": schema},
        sort_keys=True,
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:32]


def complete_json(
    *,
    purpose: str,
    cache_key: str,
    model: str,
    system: str,
    user: str,
    schema: dict[str, Any],
    cache_root: Path | None = None,
    max_retries: int = 3,
) -> dict[str, Any] | None:
    """Return parsed JSON response, hitting disk cache before calling OpenAI.

    Returns None on any failure (no key, no install, all retries exhausted).
    Callers must handle None via documented fallbacks.
    """
    cache_root = cache_root or DEFAULT_CACHE_ROOT
    cache_path = cache_root / purpose / f"{cache_key}.json"
    if cache_path.exists():
        try:
            entry = json.loads(cache_path.read_text())
            return entry.get("response")  # type: ignore[no-any-return]
        except json.JSONDecodeError:
            pass  # corrupted cache → re-fetch

    if not is_available():
        return None

    assert OpenAI is not None  # for type-checker, guarded by is_available
    client = OpenAI()

    last_err: Exception | None = None
    for attempt in range(max_retries):
        try:
            resp = client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
                response_format={
                    "type": "json_schema",
                    "json_schema": {
                        "name": purpose,
                        "schema": schema,
                        "strict": True,
                    },
                },
            )
            content = resp.choices[0].message.content or "{}"
            parsed = json.loads(content)
            cache_path.parent.mkdir(parents=True, exist_ok=True)
            cache_path.write_text(json.dumps({
                "request": {"model": model, "system": system, "user": user, "schema": schema},
                "response": parsed,
            }, indent=2))
            return parsed  # type: ignore[no-any-return]
        except Exception as e:  # noqa: BLE001
            last_err = e
            time.sleep(2 ** attempt)

    print(f"WARN: llm call failed for purpose={purpose} key={cache_key}: {last_err}")
    return None
