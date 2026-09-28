from pathlib import Path
import shutil
import pandas as pd


V1_METADATA = Path("data/metadata/sections_10k.csv")
V22_METADATA = Path("data/metadata/sections_10k_v2.csv")

V3_METADATA = Path("data/metadata/sections_10k_v3.csv")
V3_SECTIONS_DIR = Path("data/sections_v3/10k")

KEYS = [
    "ticker",
    "filing_date",
    "accession_number",
]

SECTIONS = [
    "item_1a_risk_factors",
    "item_7_mda",
    "item_7a_market_risk",
]


def clean_path(value):
    if value is None or pd.isna(value):
        return None

    text = str(value).strip()

    if not text:
        return None

    return Path(text)


def source_row(v1, v22, key):
    a = v1[v1["_key"] == key]
    b = v22[v22["_key"] == key]

    row_v1 = a.iloc[0] if not a.empty else None
    row_v22 = b.iloc[0] if not b.empty else None

    return row_v1, row_v22


def status_is_success(row, section):
    if row is None:
        return False

    return str(
        row.get(f"{section}_status", "")
    ).strip().lower() == "success"


def choose_source(row_v1, row_v22, section):
    """
    Conservative rule:
      1. V1 success -> keep V1
      2. Otherwise, V2.2 success -> rescue with V2.2
      3. Otherwise -> no usable section
    """

    if status_is_success(row_v1, section):
        return row_v1, "v1_success_kept"

    if status_is_success(row_v22, section):
        return row_v22, "v2_2_rescue"

    if row_v1 is not None:
        return row_v1, "v1_failed_v2_2_failed"

    if row_v22 is not None:
        return row_v22, "v2_2_only"

    return None, "missing_both"


def main():

    print("=" * 70)
    print("SECTION EXTRACTION V3")
    print("V1 primary + V2.2 rescue")
    print("=" * 70)

    if not V1_METADATA.exists():
        raise FileNotFoundError(
            f"Missing: {V1_METADATA}"
        )

    if not V22_METADATA.exists():
        raise FileNotFoundError(
            f"Missing: {V22_METADATA}"
        )

    v1 = pd.read_csv(
        V1_METADATA,
        dtype={"accession_number": str},
    )

    v22 = pd.read_csv(
        V22_METADATA,
        dtype={"accession_number": str},
    )

    def make_key(df):
        return (
            df["ticker"].astype(str).str.upper()
            + "|"
            + df["filing_date"].astype(str)
            + "|"
            + df["accession_number"].astype(str).str.replace(
                ".0", "", regex=False
            )
        )

    v1["_key"] = make_key(v1)
    v22["_key"] = make_key(v22)

    if len(v1) != 1000 or len(v22) != 1000:
        print(
            f"WARNING: V1={len(v1)} rows, V2.2={len(v22)} rows"
        )

    V3_SECTIONS_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    results = []

    for idx, (_, base) in enumerate(
        v1.iterrows(),
        start=1,
    ):

        key = base["_key"]

        row_v1, row_v22 = source_row(
            v1,
            v22,
            key,
        )

        result = base.drop(
            labels=["_key"]
        ).to_dict()

        result["v3_status"] = "ok"
        result["v3_error"] = ""

        ticker = str(
            base["ticker"]
        ).upper()

        accession = str(
            base["accession_number"]
        ).replace(".0", "")

        for section in SECTIONS:

            selected, reason = choose_source(
                row_v1,
                row_v22,
                section,
            )

            result[f"{section}_source"] = reason
            result[f"{section}_v1_status"] = (
                row_v1.get(
                    f"{section}_status",
                    ""
                )
                if row_v1 is not None
                else ""
            )
            result[f"{section}_v2_2_status"] = (
                row_v22.get(
                    f"{section}_status",
                    ""
                )
                if row_v22 is not None
                else ""
            )

            if selected is None:
                result[f"{section}_status"] = "missing"
                result[f"{section}_words"] = 0
                result[f"{section}_chars"] = 0
                result[f"{section}_file"] = ""
                continue

            # Copy all standard section metadata from selected source.
            for suffix in [
                "status",
                "start_line",
                "end_line",
                "words",
                "chars",
                "method",
                "boundary_method",
                "score",
            ]:
                col = f"{section}_{suffix}"

                if col in selected.index:
                    result[col] = selected[col]

            src_file = clean_path(
                selected.get(
                    f"{section}_file",
                    ""
                )
            )

            if (
                str(
                    result.get(
                        f"{section}_status",
                        ""
                    )
                ) == "success"
                and src_file is not None
                and src_file.exists()
            ):

                out_dir = (
                    V3_SECTIONS_DIR
                    / ticker
                    / accession
                )

                out_dir.mkdir(
                    parents=True,
                    exist_ok=True,
                )

                out_file = (
                    out_dir
                    / f"{section}.txt"
                )

                shutil.copy2(
                    src_file,
                    out_file,
                )

                result[
                    f"{section}_file"
                ] = str(out_file)

            elif str(
                result.get(
                    f"{section}_status",
                    ""
                )
            ) == "success":

                # Metadata says success but source file is missing.
                result[
                    f"{section}_status"
                ] = "file_missing"

                result[
                    f"{section}_file"
                ] = ""

        results.append(result)

        if idx % 100 == 0:
            print(
                f"Processed {idx}/"
                f"{len(v1)}"
            )

    out = pd.DataFrame(results)

    # --------------------------------------------------------
    # Summary
    # --------------------------------------------------------

    print()
    print("=" * 70)
    print("V3 SUMMARY")
    print("=" * 70)

    print(
        f"Filings: {len(out)}"
    )

    for section in SECTIONS:

        status_col = f"{section}_status"
        source_col = f"{section}_source"

        print()
        print(section)

        print(
            "  success :",
            int(
                (
                    out[status_col]
                    == "success"
                ).sum()
            ),
        )

        print(
            "  failed  :",
            int(
                (
                    out[status_col]
                    != "success"
                ).sum()
            ),
        )

        print(
            "  V1 kept :",
            int(
                (
                    out[source_col]
                    == "v1_success_kept"
                ).sum()
            ),
        )

        print(
            "  rescued :",
            int(
                (
                    out[source_col]
                    == "v2_2_rescue"
                ).sum()
            ),
        )

        print(
            "  unresolved:",
            int(
                (
                    out[source_col]
                    == "v1_failed_v2_2_failed"
                ).sum()
            ),
        )

        print()
        print(
            out[source_col]
            .value_counts()
            .to_string()
        )

    # --------------------------------------------------------
    # Save
    # --------------------------------------------------------

    V3_METADATA.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    out.to_csv(
        V3_METADATA,
        index=False,
        encoding="utf-8-sig",
    )

    print()
    print("=" * 70)
    print("V3 COMPLETE")
    print("=" * 70)
    print(
        "Metadata:",
        V3_METADATA,
    )
    print(
        "Sections:",
        V3_SECTIONS_DIR,
    )


if __name__ == "__main__":
    main()
