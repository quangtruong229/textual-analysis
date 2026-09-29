# Phân tích định lượng 10-K

Dự án này chỉ xử lý và kiểm tra dữ liệu theo [bộ công thức](docs/Cong_thuc_dinh_luong.docx) do nhóm cung cấp. Không có giao diện hay API trong phần bàn giao này. Mã gốc và các bảng trong ZIP được giữ ở `src/` và `data/`; kết quả chạy lại nằm riêng ở `analysis_outputs/`.

Với môi trường Python có `pandas`, `numpy`, `scipy` và `statsmodels`, chạy từ thư mục này:

```bash
python scripts/recompute_from_supplied.py
python scripts/calculate_c2_controls.py
python scripts/verify_recalculation.py
```

Để **tính lại nghiên cứu sự kiện từ bảng giá** thay vì dùng bảng kết quả đã lưu, chạy `python scripts/recompute_from_supplied.py --force-event`. Bước này đọc gần 280.000 hàng giá, xử lý 971 filing có tone và mất lâu hơn C2. Lệnh C2 chỉ ghép 969 hàng tone/CAR với biến kiểm soát và ước lượng bốn hồi quy nên chạy trong vài giây. Đầu ra đầy đủ là các CSV trong `analysis_outputs/`, không chỉ các dòng tóm tắt trên terminal.

Đọc [báo cáo kết quả](analysis_outputs/README.md), [đối chiếu yêu cầu đề án](analysis_outputs/ASSIGNMENT_AUDIT.md) và [kiểm tra dạng máy đọc](analysis_outputs/verification.json). ZIP không chứa văn bản MD&A đã trích từ 10-K; vì vậy bước đếm từ, xử lý phủ định và tf.idf được kiểm tra ở mức bảng tone đã cung cấp, chưa thể chạy lại từ văn bản gốc.

```bash
python scripts/build_firm_year_panel.py
python scripts/summarize_dictionary_comparison.py
```

Hai lệnh cuối tạo bảng tone theo công ty–năm nộp và so sánh từ điển LM với Harvard IV-4.

Để xem nhanh kết quả trên máy (không cần giao diện hoàn thiện):

```bash
python -m streamlit run app_local.py --server.address 127.0.0.1
```

Trang này chỉ đọc bảng đã tính, không tải thêm dữ liệu hoặc tính lại mô hình. Hai mục **Kết quả & diễn giải** và **Phương pháp** trình bày đầy đủ cách đọc các bảng, công thức và giới hạn. Nội dung kết quả được tạo từ CSV hiện tại; phần phương pháp ở `docs/METHODOLOGY.md`.

Nếu cần bản Markdown để gửi cho người viết báo cáo, chạy `python scripts/export_presentation.py`; bản kết quả xuất ở `analysis_outputs/RESULTS_PRESENTATION.md` và dùng cùng nguồn số liệu với trang local.
