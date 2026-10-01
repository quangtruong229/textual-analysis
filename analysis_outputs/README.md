# Kết quả xử lý dữ liệu theo bộ công thức của nhóm

Tài liệu này trình bày kết quả từ các bảng đầu vào trong repo. `app_local.py` là trang xem nhanh các bảng. Các giá trị hồi quy được diễn giải là mối liên hệ thống kê, không phải tác động nhân quả.

## Mẫu và tính tái lập

Bảng metadata gồm 100 công ty và 1.000 hồ sơ 10-K. Bảng Item 7 MD&A có 971 hàng tính tone. Nghiên cứu sự kiện và hồi quy C1/C3/C4 có 969 hồ sơ của 100 công ty. Có 29 hồ sơ không đạt bước trích Item 7: 20 `too_short`, 6 `boundary_uncertain` và 3 `heading_not_found`. Hai hồ sơ có tone nhưng không vào mẫu sự kiện là P ngày 2016-03-25 và KHC ngày 2016-03-03 vì không đủ lợi suất hợp lệ trong đủ 239 phiên ước lượng. Danh sách từng hồ sơ và lý do loại ở `missing_filings.csv` và `event_study/event_exclusions.csv`.

`tone_firm_year.csv` giữ đủ 1.000 hàng theo **năm nộp** 2016–2025, một hàng cho mỗi công ty và năm nộp; tone có ở 971 hàng và CAR ở 969 hàng. `report_year` là năm kết thúc kỳ báo cáo, không đồng nghĩa `filing_year`: 66 hồ sơ nộp năm 2016 có ngày kết thúc kỳ trong năm 2015. Vì vậy không nên ghi mẫu này là 1.000 báo cáo **năm tài chính** 2016–2025.

Mã `src/event_study_final.py` tính AR/CAR từ `daily_prices.csv`, `tone_method_item7.csv` và giờ SEC chấp nhận hồ sơ. Mã `src/regression_analysis.py` dùng các CAR này để ước lượng hồi quy. Trong đầu ra hiện hành, cả 969 dòng ngày `0` trùng ngày sự kiện; 466 hồ sơ chuyển sang phiên sau so với ngày nộp chính thức. Mỗi hồ sơ có 11 ngày tương đối. Bảng AR từng ngày nằm ở `event_study/event_ar_long.csv`; tổng AR theo cả bốn cửa sổ bằng CAR lưu ở 969 hồ sơ. Tone tỷ lệ LM và Harvard tính từ số từ tích cực, tiêu cực và tổng từ cũng khớp cả 971 hàng. Chi tiết kiểm tra và SHA-256 đầu vào nằm ở `verification.json`.

## Kết quả chính đã tính lại

Hồi quy C1 theo tone LM tỷ lệ, CAR [-1,+1]: hệ số **-0,272663**, p hai phía HC3 **0,212967**, p theo cụm công ty **0,269773**, N = 969. Đây không phải bằng chứng ở ngưỡng 5% cho đặc tả này. Các đặc tả C1/C3/C4 và bốn cửa sổ nằm đầy đủ ở `regression/regression_results.csv` (76 dòng, gồm cả hằng số).

Trên 971 filing so sánh được, tone LM và Harvard IV-4 trái dấu ở **861 filing (88,7%)**. Bảng từng hồ sơ ở `dictionary_comparison_filings.csv` và tổng hợp ở `dictionary_comparison_summary.csv`. Chỉ số trái dấu cho thấy hai cách đo khác nhau; nó không phải số trường hợp đã xác định đúng/sai của từng từ điển.

Theo bảng nghiên cứu sự kiện được chạy lại, CAAR [-1,+1] = **0,005699** (khoảng 0,570%), p MacKinlay = **0,00000000187**, N = 969. Phương sai CAR dùng xấp xỉ B4 của tài liệu công thức: số phiên trong cửa sổ nhân phương sai phần dư mô hình thị trường. Bốn cửa sổ và các phép kiểm định nằm ở `event_study/event_study_summary.csv`. Đây là phản ứng trung bình quanh ngày công bố, không tự chứng minh tone là nguyên nhân.

Brown–Warner A.11 và B7 cho cả bốn cửa sổ nằm ở `event_study/extended_window_tests.csv`; Corrado theo từng ngày ở `corrado_daily.csv`; B8 theo ba mức CAAR giả định ở `theoretical_power.csv`. Không dùng bảng B8 như power của H1 tone. Word Power ngoài năm kiểm định và H1/H2 được xuất riêng trong `word_power/`; đọc `word_power/RESULTS.md` trước khi diễn giải do danh sách tiêu cực dùng ridge và kết quả nhạy với penalty.

Các kiểm định B6 và đặc tả C5–C8 từ dữ liệu đang có nằm trong `event_study/b6_robustness_tests.csv`, `c5_reduced_results.csv`, `c6_delayed_results.csv`, `c7_cross_section_results.csv` và `c8_fama_macbeth_summary.csv`; bảng mẫu/hệ số theo năm nằm cạnh chúng. Đọc `ROBUSTNESS_RESULTS.md` để biết rõ cửa sổ, số quan sát, công thức rút gọn và giới hạn.

Các bảng `c2_matched4_results.csv`, `c2_full6_results.csv`, `c3_posneg_full6_results.csv` và `c5_full6_results.csv` dùng `EADRet` cùng Accruals trạng thái `PASS` mới bổ sung. Đọc `FULL_CONTROLS_REVIEW.md` và `full_controls_qa.json` để biết nguồn, quy tắc chọn mẫu 481 hồ sơ và giới hạn; không nhầm các mô hình tone tỷ lệ này với Word Power.

## C2 với biến kiểm soát có sẵn

Mô hình `c2_reduced_results.csv` dùng bốn biến kiểm soát Size, BM, Volatility và Turnover. Ghép bằng ticker và ngày nộp chuẩn `YYYY-MM-DD`, giữ các hàng `status=success` và đủ dữ liệu. Mỗi cửa sổ có **862 quan sát thuộc 96 công ty**; 107/969 hàng không đủ bộ biến kiểm soát.

Mô hình: `CAR = const + b·LM_net_prop + Size + BM + Volatility + Turnover + sai số`. BM là tỷ số book-to-market đã lưu ở cột `bm`; không thay bằng `log_bm`. Sai số chuẩn HC3 và theo cụm công ty đều được xuất.

| CAR | Hệ số tone | p HC3 hai phía | CI 95% HC3 | p theo cụm |
| --- | ---: | ---: | --- | ---: |
| [-1,+1] | -0,158993 | 0,473118 | [-0,593358; 0,275372] | 0,552013 |
| [0,+3] | -0,213287 | 0,351845 | [-0,662297; 0,235722] | 0,434193 |
| [-3,+3] | -0,571753 | 0,039689 | [-1,116540; -0,026965] | 0,075941 |
| [-5,+5] | 0,006216 | 0,986533 | [-0,715610; 0,728042] | 0,985423 |

Chạy lại bằng `python scripts/run_analysis.py` như README repo. Các tệp trong `analysis_outputs/` là đầu ra hiện hành; `filing_acceptance.csv`, `controls_item7.csv` và lịch chia tách là đầu vào cho bản tính này.
