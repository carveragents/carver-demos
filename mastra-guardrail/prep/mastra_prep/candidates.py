"""The candidate filter (spec §2) — goal #3's floor, in code.

**This module is an anti-padding boundary.** goal #11 names the ways a thin yield
could be "engineered around" and forbids each; the two that live here are closed
structurally rather than by discipline:

  * `ACTIONABLE_UPDATE_TYPES` is a `frozenset` CODE constant, not a `config.yaml`
    key — widening it requires a code change and review, never a runtime flag.
  * `impact_label == "high"` is a hardcoded literal comparison. There is no
    override path anywhere.

`SNAPSHOT_DATE` is likewise a code constant and never a config key (§13): an
earlier draft exposed it, which would have let `"3000-01-01"` silently defeat the
date-rot upper bound below — the whole point of that gate is that it is NOT a
tunable parameter.

**Not a leaf, deliberately** (orchestrator D12). §1:427 lists this module as a
LEAF; that listing is **stale**. `assert_cutoff_margin` needs `MODEL_CUTOFF` and
`CUTOFF_MARGIN_DAYS`, which are homed in `budget.py`, and `filter_candidates`
needs `extract_record`/`extract_urls`. All three edges point downward to leaves,
so the DAG holds (`test_imports.py` pins only `budget`/`logging_` as empty
leaves). The constants are IMPORTED, never copied: duplicating them would put the
cutoff derivation's inputs in two places, which is the exact drift V9 exists to
prevent.
"""
from __future__ import annotations

from datetime import date, timedelta
from typing import Iterable, Iterator

from .budget import CUTOFF_MARGIN_DAYS, CUTOFF_MARGIN_IS_INCLUSIVE, MODEL_CUTOFF
from .extract import extract_record
from .urls import extract_urls

ACTIONABLE_UPDATE_TYPES: frozenset[str] = frozenset({
    "enforcement", "advisory", "guidance", "bulletin",
    "final rule", "proposed rule", "comment request", "standard",
})
# Derived from goal.md's own measured pool breakdown: the 8 counts
# (2016+1637+1391+1235+864+645+439+33) sum to exactly 8,260 — the stated candidate
# pool — confirming this is the complete and correct allow-list, not independently
# invented. "press release"/"other"/"speech"/"event announcement"/"newsletter"/
# "insights"/"trend report" are excluded by omission (goal #3), which also removes
# the 98,826 `press release` noise records by construction. This set is a CODE
# CONSTANT, not a config.yaml key — see §6's anti-padding contract: widening it
# requires a code change and review, never a runtime flag.

CANDIDATE_CUTOFF_DATE = "2026-03-01"  # goal #3: gpt-5.6-sol cutoff (2026-02-16) + margin; hard floor, see §13
SNAPSHOT_DATE = "2026-07-11"          # goal.md's stated corpus snapshot date; hard ceiling, see below

# Parsed ONCE at import, not per record: `is_candidate` runs in the hot loop of a
# 212,845-record stream, where re-parsing both bounds every time is ~425,000
# redundant `fromisoformat` calls. It also turns a malformed constant from a
# per-record failure into an import-time one.
_CANDIDATE_CUTOFF = date.fromisoformat(CANDIDATE_CUTOFF_DATE)
_SNAPSHOT = date.fromisoformat(SNAPSHOT_DATE)

_REG_REFERENCE_KEYS = ("reg_rules", "reg_statutes", "reg_other_ref")


def _parse_iso_date(value) -> date | None:
    """`date.fromisoformat` with every garbage input the corpus can hand us
    folded into `None`. The corpus's date extraction has real rot (goal.md:
    Hijri calendars and bad parses spanning 1442 -> 2569), so a non-string, an
    empty string or an unparseable string is a normal input here, never an error.
    """
    if not isinstance(value, str):
        return None
    try:
        return date.fromisoformat(value)
    except ValueError:
        return None


def _reg_reference_urls(rec: dict) -> list[str]:
    """Every well-formed http(s) URL embedded in the record's reg-reference prose.

    The lanes are `list[str]` of free-text strings with an EMBEDDED URL (§2 —
    there is no separate structured URL field), and any lane may be absent or
    `None` on a real record.
    """
    urls: list[str] = []
    for key in _REG_REFERENCE_KEYS:
        lane = rec.get(key)
        if not isinstance(lane, list):
            continue
        for entry in lane:
            if isinstance(entry, str):
                urls.extend(extract_urls(entry))
    return urls


def is_candidate(rec: dict) -> tuple[bool, list[str]]:
    """Returns (passes, failed_predicate_names). Evaluates ALL predicates (does not
    short-circuit) so failed_predicate_names is complete for debugging/reporting.

    `rec` is an EXTRACTED record (`extract_record`'s flat output keys).

    Predicates:
      - reconciled_pub_valid is True AND reconciled_published_date is a parseable
        ISO date such that CANDIDATE_CUTOFF_DATE <= date <= SNAPSHOT_DATE.
        **Both bounds are load-bearing.** The lower bound alone (`>= cutoff`,
        `valid == true`) does NOT exclude corpus rot: `valid` is an upstream
        Carver flag of unknown exact semantics, and a garbage parse like year 2569
        is a "date" that can trivially be `>= 2026-03-01` and still be marked valid
        by whatever produced it. The upper bound (`<= SNAPSHOT_DATE`) is
        independent of what `valid` does or doesn't catch: no real record can be
        published after the snapshot was taken, so any date beyond 2026-07-11 is
        corpus rot by simple physical impossibility, full stop. Together the two
        bounds constrain every admitted date to a known ~4-month window, catching
        both the 1442-year underflow (fails the lower bound) and the 2569-year
        overflow (fails the upper bound) without relying on any assumption about
        `valid`'s coverage.
      - update_type (lowercased, stripped) in ACTIONABLE_UPDATE_TYPES
      - impact_label == "high"
      - key_requirements is a non-empty list
      - extract_urls() over (reg_rules + reg_statutes + reg_other_ref) yields >= 1
        well-formed http(s) URL. HTTP resolution is checked later, only for records
        that survive the probe (§2 "resolvable"), not at this filtering step (cost
        control: resolving 8,260 records' URLs up front is wasted work when <5%
        will ever be probed).
    """
    failed: list[str] = []

    published = _parse_iso_date(rec.get("reconciled_published_date"))
    if (
        rec.get("reconciled_pub_valid") is not True
        or published is None
        or published < _CANDIDATE_CUTOFF
        or published > _SNAPSHOT
    ):
        failed.append("reconciled_published_date")

    update_type = rec.get("update_type")
    if not isinstance(update_type, str) or update_type.strip().lower() not in ACTIONABLE_UPDATE_TYPES:
        failed.append("update_type")

    # A literal comparison, deliberately: goal #11 forbids admitting medium/low
    # impact to hit a number, and there is no override path for this line.
    if rec.get("impact_label") != "high":
        failed.append("impact_label")

    # goal #3 requires the record to actually STATE an obligation. A list of blank
    # strings is "non-empty" by §2's literal wording but carries nothing, and would
    # render an empty requirement into the probe's prompt — so require at least one
    # non-blank entry. Tightening only (goal #11: the filter is a floor).
    key_requirements = rec.get("key_requirements")
    if not isinstance(key_requirements, list) or not any(
        isinstance(entry, str) and entry.strip() for entry in key_requirements
    ):
        failed.append("key_requirements")

    if not _reg_reference_urls(rec):
        failed.append("reg_reference_url")

    return (not failed), failed


def filter_candidates(records: Iterable[dict]) -> Iterator[dict]:
    """Yields extract_record() output for records where is_candidate()[0] is True.

    Takes the RAW annotation stream (§3's pinned `main`:
    `filter_candidates(stream_annotations(cfg.annotations_path))`) and is a
    generator throughout — the real file is ~1.8 GB (goal #13).

    Deduplicates by `artifact_id` using a `seen: set[str]` local to this
    generator's call frame: "pure" in this spec means *referentially transparent
    given the same input stream* (same input order -> same output, no reads/writes
    outside the function's own locals), not "zero local state" — a local set that
    lives and dies with one call is consistent with that. THIS is the one and only
    place records are deduplicated; no other module (curate.py included) repeats
    or relies on a second dedup pass. First occurrence (in file order) wins; later
    duplicates of the same `artifact_id` are silently dropped.

    **An id is claimed by its first occurrence whether or not that occurrence
    passes the filter** — `seen.add` precedes the `is_candidate` gate deliberately.
    The alternative ("first *passing* occurrence wins") lets a later re-annotation
    admit a record the first copy failed (e.g. `impact_label` revised `medium` ->
    `high`), which WIDENS the pool: the padding direction, reached by accident.
    goal #11 says pay the yield in exactly this ambiguity. The cost is that `seen`
    holds every id in the stream (~212,845 short strings, tens of MB) rather than
    only the ~8,260 that pass — nothing against a 1.8 GB file.
    """
    seen: set[str] = set()
    for raw in records:
        extracted = extract_record(raw)
        if extracted is None:
            continue
        artifact_id = extracted["artifact_id"]
        if artifact_id in seen:
            continue
        seen.add(artifact_id)
        if not is_candidate(extracted)[0]:
            continue
        yield extracted


def _derived_floor() -> date:
    """The earliest defensible candidate date, derived from the PINNED MODEL.

    Read at call time, never cached: `MODEL_CUTOFF` moving is precisely the event
    this derivation exists to catch, and an import-time constant could not see it.

        floor = MODEL_CUTOFF + margin

    where the margin is `CUTOFF_MARGIN_DAYS` counted INCLUSIVELY of the cutoff date
    (the cutoff date is day 1, so the first eligible publication date is day 14).
    With the shipped constants: 2026-02-16 + 13 calendar days = **2026-03-01**,
    exactly the date goal #3 locks.

    `CUTOFF_MARGIN_IS_INCLUSIVE` is READ here rather than assumed, because §2's own
    escape hatch promises that flipping it to `False` is all it takes to reach the
    exclusive reading ("the change is one constant ... not a spec rewrite, because
    the derivation is now the mechanism rather than a literal"). Hardcoding `- 1`
    would make that promise false — a switch wired to nothing. Flipping it can only
    TIGHTEN the floor (to 2026-03-02), which is the direction goal #3 permits.
    """
    margin_days = CUTOFF_MARGIN_DAYS - 1 if CUTOFF_MARGIN_IS_INCLUSIVE else CUTOFF_MARGIN_DAYS
    return date.fromisoformat(MODEL_CUTOFF) + timedelta(days=margin_days)


def assert_cutoff_margin(candidate_cutoff_date: str) -> None:
    """Called by load_settings() (§13) on every run — the DERIVATION goal #3
    specifies, replacing the bare hard-coded floor.

    Raises ValueError unless BOTH of these are >= the derived floor (see
    `_derived_floor`):

      1. `CANDIDATE_CUTOFF_DATE` — the constant `is_candidate` ACTUALLY filters on.
      2. `candidate_cutoff_date`  — the value declared in `config.yaml`.

    **Checking (1) is not redundant, and omitting it reopens V9 one level down.**
    `is_candidate`'s pinned signature (§2:579) takes only `rec`, so the config key
    cannot reach the filter; the filter reads the module constant. Checking only
    (2) therefore guards a value nothing filters on, and produces this path:

        1. A forker takes §8's advertised one-line model swap; MODEL_CUTOFF moves later.
        2. Startup raises. The gate fires correctly.
        3. The operator does EXACTLY what the message says and re-derives
           `candidate_cutoff_date` in config.yaml.
        4. Startup passes -- and the filter still admits from the OLD cutoff,
           i.e. from inside the new model's training data.

    **Complying with the error message would convert a loud failure into a silent
    corruption** — goal #9's signature mode (*it would appear to succeed*).
    Verified by execution against the pre-fix code, not argued. `config.py`
    additionally asserts (1) == (2) so the two can never drift apart silently.

    Note the asymmetry, which is goal #3's own: this is a FLOOR. A model with an
    EARLIER cutoff lets you tighten the date (goal #3: "Tighten if the new cutoff
    is later"), but the >= means you may always be MORE conservative than
    derivation requires and never less.
    """
    floor = _derived_floor()

    # (1) The LIVE filter constant. Checked first: it is what actually selects the
    # pool, and no config edit can silence it.
    if _CANDIDATE_CUTOFF < floor:
        raise ValueError(
            f"candidates.py's CANDIDATE_CUTOFF_DATE={CANDIDATE_CUTOFF_DATE} is inside the "
            f"pinned model's knowledge window: budget.py's MODEL_CUTOFF={MODEL_CUTOFF} makes "
            f"the earliest defensible candidate date {floor} (cutoff + {CUTOFF_MARGIN_DAYS}d "
            f"margin, counted "
            f"{'inclusively' if CUTOFF_MARGIN_IS_INCLUSIVE else 'exclusively'} of the cutoff "
            f"date). This is the constant `is_candidate()` FILTERS on, so editing config.yaml "
            f"cannot fix it. If you changed the pinned model, goal #3 requires re-deriving "
            f"this date from the NEW model's documented cutoff — edit CANDIDATE_CUTOFF_DATE "
            f"in candidates.py AND candidate_cutoff_date in config.yaml — and re-running "
            f"curation, since the existing data/cleared/ was selected against the old model.")

    # (2) The value config.yaml declares.
    given = _parse_iso_date(candidate_cutoff_date)
    if given is None:
        raise ValueError(
            f"candidate_cutoff_date={candidate_cutoff_date!r} is not a parseable ISO date "
            f"(YYYY-MM-DD). It is the filter's hard floor (goal #3) and must be explicit.")
    if given < floor:
        raise ValueError(
            f"candidate_cutoff_date={candidate_cutoff_date} is inside the pinned model's "
            f"knowledge window: budget.py's MODEL_CUTOFF={MODEL_CUTOFF} makes the earliest "
            f"defensible candidate date {floor} (cutoff + {CUTOFF_MARGIN_DAYS}d margin, "
            f"counted {'inclusively' if CUTOFF_MARGIN_IS_INCLUSIVE else 'exclusively'} of the "
            f"cutoff date). If you changed the pinned model, goal #3 requires re-deriving this "
            f"date from the NEW model's documented cutoff — and re-running curation, since the "
            f"existing data/cleared/ was selected against the old model.")
