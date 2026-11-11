# Mô tả dữ liệu

Tài liệu gồm 3 bảng, cùng khóa nối là `date` (`YYYY-MM-DD`):

| File | Nội dung | Tạo bởi | Phạm vi | Mục |
|---|---|---|---|---|
| `data/evn_daily.csv` | Số liệu vận hành của EVN (biến mục tiêu) | `parser.py` | 28/05/2023 → 10/11/2026, 1 254 ngày | 1–4 |
| `data/weather.csv` | Thời tiết thực tế và dự báo của 3 miền | `weather.py` | 28/05/2023 → 10/11/2026, 1 263 ngày | 5 |
| `data/calendar.csv` | Lịch: thứ, ngày lễ, nghỉ bù, Tết | `calendar_features.py` | 28/05/2023 → hôm nay + 60 ngày | 6 |

## 1. Tổng quan `data/evn_daily.csv`

- **Mỗi dòng là một ngày vận hành** của Hệ thống điện Quốc gia. 1 254 dòng, 55 cột.
- **Nguồn:** bài "Thông tin chung về vận hành hệ thống điện Quốc gia ngày …" trên website EVN, số liệu do Công ty Vận hành HTĐ và TTĐ Quốc gia (NSMO), trước đây là Trung tâm Điều độ HTĐ Quốc gia, cung cấp.
- File tạo bởi `parser.py` từ HTML gốc trong `data/raw_html/`. Mã hóa UTF-8 có BOM, nên mở được bằng Excel mà không lỗi font.
- **Số liệu giữ nguyên như bài gốc**, kể cả khi bài gõ sai. Các ngày nghi có lỗi được đánh dấu bằng cột `qc_energy_diff` (mục 3), không tự sửa.
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
| `qc_…` | Cột kiểm tra chất lượng do parser tính, không có trong bài gốc |

### Các thời kỳ định dạng bài

EVN đã thay đổi cách trình bày bài theo thời gian. Parser đọc được mọi định dạng, nhưng **một số cột chỉ có ở một thời kỳ**:

| Thời kỳ | Số ngày | Đặc điểm | Cột có / không có |
|---|---|---|---|
| 28–29/05/2023 | 2 | Bảng công suất lấy tại **giờ cố định** (12h và 21h/22h). Tuabin khí tách chạy gas / chạy dầu | Có `e_gas_gasfuel`, `e_gas_oilfuel`, `noon_/eve_gas_gasfuel`, `…_oilfuel` |
| 30/05/2023 → 03/06/2024 | 362 | Điện mặt trời **gộp chung** trang trại và mái nhà. Một con số Pmax và sản lượng | Có `e_solar_total`. **Không có** `e_solar_farm`, `e_rooftop`, mọi cột `_dc` |
| 04/06/2024 → nay | 890 | Tách ĐMT trang trại và mái nhà. Pmax và sản lượng tính theo **2 cách** (thương phẩm, đầu cực) | Có `e_solar_farm`, `e_rooftop`, `e_rooftop_dc`, mọi cột `_dc`. **Không có** `e_solar_total` |

> **Hệ quả cho mô hình:** cột `_dc` chỉ có từ 04/06/2024. Muốn dùng toàn bộ chuỗi 2023–2026 thì dùng các cột **không `_dc`** (`pmax_mw`, `energy_mkwh`). Để so sánh điện mặt trời qua các thời kỳ, dùng `e_solar_total` cho giai đoạn trước, và `e_solar_farm + e_rooftop` cho giai đoạn sau.

### Hai cách ước tính điện mặt trời mái nhà (ĐMTMN)

ĐMTMN không được đo trực tiếp ở cấp hệ thống, nên EVN công bố hai con số ước tính:

- **Thương phẩm** (cột không có hậu tố): tính theo lượng điện mái nhà **bán lên lưới**, tức phần đo được qua công tơ.
- **Đầu cực** (cột `_dc`): ước tính **toàn bộ điện mái nhà phát ra** tại đầu cực tấm pin, gồm cả phần chủ nhà tự dùng. Vì vậy giá trị luôn **lớn hơn hoặc bằng** cách thương phẩm.

Hai cách chỉ khác nhau ở phần ĐMTMN, các nguồn khác giống nhau:

```
energy_mkwh_dc = energy_mkwh - e_rooftop + e_rooftop_dc
noon_total_dc  = noon_total  - noon_rooftop + noon_rooftop_dc
```

> **Khuyến nghị:** dùng cột *thương phẩm* (không `_dc`) làm biến mục tiêu chính, vì nó có đủ từ 2023. Có thể thử bản `_dc` như một mục tiêu thay thế từ 06/2024, vì nó gần với nhu cầu điện thực của xã hội hơn.

---

## 2. Từ điển cột

Cột "Ví dụ" lấy từ ngày **10/11/2026**. Cột "Khoảng giá trị" là min → max trên toàn bộ dữ liệu.

### 2.1. Thời gian

| Cột | Kiểu | Ý nghĩa | Ví dụ |
|---|---|---|---|
| `date` | date `YYYY-MM-DD` | Ngày vận hành mà số liệu mô tả. **Không phải** ngày đăng bài. | 2026-11-10 |

### 2.2. Chỉ tiêu tổng (biến mục tiêu)

| Cột | Đơn vị | Ý nghĩa | Ví dụ | Khoảng giá trị | Có từ |
|---|---|---|---|---|---|
| `pmax_mw` | MW | Công suất lớn nhất trong ngày của toàn hệ thống (đỉnh phụ tải), ĐMTMN theo thương phẩm | 50018.6 | 24 343 → 57 537 | 28/05/2023 |
| `pmax_time` | HH:MM | Thời điểm xảy ra `pmax_mw` | 17:45 | | 28/05/2023 |
| `energy_mkwh` | triệu kWh | Sản lượng điện sản xuất và nhập khẩu trong ngày ("sản lượng tiêu thụ" trong các bài 2023–2024), ĐMTMN theo thương phẩm | 959.9 | 434.6 → 1 215.4 | 28/05/2023 |
| `pmax_mw_dc` | MW | Như `pmax_mw`, ĐMTMN theo đầu cực | 50136.2 | 24 984 → 58 328 | 04/06/2024 |
| `pmax_time_dc` | HH:MM | Thời điểm xảy ra `pmax_mw_dc`. Có thể khác `pmax_time`, vì cộng thêm điện mái nhà làm đỉnh dịch về buổi chiều. | 17:00 | | 04/06/2024 |
| `energy_mkwh_dc` | triệu kWh | Như `energy_mkwh`, ĐMTMN theo đầu cực | 971.8 | 457.5 → 1 221.9 | 04/06/2024 |
| `qc_energy_diff` | triệu kWh | **Kiểm tra chất lượng:** tổng các nguồn `e_*` trừ `energy_mkwh`. Bình thường trong khoảng ±0,5 (do làm tròn). Giá trị lớn cho thấy bài gốc có lỗi (mục 3.3) | 0.0 | −399.9 → 1.6 | |
| `qc_same_as_adjacent` | 0/1 | **Kiểm tra chất lượng:** 1 nếu Pmax, giờ Pmax, sản lượng, thủy điện và nhiệt điện than **trùng y hệt** ngày liền trước hoặc liền sau. Dấu hiệu EVN đăng nhầm số liệu (mục 3.3) | 0 | 0 → 1 | |

**Mức trung bình theo năm** (cho thấy xu hướng tăng rõ rệt):

| Năm | Số ngày | Pmax TB (MW) | Pmax lớn nhất (MW) | Sản lượng TB (triệu kWh) |
|---|---|---|---|---|
| 2023 (từ 28/05) | 206 | 39 331 | 45 474 | 794 |
| 2024 | 366 | 41 717 | 48 955 | 844 |
| 2025 | 365 | 44 053 | 54 370 | 878 |
| 2026 (đến 10/11) | 314 | 47 883 | 57 537 | 979 |

### 2.3. Cơ cấu sản lượng theo nguồn: `e_*` (triệu kWh/ngày)

Tổng các nguồn bằng `energy_mkwh`, sai lệch do làm tròn khoảng ±0,5. Khi tính tổng, điện mặt trời là `e_solar_total` (trước 04/06/2024) hoặc `e_solar_farm + e_rooftop` (từ 04/06/2024).

| Cột | Nguồn (tên gốc trong bài) | Ví dụ | Khoảng giá trị | Thời kỳ |
|---|---|---|---|---|
| `e_hydro` | Thủy điện | 183.2 | 30.8* → 487.7 | toàn bộ |
| `e_coal` | Nhiệt điện than | 418.4 | 192.5 → 644.0 | toàn bộ |
| `e_gas` | Tuabin khí (Gas + Dầu DO) | 123.6 | 18.0 → 123.6 | toàn bộ |
| `e_gas_gasfuel` | Tuabin khí chạy gas | | 86.0 → 94.8 | chỉ 28–29/05/2023 |
| `e_gas_oilfuel` | Tuabin khí chạy dầu | | 2.4 → 16.2 | chỉ 28–29/05/2023 |
| `e_oil` | Nhiệt điện dầu | 3.6 | 0.0 → 14.8 | toàn bộ (thiếu 19 ngày, bài không ghi dòng này) |
| `e_wind` | Điện gió | 124.7 | 2.6 → 131.1 | toàn bộ |
| `e_solar_total` | Điện mặt trời, **gộp** trang trại và mái nhà | | 31.6 → 94.3 | đến 03/06/2024 |
| `e_solar_farm` | ĐMT trang trại (nhà máy nối lưới) | 33.6 | 7.1 → 58.8 | từ 04/06/2024 |
| `e_rooftop` | ĐMT mái nhà (ước tính thương phẩm) | 26.8 | 4.1 → 47.2 | từ 04/06/2024 |
| `e_rooftop_dc` | ĐMT mái nhà (ước tính đầu cực) | 38.7 | 9.4 → 61.9 | từ 04/06/2024 |
| `e_import` | Nhập khẩu điện (Lào, Trung Quốc…) | 42.9 | 0.4 → 66.3 | toàn bộ |
| `e_other` | Khác (sinh khối, diesel…) | 3.2 | 1.0 → 6.3 | toàn bộ |

\* 30.8 là lỗi gõ của bài ngày 20/09/2025 (mục 3). Giá trị nhỏ nhất thật là 40.9 (01/05/2024).

### 2.4. Công suất huy động tại hai thời điểm: `noon_*`, `eve_*` (MW)

Lấy từ bảng "CÔNG SUẤT HUY ĐỘNG …" trong bài. Mỗi nguồn có hai giá trị:
- `noon_<nguồn>`: lúc **thấp điểm trưa**. Bức xạ mặt trời mạnh nên điện mặt trời phát nhiều, còn phụ tải lấy từ lưới thấp.
- `eve_<nguồn>`: lúc **cao điểm tối**. Không có mặt trời, các nguồn khác phải bù lên.

`<nguồn>` dùng cùng tên với mục 2.3: `hydro`, `coal`, `gas`, `gas_gasfuel`, `gas_oilfuel`, `oil`, `wind`, `solar_farm`, `rooftop`, `rooftop_dc`, `import`, `other`. Khác với mục 2.3, bảng này **luôn tách** `solar_farm` và `rooftop`, kể cả ở thời kỳ 2023–2024. Ngoài ra còn các cột:

| Cột | Ý nghĩa | Ví dụ (trưa / tối) |
|---|---|---|
| `noon_total`, `eve_total` | Tổng công suất toàn quốc, ĐMTMN theo thương phẩm (= tổng các nguồn, dùng `rooftop`) | 38818.1 / 41320.5 |
| `noon_total_dc`, `eve_total_dc` | Tổng công suất toàn quốc, ĐMTMN theo đầu cực (từ 04/06/2024) | 40389.2 / 41320.5 |
| `noon_label`, `eve_label` | Thời điểm lấy số liệu, chuẩn hóa từ tiêu đề cột của bảng gốc (xem bảng dưới) | thấp điểm trưa / cao điểm tối |

| `noon_label` | `eve_label` | Số ngày | Thời kỳ |
|---|---|---|---|
| `12:00` | `22:00` | 1 | 28/05/2023 |
| `12:00` | `21:00` | 1 | 29/05/2023 |
| `thấp điểm trưa` | `cao điểm chiều-tối` | 267 | 30/05/2023 → 02/03/2024 |
| `thấp điểm trưa` | `cao điểm tối` | 981 | 03/03/2024 → nay |
| trống | trống | 4 | ngày bài không có bảng (mục 3) |

**Lưu ý:**
- Hai ngày đầu lấy số liệu tại **giờ cố định**. Từ 30/05/2023, số liệu lấy tại **thời điểm thấp điểm và cao điểm thực tế** của từng ngày, nên giữa hai thời kỳ này số liệu không hoàn toàn so sánh được. Việc đổi chữ "chiều-tối" thành "tối" (03/03/2024) có thể chỉ là đổi cách viết. Mình chưa có thông tin xác nhận.
- `eve_solar_farm`, `eve_rooftop`, `eve_rooftop_dc` bằng **0** vì buổi tối không có mặt trời (duy nhất ngày 02/06/2023 có `eve_rooftop` = 1). Hai cột tổng `eve_total` và `eve_total_dc` do đó luôn bằng nhau. Khi làm mô hình có thể bỏ các cột này.
- Bảng **không ghi giờ cụ thể** của thời điểm thấp điểm và cao điểm. "Cao điểm tối" khác với thời điểm Pmax: Pmax thường xảy ra 14–16h hoặc khoảng 18h, nên `eve_total` thường nhỏ hơn `pmax_mw` (99,7% số ngày năm 2026).

### 2.5. Truy vết nguồn

| Cột | Ý nghĩa | Ví dụ |
|---|---|---|
| `article_id` | Mã bài trên website EVN. File HTML gốc là `data/raw_html/<article_id>.html` | 510268 |
| `published` | Thời điểm EVN đăng bài (`DD/MM/YYYY HH:MM`, GMT+7), thường là khoảng 10–11h sáng **hôm sau** | 11/11/2026 10:55 |
| `title` | Tiêu đề gốc của bài | Thông tin chung về vận hành hệ thống điện Quốc gia ngày 10/11/2026 |

> **`published` quyết định khoảng cách dự báo.** Số liệu của ngày D chỉ có từ khoảng 11h ngày D+1. Dự báo cho ngày D+1 phải xong **trong ngày D**, lúc đó số liệu mới nhất là của ngày **D−1**. Vậy giá trị mới nhất dùng được cách ngày cần dự báo **2 ngày**: biến lag nhỏ nhất là **lag 2**, không được dùng lag 1. (Bản trước của tài liệu ghi nhầm là dùng được số liệu ngày D. Đã sửa ngày 11/11/2026 trong Giai đoạn 3.)

---

## 3. Dữ liệu thiếu và điểm bất thường

### 3.1. Ngày không có bài (9 ngày, 0,7%)

`2023-06-07`, `2023-06-08`, `2023-06-28` → `2023-07-03` (6 ngày), `2023-08-09`. Danh sách nằm trong `data/not_found_dates.txt`.

Đã kiểm tra bằng 3 cách: tìm kiếm trên website (nhiều kiểu tiêu đề), dò toàn bộ mã bài nằm giữa hai ngày lân cận, và đối chiếu trang danh sách của chuyên mục (chuyên mục nhảy thẳng từ 06/06 sang 09/06/2023). Kết luận: **EVN không đăng bài cho các ngày này trong chuyên mục.** Các dòng này không có trong `evn_daily.csv`. Khi làm mô hình cần xử lý khoảng trống, không được coi ngày kế tiếp là "hôm qua".

### 3.2. Bài thiếu một phần số liệu (trong bài gốc)

| Ngày | Thiếu |
|---|---|
| 08/10/2023, 10/10/2023 | Pmax và giờ Pmax |
| 07/12/2023 | Pmax, sản lượng và cơ cấu nguồn (bài chỉ có bảng công suất) |
| 03/12/2023, 27/12/2023, 13/03/2026, 14/03/2026 | Bảng công suất (`noon_*`, `eve_*`) |

Các ô thiếu để trống (NaN), không tự điền.

### 3.3. Số liệu nghi có lỗi trong bài gốc

**a) Số liệu trùng y hệt ngày kề: cờ `qc_same_as_adjacent` (14 ngày, phát hiện ở Giai đoạn 3)**

7 cặp ngày liền nhau có Pmax, giờ Pmax, sản lượng, cơ cấu nguồn và bảng công suất **giống nhau đến từng chữ số**. Hai ngày vận hành khác nhau không thể trùng như vậy: EVN đã đăng số liệu của một ngày cho cả hai bài. **Chỉ một trong hai ngày là đúng**, và bài gốc không cho biết ngày nào.

| Cặp ngày | Thứ | Pmax (MW) | Gợi ý ngày đúng |
|---|---|---|---|
| 05/06 – 06/06/2023 | T2 – T3 | 37 950,3 | Không xác định |
| 23/08 – 24/08/2024 | T6 – T7 | 42 363,8 | Không xác định |
| 28/02 – 01/03/2025 | T6 – T7 | 42 260,8 | Không xác định |
| 04/07 – 05/07/2025 | T6 – T7 | 44 603,0 | Không xác định |
| 31/12/2025 – 01/01/2026 | T4 – Tết Dương lịch | 35 742,6 | Nhiều khả năng **01/01/2026**: mức này hợp với ngày lễ, còn ngày 31/12 thấp bất thường (EDA câu 7) |
| 30/01 – 31/01/2026 | T6 – T7 | 43 863,1 | Không xác định |
| 15/03 – 16/03/2026 | CN – T2 | 48 121,0 | Nhiều khả năng **16/03/2026**: quá cao so với một Chủ nhật |

> **Quy tắc:** khi huấn luyện mô hình, loại cả hai ngày của mỗi cặp (đặt NaN), trừ khi có căn cứ chọn được ngày đúng.

**b) Tổng các nguồn không khớp tổng sản lượng: cột `qc_energy_diff`**

| Ngày | `qc_energy_diff` | Nhận định |
|---|---|---|
| **20/09/2025** | **−399.9** | Bài ghi thủy điện **30,8** triệu kWh, các ngày lân cận là 405–430. Tính ngược từ tổng thì giá trị đúng khoảng **430,7**: bài bị mất chữ số "4". |
| 24/05 → 02/06/2024 (10 ngày) | −5.9 → −6.5 | Lệch đều khoảng 6 triệu kWh mỗi ngày. Có thể một nguồn không được liệt kê trong giai đoạn này. Chưa rõ nguyên nhân. |
| 04/07/2023 | −7.8 | Chưa rõ nguyên nhân |
| 10/10/2025 | −10.0 | Chưa rõ nguyên nhân |

> **Quy tắc:** ngày nào `|qc_energy_diff| > 2` thì xem lại trước khi dùng cột `e_*`. Biến mục tiêu `pmax_mw` và `energy_mkwh` của các ngày này vẫn bình thường so với các ngày lân cận.

### 3.4. Các trường hợp khác

| Vấn đề | Ngày | Ghi chú |
|---|---|---|
| Bài đăng trùng | 10/08/2023 (hai bài khác số liệu), 24–27/11/2024 (đăng lại y hệt) | Giữ bài có `article_id` lớn nhất, coi là bản mới hoặc bản đính chính |
| Phụ tải thấp bất thường | Tết Nguyên đán: 10/02/2024, 29/01/2025, 17/02/2026 | Pmax thấp nhất cả chuỗi (24 343 MW vào Mùng 1 Tết 2024). Là số liệu thật, cần biến lịch Tết |
| Cách viết khác thường trong bài gốc | Nhiều bài năm 2023, 04/08/2026 | "37 950,3" (dấu cách ngăn nghìn), "triệu Kwh", "65,4: triệu kWh", "triệu k", tiêu đề "06/102023". Parser đã xử lý được tất cả |

Danh sách bài parse thiếu trường hoặc trùng ngày được ghi vào `data/parse_issues.csv` mỗi lần chạy `parser.py`. Lần chạy hiện tại: 3 bài thiếu trường, 5 ngày trùng.

## 4. Các file dữ liệu khác

| File | Nội dung |
|---|---|
| `data/links.csv` | Danh sách bài: `article_id`, `date`, `url`, `title` |
| `data/raw_html/*.html` | HTML gốc từng bài (không đưa lên Git). Giữ lại để parse lại khi cần, không phải crawl lại. |
| `data/not_found_dates.txt` | Các ngày crawler không tìm thấy bài (9 ngày, mục 3.1) |
| `data/parse_issues.csv` | Bài parse lỗi hoặc trùng ngày |

---

## 5. `data/weather.csv`: thời tiết

- **Nguồn:** [Open-Meteo](https://open-meteo.com/), miễn phí, giấy phép CC BY 4.0. Múi giờ `Asia/Ho_Chi_Minh`, nên mỗi "ngày" tính từ 00:00 đến 23:59 giờ Việt Nam.
- **Phạm vi:** 28/05/2023 → 10/11/2026, 1 263 ngày, 64 cột. Gồm cả 9 ngày EVN không có bài.
- **Tên cột:** `<loại>_<biến>_<địa điểm>`, ví dụ `fc_tmax_hn` là nhiệt độ cao nhất *dự báo* tại Hà Nội.

### 5.1. Loại số liệu: `obs_` và `fc_`

| Tiền tố | Ý nghĩa | API | Dùng khi |
|---|---|---|---|
| `obs_` | Thời tiết **thực tế** (tái phân tích, gần với số đo) | Archive API | Phân tích (EDA), hiểu quan hệ thời tiết và phụ tải |
| `fc_` | **Bản dự báo phát hành trước 1 ngày** (`*_previous_day1`), gộp từ dữ liệu theo giờ | Previous Runs API | **Huấn luyện và đánh giá mô hình**, vì đây là thông tin mô hình thực sự có khi dự báo ngày mai |

> **Vì sao cần `fc_`:** khi dự báo phụ tải ngày mai, ta chưa biết thời tiết thật của ngày mai, chỉ có bản dự báo. Nếu đánh giá mô hình bằng `obs_`, sai số sẽ thấp hơn so với khi dùng thật. Sai số của `fc_` so với `obs_` (Tmax, toàn bộ giai đoạn): Hà Nội 1,18°C, Đà Nẵng 1,07°C, TP.HCM 1,03°C, toàn quốc 0,78°C. Riêng năm 2026 sai số nhỏ hơn: 0,72–0,80°C.

**Dữ liệu dự báo bị thiếu** (giới hạn của Open-Meteo, không phải lỗi code):

| Biến `fc_` | Thiếu | Lý do |
|---|---|---|
| `tmax`, `tmin`, `tmean` | 21 ngày, 30/12/2023 → 19/01/2024 | Kho lưu bản dự báo cũ bị gián đoạn |
| `app_tmax`, `rh`, `rad`, `cloud`, `precip` | 237 ngày, 28/05/2023 → 19/01/2024 | Open-Meteo chỉ lưu các biến này từ 20/01/2024 |

Ngày nào bản dự báo có dưới 20/24 giờ dữ liệu thì để trống (`MIN_HOURS` trong `weather.py`), vì tính max, min hay tổng từ vài giờ sẽ cho kết quả sai. Các cột `obs_` không thiếu ngày nào.

### 5.2. Biến

| `<biến>` | Ý nghĩa | Đơn vị |
|---|---|---|
| `tmax` | Nhiệt độ cao nhất trong ngày (2 m) | °C |
| `tmin` | Nhiệt độ thấp nhất trong ngày | °C |
| `tmean` | Nhiệt độ trung bình ngày | °C |
| `app_tmax` | Nhiệt độ cảm nhận cao nhất (gộp ảnh hưởng của độ ẩm và gió) | °C |
| `rh` | Độ ẩm tương đối trung bình | % |
| `rad` | Tổng bức xạ mặt trời trong ngày (ảnh hưởng đến điện mặt trời) | MJ/m² |
| `cloud` | Lượng mây trung bình | % |
| `precip` | Tổng lượng mưa | mm |

### 5.3. Địa điểm

| `<địa điểm>` | Nơi | Tọa độ | Trọng số |
|---|---|---|---|
| `hn` | Hà Nội (miền Bắc) | 21.0285, 105.8542 | 0,45 |
| `dn` | Đà Nẵng (miền Trung) | 16.0544, 108.2022 | 0,10 |
| `hcm` | TP.HCM (miền Nam) | 10.8231, 106.6297 | 0,45 |
| `vn` | **Trung bình có trọng số** của 3 điểm trên | | |

> **Giả định:** trọng số 0,45 / 0,10 / 0,45 là ước lượng xấp xỉ tỷ trọng phụ tải từng miền, **chưa lấy từ nguồn chính thức**. Nếu có số liệu của EVN/NSMO thì sửa `REGION_WEIGHTS` trong `weather.py`. Vì các cột của từng miền vẫn được giữ, mô hình có thể tự học trọng số thay vì dùng cột `vn`.

Mỗi thành phố chỉ là một điểm đại diện cho cả miền. Thời tiết các tỉnh khác trong miền có thể khác.

---

## 6. `data/calendar.csv`: lịch

- **Nguồn:** thư viện `holidays` 0.107 (Vietnam). Lịch đã gồm ngày lễ theo Bộ luật Lao động 2019, Tết và Giỗ Tổ tính theo âm lịch, ngày nghỉ bù và ngày hoán đổi theo quyết định hằng năm của Chính phủ.
- **Phạm vi:** 28/05/2023 → hôm nay + 60 ngày. Lịch biết trước được, nên file có sẵn cả các ngày tương lai để dùng khi dự báo.

| Cột | Ý nghĩa | Ví dụ |
|---|---|---|
| `date` | Ngày | 2026-09-02 |
| `dow` | Thứ trong tuần: 0 = thứ Hai … 6 = Chủ nhật | 2 |
| `month` | Tháng (1–12) | 9 |
| `day_of_year` | Thứ tự ngày trong năm (1–366) | 245 |
| `week_of_year` | Tuần ISO (1–53) | 36 |
| `is_weekend` | 1 nếu là thứ Bảy hoặc Chủ nhật | 0 |
| `is_holiday` | 1 nếu là ngày lễ, nghỉ bù hoặc nghỉ hoán đổi chính thức | 1 |
| `holiday_name` | Tên ngày lễ (tiếng Việt), trống nếu không phải ngày lễ | Quốc khánh |
| `is_makeup_workday` | 1 nếu là thứ Bảy/Chủ nhật **phải đi làm bù** cho ngày nghỉ hoán đổi | 0 |
| `is_day_off` | 1 nếu là ngày nghỉ theo luật: (cuối tuần và không làm bù) hoặc ngày lễ | 1 |
| `off_block_len` | Độ dài chuỗi ngày nghỉ liên tiếp chứa ngày này (0 nếu là ngày làm việc). Ví dụ Tết 2026 = 9 | 5 |
| `is_pre_day_off` | 1 nếu là ngày làm việc ngay **trước** một ngày nghỉ | 0 |
| `is_post_day_off` | 1 nếu là ngày làm việc ngay **sau** một ngày nghỉ | 0 |
| `tet_offset` | Số ngày so với Mùng 1 Tết gần nhất (âm = trước Tết). Ví dụ 16/02/2026 (Giao thừa) = −1 | −167 |

**Mùng 1 Tết trong dữ liệu:** 10/02/2024, 29/01/2025, 17/02/2026. **Thứ Bảy làm bù:** 04/05/2024, 26/04/2025, 22/08/2026.

### 6.1. Kiểm chứng với số liệu phụ tải

Đối chiếu với `energy_mkwh` giai đoạn 2023–2026, tính tỉ lệ so với trung vị các ngày làm việc cùng tuần:

| Loại ngày | Tỉ lệ phụ tải |
|---|---|
| Thứ Hai – thứ Sáu làm việc | 0,98 – 1,00 |
| **Thứ Bảy** | **0,97** |
| Chủ nhật | 0,88 |
| Ngày lễ ngoài Tết | trung bình 0,79 (0,65 – 0,96) |
| Thứ Bảy làm bù (04/05/2024, 26/04/2025, 22/08/2026) | 0,97 – 1,00, gần bằng thứ Bảy thường |

> **Phát hiện:** theo luật thứ Bảy là ngày nghỉ (`is_day_off = 1`), nhưng phụ tải thứ Bảy **gần như bằng ngày làm việc**, vì phần lớn phụ tải công nghiệp vẫn chạy. Khi làm mô hình, nên dùng riêng `dow` và `is_holiday` thay vì chỉ dùng `is_day_off`.
