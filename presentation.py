"""Build a Vietnamese results narrative from saved calculation tables."""

from __future__ import annotations

import pandas as pd


WINDOW_LABELS = {
    "CAR_m1_p1": "[-1,+1]",
    "CAR_0_p3": "[0,+3]",
    "CAR_m3_p3": "[-3,+3]",
    "CAR_m5_p5": "[-5,+5]",
}


def dec(value: float, digits: int = 4) -> str:
    return f"{float(value):.{digits}f}".replace(".", ",")


def pvalue(value: float) -> str:
    if pd.isna(value):
        return "—"
    return "<0,0001" if float(value) < 0.0001 else dec(value, 4)


def financial_implications(regression: pd.DataFrame, c2: pd.DataFrame,
                           event_summary: pd.DataFrame, daily: pd.DataFrame | None = None) -> str:
    """Describe observed directions without turning associations into causal claims."""
    model = "C3_CAR_0_p3_LM_PosNeg"
    def coefficient(term: str):
        rows = regression.loc[regression.model.eq(model) & regression.term.eq(term)]
        if len(rows) != 1:
            raise ValueError(f"Missing {model}: {term}")
        return rows.iloc[0]

    def direction(row, expected_positive: bool, label: str) -> str:
        beta = float(row.coefficient)
        sign = "tăng" if beta > 0 else "giảm"
        effect_pp = beta  # A 0.01 tone increase changes decimal CAR by 0.01*beta.
        both = float(row.p_hc3_two_sided) < .05 and float(row.p_cluster_two_sided) < .05
        expected = beta > 0 if expected_positive else beta < 0
        if both and expected:
            verdict = "cùng chiều kỳ vọng của giả thuyết"
        elif both:
            verdict = "ngược chiều kỳ vọng của giả thuyết"
        else:
            verdict = "chưa có bằng chứng ổn định ở ngưỡng 5% với cả hai loại sai số chuẩn"
        return (f"{label} tăng 1 điểm phần trăm đi kèm CAR [0,+3] {sign} khoảng "
                f"{dec(abs(effect_pp), 3)} điểm phần trăm trong hồi quy C3 (p HC3 "
                f"{pvalue(row.p_hc3_two_sided)}, p theo cụm "
                f"{pvalue(row.p_cluster_two_sided)}); dấu ước lượng {verdict}.")

    pos = direction(coefficient("lm_positive_prop"), True, "Tone tích cực LM dạng tỷ lệ")
    neg = direction(coefficient("lm_negative_prop"), False, "Tone tiêu cực LM dạng tỷ lệ")
    car = event_summary.loc[event_summary.window.eq("CAR_0_p3")].iloc[0]
    ar_sentence = ""
    if daily is not None:
        day0 = daily.loc[daily.event_time.eq(0)]
        if len(day0) == 1:
            ar = float(day0.iloc[0].AAR)
            ar_sentence = f" AR trung bình ngày 0 là {dec(100 * ar, 3)}%."
    controls = c2.loc[c2.dependent_variable.eq("car_0_p3") &
                      c2.term.isin(["size", "bm", "volatility", "turnover"])]
    significant = controls.loc[(controls.p_hc3_two_sided < .05) &
                               (controls.p_cluster_two_sided < .05)]
    if significant.empty:
        control_sentence = "Không biến kiểm soát nào có p < 0,05 theo cả HC3 và cụm công ty trong C2 [0,+3]."
    else:
        descriptions = [f"{r.term} ({'dương' if r.coefficient > 0 else 'âm'})" for r in significant.itertuples()]
        control_sentence = ("Trong C2 rút gọn [0,+3], các biến kiểm soát có p < 0,05 "
                            "theo cả HC3 và cụm công ty là " + ", ".join(descriptions) + ".")
    return (f"CAR trung bình [0,+3] của mẫu là {dec(100 * car.CAAR, 3)}%.{ar_sentence} "
            "Đây là phản ứng chung quanh công bố, chưa quy cho tone.\n\n"
            f"{pos}\n\n{neg}\n\n{control_sentence} "
            "Các hệ số là quan hệ trong mẫu; không suy ra giao dịch sinh lời hay tác động nhân quả. "
            "Word Power chưa được tính từ văn bản gốc, nên H1 viết theo ScorePos Word Power chưa được kiểm định.")


def results_markdown(
    panel: pd.DataFrame,
    comparison_summary: pd.Series,
    event_summary: pd.DataFrame,
    regression: pd.DataFrame,
    c2: pd.DataFrame,
    daily: pd.DataFrame | None = None,
    extended: pd.DataFrame | None = None,
) -> str:
    implications = financial_implications(regression, c2, event_summary, daily)
    extended_text = ""
    if extended is not None:
        rows = []
        for r in extended.itertuples():
            rows.append(f"| {WINDOW_LABELS[r.window]} | {dec(r.brown_warner_z, 3)} | "
                        f"{pvalue(r.brown_warner_p)} | {pvalue(r.autocorr_p)} |")
        extended_text = ("\n\n## Kiểm định bổ sung\n\n"
                         "Brown–Warner A.11 và bản hiệu chỉnh tự tương quan B7 được tính cho cả bốn cửa sổ. "
                         "Corrado được tính theo từng ngày; bảng sức mạnh B8 là kịch bản lý thuyết cho CAAR, "
                         "không phải sức mạnh kiểm định H1 tone.\n\n"
                         "| Cửa sổ | Z Brown–Warner | p Brown–Warner | p sau hiệu chỉnh B7 |\n"
                         "| --- | ---: | ---: | ---: |\n" + "\n".join(rows))
    event_rows = []
    for _, row in event_summary.iterrows():
        event_rows.append(
            f"| {WINDOW_LABELS.get(row.window, row.window)} | {int(row.N)} | "
            f"{dec(100 * row.CAAR, 3)}% | {dec(row.MacKinlay_Z, 3)} | "
            f"{pvalue(row.MacKinlay_p)} | {pvalue(row.Sign_p)} |"
        )

    c1_rows = []
    for code, label in WINDOW_LABELS.items():
        model = f"C1_{code}_LM_NetProp"
        row = regression.loc[regression.model.eq(model) & regression.term.eq("lm_net_prop")]
        if len(row) != 1:
            raise ValueError(f"Expected exactly one result for {model}")
        r = row.iloc[0]
        c1_rows.append(
            f"| {label} | {int(r.n)} | {dec(r.coefficient, 4)} | "
            f"{pvalue(r.p_hc3_two_sided)} | {pvalue(r.p_cluster_two_sided)} |"
        )

    c2_rows = []
    for code, label in WINDOW_LABELS.items():
        target = code.lower()
        row = c2.loc[c2.dependent_variable.eq(target) & c2.term.eq("lm_net_prop")]
        if len(row) != 1:
            raise ValueError(f"Expected exactly one reduced C2 result for {target}")
        r = row.iloc[0]
        c2_rows.append(
            f"| {label} | {int(r.n)} | {dec(r.coefficient, 4)} | "
            f"{pvalue(r.p_hc3_two_sided)} | [{dec(r.ci_hc3_low, 4)}; {dec(r.ci_hc3_high, 4)}] | "
            f"{pvalue(r.p_cluster_two_sided)} |"
        )

    baseline = regression.loc[
        regression.model.eq("C1_CAR_m1_p1_LM_NetProp") & regression.term.eq("lm_net_prop")
    ].iloc[0]
    longer = regression.loc[
        regression.model.eq("C1_CAR_m3_p3_LM_NetProp") & regression.term.eq("lm_net_prop")
    ].iloc[0]
    c4 = regression.loc[
        regression.model.eq("C4_CAR_m1_p1_LM_vs_Harvard_Prop")
        & regression.term.isin(["lm_net_prop", "harvard_net_prop"])
    ]
    c4_lm = c4.loc[c4.term.eq("lm_net_prop")].iloc[0]
    c4_harvard = c4.loc[c4.term.eq("harvard_net_prop")].iloc[0]
    c2_baseline = c2.loc[
        c2.dependent_variable.eq("car_m1_p1") & c2.term.eq("lm_net_prop")
    ].iloc[0]
    opposite = int(comparison_summary.n_opposite_sign)
    comparable = int(comparison_summary.n_comparable_filings)
    report_year_2015 = int(panel.report_year.lt(2016).sum())

    return f"""# Kết quả và diễn giải

## Mẫu thực nghiệm

Danh sách đầu vào gồm **{len(panel):,} hồ sơ của {panel.ticker.nunique()} công ty**, mỗi công ty có một báo cáo cho từng **năm nộp** 2016–2025. Item 7 đủ điều kiện tạo điểm tone ở **{int(panel.has_method_score.sum())} hồ sơ**; **{int(panel.has_event_car.sum())} hồ sơ** có thêm AR/CAR. C2 rút gọn còn **{int(c2_baseline.n)} hồ sơ thuộc {int(c2_baseline.n_firms)} công ty** sau khi đòi hỏi đủ bốn biến kiểm soát. Có {report_year_2015} hồ sơ nộp năm 2016 với kỳ báo cáo kết thúc năm 2015; vì vậy “năm nộp” phải được phân biệt với “năm tài chính”.

## Phản ứng giá quanh ngày công bố 10-K

CAAR là CAR trung bình của các hồ sơ trong mẫu. Bảng này kiểm tra phản ứng trung bình quanh sự kiện, **không phải** hệ số của tone.

| Cửa sổ giao dịch | N | CAAR | Z MacKinlay | p MacKinlay | p kiểm định dấu |
| --- | ---: | ---: | ---: | ---: | ---: |
{chr(10).join(event_rows)}

Chẳng hạn ở cửa sổ `[-1,+1]`, CAAR = **{dec(100 * event_summary.loc[event_summary.window.eq('CAR_m1_p1'), 'CAAR'].iloc[0], 3)}%** và p MacKinlay = **{pvalue(event_summary.loc[event_summary.window.eq('CAR_m1_p1'), 'MacKinlay_p'].iloc[0])}**. Điều này cho thấy lợi suất bất thường trung bình khác 0 theo phép kiểm định đó. Nó không cho biết phần nào do giọng điệu báo cáo, công bố lợi nhuận gần thời điểm đó, hay tin khác.

## Tone LM và CAR: hồi quy C1

Hệ số dưới đây thuộc mô hình `CAR = a + b × LM_net_prop + sai số`, với sai số chuẩn HC3 và đối chứng gom cụm theo công ty. Tone dương hơn tương ứng `LM_net_prop` lớn hơn. Bảng trình bày **cả bốn cửa sổ**, không chọn riêng cửa sổ có p nhỏ.

| Cửa sổ | N | Hệ số b | p HC3 hai phía | p gom cụm công ty |
| --- | ---: | ---: | ---: | ---: |
{chr(10).join(c1_rows)}

Ở `[-1,+1]`, hệ số **{dec(baseline.coefficient, 4)}**, p HC3 **{pvalue(baseline.p_hc3_two_sided)}** và p gom cụm **{pvalue(baseline.p_cluster_two_sided)}**. Với ngưỡng 5%, đặc tả này **chưa cho bằng chứng thống kê đủ mạnh** rằng tone LM dự báo CAR. Ở `[-3,+3]`, hệ số mang dấu âm và có p HC3 **{pvalue(longer.p_hc3_two_sided)}**, p gom cụm **{pvalue(longer.p_cluster_two_sided)}**. Kết quả giữa các cửa sổ không nhất quán; vì có nhiều đặc tả, không nên coi một p-value đơn lẻ là xác nhận chắc chắn.

## So sánh từ điển tài chính và từ điển tổng quát

Trên **{comparable} hồ sơ** tính được cả hai điểm theo cùng quy tắc xử lý, LM và Harvard IV-4 cho tone **trái dấu ở {opposite} hồ sơ ({dec(100 * opposite / comparable, 1)}%)**. Kết quả cho thấy hai từ điển cho điểm khác nhau; chỉ số trái dấu không phải phép đánh giá đúng/sai của từng từ điển.

Ở hồi quy C4 `[-1,+1]` đưa đồng thời hai tone tỷ lệ vào mô hình, hệ số LM là **{dec(c4_lm.coefficient, 4)}** (p HC3 **{pvalue(c4_lm.p_hc3_two_sided)}**), còn Harvard là **{dec(c4_harvard.coefficient, 4)}** (p HC3 **{pvalue(c4_harvard.p_hc3_two_sided)}**). Kết quả này **không cho phép khẳng định LM luôn dự báo tốt hơn**; cần đối chiếu thêm giả thuyết, dấu hệ số và dữ liệu gốc trước khi nêu kết luận mạnh.

## C2 rút gọn với biến kiểm soát

C2 trong bảng dùng `LM_net_prop`, Size, BM, Volatility và Turnover. Do yêu cầu dữ liệu đủ bốn biến kiểm soát, mẫu gồm **{int(c2_baseline.n)} hồ sơ**. Bảng dưới chỉ hiển thị hệ số tone; toàn bộ hệ số của bốn biến kiểm soát có trong `c2_reduced_results.csv` và tab Hồi quy.

| Cửa sổ | N | Hệ số tone | p HC3 | Khoảng tin cậy HC3 95% | p gom cụm |
| --- | ---: | ---: | ---: | --- | ---: |
{chr(10).join(c2_rows)}

Ở `[-1,+1]`, hệ số tone C2 là **{dec(c2_baseline.coefficient, 4)}**, p HC3 **{pvalue(c2_baseline.p_hc3_two_sided)}**. Đây là mô hình **rút gọn**, và sự khác biệt với C1 vừa phản ánh thêm biến kiểm soát vừa phản ánh mẫu nhỏ hơn; không thể tách hai tác động chỉ bằng hai bảng này.

## Hàm ý tài chính theo kết quả hiện tại

{implications}
{extended_text}
"""
