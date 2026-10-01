"""Optional B6/C5-C8 diagnostics from the saved tone, event, control and price inputs.

These are explicitly reduced specifications: no Word Power, EADRet or Accruals.
All returns are decimal. Delayed windows include trading day +5, as in C6.
"""

from __future__ import annotations

from pathlib import Path
import sys

import numpy as np
import pandas as pd
import statsmodels.api as sm
from scipy.stats import norm, t as student_t


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "analysis_outputs"
EVENT = OUT / "event_study"
WINDOWS = {"CAR_m1_p1": (-1, 1), "CAR_0_p3": (0, 3),
           "CAR_m3_p3": (-3, 3), "CAR_m5_p5": (-5, 5)}
CONTROLS = ["size", "bm", "volatility", "turnover"]


def fit_model(frame: pd.DataFrame, y: str, predictors: list[str], name: str) -> list[dict]:
    work = frame[["ticker", y, *predictors]].replace([np.inf, -np.inf], np.nan).dropna()
    if len(work) <= len(predictors) + 2 or work.ticker.nunique() < 5:
        raise ValueError(f"Insufficient observations for {name}")
    x = sm.add_constant(work[predictors].astype(float), has_constant="add")
    model = sm.OLS(work[y].astype(float), x)
    hc3 = model.fit(cov_type="HC3")
    cluster = model.fit(cov_type="cluster", cov_kwds={"groups": work.ticker,
                        "use_correction": True}, use_t=True)
    rows = []
    for term in hc3.params.index:
        lo, hi = hc3.conf_int().loc[term]
        rows.append({"model": name, "dependent_variable": y, "term": term,
                     "n": len(work), "n_firms": work.ticker.nunique(),
                     "coefficient": hc3.params[term], "se_hc3": hc3.bse[term],
                     "p_hc3_two_sided": hc3.pvalues[term],
                     "ci_hc3_low": lo, "ci_hc3_high": hi,
                     "se_cluster": cluster.bse[term],
                     "p_cluster_two_sided": cluster.pvalues[term]})
    return rows


def b6_tests(estimation: pd.DataFrame, filings: pd.DataFrame) -> pd.DataFrame:
    keys = ["ticker", "accession_number"]
    sd = estimation.groupby(keys).ar.agg(["std", "count"]).reset_index()
    if not sd["count"].eq(239).all():
        raise ValueError("B6 requires 239 estimation ARs per filing")
    merged = filings.merge(sd[keys + ["std"]], on=keys, validate="one_to_one")
    if len(merged) != len(filings) or merged["std"].le(0).any():
        raise ValueError("B6 estimation SD alignment failed")
    rows = []
    for name, (lo, hi) in WINDOWS.items():
        car = merged[name].astype(float).to_numpy()
        n = len(car)
        standardized = car / (merged["std"].to_numpy() * np.sqrt(hi - lo + 1))
        z_std = float(standardized.sum() / np.sqrt(n))
        mean_car = float(np.mean(car))
        # MacKinlay Eq. 21 uses N^-2 times the sum of squared deviations.
        se_cross = float(np.sqrt(np.sum((car - mean_car) ** 2)) / n)
        z_cross = mean_car / se_cross
        rows.append({"window": name, "n": n, "caar": float(np.mean(car)),
                     "standardized_z": z_std,
                     "standardized_p": float(2 * norm.sf(abs(z_std))),
                     "cross_sectional_se": se_cross, "cross_sectional_z": z_cross,
                     "cross_sectional_p": float(2 * norm.sf(abs(z_cross)))})
    return pd.DataFrame(rows)


def c5_reduced(panel: pd.DataFrame, controls: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    keys = ["ticker", "filing_date"]
    if panel.duplicated(keys).any() or controls.duplicated(keys).any():
        raise ValueError("Duplicate C5 filing key")
    work = panel[keys + ["filing_year", "lm_net_prop"]].sort_values(keys).copy()
    work["lag_tone"] = work.groupby("ticker").lm_net_prop.shift(1)
    work["lag_year"] = work.groupby("ticker").filing_year.shift(1)
    work = work.loc[work.filing_year.sub(work.lag_year).eq(1)]
    work = work.merge(controls[keys + ["status", *CONTROLS]], on=keys,
                      how="left", validate="one_to_one")
    work = work.loc[work.status.eq("success")].dropna(
        subset=["lm_net_prop", "lag_tone", *CONTROLS]).copy()
    predictors = [*CONTROLS, "lag_tone"]
    for col in predictors:
        work[col] = pd.to_numeric(work[col], errors="raise")
        scale = work[col].std(ddof=1)
        if not np.isfinite(scale) or scale <= 0:
            raise ValueError(f"Cannot standardize C5 {col}")
        work[f"z_{col}"] = (work[col] - work[col].mean()) / scale
    rows = fit_model(work, "lm_net_prop", [f"z_{x}" for x in predictors],
                     "C5_reduced_4controls_lag_tone")
    return work, pd.DataFrame(rows)


def delayed_returns(filings: pd.DataFrame, prices: pd.DataFrame) -> pd.DataFrame:
    market = prices.loc[prices.ticker.eq("^GSPC"), ["date", "return"]].sort_values("date")
    if market.date.duplicated().any():
        raise ValueError("Duplicate market trading date")
    sessions = market.date.tolist()
    positions = {day: i for i, day in enumerate(sessions)}
    market_returns = market["return"].to_numpy(dtype=float)
    firms = {ticker: group.set_index("date")["return"] for ticker, group in prices.groupby("ticker")}
    rows = []
    for row in filings.itertuples():
        if row.event_date not in positions or row.ticker not in firms:
            raise ValueError(f"Missing event date or ticker for {row.accession_number}")
        pos = positions[row.event_date]
        firm_returns = firms[row.ticker]
        record = {"ticker": row.ticker, "filing_date": row.filing_date,
                  "accession_number": row.accession_number}
        for end in (5, 10, 22):
            days = sessions[pos + 5:pos + end + 1]
            if len(days) != end - 4:
                record[f"car_p5_p{end}"] = np.nan
                continue
            observed = firm_returns.reindex(days).to_numpy(dtype=float)
            expected = row.alpha + row.beta * market_returns[pos + 5:pos + end + 1]
            record[f"car_p5_p{end}"] = (float(np.sum(observed - expected))
                                         if np.isfinite(observed).all() and np.isfinite(expected).all()
                                         else np.nan)
        rows.append(record)
    return pd.DataFrame(rows)


def c8_fama_macbeth(frame: pd.DataFrame, y: str, predictors: list[str],
                    name: str) -> tuple[pd.DataFrame, pd.DataFrame]:
    annual = []
    for year, group in frame.groupby("filing_year"):
        work = group[[y, *predictors]].replace([np.inf, -np.inf], np.nan).dropna()
        if len(work) <= max(20, 5 * (len(predictors) + 1)):
            raise ValueError(f"C8 year {year} too small for {name}")
        x = sm.add_constant(work[predictors].astype(float), has_constant="add")
        fitted = sm.OLS(work[y].astype(float), x).fit()
        for term, coefficient in fitted.params.items():
            annual.append({"model": name, "filing_year": int(year), "term": term,
                           "n": len(work), "coefficient": float(coefficient)})
    yearly = pd.DataFrame(annual)
    if yearly.filing_year.nunique() != 10:
        raise ValueError("C8 requires all ten filing years")
    summary = []
    for term, group in yearly.groupby("term", sort=False):
        coefficients = group.coefficient.to_numpy(dtype=float)
        n_years = len(coefficients)
        se = float(np.std(coefficients, ddof=1) / np.sqrt(n_years))
        statistic = float(np.mean(coefficients) / se) if se > 0 else np.nan
        summary.append({"model": name, "dependent_variable": y, "term": term,
                        "n_years": n_years, "mean_coefficient": float(np.mean(coefficients)),
                        "se_across_years": se, "t_stat": statistic,
                        "p_two_sided": float(2 * student_t.sf(abs(statistic), n_years - 1))})
    return yearly, pd.DataFrame(summary)


def write_report(b6: pd.DataFrame, c5: pd.DataFrame, c6: pd.DataFrame,
                 c7: pd.DataFrame, c8: pd.DataFrame) -> None:
    def item(table: pd.DataFrame, term: str, model: str | None = None) -> pd.Series:
        rows = table.loc[table.term.eq(term)]
        if model is not None:
            rows = rows.loc[rows.model.eq(model)]
        if len(rows) != 1:
            raise ValueError(f"Missing report row: {model}, {term}")
        return rows.iloc[0]

    c5_lag = item(c5, "z_lag_tone")
    c6_lines = []
    for end in (5, 10, 22):
        row = item(c6, "lm_net_prop", f"C6_delayed_p5_p{end}_LM_NetProp")
        c6_lines.append(f"| [+5,+{end}] | {int(row.n)} | {row.coefficient:.4f} | "
                        f"{row.p_hc3_two_sided:.4f} | {row.p_cluster_two_sided:.4f} |")
    c7_tone = item(c7, "lm_net_prop")
    c8_base = item(c8, "lm_net_prop", "C8_C1_LM_NetProp")
    c8_control = item(c8, "lm_net_prop", "C8_C2_reduced_4controls")
    b6_lines = [f"| {row.window} | {int(row.n)} | {row.standardized_p:.4g} | "
                f"{row.cross_sectional_p:.4g} |" for row in b6.itertuples()]
    report = f"""# Kiểm định độ vững B6 và mô hình C5–C8

Các bảng này dùng **tone LM dạng tỷ lệ**, không dùng Word Power. Đây là phân tích bổ sung từ đầu vào hiện có; hệ số hồi quy là quan hệ trong mẫu, không chứng minh nhân quả. B6 kiểm tra **CAAR trung bình**, không kiểm định hệ số tone.

## B6 — hai kiểm định bổ sung

Kiểm định chuẩn hóa chia CAR từng hồ sơ cho độ lệch chuẩn AR của 239 ngày ước lượng và căn bậc hai số ngày sự kiện, rồi cộng qua hồ sơ theo giả định độc lập chéo. Kiểm định phương sai cắt ngang dùng đúng phương sai Eq. 21 trong tài liệu công thức. Do các sự kiện có thể trùng ngày, giả định độc lập chéo cần được cân nhắc khi diễn giải p-value.

| Cửa sổ | N | p chuẩn hóa | p phương sai cắt ngang |
| --- | ---: | ---: | ---: |
{chr(10).join(b6_lines)}

## C5 — yếu tố quyết định tone, bản rút gọn

Hồi quy `LM_net_prop` theo Size, BM, Volatility, Turnover và tone của **hồ sơ năm nộp liền trước**. Năm trước thiếu tone thì không thay bằng năm cũ hơn. Các biến giải thích được chuẩn hóa trên mẫu hồi quy; tone phụ thuộc giữ đơn vị tỷ lệ. Mẫu còn **{int(c5_lag.n)} hồ sơ, {int(c5_lag.n_firms)} công ty**. Hệ số tone trễ chuẩn hóa = {c5_lag.coefficient:.6f}, p HC3 = {c5_lag.p_hc3_two_sided:.4g}, p cụm công ty = {c5_lag.p_cluster_two_sided:.4g}. Đây chưa phải Eq. 11 đầy đủ vì thiếu EADRet và Accruals.

## C6 — phản ứng chậm

Mã tính tổng AR từ phiên `+5` tới `+T` theo mô hình thị trường đã ước lượng trước sự kiện. Đúng theo cách viết Eq. 17 trong file nhóm, cửa sổ `[+5,+5]` chỉ có một ngày; ba cửa sổ **đều bao gồm ngày +5**. Hồ sơ thiếu bất kỳ phiên nào của cửa sổ bị loại khỏi riêng hồi quy đó.

| Cửa sổ | N | Hệ số LM net tỷ lệ | p HC3 | p cụm công ty |
| --- | ---: | ---: | ---: | ---: |
{chr(10).join(c6_lines)}

## C7 — hồi quy cắt ngang AR ngày 0

AR ngày 0 được hồi quy theo LM net tỷ lệ và bốn biến kiểm soát, với HC3 và sai số chuẩn cụm công ty. N = {int(c7_tone.n)}; hệ số tone = {c7_tone.coefficient:.4f}, p HC3 = {c7_tone.p_hc3_two_sided:.4f}, p cụm = {c7_tone.p_cluster_two_sided:.4f}. C2 rút gọn đã bao phủ đặc tả tương ứng với CAR; bảng C7 này bổ sung **AR ngày 0**, tránh lặp cùng một hồi quy dưới tên khác.

## C8 — Fama–MacBeth theo năm nộp

Hồi quy cắt ngang riêng cho từng năm 2016–2025, sau đó lấy trung bình **10 hệ số năm** và tính sai số chuẩn từ độ phân tán giữa các năm (t với 9 bậc tự do). Dùng CAR `[0,+3]`. Đặc tả C1 tỷ lệ: hệ số tone trung bình = {c8_base.mean_coefficient:.4f}, p = {c8_base.p_two_sided:.4f}; đặc tả C2 rút gọn: {c8_control.mean_coefficient:.4f}, p = {c8_control.p_two_sided:.4f}. Chỉ có 10 năm, nên sức mạnh kiểm định hạn chế; cả hai mô hình không dùng Word Power.

Các CSV trong `analysis_outputs/` và `analysis_outputs/event_study/` lưu toàn bộ hệ số, p-value, cỡ mẫu và hồ sơ. C2/C5 sáu controls từ hai bảng mới được tính riêng bởi `calculate_full_controls.py` và giải thích ở `FULL_CONTROLS_REVIEW.md`. Word Power được tính riêng tại `word_power/`; kiểm tra ngữ cảnh từng từ và tái tạo toàn bộ từ HTML gốc cần tải lại corpus theo manifest SEC.
"""
    (OUT / "ROBUSTNESS_RESULTS.md").write_text(report, encoding="utf-8")


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    key_types = {"accession_number": str, "ticker": str, "filing_date": str}
    filings = pd.read_csv(EVENT / "event_filing_results.csv", dtype=key_types)
    estimation = pd.read_csv(EVENT / "estimation_ar_long.csv", dtype=key_types)
    b6 = b6_tests(estimation, filings)
    b6.to_csv(EVENT / "b6_robustness_tests.csv", index=False)

    panel = pd.read_csv(OUT / "tone_firm_year.csv", dtype={"ticker": str, "filing_date": str})
    controls = pd.read_csv(ROOT / "data/metadata/controls/controls_item7.csv",
                           dtype={"ticker": str, "filing_date": str})
    c5_sample, c5 = c5_reduced(panel, controls)
    c5.to_csv(OUT / "c5_reduced_results.csv", index=False)
    c5_sample.to_csv(OUT / "c5_reduced_sample.csv", index=False)

    prices = pd.read_csv(ROOT / "data/market_data/daily_prices.csv",
                         usecols=["ticker", "date", "return"], dtype={"ticker": str, "date": str})
    delayed = delayed_returns(filings, prices)
    delayed.to_csv(EVENT / "delayed_filing_results.csv", index=False)
    tone = pd.read_csv(OUT / "regression/regression_sample.csv",
                       dtype={"ticker": str, "filing_date": str})
    delayed_sample = tone.merge(delayed, on=["ticker", "filing_date"],
                                validate="one_to_one", how="inner")
    if len(delayed_sample) != len(tone):
        raise ValueError("C6 tone/event join lost filings")
    c6_rows = []
    for end in (5, 10, 22):
        c6_rows.extend(fit_model(delayed_sample, f"car_p5_p{end}", ["lm_net_prop"],
                                 f"C6_delayed_p5_p{end}_LM_NetProp"))
    pd.DataFrame(c6_rows).to_csv(OUT / "c6_delayed_results.csv", index=False)

    c2 = pd.read_csv(OUT / "c2_reduced_sample.csv", dtype={"ticker": str, "filing_date": str})
    day_zero = pd.read_csv(EVENT / "event_ar_long.csv", dtype=key_types)
    day_zero = day_zero.loc[day_zero.event_time.eq(0), ["ticker", "filing_date", "ar"]]
    day_zero = day_zero.rename(columns={"ar": "ar_day0"})
    c7_sample = c2.merge(day_zero, on=["ticker", "filing_date"], validate="one_to_one")
    if len(c7_sample) != len(c2):
        raise ValueError("C7 day-zero AR join lost filings")
    c7_sample.to_csv(OUT / "c7_cross_section_sample.csv", index=False)
    c7 = fit_model(c7_sample, "ar_day0", ["lm_net_prop", *CONTROLS],
                   "C7_AR_day0_reduced_controls")
    pd.DataFrame(c7).to_csv(OUT / "c7_cross_section_results.csv", index=False)

    tone["filing_year"] = pd.to_datetime(tone.filing_date).dt.year
    c2["filing_year"] = pd.to_datetime(c2.filing_date).dt.year
    annual_a, summary_a = c8_fama_macbeth(tone, "car_0_p3", ["lm_net_prop"],
                                            "C8_C1_LM_NetProp")
    annual_b, summary_b = c8_fama_macbeth(c2, "car_0_p3", ["lm_net_prop", *CONTROLS],
                                            "C8_C2_reduced_4controls")
    pd.concat([annual_a, annual_b], ignore_index=True).to_csv(
        OUT / "c8_annual_coefficients.csv", index=False)
    c8 = pd.concat([summary_a, summary_b], ignore_index=True)
    c8.to_csv(OUT / "c8_fama_macbeth_summary.csv", index=False)
    write_report(b6, c5, pd.DataFrame(c6_rows), pd.DataFrame(c7), c8)
    print(f"B6: {len(b6)} windows; C5: {len(c5_sample)} filings; "
          f"C6 complete (+5/+10/+22): " + "/".join(
              str(delayed[f'car_p5_p{end}'].notna().sum()) for end in (5, 10, 22)))
    print(f"C7: {len(c7_sample)} filings; C8: ten years, two specifications")


if __name__ == "__main__":
    main()
