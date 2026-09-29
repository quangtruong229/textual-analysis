# Kết quả xử lý dữ liệu theo bộ công thức của nhóm

Phạm vi bản này là tính lại và kiểm tra kết quả từ dữ liệu trong ZIP. `app_local.py` là trang xem nhanh các bảng, còn phần thiết kế UX/UI do thành viên khác thực hiện. Không chọn mô hình theo p-value. Các giá trị hồi quy được diễn giải là mối liên hệ thống kê, không phải tác động nhân quả.

## Mẫu và tính tái lập

ZIP có 100 công ty và 1.000 hồ sơ 10-K. Bảng Item 7 MD&A có 971 hàng tính tone. Nghiên cứu sự kiện và hồi quy C1/C3/C4 có 969 hồ sơ của 100 công ty. Có 29 hồ sơ không đạt bước trích Item 7: 20 `too_short`, 6 `boundary_uncertain` và 3 `heading_not_found`. Hai hồ sơ có tone nhưng không vào mẫu sự kiện là P ngày 2016-03-25 và KHC ngày 2016-03-03 vì không đủ lợi suất hợp lệ trong đủ 239 phiên ước lượng. Danh sách từng hồ sơ thiếu và lý do loại ở `missing_filings.csv` và `event_study/event_exclusions.csv`.

`tone_firm_year.csv` giữ đủ 1.000 hàng theo **năm nộp** 2016–2025, một hàng cho mỗi công ty và năm nộp; tone có ở 971 hàng và CAR ở 969 hàng. `report_year` là năm kết thúc kỳ báo cáo, không đồng nghĩa `filing_year`: 66 hồ sơ nộp năm 2016 có ngày kết thúc kỳ trong năm 2015. Vì vậy không nên ghi mẫu này là 1.000 báo cáo **năm tài chính** 2016–2025.

Mã `src/event_study_final.py` chạy lại từ `daily_prices.csv` và `tone_method_item7.csv`. Mã `src/regression_analysis.py` sau đó chạy lại từ các CAR vừa tính. Kiểm tra phát hiện bảng sự kiện cũ trong ZIP bị **lệch một phiên**: cả 969 dòng ghi `event_time=0` có ngày giao dịch khác `event_date`. Sau sửa mã, cả 969 dòng ngày 0 đều trùng ngày sự kiện và mỗi hồ sơ có 11 ngày tương đối. Vì vậy CAR và hồi quy mới **cố ý khác** các bảng kết quả cũ trong `data/metadata/`. Bảng AR từng ngày mới tính lại nằm ở `event_study/event_ar_long.csv`; tổng AR theo cả bốn cửa sổ bằng CAR lưu ở 969 hồ sơ, không có sai khác. Tone tỷ lệ LM và Harvard tính từ số từ tích cực, tiêu cực và tổng từ cũng khớp cả 971 hàng. Chi tiết kiểm tra và SHA-256 đầu vào nằm ở `verification.json`.

## Kết quả chính đã tính lại

Hồi quy C1 theo tone LM tỷ lệ, CAR [-1,+1]: hệ số **-0,371931**, p hai phía HC3 **0,099111**, p theo cụm công ty **0,123529**, N = 969. Đây không phải bằng chứng ở ngưỡng 5% cho đặc tả này. Các đặc tả C1/C3/C4 và bốn cửa sổ nằm đầy đủ ở `regression/regression_results.csv` (76 dòng, gồm cả hằng số).

Trên 971 filing so sánh được, tone LM và Harvard IV-4 trái dấu ở **861 filing (88,7%)**. Bảng từng hồ sơ ở `dictionary_comparison_filings.csv` và tổng hợp ở `dictionary_comparison_summary.csv`. Đây là bằng chứng hai từ điển cho kết quả khác nhau; chưa thể gọi 861 trường hợp là Harvard "sai" vì ZIP không có văn bản gốc và bộ nhãn đúng để thẩm định ngữ cảnh.

Theo bảng nghiên cứu sự kiện được chạy lại, CAAR [-1,+1] = **0,005189** (khoảng 0,519%), p MacKinlay = **0,000000045**, N = 969. Phương sai CAR dùng xấp xỉ B4 của tài liệu công thức: số phiên trong cửa sổ nhân phương sai phần dư mô hình thị trường. Bốn cửa sổ và các phép kiểm định nằm ở `event_study/event_study_summary.csv`. Đây là phản ứng trung bình quanh ngày nộp, không tự chứng minh tone là nguyên nhân.

## C2 với biến kiểm soát có sẵn

Tài liệu công thức C2 nêu Size, BM, Volatility, Turnover, EADRet và Accruals. ZIP chỉ có bốn biến đầu; vì vậy `c2_reduced_results.csv` là **C2 rút gọn**, không được gọi là mô hình C2 đầy đủ. Ghép bằng ticker và ngày nộp đã chuẩn hóa (ngày trong bảng controls được ghi dưới dạng chuỗi tuple), giữ các hàng `status=success` và đủ dữ liệu. Mỗi cửa sổ có **862 quan sát thuộc 96 công ty**; 107/969 hàng không đủ bộ biến kiểm soát.

Mô hình: `CAR = const + b·LM_net_prop + Size + BM + Volatility + Turnover + sai số`. BM là tỷ số book-to-market đã lưu ở cột `bm`; không thay bằng `log_bm`. Sai số chuẩn HC3 và theo cụm công ty đều được xuất.

| CAR | Hệ số tone | p HC3 hai phía | CI 95% HC3 | p theo cụm |
| --- | ---: | ---: | --- | ---: |
| [-1,+1] | -0,318030 | 0,165640 | [-0,767647; 0,131588] | 0,232724 |
| [0,+3] | -0,198126 | 0,388443 | [-0,648381; 0,252129] | 0,501069 |
| [-3,+3] | -0,388284 | 0,186191 | [-0,963972; 0,187405] | 0,227767 |
| [-5,+5] | -0,181740 | 0,626133 | [-0,912900; 0,549420] | 0,584202 |

## Giới hạn của bộ ZIP

Các thư mục `data/raw/`, `data/processed/` và `data/sections_v3/` bị loại khỏi ZIP. Vì vậy không thể chạy lại trực tiếp tiền xử lý và quy tắc phủ định A1, đếm từ/tf.idf A2–A3 từ văn bản gốc. Việc kiểm tra tone ở đây chỉ xác nhận số học từ các cột đếm từ đã cung cấp. Word Power A4 là phần mở rộng, chưa tính. C2 đầy đủ cần thêm EADRet và Accruals. Những phép kiểm định khác trong tài liệu chưa có đủ đầu vào hoặc chưa được triển khai trong mã cung cấp; không được xem là đã hoàn thành chỉ vì có bảng kết quả C1/C3/C4.

Chạy lại bằng `python scripts/run_analysis.py` như README repo. Các tệp trong `analysis_outputs/` là đầu ra hiện hành; không ghi đè bảng gốc trong `data/metadata/`. Bốn biến kiểm soát của C2 lấy từ CSV cung cấp sẵn; phép tạo Size/BM bằng giá Yahoo và cổ phiếu lưu hành lịch sử cần được kiểm toán thêm về điều chỉnh chia tách trước khi coi C2 là bằng chứng vững.
