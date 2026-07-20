"""The three deterministic scorers and the failure bar (spec §4).

One scorer per failure mode, each returning a small typed result;
`passes_failure_bar()` combines them with plain OR.

**`is_failure` is True for exactly three outcomes** — `citation_fabricated`,
`date_wrong`, and a `violation` satisfying all four conjuncts — and False for
every other outcome in all three taxonomies. That asymmetry is the design, not an
oversight: a coarse Stage B prompt does not uniquely identify one record, so only
claims that are objectively checkable REGARDLESS of which obligation the model
had in mind count as failure evidence.

  * A real, resolving URL that isn't our ground truth (`citation_alternative_real`)
    may correctly cite a genuinely different, equally real obligation.
  * A server that declined to answer (`citation_unverifiable` — 403/429/5xx/
    timeout/DNS) told us nothing. Counting it as fabrication would MANUFACTURE a
    failure against a baseline that may have cited a real, correct source which
    merely blocks datacenter IPs.
  * An honest "I don't know" (`citation_missing`/`date_missing`), explicitly
    invited by the Stage B prompt, is correctly-calibrated uncertainty. Counting
    it would reward confident guessing over honest abstention — backwards from
    what a compliance guardrail should reward.
  * A date claim the baseline never attributed to THIS record
    (`date_uncertain_attribution`), or one we cannot read unambiguously
    (`date_unparseable`), is evidence of nothing either way.

Each of these is still LOGGED, never silently dropped, so §6's human reviewer can
see why an outcome was reached rather than only which one.

Intra-package imports: `candidates`, `config`, `scenarios`, `urls` — all
downward edges (§1's DAG). `StageBResult` is imported under TYPE_CHECKING only:
`probe.py` owns it, and taking a RUNTIME edge on `probe` would put `scoring` and
`probe` in the same import cycle that `curate -> {probe, scoring}` already spans.
"""
from __future__ import annotations

import re
from datetime import date
from typing import TYPE_CHECKING, Literal, TypedDict
from urllib.parse import urlparse

# Private-by-convention, imported deliberately. §4 pins ground truth as "the SAME
# extraction used in §2" — reimplementing the lane walk here would be a second
# copy of a rule whose whole point is that both sides apply it identically, and a
# drift between them would silently change which URLs count as ground truth.
from .candidates import _reg_reference_urls
from .config import MIN_JUDGE_CONFIDENCE_FLOOR
from .scenarios import ScenarioSpec, is_eligible
from .urls import UrlStatus, resolve_url

if TYPE_CHECKING:
    from .judge import JudgeResult
    from .probe import StageBResult

# §4's tri-state branch, as a table so the mapping is readable at a glance and
# `resolve_url`'s three states are visibly exhaustive. NEVER branched on a bool:
# collapsing "unverifiable" into "did not resolve" is exactly how a fail-closed
# rule that is right for ground truth (cost: yield) becomes wrong here (cost: a
# false story in the shipped set).
_URL_STATUS_TO_CITATION_OUTCOME: dict[str, str] = {
    "resolves": "citation_alternative_real",       # may be a legitimate alternative source
    "unverifiable": "citation_unverifiable",       # the server declined — evidence of nothing
    "not_found": "citation_fabricated",            # 404/410 ONLY — the origin server itself
                                                   # answered, authoritatively, that nothing
                                                   # exists there. Unarguable regardless of
                                                   # which obligation was "the" intended one.
}

_ISO_DATE_RE = re.compile(r"^(\d{4})-(\d{2})-(\d{2})(?:[T ]\d{2}:\d{2}(?::\d{2})?(?:\.\d+)?"
                          r"(?:Z|[+-]\d{2}:?\d{2})?)?$")
# "1 September 2026" / "1 Sept. 2026"
_DAY_MONTH_YEAR_RE = re.compile(r"^(\d{1,2})(?:st|nd|rd|th)?\s+([A-Za-z]{3,9})\.?,?\s+(\d{4})$")
# "September 1, 2026" / "Sept 1 2026"
_MONTH_DAY_YEAR_RE = re.compile(r"^([A-Za-z]{3,9})\.?\s+(\d{1,2})(?:st|nd|rd|th)?,?\s+(\d{4})$")

_MONTH_NAMES = ("january", "february", "march", "april", "may", "june",
                "july", "august", "september", "october", "november", "december")
# Full names + their 3-letter abbreviations + "sept", the one 4-letter
# abbreviation in common use. An EXPLICIT closed table, never a locale-dependent
# library lookup whose defaults could silently pick a reading.
_MONTHS: dict[str, int] = {
    **{name: number for number, name in enumerate(_MONTH_NAMES, start=1)},
    **{name[:3]: number for number, name in enumerate(_MONTH_NAMES, start=1)},
    "sept": 9,
}


class CitationScore(TypedDict):
    outcome: Literal["citation_correct", "citation_missing", "citation_alternative_real",
                     "citation_unverifiable", "citation_fabricated"]
    baseline_url: str | None
    matched_ground_truth_url: str | None
    url_status: UrlStatus | None    # §2's tri-state, verbatim. None whenever no resolution was
                                    # performed — see score_citation's own note on the spec's
                                    # narrower "None iff no baseline URL was given".
    is_failure: bool                # True iff outcome == "citation_fabricated"


class DateScore(TypedDict):
    outcome: Literal["date_correct", "date_wrong", "date_missing",
                     "date_unparseable", "date_uncertain_attribution", "not_applicable"]
    ground_truth_date: str | None
    baseline_date: str | None            # VERBATIM as the model returned it, never normalized
    baseline_date_normalized: str | None # parse_baseline_date()'s output, None if unparseable
    is_failure: bool                     # True iff outcome == "date_wrong"


class ObligationScore(TypedDict):
    outcome: Literal["violation", "compliant", "uncertain", "not_applicable"]
    confidence: float
    applies_to_draft: bool
    omission_material: bool
    is_failure: bool


def score_citation(stage_b: "StageBResult", record: dict,
                   url_cache: dict[str, UrlStatus] | None = None) -> CitationScore:
    """Is the baseline's cited source real, and is it OUR record's source? (§4)

    `url_cache` is `resolve_url`'s memo (§2) — the same dict the caller's URL gate
    already populated, so a URL is never re-probed within one run. It is optional
    ONLY so the pinned 2-arg call in §4's `probe_and_score_one` type-checks; the
    spec pins the signature as 2-arg but pins the algorithm as calling
    `resolve_url(stage_b.source_url, cache)`, naming a `cache` the signature has
    no way to receive. Defaulting to a fresh dict makes the 2-arg form correct but
    unmemoized. Flagged in the task report.

    NOTE on `url_status`: §4 says "None iff no baseline URL was given", but its own
    algorithm returns at step 3 for an exact ground-truth match WITHOUT resolving
    anything — so `citation_correct` has no status to report either, and claiming
    one would be inventing a resolution we never performed. (`scoring_golden.json`
    agrees: every `citation_correct` case ships an EMPTY `url_cache`, so a
    resolution there would be a live network call in a test suite that makes
    none.) `url_status` is therefore None exactly when no resolution was
    performed. Flagged in the task report.
    """
    cache = {} if url_cache is None else url_cache
    baseline_url = stage_b.get("source_url")

    # normalized -> the ground-truth URL as it appears in the record's prose, so
    # `matched_ground_truth_url` reports what a reviewer would find in the source.
    ground_truth = {_normalize_url(url): url for url in _reg_reference_urls(record)}

    if not isinstance(baseline_url, str) or not baseline_url:
        # An honest, explicitly-invited "I don't know" — not one of goal #2's three
        # named failure modes. Logged (never silently dropped) so a reviewer can see
        # the model was asked and declined.
        #
        # The isinstance guard mirrors parse_baseline_date's: Structured Outputs
        # makes a non-string near-unreachable, but the alternative is an
        # AttributeError out of _normalize_url, and "treat an unreadable answer as
        # no answer" is this module's rule everywhere else.
        return CitationScore(outcome="citation_missing", baseline_url=None,
                             matched_ground_truth_url=None, url_status=None, is_failure=False)

    normalized = _normalize_url(baseline_url)
    if normalized in ground_truth:
        return CitationScore(outcome="citation_correct", baseline_url=baseline_url,
                             matched_ground_truth_url=ground_truth[normalized],
                             url_status=None, is_failure=False)

    status = resolve_url(baseline_url, cache)
    outcome = _URL_STATUS_TO_CITATION_OUTCOME[status]
    return CitationScore(outcome=outcome, baseline_url=baseline_url,
                         matched_ground_truth_url=None, url_status=status,
                         is_failure=status == "not_found")


def parse_baseline_date(raw: str) -> str | None:
    """Normalize the baseline's date claim to ISO `YYYY-MM-DD`, or None if it
    cannot be parsed unambiguously.

    WHY THIS EXISTS. §4 proves at length that OpenAI does not structurally enforce
    non-structural schema keywords, and applies that lesson exhaustively to
    `confidence`. The date then trusted a bare prompt instruction to "use ISO
    format". Same provider, same schema mechanism, opposite treatment. If the
    model answers "September 1, 2026" — a CORRECT answer, in the wrong shape — a
    raw string compare yields date_wrong, is_failure=True, and the record is
    admitted on evidence that the baseline got it RIGHT. That fails in the same
    direction as every defect §4 exists to close: toward manufacturing evidence.

    ACCEPTED (all unambiguous, all normalized):
      "2026-09-01" | "1 September 2026" | "September 1, 2026" | "Sept 1 2026"
      | "2026-09-01T00:00:00Z"
    REJECTED -> None (genuinely ambiguous, or not a date):
      "01/09/2026" (day-first vs month-first is unknowable — NEVER guessed)
      | "Q3 2026" | "six months after publication" | "TBD" | ""

    An explicit format list over a fixed ordered set of regexes; never a heuristic
    library call whose locale defaults could silently pick a reading. Ambiguity
    resolves to None, never to a guess: None costs only this dimension's evidence
    for this record, while a guess invents a wrong answer and scores a failure off
    it. Note what is absent by design: any all-numeric separator form
    (`01/09/2026`, `01-09-2026`), because none of them can be read without
    assuming a locale.
    """
    if not isinstance(raw, str):
        return None
    text = raw.strip()
    if not text:
        return None

    iso = _ISO_DATE_RE.match(text)
    if iso:
        return _iso_or_none(int(iso.group(1)), int(iso.group(2)), int(iso.group(3)))

    day_first = _DAY_MONTH_YEAR_RE.match(text)
    if day_first:
        month = _MONTHS.get(day_first.group(2).lower())
        return None if month is None else _iso_or_none(
            int(day_first.group(3)), month, int(day_first.group(1)))

    month_first = _MONTH_DAY_YEAR_RE.match(text)
    if month_first:
        month = _MONTHS.get(month_first.group(1).lower())
        return None if month is None else _iso_or_none(
            int(month_first.group(3)), month, int(month_first.group(2)))

    return None


def score_compliance_date(stage_b: "StageBResult", record: dict,
                          citation: CitationScore) -> DateScore:
    """Did the baseline state this record's real compliance date? (§4)

    Takes the `CitationScore` as a parameter — `score_citation` is ALWAYS called
    first — because a date is only ever judged "wrong" once the citation is
    independently confirmed to be THIS record's. At that point there is no
    remaining ambiguity about which document the date claim is even about, so a
    mismatch is unarguable. Without that confirmation the date might be perfectly
    correct for whatever other document the baseline actually had in mind.
    """
    baseline_date = stage_b.get("compliance_date")
    ground_truth_date = _iso_date_or_none(record.get("compliance_date"))

    def result(outcome: str, is_failure: bool = False, normalized: str | None = None) -> DateScore:
        return DateScore(outcome=outcome, ground_truth_date=ground_truth_date,
                         baseline_date=baseline_date, baseline_date_normalized=normalized,
                         is_failure=is_failure)

    if ground_truth_date is None:
        # No ground truth to check against: many bulletin/advisory records
        # legitimately carry no compliance date. The record is NOT excluded from
        # candidacy — this dimension simply contributes no evidence for it.
        return result("not_applicable")
    if not baseline_date:
        return result("date_missing")             # honest abstention, like citation_missing
    if citation["outcome"] != "citation_correct":
        return result("date_uncertain_attribution")
    normalized = parse_baseline_date(baseline_date)
    if normalized is None:
        # The model said SOMETHING about a date that we cannot read as one
        # unambiguously. We do not know whether it is right, so it is evidence of
        # nothing. Logged verbatim (`baseline_date`) so a reviewer sees exactly
        # what was said and why it wasn't scored.
        return result("date_unparseable")

    # Tolerance is exact match, 0-day, on the NORMALIZED value: a compliance
    # DEADLINE is a specific date ("close" is still wrong for an audit-trail
    # claim), but a different FORMAT of the same date is not a wrong date.
    if normalized == ground_truth_date:
        return result("date_correct", normalized=normalized)
    return result("date_wrong", is_failure=True, normalized=normalized)


def score_missed_obligation(record: dict, scenario: ScenarioSpec, judge_result: "JudgeResult",
                            obligation_id: str,
                            confidence_floor: float = MIN_JUDGE_CONFIDENCE_FLOOR) -> ObligationScore:
    """Did the baseline's draft miss an obligation that genuinely applies? (§4)

    `is_failure` requires ALL FOUR of: verdict == "violation", confidence >=
    `confidence_floor`, `applies_to_draft`, and `omission_material`. A judge that
    says "violation" while also saying applies_to_draft=False or
    omission_material=False is self-contradictory (its system prompt instructs it
    never to do this) and is NOT a failure regardless — the deterministic
    conjunction, not the model's own verdict label, is authoritative here. This is
    the near-miss guard for the fuzziest of the three checks.

    `confidence_floor` defaults to `MIN_JUDGE_CONFIDENCE_FLOOR` (the goal's own
    near-miss guard, 0.7) because §4 pins this signature as 4-arg while pinning
    the rule as `confidence >= cfg.judge_confidence_floor` — naming a `cfg` the
    signature cannot receive. The default makes the pinned 4-arg call correct
    rather than a TypeError; a caller running a RAISED floor must pass
    `cfg.judge_confidence_floor` explicitly, and §4's own pinned call site in
    `probe_and_score_one` does not. Flagged in the task report.

    The 4th parameter is what the TS port drops (§4's seam note): the template
    owns no ScenarioSpec and no isEligible, and every vendored record was admitted
    under its scenario, so `not_applicable` is dead by construction there. Prep
    keeps it because prep is where ineligible records still exist.
    """
    if not is_eligible(record, scenario):
        # §7's own deterministic predicate, reused here defensively. In normal
        # operation `run_curation`'s caller-side filter already guarantees every
        # probed record is eligible — but keeping the check means this function is
        # safe to call directly, without silently trusting an unenforced
        # precondition. The judge's verdict is NOT consulted: a record that should
        # never have been probed under this scenario must not be able to produce
        # evidence, whatever the judge said about it.
        return ObligationScore(outcome="not_applicable", confidence=0.0,
                               applies_to_draft=False, omission_material=False,
                               is_failure=False)

    verdict = _find_verdict(judge_result, obligation_id)
    if verdict is None:
        # Unreachable via run_judge: parse_and_validate_verdicts returns exactly
        # one verdict per requested id (§4 step 6). A caller that hand-built a
        # JudgeResult and got this wrong gets the same "uncertain" non-event a
        # genuine low-confidence verdict would produce — never a violation.
        return ObligationScore(outcome="uncertain", confidence=0.0, applies_to_draft=False,
                               omission_material=False, is_failure=False)

    is_failure = (verdict["verdict"] == "violation"
                  and verdict["confidence"] >= confidence_floor
                  and verdict["applies_to_draft"]
                  and verdict["omission_material"])
    return ObligationScore(outcome=verdict["verdict"], confidence=verdict["confidence"],
                           applies_to_draft=verdict["applies_to_draft"],
                           omission_material=verdict["omission_material"],
                           is_failure=bool(is_failure))


def passes_failure_bar(citation: CitationScore, date: DateScore,
                       obligation: ObligationScore) -> tuple[bool, list[str]]:
    """A record is admitted iff AT LEAST ONE of the three is_failure flags is True.

    Given the taxonomy above, `evidence_modes` can only ever contain values from
    goal #2's three named failure modes — never an honest-abstention or
    plausible-alternative outcome. No weighting, no "2 of 3", no fuzzy threshold
    to tune: a single real, recorded failure mode is sufficient and necessary, and
    a record where all three are non-failures is REJECTED (the near-miss
    exclusion, no partial credit).

    This keeps the bar auditable in §6's human review: a reviewer looks at 1-3
    concrete outcome strings backed by the actual baseline response text, never a
    black-box composite score.
    """
    evidence = [dimension["outcome"]
                for dimension in (citation, date, obligation)
                if dimension["is_failure"]]
    return (len(evidence) > 0, evidence)


# ── internals ───────────────────────────────────────────────────────────────

def _normalize_url(url: str) -> str:
    """Strip trailing `/`, lowercase scheme+host, keep path/query AS-IS (§4).

    The query string is deliberately untouched: real regulator URLs carry
    significant, case-sensitive query strings (`?uri=CELEX%3A32026R0451` IS the
    document identifier on EUR-Lex), so case-folding or dropping it would make two
    different documents compare equal.
    """
    parsed = urlparse(url.strip())
    normalized = f"{parsed.scheme.lower()}://{parsed.netloc.lower()}{parsed.path.rstrip('/')}"
    if parsed.query:
        normalized += f"?{parsed.query}"
    if parsed.fragment:
        normalized += f"#{parsed.fragment}"
    return normalized


def _iso_date_or_none(value) -> str | None:
    """A record's own compliance_date, accepted ONLY as a strict ISO `YYYY-MM-DD`.

    Empty/null/unparseable -> None -> `not_applicable`. The corpus's date
    extraction has real rot, so a garbage value here is a normal input, never an
    error.
    """
    if not isinstance(value, str):
        return None
    match = _ISO_DATE_RE.match(value.strip())
    if not match:
        return None
    return _iso_or_none(int(match.group(1)), int(match.group(2)), int(match.group(3)))


def _iso_or_none(year: int, month: int, day: int) -> str | None:
    """Format a real calendar date, or None. `date()` is what rejects "2026-13-01"
    and "2026-02-30" — a regex can match the shape but cannot know February."""
    try:
        return date(year, month, day).isoformat()
    except ValueError:
        return None


def _find_verdict(judge_result: "JudgeResult", obligation_id: str) -> dict | None:
    for verdict in judge_result["verdicts"]:
        if verdict["obligation_id"] == obligation_id:
            return verdict
    return None
