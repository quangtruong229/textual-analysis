from pathlib import Path
import re
from collections import Counter

import pandas as pd


V3_METADATA = Path("data/metadata/sections_10k_v3.csv")
SECTION_DIR = Path("data/sections_v3/10k")
DICTIONARY_DIR = Path("data/dictionary")

OUTPUT_WIDE = Path("data/metadata/lm_tone.csv")
OUTPUT_LONG = Path("data/metadata/lm_tone_long.csv")

SECTIONS = {
    "item_1a_risk_factors": "Item 1A",
    "item_7_mda": "Item 7",
    "item_7a_market_risk": "Item 7A",
}

WORD_RE = re.compile(r"[A-Za-z]+(?:[-'][A-Za-z]+)*")


def find_dictionary():
    files = list(DICTIONARY_DIR.glob("Loughran-McDonald*.xlsx"))
    if not files:
        files = list(DICTIONARY_DIR.glob("Loughran-McDonald*.csv"))

    if not files:
        raise FileNotFoundError(
            "Không tìm thấy Loughran-McDonald dictionary trong data/dictionary/"
        )

    return files[0]


def load_dictionary(path):
    print("=" * 70)
    print("LOAD LOUGHRAN-MCDONALD DICTIONARY")
    print("=" * 70)
    print("File:", path)

    if path.suffix.lower() == ".xlsx":
        df = pd.read_excel(path)
    else:
        df = pd.read_csv(path)

    df.columns = [str(c).strip() for c in df.columns]

    word_col = next(
        (c for c in df.columns if c.lower() == "word"),
        df.columns[0],
    )

    needed = {}
    lower_cols = {c.lower(): c for c in df.columns}

    for name in ["negative", "positive", "uncertainty"]:
        if name not in lower_cols:
            raise ValueError(
                f"Missing dictionary column: {name}\n"
                f"Available: {list(df.columns)}"
            )
        needed[name] = lower_cols[name]

    df["_WORD"] = (
        df[word_col]
        .astype(str)
        .str.strip()
        .str.upper()
    )

    result = {}

    for name, col in needed.items():
        values = pd.to_numeric(df[col], errors="coerce").fillna(0)
        result[name] = set(
            df.loc[values > 0, "_WORD"]
        )

    print("Rows:", len(df))
    print("Negative:", len(result["negative"]))
    print("Positive:", len(result["positive"]))
    print("Uncertainty:", len(result["uncertainty"]))

    return result


def tokenize(text):
    return [
        x.upper()
        for x in WORD_RE.findall(str(text))
    ]


def count_tone(text, dictionary):
    tokens = tokenize(text)
    counts = Counter(tokens)

    total_words = len(tokens)

    positive = sum(
        counts[w]
        for w in counts
        if w in dictionary["positive"]
    )

    negative = sum(
        counts[w]
        for w in counts
        if w in dictionary["negative"]
    )

    uncertainty = sum(
        counts[w]
        for w in counts
        if w in dictionary["uncertainty"]
    )

    positive_tone = (
        positive / total_words
        if total_words else None
    )

    negative_tone = (
        negative / total_words
        if total_words else None
    )

    uncertainty_tone = (
        uncertainty / total_words
        if total_words else None
    )

    net_tone = (
        positive_tone - negative_tone
        if positive_tone is not None
        and negative_tone is not None
        else None
    )

    return {
        "total_words": total_words,
        "positive_count": positive,
        "negative_count": negative,
        "uncertainty_count": uncertainty,
        "positive_tone": positive_tone,
        "negative_tone": negative_tone,
        "uncertainty_tone": uncertainty_tone,
        "net_tone": net_tone,
    }


def get_section_file(row, section):
    ticker = str(row["ticker"]).upper()
    accession = str(row["accession_number"]).strip()

    path = (
        SECTION_DIR
        / ticker
        / accession
        / f"{section}.txt"
    )

    return path if path.exists() else None


def main():
    if not V3_METADATA.exists():
        raise FileNotFoundError(
            f"Không tìm thấy {V3_METADATA}"
        )

    dictionary = load_dictionary(
        find_dictionary()
    )

    df = pd.read_csv(
        V3_METADATA,
        dtype={"accession_number": str},
    )

    print()
    print("=" * 70)
    print("BUILD LM TONE")
    print("=" * 70)
    print("Filings:", len(df))

    rows = []

    for i, row in df.iterrows():
        out = {
            "ticker": row["ticker"],
            "filing_date": row["filing_date"],
            "report_date": row.get("report_date"),
            "accession_number": row["accession_number"],
            "company_name": row.get("company_name"),
        }

        for section, label in SECTIONS.items():
            prefix = section + "_"

            extraction_status = str(
                row.get(
                    f"{prefix}status",
                    "missing",
                )
            )

            out[f"{prefix}extraction_status"] = extraction_status

            for metric in [
                "total_words",
                "positive_count",
                "negative_count",
                "uncertainty_count",
                "positive_tone",
                "negative_tone",
                "uncertainty_tone",
                "net_tone",
            ]:
                out[f"{prefix}{metric}"] = None

            out[f"{prefix}lm_status"] = "not_processed"

            if extraction_status != "success":
                out[f"{prefix}lm_status"] = (
                    "excluded_extraction_failed"
                )
                continue

            path = get_section_file(
                row,
                section,
            )

            if path is None:
                out[f"{prefix}lm_status"] = "file_missing"
                continue

            text = path.read_text(
                encoding="utf-8",
                errors="replace",
            )

            metrics = count_tone(
                text,
                dictionary,
            )

            for key, value in metrics.items():
                out[f"{prefix}{key}"] = value

            out[f"{prefix}lm_status"] = "success"
            out[f"{prefix}file"] = str(path)

        rows.append(out)

        if (i + 1) % 100 == 0:
            print(
                f"Processed {i + 1}/{len(df)}"
            )

    wide = pd.DataFrame(rows)

    # --------------------------------------------------------
    # LONG FORMAT
    # --------------------------------------------------------

    long_rows = []

    for _, row in wide.iterrows():
        for section, label in SECTIONS.items():
            prefix = section + "_"

            long_rows.append({
                "ticker": row["ticker"],
                "filing_date": row["filing_date"],
                "report_date": row.get("report_date"),
                "accession_number": row["accession_number"],
                "company_name": row.get("company_name"),
                "section": label,
                "section_code": section,
                "extraction_status": row[
                    f"{prefix}extraction_status"
                ],
                "lm_status": row[
                    f"{prefix}lm_status"
                ],
                "total_words": row[
                    f"{prefix}total_words"
                ],
                "positive_count": row[
                    f"{prefix}positive_count"
                ],
                "negative_count": row[
                    f"{prefix}negative_count"
                ],
                "uncertainty_count": row[
                    f"{prefix}uncertainty_count"
                ],
                "positive_tone": row[
                    f"{prefix}positive_tone"
                ],
                "negative_tone": row[
                    f"{prefix}negative_tone"
                ],
                "uncertainty_tone": row[
                    f"{prefix}uncertainty_tone"
                ],
                "net_tone": row[
                    f"{prefix}net_tone"
                ],
            })

    long = pd.DataFrame(long_rows)

    OUTPUT_WIDE.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    wide.to_csv(
        OUTPUT_WIDE,
        index=False,
        encoding="utf-8-sig",
    )

    long.to_csv(
        OUTPUT_LONG,
        index=False,
        encoding="utf-8-sig",
    )

    print()
    print("=" * 70)
    print("LM TONE COMPLETE")
    print("=" * 70)

    for section, label in SECTIONS.items():
        prefix = section + "_"

        mask = (
            wide[f"{prefix}lm_status"]
            == "success"
        )

        n = int(mask.sum())

        print()
        print(label)
        print("  LM success:", n)

        if n:
            print(
                "  Total words:",
                f"{wide.loc[mask, f'{prefix}total_words'].sum():,.0f}",
            )

            print(
                "  Mean positive tone:",
                f"{wide.loc[mask, f'{prefix}positive_tone'].mean():.6f}",
            )

            print(
                "  Mean negative tone:",
                f"{wide.loc[mask, f'{prefix}negative_tone'].mean():.6f}",
            )

            print(
                "  Mean uncertainty:",
                f"{wide.loc[mask, f'{prefix}uncertainty_tone'].mean():.6f}",
            )

            print(
                "  Mean net tone:",
                f"{wide.loc[mask, f'{prefix}net_tone'].mean():.6f}",
            )

    print()
    print("Wide :", OUTPUT_WIDE)
    print("Long :", OUTPUT_LONG)


if __name__ == "__main__":
    main()
