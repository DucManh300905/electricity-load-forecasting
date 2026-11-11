# Dự báo phụ tải điện Quốc gia theo ngày

Dự báo công suất lớn nhất (Pmax) và sản lượng điện của Hệ thống điện Quốc gia Việt Nam cho **ngày hôm sau**. Dữ liệu lấy từ bản tin vận hành hằng ngày do EVN công bố.

## Trạng thái

| Giai đoạn | Nội dung | Trạng thái |
|---|---|---|
| 1 | Thu thập và chuẩn hóa dữ liệu EVN | Hoàn thành: 1 254 ngày (28/05/2023 → 10/11/2026) |
| 2 | Dữ liệu thời tiết và lịch lễ, Tết | Hoàn thành |
| 3 | Phân tích khám phá (EDA) | Hoàn thành: [docs/EDA.md](docs/EDA.md) |
| 4 | Mô hình dự báo | Hoàn thành: MAPE test Pmax 2,12%, sản lượng 2,10% ([docs/Model.md](docs/Model.md)) |
| 5 | Vận hành hằng ngày và dashboard |  |

Kế hoạch chi tiết: [docs/Projects.md](docs/Projects.md)

## Dữ liệu

- Nguồn: [EVN – Thông tin tóm tắt vận hành HTĐ Quốc gia](https://www.evn.com.vn/vi-VN/news-l/Thong-tin-tom-tat-van-hanh-HTD-Quoc-gia-60-2015) (số liệu của NSMO).
- File chính: [`data/evn_daily.csv`](data/evn_daily.csv). Mỗi dòng là một ngày, 55 cột.
- Thời tiết: [Open-Meteo](https://open-meteo.com/) (CC BY 4.0), lịch: thư viện `holidays`.
- Ý nghĩa từng cột: [docs/Data.md](docs/Data.md)

## Cài đặt

```bash
pip install -r requirements.txt
```

## Cách chạy

```bash
python crawler.py      # tải bản tin EVN từ 28/05/2023 đến hôm qua vào data/raw_html/
python parser.py       # tạo data/evn_daily.csv
python weather.py      # thời tiết thực tế + dự báo → data/weather.csv
python calendar_features.py  # lịch lễ, Tết → data/calendar.csv
python train.py        # huấn luyện + backtest → data/backtest*.csv, models/params.json
```

`crawler.py` chạy tiếp được khi bị dừng giữa chừng: chạy lại thì nó chỉ tải phần còn thiếu. Tham số: `--start YYYY-MM-DD`, `--end YYYY-MM-DD`, `--scan-ids`, `--retry-not-found`.

> Thư mục `data/raw_html/` (HTML gốc, khoảng 25 MB) không đưa lên Git. Chạy `python crawler.py` để tải lại.

## Cấu trúc

```
├── crawler.py          # thu thập HTML từ website EVN
├── parser.py           # HTML → data/evn_daily.csv
├── weather.py          # Open-Meteo → data/weather.csv
├── calendar_features.py  # lịch → data/calendar.csv
├── features.py         # đặc trưng cho mô hình
├── train.py            # huấn luyện, walk-forward backtest, kiểm định
├── requirements.txt
├── data/
│   ├── evn_daily.csv       # dữ liệu EVN sạch
│   ├── weather.csv         # thời tiết 3 miền
│   ├── calendar.csv        # lịch
│   ├── links.csv           # danh sách bài (id, ngày, url)
│   ├── parse_issues.csv
│   └── not_found_dates.txt
├── notebooks/
│   ├── 01_eda.ipynb        # phân tích khám phá (Giai đoạn 3)
│   └── 02_modeling.ipynb   # kết quả mô hình (Giai đoạn 4)
├── models/params.json      # tham số và mô hình được chọn
├── reports/figures/        # biểu đồ EDA và mô hình
└── docs/
    ├── Projects.md         # kế hoạch dự án
    ├── Data.md             # từ điển dữ liệu
    ├── EDA.md              # báo cáo phân tích khám phá
    ├── Model.md            # báo cáo mô hình
    └── Algorithm.md        # cách mô hình hoạt động, kèm ví dụ tính tay
```

## Ghi chú

Số liệu thuộc về EVN/NSMO. Dự án chỉ dùng cho mục đích học tập và nghiên cứu. Crawler có độ trễ 0,7 giây giữa các request để không gây tải cho máy chủ.
