# Phân tích định lượng 10-K

Dự án xử lý và kiểm tra dữ liệu theo [bộ công thức](docs/Cong_thuc_dinh_luong.docx) do nhóm cung cấp: tính AR/CAR từ bảng giá, hồi quy liên hệ tone với CAR, tạo bảng theo công ty–năm nộp và xuất phần trình bày kết quả. Có trang local để xem nhanh; thiết kế UX/UI của sản phẩm do thành viên phụ trách thực hiện riêng.

## Cài đặt và chạy

Dùng **Python 3.12**, kích hoạt môi trường ảo của bạn và chạy các lệnh sau từ thư mục gốc của repo:

```bash
python -m pip install -r requirements.txt
python scripts/run_analysis.py
```

Sau bước cài thư viện, lệnh phân tích chạy **offline từ các CSV có sẵn trong repo**. Mặc định lệnh này tính lại nghiên cứu sự kiện từ bảng giá và giờ SEC chấp nhận hồ sơ, chạy C1/C3/C4, C2 bốn controls và C2/C3/C5 sáu controls từ dữ liệu bổ sung, tạo bảng công ty–năm, rồi kiểm tra tính nhất quán và xuất kết quả. Thứ tự chạy được quản lý trong `scripts/run_analysis.py`; không cần chạy rời từng bước. Tính AR/CAR từ gần 280.000 hàng giá sẽ lâu hơn riêng bước hồi quy. Terminal hiển thị tiến trình; các bảng đầy đủ được lưu trong `analysis_outputs/`.

Lệnh này cũng tính Brown–Warner cho bốn cửa sổ, kiểm tra tự tương quan B7, Corrado theo ngày và sức mạnh kiểm định lý thuyết B8. Các bảng nằm trong `analysis_outputs/event_study/`. Bước Word Power dùng tần suất từ Item 7 sau phủ định A1, ước lượng trọng số ngoài năm đang chấm điểm và chạy H1/H2 với sáu controls. Đọc [`analysis_outputs/word_power/RESULTS.md`](analysis_outputs/word_power/RESULTS.md): từ tiêu cực dùng ridge theo cỡ mẫu, nên không phải bản tái lập nguyên xi OLS của Jegadeesh–Wu.

Lệnh còn xuất các kiểm định độ vững B6 và đặc tả C5–C8 có thể ước lượng từ dữ liệu hiện có. Đọc [`analysis_outputs/ROBUSTNESS_RESULTS.md`](analysis_outputs/ROBUSTNESS_RESULTS.md) trước khi dùng các bảng: C5/C7 và một đặc tả C8 là mô hình rút gọn; C6 dùng các phiên `[+5,+5]`, `[+5,+10]`, `[+5,+22]` và loại hồ sơ thiếu giá trong từng cửa sổ. Không dùng các kết quả này thay cho Word Power hoặc C2 đầy đủ.

Hai bảng `EADRet` và `Accruals` mới từ nhánh `finalize-eadret-accruals` được ghép vào **một đặc tả sáu biến kiểm soát riêng**, giữ nguyên bốn controls và CAR hiện hành. Chỉ dùng `Accruals` trạng thái `PASS`; mẫu C2 sáu controls còn 481 hồ sơ thuộc 71 công ty. Đọc [`analysis_outputs/FULL_CONTROLS_REVIEW.md`](analysis_outputs/FULL_CONTROLS_REVIEW.md) để xem kết quả và đối chứng bốn controls trên cùng 481 hồ sơ. Điểm tone vẫn là LM dạng tỷ lệ, chưa phải Word Power.

## Dữ liệu và kết quả

`data/` giữ dữ liệu đầu vào của nhóm. **Nguồn kết quả dùng cho trình bày là `analysis_outputs/`**, kể cả CAR trong bảng công ty–năm. Chạy `scripts/run_analysis.py` để tái tạo bộ kết quả từ các đầu vào này.

Đọc [luồng xử lý](docs/data_pipeline.md), [phương pháp](docs/METHODOLOGY.md), [kết quả và diễn giải](analysis_outputs/RESULTS_PRESENTATION.md), [đối chiếu yêu cầu đề án](analysis_outputs/ASSIGNMENT_AUDIT.md) và [kiểm tra dạng máy đọc](analysis_outputs/verification.json). `handoff/manifest.json` lưu danh sách bảng, cột, đơn vị và mã kiểm tra tệp.

Mẫu đầu vào gồm 1.000 hồ sơ của 100 công ty, theo **năm nộp 2016–2025**, không đồng nghĩa năm tài chính. Lệnh phân tích đọc tone từ `data/metadata/tone_method_item7.csv`, giờ công bố từ `data/metadata/filing_acceptance.csv`, tính AR/CAR từ `data/market_data/daily_prices.csv` và ước lượng các mô hình hồi quy. C2 dùng bốn biến kiểm soát Size, BM, Volatility và Turnover; lịch chia tách ở `data/market_data/stock_splits.csv` giữ giá và số cổ phiếu trên cùng một cơ sở.

### Corpus Item 7 tải từ SEC

`data/item7_corpus/manifest.csv` ghi URL SEC, accession, SHA-256 và trạng thái của 1.000 hồ sơ. `item7_term_counts.csv.gz` là bảng tần suất `ticker, filing_date, accession_number, term, count` cho 971 Item 7 đạt QA. `verification.json` đối chiếu tần suất và các đếm LM, gồm quy tắc phủ định A1, với bảng tone cũ. HTML 10-K gốc (khoảng 4,4 GB), văn bản sạch và Item 7 được giữ trong `data/raw/`, `data/processed/`, `data/sections_v3/` trên máy chạy, không đưa vào Git; có thể tải lại từ URL trong manifest.

Để tái tạo corpus, đặt biến môi trường `SEC_USER_AGENT` bằng tên nhóm và email liên hệ thật, rồi chạy `python scripts/fetch_item7_corpus.py --all --workers 4` và `python scripts/verify_item7_corpus.py`. Mặc định không có `--all`, lệnh đầu chỉ thử 10 hồ sơ và ghi `pilot_manifest.csv`, không thay manifest toàn mẫu. Bảng `item7_lm_sentiment_counts.csv.gz` lưu tần suất từng từ LM sau phủ định A1; `python scripts/run_analysis.py` dùng bảng này để tính lại Word Power và hồi quy offline.

## Xem nhanh trên máy

Sau khi chạy phân tích, mở trang local bằng:

```bash
python -m streamlit run app_local.py --server.address 127.0.0.1
```

Trang chỉ đọc các bảng đã tính. Hai mục **Kết quả & diễn giải** và **Phương pháp** trình bày cách đọc kết quả, công thức và giới hạn. Nếu tính lại dữ liệu khi trang đang mở, khởi động lại trang để đọc đầu ra mới.

`analysis_outputs/RESULTS_PRESENTATION.md` được tạo từ cùng CSV với trang local. Có thể xuất lại riêng nội dung này bằng `python scripts/export_presentation.py`.
