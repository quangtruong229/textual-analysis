#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Final regression/diagnostic module for the 10-K tone research.

Implements the requested quantitative framework:
C1: CAR = a + b Score + e                 (baseline)
C2: CAR = a + b Score + controls + e      (Size, BM, Volatility, Turnover)
C3: CAR = a + b Pos + c Neg + controls + e
C4: CAR = a + b Score_LM + c Score_Harvard + e, separately by scoring method

Diagnostics:
- Pearson correlation among regressors
- VIF for multicollinearity
- Breusch-Pagan and White tests for heteroskedasticity
- OLS conventional SE, HC3 robust SE, and firm-clustered SE
- Baseline vs controlled-model coefficient comparison
- One-sided directional p-values for H1 (beta_pos > 0) and H2 (gamma_neg < 0)

No causal language is produced by this script.
"""
from __future__ import annotations

import argparse
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd
import statsmodels.api as sm
from statsmodels.stats.diagnostic import het_breuschpagan, het_white
from statsmodels.stats.outliers_influence import variance_inflation_factor

ROOT = Path(__file__).resolve().parents[1]
TONE = ROOT / "data" / "metadata" / "tone_method_item7.csv"
EVENT = ROOT / "data" / "metadata" / "event_study_final" / "event_filing_results.csv"
CONTROL = ROOT / "data" / "metadata" / "controls" / "controls_item7.csv"
OUTDIR = ROOT / "data" / "metadata" / "regression_analysis"

CAR_WINDOWS = {
    "m1_p1": (-1, 1),
    "p0_p3": (0, 3),
    "m3_p3": (-3, 3),
    "m5_p5": (-5, 5),
}

SCORE_CANDIDATES = {
    "lm_positive_prop": ["lm_positive_prop", "lm_pos_prop", "positive_prop_lm", "lm_pos"],
    "lm_negative_prop": ["lm_negative_prop", "lm_neg_prop", "negative_prop_lm", "lm_neg"],
    "lm_net_prop": ["lm_net_prop", "lm_net_tone", "net_prop_lm"],
    "lm_positive_tfidf": ["lm_positive_tfidf", "lm_pos_tfidf", "positive_tfidf_lm"],
    "lm_negative_tfidf": ["lm_negative_tfidf", "lm_neg_tfidf", "negative_tfidf_lm"],
    "lm_net_tfidf": ["lm_net_tfidf", "lm_net_tfidf_score", "net_tfidf_lm"],
    "harvard_positive_prop": ["harvard_positive_prop", "general_positive_prop", "h_positive_prop"],
    "harvard_negative_prop": ["harvard_negative_prop", "general_negative_prop", "h_negative_prop"],
    "harvard_net_prop": ["harvard_net_prop", "general_net_prop", "h_net_prop"],
    "harvard_positive_tfidf": ["harvard_positive_tfidf", "general_positive_tfidf", "h_positive_tfidf"],
    "harvard_negative_tfidf": ["harvard_negative_tfidf", "general_negative_tfidf", "h_negative_tfidf"],
    "harvard_net_tfidf": ["harvard_net_tfidf", "general_net_tfidf", "h_net_tfidf"],
}

CONTROL_CANDIDATES = {
    "size": ["size", "Size"],
    "bm": ["bm", "BM", "book_to_market"],
    "volatility": ["volatility", "Volatility", "vol"],
    "turnover": ["turnover", "Turnover"],
}


def pick(df: pd.DataFrame, names: list[str]) -> Optional[str]:
    lower = {str(c).strip().lower(): c for c in df.columns}
    for n in names:
        if n.lower() in lower:
            return lower[n.lower()]
    return None


def resolve(df: pd.DataFrame, mapping: dict[str, list[str]], required: bool = True) -> dict[str, str]:
    out = {}
    missing = []
    for canon, cand in mapping.items():
        c = pick(df, cand)
        if c:
            out[canon] = c
        elif required:
            missing.append(canon)
    if missing:
        raise ValueError(f"Thiếu cột {missing}. Available={list(df.columns)}")
    return out


def find_car_col(event: pd.DataFrame, lo: int, hi: int) -> str:
    explicit = [
        f"car_{'m'+str(abs(lo)) if lo < 0 else 'p'+str(lo)}_{'m'+str(abs(hi)) if hi < 0 else 'p'+str(hi)}",
        f"CAR_{lo}_{hi}",
        f"car_{lo}_{hi}",
        f"CAR[{lo:+d},{hi:+d}]",
        f"car_{lo:+d}_{hi:+d}",
    ]
    for c in explicit:
        if c in event.columns:
            return c
    # Normalized matching against compact column names.
    target = f"{lo}_{hi}".replace("-", "m")
    for c in event.columns:
        s = str(c).lower().replace(" ", "")
        if "car" in s and (str(lo) in s or (lo < 0 and f"m{abs(lo)}" in s)) and (str(hi) in s or (hi >= 0 and f"p{hi}" in s)):
            return c
    raise ValueError(f"Không tìm thấy CAR window [{lo},{hi}]. Event columns={list(event.columns)}")


def clean_merge_keys(df: pd.DataFrame) -> pd.DataFrame:
    d = df.copy()
    ticker = pick(d, ["ticker", "Ticker"])
    date = pick(d, ["filing_date", "date"])
    if not ticker or not date:
        raise ValueError(f"File thiếu ticker/filing_date: {list(d.columns)}")
    d = d.rename(columns={ticker: "ticker", date: "filing_date"})
    d["ticker"] = d["ticker"].astype(str).str.upper().str.strip()
    d["filing_date"] = pd.to_datetime(d["filing_date"], errors="coerce")
    return d


def fit_model(y: pd.Series, X: pd.DataFrame, group: pd.Series) -> dict:
    x = sm.add_constant(X.astype(float), has_constant="add")
    yy = pd.to_numeric(y, errors="coerce").astype(float)
    good = yy.notna() & np.isfinite(yy)
    for c in x.columns:
        good &= np.isfinite(pd.to_numeric(x[c], errors="coerce"))
    x = x.loc[good]
    yy = yy.loc[good]
    grp = group.loc[good]
    if len(x) <= x.shape[1] + 3:
        raise ValueError("Không đủ quan sát cho mô hình")
    ols = sm.OLS(yy, x).fit()
    hc3 = ols.get_robustcov_results(cov_type="HC3")
    cluster = ols.get_robustcov_results(cov_type="cluster", groups=grp.astype(str))

    params = pd.Series(ols.params, index=x.columns)
    se_hc3 = pd.Series(hc3.bse, index=x.columns)
    p_hc3 = pd.Series(hc3.pvalues, index=x.columns)
    se_cl = pd.Series(cluster.bse, index=x.columns)
    p_cl = pd.Series(cluster.pvalues, index=x.columns)
    return {
        "n": int(len(yy)),
        "firms": int(grp.nunique()),
        "r2": float(ols.rsquared),
        "adj_r2": float(ols.rsquared_adj),
        "aic": float(ols.aic),
        "bic": float(ols.bic),
        "ols": ols,
        "params": params,
        "se_hc3": se_hc3,
        "p_hc3": p_hc3,
        "se_cluster": se_cl,
        "p_cluster": p_cl,
        "y": yy,
        "X": x,
        "group": grp,
    }


def one_sided_p(p_two: float, coef: float, expected: str) -> float:
    if not np.isfinite(p_two) or not np.isfinite(coef):
        return np.nan
    if expected == ">0":
        return p_two / 2 if coef > 0 else 1 - p_two / 2
    if expected == "<0":
        return p_two / 2 if coef < 0 else 1 - p_two / 2
    return p_two / 2


def diagnostics(model: dict, predictor_cols: list[str]) -> dict:
    ols = model["ols"]
    x = model["X"]
    y = model["y"]
    bp_lm, bp_lmf, bp_f, bp_ff = het_breuschpagan(ols.resid, x)
    try:
        white_lm, white_lmf, white_f, white_ff = het_white(ols.resid, x)
    except Exception as exc:
        white_lm = white_lmf = white_f = white_ff = np.nan
        white_err = str(exc)
    else:
        white_err = ""
    vif_rows = []
    xv = x.drop(columns=["const"], errors="ignore")
    for c in xv.columns:
        try:
            vif = variance_inflation_factor(xv.values, xv.columns.get_loc(c))
        except Exception:
            vif = np.nan
        vif_rows.append({"variable": c, "vif": vif})
    corr = xv.corr(method="pearson")
    return {
        "bp_lm_stat": bp_lm,
        "bp_lm_p": bp_lmf,
        "bp_f_stat": bp_f,
        "bp_f_p": bp_ff,
        "white_lm_stat": white_lm,
        "white_lm_p": white_lmf,
        "white_f_stat": white_f,
        "white_f_p": white_ff,
        "white_error": white_err,
        "vif": pd.DataFrame(vif_rows),
        "corr": corr,
    }


def add_result(rows: list[dict], model_id: str, car_window: str, score_name: str, expected: Optional[str], model: dict, label: str) -> None:
    b = model["params"]
    for variable in b.index:
        p_hc3 = float(model["p_hc3"].get(variable, np.nan))
        coef = float(b[variable])
        expected_local = expected if variable != "const" else None
        rows.append({
            "model": model_id,
            "label": label,
            "car_window": car_window,
            "score": score_name,
            "variable": variable,
            "coef": coef,
            "se_ols": float(model["ols"].bse[variable]),
            "p_ols_two_sided": float(model["ols"].pvalues[variable]),
            "se_hc3": float(model["se_hc3"][variable]),
            "p_hc3_two_sided": p_hc3,
            "se_cluster": float(model["se_cluster"][variable]),
            "p_cluster_two_sided": float(model["p_cluster"][variable]),
            "expected_direction": expected_local or "",
            "p_hc3_one_sided": one_sided_p(p_hc3, coef, expected_local) if expected_local else np.nan,
            "direction_correct": (coef > 0) if expected_local == ">0" else ((coef < 0) if expected_local == "<0" else np.nan),
            "n": model["n"],
            "firms": model["firms"],
            "r2": model["r2"],
            "adj_r2": model["adj_r2"],
            "aic": model["aic"],
            "bic": model["bic"],
        })


def run() -> None:
    OUTDIR.mkdir(parents=True, exist_ok=True)
    tone = clean_merge_keys(pd.read_csv(TONE, low_memory=False))
    event = clean_merge_keys(pd.read_csv(EVENT, low_memory=False))
    control = clean_merge_keys(pd.read_csv(CONTROL, low_memory=False))
    scores = resolve(tone, SCORE_CANDIDATES, required=False)
    controls = resolve(control, CONTROL_CANDIDATES, required=True)

    event_keep = ["ticker", "filing_date"]
    for key, (lo, hi) in CAR_WINDOWS.items():
        event_keep.append(find_car_col(event, lo, hi))
    event = event[event_keep].copy()
    event = event.drop_duplicates(["ticker", "filing_date"])

    tone_keep = ["ticker", "filing_date"] + list(scores.values())
    tone = tone[tone_keep].drop_duplicates(["ticker", "filing_date"])
    ctrl_keep = ["ticker", "filing_date"] + list(controls.values())
    control = control[ctrl_keep].drop_duplicates(["ticker", "filing_date"])

    # Rename to canonical names.
    tone = tone.rename(columns={v: k for k, v in scores.items()})
    control = control.rename(columns={v: k for k, v in controls.items()})
    event = event.rename(columns={find_car_col(event, *CAR_WINDOWS[k]): f"car_{k}" for k in CAR_WINDOWS})
    df = event.merge(tone, on=["ticker", "filing_date"], how="inner").merge(control, on=["ticker", "filing_date"], how="left")
    df = df.sort_values(["ticker", "filing_date"]).reset_index(drop=True)
    df.to_csv(OUTDIR / "regression_sample.csv", index=False, encoding="utf-8-sig")

    result_rows: list[dict] = []
    diag_rows: list[dict] = []
    compare_rows: list[dict] = []
    corr_payload: list[pd.DataFrame] = []
    vif_payload: list[pd.DataFrame] = []

    # Primary control set for this phase: the four controls that are directly defined and implementable.
    controls4 = ["size", "bm", "volatility", "turnover"]
    print(f"Merged sample: {len(df)} rows | firms={df['ticker'].nunique()}")
    print(f"Scores found: {list(scores)}")

    for car_key in CAR_WINDOWS:
        ycol = f"car_{car_key}"
        y = pd.to_numeric(df[ycol], errors="coerce")

        # C1 H1: LM Positive; C1 H2: LM Negative; plus other available score variants as diagnostic rows.
        primary_c1 = [
            ("lm_positive_prop", ">0", "C1_H1_LM_Positive"),
            ("lm_negative_prop", "<0", "C1_H2_LM_Negative"),
        ]
        for score, expected, label in primary_c1:
            if score not in df.columns:
                continue
            x = df[[score]].apply(pd.to_numeric, errors="coerce")
            try:
                m = fit_model(y, x, df["ticker"])
            except Exception:
                continue
            add_result(result_rows, "C1", car_key, score, expected, m, label)

            d = diagnostics(m, [score])
            diag_rows.append({"model": "C1", "label": label, "car_window": car_key, **{k:v for k,v in d.items() if not isinstance(v,(pd.DataFrame,pd.Series))}})

            # Baseline coefficient used later.
            coef = float(m["params"][score]); se = float(m["se_hc3"][score]); p = float(m["p_hc3"][score])
            compare_rows.append({"car_window": car_key, "construct": score, "model": "Baseline_C1", "coef": coef, "se_hc3": se, "p_hc3": p, "r2": m["r2"], "n": m["n"], "firms": m["firms"], "delta_coef_vs_baseline": 0.0})

        # C2 for Positive and Negative separately.
        for score, expected, label in primary_c1:
            if score not in df.columns:
                continue
            cols = [score] + controls4
            dff = df[[ycol, "ticker"] + cols].copy()
            dff = dff.dropna()
            if len(dff) < 50:
                continue

            # Matched baseline: chạy lại C1 trên đúng sample của C2.
            # Như vậy delta_coef_vs_baseline chỉ phản ánh thay đổi do thêm controls,
            # không bị trộn với thay đổi sample do missing controls.
            try:
                matched_baseline = fit_model(
                    dff[ycol],
                    dff[[score]],
                    dff["ticker"],
                )
                matched_coef = float(matched_baseline["params"][score])
                matched_se = float(matched_baseline["se_hc3"][score])
                matched_p = float(matched_baseline["p_hc3"][score])

                compare_rows.append({
                    "car_window": car_key,
                    "construct": score,
                    "model": "Baseline_C1_Matched",
                    "coef": matched_coef,
                    "se_hc3": matched_se,
                    "p_hc3": matched_p,
                    "r2": matched_baseline["r2"],
                    "n": matched_baseline["n"],
                    "firms": matched_baseline["firms"],
                    "delta_coef_vs_baseline": 0.0,
                })
            except Exception:
                continue

            try:
                m = fit_model(dff[ycol], dff[cols], dff["ticker"])
            except Exception:
                continue
            add_result(result_rows, "C2", car_key, score, expected, m, label+"_Controls")
            dg = diagnostics(m, cols)
            diag_rows.append({"model": "C2", "label": label+"_Controls", "car_window": car_key, **{k:v for k,v in dg.items() if not isinstance(v,(pd.DataFrame,pd.Series))}})
            v = dg["vif"].copy(); v["model"]="C2"; v["label"]=label+"_Controls"; v["car_window"]=car_key; vif_payload.append(v)
            c = dg["corr"].copy(); c.insert(0,"variable",c.index); c["model"]="C2"; c["label"]=label+"_Controls"; c["car_window"]=car_key; corr_payload.append(c)

            coef = float(m["params"][score]); se = float(m["se_hc3"][score]); p = float(m["p_hc3"][score])
            base = [r for r in compare_rows if r["car_window"]==car_key and r["construct"]==score and r["model"]=="Baseline_C1_Matched"]
            base_coef = base[0]["coef"] if base else np.nan
            compare_rows.append({"car_window": car_key, "construct": score, "model": "Full_C2_Controls4", "coef": coef, "se_hc3": se, "p_hc3": p, "r2": m["r2"], "n": m["n"], "firms": m["firms"], "delta_coef_vs_baseline": coef-base_coef if np.isfinite(base_coef) else np.nan})

        # C3 LM Positive + Negative + controls.
        if {"lm_positive_prop","lm_negative_prop"}.issubset(df.columns):
            cols = ["lm_positive_prop","lm_negative_prop"] + controls4
            dff = df[[ycol,"ticker"]+cols].dropna()
            if len(dff) >= 50:
                try:
                    m = fit_model(dff[ycol], dff[cols], dff["ticker"])
                    add_result(result_rows,"C3",car_key,"lm_positive_prop+lm_negative_prop",None,m,"C3_LM_Pos_Neg_Controls4")
                    # Overwrite hypothesis-direction fields separately for the two tone coefficients.
                    for rr in result_rows[-(len(m["params"])):]:
                        if rr["variable"] == "lm_positive_prop":
                            rr["expected_direction"] = ">0"
                            rr["p_hc3_one_sided"] = one_sided_p(rr["p_hc3_two_sided"], rr["coef"], ">0")
                            rr["direction_correct"] = rr["coef"] > 0
                        elif rr["variable"] == "lm_negative_prop":
                            rr["expected_direction"] = "<0"
                            rr["p_hc3_one_sided"] = one_sided_p(rr["p_hc3_two_sided"], rr["coef"], "<0")
                            rr["direction_correct"] = rr["coef"] < 0
                    dg=diagnostics(m,cols)
                    diag_rows.append({"model":"C3","label":"C3_LM_Pos_Neg_Controls4","car_window":car_key,**{k:v for k,v in dg.items() if not isinstance(v,(pd.DataFrame,pd.Series))}})
                    v=dg["vif"].copy();v["model"]="C3";v["label"]="C3_LM_Pos_Neg_Controls4";v["car_window"]=car_key;vif_payload.append(v)
                    c=dg["corr"].copy();c.insert(0,"variable",c.index);c["model"]="C3";c["label"]="C3_LM_Pos_Neg_Controls4";c["car_window"]=car_key;corr_payload.append(c)
                except Exception:
                    pass

        # C4 LM vs Harvard, by proportional and TF-IDF score.
        pairs = [
            ("lm_net_prop","harvard_net_prop","C4_Proportional"),
            ("lm_net_tfidf","harvard_net_tfidf","C4_TFIDF"),
        ]
        for lm_col, h_col, label in pairs:
            if not {lm_col,h_col}.issubset(df.columns):
                continue
            cols=[lm_col,h_col]
            dff=df[[ycol,"ticker"]+cols].dropna()
            if len(dff)<50:
                continue
            try:
                m=fit_model(dff[ycol],dff[cols],dff["ticker"])
            except Exception:
                continue
            add_result(result_rows,"C4",car_key,f"{lm_col}__{h_col}",None,m,label)
            dg=diagnostics(m,cols)
            diag_rows.append({"model":"C4","label":label,"car_window":car_key,**{k:v for k,v in dg.items() if not isinstance(v,(pd.DataFrame,pd.Series))}})
            v=dg["vif"].copy();v["model"]="C4";v["label"]=label;v["car_window"]=car_key;vif_payload.append(v)
            c=dg["corr"].copy();c.insert(0,"variable",c.index);c["model"]="C4";c["label"]=label;c["car_window"]=car_key;corr_payload.append(c)

    results = pd.DataFrame(result_rows)
    results.to_csv(OUTDIR / "regression_results.csv", index=False, encoding="utf-8-sig")
    pd.DataFrame(diag_rows).to_csv(OUTDIR / "regression_diagnostics.csv", index=False, encoding="utf-8-sig")
    pd.DataFrame(compare_rows).to_csv(OUTDIR / "baseline_vs_full.csv", index=False, encoding="utf-8-sig")
    if vif_payload:
        pd.concat(vif_payload, ignore_index=True).to_csv(OUTDIR / "vif_results.csv", index=False, encoding="utf-8-sig")
    if corr_payload:
        pd.concat(corr_payload, ignore_index=True).to_csv(OUTDIR / "correlation_results.csv", index=False, encoding="utf-8-sig")

    # Compact hypothesis table:
    # retain only the variables that correspond to the primary hypotheses H1/H2.
    # Controls are estimation variables, not hypothesis-test rows.
    hypothesis_variables = {"lm_positive_prop", "lm_negative_prop"}
    hyp = results[
        results["model"].isin(["C1", "C2", "C3"])
        & results["variable"].isin(hypothesis_variables)
    ].copy()
    hyp["decision_alpha_05"] = np.where(
        hyp["expected_direction"].eq(">0") | hyp["expected_direction"].eq("<0"),
        (hyp["direction_correct"] == True) & (hyp["p_hc3_one_sided"] < 0.05),
        np.nan,
    )
    hyp.to_csv(OUTDIR / "hypothesis_tests.csv", index=False, encoding="utf-8-sig")

    print("\nREGRESSION COMPLETE")
    print(f"sample={len(df)} firms={df['ticker'].nunique()}")
    print(f"results={OUTDIR/'regression_results.csv'}")
    print(f"diagnostics={OUTDIR/'regression_diagnostics.csv'}")
    print(f"baseline_vs_full={OUTDIR/'baseline_vs_full.csv'}")
    if not results.empty:
        show = results[(results["variable"].isin(["lm_positive_prop","lm_negative_prop"])) & (results["model"].isin(["C1","C2","C3"]))].copy()
        if not show.empty:
            print("\nKEY HYPOTHESIS COEFFICIENTS (HC3)")
            print(show[["model","car_window","variable","coef","se_hc3","p_hc3_two_sided","p_hc3_one_sided","direction_correct","n","r2"]].to_string(index=False))


if __name__ == "__main__":
    run()
