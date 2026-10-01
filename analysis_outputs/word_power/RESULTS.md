# Word Power và kiểm định H1/H2

Đầu vào là 971 Item 7 đã tải từ SEC, bảng tần suất **sau quy tắc phủ định A1** tại `data/item7_corpus/item7_lm_sentiment_counts.csv.gz`, và CAR mô hình thị trường. Với mỗi năm nộp, trọng số từ được ước lượng từ **mọi năm khác năm đó**; năm được chấm điểm không tham gia bước ước lượng trọng số của chính mình. Biến mục tiêu bước ước lượng là CAR `[0,+3]`. Điểm bằng tổng `w_j × F_ij / a_i`, với `a_i` là số token Item 7, rồi chuẩn hóa hệ số từ theo Eq. 7 của [Jegadeesh–Wu (2013)](https://repository.upenn.edu/server/api/core/bitstreams/caf9d0c9-0de5-475a-ac72-f6e4ad3bfce5/content).

Danh sách tích cực dùng OLS Eq. 6, chỉ giữ từ xuất hiện trong ít nhất 5 văn bản huấn luyện. Ma trận có đủ hạng ở cả 10 lần ước lượng (197–201 từ). Danh sách tiêu cực có nhiều từ so với cỡ mẫu; để giảm hệ số bất ổn, bước Eq. 6 dùng **ridge**, chọn penalty bằng kiểm tra chéo theo năm trong tập huấn luyện, sau khi chuẩn hóa Score và hiệu chỉnh Eq. 8. Đây là **điều chỉnh cho mẫu nhỏ**, không phải tái lập nguyên xi ước lượng OLS của bài gốc. 9/10 lần chọn mức phạt cao nhất của lưới, cho thấy trọng số tiêu cực thiếu ổn định.

Điểm Word Power của **cả hai danh sách** càng cao thì ngôn từ càng gắn với CAR cao trong tập huấn luyện. Do đó dấu kỳ vọng cho H2 Word Power là **dương**; dấu âm chỉ áp dụng cho tỷ lệ từ tiêu cực chưa điều chỉnh trọng số. Các mô hình dưới đây dùng CAR `[0,+3]`; p một phía kiểm tra hệ số `> 0`, đúng chiều giả thuyết. Cột hiệu ứng là thay đổi CAR tính bằng **điểm phần trăm** khi Score tăng một độ lệch chuẩn trong đúng mẫu của mô hình.

| Mô hình | N | Hệ số/1 đơn vị Score | CAR điểm %/1 SD | p HC3 một phía | p cụm công ty một phía |
| --- | ---: | ---: | ---: | ---: | ---: |
| H1, C1 | 969 | -5.2487 | -0.132 | 0.7967 | 0.7802 |
| H2, C1 | 969 | 0.0745 | +0.007 | 0.4868 | 0.4901 |
| H1, C2 đủ 6 controls | 481 | -9.5604 | -0.226 | 0.8585 | 0.8333 |
| H2, C2 đủ 6 controls | 481 | -3.1214 | -0.279 | 0.8404 | 0.8278 |

Các hệ số H1/H2 trong đặc tả chính không đạt mức 5% theo chiều kỳ vọng. Bảng `regression_results.csv` còn chứa C3 dùng đồng thời hai Score, ba cửa sổ CAR còn lại và mô hình tone tỷ lệ trên cùng mẫu để đối chiếu. Mẫu sáu controls chỉ dùng 481 hồ sơ của 71 công ty có Accruals `PASS` và các biến còn lại hợp lệ.

## Độ nhạy của danh sách tiêu cực

Đây là hồi quy `[0,+3]` khi cố định penalty ở các mức khác nhau; p trong bảng là **hai phía**. Hiệu ứng cùng đơn vị điểm phần trăm CAR cho một độ lệch chuẩn Score.

| Ridge alpha | Mô hình | CAR điểm %/1 SD | p HC3 hai phía | p cụm hai phía |
| ---: | --- | ---: | ---: | ---: |
| 1,000 | C1 | -0.041 | 0.8174 | 0.8775 |
| 1,000 | C2_six_controls | -0.402 | 0.1109 | 0.2360 |
| 10,000 | C1 | +0.114 | 0.5794 | 0.7084 |
| 10,000 | C2_six_controls | -0.266 | 0.3670 | 0.4918 |
| 100,000 | C1 | +0.111 | 0.5972 | 0.7172 |
| 100,000 | C2_six_controls | -0.223 | 0.4475 | 0.5548 |
| 1,000,000 | C1 | +0.103 | 0.6217 | 0.7353 |
| 1,000,000 | C2_six_controls | -0.219 | 0.4523 | 0.5577 |

`qa.json` ghi số từ, bậc hạng, số hồ sơ huấn luyện và penalty của từng năm; `annual_weights.csv.gz` lưu trọng số từng từ. Các p-value HC3 và cụm công ty **điều kiện trên Score đã ước lượng**; chúng chưa phản ánh đầy đủ bất định ở bước tạo trọng số. Mẫu 100 công ty/10 năm, cách đo CAR theo mô hình thị trường, lọc từ ít xuất hiện và ridge cho từ tiêu cực đều khác bài J&W. Kết quả mô tả liên hệ, không chứng minh quan hệ nhân quả hoặc khả năng giao dịch sinh lời.
