import argparse
import json
from pathlib import Path

from pipeline.config import load_config
from pipeline.fetch import enumerate_versions, download, fetch_cdx, Snapshot
from pipeline.extract import extract_sections
from pipeline.diff import diff_sections
from pipeline.llm import LLMClient
from pipeline.orchestrator import Orchestrator
from pipeline.pdf_render import render_policy_pdf
from presentation.render import load_site_config, render_site


SPME_URL = "https://www.mastercard.us/content/dam/public/mastercardcom/na/global-site/documents/SPME-Manual.pdf"


def cmd_run_phase(args):
    cfg = load_config(Path("config/models.yaml"))
    llm = LLMClient(cfg)
    artifacts = Path("artifacts")
    credio_repo = Path("credio-policies")

    cdx_rows = fetch_cdx(SPME_URL)
    snapshots = enumerate_versions(cdx_rows)

    sections_by_version: list[tuple[Snapshot, list]] = []
    for s in snapshots:
        pdf_path = artifacts / "spme" / f"{s.timestamp}.pdf"
        download(s, pdf_path)
        sections_by_version.append((s, extract_sections(pdf_path)))

    # One Orchestrator instance per phase: it accumulates cumulative Credio
    # state in-memory across transitions so each subsequent transition's
    # proposer sees the policies as the prior transition left them.
    orch = Orchestrator(cfg=cfg, credio_repo=credio_repo, artifacts_dir=artifacts, llm=llm)
    for i in range(len(sections_by_version) - 1):
        a_snap, a_secs = sections_by_version[i]
        b_snap, b_secs = sections_by_version[i + 1]
        deltas = diff_sections(a_secs, b_secs)
        from_label = f"{a_snap.timestamp[:4]}-{a_snap.timestamp[4:6]}"
        to_label = f"{b_snap.timestamp[:4]}-{b_snap.timestamp[4:6]}"
        orch.run_transition(
            transition_from=from_label, transition_to=to_label,
            deltas=deltas,
        )
    print(json.dumps({"phase": "spme", "transitions": len(sections_by_version) - 1}))


def cmd_render_site(args):
    artifacts = Path("artifacts") / args.artifact
    dist = Path("credio-policies") / "dist"
    site_config = load_site_config(Path("config") / "sites" / f"{args.artifact}.yaml")
    render_site(artifacts_root=artifacts, dist=dist, site_config=site_config)
    print(f"site → {dist}/index.html (root) · {dist}/timeline/ · {dist}/policies/")


def cmd_render_pdfs(args):
    repo = Path("credio-policies")
    for md in (repo / "policies").rglob("policy.md"):
        rel = md.relative_to(repo / "policies").with_suffix(".pdf")
        out = repo / "dist" / "policies" / rel
        render_policy_pdf(md, out)
    print(f"pdfs → {repo}/dist/policies/")


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="cmd", required=True)
    p1 = sub.add_parser("run-phase"); p1.add_argument("--artifact", choices=["spme"], required=True)
    p1.set_defaults(func=cmd_run_phase)
    p2 = sub.add_parser("render-site"); p2.add_argument("--artifact", choices=["spme"], required=True)
    p2.set_defaults(func=cmd_render_site)
    p3 = sub.add_parser("render-pdfs")
    p3.set_defaults(func=cmd_render_pdfs)
    return parser


def main():
    args = build_arg_parser().parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
