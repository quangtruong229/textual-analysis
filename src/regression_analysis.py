#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
CROSS-SECTIONAL REGRESSION — C1 / C3 / C4
==========================================

Input
-----
data/metadata/tone_method_item7.csv
data/metadata/event_study_final/event_filing_results.csv

Models
------
C1:
    CAR_i = a + b * LM_NetTone_i + e_i

C3:
    CAR_i = a + b * LM_Positive_i + c * LM_Negative_i + e_i

C4:
    CAR_i = a + b * LM_NetTone_i + c * Harvard_NetTone_i + e_i

The script runs both proportional and TF-IDF tone measures where
the corresponding columns exist.

Standard errors
---------------
- HC3 heteroskedasticity-robust
- Firm-clustered by ticker (when feasible)

Optional controls
-----------------
If Size, BM, Volatility, Turnover are already present in the merged
data, the script will additionally estimate control models.
It will NOT fabricate missing controls.
"""

from __future__ import annotations

from pathlib import Path
import re
import sys

import numpy as np
import pandas as pd
import statsmodels.api as sm


# ============================================================
# PATHS
# ============================================================

ROOT = Path(".")
TONE_PATH = ROOT / "data" / "metadata" / "tone_method_item7.csv"
EVENT_PATH = (
    ROOT
    / "data"
    / "metadata"
    / "event_study_final"
    / "event_filing_results.csv"
)

OUT_DIR = ROOT / "data" / "metadata" / "regression_analysis"

RESULT_PATH = OUT_DIR / "regression_results.csv"
SAMPLE_PATH = OUT_DIR / "regression_sample.csv"
DESC_PATH = OUT_DIR / "regression_descriptives.csv"


# ============================================================
# HELPERS
# ============================================================

def norm_col(x: str) -> str:
    """Normalize column names for robust matching."""
    s = str(x).strip().lower()
    s = s.replace("%", "pct")
    s = re.sub(r"[^a-z0-9]+", "_", s)
    s = re.sub(r"_+", "_", s).strip("_")
    return s


def canonicalize_columns(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    out.columns = [norm_col(c) for c in out.columns]
    return out


def find_col(
    df: pd.DataFrame,
    candidates: list[str],
    required: bool = True,
) -> str | None:
    cols = set(df.columns)

    for c in candidates:
        c2 = norm_col(c)
        if c2 in cols:
            return c2

    if required:
        raise KeyError(
            f"Không tìm thấy cột. Candidates={candidates}. "
            f"Các cột hiện có: {list(df.columns)}"
        )

    return None


def parse_numeric(series: pd.Series) -> pd.Series:
    return pd.to_numeric(series, errors="coerce")


def one_sided_p_positive(coef: float, p_two_sided: float) -> float:
    """
    H1: coefficient > 0
    Convert two-sided p-value to one-sided p-value.
    """
    if not np.isfinite(coef) or not np.isfinite(p_two_sided):
        return np.nan

    if coef > 0:
        return p_two_sided / 2.0

    return 1.0 - p_two_sided / 2.0


def fit_ols(
    df: pd.DataFrame,
    y_col: str,
    x_cols: list[str],
    model_name: str,
) -> list[dict]:

    cols = [y_col] + x_cols + ["ticker"]
    work = df[cols].copy()

    for c in [y_col] + x_cols:
        work[c] = parse_numeric(work[c])

    work = work.dropna(subset=[y_col] + x_cols).copy()

    if work.empty:
        return [{
            "model": model_name,
            "dependent_variable": y_col,
            "n": 0,
            "r_squared": np.nan,
            "adj_r_squared": np.nan,
            "term": "__MODEL_FAILED__",
            "coefficient": np.nan,
            "se_hc3": np.nan,
            "t_hc3": np.nan,
            "p_hc3_two_sided": np.nan,
            "p_hc3_one_sided_positive": np.nan,
            "se_cluster": np.nan,
            "t_cluster": np.nan,
            "p_cluster_two_sided": np.nan,
            "p_cluster_one_sided_positive": np.nan,
            "n_firms": 0,
            "error": "No complete observations",
        }]

    y = work[y_col].astype(float)
    X = work[x_cols].astype(float)
    X = sm.add_constant(X, has_constant="add")

    # OLS
    model = sm.OLS(y, X, missing="drop").fit()

    # HC3
    hc3 = model.get_robustcov_results(cov_type="HC3")

    # Firm-clustered
    cluster_res = None
    n_firms = work["ticker"].nunique()

    if n_firms >= 20:
        try:
            cluster_res = model.get_robustcov_results(
                cov_type="cluster",
                groups=work["ticker"],
            )
        except Exception:
            cluster_res = None

    rows = []

    for term in X.columns:
        coef = float(model.params[term])

        hc3_se = float(hc3.bse[hc3.model.exog_names.index(term)])
        hc3_t = float(hc3.tvalues[hc3.model.exog_names.index(term)])
        hc3_p = float(hc3.pvalues[hc3.model.exog_names.index(term)])

        if cluster_res is not None:
            idx = cluster_res.model.exog_names.index(term)
            cl_se = float(cluster_res.bse[idx])
            cl_t = float(cluster_res.tvalues[idx])
            cl_p = float(cluster_res.pvalues[idx])
        else:
            cl_se = np.nan
            cl_t = np.nan
            cl_p = np.nan

        rows.append({
            "model": model_name,
            "dependent_variable": y_col,
            "n": int(model.nobs),
            "r_squared": float(model.rsquared),
            "adj_r_squared": float(model.rsquared_adj),
            "term": term,
            "coefficient": coef,
            "se_hc3": hc3_se,
            "t_hc3": hc3_t,
            "p_hc3_two_sided": hc3_p,
            "p_hc3_one_sided_positive": one_sided_p_positive(
                coef, hc3_p
            ),
            "se_cluster": cl_se,
            "t_cluster": cl_t,
            "p_cluster_two_sided": cl_p,
            "p_cluster_one_sided_positive": one_sided_p_positive(
                coef, cl_p
            ),
            "n_firms": int(n_firms),
            "error": "",
        })

    return rows


# ============================================================
# LOAD
# ============================================================

def main() -> int:

    print("=" * 80)
    print("CROSS-SECTIONAL REGRESSION — C1 / C3 / C4")
    print("=" * 80)

    if not TONE_PATH.exists():
        print(f"ERROR: Không tìm thấy {TONE_PATH}")
        return 1

    if not EVENT_PATH.exists():
        print(f"ERROR: Không tìm thấy {EVENT_PATH}")
        return 1

    OUT_DIR.mkdir(parents=True, exist_ok=True)

    print(f"Tone input : {TONE_PATH}")
    print(f"Event input: {EVENT_PATH}")

    tone = pd.read_csv(TONE_PATH)
    event = pd.read_csv(EVENT_PATH)

    tone = canonicalize_columns(tone)
    event = canonicalize_columns(event)

    print(f"Tone rows : {len(tone)}")
    print(f"Event rows: {len(event)}")

    # ========================================================
    # IDENTIFY KEYS
    # ========================================================

    tone_ticker = find_col(
        tone,
        ["ticker", "symbol", "stock_ticker"]
    )
    tone_date = find_col(
        tone,
        ["filing_date", "date", "event_date"]
    )

    event_ticker = find_col(
        event,
        ["ticker", "symbol", "stock_ticker"]
    )
    event_date = find_col(
        event,
        ["filing_date", "event_date", "date"]
    )

    tone[tone_ticker] = (
        tone[tone_ticker].astype(str).str.upper().str.strip()
    )
    event[event_ticker] = (
        event[event_ticker].astype(str).str.upper().str.strip()
    )

    tone["merge_ticker"] = tone[tone_ticker]

    event["merge_ticker"] = event[event_ticker]

    tone["merge_date"] = pd.to_datetime(
        tone[tone_date],
        errors="coerce",
    ).dt.strftime("%Y-%m-%d")

    event["merge_date"] = pd.to_datetime(
        event[event_date],
        errors="coerce",
    ).dt.strftime("%Y-%m-%d")

    # ========================================================
    # IDENTIFY TONE COLUMNS
    # ========================================================

    tone_map = {
        "lm_positive_prop": find_col(
            tone,
            [
                "lm_positive_prop",
                "positive_prop_lm",
                "lm_pos_prop",
            ],
            required=False,
        ),
        "lm_negative_prop": find_col(
            tone,
            [
                "lm_negative_prop",
                "negative_prop_lm",
                "lm_neg_prop",
            ],
            required=False,
        ),
        "lm_net_prop": find_col(
            tone,
            [
                "lm_net_prop",
                "net_prop_lm",
                "lm_net_tone",
            ],
            required=False,
        ),
        "lm_positive_tfidf": find_col(
            tone,
            [
                "lm_positive_tfidf",
                "positive_tfidf_lm",
            ],
            required=False,
        ),
        "lm_negative_tfidf": find_col(
            tone,
            [
                "lm_negative_tfidf",
                "negative_tfidf_lm",
            ],
            required=False,
        ),
        "lm_net_tfidf": find_col(
            tone,
            [
                "lm_net_tfidf",
                "net_tfidf_lm",
            ],
            required=False,
        ),
        "lm_net_ratio": find_col(
            tone,
            [
                "lm_net_ratio",
                "net_ratio_lm",
            ],
            required=False,
        ),
        "harvard_positive_prop": find_col(
            tone,
            [
                "harvard_positive_prop",
                "h_positive_prop",
                "general_positive_prop",
                "harvard_pos_prop",
            ],
            required=False,
        ),
        "harvard_negative_prop": find_col(
            tone,
            [
                "harvard_negative_prop",
                "h_negative_prop",
                "general_negative_prop",
                "harvard_neg_prop",
            ],
            required=False,
        ),
        "harvard_net_prop": find_col(
            tone,
            [
                "harvard_net_prop",
                "h_net_prop",
                "general_net_prop",
                "harvard_net_tone",
            ],
            required=False,
        ),
        "harvard_positive_tfidf": find_col(
            tone,
            [
                "harvard_positive_tfidf",
                "h_positive_tfidf",
                "general_positive_tfidf",
            ],
            required=False,
        ),
        "harvard_negative_tfidf": find_col(
            tone,
            [
                "harvard_negative_tfidf",
                "h_negative_tfidf",
                "general_negative_tfidf",
            ],
            required=False,
        ),
        "harvard_net_tfidf": find_col(
            tone,
            [
                "harvard_net_tfidf",
                "h_net_tfidf",
                "general_net_tfidf",
            ],
            required=False,
        ),
    }

    print("\nTone columns detected:")
    for k, v in tone_map.items():
        print(f"  {k:<28} -> {v}")

    # ========================================================
    # IDENTIFY CAR COLUMNS
    # ========================================================

    car_candidates = {
        "CAR_m1_p1": [
            "car_m1_p1",
            "car_-1_1",
            "car_m1p1",
        ],
        "CAR_0_p3": [
            "car_0_p3",
            "car_0_3",
            "car_0p3",
        ],
        "CAR_m3_p3": [
            "car_m3_p3",
            "car_-3_3",
            "car_m3p3",
        ],
        "CAR_m5_p5": [
            "car_m5_p5",
            "car_-5_5",
            "car_m5p5",
        ],
    }

    car_map = {}

    for display_name, candidates in car_candidates.items():
        found = find_col(
            event,
            candidates,
            required=False,
        )

        if found is None:
            # Generic fallback: search for substring
            for c in event.columns:
                nc = norm_col(c)
                if (
                    "car" in nc
                    and display_name.lower().replace("_", "") in nc.replace("_", "")
                ):
                    found = c
                    break

        car_map[display_name] = found

    print("\nCAR columns detected:")
    for k, v in car_map.items():
        print(f"  {k:<15} -> {v}")

    usable_car_cols = [
        c for c in car_map.values()
        if c is not None
    ]

    if not usable_car_cols:
        print("\nERROR: Không tìm thấy cột CAR trong event_filing_results.csv")
        print("Các cột event hiện có:")
        print(list(event.columns))
        return 1

    # ========================================================
    # MERGE
    # ========================================================

    tone_keep = [
        "merge_ticker",
        "merge_date",
    ]

    tone_keep += [
        c for c in tone_map.values()
        if c is not None
    ]

    # optional controls if already present
    control_aliases = {
        "size": ["size", "log_market_cap", "ln_market_cap"],
        "bm": ["bm", "book_to_market", "book_market"],
        "volatility": ["volatility", "vol", "idiosyncratic_volatility"],
        "turnover": ["turnover", "ln_turnover"],
    }

    control_map = {}

    for name, candidates in control_aliases.items():
        control_map[name] = find_col(
            tone,
            candidates,
            required=False,
        )

    # Also search in event file if not available in tone
    for name, candidates in control_aliases.items():
        if control_map[name] is None:
            control_map[name] = find_col(
                event,
                candidates,
                required=False,
            )

    print("\nControl columns detected:")
    for k, v in control_map.items():
        print(f"  {k:<12} -> {v}")

    event_keep = [
        "merge_ticker",
        "merge_date",
    ] + usable_car_cols

    # avoid duplicated key rows before merge
    event_small = event[event_keep].copy()

    # If duplicated, retain first exact key row
    event_small = event_small.drop_duplicates(
        subset=["merge_ticker", "merge_date"],
        keep="first",
    )

    merged = tone[tone_keep].merge(
        event_small,
        on=["merge_ticker", "merge_date"],
        how="inner",
        validate="one_to_one",
    )

    # Attach controls from event if needed
    for name, col in control_map.items():
        if col is not None and col not in merged.columns:
            if col in event.columns:
                tmp = event[
                    ["merge_ticker", "merge_date", col]
                ].drop_duplicates(
                    ["merge_ticker", "merge_date"]
                )
                merged = merged.merge(
                    tmp,
                    on=["merge_ticker", "merge_date"],
                    how="left",
                )

    merged = merged.rename(
        columns={
            "merge_ticker": "ticker",
            "merge_date": "filing_date",
        }
    )

    print("\nMERGE RESULT")
    print(f"Matched observations: {len(merged)}")
    print(f"Unique firms         : {merged['ticker'].nunique()}")

    if len(merged) == 0:
        print("\nERROR: Không có quan sát sau merge.")
        print("Kiểm tra ticker / filing_date giữa hai file.")
        return 1

    # ========================================================
    # SAVE MERGED SAMPLE
    # ========================================================

    merged.to_csv(
        SAMPLE_PATH,
        index=False,
        encoding="utf-8-sig",
    )

    # ========================================================
    # REGRESSIONS
    # ========================================================

    results: list[dict] = []

    # ---------------------------------
    # CAR windows
    # ---------------------------------

    car_windows = [
        ("CAR_m1_p1", car_map.get("CAR_m1_p1")),
        ("CAR_0_p3", car_map.get("CAR_0_p3")),
        ("CAR_m3_p3", car_map.get("CAR_m3_p3")),
        ("CAR_m5_p5", car_map.get("CAR_m5_p5")),
    ]

    # ========================================================
    # C1 — single-score regressions
    # ========================================================

    c1_scores = [
        ("LM_NetProp", tone_map.get("lm_net_prop")),
        ("LM_NetRatio", tone_map.get("lm_net_ratio")),
        ("LM_NetTFIDF", tone_map.get("lm_net_tfidf")),
        ("Harvard_NetProp", tone_map.get("harvard_net_prop")),
        ("Harvard_NetTFIDF", tone_map.get("harvard_net_tfidf")),
    ]

    print("\n" + "=" * 80)
    print("C1 — SCORE REGRESSIONS")
    print("=" * 80)

    for window_name, y_col in car_windows:

        if y_col is None:
            continue

        for score_name, x_col in c1_scores:

            if x_col is None or x_col not in merged.columns:
                continue

            model_name = f"C1_{window_name}_{score_name}"

            rows = fit_ols(
                merged,
                y_col=y_col,
                x_cols=[x_col],
                model_name=model_name,
            )

            for r in rows:
                r["section"] = "C1"
                r["score_definition"] = score_name

            results.extend(rows)

            print(
                f"  {model_name:<40} "
                f"N={rows[0]['n']:<4} "
                f"coef={rows[1]['coefficient'] if len(rows)>1 else np.nan:.6f} "
                f"p={rows[1]['p_hc3_two_sided'] if len(rows)>1 else np.nan:.6g}"
            )

    # ========================================================
    # C3 — positive + negative simultaneously
    # ========================================================

    lp = tone_map.get("lm_positive_prop")
    ln = tone_map.get("lm_negative_prop")

    print("\n" + "=" * 80)
    print("C3 — POSITIVE + NEGATIVE SIMULTANEOUSLY")
    print("=" * 80)

    if lp is not None and ln is not None:

        for window_name, y_col in car_windows:

            if y_col is None:
                continue

            model_name = f"C3_{window_name}_LM_PosNeg"

            rows = fit_ols(
                merged,
                y_col=y_col,
                x_cols=[lp, ln],
                model_name=model_name,
            )

            for r in rows:
                r["section"] = "C3"
                r["score_definition"] = "LM_PosProp_And_NegProp"

            results.extend(rows)

            print(f"  {model_name}")

    else:
        print(
            "  SKIP: thiếu LM positive/negative proportional columns."
        )

    # ========================================================
    # C4 — LM + Harvard
    # ========================================================

    lmp = tone_map.get("lm_net_prop")
    hvp = tone_map.get("harvard_net_prop")

    print("\n" + "=" * 80)
    print("C4 — LM VS HARVARD")
    print("=" * 80)

    if lmp is not None and hvp is not None:

        for window_name, y_col in car_windows:

            if y_col is None:
                continue

            model_name = f"C4_{window_name}_LM_vs_Harvard_Prop"

            rows = fit_ols(
                merged,
                y_col=y_col,
                x_cols=[lmp, hvp],
                model_name=model_name,
            )

            for r in rows:
                r["section"] = "C4"
                r["score_definition"] = "LM_NetProp_And_Harvard_NetProp"

            results.extend(rows)

            print(f"  {model_name}")

    else:
        print(
            "  SKIP: thiếu LM net prop hoặc Harvard net prop."
        )

    # TF-IDF version of C4
    lmt = tone_map.get("lm_net_tfidf")
    hvt = tone_map.get("harvard_net_tfidf")

    if lmt is not None and hvt is not None:

        for window_name, y_col in car_windows:

            if y_col is None:
                continue

            model_name = f"C4_{window_name}_LM_vs_Harvard_TFIDF"

            rows = fit_ols(
                merged,
                y_col=y_col,
                x_cols=[lmt, hvt],
                model_name=model_name,
            )

            for r in rows:
                r["section"] = "C4"
                r["score_definition"] = "LM_NetTFIDF_And_Harvard_NetTFIDF"

            results.extend(rows)

    # ========================================================
    # CONTROL MODELS
    # ========================================================

    available_controls = []

    for name, col in control_map.items():
        if col is not None and col in merged.columns:
            available_controls.append(col)

    print("\n" + "=" * 80)
    print("OPTIONAL CONTROL MODELS")
    print("=" * 80)

    if len(available_controls) == 4 and lmp is not None:
        print("All four controls detected. Running LM + controls.")

        for window_name, y_col in car_windows:

            if y_col is None:
                continue

            model_name = f"C2_{window_name}_LM_Controls"

            xcols = [lmp] + available_controls

            rows = fit_ols(
                merged,
                y_col=y_col,
                x_cols=xcols,
                model_name=model_name,
            )

            for r in rows:
                r["section"] = "C2"
                r["score_definition"] = "LM_NetProp_plus_Size_BM_Volatility_Turnover"

            results.extend(rows)

    else:
        print(
            "Controls chưa đầy đủ trong hai input files -> "
            "không chạy để tránh tạo control giả."
        )

    # ========================================================
    # SAVE RESULTS
    # ========================================================

    result_df = pd.DataFrame(results)

    # Stable column ordering
    preferred = [
        "section",
        "model",
        "score_definition",
        "dependent_variable",
        "term",
        "n",
        "n_firms",
        "coefficient",
        "se_hc3",
        "t_hc3",
        "p_hc3_two_sided",
        "p_hc3_one_sided_positive",
        "se_cluster",
        "t_cluster",
        "p_cluster_two_sided",
        "p_cluster_one_sided_positive",
        "r_squared",
        "adj_r_squared",
        "error",
    ]

    result_df = result_df[
        [c for c in preferred if c in result_df.columns]
    ]

    result_df.to_csv(
        RESULT_PATH,
        index=False,
        encoding="utf-8-sig",
    )

    # ========================================================
    # DESCRIPTIVES
    # ========================================================

    numeric_candidates = []

    for c in (
        list(tone_map.values())
        + usable_car_cols
    ):
        if c is not None and c in merged.columns:
            numeric_candidates.append(c)

    numeric_candidates = list(
        dict.fromkeys(numeric_candidates)
    )

    desc = merged[numeric_candidates].apply(
        pd.to_numeric,
        errors="coerce",
    ).describe().T

    desc["missing"] = merged[numeric_candidates].isna().sum()

    desc.to_csv(
        DESC_PATH,
        encoding="utf-8-sig",
    )

    # ========================================================
    # SUMMARY
    # ========================================================

    print("\n" + "=" * 80)
    print("REGRESSION COMPLETE")
    print("=" * 80)

    print(f"Matched sample       : {len(merged)}")
    print(f"Unique firms         : {merged['ticker'].nunique()}")
    print(f"Regression rows      : {len(result_df)}")

    print("\nOUTPUTS")
    print(RESULT_PATH)
    print(SAMPLE_PATH)
    print(DESC_PATH)

    # Print headline coefficients for C1/C3/C4
    headline = result_df[
        result_df["term"] != "const"
    ].copy()

    if not headline.empty:

        print("\nHEADLINE RESULTS — HC3")

        show_cols = [
            "model",
            "term",
            "n",
            "coefficient",
            "t_hc3",
            "p_hc3_two_sided",
            "r_squared",
        ]

        print(
            headline[show_cols]
            .to_string(index=False)
        )

    return 0


if __name__ == "__main__":
    sys.exit(main())
