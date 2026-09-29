# Phân tích định lượng 10-K

Dự án xử lý và kiểm tra dữ liệu theo [bộ công thức](docs/Cong_thuc_dinh_luong.docx) do nhóm cung cấp: tính AR/CAR từ bảng giá, hồi quy liên hệ tone với CAR, tạo bảng theo công ty–năm nộp và xuất phần trình bày kết quả. Có trang local để xem nhanh; thiết kế UX/UI của sản phẩm do thành viên phụ trách thực hiện riêng.

## Cài đặt và chạy

Dùng **Python 3.12**, kích hoạt môi trường ảo của bạn và chạy các lệnh sau từ thư mục gốc của repo:

```bash
python -m pip install -r requirements.txt
python scripts/run_analysis.py
```

Sau bước cài thư viện, lệnh phân tích chạy **offline từ các CSV có sẵn trong repo**. Mặc định lệnh này tính lại nghiên cứu sự kiện từ bảng giá, chạy C1/C3/C4 và C2 rút gọn, tạo bảng công ty–năm và so sánh từ điển, rồi kiểm tra tính nhất quán và xuất kết quả. Thứ tự chạy được quản lý trong `scripts/run_analysis.py`; không cần chạy rời từng bước. Tính AR/CAR từ gần 280.000 hàng giá sẽ lâu hơn riêng bước hồi quy C2. Terminal hiển thị tiến trình; các bảng đầy đủ được lưu trong `analysis_outputs/`.

## Dữ liệu và kết quả

`data/` giữ dữ liệu đầu vào do nhóm cung cấp. Các bảng sự kiện/hồi quy cũ trong `data/metadata/event_study_final/` và `data/metadata/regression_analysis/` được giữ để đối chiếu lịch sử. **Nguồn kết quả hiện hành là `analysis_outputs/`**, kể cả CAR trong bảng công ty–năm. Kết quả sau sửa lỗi phương pháp có thể khác bảng cũ; việc trùng với bảng cũ không phải điều kiện để xác nhận phép tính đúng.

Đọc [luồng xử lý](docs/data_pipeline.md), [phương pháp](docs/METHODOLOGY.md), [kết quả và diễn giải](analysis_outputs/RESULTS_PRESENTATION.md), [đối chiếu yêu cầu đề án](analysis_outputs/ASSIGNMENT_AUDIT.md) và [kiểm tra dạng máy đọc](analysis_outputs/verification.json). `handoff/manifest.json` lưu danh sách bảng, cột, đơn vị và mã kiểm tra tệp.

Mẫu đầu vào gồm 1.000 hồ sơ của 100 công ty, theo **năm nộp 2016–2025**, không đồng nghĩa năm tài chính. Repo không có HTML 10-K hoặc văn bản MD&A đã trích. Vì vậy tính toán hiện tại dùng bảng tone được cung cấp; chỉ kiểm tra được số học từ các cột đếm từ, chưa tính lại đếm từ, phủ định và tf.idf từ văn bản gốc. C2 là **mô hình rút gọn** vì thiếu EADRet và Accruals.

## Xem nhanh trên máy

Sau khi chạy phân tích, mở trang local bằng:

```bash
python -m streamlit run app_local.py --server.address 127.0.0.1
```

Trang chỉ đọc các bảng đã tính. Hai mục **Kết quả & diễn giải** và **Phương pháp** trình bày cách đọc kết quả, công thức và giới hạn. Nếu tính lại dữ liệu khi trang đang mở, khởi động lại trang để đọc đầu ra mới.

`analysis_outputs/RESULTS_PRESENTATION.md` được tạo từ cùng CSV với trang local. Có thể xuất lại riêng nội dung này bằng `python scripts/export_presentation.py`.
