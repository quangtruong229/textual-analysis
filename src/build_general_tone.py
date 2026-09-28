from pathlib import Path
import re
from collections import Counter

import pandas as pd


# ============================================================
# PATHS
# ============================================================

V3_METADATA = Path(
    "data/metadata/sections_10k_v3.csv"
)

SECTION_DIR = Path(
    "data/sections_v3/10k"
)

DICTIONARY_PATH = Path(
    "data/dictionary/HIV-4.csv"
)

OUTPUT = Path(
    "data/metadata/general_tone.csv"
)


# ============================================================
# MAIN SECTION
# ============================================================

MAIN_SECTION = "item_7_mda"


# ============================================================
# TOKENIZER
# ============================================================

WORD_RE = re.compile(
    r"[A-Za-z]+(?:[-'][A-Za-z]+)*"
)


def tokenize(text):
    return [
        x.upper()
        for x in WORD_RE.findall(str(text))
    ]


# ============================================================
# LOAD HARVARD-IV-4
# ============================================================

def load_dictionary():

    print("=" * 70)
    print("LOAD HARVARD-IV-4")
    print("=" * 70)

    df = pd.read_csv(
        DICTIONARY_PATH,
        low_memory=False,
    )

    df.columns = [
        str(c).strip()
        for c in df.columns
    ]

    if "Entry" not in df.columns:
        raise ValueError(
            "Không tìm thấy cột Entry."
        )

    if "Positiv" not in df.columns:
        raise ValueError(
            "Không tìm thấy cột Positiv."
        )

    if "Negativ" not in df.columns:
        raise ValueError(
            "Không tìm thấy cột Negativ."
        )

    df["_WORD"] = (
        df["Entry"]
        .astype(str)
        .str.strip()
        .str.upper()
    )

    positive = set(
        df.loc[
            df["Positiv"].notna(),
            "_WORD",
        ]
    )

    negative = set(
        df.loc[
            df["Negativ"].notna(),
            "_WORD",
        ]
    )

    print("Rows:", len(df))
    print("Positive:", len(positive))
    print("Negative:", len(negative))

    return {
        "positive": positive,
        "negative": negative,
    }


# ============================================================
# SECTION FILE
# ============================================================

def get_section_file(row):

    ticker = str(
        row["ticker"]
    ).upper()

    accession = str(
        row["accession_number"]
    ).strip()

    path = (
        SECTION_DIR
        / ticker
        / accession
        / f"{MAIN_SECTION}.txt"
    )

    return path if path.exists() else None


# ============================================================
# COUNT
# ============================================================

def count_general_tone(
    text,
    dictionary,
):

    tokens = tokenize(text)

    counts = Counter(tokens)

    total_words = len(tokens)

    positive_count = sum(
        counts[word]
        for word in counts
        if word in dictionary["positive"]
    )

    negative_count = sum(
        counts[word]
        for word in counts
        if word in dictionary["negative"]
    )

    positive_tone = (
        positive_count / total_words
        if total_words
        else None
    )

    negative_tone = (
        negative_count / total_words
        if total_words
        else None
    )

    net_tone = (
        positive_tone - negative_tone
        if positive_tone is not None
        and negative_tone is not None
        else None
    )

    return {
        "total_words": total_words,
        "positive_count": positive_count,
        "negative_count": negative_count,
        "positive_tone": positive_tone,
        "negative_tone": negative_tone,
        "net_tone": net_tone,
    }


# ============================================================
# MAIN
# ============================================================

def main():

    if not V3_METADATA.exists():
        raise FileNotFoundError(
            f"Missing: {V3_METADATA}"
        )

    if not DICTIONARY_PATH.exists():
        raise FileNotFoundError(
            f"Missing: {DICTIONARY_PATH}"
        )

    dictionary = load_dictionary()

    df = pd.read_csv(
        V3_METADATA,
        dtype={
            "accession_number": str,
        },
    )

    print()
    print("=" * 70)
    print("BUILD GENERAL SENTIMENT TONE")
    print("=" * 70)

    print("Filings:", len(df))
    print("Main section: Item 7 MD&A")

    rows = []

    for i, row in df.iterrows():

        result = {
            "ticker": row["ticker"],
            "filing_date": row["filing_date"],
            "report_date": row.get("report_date"),
            "accession_number": row[
                "accession_number"
            ],
            "company_name": row.get(
                "company_name"
            ),
            "section": "Item 7",
            "section_code": MAIN_SECTION,
            "extraction_status": row.get(
                f"{MAIN_SECTION}_status"
            ),
            "general_tone_status": "not_processed",
            "total_words": None,
            "positive_count": None,
            "negative_count": None,
            "positive_tone": None,
            "negative_tone": None,
            "net_tone": None,
        }

        # Only use sections successfully extracted by V3.
        if str(
            row.get(
                f"{MAIN_SECTION}_status"
            )
        ) != "success":

            result[
                "general_tone_status"
            ] = "excluded_extraction_failed"

            rows.append(result)
            continue

        path = get_section_file(row)

        if path is None:

            result[
                "general_tone_status"
            ] = "file_missing"

            rows.append(result)
            continue

        text = path.read_text(
            encoding="utf-8",
            errors="replace",
        )

        metrics = count_general_tone(
            text,
            dictionary,
        )

        result.update(metrics)

        result[
            "general_tone_status"
        ] = "success"

        rows.append(result)

        if (i + 1) % 100 == 0:
            print(
                f"Processed {i + 1}/"
                f"{len(df)}"
            )

    out = pd.DataFrame(rows)

    OUTPUT.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    out.to_csv(
        OUTPUT,
        index=False,
        encoding="utf-8-sig",
    )

    # ========================================================
    # SUMMARY
    # ========================================================

    success = (
        out["general_tone_status"]
        == "success"
    )

    print()
    print("=" * 70)
    print("GENERAL TONE COMPLETE")
    print("=" * 70)

    print(
        "Total filings:",
        len(out),
    )

    print(
        "Usable Item 7:",
        int(success.sum()),
    )

    print(
        "Excluded:",
        int((~success).sum()),
    )

    if success.any():

        print(
            "Total words:",
            f"{out.loc[success, 'total_words'].sum():,.0f}",
        )

        print(
            "Mean positive tone:",
            f"{out.loc[success, 'positive_tone'].mean():.6f}",
        )

        print(
            "Mean negative tone:",
            f"{out.loc[success, 'negative_tone'].mean():.6f}",
        )

        print(
            "Mean net tone:",
            f"{out.loc[success, 'net_tone'].mean():.6f}",
        )

    print()
    print("Output:", OUTPUT)


if __name__ == "__main__":
    main()
