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


def results_markdown(
    panel: pd.DataFrame,
    comparison_summary: pd.Series,
    event_summary: pd.DataFrame,
    regression: pd.DataFrame,
    c2: pd.DataFrame,
) -> str:
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

## Phản ứng giá quanh ngày nộp 10-K

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

Ở `[-1,+1]`, hệ số **{dec(baseline.coefficient, 4)}**, p HC3 **{pvalue(baseline.p_hc3_two_sided)}** và p gom cụm **{pvalue(baseline.p_cluster_two_sided)}**. Với ngưỡng 5%, đặc tả này **chưa cho bằng chứng thống kê đủ mạnh** rằng tone LM dự báo CAR. Cửa sổ `[-3,+3]` có p HC3 **{pvalue(longer.p_hc3_two_sided)}**, nhưng p gom cụm là **{pvalue(longer.p_cluster_two_sided)}**; kết luận phụ thuộc cách tính sai số chuẩn và cửa sổ được chọn. Vì có nhiều đặc tả, không nên coi một p-value đơn lẻ là xác nhận chắc chắn.

## So sánh từ điển tài chính và từ điển tổng quát

Trên **{comparable} hồ sơ** tính được cả hai điểm theo cùng quy tắc xử lý, LM và Harvard IV-4 cho tone **trái dấu ở {opposite} hồ sơ ({dec(100 * opposite / comparable, 1)}%)**. Đây là khác biệt đáng kể về cách hai từ điển mô tả cùng văn bản, nhưng **không phải {opposite} lỗi được kiểm chứng của Harvard**. ZIP không có văn bản Item 7 để gắn nhãn thủ công cho từ trong ngữ cảnh.

Ở hồi quy C4 `[-1,+1]` đưa đồng thời hai tone tỷ lệ vào mô hình, hệ số LM là **{dec(c4_lm.coefficient, 4)}** (p HC3 **{pvalue(c4_lm.p_hc3_two_sided)}**), còn Harvard là **{dec(c4_harvard.coefficient, 4)}** (p HC3 **{pvalue(c4_harvard.p_hc3_two_sided)}**). Kết quả này **không cho phép khẳng định LM luôn dự báo tốt hơn**; cần đối chiếu thêm giả thuyết, dấu hệ số và dữ liệu gốc trước khi nêu kết luận mạnh.

## C2 rút gọn với biến kiểm soát

C2 dùng `LM_net_prop`, Size, BM, Volatility và Turnover. Hai biến EADRet và Accruals trong công thức đầy đủ không có trong ZIP. Do yêu cầu dữ liệu đủ bốn biến kiểm soát, mẫu giảm từ {int(baseline.n)} xuống **{int(c2_baseline.n)} hồ sơ**. Bảng dưới chỉ hiển thị hệ số tone; toàn bộ hệ số của bốn biến kiểm soát có trong `c2_reduced_results.csv` và tab Hồi quy.

| Cửa sổ | N | Hệ số tone | p HC3 | Khoảng tin cậy HC3 95% | p gom cụm |
| --- | ---: | ---: | ---: | --- | ---: |
{chr(10).join(c2_rows)}

Ở `[-1,+1]`, hệ số tone C2 là **{dec(c2_baseline.coefficient, 4)}**, p HC3 **{pvalue(c2_baseline.p_hc3_two_sided)}**. Đây là mô hình **rút gọn**, và sự khác biệt với C1 vừa phản ánh thêm biến kiểm soát vừa phản ánh mẫu nhỏ hơn; không thể tách hai tác động chỉ bằng hai bảng này.

## Kết luận sử dụng được và giới hạn

Dữ liệu cho thấy có phản ứng lợi suất bất thường trung bình quanh ngày nộp 10-K và tone khác nhau đáng kể giữa hai từ điển. Mối liên hệ riêng giữa tone LM và CAR **không ổn định qua cửa sổ và cách tính sai số chuẩn**, nên chưa có cơ sở để nói tone gây ra biến động giá. Phần chi tiết cách tính nằm ở tab **Phương pháp**; trạng thái thiếu dữ liệu và khả năng chạy lại nằm ở tab **Kiểm tra**. Việc không có HTML/MD&A gốc giới hạn kiểm chứng bước trích và đếm từ, còn C2 đầy đủ cần thêm EADRet và Accruals.
"""
