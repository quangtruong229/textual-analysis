"""Rebuild all calculated outputs from the supplied tone, price and control CSVs.

Tone starts from data/metadata/tone_method_item7.csv. Run from any working
directory with the same Python environment.
"""

from __future__ import annotations

import argparse
from pathlib import Path
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reuse-event", action="store_true",
                        help="Use existing event CSVs; default recalculates from daily prices")
    args = parser.parse_args()
    reuse_event = args.reuse_event and (ROOT / "analysis_outputs/event_study/estimation_ar_long.csv").exists()
    steps = [
        ("recompute_from_supplied.py", [] if reuse_event else ["--force-event"]),
        ("extended_event_tests.py", []),
        ("calculate_c2_controls.py", []),
        ("build_firm_year_panel.py", []),
        ("optional_robustness.py", []),
        ("calculate_full_controls.py", []),
        ("calculate_word_power.py", []),
        ("verify_word_power.py", []),
        ("summarize_dictionary_comparison.py", []),
        ("export_presentation.py", []),
        ("verify_recalculation.py", []),
        ("validate_handoff.py", []),
    ]
    for name, options in steps:
        print(f"Running {name}", flush=True)
        subprocess.run([sys.executable, str(SCRIPTS / name), *options],
                       cwd=ROOT, check=True)
    print("All calculated outputs and audit checks completed.")


if __name__ == "__main__":
    main()
