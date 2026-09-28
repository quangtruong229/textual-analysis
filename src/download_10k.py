from pathlib import Path
from urllib.parse import quote
import argparse
import time

import pandas as pd
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from tqdm import tqdm


# ============================================================
# CONFIG
# ============================================================

INPUT_FILE = Path(
    "data/metadata/filings_2016_2025.csv"
)

OUTPUT_DIR = Path(
    "data/raw/10k"
)

# QUAN TRỌNG:
# Thay bằng email thật của bạn.
USER_AGENT = (
    "textual-analysis research "
    "truongungquang1@gmail.com"
)

# 0.20 giây/request = tối đa khoảng 5 request/giây
# thấp hơn giới hạn 10 request/giây của SEC.
REQUEST_DELAY = 0.20

TIMEOUT = 60


# ============================================================
# CREATE DIRECTORIES
# ============================================================

OUTPUT_DIR.mkdir(
    parents=True,
    exist_ok=True
)


# ============================================================
# HTTP SESSION
# ============================================================

def create_session() -> requests.Session:
    """
    Create a requests session with automatic retry.
    """

    session = requests.Session()

    retry_strategy = Retry(
        total=3,
        backoff_factor=2,
        status_forcelist=[
            429,
            500,
            502,
            503,
            504,
        ],
        allowed_methods=[
            "GET",
        ],
        raise_on_status=False,
    )

    adapter = HTTPAdapter(
        max_retries=retry_strategy
    )

    session.mount(
        "https://",
        adapter
    )

    session.headers.update(
        {
            "User-Agent": USER_AGENT,
            "Accept-Encoding": "gzip, deflate",
        }
    )

    return session


# ============================================================
# BUILD SEC URL
# ============================================================

def build_sec_url(
    cik: str,
    accession_number: str,
    primary_document: str,
) -> str:
    """
    Build the SEC Archives URL for the primary filing document.
    """

    accession_no_dash = (
        accession_number.replace("-", "")
    )

    cik_number = str(
        int(str(cik))
    )

    document = quote(
        primary_document,
        safe=""
    )

    url = (
        "https://www.sec.gov/Archives/edgar/data/"
        f"{cik_number}/"
        f"{accession_no_dash}/"
        f"{document}"
    )

    return url


# ============================================================
# BUILD OUTPUT PATH
# ============================================================

def build_output_path(
    row: pd.Series,
) -> Path:
    """
    Organize files by ticker.

    Example:
    data/raw/10k/AAPL/
        AAPL_2025-10-31_000032019325000079_aapl-20250927.htm
    """

    ticker = str(
        row["ticker"]
    ).strip()

    filing_date = str(
        row["filing_date"]
    ).strip()

    accession = str(
        row["accession_number"]
    ).replace("-", "")

    primary_document = str(
        row["primary_document"]
    ).strip()

    ticker_dir = (
        OUTPUT_DIR / ticker
    )

    ticker_dir.mkdir(
        parents=True,
        exist_ok=True
    )

    filename = (
        f"{ticker}_"
        f"{filing_date}_"
        f"{accession}_"
        f"{primary_document}"
    )

    return ticker_dir / filename


# ============================================================
# DOWNLOAD ONE FILE
# ============================================================

def download_one(
    session: requests.Session,
    row: pd.Series,
) -> tuple[str, str]:
    """
    Download one 10-K.

    Returns:
        (status, path)
    """

    output_path = build_output_path(row)

    # --------------------------------------------------------
    # Skip already downloaded files
    # --------------------------------------------------------

    if output_path.exists():

        return (
            "SKIPPED",
            str(output_path)
        )


    # --------------------------------------------------------
    # Build URL
    # --------------------------------------------------------

    url = build_sec_url(
        cik=str(row["cik"]),
        accession_number=str(
            row["accession_number"]
        ),
        primary_document=str(
            row["primary_document"]
        ),
    )


    # --------------------------------------------------------
    # Request
    # --------------------------------------------------------

    response = session.get(
        url,
        timeout=TIMEOUT,
    )


    # --------------------------------------------------------
    # Check HTTP status
    # --------------------------------------------------------

    if response.status_code != 200:

        raise RuntimeError(
            f"HTTP {response.status_code} "
            f"for {url}"
        )


    # --------------------------------------------------------
    # Basic validation
    # --------------------------------------------------------

    if len(response.content) == 0:

        raise RuntimeError(
            "Downloaded file is empty"
        )


    # --------------------------------------------------------
    # Save raw HTML
    # --------------------------------------------------------

    output_path.write_bytes(
        response.content
    )


    return (
        "DOWNLOADED",
        str(output_path)
    )


# ============================================================
# TEST MODE
# ============================================================

def test_download(
    df: pd.DataFrame,
) -> None:
    """
    Download only the first filing.
    """

    first_row = df.iloc[0]

    print()
    print("=" * 60)
    print("TEST MODE")
    print("=" * 60)

    print(
        f"Company : {first_row['company_name']}"
    )

    print(
        f"Ticker  : {first_row['ticker']}"
    )

    print(
        f"Filing  : {first_row['filing_date']}"
    )

    print(
        f"Form    : {first_row['form']}"
    )

    print(
        f"Accession: "
        f"{first_row['accession_number']}"
    )

    url = build_sec_url(
        cik=str(first_row["cik"]),
        accession_number=str(
            first_row["accession_number"]
        ),
        primary_document=str(
            first_row["primary_document"]
        ),
    )

    print()
    print("SEC URL:")
    print(url)

    print()

    session = create_session()

    try:

        status, path = download_one(
            session,
            first_row
        )

        print(
            f"STATUS: {status}"
        )

        print(
            f"SAVED : {path}"
        )

        print()

        print(
            f"File size: "
            f"{Path(path).stat().st_size:,} bytes"
        )

        print()
        print("TEST SUCCESS")

    except Exception as e:

        print()
        print("TEST FAILED")
        print(
            f"ERROR: {e}"
        )

    finally:

        session.close()


# ============================================================
# DOWNLOAD ALL
# ============================================================

def download_all(
    df: pd.DataFrame,
) -> None:
    """
    Download all filings.
    """

    print()
    print("=" * 60)
    print("FULL DOWNLOAD")
    print("=" * 60)

    print(
        f"Total filings: {len(df):,}"
    )

    print(
        f"Output directory: {OUTPUT_DIR}"
    )

    print(
        f"Request delay: "
        f"{REQUEST_DELAY} seconds"
    )

    print()

    session = create_session()

    downloaded = 0
    skipped = 0
    failed = 0

    failures = []


    try:

        for _, row in tqdm(
            df.iterrows(),
            total=len(df),
            desc="Downloading 10-K",
        ):

            ticker = str(
                row["ticker"]
            )

            filing_date = str(
                row["filing_date"]
            )


            try:

                status, path = download_one(
                    session,
                    row
                )

                if status == "DOWNLOADED":

                    downloaded += 1

                elif status == "SKIPPED":

                    skipped += 1


            except Exception as e:

                failed += 1

                failures.append(
                    {
                        "ticker":
                            ticker,

                        "filing_date":
                            filing_date,

                        "accession_number":
                            row[
                                "accession_number"
                            ],

                        "primary_document":
                            row[
                                "primary_document"
                            ],

                        "error":
                            str(e),
                    }
                )

                print()
                print(
                    f"ERROR: "
                    f"{ticker} "
                    f"{filing_date}: "
                    f"{e}"
                )


            # Respect SEC fair-access policy
            time.sleep(
                REQUEST_DELAY
            )


    finally:

        session.close()


    # --------------------------------------------------------
    # Save failure log
    # --------------------------------------------------------

    failure_file = (
        Path("data/metadata")
        / "download_failures.csv"
    )

    if failures:

        failures_df = pd.DataFrame(
            failures
        )

        failures_df.to_csv(
            failure_file,
            index=False,
            encoding="utf-8-sig"
        )


    # --------------------------------------------------------
    # Final report
    # --------------------------------------------------------

    print()
    print("=" * 60)
    print("DOWNLOAD COMPLETE")
    print("=" * 60)

    print(
        f"Downloaded : {downloaded:,}"
    )

    print(
        f"Skipped    : {skipped:,}"
    )

    print(
        f"Failed     : {failed:,}"
    )

    print(
        f"Total      : {len(df):,}"
    )

    if failures:

        print()
        print(
            f"Failure log:"
        )

        print(
            failure_file
        )

    print()


# ============================================================
# MAIN
# ============================================================

def main():

    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--test",
        action="store_true",
        help="Download only the first 10-K"
    )

    parser.add_argument(
        "--all",
        action="store_true",
        help="Download all 10-K filings"
    )

    args = parser.parse_args()


    # --------------------------------------------------------
    # Load metadata
    # --------------------------------------------------------

    if not INPUT_FILE.exists():

        raise FileNotFoundError(
            f"Input file not found: "
            f"{INPUT_FILE}"
        )

    df = pd.read_csv(
        INPUT_FILE
    )


    # --------------------------------------------------------
    # Basic validation
    # --------------------------------------------------------

    required_columns = [
        "cik",
        "filing_date",
        "form",
        "accession_number",
        "primary_document",
        "company_name",
        "ticker",
    ]

    missing_columns = [
        col
        for col in required_columns
        if col not in df.columns
    ]

    if missing_columns:

        raise ValueError(
            "Missing columns: "
            + ", ".join(
                missing_columns
            )
        )


    # --------------------------------------------------------
    # Filter 10-K
    # --------------------------------------------------------

    df = df[
        df["form"] == "10-K"
    ].copy()


    print(
        f"Metadata loaded: "
        f"{len(df):,} filings"
    )


    # --------------------------------------------------------
    # Mode selection
    # --------------------------------------------------------

    if args.test:

        test_download(df)

    elif args.all:

        download_all(df)

    else:

        print()
        print(
            "Please specify one of:"
        )

        print(
            "  python src/download_10k.py --test"
        )

        print(
            "  python src/download_10k.py --all"
        )


# ============================================================
# ENTRY POINT
# ============================================================

if __name__ == "__main__":
    main()