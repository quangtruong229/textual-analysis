"""Export the same detailed results text shown by the local app."""

from pathlib import Path
import sys

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from presentation import results_markdown  # noqa: E402


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    out = ROOT / "analysis_outputs"
    text = results_markdown(
        pd.read_csv(out / "tone_firm_year.csv"),
        pd.read_csv(out / "dictionary_comparison_summary.csv").iloc[0],
        pd.read_csv(out / "event_study/event_study_summary.csv"),
        pd.read_csv(out / "regression/regression_results.csv"),
        pd.read_csv(out / "c2_reduced_results.csv"),
        pd.read_csv(out / "event_study/event_daily_summary.csv"),
        pd.read_csv(out / "event_study/extended_window_tests.csv"),
        pd.read_csv(out / "word_power/regression_results.csv"),
    )
    target = out / "RESULTS_PRESENTATION.md"
    target.write_text(text, encoding="utf-8")
    print(f"Saved {target} ({len(text)} characters)")


if __name__ == "__main__":
    main()
