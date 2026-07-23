"""Recency-wall probe: does the ungrounded baseline KNOW about a post-cutoff event?

This tests the contrast mechanism that actually works, rather than the one
`probe_targeted.py` showed to be broken. Instead of asking the model to draft
something and checking whether it missed an obligation (which fails because a
generic drafting task never engages a specific record), it asks a DIRECT question
about a specific, recent, checkable event:

    "Any advisories affecting Schneider Electric products recently?"

The subject is named — that is deliberate and is NOT leaking. We are not testing
"did it spot the obligation"; we are testing "does this event exist in its
weights at all". The answer (which document, which date, which requirements) is
what stays withheld, and that is what the grounded agent supplies.

    cd mastra-guardrail/prep && PYTHONPATH=. .venv/bin/python \
        tools/probe_recency.py <pool.json> <out.json> <n> <ceiling_usd>

One call per record (~$0.01). Prints each answer for human classification into:
  KNOWS      - names the real document/date -> useless as a demo beat
  WALL       - says it cannot know / past its cutoff -> the honest, strong beat
  FABRICATES - invents a plausible advisory -> the strongest beat of all

Classification is left to a human ON PURPOSE. An LLM judge here would be judging
its own sibling's honesty, and the distinction between "declines" and "hedges
then guesses" is exactly the nuance a judge flattens.
"""
import json
import sys

from mastra_prep.budget import SpendBudget
from mastra_prep.config import load_settings
from mastra_prep.openai_client import load_env, make_client
from mastra_prep.probe import _bare_model_id, build_request_payload

POOL, OUT, N, CEILING = sys.argv[1], sys.argv[2], int(sys.argv[3]), float(sys.argv[4])

SYSTEM = ("You are a regulatory-intelligence assistant. Answer questions about what "
          "regulators have published. Be specific: name documents and give dates. "
          "Keep it under 120 words.")

def question(rec: dict) -> str:
    """A demo-shaped question naming the regulator and subject, withholding the answer."""
    regulator = (rec.get("regulator_name") or "the regulator").strip()
    subject = (rec.get("title") or "").strip()
    # Use the record's own subject matter, but ask OPEN — never quote the document.
    return (f"Has {regulator} published anything recently about the subject area of "
            f"“{subject[:70]}”? If so, name the specific document and its date. "
            f"If you are not aware of any, say so plainly.")

cfg = load_settings("config.yaml")
load_env(cfg.dotenv_path)
client = make_client()
budget = SpendBudget(CEILING, cfg.price_input_per_million_usd, cfg.price_output_per_million_usd)

pool = json.load(open(POOL))
pool.sort(key=lambda r: str(r.get("reconciled_published_date") or ""), reverse=True)
selected = pool[:N]
print(f"pool {len(pool):,} -> asking {len(selected)}, ceiling ${CEILING}\n", flush=True)

out = []
for i, rec in enumerate(selected, 1):
    q = question(rec)
    # REASONING TOKENS COUNT AGAINST max_completion_tokens on the GPT-5 family.
    # At 400/medium every single answer came back EMPTY — reasoning consumed the
    # whole allowance and left nothing for the message. That reads exactly like
    # "the model knows nothing", which is the wrong conclusion drawn from a bug.
    # Keep the headroom generous and the effort low: this is a recall question,
    # not a reasoning one.
    payload = build_request_payload(
        model=_bare_model_id(cfg.model_router_string),
        system_text=SYSTEM, user_text=q,
        max_completion_tokens=2000, reasoning_effort="low", schema=None,
    )
    res = budget.reserve(payload)
    try:
        resp = client.chat.completions.create(**payload)
    except Exception as exc:
        print(f"[{i}] ERROR {type(exc).__name__}: {exc}", flush=True)
        break
    res.settle(resp.usage.model_dump() if resp.usage else None)
    answer = resp.choices[0].message.content

    row = {
        "record_id": rec.get("artifact_id"),
        "ground_truth_date": rec.get("reconciled_published_date"),
        "regulator": rec.get("regulator_name"),
        "ground_truth_title": rec.get("title"),
        "question": q,
        "baseline_answer": answer,
    }
    out.append(row)
    print(f"\n{'='*72}\n[{i}/{len(selected)}] {rec.get('regulator_name')} · "
          f"{rec.get('reconciled_published_date')}  (${budget.spend_so_far_usd:.3f})")
    print(f"GROUND TRUTH: {(rec.get('title') or '')[:100]}")
    print(f"Q: {q[:150]}")
    print(f"A: {(answer or '').strip()[:600]}", flush=True)

json.dump({"spend_usd": budget.spend_so_far_usd, "results": out}, open(OUT, "w"),
          indent=2, default=str)
print(f"\n\nspend ${budget.spend_so_far_usd:.2f} — wrote {OUT}")
