# Phương pháp tính toán

## 1. Câu hỏi và đơn vị quan sát

Nghiên cứu hỏi liệu giọng điệu trong phần **Item 7 – Management’s Discussion and Analysis (MD&A)** của báo cáo 10-K có liên hệ với phản ứng giá cổ phiếu quanh ngày nộp báo cáo hay không. Một quan sát là **một hồ sơ 10-K của một công ty tại một ngày nộp**. Phần mềm dùng 100 công ty, mỗi công ty một hồ sơ cho từng **năm nộp** 2016–2025, tổng cộng 1.000 hồ sơ. Năm nộp không đồng nghĩa năm tài chính: 66 hồ sơ nộp năm 2016 có kỳ báo cáo kết thúc năm 2015. Vì vậy các bảng ghi riêng `filing_year` và `report_year`.

## 2. Từ báo cáo sang biến tone

`scripts/fetch_item7_corpus.py` tải HTML 10-K trực tiếp từ SEC theo accession, dùng `src/preprocess_10k.py` làm sạch và ranh giới Item 7 đã được thẩm định trong `sections_10k_v3.csv` để trích văn bản. HTML, văn bản sạch và Item 7 gốc nằm trên máy chạy, không đưa vào Git; manifest lưu URL và SHA-256. Bảng tần suất từ theo từng hồ sơ được chia sẻ dưới dạng `data/item7_corpus/item7_term_counts.csv.gz`. Phiên phân tích hồi quy hiện hành vẫn bắt đầu từ bảng điểm `data/metadata/tone_method_item7.csv`.

Word Power được ước lượng riêng trong `scripts/calculate_word_power.py` từ bảng tần suất **sau phủ định A1** của 971 Item 7. Với mỗi năm nộp, chỉ dùng CAR `[0,+3]` của các năm khác để ước lượng trọng số từ, rồi chấm điểm năm được giữ lại theo Jegadeesh–Wu (2013, Eq. 4, 6, 7). Danh sách tích cực dùng OLS khi đủ hạng; danh sách tiêu cực cần ridge và chọn penalty bằng kiểm tra chéo theo năm trong tập huấn luyện vì số từ lớn so với số hồ sơ. Chỉ giữ từ xuất hiện trong ít nhất 5 hồ sơ huấn luyện. Đây là **bản điều chỉnh theo cỡ mẫu**, không phải tái lập nguyên xi bài gốc. `lm_positive_prop` và `lm_positive_tfidf` vẫn là hai biến khác `lm_positive_wp`. [Bài gốc Jegadeesh–Wu](https://repository.upenn.edu/server/api/core/bitstreams/caf9d0c9-0de5-475a-ac72-f6e4ad3bfce5/content).

Từ điển tài chính Loughran–McDonald (LM) và từ điển tổng quát Harvard IV-4 nằm trong `data/dictionary/`. Theo `src/build_method_scores.py`, văn bản được tách thành token chữ và chuyển thành chữ hoa. Với mỗi từ tích cực/tiêu cực, nếu `NOT`, `NO` hoặc `NEVER` xuất hiện trong ba token đứng trước, từ đó không được cộng vào nhóm tích cực/tiêu cực. Bảng tone lưu cả số từ bị loại vì phủ định.

Với một báo cáo có `W` token, `P` lần xuất hiện từ tích cực và `N` lần xuất hiện từ tiêu cực sau quy tắc phủ định, chỉ số cơ sở là:

`positive_prop = P / W`, `negative_prop = N / W`, `net_prop = positive_prop − negative_prop`.

Đặc tả đối chứng `net_ratio = (positive_prop − negative_prop) / (positive_prop + negative_prop)` chỉ xác định khi mẫu số khác 0. Cách tính tf.idf dùng `idf_j = log(số văn bản / số văn bản chứa từ j)` và trọng số tần suất `1 + log(tf)` trước khi chuẩn hóa theo `1 + log(W)`. Điểm LM và Harvard được xây trên cùng quy tắc xử lý trong mã này. Bảng `lm_tone.csv` còn có số từ bất định; bảng `tone_method_item7.csv` chứa các điểm dùng cho so sánh và hồi quy.

Trong 1.000 hồ sơ, 971 có Item 7 đủ điều kiện tính tone. 29 hồ sơ không được gán tone bằng 0: 20 `too_short`, 6 `boundary_uncertain`, 3 `heading_not_found`. `tone_firm_year.csv` giữ đủ 1.000 hàng và đánh dấu trạng thái từng hồ sơ. HTML gốc đã được tải lại cho cả 1.000 hồ sơ; 971 Item 7 được tái tạo và kiểm tra độc lập tổng token, tần suất từng từ, số từ LM tích cực/tiêu cực và số từ bị loại theo quy tắc phủ định A1, không có sai lệch trong `data/item7_corpus/verification.json`.

## 3. Nghiên cứu sự kiện AR và CAR

Giá đóng cửa đã điều chỉnh và lợi suất ngày nằm trong `data/market_data/daily_prices.csv`; chỉ số thị trường là `^GSPC`. `src/event_study_final.py` dùng các phiên của chỉ số làm lịch chuẩn rồi ghép lợi suất cổ phiếu theo ngày, giữ nguyên phiên bị thiếu để kiểm tra. Giờ chấp nhận từng hồ sơ nằm trong `data/metadata/filing_acceptance.csv` từ SEC. Ngày sự kiện `t=0` là phiên NYSE đang mở nếu hồ sơ được chấp nhận trước giờ đóng cửa phiên đó; nếu sau giờ đóng cửa hoặc ngoài ngày giao dịch, mã chọn phiên kế tiếp. Lịch NYSE xử lý cả các phiên đóng cửa sớm.

Mỗi hồ sơ cần đủ **239 phiên ước lượng** từ `t=−244` đến `t=−6`, tách khỏi vùng sự kiện `t=−5` đến `t=+5`. Hồi quy mô hình thị trường trên cửa sổ ước lượng cho `α_i` và `β_i`:

`R_i,t = α_i + β_i R_m,t + ε_i,t`.

Lợi suất bất thường của hồ sơ `i` tại ngày tương đối `t` là `AR_i,t = R_i,t − (α_i + β_i R_m,t)`. `CAR_i[a,b]` là tổng AR từ `a` đến `b`. Bốn cửa sổ được xuất: `[-1,+1]`, `[0,+3]`, `[-3,+3]` và `[-5,+5]`. Phương sai CAR dùng **xấp xỉ B4** trong bộ công thức nhóm: `Var(CAR_i[a,b]) ≈ (b−a+1) × σ²_ε,i`. Đây là xấp xỉ cho cửa sổ ước lượng dài; không bao gồm sai số do ước lượng α/β. Bảng `event_ar_long.csv` lưu AR từng ngày để kiểm tra tổng CAR và xác nhận ngày `0` trùng ngày sự kiện.

Trong 971 hồ sơ có tone, 969 có đủ lợi suất hợp lệ trong cửa sổ ước lượng; hai hồ sơ bị loại được ghi tại `event_study/event_exclusions.csv`. Trong 969 hồ sơ này, 466 có ngày sự kiện ở phiên sau ngày nộp chính thức. `event_study_summary.csv` báo CAAR trung bình, thống kê MacKinlay và kiểm định dấu cho cả bốn cửa sổ; `extended_window_tests.csv` báo Brown–Warner nhiều ngày cho cả bốn cửa sổ. Các p-value này kiểm tra **phản ứng trung bình quanh ngày công bố**, chưa kiểm tra riêng vai trò của tone.

`scripts/extended_event_tests.py` tính Brown–Warner A.11 cho cả bốn cửa sổ bằng tổng AAR chia cho độ lệch chuẩn AAR trong 239 ngày ước lượng nhân căn bậc hai độ dài cửa sổ. B7 ước lượng tự tương quan AAR ở độ trễ 1–3 theo trình tự; chỉ giữ độ trễ có ý nghĩa và dùng ma trận hiệp phương sai để hiệu chỉnh phương sai tổng AAR. Trong bộ mẫu này không có độ trễ nào được giữ, nên các thống kê B7 bằng Brown–Warner chưa hiệu chỉnh. `corrado_daily.csv` xếp hạng 250 AR của từng hồ sơ (239 ngày ước lượng và 11 ngày sự kiện), báo Z và p cho từng ngày tương đối; **không** gọi đây là Corrado đa ngày cho bốn CAR. `theoretical_power.csv` dùng xấp xỉ chuẩn hai phía với α = 5% và các mức CAAR giả định 0,25%, 0,5%, 1%; đây không phải power của hồi quy tone. [Brown–Warner (1985)](https://leeds-faculty.colorado.edu/bhagat/brownwarner1985.pdf), [MacKinlay (1997)](https://www.bu.edu/econ/files/2011/01/MacKinlay-1996-Event-Studies-in-Economics-and-Finance.pdf).

## 4. Hồi quy liên hệ tone với CAR

`src/regression_analysis.py` nối tone và CAR theo công ty và ngày nộp; mẫu chung có 969 hồ sơ thuộc 100 công ty. Các biến phụ thuộc là bốn CAR ở trên. Những đặc tả đã chạy là:

- **C1:** `CAR_i = a + b·Score_i + ε_i`, lần lượt dùng LM net proportional, LM net ratio, LM net tf.idf và các điểm Harvard tương ứng.
- **C3:** `CAR_i = a + b·LM_positive_i + c·LM_negative_i + ε_i`.
- **C4:** `CAR_i = a + b·LM_net_i + c·Harvard_net_i + ε_i`, với phiên bản tỷ lệ và tf.idf.
- **C2 rút gọn:** `CAR_i = a + b·LM_net_prop_i + c·Size_i + d·BM_i + e·Volatility_i + f·Turnover_i + ε_i` từ `controls_item7.csv`. `Size` là log vốn hóa thị trường, `BM` là book-to-market lưu ở cột `bm`, `Volatility` là độ lệch chuẩn phần dư thị trường, và `Turnover` là log tỷ lệ giao dịch. Giá Yahoo lịch sử và số cổ phiếu SEC được đưa về cùng cơ sở chia tách bằng `stock_splits.csv` trước khi tính Size, BM và Turnover.

H1/H2 theo Word Power được chạy riêng ở `analysis_outputs/word_power/regression_results.csv`, cho cả C1/C3 và C2/C3 sáu biến kiểm soát, bốn cửa sổ CAR. H1 kỳ vọng hệ số điểm tích cực dương. Khi điểm tiêu cực được chuẩn hóa theo phản ứng thị trường như Eq. 7, điểm cao cũng biểu thị từ gắn với CAR cao trong tập huấn luyện, nên H2 Word Power kỳ vọng dấu dương; H2 dùng **tỷ lệ từ tiêu cực** mới kỳ vọng dấu âm. Báo cáo chính và kiểm tra độ nhạy ở `analysis_outputs/word_power/RESULTS.md`. P-value điều kiện trên điểm được ước lượng, chưa bao quát hết sai số của bước tạo trọng số. Các hồi quy tone tỷ lệ trước đây giữ nguyên để đối chứng.

C1/C3/C4 dùng OLS với sai số chuẩn HC3 và sai số chuẩn gom cụm theo công ty. C2 rút gọn cũng báo hai loại sai số chuẩn. C2 chỉ giữ hàng `status=success` và đủ tất cả biến; số quan sát và công ty được ghi trong `c2_reduced_results.csv`. Không so sánh p-value giữa C1 và C2 như thể hai mô hình dùng cùng một mẫu.

Hệ số hồi quy mô tả **mối liên hệ trong mẫu**, không chứng minh tone gây biến động giá. Bốn cửa sổ và nhiều đặc tả được trình bày cùng nhau; không chọn riêng mô hình có p-value nhỏ để đổi kết luận chính.

Phần **Hàm ý tài chính** trong `presentation.py` được sinh lại từ CAAR/AR ngày 0, hệ số positive và negative tone của C3, p HC3/p gom cụm, và các biến kiểm soát C2 ở cửa sổ `[0,+3]`. Nó nêu chiều của mối liên hệ, mức thay đổi tương ứng khi tone tăng 1 điểm phần trăm và có/không có bằng chứng ở ngưỡng 5%; không chuyển hệ số hồi quy thành khuyến nghị giao dịch hoặc kết luận nhân quả.

## 5. Kiểm định độ vững và mô hình mở rộng từ dữ liệu hiện có

`scripts/optional_robustness.py` xuất kết quả đầy đủ và giải thích tại `analysis_outputs/ROBUSTNESS_RESULTS.md`:

- **B6:** chuẩn hóa CAR từng hồ sơ bằng độ lệch chuẩn AR trong 239 phiên ước lượng và căn bậc hai độ dài cửa sổ; cộng thống kê dưới giả định độc lập chéo. Đối chứng phương sai cắt ngang dùng `N⁻² Σ(CARᵢ − CAAR)²` theo Eq. 21 trong bộ công thức. Hai phép này kiểm tra CAAR trung bình, không kiểm định tone.
- **C5 rút gọn:** `LM_net_prop` phụ thuộc vào Size, BM, Volatility, Turnover và tone của đúng năm nộp trước. Chỉ chuẩn hóa các biến giải thích trên mẫu hoàn chỉnh. Bản sáu controls với EADRet/Accruals được xuất riêng ở mục 6.
- **C6:** cộng AR theo mô hình thị trường từ phiên +5 đến +5, +10 hoặc +22, rồi hồi quy từng CAR sau sự kiện theo `LM_net_prop`. Ngày +5 nằm trong cả ba cửa sổ theo cách viết Eq. 17 của nhóm. Không điền 0 cho phiên thiếu; mẫu của từng cửa sổ được ghi riêng.
- **C7:** hồi quy cắt ngang AR ngày 0 theo `LM_net_prop` và bốn biến kiểm soát với HC3 và sai số chuẩn cụm công ty. Phiên bản CAR tương ứng đã có trong C2 rút gọn; không báo lại như một ước lượng độc lập mới.
- **C8:** ước lượng hồi quy cắt ngang CAR `[0,+3]` riêng cho từng năm nộp 2016–2025, rồi lấy trung bình 10 hệ số năm, sai số chuẩn từ độ phân tán giữa các năm và p theo t với 9 bậc tự do. Có đặc tả C1 tone tỷ lệ và C2 bốn biến kiểm soát, chưa có Word Power/C2 đầy đủ.

Các p-value vẫn nhạy với sự kiện trùng ngày, phụ thuộc chéo giữa công ty, chọn cửa sổ và số năm chỉ bằng 10. Không chọn một kết quả mở rộng có p nhỏ để thay kết luận chính.

## 6. EADRet, Accruals và mô hình sáu biến kiểm soát

Hai CSV `data/metadata/controls/eadret_item7.csv` và `accruals_item7.csv` được chép nguyên từ nhánh `finalize-eadret-accruals`, commit `0ee574c`. Script `calculate_full_controls.py` kiểm tra đủ 1.000 khóa hồ sơ, accession 10-K, kỳ báo cáo, thứ tự thời gian của thông báo lợi nhuận và số học từng biến. `EADRet` là lợi suất ba ngày quanh 8-K Item 2.02 trừ lợi suất `^GSPC`; 991 hồ sơ có giá trị. Accruals là công thức Sloan trên các thành phần SEC Company Facts chia cho tài sản bình quân. Có 571 hàng `PASS`, 341 `WARN`, 88 `STRUCTURAL_MISSING`; mô hình chính chỉ dùng `PASS`, không diễn giải giá trị số ở hàng `WARN` là đã xác minh.

Bốn controls Size, BM, Volatility, Turnover được giữ theo **định nghĩa và dữ liệu của nhánh main**. Bảng `controls_item7_final6.csv` ở nhánh nguồn dùng các quy tắc đo lường khác nên không thay thế trực tiếp. Giao với mẫu CAR và bốn controls hiện hành còn 481 hồ sơ của 71 công ty. Trên cùng 481 hàng, script ước lượng C2 bốn controls đối chứng, C2 sáu controls, C3 positive/negative tone sáu controls; C5 thêm tone năm trước còn 431 hàng. Hệ số HC3 và cụm công ty được xuất ở `analysis_outputs/`, cùng báo cáo `FULL_CONTROLS_REVIEW.md`. Các bảng C2/C3 ở thư mục gốc dùng tone LM dạng tỷ lệ; mô hình Word Power sáu controls nằm riêng tại `analysis_outputs/word_power/`.

Nhánh nguồn có các cột đặt tên `word_power`, nhưng trong `src/build_method_scores.py` chúng bằng tổng TF-IDF chưa chuẩn hóa, không có bước ước lượng trọng số từ theo phản ứng thị trường. Vì vậy không nhập các cột đó hoặc nhận là Word Power. Các CSV mới cho phép tính lại hồi quy offline, nhưng bước dựng `EADRet`/`Accruals` từ toàn bộ nguồn SEC vẫn cần kiểm toán riêng nếu muốn tái lập từ dữ liệu gốc.

## 7. Kiểm tra và khả năng chạy lại

`scripts/run_analysis.py` chạy toàn bộ các bước theo thứ tự, mặc định tính lại nghiên cứu sự kiện từ bảng giá, rồi chạy hồi quy, tạo bảng công ty–năm và xuất kết quả. `scripts/verify_recalculation.py` kiểm tra ngày `0`, số ngày cửa sổ, số học tone, tổng AR thành CAR và độ phủ bảng công ty–năm. Kết quả kiểm tra hiện hành có 969/969 ngày `0` khớp ngày sự kiện. Chi tiết và SHA-256 của đầu vào nằm trong `analysis_outputs/verification.json`.

Bộ công thức tham chiếu là `docs/Cong_thuc_dinh_luong.docx`; các bảng kết quả ghi rõ đặc tả và mẫu thực tế được ước lượng.
