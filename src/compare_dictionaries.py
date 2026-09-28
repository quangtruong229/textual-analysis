from pathlib import Path
import pandas as pd


LM_PATH = Path(
    "data/metadata/lm_tone.csv"
)

GENERAL_PATH = Path(
    "data/metadata/general_tone.csv"
)

LM_DICT_PATH = Path(
    "data/dictionary/Loughran-McDonald_MasterDictionary_1993-2025.xlsx"
)

GENERAL_DICT_PATH = Path(
    "data/dictionary/HIV-4.csv"
)

OUTPUT = Path(
    "data/metadata/dictionary_comparison_item7.csv"
)


KEYS = [
    "ticker",
    "filing_date",
    "accession_number",
]


def safe_corr(a, b, method="pearson"):
    x = pd.to_numeric(a, errors="coerce")
    y = pd.to_numeric(b, errors="coerce")

    mask = x.notna() & y.notna()

    if mask.sum() < 3:
        return None

    x = x[mask]
    y = y[mask]

    if method == "spearman":
        # Spearman = Pearson correlation of ranks.
        return x.rank().corr(
            y.rank(),
            method="pearson",
        )

    return x.corr(
        y,
        method="pearson",
    )


def main():

    print("=" * 80)
    print("LM vs HARVARD-IV-4 — ITEM 7 COMPARISON")
    print("=" * 80)

    lm = pd.read_csv(
        LM_PATH,
        dtype={"accession_number": str},
    )

    general = pd.read_csv(
        GENERAL_PATH,
        dtype={"accession_number": str},
    )

    lm_keep = lm[
        KEYS + [
            "item_7_mda_lm_status",
            "item_7_mda_total_words",
            "item_7_mda_positive_count",
            "item_7_mda_negative_count",
            "item_7_mda_uncertainty_count",
            "item_7_mda_positive_tone",
            "item_7_mda_negative_tone",
            "item_7_mda_uncertainty_tone",
            "item_7_mda_net_tone",
        ]
    ].copy()

    gen_keep = general[
        KEYS + [
            "general_tone_status",
            "total_words",
            "positive_count",
            "negative_count",
            "positive_tone",
            "negative_tone",
            "net_tone",
        ]
    ].copy()

    merged = lm_keep.merge(
        gen_keep,
        on=KEYS,
        how="inner",
        suffixes=("_lm", "_harvard"),
    )

    usable = merged[
        merged["item_7_mda_lm_status"].eq("success")
        & merged["general_tone_status"].eq("success")
    ].copy()

    print()
    print("Total merged filings :", len(merged))
    print("Comparable filings   :", len(usable))

    # --------------------------------------------------------
    # Descriptive statistics
    # --------------------------------------------------------

    variables = [
        (
            "Positive",
            "item_7_mda_positive_tone",
            "positive_tone",
        ),
        (
            "Negative",
            "item_7_mda_negative_tone",
            "negative_tone",
        ),
        (
            "Net Tone",
            "item_7_mda_net_tone",
            "net_tone",
        ),
    ]

    print()
    print("-" * 80)
    print("MEAN / MEDIAN")
    print("-" * 80)

    rows = []

    for label, lm_col, h_col in variables:

        lm_x = pd.to_numeric(
            usable[lm_col],
            errors="coerce",
        )

        h_x = pd.to_numeric(
            usable[h_col],
            errors="coerce",
        )

        rows.append({
            "measure": label,
            "lm_mean": lm_x.mean(),
            "harvard_mean": h_x.mean(),
            "lm_median": lm_x.median(),
            "harvard_median": h_x.median(),
            "mean_difference_lm_minus_harvard": (
                lm_x - h_x
            ).mean(),
        })

    stats = pd.DataFrame(rows)

    print(
        stats.to_string(index=False)
    )

    # --------------------------------------------------------
    # Correlations
    # --------------------------------------------------------

    print()
    print("-" * 80)
    print("CORRELATIONS")
    print("-" * 80)

    corr_rows = []

    for label, lm_col, h_col in variables:

        corr_rows.append({
            "measure": label,
            "pearson": safe_corr(
                usable[lm_col],
                usable[h_col],
                "pearson",
            ),
            "spearman": safe_corr(
                usable[lm_col],
                usable[h_col],
                "spearman",
            ),
        })

    corr_df = pd.DataFrame(
        corr_rows
    )

    print(
        corr_df.to_string(index=False)
    )

    # --------------------------------------------------------
    # Direction disagreement
    # --------------------------------------------------------

    lm_net = pd.to_numeric(
        usable["item_7_mda_net_tone"],
        errors="coerce",
    )

    h_net = pd.to_numeric(
        usable["net_tone"],
        errors="coerce",
    )

    valid = (
        lm_net.notna()
        & h_net.notna()
    )

    same_sign = (
        ((lm_net >= 0) & (h_net >= 0))
        |
        ((lm_net < 0) & (h_net < 0))
    )

    opposite_sign = (
        ((lm_net >= 0) & (h_net < 0))
        |
        ((lm_net < 0) & (h_net >= 0))
    )

    zero_cases = (
        (lm_net == 0)
        |
        (h_net == 0)
    )

    print()
    print("-" * 80)
    print("NET TONE DIRECTION")
    print("-" * 80)

    print(
        "Comparable net-tone observations:",
        int(valid.sum()),
    )

    print(
        "Same sign:",
        int((same_sign & valid).sum()),
    )

    print(
        "Opposite sign:",
        int((opposite_sign & valid).sum()),
    )

    print(
        "At least one exactly zero:",
        int((zero_cases & valid).sum()),
    )

    # --------------------------------------------------------
    # Largest disagreements
    # --------------------------------------------------------

    usable["net_difference_abs"] = (
        (
            usable["item_7_mda_net_tone"]
            - usable["net_tone"]
        ).abs()
    )

    print()
    print("-" * 80)
    print("10 LARGEST NET-TONE DISAGREEMENTS")
    print("-" * 80)

    print(
        usable.sort_values(
            "net_difference_abs",
            ascending=False,
        )[
            KEYS
            + [
                "item_7_mda_net_tone",
                "net_tone",
                "net_difference_abs",
                "item_7_mda_positive_tone",
                "positive_tone",
                "item_7_mda_negative_tone",
                "negative_tone",
            ]
        ]
        .head(10)
        .to_string(index=False)
    )

    # --------------------------------------------------------
    # Dictionary word overlap
    # --------------------------------------------------------

    print()
    print("-" * 80)
    print("DICTIONARY WORD OVERLAP")
    print("-" * 80)

    lm_dict = pd.read_excel(
        LM_DICT_PATH
    )

    lm_dict["_WORD"] = (
        lm_dict["Word"]
        .astype(str)
        .str.strip()
        .str.upper()
    )

    lm_positive = set(
        lm_dict.loc[
            pd.to_numeric(
                lm_dict["Positive"],
                errors="coerce",
            ).fillna(0) > 0,
            "_WORD",
        ]
    )

    lm_negative = set(
        lm_dict.loc[
            pd.to_numeric(
                lm_dict["Negative"],
                errors="coerce",
            ).fillna(0) > 0,
            "_WORD",
        ]
    )

    h_dict = pd.read_csv(
        GENERAL_DICT_PATH,
        low_memory=False,
    )

    h_dict["_WORD"] = (
        h_dict["Entry"]
        .astype(str)
        .str.strip()
        .str.upper()
    )

    h_positive = set(
        h_dict.loc[
            h_dict["Positiv"].notna(),
            "_WORD",
        ]
    )

    h_negative = set(
        h_dict.loc[
            h_dict["Negativ"].notna(),
            "_WORD",
        ]
    )

    print(
        "LM Positive words     :",
        len(lm_positive),
    )

    print(
        "Harvard Positive words:",
        len(h_positive),
    )

    print(
        "LM Negative words     :",
        len(lm_negative),
    )

    print(
        "Harvard Negative words:",
        len(h_negative),
    )

    print()
    print(
        "Positive ∩ Positive:",
        len(lm_positive & h_positive),
    )

    print(
        "Negative ∩ Negative:",
        len(lm_negative & h_negative),
    )

    print(
        "Harvard Negative ∩ LM Positive:",
        len(h_negative & lm_positive),
    )

    print(
        "Harvard Positive ∩ LM Negative:",
        len(h_positive & lm_negative),
    )

    # --------------------------------------------------------
    # Save comparable dataset
    # --------------------------------------------------------

    OUTPUT.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    usable.to_csv(
        OUTPUT,
        index=False,
        encoding="utf-8-sig",
    )

    print()
    print("=" * 80)
    print("COMPARISON COMPLETE")
    print("=" * 80)
    print("Output:", OUTPUT)


if __name__ == "__main__":
    main()
