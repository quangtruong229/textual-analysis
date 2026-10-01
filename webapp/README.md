# Webapp: Textual Analysis in Finance — Quant Research Lab

> Trang xem kết quả phân tích Item 7 của 1.000 hồ sơ 10-K, 100 công ty, năm nộp 2016–2025 và CAR với chỉ số đối chứng S&P 500.

---

## 📖 Tài liệu Sản phẩm Chi tiết
Xem phạm vi dữ liệu, mô hình và giới hạn diễn giải tại:
👉 **[PRODUCT_DESCRIPTION.md](PRODUCT_DESCRIPTION.md)**

---

## 🚀 Hướng dẫn Chạy Ứng dụng

### Cách 1: Khởi động Local Web Server (Khuyên dùng)
Từ thư mục gốc dự án (`textual-analysis`), mở terminal PowerShell và chạy:
```powershell
python webapp/build_data.py
python -m http.server 8000 --directory webapp
```
Truy cập qua trình duyệt: **[http://localhost:8000](http://localhost:8000)**

### Cách 2: Mở trực tiếp file HTML
```powershell
Start-Process "webapp/index.html"
```
Hoặc mở trực tiếp file `webapp/index.html` trong trình duyệt Chrome / Edge.

---

## 🛠 Cấu trúc Thư mục `webapp/`
- `index.html`: Cấu trúc giao diện web, tích hợp KaTeX và Chart.js.
- `app.js`: Toàn bộ logic giao diện, phân loại tín hiệu tone, lọc dữ liệu, vẽ biểu đồ zoom/pan.
- `style.css`: Hệ thống thiết kế Fintech (Design tokens, Dark/Light mode, animations).
- `data.js`: Dữ liệu JSON tổng hợp từ các file kết quả CSV trong `analysis_outputs/`.
- `build_data.py`: Script tự động đọc CSV và đóng gói thành `data.js`.
- `PRODUCT_DESCRIPTION.md`: Phạm vi dữ liệu, phương pháp và giới hạn kết quả.

`data.js` là bản đóng gói tại thời điểm chạy `build_data.py`; sau khi cập nhật CSV hoặc manifest, cần dựng lại file này và kiểm tra tab Hồi quy/Audit. Webapp không chạy hồi quy và không đọc trực tiếp HTML 10-K. Hệ số là kết quả toàn mẫu đã lưu; lọc bảng hồ sơ không ước lượng lại mô hình.
