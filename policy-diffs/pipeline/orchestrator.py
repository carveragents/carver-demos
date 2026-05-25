import sys
from dataclasses import dataclass, field
from pathlib import Path

import yaml

from pipeline.change_record import AffectedFile, ChangeRecord, save_change_record
from pipeline.classify import classify_delta
from pipeline.config import Config
from pipeline.diff import SectionDelta
from pipeline.llm import LLMClient
from pipeline.map_changes import PolicyCatalogEntry, map_delta
from pipeline.propose import propose_edit


@dataclass
class TransitionResult:
    change_records: list[ChangeRecord] = field(default_factory=list)


class Orchestrator:
    """Runs Mastercard-version transitions end-to-end.

    For each section delta: classify -> filter cosmetic/clarifying -> map ->
    propose per-file edits -> persist a ChangeRecord JSON.

    Sequential state model: the Credio policy files on disk remain pinned to
    the v1 baseline. The orchestrator maintains an in-memory cumulative state
    across transitions within a single phase run, so transition N's proposer
    sees the files as they were after transition N-1's edits — matching how a
    real compliance team applies year-over-year refreshes — without mutating
    the tracked baseline.
    """

    def __init__(self, *, cfg: Config, credio_repo: Path, artifacts_dir: Path, llm: LLMClient):
        self.cfg = cfg
        self.credio_repo = credio_repo
        self.artifacts_dir = artifacts_dir
        self.llm = llm
        # Cumulative in-memory state: policy_path -> latest contents.
        # Files not in this dict are read from disk (the v1 baseline).
        self._state: dict[str, str] = {}

    def _build_catalog(self) -> list[PolicyCatalogEntry]:
        entries: list[PolicyCatalogEntry] = []
        policies_dir = self.credio_repo / "policies"
        for folder in sorted(policies_dir.iterdir()):
            if not folder.is_dir():
                continue
            source_path = folder / "source.yaml"
            source = yaml.safe_load(source_path.read_text()) if source_path.exists() else {}
            cited = [str(s.get("id", "")) for s in (source or {}).get("sections", [])]
            policy_md = folder / "policy.md"
            desc = policy_md.read_text().splitlines()[0].lstrip("# ").strip() if policy_md.exists() else ""
            entries.append(PolicyCatalogEntry(name=folder.name, description=desc, cited_sections=cited))
        return entries

    def _read_current(self, policy_path: str, fpath: Path) -> str:
        """Return cumulative state for this file (in-memory if seen, else baseline from disk)."""
        if policy_path in self._state:
            return self._state[policy_path]
        return fpath.read_text()

    def run_transition(
        self,
        *,
        transition_from: str,
        transition_to: str,
        deltas: list[SectionDelta],
    ) -> TransitionResult:
        catalog = self._build_catalog()
        result = TransitionResult()

        for delta in deltas:
            classification = classify_delta(delta, llm=self.llm)
            if classification.materiality in ("cosmetic", "clarifying"):
                continue
            mapping = map_delta(
                classification,
                before=delta.before, after=delta.after,
                catalog=catalog, llm=self.llm,
            )
            if not mapping.affected_policies:
                continue

            affected: list[AffectedFile] = []
            for ap in mapping.affected_policies:
                folder = self.credio_repo / "policies" / ap.policy
                if not folder.exists():
                    print(
                        f"[orchestrator] WARN: mapper named non-existent policy '{ap.policy}' "
                        f"for SPME §{delta.section_id}; skipping.",
                        file=sys.stderr,
                    )
                    continue
                for fname in ("rules.yaml", "policy.md"):
                    fpath = folder / fname
                    if not fpath.exists():
                        continue
                    policy_path = f"policies/{ap.policy}/{fname}"
                    current = self._read_current(policy_path, fpath)
                    edit = propose_edit(
                        policy_path=policy_path,
                        current_contents=current,
                        section_id=delta.section_id,
                        section_before=delta.before,
                        section_after=delta.after,
                        rationale=ap.rationale,
                        llm=self.llm,
                    )
                    if edit.new_contents.strip() == edit.old_contents.strip():
                        continue
                    # Update cumulative in-memory state; do NOT touch disk.
                    self._state[policy_path] = edit.new_contents
                    affected.append(AffectedFile(
                        path=edit.policy_path,
                        old_contents=edit.old_contents,
                        new_contents=edit.new_contents,
                        change_summary=edit.change_summary,
                    ))

            if not affected:
                continue

            change_id = f"{transition_from}_to_{transition_to}_{delta.section_id}"
            rec = ChangeRecord(
                change_id=change_id,
                transition_from=transition_from,
                transition_to=transition_to,
                section_id=delta.section_id,
                section_title=delta.title,
                materiality=classification.materiality,
                summary=classification.summary,
                section_before=delta.before,
                section_after=delta.after,
                affected_files=affected,
                rationale="; ".join(p.rationale for p in mapping.affected_policies),
            )
            save_change_record(
                rec,
                self.artifacts_dir / "spme" / f"{transition_from}_to_{transition_to}" / "changes" / f"{change_id}.json",
            )
            result.change_records.append(rec)

        return result
