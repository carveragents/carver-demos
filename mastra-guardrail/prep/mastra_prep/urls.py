"""URL extraction and tri-state HTTP resolution over Carver's free-text
reg-reference prose (spec §2).

`resolve_url` is TRI-STATE, and this is load-bearing, not a stylistic choice. The
same HTTP answer means opposite things depending on which side of the pipeline
asks it (spec §2 / §4):

  - The ground-truth gate (§2) treats a false negative as DROPPING a record --
    fail-closed is correct there, so anything short of a live 2xx/3xx fails it.
  - The baseline-citation scorer (§4) treats a false negative as ADMITTING a
    record on fabricated-citation evidence -- collapsing "the regulator returned
    403 to our datacenter IP" into "this citation is fabricated" would manufacture
    failure evidence out of link rot, exactly the thing goal #2 forbids ("a record
    enters the set ONLY with recorded evidence of how the baseline failed it").

So `resolve_url` never collapses back to a bool. `"not_found"` is reserved for the
only two statuses that are an authoritative "nothing lives here" from the server
(404/410); everything else that fails to affirmatively resolve -- 403, 429, 5xx,
timeout, DNS/connection error, or even a malformed/unparseable URL -- is
`"unverifiable"`: evidence of nothing.
"""
from __future__ import annotations

import re
from typing import Literal
from urllib.parse import urlparse

import httpx

UrlStatus = Literal["resolves", "not_found", "unverifiable"]

# The only statuses that are an authoritative "the document is not there" from
# the server itself -- never inferred from anything else (timeouts, 5xx, blocks).
_NOT_FOUND_STATUSES = frozenset({404, 410})

# Matches an http(s) URL embedded in free-text prose (e.g. inside a parenthetical
# citation like "... (https://eur-lex.europa.eu/...)"). Parens are DELIBERATELY
# allowed inside the match (unlike whitespace/angle-brackets/quotes) because some
# real citation URLs legitimately contain them (eCFR section refs like
# ".../section-1026.36(a)", MediaWiki-style paths) -- excluding `()` outright
# would silently truncate those into a different, likely-404ing URL, which is
# exactly the "manufacture fabricated-citation evidence out of link rot" failure
# mode this module exists to prevent. The wrapping paren from prose like
# "(https://example.gov/doc)" is stripped afterward by `_trim_trailing_noise`'s
# balanced-paren check, not by the regex.
_URL_RE = re.compile(r"https?://[^\s<>\"']+", re.IGNORECASE)

# Simple trailing punctuation that can survive the regex when a URL is followed
# immediately (no space) by prose punctuation, e.g. "...see https://x.gov/doc."
_TRAILING_PUNCTUATION = ".,;:!?"

# Shared client. Tests inject a MockTransport by monkeypatching this module's
# `_client` attribute (see tests/test_urls.py) -- resolve_url's signature is
# pinned by spec §2 and carries no transport/client parameter of its own.
_client = httpx.Client()


def _trim_trailing_noise(candidate: str) -> str:
    """Strip prose punctuation and unbalanced wrapping parens from the tail of a
    regex-matched URL candidate, alternating between the two until neither
    applies. A trailing `)` is stripped only while it is NOT balanced by an
    opening `(` earlier in the candidate, so a URL that legitimately contains
    parens (`.../section-1026.36(a)`) keeps them, while the outer wrapping
    paren from prose like "(https://example.gov/doc)" is removed.
    """
    while candidate:
        if candidate[-1] in _TRAILING_PUNCTUATION:
            candidate = candidate[:-1]
            continue
        if candidate.endswith(")") and candidate.count("(") < candidate.count(")"):
            candidate = candidate[:-1]
            continue
        break
    return candidate


def extract_urls(text: str) -> list[str]:
    """Extract well-formed http(s) URLs embedded in free-text prose.

    Order-preserving; does not deduplicate (callers needing uniqueness do so
    themselves). Pure; no I/O. A regex match that `urlparse` cannot parse (e.g.
    an unbalanced `[` from a mangled would-be IPv6 host) is skipped rather than
    raised -- this function is a best-effort filter over LLM-authored prose, not
    a validator that trusts its input to be well-formed.
    """
    if not text:
        return []

    urls: list[str] = []
    for match in _URL_RE.findall(text):
        candidate = _trim_trailing_noise(match)
        try:
            parsed = urlparse(candidate)
        except ValueError:
            continue
        if parsed.scheme.lower() in ("http", "https") and parsed.netloc:
            urls.append(candidate)
    return urls


def _classify_status_code(status_code: int) -> UrlStatus:
    if 200 <= status_code < 400:
        return "resolves"
    if status_code in _NOT_FOUND_STATUSES:
        return "not_found"
    return "unverifiable"


def _attempt(method: str, url: str, timeout: float) -> UrlStatus:
    try:
        # `.stream()` reads only the status line and headers; the body is never
        # downloaded (regulator citations are frequently large PDFs, and only
        # the status code is ever consulted).
        with _client.stream(method, url, timeout=timeout, follow_redirects=True) as response:
            status_code = response.status_code
    except (httpx.RequestError, httpx.InvalidURL):
        # Timeout, DNS failure, connection refused, malformed URL, etc. -- the
        # server told us nothing at all, which is exactly "unverifiable", never
        # "not_found".
        return "unverifiable"
    return _classify_status_code(status_code)


def resolve_url(url: str, cache: dict[str, UrlStatus], timeout: float = 10.0) -> UrlStatus:
    """HEAD (then GET on anything short of resolving -- some regulator sites
    reject HEAD outright), then classify:

      "resolves"      -- 2xx/3xx. The document is there.
      "not_found"      -- 404 or 410, and ONLY those. The server answered,
                          authoritatively, that nothing lives at this URL.
      "unverifiable"   -- everything else: 403, 429, 5xx, timeout, DNS/connection
                          error. The server did not tell us whether the document
                          exists.

    A HEAD 404/410 still triggers the GET retry (some sites blanket-reject HEAD
    with a 4xx unrelated to whether the resource exists), so the returned status
    always reflects the LAST attempt made, not the first. This means a HEAD 404
    followed by a GET 429 is reported as "unverifiable", not "not_found" --
    deliberately: the final, most-informed answer wins, and the conservative
    direction here is the same one goal #2 requires (never letting a transient
    response manufacture "not_found" that the record didn't earn).

    Memoized in `cache` for the caller's run lifetime (the same regulator domain
    recurs across records) -- including "unverifiable" results, so a transient
    blip is not re-probed within one run; callers that need a fresh answer pass
    a fresh `cache`.
    """
    if url in cache:
        return cache[url]

    status = _attempt("HEAD", url, timeout)
    if status != "resolves":
        status = _attempt("GET", url, timeout)

    cache[url] = status
    return status
