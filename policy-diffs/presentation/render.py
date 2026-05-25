# presentation/render.py
import difflib
import shutil
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

import yaml
from jinja2 import Environment, FileSystemLoader, select_autoescape
from markdown_it import MarkdownIt

from pipeline.change_record import ChangeRecord, load_change_record
from presentation.redline import (
    render_markdown_redline,
    render_prose_redline,
    render_section_compare,
)
from presentation.yaml_diff import render_yaml_diff


import re as _re

MATERIALITY_ORDER = ("breaking", "substantive", "clarifying", "cosmetic")

# Lines that are clearly page-running chrome (publication header, copyright,
# bare page numbers, bare dates). Used to detect sections whose body is just
# chrome leftovers from a heading that fell on a page boundary.
_CHROME_LINE_RES = [
    _re.compile(r"^Security Rules and Procedures.*\d{4}\s*$"),
    _re.compile(r"^©\s*\d{4}.*Mastercard", _re.IGNORECASE),
    _re.compile(r"^\d{1,4}\s*$"),
    _re.compile(r"^\d{1,2}\s+\w+\s+\d{4}\s*$"),
]


def _looks_like_chrome_only(text: str) -> bool:
    """True if `text` is non-empty but its non-chrome body is < 30 chars.

    Catches the failure mode where a Mastercard SPME section gets extracted as
    just the page-running header (e.g. \"Security Rules and Procedures—Merchant
    Edition · 6 February 2024\") with no real body — typically because the
    section heading fell at the bottom of a page and the next page started
    fresh with chrome before the next heading.
    """
    if not text.strip():
        return False  # empty is not the same as chrome-only; could be legit
    body_chars = 0
    for line in text.splitlines():
        s = line.strip()
        if not s:
            continue
        if any(r.match(s) for r in _CHROME_LINE_RES):
            continue
        body_chars += len(s)
    return body_chars < 30

# Acronyms inside policy slugs that should stay uppercase in display names.
# Set by render_site() from site_config.acronyms; the default below is a
# fallback for direct test calls that bypass render_site().
_ACRONYMS: set[str] = {"bram", "ecp", "kyb", "ato", "kyc", "id", "spme", "ach", "mid", "pci", "adc"}


def _set_acronyms(acronyms: list[str] | set[str]) -> None:
    global _ACRONYMS
    _ACRONYMS = {a.lower() for a in acronyms}


def load_site_config(path: Path) -> dict:
    """Load a site config YAML (brand, artifact, glossary, etc.) as a plain dict."""
    with open(path) as f:
        return yaml.safe_load(f)


def _policy_display_name(slug: str) -> str:
    """`bram_response` -> `BRAM Response`, `chargeback_handling` -> `Chargeback Handling`."""
    parts = slug.split("_")
    return " ".join(p.upper() if p.lower() in _ACRONYMS else p.title() for p in parts)


def make_env() -> Environment:
    templates_dir = Path(__file__).parent / "templates"
    return Environment(
        loader=FileSystemLoader(templates_dir),
        autoescape=select_autoescape(["html", "j2"]),
    )


def _human_date(yyyymm: str) -> str:
    return datetime.strptime(yyyymm, "%Y-%m").strftime("%b %Y")


def _policy_key(path: str) -> str:
    # "policies/bram_response/rules.yaml" -> "bram_response"
    parts = path.split("/")
    return parts[1] if len(parts) >= 2 else path


def _pct(counts: dict[str, int]) -> dict[str, float]:
    total = sum(counts.values()) or 1
    return {k: round(v / total * 100, 2) for k, v in counts.items()}


def _first_paragraph(md_text: str) -> str:
    """Skip the H1, return the first non-empty paragraph as plain text."""
    lines = md_text.splitlines()
    body: list[str] = []
    started = False
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("# ") and not started:
            continue
        if not stripped:
            if body:
                break
            continue
        if stripped.startswith("#"):
            if body:
                break
            continue
        body.append(stripped)
        started = True
    return " ".join(body)


_MD_RENDERER = MarkdownIt("default")


def _load_policy(policies_root: Path, slug: str) -> dict:
    """Read policy.md + rules.yaml + source.yaml for one policy."""
    pdir = policies_root / slug
    policy_md = (pdir / "policy.md").read_text() if (pdir / "policy.md").exists() else ""
    rules_yaml = (pdir / "rules.yaml").read_text() if (pdir / "rules.yaml").exists() else ""
    source_yaml_text = (pdir / "source.yaml").read_text() if (pdir / "source.yaml").exists() else ""

    policy_html = _MD_RENDERER.render(policy_md) if policy_md else ""
    description = _first_paragraph(policy_md)

    authorities: list[dict] = []
    if source_yaml_text:
        data = yaml.safe_load(source_yaml_text) or {}
        for s in data.get("sections", []) or []:
            authorities.append({
                "id": str(s.get("id", "")),
                "title": s.get("title", "") or "",
                "anchor_version": s.get("anchor_version", ""),
            })

    return {
        "slug": slug,
        "name": _policy_display_name(slug),
        "policy_md": policy_md,
        "policy_html": policy_html,
        "rules_yaml": rules_yaml,
        "source_yaml": source_yaml_text,
        "description": description,
        "authorities": authorities,
    }


def _build_section_page_index(artifacts_root: Path) -> dict[tuple[str, str], int]:
    """For each (yyyy-mm, section_id), the first body-page number in the PDF."""
    from pipeline.extractors.pymupdf_pdfplumber import extract_section_pages
    pdf_map = _pdfs_by_yyyymm(artifacts_root)
    index: dict[tuple[str, str], int] = {}
    for yyyymm, pdf_path in pdf_map.items():
        for section_id, page in extract_section_pages(pdf_path).items():
            index[(yyyymm, section_id)] = page
    return index


def _pdfs_by_yyyymm(artifacts_root: Path) -> dict[str, Path]:
    """Map 'YYYY-MM' to the Wayback-named PDF whose timestamp begins with YYYYMM."""
    result: dict[str, Path] = {}
    for p in sorted(artifacts_root.glob("*.pdf")):
        stem = p.stem
        if len(stem) >= 6 and stem[:6].isdigit():
            yyyymm = f"{stem[:4]}-{stem[4:6]}"
            result.setdefault(yyyymm, p)
    return result


def _copy_source_pdfs(artifacts_root: Path, dist: Path, sources_subdir: str) -> dict[str, str]:
    """Copy each source PDF into dist/sources/<subdir>/ ; return YYYY-MM -> filename."""
    pdf_map = _pdfs_by_yyyymm(artifacts_root)
    dest_dir = dist / "sources" / sources_subdir
    dest_dir.mkdir(parents=True, exist_ok=True)
    out: dict[str, str] = {}
    for yyyymm, src in pdf_map.items():
        dest = dest_dir / src.name
        if not dest.exists() or dest.stat().st_size != src.stat().st_size:
            shutil.copy2(src, dest)
        out[yyyymm] = src.name
    return out


# ── Renderers ────────────────────────────────────────────────────────────


def render_timeline(
    *,
    out_path: Path,
    config: dict,
    start_date: str,
    end_date: str,
    transitions: list[dict],
    total_changes: int,
    total_breaking: int,
    total_policies: int,
    assets_prefix: str = "../",
) -> None:
    env = make_env()
    tmpl = env.get_template("timeline.html.j2")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(tmpl.render(
        config=config,
        start_date=start_date,
        end_date=end_date,
        start_date_label=_human_date(start_date),
        end_date_label=_human_date(end_date),
        transitions=transitions,
        total_changes=total_changes,
        total_breaking=total_breaking,
        total_policies=total_policies,
        assets_prefix=assets_prefix,
    ))


def render_transition(
    *,
    out_path: Path,
    config: dict,
    slug: str,
    from_date: str,
    to_date: str,
    changes: list[dict],
    groups: list[dict],
    materiality_counts: dict[str, int],
    policies: list[dict],
    assets_prefix: str = "../",
) -> None:
    env = make_env()
    tmpl = env.get_template("transition.html.j2")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(tmpl.render(
        config=config,
        slug=slug,
        from_date=from_date,
        to_date=to_date,
        from_date_label=_human_date(from_date),
        to_date_label=_human_date(to_date),
        changes=changes,
        groups=groups,
        breaking=materiality_counts.get("breaking", 0),
        substantive=materiality_counts.get("substantive", 0),
        clarifying=materiality_counts.get("clarifying", 0),
        cosmetic=materiality_counts.get("cosmetic", 0),
        policy_count=len(policies),
        policies=policies,
        assets_prefix=assets_prefix,
    ))


def render_change(
    *,
    out_path: Path,
    config: dict,
    change: dict,
    assets_prefix: str = "../",
) -> None:
    env = make_env()
    tmpl = env.get_template("change.html.j2")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(tmpl.render(config=config, change=change, assets_prefix=assets_prefix))


def render_policies_index(
    *,
    out_path: Path,
    config: dict,
    policies: list[dict],
    total_changes: int,
    release_count: int,
    assets_prefix: str = "../",
) -> None:
    env = make_env()
    tmpl = env.get_template("policies/index.html.j2")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(tmpl.render(
        config=config,
        policies=policies,
        total_changes=total_changes,
        release_count=release_count,
        assets_prefix=assets_prefix,
    ))


def render_overview(
    *,
    out_path: Path,
    config: dict,
    pdf_versions: list[dict],
    policies: list[dict],
    total_changes: int,
    total_breaking: int,
    total_policies: int,
    release_count: int,
    start_date_label: str,
    end_date_label: str,
    assets_prefix: str = "",
) -> None:
    env = make_env()
    tmpl = env.get_template("overview.html.j2")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(tmpl.render(
        config=config,
        pdf_versions=pdf_versions,
        policies=policies,
        total_changes=total_changes,
        total_breaking=total_breaking,
        total_policies=total_policies,
        release_count=release_count,
        start_date_label=start_date_label,
        end_date_label=end_date_label,
        assets_prefix=assets_prefix,
    ))


def render_policy_detail(
    *,
    out_path: Path,
    config: dict,
    policy: dict,
    history: list[dict],
    total_changes: int,
    total_breaking: int,
    release_count: int,
    total_releases: int,
    assets_prefix: str = "../",
) -> None:
    env = make_env()
    tmpl = env.get_template("policies/detail.html.j2")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(tmpl.render(
        config=config,
        policy=policy,
        history=history,
        total_changes=total_changes,
        total_breaking=total_breaking,
        release_count=release_count,
        total_releases=total_releases,
        assets_prefix=assets_prefix,
    ))


# ── Enrichment helpers ──────────────────────────────────────────────────


def _kind_for_path(path: str) -> str:
    return "yaml" if path.endswith((".yaml", ".yml")) else "markdown"


def _pdf_url_with_page(pdf_name: str | None, page: int | None, sources_subdir: str) -> str | None:
    if not pdf_name:
        return None
    base = f"../sources/{sources_subdir}/{pdf_name}"
    return f"{base}#page={page}" if page else base


def _build_siblings(all_records: list[ChangeRecord], current: ChangeRecord) -> list[dict]:
    """Other section changes in the same family (same top-level number) in this release."""
    if not current.section_id:
        return []
    current_family = current.section_id.split(".")[0]
    mat_order = {"breaking": 0, "substantive": 1, "clarifying": 2, "cosmetic": 3}
    siblings = [
        r for r in all_records
        if r is not current
        and r.section_id
        and r.section_id.split(".")[0] == current_family
    ]
    siblings.sort(key=lambda r: (mat_order.get(r.materiality, 4), r.section_id))
    return [
        {
            "section_id": r.section_id,
            "title": r.section_title or "",
            "change_id": r.change_id,
            "materiality": r.materiality,
        }
        for r in siblings
    ]


def _enrich_change(
    rec: ChangeRecord,
    transition_label: str,
    from_pdf_name: str | None,
    to_pdf_name: str | None,
    from_page: int | None,
    to_page: int | None,
    siblings: list[dict],
    sources_subdir: str,
) -> dict:
    # Pick redline vs split view based on similarity (SPME sections can be
    # substantively restructured between releases, which makes word-level
    # diffs unreadable — fall back to side-by-side blocks in that case).
    section_compare = render_section_compare(rec.section_before, rec.section_after)
    affected: list[dict] = []
    unified_chunks: list[str] = []
    for f in rec.affected_files:
        kind = _kind_for_path(f.path)
        pk = _policy_key(f.path)
        filename = f.path.rsplit("/", 1)[-1]
        if kind == "yaml":
            diff_html = render_yaml_diff(f.old_contents, f.new_contents)
            full_redline = ""
        else:
            # Markdown: redline first, then markdown-render so headings/lists structure.
            diff_html = render_markdown_redline(f.old_contents, f.new_contents)
            full_redline = diff_html
        unified_chunks.append(
            "".join(difflib.unified_diff(
                f.old_contents.splitlines(keepends=True),
                f.new_contents.splitlines(keepends=True),
                fromfile=f"a/{f.path}", tofile=f"b/{f.path}",
            ))
        )
        affected.append({
            "path": f.path,
            "kind": kind,
            "policy_slug": pk,
            "policy_name": _policy_display_name(pk),
            "filename": filename,
            "diff_html": diff_html,
            "full_redline_html": full_redline,
        })

    affected_policy_keys = sorted({_policy_key(f.path) for f in rec.affected_files})
    affected_policies = [
        {"slug": k, "name": _policy_display_name(k)} for k in affected_policy_keys
    ]

    suspicious = (
        _looks_like_chrome_only(rec.section_before)
        or _looks_like_chrome_only(rec.section_after)
    )

    return {
        "change_id": rec.change_id,
        "suspicious_extraction": suspicious,
        "title": rec.section_title or rec.summary[:60],
        "summary": rec.summary,
        "materiality": rec.materiality,
        "section_id": rec.section_id,
        "transition_slug": f"{rec.transition_from}_to_{rec.transition_to}",
        "transition_label": transition_label,
        "transition_from_label": _human_date(rec.transition_from),
        "transition_to_label": _human_date(rec.transition_to),
        "from_pdf_url": _pdf_url_with_page(from_pdf_name, from_page, sources_subdir),
        "to_pdf_url": _pdf_url_with_page(to_pdf_name, to_page, sources_subdir),
        "from_page": from_page,
        "to_page": to_page,
        "section_family": rec.section_id.split(".")[0] if rec.section_id else "",
        "siblings": siblings,
        "section_compare": section_compare,
        "affected_files": affected,
        "affected_policies": affected_policies,
        "unified_diff": "\n".join(unified_chunks),
        "rationale": rec.rationale,
        "affected_paths": [f.path for f in rec.affected_files],
    }


def _change_summary(rec: ChangeRecord) -> dict:
    """Lightweight per-card data for the transition page."""
    title = rec.section_title or rec.summary[:60]
    paths = [f.path for f in rec.affected_files]
    policy_keys = sorted({_policy_key(p) for p in paths})
    policy_display = [{"slug": k, "name": _policy_display_name(k)} for k in policy_keys]
    display_names = [p["name"] for p in policy_display]
    search_blob = " ".join([
        title, rec.summary, rec.section_id or "",
        *paths, *policy_keys, *display_names,
    ]).lower()
    suspicious = (
        _looks_like_chrome_only(rec.section_before)
        or _looks_like_chrome_only(rec.section_after)
    )
    return {
        "change_id": rec.change_id,
        "title": title,
        "summary": rec.summary,
        "materiality": rec.materiality,
        "section_id": rec.section_id,
        "affected_paths": paths,
        "policy_keys": policy_keys,
        "policy_display": policy_display,
        "search_text": search_blob,
        "suspicious_extraction": suspicious,
    }


def _group_by_materiality(items: list[dict]) -> list[dict]:
    by_mat: dict[str, list[dict]] = defaultdict(list)
    for c in items:
        by_mat[c["materiality"]].append(c)
    groups: list[dict] = []
    for mat in MATERIALITY_ORDER:
        if by_mat[mat]:
            groups.append({"materiality": mat, "changes": by_mat[mat]})
    return groups


# ── Top-level site renderer ─────────────────────────────────────────────


def render_site(
    *,
    artifacts_root: Path,
    dist: Path,
    site_config: dict,
    policies_root: Path | None = None,
) -> None:
    if policies_root is None:
        policies_root = dist.parent / "policies"

    # Acronyms drive policy-slug display-name capitalization (BRAM, ECP, …).
    _set_acronyms(site_config.get("acronyms", []))
    sources_subdir = site_config["artifact"]["sources_subdir"]

    # Copy source PDFs into dist so change pages can link to them.
    pdf_by_yyyymm = _copy_source_pdfs(artifacts_root, dist, sources_subdir)
    # Build (yyyy-mm, section_id) -> page-number map for PDF deep-linking.
    section_page_index = _build_section_page_index(artifacts_root)

    transitions: list[dict] = []
    all_policy_keys: set[str] = set()
    total_breaking = 0
    total_changes = 0

    # Per-transition cache for use in policy-detail rendering below.
    per_transition_changes: dict[str, list[dict]] = {}
    transition_metadata: dict[str, dict] = {}

    for t_dir in sorted(p for p in artifacts_root.iterdir() if p.is_dir()):
        change_files = sorted((t_dir / "changes").glob("*.json")) if (t_dir / "changes").exists() else []
        records = [load_change_record(f) for f in change_files]
        if not records:
            continue
        from_d = records[0].transition_from
        to_d = records[0].transition_to
        slug = f"{from_d}_to_{to_d}"
        label = f"{_human_date(from_d)} → {_human_date(to_d)}"

        from_pdf = pdf_by_yyyymm.get(from_d)
        to_pdf = pdf_by_yyyymm.get(to_d)

        counts: Counter[str] = Counter(r.materiality for r in records)
        for k in MATERIALITY_ORDER:
            counts.setdefault(k, 0)

        # Per-change pages
        for rec in records:
            from_page = section_page_index.get((from_d, rec.section_id))
            to_page = section_page_index.get((to_d, rec.section_id))
            siblings = _build_siblings(records, rec)
            enriched = _enrich_change(
                rec, label, from_pdf, to_pdf, from_page, to_page, siblings, sources_subdir,
            )
            render_change(
                out_path=dist / "changes" / f"{rec.change_id}.html",
                config=site_config,
                change=enriched,
                assets_prefix="../",
            )

        # Per-transition page data
        change_summaries = [_change_summary(r) for r in records]
        change_summaries.sort(key=lambda c: (c["section_id"] or "",))
        groups = _group_by_materiality(change_summaries)

        transition_policies = sorted({
            pk for c in change_summaries for pk in c["policy_keys"]
        })
        transition_policies_meta = [
            {"slug": k, "name": _policy_display_name(k)} for k in transition_policies
        ]

        render_transition(
            out_path=dist / "transitions" / f"{slug}.html",
            config=site_config,
            slug=slug,
            from_date=from_d, to_date=to_d,
            changes=change_summaries,
            groups=groups,
            materiality_counts=dict(counts),
            policies=transition_policies_meta,
            assets_prefix="../",
        )

        # Cache for policy-history pass.
        per_transition_changes[slug] = change_summaries
        transition_metadata[slug] = {
            "slug": slug,
            "from_date": from_d,
            "to_date": to_d,
            "from_date_label": _human_date(from_d),
            "to_date_label": _human_date(to_d),
            "label": label,
        }

        all_policy_keys.update(transition_policies)
        total_breaking += counts["breaking"]
        total_changes += len(records)

        transitions.append({
            "from_date": from_d,
            "to_date": to_d,
            "from_date_label": _human_date(from_d),
            "to_date_label": _human_date(to_d),
            "slug": slug,
            "label": label,
            "change_count": len(records),
            "affected_policy_count": len(transition_policies),
            "materiality_counts": dict(counts),
            "pct": _pct(dict(counts)),
        })

    # ── Policies: index + per-policy detail with mini-timeline ──────────
    if all_policy_keys and policies_root.exists():
        # Include any policy folder that exists on disk, even if untouched by any change.
        on_disk = sorted({p.name for p in policies_root.iterdir() if p.is_dir()})
        all_known = sorted(all_policy_keys | set(on_disk))

        loaded_policies: dict[str, dict] = {
            slug: _load_policy(policies_root, slug) for slug in all_known
        }

        index_entries: list[dict] = []
        for slug in all_known:
            policy = loaded_policies[slug]

            # Build per-transition history filtered to this policy.
            history: list[dict] = []
            agg_counts: Counter[str] = Counter()
            policy_total_changes = 0
            policy_total_breaking = 0
            releases_touched = 0

            for t_slug, meta in transition_metadata.items():
                cs = [c for c in per_transition_changes[t_slug] if slug in c["policy_keys"]]
                tcounts: Counter[str] = Counter(c["materiality"] for c in cs)
                for k in MATERIALITY_ORDER:
                    tcounts.setdefault(k, 0)
                history.append({
                    **meta,
                    "changes": cs,
                    "change_count": len(cs),
                    "materiality_counts": dict(tcounts),
                    "pct": _pct(dict(tcounts)),
                })
                if cs:
                    releases_touched += 1
                policy_total_changes += len(cs)
                policy_total_breaking += tcounts["breaking"]
                agg_counts.update(tcounts)

            render_policy_detail(
                out_path=dist / "policies" / f"{slug}.html",
                config=site_config,
                policy=policy,
                history=history,
                total_changes=policy_total_changes,
                total_breaking=policy_total_breaking,
                release_count=releases_touched,
                total_releases=len(transition_metadata),
                assets_prefix="../",
            )

            index_entries.append({
                **policy,
                "change_count": policy_total_changes,
                "breaking_count": policy_total_breaking,
                "release_count": releases_touched,
                "materiality_counts": dict(agg_counts),
                "pct": _pct(dict(agg_counts)),
            })

        render_policies_index(
            out_path=dist / "policies" / "index.html",
            config=site_config,
            policies=index_entries,
            total_changes=total_changes,
            release_count=len(transitions),
            assets_prefix="../",
        )

    if transitions:
        start_date = transitions[0]["from_date"]
        end_date = transitions[-1]["to_date"]
        render_timeline(
            out_path=dist / "timeline" / "index.html",
            config=site_config,
            start_date=start_date, end_date=end_date,
            transitions=transitions,
            total_changes=total_changes,
            total_breaking=total_breaking,
            total_policies=len(all_policy_keys),
            assets_prefix="../",
        )

        # Overview / context landing page (the new entry point).
        pdf_versions = [
            {"yyyymm": k, "label": _human_date(k), "filename": v}
            for k, v in sorted(pdf_by_yyyymm.items())
        ]
        # Use the on-disk policies (may include ones not touched by any change).
        overview_policies: list[dict] = []
        if policies_root.exists():
            for slug in sorted(p.name for p in policies_root.iterdir() if p.is_dir()):
                p = _load_policy(policies_root, slug)
                overview_policies.append({
                    "slug": p["slug"],
                    "name": p["name"],
                    "description": p["description"],
                })
        render_overview(
            out_path=dist / "index.html",
            config=site_config,
            pdf_versions=pdf_versions,
            policies=overview_policies,
            total_changes=total_changes,
            total_breaking=total_breaking,
            total_policies=len(all_policy_keys),
            release_count=len(transitions),
            start_date_label=_human_date(start_date),
            end_date_label=_human_date(end_date),
        )
