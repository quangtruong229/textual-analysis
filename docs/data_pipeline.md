# Luồng xử lý dữ liệu

## Phạm vi chạy từ repo

Chạy `python scripts/run_analysis.py` từ thư mục gốc sau khi cài `requirements.txt`. Lệnh này dùng dữ liệu đã có trong repo, không gọi SEC hoặc Yahoo Finance. Mỗi quan sát được nhận diện bằng công ty và ngày nộp; các phép ghép hồ sơ còn kiểm tra accession khi có cột này. Năm trên bảng công ty–năm là `filing_year`; `report_year` được giữ riêng.

| Bước | Đầu vào | Xử lý và đầu ra hiện hành |
| --- | --- | --- |
| Nghiên cứu sự kiện | `data/metadata/tone_method_item7.csv`, `data/market_data/daily_prices.csv` | `scripts/recompute_from_supplied.py --force-event` tính mô hình thị trường, AR theo ngày và CAR theo bốn cửa sổ; ghi `analysis_outputs/event_study/` |
| Hồi quy C1/C3/C4 | Bảng tone được cung cấp và CAR vừa tính | Cùng lệnh trên chạy `src/regression_analysis.py`; ghi kết quả, mẫu và thống kê mô tả vào `analysis_outputs/regression/` |
| C2 rút gọn | Mẫu hồi quy hiện hành và `data/metadata/controls/controls_item7.csv` | `scripts/calculate_c2_controls.py` ghép Size, BM, Volatility, Turnover; ghi `analysis_outputs/c2_reduced_results.csv` và `c2_reduced_sample.csv` |
| Bảng công ty–năm nộp | Metadata hồ sơ, bảng tone được cung cấp và CAR hiện hành | `scripts/build_firm_year_panel.py` giữ toàn bộ hồ sơ, đánh dấu phần có/thiếu tone và CAR; ghi `analysis_outputs/tone_firm_year.csv` |
| So sánh từ điển | `data/metadata/tone_method_item7.csv` | `scripts/summarize_dictionary_comparison.py` xuất bảng từng hồ sơ và tổng hợp LM/Harvard vào `analysis_outputs/` |
| Kiểm tra và trình bày | Các đầu vào và đầu ra trên | Các script kiểm tra số học, khóa và độ phủ dữ liệu, tổng AR thành CAR, sự nhất quán giữa các bảng; lưu `analysis_outputs/verification.json`, `handoff/manifest.json` và `analysis_outputs/RESULTS_PRESENTATION.md` |

`run_analysis.py` quản lý thứ tự các bước. Nếu một bước lỗi, cần xử lý lỗi đó trước khi sử dụng đầu ra; không ghép bảng mới và bảng cũ thành một bộ kết quả.

## Nguồn kết quả chính thức

Các bảng trong `analysis_outputs/` là kết quả dùng để đọc, trình bày và tích hợp. Các phép kiểm tra dựa trên công thức, cửa sổ thời gian, lịch giao dịch và tính nhất quán giữa các đầu ra.

CAR, CAAR và AAR là lợi suất dạng thập phân: `0.01` tương ứng `1%`. Ô thiếu nghĩa là không có phép đo và không được thay bằng 0. Các CSV hồi quy chứa mô hình của mẫu đã lưu; lọc dòng để hiển thị không đồng nghĩa ước lượng lại mô hình.

## Bảng đầu vào

`run_analysis.py` sử dụng các bảng đầu vào được liệt kê ở trên và không tải thêm dữ liệu. Mã thu thập báo cáo và giá nằm trong `src/` để nhóm quản lý riêng với luồng tính kết quả. Mỗi đầu ra trong `analysis_outputs/` có thể đối chiếu với bảng đầu vào và mã xử lý tương ứng.
