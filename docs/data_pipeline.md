# Luồng xử lý dữ liệu

## Phạm vi chạy từ repo

Chạy `python scripts/run_analysis.py` từ thư mục gốc sau khi cài `requirements.txt`. Lệnh này dùng dữ liệu đã có trong repo, không gọi SEC hoặc Yahoo Finance. Mỗi quan sát được nhận diện bằng công ty và ngày nộp; các phép ghép hồ sơ còn kiểm tra accession khi có cột này. Năm trên bảng công ty–năm là `filing_year`; `report_year` được giữ riêng.

| Bước | Đầu vào | Xử lý và đầu ra hiện hành |
| --- | --- | --- |
| Nghiên cứu sự kiện | `data/metadata/tone_method_item7.csv`, `data/metadata/filing_acceptance.csv`, `data/market_data/daily_prices.csv` | `scripts/recompute_from_supplied.py --force-event` gán ngày 0 theo giờ SEC chấp nhận hồ sơ và giờ đóng cửa NYSE, tính mô hình thị trường, AR và CAR; ghi `analysis_outputs/event_study/` |
| Kiểm định sự kiện bổ sung | AR của 239 ngày ước lượng và 11 ngày sự kiện | `scripts/extended_event_tests.py` ghi Brown–Warner cho bốn cửa sổ, B7, Corrado theo ngày và bảng B8 lý thuyết vào `analysis_outputs/event_study/` |
| Hồi quy C1/C3/C4 | Bảng tone được cung cấp và CAR vừa tính | Cùng lệnh trên chạy `src/regression_analysis.py`; ghi kết quả, mẫu và thống kê mô tả vào `analysis_outputs/regression/` |
| C2 rút gọn | Mẫu hồi quy hiện hành và `data/metadata/controls/controls_item7.csv` | `scripts/calculate_c2_controls.py` ghép Size, BM, Volatility, Turnover; giá và số cổ phiếu được đưa về cùng cơ sở chia tách bằng `data/market_data/stock_splits.csv`; ghi `analysis_outputs/c2_reduced_results.csv` và `c2_reduced_sample.csv` |
| Bảng công ty–năm nộp | Metadata hồ sơ, bảng tone được cung cấp và CAR hiện hành | `scripts/build_firm_year_panel.py` giữ toàn bộ hồ sơ, đánh dấu phần có/thiếu tone và CAR; ghi `analysis_outputs/tone_firm_year.csv` |
| Độ vững B6, C5–C8 | AR ước lượng/sự kiện, bảng công ty–năm, controls, giá và mẫu hồi quy | `scripts/optional_robustness.py` ghi các bảng B6, C5 rút gọn, C6 phản ứng chậm, C7 AR ngày 0 và C8 theo năm; giải thích trong `analysis_outputs/ROBUSTNESS_RESULTS.md` |
| So sánh từ điển | `data/metadata/tone_method_item7.csv` | `scripts/summarize_dictionary_comparison.py` xuất bảng từng hồ sơ và tổng hợp LM/Harvard vào `analysis_outputs/` |
| Kiểm tra và trình bày | Các đầu vào và đầu ra trên | Các script kiểm tra số học, khóa và độ phủ dữ liệu, tổng AR thành CAR, sự nhất quán giữa các bảng; hàm ý tài chính được tạo lại từ hệ số và p-value hiện hành; lưu `analysis_outputs/verification.json`, `handoff/manifest.json` và `analysis_outputs/RESULTS_PRESENTATION.md` |

`run_analysis.py` quản lý thứ tự các bước. Nếu một bước lỗi, cần xử lý lỗi đó trước khi sử dụng đầu ra; không ghép bảng mới và bảng cũ thành một bộ kết quả.

Hai bảng bổ sung `filing_acceptance.csv` và `stock_splits.csv` được lưu sẵn để chạy phân tích offline. Khi cập nhật dữ liệu nguồn, đặt `SEC_USER_AGENT` thành tên nhóm và email liên hệ rồi chạy lần lượt `src/download_filing_acceptance.py`, `src/download_stock_splits.py`, `scripts/recompute_from_supplied.py --force-event`, `src/build_controls.py` và `scripts/run_analysis.py --reuse-event`. Bước nghiên cứu sự kiện đồng bộ bảng hồ sơ sang `data/metadata/event_study_final/` để bước tạo controls luôn dùng đúng mẫu mới.

## Nguồn kết quả chính thức

Các bảng trong `analysis_outputs/` là kết quả dùng để đọc, trình bày và tích hợp. Các phép kiểm tra dựa trên công thức, cửa sổ thời gian, lịch giao dịch và tính nhất quán giữa các đầu ra.

CAR, CAAR và AAR là lợi suất dạng thập phân: `0.01` tương ứng `1%`. Ô thiếu nghĩa là không có phép đo và không được thay bằng 0. Các CSV hồi quy chứa mô hình của mẫu đã lưu; lọc dòng để hiển thị không đồng nghĩa ước lượng lại mô hình.

## Bảng đầu vào

`run_analysis.py` sử dụng các bảng đầu vào được liệt kê ở trên và không tải thêm dữ liệu. Mã thu thập báo cáo và giá nằm trong `src/` để nhóm quản lý riêng với luồng tính kết quả. Mỗi đầu ra trong `analysis_outputs/` có thể đối chiếu với bảng đầu vào và mã xử lý tương ứng.
