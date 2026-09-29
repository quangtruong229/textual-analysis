# Đối chiếu phần tính toán với yêu cầu Đề án 5

Đánh giá này dựa trên bốn nội dung cốt lõi trong ảnh đề bài và dữ liệu đang có ở thư mục `D:\nhóm 5\textual-analysis`. Nó không chấm điểm UI/UX, thuyết trình hay tài liệu của thành viên khác.

| Nội dung yêu cầu | Hiện trạng phần tính toán | Minh chứng | Việc còn thiếu |
| --- | --- | --- | --- |
| Thu thập báo cáo SEC 10-K | Có metadata 1.000 filing của 100 công ty, mỗi công ty 10 năm **nộp** 2016–2025; có URL SEC trong bảng bàn giao | `data/metadata/filings_2016_2025.csv`, `tone_firm_year.csv`, mã tải ở `src/download_10k.py` | ZIP không chứa HTML 10-K gốc, không thể kiểm chứng lại mọi bước trích từ nguồn local |
| Làm sạch, đếm tích cực/tiêu cực/bất định theo LM | Có từ điển LM, mã xử lý và 971 bảng tone Item 7 dùng được; 29 hồ sơ bị loại có trạng thái rõ | `data/dictionary/`, `src/build_method_scores.py`, `data/metadata/lm_tone.csv`, `missing_filings.csv` | Thiếu văn bản MD&A đã trích, nên chưa chạy lại A1–A3 từ chữ gốc; kiểm tra hiện tại chỉ xác nhận số học từ bảng đếm đã cho |
| Tone theo doanh nghiệp và năm | Đã xuất panel 1.000 hàng theo **năm nộp**, trong đó 971 tone hợp lệ; 100 công ty đều có hàng cho từng năm nộp 2016–2025 | `tone_firm_year.csv` | Không trình bày 29 tone thiếu như số 0. Năm nộp khác năm tài chính; 66 filing nộp 2016 báo cáo kỳ kết thúc 2015 |
| Nghiên cứu sự kiện AR/CAR | Đã chạy lại từ 279.958 hàng giá; 969 sự kiện, 4 cửa sổ CAR, kiểm tra tổng AR thành CAR không sai khác | `event_study/`, `verification.json` | Hai hồ sơ có tone thiếu đủ lịch sử giá ước lượng; nêu mẫu N=969 khi báo cáo kết quả |
| Từ điển tổng quát so với LM | Đã so sánh 971 filing; 861 tone trái dấu; có hồi quy C4 | `dictionary_comparison_summary.csv`, `dictionary_comparison_filings.csv`, `regression/regression_results.csv` | Chưa có kiểm định thủ công trên ngữ cảnh gốc hoặc nhãn chuẩn để khẳng định trường hợp nào là phân loại sai |
| Tone và phản ứng thị trường | Có hồi quy C1/C3/C4 tính lại và C2 rút gọn với HC3, cụm công ty; đầu ra và mẫu rõ ràng | `regression/`, `c2_reduced_results.csv`, `c2_reduced_sample.csv` | C2 đầy đủ thiếu EADRet và Accruals; không được gọi bản rút gọn là đầy đủ. Không suy luận nhân quả từ hệ số |

**Kết luận:** Phần tính toán hiện có đủ bảng kết quả chính để nhóm trình bày một nghiên cứu thực nghiệm có giới hạn rõ ràng. **Chưa đủ để cam kết toàn bộ sản phẩm đã đáp ứng đề bài** nếu giảng viên yêu cầu nộp HTML 10-K gốc, chạy lại tone từ văn bản, minh họa lỗi từ điển bằng ngữ cảnh, báo cáo học thuật và phần trình bày. Những phần đó cần được nhóm xử lý hoặc ghi thành giới hạn minh bạch.
