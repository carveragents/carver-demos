"""`mastra_prep` — prep's package surface (spec §1:396-412).

The re-export block below is pinned by the spec and copied exactly. It lands
with `generate_template_config.py` rather than in Phase 1 because its last two
lines re-export `decide_scenario` and this package's generation entry points —
a Phase-1 `__init__.py` would import modules that did not exist yet.

`probe.py`, `judge.py` and `scoring.py` are intentionally NOT re-exported: they
take an injected client and are imported directly by callers that need to
control cost (mirroring the `fetch_topics`/`load_from_cache` network-vs-pure
split convention in `gics-topic-tagging`). The omission is load-bearing, not an
oversight — re-exporting them at package level is what re-creates the
`probe -> judge -> curate -> probe` cycle that extracting the leaf `budget.py`
fixed. `tests/test_generate_template_config.py::test_probe_judge_scoring_are_not_reexported`
guards this surface; `test_imports.py::test_no_circular_imports` guards the
module graph itself, which is a different thing.
"""
from .config import Settings, load_settings
from .reader import stream_annotations
from .extract import FIELD_MAP, extract_record
from .candidates import is_candidate, filter_candidates
from .urls import extract_urls, resolve_url
from .sampling import stratified_sample_sequence
from .budget import SpendBudget, BudgetExhausted, BudgetPoisoned   # from budget.py, NOT curate.py
from .curate import run_curation
from .scenarios import SCENARIO_A, SCENARIO_B, is_eligible
from .scenario_decision import decide_scenario
from .schema import ClearedRecord, to_json, validate_cleared_record, predicts_stage_a_violation
from .openai_client import load_env, make_client
from .generate_template_config import emit_template_config, firm_profile_for_record
