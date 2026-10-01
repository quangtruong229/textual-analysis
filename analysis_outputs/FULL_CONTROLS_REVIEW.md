# Bổ sung EADRet và Accruals vào mô hình hiện hành

Nguồn: hai CSV ở `data/metadata/controls/` được chép nguyên từ nhánh GitHub `finalize-eadret-accruals` (commit `0ee574c`). `EADRet` dùng phản ứng lợi suất quanh 8-K Item 2.02 trước ngày chấp nhận 10-K, điều chỉnh theo `^GSPC`; `Accruals` dùng các thành phần Sloan từ SEC Company Facts. Mã kiểm tra accession, kỳ báo cáo, thứ tự ngày, số học và trạng thái từng hàng trước khi ghép. Bốn controls còn lại và AR/CAR vẫn là phiên bản đang dùng trên `main`; không thay bằng bảng `controls_item7_final6.csv` ở nhánh khác vì quy tắc Size/BM/Turnover khác.

Trong 1.000 hồ sơ, `EADRet` có **991** hàng `success`. `Accruals` có **571** hàng `PASS`, 341 hàng `WARN` và 88 hàng thiếu cấu trúc. Chỉ `PASS` được vào mô hình chính; giá trị số ở hàng `WARN` không được xem như đã đạt chuẩn. Giao với mẫu bốn controls và CAR còn **481 hồ sơ, 71 công ty**. C5 có thêm điều kiện tone năm liền trước nên còn **431 hồ sơ**.

## C2 — sáu controls, tone LM net dạng tỷ lệ

`CAR = a + b·LM_net_prop + Size + BM + Volatility + Turnover + EADRet + Accruals + ε`. Hai cột bốn-controls bên trái được ước lượng lại **trên cùng 481 hồ sơ** để tách thay đổi đặc tả khỏi thay đổi cỡ mẫu. p HC3 và p cụm công ty của mô hình sáu controls đều nằm trong CSV.

| Cửa sổ | b bốn controls, cùng mẫu | p HC3 | b sáu controls | p HC3 | p cụm |
| --- | ---: | ---: | ---: | ---: | ---: |
| [-1,+1] | -0.0601 | 0.8586 | -0.0303 | 0.9299 | 0.9340 |
| [0,+3] | -0.0808 | 0.8349 | -0.0613 | 0.8779 | 0.8702 |
| [-3,+3] | -0.1276 | 0.7659 | -0.0841 | 0.8478 | 0.8380 |
| [-5,+5] | 0.2601 | 0.6596 | 0.2988 | 0.5993 | 0.4922 |

## C3 và C5 với sáu controls

C3 đưa đồng thời positive và negative tone **dạng tỷ lệ** vào mô hình với sáu controls. Ở `[0,+3]`, hệ số positive = -0.4349 (p HC3 0.5020, p cụm 0.4516); negative = -0.0072 (p HC3 0.9865, p cụm 0.9848). Đây chưa phải H1/H2 viết bằng Word Power.

C5 dùng tone hiện tại làm biến phụ thuộc, sáu controls và tone năm nộp liền trước, chuẩn hóa các biến giải thích trên mẫu hoàn chỉnh. Hệ số tone trễ chuẩn hóa = 0.003592, p HC3 = 2.554e-37, p cụm = 1.402e-18.

Hai bảng nguồn là dữ liệu đã tính sẵn từ nhánh khác. Kiểm tra ở đây xác nhận khóa, thời gian và số học nhưng không tái dựng độc lập mọi SEC Company Fact hay 8-K từ đầu. Cột `word_power` ở nhánh nguồn chỉ là TF-IDF chưa chuẩn hóa; không dùng cột đó trong các mô hình tỷ lệ của báo cáo này. Word Power ước lượng từ tần suất từng từ được báo riêng tại `word_power/RESULTS.md`. Các kết quả hồi quy mô tả liên hệ trong mẫu nhỏ hơn và không chứng minh tác động nhân quả.
