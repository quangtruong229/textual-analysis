# Phương pháp tính toán

## 1. Câu hỏi và đơn vị quan sát

Nghiên cứu hỏi liệu giọng điệu trong phần **Item 7 – Management’s Discussion and Analysis (MD&A)** của báo cáo 10-K có liên hệ với phản ứng giá cổ phiếu quanh ngày nộp báo cáo hay không. Một quan sát là **một hồ sơ 10-K của một công ty tại một ngày nộp**. Phần mềm dùng 100 công ty, mỗi công ty một hồ sơ cho từng **năm nộp** 2016–2025, tổng cộng 1.000 hồ sơ. Năm nộp không đồng nghĩa năm tài chính: 66 hồ sơ nộp năm 2016 có kỳ báo cáo kết thúc năm 2015. Vì vậy các bảng ghi riêng `filing_year` và `report_year`.

## 2. Từ báo cáo sang biến tone

`src/download_10k.py`, `src/preprocess_10k.py` và `src/extract_sections_v3.py` là chuỗi mã gốc để tải, làm sạch và trích Item 7. Bản ZIP đang dùng chỉ có metadata và bảng điểm, **không có HTML 10-K hoặc văn bản Item 7 đã trích**. Do đó phiên chạy hiện tại bắt đầu từ `data/metadata/tone_method_item7.csv`; không tuyên bố đã chạy lại việc đọc báo cáo từ chữ gốc.

Từ điển tài chính Loughran–McDonald (LM) và từ điển tổng quát Harvard IV-4 nằm trong `data/dictionary/`. Theo `src/build_method_scores.py`, văn bản được tách thành token chữ và chuyển thành chữ hoa. Với mỗi từ tích cực/tiêu cực, nếu `NOT`, `NO` hoặc `NEVER` xuất hiện trong ba token đứng trước, từ đó không được cộng vào nhóm tích cực/tiêu cực. Bảng tone lưu cả số từ bị loại vì phủ định.

Với một báo cáo có `W` token, `P` lần xuất hiện từ tích cực và `N` lần xuất hiện từ tiêu cực sau quy tắc phủ định, chỉ số cơ sở là:

`positive_prop = P / W`, `negative_prop = N / W`, `net_prop = positive_prop − negative_prop`.

Đặc tả đối chứng `net_ratio = (positive_prop − negative_prop) / (positive_prop + negative_prop)` chỉ xác định khi mẫu số khác 0. Cách tính tf.idf dùng `idf_j = log(số văn bản / số văn bản chứa từ j)` và trọng số tần suất `1 + log(tf)` trước khi chuẩn hóa theo `1 + log(W)`. Điểm LM và Harvard được xây trên cùng quy tắc xử lý trong mã này. Bảng `lm_tone.csv` còn có số từ bất định; bảng `tone_method_item7.csv` chứa các điểm dùng cho so sánh và hồi quy.

Trong 1.000 hồ sơ, 971 có Item 7 đủ điều kiện tính tone. 29 hồ sơ không được gán tone bằng 0: 20 `too_short`, 6 `boundary_uncertain`, 3 `heading_not_found`. `tone_firm_year.csv` giữ đủ 1.000 hàng và đánh dấu trạng thái từng hồ sơ. Do thiếu văn bản gốc, kiểm tra hiện nay xác nhận công thức `P/W − N/W` trên 971 hàng, nhưng không xác nhận từng lần đếm từ hoặc phạm vi Item 7.

## 3. Nghiên cứu sự kiện AR và CAR

Giá đóng cửa đã điều chỉnh và lợi suất ngày nằm trong `data/market_data/daily_prices.csv`; chỉ số thị trường là `^GSPC`. `src/event_study_final.py` dùng các phiên của chỉ số làm lịch chuẩn rồi ghép lợi suất cổ phiếu theo ngày, giữ nguyên phiên bị thiếu để kiểm tra. Ngày sự kiện `t=0` là ngày nộp nếu có phiên giao dịch; nếu không, mã chọn phiên đầu tiên sau ngày nộp. Dữ liệu hiện tại không có hồ sơ nào phải dịch sang phiên sau. CSV chỉ có **ngày** nộp, không có giờ SEC chấp nhận hồ sơ; vì vậy không xác định được hồ sơ nộp sau giờ đóng cửa có nên chuyển sang phiên kế tiếp hay không.

Mỗi hồ sơ cần đủ **239 phiên ước lượng** từ `t=−244` đến `t=−6`, tách khỏi vùng sự kiện `t=−5` đến `t=+5`. Hồi quy mô hình thị trường trên cửa sổ ước lượng cho `α_i` và `β_i`:

`R_i,t = α_i + β_i R_m,t + ε_i,t`.

Lợi suất bất thường của hồ sơ `i` tại ngày tương đối `t` là `AR_i,t = R_i,t − (α_i + β_i R_m,t)`. `CAR_i[a,b]` là tổng AR từ `a` đến `b`. Bốn cửa sổ được xuất: `[-1,+1]`, `[0,+3]`, `[-3,+3]` và `[-5,+5]`. Phương sai CAR dùng **xấp xỉ B4** trong bộ công thức nhóm: `Var(CAR_i[a,b]) ≈ (b−a+1) × σ²_ε,i`. Đây là xấp xỉ cho cửa sổ ước lượng dài; không bao gồm sai số do ước lượng α/β. Bảng `event_ar_long.csv` lưu AR từng ngày để kiểm tra tổng CAR và xác nhận ngày `0` trùng ngày sự kiện.

Trong 971 hồ sơ có tone, 969 có đủ lợi suất hợp lệ trong cửa sổ ước lượng; hai hồ sơ bị loại được ghi tại `event_study/event_exclusions.csv`. `event_study_summary.csv` báo CAAR trung bình, thống kê MacKinlay và kiểm định dấu cho cả bốn cửa sổ; thống kê Brown–Warner nhiều ngày được báo cho `[-5,+5]`. Các p-value này kiểm tra **phản ứng trung bình quanh ngày nộp**, chưa kiểm tra riêng vai trò của tone.

## 4. Hồi quy liên hệ tone với CAR

`src/regression_analysis.py` nối tone và CAR theo công ty và ngày nộp; mẫu chung có 969 hồ sơ thuộc 100 công ty. Các biến phụ thuộc là bốn CAR ở trên. Những đặc tả đã chạy là:

- **C1:** `CAR_i = a + b·Score_i + ε_i`, lần lượt dùng LM net proportional, LM net ratio, LM net tf.idf và các điểm Harvard tương ứng.
- **C3:** `CAR_i = a + b·LM_positive_i + c·LM_negative_i + ε_i`.
- **C4:** `CAR_i = a + b·LM_net_i + c·Harvard_net_i + ε_i`, với phiên bản tỷ lệ và tf.idf.
- **C2 rút gọn:** `CAR_i = a + b·LM_net_prop_i + c·Size_i + d·BM_i + e·Volatility_i + f·Turnover_i + ε_i` từ `controls_item7.csv`. `Size` là log vốn hóa thị trường, `BM` là book-to-market lưu ở cột `bm`, `Volatility` là độ lệch chuẩn phần dư thị trường, và `Turnover` là log tỷ lệ giao dịch theo mã gốc. Bộ công thức C2 đầy đủ còn EADRet và Accruals; hai biến đó không có trong ZIP nên không được bịa hoặc thay thế.

C1/C3/C4 dùng OLS với sai số chuẩn HC3 và sai số chuẩn gom cụm theo công ty. C2 rút gọn cũng báo hai loại sai số chuẩn. C2 chỉ giữ hàng `status=success` và đủ tất cả biến; còn 862 hồ sơ thuộc 96 công ty. Không so sánh p-value giữa C1 và C2 như thể hai mô hình dùng cùng một mẫu. Bộ controls được cung cấp sẵn; mã tạo nó nhân giá Yahoo `close` với cổ phiếu lưu hành lịch sử để tính Size/BM. Chưa xác minh được quy ước điều chỉnh chia tách của giá và số cổ phiếu tương ứng, nên cần kiểm toán thêm trước khi diễn giải mạnh hệ số C2.

Hệ số hồi quy mô tả **mối liên hệ trong mẫu**, không chứng minh tone gây biến động giá. Bốn cửa sổ và nhiều đặc tả được trình bày cùng nhau; không chọn riêng mô hình có p-value nhỏ để đổi kết luận chính.

## 5. Kiểm tra và khả năng chạy lại

`scripts/run_analysis.py` chạy toàn bộ các bước theo thứ tự, mặc định tính lại nghiên cứu sự kiện từ bảng giá, rồi chạy hồi quy, tạo bảng công ty–năm và xuất kết quả. `scripts/verify_recalculation.py` kiểm tra ngày `0`, số ngày cửa sổ, số học tone, tổng AR thành CAR và độ phủ bảng công ty–năm. Nó còn ghi mức khác biệt với các bảng cũ trong ZIP để truy vết; **không dùng sự trùng khớp với bản cũ làm tiêu chí đúng**. Trước khi sửa, toàn bộ 969 dòng ngày `0` trong bản cũ lệch một phiên so với ngày sự kiện đã ghi. Sau sửa, 969/969 dòng khớp. Kết quả kiểm tra và SHA-256 của đầu vào nằm trong `analysis_outputs/verification.json`.

Bộ công thức tham chiếu là `docs/Cong_thuc_dinh_luong.docx`. Các bước không có dữ liệu đầu vào cần thiết, đặc biệt việc đọc HTML/MD&A và C2 đầy đủ, được nêu là giới hạn thay vì được đánh dấu hoàn thành.
