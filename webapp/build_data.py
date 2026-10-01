"""Build embedded data for the web app from analysis CSV outputs.

Run from the repository root:
    python webapp/build_data.py

Reads the result CSVs used by the webapp and writes webapp/data.js.
No statistical recalculation is performed — every number shown on the
UI comes directly from the saved CSV tables.
"""

from __future__ import annotations

import csv
import hashlib
import json
import math
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "webapp" / "data.js"
IDENTIFIERS = {"ticker", "cik", "accession_number", "sec_url"}


def parse_value(v: str):
    """Convert a CSV string to int, float, bool or str."""
    if v is None or v.strip() == "":
        return None
    s = v.strip()
    if s.lower() == "true":
        return True
    if s.lower() == "false":
        return False
    try:
        f = float(s)
        if not math.isfinite(f):
            return None
        if "." not in s and "e" not in s.lower() and f == int(f):
            return int(f)
        return f
    except (ValueError, TypeError):
        return s


def read_csv_typed(path: Path, columns: list[str] | None = None) -> list[dict]:
    """Read a CSV with automatic type conversion."""
    rows: list[dict] = []
    with open(path, encoding="utf-8-sig", newline="") as f:
        for row in csv.DictReader(f):
            if columns:
                rows.append({k: row.get(k, "") if k in IDENTIFIERS else parse_value(row.get(k, "")) for k in columns})
            else:
                rows.append({k: v if k in IDENTIFIERS else parse_value(v) for k, v in row.items()})
    return rows


def compare_source_bytes(raw: bytes, expected: str) -> dict:
    """Phân biệt khớp byte, khác xuống dòng và khác nội dung."""
    current = hashlib.sha256(raw).hexdigest()
    lf = raw.replace(b"\r\n", b"\n")
    if current == expected:
        status = "exact"
    elif expected in {
        hashlib.sha256(lf).hexdigest(),
        hashlib.sha256(lf.replace(b"\n", b"\r\n")).hexdigest(),
    }:
        status = "line_endings_only"
    else:
        status = "mismatch"
    return {"current_sha256": current, "status": status}


def source_integrity(hashes: dict) -> dict:
    """Ghi nhận đối chiếu nguồn tại thời điểm đóng gói, giữ nguyên mã băm gốc."""
    result = {}
    for name, expected in hashes.items():
        path = ROOT / name.replace("\\", "/")
        result[name] = compare_source_bytes(path.read_bytes(), expected) if path.is_file() else {
            "current_sha256": None, "status": "missing",
        }
    return result


def main() -> None:
    a = ROOT / "analysis_outputs"

    manifest = json.loads(
        (ROOT / "handoff" / "manifest.json").read_text(encoding="utf-8")
    )
    verification = json.loads(
        (a / "verification.json").read_text(encoding="utf-8")
    )

    firm_year = read_csv_typed(a / "tone_firm_year.csv", [
        "ticker", "company_name", "cik", "filing_year", "report_year",
        "filing_date", "report_date", "accession_number", "sec_url",
        "item_7_mda_lm_status",
        "item_7_mda_total_words", "item_7_mda_positive_count",
        "item_7_mda_negative_count", "item_7_mda_uncertainty_count",
        "item_7_mda_net_tone",
        "lm_net_prop", "lm_net_ratio", "lm_net_tfidf",
        "lm_negated_positive_count", "lm_negated_negative_count",
        "harvard_net_prop", "harvard_net_tfidf",
        "event_date",
        "CAR_m1_p1", "CAR_0_p3", "CAR_m3_p3", "CAR_m5_p5",
        "has_item7_tone", "has_method_score", "has_event_car",
    ])

    event_summary = read_csv_typed(a / "event_study" / "event_study_summary.csv")
    event_daily = read_csv_typed(a / "event_study" / "event_daily_summary.csv")
    event_filing = read_csv_typed(a / "event_study" / "event_filing_results.csv")

    regression = read_csv_typed(a / "regression" / "regression_results.csv")
    c2 = read_csv_typed(a / "c2_reduced_results.csv")
    extended = {
        "c2Full6": "c2_full6_results.csv",
        "c2Matched4": "c2_matched4_results.csv",
        "wordPower": "word_power/regression_results.csv",
        "b6": "event_study/b6_robustness_tests.csv",
        "brownWarner": "event_study/extended_window_tests.csv",
        "c5Full6": "c5_full6_results.csv",
        "c6": "c6_delayed_results.csv",
        "c7": "c7_cross_section_results.csv",
        "c8": "c8_fama_macbeth_summary.csv",
    }

    dict_summary_rows = read_csv_typed(a / "dictionary_comparison_summary.csv")
    dict_filings = read_csv_typed(a / "dictionary_comparison_filings.csv", [
        "ticker", "company_name", "filing_date", "report_date",
        "accession_number",
        "lm_net_prop", "harvard_net_prop", "opposite_sign", "harvard_minus_lm",
    ])

    missing = read_csv_typed(a / "missing_filings.csv")
    exclusions = read_csv_typed(a / "event_study" / "event_exclusions.csv")

    desc_path = a / "regression" / "regression_descriptives.csv"
    descriptives = read_csv_typed(desc_path) if desc_path.exists() else []

    data = {
        "generatedAt": datetime.now().isoformat(),
        "manifest": manifest,
        "verification": verification,
        "sourceIntegrity": source_integrity(verification.get("source_sha256", {})),
        "firmYear": firm_year,
        "eventSummary": event_summary,
        "eventDaily": event_daily,
        "eventFiling": event_filing,
        "regression": regression,
        "c2": c2,
        **{key: read_csv_typed(a / path) for key, path in extended.items()},
        "dictSummary": dict_summary_rows[0] if dict_summary_rows else {},
        "dictFilings": dict_filings,
        "missing": missing,
        "exclusions": exclusions,
        "descriptives": descriptives,
    }

    OUT.parent.mkdir(exist_ok=True)
    ts = data["generatedAt"]
    content = (
        "// Auto-generated from analysis CSVs — do not edit.\n"
        f"// Built: {ts}\n"
        f"window.APP_DATA = {json.dumps(data, ensure_ascii=False)};\n"
    )
    OUT.write_text(content, encoding="utf-8", newline="\n")

    kb = OUT.stat().st_size / 1024
    print(f"Wrote {OUT} ({kb:.0f} KB)")
    for key in ("firmYear", "eventSummary", "eventFiling", "regression", "c2", "dictFilings", "missing"):
        print(f"  {key}: {len(data[key])} rows")


if __name__ == "__main__":
    main()
