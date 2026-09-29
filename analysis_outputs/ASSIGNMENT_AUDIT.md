# Kiểm tra bộ kết quả tính toán

Bộ kết quả hiện hành nằm trong `analysis_outputs/`. Chạy `python scripts/run_analysis.py` để tạo lại các bảng từ dữ liệu đầu vào và thực hiện kiểm tra tự động. `verification.json` ghi số quan sát, phép đối chiếu và mã SHA-256 của các bảng đầu vào.

| Nội dung | Bảng kết quả | Kiểm tra |
| --- | --- | --- |
| Hồ sơ và tone theo công ty–năm nộp | `tone_firm_year.csv` | 1.000 hồ sơ, 100 công ty, một hàng cho mỗi công ty và năm nộp 2016–2025; 971 hàng có tone |
| Nghiên cứu sự kiện | `event_study/event_filing_results.csv`, `event_ar_long.csv`, `event_study_summary.csv` | 969 hồ sơ có CAR; 969 ngày `0` khớp ngày sự kiện; 10.659 hàng AR khớp lịch phiên thị trường; CAR bằng tổng AR của từng cửa sổ |
| So sánh từ điển | `dictionary_comparison_filings.csv`, `dictionary_comparison_summary.csv` | 971 hồ sơ có cả điểm LM và Harvard IV-4; số học tone tỷ lệ khớp các cột đếm từ |
| Hồi quy C1/C3/C4 | `regression/regression_results.csv`, `regression_sample.csv` | 969 quan sát trong mẫu hồi quy; hệ số và mẫu gắn với bốn cửa sổ CAR |
| C2 với bốn biến kiểm soát | `c2_reduced_results.csv`, `c2_reduced_sample.csv` | 862 quan sát thuộc 96 công ty; dùng Size, BM, Volatility và Turnover |

`missing_filings.csv` và `event_study/event_exclusions.csv` ghi trạng thái hồ sơ không có đủ số đo cho từng bước. Ô trống trong bảng kết quả là dữ liệu không có số đo, không được thay bằng 0. `filing_year` là năm nộp hồ sơ; `report_year` là năm kết thúc kỳ báo cáo.
