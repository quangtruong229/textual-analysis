from pathlib import Path
import pandas as pd


ROOT = Path(".")
CONTROL = ROOT / "data/metadata/controls/controls_item7_final6.csv"
TONE = ROOT / "data/metadata/tone_method_item7.csv"

OUT = ROOT / "data/metadata/controls/controls_item7_final7.csv"


def main():

    control = pd.read_csv(CONTROL)
    tone = pd.read_csv(TONE)

    tone = tone[
        [
            "ticker",
            "accession_number",
            "lm_word_power_positive",
            "lm_word_power_negative",
            "lm_word_power_net",
            "harvard_word_power_net"
        ]
    ]

    control["accession_number"] = (
        control["accession_number"]
        .astype(str)
        .str.replace("-", "", regex=False)
    )

    tone["accession_number"] = (
        tone["accession_number"]
        .astype(str)
        .str.replace("-", "", regex=False)
    )


    merged = control.merge(
        tone,
        on=["ticker", "accession_number"],
        how="left"
    )


    print("="*80)
    print("FINAL 7 CONTROL MERGE")
    print("="*80)

    print("rows:", len(merged))
    print(
        "word_power:",
        merged["lm_word_power_net"].notna().sum()
    )

    print(
        "complete:",
        merged.dropna(
            subset=[
                "lm_word_power_net"
            ]
        ).shape[0]
    )


    merged.to_csv(
        OUT,
        index=False,
        encoding="utf-8-sig"
    )


    print("saved:", OUT)


if __name__ == "__main__":
    main()