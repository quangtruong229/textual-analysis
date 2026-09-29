"""Minimal local viewer for the supplied and recalculated research CSVs.

This app does not scrape filings or rerun statistical models. Run the scripts
in README.md first if the calculation outputs need refreshing.
"""

from pathlib import Path

import pandas as pd
import streamlit as st
from presentation import results_markdown


ROOT = Path(__file__).resolve().parent
OUT = ROOT / "analysis_outputs"

st.set_page_config(page_title="Nhóm 5 · Kết quả tính toán", layout="wide")


@st.cache_data(show_spinner=False)
def read_csv(relative_path: str) -> pd.DataFrame:
    path = ROOT / relative_path
    return pd.read_csv(path)


required = [
    "analysis_outputs/tone_firm_year.csv",
    "analysis_outputs/dictionary_comparison_summary.csv",
    "analysis_outputs/dictionary_comparison_filings.csv",
    "analysis_outputs/event_study/event_study_summary.csv",
    "analysis_outputs/event_study/event_daily_summary.csv",
    "analysis_outputs/regression/regression_results.csv",
    "analysis_outputs/c2_reduced_results.csv",
]
missing = [name for name in required if not (ROOT / name).exists()]
if missing:
    st.error("Thiếu bảng kết quả: " + ", ".join(missing))
    st.stop()

panel = read_csv("analysis_outputs/tone_firm_year.csv")
comparison_summary = read_csv("analysis_outputs/dictionary_comparison_summary.csv").iloc[0]
comparison = read_csv("analysis_outputs/dictionary_comparison_filings.csv")
event_summary = read_csv("analysis_outputs/event_study/event_study_summary.csv")
daily = read_csv("analysis_outputs/event_study/event_daily_summary.csv")
regression = read_csv("analysis_outputs/regression/regression_results.csv")
c2 = read_csv("analysis_outputs/c2_reduced_results.csv")

st.title("Nhóm 5 · Kết quả phân tích 10-K")
st.caption("Trang local đọc bảng kết quả có sẵn. Năm trong bộ lọc là năm nộp 10-K, không nhất thiết là năm tài chính.")

overview, results_tab, method_tab, tone_tab, dictionary_tab, event_tab, model_tab, audit_tab = st.tabs([
    "Tổng quan", "Kết quả & diễn giải", "Phương pháp", "Tone công ty–năm",
    "LM và Harvard", "AR/CAR", "Hồi quy", "Kiểm tra",
])

with overview:
    a, b, c, d = st.columns(4)
    a.metric("Hồ sơ 10-K", len(panel))
    b.metric("Có tone Item 7", int(panel.has_method_score.sum()))
    c.metric("Có CAR", int(panel.has_event_car.sum()))
    d.metric("Mẫu C2 rút gọn", int(c2.n.iloc[0]))
    st.write("**Phạm vi:** 100 công ty × 10 năm nộp 2016–2025. Tone thiếu ở 29 hồ sơ; CAR thiếu ở 31 hồ sơ.")
    st.info("Các số trong tab AR/CAR và Hồi quy là kết quả toàn mẫu. Bộ lọc ở tab Tone chỉ thay bảng hồ sơ.")
    st.dataframe(event_summary[["window", "N", "CAAR", "MacKinlay_Z", "MacKinlay_p"]],
                 hide_index=True, width="stretch")

with results_tab:
    narrative = results_markdown(panel, comparison_summary, event_summary, regression, c2)
    st.markdown(narrative)
    st.download_button("Tải phần trình bày kết quả", narrative.encode("utf-8"),
                       file_name="Ket_qua_va_dien_giai.md", mime="text/markdown")

with method_tab:
    method = (ROOT / "docs/METHODOLOGY.md").read_text(encoding="utf-8")
    st.markdown(method)
    st.download_button("Tải phần phương pháp", method.encode("utf-8"),
                       file_name="Phuong_phap.md", mime="text/markdown")

with tone_tab:
    ticker = st.selectbox("Doanh nghiệp", ["Tất cả", *sorted(panel.ticker.unique())])
    year = st.selectbox("Năm nộp", ["Tất cả", *sorted(panel.filing_year.unique())])
    shown = panel
    if ticker != "Tất cả":
        shown = shown.loc[shown.ticker.eq(ticker)]
    if year != "Tất cả":
        shown = shown.loc[shown.filing_year.eq(year)]
    columns = ["ticker", "company_name", "filing_year", "report_date",
               "filing_date", "item_7_mda_lm_status", "lm_net_prop",
               "harvard_net_prop", "CAR_m1_p1", "has_method_score", "has_event_car", "sec_url"]
    st.dataframe(shown[columns], hide_index=True, width="stretch")
    st.caption(f"Đang hiển thị {len(shown)} hồ sơ. Ô trống nghĩa là không có số đo; không phải tone hoặc CAR bằng 0.")
    st.download_button("Tải toàn bộ bảng công ty–năm", (OUT / "tone_firm_year.csv").read_bytes(),
                       file_name="tone_firm_year.csv", mime="text/csv")

with dictionary_tab:
    a, b = st.columns(2)
    a.metric("Hồ sơ so sánh được", int(comparison_summary.n_comparable_filings))
    b.metric("LM và Harvard trái dấu", f"{int(comparison_summary.n_opposite_sign)} ({100 * comparison_summary.share_opposite_sign:.1f}%)")
    st.caption("Trái dấu chứng tỏ hai từ điển cho kết quả khác nhau; chưa xác định từ điển nào đúng cho từng ngữ cảnh.")
    st.dataframe(comparison[["ticker", "filing_date", "lm_net_prop", "harvard_net_prop",
                             "harvard_minus_lm", "opposite_sign"]],
                 hide_index=True, width="stretch")

with event_tab:
    st.write("Nghiên cứu sự kiện trên 969 filing có đủ tone và lịch sử giá.")
    st.dataframe(event_summary, hide_index=True, width="stretch")
    st.write("Lợi suất bất thường trung bình theo ngày giao dịch tương đối:")
    st.line_chart(daily.set_index("event_time")["AAR"], x_label="Ngày giao dịch tương đối", y_label="AAR")
    st.dataframe(daily, hide_index=True, width="stretch")

with model_tab:
    st.subheader("C1, C3, C4 · bảng tính lại")
    family = st.selectbox("Nhóm mô hình", sorted(regression.section.unique()))
    outcome = st.selectbox("Cửa sổ CAR", sorted(regression.dependent_variable.unique()))
    subset = regression.loc[regression.section.eq(family) & regression.dependent_variable.eq(outcome)]
    st.dataframe(subset[["model", "term", "n", "coefficient", "se_hc3", "p_hc3_two_sided",
                         "se_cluster", "p_cluster_two_sided", "r_squared"]],
                 hide_index=True, width="stretch")
    st.subheader("C2 rút gọn · bốn biến kiểm soát")
    st.caption("N = 862, 96 công ty. EADRet và Accruals không có trong ZIP.")
    st.dataframe(c2[["dependent_variable", "term", "n", "coefficient", "se_hc3",
                     "p_hc3_two_sided", "ci_hc3_low", "ci_hc3_high", "p_cluster_two_sided"]],
                 hide_index=True, width="stretch")

with audit_tab:
    st.write("Đối chiếu dữ liệu gốc với bảng chạy lại và các giới hạn:")
    st.markdown((OUT / "ASSIGNMENT_AUDIT.md").read_text(encoding="utf-8"))
    st.download_button("Tải bảng hồ sơ thiếu tone/CAR", (OUT / "missing_filings.csv").read_bytes(),
                       file_name="missing_filings.csv", mime="text/csv")
