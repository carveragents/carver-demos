"""Slice generator: Stage 1 artifacts corpus → build/page_data/.

Stage 1 produces `landing.json` (headline stats for the landing page) from
the artifacts.jsonl JSONL corpus and a5-prime-manifest.json.

Later stages add per-scene slices.
"""

from __future__ import annotations

import datetime as _dt
import json
import re
import sys
from pathlib import Path
from typing import Any

import yaml

# Add repo root to path so we can import build modules when run from repo root
_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))


# ISO-2 country code (e.g. "US", "FR") and ISO-3166 subdivision (e.g. "US-CA")
# patterns. Used to filter the landing-page jurisdiction count down from
# 845 noisy free-form strings to a defensible ~99 real jurisdictions.
_ISO2 = re.compile(r"^[A-Z]{2}$")
_SUBDIVISION = re.compile(r"^[A-Z]{2}-[A-Z0-9]{1,3}$")


def generate_landing_slice(
    corpus_path: Path = Path("data/_scratch/artifacts.jsonl"),
) -> dict[str, Any]:
    """Produce landing-page headline stats from the Stage 1 artifacts corpus.

    Reads JSONL line-by-line (no in-memory accumulation). Skips records where
    pub_date is empty or pub_date_valid is False.
    """
    events_count = 0
    jurisdictions: set[str] = set()
    regulators: set[str] = set()
    dates: list[str] = []

    if not corpus_path.exists():
        # Build must still produce a landing page even before the first pull
        return {
            "events_count": 0,
            "jurisdictions_count": 0,
            "unique_regulators_count": 0,
            "earliest_pub_date": None,
            "latest_pub_date": None,
        }

    with corpus_path.open() as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            r = json.loads(line)
            events_count += 1
            # Count distinct bodies via topic_name, not regulator_name. The
            # raw regulator_name field carries dozens of variants per agency
            # (e.g., "U.S. Securities and Exchange Commission" vs "Securities
            # and Exchange Commission" — both the same SEC). topic_name is
            # the de-duped Carver-catalog entity (~157 across this corpus).
            topic = r.get("topic_name") or ""
            if topic:
                regulators.add(topic)
            # Count distinct jurisdictions from topic_jurisdiction_code only
            # (Carver's curated field). The LLM-extracted
            # impacted_business.jurisdiction list carries noise — postal
            # codes, ISO-3 strings, region blocs ("APAC"), and free-form
            # phrases ("11 other states"). Filter to ISO-2 country codes,
            # EU, and ISO-3166-style subdivisions for an honest headline.
            tj = (r.get("topic_jurisdiction_code") or "").strip()
            if tj and (_ISO2.match(tj) or _SUBDIVISION.match(tj) or tj == "EU"):
                jurisdictions.add(tj)
            if r.get("pub_date_valid") and r.get("pub_date"):
                dates.append(r["pub_date"][:10])

    dates.sort()
    # Filter outliers: the corpus has a handful of LLM-parsed dates outside
    # any plausible window (1944, 2029, etc.). For the landing-page headline
    # we want the realistic publication window, not those artifacts.
    today_iso = _dt.date.today().isoformat()
    plausible_min = "2020-01-01"
    in_window = [d for d in dates if plausible_min <= d <= today_iso]
    return {
        "events_count": events_count,
        "jurisdictions_count": len(jurisdictions),
        "unique_regulators_count": len(regulators),
        "earliest_pub_date": in_window[0] if in_window else None,
        "latest_pub_date": in_window[-1] if in_window else None,
    }


def main() -> None:
    """Run all slice generators in dependency order."""
    REPO = Path(__file__).resolve().parent.parent
    corpus = REPO / "data" / "_scratch" / "artifacts.jsonl"
    curation = REPO / "data" / "alpha-curation.yml"
    pd = REPO / "build" / "page_data"

    # Landing
    landing = generate_landing_slice(corpus_path=corpus)
    (pd / "landing.json").parent.mkdir(parents=True, exist_ok=True)
    (pd / "landing.json").write_text(json.dumps(landing, indent=2))
    print(f"landing.json: events={landing['events_count']}")

    # α (only if both curation file and corpus are present)
    if curation.exists() and corpus.exists():
        cur_doc = yaml.safe_load(curation.read_text())
        build_date_str = cur_doc.get("build_date")
        today = _dt.date.fromisoformat(build_date_str) if build_date_str else _dt.date.today()

        from build.alpha_audit import generate as gen_audit
        from build.alpha_dashboard import generate as gen_dashboard
        from build.alpha_inbox import generate as gen_inbox
        from build.alpha_ticket import generate as gen_tickets

        gen_inbox(corpus_path=corpus, curation_path=curation,
                  out_path=pd / "alpha" / "inbox.json", today=today)
        ticket_paths = gen_tickets(
            corpus_path=corpus, curation_path=curation,
            out_dir=pd / "alpha" / "tickets", today=today)
        gen_dashboard(
            corpus_path=corpus, curation_path=curation,
            out_path=pd / "alpha" / "dashboard.json", today=today)
        gen_audit(
            tickets_dir=pd / "alpha" / "tickets",
            out_path=pd / "alpha" / "audit_export.json", today=today)
        print(
            f"alpha (build_date={today.isoformat()}): "
            f"inbox + {len(ticket_paths)} tickets + dashboard + audit_export"
        )
    elif curation.exists():
        print(f"WARN: corpus {corpus.relative_to(REPO)} missing — skipping alpha slices")
    elif corpus.exists():
        print(f"WARN: curation {curation.relative_to(REPO)} missing — skipping alpha slices")
    else:
        print(f"WARN: {curation.relative_to(REPO)} missing — skipping alpha slices")

    # γ — uses gamma-curation.yml + contracts.yml + retrospective YAMLs
    gamma_curation = REPO / "data" / "gamma-curation.yml"
    kalshi_contracts = REPO / "data" / "platforms" / "kalshi" / "contracts.yml"
    polymarket_contracts = REPO / "data" / "platforms" / "polymarket" / "contracts.yml"
    retrospectives_root = REPO / "data" / "platforms"

    if gamma_curation.exists() and corpus.exists():
        cur_g = yaml.safe_load(gamma_curation.read_text())
        bd_g = cur_g.get("build_date")
        today_g = _dt.date.fromisoformat(bd_g) if bd_g else _dt.date.today()

        from build.gamma_contract import generate as gen_contract
        from build.gamma_dashboard import generate as gen_dash
        from build.gamma_scan import generate as gen_scan

        scan_paths = gen_scan(
            corpus_path=corpus, curation_path=gamma_curation,
            out_dir=pd / "gamma" / "pre-listing-scans", today=today_g,
        )
        gen_dash(
            corpus_path=corpus, gamma_curation_path=gamma_curation,
            kalshi_contracts_path=kalshi_contracts,
            polymarket_contracts_path=polymarket_contracts,
            out_path=pd / "gamma" / "dashboard.json", today=today_g,
        )
        contract_paths = gen_contract(
            corpus_path=corpus, gamma_curation_path=gamma_curation,
            kalshi_contracts_path=kalshi_contracts,
            polymarket_contracts_path=polymarket_contracts,
            retrospectives_root=retrospectives_root,
            out_dir=pd / "gamma" / "contracts", today=today_g,
        )
        print(
            f"gamma (build_date={today_g.isoformat()}): "
            f"{len(scan_paths)} scans + dashboard + {len(contract_paths)} contract details"
        )

        # γ contract intelligence enrichment — adds conditions, narrative,
        # heat_panel, and per-event LLM relevance fields. Cached responses
        # under build/_cache/llm/ keep this near-free in CI.
        from build import gamma_contract_enrich

        gamma_corpus: list[dict[str, Any]] = []
        if corpus.exists():
            with corpus.open() as _f:
                for _line in _f:
                    _line = _line.strip()
                    if _line:
                        gamma_corpus.append(json.loads(_line))

        # Peer heats for percentile = all dashboard rows' current heat.
        dashboard_path = pd / "gamma" / "dashboard.json"
        if dashboard_path.exists():
            dashboard = json.loads(dashboard_path.read_text())
            peer_heats = [row["heat"] for row in dashboard.get("rows", [])]
        else:
            peer_heats = []

        contracts_dir = pd / "gamma" / "contracts"
        if contracts_dir.exists():
            gamma_contract_enrich.enrich_all(
                slice_dir=contracts_dir,
                corpus=gamma_corpus,
                peer_heats=peer_heats,
                today=today_g,
            )
            print(f"  enriched {len(list(contracts_dir.glob('*.json')))} γ contract slices")
    elif gamma_curation.exists():
        print(f"WARN: corpus {corpus.relative_to(REPO)} missing — skipping gamma slices")
    elif corpus.exists():
        print(f"WARN: {gamma_curation.relative_to(REPO)} missing — skipping gamma slices")

    # Trader dashboard — uses trader-curation.yml + contracts.yml + retrospective YAMLs
    trader_curation = REPO / "data" / "trader-curation.yml"

    if trader_curation.exists() and corpus.exists():
        cur_t = yaml.safe_load(trader_curation.read_text())
        bd_t = cur_t.get("build_date")
        today_t = _dt.date.fromisoformat(bd_t) if bd_t else _dt.date.today()

        from build.trader_contract import generate as gen_trader_contract
        from build import trader_contract_enrich

        trader_contract_paths = gen_trader_contract(
            corpus_path=corpus,
            trader_curation_path=trader_curation,
            kalshi_contracts_path=kalshi_contracts,
            polymarket_contracts_path=polymarket_contracts,
            retrospectives_root=retrospectives_root,
            out_dir=pd / "trader" / "contracts",
            today=today_t,
        )
        print(
            f"trader (build_date={today_t.isoformat()}): "
            f"{len(trader_contract_paths)} contract details"
        )

        # Trader contract enrichment
        trader_corpus: list[dict[str, Any]] = []
        if corpus.exists():
            with corpus.open() as _f:
                for _line in _f:
                    _line = _line.strip()
                    if _line:
                        trader_corpus.append(json.loads(_line))

        # Peer heats from all trader contracts
        trader_contracts_dir = pd / "trader" / "contracts"
        trader_peer_heats = []
        if trader_contracts_dir.exists():
            for p in trader_contracts_dir.glob("*.json"):
                doc = json.loads(p.read_text())
                trader_peer_heats.append(doc.get("contract", {}).get("heat", 0))

        if trader_contracts_dir.exists():
            trader_contract_enrich.enrich_all(
                slice_dir=trader_contracts_dir,
                corpus=trader_corpus,
                peer_heats=trader_peer_heats,
                today=today_t,
            )
            print(f"  enriched {len(list(trader_contracts_dir.glob('*.json')))} trader contract slices")

        # Portfolio + calendar aggregation
        from build._portfolio import build_portfolio
        from build._calendar import extract_calendar_events, calendar_month

        enriched_slices = []
        for p in sorted(trader_contracts_dir.glob("*.json")):
            enriched_slices.append(json.loads(p.read_text()))

        portfolio_data = build_portfolio(enriched_slices, today=today_t.isoformat())
        (pd / "trader" / "portfolio.json").parent.mkdir(parents=True, exist_ok=True)
        (pd / "trader" / "portfolio.json").write_text(json.dumps(portfolio_data, indent=2))

        all_cal_events = extract_calendar_events(enriched_slices)
        cal_months = []
        for offset in [-1, 0, 1]:
            m = today_t.month + offset
            y = today_t.year
            if m < 1:
                m += 12
                y -= 1
            elif m > 12:
                m -= 12
                y += 1
            cal_months.append(calendar_month(y, m, all_cal_events))
        cal_data = {"months": cal_months, "events": all_cal_events, "today": today_t.isoformat()}
        (pd / "trader" / "calendar.json").write_text(json.dumps(cal_data, indent=2))

        # Retrospective slices (reuse gamma enriched data if available)
        retro_dir = pd / "trader" / "retrospectives"
        retro_dir.mkdir(parents=True, exist_ok=True)
        for retro in cur_t.get("retrospectives", []):
            gamma_slice = pd / "gamma" / "contracts" / f"{retro['id']}.json"
            if gamma_slice.exists():
                import shutil
                shutil.copy(gamma_slice, retro_dir / f"{retro['id']}.json")

        print(f"  portfolio.json + calendar.json + {len(cur_t.get('retrospectives', []))} retrospectives")

    elif trader_curation.exists():
        print(f"WARN: corpus {corpus.relative_to(REPO)} missing — skipping trader slices")

    # β — heat-map + cascades + quarterly report
    beta_curation = REPO / "data" / "beta-curation.yml"
    cascades_yml = REPO / "data" / "cascades.yml"

    if beta_curation.exists() and corpus.exists():
        cur_b = yaml.safe_load(beta_curation.read_text())
        bd_b = cur_b.get("build_date")
        today_b = _dt.date.fromisoformat(bd_b) if bd_b else _dt.date.today()
        platform_b = cur_b["platform_footprint"]
        footprint_b = REPO / "data" / "platforms" / platform_b / "footprint.yml"

        from build.beta_cascades import generate as gen_beta_cascades
        from build.beta_heatmap import generate as gen_beta_heatmap
        from build.beta_report import generate as gen_beta_report

        gen_beta_heatmap(
            corpus_path=corpus, curation_path=beta_curation,
            footprint_path=footprint_b,
            out_path=pd / "beta" / "heatmap.json", today=today_b,
        )
        gen_beta_cascades(
            cascades_path=cascades_yml, curation_path=beta_curation,
            footprint_path=footprint_b,
            out_path=pd / "beta" / "cascades.json", today=today_b,
        )
        gen_beta_report(
            corpus_path=corpus, curation_path=beta_curation,
            footprint_path=footprint_b, cascades_path=cascades_yml,
            out_path=pd / "beta" / "report.json", today=today_b,
        )
        print(f"beta (build_date={today_b.isoformat()}, "
              f"platform={platform_b}): heatmap + cascades + report")
    elif beta_curation.exists():
        print(f"WARN: corpus {corpus.relative_to(REPO)} missing — skipping beta slices")
    elif corpus.exists():
        print(f"WARN: {beta_curation.relative_to(REPO)} missing — skipping beta slices")


if __name__ == "__main__":
    main()
