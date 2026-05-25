# pipeline/diff.py
from dataclasses import dataclass
from typing import Literal

from pipeline.extractors.base import Section


@dataclass(frozen=True)
class SectionDelta:
    section_id: str
    title: str
    kind: Literal["added", "removed", "modified"]
    before: str
    after: str


def diff_sections(v_from: list[Section], v_to: list[Section]) -> list[SectionDelta]:
    by_id_from = {s.section_id: s for s in v_from}
    by_id_to = {s.section_id: s for s in v_to}
    deltas: list[SectionDelta] = []
    for sid in sorted(by_id_from.keys() | by_id_to.keys(), key=_sortkey):
        a = by_id_from.get(sid)
        b = by_id_to.get(sid)
        if a is None and b is not None:
            deltas.append(SectionDelta(sid, b.title, "added", "", b.markdown))
        elif b is None and a is not None:
            deltas.append(SectionDelta(sid, a.title, "removed", a.markdown, ""))
        elif a is not None and b is not None and a.markdown != b.markdown:
            deltas.append(SectionDelta(sid, b.title, "modified", a.markdown, b.markdown))
    return deltas


def _sortkey(sid: str) -> tuple[int, ...]:
    return tuple(int(p) for p in sid.split(".") if p.isdigit())
