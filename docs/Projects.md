# Kế hoạch dự án: Dự báo phụ tải điện theo ngày

## 1. Mục tiêu

Dự báo phụ tải của Hệ thống điện Quốc gia cho **ngày hôm sau** (day-ahead). Mô hình được cập nhật mỗi ngày, ngay khi EVN đăng bản tin vận hành của ngày hôm trước.

**Biến mục tiêu**

| Biến | Ý nghĩa | Đơn vị | Ưu tiên |
|---|---|---|---|
| `pmax_mw` | Công suất lớn nhất trong ngày | MW | Chính |
| `energy_mkwh` | Sản lượng điện sản xuất và nhập khẩu trong ngày | triệu kWh | Chính |
| `noon_total` | Công suất lúc thấp điểm trưa | MW | Phụ |
| `pmax_time` | Giờ xảy ra Pmax | HH:MM | Phụ (phân tích) |

**Tiêu chí thành công (đề xuất)**
- MAPE của `pmax_mw` và `energy_mkwh` thấp hơn rõ rệt so với baseline "cùng thứ tuần trước".
- Pipeline tự chạy hằng ngày, không cần thao tác tay.

## 2. Nguồn dữ liệu

**Nguồn chính:** chuyên mục [Thông tin tóm tắt vận hành HTĐ Quốc gia](https://www.evn.com.vn/vi-VN/news-l/Thong-tin-tom-tat-van-hanh-HTD-Quoc-gia-60-2015) của EVN. Số liệu do Công ty Vận hành HTĐ và TTĐ Quốc gia (NSMO) cung cấp.

- Mỗi ngày có 1 bài, đăng khoảng 10–11h sáng hôm sau.
- Chuỗi bài bắt đầu từ 28/05/2023. **Phạm vi dự án: 28/05/2023 → nay** (mở rộng từ "chỉ năm 2026" ngày 11/11/2026, để có đủ 3 lần Tết và nhiều chu kỳ năm).
- Mỗi bài gồm:
  - Pmax và giờ xảy ra Pmax.
  - Sản lượng ngày.
  - Cơ cấu sản lượng theo nguồn: thủy điện, than, khí, dầu, gió, mặt trời trang trại, mặt trời mái nhà, nhập khẩu, khác.
  - Bảng công suất huy động tại 2 thời điểm: thấp điểm trưa và cao điểm tối.
- Các bài gần đây tính số liệu theo 2 cách ước tính điện mặt trời mái nhà: *thương phẩm* (cột thường) và *đầu cực* (cột hậu tố `_dc`).
- **Không có:** đường phụ tải theo giờ, số liệu theo miền, số liệu theo từng nhà máy.

**Nguồn bổ sung (dự kiến)**
- Thời tiết: Open-Meteo, gồm số liệu lịch sử và dự báo cho Hà Nội, Đà Nẵng, TP.HCM (nhiệt độ, độ ẩm, bức xạ, mây).
- Lịch: ngày lễ, nghỉ bù, Tết Âm lịch.

## 3. Kiến trúc tổng quan

```
EVN website ──► crawler.py ──► data/raw_html/*.html ──► parser.py ──► data/evn_daily.csv
                                                                          │
Open-Meteo ──► weather.py ──► data/weather.csv ──┐                        │
Lịch lễ/Tết ──► calendar_features.py─────────────────┴──► features.py ◄──────┘
                                                          │
                                              train.py / predict.py ──► data/forecast.csv
                                                          │
                                                  app/ (Streamlit dashboard)
```

## 4. Các giai đoạn

### Giai đoạn 1: Thu thập và chuẩn hóa dữ liệu hoàn thành (11/11/2026)
- [x] Khảo sát cấu trúc trang EVN.
- [x] `crawler.py`: lấy danh sách bài, tìm theo ngày, dò ID, tải HTML (có thể chạy tiếp khi bị dừng).
- [x] `parser.py`: tách số liệu thành bảng, mỗi ngày một dòng.
- [x] Chạy parser trên toàn bộ dữ liệu năm 2026: **314/314 ngày** (01/01 → 10/11/2026), không thiếu ngày nào.
- [x] Kiểm tra chất lượng: tổng các nguồn khớp `energy_mkwh` (lệch trung bình 0,05 triệu kWh). Chỉ thiếu bảng công suất ngày 13/03 và 14/03, vì bài gốc không đăng bảng.
- [x] **Mở rộng sang 28/05/2023 → 31/12/2025:** tổng cộng **1 254/1 263 ngày** (99,3%). 9 ngày năm 2023 EVN không đăng bài (đã kiểm tra bằng tìm kiếm, dò mã bài và đối chiếu chuyên mục).
  - Crawler: bước dò ID tìm thêm 3 bài mà tìm kiếm bỏ sót (06/10/2023 có tiêu đề gõ sai "06/102023", 28/11/2024, 04/12/2024). Đã sửa lỗi `links.csv` bị xóa link ngoài khoảng `--start/--end`, lỗi in tiếng Việt ra log, và lỗi nhận nhầm bài tin tức.
  - Parser: xử lý 3 thời kỳ định dạng (mốc 30/05/2023 và 04/06/2024). Sửa lỗi **lấy nhầm bảng sản lượng làm bảng công suất** (tháng 6/2023), cùng các cách viết số và đơn vị khác thường.
  - Thêm cột kiểm tra chất lượng `qc_energy_diff`, phát hiện bài 20/09/2025 gõ sai sản lượng thủy điện (chi tiết: `Data.md` mục 3).

### Giai đoạn 2: Dữ liệu bổ sung hoàn thành (11/11/2026)
- [x] `weather.py`: thời tiết thực tế (`obs_`, Archive API) và **dự báo trước 1 ngày** (`fc_`, Previous Runs API) cho Hà Nội, Đà Nẵng, TP.HCM, kèm trung bình có trọng số toàn quốc → `data/weather.csv` (314 ngày, không thiếu).
- [x] `calendar_features.py`: thứ, ngày lễ, nghỉ bù, làm bù, độ dài kỳ nghỉ, khoảng cách tới Tết → `data/calendar.csv` (có sẵn 60 ngày tương lai).
- [x] Kiểm chứng: lịch nghỉ khớp với các ngày phụ tải giảm. Phát hiện thứ Bảy có phụ tải gần bằng ngày thường (xem `Data.md` mục 6.1).
- [x] **Mở rộng sang 28/05/2023:** `weather.csv` 1 263 ngày, `calendar.csv` từ 28/05/2023. Bản dự báo `fc_` của Open-Meteo bị thiếu: nhiệt độ thiếu 21 ngày (30/12/2023 → 19/01/2024), các biến khác chỉ có từ 20/01/2024 (chi tiết: `Data.md` mục 5.1).
- [ ] Còn mở: trọng số miền 0,45/0,10/0,45 là giả định, cần thay bằng số liệu chính thức nếu có.
- [ ] Còn mở (quyết định ở Giai đoạn 4): xử lý giai đoạn thiếu `fc_` trước 20/01/2024: huấn luyện từ 2024, hay dùng `obs_` thay thế cho giai đoạn đầu.

### Giai đoạn 3: Phân tích khám phá (EDA) hoàn thành (11/11/2026)
Mã nguồn `notebooks/01_eda.ipynb`, biểu đồ `reports/figures/`, báo cáo **`docs/EDA.md`**.
- [x] Xu hướng: tăng khoảng 7,5%/năm, không đều giữa các năm (2025 chậm, 2026 nhanh).
- [x] Mùa vụ theo tuần: CN −13%, T7 −5% (Pmax); T2 sản lượng −2%.
- [x] Lễ: −22% trung bình. Tết: đáy −45 đến −49%, kéo dài khoảng 3 tuần, hình dạng lặp lại qua 3 năm.
- [x] Nhiệt độ: phi tuyến, tăng mạnh khi Tmax trên 30°C. Trọng số miền giả định chưa phù hợp.
- [x] Tự tương quan: lag 7 mạnh hơn lag 2. Lag 1 không dùng được (khoảng cách dự báo 2 ngày).
- [x] Giờ Pmax: mùa đông buổi tối, mùa hè buổi chiều. Không đổi sau khi tách điện mặt trời mái nhà.
- [x] Ngày bất thường: nắng nóng, mưa lớn, ngày kề lễ. **Phát hiện 7 cặp ngày EVN đăng trùng số liệu** → thêm cờ `qc_same_as_adjacent`.
- [x] Baseline (12 tháng gần nhất): MAPE Pmax 5,63%, sản lượng 6,44%. Lễ/Tết sai 24–28%.
- [x] Sửa nhận định sai trong `Data.md`: biến lag nhỏ nhất là lag 2, không phải lag 1.

### Giai đoạn 4: Mô hình hoàn thành (11/11/2026)
Mã nguồn `features.py`, `train.py`, `notebooks/02_modeling.ipynb`; báo cáo **`docs/Model.md`**.

Quyết định đã chốt (theo khuyến nghị): (a) chỉ dùng nhiệt độ dự báo, huấn luyện từ 07/2023; (b) Tết xử lý bằng đặc trưng trong mô hình chung; (c) dự báo cả Pmax và sản lượng.

- [x] Làm sạch: loại 14 ngày có cờ `qc_same_as_adjacent`.
- [x] Dự báo **tỉ lệ so với baseline sạch** (4 tuần cùng thứ, bỏ ngày lễ/Tết) để xử lý xu hướng tăng.
- [x] Mô hình: baseline, Ridge (thay SARIMAX của kế hoạch cũ), LightGBM, Ensemble, LightGBM quantile.
- [x] Walk-forward, huấn luyện lại hằng tháng. Chọn tham số và mô hình cuối trên tập kiểm định (11/2024–11/2025). Test 11/2025–11/2026.
- [x] Kết quả test: **Pmax 2,12%** (Ensemble), **sản lượng 2,10%** (Ridge), so với baseline 5,12% và 5,88%. Diebold–Mariano p < 0,001.
- [ ] Còn mở: khoảng P10–P90 quá hẹp (độ phủ 64–66%), cần hiệu chỉnh bằng conformal prediction.
- [ ] Còn mở: ngày nghỉ bù và lễ rơi vào cuối tuần bị dự báo thấp quá mức. Cần thêm đặc trưng, đánh giá lại trên dữ liệu mới.

### Giai đoạn 5: Vận hành hằng ngày
- [ ] Lịch chạy khoảng 11:30 mỗi ngày: `crawler.py` → `parser.py` → cập nhật thời tiết → `predict.py`.
- [ ] Lưu dự báo và so sánh với số liệu thực tế khi có.
- [ ] Dashboard Streamlit: thực tế so với dự báo, sai số theo thời gian.
- [ ] Huấn luyện lại định kỳ (hằng tháng) hoặc khi sai số vượt ngưỡng.

## 5. Rủi ro và cách xử lý

| Rủi ro | Ảnh hưởng | Cách xử lý |
|---|---|---|
| Dữ liệu ngắn | Chỉ có 3 lần Tết, khoảng 3,5 chu kỳ năm | Đã mở rộng tối đa về 28/05/2023 (bài đầu tiên của chuyên mục). Báo cáo rõ độ tin cậy của kết luận về Tết |
| Định dạng bài thay đổi theo thời gian | Parser bỏ sót hoặc đọc sai cột | Lưu HTML gốc; `parse_issues.csv` liệt kê bài lỗi; `qc_energy_diff` kiểm tra tổng các nguồn |
| Bài gốc gõ sai số liệu | Giá trị sai lọt vào mô hình | Giữ nguyên số gốc, đánh dấu bằng `qc_energy_diff`, quyết định xử lý ở bước làm sạch |
| Cột chỉ có ở một thời kỳ (`_dc`, `e_solar_total`) | Không dùng được cho toàn chuỗi | Biến mục tiêu dùng cột không `_dc`, có đủ từ 2023 |
| Trang danh sách phân trang lỗi | Không duyệt được hết bài | Tìm kiếm theo ngày và dò ID (đã xử lý trong crawler) |
| EVN đăng muộn hoặc thiếu ngày | Dự báo dựa trên dữ liệu cũ | Crawler chạy lại được; ghi các ngày không tìm thấy vào `not_found_dates.txt` |
| Hai cách ước tính điện mặt trời mái nhà | Nhầm lẫn khi so sánh | Mặc định dùng cột *thương phẩm*, giữ cột `_dc` để đối chiếu |

## 6. Cấu trúc thư mục

```
evn_load/
├── crawler.py          # thu thập HTML từ EVN
├── parser.py           # HTML → evn_daily.csv
├── weather.py          # Open-Meteo → weather.csv
├── calendar_features.py  # lịch → calendar.csv
├── data/
│   ├── links.csv           # danh sách bài (id, ngày, url, tiêu đề)
│   ├── raw_html/           # HTML gốc từng bài
│   ├── not_found_dates.txt # ngày không tìm thấy bài
│   ├── evn_daily.csv       # dữ liệu sạch, mỗi ngày 1 dòng
│   └── parse_issues.csv    # bài parse thiếu trường / trùng ngày
└── docs/               # tài liệu dự án
```

## 7. Cách chạy

```bash
cd "C:\Users\ACER\Desktop\Data Science\evn_load"
python crawler.py              # thu thập 28/05/2023 → hôm qua
python crawler.py --scan-ids   # thêm bước dò ID cho ngày còn thiếu
python parser.py               # tạo data/evn_daily.csv
python weather.py              # tạo data/weather.csv
python calendar_features.py    # tạo data/calendar.csv
```
