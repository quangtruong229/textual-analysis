# TÀI LIỆU MÔ TẢ SẢN PHẨM & TÍNH ỨNG DỤNG ĐẦU TƯ
## TEXTUAL ANALYSIS IN FINANCE — QUANT RESEARCH LAB

> **Nền tảng phân tích định lượng giọng điệu văn bản Item 7 (MD&A) trong hồ sơ 10-K và phản ứng giá cổ phiếu thị trường chứng khoán Hoa Kỳ (NYSE / Nasdaq 100, Giai đoạn 2016–2025, Benchmark S&P 500).**

---

## 1. TỔNG QUAN SẢN PHẨM (PRODUCT OVERVIEW)

### 1.1. Bối cảnh & Bài toán Thị trường
Mỗi năm, các công ty đại chúng niêm yết trên các sở giao dịch chứng khoán Hoa Kỳ (NYSE, Nasdaq) đều phải nộp báo cáo thường niên theo mẫu **Form 10-K** lên Ủy ban Giao dịch Chứng khoán Hoa Kỳ (SEC). Trong đó, **Item 7: Management’s Discussion and Analysis of Financial Condition and Results of Operations (MD&A)** là phần quan trọng nhất chứa đựng nhận định chiến lược, phân tích chuyên sâu của ban điều hành về kết quả kinh doanh, triển vọng và các rủi ro cốt lõi.

Tuy nhiên, giới đầu tư tài chính đối mặt với 3 thách thức lớn:
1. **Quá tải thông tin (Information Overload):** Một hồ sơ 10-K thường dài từ 100 đến 300 trang; Item 7 chứa hàng chục nghìn từ vựng học thuật phức tạp. Việc đọc thủ công 1.000 hồ sơ qua 10 năm là bất khả thi đối với nhà đầu tư cá nhân và tốn kém tài nguyên của các quỹ đầu tư.
2. **Thiên lệch nhận thức từ từ điển tổng quát (Dictionary Bias):** Khi dùng các công cụ NLP thông thường (như từ điển Harvard IV-4), các từ như *"tax", "cost", "liability", "depreciation"* thường bị gán nhãn tiêu cực hoặc ngược lại gán tích cực cho ngôn ngữ thận trọng, tạo ra tín hiệu giả mạo tới 88.7% trường hợp.
3. **Mô hình "Hộp đen" (Black-box Fallacy):** Nhiều giải pháp AI trên thị trường đưa ra dự báo mà không có kiểm định thống kê khắt khe, không xử lý rò rỉ dữ liệu (data leakage) hoặc ép buộc dữ liệu thiếu về 0 làm sai lệch kết quả phân tích.

### 1.2. Định vị Sản phẩm
**Textual Analysis in Finance — Quant Research Lab** là một nền tảng nghiên cứu tài chính định lượng chuyên nghiệp (Fintech Quantitative Platform). Nền tảng kết hợp giữa **Xử lý ngôn ngữ tự nhiên tài chính chuyên ngành (Financial NLP)** theo chuẩn *Loughran & McDonald (2011)*, **Mô hình nghiên cứu sự kiện kinh điển (Event Study)** theo *MacKinlay (1997)* và *Brown & Warner (1985)*, cùng **Bộ hồi quy kinh lượng OLS đa biến** theo *Jegadeesh & Wu (2013)*.

Toàn bộ hệ thống hoạt động với triết lý **Toàn vẹn số liệu (Data Contract Integrity)**: 100% số liệu hiển thị được tính toán từ dữ liệu gốc, có mã băm SHA-256 bảo chứng, quy định rõ ràng về giả thuyết thống kê, không ngụy tạo kết quả hay "thêu dệt" tín hiệu đầu cơ.

---

## 2. QUY MÔ & PHẠM VI DỮ LIỆU THỰC NGHIỆM

| Tiêu chí | Thông số chuẩn hóa | Ý nghĩa thực tiễn cho nhà đầu tư |
| :--- | :--- | :--- |
| **Thị trường mục tiêu** | NYSE & Nasdaq (Hoa Kỳ) | Thị trường vốn thanh khoản và minh bạch bậc nhất thế giới, hạn chế rủi ro thao túng giá. |
| **Quy mô mẫu** | **100 Doanh nghiệp hàng đầu** | Đại diện cho các tập đoàn vốn hóa lớn (Large-cap) thuộc nhiều nhóm ngành (Công nghệ, Tài chính, Y tế, Tiêu dùng...). |
| **Giai đoạn quan sát** | **10 năm liên tục (2016–2025)** | Bao trùm đủ các chu kỳ thị trường: bình thường, đại dịch Covid-19, chu kỳ tăng lãi suất và bùng nổ AI. |
| **Tổng số quan sát** | **1.000 hồ sơ 10-K** | Mỗi doanh nghiệp tối đa 1 quan sát mỗi năm nộp (`filing_year`), phân biệt rành mạch với năm tài chính (`report_year`). |
| **Thước đo chuẩn (Benchmark)** | **S&P 500 Index (`^GSPC`)** | Đại diện toàn diện cho danh mục thị trường; phản ánh chính xác phần bù rủi ro thị trường. |
| **Khung giờ cắt SEC EDGAR** | **16:00 ET (Giờ đóng cửa NYSE)** | Các hồ sơ nộp sau 16:00 ET tự động dời ngày sự kiện sang phiên $T+1$ (466 phiên), loại bỏ hoàn toàn bẫy nhìn trước (Look-ahead bias). |

---

## 3. TÍNH NĂNG CỐT LÕI (CORE QUANTITATIVE FEATURES)

Các tính năng nền tảng tạo nên sức mạnh phân tích học thuật và độ tin cậy khoa học của sản phẩm:

### 3.1. Bóc tách Item 7 MD&A & Chấm điểm Giọng điệu Đa Thước đo
* **Làm sạch văn bản & Quy tắc phủ định (Negation Rule):** Bóc tách chính xác Item 7 MD&A từ hồ sơ SEC thô. Nếu các từ `NOT`, `NO`, `NEVER` xuất hiện trong phạm vi 3 từ đứng trước một từ tích cực/tiêu cực, từ đó sẽ bị loại bỏ khỏi thống kê (theo Jegadeesh & Wu 2013).
* **3 Phương pháp tính điểm Tone đồng thời:**
  1. *Tone theo tỷ trọng (Proportional Weighting - LM 2011):* $Pos_i = \sum \frac{F_{i,j}}{W_i}$, $Neg_i = \sum \frac{F_{i,j}}{W_i}$, $net\_prop_i = Pos_i - Neg_i$.
  2. *Tone theo tỷ số (Ratio Weighting):* $net\_ratio_i = \frac{Pos_i - Neg_i}{Pos_i + Neg_i}$ (xác định khi $Pos + Neg > 0$).
  3. *Trọng số Tần suất nghịch đảo (TF-IDF - Jegadeesh & Wu Eq. 1–3):* Giảm thiểu trọng số của các từ ngữ xuất hiện quá phổ biến ở mọi doanh nghiệp và nhấn mạnh các thuật ngữ đặc thù mang thông tin cá biệt.
* **Đối chứng Từ điển Tài chính (LM) vs. Từ điển Chung (Harvard IV-4):**
  Minh chứng thực nghiệm trực quan cho thấy **88.7% hồ sơ bị trái dấu** giữa hai từ điển. Từ điển Harvard thường ngộ nhận các từ vựng phòng thủ và nghĩa vụ thuế thành tích cực, trong khi Loughran-McDonald phân loại chuẩn xác ngữ cảnh tài chính doanh nghiệp.

### 3.2. Động cơ Nghiên cứu Sự kiện (Event Study Engine)
* **Quy chuẩn Lịch giao dịch & Giờ nộp SEC:** Khớp chính xác ngày nộp với phiên NYSE đang mở cửa. Nộp sau 16:00 ET hoặc ngày nghỉ tự động dời sang $T+1$.
* **Cửa sổ Ước lượng Độc lập 239 ngày:** Ước lượng mô hình thị trường OLS ($R_{i,\tau} = \alpha_i + \beta_i R_{m,\tau} + \varepsilon_{i,\tau}$) trong giai đoạn từ phiên $\tau = -244$ đến $\tau = -6$, hoàn toàn tách rời cửa sổ sự kiện $\tau \in [-5, +5]$ để tránh rò rỉ dữ liệu.
* **Phân tích Đa Cửa sổ CAR:** Tính toán lợi suất bất thường ($AR$) và lợi suất bất thường tích lũy ($CAR$) trên 4 cửa sổ quan sát:
  - Cửa sổ hẹp: $[-1, +1]$ (3 phiên quanh ngày nộp).
  - Cửa sổ phản ứng tức thời: $[0, +3]$ (4 phiên kể từ ngày công bố).
  - Cửa sổ mở rộng: $[-3, +3]$ (7 phiên) và $[-5, +5]$ (11 phiên).
* **Kiểm định Thống kê Đa chiều:** Cung cấp kiểm định tham số chuỗi thời gian MacKinlay ($\theta_1$), kiểm định phương sai cắt ngang ($Var_{CS}$ phòng chống hiện tượng phương sai biến động tăng đột ngột quanh ngày sự kiện) và kiểm định phi tham số Sign Test ($\theta_2$).

### 3.3. Bộ Hồi quy Kinh lượng OLS Đa biến (Econometric Regressions)
* **Mô hình C1 (Đơn biến):** $CAR_i = a + b \cdot Score_i + \varepsilon_i$, kiểm tra độ nhạy với cả 3 thước đo (`net_prop`, `net_ratio`, `net_tfidf`).
* **Mô hình C2 (Đa biến có 4 biến kiểm soát):**
  $$CAR_i = a + \beta \cdot Score_i + b \cdot Size_i + c \cdot BM_i + d \cdot Volatility_i + e \cdot Turnover_i + \varepsilon_i$$
  Giúp cô lập tác động của giọng điệu khỏi quy mô doanh nghiệp ($Size$), định giá sổ sách trên thị trường ($BM$), độ biến động lịch sử ($Volatility$) và tính thanh khoản giao dịch ($Turnover$).
* **Mô hình C3 (Bất đối xứng tích cực / tiêu cực):** Tách riêng $Positive\_prop$ và $Negative\_prop$ để kiểm tra xem thị trường phản ứng nhạy hơn với tin xấu hay tin tốt.
* **Mô hình C4 (Đua ngựa từ điển - Dictionary Horse Race):** Đưa đồng thời điểm LM và điểm Harvard vào một hồi quy để đo lường độ vượt trội thông tin của từ điển tài chính.
* **Sai số chuẩn vững (Robust Standard Errors):** Sử dụng sai số chuẩn White HC3 (chống phương sai thay đổi) và Clustered SE (gom cụm theo công ty), giúp các kết luận thống kê đạt độ tin cậy thực chất.

### 3.4. Hệ thống Kiểm toán Tính Toàn vẹn Dữ liệu (Audit & Data Integrity)
* **Data Contract Manifest:** Giao diện đọc trực tiếp cấu trúc dữ liệu theo hợp đồng bàn giao (`handoff/manifest.json`).
* **Mã băm SHA-256:** Cho phép đối chiếu mã băm mật mã học của mọi file dữ liệu đầu vào.
* **Kiểm tra Tính nhất quán Số học:** Xác minh 969/969 ngày $t=0$ trùng khớp ngày sự kiện, tổng các ngày $AR$ chính xác bằng $CAR$, không có sai lệch số học trong bộ nhớ.
* **Minh bạch Dữ liệu Thiếu:** Công khai danh sách 29 hồ sơ thiếu Item 7 MD&A và 2 hồ sơ thiếu dữ liệu giá, không che giấu hoặc gán ép số liệu bằng 0.

---

## 4. TÍNH NĂNG PHỤ & CHỨNG MINH TÍNH ỨNG DỤNG CHO NHÀ ĐẦU TƯ (VALUE-ADDED FEATURES)

Bên cạnh các mô hình học thuật, webapp được trang bị các tính năng mở rộng được thiết kế riêng nhằm biến dữ liệu định lượng thành **công cụ ra quyết định đầu tư thực chiến**:

### 4.1. Hệ thống Phân loại Tín hiệu Đầu tư Nhanh (Tone Signal Badges)
* **Cơ chế hoạt động:** Chuyển đổi điểm liên tục `LM net_prop` thành hệ thống huy hiệu trực quan trên giao diện:
  - 🟢 **Tín hiệu Tích cực (Positive):** $net\_prop > 0$ (88 hồ sơ / 8.8% mẫu) — Phản ánh ban lãnh đạo có đánh giá lạc quan thực sự, số lượng từ tích cực vượt trội từ rủi ro.
  - ⚪ **Tín hiệu Trung tính (Neutral):** $net\_prop = 0$ (8 hồ sơ / 0.8% mẫu) — Trạng thái cân bằng từ ngữ.
  - 🔴 **Tín hiệu Tiêu cực (Negative):** $net\_prop < 0$ (875 hồ sơ / 87.5% mẫu) — Thể hiện mức độ thận trọng cao hoặc điều khoản rủi ro pháp lý lớn.
  - ⚠️ **Thiếu Tone (Missing):** 29 hồ sơ không bóc tách được Item 7, cảnh báo nhà đầu tư về rủi ro định dạng báo cáo.
* **Giá trị cho Nhà đầu tư:** 
  - Thay vì phải đọc hàng nghìn trang tài liệu, nhà đầu tư chỉ cần 1 giây để nhận biết giọng điệu tổng thể của báo cáo.
  - Dễ dàng lọc ra nhóm cổ phiếu hiếm hoi có tone dương (8.8% mẫu) để xem xét khả năng cổ phiếu có tin tức kinh doanh đột phá.

### 4.2. Thanh Thống kê Nhanh Thời gian Thực (Dynamic Micro-Stats Bar)
* **Cơ chế hoạt động:** Ngay phía trên bảng dữ liệu, thanh Micro-Stats tự động tính toán lại tức thì:
  - Tỷ lệ phần trăm và số lượng hồ sơ 🟢 Tích cực, ⚪ Trung tính, 🔴 Tiêu cực, ⚠️ Thiếu tone.
  - Điểm Tone trung bình và Lợi suất $CAR [-1, +1]$ trung bình của tập hợp đang lọc.
* **Giá trị cho Nhà đầu tư:** Hỗ trợ kiểm tra nhanh phân bổ tâm lý ban lãnh đạo theo từng năm tài chính hoặc từng nhóm doanh nghiệp được chọn.

### 4.3. Biểu đồ Tương tác Đa năng với Tính năng Zoom In / Zoom Out & Pan
* **Cơ chế hoạt động:** Tích hợp thư viện Chart.js cùng plugin Zoom và Hammer.js:
  - Lăn chuột (wheel) hoặc chụm ngón tay (pinch) trên màn hình cảm ứng để phóng to từng cụm dữ liệu phân tán (Scatter plot) hoặc dải dao động $AAR [-5, +5]$.
  - Kéo chuột (pan) để di chuyển giữa các vùng mật độ cao.
  - Nút **"Đặt lại Zoom" (Reset Zoom)** đưa biểu đồ về khung nhìn chuẩn chỉ với 1 click.
* **Giá trị cho Nhà đầu tư:** Cho phép soi rõ từng cổ phiếu cá biệt trong đám mây 971 điểm phân tán, đặc biệt là các trường hợp lệch pha nghiêm trọng giữa từ điển LM và Harvard.

### 4.4. Truy vết Nguồn gốc Hồ sơ 1-Click (1-Click SEC EDGAR Traceability)
* **Cơ chế hoạt động:** Mỗi hàng trong bảng 1.000 hồ sơ đều có đường dẫn trực tiếp (`sec_url`) đến trang hồ sơ gốc trên cổng thông tin SEC EDGAR chính thức của chính phủ Hoa Kỳ.
* **Giá trị cho Nhà đầu tư:** Khi phát hiện một cổ phiếu có điểm tone hoặc $CAR$ bất thường, chuyên viên phân tích (buy-side / sell-side analyst) có thể bấm ngay vào liên kết để đọc chi tiết các thuyết minh tài chính gốc của công ty mà không phải mất công tìm kiếm thủ công.

### 4.5. Xuất Dữ liệu Tinh gọn phục vụ Mô hình Cá nhân (Custom CSV Export)
* **Cơ chế hoạt động:** Nút bấm **"Xuất CSV" (Export CSV)** trên bảng điều khiển hồ sơ cho phép tải xuống toàn bộ tập dữ liệu đã qua lọc (theo năm, ticker, tín hiệu tone).
* **Giá trị cho Nhà đầu tư:** Dữ liệu xuất ra ở định dạng UTF-8 chuẩn, sẵn sàng để nạp vào Microsoft Excel, Python Pandas, R hoặc các hệ sinh thái giao dịch thuật toán (Algo-trading backtesting platforms).

### 4.6. Trải nghiệm Fintech Cao cấp & Tối ưu Thị giác (Institutional UX/UI)
* **Thiết kế chuẩn Institutional:** Sử dụng bảng màu xanh navy - đá phiến (slate navy), kiểu chữ hiện đại (Inter, JetBrains Mono) và bảng dữ liệu mật độ cao (compact data density) tương tự phong cách giao diện của Bloomberg Terminal hay FactSet.
* **Dark / Light Theme linh hoạt:** Hỗ trợ chuyển đổi giao diện Sáng ngà / Tối chỉ với 1 nút bấm, đảm bảo tiêu chuẩn tương phản cao WCAG 2.1 AA, chống mỏi mắt cho các nhà phân tích làm việc trong thời gian dài.
* **Hiệu ứng Micro-animations mượt mà:** Chuyển tab có gia tốc mượt (`fadeSlideIn`), thẻ số liệu xuất hiện so le (`staggerFadeUp`), thẻ nâng nhẹ khi rê chuột (`hover lift`), giúp giao diện sống động và chuyên nghiệp.

---

## 5. KỊCH BẢN ỨNG DỤNG THỰC TẾ CHO CÁC NHÓM NHÀ ĐẦU TƯ (INVESTOR USE CASES)

### Kịch bản 1: Quỹ Đầu tư Cơ bản (Fundamental & Long-Short Equity Funds)
* **Mục tiêu:** Tìm kiếm cổ phiếu có tín hiệu đảo chiều kinh doanh (Turnaround Candidates).
* **Quy trình áp dụng:**
  1. Vào tab **Hồ sơ 10-K**, lọc các doanh nghiệp có tín hiệu chuyển biến từ 🔴 Tiêu cực trong các năm trước sang 🟢 Tích cực trong năm hiện tại.
  2. Bấm vào liên kết SEC EDGAR để đọc chi tiết Item 7 của các doanh nghiệp này, xác minh xem sự lạc quan đến từ việc mở rộng thị phần, ra mắt sản phẩm mới hay cắt giảm chi phí tái cơ cấu.
  3. Xây dựng vị thế Long đối với nhóm cải thiện giọng điệu và vị thế Short đối với nhóm có giọng điệu suy giảm nghiêm trọng.

### Kịch bản 2: Nhà đầu tư Định lượng & Thuật toán (Quantitative Analysts & Algo Traders)
* **Mục tiêu:** Xây dựng nhân tố định lượng mới (Sentiment Alpha Factor) bổ sung vào danh mục đa nhân tố (Multi-factor Portfolio).
* **Quy trình áp dụng:**
  1. Sử dụng kết quả kiểm định mô hình C2 đa biến từ tab **Hồi quy OLS** để xác định độ lớn hệ số $\beta$ của tone sau khi đã loại trừ các nhân tố truyền thống (Fama-French: Size, Value, Volatility, Liquidity).
  2. Sử dụng tính năng **Xuất CSV** để lấy chuỗi dữ liệu bảng (panel data) 10 năm của 100 mã cổ phiếu lớn.
  3. Kết hợp chỉ số `lm_net_prop` vào tín hiệu tái cân bằng danh mục định kỳ sau mỗi mùa báo cáo 10-K (tháng 2 – tháng 4 hàng năm).

### Kịch bản 3: Chuyên viên Quản trị Rủi ro Danh mục (Risk Managers)
* **Mục tiêu:** Phát hiện rủi ro tiềm ẩn (Early Warning of Narrative Risk).
* **Quy trình áp dụng:**
  1. Khảo sát tab **So sánh từ điển**, lọc các cổ phiếu nằm ở góc phần tư lệch pha (LM âm nặng nhưng Harvard dương).
  2. Đối chiếu với độ biến động phần dư đặc thù ($\sigma_{\varepsilon_i}$) và các chỉ số kiểm định sự kiện $CAAR$ quanh ngày nộp.
  3. Thiết lập cảnh báo rủi ro đối với những cổ phiếu ban lãnh đạo gia tăng đột biến tần suất từ ngữ tiêu cực/thận trọng nhằm chủ động giảm tỷ trọng trước khi thị trường phản ứng tiêu cực dài hạn.

---

## 6. HƯỚNG DẪN KHỞI CHẠY & VẬN HÀNH ỨNG DỤNG

Ứng dụng được xây dựng theo kiến trúc **Zero-dependency Client-side Static App**, không yêu cầu cấu hình cơ sở dữ liệu phức tạp:

### Khởi động Local Web Server (Khuyên dùng):
```powershell
# Chạy web server cục bộ qua Python từ thư mục gốc dự án:
python -m http.server 8000 --directory webapp
```
Truy cập qua trình duyệt tại: **`http://localhost:8000`**

### Hoặc mở trực tiếp file HTML:
```powershell
# Mở file trực tiếp trên Windows PowerShell:
Start-Process "webapp/index.html"
```

---

*Tài liệu được biên soạn đồng bộ cùng mã nguồn của dự án tại `webapp/` — Fintech Research Lab.*
