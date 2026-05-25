#!/usr/bin/env bash
# scripts/smoke_v5_v6.sh — pulls SPME v5 and v6, runs single transition end-to-end.
set -euo pipefail

# Load .env
if [ -f .env ]; then
  set -a
  # shellcheck disable=SC1091
  source .env
  set +a
fi

if [ -z "${OPENAI_API_KEY:-}" ]; then
  echo "ERROR: OPENAI_API_KEY not set; populate .env first" >&2
  exit 1
fi

mkdir -p artifacts/spme

# v5: 2024-09-01 (digest XYEY74G7…)
curl -sL -fL -o artifacts/spme/20240901001027.pdf \
  "https://web.archive.org/web/20240901001027id_/https://www.mastercard.us/content/dam/public/mastercardcom/na/global-site/documents/SPME-Manual.pdf"

# v6: 2025-05-24 (digest OTGAYCHJ…)
curl -sL -fL -o artifacts/spme/20250524042807.pdf \
  "https://web.archive.org/web/20250524042807id_/https://www.mastercard.us/content/dam/public/mastercardcom/na/global-site/documents/SPME-Manual.pdf"

# Sanity: confirm both look like PDFs, not HTML redirects
file artifacts/spme/20240901001027.pdf
file artifacts/spme/20250524042807.pdf

# Reset any stale smoke branch in the sibling repo
( cd credio-policies && git checkout main && git branch -D pr-smoke 2>/dev/null || true )

# Run the pipeline through Python (bypasses the CLI's full-fan-out path so we control the pair)
uv run python <<'PY'
from pathlib import Path
from collections import Counter
from pipeline.config import load_config
from pipeline.extract import extract_sections
from pipeline.diff import diff_sections
from pipeline.llm import LLMClient
from pipeline.orchestrator import Orchestrator

cfg = load_config(Path("config/models.yaml"))
llm = LLMClient(cfg)

v5 = extract_sections(Path("artifacts/spme/20240901001027.pdf"))
v6 = extract_sections(Path("artifacts/spme/20250524042807.pdf"))
print(f"v5 sections: {len(v5)}")
print(f"v6 sections: {len(v6)}")

# Heuristic phantom-section check: bare-integer ids > 50 are suspicious
phantoms = [s for s in v6 if "." not in s.section_id and int(s.section_id) > 50]
if phantoms:
    print(f"WARN: {len(phantoms)} likely-phantom sections (bare integer > 50). Examples:")
    for s in phantoms[:5]:
        print(f"  id={s.section_id} title={s.title[:80]}")

deltas = diff_sections(v5, v6)
print(f"section deltas: {len(deltas)} ({Counter(d.kind for d in deltas)})")

orch = Orchestrator(
    cfg=cfg,
    credio_repo=Path("credio-policies"),
    artifacts_dir=Path("artifacts"),
    llm=llm,
)
result = orch.run_transition(
    transition_from="2024-09",
    transition_to="2025-05",
    deltas=deltas,
    branch_base="main",
    branch_name="pr-smoke",
)
print(f"change records: {len(result.change_records)}")
for rec in result.change_records:
    paths = ", ".join(f.path for f in rec.affected_files)
    print(f"  §{rec.section_id} ({rec.materiality}) → {paths}")
PY

# Render the site + PDFs
uv run python -m pipeline.cli render-site --artifact spme
uv run python -m pipeline.cli render-pdfs

echo
echo "=== smoke complete ==="
echo "open credio-policies/dist/timeline.html"
