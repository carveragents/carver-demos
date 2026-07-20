"""Tests for `mastra_prep.urls` (spec §2's tri-state `resolve_url`).

`resolve_url` is TRI-STATE and this is load-bearing (goal.md, spec §2): the same
answer means opposite things to the ground-truth gate (a false negative *drops* a
record -> stay fail-closed) and to the baseline-citation scorer (a false negative
*admits* a record on fabricated evidence -> must not conflate link rot with a
regulator site 403'ing a datacenter IP). So:

  - "resolves"      -- 2xx/3xx. The document is there.
  - "not_found"     -- 404/410 ONLY. The server affirmatively said nothing is there.
  - "unverifiable"  -- everything else (403/429/5xx/timeout/connection error/
                       malformed URL). Evidence of nothing, never treated as
                       fabrication.

All HTTP is stubbed via `httpx.MockTransport` — zero network calls. `_no_real_network`
is an autouse guard: any test in this module that forgets to call
`_install_transport()` hits it and fails loudly instead of silently reaching the
real network.
"""
from __future__ import annotations

import httpx
import pytest

from mastra_prep.urls import extract_urls, resolve_url

# ---------------------------------------------------------------------------
# extract_urls -- against the real reg-reference prose (spec §2: free-text
# strings with an embedded, parenthesized URL; confirmed from the live sample
# record used to derive FIELD_MAP).
# ---------------------------------------------------------------------------

REAL_REG_RULE_PROSE = (
    "Commission Implementing Regulation (EU) 2021/451 of 17 December 2020 "
    "(https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX%3A32021R0451)"
)

REAL_REG_RULE_PROSE_WITH_NON_URL_PARENS = (
    "Banking Rules BR/16, BR/24, BR/31 issued under the Banking Act (Cap. 371) "
    "(https://www.mfsa.mt/legislation/banking-act/)"
)


def test_extract_urls_from_parenthetical_reg_reference_prose():
    urls = extract_urls(REAL_REG_RULE_PROSE)

    assert urls == [
        "https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX%3A32021R0451"
    ]


def test_extract_urls_ignores_non_url_parenthetical_text():
    urls = extract_urls(REAL_REG_RULE_PROSE_WITH_NON_URL_PARENS)

    assert urls == ["https://www.mfsa.mt/legislation/banking-act/"]


def test_extract_urls_finds_multiple_urls_in_one_string():
    text = (
        "See https://www.eba.europa.eu/regulation-and-policy/supervisory-reporting "
        "and also https://www.mfsa.mt/legislation/banking-act/ for context."
    )

    urls = extract_urls(text)

    assert urls == [
        "https://www.eba.europa.eu/regulation-and-policy/supervisory-reporting",
        "https://www.mfsa.mt/legislation/banking-act/",
    ]


def test_extract_urls_no_url_present():
    assert extract_urls("EBA Filing Rules v5.6 published May 2025, no link given.") == []


def test_extract_urls_empty_string():
    assert extract_urls("") == []


def test_extract_urls_strips_trailing_sentence_punctuation():
    text = "Full text at https://eur-lex.europa.eu/legal-content/EN/TXT/."

    assert extract_urls(text) == ["https://eur-lex.europa.eu/legal-content/EN/TXT/"]


def test_extract_urls_preserves_balanced_internal_parens():
    """A URL that legitimately contains parens (an eCFR section reference) must
    survive whole -- truncating it would plausibly turn a correct citation into
    one that 404s, manufacturing fabricated-citation evidence out of extraction
    truncation rather than an actual baseline error."""
    text = "See 12 CFR (https://www.ecfr.gov/current/title-12/section-1026.36(a))."

    urls = extract_urls(text)

    assert urls == ["https://www.ecfr.gov/current/title-12/section-1026.36(a)"]


def test_extract_urls_skips_unparseable_candidate_without_raising():
    """A mangled would-be IPv6 host in LLM-authored prose must not crash
    extraction -- it is simply not a URL this function can vouch for."""
    text = "Malformed reference at https://[not-a-valid-host and nothing else."

    assert extract_urls(text) == []


# ---------------------------------------------------------------------------
# resolve_url -- every UrlStatus branch, against httpx.MockTransport.
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _no_real_network(monkeypatch):
    """Guard against accidental real HTTP calls: install a transport that fails
    loudly for any request, so a `resolve_url` test that forgets to call
    `_install_transport()` errors instead of silently hitting the network."""
    import mastra_prep.urls as urls_module

    def _guard_handler(request: httpx.Request) -> httpx.Response:
        raise AssertionError(
            f"test attempted a real HTTP request to {request.url!r} without "
            "installing a MockTransport via _install_transport()"
        )

    monkeypatch.setattr(urls_module, "_client", httpx.Client(transport=httpx.MockTransport(_guard_handler)))


def _install_transport(monkeypatch, handler, call_log: list[tuple[str, str]] | None = None):
    """Point mastra_prep.urls's shared client at a MockTransport built from
    `handler`, so resolve_url makes zero real network calls. If `call_log` is
    given, every request's (method, url) is recorded in order before `handler`
    runs, so tests can assert not just the final status but the exact sequence
    of attempts (e.g. that HEAD really is tried before GET)."""
    import mastra_prep.urls as urls_module

    def logging_handler(request: httpx.Request) -> httpx.Response:
        if call_log is not None:
            call_log.append((request.method, str(request.url)))
        return handler(request)

    test_client = httpx.Client(transport=httpx.MockTransport(logging_handler))
    monkeypatch.setattr(urls_module, "_client", test_client)
    return test_client


def test_resolve_url_200_resolves(monkeypatch):
    call_log: list[tuple[str, str]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200)

    _install_transport(monkeypatch, handler, call_log)

    assert resolve_url("https://example.gov/doc", {}) == "resolves"
    assert call_log == [("HEAD", "https://example.gov/doc")]  # no GET needed


def test_resolve_url_redirect_301_then_404_is_not_found(monkeypatch):
    """A bare 301 alone would classify as "resolves" (2xx/3xx) even without
    following it -- so the only way to actually prove `follow_redirects=True`
    is honored is to make the FOLLOWED target return something else and assert
    THAT status wins."""

    def handler(request: httpx.Request) -> httpx.Response:
        if str(request.url) == "https://example.gov/old":
            return httpx.Response(301, headers={"Location": "https://example.gov/new"})
        return httpx.Response(404)

    call_log: list[tuple[str, str]] = []
    _install_transport(monkeypatch, handler, call_log)

    assert resolve_url("https://example.gov/old", {}) == "not_found"
    # A HEAD 404 still triggers the GET retry (§2: any non-resolving HEAD does),
    # so both the HEAD and GET attempts each follow the redirect in turn.
    assert call_log == [
        ("HEAD", "https://example.gov/old"),
        ("HEAD", "https://example.gov/new"),
        ("GET", "https://example.gov/old"),
        ("GET", "https://example.gov/new"),
    ]


@pytest.mark.parametrize("status_code", [404, 410])
def test_resolve_url_not_found_statuses(monkeypatch, status_code):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(status_code)

    _install_transport(monkeypatch, handler)

    assert resolve_url("https://example.gov/gone", {}) == "not_found"


@pytest.mark.parametrize("status_code", [403, 429, 500, 503])
def test_resolve_url_unverifiable_statuses(monkeypatch, status_code):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(status_code)

    _install_transport(monkeypatch, handler)

    assert resolve_url("https://example.gov/blocked", {}) == "unverifiable"


def test_resolve_url_timeout_is_unverifiable(monkeypatch):
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.TimeoutException("timed out", request=request)

    _install_transport(monkeypatch, handler)

    assert resolve_url("https://example.gov/slow", {}) == "unverifiable"


def test_resolve_url_dns_connection_error_is_unverifiable(monkeypatch):
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("name resolution failed", request=request)

    _install_transport(monkeypatch, handler)

    assert resolve_url("https://nonexistent.invalid/doc", {}) == "unverifiable"


def test_resolve_url_malformed_url_is_unverifiable_not_raised(monkeypatch):
    """httpx raises InvalidURL (NOT a RequestError subclass) for a URL like an
    unparseable port before ever dispatching to the transport -- resolve_url
    must swallow this into "unverifiable" rather than propagate it and abort a
    sweep over hundreds of records."""

    def handler(request: httpx.Request) -> httpx.Response:  # pragma: no cover
        return httpx.Response(200)

    _install_transport(monkeypatch, handler)

    assert resolve_url("https://example.gov:80x/doc", {}) == "unverifiable"


def test_resolve_url_head_rejected_get_succeeds_resolves(monkeypatch):
    """Some regulator sites reject HEAD outright -- resolve_url must retry with
    GET before concluding anything, and a successful GET must win. Asserts the
    exact method sequence, not just the final status, so a GET-only
    implementation cannot pass this by accident."""

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "HEAD":
            return httpx.Response(405)
        return httpx.Response(200)

    call_log: list[tuple[str, str]] = []
    _install_transport(monkeypatch, handler, call_log)

    assert resolve_url("https://example.gov/head-rejected", {}) == "resolves"
    assert [method for method, _ in call_log] == ["HEAD", "GET"]


def test_resolve_url_head_error_get_succeeds_resolves(monkeypatch):
    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "HEAD":
            raise httpx.ConnectError("HEAD not supported", request=request)
        return httpx.Response(200)

    call_log: list[tuple[str, str]] = []
    _install_transport(monkeypatch, handler, call_log)

    assert resolve_url("https://example.gov/head-errors", {}) == "resolves"
    assert [method for method, _ in call_log] == ["HEAD", "GET"]


def test_resolve_url_head_200_never_attempts_get(monkeypatch):
    """The mirror image of the retry tests: when HEAD resolves outright, GET
    must never be attempted at all (cost/latency discipline, and proof the
    "retry once" rule doesn't over-fire)."""

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200)

    call_log: list[tuple[str, str]] = []
    _install_transport(monkeypatch, handler, call_log)

    assert resolve_url("https://example.gov/head-fine", {}) == "resolves"
    assert [method for method, _ in call_log] == ["HEAD"]


def test_resolve_url_head_404_get_also_404_not_found(monkeypatch):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(404)

    call_log: list[tuple[str, str]] = []
    _install_transport(monkeypatch, handler, call_log)

    assert resolve_url("https://example.gov/really-gone", {}) == "not_found"
    assert [method for method, _ in call_log] == ["HEAD", "GET"]  # HEAD 404 still retries


def test_resolve_url_head_403_get_500_unverifiable_not_conflated_with_fabrication(monkeypatch):
    """The exact scenario the tri-state exists for: a regulator blocking our
    datacenter IP on HEAD, then erroring on GET too -- never 'not_found'."""

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "HEAD":
            return httpx.Response(403)
        return httpx.Response(500)

    _install_transport(monkeypatch, handler)

    assert resolve_url("https://regulator.example/blocked", {}) == "unverifiable"


def test_resolve_url_head_404_get_429_reports_last_attempt_unverifiable(monkeypatch):
    """A HEAD 404 does not short-circuit to "not_found" -- the GET retry's
    result is the one that ships, even when it downgrades an initially
    authoritative-looking HEAD answer. Documents and locks the "last attempt
    wins" rule stated in resolve_url's docstring."""

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "HEAD":
            return httpx.Response(404)
        return httpx.Response(429)

    _install_transport(monkeypatch, handler)

    assert resolve_url("https://example.gov/flaky", {}) == "unverifiable"


def test_resolve_url_cache_memoization(monkeypatch):
    call_log: list[tuple[str, str]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200)

    _install_transport(monkeypatch, handler, call_log)

    cache: dict = {}
    first = resolve_url("https://example.gov/cached", cache)
    second = resolve_url("https://example.gov/cached", cache)

    assert first == "resolves"
    assert second == "resolves"
    assert cache["https://example.gov/cached"] == "resolves"
    assert len(call_log) == 1  # second call served from cache, no new HTTP request


def test_resolve_url_cache_is_per_url(monkeypatch):
    def handler(request: httpx.Request) -> httpx.Response:
        if str(request.url) == "https://example.gov/present":
            return httpx.Response(200)
        return httpx.Response(404)

    _install_transport(monkeypatch, handler)

    cache: dict = {}
    assert resolve_url("https://example.gov/present", cache) == "resolves"
    assert resolve_url("https://example.gov/absent", cache) == "not_found"
    assert cache == {
        "https://example.gov/present": "resolves",
        "https://example.gov/absent": "not_found",
    }
