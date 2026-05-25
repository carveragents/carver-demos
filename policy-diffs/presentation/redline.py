# presentation/redline.py
import html as _html
import re
from difflib import SequenceMatcher

from markdown_it import MarkdownIt
from redlines import Redlines


# Below this ratio (0.0–1.0), a word-level redline becomes unreadable confetti
# because before/after share too little content. Fall back to a split view.
SIMILARITY_THRESHOLD = 0.4

# PDF extractors (pymupdf/pdfplumber) typically put list markers on their own
# line, with the item content on the next line(s). These regexes match a line
# that is JUST a marker.
_BULLET_MARKER_RE = re.compile(r"^[•·▪▫●○]$")
_NUMBERED_MARKER_RE = re.compile(r"^(\d+)\.$")
_SUBITEM_MARKER_RE = re.compile(r"^([a-z])\.$", re.IGNORECASE)


def _is_list_marker(line: str) -> bool:
    return bool(
        _BULLET_MARKER_RE.match(line)
        or _NUMBERED_MARKER_RE.match(line)
        or _SUBITEM_MARKER_RE.match(line)
    )


def render_prose_redline(before: str, after: str) -> str:
    """Word-level diff → HTML with <ins>/<del>. Empty markers when no change."""
    if before == after:
        return f"<span class='unchanged'>{before}</span>"
    r = Redlines(before, after, markdown_style="none")
    return r.output_markdown.replace(
        "<ins>", "<ins class='ins'>"
    ).replace(
        "<del>", "<del class='del'>"
    )


# HTML-enabled renderer so inline <ins>/<del> tags pass through unchanged
# while markdown headings, lists, bold, code, etc. still render structurally.
_MD_RENDERER = MarkdownIt("default", {"html": True})


def _to_paragraphs_html(text: str) -> str:
    """Convert PDF-extracted prose to HTML with proper paragraphs and lists.

    Mastercard SPME PDFs are extracted such that each list marker (`•`, `N.`,
    or `a.`) sits on its own line and the item content follows on the next
    line(s). Treating the whole thing as one paragraph collapses everything
    into an unreadable run-on. This parser groups consecutive marker lines
    into proper `<ul>` / `<ol>` blocks and nests `a./b./c.` sub-items under
    numbered parents.
    """
    lines = [l.rstrip() for l in text.splitlines()]
    i, n = 0, len(lines)
    out: list[str] = []

    def collect_item(start: int) -> tuple[str, int]:
        """Collect lines after a marker, joined into one item, stopping at the
        next marker or end of text. Blank lines are tolerated (skipped)."""
        buf: list[str] = []
        while start < n:
            ln = lines[start].strip()
            if not ln:
                start += 1
                continue
            if _is_list_marker(ln):
                break
            buf.append(ln)
            start += 1
        return (" ".join(buf).strip(), start)

    while i < n:
        line = lines[i].strip()
        if not line:
            i += 1
            continue

        # Numbered list (with optional nested a./b./c. sub-items)
        if _NUMBERED_MARKER_RE.match(line):
            items: list[str] = []
            while i < n and _NUMBERED_MARKER_RE.match(lines[i].strip()):
                i += 1
                content, i = collect_item(i)
                sub_items: list[str] = []
                while i < n and _SUBITEM_MARKER_RE.match(lines[i].strip()):
                    i += 1
                    sub_content, i = collect_item(i)
                    if sub_content:
                        sub_items.append(sub_content)
                item_html = _html.escape(content)
                if sub_items:
                    item_html += '<ol type="a">' + "".join(
                        f"<li>{_html.escape(s)}</li>" for s in sub_items
                    ) + "</ol>"
                items.append(f"<li>{item_html}</li>")
            out.append("<ol>" + "".join(items) + "</ol>")
            continue

        # Bullet list
        if _BULLET_MARKER_RE.match(line):
            bullets: list[str] = []
            while i < n and _BULLET_MARKER_RE.match(lines[i].strip()):
                i += 1
                content, i = collect_item(i)
                if content:
                    bullets.append(content)
            out.append("<ul>" + "".join(
                f"<li>{_html.escape(b)}</li>" for b in bullets
            ) + "</ul>")
            continue

        # Standalone sub-item list (no preceding numbered marker captured)
        if _SUBITEM_MARKER_RE.match(line):
            subs: list[str] = []
            while i < n and _SUBITEM_MARKER_RE.match(lines[i].strip()):
                i += 1
                content, i = collect_item(i)
                if content:
                    subs.append(content)
            out.append('<ol type="a">' + "".join(
                f"<li>{_html.escape(s)}</li>" for s in subs
            ) + "</ol>")
            continue

        # Regular paragraph: collect until blank line or list marker
        para = [line]
        i += 1
        while i < n:
            ln = lines[i].strip()
            if not ln:
                i += 1
                break
            if _is_list_marker(ln):
                break
            para.append(ln)
            i += 1
        out.append(f"<p>{_html.escape(' '.join(para))}</p>")

    return "\n".join(out)


def render_section_compare(before: str, after: str) -> dict:
    """Pick the right visualization for a SPME section diff.

    Returns:
      {"mode": "redline", "html": "..."} — high-similarity word-level redline
      {"mode": "split", "before_html": "...", "after_html": "...", "similarity": float}
        — low-similarity case where the section was substantively restructured;
        the template should show before and after as separate blocks.
    """
    if before == after:
        return {"mode": "redline", "html": f"<span class='unchanged'>{_html.escape(before)}</span>"}
    ratio = SequenceMatcher(None, before, after).ratio()
    if ratio >= SIMILARITY_THRESHOLD:
        return {"mode": "redline", "html": render_prose_redline(before, after)}
    return {
        "mode": "split",
        "before_html": _to_paragraphs_html(before),
        "after_html": _to_paragraphs_html(after),
        "similarity": round(ratio, 2),
    }


def render_markdown_redline(before: str, after: str) -> str:
    """Word-level diff over a markdown source, then render the whole document as
    markdown so headings/lists/code render structurally. <ins>/<del> redline
    marks are inline HTML and survive markdown rendering."""
    if before == after:
        return _MD_RENDERER.render(before)
    redlined = (
        Redlines(before, after, markdown_style="none").output_markdown
        .replace("<ins>", "<ins class='ins'>")
        .replace("<del>", "<del class='del'>")
    )
    return _MD_RENDERER.render(redlined)
