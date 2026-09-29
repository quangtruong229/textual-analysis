# Kết quả và diễn giải

## Mẫu thực nghiệm

Danh sách đầu vào gồm **1,000 hồ sơ của 100 công ty**, mỗi công ty có một báo cáo cho từng **năm nộp** 2016–2025. Item 7 đủ điều kiện tạo điểm tone ở **971 hồ sơ**; **969 hồ sơ** có thêm AR/CAR. C2 rút gọn còn **862 hồ sơ thuộc 96 công ty** sau khi đòi hỏi đủ bốn biến kiểm soát. Có 66 hồ sơ nộp năm 2016 với kỳ báo cáo kết thúc năm 2015; vì vậy “năm nộp” phải được phân biệt với “năm tài chính”.

## Phản ứng giá quanh ngày nộp 10-K

CAAR là CAR trung bình của các hồ sơ trong mẫu. Bảng này kiểm tra phản ứng trung bình quanh sự kiện, **không phải** hệ số của tone.

| Cửa sổ giao dịch | N | CAAR | Z MacKinlay | p MacKinlay | p kiểm định dấu |
| --- | ---: | ---: | ---: | ---: | ---: |
| [-1,+1] | 969 | 0,519% | 5,471 | <0,0001 | 0,1013 |
| [0,+3] | 969 | 0,444% | 4,056 | <0,0001 | 0,1483 |
| [-3,+3] | 969 | 0,588% | 4,059 | <0,0001 | 0,1672 |
| [-5,+5] | 969 | 0,766% | 4,221 | <0,0001 | 0,3515 |

Chẳng hạn ở cửa sổ `[-1,+1]`, CAAR = **0,519%** và p MacKinlay = **<0,0001**. Điều này cho thấy lợi suất bất thường trung bình khác 0 theo phép kiểm định đó. Nó không cho biết phần nào do giọng điệu báo cáo, công bố lợi nhuận gần thời điểm đó, hay tin khác.

## Tone LM và CAR: hồi quy C1

Hệ số dưới đây thuộc mô hình `CAR = a + b × LM_net_prop + sai số`, với sai số chuẩn HC3 và đối chứng gom cụm theo công ty. Tone dương hơn tương ứng `LM_net_prop` lớn hơn. Bảng trình bày **cả bốn cửa sổ**, không chọn riêng cửa sổ có p nhỏ.

| Cửa sổ | N | Hệ số b | p HC3 hai phía | p gom cụm công ty |
| --- | ---: | ---: | ---: | ---: |
| [-1,+1] | 969 | -0,3719 | 0,0991 | 0,1235 |
| [0,+3] | 969 | -0,4214 | 0,0481 | 0,1122 |
| [-3,+3] | 969 | -0,6549 | 0,0155 | 0,0379 |
| [-5,+5] | 969 | -0,5685 | 0,0922 | 0,0889 |

Ở `[-1,+1]`, hệ số **-0,3719**, p HC3 **0,0991** và p gom cụm **0,1235**. Với ngưỡng 5%, đặc tả này **chưa cho bằng chứng thống kê đủ mạnh** rằng tone LM dự báo CAR. Cửa sổ `[-3,+3]` có p HC3 **0,0155**, nhưng p gom cụm là **0,0379**; kết luận phụ thuộc cách tính sai số chuẩn và cửa sổ được chọn. Vì có nhiều đặc tả, không nên coi một p-value đơn lẻ là xác nhận chắc chắn.

## So sánh từ điển tài chính và từ điển tổng quát

Trên **971 hồ sơ** tính được cả hai điểm theo cùng quy tắc xử lý, LM và Harvard IV-4 cho tone **trái dấu ở 861 hồ sơ (88,7%)**. Kết quả cho thấy hai từ điển cho điểm khác nhau; chỉ số trái dấu không phải phép đánh giá đúng/sai của từng từ điển.

Ở hồi quy C4 `[-1,+1]` đưa đồng thời hai tone tỷ lệ vào mô hình, hệ số LM là **-0,0781** (p HC3 **0,7700**), còn Harvard là **-0,6868** (p HC3 **0,0091**). Kết quả này **không cho phép khẳng định LM luôn dự báo tốt hơn**; cần đối chiếu thêm giả thuyết, dấu hệ số và dữ liệu gốc trước khi nêu kết luận mạnh.

## C2 rút gọn với biến kiểm soát

C2 trong bảng dùng `LM_net_prop`, Size, BM, Volatility và Turnover. Do yêu cầu dữ liệu đủ bốn biến kiểm soát, mẫu gồm **862 hồ sơ**. Bảng dưới chỉ hiển thị hệ số tone; toàn bộ hệ số của bốn biến kiểm soát có trong `c2_reduced_results.csv` và tab Hồi quy.

| Cửa sổ | N | Hệ số tone | p HC3 | Khoảng tin cậy HC3 95% | p gom cụm |
| --- | ---: | ---: | ---: | --- | ---: |
| [-1,+1] | 862 | -0,3180 | 0,1656 | [-0,7676; 0,1316] | 0,2327 |
| [0,+3] | 862 | -0,1981 | 0,3884 | [-0,6484; 0,2521] | 0,5011 |
| [-3,+3] | 862 | -0,3883 | 0,1862 | [-0,9640; 0,1874] | 0,2278 |
| [-5,+5] | 862 | -0,1817 | 0,6261 | [-0,9129; 0,5494] | 0,5842 |

Ở `[-1,+1]`, hệ số tone C2 là **-0,3180**, p HC3 **0,1656**. Đây là mô hình **rút gọn**, và sự khác biệt với C1 vừa phản ánh thêm biến kiểm soát vừa phản ánh mẫu nhỏ hơn; không thể tách hai tác động chỉ bằng hai bảng này.

## Kết luận sử dụng được và giới hạn

Dữ liệu cho thấy có phản ứng lợi suất bất thường trung bình quanh ngày nộp 10-K và tone khác nhau đáng kể giữa hai từ điển. Mối liên hệ riêng giữa tone LM và CAR **không ổn định qua cửa sổ và cách tính sai số chuẩn**, nên chưa có cơ sở để nói tone gây ra biến động giá. Phần chi tiết cách tính nằm ở tab **Phương pháp**; trạng thái hồ sơ và các phép kiểm tra nằm ở tab **Kiểm tra**.
