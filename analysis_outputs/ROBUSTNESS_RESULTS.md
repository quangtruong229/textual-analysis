# Kiểm định độ vững B6 và mô hình C5–C8

Các bảng này dùng **tone LM dạng tỷ lệ**, không dùng Word Power. Đây là phân tích bổ sung từ đầu vào hiện có; hệ số hồi quy là quan hệ trong mẫu, không chứng minh nhân quả. B6 kiểm tra **CAAR trung bình**, không kiểm định hệ số tone.

## B6 — hai kiểm định bổ sung

Kiểm định chuẩn hóa chia CAR từng hồ sơ cho độ lệch chuẩn AR của 239 ngày ước lượng và căn bậc hai số ngày sự kiện, rồi cộng qua hồ sơ theo giả định độc lập chéo. Kiểm định phương sai cắt ngang dùng đúng phương sai Eq. 21 trong tài liệu công thức. Do các sự kiện có thể trùng ngày, giả định độc lập chéo cần được cân nhắc khi diễn giải p-value.

| Cửa sổ | N | p chuẩn hóa | p phương sai cắt ngang |
| --- | ---: | ---: | ---: |
| CAR_m1_p1 | 969 | 3.644e-07 | 2.489e-05 |
| CAR_0_p3 | 969 | 0.0008254 | 0.000419 |
| CAR_m3_p3 | 969 | 0.0005436 | 0.0003166 |
| CAR_m5_p5 | 969 | 0.001278 | 0.0006772 |

## C5 — yếu tố quyết định tone, bản rút gọn

Hồi quy `LM_net_prop` theo Size, BM, Volatility, Turnover và tone của **hồ sơ năm nộp liền trước**. Năm trước thiếu tone thì không thay bằng năm cũ hơn. Các biến giải thích được chuẩn hóa trên mẫu hồi quy; tone phụ thuộc giữ đơn vị tỷ lệ. Mẫu còn **769 hồ sơ, 96 công ty**. Hệ số tone trễ chuẩn hóa = 0.004733, p HC3 = 1.16e-162, p cụm công ty = 5.471e-34. Đây chưa phải Eq. 11 đầy đủ vì thiếu EADRet và Accruals.

## C6 — phản ứng chậm

Mã tính tổng AR từ phiên `+5` tới `+T` theo mô hình thị trường đã ước lượng trước sự kiện. Đúng theo cách viết Eq. 17 trong file nhóm, cửa sổ `[+5,+5]` chỉ có một ngày; ba cửa sổ **đều bao gồm ngày +5**. Hồ sơ thiếu bất kỳ phiên nào của cửa sổ bị loại khỏi riêng hồi quy đó.

| Cửa sổ | N | Hệ số LM net tỷ lệ | p HC3 | p cụm công ty |
| --- | ---: | ---: | ---: | ---: |
| [+5,+5] | 969 | 0.1431 | 0.1751 | 0.2072 |
| [+5,+10] | 969 | -0.0623 | 0.8194 | 0.8305 |
| [+5,+22] | 963 | 0.2296 | 0.6156 | 0.5339 |

## C7 — hồi quy cắt ngang AR ngày 0

AR ngày 0 được hồi quy theo LM net tỷ lệ và bốn biến kiểm soát, với HC3 và sai số chuẩn cụm công ty. N = 862; hệ số tone = -0.1454, p HC3 = 0.3354, p cụm = 0.2924. C2 rút gọn đã bao phủ đặc tả tương ứng với CAR; bảng C7 này bổ sung **AR ngày 0**, tránh lặp cùng một hồi quy dưới tên khác.

## C8 — Fama–MacBeth theo năm nộp

Hồi quy cắt ngang riêng cho từng năm 2016–2025, sau đó lấy trung bình **10 hệ số năm** và tính sai số chuẩn từ độ phân tán giữa các năm (t với 9 bậc tự do). Dùng CAR `[0,+3]`. Đặc tả C1 tỷ lệ: hệ số tone trung bình = -0.2800, p = 0.1708; đặc tả C2 rút gọn: -0.2888, p = 0.1094. Chỉ có 10 năm, nên sức mạnh kiểm định hạn chế; cả hai mô hình không dùng Word Power.

Các CSV trong `analysis_outputs/` và `analysis_outputs/event_study/` lưu toàn bộ hệ số, p-value, cỡ mẫu và hồ sơ. C2/C5 sáu controls từ hai bảng mới được tính riêng bởi `calculate_full_controls.py` và giải thích ở `FULL_CONTROLS_REVIEW.md`. Word Power, kiểm tra ngữ cảnh từng từ và khả năng tái tạo bước xử lý văn bản vẫn cần dữ liệu gốc bổ sung.
