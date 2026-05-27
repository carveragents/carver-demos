#!/usr/bin/env python3
"""
Preprocess raw PMS data from USA/UK/CH into slim, cardiovascular-filtered
JSON files suitable for direct import into the React demo.

Output: public/data/events_us.json
        public/data/events_uk.json
        public/data/events_ch.json
        public/data/summary.json
"""

import json, re, os, sys
from pathlib import Path
from collections import Counter
from datetime import datetime

ROOT = Path(__file__).parent.parent
DATA_IN  = ROOT / "medical-device-data"
DATA_OUT = ROOT / "public" / "data"

DATA_OUT.mkdir(parents=True, exist_ok=True)

# ── Cardiovascular filter ─────────────────────────────────────────────────────

CARDIO_TERMS = [
    r"cardiac", r"cardio", r"\bheart\b", r"coronary", r"arrhythmia",
    r"atrial", r"ventricular", r"defibrillator", r"pacemaker",
    r"\becg\b", r"\bekg\b", r"electrophysiol",
    r"cardiac.catheter", r"coronary.stent", r"heart.valve",
    r"ablation", r"fibrillation", r"tachycardia", r"bradycardia",
    r"myocardial", r"transcatheter", r"\bicd\b", r"\bcrt\b",
    r"\bppg\b", r"cardioverter", r"electrogram",
    r"holter", r"physiolog.*monitor", r"ecg.*monitor", r"cardiac.*monitor",
    r"ambulatory.*ecg", r"cardiac.*rhythm",
]
CARDIO_PAT = re.compile("|".join(CARDIO_TERMS), re.IGNORECASE)

def is_cardio(*fields):
    text = " ".join(str(f) for f in fields if f)
    return bool(CARDIO_PAT.search(text))

# ── Severity normalisation ────────────────────────────────────────────────────

SEVERITY_MAP = {
    "death": "death",
    "serious injury": "serious",
    "injury": "serious",
    "death/serious injury risk": "serious",
    "serious (high-risk device class)": "serious",
    "serious": "serious",
    "malfunction": "malfunction",
    "near-miss": "near-miss",
}

def normalise_severity(raw):
    return SEVERITY_MAP.get((raw or "").lower(), "unknown")

# ── Date normalisation ────────────────────────────────────────────────────────

def normalise_date(raw):
    if not raw: return ""
    # MAUDE: "20260213"
    if re.match(r"^\d{8}$", raw):
        try: return datetime.strptime(raw, "%Y%m%d").strftime("%Y-%m-%d")
        except: pass
    # Already ISO
    if re.match(r"^\d{4}-\d{2}-\d{2}", raw):
        return raw[:10]
    # "19 March 2026"
    try: return datetime.strptime(raw.strip(), "%d %B %Y").strftime("%Y-%m-%d")
    except: pass
    return raw[:10] if raw else ""

# ── Source-specific parsers ───────────────────────────────────────────────────

def parse_usa(record):
    device = record.get("device_generic_name", "") or ""
    brand  = record.get("device_brand_name", "") or ""
    if not is_cardio(device, brand):
        return None
    return {
        "id":           f"US-{record.get('source_record_id', '')}",
        "date":         normalise_date(record.get("date_of_event") or record.get("date_received", "")),
        "received":     normalise_date(record.get("date_received", "")),
        "source":       "FDA_MAUDE",
        "country":      "US",
        "device_name":  (brand or device).strip(),
        "device_type":  device.strip(),
        "manufacturer": (record.get("manufacturer_d_name") or "").strip(),
        "model":        (record.get("model_number") or "").strip(),
        "product_code": record.get("device_report_product_code", ""),
        "udi_di":       record.get("udi_di", ""),
        "severity":     normalise_severity(record.get("severity", "")),
        "event_type":   record.get("event_type", ""),
        "is_recall":    False,
        "action":       record.get("action_taken", ""),
        "description":  (record.get("event_description") or "")[:400],
        "gmdn_term":    "",
    }

def parse_uk(record):
    device = record.get("device_name_raw", "") or ""
    dtype  = record.get("device_type_effective", "") or ""
    gmdn   = record.get("gmdn_term_proxy", "") or ""
    if not is_cardio(device, dtype, gmdn):
        return None
    return {
        "id":           f"UK-{record.get('source_native_id', '')}",
        "date":         normalise_date(record.get("event_date") or record.get("report_date", "")),
        "received":     normalise_date(record.get("report_date", "")),
        "source":       "MHRA",
        "country":      "UK",
        "device_name":  device.strip(),
        "device_type":  (dtype or gmdn).strip(),
        "manufacturer": (record.get("manufacturer_name_raw") or "").strip(),
        "model":        "",
        "product_code": "",
        "udi_di":       record.get("udi_di", "") or "",
        "severity":     normalise_severity(record.get("severity", "")),
        "event_type":   record.get("action_type", "Field Safety Notice"),
        "is_recall":    bool(record.get("is_recall", False)),
        "action":       record.get("action_type", ""),
        "description":  "",
        "gmdn_term":    record.get("gmdn_term", "") or gmdn,
        "source_url":   record.get("source_url", ""),
    }

def parse_ch(record):
    device = record.get("device_name_raw", "") or ""
    dclass = record.get("device_class", "") or ""
    gmdn   = record.get("gmdn_term_proxy", "") or ""
    if not is_cardio(device, dclass, gmdn):
        return None
    return {
        "id":           f"CH-{record.get('source_native_id', '')}",
        "date":         normalise_date(record.get("event_date") or record.get("report_date", "")),
        "received":     normalise_date(record.get("report_date", "")),
        "source":       "Swissmedic",
        "country":      "CH",
        "device_name":  device.strip(),
        "device_type":  (dclass or gmdn).strip(),
        "manufacturer": (record.get("manufacturer_name_raw") or "").strip(),
        "model":        "",
        "product_code": "",
        "udi_di":       record.get("udi_di", "") or "",
        "severity":     normalise_severity(record.get("severity", "")),
        "event_type":   record.get("action_type", "FSCA"),
        "is_recall":    bool(record.get("is_recall", False)),
        "action":       record.get("corrective_action", "") or "",
        "description":  (record.get("problem_description") or record.get("hazard_description") or "")[:400],
        "gmdn_term":    record.get("gmdn_term", "") or gmdn,
        "source_url":   record.get("source_url", ""),
    }

# ── Main ──────────────────────────────────────────────────────────────────────

KEEP_FIELDS = {"id","date","received","source","country","device_name","device_type",
               "manufacturer","severity","event_type","is_recall","description","gmdn_term","source_url"}

def slim(record):
    return {k: v for k, v in record.items() if k in KEEP_FIELDS and v not in (None, "", [])}

def process(source_path, parser, out_name, cap=None):
    print(f"Processing {source_path} ...", end=" ", flush=True)
    with open(source_path) as f:
        records = json.load(f)
    parsed = [r for r in (parser(x) for x in records) if r]
    parsed.sort(key=lambda r: r["date"] or "", reverse=True)
    if cap: parsed = parsed[:cap]
    slimmed = [slim(r) for r in parsed]
    out_path = DATA_OUT / out_name
    with open(out_path, "w") as f:
        json.dump(slimmed, f, separators=(",", ":"))
    raw_size  = os.path.getsize(source_path)
    out_size  = os.path.getsize(out_path)
    print(f"{len(records):,} in → {len(parsed):,} cardiovascular{f' (capped at {cap})' if cap else ''}  ({raw_size/1e6:.1f}MB → {out_size/1e6:.2f}MB)")
    return parsed

def find_latest(country_dir):
    ts_dirs = sorted(country_dir.iterdir(), reverse=True)
    return next(d for d in ts_dirs if d.is_dir())

us_dir = find_latest(DATA_IN / "USA")
uk_dir = find_latest(DATA_IN / "UK")
ch_dir = find_latest(DATA_IN / "CH")

us = process(us_dir / "events.json",  parse_usa, "events_us.json", cap=1000)
uk = process(uk_dir / "events.json",  parse_uk,  "events_uk.json")
ch = process(ch_dir / "devices.json", parse_ch,  "events_ch.json")

all_events = us + uk + ch

# ── Summary stats ─────────────────────────────────────────────────────────────

def sev_counts(events):
    c = Counter(e["severity"] for e in events)
    return dict(c)

summary = {
    "generated_at": datetime.utcnow().isoformat() + "Z",
    "total": len(all_events),
    "by_source": {
        "US": {"count": len(us), "severity": sev_counts(us)},
        "UK": {"count": len(uk), "severity": sev_counts(uk)},
        "CH": {"count": len(ch), "severity": sev_counts(ch)},
    },
    "severity_totals": sev_counts(all_events),
    "recall_count": sum(1 for e in all_events if e.get("is_recall")),
    "death_count":  sum(1 for e in all_events if e["severity"] == "death"),
    "date_range": {
        "earliest": min((e["date"] for e in all_events if e["date"]), default=""),
        "latest":   max((e["date"] for e in all_events if e["date"]), default=""),
    },
}

with open(DATA_OUT / "summary.json", "w") as f:
    json.dump(summary, f, indent=2)

print(f"\nSummary: {summary['total']:,} total cardiovascular events")
print(f"  Deaths: {summary['death_count']}  |  Recalls: {summary['recall_count']}")
print(f"  Date range: {summary['date_range']['earliest']} → {summary['date_range']['latest']}")
print(f"  Files written to: {DATA_OUT}/")
