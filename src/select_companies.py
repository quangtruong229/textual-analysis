from pathlib import Path
import os
import time

import pandas as pd
import requests


# ============================================================
# CONFIG
# ============================================================

START_DATE = "2016-01-01"
END_DATE = "2025-12-31"

TARGET_COMPANIES = 100

USER_AGENT = os.environ.get("SEC_USER_AGENT", "").strip()


# ============================================================
# PATHS
# ============================================================

DATA_DIR = Path(__file__).resolve().parents[1] / "data"
METADATA_DIR = DATA_DIR / "metadata"

# ============================================================
# SEC HEADERS
# ============================================================

SEC_HEADERS = {
    "User-Agent": USER_AGENT,
    "Accept-Encoding": "gzip, deflate",
}

DATA_HEADERS = {
    "User-Agent": USER_AGENT,
    "Accept-Encoding": "gzip, deflate",
}


# ============================================================
# HELPER
# ============================================================

def get_json(url: str, headers: dict) -> dict:
    """Download JSON from SEC."""
    if not headers.get("User-Agent"):
        raise RuntimeError("Set SEC_USER_AGENT to a group name and contact email before requesting SEC data")
    response = requests.get(
        url,
        headers=headers,
        timeout=30
    )

    response.raise_for_status()

    return response.json()


# ============================================================
# GET COMPANY LIST
# ============================================================

def get_company_list() -> pd.DataFrame:
    """
    Download SEC company ticker/exchange list.
    """

    url = "https://www.sec.gov/files/company_tickers_exchange.json"

    print("Downloading SEC company list...")

    data = get_json(url, SEC_HEADERS)

    rows = data["data"]

    df = pd.DataFrame(
        rows,
        columns=[
            "cik",
            "company_name",
            "ticker",
            "exchange",
        ],
    )

    # Keep major US exchanges for now
    df = df[
        df["exchange"].isin(
            [
                "NYSE",
                "Nasdaq",
                "NYSE American",
            ]
        )
    ].copy()

    # SEC CIK must be represented by 10 digits
    df["cik"] = (
        df["cik"]
        .astype(int)
        .astype(str)
        .str.zfill(10)
    )

    return df


# ============================================================
# GET 10-K FILINGS
# ============================================================

def get_10k_filings(cik: str) -> list:
    """
    Get 10-K filings for a company.
    """

    url = (
        f"https://data.sec.gov/"
        f"submissions/CIK{cik}.json"
    )

    data = get_json(url, DATA_HEADERS)

    recent = pd.DataFrame(
        data["filings"]["recent"]
    )

    if recent.empty:
        return []

    # Convert dates
    recent["filingDate"] = pd.to_datetime(
        recent["filingDate"],
        errors="coerce"
    )

    # Filter:
    #   Form = 10-K
    #   Filing date = 2016-2025
    filtered = recent[
        (recent["form"] == "10-K")
        & (
            recent["filingDate"]
            >= pd.Timestamp(START_DATE)
        )
        & (
            recent["filingDate"]
            <= pd.Timestamp(END_DATE)
        )
    ].copy()

    records = []

    for _, row in filtered.iterrows():

        records.append(
            {
                "cik": cik,

                "filing_date":
                    row["filingDate"].strftime(
                        "%Y-%m-%d"
                    ),

                "report_date":
                    row.get(
                        "reportDate",
                        ""
                    ),

                "form":
                    row["form"],

                "accession_number":
                    row["accessionNumber"],

                "primary_document":
                    row["primaryDocument"],
            }
        )

    return records


# ============================================================
# MAIN
# ============================================================

def main():
    METADATA_DIR.mkdir(parents=True, exist_ok=True)

    # --------------------------------------------------------
    # 1. Get SEC company list
    # --------------------------------------------------------

    companies = get_company_list()

    print(
        f"SEC candidate companies: "
        f"{len(companies):,}"
    )

    selected_companies = []

    all_filings = []


    # --------------------------------------------------------
    # 2. Scan companies
    # --------------------------------------------------------

    for _, company in companies.iterrows():

        cik = company["cik"]

        try:

            filings = get_10k_filings(cik)

            # We want companies with approximately
            # 10 years of annual 10-K filings.
            if len(filings) >= 10:

                selected_companies.append(
                    {
                        "cik":
                            cik,

                        "company_name":
                            company["company_name"],

                        "ticker":
                            company["ticker"],

                        "exchange":
                            company["exchange"],

                        "n_10k":
                            len(filings),
                    }
                )


                # Attach company information
                # to every filing
                for filing in filings:

                    filing["company_name"] = (
                        company["company_name"]
                    )

                    filing["ticker"] = (
                        company["ticker"]
                    )

                all_filings.extend(
                    filings
                )


                print(
                    f"[{len(selected_companies):03d}/"
                    f"{TARGET_COMPANIES}] "
                    f"{company['ticker']} "
                    f"{company['company_name']} "
                    f"-> {len(filings)} 10-K"
                )


            # Stop after reaching target
            if (
                len(selected_companies)
                >= TARGET_COMPANIES
            ):
                break


            # Respect SEC fair-access policy
            time.sleep(0.15)


        except Exception as e:

            print(
                f"ERROR "
                f"{company['ticker']}: "
                f"{e}"
            )


    # --------------------------------------------------------
    # 3. Convert to DataFrames
    # --------------------------------------------------------

    companies_df = pd.DataFrame(
        selected_companies
    )

    filings_df = pd.DataFrame(
        all_filings
    )


    # --------------------------------------------------------
    # 4. Save metadata
    # --------------------------------------------------------

    companies_path = (
        METADATA_DIR
        / "companies_100.csv"
    )

    filings_path = (
        METADATA_DIR
        / "filings_2016_2025.csv"
    )


    companies_df.to_csv(
        companies_path,
        index=False,
        encoding="utf-8-sig",
    )

    filings_df.to_csv(
        filings_path,
        index=False,
        encoding="utf-8-sig",
    )


    # --------------------------------------------------------
    # 5. Final report
    # --------------------------------------------------------

    print()
    print("=" * 50)
    print("DONE")
    print("=" * 50)

    print(
        f"Companies: "
        f"{len(companies_df)}"
    )

    print(
        f"10-K filings: "
        f"{len(filings_df)}"
    )

    print(
        f"Saved: "
        f"{companies_path}"
    )

    print(
        f"Saved: "
        f"{filings_path}"
    )


# ============================================================
# ENTRY POINT
# ============================================================

if __name__ == "__main__":
    main()
