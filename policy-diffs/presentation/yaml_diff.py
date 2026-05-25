# presentation/yaml_diff.py
import difflib
from html import escape


def render_yaml_diff(before: str, after: str) -> str:
    """Line-level YAML diff → HTML. Each line wrapped with class indicating add/remove/keep."""
    matcher = difflib.SequenceMatcher(a=before.splitlines(), b=after.splitlines())
    lines: list[str] = []
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == "equal":
            for line in before.splitlines()[i1:i2]:
                lines.append(f"<div class='diff-line-equal'>{escape(line) or '&nbsp;'}</div>")
        elif tag == "delete":
            for line in before.splitlines()[i1:i2]:
                lines.append(f"<div class='diff-line-removed'>- {escape(line)}</div>")
        elif tag == "insert":
            for line in after.splitlines()[j1:j2]:
                lines.append(f"<div class='diff-line-added'>+ {escape(line)}</div>")
        elif tag == "replace":
            for line in before.splitlines()[i1:i2]:
                lines.append(f"<div class='diff-line-removed'>- {escape(line)}</div>")
            for line in after.splitlines()[j1:j2]:
                lines.append(f"<div class='diff-line-added'>+ {escape(line)}</div>")
    return "<pre class='yaml-diff'>" + "\n".join(lines) + "</pre>"
