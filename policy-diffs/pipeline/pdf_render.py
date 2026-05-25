# pipeline/pdf_render.py
import re
import subprocess
from pathlib import Path

# Strip ASCII control characters (except tab, LF, CR) that cause LaTeX failures
_CONTROL_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")


def _sanitize(text: str) -> str:
    return _CONTROL_RE.sub("", text)


def render_policy_pdf(md_path: Path, pdf_path: Path) -> None:
    pdf_path.parent.mkdir(parents=True, exist_ok=True)
    # Sanitize control chars that trip up LaTeX; write to a temp file
    tmp = pdf_path.parent / (md_path.stem + ".tmp.md")
    try:
        tmp.write_text(_sanitize(md_path.read_text()))
        subprocess.run(
            ["pandoc", str(tmp), "-o", str(pdf_path), "--pdf-engine=xelatex"],
            check=True,
            capture_output=True,
        )
    finally:
        if tmp.exists():
            tmp.unlink()
