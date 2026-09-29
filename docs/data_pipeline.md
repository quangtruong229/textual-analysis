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

Các bảng trong `analysis_outputs/` là kết quả hiện hành để đọc, trình bày và tích hợp. Các bảng sự kiện/hồi quy ban đầu trong `data/metadata/event_study_final/` và `data/metadata/regression_analysis/` chỉ dùng đối chiếu lịch sử. Sau khi sửa phương pháp, hai bộ có thể khác nhau. Việc kiểm tra phải dựa vào công thức, cửa sổ thời gian và tính nhất quán của đầu ra, không buộc kết quả mới trùng bản cũ.

CAR, CAAR và AAR là lợi suất dạng thập phân: `0.01` tương ứng `1%`. Ô thiếu nghĩa là không có phép đo và không được thay bằng 0. Các CSV hồi quy chứa mô hình của mẫu đã lưu; lọc dòng để hiển thị không đồng nghĩa ước lượng lại mô hình.

## Phần nguồn thô và tải dữ liệu

Repo có mã tải và trích báo cáo trong `src/`, nhưng không kèm `data/raw/`, `data/processed/` hoặc văn bản `data/sections_v3/`. Vì vậy lần chạy offline bắt đầu từ bảng tone. Các phép kiểm tra số học tone không xác nhận lại từng từ hoặc ranh giới MD&A trong HTML gốc.

Nếu nhóm thực hiện lại việc thu thập nguồn, các bước đó cần kết nối mạng và được chạy riêng: chuẩn bị metadata hồ sơ, đặt tên/email liên hệ phù hợp trong User-Agent của mã SEC, tải 10-K, tiền xử lý rồi chạy các phiên bản trích section theo đầu vào chúng yêu cầu. `src/extract_sections_v3.py` cần kết quả của các bước trích trước; không thể chạy riêng trên một clone chỉ có metadata hiện tại. Chỉ chạy lại mã tính tone sau khi đã có văn bản section tương ứng.

`src/download_market_data.py` dùng `yfinance` để tải giá và có thể ghi lại CSV đầu vào. Đây không phải bước mặc định của `run_analysis.py`; dữ liệu tải mới có thể được nhà cung cấp điều chỉnh so với bản đã lưu. C2 đầy đủ vẫn cần bổ sung EADRet và Accruals; quy trình hiện tại chỉ tính C2 rút gọn từ bốn biến kiểm soát sẵn có.
