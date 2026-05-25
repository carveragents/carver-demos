# pipeline/propose.py
import yaml
from dataclasses import dataclass
from pathlib import Path

from pipeline.llm import LLMClient


PROMPT = (Path(__file__).parent.parent / "prompts" / "propose.txt").read_text()

SCHEMA = {
    "type": "object",
    "properties": {
        "new_contents": {"type": "string"},
        "change_summary": {"type": "string"},
    },
    "required": ["new_contents", "change_summary"],
    "additionalProperties": False,
}

MAX_SECTION_CHARS = 8000

_YAML_EXTENSIONS = {".yaml", ".yml"}


def _truncate(s: str, n: int = MAX_SECTION_CHARS) -> str:
    if len(s) <= n:
        return s
    return s[:n] + f"\n\n[... section truncated; total {len(s)} chars omitted ...]"


def _clean_control_chars(text: str) -> str:
    """Strip null bytes and C0 control chars (keep \\n, \\t, \\r)."""
    keep = {"\n", "\t", "\r"}
    return "".join(ch for ch in text if ch in keep or ord(ch) >= 0x20)


def _is_valid_yaml_dict(text: str) -> tuple[bool, str]:
    """Return (ok, error_message). ok=True iff text parses as a dict."""
    try:
        result = yaml.safe_load(text)
        if isinstance(result, dict):
            return True, ""
        return False, f"yaml.safe_load returned {type(result).__name__}, not a dict"
    except yaml.YAMLError as exc:
        return False, str(exc)


@dataclass(frozen=True)
class FileEdit:
    policy_path: str
    old_contents: str
    new_contents: str
    change_summary: str


def propose_edit(
    *,
    policy_path: str,
    current_contents: str,
    section_id: str,
    section_before: str,
    section_after: str,
    rationale: str,
    llm: LLMClient,
) -> FileEdit:
    file_kind = "yaml" if Path(policy_path).suffix in _YAML_EXTENSIONS else "markdown"

    before = _truncate(section_before)
    after = _truncate(section_after)
    user = (
        f"file_kind: {file_kind}\n\n"
        f"File: {policy_path}\n\n"
        f"--- CURRENT CONTENTS ---\n{current_contents}\n\n"
        f"Mastercard SPME §{section_id}\n"
        f"--- BEFORE ---\n{before}\n\n"
        f"--- AFTER ---\n{after}\n\n"
        f"Rationale: {rationale}\n"
    )
    out = llm.complete_json(stage="propose", system=PROMPT, user=user, json_schema=SCHEMA)
    new_contents = out["new_contents"]
    change_summary = out["change_summary"]

    if file_kind == "yaml":
        new_contents = _clean_control_chars(new_contents)
        ok, err = _is_valid_yaml_dict(new_contents)
        if not ok:
            # Retry once with an explanation of the failure
            retry_user = (
                user
                + f"\nPREVIOUS ATTEMPT FAILED YAML PARSE:\n{err}\n"
                f"The previous output was:\n---\n{new_contents}\n---\n"
                "Return ONLY valid YAML this time. No bare text after the YAML structure.\n"
            )
            out2 = llm.complete_json(stage="propose", system=PROMPT, user=retry_user, json_schema=SCHEMA)
            new_contents2 = _clean_control_chars(out2["new_contents"])
            ok2, _ = _is_valid_yaml_dict(new_contents2)
            if ok2:
                new_contents = new_contents2
                change_summary = out2["change_summary"]
            else:
                return FileEdit(
                    policy_path=policy_path,
                    old_contents=current_contents,
                    new_contents=current_contents,
                    change_summary="Skipped: LLM produced invalid YAML twice.",
                )

    return FileEdit(
        policy_path=policy_path,
        old_contents=current_contents,
        new_contents=new_contents,
        change_summary=change_summary,
    )
