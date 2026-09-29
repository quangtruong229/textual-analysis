# Bàn giao dữ liệu cho UX/UI

Đây là **hợp đồng dữ liệu**, không phải yêu cầu thiết kế giao diện. Các bảng trong `analysis_outputs/` là kết quả tính sẵn; phía UX/UI chỉ đọc và hiển thị. Mở `manifest.json` để lấy đường dẫn, danh sách cột, số hàng và SHA-256 của từng CSV. Chạy `python scripts/validate_handoff.py` sau mỗi lần cập nhật kết quả; lệnh sẽ dừng nếu khóa, cỡ mẫu hoặc đơn vị hiển thị không còn đúng.

## Bảng nên dùng

| Vai trò | Tệp | Khóa / số hàng |
| --- | --- | --- |
| Hồ sơ, tone từng công ty–năm nộp và CAR | `analysis_outputs/tone_firm_year.csv` | `ticker` + `filing_date`; 1.000 hàng, có cờ thiếu dữ liệu |
| LM so với Harvard | `analysis_outputs/dictionary_comparison_summary.csv`, `dictionary_comparison_filings.csv` | Một hàng tổng hợp và 971 hồ sơ |
| CAR từng hồ sơ | `analysis_outputs/event_study/event_filing_results.csv` | `ticker` + `filing_date`; 969 hàng |
| AR trung bình từng ngày và CAAR theo cửa sổ | `analysis_outputs/event_study/event_daily_summary.csv`, `event_study_summary.csv` | 11 ngày tương đối, 4 cửa sổ |
| Hồi quy C1/C3/C4 | `analysis_outputs/regression/regression_results.csv` | 76 dòng hệ số; lọc theo `model`, `term`, `dependent_variable` |
| Hồi quy C2 rút gọn | `analysis_outputs/c2_reduced_results.csv` | 24 dòng hệ số; N=862, 96 công ty |
| Hồ sơ không vào tone/CAR | `analysis_outputs/missing_filings.csv` | 31 hồ sơ; trạng thái tone và sự kiện rõ ràng |

## Quy tắc hiển thị bắt buộc

- **Năm:** `filing_year` là năm nộp 10-K, không phải năm tài chính. `report_year` lấy từ ngày kết thúc kỳ báo cáo. Có 66 hồ sơ nộp năm 2016 nhưng kỳ báo cáo kết thúc năm 2015. Ghi nhãn rõ “năm nộp” nếu lọc theo `filing_year`.
- **Đơn vị:** `CAR`, `CAAR`, `AAR` là lợi suất dạng số thập phân. Ví dụ `0.004` = `0,4%` khi hiển thị. `lm_net_prop` và `harvard_net_prop` là tỷ lệ tone; không hiển thị trực tiếp như phần trăm lợi suất.
- **Dữ liệu thiếu:** `has_method_score` và `has_event_car` cho biết có số đo hay không. Ô trống là thiếu dữ liệu, **không phải 0**. Panel giữ cả 1.000 hồ sơ; có 971 tone và 969 CAR. Không tự drop hàng thiếu khi trình bày tổng mẫu.
- **Hồi quy:** p-value HC3 nằm ở `p_hc3_two_sided`, p gom cụm công ty ở `p_cluster_two_sided`. Đừng trộn hai loại mà không ghi nhãn. Bảng hồi quy là kết quả mẫu cố định; bộ lọc công ty/năm trên trang không được làm như hệ số đã tính lại theo bộ lọc.
- **Kết luận:** CAAR quanh ngày nộp khác 0 không chứng minh tone gây biến động giá. LM và Harvard trái dấu ở 861/971 hồ sơ nhưng chưa có nhãn thủ công để gọi đó là 861 lỗi của Harvard. C2 là bản **rút gọn**, thiếu EADRet và Accruals.

## Nội dung tham khảo

`docs/METHODOLOGY.md` giải thích công thức, mẫu và kiểm tra. `analysis_outputs/RESULTS_PRESENTATION.md` trình bày kết quả từ bảng CSV. `analysis_outputs/ASSIGNMENT_AUDIT.md` nêu phần nào đã có và giới hạn. `app_local.py` là trang xem dữ liệu đơn giản để tham khảo nội dung, **không áp đặt thiết kế UX/UI**.

Không cần đưa `analysis_outputs/event_study/estimation_ar_long.csv` (30 MB) vào giao diện; đó là bảng kiểm tra nội bộ của cửa sổ ước lượng. HTML/MD&A 10-K gốc không có trong ZIP nên không hứa tính lại tone từ văn bản ngay trên giao diện.
