"""Match 10-K filings to SEC acceptance timestamps by CIK and accession."""

from pathlib import Path
import os
import time

import pandas as pd
import requests


ROOT = Path(__file__).resolve().parents[1]
FILINGS = ROOT / "data/metadata/filings_2016_2025.csv"
OUT = ROOT / "data/metadata/filing_acceptance.csv"
BASE = "https://data.sec.gov/submissions/"
USER_AGENT = os.environ.get("SEC_USER_AGENT")


def get_json(session: requests.Session, name: str) -> dict:
    for attempt in range(4):
        response = session.get(BASE + name, timeout=30)
        if response.status_code == 200:
            time.sleep(0.12)
            return response.json()
        if response.status_code not in (429, 500, 502, 503, 504):
            response.raise_for_status()
        time.sleep(2 ** attempt)
    response.raise_for_status()
    raise RuntimeError(name)


def rows_from_recent(data: dict) -> dict[str, str]:
    recent = data["filings"]["recent"] if "filings" in data else data
    return dict(zip(recent["accessionNumber"], recent["acceptanceDateTime"]))


def main() -> None:
    if not USER_AGENT:
        raise RuntimeError("Set SEC_USER_AGENT to a project name and contact email")
    filings = pd.read_csv(FILINGS, dtype={"cik": str, "accession_number": str})
    session = requests.Session()
    session.headers.update({"User-Agent": USER_AGENT, "Accept-Encoding": "gzip, deflate"})
    output = []
    for cik, group in filings.groupby("cik", sort=True):
        data = get_json(session, f"CIK{int(cik):010d}.json")
        timestamps = rows_from_recent(data)
        wanted = set(group.accession_number)
        if wanted - timestamps.keys():
            for old in data["filings"]["files"]:
                if old["filingTo"] < "2016-01-01" or old["filingFrom"] > "2025-12-31":
                    continue
                timestamps.update(rows_from_recent(get_json(session, old["name"])))
                if wanted.issubset(timestamps):
                    break
        for _, filing in group.iterrows():
            stamp = timestamps.get(filing.accession_number, "")
            output.append({
                "ticker": filing.ticker,
                "cik": cik,
                "accession_number": filing.accession_number,
                "filing_date": filing.filing_date,
                "accepted_at_utc": stamp,
                "status": "matched" if stamp else "missing",
            })
    result = pd.DataFrame(output)
    if result.duplicated(["ticker", "accession_number"]).any():
        raise ValueError("Duplicate filing acceptance key")
    if not result.status.eq("matched").all():
        missing = result.loc[result.status.ne("matched"), ["ticker", "accession_number"]]
        raise RuntimeError(f"SEC acceptance timestamps missing for {len(missing)} filings")
    result.to_csv(OUT, index=False)
    print(f"Matched SEC acceptance timestamps for {len(result)} filings.")


if __name__ == "__main__":
    main()
