# Dự báo phụ tải điện Quốc gia theo ngày

Dự báo công suất lớn nhất (Pmax) và sản lượng điện của Hệ thống điện Quốc gia Việt Nam cho **ngày hôm sau**. Dữ liệu lấy từ bản tin vận hành hằng ngày do EVN công bố.

## Trạng thái

| Giai đoạn | Nội dung | Trạng thái |
|---|---|---|
| 1 | Thu thập và chuẩn hóa dữ liệu EVN | Hoàn thành: 1 254 ngày (28/05/2023 → 10/11/2026) |
| 2 | Dữ liệu thời tiết và lịch lễ, Tết | Hoàn thành |
| 3 | Phân tích khám phá (EDA) |  |
| 4 | Mô hình dự báo |  |
| 5 | Vận hành hằng ngày và dashboard |  |

Kế hoạch chi tiết: [docs/Projects.md](docs/Projects.md)

## Dữ liệu

- Nguồn: [EVN – Thông tin tóm tắt vận hành HTĐ Quốc gia](https://www.evn.com.vn/vi-VN/news-l/Thong-tin-tom-tat-van-hanh-HTD-Quoc-gia-60-2015) (số liệu của NSMO).
- File chính: [`data/evn_daily.csv`](data/evn_daily.csv). Mỗi dòng là một ngày, 54 cột.
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
```

`crawler.py` chạy tiếp được khi bị dừng giữa chừng: chạy lại thì nó chỉ tải phần còn thiếu. Tham số: `--start YYYY-MM-DD`, `--end YYYY-MM-DD`, `--scan-ids`, `--retry-not-found`.

> Thư mục `data/raw_html/` (HTML gốc, khoảng 25 MB) không đưa lên Git. Chạy `python crawler.py` để tải lại.

## Cấu trúc

```
├── crawler.py          # thu thập HTML từ website EVN
├── parser.py           # HTML → data/evn_daily.csv
├── weather.py          # Open-Meteo → data/weather.csv
├── calendar_features.py  # lịch → data/calendar.csv
├── requirements.txt
├── data/
│   ├── evn_daily.csv       # dữ liệu EVN sạch
│   ├── weather.csv         # thời tiết 3 miền
│   ├── calendar.csv        # lịch
│   ├── links.csv           # danh sách bài (id, ngày, url)
│   ├── parse_issues.csv
│   └── not_found_dates.txt
└── docs/
    ├── Projects.md         # kế hoạch dự án
    └── Data.md             # từ điển dữ liệu
```

## Ghi chú

Số liệu thuộc về EVN/NSMO. Dự án chỉ dùng cho mục đích học tập và nghiên cứu. Crawler có độ trễ 0,7 giây giữa các request để không gây tải cho máy chủ.
