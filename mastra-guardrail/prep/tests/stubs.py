"""Injectable OpenAI stub clients for tests (no key, no network) — spec §14.

The stub CLASSES live here, not in `conftest.py`, so they can be imported
directly (`import stubs`) without tripping the `tests/` package self-import trap
documented in `docs/LESSONS.md`. `conftest.py` holds only thin pytest fixtures
that wrap these; it defines no stub of its own.

Every stub mimics the exact surface `prep/`'s pinned call lifecycle (spec §3)
touches, and nothing more:

    response = client.chat.completions.create(**payload)
    response.usage.model_dump() if response.usage is not None else None
    response.choices[0].message.content
    response.choices[0].finish_reason

`usage` is a pydantic `CompletionUsage` on the real SDK, so `StubUsage` exposes
`model_dump()` rather than being a dict — a stub that handed back a plain dict
would let a call site skip `.model_dump()` and still pass, then fail against the
real client.
"""
from __future__ import annotations

import types as _types


class StubUsage:
    """Mimics the SDK's pydantic CompletionUsage: `.model_dump()` -> mapping."""

    def __init__(self, prompt_tokens: int = 100, completion_tokens: int = 50):
        self.prompt_tokens = prompt_tokens
        self.completion_tokens = completion_tokens

    def model_dump(self) -> dict:
        return {
            "prompt_tokens": self.prompt_tokens,
            "completion_tokens": self.completion_tokens,
            "total_tokens": self.prompt_tokens + self.completion_tokens,
        }


class StubResponse:
    """Mimics an openai ChatCompletion: one choice + a usage report."""

    def __init__(self, content: str, finish_reason: str = "stop",
                 usage: StubUsage | None = None):
        self.choices = [
            _types.SimpleNamespace(
                message=_types.SimpleNamespace(content=content),
                finish_reason=finish_reason,
            )
        ]
        self.usage = usage if usage is not None else StubUsage()


class StubOpenAIClient:
    """Returns a canned response PER CALL INDEX, in the order provided.

    `responses` accepts, per entry, either a bare `str` (content, finish_reason
    "stop", default usage) or a fully-built `StubResponse` for cases that need a
    specific finish_reason/usage. A single str is shorthand for "same response
    every call" — unbounded, since most tests care about one call's shape rather
    than the count.

    Exhausting a finite list raises `AssertionError` rather than IndexError or a
    silent replay: a test that makes more calls than it canned is a test whose
    premise moved, and it should say so.
    """

    def __init__(self, responses: str | StubResponse | list[str | StubResponse]):
        self._repeat = not isinstance(responses, list)
        self._responses: list = [responses] if self._repeat else list(responses)
        self.call_count = 0
        self.calls: list[dict] = []
        self.chat = self
        self.completions = self

    def _next(self) -> StubResponse:
        idx = 0 if self._repeat else self.call_count
        if idx >= len(self._responses):
            raise AssertionError(
                f"StubOpenAIClient exhausted: call #{self.call_count + 1} was made but only "
                f"{len(self._responses)} response(s) were canned")
        item = self._responses[idx]
        return item if isinstance(item, StubResponse) else StubResponse(item)

    def create(self, **kwargs) -> StubResponse:
        response = self._next()
        self.call_count += 1
        self.calls.append(kwargs)
        return response


class RecordingStubClient(StubOpenAIClient):
    """Captures kwargs and ASSERTS the call's shape on every create().

    The assertions are the point — this is not a passive recorder. `temperature`
    is rejected because the pinned model does not accept it alongside
    `reasoning_effort`, and passing it is a runtime error against the real API
    that a passive stub would never surface.
    """

    def __init__(self, responses: str | StubResponse | list[str | StubResponse] = "{}",
                 expected_reasoning_effort: str | None = None,
                 expected_max_completion_tokens: int | None = None):
        super().__init__(responses)
        self._expected_effort = expected_reasoning_effort
        self._expected_max_tokens = expected_max_completion_tokens

    @property
    def last_kwargs(self) -> dict:
        if not self.calls:
            raise AssertionError("no create() call has been made yet")
        return self.calls[-1]

    def create(self, **kwargs) -> StubResponse:
        assert "temperature" not in kwargs, (
            "the pinned model rejects `temperature` alongside `reasoning_effort`; "
            f"call carried temperature={kwargs.get('temperature')!r}")
        if self._expected_effort is not None:
            assert kwargs.get("reasoning_effort") == self._expected_effort, (
                f"expected reasoning_effort={self._expected_effort!r}, "
                f"got {kwargs.get('reasoning_effort')!r}")
        if self._expected_max_tokens is not None:
            assert kwargs.get("max_completion_tokens") == self._expected_max_tokens, (
                f"expected max_completion_tokens={self._expected_max_tokens!r}, "
                f"got {kwargs.get('max_completion_tokens')!r}")
        return super().create(**kwargs)


class TruncatingStubClient(StubOpenAIClient):
    """Always returns a truncated response (`finish_reason="length"`)."""

    def __init__(self, content: str = ""):
        super().__init__(StubResponse(content=content, finish_reason="length"))


class RaisingStubClient(StubOpenAIClient):
    """Raises on create() to simulate an API/network error.

    `status_code` drives `terminal_for_exception`'s release-vs-finalize choice
    (budget.py's UNBILLED_STATUS_CODES), so tests set it to pick the branch.
    """

    def __init__(self, exc: Exception | None = None, status_code: int | None = None):
        super().__init__("")
        if exc is None:
            exc = Exception("simulated API error")
        if status_code is not None:
            exc.status_code = status_code
        self._exc = exc

    def create(self, **kwargs) -> StubResponse:
        self.call_count += 1
        self.calls.append(kwargs)
        raise self._exc


class SequencedStubClient(StubOpenAIClient):
    """Per-call-index responses where an entry may be an Exception to RAISE.

    Needed for the retry paths: "malformed JSON, then valid on retry" and
    "raises once, then succeeds" are both one call sequence, not two clients.
    """

    def create(self, **kwargs) -> StubResponse:
        idx = 0 if self._repeat else self.call_count
        if idx < len(self._responses) and isinstance(self._responses[idx], Exception):
            exc = self._responses[idx]
            self.call_count += 1
            self.calls.append(kwargs)
            raise exc
        return super().create(**kwargs)
