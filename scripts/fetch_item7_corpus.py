"""Fetch SEC 10-K HTML and reconstruct an auditable Item 7 word corpus.

Run with SEC_USER_AGENT set to a group name and contact email. By default this
fetches ten filings spread across the supplied 1,000-filing metadata table.
Use --all to fetch every filing with a validated Item 7 boundary.
"""

from __future__ import annotations

import argparse
import csv
import gzip
import hashlib
import os
import sys
import time
from collections import Counter
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

import pandas as pd
import requests

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from src import preprocess_10k  # noqa: E402
from src.build_method_scores import tokenize  # noqa: E402

FILINGS = ROOT / "data/metadata/filings_2016_2025.csv"
PREPROCESSED = ROOT / "data/metadata/preprocessed_10k.csv"
SECTIONS = ROOT / "data/metadata/sections_10k_v3.csv"
TONE = ROOT / "data/metadata/tone_method_item7.csv"
CORPUS = ROOT / "data/item7_corpus"
MANIFEST = CORPUS / "manifest.csv"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def key(row: pd.Series) -> tuple[str, str]:
    return str(row["ticker"]), str(row["filing_date"])


def fetch_one(row: pd.Series, expected: pd.Series, section: pd.Series | None,
              tone: pd.Series | None, session: requests.Session) -> dict[str, object]:
    accession = str(row["accession_number"]).replace("-", "")
    cik = str(int(row["cik"]))
    url = (
        "https://www.sec.gov/Archives/edgar/data/"
        f"{cik}/{accession}/{row['primary_document']}"
    )
    raw = (
        ROOT / "data/raw/10k" / str(row["ticker"])
        / f"{row['ticker']}_{row['filing_date']}_{accession}_{row['primary_document']}"
    )
    record: dict[str, object] = {
        "ticker": row["ticker"],
        "filing_date": row["filing_date"],
        "accession_number": row["accession_number"],
        "sec_url": url,
        "status": "",
        "raw_bytes": "",
        "raw_sha256": "",
        "item7_chars": "",
        "item7_tokens": "",
        "item7_sha256": "",
        "unique_terms": "",
        "error": "",
    }
    try:
        raw.parent.mkdir(parents=True, exist_ok=True)
        if not raw.exists():
            response = session.get(url, timeout=60)
            response.raise_for_status()
            payload = response.content
            if len(payload) < 1000 or b"<html" not in payload[:10000].lower():
                raise ValueError("SEC response is too short or not HTML")
            temporary = raw.with_name(raw.name + ".part")
            temporary.write_bytes(payload)
            temporary.replace(raw)
        record["raw_bytes"] = raw.stat().st_size
        record["raw_sha256"] = sha256(raw)

        cleaned = preprocess_10k.process_one_row(row)
        if cleaned["status"] != "success":
            raise ValueError(f"Preprocessing: {cleaned['status']}: {cleaned['error']}")
        if int(cleaned["char_count"]) != int(expected["char_count"]):
            raise ValueError("Cleaned 10-K length differs from existing metadata")
        if section is None or tone is None:
            record["status"] = "no_valid_item7"
            return record

        processed_path = ROOT / str(cleaned["processed_file"])
        lines = processed_path.read_text(encoding="utf-8").splitlines()
        start = int(float(section["item_7_mda_start_line"])) - 1
        end = int(float(section["item_7_mda_end_line"]))
        item7 = "\n".join(lines[start:end]).strip()
        if len(item7) != int(float(section["item_7_mda_chars"])):
            raise ValueError("Item 7 length differs from existing metadata")
        tokens = tokenize(item7)
        if len(tokens) != int(float(tone["lm_total_words"])):
            raise ValueError("Item 7 token count differs from existing tone table")

        section_path = ROOT / "data/sections_v3/10k" / str(row["ticker"]) / accession / "item_7_mda.txt"
        section_path.parent.mkdir(parents=True, exist_ok=True)
        section_path.write_text(item7, encoding="utf-8")
        terms_path = CORPUS / "terms" / str(row["ticker"]) / f"{accession}.csv.gz"
        terms_path.parent.mkdir(parents=True, exist_ok=True)
        with gzip.open(terms_path, "wt", encoding="utf-8", newline="") as stream:
            writer = csv.writer(stream)
            writer.writerow(["accession_number", "term", "count"])
            for term, count in sorted(Counter(tokens).items()):
                writer.writerow([str(row["accession_number"]), term, count])
        record.update({
            "status": "verified",
            "item7_chars": len(item7),
            "item7_tokens": len(tokens),
            "item7_sha256": sha256(section_path),
            "unique_terms": len(set(tokens)),
        })
    except Exception as exc:
        record["status"] = "failed"
        record["error"] = str(exc)
    return record


def run_task(task: tuple[pd.Series, pd.Series, pd.Series | None, pd.Series | None],
             user_agent: str, delay: float) -> dict[str, object]:
    row, expected, section, tone_row = task
    with requests.Session() as session:
        session.headers.update({"User-Agent": user_agent, "Accept": "text/html,application/xhtml+xml"})
        result = fetch_one(row, expected, section, tone_row, session)
    time.sleep(max(0.0, delay))
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--all", action="store_true", help="Fetch all validated Item 7 filings")
    parser.add_argument("--limit", type=int, default=10, help="Pilot size (default: 10)")
    parser.add_argument("--delay", type=float, default=0.35, help="Seconds between SEC requests")
    parser.add_argument("--workers", type=int, default=1, help="Concurrent workers (maximum 4)")
    args = parser.parse_args()
    user_agent = os.getenv("SEC_USER_AGENT", "").strip()
    if not user_agent or "@" not in user_agent:
        parser.error("Set SEC_USER_AGENT to a group name and contact email")
    if not 1 <= args.workers <= 4:
        parser.error("--workers must be between 1 and 4")

    filings = pd.read_csv(FILINGS, dtype=str)
    processed = pd.read_csv(PREPROCESSED, dtype=str).set_index(["ticker", "filing_date"])
    sections = pd.read_csv(SECTIONS, dtype=str).set_index(["ticker", "filing_date"])
    tone = pd.read_csv(TONE, dtype=str).set_index(["ticker", "filing_date"])
    if args.all:
        chosen = filings
        manifest_path = MANIFEST
    else:
        if args.limit < 1:
            parser.error("--limit must be positive")
        indices = [round(i * (len(filings) - 1) / max(args.limit - 1, 1)) for i in range(args.limit)]
        chosen = filings.iloc[sorted(set(indices))]
        manifest_path = CORPUS / "pilot_manifest.csv"

    results = []
    pending = []
    for _, row in chosen.iterrows():
        filing_key = key(row)
        if filing_key not in tone.index or sections.loc[filing_key, "item_7_mda_status"] != "success":
            pending.append((row, processed.loc[filing_key], None, None))
            continue
        pending.append((row, processed.loc[filing_key], sections.loc[filing_key], tone.loc[filing_key]))

    CORPUS.mkdir(parents=True, exist_ok=True)
    with ProcessPoolExecutor(max_workers=args.workers) as pool:
        futures = [pool.submit(run_task, task, user_agent, args.delay) for task in pending]
        for future in as_completed(futures):
            result = future.result()
            results.append(result)
            print(f"{result['ticker']} {result['filing_date']}: {result['status']} {result['error']}", flush=True)
            if len(results) % 25 == 0:
                pd.DataFrame(results).to_csv(manifest_path, index=False)
    results.sort(key=lambda x: (str(x["ticker"]), str(x["filing_date"])))
    pd.DataFrame(results).to_csv(manifest_path, index=False)
    print(f"Verified {sum(x['status'] == 'verified' for x in results)}/{len(results)}; manifest: {manifest_path}")


if __name__ == "__main__":
    main()
