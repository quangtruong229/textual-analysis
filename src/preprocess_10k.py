from pathlib import Path
from collections import Counter
import argparse
import html
import re
import unicodedata
import warnings

import pandas as pd
from bs4 import BeautifulSoup, Comment
from bs4 import XMLParsedAsHTMLWarning


# ============================================================
# IGNORE EXPECTED SEC/XBRL PARSER WARNING
# ============================================================

warnings.filterwarnings(
    "ignore",
    category=XMLParsedAsHTMLWarning
)


# ============================================================
# PATHS
# ============================================================

BASE_DIR = Path(__file__).resolve().parent.parent

METADATA_FILE = (
    BASE_DIR
    / "data"
    / "metadata"
    / "filings_2016_2025.csv"
)

RAW_DIR = (
    BASE_DIR
    / "data"
    / "raw"
    / "10k"
)

PROCESSED_DIR = (
    BASE_DIR
    / "data"
    / "processed"
    / "10k"
)

OUTPUT_METADATA = (
    BASE_DIR
    / "data"
    / "metadata"
    / "preprocessed_10k.csv"
)


# ============================================================
# TAGS THAT SHOULD NOT ENTER TEXTUAL ANALYSIS
# ============================================================

REMOVE_TAGS = [
    "script",
    "style",
    "noscript",
    "template",
    "svg",
    "canvas",
    "form",
    "input",
    "button",
    "select",
    "option",
    "textarea",
]


# Inline XBRL containers containing metadata rather than
# human-readable narrative text.
XBRL_CONTAINER_TAGS = {
    "ix:header",
    "ix:hidden",
    "ix:references",
    "ix:resources",
    "xbrli:unit",
}


# ============================================================
# TEXT NORMALIZATION
# ============================================================

def normalize_line(line: str) -> str:
    """
    Normalize one line of extracted text.
    """

    # Convert HTML entities such as &amp; -> &
    line = html.unescape(line)

    # Normalize Unicode characters
    line = unicodedata.normalize("NFKC", line)

    # Replace tabs and unusual whitespace
    line = re.sub(
        r"[\t\r\f\v]+",
        " ",
        line
    )

    # Collapse repeated spaces
    line = re.sub(
        r" {2,}",
        " ",
        line
    )

    return line.strip()


def is_page_number(line: str) -> bool:
    """
    Identify simple page-number lines.

    Examples:
        1
        15
        Page 15
        Page 15 of 120
    """

    patterns = [
        r"^\d+$",
        r"^page\s+\d+$",
        r"^page\s+\d+\s+of\s+\d+$",
    ]

    for pattern in patterns:
        if re.fullmatch(
            pattern,
            line,
            flags=re.IGNORECASE
        ):
            return True

    return False


def remove_repeated_headers(lines: list[str]) -> list[str]:
    """
    Remove exact lines appearing many times.

    This is intended mainly for repeated:
    - company names
    - document headers
    - page footers
    - page numbers not caught above

    Conservative threshold:
        >= 12 occurrences
        AND <= 150 characters
    """

    counts = Counter(lines)

    cleaned = []

    for line in lines:

        repeated_too_much = (
            counts[line] >= 12
            and len(line) <= 150
        )

        if repeated_too_much:
            continue

        cleaned.append(line)

    return cleaned


# ============================================================
# CLEAN ONE HTML FILE
# ============================================================

def clean_html_file(file_path: Path) -> str:
    """
    Read one SEC 10-K HTML/XHTML file and return cleaned text.
    """

    raw_bytes = file_path.read_bytes()

    # --------------------------------------------------------
    # Parse SEC filing
    # --------------------------------------------------------

    soup = BeautifulSoup(
        raw_bytes,
        "lxml"
    )

    # --------------------------------------------------------
    # Remove HTML comments
    # --------------------------------------------------------

    for comment in soup.find_all(
        string=lambda text: isinstance(text, Comment)
    ):
        comment.extract()

    # --------------------------------------------------------
    # Remove non-text HTML elements
    # --------------------------------------------------------

    for tag_name in REMOVE_TAGS:

        for tag in soup.find_all(tag_name):
            tag.decompose()

    # --------------------------------------------------------
    # Remove document head
    # --------------------------------------------------------

    if soup.head is not None:
        soup.head.decompose()

    # --------------------------------------------------------
    # Remove XBRL metadata containers
    # --------------------------------------------------------
    #
    # Important:
    #
    # We remove metadata containers such as:
    #
    #   ix:header
    #   ix:hidden
    #   ix:references
    #   ix:resources
    #
    # because their contents created noise such as:
    #
    #   us-gaap:...
    #   xbrli:...
    #   iso4217:...
    #   P1Y
    #   P2Y
    #
    # which appeared in the previous test.
    # --------------------------------------------------------

    tags_to_remove = []

    for tag in soup.find_all(True):

        tag_name = str(tag.name).lower()

        # XBRL metadata containers
        if tag_name in XBRL_CONTAINER_TAGS:
            tags_to_remove.append(tag)
            continue

        # Explicitly hidden elements
        style = str(
            tag.get("style", "")
        ).lower()

        style_normalized = re.sub(
            r"\s+",
            "",
            style
        )

        if (
            "display:none" in style_normalized
            or "visibility:hidden" in style_normalized
        ):
            tags_to_remove.append(tag)

    for tag in tags_to_remove:

        try:
            tag.decompose()

        except ValueError:
            pass

    # --------------------------------------------------------
    # Unwrap remaining inline XBRL tags
    # --------------------------------------------------------
    #
    # We KEEP their human-readable content.
    #
    # Example:
    #
    #   <ix:nonNumeric>
    #       Apple Inc.
    #   </ix:nonNumeric>
    #
    # becomes:
    #
    #   Apple Inc.
    # --------------------------------------------------------

    for tag in soup.find_all(True):

        tag_name = str(tag.name).lower()

        if (
            tag_name.startswith("ix:")
            or tag_name in {
                "ixbrl",
                "nonfraction",
                "nonnumeric",
            }
        ):

            try:
                tag.unwrap()

            except ValueError:
                pass

    # --------------------------------------------------------
    # Convert HTML -> text
    # --------------------------------------------------------

    text = soup.get_text(
        separator="\n"
    )

    # --------------------------------------------------------
    # Normalize lines
    # --------------------------------------------------------

    raw_lines = text.splitlines()

    lines = []

    for line in raw_lines:

        line = normalize_line(line)

        if not line:
            continue

        # Remove simple page numbers
        if is_page_number(line):
            continue

        lines.append(line)

    # --------------------------------------------------------
    # Remove repetitive headers / footers
    # --------------------------------------------------------

    lines = remove_repeated_headers(lines)

    # --------------------------------------------------------
    # Final whitespace normalization
    # --------------------------------------------------------

    cleaned_text = "\n".join(lines)

    cleaned_text = re.sub(
        r"\n{3,}",
        "\n\n",
        cleaned_text
    )

    cleaned_text = cleaned_text.strip()

    return cleaned_text


# ============================================================
# FIND RAW FILE
# ============================================================

def find_raw_file(
    ticker: str,
    accession_number: str,
    primary_document: str
) -> Path | None:
    """
    Locate the downloaded raw HTML file.
    """

    ticker_dir = RAW_DIR / ticker

    if not ticker_dir.exists():
        return None

    # Primary method:
    # metadata gives the exact SEC primary document name.
    exact_path = ticker_dir / primary_document

    if exact_path.exists():
        return exact_path

    # Fallback:
    # search using accession number without dashes.
    accession_clean = accession_number.replace(
        "-",
        ""
    )

    candidates = list(
        ticker_dir.glob(
            f"*{accession_clean}*"
        )
    )

    if candidates:
        return candidates[0]

    return None


# ============================================================
# PROCESS ONE FILING
# ============================================================

def process_one_row(row: pd.Series) -> dict:
    """
    Process one filing and return metadata / validation results.
    """

    ticker = str(
        row["ticker"]
    )

    accession_number = str(
        row["accession_number"]
    )

    primary_document = str(
        row["primary_document"]
    )

    raw_file = find_raw_file(
        ticker=ticker,
        accession_number=accession_number,
        primary_document=primary_document,
    )

    result = {
        "ticker": ticker,
        "filing_date": row["filing_date"],
        "report_date": row["report_date"],
        "accession_number": accession_number,
        "company_name": row["company_name"],
        "raw_file": "",
        "processed_file": "",
        "status": "",
        "char_count": 0,
        "word_count": 0,
        "error": "",
    }

    # --------------------------------------------------------
    # Raw file missing
    # --------------------------------------------------------

    if raw_file is None:

        result["status"] = "missing_raw"

        result["error"] = (
            "Raw HTML file not found"
        )

        return result

    result["raw_file"] = str(
        raw_file.relative_to(BASE_DIR)
    )

    # --------------------------------------------------------
    # Output file
    # --------------------------------------------------------

    accession_clean = accession_number.replace(
        "-",
        ""
    )

    ticker_dir = (
        PROCESSED_DIR
        / ticker
    )

    ticker_dir.mkdir(
        parents=True,
        exist_ok=True
    )

    output_file = (
        ticker_dir
        / f"{accession_clean}.txt"
    )

    result["processed_file"] = str(
        output_file.relative_to(BASE_DIR)
    )

    # --------------------------------------------------------
    # Process
    # --------------------------------------------------------

    try:

        cleaned_text = clean_html_file(
            raw_file
        )

        # Basic quality check
        if len(cleaned_text) < 100:

            result["status"] = "too_short"

            result["error"] = (
                "Cleaned text is unexpectedly short"
            )

            return result

        # Word count
        word_count = len(
            re.findall(
                r"\b[\w'-]+\b",
                cleaned_text
            )
        )

        # Save clean text
        output_file.write_text(
            cleaned_text,
            encoding="utf-8"
        )

        result["status"] = "success"

        result["char_count"] = len(
            cleaned_text
        )

        result["word_count"] = word_count

    except Exception as exc:

        result["status"] = "error"

        result["error"] = repr(exc)

    return result


# ============================================================
# MAIN
# ============================================================

def main():

    parser = argparse.ArgumentParser(
        description=(
            "Preprocess SEC 10-K HTML filings "
            "into clean text."
        )
    )

    parser.add_argument(
        "--test",
        action="store_true",
        help="Process only the first filing."
    )

    parser.add_argument(
        "--ticker",
        type=str,
        default=None,
        help="Process one ticker, e.g. AAPL."
    )

    parser.add_argument(
        "--all",
        action="store_true",
        help="Process all filings."
    )

    args = parser.parse_args()

    # --------------------------------------------------------
    # Load metadata
    # --------------------------------------------------------

    if not METADATA_FILE.exists():

        raise FileNotFoundError(
            f"Metadata file not found: "
            f"{METADATA_FILE}"
        )

    df = pd.read_csv(
        METADATA_FILE
    )

    required_columns = [
        "ticker",
        "filing_date",
        "report_date",
        "accession_number",
        "primary_document",
        "company_name",
    ]

    missing_columns = [
        col
        for col in required_columns
        if col not in df.columns
    ]

    if missing_columns:

        raise ValueError(
            "Missing columns in metadata: "
            f"{missing_columns}"
        )

    # --------------------------------------------------------
    # Filter by ticker
    # --------------------------------------------------------

    if args.ticker:

        ticker = args.ticker.upper()

        df = df[
            df["ticker"]
            .astype(str)
            .str.upper()
            == ticker
        ].copy()

        if df.empty:

            raise ValueError(
                f"No filings found for ticker: "
                f"{ticker}"
            )

    # --------------------------------------------------------
    # Select processing mode
    # --------------------------------------------------------

    if args.test:

        df = df.head(1).copy()

    elif not args.all and not args.ticker:

        parser.error(
            "Use --test, --ticker TICKER, or --all."
        )

    # --------------------------------------------------------
    # Process filings
    # --------------------------------------------------------

    results = []

    total = len(df)

    print("=" * 60)
    print("10-K PREPROCESSING")
    print("=" * 60)

    print(
        f"Files to process: {total}"
    )

    print()

    for i, (_, row) in enumerate(
        df.iterrows(),
        start=1
    ):

        ticker = row["ticker"]

        accession = row[
            "accession_number"
        ]

        print(
            f"[{i:4d}/{total}] "
            f"{ticker:<8} "
            f"{accession}"
        )

        result = process_one_row(
            row
        )

        results.append(
            result
        )

    # --------------------------------------------------------
    # Save metadata
    # --------------------------------------------------------

    results_df = pd.DataFrame(
        results
    )

    OUTPUT_METADATA.parent.mkdir(
        parents=True,
        exist_ok=True
    )

    results_df.to_csv(
        OUTPUT_METADATA,
        index=False,
        encoding="utf-8-sig"
    )

    # --------------------------------------------------------
    # Summary
    # --------------------------------------------------------

    success = (
        results_df["status"]
        == "success"
    ).sum()

    failed = (
        results_df["status"]
        != "success"
    ).sum()

    total_words = (
        results_df["word_count"]
        .sum()
    )

    print()

    print("=" * 60)
    print("PREPROCESSING COMPLETE")
    print("=" * 60)

    print(
        f"Success      : {success:,}"
    )

    print(
        f"Failed       : {failed:,}"
    )

    print(
        f"Total words  : {total_words:,}"
    )

    print()

    print(
        "Metadata saved:"
    )

    print(
        OUTPUT_METADATA
    )

    # --------------------------------------------------------
    # Show failures
    # --------------------------------------------------------

    if failed > 0:

        print()

        print(
            "Failed files:"
        )

        print(
            results_df[
                results_df["status"]
                != "success"
            ][
                [
                    "ticker",
                    "filing_date",
                    "accession_number",
                    "status",
                    "error",
                ]
            ].to_string(
                index=False
            )
        )


# ============================================================
# ENTRY POINT
# ============================================================

if __name__ == "__main__":
    main()