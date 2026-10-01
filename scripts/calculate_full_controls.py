"""Add audited EADRet/Accruals to the existing four-control analysis.

The two source CSVs came from the separate finalize-eadret-accruals branch.
Keep the current main-branch Size/BM/Volatility/Turnover definitions intact.
Only Accruals rows explicitly marked PASS enter the primary six-control sample.
"""

from __future__ import annotations

import json
from pathlib import Path
import sys

import numpy as np
import pandas as pd

from optional_robustness import fit_model


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "analysis_outputs"
SOURCE = ROOT / "data/metadata/controls"
KEY = ["ticker", "filing_date"]
FOUR = ["size", "bm", "volatility", "turnover"]
SIX = [*FOUR, "eadret", "accruals"]
WINDOWS = ["car_m1_p1", "car_0_p3", "car_m3_p3", "car_m5_p5"]


def normalized_accession(series: pd.Series) -> pd.Series:
    return series.astype(str).str.replace("-", "", regex=False).str.strip()


def load_controls(panel: pd.DataFrame, earnings: pd.DataFrame,
                  accruals: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    """Validate one-to-one filing provenance before using supplied controls."""
    panel = panel[[*KEY, "accession_number", "report_date"]].copy()
    earnings = earnings.rename(columns={"tenk_filing_date": "filing_date"}).copy()
    for frame in (panel, earnings, accruals):
        frame["filing_date"] = frame.filing_date.astype(str).str[:10]
        if frame.duplicated(KEY).any():
            raise ValueError("Duplicate company/filing date in supplied controls")
    joined = panel.merge(earnings, on=KEY, how="left", validate="one_to_one")
    if len(joined) != len(panel) or joined.status.isna().any():
        raise ValueError("EADRet does not cover the current filing cohort")
    if not normalized_accession(joined.accession_number).eq(
            normalized_accession(joined.tenk_accession)).all():
        raise ValueError("EADRet 10-K accession differs from current cohort")
    success = joined.status.eq("success")
    if joined.loc[success, "eadret"].isna().any():
        raise ValueError("Successful EADRet row has no value")
    if not np.allclose(joined.loc[success, "eadret"],
                       joined.loc[success, "stock_return"] - joined.loc[success, "market_return"],
                       atol=1e-12, rtol=1e-10):
        raise ValueError("EADRet arithmetic changed")
    accepted = pd.to_datetime(joined.loc[success, "tenk_acceptance_datetime_utc"], utc=True)
    announced = pd.to_datetime(joined.loc[success, "acceptance_datetime_utc"], utc=True)
    if not announced.lt(accepted).all():
        raise ValueError("Earnings announcement not before 10-K acceptance")

    joined = joined.merge(accruals[[*KEY, "report_date", "status", "accruals",
                                    "accruals_numerator", "average_total_assets"]],
                          on=KEY, how="left", validate="one_to_one",
                          suffixes=("_tenk", "_accruals"))
    if joined.status_accruals.isna().any():
        raise ValueError("Accruals does not cover the current filing cohort")
    if not joined.report_date_tenk.eq(joined.report_date_accruals).all():
        raise ValueError("Accrual fiscal period differs from current cohort")
    passed = joined.status_accruals.eq("PASS")
    if joined.loc[passed, "accruals"].isna().any() or not np.allclose(
        joined.loc[passed, "accruals"],
        joined.loc[passed, "accruals_numerator"] / joined.loc[passed, "average_total_assets"],
        atol=1e-12, rtol=1e-10,
    ):
        raise ValueError("PASS Accruals value/arithmetic changed")
    joined["eadret_accepted"] = joined.eadret.where(success)
    joined["accruals_accepted"] = joined.accruals.where(passed)
    qa = {"input_filings": len(panel), "eadret_success": int(success.sum()),
          "accruals_pass": int(passed.sum()),
          "accruals_warn": int(joined.status_accruals.eq("WARN").sum()),
          "accruals_structural_missing": int(joined.status_accruals.eq("STRUCTURAL_MISSING").sum()),
          "eadret_arithmetic_mismatches": 0, "accession_mismatches": 0,
          "report_date_mismatches": 0}
    return joined, qa


def make_samples(panel: pd.DataFrame, c2: pd.DataFrame, c5: pd.DataFrame,
                 regression: pd.DataFrame, validated: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    extra = validated[[*KEY, "eadret_accepted", "accruals_accepted"]].rename(
        columns={"eadret_accepted": "eadret", "accruals_accepted": "accruals"})
    sample = c2.merge(panel[[*KEY, "accession_number"]],
                      on=KEY, validate="one_to_one")
    sample = sample.merge(regression[[*KEY, "lm_positive_prop", "lm_negative_prop"]],
                          on=KEY, validate="one_to_one")
    sample = sample.merge(extra, on=KEY, validate="one_to_one")
    sample = sample.dropna(subset=[*SIX, *WINDOWS]).copy()
    lag = c5.merge(extra, on=KEY, validate="one_to_one")
    lag = lag.dropna(subset=["lm_net_prop", "lag_tone", *SIX]).copy()
    return sample, lag


def write_report(qa: dict, matched4: pd.DataFrame, full: pd.DataFrame,
                 posneg: pd.DataFrame, c5: pd.DataFrame) -> None:
    labels = {"car_m1_p1": "[-1,+1]", "car_0_p3": "[0,+3]",
              "car_m3_p3": "[-3,+3]", "car_m5_p5": "[-5,+5]"}
    lines = []
    for y in WINDOWS:
        before = matched4.loc[matched4.dependent_variable.eq(y) &
                              matched4.term.eq("lm_net_prop")].iloc[0]
        after = full.loc[full.dependent_variable.eq(y) &
                         full.term.eq("lm_net_prop")].iloc[0]
        lines.append(f"| {labels[y]} | {before.coefficient:.4f} | {before.p_hc3_two_sided:.4f} | "
                     f"{after.coefficient:.4f} | {after.p_hc3_two_sided:.4f} | "
                     f"{after.p_cluster_two_sided:.4f} |")
    pos = posneg.loc[posneg.dependent_variable.eq("car_0_p3") &
                     posneg.term.eq("lm_positive_prop")].iloc[0]
    neg = posneg.loc[posneg.dependent_variable.eq("car_0_p3") &
                     posneg.term.eq("lm_negative_prop")].iloc[0]
    lag = c5.loc[c5.term.eq("z_lag_tone")].iloc[0]
    report = f"""# Bổ sung EADRet và Accruals vào mô hình hiện hành

Nguồn: hai CSV ở `data/metadata/controls/` được chép nguyên từ nhánh GitHub `finalize-eadret-accruals` (commit `0ee574c`). `EADRet` dùng phản ứng lợi suất quanh 8-K Item 2.02 trước ngày chấp nhận 10-K, điều chỉnh theo `^GSPC`; `Accruals` dùng các thành phần Sloan từ SEC Company Facts. Mã kiểm tra accession, kỳ báo cáo, thứ tự ngày, số học và trạng thái từng hàng trước khi ghép. Bốn controls còn lại và AR/CAR vẫn là phiên bản đang dùng trên `main`; không thay bằng bảng `controls_item7_final6.csv` ở nhánh khác vì quy tắc Size/BM/Turnover khác.

Trong 1.000 hồ sơ, `EADRet` có **{qa['eadret_success']}** hàng `success`. `Accruals` có **{qa['accruals_pass']}** hàng `PASS`, {qa['accruals_warn']} hàng `WARN` và {qa['accruals_structural_missing']} hàng thiếu cấu trúc. Chỉ `PASS` được vào mô hình chính; giá trị số ở hàng `WARN` không được xem như đã đạt chuẩn. Giao với mẫu bốn controls và CAR còn **{qa['six_control_complete_cases']} hồ sơ, {qa['six_control_firms']} công ty**. C5 có thêm điều kiện tone năm liền trước nên còn **{qa['c5_six_control_complete_cases']} hồ sơ**.

## C2 — sáu controls, tone LM net dạng tỷ lệ

`CAR = a + b·LM_net_prop + Size + BM + Volatility + Turnover + EADRet + Accruals + ε`. Hai cột bốn-controls bên trái được ước lượng lại **trên cùng {qa['six_control_complete_cases']} hồ sơ** để tách thay đổi đặc tả khỏi thay đổi cỡ mẫu. p HC3 và p cụm công ty của mô hình sáu controls đều nằm trong CSV.

| Cửa sổ | b bốn controls, cùng mẫu | p HC3 | b sáu controls | p HC3 | p cụm |
| --- | ---: | ---: | ---: | ---: | ---: |
{chr(10).join(lines)}

## C3 và C5 với sáu controls

C3 đưa đồng thời positive và negative tone **dạng tỷ lệ** vào mô hình với sáu controls. Ở `[0,+3]`, hệ số positive = {pos.coefficient:.4f} (p HC3 {pos.p_hc3_two_sided:.4f}, p cụm {pos.p_cluster_two_sided:.4f}); negative = {neg.coefficient:.4f} (p HC3 {neg.p_hc3_two_sided:.4f}, p cụm {neg.p_cluster_two_sided:.4f}). Đây chưa phải H1/H2 viết bằng Word Power.

C5 dùng tone hiện tại làm biến phụ thuộc, sáu controls và tone năm nộp liền trước, chuẩn hóa các biến giải thích trên mẫu hoàn chỉnh. Hệ số tone trễ chuẩn hóa = {lag.coefficient:.6f}, p HC3 = {lag.p_hc3_two_sided:.4g}, p cụm = {lag.p_cluster_two_sided:.4g}.

Hai bảng nguồn là dữ liệu đã tính sẵn từ nhánh khác. Kiểm tra ở đây xác nhận khóa, thời gian và số học nhưng không tái dựng độc lập mọi SEC Company Fact hay 8-K từ đầu. Cột `word_power` ở nhánh nguồn chỉ là TF-IDF chưa chuẩn hóa; không dùng cột đó trong các mô hình tỷ lệ của báo cáo này. Word Power ước lượng từ tần suất từng từ được báo riêng tại `word_power/RESULTS.md`. Các kết quả hồi quy mô tả liên hệ trong mẫu nhỏ hơn và không chứng minh tác động nhân quả.
"""
    (OUT / "FULL_CONTROLS_REVIEW.md").write_text(report, encoding="utf-8")


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    panel = pd.read_csv(OUT / "tone_firm_year.csv", dtype={"accession_number": str})
    earnings = pd.read_csv(SOURCE / "eadret_item7.csv", dtype={"tenk_accession": str})
    accruals = pd.read_csv(SOURCE / "accruals_item7.csv", dtype={"cik": str})
    validated, qa = load_controls(panel, earnings, accruals)
    c2 = pd.read_csv(OUT / "c2_reduced_sample.csv")
    c5 = pd.read_csv(OUT / "c5_reduced_sample.csv")
    regression = pd.read_csv(OUT / "regression/regression_sample.csv")
    sample, lag = make_samples(panel, c2, c5, regression, validated)
    qa.update({"current_four_control_sample": len(c2),
               "six_control_complete_cases": len(sample),
               "six_control_firms": int(sample.ticker.nunique()),
               "c5_six_control_complete_cases": len(lag),
               "c5_six_control_firms": int(lag.ticker.nunique())})
    sample.to_csv(OUT / "c2_full6_sample.csv", index=False)
    lag.to_csv(OUT / "c5_full6_sample.csv", index=False)
    matched4_rows, c2_rows, c3_rows = [], [], []
    for y in WINDOWS:
        matched4_rows.extend(fit_model(sample, y, ["lm_net_prop", *FOUR],
                                       "C2_LM_NetProp_4controls_matched_sample"))
        c2_rows.extend(fit_model(sample, y, ["lm_net_prop", *SIX],
                                 "C2_LM_NetProp_6controls"))
        c3_rows.extend(fit_model(sample, y, ["lm_positive_prop", "lm_negative_prop", *SIX],
                                 "C3_LM_PosNeg_6controls"))
    matched4 = pd.DataFrame(matched4_rows)
    full = pd.DataFrame(c2_rows)
    posneg = pd.DataFrame(c3_rows)
    matched4.to_csv(OUT / "c2_matched4_results.csv", index=False)
    full.to_csv(OUT / "c2_full6_results.csv", index=False)
    posneg.to_csv(OUT / "c3_posneg_full6_results.csv", index=False)
    for col in SIX + ["lag_tone"]:
        scale = lag[col].std(ddof=1)
        if not np.isfinite(scale) or scale <= 0:
            raise ValueError(f"Cannot standardize full C5 {col}")
        lag[f"z_{col}"] = (lag[col] - lag[col].mean()) / scale
    c5_rows = fit_model(lag, "lm_net_prop", [f"z_{x}" for x in SIX + ["lag_tone"]],
                        "C5_LM_NetProp_6controls_lag_tone")
    c5_results = pd.DataFrame(c5_rows)
    c5_results.to_csv(OUT / "c5_full6_results.csv", index=False)
    write_report(qa, matched4, full, posneg, c5_results)
    (OUT / "full_controls_qa.json").write_text(
        json.dumps(qa, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(qa, ensure_ascii=False))


if __name__ == "__main__":
    main()
