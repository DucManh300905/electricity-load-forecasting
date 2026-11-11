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
- Chuỗi bài bắt đầu từ 28/05/2023. **Phạm vi dự án hiện tại: 01/01/2026 → nay.**
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
Lịch lễ/Tết ──► calendar.py ──────────────────────┴──► features.py ◄──────┘
                                                          │
                                              train.py / predict.py ──► data/forecast.csv
                                                          │
                                                  app/ (Streamlit dashboard)
```

## 4. Các giai đoạn

### Giai đoạn 1: Thu thập và chuẩn hóa dữ liệu ✅ hoàn thành (11/11/2026)
- [x] Khảo sát cấu trúc trang EVN.
- [x] `crawler.py`: lấy danh sách bài, tìm theo ngày, dò ID, tải HTML (có thể chạy tiếp khi bị dừng).
- [x] `parser.py`: tách số liệu thành bảng, mỗi ngày một dòng.
- [x] Chạy parser trên toàn bộ dữ liệu năm 2026: **314/314 ngày** (01/01 → 10/11/2026), không thiếu ngày nào.
- [x] Kiểm tra chất lượng: tổng các nguồn khớp `energy_mkwh` (lệch trung bình 0,05 triệu kWh). Chỉ thiếu bảng công suất ngày 13/03 và 14/03, vì bài gốc không đăng bảng.

### Giai đoạn 2: Dữ liệu bổ sung
- [ ] `weather.py`: tải thời tiết lịch sử và dự báo, tổng hợp theo ngày (Tmax, Tmean, độ ẩm, bức xạ).
- [ ] `calendar.py`: thứ trong tuần, ngày lễ, nghỉ bù, số ngày trước/sau Tết.

### Giai đoạn 3: Phân tích khám phá (EDA)
- [ ] Xu hướng, mùa vụ theo tuần và theo tháng.
- [ ] Quan hệ giữa phụ tải và nhiệt độ.
- [ ] Ảnh hưởng của lễ, Tết và các đợt nắng nóng.
- [ ] Giờ xảy ra Pmax dịch chuyển thế nào theo mùa (ảnh hưởng của điện mặt trời mái nhà).

### Giai đoạn 4: Mô hình
| Bậc | Mô hình | Vai trò |
|---|---|---|
| Baseline | Naive (hôm qua), seasonal naive (cùng thứ tuần trước) | Mốc so sánh |
| Thống kê | SARIMAX có biến nhiệt độ | Dễ giải thích |
| Machine learning | LightGBM với các biến lag (t-1, t-7), rolling mean, thời tiết, lịch | Mô hình chính dự kiến |

- Đánh giá bằng **walk-forward** (huấn luyện trên quá khứ, dự báo ngày kế tiếp, trượt dần). Không chia dữ liệu ngẫu nhiên.
- Chỉ số: MAPE, MAE, RMSE. Báo cáo riêng cho ngày lễ và ngày nắng nóng.
- Khoảng dự báo P10/P50/P90 bằng quantile regression.

### Giai đoạn 5: Vận hành hằng ngày
- [ ] Lịch chạy khoảng 11:30 mỗi ngày: `crawler.py` → `parser.py` → cập nhật thời tiết → `predict.py`.
- [ ] Lưu dự báo và so sánh với số liệu thực tế khi có.
- [ ] Dashboard Streamlit: thực tế so với dự báo, sai số theo thời gian.
- [ ] Huấn luyện lại định kỳ (hằng tháng) hoặc khi sai số vượt ngưỡng.

## 5. Rủi ro và cách xử lý

| Rủi ro | Ảnh hưởng | Cách xử lý |
|---|---|---|
| Chỉ có khoảng 310 ngày (năm 2026) | Không học được mùa vụ theo năm và Tết của các năm trước | Có thể mở rộng sang 2023–2025 bằng `--start 2023-05-28` |
| Định dạng bài thay đổi theo thời gian | Parser bỏ sót cột | Lưu HTML gốc; `parse_issues.csv` liệt kê các bài lỗi |
| Trang danh sách phân trang lỗi | Không duyệt được hết bài | Tìm kiếm theo ngày và dò ID (đã xử lý trong crawler) |
| EVN đăng muộn hoặc thiếu ngày | Dự báo dựa trên dữ liệu cũ | Crawler chạy lại được; ghi các ngày không tìm thấy vào `not_found_dates.txt` |
| Hai cách ước tính điện mặt trời mái nhà | Nhầm lẫn khi so sánh | Mặc định dùng cột *thương phẩm*, giữ cột `_dc` để đối chiếu |

## 6. Cấu trúc thư mục

```
evn_load/
├── crawler.py          # thu thập HTML từ EVN
├── parser.py           # HTML → evn_daily.csv
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
python crawler.py              # thu thập 01/01/2026 → hôm qua
python crawler.py --scan-ids   # thêm bước dò ID cho ngày còn thiếu
python parser.py               # tạo data/evn_daily.csv
```
