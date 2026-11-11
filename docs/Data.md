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

### Cách đọc tên cột (tóm tắt)

Bảng này chỉ giúp đọc nhanh tên cột. **Ý nghĩa đầy đủ của từng cột nằm trong từ điển ở mục 2**, mỗi cột một dòng.

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

### 2.4. Công suất huy động tại hai thời điểm trong ngày (MW)

Lấy từ bảng "CÔNG SUẤT HUY ĐỘNG …" trong bài. Bảng cho biết **mỗi nguồn đang phát bao nhiêu MW** tại hai thời điểm:
- **Thấp điểm trưa** (cột bắt đầu bằng `noon_`): bức xạ mặt trời mạnh nên điện mặt trời phát nhiều, còn phụ tải lấy từ lưới thấp.
- **Cao điểm tối** (cột bắt đầu bằng `eve_`): không có mặt trời, các nguồn khác phải bù lên.

Khác với mục 2.3, bảng này **luôn tách** ĐMT trang trại và mái nhà, kể cả ở thời kỳ 2023–2024. Tổng các nguồn của một thời điểm bằng cột `…_total` của thời điểm đó.

| Cột | Ý nghĩa | Ví dụ 10/11/2026 | Khoảng giá trị | Số ngày có | Thời kỳ có dữ liệu |
|---|---|---|---|---|---|
| `noon_total` | **Tổng công suất toàn quốc**, ĐMT mái nhà theo ước tính thương phẩm (= tổng các nguồn bên dưới, dùng `rooftop`) lúc **thấp điểm trưa** | 38 818.1 | 14 384.2 → 52 681.3 | 1250 | từ 28/05/2023 |
| `eve_total` | **Tổng công suất toàn quốc**, ĐMT mái nhà theo ước tính thương phẩm (= tổng các nguồn bên dưới, dùng `rooftop`) lúc **cao điểm tối** | 41 320.5 | 21 495.9 → 55 459.1 | 1250 | từ 28/05/2023 |
| `noon_total_dc` | **Tổng công suất toàn quốc**, ĐMT mái nhà theo ước tính đầu cực (dùng `rooftop_dc`) lúc **thấp điểm trưa** | 40 389.2 | 17 271.7 → 53 630.9 | 888 | từ 04/06/2024 |
| `eve_total_dc` | **Tổng công suất toàn quốc**, ĐMT mái nhà theo ước tính đầu cực (dùng `rooftop_dc`) lúc **cao điểm tối** | 41 320.5 | 21 495.9 → 55 459.1 | 888 | từ 04/06/2024 |
| `noon_hydro` | Công suất thủy điện lúc **thấp điểm trưa** | 4 962.8 | 25.5 → 19 638 | 1250 | từ 28/05/2023 |
| `eve_hydro` | Công suất thủy điện lúc **cao điểm tối** | 9 144.5 | 3 289.8 → 22 529 | 1250 | từ 28/05/2023 |
| `noon_coal` | Công suất nhiệt điện than lúc **thấp điểm trưa** | 14 577.5 | 6 947.9 → 26 216 | 1250 | từ 28/05/2023 |
| `eve_coal` | Công suất nhiệt điện than lúc **cao điểm tối** | 18 025.9 | 8 302.8 → 27 643.7 | 1250 | từ 28/05/2023 |
| `noon_gas` | Công suất tuabin khí (chạy gas và dầu DO, gộp) lúc **thấp điểm trưa** | 4 049 | 669.0 → 4 618 | 1250 | từ 28/05/2023 |
| `eve_gas` | Công suất tuabin khí (chạy gas và dầu DO, gộp) lúc **cao điểm tối** | 6 447 | 653.0 → 7 652 | 1250 | từ 28/05/2023 |
| `noon_gas_gasfuel` | Công suất tuabin khí chạy gas (chỉ 2 bài đầu tiên tách riêng) lúc **thấp điểm trưa** |  | 1 786 → 2 853 | 2 | 28/05/2023 → 29/05/2023 |
| `eve_gas_gasfuel` | Công suất tuabin khí chạy gas (chỉ 2 bài đầu tiên tách riêng) lúc **cao điểm tối** |  | 4 344 → 4 876 | 2 | 28/05/2023 → 29/05/2023 |
| `noon_gas_oilfuel` | Công suất tuabin khí chạy dầu (chỉ 2 bài đầu tiên tách riêng) lúc **thấp điểm trưa** |  | 0.0 → 0.0 | 2 | 28/05/2023 → 29/05/2023 |
| `eve_gas_oilfuel` | Công suất tuabin khí chạy dầu (chỉ 2 bài đầu tiên tách riêng) lúc **cao điểm tối** |  | 0.0 → 1 568 | 2 | 28/05/2023 → 29/05/2023 |
| `noon_oil` | Công suất nhiệt điện dầu lúc **thấp điểm trưa** | 66.0 | 0.0 → 330.0 | 1232 | từ 28/05/2023 |
| `eve_oil` | Công suất nhiệt điện dầu lúc **cao điểm tối** | 330.0 | 0.0 → 813.0 | 1232 | từ 28/05/2023 |
| `noon_wind` | Công suất điện gió lúc **thấp điểm trưa** | 5 849.3 | 31.7 → 5 849.3 | 1250 | từ 28/05/2023 |
| `eve_wind` | Công suất điện gió lúc **cao điểm tối** | 5 191.4 | 41.9 → 5 351.1 | 1250 | từ 28/05/2023 |
| `noon_solar_farm` | Công suất điện mặt trời trang trại (nhà máy nối lưới) lúc **thấp điểm trưa** | 4 091.7 | 129.1 → 7 620.1 | 1250 | từ 28/05/2023 |
| `eve_solar_farm` | Công suất điện mặt trời trang trại (nhà máy nối lưới) lúc **cao điểm tối** | 0.0 | 0.0 → 0.0 | 1228 | từ 28/05/2023 |
| `noon_rooftop` | Công suất điện mặt trời mái nhà, ước tính thương phẩm lúc **thấp điểm trưa** | 3 302 | 377.0 → 6 543.4 | 1250 | từ 28/05/2023 |
| `eve_rooftop` | Công suất điện mặt trời mái nhà, ước tính thương phẩm lúc **cao điểm tối** | 0.0 | 0.0 → 1.0 | 1228 | từ 28/05/2023 |
| `noon_rooftop_dc` | Công suất điện mặt trời mái nhà, ước tính đầu cực lúc **thấp điểm trưa** | 4 873.1 | 1 095.9 → 8 567.4 | 888 | từ 04/06/2024 |
| `eve_rooftop_dc` | Công suất điện mặt trời mái nhà, ước tính đầu cực lúc **cao điểm tối** | 0.0 | 0.0 → 0.0 | 888 | từ 04/06/2024 |
| `noon_import` | Công suất nhập khẩu điện lúc **thấp điểm trưa** | 1 787.7 | 18.0 → 8 671.7* | 1250 | từ 28/05/2023 |
| `eve_import` | Công suất nhập khẩu điện lúc **cao điểm tối** | 2 048.9 | 29.3 → 2 972.8 | 1250 | từ 28/05/2023 |
| `noon_other` | Công suất nguồn khác (sinh khối, diesel…) lúc **thấp điểm trưa** | 132.0 | 36.5 → 262.8 | 1249 | từ 28/05/2023 |
| `eve_other` | Công suất nguồn khác (sinh khối, diesel…) lúc **cao điểm tối** | 132.8 | 1.0 → 263.6 | 1248 | từ 28/05/2023 |
| `noon_label` | **Thời điểm** lấy số liệu cho các cột `noon_*` (chuẩn hóa từ tiêu đề cột của bảng gốc). Các giá trị: xem bảng bên dưới | thấp điểm trưa | | 1250 | từ 28/05/2023 |
| `eve_label` | **Thời điểm** lấy số liệu cho các cột `eve_*` (chuẩn hóa từ tiêu đề cột của bảng gốc). Các giá trị: xem bảng bên dưới | cao điểm tối | | 1250 | từ 28/05/2023 |

\* 8 671.7 (29/07/2025) nghi là lỗi gõ trong bài gốc (mục 3.3c). Các ngày khác không vượt quá khoảng 3 000.

"Số ngày có" nhỏ hơn 1 250 ở một số cột (`noon/eve_oil`, `eve_solar_farm`, `eve_rooftop`, `…_other`) vì bài không ghi dòng đó, hoặc để trống ô buổi tối của điện mặt trời.

Giá trị của `noon_label` và `eve_label`:

| `noon_label` | `eve_label` | Số ngày | Thời kỳ |
|---|---|---|---|
| `12:00` | `22:00` | 1 | 28/05/2023 |
| `12:00` | `21:00` | 1 | 29/05/2023 |
| `thấp điểm trưa` | `cao điểm chiều-tối` | 267 | 30/05/2023 → 02/03/2024 |
| `thấp điểm trưa` | `cao điểm tối` | 981 | 03/03/2024 → nay |
| trống | trống | 4 | ngày bài không có bảng (mục 3) |

**Lưu ý:**
- Hai ngày đầu lấy số liệu tại **giờ cố định**. Từ 30/05/2023, số liệu lấy tại **thời điểm thấp điểm và cao điểm thực tế** của từng ngày, nên giữa hai thời kỳ này số liệu không hoàn toàn so sánh được. Việc đổi chữ "chiều-tối" thành "tối" (03/03/2024) có thể chỉ là đổi cách viết, chưa có thông tin xác nhận.
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

**c) Bảng công suất (`noon_*`, `eve_*`): phát hiện khi lập từ điển cột, chưa có cờ tự động**

| Ngày | Cột | Nhận định |
|---|---|---|
| **29/07/2025** | `noon_import` = **8 671.7** MW | Các ngày lân cận chỉ 780–1 730 MW. Sản lượng nhập khẩu cả ngày 40,6 triệu kWh tương đương trung bình khoảng 1 700 MW. Nghi là lỗi gõ (có thể là 1 671,7). Tổng các nguồn vẫn khớp `noon_total` (45 511), nên có thể `noon_total` cũng được tính từ con số sai. |
| 16/01/2024, 02/02/2024, 28/05/2023 | `eve_*` | Tổng các nguồn buổi tối nhỏ hơn `eve_total` lần lượt 199, 161 và 10 MW. Các ngày khác khớp trong khoảng ±5 MW. |

> **Quy tắc:** các cột `noon_*`, `eve_*` không phải biến mục tiêu. Nếu dùng làm đặc trưng thì bỏ giá trị `noon_import` ngày 29/07/2025.

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
- **Tên cột** ghép từ 3 phần `<loại>_<biến>_<địa điểm>`, ví dụ `fc_tmax_hn` là nhiệt độ cao nhất *dự báo* tại Hà Nội. Ý nghĩa của **từng cột** liệt kê đầy đủ ở mục 5.3.

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

### 5.2. Địa điểm

| `<địa điểm>` | Nơi | Tọa độ | Trọng số |
|---|---|---|---|
| `hn` | Hà Nội (miền Bắc) | 21.0285, 105.8542 | 0,45 |
| `dn` | Đà Nẵng (miền Trung) | 16.0544, 108.2022 | 0,10 |
| `hcm` | TP.HCM (miền Nam) | 10.8231, 106.6297 | 0,45 |
| `vn` | **Trung bình có trọng số** của 3 điểm trên | | |

> **Giả định:** trọng số 0,45 / 0,10 / 0,45 là ước lượng xấp xỉ tỷ trọng phụ tải từng miền, **chưa lấy từ nguồn chính thức**. Nếu có số liệu của EVN/NSMO thì sửa `REGION_WEIGHTS` trong `weather.py`. Vì các cột của từng miền vẫn được giữ, mô hình có thể tự học trọng số thay vì dùng cột `vn`.

Mỗi thành phố chỉ là một điểm đại diện cho cả miền. Thời tiết các tỉnh khác trong miền có thể khác.

### 5.3. Từ điển cột

| Cột | Ý nghĩa | Ví dụ |
|---|---|---|
| `date` | Ngày (giờ Việt Nam). Khóa nối với `evn_daily.csv` và `calendar.csv` | 2026-11-10 |

Mỗi biến thời tiết có 8 cột: 2 loại số liệu (thực tế `obs_`, dự báo `fc_`) × 4 địa điểm (Hà Nội, Đà Nẵng, TP.HCM, trung bình toàn quốc). Cột "Số ngày thiếu" tính trên 1 263 ngày; lý do thiếu ở mục 5.1.
**Nhiệt độ cao nhất trong ngày (đo ở độ cao 2 m)** (°C)

| Cột | Ý nghĩa | Ví dụ 10/11/2026 | Khoảng giá trị | Số ngày thiếu |
|---|---|---|---|---|
| `obs_tmax_hn` | Nhiệt độ cao nhất trong ngày, thực tế, tại Hà Nội | 19.8 | 11.3 → 40.2 | 0 |
| `obs_tmax_dn` | Nhiệt độ cao nhất trong ngày, thực tế, tại Đà Nẵng | 25.3 | 19.1 → 40.3 | 0 |
| `obs_tmax_hcm` | Nhiệt độ cao nhất trong ngày, thực tế, tại TP.HCM | 34.6 | 26.4 → 39.5 | 0 |
| `obs_tmax_vn` | Nhiệt độ cao nhất trong ngày, thực tế, **trung bình toàn quốc** (có trọng số của 3 điểm) | 27.0 | 21.7 → 39.2 | 0 |
| `fc_tmax_hn` | Nhiệt độ cao nhất trong ngày, **dự báo** (phát hành trước 1 ngày), tại Hà Nội | 20.7 | 9.4 → 41.4 | 21 |
| `fc_tmax_dn` | Nhiệt độ cao nhất trong ngày, **dự báo** (phát hành trước 1 ngày), tại Đà Nẵng | 24.7 | 19.0 → 43.4 | 21 |
| `fc_tmax_hcm` | Nhiệt độ cao nhất trong ngày, **dự báo** (phát hành trước 1 ngày), tại TP.HCM | 33.7 | 26.3 → 39.3 | 21 |
| `fc_tmax_vn` | Nhiệt độ cao nhất trong ngày, **dự báo** (phát hành trước 1 ngày), **trung bình toàn quốc** (có trọng số của 3 điểm) | 26.9 | 20.5 → 40.1 | 21 |

**Nhiệt độ thấp nhất trong ngày** (°C)

| Cột | Ý nghĩa | Ví dụ 10/11/2026 | Khoảng giá trị | Số ngày thiếu |
|---|---|---|---|---|
| `obs_tmin_hn` | Nhiệt độ thấp nhất trong ngày, thực tế, tại Hà Nội | 15.4 | 7.1 → 29.2 | 0 |
| `obs_tmin_dn` | Nhiệt độ thấp nhất trong ngày, thực tế, tại Đà Nẵng | 23.0 | 15.9 → 31.0 | 0 |
| `obs_tmin_hcm` | Nhiệt độ thấp nhất trong ngày, thực tế, tại TP.HCM | 24.3 | 17.7 → 29.3 | 0 |
| `obs_tmin_vn` | Nhiệt độ thấp nhất trong ngày, thực tế, **trung bình toàn quốc** (có trọng số của 3 điểm) | 20.2 | 13.6 → 28.1 | 0 |
| `fc_tmin_hn` | Nhiệt độ thấp nhất trong ngày, **dự báo** (phát hành trước 1 ngày), tại Hà Nội | 16.9 | 8.0 → 30.3 | 21 |
| `fc_tmin_dn` | Nhiệt độ thấp nhất trong ngày, **dự báo** (phát hành trước 1 ngày), tại Đà Nẵng | 23.4 | 13.1 → 31.2 | 21 |
| `fc_tmin_hcm` | Nhiệt độ thấp nhất trong ngày, **dự báo** (phát hành trước 1 ngày), tại TP.HCM | 24.3 | 17.1 → 28.7 | 21 |
| `fc_tmin_vn` | Nhiệt độ thấp nhất trong ngày, **dự báo** (phát hành trước 1 ngày), **trung bình toàn quốc** (có trọng số của 3 điểm) | 20.9 | 13.2 → 28.0 | 21 |

**Nhiệt độ trung bình ngày** (°C)

| Cột | Ý nghĩa | Ví dụ 10/11/2026 | Khoảng giá trị | Số ngày thiếu |
|---|---|---|---|---|
| `obs_tmean_hn` | Nhiệt độ trung bình ngày, thực tế, tại Hà Nội | 17.3 | 9.2 → 33.0 | 0 |
| `obs_tmean_dn` | Nhiệt độ trung bình ngày, thực tế, tại Đà Nẵng | 24.4 | 18.3 → 34.3 | 0 |
| `obs_tmean_hcm` | Nhiệt độ trung bình ngày, thực tế, tại TP.HCM | 28.3 | 23.7 → 32.5 | 0 |
| `obs_tmean_vn` | Nhiệt độ trung bình ngày, thực tế, **trung bình toàn quốc** (có trọng số của 3 điểm) | 23.0 | 19.0 → 32.5 | 0 |
| `fc_tmean_hn` | Nhiệt độ trung bình ngày, **dự báo** (phát hành trước 1 ngày), tại Hà Nội | 18.7 | 8.8 → 34.2 | 21 |
| `fc_tmean_dn` | Nhiệt độ trung bình ngày, **dự báo** (phát hành trước 1 ngày), tại Đà Nẵng | 24.0 | 18.0 → 34.2 | 21 |
| `fc_tmean_hcm` | Nhiệt độ trung bình ngày, **dự báo** (phát hành trước 1 ngày), tại TP.HCM | 27.7 | 23.2 → 32.4 | 21 |
| `fc_tmean_vn` | Nhiệt độ trung bình ngày, **dự báo** (phát hành trước 1 ngày), **trung bình toàn quốc** (có trọng số của 3 điểm) | 23.3 | 18.5 → 32.4 | 21 |

**Nhiệt độ cảm nhận cao nhất trong ngày (tính cả độ ẩm và gió)** (°C)

| Cột | Ý nghĩa | Ví dụ 10/11/2026 | Khoảng giá trị | Số ngày thiếu |
|---|---|---|---|---|
| `obs_app_tmax_hn` | Nhiệt độ cảm nhận cao nhất trong ngày, thực tế, tại Hà Nội | 18.6 | 8.2 → 46.9 | 0 |
| `obs_app_tmax_dn` | Nhiệt độ cảm nhận cao nhất trong ngày, thực tế, tại Đà Nẵng | 26.9 | 19.2 → 46.1 | 0 |
| `obs_app_tmax_hcm` | Nhiệt độ cảm nhận cao nhất trong ngày, thực tế, tại TP.HCM | 39.4 | 30.2 → 44.2 | 0 |
| `obs_app_tmax_vn` | Nhiệt độ cảm nhận cao nhất trong ngày, thực tế, **trung bình toàn quốc** (có trọng số của 3 điểm) | 28.8 | 22.5 → 45.2 | 0 |
| `fc_app_tmax_hn` | Nhiệt độ cảm nhận cao nhất trong ngày, **dự báo** (phát hành trước 1 ngày), tại Hà Nội | 19.3 | 7.2 → 48.1 | 237 |
| `fc_app_tmax_dn` | Nhiệt độ cảm nhận cao nhất trong ngày, **dự báo** (phát hành trước 1 ngày), tại Đà Nẵng | 26.4 | 19.3 → 49.0 | 237 |
| `fc_app_tmax_hcm` | Nhiệt độ cảm nhận cao nhất trong ngày, **dự báo** (phát hành trước 1 ngày), tại TP.HCM | 39.6 | 27.7 → 45.1 | 237 |
| `fc_app_tmax_vn` | Nhiệt độ cảm nhận cao nhất trong ngày, **dự báo** (phát hành trước 1 ngày), **trung bình toàn quốc** (có trọng số của 3 điểm) | 29.1 | 22.6 → 46.1 | 237 |

**Độ ẩm tương đối trung bình ngày** (%)

| Cột | Ý nghĩa | Ví dụ 10/11/2026 | Khoảng giá trị | Số ngày thiếu |
|---|---|---|---|---|
| `obs_rh_hn` | Độ ẩm tương đối trung bình ngày, thực tế, tại Hà Nội | 67.0 | 44.0 → 97.0 | 0 |
| `obs_rh_dn` | Độ ẩm tương đối trung bình ngày, thực tế, tại Đà Nẵng | 85.0 | 48.0 → 95.0 | 0 |
| `obs_rh_hcm` | Độ ẩm tương đối trung bình ngày, thực tế, tại TP.HCM | 75.0 | 51.0 → 93.0 | 0 |
| `obs_rh_vn` | Độ ẩm tương đối trung bình ngày, thực tế, **trung bình toàn quốc** (có trọng số của 3 điểm) | 72.4 | 50.1 → 91.6 | 0 |
| `fc_rh_hn` | Độ ẩm tương đối trung bình ngày, **dự báo** (phát hành trước 1 ngày), tại Hà Nội | 54.4 | 46.9 → 96.0 | 237 |
| `fc_rh_dn` | Độ ẩm tương đối trung bình ngày, **dự báo** (phát hành trước 1 ngày), tại Đà Nẵng | 87.7 | 50.7 → 95.5 | 237 |
| `fc_rh_hcm` | Độ ẩm tương đối trung bình ngày, **dự báo** (phát hành trước 1 ngày), tại TP.HCM | 80.6 | 51.1 → 94.1 | 237 |
| `fc_rh_vn` | Độ ẩm tương đối trung bình ngày, **dự báo** (phát hành trước 1 ngày), **trung bình toàn quốc** (có trọng số của 3 điểm) | 69.5 | 53.5 → 90.9 | 237 |

**Tổng bức xạ mặt trời trong ngày** (MJ/m²)

| Cột | Ý nghĩa | Ví dụ 10/11/2026 | Khoảng giá trị | Số ngày thiếu |
|---|---|---|---|---|
| `obs_rad_hn` | Tổng bức xạ mặt trời trong ngày, thực tế, tại Hà Nội | 6.2 | 1.9 → 26.4 | 0 |
| `obs_rad_dn` | Tổng bức xạ mặt trời trong ngày, thực tế, tại Đà Nẵng | 9.3 | 1.4 → 26.6 | 0 |
| `obs_rad_hcm` | Tổng bức xạ mặt trời trong ngày, thực tế, tại TP.HCM | 18.0 | 4.5 → 26.0 | 0 |
| `obs_rad_vn` | Tổng bức xạ mặt trời trong ngày, thực tế, **trung bình toàn quốc** (có trọng số của 3 điểm) | 11.8 | 4.3 → 24.9 | 0 |
| `fc_rad_hn` | Tổng bức xạ mặt trời trong ngày, **dự báo** (phát hành trước 1 ngày), tại Hà Nội | 11.1 | 0.8 → 27.1 | 237 |
| `fc_rad_dn` | Tổng bức xạ mặt trời trong ngày, **dự báo** (phát hành trước 1 ngày), tại Đà Nẵng | 5.9 | 0.6 → 27.0 | 237 |
| `fc_rad_hcm` | Tổng bức xạ mặt trời trong ngày, **dự báo** (phát hành trước 1 ngày), tại TP.HCM | 18.6 | 3.8 → 26.0 | 237 |
| `fc_rad_vn` | Tổng bức xạ mặt trời trong ngày, **dự báo** (phát hành trước 1 ngày), **trung bình toàn quốc** (có trọng số của 3 điểm) | 13.9 | 4.9 → 24.7 | 237 |

**Lượng mây che phủ trung bình ngày** (%)

| Cột | Ý nghĩa | Ví dụ 10/11/2026 | Khoảng giá trị | Số ngày thiếu |
|---|---|---|---|---|
| `obs_cloud_hn` | Lượng mây che phủ trung bình ngày, thực tế, tại Hà Nội | 83.0 | 0.0 → 100.0 | 0 |
| `obs_cloud_dn` | Lượng mây che phủ trung bình ngày, thực tế, tại Đà Nẵng | 94.0 | 1.0 → 100.0 | 0 |
| `obs_cloud_hcm` | Lượng mây che phủ trung bình ngày, thực tế, tại TP.HCM | 91.0 | 4.0 → 100.0 | 0 |
| `obs_cloud_vn` | Lượng mây che phủ trung bình ngày, thực tế, **trung bình toàn quốc** (có trọng số của 3 điểm) | 87.7 | 6.3 → 100.0 | 0 |
| `fc_cloud_hn` | Lượng mây che phủ trung bình ngày, **dự báo** (phát hành trước 1 ngày), tại Hà Nội | 77.8 | 0.0 → 100.0 | 237 |
| `fc_cloud_dn` | Lượng mây che phủ trung bình ngày, **dự báo** (phát hành trước 1 ngày), tại Đà Nẵng | 99.4 | 1.5 → 100.0 | 237 |
| `fc_cloud_hcm` | Lượng mây che phủ trung bình ngày, **dự báo** (phát hành trước 1 ngày), tại TP.HCM | 58.2 | 3.3 → 100.0 | 237 |
| `fc_cloud_vn` | Lượng mây che phủ trung bình ngày, **dự báo** (phát hành trước 1 ngày), **trung bình toàn quốc** (có trọng số của 3 điểm) | 71.1 | 2.5 → 100.0 | 237 |

**Tổng lượng mưa trong ngày** (mm)

| Cột | Ý nghĩa | Ví dụ 10/11/2026 | Khoảng giá trị | Số ngày thiếu |
|---|---|---|---|---|
| `obs_precip_hn` | Tổng lượng mưa trong ngày, thực tế, tại Hà Nội | 0.4 | 0.0 → 133.0 | 0 |
| `obs_precip_dn` | Tổng lượng mưa trong ngày, thực tế, tại Đà Nẵng | 91.0 | 0.0 → 173.7 | 0 |
| `obs_precip_hcm` | Tổng lượng mưa trong ngày, thực tế, tại TP.HCM | 3.3 | 0.0 → 52.6 | 0 |
| `obs_precip_vn` | Tổng lượng mưa trong ngày, thực tế, **trung bình toàn quốc** (có trọng số của 3 điểm) | 10.8 | 0.0 → 61.7 | 0 |
| `fc_precip_hn` | Tổng lượng mưa trong ngày, **dự báo** (phát hành trước 1 ngày), tại Hà Nội | 0.0 | 0.0 → 147.5 | 237 |
| `fc_precip_dn` | Tổng lượng mưa trong ngày, **dự báo** (phát hành trước 1 ngày), tại Đà Nẵng | 69.3 | 0.0 → 137.2 | 237 |
| `fc_precip_hcm` | Tổng lượng mưa trong ngày, **dự báo** (phát hành trước 1 ngày), tại TP.HCM | 9.6 | 0.0 → 56.3 | 237 |
| `fc_precip_vn` | Tổng lượng mưa trong ngày, **dự báo** (phát hành trước 1 ngày), **trung bình toàn quốc** (có trọng số của 3 điểm) | 11.2 | 0.0 → 71.4 | 237 |

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
