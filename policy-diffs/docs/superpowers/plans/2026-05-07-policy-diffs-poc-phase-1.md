# Policy-diffs POC — Phase 1 (SPME) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the end-to-end pipeline that fetches Mastercard SPME PDF versions from Wayback, detects per-section deltas, maps them to a synthetic Credio policy repo, proposes structured policy edits via OpenAI, and renders a static three-layer browser site (timeline → change-cards → tabbed detail) for customer demo.

**Architecture:** Six-stage Python pipeline (fetch · extract · diff · classify · map · propose), deterministic upstream + LLM downstream, output cached as reusable JSON/markdown partials. A separate sibling git repo (`credio-policies/`) holds the synthetic baseline + sequential branches. A renderer transforms the pipeline's change-record JSONs into static HTML pages.

**Tech Stack:** Python 3.12 (uv), `pymupdf` + `pdfplumber` for PDF, `openai` SDK, `redlines` + `markdown-it-py` + `pygments` + `jinja2` for presentation, `pandoc` for policy PDFs, `pytest` for tests.

---

## File Structure

```
policy-diffs/
├── pyproject.toml                          # uv project + deps
├── .gitignore                              # already exists; appended for .venv, artifacts/
├── README.md
├── config/
│   └── models.yaml                         # LLM model config (per stage)
├── pipeline/
│   ├── __init__.py
│   ├── cli.py                              # `python -m pipeline ...`
│   ├── config.py                           # Load models.yaml + env
│   ├── llm.py                              # OpenAI client wrapper
│   ├── fetch.py                            # Wayback CDX + curl fetch
│   ├── extractors/
│   │   ├── __init__.py
│   │   ├── base.py                         # Extractor protocol
│   │   └── pymupdf_pdfplumber.py           # default impl
│   ├── extract.py                          # Section orchestrator over Extractor
│   ├── diff.py                             # Per-section deterministic diff
│   ├── classify.py                         # LLM materiality + summary
│   ├── map_changes.py                      # LLM map MC → Credio policies
│   ├── propose.py                          # LLM emit per-file diff + change record
│   ├── repo_manager.py                     # Apply patches on sequential branches
│   ├── pdf_render.py                       # pandoc invocation
│   └── orchestrator.py                     # End-to-end runner
├── prompts/
│   ├── classify.txt
│   ├── map.txt
│   └── propose.txt
├── presentation/
│   ├── __init__.py
│   ├── render.py                           # HTML site generator
│   ├── redline.py                          # `redlines` lib wrapper + post-processing
│   ├── yaml_diff.py                        # difflib-based YAML diff → HTML
│   └── templates/
│       ├── _base.html.j2
│       ├── timeline.html.j2
│       ├── transition.html.j2
│       └── change.html.j2
├── credio-policies/                        # Sibling repo (own .git, sequential branches)
│   ├── README.md
│   ├── policies/<8 folders>/{policy.md,rules.yaml,source.yaml}
│   └── agents/<2 folders>/runbook.md
├── artifacts/                              # cached PDFs, partials (gitignored)
└── tests/
    ├── conftest.py
    ├── fixtures/
    │   ├── tiny.pdf                        # 1-page test PDF
    │   ├── section_v1.md
    │   ├── section_v2.md
    │   └── change_record.json
    ├── test_config.py
    ├── test_llm.py
    ├── test_fetch.py
    ├── test_extract.py
    ├── test_diff.py
    ├── test_classify.py
    ├── test_map_changes.py
    ├── test_propose.py
    ├── test_repo_manager.py
    ├── test_redline.py
    ├── test_yaml_diff.py
    └── test_render.py
```

**Decomposition rationale:** Each pipeline stage is one file with one responsibility and a tested public function. The `presentation/` package is structurally separate so it can be re-run on cached pipeline output without rerunning LLM calls. Tests are colocated by stage, fixtures shared via `tests/fixtures/`.

---

## Task 1: Project scaffolding

**Files:**
- Create: `pyproject.toml`
- Create: `README.md`
- Modify: `.gitignore`
- Create: `pipeline/__init__.py`, `pipeline/extractors/__init__.py`, `presentation/__init__.py`, `tests/__init__.py`, `tests/conftest.py`
- Create: `config/models.yaml`

- [ ] **Step 1: Write `pyproject.toml`**

```toml
[project]
name = "policy-diffs"
version = "0.1.0"
description = "Mastercard B2B rule-change → Credio policy diff POC"
requires-python = ">=3.12"
dependencies = [
  "pymupdf>=1.24",
  "pdfplumber>=0.11",
  "openai>=1.40",
  "pyyaml>=6.0",
  "jinja2>=3.1",
  "redlines>=0.5",
  "markdown-it-py>=3.0",
  "pygments>=2.18",
  "requests>=2.32",
]

[dependency-groups]
dev = [
  "pytest>=8.0",
  "pytest-mock>=3.14",
]

[tool.pytest.ini_options]
pythonpath = ["."]
testpaths = ["tests"]
```

- [ ] **Step 2: Append to `.gitignore`**

```
.venv/
__pycache__/
*.pyc
artifacts/
.pytest_cache/
```

- [ ] **Step 3: Create empty package init files**

```bash
touch pipeline/__init__.py pipeline/extractors/__init__.py presentation/__init__.py tests/__init__.py tests/conftest.py
```

- [ ] **Step 4: Create `config/models.yaml`**

```yaml
provider: openai
default_model: gpt-5.4-mini
stages:
  classify:
    model: gpt-5.4-mini
  map:
    model: gpt-5.4-mini
  propose:
    model: gpt-5.4-mini
api_key_env: OPENAI_API_KEY
```

- [ ] **Step 5: Create minimal `README.md`**

```markdown
# policy-diffs

POC: Mastercard B2B artifact deltas → Credio policy update proposals.

## Setup
```bash
uv sync
export OPENAI_API_KEY=sk-...
```

## Run pipeline (phase 1: SPME, all 5 transitions)
```bash
uv run python -m pipeline.cli run-phase --artifact spme
```

## Open the demo
```bash
open credio-policies/dist/timeline.html
```

See `docs/superpowers/specs/2026-05-07-policy-diffs-poc-design.md` for full design.
```

- [ ] **Step 6: Verify `uv sync` succeeds**

Run: `uv sync`
Expected: lockfile written, `.venv/` populated, no errors.

- [ ] **Step 7: Verify pytest collects with no tests**

Run: `uv run pytest`
Expected: `no tests ran` (exit 5 is OK).

- [ ] **Step 8: Commit**

```bash
git add pyproject.toml uv.lock README.md .gitignore pipeline/ presentation/ tests/ config/
git commit -m "chore: project scaffolding (uv, pytest, package layout, models config)"
```

---

## Task 2: Config loader

**Files:**
- Create: `pipeline/config.py`
- Create: `tests/test_config.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_config.py
import os
import textwrap
from pathlib import Path

from pipeline.config import load_config


def test_load_config_reads_default_model_and_stages(tmp_path: Path, monkeypatch):
    cfg_file = tmp_path / "models.yaml"
    cfg_file.write_text(textwrap.dedent("""
        provider: openai
        default_model: gpt-5.4-mini
        stages:
          classify:
            model: gpt-5.4-mini
          map:
            model: gpt-5.4-large
        api_key_env: OPENAI_API_KEY
    """).strip())
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")

    cfg = load_config(cfg_file)

    assert cfg.provider == "openai"
    assert cfg.model_for("classify") == "gpt-5.4-mini"
    assert cfg.model_for("map") == "gpt-5.4-large"
    assert cfg.model_for("propose") == "gpt-5.4-mini"  # falls back to default
    assert cfg.api_key == "sk-test"


def test_load_config_raises_when_api_key_env_missing(tmp_path: Path, monkeypatch):
    cfg_file = tmp_path / "models.yaml"
    cfg_file.write_text("provider: openai\ndefault_model: gpt-5.4-mini\nstages: {}\napi_key_env: OPENAI_API_KEY\n")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    import pytest
    with pytest.raises(RuntimeError, match="OPENAI_API_KEY"):
        load_config(cfg_file)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_config.py -v`
Expected: FAIL — module not found.

- [ ] **Step 3: Write minimal implementation**

```python
# pipeline/config.py
import os
from dataclasses import dataclass
from pathlib import Path

import yaml


@dataclass(frozen=True)
class Config:
    provider: str
    default_model: str
    stage_models: dict[str, str]
    api_key: str

    def model_for(self, stage: str) -> str:
        return self.stage_models.get(stage, self.default_model)


def load_config(path: Path) -> Config:
    raw = yaml.safe_load(path.read_text())
    api_key_env = raw.get("api_key_env", "OPENAI_API_KEY")
    api_key = os.environ.get(api_key_env)
    if not api_key:
        raise RuntimeError(f"Missing API key — set ${api_key_env}")
    stage_models = {
        name: stage["model"]
        for name, stage in (raw.get("stages") or {}).items()
        if isinstance(stage, dict) and "model" in stage
    }
    return Config(
        provider=raw["provider"],
        default_model=raw["default_model"],
        stage_models=stage_models,
        api_key=api_key,
    )
```

- [ ] **Step 4: Run tests to verify pass**

Run: `uv run pytest tests/test_config.py -v`
Expected: 2 passed.

- [ ] **Step 5: Commit**

```bash
git add pipeline/config.py tests/test_config.py
git commit -m "feat(config): load per-stage LLM model config from yaml"
```

---

## Task 3: LLM client wrapper

**Files:**
- Create: `pipeline/llm.py`
- Create: `tests/test_llm.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_llm.py
from unittest.mock import MagicMock

import pytest

from pipeline.config import Config
from pipeline.llm import LLMClient


@pytest.fixture
def cfg():
    return Config(
        provider="openai",
        default_model="gpt-5.4-mini",
        stage_models={"map": "gpt-5.4-large"},
        api_key="sk-test",
    )


def test_complete_uses_per_stage_model(cfg, mocker):
    fake_openai = MagicMock()
    fake_openai.chat.completions.create.return_value = MagicMock(
        choices=[MagicMock(message=MagicMock(content='{"materiality":"substantive"}'))]
    )
    mocker.patch("pipeline.llm.OpenAI", return_value=fake_openai)

    client = LLMClient(cfg)
    out = client.complete_json(
        stage="map",
        system="you are an analyst",
        user="diff here",
        json_schema={"type": "object"},
    )

    assert out == {"materiality": "substantive"}
    call_kwargs = fake_openai.chat.completions.create.call_args.kwargs
    assert call_kwargs["model"] == "gpt-5.4-large"


def test_complete_uses_default_model_for_unspecified_stage(cfg, mocker):
    fake_openai = MagicMock()
    fake_openai.chat.completions.create.return_value = MagicMock(
        choices=[MagicMock(message=MagicMock(content='{}'))]
    )
    mocker.patch("pipeline.llm.OpenAI", return_value=fake_openai)

    client = LLMClient(cfg)
    client.complete_json(stage="classify", system="s", user="u", json_schema={"type": "object"})

    assert fake_openai.chat.completions.create.call_args.kwargs["model"] == "gpt-5.4-mini"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_llm.py -v`
Expected: FAIL — module not found.

- [ ] **Step 3: Write minimal implementation**

```python
# pipeline/llm.py
import json
from typing import Any

from openai import OpenAI

from pipeline.config import Config


class LLMClient:
    def __init__(self, cfg: Config):
        self._cfg = cfg
        self._client = OpenAI(api_key=cfg.api_key)

    def complete_json(
        self,
        *,
        stage: str,
        system: str,
        user: str,
        json_schema: dict[str, Any],
    ) -> dict[str, Any]:
        model = self._cfg.model_for(stage)
        resp = self._client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            response_format={
                "type": "json_schema",
                "json_schema": {"name": stage, "schema": json_schema, "strict": True},
            },
        )
        return json.loads(resp.choices[0].message.content)
```

- [ ] **Step 4: Run tests to verify pass**

Run: `uv run pytest tests/test_llm.py -v`
Expected: 2 passed.

- [ ] **Step 5: Commit**

```bash
git add pipeline/llm.py tests/test_llm.py
git commit -m "feat(llm): OpenAI client with per-stage model selection + JSON schema responses"
```

---

## Task 4: Wayback fetcher

**Files:**
- Create: `pipeline/fetch.py`
- Create: `tests/test_fetch.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_fetch.py
from unittest.mock import MagicMock

import pytest

from pipeline.fetch import enumerate_versions, raw_url, Snapshot


def test_enumerate_versions_dedupes_by_digest():
    cdx_rows = [
        ["timestamp", "digest", "statuscode", "mimetype"],
        ["20220628210349", "AAAA", "200", "application/pdf"],
        ["20220708091346", "AAAA", "200", "application/pdf"],          # dupe digest
        ["20230516183156", "BBBB", "200", "application/pdf"],
        ["20230516183200", "CCCC", "200", "warc/revisit"],             # skip revisit
        ["20230907012045", "DDDD", "200", "application/pdf"],
    ]

    snapshots = enumerate_versions(cdx_rows)

    assert [s.digest for s in snapshots] == ["AAAA", "BBBB", "DDDD"]
    assert snapshots[0].timestamp == "20220628210349"  # earliest kept


def test_raw_url_uses_id_form():
    s = Snapshot(timestamp="20220628210349", digest="AAAA", original="https://example.com/a.pdf")
    assert raw_url(s) == "https://web.archive.org/web/20220628210349id_/https://example.com/a.pdf"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_fetch.py -v`
Expected: FAIL — module not found.

- [ ] **Step 3: Write minimal implementation**

```python
# pipeline/fetch.py
import subprocess
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Snapshot:
    timestamp: str
    digest: str
    original: str


def enumerate_versions(cdx_rows: list[list[str]]) -> list[Snapshot]:
    """Dedupe CDX rows by digest, keeping the earliest timestamp. Skip warc/revisit."""
    if not cdx_rows:
        return []
    header, *data = cdx_rows
    cols = {name: i for i, name in enumerate(header)}
    seen: dict[str, Snapshot] = {}
    for row in data:
        if row[cols["mimetype"]] == "warc/revisit":
            continue
        if row[cols["statuscode"]] != "200":
            continue
        digest = row[cols["digest"]]
        if digest not in seen:
            # CDX rows arrive sorted by timestamp ascending; first sighting is earliest
            seen[digest] = Snapshot(
                timestamp=row[cols["timestamp"]],
                digest=digest,
                original=row[cols.get("original", 2)] if "original" in cols else "",
            )
    return list(seen.values())


def raw_url(snapshot: Snapshot) -> str:
    return f"https://web.archive.org/web/{snapshot.timestamp}id_/{snapshot.original}"


def fetch_cdx(target_url: str) -> list[list[str]]:
    """Hit the Wayback CDX API via curl. Returns parsed JSON rows."""
    import json
    cdx = (
        "https://web.archive.org/cdx/search/cdx?"
        f"url={target_url}&output=json"
        "&fl=timestamp,digest,statuscode,mimetype,original"
    )
    out = subprocess.run(["curl", "-s", cdx], capture_output=True, text=True, check=True)
    return json.loads(out.stdout)


def download(snapshot: Snapshot, dest: Path) -> Path:
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.exists():
        return dest
    subprocess.run(
        ["curl", "-sL", "-o", str(dest), raw_url(snapshot)],
        check=True,
    )
    return dest
```

- [ ] **Step 4: Run tests to verify pass**

Run: `uv run pytest tests/test_fetch.py -v`
Expected: 2 passed.

- [ ] **Step 5: Commit**

```bash
git add pipeline/fetch.py tests/test_fetch.py
git commit -m "feat(fetch): Wayback CDX enumeration with digest dedupe + raw id_ fetch"
```

---

## Task 5: Extractor protocol + default impl

**Files:**
- Create: `pipeline/extractors/base.py`
- Create: `pipeline/extractors/pymupdf_pdfplumber.py`
- Create: `pipeline/extract.py`
- Create: `tests/fixtures/tiny.pdf` (binary, 1 page)
- Create: `tests/test_extract.py`

- [ ] **Step 1: Generate the test fixture PDF**

Run this once to produce a 1-page test PDF:

```bash
uv run python -c "
import fitz
doc = fitz.open()
page = doc.new_page()
page.insert_text((50, 60), '1. Introduction', fontsize=16)
page.insert_text((50, 100), 'This is the intro section.', fontsize=11)
page.insert_text((50, 150), '2. Fraud Monitoring', fontsize=16)
page.insert_text((50, 190), 'Acquirers must monitor fraud-to-sales ratio.', fontsize=11)
doc.save('tests/fixtures/tiny.pdf')
"
```

- [ ] **Step 2: Write the failing test**

```python
# tests/test_extract.py
from pathlib import Path

from pipeline.extract import extract_sections


FIXTURE = Path("tests/fixtures/tiny.pdf")


def test_extract_sections_splits_by_numbered_headings():
    sections = extract_sections(FIXTURE)

    assert len(sections) == 2
    assert sections[0].section_id == "1"
    assert sections[0].title == "Introduction"
    assert "intro section" in sections[0].markdown
    assert sections[1].section_id == "2"
    assert sections[1].title == "Fraud Monitoring"
    assert "fraud-to-sales" in sections[1].markdown
```

- [ ] **Step 3: Run test to verify it fails**

Run: `uv run pytest tests/test_extract.py -v`
Expected: FAIL — module not found.

- [ ] **Step 4: Implement extractor protocol**

```python
# pipeline/extractors/base.py
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol


@dataclass(frozen=True)
class Section:
    section_id: str
    title: str
    markdown: str


class Extractor(Protocol):
    def extract(self, pdf_path: Path) -> list[Section]: ...
```

- [ ] **Step 5: Implement pymupdf+pdfplumber extractor**

```python
# pipeline/extractors/pymupdf_pdfplumber.py
import re
from pathlib import Path

import fitz  # pymupdf

from pipeline.extractors.base import Section


HEADING_RE = re.compile(r"^(\d+(?:\.\d+)*)\s+(.+)$")


class PyMuPdfExtractor:
    """Default extractor — pymupdf for body text, pdfplumber for tables (later)."""

    def extract(self, pdf_path: Path) -> list[Section]:
        doc = fitz.open(pdf_path)
        text = "\n".join(page.get_text() for page in doc)
        return _split_sections(text)


def _split_sections(text: str) -> list[Section]:
    lines = text.splitlines()
    sections: list[Section] = []
    current_id: str | None = None
    current_title: str | None = None
    current_body: list[str] = []
    for line in lines:
        m = HEADING_RE.match(line.strip())
        if m and len(m.group(1).split(".")) <= 3:
            if current_id is not None:
                sections.append(Section(current_id, current_title or "", "\n".join(current_body).strip()))
            current_id = m.group(1)
            current_title = m.group(2).strip()
            current_body = []
        else:
            current_body.append(line)
    if current_id is not None:
        sections.append(Section(current_id, current_title or "", "\n".join(current_body).strip()))
    return sections
```

- [ ] **Step 6: Implement extract orchestrator**

```python
# pipeline/extract.py
from pathlib import Path

from pipeline.extractors.base import Extractor, Section
from pipeline.extractors.pymupdf_pdfplumber import PyMuPdfExtractor


def extract_sections(pdf_path: Path, extractor: Extractor | None = None) -> list[Section]:
    return (extractor or PyMuPdfExtractor()).extract(pdf_path)
```

- [ ] **Step 7: Run tests to verify pass**

Run: `uv run pytest tests/test_extract.py -v`
Expected: 1 passed.

- [ ] **Step 8: Commit**

```bash
git add pipeline/extractors/ pipeline/extract.py tests/test_extract.py tests/fixtures/tiny.pdf
git commit -m "feat(extract): pymupdf-based section splitter with adapter interface"
```

---

## Task 6: Section diff

**Files:**
- Create: `pipeline/diff.py`
- Create: `tests/fixtures/section_v1.md`
- Create: `tests/fixtures/section_v2.md`
- Create: `tests/test_diff.py`

- [ ] **Step 1: Create fixture files**

`tests/fixtures/section_v1.md`:
```
The acquirer must respond within one hundred eighty (180) days with documentation of remediation actions taken.
```

`tests/fixtures/section_v2.md`:
```
The acquirer must respond within one hundred twenty (120) days with documentation of remediation actions taken, including video-KYC re-verification of the merchant's beneficial owners.
```

- [ ] **Step 2: Write the failing test**

```python
# tests/test_diff.py
from pathlib import Path

from pipeline.extractors.base import Section
from pipeline.diff import diff_sections, SectionDelta


def test_diff_sections_only_returns_changed():
    v1 = [
        Section("1", "Intro", "unchanged content"),
        Section("2", "BRAM", "old text 180 days"),
    ]
    v2 = [
        Section("1", "Intro", "unchanged content"),
        Section("2", "BRAM", "new text 120 days"),
        Section("3", "New Section", "added"),
    ]

    deltas = diff_sections(v1, v2)

    ids = {d.section_id for d in deltas}
    assert ids == {"2", "3"}
    bram = next(d for d in deltas if d.section_id == "2")
    assert bram.kind == "modified"
    assert "180 days" in bram.before
    assert "120 days" in bram.after
    new = next(d for d in deltas if d.section_id == "3")
    assert new.kind == "added"


def test_diff_sections_detects_removed_section():
    v1 = [Section("1", "A", "x"), Section("2", "B", "y")]
    v2 = [Section("1", "A", "x")]

    deltas = diff_sections(v1, v2)

    assert len(deltas) == 1
    assert deltas[0].section_id == "2"
    assert deltas[0].kind == "removed"
```

- [ ] **Step 3: Run test to verify it fails**

Run: `uv run pytest tests/test_diff.py -v`
Expected: FAIL — module not found.

- [ ] **Step 4: Write minimal implementation**

```python
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
```

- [ ] **Step 5: Run tests to verify pass**

Run: `uv run pytest tests/test_diff.py -v`
Expected: 2 passed.

- [ ] **Step 6: Commit**

```bash
git add pipeline/diff.py tests/test_diff.py tests/fixtures/section_v1.md tests/fixtures/section_v2.md
git commit -m "feat(diff): per-section delta detection (added/removed/modified)"
```

---

## Task 7: Synthetic Credio repo bootstrap

**Files:**
- Create: `credio-policies/` (sibling git repo)
- Create: `credio-policies/README.md`
- Create: `credio-policies/policies/<8 folders>/{policy.md, rules.yaml, source.yaml}`
- Create: `credio-policies/agents/<2 folders>/runbook.md`
- Create: `tests/test_credio_baseline.py` (structural validation)

The eight baseline policies (anchored to SPME v1, 2022-06):
1. **fraud_monitoring** — fraud-to-sales ratio thresholds, monitoring cadence (SPME §3.x)
2. **bram_response** — BRAM investigation response window + evidence package (SPME §10.x)
3. **ecp_thresholds** — Excessive Chargeback Program thresholds (SPME §11.x)
4. **kyb_acquirer** — Acquirer KYB obligations on merchants (SPME §2.x)
5. **chargeback_handling** — Dispute lifecycle ops (cross-ref to Chargeback Guide; SPME §10.x)
6. **refund_policy** — Refund processing rules
7. **ato_detection** — Account-takeover signals + 3DS challenge handling (SPME §6.x)
8. **content_moderation** — BRAM brand-integrity / prohibited content (SPME §10.x)

- [ ] **Step 1: Initialize the sibling repo**

```bash
mkdir -p credio-policies && cd credio-policies && git init -b main
```

- [ ] **Step 2: Write `credio-policies/README.md`**

```markdown
# Credio Policy Library

Internal compliance rulebook referenced by Credio's risk and compliance agents.
Each `policies/<area>/` folder contains:
- `policy.md`   — narrative, distributed to compliance staff (also rendered to PDF in `dist/`)
- `rules.yaml`  — machine-actionable thresholds and required actions
- `source.yaml` — Mastercard rule citations that justify the policy

Branches: each non-`main` branch represents a proposed update against an upstream Mastercard refresh.
```

- [ ] **Step 3: Author `policies/bram_response/policy.md` (full example)**

```markdown
# BRAM Investigation Response

When Mastercard issues a Business Risk Assessment and Mitigation (BRAM) investigation
notice for one of our merchants, the acquirer must halt new merchant onboarding
immediately and submit an evidence package within one hundred eighty (180) days
of receipt of the notice.

## Required actions

1. Halt new merchant onboarding for the merchant under investigation.
2. Compile and submit an evidence package containing:
   - Transaction monitoring records covering the prior 180 days.
   - A written corrective action plan.
3. Notify the Credio Compliance lead within 24 hours of receipt.

Source authority: Mastercard SPME §10.2.
```

- [ ] **Step 4: Author `policies/bram_response/rules.yaml` (full example)**

```yaml
program: BRAM
authority: Mastercard SPME §10.2
response_window_days: 180
required_evidence:
  - transaction_monitoring_records
  - corrective_action_plan
halt_actions:
  - halt_new_merchant_onboarding
internal_notification_hours: 24
agent_owner: bram_response_agent
```

- [ ] **Step 5: Author `policies/bram_response/source.yaml` (full example)**

```yaml
mastercard_artifact: SPME
sections:
  - id: "10.2"
    title: BRAM Investigation Process
    anchor_version: "2022-06"
```

- [ ] **Step 6: Author the remaining 7 policy folders**

Apply the same `policy.md` + `rules.yaml` + `source.yaml` pattern. For each, ground the content in real SPME v1 (2022-06) language. Keep narrative ~100–200 words, rules.yaml ~6–12 keys.

Specific guidance per policy (paste from SPME v1 extracted markdown when available; otherwise draft realistic content the engineer can refine):

- **fraud_monitoring** — `fraud_to_sales_ratio_threshold: 0.015`, `min_count_per_month: 100`, monitoring cadence: monthly. Cite SPME §3.7.
- **ecp_thresholds** — `chargeback_to_transaction_ratio_threshold: 0.015`, `min_chargeback_count: 100`, `program_tier: standard | excessive`. Cite SPME §11.4.
- **kyb_acquirer** — required KYB documents (incorporation, beneficial ownership, AML screen). Cite SPME §2.x.
- **chargeback_handling** — first-presentment / chargeback / second-presentment / pre-arb / arb states with evidence requirements. Cite SPME §10.x and Chargeback Guide.
- **refund_policy** — refund_window_days, partial-refund rules. Cite SPME §10.x.
- **ato_detection** — 3DS challenge requirement on high-risk auth, signals (geo/device/velocity). Cite SPME §6.2.
- **content_moderation** — BRAM prohibited content categories. Cite SPME §10.5.

- [ ] **Step 7: Author two minimal agent runbooks**

Create `agents/fraud_ops/runbook.md` and `agents/bram_response/runbook.md`. Each is ~10 lines: "When event X happens, look up rules.yaml in policies/<area>/, apply thresholds, escalate or auto-action."

`agents/bram_response/runbook.md` example:

```markdown
# BRAM Response Agent Runbook

1. On BRAM notice received: read `policies/bram_response/rules.yaml`.
2. Halt actions listed under `halt_actions`.
3. Open a case file; collect evidence from data sources matching `required_evidence`.
4. Notify Credio Compliance lead within `internal_notification_hours` hours.
5. Submit response within `response_window_days` days.
```

- [ ] **Step 8: Write the failing structural test**

```python
# tests/test_credio_baseline.py
from pathlib import Path

import pytest
import yaml

ROOT = Path("credio-policies")
EXPECTED_POLICIES = [
    "fraud_monitoring",
    "bram_response",
    "ecp_thresholds",
    "kyb_acquirer",
    "chargeback_handling",
    "refund_policy",
    "ato_detection",
    "content_moderation",
]


@pytest.mark.parametrize("name", EXPECTED_POLICIES)
def test_policy_has_three_required_files(name):
    folder = ROOT / "policies" / name
    assert (folder / "policy.md").exists(), f"{name} missing policy.md"
    assert (folder / "rules.yaml").exists(), f"{name} missing rules.yaml"
    assert (folder / "source.yaml").exists(), f"{name} missing source.yaml"


@pytest.mark.parametrize("name", EXPECTED_POLICIES)
def test_rules_yaml_is_valid(name):
    data = yaml.safe_load((ROOT / "policies" / name / "rules.yaml").read_text())
    assert isinstance(data, dict) and data, f"{name} rules.yaml empty or not a mapping"


@pytest.mark.parametrize("name", EXPECTED_POLICIES)
def test_source_yaml_cites_at_least_one_section(name):
    data = yaml.safe_load((ROOT / "policies" / name / "source.yaml").read_text())
    assert "sections" in data and len(data["sections"]) >= 1
```

- [ ] **Step 9: Run tests to verify pass**

Run: `uv run pytest tests/test_credio_baseline.py -v`
Expected: 24 passed (8 policies × 3 tests).

- [ ] **Step 10: Commit baseline in the sibling repo**

```bash
cd credio-policies
git add .
git commit -m "feat: baseline policy library anchored to SPME v1 (2022-06)"
cd ..
```

- [ ] **Step 11: Commit the structural test in the parent repo**

```bash
git add tests/test_credio_baseline.py
git commit -m "test: structural validation of credio-policies baseline"
```

---

## Task 8: Classifier

**Files:**
- Create: `prompts/classify.txt`
- Create: `pipeline/classify.py`
- Create: `tests/test_classify.py`

- [ ] **Step 1: Write `prompts/classify.txt`**

```
You are an expert payments compliance analyst.

You will be given a section diff from Mastercard SPME (Security Rules and Procedures, Merchant Edition) showing the change between two published versions of one section.

Your job:
1. Summarise the change in one paragraph (max 60 words), in plain English.
2. Score the materiality on this fixed scale:
   - "cosmetic"     — typo, whitespace, or pure formatting
   - "clarifying"   — wording change with no semantic effect on obligations
   - "substantive"  — a genuine change in obligation, threshold, scope, or evidence
   - "breaking"     — substantive change that almost certainly invalidates existing acquirer/processor controls
3. Echo back the section_id and title from the input.

Return strictly the JSON schema specified.
```

- [ ] **Step 2: Write the failing test**

```python
# tests/test_classify.py
from pipeline.classify import classify_delta, ClassificationRecord
from pipeline.diff import SectionDelta


def test_classify_delta_returns_record(mocker):
    mock_llm = mocker.MagicMock()
    mock_llm.complete_json.return_value = {
        "section_id": "10.2",
        "title": "BRAM Investigation Process",
        "summary": "Response window reduced from 180 to 120 days; new video-KYC evidence requirement added.",
        "materiality": "substantive",
    }

    delta = SectionDelta(
        section_id="10.2",
        title="BRAM Investigation Process",
        kind="modified",
        before="180 days",
        after="120 days, video KYC required",
    )

    rec = classify_delta(delta, llm=mock_llm)

    assert isinstance(rec, ClassificationRecord)
    assert rec.section_id == "10.2"
    assert rec.materiality == "substantive"
    assert "180" in rec.summary or "120" in rec.summary

    call = mock_llm.complete_json.call_args.kwargs
    assert call["stage"] == "classify"
    assert "180 days" in call["user"] and "120 days" in call["user"]
```

- [ ] **Step 3: Run test to verify it fails**

Run: `uv run pytest tests/test_classify.py -v`
Expected: FAIL — module not found.

- [ ] **Step 4: Implement classifier**

```python
# pipeline/classify.py
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from pipeline.diff import SectionDelta
from pipeline.llm import LLMClient


PROMPT = (Path(__file__).parent.parent / "prompts" / "classify.txt").read_text()

SCHEMA = {
    "type": "object",
    "properties": {
        "section_id": {"type": "string"},
        "title": {"type": "string"},
        "summary": {"type": "string"},
        "materiality": {
            "type": "string",
            "enum": ["cosmetic", "clarifying", "substantive", "breaking"],
        },
    },
    "required": ["section_id", "title", "summary", "materiality"],
    "additionalProperties": False,
}


@dataclass(frozen=True)
class ClassificationRecord:
    section_id: str
    title: str
    summary: str
    materiality: Literal["cosmetic", "clarifying", "substantive", "breaking"]


def classify_delta(delta: SectionDelta, *, llm: LLMClient) -> ClassificationRecord:
    user = (
        f"section_id: {delta.section_id}\n"
        f"title: {delta.title}\n"
        f"kind: {delta.kind}\n\n"
        f"--- BEFORE ---\n{delta.before}\n\n"
        f"--- AFTER ---\n{delta.after}\n"
    )
    out = llm.complete_json(stage="classify", system=PROMPT, user=user, json_schema=SCHEMA)
    return ClassificationRecord(**out)
```

- [ ] **Step 5: Run tests to verify pass**

Run: `uv run pytest tests/test_classify.py -v`
Expected: 1 passed.

- [ ] **Step 6: Commit**

```bash
git add prompts/classify.txt pipeline/classify.py tests/test_classify.py
git commit -m "feat(classify): LLM materiality scoring + plain-English summary"
```

---

## Task 9: Mapper

**Files:**
- Create: `prompts/map.txt`
- Create: `pipeline/map_changes.py`
- Create: `tests/test_map_changes.py`

- [ ] **Step 1: Write `prompts/map.txt`**

```
You are a payments compliance analyst mapping Mastercard SPME rule changes to Credio's internal policy library.

You will be given:
1. The Credio policy library catalog: a list of policy folders with a 1-line description and the Mastercard sections they cite.
2. One Mastercard SPME section diff (before / after).

Your job:
- List which Credio policy folders are likely affected. Cite policies by exact folder name.
- For each, write a 1–2 sentence rationale that names the specific obligation that shifted.
- Echo back the SPME section_id.

If no Credio policy is affected, return an empty `affected_policies` list and a `rationale` explaining why.

Return strictly the JSON schema specified.
```

- [ ] **Step 2: Write the failing test**

```python
# tests/test_map_changes.py
from pipeline.map_changes import map_delta, MappingRecord, PolicyCatalogEntry
from pipeline.classify import ClassificationRecord


def test_map_delta_returns_affected_policies(mocker):
    mock_llm = mocker.MagicMock()
    mock_llm.complete_json.return_value = {
        "section_id": "10.2",
        "affected_policies": [
            {"policy": "bram_response", "rationale": "Response window obligation changes."},
            {"policy": "kyb_acquirer", "rationale": "New video-KYC requirement adds an acquirer obligation."},
        ],
    }

    catalog = [
        PolicyCatalogEntry(name="bram_response", description="BRAM investigation response", cited_sections=["10.2"]),
        PolicyCatalogEntry(name="fraud_monitoring", description="Fraud thresholds", cited_sections=["3.7"]),
        PolicyCatalogEntry(name="kyb_acquirer", description="Acquirer KYB obligations", cited_sections=["2.1"]),
    ]
    classification = ClassificationRecord(
        section_id="10.2",
        title="BRAM Investigation Process",
        summary="Response window cut; video KYC added.",
        materiality="substantive",
    )

    rec = map_delta(classification, before="…180 days…", after="…120 days; video KYC…", catalog=catalog, llm=mock_llm)

    assert isinstance(rec, MappingRecord)
    assert {p.policy for p in rec.affected_policies} == {"bram_response", "kyb_acquirer"}


def test_map_delta_handles_empty_affected(mocker):
    mock_llm = mocker.MagicMock()
    mock_llm.complete_json.return_value = {
        "section_id": "99.9",
        "affected_policies": [],
        "rationale": "Section concerns physical card embossing; no Credio surface.",
    }

    catalog = [PolicyCatalogEntry(name="x", description="", cited_sections=[])]
    classification = ClassificationRecord(
        section_id="99.9", title="Embossing", summary="", materiality="substantive"
    )
    rec = map_delta(classification, before="", after="", catalog=catalog, llm=mock_llm)
    assert rec.affected_policies == []
    assert rec.rationale and "physical card" in rec.rationale
```

- [ ] **Step 3: Run test to verify it fails**

Run: `uv run pytest tests/test_map_changes.py -v`
Expected: FAIL — module not found.

- [ ] **Step 4: Implement mapper**

```python
# pipeline/map_changes.py
import json
from dataclasses import dataclass
from pathlib import Path

from pipeline.classify import ClassificationRecord
from pipeline.llm import LLMClient


PROMPT = (Path(__file__).parent.parent / "prompts" / "map.txt").read_text()

SCHEMA = {
    "type": "object",
    "properties": {
        "section_id": {"type": "string"},
        "affected_policies": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "policy": {"type": "string"},
                    "rationale": {"type": "string"},
                },
                "required": ["policy", "rationale"],
                "additionalProperties": False,
            },
        },
        "rationale": {"type": "string"},
    },
    "required": ["section_id", "affected_policies"],
    "additionalProperties": False,
}


@dataclass(frozen=True)
class PolicyCatalogEntry:
    name: str
    description: str
    cited_sections: list[str]


@dataclass(frozen=True)
class AffectedPolicy:
    policy: str
    rationale: str


@dataclass(frozen=True)
class MappingRecord:
    section_id: str
    affected_policies: list[AffectedPolicy]
    rationale: str | None = None


def map_delta(
    classification: ClassificationRecord,
    *,
    before: str,
    after: str,
    catalog: list[PolicyCatalogEntry],
    llm: LLMClient,
) -> MappingRecord:
    user = (
        "Credio policy catalog:\n"
        + json.dumps([c.__dict__ for c in catalog], indent=2)
        + "\n\nMastercard SPME diff:\n"
        f"section_id: {classification.section_id}\n"
        f"title: {classification.title}\n"
        f"materiality: {classification.materiality}\n"
        f"summary: {classification.summary}\n\n"
        f"--- BEFORE ---\n{before}\n\n"
        f"--- AFTER ---\n{after}\n"
    )
    out = llm.complete_json(stage="map", system=PROMPT, user=user, json_schema=SCHEMA)
    return MappingRecord(
        section_id=out["section_id"],
        affected_policies=[AffectedPolicy(**p) for p in out["affected_policies"]],
        rationale=out.get("rationale"),
    )
```

- [ ] **Step 5: Run tests to verify pass**

Run: `uv run pytest tests/test_map_changes.py -v`
Expected: 2 passed.

- [ ] **Step 6: Commit**

```bash
git add prompts/map.txt pipeline/map_changes.py tests/test_map_changes.py
git commit -m "feat(map): LLM-driven Mastercard section → Credio policy mapping"
```

---

## Task 10: Proposer

**Files:**
- Create: `prompts/propose.txt`
- Create: `pipeline/propose.py`
- Create: `tests/test_propose.py`

- [ ] **Step 1: Write `prompts/propose.txt`**

```
You are a payments compliance analyst proposing a concrete edit to a Credio policy file in response to a Mastercard SPME change.

You will be given:
1. The current contents of one Credio policy file (markdown or yaml).
2. The Mastercard SPME section diff (before / after).
3. The rationale for why this file is affected.

Your job: produce the new full contents of the file. Preserve formatting style. Do NOT add commentary or markers — only the new file contents.

Also produce a 1-sentence change_summary describing the specific edit.

Return strictly the JSON schema specified.
```

- [ ] **Step 2: Write the failing test**

```python
# tests/test_propose.py
from pipeline.propose import propose_edit, FileEdit


def test_propose_edit_returns_new_contents(mocker):
    mock_llm = mocker.MagicMock()
    mock_llm.complete_json.return_value = {
        "new_contents": "response_window_days: 120\n",
        "change_summary": "Reduce BRAM response window to 120 days.",
    }

    edit = propose_edit(
        policy_path="policies/bram_response/rules.yaml",
        current_contents="response_window_days: 180\n",
        section_id="10.2",
        section_before="…180 days…",
        section_after="…120 days…",
        rationale="Response window obligation changed.",
        llm=mock_llm,
    )

    assert isinstance(edit, FileEdit)
    assert edit.policy_path == "policies/bram_response/rules.yaml"
    assert "120" in edit.new_contents and "180" not in edit.new_contents
    assert edit.change_summary
```

- [ ] **Step 3: Run test to verify it fails**

Run: `uv run pytest tests/test_propose.py -v`
Expected: FAIL — module not found.

- [ ] **Step 4: Implement proposer**

```python
# pipeline/propose.py
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
    user = (
        f"File: {policy_path}\n\n"
        f"--- CURRENT CONTENTS ---\n{current_contents}\n\n"
        f"Mastercard SPME §{section_id}\n"
        f"--- BEFORE ---\n{section_before}\n\n"
        f"--- AFTER ---\n{section_after}\n\n"
        f"Rationale: {rationale}\n"
    )
    out = llm.complete_json(stage="propose", system=PROMPT, user=user, json_schema=SCHEMA)
    return FileEdit(
        policy_path=policy_path,
        old_contents=current_contents,
        new_contents=out["new_contents"],
        change_summary=out["change_summary"],
    )
```

- [ ] **Step 5: Run tests to verify pass**

Run: `uv run pytest tests/test_propose.py -v`
Expected: 1 passed.

- [ ] **Step 6: Commit**

```bash
git add prompts/propose.txt pipeline/propose.py tests/test_propose.py
git commit -m "feat(propose): LLM emits full new file contents per affected Credio policy"
```

---

## Task 11: Repo manager (sequential branches)

**Files:**
- Create: `pipeline/repo_manager.py`
- Create: `tests/test_repo_manager.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_repo_manager.py
import subprocess
from pathlib import Path

import pytest

from pipeline.propose import FileEdit
from pipeline.repo_manager import apply_edits_on_branch


def _git(*args, cwd: Path):
    subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True)


@pytest.fixture
def tmp_credio_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "credio-policies"
    repo.mkdir()
    _git("init", "-b", "main", cwd=repo)
    _git("config", "user.email", "test@example.com", cwd=repo)
    _git("config", "user.name", "Test", cwd=repo)
    (repo / "policies" / "bram_response").mkdir(parents=True)
    (repo / "policies" / "bram_response" / "rules.yaml").write_text("response_window_days: 180\n")
    _git("add", ".", cwd=repo)
    _git("commit", "-m", "baseline", cwd=repo)
    return repo


def test_apply_edits_creates_branch_and_commit(tmp_credio_repo: Path):
    edits = [
        FileEdit(
            policy_path="policies/bram_response/rules.yaml",
            old_contents="response_window_days: 180\n",
            new_contents="response_window_days: 120\n",
            change_summary="Cut BRAM window 180→120",
        )
    ]

    apply_edits_on_branch(
        repo=tmp_credio_repo,
        branch="pr-1",
        base="main",
        edits=edits,
        message="SPME 2023-05 update",
    )

    out = subprocess.run(
        ["git", "branch", "--list", "pr-1"], cwd=tmp_credio_repo, capture_output=True, text=True, check=True
    )
    assert "pr-1" in out.stdout

    show = subprocess.run(
        ["git", "show", "pr-1:policies/bram_response/rules.yaml"],
        cwd=tmp_credio_repo, capture_output=True, text=True, check=True,
    )
    assert "120" in show.stdout
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_repo_manager.py -v`
Expected: FAIL — module not found.

- [ ] **Step 3: Implement repo manager**

```python
# pipeline/repo_manager.py
import subprocess
from pathlib import Path

from pipeline.propose import FileEdit


def _git(*args: str, cwd: Path) -> None:
    subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True)


def apply_edits_on_branch(
    *,
    repo: Path,
    branch: str,
    base: str,
    edits: list[FileEdit],
    message: str,
) -> None:
    """Create `branch` off `base`, write edits, commit, and return on the branch."""
    # Drop branch if it exists, recreate from base
    existing = subprocess.run(
        ["git", "branch", "--list", branch], cwd=repo, capture_output=True, text=True, check=True
    )
    if existing.stdout.strip():
        _git("branch", "-D", branch, cwd=repo)
    _git("checkout", base, cwd=repo)
    _git("checkout", "-b", branch, cwd=repo)
    for edit in edits:
        target = repo / edit.policy_path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(edit.new_contents)
    _git("add", ".", cwd=repo)
    _git("commit", "-m", message, cwd=repo)
```

- [ ] **Step 4: Run tests to verify pass**

Run: `uv run pytest tests/test_repo_manager.py -v`
Expected: 1 passed.

- [ ] **Step 5: Commit**

```bash
git add pipeline/repo_manager.py tests/test_repo_manager.py
git commit -m "feat(repo): apply edits on a fresh branch off the previous PR's head"
```

---

## Task 12: PDF renderer

**Files:**
- Create: `pipeline/pdf_render.py`
- Create: `tests/test_pdf_render.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_pdf_render.py
import shutil
from pathlib import Path

import pytest

from pipeline.pdf_render import render_policy_pdf


pytestmark = pytest.mark.skipif(not shutil.which("pandoc"), reason="pandoc not installed")


def test_render_policy_pdf_produces_output(tmp_path: Path):
    md = tmp_path / "policy.md"
    md.write_text("# Title\n\nbody text\n")
    out = tmp_path / "policy.pdf"

    render_policy_pdf(md, out)

    assert out.exists() and out.stat().st_size > 0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_pdf_render.py -v`
Expected: FAIL — module not found.

- [ ] **Step 3: Implement renderer**

```python
# pipeline/pdf_render.py
import subprocess
from pathlib import Path


def render_policy_pdf(md_path: Path, pdf_path: Path) -> None:
    pdf_path.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        ["pandoc", str(md_path), "-o", str(pdf_path)],
        check=True,
        capture_output=True,
    )
```

- [ ] **Step 4: Run tests to verify pass**

Run: `uv run pytest tests/test_pdf_render.py -v`
Expected: 1 passed (or skipped if pandoc unavailable).

- [ ] **Step 5: Commit**

```bash
git add pipeline/pdf_render.py tests/test_pdf_render.py
git commit -m "feat(pdf): render policy.md to PDF via pandoc"
```

---

## Task 13: Presentation — redline wrapper

**Files:**
- Create: `presentation/redline.py`
- Create: `tests/test_redline.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_redline.py
from presentation.redline import render_prose_redline


def test_render_prose_redline_marks_changes():
    before = "Acquirer must respond within 180 days."
    after = "Acquirer must respond within 120 days, including video-KYC."

    html = render_prose_redline(before, after)

    assert "<del" in html and "180" in html
    assert "<ins" in html and "120" in html
    assert "video-KYC" in html


def test_render_prose_redline_handles_no_changes():
    text = "Acquirer must respond within 180 days."
    html = render_prose_redline(text, text)
    assert "<ins" not in html and "<del" not in html
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_redline.py -v`
Expected: FAIL — module not found.

- [ ] **Step 3: Implement redline wrapper**

```python
# presentation/redline.py
from redlines import Redlines


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
```

- [ ] **Step 4: Run tests to verify pass**

Run: `uv run pytest tests/test_redline.py -v`
Expected: 2 passed.

- [ ] **Step 5: Commit**

```bash
git add presentation/redline.py tests/test_redline.py
git commit -m "feat(presentation): word-level prose redline via redlines lib"
```

---

## Task 14: Presentation — YAML diff

**Files:**
- Create: `presentation/yaml_diff.py`
- Create: `tests/test_yaml_diff.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_yaml_diff.py
from presentation.yaml_diff import render_yaml_diff


def test_render_yaml_diff_marks_added_and_removed_lines():
    before = "response_window_days: 180\nrequired_evidence:\n  - txn_monitoring\n"
    after = "response_window_days: 120\nrequired_evidence:\n  - txn_monitoring\n  - video_kyc\n"

    html = render_yaml_diff(before, after)

    assert "diff-line-removed" in html and "180" in html
    assert "diff-line-added" in html and "120" in html
    assert "video_kyc" in html
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_yaml_diff.py -v`
Expected: FAIL — module not found.

- [ ] **Step 3: Implement YAML diff renderer**

```python
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
```

- [ ] **Step 4: Run tests to verify pass**

Run: `uv run pytest tests/test_yaml_diff.py -v`
Expected: 1 passed.

- [ ] **Step 5: Commit**

```bash
git add presentation/yaml_diff.py tests/test_yaml_diff.py
git commit -m "feat(presentation): line-level YAML diff with classed HTML output"
```

---

## Task 15: Change record schema + serializer

**Files:**
- Create: `pipeline/change_record.py`
- Create: `tests/test_change_record.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_change_record.py
import json
from pathlib import Path

from pipeline.change_record import ChangeRecord, AffectedFile, save_change_record, load_change_record


def test_change_record_round_trip(tmp_path: Path):
    rec = ChangeRecord(
        change_id="2024-09_to_2025-05_10.2",
        transition_from="2024-09",
        transition_to="2025-05",
        section_id="10.2",
        section_title="BRAM Investigation Process",
        materiality="substantive",
        summary="Window cut 180→120; video KYC added.",
        section_before="180 days",
        section_after="120 days, video KYC",
        affected_files=[
            AffectedFile(
                path="policies/bram_response/rules.yaml",
                old_contents="response_window_days: 180\n",
                new_contents="response_window_days: 120\n",
                change_summary="Cut window",
            )
        ],
        rationale="Response window obligation changed.",
    )

    path = tmp_path / "rec.json"
    save_change_record(rec, path)
    loaded = load_change_record(path)

    assert loaded == rec
    raw = json.loads(path.read_text())
    assert raw["change_id"] == rec.change_id
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_change_record.py -v`
Expected: FAIL — module not found.

- [ ] **Step 3: Implement change record**

```python
# pipeline/change_record.py
import dataclasses
import json
from pathlib import Path
from typing import Literal


@dataclasses.dataclass(frozen=True)
class AffectedFile:
    path: str
    old_contents: str
    new_contents: str
    change_summary: str


@dataclasses.dataclass(frozen=True)
class ChangeRecord:
    change_id: str
    transition_from: str
    transition_to: str
    section_id: str
    section_title: str
    materiality: Literal["cosmetic", "clarifying", "substantive", "breaking"]
    summary: str
    section_before: str
    section_after: str
    affected_files: list[AffectedFile]
    rationale: str


def save_change_record(rec: ChangeRecord, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(dataclasses.asdict(rec), indent=2))


def load_change_record(path: Path) -> ChangeRecord:
    raw = json.loads(path.read_text())
    raw["affected_files"] = [AffectedFile(**f) for f in raw["affected_files"]]
    return ChangeRecord(**raw)
```

- [ ] **Step 4: Run tests to verify pass**

Run: `uv run pytest tests/test_change_record.py -v`
Expected: 1 passed.

- [ ] **Step 5: Commit**

```bash
git add pipeline/change_record.py tests/test_change_record.py
git commit -m "feat(record): ChangeRecord schema for pipeline → presentation handoff"
```

---

## Task 16: Presentation — base template + style

**Files:**
- Create: `presentation/templates/_base.html.j2`
- Create: `presentation/render.py` (initial scaffold)
- Create: `credio-policies/dist/assets/style.css` (committed to credio-policies repo on main)
- Create: `tests/test_render.py` (smoke test only at this stage)

- [ ] **Step 1: Write `presentation/templates/_base.html.j2`**

```html
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>{% block title %}Credio Policy Updates{% endblock %}</title>
  <link rel="stylesheet" href="{{ assets_prefix }}assets/style.css">
</head>
<body>
  <header class="site-header">
    <a href="{{ assets_prefix }}timeline.html" class="brand">Credio Policy Updates</a>
  </header>
  <main class="container">
    {% block content %}{% endblock %}
  </main>
</body>
</html>
```

- [ ] **Step 2: Write `credio-policies/dist/assets/style.css`**

```css
* { box-sizing: border-box; }
body { margin: 0; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; color: #222; background: #fafbfd; }
.container { max-width: 960px; margin: 0 auto; padding: 24px 20px; }
.site-header { background: white; border-bottom: 1px solid #e2e6ec; padding: 14px 20px; }
.site-header .brand { color: #6b46ff; text-decoration: none; font-weight: 600; }

.timeline-row { display: flex; gap: 14px; align-items: flex-start; margin-bottom: 12px; }
.timeline-row .date { font-size: 12px; color: #666; min-width: 90px; padding-top: 14px; text-align: right; }
.timeline-row .card { flex: 1; background: white; border: 1px solid #e2e6ec; border-radius: 6px; padding: 14px; }

.materiality { padding: 2px 10px; border-radius: 10px; font-size: 11px; }
.materiality.breaking   { background: #fdd; color: #900; }
.materiality.substantive { background: #fee; color: #c33; }
.materiality.clarifying { background: #fef3c7; color: #854d0e; }
.materiality.cosmetic   { background: #f1f5f9; color: #555; }

.change-card { background: white; border: 1px solid #e2e6ec; border-radius: 6px; padding: 14px; margin-bottom: 10px; }
.change-card .title { font-weight: 600; font-size: 14px; }

.tabs { display: flex; gap: 0; border-bottom: 1px solid #eee; background: #fafafa; }
.tabs a { padding: 10px 18px; font-size: 13px; color: #888; text-decoration: none; }
.tabs a.active { color: #6b46ff; border-bottom: 2px solid #6b46ff; font-weight: 600; }

.tab-panel { display: none; padding: 18px; background: white; }
.tab-panel:target, .tab-panel.default { display: block; }

.side-by-side { display: grid; grid-template-columns: 1fr 1fr; gap: 0; }
.side-by-side .col { padding: 14px 18px; }
.side-by-side .col + .col { border-left: 1px solid #eee; background: #fafbfd; }

ins.ins { background: #dfd; color: #272; text-decoration: none; }
del.del { background: #fee; color: #c33; }

.yaml-diff { font-family: ui-monospace, SFMono-Regular, Menlo, monospace; font-size: 12px; line-height: 1.5; padding: 10px; background: white; border: 1px solid #e2e6ec; border-radius: 4px; overflow-x: auto; }
.diff-line-added   { background: #dfd; color: #272; }
.diff-line-removed { background: #fee; color: #c33; }
.diff-line-equal   { color: #444; }

.why-edits { padding: 10px 18px; background: #f7f5ff; border-top: 1px solid #eee; font-size: 12px; color: #555; }
```

- [ ] **Step 3: Implement render scaffold**

```python
# presentation/render.py
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape


def make_env() -> Environment:
    templates_dir = Path(__file__).parent / "templates"
    return Environment(
        loader=FileSystemLoader(templates_dir),
        autoescape=select_autoescape(["html", "j2"]),
    )
```

- [ ] **Step 4: Smoke test that env loads**

```python
# tests/test_render.py
from presentation.render import make_env


def test_make_env_loads_base_template():
    env = make_env()
    tmpl = env.get_template("_base.html.j2")
    assert tmpl is not None
```

- [ ] **Step 5: Run test to verify pass**

Run: `uv run pytest tests/test_render.py -v`
Expected: 1 passed.

- [ ] **Step 6: Commit**

```bash
git add presentation/render.py presentation/templates/_base.html.j2 tests/test_render.py
git commit -m "feat(presentation): base template, style.css, jinja2 env"
cd credio-policies && git add dist/assets/style.css && git commit -m "feat(dist): site stylesheet" && cd ..
```

---

## Task 17: Presentation — timeline page

**Files:**
- Create: `presentation/templates/timeline.html.j2`
- Modify: `presentation/render.py` (add `render_timeline`)
- Modify: `tests/test_render.py`

- [ ] **Step 1: Write `presentation/templates/timeline.html.j2`**

```html
{% extends "_base.html.j2" %}
{% block title %}Mastercard {{ artifact_label }} — change timeline{% endblock %}
{% block content %}
<h1>Mastercard {{ artifact_label }} — change timeline</h1>
<p class="subtitle">{{ transitions|length }} transitions covering {{ start_date }} → {{ end_date }}.</p>

{% for t in transitions %}
<div class="timeline-row">
  <div class="date">{{ t.from_date }}<br>↓<br>{{ t.to_date }}</div>
  <div class="card">
    <div style="display:flex; justify-content:space-between; align-items:center;">
      <strong>{{ t.label }}</strong>
      <span style="font-size:11px; color:#666;">
        {% for k, count in t.materiality_counts.items() if count %}
          <span class="materiality {{ k }}">{{ count }} {{ k }}</span>
        {% endfor %}
      </span>
    </div>
    <div style="font-size:12px; color:#666; margin-top:6px;">
      {{ t.affected_policy_count }} Credio policies affected ·
      <a href="transitions/{{ t.slug }}.html">View {{ t.change_count }} changes →</a>
    </div>
  </div>
</div>
{% endfor %}
{% endblock %}
```

- [ ] **Step 2: Write the failing test**

```python
# tests/test_render.py  (append)
from pathlib import Path

from presentation.render import make_env, render_timeline


def test_render_timeline_writes_html(tmp_path: Path):
    out = tmp_path / "timeline.html"
    render_timeline(
        out_path=out,
        artifact_label="SPME",
        start_date="2022-06",
        end_date="2025-05",
        transitions=[
            {
                "from_date": "2024-09",
                "to_date": "2025-05",
                "label": "SPME 2025 yearly refresh",
                "slug": "2024-09_to_2025-05",
                "change_count": 4,
                "affected_policy_count": 5,
                "materiality_counts": {"breaking": 1, "substantive": 3, "clarifying": 0, "cosmetic": 0},
            }
        ],
    )

    html = out.read_text()
    assert "SPME 2025 yearly refresh" in html
    assert 'href="transitions/2024-09_to_2025-05.html"' in html
    assert "1 breaking" in html and "3 substantive" in html
```

- [ ] **Step 3: Run test to verify it fails**

Run: `uv run pytest tests/test_render.py -v`
Expected: FAIL — `render_timeline` not defined.

- [ ] **Step 4: Implement `render_timeline`**

Append to `presentation/render.py`:

```python
def render_timeline(
    *,
    out_path: Path,
    artifact_label: str,
    start_date: str,
    end_date: str,
    transitions: list[dict],
) -> None:
    env = make_env()
    tmpl = env.get_template("timeline.html.j2")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(tmpl.render(
        artifact_label=artifact_label,
        start_date=start_date,
        end_date=end_date,
        transitions=transitions,
        assets_prefix="",
    ))
```

- [ ] **Step 5: Run tests to verify pass**

Run: `uv run pytest tests/test_render.py -v`
Expected: 2 passed.

- [ ] **Step 6: Commit**

```bash
git add presentation/render.py presentation/templates/timeline.html.j2 tests/test_render.py
git commit -m "feat(presentation): timeline page with materiality counts and per-transition links"
```

---

## Task 18: Presentation — transition (change-cards) page

**Files:**
- Create: `presentation/templates/transition.html.j2`
- Modify: `presentation/render.py` (add `render_transition`)
- Modify: `tests/test_render.py`

- [ ] **Step 1: Write `presentation/templates/transition.html.j2`**

```html
{% extends "_base.html.j2" %}
{% block title %}{{ label }} — changes{% endblock %}
{% block content %}
<p style="font-size:11px; color:#888;"><a href="{{ assets_prefix }}timeline.html">← Timeline</a> · {{ label }}</p>
<h1>{{ label }}</h1>

{% for c in changes %}
<div class="change-card">
  <div style="display:flex; justify-content:space-between; align-items:center;">
    <span class="title">{{ c.title }}</span>
    <span class="materiality {{ c.materiality }}">{{ c.materiality }}</span>
  </div>
  <div style="font-size:12px; color:#444; margin:6px 0;">{{ c.summary }}</div>
  <div style="background:#f7f5ff; padding:8px 10px; border-radius:4px; font-size:11px;">
    Cites <code>SPME §{{ c.section_id }}</code> · Affects
    {% for f in c.affected_paths %}<code>{{ f }}</code>{% if not loop.last %}, {% endif %}{% endfor %}
  </div>
  <div style="margin-top:10px; text-align:right;">
    <a href="{{ assets_prefix }}changes/{{ c.change_id }}.html" style="font-size:12px;">Open detail →</a>
  </div>
</div>
{% endfor %}
{% endblock %}
```

- [ ] **Step 2: Write the failing test**

```python
# tests/test_render.py  (append)
from presentation.render import render_transition


def test_render_transition_lists_changes(tmp_path: Path):
    out = tmp_path / "transitions" / "2024-09_to_2025-05.html"
    render_transition(
        out_path=out,
        slug="2024-09_to_2025-05",
        label="SPME 2025 yearly refresh",
        changes=[
            {
                "change_id": "2024-09_to_2025-05_10.2",
                "title": "BRAM response window tightened",
                "summary": "180→120 days; video KYC added.",
                "materiality": "substantive",
                "section_id": "10.2",
                "affected_paths": ["policies/bram_response/rules.yaml"],
            }
        ],
        assets_prefix="../",
    )

    html = out.read_text()
    assert "BRAM response window tightened" in html
    assert "10.2" in html
    assert 'href="../changes/2024-09_to_2025-05_10.2.html"' in html
```

- [ ] **Step 3: Run test to verify it fails**

Run: `uv run pytest tests/test_render.py::test_render_transition_lists_changes -v`
Expected: FAIL — `render_transition` not defined.

- [ ] **Step 4: Implement `render_transition`**

Append to `presentation/render.py`:

```python
def render_transition(
    *,
    out_path: Path,
    slug: str,
    label: str,
    changes: list[dict],
    assets_prefix: str = "../",
) -> None:
    env = make_env()
    tmpl = env.get_template("transition.html.j2")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(tmpl.render(
        slug=slug, label=label, changes=changes, assets_prefix=assets_prefix,
    ))
```

- [ ] **Step 5: Run tests to verify pass**

Run: `uv run pytest tests/test_render.py -v`
Expected: 3 passed.

- [ ] **Step 6: Commit**

```bash
git add presentation/render.py presentation/templates/transition.html.j2 tests/test_render.py
git commit -m "feat(presentation): per-transition change-cards page"
```

---

## Task 19: Presentation — detail page (tabbed)

**Files:**
- Create: `presentation/templates/change.html.j2`
- Modify: `presentation/render.py` (add `render_change`)
- Modify: `tests/test_render.py`

- [ ] **Step 1: Write `presentation/templates/change.html.j2`**

```html
{% extends "_base.html.j2" %}
{% block title %}{{ change.title }}{% endblock %}
{% block content %}
<p style="font-size:11px; color:#888;">
  <a href="{{ assets_prefix }}timeline.html">Timeline</a> ·
  <a href="{{ assets_prefix }}transitions/{{ change.transition_slug }}.html">{{ change.transition_label }}</a> ·
  <strong>{{ change.title }}</strong>
</p>

<header style="display:flex; justify-content:space-between; align-items:center; padding:14px 0;">
  <div>
    <h1 style="margin:0;">{{ change.title }}</h1>
    <div style="font-size:12px; color:#888;">Mastercard SPME §{{ change.section_id }} · {{ change.transition_label }}</div>
  </div>
  <span class="materiality {{ change.materiality }}">{{ change.materiality }}</span>
</header>

<nav class="tabs">
  <a href="#side-by-side" class="active">Side-by-side</a>
  <a href="#redline">Redline (compliance view)</a>
  <a href="#raw-diff">Raw diff</a>
</nav>

<section id="side-by-side" class="tab-panel default">
  <div class="side-by-side">
    <div class="col">
      <div class="label">Mastercard SPME §{{ change.section_id }}</div>
      <div class="prose">{{ change.section_redline_html | safe }}</div>
    </div>
    <div class="col">
      <div class="label">Credio · {{ change.affected_files | length }} file(s) affected</div>
      {% for f in change.affected_files %}
        <div style="margin-bottom:14px;">
          <div style="font-size:12px; font-weight:600;">{{ f.path }}</div>
          {% if f.kind == "yaml" %}{{ f.diff_html | safe }}{% else %}{{ f.diff_html | safe }}{% endif %}
        </div>
      {% endfor %}
    </div>
  </div>
  <div class="why-edits"><strong>Why these edits?</strong> {{ change.rationale }}</div>
</section>

<section id="redline" class="tab-panel">
  {% for f in change.affected_files if f.kind == "markdown" %}
    <div class="label">{{ f.path }} (after applying change)</div>
    <div class="prose">{{ f.full_redline_html | safe }}</div>
  {% endfor %}
  <p style="font-size:11px; color:#888;">Source authority: Mastercard SPME §{{ change.section_id }}.</p>
</section>

<section id="raw-diff" class="tab-panel">
  <pre>{{ change.unified_diff }}</pre>
</section>
{% endblock %}
```

- [ ] **Step 2: Write the failing test**

```python
# tests/test_render.py  (append)
from presentation.render import render_change


def test_render_change_includes_three_tabs(tmp_path: Path):
    out = tmp_path / "changes" / "2024-09_to_2025-05_10.2.html"
    render_change(
        out_path=out,
        change={
            "change_id": "2024-09_to_2025-05_10.2",
            "title": "BRAM response window tightened",
            "materiality": "substantive",
            "section_id": "10.2",
            "transition_slug": "2024-09_to_2025-05",
            "transition_label": "SPME 2025 yearly refresh",
            "section_redline_html": "<p>Acquirer must respond within <del class='del'>180</del><ins class='ins'>120</ins> days.</p>",
            "affected_files": [
                {
                    "path": "policies/bram_response/rules.yaml",
                    "kind": "yaml",
                    "diff_html": "<pre class='yaml-diff'>diff html</pre>",
                    "full_redline_html": "",
                }
            ],
            "unified_diff": "--- a\n+++ b\n@@ ...",
            "rationale": "Window obligation changed.",
        },
        assets_prefix="../",
    )

    html = out.read_text()
    assert 'id="side-by-side"' in html
    assert 'id="redline"' in html
    assert 'id="raw-diff"' in html
    assert "BRAM response window tightened" in html
    assert "Window obligation changed." in html
```

- [ ] **Step 3: Run test to verify it fails**

Run: `uv run pytest tests/test_render.py::test_render_change_includes_three_tabs -v`
Expected: FAIL — `render_change` not defined.

- [ ] **Step 4: Implement `render_change`**

Append to `presentation/render.py`:

```python
def render_change(
    *,
    out_path: Path,
    change: dict,
    assets_prefix: str = "../",
) -> None:
    env = make_env()
    tmpl = env.get_template("change.html.j2")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(tmpl.render(change=change, assets_prefix=assets_prefix))
```

- [ ] **Step 5: Run tests to verify pass**

Run: `uv run pytest tests/test_render.py -v`
Expected: 4 passed.

- [ ] **Step 6: Commit**

```bash
git add presentation/render.py presentation/templates/change.html.j2 tests/test_render.py
git commit -m "feat(presentation): tabbed detail page (side-by-side, redline, raw diff)"
```

---

## Task 20: Orchestrator + CLI

**Files:**
- Create: `pipeline/orchestrator.py`
- Create: `pipeline/cli.py`
- Create: `tests/test_orchestrator.py`

- [ ] **Step 1: Write the failing test (orchestrator with mocked LLM)**

```python
# tests/test_orchestrator.py
import subprocess
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from pipeline.orchestrator import Orchestrator
from pipeline.config import Config


@pytest.fixture
def cfg():
    return Config(provider="openai", default_model="gpt-5.4-mini", stage_models={}, api_key="sk-test")


@pytest.fixture
def fake_credio_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "credio-policies"
    repo.mkdir()
    (repo / "policies" / "bram_response").mkdir(parents=True)
    (repo / "policies" / "bram_response" / "rules.yaml").write_text("response_window_days: 180\n")
    (repo / "policies" / "bram_response" / "policy.md").write_text("# BRAM\n\n180 days.\n")
    (repo / "policies" / "bram_response" / "source.yaml").write_text("sections: [{id: '10.2'}]\n")
    subprocess.run(["git", "init", "-b", "main"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "t@e.com"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.name", "t"], cwd=repo, check=True)
    subprocess.run(["git", "add", "."], cwd=repo, check=True)
    subprocess.run(["git", "commit", "-m", "baseline"], cwd=repo, check=True, capture_output=True)
    return repo


def test_run_transition_creates_branch_and_change_record(cfg, fake_credio_repo, tmp_path, mocker):
    # Mock the LLM at every stage to avoid real API calls.
    fake_llm = MagicMock()
    fake_llm.complete_json.side_effect = [
        # classify
        {"section_id": "10.2", "title": "BRAM", "summary": "180→120; video KYC", "materiality": "substantive"},
        # map
        {"section_id": "10.2", "affected_policies": [{"policy": "bram_response", "rationale": "window changed"}]},
        # propose (rules.yaml)
        {"new_contents": "response_window_days: 120\n", "change_summary": "Cut window"},
        # propose (policy.md)
        {"new_contents": "# BRAM\n\n120 days.\n", "change_summary": "Update prose"},
    ]
    mocker.patch("pipeline.llm.LLMClient", return_value=fake_llm)

    artifacts_dir = tmp_path / "artifacts"
    orch = Orchestrator(
        cfg=cfg,
        credio_repo=fake_credio_repo,
        artifacts_dir=artifacts_dir,
        llm=fake_llm,
    )

    # Stub a section delta directly (bypassing fetch+extract+diff for unit clarity)
    from pipeline.diff import SectionDelta
    deltas = [SectionDelta(
        section_id="10.2", title="BRAM", kind="modified",
        before="…180 days…", after="…120 days; video KYC…",
    )]

    result = orch.run_transition(
        transition_from="2024-09",
        transition_to="2025-05",
        deltas=deltas,
        branch_base="main",
        branch_name="pr-1",
    )

    assert result.branch == "pr-1"
    assert len(result.change_records) == 1
    rec = result.change_records[0]
    assert rec.section_id == "10.2"
    assert any(f.path == "policies/bram_response/rules.yaml" for f in rec.affected_files)

    # Branch exists in git
    out = subprocess.run(
        ["git", "branch", "--list", "pr-1"], cwd=fake_credio_repo, capture_output=True, text=True, check=True,
    )
    assert "pr-1" in out.stdout

    # Change record persisted
    rec_path = artifacts_dir / "spme" / "2024-09_to_2025-05" / "changes" / "2024-09_to_2025-05_10.2.json"
    assert rec_path.exists()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_orchestrator.py -v`
Expected: FAIL — module not found.

- [ ] **Step 3: Implement orchestrator**

```python
# pipeline/orchestrator.py
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
from pipeline.repo_manager import apply_edits_on_branch


@dataclass
class TransitionResult:
    branch: str
    change_records: list[ChangeRecord] = field(default_factory=list)


class Orchestrator:
    def __init__(self, *, cfg: Config, credio_repo: Path, artifacts_dir: Path, llm: LLMClient):
        self.cfg = cfg
        self.credio_repo = credio_repo
        self.artifacts_dir = artifacts_dir
        self.llm = llm

    def _build_catalog(self) -> list[PolicyCatalogEntry]:
        entries: list[PolicyCatalogEntry] = []
        policies_dir = self.credio_repo / "policies"
        for folder in sorted(policies_dir.iterdir()):
            if not folder.is_dir():
                continue
            source = yaml.safe_load((folder / "source.yaml").read_text())
            cited = [str(s.get("id", "")) for s in (source or {}).get("sections", [])]
            policy_md = folder / "policy.md"
            desc = policy_md.read_text().splitlines()[0].lstrip("# ").strip() if policy_md.exists() else ""
            entries.append(PolicyCatalogEntry(name=folder.name, description=desc, cited_sections=cited))
        return entries

    def run_transition(
        self,
        *,
        transition_from: str,
        transition_to: str,
        deltas: list[SectionDelta],
        branch_base: str,
        branch_name: str,
    ) -> TransitionResult:
        catalog = self._build_catalog()
        result = TransitionResult(branch=branch_name)
        edits_to_apply = []

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
                for fname in ("rules.yaml", "policy.md"):
                    fpath = folder / fname
                    if not fpath.exists():
                        continue
                    edit = propose_edit(
                        policy_path=f"policies/{ap.policy}/{fname}",
                        current_contents=fpath.read_text(),
                        section_id=delta.section_id,
                        section_before=delta.before,
                        section_after=delta.after,
                        rationale=ap.rationale,
                        llm=self.llm,
                    )
                    if edit.new_contents.strip() == edit.old_contents.strip():
                        continue
                    edits_to_apply.append(edit)
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

        if edits_to_apply:
            from pipeline.propose import FileEdit
            # Group edits by path: latest edit wins per file (covers multi-section edits to same file)
            latest: dict[str, FileEdit] = {}
            for e in edits_to_apply:
                latest[e.policy_path] = e
            apply_edits_on_branch(
                repo=self.credio_repo,
                branch=branch_name,
                base=branch_base,
                edits=list(latest.values()),
                message=f"SPME {transition_from} → {transition_to}",
            )
        return result
```

- [ ] **Step 4: Implement CLI**

```python
# pipeline/cli.py
import argparse
import json
from pathlib import Path

from pipeline.config import load_config
from pipeline.fetch import enumerate_versions, download, fetch_cdx, Snapshot
from pipeline.extract import extract_sections
from pipeline.diff import diff_sections
from pipeline.llm import LLMClient
from pipeline.orchestrator import Orchestrator


SPME_URL = "https://www.mastercard.us/content/dam/public/mastercardcom/na/global-site/documents/SPME-Manual.pdf"


def cmd_run_phase(args):
    cfg = load_config(Path("config/models.yaml"))
    llm = LLMClient(cfg)
    artifacts = Path("artifacts")
    credio_repo = Path("credio-policies")

    cdx_rows = fetch_cdx(SPME_URL)
    snapshots = enumerate_versions(cdx_rows)

    # For each snapshot, fetch + extract
    sections_by_version: list[tuple[Snapshot, list]] = []
    for s in snapshots:
        pdf_path = artifacts / "spme" / f"{s.timestamp}.pdf"
        download(s, pdf_path)
        sections_by_version.append((s, extract_sections(pdf_path)))

    orch = Orchestrator(cfg=cfg, credio_repo=credio_repo, artifacts_dir=artifacts, llm=llm)
    base = "main"
    for i in range(len(sections_by_version) - 1):
        a_snap, a_secs = sections_by_version[i]
        b_snap, b_secs = sections_by_version[i + 1]
        deltas = diff_sections(a_secs, b_secs)
        from_label = a_snap.timestamp[:6]
        to_label = b_snap.timestamp[:6]
        branch = f"pr-{i+1}"
        orch.run_transition(
            transition_from=f"{from_label[:4]}-{from_label[4:]}",
            transition_to=f"{to_label[:4]}-{to_label[4:]}",
            deltas=deltas,
            branch_base=base,
            branch_name=branch,
        )
        base = branch
    print(json.dumps({"phase": "spme", "transitions": len(sections_by_version) - 1}, indent=2))


def main():
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="cmd", required=True)
    p1 = sub.add_parser("run-phase")
    p1.add_argument("--artifact", choices=["spme"], required=True)
    p1.set_defaults(func=cmd_run_phase)
    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
```

- [ ] **Step 5: Run tests to verify pass**

Run: `uv run pytest tests/test_orchestrator.py -v`
Expected: 1 passed.

- [ ] **Step 6: Commit**

```bash
git add pipeline/orchestrator.py pipeline/cli.py tests/test_orchestrator.py
git commit -m "feat(orchestrator): per-transition runner + CLI entry point"
```

---

## Task 21: Site renderer (timeline + transitions + changes from change records)

**Files:**
- Modify: `presentation/render.py` (add `render_site`)
- Create: `tests/test_render_site.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_render_site.py
from pathlib import Path

from pipeline.change_record import AffectedFile, ChangeRecord, save_change_record
from presentation.render import render_site


def test_render_site_produces_three_layers(tmp_path: Path):
    artifacts = tmp_path / "artifacts" / "spme"
    transition_dir = artifacts / "2024-09_to_2025-05" / "changes"
    rec = ChangeRecord(
        change_id="2024-09_to_2025-05_10.2",
        transition_from="2024-09",
        transition_to="2025-05",
        section_id="10.2",
        section_title="BRAM Investigation Process",
        materiality="substantive",
        summary="180→120, video KYC.",
        section_before="…180 days…",
        section_after="…120 days, video KYC…",
        affected_files=[
            AffectedFile(
                path="policies/bram_response/rules.yaml",
                old_contents="response_window_days: 180\n",
                new_contents="response_window_days: 120\n",
                change_summary="Cut window",
            )
        ],
        rationale="Response window changed.",
    )
    save_change_record(rec, transition_dir / f"{rec.change_id}.json")

    dist = tmp_path / "dist"
    render_site(artifacts_root=artifacts, dist=dist, artifact_label="SPME")

    assert (dist / "timeline.html").exists()
    assert (dist / "transitions" / "2024-09_to_2025-05.html").exists()
    assert (dist / "changes" / "2024-09_to_2025-05_10.2.html").exists()
    timeline_html = (dist / "timeline.html").read_text()
    assert "2024-09" in timeline_html and "2025-05" in timeline_html
    assert "1 substantive" in timeline_html
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_render_site.py -v`
Expected: FAIL — `render_site` not defined.

- [ ] **Step 3: Implement `render_site`**

Append to `presentation/render.py`:

```python
import difflib
from collections import Counter

from pipeline.change_record import ChangeRecord, load_change_record
from presentation.redline import render_prose_redline
from presentation.yaml_diff import render_yaml_diff


def _kind_for_path(path: str) -> str:
    return "yaml" if path.endswith((".yaml", ".yml")) else "markdown"


def _enrich_change(rec: ChangeRecord, transition_label: str) -> dict:
    section_redline = render_prose_redline(rec.section_before, rec.section_after)
    affected = []
    unified_chunks: list[str] = []
    for f in rec.affected_files:
        kind = _kind_for_path(f.path)
        if kind == "yaml":
            diff_html = render_yaml_diff(f.old_contents, f.new_contents)
            full_redline = ""
        else:
            diff_html = render_prose_redline(f.old_contents, f.new_contents)
            full_redline = diff_html
        unified_chunks.append(
            "".join(difflib.unified_diff(
                f.old_contents.splitlines(keepends=True),
                f.new_contents.splitlines(keepends=True),
                fromfile=f"a/{f.path}", tofile=f"b/{f.path}",
            ))
        )
        affected.append({
            "path": f.path, "kind": kind,
            "diff_html": diff_html, "full_redline_html": full_redline,
        })
    return {
        "change_id": rec.change_id,
        "title": rec.section_title or rec.summary[:60],
        "summary": rec.summary,
        "materiality": rec.materiality,
        "section_id": rec.section_id,
        "transition_slug": f"{rec.transition_from}_to_{rec.transition_to}",
        "transition_label": transition_label,
        "section_redline_html": section_redline,
        "affected_files": affected,
        "unified_diff": "\n".join(unified_chunks),
        "rationale": rec.rationale,
        "affected_paths": [f.path for f in rec.affected_files],
    }


def render_site(*, artifacts_root: Path, dist: Path, artifact_label: str) -> None:
    transitions: list[dict] = []
    for t_dir in sorted(p for p in artifacts_root.iterdir() if p.is_dir()):
        change_files = sorted((t_dir / "changes").glob("*.json")) if (t_dir / "changes").exists() else []
        records = [load_change_record(f) for f in change_files]
        if not records:
            continue
        from_d = records[0].transition_from
        to_d = records[0].transition_to
        slug = f"{from_d}_to_{to_d}"
        label = f"{artifact_label} {from_d} → {to_d}"
        counts = Counter(r.materiality for r in records)
        for k in ("breaking", "substantive", "clarifying", "cosmetic"):
            counts.setdefault(k, 0)

        # Per-change pages
        for rec in records:
            enriched = _enrich_change(rec, label)
            render_change(
                out_path=dist / "changes" / f"{rec.change_id}.html",
                change=enriched,
                assets_prefix="../",
            )

        # Per-transition page
        change_summaries = [
            {
                "change_id": r.change_id,
                "title": r.section_title or r.summary[:60],
                "summary": r.summary,
                "materiality": r.materiality,
                "section_id": r.section_id,
                "affected_paths": [f.path for f in r.affected_files],
            }
            for r in records
        ]
        render_transition(
            out_path=dist / "transitions" / f"{slug}.html",
            slug=slug, label=label, changes=change_summaries, assets_prefix="../",
        )

        affected_count = len({f.path.split("/")[1] for r in records for f in r.affected_files})
        transitions.append({
            "from_date": from_d, "to_date": to_d, "slug": slug, "label": label,
            "change_count": len(records),
            "affected_policy_count": affected_count,
            "materiality_counts": dict(counts),
        })

    if transitions:
        start_date = transitions[0]["from_date"]
        end_date = transitions[-1]["to_date"]
        render_timeline(
            out_path=dist / "timeline.html",
            artifact_label=artifact_label,
            start_date=start_date, end_date=end_date,
            transitions=transitions,
        )
```

- [ ] **Step 4: Run tests to verify pass**

Run: `uv run pytest tests/test_render_site.py -v`
Expected: 1 passed.

- [ ] **Step 5: Commit**

```bash
git add presentation/render.py tests/test_render_site.py
git commit -m "feat(presentation): site renderer that drives timeline + transitions + changes from records"
```

---

## Task 22: Wire site rendering + PDF rendering into CLI

**Files:**
- Modify: `pipeline/cli.py`
- Modify: `tests/test_orchestrator.py` (no changes needed; CLI test added)
- Create: `tests/test_cli.py` (smoke)

- [ ] **Step 1: Write the failing CLI smoke test**

```python
# tests/test_cli.py
from pathlib import Path

from pipeline.cli import build_arg_parser


def test_cli_has_run_phase_and_render_subcommands():
    parser = build_arg_parser()
    args = parser.parse_args(["render-site", "--artifact", "spme"])
    assert args.cmd == "render-site"
    args = parser.parse_args(["run-phase", "--artifact", "spme"])
    assert args.cmd == "run-phase"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_cli.py -v`
Expected: FAIL — `build_arg_parser` not defined.

- [ ] **Step 3: Refactor CLI to expose `build_arg_parser` and add `render-site` + `render-pdfs`**

Replace `pipeline/cli.py`:

```python
# pipeline/cli.py
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
from presentation.render import render_site


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

    orch = Orchestrator(cfg=cfg, credio_repo=credio_repo, artifacts_dir=artifacts, llm=llm)
    base = "main"
    for i in range(len(sections_by_version) - 1):
        a_snap, a_secs = sections_by_version[i]
        b_snap, b_secs = sections_by_version[i + 1]
        deltas = diff_sections(a_secs, b_secs)
        from_label = f"{a_snap.timestamp[:4]}-{a_snap.timestamp[4:6]}"
        to_label = f"{b_snap.timestamp[:4]}-{b_snap.timestamp[4:6]}"
        branch = f"pr-{i+1}"
        orch.run_transition(
            transition_from=from_label, transition_to=to_label,
            deltas=deltas, branch_base=base, branch_name=branch,
        )
        base = branch
    print(json.dumps({"phase": "spme", "transitions": len(sections_by_version) - 1}))


def cmd_render_site(args):
    artifacts = Path("artifacts") / args.artifact
    dist = Path("credio-policies") / "dist"
    render_site(artifacts_root=artifacts, dist=dist, artifact_label=args.artifact.upper())
    print(f"site → {dist}/timeline.html")


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
```

- [ ] **Step 4: Run tests to verify pass**

Run: `uv run pytest tests/test_cli.py -v`
Expected: 1 passed.

- [ ] **Step 5: Commit**

```bash
git add pipeline/cli.py tests/test_cli.py
git commit -m "feat(cli): add render-site and render-pdfs subcommands"
```

---

## Task 23: End-to-end smoke run on real SPME v5 → v6

This is a manual + automated checkpoint. Pulls real data, makes real LLM calls, validates output.

**Files:**
- Create: `scripts/smoke_v5_v6.sh`

- [ ] **Step 1: Write the smoke script**

```bash
#!/usr/bin/env bash
# scripts/smoke_v5_v6.sh — pulls only SPME v5 and v6, runs single transition.
set -euo pipefail
mkdir -p artifacts/spme

curl -sL -o artifacts/spme/20240901001027.pdf "https://web.archive.org/web/20240901001027id_/https://www.mastercard.us/content/dam/public/mastercardcom/na/global-site/documents/SPME-Manual.pdf"
curl -sL -o artifacts/spme/20250524042807.pdf "https://web.archive.org/web/20250524042807id_/https://www.mastercard.us/content/dam/public/mastercardcom/na/global-site/documents/SPME-Manual.pdf"

uv run python -c "
from pathlib import Path
from pipeline.config import load_config
from pipeline.extract import extract_sections
from pipeline.diff import diff_sections
from pipeline.llm import LLMClient
from pipeline.orchestrator import Orchestrator

cfg = load_config(Path('config/models.yaml'))
llm = LLMClient(cfg)
v5 = extract_sections(Path('artifacts/spme/20240901001027.pdf'))
v6 = extract_sections(Path('artifacts/spme/20250524042807.pdf'))
deltas = diff_sections(v5, v6)
print(f'sections changed: {len(deltas)}')
orch = Orchestrator(cfg=cfg, credio_repo=Path('credio-policies'), artifacts_dir=Path('artifacts'), llm=llm)
orch.run_transition(transition_from='2024-09', transition_to='2025-05', deltas=deltas, branch_base='main', branch_name='pr-smoke')
"

uv run python -m pipeline.cli render-site --artifact spme
uv run python -m pipeline.cli render-pdfs

echo "Open: credio-policies/dist/timeline.html"
```

- [ ] **Step 2: Make executable, run**

```bash
chmod +x scripts/smoke_v5_v6.sh
./scripts/smoke_v5_v6.sh
```

Expected:
- `artifacts/spme/20240901001027.pdf` and `20250524042807.pdf` exist.
- `pr-smoke` branch exists in `credio-policies` repo.
- At least one change record in `artifacts/spme/2024-09_to_2025-05/changes/*.json`.
- `credio-policies/dist/timeline.html`, `transitions/*.html`, `changes/*.html` exist.

- [ ] **Step 3: Manually open `credio-policies/dist/timeline.html` in a browser**

Navigate timeline → a transition → a detail page → confirm:
- Side-by-side tab shows the Mastercard SPME redline on left, Credio file diffs on right.
- Redline tab shows resulting `policy.md` in track-changes form.
- Raw diff tab shows a unified diff.
- Materiality badges render in expected colors.
- Internal links work from `file://`.

- [ ] **Step 4: Spot-check extraction quality**

Open one extracted SPME section markdown from `artifacts/spme/<timestamp>/sections/` (if cached — extraction currently runs in-memory; add caching here if needed for spot-check). For at least one section that contains a table, confirm pdfplumber-extracted table content survives. If garbled, take notes and add a follow-up task to swap to a vision/LLM extractor.

- [ ] **Step 5: Commit smoke script**

```bash
git add scripts/smoke_v5_v6.sh
git commit -m "test: end-to-end smoke for SPME v5→v6 transition"
```

---

## Task 24: Fan out across all 5 SPME pairs

**Files:**
- No new files; runs the full CLI.

- [ ] **Step 1: Drop any stale demo branches**

```bash
cd credio-policies
git checkout main
for b in $(git branch --format='%(refname:short)' | grep -E '^pr-'); do git branch -D "$b"; done
cd ..
```

- [ ] **Step 2: Run the full pipeline**

```bash
uv run python -m pipeline.cli run-phase --artifact spme
uv run python -m pipeline.cli render-site --artifact spme
uv run python -m pipeline.cli render-pdfs
```

Expected: 5 branches `pr-1` … `pr-5` exist; timeline shows 5 transitions; each transitions/*.html lists at least one change.

- [ ] **Step 3: Inspect every detail page**

For each `dist/changes/*.html`:
- Side-by-side renders without empty columns.
- Mastercard cited section ID is present and matches a real section in the corresponding extracted markdown.
- At least one Credio file is visibly edited.

- [ ] **Step 4: Validate phase 1 success criteria from §11 of the spec**

Check each criterion explicitly:
- [ ] All 5 SPME transitions produce a passing proposal (at least one Credio file edited per transition, valid YAML).
- [ ] Each detail page cites specific Mastercard SPME section IDs.
- [ ] Timeline → cards → detail navigation has no dead ends.
- [ ] Side-by-side and redline render correctly for at least one example of clarifying / substantive / breaking class each (skip class if no instance exists; note in success report).
- [ ] Cold-cache run completes in < 30 minutes; warm < 15.
- [ ] Non-cosmetic Mastercard section diffs covered: ≥ 80% mapped to a Credio policy or explicitly marked "no surface".

- [ ] **Step 5: Commit phase 1 demo state**

```bash
cd credio-policies
git tag phase-1-demo
cd ..
echo "Phase 1 ready."
```

---

## Task 25: Demo dry-run

**Files:**
- Create: `docs/superpowers/demo-runbook.md`

- [ ] **Step 1: Write the dry-run runbook**

```markdown
# Phase 1 demo dry-run

## Setup
- Open `credio-policies/dist/timeline.html` in browser.

## Walkthrough (5 min)
1. Land on timeline. Read out: "5 SPME transitions across 3 years; here's the materiality breakdown."
2. Click into the most-loaded transition. Skim 1-2 cards.
3. Open the headline change. Walk side-by-side: "Here is the exact Mastercard line that changed; here is the corresponding edit to a Credio file."
4. Click Redline tab: "This is what compliance reviewers see — Word-style track changes."
5. Click Raw diff: "And for engineers, here's the underlying patch."
6. Back to timeline. Mention that the same pipeline runs against Mastercard Rules and Chargeback Guide in phases 2 and 3.

## What to listen for
- Is the change-detection right? (factual)
- Is the impact mapping plausible? (expert judgment)
- Would they merge the proposed Credio edit?

## Captured feedback template
- Misclassified changes:
- Missed mappings:
- Bad LLM proposals:
- Presentation issues:
- Things they want for phase 2:
```

- [ ] **Step 2: Run the dry-run with one internal reviewer**

Capture feedback in the template. Do not ship to Credio until at least one round of internal feedback is integrated.

- [ ] **Step 3: Commit**

```bash
git add docs/superpowers/demo-runbook.md
git commit -m "docs: phase 1 demo runbook"
```

---

## Self-Review

**Spec coverage:**
- §1 problem & customer-facing surface → covered by tasks 16-21 (presentation layer) and §6 of spec
- §2 phased rollout → addressed implicitly: pipeline is artifact-agnostic; phase 1 only in this plan
- §3 phase 1 scope (5 transitions) → tasks 24
- §4.1 fetch → task 4
- §4.2 extract (pymupdf+pdfplumber adapter) → task 5
- §4.3 diff → task 6
- §4.4 classify → task 8
- §4.5 map → task 9
- §4.6 propose (with change-record JSON) → tasks 10, 15
- §5 synthetic Credio repo → task 7
- §5.3 sequential branches → task 11
- §5.4 PDF rendering → task 12, wired in task 22
- §6.1 timeline → task 17
- §6.2 transition feed → task 18
- §6.3 detail page tabs → task 19
- §6.4 deterministic render from records → task 21
- §8 repo layout → task 1
- §9 tech stack → task 1
- §10 config → tasks 1, 2
- §11 success criteria → task 24 explicit checklist
- §12 risk on `redlines` quality → smoke test step 4 of task 23 spot-checks; if it breaks, follow-up task is implied
- §13 out of scope → respected throughout (no GitHub, no real Credio code)

**Placeholder scan:** No "TBD"/"TODO"/"implement later" wording in steps. Task 7 lists 7 policy folders by name + topic + thresholds — this is concrete enough to author from. The "drop stale branches" line in Task 24 is a real shell loop, not a placeholder.

**Type consistency:** `Snapshot`, `Section`, `SectionDelta`, `ClassificationRecord`, `MappingRecord`, `PolicyCatalogEntry`, `AffectedPolicy`, `FileEdit`, `AffectedFile`, `ChangeRecord` defined in their respective tasks; all subsequent uses match these names. `LLMClient.complete_json(stage, system, user, json_schema)` signature is consistent across `classify.py`, `map_changes.py`, `propose.py`. `apply_edits_on_branch(repo, branch, base, edits, message)` matches its caller in `orchestrator.py`. `render_timeline`, `render_transition`, `render_change`, `render_site` all defined consistently.

**Things explicitly NOT in this plan (and why):** any cross-phase work (Mastercard Rules, Chargeback Guide); GitHub `gh` integration; CI; real-time observability — all properly out-of-scope per spec §13.
