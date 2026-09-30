"""Reduced C2 regressions using four controls from controls_item7.csv.

Implements CAR ~ LM net proportional tone + Size + BM + Volatility + Turnover.
This implementation estimates the four-control specification.
No rows or coefficients are added to the original supplied tables.
"""

from __future__ import annotations

from pathlib import Path
import sys

import numpy as np
import pandas as pd
import statsmodels.api as sm


ROOT = Path(__file__).resolve().parents[1]
SAMPLE = ROOT / "analysis_outputs/regression/regression_sample.csv"
CONTROLS = ROOT / "data/metadata/controls/controls_item7.csv"
OUT = ROOT / "analysis_outputs"
WINDOWS = ("car_m1_p1", "car_0_p3", "car_m3_p3", "car_m5_p5")
PREDICTORS = ("lm_net_prop", "size", "bm", "volatility", "turnover")


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    sample = pd.read_csv(SAMPLE, dtype={"ticker": str, "filing_date": str})
    controls = pd.read_csv(CONTROLS, dtype={"ticker": str, "filing_date": str})
    sample["filing_date"] = sample["filing_date"].str[:10]
    controls["filing_date"] = pd.to_datetime(
        controls["filing_date"], format="%Y-%m-%d", errors="raise"
    ).dt.strftime("%Y-%m-%d")
    cols = ["ticker", "filing_date", "status", *PREDICTORS[1:]]
    if controls.duplicated(["ticker", "filing_date"]).any():
        raise ValueError("Duplicate control rows by ticker and filing date")
    merged = sample.merge(
        controls[cols], on=["ticker", "filing_date"], how="left", validate="one_to_one"
    )
    if merged.status.isna().any():
        raise ValueError("Some regression rows lack a matching control record")
    for col in (*PREDICTORS, *WINDOWS):
        merged[col] = pd.to_numeric(merged[col], errors="coerce")
    merged[list(PREDICTORS)] = merged[list(PREDICTORS)].replace(
        [np.inf, -np.inf], np.nan
    )

    frame = merged.loc[merged.status.eq("success")].dropna(
        subset=[*PREDICTORS, *WINDOWS]
    ).copy()
    if frame.ticker.nunique() < 5:
        raise ValueError("Too few firm clusters for C2")
    results = []
    for window in WINDOWS:
        x = sm.add_constant(frame[list(PREDICTORS)], has_constant="add")
        y = frame[window]
        model = sm.OLS(y, x)
        hc3 = model.fit(cov_type="HC3")
        clustered = model.fit(
            cov_type="cluster", cov_kwds={"groups": frame.ticker, "use_correction": True},
            use_t=True,
        )
        for term in hc3.params.index:
            ci = hc3.conf_int().loc[term]
            results.append({
                "model": "C2_reduced_LM_NetProp_4controls",
                "dependent_variable": window,
                "term": term,
                "n": int(hc3.nobs),
                "n_firms": int(frame.ticker.nunique()),
                "coefficient": float(hc3.params[term]),
                "se_hc3": float(hc3.bse[term]),
                "p_hc3_two_sided": float(hc3.pvalues[term]),
                "ci_hc3_low": float(ci.iloc[0]),
                "ci_hc3_high": float(ci.iloc[1]),
                "se_cluster": float(clustered.bse[term]),
                "p_cluster_two_sided": float(clustered.pvalues[term]),
                "r_squared": float(hc3.rsquared),
                "controls_omitted": "EADRet; Accruals",
            })
    OUT.mkdir(exist_ok=True)
    pd.DataFrame(results).to_csv(OUT / "c2_reduced_results.csv", index=False, encoding="utf-8-sig")
    frame[["ticker", "filing_date", *WINDOWS, *PREDICTORS]].to_csv(
        OUT / "c2_reduced_sample.csv", index=False, encoding="utf-8-sig"
    )
    print("Input tone/CAR observations:", len(sample))
    print("Matched control rows:", int(merged.status.notna().sum()))
    print("Complete-case C2 observations:", len(frame))
    print("Excluded for incomplete controls:", len(merged) - len(frame))
    print("Firms in C2:", frame.ticker.nunique())
    print("Model: CAR ~ LM_net_prop + Size + BM + Volatility + Turnover")
    print("EADRet and Accruals unavailable; this is reduced C2.")
    headline = pd.DataFrame(results).query("term == 'lm_net_prop'")
    print("\nTone coefficient by CAR window (HC3 and firm-clustered p-values):")
    print(headline[["dependent_variable", "coefficient", "p_hc3_two_sided", "p_cluster_two_sided", "n"]].to_string(index=False, float_format=lambda x: f"{x:.6f}"))
    print("\nSaved:", OUT / "c2_reduced_results.csv")
    print("Saved:", OUT / "c2_reduced_sample.csv")


if __name__ == "__main__":
    main()
