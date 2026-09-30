# Webapp: Textual Analysis in Finance — Quant Research Lab

> Nền tảng phân tích định lượng giọng điệu báo cáo 10-K (Item 7 MD&A) và phản ứng giá cổ phiếu (NYSE / Nasdaq 100, 2016–2025, Benchmark S&P 500).

---

## 📖 Tài liệu Sản phẩm Chi tiết
Xem toàn bộ mô tả sản phẩm, tính năng cốt lõi và tính năng phụ chứng minh giá trị cho nhà đầu tư tại:
👉 **[PRODUCT_DESCRIPTION.md](PRODUCT_DESCRIPTION.md)**

---

## 🚀 Hướng dẫn Chạy Ứng dụng

### Cách 1: Khởi động Local Web Server (Khuyên dùng)
Từ thư mục gốc dự án (`textual-analysis`), mở terminal PowerShell và chạy:
```powershell
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
- `PRODUCT_DESCRIPTION.md`: Bản mô tả sản phẩm toàn diện và tính ứng dụng thực chiến cho nhà đầu tư.
