"""Post-decision generation of `template/`'s scenario-locked constants (spec §7).

`template/src/config.ts`'s `DEMO_TRIGGER_RECORD_ID`, `firmProfile.ts`'s
`DEMO_FIRM_PROFILE`, `agents/baselineAgent.ts`'s `SCENARIO_PERSONA_INSTRUCTIONS`
and `scenario/prompts.ts` in full are **never hand-written against an assumed
winner** (rubric #5). They are produced here, mechanically and deterministically,
run once by hand (`run_prep.py --emit-template-config`) after `decide_scenario`
and after curation/review have both completed. String templating only — this
module never executes or imports TypeScript; it writes ordinary text files, which
is why `template/`'s zero-dependency-on-`prep/` guarantee (goal #1) still holds.

**Two gates stand between a decision and an emitted demo, and both fail loudly.**

  1. **Evidence TYPE gates candidacy before strength ranks it** (step 2). Only
     `predicts_stage_a_violation` records can be the trigger. A record admitted
     purely for `citation_fabricated`/`date_wrong` proves a Stage B KNOWLEDGE
     failure — the baseline does not know this regulation — which licenses no
     expectation whatsoever about whether a *draft* violates the obligation.
     Choosing one produces a demo that reliably does nothing, for a reason no
     amount of debugging the guardrail would reveal, because the guardrail would
     be behaving correctly. An empty candidate set is a REPORTABLE FINDING, never
     a condition to engineer around by relaxing this rule (§7's Goal issue).
  2. **Narrowing is re-checked, not assumed** (steps 4 and 7). §9a proves every
     eligible record is RELEVANT to its own generated profile; it does NOT prove
     the record wins one of the five ranked slots — five same-tag records with
     nearer compliance dates outrank it on `urgency_weight`. So step 4 is a real
     filter, and step 7 re-runs it against the profile actually being emitted.

**Idempotent replacement** (orchestrator D2). §7 step 8 says "render the fragment
and write it into its owning `.ts` file" without saying what happens when that
file already holds a previously generated declaration *plus* hand-authored code —
which is exactly the state of the Phase-8 re-run over the real dataset. Blind
appending emits a duplicate `export const`; blind overwriting deletes the
hand-authored half of the file. So: replace the declaration in place if it is
there, insert it if it is not. `scenario/prompts.ts` alone is written whole — it
is generated end to end and has no hand-authored half to preserve.

Intra-package imports: `schema` (`predicts_stage_a_violation`, `SNAPSHOT_DATE`),
`scenarios` and `probe` (§8's "both generated from `scenarios.py`'s single
source" — the alternative is retyping the bucket vocabulary, the mapping, the
task template, the negative controls and the update-type phrases into a `.tmpl`,
which is the exact cross-seam drift the generation contract exists to prevent).
§1's dependency row for this module lists only `stdlib, schema,
scenario_decision`; that row predates §8's resolution of `scenario/prompts.ts` as
generated and is stale — flagged in the task report. Both added edges point
strictly downward (`scenarios` is a leaf, `probe` is level 1), so §1's DAG holds
and `test_imports.py::test_no_circular_imports` stays green. `ScenarioDecision`
is imported under TYPE_CHECKING only: it is used purely as an annotation, and
`from __future__ import annotations` makes every annotation here a string that is
never evaluated at import time.
"""
from __future__ import annotations

import json
import re
from datetime import date
from pathlib import Path
from typing import TYPE_CHECKING, Literal, TypedDict

from .probe import (
    RECENCY_PHRASE,
    UPDATE_TYPE_PHRASES,
    _DEFAULT_UPDATE_TYPE_PHRASE,
)
from .scenarios import (
    _DEFAULT_DOMAIN_BUCKET,
    _SCENARIO_KEYWORD_BUCKETS,
    COUNTRY_CODE_TO_NAME,
    DOMAIN_BUCKETS,
    INDUSTRY_TAG_TO_BUCKET,
    SCENARIOS,
    build_negative_control_prompts,
)
from .schema import SNAPSHOT_DATE, ClearedRecord, predicts_stage_a_violation

if TYPE_CHECKING:
    from .scenario_decision import ScenarioDecision

_PREP_DIR = Path(__file__).resolve().parent.parent
_TEMPLATES_DIR = _PREP_DIR / "templates"
_PROMPTS_DIR = _PREP_DIR / "prompts"

# The real target. `emit_template_config` takes an override so tests can emit
# into a tmp dir; nothing else ever passes it.
DEFAULT_TEMPLATE_SRC_DIR = _PREP_DIR.parent / "template" / "src"

# §9a's `urgencyWeight` boundary: <= 180 days from SNAPSHOT_DATE scores 2.
URGENCY_NEAR_DAYS = 180

# `a.compliance_date ?? "9999-99-99"` — the sentinel that sorts nulls last (§9a).
# Not a real date, deliberately: it is a STRING comparison, and this sorts after
# every ISO date without pretending to be one.
_NULL_DATE_SENTINEL = "9999-99-99"

_SNAPSHOT = date.fromisoformat(SNAPSHOT_DATE)


class TemplateConfigBundle(TypedDict):
    winner: Literal["A", "B"]
    trigger_record_id: str
    trigger_candidate_count: int   # len(trigger_candidates) from step 2 — always >= 1 on a
                                   # successful emit; printed by the CLI and echoed into the
                                   # README so the demo's evidentiary basis is visible
    firm_profile: dict
    written_files: list[str]       # relative paths under ../template/src/


def emit_template_config(
    cleared_records: list[ClearedRecord],
    decision: "ScenarioDecision",
    *,
    template_src_dir: Path | str | None = None,
) -> TemplateConfigBundle:
    """Generate and write `template/`'s four scenario-locked `.ts` targets (§7).

    `template_src_dir` is not in §7's pinned signature: the algorithm needs a
    write root and the pinned parameters cannot supply one. It is optional and
    defaults to the real `../template/src`, so the caller `run_prep.py
    --emit-template-config` passes nothing and gets the specified behavior; only
    tests override it. Defaulting in the admitting direction here means the
    default is the production path, not a sandbox.

    Raises:
        ValueError: if the decision named no winner (step 0), if the winning
            scenario cleared no records (step 1), if none of them carries
            human-confirmed `missed_obligation` evidence (step 2), or if no
            candidate survives narrowing under its own profile (step 4). Every
            one of these must fail at generation time rather than silently ship
            a demo that cannot fire — so nothing is written. Also raised by step
            8 if a target file holds an unterminated declaration of a generated
            symbol, rather than guess at how much of it to replace.
        AssertionError: if the emitted profile does not surface the trigger
            (step 7).
    """
    src_dir = Path(template_src_dir) if template_src_dir is not None else DEFAULT_TEMPLATE_SRC_DIR
    winner = decision["winner"]

    # 0 — `winner is None` IFF the trial was insufficient (§7). Reachable: this
    # is its own CLI branch (`--emit-template-config`), run by hand against
    # whatever decision the last run wrote. Named exactly rather than left to
    # fall through step 1 as "0 cleared records for scenario None", which is
    # loud but misnames the cause.
    if winner is None:
        raise ValueError(
            f"cannot generate a demo from a {decision['outcome']!r} decision — no "
            f"scenario won. The trial did not probe enough records to read a winner "
            f"out of; re-run the trial rather than emitting against an arm that "
            f"never ran."
        )

    # 1 — the winner's cleared records.
    winner_records = [r for r in cleared_records if r["scenario"] == winner]
    if not winner_records:
        raise ValueError(
            f"0 cleared records for scenario {winner} of {len(cleared_records)} total — "
            f"there is nothing to build a demo around. This must fail at generation "
            f"time, not silently ship an empty demo."
        )

    # 2 — evidence TYPE gates candidacy. See the module docstring.
    trigger_candidates = [r for r in winner_records if predicts_stage_a_violation(r)]
    if not trigger_candidates:
        raise ValueError(
            f"{len(winner_records)} cleared records for scenario {winner}, but 0 carry "
            f"human-confirmed missed_obligation evidence. The demo requires a record "
            f"whose evidence proves the baseline's DRAFT omits a material, applicable "
            f"obligation; citation/date evidence proves a Stage B knowledge failure and "
            f"cannot support goal success criterion #2 (a visible tripwire block on a "
            f"draft)."
        )

    # 3 — the mechanical "strongest single record" rule: most distinct failure
    # modes first, ties broken by id ASCENDING. `sorted()`'s default direction,
    # NOT `max()` with a plain tuple key — which picks the lexicographically
    # LARGEST id on a tie, the opposite of what "ascending" means.
    ordered = sorted(trigger_candidates, key=lambda r: (-len(r["baseline_failures"]), r["id"]))

    # 4 — the strongest candidate that DEMONSTRABLY survives narrowing under its
    # own generated profile. A fixed order, first match wins, no tie left unbroken.
    trigger = _first_surviving_narrowing(ordered, cleared_records)
    if trigger is None:
        raise ValueError(
            f"none of the {len(trigger_candidates)} trigger candidate(s) for scenario "
            f"{winner} survives narrowing under its own generated firm profile — every "
            f"one is crowded out of narrowObligationsPure's five ranked slots by "
            f"same-tag records with nearer compliance dates. Emitting would ship a demo "
            f"that never fires."
        )

    # 5 — REUSES §8's exact firmProfileForRecord logic. Step 4 already
    # established that narrowing surfaces `trigger` under this exact profile.
    firm_profile = firm_profile_for_record(trigger)

    # 6 — §7's table, the winning column only. A lookup; no new content invented.
    scenario = SCENARIOS[winner]

    # 7 — the same check step 4 selected on, re-run against the profile actually
    # being emitted. Redundant by construction, kept deliberately: it costs
    # nothing and it is the one assertion standing between "the demo works" and
    # "the demo silently doesn't fire".
    #
    # `raise AssertionError`, not `assert`: §7 pins the exception TYPE, which
    # this keeps, but a bare `assert` vanishes under `python -O` — and a gate
    # that a flag can switch off is not a gate (schema.py::to_json's reasoning).
    if trigger["id"] not in narrow_obligations_pure(firm_profile, cleared_records):
        raise AssertionError(
            f"refusing to emit: trigger {trigger['id']!r} does not survive narrowing "
            f"under the firm profile being emitted ({firm_profile!r})"
        )

    # 8 — render and write.
    written_files = _write_targets(src_dir, trigger, firm_profile, scenario)

    return TemplateConfigBundle(
        winner=winner,
        trigger_record_id=trigger["id"],
        trigger_candidate_count=len(trigger_candidates),
        firm_profile=firm_profile,
        written_files=written_files,
    )


def firm_profile_for_record(record: ClearedRecord) -> dict:
    """The Python port of §8's `firmProfileForRecord` — the synthetic firm
    profile a record narrow-matches by construction.

    **camelCase keys**, matching `FirmProfileSchema` exactly, even though
    `ClearedRecord` itself is snake_case: `emit_template_config` serializes this
    dict straight into a TS object literal via `json.dumps()`, with no separate
    key-transform step. `impactedFunctions` is authoritative over §9a's
    pseudocode, which reads `firm.impacted_functions` (orchestrator D18) — in
    TypeScript that misspelling is not an error, it is `undefined`, so narrowing
    would silently lose one of its two required predicates while still firing,
    still blocking, and still looking correct.

    GUARANTEE (§9a's proof, made true by §7's two narrowability preconditions):
    `record` satisfies BOTH of `narrow_obligations_pure`'s REQUIRED predicates
    against `firm_profile_for_record(record)`. That is RELEVANCE, not a top-5
    slot — nothing here relies on more.
    """
    jurisdiction = record["jurisdiction"]
    industry = list(record["impacted_business"]["industry"])
    country = jurisdiction["country"]
    return {
        # `?? ""` — null-coalescing, not truthiness: mirrors the TS exactly.
        "jurisdiction": {"country": country if country is not None else "",
                         "bloc": jurisdiction["bloc"]},
        "sector": industry[0] if industry else "",
        "industry": industry,
        "size": "medium",
        "impactedFunctions": list(record["impacted_functions"]),
    }


def narrow_obligations_pure(firm_profile: dict, cleared_records: list[ClearedRecord]) -> list[str]:
    """The Python port of §9a's `narrowObligationsPure` — same required
    predicates, same ranking, same SNAPSHOT_DATE-pinned urgency weight, same
    top-5 slice, same tie-breaks.

    **Required vs. ranking, not one blended score.** An earlier draft used a
    single additive `matchScore >= 1` gate, under which a lone weak signal (in
    particular `scope === "supranational"` matching unconditionally) could admit
    an obligation with no real connection to the firm — and the top-5 truncation
    could then discard an actually-relevant record in favour of that noise. Both
    required predicates must hold: jurisdiction (a firm outside a record's
    jurisdiction is categorically irrelevant) AND industry-or-function overlap.
    Only records clearing both gates compete for the five slots, so truncation
    discards only genuinely-lower-priority *relevant* records.

    Kept in lockstep with the TypeScript original by `narrowing_golden.json`
    (duplicated byte-for-byte on both sides), never by importing across the
    language boundary — goal #1 forbids the import, and a silent divergence here
    would be worse than the bug it replaces.

    **THREE CONTRACTS THE GOLDEN DOES NOT LOCK — read before writing the TS.**
    §9a names `daysBetween`, `overlapCount` and `intersects` and defines none of
    them, and no golden case distinguishes the readings below. They are stated
    here so the P6 implementer copies a decision instead of re-deriving one, and
    they are flagged for an orchestrator ruling (adding the missing cases means
    editing BOTH copies of a shared fixture, which is not this task's to do):

      1. `_overlap_count` iterates the RECORD's tags against a SET of the firm's.
         Direction is observable, because `firm_profile_for_record` always
         duplicates `industry[0]` into `sector`: iterating the firm's tags
         instead double-counts that duplicate and can flip top-5 membership.
      2. `_urgency_weight`'s day delta is SIGNED. A compliance date already in
         the past is near (weight 2), not far — `Math.abs` would make an overdue
         obligation rank as if it were years away. Past dates are routine: §2's
         cutoff bounds the PUBLICATION date, never the compliance date.
      3. An unparseable compliance date scores 1 — JS `NaN <= 180` is `false`.
    """
    tags = _industry_tags(firm_profile)
    functions = firm_profile["impactedFunctions"]

    relevant = [
        record for record in cleared_records
        if _jurisdiction_matches(record, firm_profile)                       # REQUIRED
        and (_intersects(record["impacted_business"]["industry"], tags)      # REQUIRED
             or _intersects(record["impacted_functions"], functions))
    ]

    def sort_key(record: ClearedRecord) -> tuple[int, str, str]:
        rank = (_overlap_count(record["impacted_business"]["industry"], tags)
                + _overlap_count(record["impacted_functions"], functions)
                + _urgency_weight(record["compliance_date"]))
        return (
            -rank,                                                  # higher rank first
            record["compliance_date"] or _NULL_DATE_SENTINEL,       # sooner deadline, nulls last
            record["id"],                                           # final deterministic tie-break
        )

    return [record["id"] for record in sorted(relevant, key=sort_key)[:5]]


# ── §9a's internals ─────────────────────────────────────────────────────────

def _jurisdiction_matches(record: ClearedRecord, firm: dict) -> bool:
    """A supranational/bloc-scoped record matches ONLY if its OWN bloc value
    equals the firm's bloc — `scope == "supranational"` alone is never
    sufficient. An EU AI Act record's bloc is "EU"; it matches a firm whose
    bloc is "EU", never one whose bloc is None or a different bloc."""
    record_jurisdiction = record["jurisdiction"]
    country = record_jurisdiction["country"]
    if country and country == firm["jurisdiction"]["country"]:
        return True
    bloc = record_jurisdiction["bloc"]
    if bloc and bloc == firm["jurisdiction"]["bloc"]:
        return True
    return False


def _industry_tags(firm: dict) -> list[str]:
    """`[...firm.industry, firm.sector]` — sector folded into the
    industry-overlap signal (§9a)."""
    return [*firm["industry"], firm["sector"]]


def _intersects(left: list[str], right: list[str]) -> bool:
    """Case-insensitive — tag capitalization is not consistent across the corpus."""
    return bool({value.lower() for value in left} & {value.lower() for value in right})


def _overlap_count(left: list[str], right: list[str]) -> int:
    lowered_right = {value.lower() for value in right}
    return sum(1 for value in left if value.lower() in lowered_right)


def _urgency_weight(compliance_date: str | None) -> int:
    """Relative to SNAPSHOT_DATE, NOT `date.today()` — the corpus snapshot date
    is already this project's fixed reference point for "now" (§2, §13). Using
    the wall-clock would make narrowing rank a record differently depending on
    what day the demo or `npm test` happened to run.

    An UNPARSEABLE date scores 1, not 0 and not a raise — the reading that
    matches the TypeScript, where `daysBetween` over `new Date("Q3 2026")` is
    `NaN` and `NaN <= 180` is `false`. The corpus's date extraction has real rot
    (goal.md: Hijri calendars and bad parses spanning 1442 -> 2569), and nothing
    on this path closes the gap — `validate_cleared_record` type-checks
    `compliance_date` without parsing it, so a rotten value clears review and
    ships. Since narrowing sorts the ENTIRE cleared set, one such record
    anywhere would otherwise kill the generator with an opaque
    `Invalid isoformat string` raised from inside a sort key. `candidates.py`
    and `scoring.py` both fold the same rot for the same reason.
    """
    if not compliance_date:
        return 0
    parsed = _parse_iso_date(compliance_date)
    if parsed is None:
        return 1
    return 2 if (parsed - _SNAPSHOT).days <= URGENCY_NEAR_DAYS else 1


def _parse_iso_date(value: str) -> date | None:
    """`date.fromisoformat`, with every garbage input the corpus can hand us
    folded into None — a normal input here, never an error."""
    try:
        return date.fromisoformat(value)
    except (TypeError, ValueError):
        return None


# ── step 4 ──────────────────────────────────────────────────────────────────

def _first_surviving_narrowing(
    ordered: list[ClearedRecord], cleared_records: list[ClearedRecord]
) -> ClearedRecord | None:
    for record in ordered:
        if record["id"] in narrow_obligations_pure(firm_profile_for_record(record),
                                                   cleared_records):
            return record
    return None


# ── step 8: rendering ───────────────────────────────────────────────────────

_PLACEHOLDER = re.compile(r"\{\{([A-Z0-9_]+)\}\}")


def _render(template: str, substitutions: dict[str, str]) -> str:
    """Substitute `{{KEY}}` in ONE pass, leaving unknown placeholders untouched.

    One pass, not a `str.replace` chain: `prompts_ts_fragment.tmpl` renders TS
    that *itself* carries `{{DOMAIN_PHRASE}}`/`{{JURISDICTION_PHRASE}}` (the
    Stage A task template the generated `buildStageAPrompt` substitutes at
    runtime), and a substituted value must never be re-scanned for placeholders.
    """
    return _PLACEHOLDER.sub(
        lambda match: substitutions.get(match.group(1), match.group(0)), template
    )


def _read_template(name: str) -> str:
    return (_TEMPLATES_DIR / name).read_text(encoding="utf-8")


def _json_literal(value, *, indent: int | None = None) -> str:
    """Valid TS object-literal syntax is a strict subset of JSON, so no format
    conversion is needed. `ensure_ascii=False` per D11 — the wire is UTF-8 and
    `\\uXXXX` soup in shipped source helps nobody."""
    return json.dumps(value, indent=indent, ensure_ascii=False)


def _write_targets(src_dir: Path, trigger: ClearedRecord, firm_profile: dict,
                   scenario: dict) -> list[str]:
    """Render all four fragments, then write. The three fragment targets are
    written by idempotent replacement; `scenario/prompts.ts` is written whole."""
    config_ts = _render(_read_template("config_ts_fragment.tmpl"),
                        {"TRIGGER_RECORD_ID": _json_literal(trigger["id"])[1:-1]})
    firm_profile_ts = _render(_read_template("firm_profile_ts_fragment.tmpl"),
                              {"FIRM_PROFILE_JSON": _json_literal(firm_profile, indent=2)})
    persona_ts = _render(_read_template("persona_ts_fragment.tmpl"),
                         {"PERSONA_INSTRUCTIONS_JSON": _json_literal(_persona_instructions(scenario))})
    prompts_ts = _render(_read_template("prompts_ts_fragment.tmpl"),
                         _prompts_substitutions(scenario))

    for relative_path, symbol, rendered in (
        ("config.ts", "DEMO_TRIGGER_RECORD_ID", config_ts),
        ("firmProfile.ts", "DEMO_FIRM_PROFILE", firm_profile_ts),
        ("agents/baselineAgent.ts", "SCENARIO_PERSONA_INSTRUCTIONS", persona_ts),
    ):
        _replace_or_insert_declaration(src_dir / relative_path, symbol, rendered)

    _write_whole(src_dir / "scenario" / "prompts.ts", prompts_ts)

    return ["config.ts", "firmProfile.ts", "agents/baselineAgent.ts", "scenario/prompts.ts"]


def _persona_instructions(scenario: dict) -> str:
    """The winning scenario's business-persona instructions — `stage_a_system.md`
    with PERSONA/COMPANY substituted, i.e. the EXACT system prompt prep probed
    the baseline with. Re-typing it template-side is how the two halves end up
    measuring two different agents."""
    return _render(
        (_PROMPTS_DIR / "stage_a_system.md").read_text(encoding="utf-8"),
        {"PERSONA": scenario["PERSONA"], "COMPANY": scenario["COMPANY"]},
    )


def _prompts_substitutions(scenario: dict) -> dict[str, str]:
    """Everything `scenario/prompts.ts` needs, all of it read from prep's own
    single sources (§8) — never retyped into the `.tmpl`.

    `INDUSTRY_TAG_TO_BUCKET` ships WHOLE (both scenarios' tags) while
    `DOMAIN_BUCKETS` ships FLAT (the winner's five phrases only): the mapping is
    scenario-free and `buckets_golden.json`'s `tag_bucket_cases` are asserted
    against every entry on both sides of the seam, whereas the vocabulary is the
    shipped scenario's, since goal #10 ships exactly one.
    """
    scenario_id = scenario["id"]
    return {
        "SCENARIO_ID": scenario_id,
        "DOMAIN_BUCKETS_JSON": _json_literal(list(DOMAIN_BUCKETS[scenario_id]), indent=2),
        "INDUSTRY_TAG_TO_BUCKET_JSON": _json_literal(INDUSTRY_TAG_TO_BUCKET, indent=2),
        "SCENARIO_TASK_TEMPLATES_JSON": _json_literal(dict(scenario), indent=2),
        "NEGATIVE_CONTROL_PROMPTS_JSON": _json_literal(
            build_negative_control_prompts(scenario), indent=2),
        "DEFAULT_DOMAIN_BUCKET_JSON": _json_literal(_DEFAULT_DOMAIN_BUCKET[scenario_id]),
        "SCENARIO_KEYWORD_BUCKETS_JSON": _json_literal(
            [[keyword, bucket] for keyword, bucket in _SCENARIO_KEYWORD_BUCKETS[scenario_id]],
            indent=2),
        "COUNTRY_CODE_TO_NAME_JSON": _json_literal(COUNTRY_CODE_TO_NAME, indent=2),
        "UPDATE_TYPE_PHRASES_JSON": _json_literal(UPDATE_TYPE_PHRASES, indent=2),
        "DEFAULT_UPDATE_TYPE_PHRASE_JSON": _json_literal(_DEFAULT_UPDATE_TYPE_PHRASE),
        "RECENCY_PHRASE_JSON": _json_literal(RECENCY_PHRASE),
        "STAGE_B_USER_TEMPLATE_JSON": _json_literal(
            (_PROMPTS_DIR / "stage_b_user.md").read_text(encoding="utf-8")),
    }


# ── step 8: the write (orchestrator D2 — idempotent replacement) ────────────

def _write_whole(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(_normalize(text), encoding="utf-8")


def _normalize(text: str) -> str:
    return text.strip("\n") + "\n"


def _replace_or_insert_declaration(path: Path, symbol: str, rendered: str) -> None:
    """Write `rendered` into `path` as the sole declaration of `symbol`.

    Replace the existing declaration in place if there is one, insert it at the
    end if there is not — never touching the rest of the file. This is what makes
    the Phase-8 re-run safe against files Phase 6 has since filled in with
    hand-authored code (D2), and what makes a second run byte-identical to the
    first.
    """
    block = _normalize(rendered)
    path.parent.mkdir(parents=True, exist_ok=True)

    if not path.exists():
        path.write_text(block, encoding="utf-8")
        return

    text = path.read_text(encoding="utf-8")
    span = _declaration_span(text, symbol)
    if span is None:
        separator = "" if text.endswith("\n") or not text else "\n"
        path.write_text(text + separator + block, encoding="utf-8")
        return

    start, end = span
    path.write_text(text[:start] + block + text[end:], encoding="utf-8")


def _declaration_span(text: str, symbol: str) -> tuple[int, int] | None:
    """`(start, end)` of the whole `export const <symbol> … ;` STATEMENT, or None.

    The statement, not the line: `DEMO_FIRM_PROFILE`'s object literal spans a
    dozen lines, and replacing only the line that declares it would leave the
    previous object's tail behind as syntactic rubble — a file that no longer
    parses, produced by a generator that reported success.

    Only the FIRST declaration is located. A file already carrying two of them
    does not compile TS-side either, so there is no sensible behavior to define
    for it beyond not inventing one.
    """
    match = re.search(rf"^export const {re.escape(symbol)}\b", text, re.MULTILINE)
    if match is None:
        return None
    return (match.start(), _statement_end(text, match.end(), symbol))


_OPENERS = {"{": "}", "[": "]", "(": ")"}
_CLOSERS = set(_OPENERS.values())
_QUOTES = {'"', "'", "`"}


def _statement_end(text: str, index: int, symbol: str) -> int:
    """Index just past the `;` closing the statement that starts at `index`,
    plus its trailing newline.

    Depth-tracks brackets and skips both string literals AND comments, so a `;`,
    a brace or a quote inside either cannot mis-terminate the statement.

    **Comments are skipped because prose is where this scanner would otherwise
    die, and die silently.** `// the firm's primary sector` beside a
    hand-authored `DEMO_FIRM_PROFILE` — §8 puts `firmProfileForRecord`
    immediately after it — opens an apostrophe "string" that never closes; the
    scan then runs to EOF and the replacement eats the rest of the file while
    the generator reports success. That is precisely the outcome D2's idempotent
    replacement exists to prevent, arriving through the back door.

    **An unterminated statement RAISES rather than defaulting to end-of-text.**
    The two cases that reach it — a genuinely truncated file, and a scanner that
    lost its place — demand opposite responses (harmless rewrite vs. silent data
    loss), and this function cannot tell them apart. Refusing to guess is the
    only answer that cannot destroy a reviewer's work.
    """
    depth = 0
    position = index
    while position < len(text):
        if text.startswith("//", position):
            newline = text.find("\n", position)
            position = len(text) if newline == -1 else newline + 1
            continue
        if text.startswith("/*", position):
            close = text.find("*/", position + 2)
            if close == -1:
                break
            position = close + 2
            continue
        char = text[position]
        if char in _QUOTES:
            position = _skip_string(text, position)
            continue
        if char in _OPENERS:
            depth += 1
        elif char in _CLOSERS:
            depth -= 1
        elif char == ";" and depth <= 0:
            end = position + 1
            return end + 1 if text[end:end + 1] == "\n" else end
        position += 1

    raise ValueError(
        f"refusing to write: found `export const {symbol}` but no `;` closing it — "
        f"the file is truncated, or this scanner lost its place inside it. Replacing "
        f"to end-of-text would silently delete everything below the declaration."
    )


def _skip_string(text: str, index: int) -> int:
    """Index just past the string literal opening at `index` (backslash-escape
    aware). An unterminated literal consumes to end-of-text, which
    `_statement_end` then reports as "no terminator found"."""
    quote = text[index]
    position = index + 1
    while position < len(text):
        char = text[position]
        if char == "\\":
            position += 2
            continue
        if char == quote:
            return position + 1
        position += 1
    return len(text)
