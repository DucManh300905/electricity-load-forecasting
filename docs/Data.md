# Mô tả dữ liệu: `data/evn_daily.csv`

> Cập nhật: 11/11/2026. Phạm vi: 01/01/2026 → 10/11/2026 (314 ngày, không thiếu ngày nào).

## 1. Tổng quan

- **Mỗi dòng là một ngày vận hành** của Hệ thống điện Quốc gia.
- **Nguồn:** bài "Thông tin chung về vận hành hệ thống điện Quốc gia ngày …" trên website EVN, số liệu do Công ty Vận hành HTĐ và TTĐ Quốc gia (NSMO) cung cấp.
- File tạo bởi `parser.py` từ HTML gốc trong `data/raw_html/`. Mã hóa UTF-8 có BOM, nên mở được bằng Excel mà không lỗi font.
- **Đơn vị:**
  - Công suất (power): **MW**, là giá trị tức thời tại một thời điểm.
  - Sản lượng (energy): **triệu kWh** = GWh, là tổng của cả ngày.

### Quy tắc đặt tên cột

| Thành phần | Ý nghĩa |
|---|---|
| `pmax_…` | Công suất lớn nhất trong ngày |
| `energy_…` | Tổng sản lượng ngày |
| `e_<nguồn>` | Sản lượng ngày của một loại nguồn (**e** = energy) |
| `noon_<nguồn>` | Công suất của nguồn đó **lúc thấp điểm trưa** |
| `eve_<nguồn>` | Công suất của nguồn đó **lúc cao điểm tối** (**eve** = evening) |
| hậu tố `_dc` | Số liệu tính với điện mặt trời mái nhà theo cách **ước tính đầu cực** |
| không có `_dc` | Số liệu tính với điện mặt trời mái nhà theo cách **ước tính thương phẩm** |

### Hai cách ước tính điện mặt trời mái nhà (ĐMTMN)

ĐMTMN không được đo trực tiếp ở cấp hệ thống, nên EVN công bố hai con số ước tính:

- **Thương phẩm** (cột không có hậu tố): tính theo lượng điện mái nhà **bán lên lưới**, tức phần đo được qua công tơ.
- **Đầu cực** (cột `_dc`): ước tính **toàn bộ điện mái nhà phát ra** tại đầu cực tấm pin, gồm cả phần chủ nhà tự dùng. Vì vậy giá trị luôn **lớn hơn hoặc bằng** cách thương phẩm.

Hai cách chỉ khác nhau ở phần ĐMTMN, các nguồn khác giống nhau:

```
energy_mkwh_dc = energy_mkwh - e_rooftop + e_rooftop_dc
noon_total_dc  = noon_total  - noon_rooftop + noon_rooftop_dc
```

> **Khuyến nghị:** dùng cột *thương phẩm* (không `_dc`) làm biến mục tiêu chính. Có thể thử bản `_dc` như một mục tiêu thay thế, vì nó gần với nhu cầu điện thực của xã hội hơn.

---

## 2. Từ điển cột

Cột "Ví dụ" lấy từ ngày **10/11/2026**. Cột "Khoảng giá trị" là min → max trong năm 2026.

### 2.1. Thời gian

| Cột | Kiểu | Ý nghĩa | Ví dụ |
|---|---|---|---|
| `date` | date `YYYY-MM-DD` | Ngày vận hành mà số liệu mô tả. **Không phải** ngày đăng bài. | 2026-11-10 |

### 2.2. Chỉ tiêu tổng (biến mục tiêu)

| Cột | Đơn vị | Ý nghĩa | Ví dụ | Khoảng giá trị |
|---|---|---|---|---|
| `pmax_mw` | MW | Công suất lớn nhất trong ngày của toàn hệ thống (đỉnh phụ tải), ĐMTMN tính theo thương phẩm | 50018.6 | 27 919 → 57 537 |
| `pmax_time` | HH:MM | Thời điểm xảy ra `pmax_mw` | 17:45 | |
| `energy_mkwh` | triệu kWh | Sản lượng điện sản xuất và nhập khẩu trong ngày, ĐMTMN theo thương phẩm | 959.9 | 511.0 → 1 215.4 |
| `pmax_mw_dc` | MW | Như `pmax_mw`, ĐMTMN theo đầu cực | 50136.2 | 27 928 → 58 328 |
| `pmax_time_dc` | HH:MM | Thời điểm xảy ra `pmax_mw_dc`. Có thể khác `pmax_time`, vì cộng thêm điện mái nhà làm đỉnh dịch về buổi chiều. | 17:00 | |
| `energy_mkwh_dc` | triệu kWh | Như `energy_mkwh`, ĐMTMN theo đầu cực | 971.8 | 515.2 → 1 221.9 |

### 2.3. Cơ cấu sản lượng theo nguồn: `e_*` (triệu kWh/ngày)

Tổng các cột này (dùng `e_rooftop`) bằng `energy_mkwh`, sai lệch do làm tròn khoảng ±0,3.

| Cột | Nguồn (tên gốc trong bài) | Ví dụ | Khoảng giá trị |
|---|---|---|---|
| `e_hydro` | Thủy điện | 183.2 | 83.4 → 410.4 |
| `e_coal` | Nhiệt điện than | 418.4 | 192.5 → 644.0 |
| `e_gas` | Tuabin khí (Gas + Dầu DO) | 123.6 | 28.6 → 123.6 |
| `e_oil` | Nhiệt điện dầu | 3.6 | 0.0 → 9.6 |
| `e_wind` | Điện gió | 124.7 | 4.0 → 131.1 |
| `e_solar_farm` | Điện mặt trời trang trại (nhà máy nối lưới) | 33.6 | 19.6 → 58.8 |
| `e_rooftop` | ĐMT mái nhà (ước tính thương phẩm) | 26.8 | 11.3 → 47.2 |
| `e_rooftop_dc` | ĐMT mái nhà (ước tính đầu cực) | 38.7 | 16.3 → 61.9 |
| `e_import` | Nhập khẩu điện (Lào, Trung Quốc…) | 42.9 | 13.3 → 66.3 |
| `e_other` | Khác (sinh khối, diesel…) | 3.2 | 2.9 → 6.3 |

### 2.4. Công suất huy động tại hai thời điểm: `noon_*`, `eve_*` (MW)

Lấy từ bảng "CÔNG SUẤT HUY ĐỘNG NGÀY …" trong bài. Mỗi nguồn có hai giá trị:
- `noon_<nguồn>`: lúc **thấp điểm trưa**. Bức xạ mặt trời mạnh nên điện mặt trời phát nhiều, còn phụ tải lấy từ lưới thấp.
- `eve_<nguồn>`: lúc **cao điểm tối**. Không có mặt trời, các nguồn khác phải bù lên.

`<nguồn>` dùng cùng tên với mục 2.3: `hydro`, `coal`, `gas`, `oil`, `wind`, `solar_farm`, `rooftop`, `rooftop_dc`, `import`, `other`. Ngoài ra còn hai cột tổng:

| Cột | Ý nghĩa | Ví dụ (trưa / tối) |
|---|---|---|
| `noon_total`, `eve_total` | Tổng công suất toàn quốc, ĐMTMN theo thương phẩm (= tổng các nguồn, dùng `rooftop`) | 38818.1 / 41320.5 |
| `noon_total_dc`, `eve_total_dc` | Tổng công suất toàn quốc, ĐMTMN theo đầu cực | 40389.2 / 41320.5 |
| `noon_label`, `eve_label` | Tiêu đề cột gốc trong bảng của EVN, giữ lại để biết định nghĩa thời điểm | "Khi phụ tải vào thấp điểm trưa" / "… cao điểm tối" |

**Lưu ý:**
- `eve_solar_farm`, `eve_rooftop`, `eve_rooftop_dc` luôn bằng **0** vì buổi tối không có mặt trời. Hai cột tổng `eve_total` và `eve_total_dc` do đó luôn bằng nhau. Khi làm mô hình có thể bỏ các cột này.
- Bảng **không ghi giờ cụ thể** của hai thời điểm. "Cao điểm tối" khác với thời điểm Pmax: Pmax thường xảy ra 14–16h hoặc khoảng 18h, nên `eve_total` thường nhỏ hơn `pmax_mw`.

### 2.5. Truy vết nguồn

| Cột | Ý nghĩa | Ví dụ |
|---|---|---|
| `article_id` | Mã bài trên website EVN. File HTML gốc là `data/raw_html/<article_id>.html` | 510268 |
| `published` | Thời điểm EVN đăng bài (`DD/MM/YYYY HH:MM`, GMT+7), thường là khoảng 10–11h sáng **hôm sau** | 11/11/2026 10:55 |
| `title` | Tiêu đề gốc của bài | Thông tin chung về vận hành hệ thống điện Quốc gia ngày 10/11/2026 |

> `published` quan trọng khi dự báo thật: số liệu của ngày D chỉ có từ khoảng 11h ngày D+1. Khi dự báo cho ngày D+1, dữ liệu mới nhất có được là của ngày D.

---

## 3. Dữ liệu thiếu và điểm bất thường

| Vấn đề | Ngày | Ghi chú |
|---|---|---|
| Thiếu toàn bộ cột `noon_*`, `eve_*` | 13/03/2026, 14/03/2026 | Bài gốc không đăng bảng công suất. Để trống (NaN), không tự điền. |
| Phụ tải thấp bất thường | 17–21/02/2026 | **Tết Nguyên đán Bính Ngọ**. Pmax chỉ khoảng 28 000 MW. Đây là số liệu thật, không phải lỗi, nhưng cần biến lịch Tết để mô hình học được. |
| Bài gốc ghi sai đơn vị | 04/08/2026 | Bài viết "3,6 triệu k" (thiếu "Wh"). Parser đã xử lý, `e_other` = 3.6. |

Danh sách bài parse thiếu trường hoặc trùng ngày được ghi vào `data/parse_issues.csv` mỗi lần chạy `parser.py`. Lần chạy hiện tại: **0 bài**.

## 4. Các file dữ liệu khác

| File | Nội dung |
|---|---|
| `data/links.csv` | Danh sách bài: `article_id`, `date`, `url`, `title` |
| `data/raw_html/*.html` | HTML gốc từng bài. Giữ lại để parse lại khi cần, không phải crawl lại. |
| `data/not_found_dates.txt` | Các ngày crawler không tìm thấy bài (hiện trống) |
| `data/parse_issues.csv` | Bài parse lỗi hoặc trùng ngày |
