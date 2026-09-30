"""Re-run the supplied event-study and regression code without overwriting inputs.

Tone is read from data/metadata/tone_method_item7.csv. The event study and
regressions are rebuilt from the stored input tables.
"""

from __future__ import annotations

import importlib.util
import argparse
from pathlib import Path
import shutil
import sys


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "analysis_outputs"


def load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main(force_event: bool = False) -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    event_dir = OUT / "event_study"
    regression_dir = OUT / "regression"
    event_dir.mkdir(parents=True, exist_ok=True)
    regression_dir.mkdir(parents=True, exist_ok=True)

    event = load("supplied_event_study", ROOT / "src" / "event_study_final.py")
    event.TONE_PATH = ROOT / "data/metadata/tone_method_item7.csv"
    event.PRICE_PATH = ROOT / "data/market_data/daily_prices.csv"
    event.OUT_DIR = event_dir
    event.FILING_OUT = event_dir / "event_filing_results.csv"
    event.AR_OUT = event_dir / "event_ar_long.csv"
    event.DAILY_OUT = event_dir / "event_daily_summary.csv"
    event.SUMMARY_OUT = event_dir / "event_study_summary.csv"
    if force_event or not event.FILING_OUT.exists():
        print("[1/2] Recomputing event study from supplied daily prices and tone rows...", flush=True)
        event.main()
        metadata_event_dir = ROOT / "data/metadata/event_study_final"
        metadata_event_dir.mkdir(parents=True, exist_ok=True)
        for name in ("event_filing_results.csv", "event_daily_summary.csv", "event_study_summary.csv"):
            shutil.copyfile(event_dir / name, metadata_event_dir / name)
    else:
        print("[1/2] Using existing recomputed event table; pass --force-event to recalculate.", flush=True)

    regression = load("supplied_regression", ROOT / "src" / "regression_analysis.py")
    regression.TONE_PATH = event.TONE_PATH
    regression.EVENT_PATH = event.FILING_OUT
    regression.OUT_DIR = regression_dir
    regression.RESULT_PATH = regression_dir / "regression_results.csv"
    regression.SAMPLE_PATH = regression_dir / "regression_sample.csv"
    regression.DESC_PATH = regression_dir / "regression_descriptives.csv"
    print("[2/2] Recomputing C1/C3/C4 regressions from event results...", flush=True)
    result = regression.main()
    if result not in (None, 0):
        raise RuntimeError(f"Regression exited with {result}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--force-event", action="store_true", help="Recompute the event study even if outputs exist")
    main(force_event=parser.parse_args().force_event)
