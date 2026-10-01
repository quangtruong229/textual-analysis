# Textual Analysis in Finance — mô tả sản phẩm nghiên cứu

## Phạm vi và dữ liệu

Ứng dụng trình bày kết quả phân tích Item 7 (MD&A) của 10-K, từ điển Loughran–McDonald (LM), nghiên cứu sự kiện AR/CAR và hồi quy. Mẫu là 100 công ty × 10 năm nộp 2016–2025: 1.000 hồ sơ, 971 hồ sơ có tone Item 7 và 969 hồ sơ có đủ dữ liệu nghiên cứu sự kiện. Chỉ số thị trường đối chứng là S&P 500. Năm nộp 10-K khác với năm tài chính của báo cáo.

Nguồn và khả năng kiểm tra:

- `data/item7_corpus/manifest.csv` lưu URL SEC, accession, trạng thái và SHA-256 của hồ sơ. Bảng tần suất từ theo hồ sơ được lưu dạng nén. HTML 10-K/Item 7 gốc không nằm trong Git; xem [hướng dẫn tái tạo corpus](../README.md).
- `analysis_outputs/` chứa các bảng kết quả đã tính. `handoff/manifest.json` liệt kê các tệp bàn giao và mã băm để đối chiếu.
- Webapp tĩnh đọc `webapp/data.js` do `python webapp/build_data.py` tạo từ các CSV kết quả. Webapp **không** trực tiếp đọc CSV hoặc tính lại mô hình khi mở trang. Người xem cần dựng lại `data.js` sau mỗi lần cập nhật kết quả.

## Phương pháp và cách đọc kết quả

Tone LM dạng tỷ lệ, tỷ số và TF-IDF được tính cho Item 7. So sánh Harvard IV-4 là đối chứng độ nhạy của thước đo. LM và Harvard cho điểm trái dấu ở 861/971 hồ sơ (88,7%). Con số này **không xác định từ điển nào phân loại đúng từng từ hoặc từng ngữ cảnh**; cần đánh giá ngữ cảnh có nhãn để đưa ra kết luận đó.

AR và CAR dùng mô hình thị trường với 239 phiên ước lượng, xét bốn cửa sổ `[-1,+1]`, `[0,+3]`, `[-3,+3]`, `[-5,+5]`. Ngày sự kiện theo thời điểm SEC và lịch giao dịch. Brown–Warner, kiểm định chuẩn hóa, phương sai cắt ngang, Corrado từng ngày, hiệu chỉnh tự tương quan và power giả định CAAR có các phạm vi kiểm định khác nhau. **Power CAAR không phải power của H1.**

Các bảng hồi quy được phân biệt rõ:

| Nhóm | Thước đo/đặc tả | Mẫu |
| --- | --- | ---: |
| C1/C3/C4 | Tone tỷ lệ, tỷ số, TF-IDF và đối chứng từ điển | Theo từng mô hình |
| C2 rút gọn | LM tỷ lệ + Size, BM, Volatility, Turnover | 862 hồ sơ, 96 công ty |
| C2 sáu biến | C2 rút gọn + EADRet, Accruals đạt `PASS` | 481 hồ sơ, 71 công ty |
| Word Power H1/H2 | Trọng số từ ước lượng ngoài năm được chấm điểm; nhóm từ tiêu cực dùng ridge | 969 hoặc 481 hồ sơ tùy đặc tả |
| C5–C8 | Yếu tố quyết định tone, phản ứng chậm, AR ngày 0, Fama–MacBeth | Xem N từng bảng |

Word Power có bảng tần suất từng từ theo hồ sơ và kiểm tra không dùng năm được chấm điểm để học trọng số. Vì nhóm từ tiêu cực dùng ridge, đây là **biến thể có điều chỉnh**, không phải tái lập OLS nguyên xi của Jegadeesh & Wu. H1/H2 Word Power ở cửa sổ `[0,+3]` không đạt mức ý nghĩa 5% theo chiều kỳ vọng trong đặc tả chính. Xem [báo cáo Word Power](../analysis_outputs/word_power/RESULTS.md), [báo cáo sáu biến](../analysis_outputs/FULL_CONTROLS_REVIEW.md) và [bảng độ vững](../analysis_outputs/ROBUSTNESS_RESULTS.md).

Hệ số và p-value mô tả liên hệ trong mẫu. CAR có thể chịu ảnh hưởng của thông tin công bố cùng kỳ. Kết quả không chứng minh tone gây biến động giá, không xác nhận tín hiệu giao dịch sinh lời, và không phải khuyến nghị đầu tư. Bản web phục vụ khám phá hồ sơ, đối chiếu kết quả và kiểm tra nguồn.

## Giao diện và bàn giao

Các tab hiển thị tổng quan, AR/CAR, hồi quy, so sánh từ điển, hồ sơ 10-K, phương pháp và audit. Tab hồi quy có bảng Word Power, C2 sáu biến và B6–C8 bên cạnh C2 rút gọn; bộ lọc hồ sơ không thay đổi hệ số đã tính trên toàn mẫu. Người dùng có thể tải bảng hồ sơ đã lọc hoặc mở hồ sơ SEC từ liên kết trong dữ liệu.

Quy trình cập nhật: chạy `python scripts/run_analysis.py`, xác nhận `python scripts/validate_handoff.py`, chạy `python webapp/build_data.py`, rồi kiểm tra tab hồi quy và audit. Mọi thay đổi dữ liệu đầu vào cần được phản ánh trong CSV, manifest và `data.js` trước khi xuất bản webapp.
