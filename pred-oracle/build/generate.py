"""Site builder: render Jinja2 templates with their slice JSON into site/.

Mapping convention:
- templates/landing.html       → site/index.html       (loads page_data/landing.json)
- templates/close.html         → site/close.html
- templates/<scene>/intro.html → site/<scene>/index.html
- templates/<scene>/<page>.html → site/<scene>/<page>/index.html

Static dir copied verbatim: build/static/ → site/static/.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import sys
from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader, select_autoescape


def _render_parametric(
    repo_root: Path,
    env: Environment,
    site_root: Path,
    base_url: str | None,
    template_path: str,
    slice_dir_relative: str,
    site_subpath: str,
    scene: str | None = None,
) -> int:
    """Render `template_path` once per slice in build/page_data/<slice_dir_relative>/*.json.

    Output: site_root/<site_subpath>/<slice_stem>/index.html.
    Returns count of pages written.
    """
    pd_dir = repo_root / "build" / "page_data" / slice_dir_relative
    if not pd_dir.exists():
        return 0
    tpl = env.get_template(template_path)
    written = 0
    for slice_path in sorted(pd_dir.glob("*.json")):
        ctx = json.loads(slice_path.read_text())
        ctx["scene_only"] = scene is not None
        out_dir = site_root / site_subpath / slice_path.stem
        out_dir.mkdir(parents=True, exist_ok=True)
        out_file = out_dir / "index.html"
        ctx["base_url"] = base_url if base_url is not None else _relative_base(site_root, out_file)
        html = tpl.render(**ctx)
        if base_url is None:
            html = _fileify_links(html)
        if scene:
            html = _strip_scene_links(html, scene)
        out_file.write_text(html)
        written += 1
    return written


def _render_parametric_tickets(
    repo_root: Path,
    env: Environment,
    site_root: Path,
    base_url: str | None,
) -> int:
    """Backwards-compat wrapper for the α-tickets render."""
    return _render_parametric(
        repo_root, env, site_root, base_url,
        template_path="alpha/ticket_detail.html",
        slice_dir_relative="alpha/tickets",
        site_subpath="alpha/tickets",
    )


def _load_slice(repo_root: Path, rel: Path) -> dict[str, Any]:
    """Load the slice JSON corresponding to a template's relative path.

    Convention: build/page_data/ mirrors the build/templates/ tree.
    E.g., templates/alpha/inbox.html ↔ page_data/alpha/inbox.json.
    """
    slice_path = repo_root / "build" / "page_data" / rel.with_suffix(".json")
    if slice_path.exists():
        return json.loads(slice_path.read_text())  # type: ignore[no-any-return]
    return {}


def _load_gamma_scan_bundle(repo_root: Path) -> dict[str, Any]:
    """Load all γ pre-listing-scan slices as a list, in curation order.

    The scan template at gamma/scan.html switches between scans client-side
    via Alpine tabs, so it needs ALL three slices in scope at render time.
    Ordering follows `data/gamma-curation.yml::pre_listing_scans[*].id` so
    the demo's narrative beat (TikTok ban first, then Solana, then state) is
    preserved — alphabetical filename order would put Solana first.
    """
    scan_dir = repo_root / "build" / "page_data" / "gamma" / "pre-listing-scans"
    curation_path = repo_root / "data" / "gamma-curation.yml"
    scans: list[dict[str, Any]] = []
    if not scan_dir.exists():
        return {"scans": scans}

    # Build id → slice index from the JSON files.
    slices_by_id: dict[str, dict[str, Any]] = {}
    for p in scan_dir.glob("*.json"):
        doc = json.loads(p.read_text())
        slices_by_id[doc.get("id") or p.stem] = doc

    # Order via curation YAML if available; fall back to alphabetical.
    if curation_path.exists():
        import yaml as _yaml
        cur = _yaml.safe_load(curation_path.read_text())
        for entry in cur.get("pre_listing_scans") or []:
            doc = slices_by_id.pop(entry["id"], None)
            if doc is not None:
                scans.append(doc)
    for remaining in sorted(slices_by_id.keys()):
        scans.append(slices_by_id[remaining])
    return {"scans": scans}


def _render_trader_briefings(
    repo_root: Path,
    env: Environment,
    site_root: Path,
    base_url: str | None,
    slice_dir_relative: str,
    site_subpath: str,
    scene: str | None = None,
) -> int:
    """Render trader/briefing.html once per slice, injecting price data from cache.

    Output: site_root/<site_subpath>/<slice_stem>/index.html.
    Returns count of pages written.
    """
    pd_dir = repo_root / "build" / "page_data" / slice_dir_relative
    prices_dir = repo_root / "build" / "_cache" / "prices"
    if not pd_dir.exists():
        return 0
    tpl = env.get_template("trader/briefing.html")
    written = 0
    for slice_path in sorted(pd_dir.glob("*.json")):
        ctx = json.loads(slice_path.read_text())
        ctx["scene_only"] = scene is not None
        # Inject price data keyed by contract id
        contract_id = ctx.get("contract", {}).get("id", slice_path.stem)
        price_file = prices_dir / f"{contract_id}.json"
        if price_file.exists():
            ctx["prices"] = json.loads(price_file.read_text())
        else:
            ctx["prices"] = {"series": []}
        out_dir = site_root / site_subpath / slice_path.stem
        out_dir.mkdir(parents=True, exist_ok=True)
        out_file = out_dir / "index.html"
        ctx["base_url"] = base_url if base_url is not None else _relative_base(site_root, out_file)
        html = tpl.render(**ctx)
        if base_url is None:
            html = _fileify_links(html)
        if scene:
            html = _strip_scene_links(html, scene)
        out_file.write_text(html)
        written += 1
    return written


# Explicit overrides: templates that should land at a non-default route.
# Used to make alpha/inbox.html the scene entry point (alpha/index.html)
# while keeping semantic naming for the template file.
_EXPLICIT_ROUTES: dict[str, str] = {
    "alpha/inbox.html": "alpha/index.html",
    "alpha/audit_export.html": "alpha/audit-export/index.html",
    "gamma/scan.html": "gamma/scan/index.html",
    "gamma/dashboard.html": "gamma/dashboard/index.html",
    "beta/heatmap.html": "beta/heatmap/index.html",
    "beta/cascades.html": "beta/cascades/index.html",
    "beta/report.html": "beta/report/index.html",
    "trader/intro.html": "trader/index.html",
    "trader/list.html": "trader/portfolio/index.html",
    "trader/calendar.html": "trader/calendar/index.html",
    "trader/retrospectives.html": "trader/retrospectives/index.html",
}


def _route_for_template(rel_path: Path) -> Path:
    """Map a template relative path to its site output relative path.

    landing.html → index.html
    close.html → close.html
    alpha/inbox.html → alpha/index.html  (explicit override — scene entry)
    <scene>/intro.html → <scene>/index.html  (beta/gamma placeholders)
    <scene>/<page>.html → <scene>/<page>/index.html
    """
    parts = rel_path.parts
    stem = rel_path.stem
    rel_posix = rel_path.as_posix()

    if rel_posix in _EXPLICIT_ROUTES:
        return Path(_EXPLICIT_ROUTES[rel_posix])
    if rel_path == Path("landing.html"):
        return Path("index.html")
    if len(parts) == 1:
        return rel_path  # e.g., close.html
    # Subdirectory case
    if stem == "intro":
        return Path(*parts[:-1]) / "index.html"
    return Path(*parts[:-1]) / stem / "index.html"


_LINK_SKIP_PREFIXES = (
    "http://", "https://", "//", "mailto:", "tel:", "data:", "javascript:", "#",
)
_LINK_ATTR_RE = re.compile(r'(href|src)="([^"]*)"')


def _fileify_links(html: str) -> str:
    """Rewrite internal directory-style links to point at the explicit index.html.

    Browsers do not auto-serve index.html for a directory over `file://` (they
    show a directory listing). Rewriting `href="../trader/"` → `href="../trader/
    index.html"` makes the built site directly navigable from disk, matching the
    sibling policy-diffs demo. Links that already name a file (have an extension)
    and external/anchor links are left untouched.
    """
    def _repl(m: re.Match[str]) -> str:
        attr, val = m.group(1), m.group(2)
        if val.startswith(_LINK_SKIP_PREFIXES):
            return m.group(0)
        parts = re.match(r"^([^?#]*)([?#].*)?$", val)
        core = parts.group(1) if parts else val
        rest = (parts.group(2) if parts else "") or ""
        if core == "":
            core = "index.html"
        elif core.endswith("/"):
            core = core + "index.html"
        else:
            return m.group(0)  # already a file (has a name/extension)
        return f'{attr}="{core}{rest}"'

    return _LINK_ATTR_RE.sub(_repl, html)


def _strip_scene_links(html: str, scene: str) -> str:
    """Drop a leading '<scene>/' path segment from internal links.

    Lets a single scene be mounted at the site root (e.g. a trader-only export):
    `href="../trader/portfolio/index.html"` → `href="../portfolio/index.html"`.
    Only the segment immediately after the relative prefix is removed, so deep
    links and the relative `../` depth stay correct.
    """
    pat = re.compile(r'((?:href|src)="(?:\.\./)*)' + re.escape(scene) + r"/")
    return pat.sub(r"\1", html)


def _remount_route(route: Path, scene: str | None) -> Path:
    """Strip a leading '<scene>/' directory from an output route (root-mount)."""
    if scene and route.parts and route.parts[0] == scene:
        rest = route.parts[1:]
        return Path(*rest) if rest else Path("index.html")
    return route


def _relative_base(site_root: Path, out_path: Path) -> str:
    """Per-page relative prefix from an output file back to the site root.

    Every internal link in the templates is written as `{{ base_url }}trader/...`.
    Returning a depth-aware relative prefix ("" at root, "../" one level deep,
    "../../../" three deep) makes the built site portable: it works under
    `file://`, at a domain root, and at any deploy subpath — no hardcoded path.
    """
    rel = os.path.relpath(site_root, out_path.parent)
    return "" if rel == "." else rel + "/"


def _preserve_sliceless_retrospectives(
    repo_root: Path, out_dir: Path, scene: str | None
) -> dict[str, bytes]:
    """Snapshot committed retrospective pages that have no page_data slice.

    A few resolved-contract retrospectives ship as committed rendered HTML
    while their source slices do NOT (the corpus that produced them is
    gitignored scratch — see docs/LESSONS.md). `build_site` wipes `out_dir`
    wholesale before re-rendering from slices, which would permanently delete
    these pages. Snapshot them here so the caller can restore them after the
    rebuild. Returns {site-relative path: html bytes}; empty when every
    retrospective dir has a matching slice (self-disabling once slices exist).
    """
    # The page_data source path is always scene-independent; only the rendered
    # output mount point (retros_sub) changes for a trader-only scene export.
    pd_retro = repo_root / "build" / "page_data" / "trader" / "retrospectives"
    have_slice = {p.stem for p in pd_retro.glob("*.json")} if pd_retro.exists() else set()
    retros_sub = "retrospectives" if scene == "trader" else "trader/retrospectives"
    retro_root = out_dir / retros_sub
    preserved: dict[str, bytes] = {}
    if not retro_root.exists():
        return preserved
    for d in sorted(retro_root.iterdir()):
        idx = d / "index.html"
        if d.is_dir() and d.name not in have_slice and idx.exists():
            preserved[f"{retros_sub}/{d.name}/index.html"] = idx.read_bytes()
    return preserved


def build_site(repo_root: Path, out_dir: Path) -> None:
    """Render templates and write to out_dir.

    WARNING: This wipes out_dir entirely before writing. Callers must ensure
    out_dir points to a build-output location, not user data. Committed
    retrospective pages without a page_data slice are snapshotted and restored
    across the wipe (see _preserve_sliceless_retrospectives) so they survive.

    Link mode is controlled by the `PRED_ORACLE_BASE_URL` env var:
      - set to an absolute path ("/carver-briefs/pred-oracle/") or a URL →
        that fixed prefix is applied to every internal link (project-site mode).
      - unset/empty → per-page RELATIVE links, portable across file:// and any
        deploy path (the default; matches the sibling policy-diffs demo).
    """
    raw = os.environ.get("PRED_ORACLE_BASE_URL", "").strip()
    base_url: str | None
    if raw and (raw.startswith("/") or raw.startswith("http")):
        base_url = raw if raw.endswith("/") else raw + "/"
    else:
        base_url = None  # relative mode — computed per output file

    # Scene-only export: when set (e.g. "trader"), build just that scene and
    # mount it at the site root — its pages drop the "<scene>/" path segment and
    # its internal links are rewritten to match. Used for standalone demo folders.
    scene = os.environ.get("PRED_ORACLE_SCENE", "").strip() or None

    templates_dir = repo_root / "build" / "templates"
    static_dir = repo_root / "build" / "static"

    # Snapshot committed retrospective pages whose slices aren't committed, so
    # the wholesale wipe below doesn't permanently delete them.
    preserved_retros = _preserve_sliceless_retrospectives(repo_root, out_dir, scene)

    if out_dir.exists():
        shutil.rmtree(out_dir)
    out_dir.mkdir(parents=True)

    env = Environment(
        loader=FileSystemLoader(str(templates_dir)),
        autoescape=select_autoescape(["html"]),
    )

    # Alpha templates that require a populated slice to render correctly.
    # If the slice JSON is missing (e.g. CI build without corpus), skip them
    # gracefully rather than crashing on undefined variables.
    TEMPLATES_REQUIRING_SLICE = {
        Path("alpha/inbox.html"),
        Path("alpha/dashboard.html"),
        Path("alpha/audit_export.html"),
        Path("beta/heatmap.html"),
        Path("beta/cascades.html"),
        Path("beta/report.html"),
        Path("gamma/scan.html"),
        Path("gamma/dashboard.html"),
    }

    for tpl_path in sorted(templates_dir.rglob("*.html")):
        rel = tpl_path.relative_to(templates_dir)
        # Skip partials (_components) and layout-only base templates
        if any(p.startswith("_") for p in rel.parts):
            continue
        if rel == Path("base.html"):
            continue
        # Scene-only export: skip everything outside the chosen scene (this also
        # drops the top-level landing/close pages, which aren't under any scene).
        if scene and (len(rel.parts) < 2 or rel.parts[0] != scene):
            continue
        # Skip parametric templates; rendered separately below
        if rel in {Path("alpha/ticket_detail.html"), Path("gamma/contract_detail.html"), Path("trader/briefing.html")}:
            continue
        ctx = _load_slice(repo_root, rel)
        # γ scan needs all 3 scan slices simultaneously (Alpine tab UI),
        # not the single JSON the default loader would pick.
        if rel == Path("gamma/scan.html"):
            ctx = _load_gamma_scan_bundle(repo_root)
            if not ctx.get("scans"):
                print(f"  skip {rel}: no scan data")
                continue

        if rel == Path("trader/intro.html"):
            landing_path = repo_root / "build" / "page_data" / "landing.json"
            if landing_path.exists():
                ctx = json.loads(landing_path.read_text())

        if rel == Path("trader/list.html"):
            portfolio_path = repo_root / "build" / "page_data" / "trader" / "portfolio.json"
            if portfolio_path.exists():
                rows = json.loads(portfolio_path.read_text())
                # Add price placeholders for each row (actual prices come from cache)
                prices_dir = repo_root / "build" / "_cache" / "prices"
                for row in rows:
                    price_file = prices_dir / f"{row['contract_id']}.json"
                    if price_file.exists():
                        pd = json.loads(price_file.read_text())
                        series = pd.get("series", [])
                        if series:
                            last_p = series[-1].get("p", 0.5)
                            row["yes_price"] = round(last_p * 100)
                            row["no_price"] = 100 - round(last_p * 100)
                        else:
                            row["yes_price"] = 50
                            row["no_price"] = 50
                    else:
                        row["yes_price"] = 50
                        row["no_price"] = 50
                ctx = {"rows": rows}
            else:
                ctx = {"rows": []}

        if rel == Path("trader/calendar.html"):
            cal_path = repo_root / "build" / "page_data" / "trader" / "calendar.json"
            if cal_path.exists():
                ctx = json.loads(cal_path.read_text())
                ctx["all_events"] = ctx.pop("events", [])
            else:
                ctx = {"months": [], "all_events": [], "today": ""}

        if rel == Path("trader/retrospectives.html"):
            retro_dir = repo_root / "build" / "page_data" / "trader" / "retrospectives"
            retros = []
            if retro_dir.exists():
                for p in sorted(retro_dir.glob("*.json")):
                    retros.append(json.loads(p.read_text()))
            ctx = {"retrospectives": retros}

        # If the slice file is required but missing, skip this template's render
        # entirely. This handles CI builds without the corpus committed.
        if rel in TEMPLATES_REQUIRING_SLICE and not ctx:
            print(f"  skip {rel}: slice missing")
            continue
        out_path = out_dir / _remount_route(_route_for_template(rel), scene)
        ctx["base_url"] = base_url if base_url is not None else _relative_base(out_dir, out_path)
        ctx["scene_only"] = scene is not None

        rendered = env.get_template(rel.as_posix()).render(**ctx)
        if base_url is None:
            rendered = _fileify_links(rendered)
        if scene:
            rendered = _strip_scene_links(rendered, scene)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(rendered)
        print(f"Rendered {rel} → {out_path.relative_to(out_dir)}")

    # Parametric ticket pages: one per ticket slice (α only)
    if scene is None or scene == "alpha":
        n_tickets = _render_parametric_tickets(repo_root, env, out_dir, base_url)
        print(f"alpha/tickets: rendered {n_tickets} pages")

    # γ contract-detail pages: one per contract_detail_pick
    if scene is None or scene == "gamma":
        n_contracts = _render_parametric(
            repo_root, env, out_dir, base_url,
            template_path="gamma/contract_detail.html",
            slice_dir_relative="gamma/contracts",
            site_subpath="gamma/contracts",
        )
        print(f"gamma/contracts: rendered {n_contracts} pages")

    # Trader contract + retrospective pages. In a trader-only export these mount
    # at the root ("contracts/…", "retrospectives/…") with links stripped to match.
    if scene is None or scene == "trader":
        contracts_subpath = "contracts" if scene == "trader" else "trader/contracts"
        retros_subpath = "retrospectives" if scene == "trader" else "trader/retrospectives"
        n_trader = _render_trader_briefings(
            repo_root, env, out_dir, base_url,
            slice_dir_relative="trader/contracts",
            site_subpath=contracts_subpath,
            scene=scene,
        )
        print(f"{contracts_subpath}: rendered {n_trader} pages")

        n_retro = _render_trader_briefings(
            repo_root, env, out_dir, base_url,
            slice_dir_relative="trader/retrospectives",
            site_subpath=retros_subpath,
            scene=scene,
        )
        print(f"{retros_subpath}: rendered {n_retro} pages")

    # Copy static dir
    shutil.copytree(static_dir, out_dir / "static", dirs_exist_ok=True)
    print(f"Copied static assets to {out_dir / 'static'}")

    # Restore committed retrospective pages the wipe removed (sliceless ones).
    for rel, data in preserved_retros.items():
        dest = out_dir / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(data)
    if preserved_retros:
        print(f"Preserved {len(preserved_retros)} sliceless retrospective page(s)")


def main() -> int:
    repo_root = Path(__file__).parent.parent
    build_site(repo_root, repo_root / "site")
    return 0


if __name__ == "__main__":
    sys.exit(main())
