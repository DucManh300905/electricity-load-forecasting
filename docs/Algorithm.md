# Cách hoạt động của mô hình dự báo

Tài liệu giải thích **từng bước** mô hình biến dữ liệu thành một con số dự báo: thuật toán, công thức và **hai ví dụ tính tay trên ngày thật** của tập test. Các con số trong ví dụ được tính lại bằng đúng mô hình đã dùng trong backtest, và **khớp với `data/backtest.csv`**.

Kết quả tổng hợp và đánh giá: [`Model.md`](Model.md). Mã nguồn: [`features.py`](../features.py), [`train.py`](../train.py).

## Mục lục

1. [Tổng quan quy trình](#1-tổng-quan-quy-trình)
2. [Bước 1: Baseline sạch](#2-bước-1-baseline-sạch)
3. [Bước 2: Biến mục tiêu dạng tỉ lệ](#3-bước-2-biến-mục-tiêu-dạng-tỉ-lệ)
4. [Bước 3: Đặc trưng đầu vào](#4-bước-3-đặc-trưng-đầu-vào)
5. [Thuật toán 1: Hồi quy Ridge](#5-thuật-toán-1-hồi-quy-ridge)
6. [Thuật toán 2: LightGBM](#6-thuật-toán-2-lightgbm-gradient-boosting)
7. [Bước 4: Kết hợp (Ensemble) và đổi về MW](#7-bước-4-kết-hợp-ensemble-và-đổi-về-mw)
8. [Ví dụ 1: Ngày nắng nóng 24/06/2026](#8-ví-dụ-1-ngày-nắng-nóng-24062026)
9. [Ví dụ 2: Ngày lễ Quốc khánh 02/09/2026](#9-ví-dụ-2-ngày-lễ-quốc-khánh-02092026)
10. [Huấn luyện: walk-forward](#10-huấn-luyện-walk-forward)
11. [Chọn tham số và chọn mô hình](#11-chọn-tham-số-và-chọn-mô-hình)
12. [Cách đo sai số và kiểm định](#12-cách-đo-sai-số-và-kiểm-định)
13. [Khoảng dự báo (quantile)](#13-khoảng-dự-báo-quantile)

---

## 1. Tổng quan quy trình

Mục tiêu: **trong ngày D**, dự báo Pmax (MW) và sản lượng (triệu kWh) của **ngày D+1**. Lúc dự báo, EVN mới công bố số liệu đến ngày **D−1**, nên số liệu mới nhất cách ngày cần dự báo **2 ngày**.

```
  Số liệu EVN đến ngày D−1 ─┐
  Lịch của ngày D+1 ────────┼─► (1) Baseline sạch ──► base
  Nhiệt độ DỰ BÁO ngày D+1 ─┘          │
                                       ▼
                     (2)+(3) Đặc trưng x ──► Ridge ──────► tỉ lệ r₁ ─┐
                                        └──► LightGBM ──► tỉ lệ r₂ ─┤
                                                                     ▼
                                    (4) r = (r₁ + r₂)/2  →  Dự báo = r × base
```

| Biến mục tiêu | Mô hình cuối | Cách tính tỉ lệ |
|---|---|---|
| Pmax | **Ensemble** | r = (r_Ridge + r_LightGBM) / 2 |
| Sản lượng | **Ridge** | r = r_Ridge |

Ý tưởng chính: mô hình **không dự báo trực tiếp** giá trị MW, mà dự báo **"ngày mai sẽ cao hơn hay thấp hơn mức bình thường bao nhiêu phần trăm"**.

---

## 2. Bước 1: Baseline sạch

### Định nghĩa

```
base(t) = trung bình của 4 ngày gần nhất trong các ngày t−7, t−14, …, t−56
          (cùng thứ với t) thỏa mãn đồng thời:
            • có số liệu (không thiếu, không bị cờ lỗi)
            • KHÔNG phải ngày lễ và KHÔNG nằm trong ±10 ngày quanh Mùng 1 Tết
          Cần ít nhất 2 ngày hợp lệ, nếu không thì không dự báo.
```

### Vì sao "sạch"?

Baseline thông thường lấy 4 tuần cùng thứ gần nhất, bất kể ngày đó là gì. Nếu tuần trước là kỳ nghỉ lễ, baseline bị **kéo thấp** và dự báo ngày thường sau đó sẽ sai. Baseline sạch **bỏ qua các ngày lễ/Tết** và lùi thêm tuần để lấy đủ 4 ngày bình thường.

### Vì sao luôn lấy cùng thứ?

Phụ tải Chủ nhật thấp hơn ngày thường khoảng 13% (EDA câu 2). So thứ Tư với thứ Tư thì hiệu ứng thứ trong tuần **tự triệt tiêu**.

### Thuộc tính quan trọng

- Chỉ dùng các ngày **≤ t−7**, luôn có sẵn khi dự báo (vì độ trễ tối thiểu là 2 ngày).
- **Tự cập nhật theo xu hướng:** baseline luôn là mức của 4–8 tuần gần nhất, nên phụ tải tăng 7,5%/năm đã được phản ánh sẵn trong baseline.

---

## 3. Bước 2: Biến mục tiêu dạng tỉ lệ

```
ratio(t) = y(t) / base(t)           (khi huấn luyện: y là giá trị thực tế)
ŷ(t)     = r̂(t) × base(t)           (khi dự báo: r̂ là tỉ lệ do mô hình dự báo)
```

| ratio | Nghĩa |
|---|---|
| 1,00 | Ngày mai bằng mức bình thường của 4 tuần trước |
| 1,05 | Cao hơn 5% (ví dụ trời nóng hơn) |
| 0,75 | Thấp hơn 25% (ví dụ ngày lễ) |

**Vì sao không dự báo trực tiếp MW?** Phụ tải năm 2026 cao hơn mọi năm trước. Mô hình cây (LightGBM) **không dự báo được giá trị lớn hơn những gì nó đã thấy** khi huấn luyện. Còn tỉ lệ thì luôn dao động quanh 1, ở mọi năm, nên mô hình học được quy luật dùng chung cho cả giai đoạn.

---

## 4. Bước 3: Đặc trưng đầu vào

Mỗi ngày cần dự báo t được mô tả bằng 27 con số (đặc trưng). **Mọi số liệu EVN đều lấy từ ngày ≤ t−2.**

### 4.1. Lịch của ngày t (biết trước)

| Đặc trưng | Cách tính |
|---|---|
| `dow` | Thứ trong tuần, 0 = T2 … 6 = CN |
| `is_holiday` | 1 nếu là ngày lễ / nghỉ bù / nghỉ hoán đổi chính thức |
| `off_block_len` | Số ngày của kỳ nghỉ liên tiếp chứa ngày t (0 nếu đi làm) |
| `is_pre_day_off`, `is_post_day_off` | Ngày làm việc ngay trước / ngay sau kỳ nghỉ |
| `is_makeup_workday` | Thứ Bảy/CN phải đi làm bù |
| `tet_offset` | Số ngày so với Mùng 1 Tết, chỉ giữ trong khoảng −10 → +15, ngoài khoảng gán 99 |
| `doy_sin`, `doy_cos` | sin(2π·ngày_trong_năm/365,25) và cos(…): vị trí trong năm dưới dạng vòng tròn, để 31/12 và 01/01 nằm cạnh nhau |

### 4.2. Độ lệch gần đây (từ số liệu EVN, trễ ≥ 2 ngày)

| Đặc trưng | Công thức | Ý nghĩa |
|---|---|---|
| `ratio_lag2` | y(t−2) / base(t−2), bỏ trống nếu t−2 là ngày lễ/Tết | Ngày gần nhất có số liệu đang cao hay thấp so với bình thường |
| `ratio_mean_2_8` | trung bình ratio từ t−8 đến t−2 (chỉ ngày thường) | Xu hướng của tuần gần nhất |
| `base_growth_4w` | base(t) / base(t−28) − 1 | Mức nền đang tăng nhanh hay chậm |

### 4.3. Nhiệt độ dự báo, cho mỗi miền r ∈ {Hà Nội `hn`, Đà Nẵng `dn`, TP.HCM `hcm`}

| Đặc trưng | Công thức |
|---|---|
| `fc_tmax_r`, `fc_tmean_r` | Nhiệt độ cao nhất / trung bình **dự báo** của ngày t |
| `hot_r` | max(0, fc_tmax_r − 30): phần vượt ngưỡng 30°C |
| `dtmax_r` | fc_tmax_r(t) − trung bình Tmax **thực tế** của 4 ngày tham chiếu của baseline |
| `dhot_r` | hot_r(t) − trung bình max(0, Tmax thực tế − 30) của 4 ngày tham chiếu |

**Vì sao cần `dtmax` và `dhot`?** Mô hình dự báo **tỉ lệ so với baseline**. Nếu 4 ngày tham chiếu cũng nóng như ngày mai thì baseline đã "chứa" sẵn ảnh hưởng của nắng nóng. Điều quan trọng là ngày mai **nóng hơn hay mát hơn các ngày tham chiếu** bao nhiêu.

**Vì sao ngưỡng 30°C?** EDA (câu 4) cho thấy phụ tải gần như không đổi khi Tmax dưới 30°C, và tăng mạnh khi vượt 30°C.

---

## 5. Thuật toán 1: Hồi quy Ridge

### 5.1. Mô hình

Ridge là **hồi quy tuyến tính**: tỉ lệ dự báo bằng một hằng số cộng tổng có trọng số của các đặc trưng.

```
r̂ = β₀ + β₁·z₁ + β₂·z₂ + … + β_p·z_p
```

- `z_j` là đặc trưng thứ j **đã chuẩn hóa**: `z_j = (x_j − trung bình_j) / độ lệch chuẩn_j`, tính trên tập huấn luyện. Nhờ vậy các hệ số β so sánh được với nhau dù đặc trưng có đơn vị khác nhau (°C, số ngày, tỉ lệ).
- Mỗi tích `β_j·z_j` là **đóng góp** của đặc trưng j vào dự báo.

### 5.2. Cách tìm hệ số

Ridge chọn các hệ số β làm nhỏ nhất:

```
Σᵢ (ratioᵢ − r̂ᵢ)²   +   α · Σⱼ βⱼ²
└─ sai số bình phương ─┘   └─ phạt hệ số lớn ─┘
```

Có công thức đóng: `β = (ZᵀZ + αI)⁻¹ Zᵀ(ratio − mean)`, và `β₀ = trung bình ratio của tập huấn luyện`.

- **α = 0:** hồi quy tuyến tính thường (bình phương nhỏ nhất).
- **α lớn:** các hệ số bị kéo về gần 0, mô hình "thận trọng" hơn và ít học quá khớp hơn.
- Phần phạt rất quan trọng ở đây, vì nhiều đặc trưng **tương quan mạnh với nhau** (nhiệt độ 3 miền cùng tăng vào mùa hè). Không có phạt, các hệ số sẽ dao động rất lớn.
- **α được chọn trên tập kiểm định:** Pmax α = 10, sản lượng α = 1.

### 5.3. Mã hóa riêng cho Ridge

Ridge là mô hình tuyến tính, nên các đặc trưng phân loại được mã hóa lại (`ridge_design`):
- `dow` → 6 biến 0/1 (`dow_1` … `dow_6`; thứ Hai là mốc so sánh).
- `tet_offset` → 7 biến 0/1 theo nhóm ngày: −10…−8, −7…−4, −3…−1, 0…3, 4…6, 7…10, 11…15.
- Thêm `holiday_x_dow5`, `holiday_x_dow6`: ngày lễ rơi vào thứ Bảy / Chủ nhật.
- Giá trị thiếu (ví dụ `ratio_lag2` khi t−2 là ngày lễ) được điền bằng **trung vị** của tập huấn luyện.

### 5.4. Ưu, nhược điểm

| Ưu điểm | Nhược điểm |
|---|---|
| Dễ giải thích: mỗi hệ số là một con số | Chỉ học được quan hệ tuyến tính (phải tự tạo `hot_r` để mô tả phi tuyến) |
| Ổn định với ít dữ liệu, kể cả ngày hiếm như lễ/Tết | Hệ số của các biến tương quan nhau khó diễn giải riêng lẻ (xem ví dụ 1) |
| Huấn luyện tức thì | |

---

## 6. Thuật toán 2: LightGBM (gradient boosting)

### 6.1. Ý tưởng

LightGBM xây **600 cây quyết định nhỏ, nối tiếp nhau**. Mỗi cây sau học cách **sửa phần sai còn lại** của tất cả các cây trước.

```
F₀        = giá trị khởi đầu (≈ tỉ lệ điển hình của tập huấn luyện, ≈ 0,99)
F_m(x)    = F_{m−1}(x) + η · h_m(x)          m = 1, 2, …, 600
r̂         = F_600(x)
```

- `h_m` là cây thứ m, có **tối đa 15 lá**. Mỗi lá chứa một con số điều chỉnh.
- `η = 0,03` là **tốc độ học**: mỗi cây chỉ sửa 3% phần sai, để các cây sau tiếp tục tinh chỉnh. Học chậm nhưng ít học quá khớp.

### 6.2. Mỗi cây học gì?

Ở bước m, với mỗi ngày i trong tập huấn luyện, tính **phần sai còn lại** (pseudo-residual) theo hàm mất mát:

| Hàm mất mát | Dùng cho | Phần sai còn lại gᵢ | Giá trị tại mỗi lá |
|---|---|---|---|
| L2: (y − F)² | Sản lượng | yᵢ − F_{m−1}(xᵢ) | trung bình gᵢ của các ngày rơi vào lá |
| **L1: \|y − F\|** | **Pmax** | dấu(yᵢ − F_{m−1}(xᵢ)) = ±1 | **trung vị** phần sai của các ngày rơi vào lá |

Cây được dựng sao cho các ngày có phần sai giống nhau rơi vào cùng một lá. Hàm L1 (được chọn cho Pmax) **ít bị ảnh hưởng bởi ngày bất thường** hơn L2, vì nó dùng trung vị thay vì trung bình.

### 6.3. Cách dựng một cây

1. **Chia giá trị thành ô (histogram):** mỗi đặc trưng được chia thành tối đa 255 khoảng. Thuật toán chỉ thử các ngưỡng tại ranh giới các khoảng, nên rất nhanh.
2. **Mọc theo lá (leaf-wise):** ở mỗi bước, chọn **lá nào và ngưỡng nào** giảm sai số nhiều nhất để chia đôi. Ví dụ "`is_holiday` ≤ 0,5?" hoặc "`dhot_hn` ≤ 1,8?". Dừng khi đủ 15 lá.
3. **Ràng buộc chống học quá khớp:** mỗi lá cần ít nhất 10 ngày (`min_child_samples`). Mỗi cây chỉ dùng ngẫu nhiên 90% số ngày (`subsample`) và 90% số đặc trưng (`colsample_bytree`).
4. **Giá trị thiếu:** khi chia nhánh, thuật toán tự học xem ngày bị thiếu giá trị nên đi nhánh nào.

### 6.4. Tham số đã chọn (trên tập kiểm định)

| | Pmax | Sản lượng |
|---|---|---|
| Hàm mất mát | L1 | L2 |
| Số lá tối đa | 15 | 15 |
| Số ngày tối thiểu mỗi lá | 10 | 10 |
| Số cây | 600 | 300 |
| Tốc độ học | 0,03 | 0,03 |

### 6.5. Giải thích một dự báo: SHAP

Với mô hình cây, đóng góp của từng đặc trưng vào một dự báo cụ thể được tính bằng **giá trị SHAP** (LightGBM có sẵn, `pred_contrib=True`):

```
r̂ = giá trị gốc + Σⱼ SHAPⱼ
```

`SHAPⱼ > 0`: đặc trưng j đẩy dự báo lên; `< 0`: kéo xuống. Dùng trong hai ví dụ dưới đây.

### 6.6. Ưu, nhược điểm

| Ưu điểm | Nhược điểm |
|---|---|
| Tự học quan hệ phi tuyến và tương tác (ví dụ nóng **và** ngày thường) | Kém ở trường hợp hiếm (lễ/Tết), vì ít dữ liệu để chia nhánh |
| Xử lý giá trị thiếu tự động | Không ngoại suy (đã xử lý bằng cách dự báo tỉ lệ) |
| Tốt nhất ở ngày nắng nóng (MAPE 2,24%) | Khó giải thích hơn Ridge, cần SHAP |

---

## 7. Bước 4: Kết hợp (Ensemble) và đổi về MW

```
Pmax:       r̂ = (r̂_Ridge + r̂_LightGBM) / 2          ŷ = r̂ × base
Sản lượng:  r̂ = r̂_Ridge                              ŷ = r̂ × base
```

**Vì sao lấy trung bình lại tốt hơn?** Hai mô hình **sai theo kiểu khác nhau**: Ridge tốt ở lễ/Tết, LightGBM tốt ở ngày nắng nóng. Khi một mô hình sai lệch, mô hình kia thường kéo lại. Trên tập kiểm định của Pmax, trung bình hai mô hình đạt 2,25%, tốt hơn Ridge (2,34%) và LightGBM (2,37%). Với sản lượng thì Ridge một mình tốt nhất (2,20%), nên được chọn.

---

## 8. Ví dụ 1: Ngày nắng nóng 24/06/2026

**Thứ Tư, ngày Pmax đạt kỷ lục 57 536,7 MW.** Dự báo được lập ngày 23/06, khi EVN mới có số liệu đến hết 22/06.

### Bước 1: Baseline sạch

Lấy các thứ Tư trước đó, chọn 4 ngày gần nhất không phải lễ/Tết:

| Ngày tham chiếu | Cách ngày dự báo | Pmax thực tế (MW) | Ngày lễ/Tết? | Dùng? |
|---|---|---|---|---|
| 17/06/2026 | t−7 | 53 119,4 | Không | ✔ |
| 10/06/2026 | t−14 | 48 962,3 | Không | ✔ |
| 03/06/2026 | t−21 | 53 453,8 | Không | ✔ |
| 27/05/2026 | t−28 | 57 189,4 | Không | ✔ |
| 20/05/2026 … | t−35 … | | | (đã đủ 4 ngày) |

```
base = (53 119,4 + 48 962,3 + 53 453,8 + 57 189,4) / 4 = 53 181,2 MW
```

Không tuần nào có lễ, nên baseline sạch trùng với baseline TB 4 tuần thông thường.

### Bước 2: Đặc trưng (một số đặc trưng chính)

| Đặc trưng | Cách tính | Giá trị |
|---|---|---|
| `dow` | Thứ Tư | 2 |
| `is_holiday`, `off_block_len` | Ngày thường | 0, 0 |
| `ratio_lag2` | y(22/06) / base(22/06) = 53 447,8 / 54 292,0 | 0,9845 |
| `ratio_mean_2_8` | TB tỉ lệ 16/06 → 22/06 | 1,0097 |
| `base_growth_4w` | base(24/06) / base(27/05) − 1 | +0,0884 |
| `fc_tmax_hn` | Tmax dự báo Hà Nội | 36,7°C |
| `hot_hn` | max(0, 36,7 − 30) | 6,7 |
| `dtmax_hn` | 36,7 − TB(33,9; 30,4; 35,0; 36,7) = 36,7 − 34,0 | +2,7°C |
| `dhot_hn` | 6,7 − TB(3,9; 0,4; 5,0; 6,7) = 6,7 − 4,0 | +2,7 |
| `fc_tmax_dn`, `hot_dn`, `dhot_dn` | Đà Nẵng | 39,6°C; 9,6; +3,75 |
| `fc_tmax_hcm`, `hot_hcm`, `dhot_hcm` | TP.HCM | 35,2°C; 5,2; +2,45 |

Nhìn bằng mắt: ngày mai **nóng hơn các ngày tham chiếu khoảng 2,5–3,8°C ở cả 3 miền**, nên phụ tải dự kiến cao hơn baseline.

### Bước 3a: Ridge

Mô hình Ridge dùng cho tháng 6/2026 được huấn luyện trên 1 046 ngày (04/07/2023 → 30/05/2026).

```
r̂_Ridge = β₀ + Σ đóng góp = 0,99030 + 0,02500 = 1,01530
```

Đóng góp theo nhóm đặc trưng:

| Nhóm | Tổng đóng góp |
|---|---|
| Nhiệt độ | **+0,0431** |
| Lịch | +0,0168 |
| Mùa trong năm | −0,0091 |
| Độ lệch gần đây | −0,0258 |
| **Tổng** | **+0,0250** |

Một vài đóng góp riêng lẻ (z = giá trị đã chuẩn hóa):

| Đặc trưng | Giá trị | z | Hệ số β | Đóng góp β·z |
|---|---|---|---|---|
| `dhot_dn` | 3,75 | +1,63 | +0,0135 | +0,0220 |
| `dhot_hn` | 2,70 | +1,15 | +0,0168 | +0,0194 |
| `fc_tmean_hn` | 32,51 | +1,58 | +0,0104 | +0,0165 |
| `hot_hn` | 6,70 | +2,26 | +0,0055 | +0,0123 |
| `hot_dn` | 9,60 | +3,15 | −0,0065 | −0,0204 |
| `fc_tmax_dn` | 39,6 | +2,17 | −0,0063 | −0,0136 |
| `base_growth_4w` | 0,088 | +2,82 | −0,0075 | −0,0211 |

> **Lưu ý khi đọc hệ số Ridge:** `hot_dn` và `fc_tmax_dn` có hệ số **âm**, nghe có vẻ vô lý (nóng hơn mà phụ tải giảm?). Nguyên nhân là các biến nhiệt độ **tương quan rất mạnh với nhau**: `hot_dn`, `dhot_dn`, `fc_tmax_dn` gần như cùng tăng giảm. Mô hình chia ảnh hưởng giữa chúng theo cách khó diễn giải riêng lẻ. Chỉ nên đọc **tổng của cả nhóm**: nhóm nhiệt độ đóng góp **+4,3%**, đúng chiều trực giác.

```
Ridge: 1,01530 × 53 181,2 = 53 995,1 MW
```

### Bước 3b: LightGBM

Cùng tập huấn luyện 1 046 ngày, 600 cây, hàm mất mát L1.

**Dự báo được cộng dồn qua các cây:**

| Sau số cây | 1 | 2 | 3 | 10 | 50 | 100 | 300 | 600 |
|---|---|---|---|---|---|---|---|---|
| Tỉ lệ dự báo | 1,0054 | 1,0066 | 1,0078 | 1,0140 | 1,0393 | 1,0532 | 1,0627 | **1,0619** |

Mỗi cây chỉ nhích dự báo lên một chút (tốc độ học 0,03). Sau khoảng 300 cây thì dự báo gần như ổn định.

**Đóng góp SHAP:**

```
r̂_LightGBM = giá trị gốc + Σ SHAP = 0,99061 + 0,07127 = 1,06188
```

| Nhóm | Tổng SHAP |
|---|---|
| Nhiệt độ | **+0,0792** |
| Lịch | +0,0128 |
| Mùa trong năm | −0,0046 |
| Độ lệch gần đây | −0,0162 |

| Đặc trưng có SHAP lớn nhất | Giá trị | SHAP |
|---|---|---|
| `fc_tmean_dn` | 32,94°C | +0,0208 |
| `fc_tmean_hn` | 32,51°C | +0,0191 |
| `base_growth_4w` | +0,088 | −0,0179 |
| `dhot_hn` | +2,7 | +0,0137 |
| `fc_tmax_hn` | 36,7°C | +0,0095 |

LightGBM đánh giá ảnh hưởng của nắng nóng **mạnh gần gấp đôi** Ridge (+7,9% so với +4,3%), vì nó học được quan hệ phi tuyến: càng nóng thì phụ tải tăng càng nhanh.

```
LightGBM: 1,06188 × 53 181,2 = 56 472,0 MW
```

### Bước 4: Kết hợp và kết quả

```
r̂ = (1,01530 + 1,06188) / 2 = 1,03859
ŷ = 1,03859 × 53 181,2 = 55 233,5 MW
```

| Cách dự báo | Dự báo (MW) | Thực tế (MW) | Sai số |
|---|---|---|---|
| Lấy số 2 ngày trước (22/06) | 53 447,8 | 57 536,7 | −7,1% |
| Baseline TB 4 tuần | 53 181,2 | 57 536,7 | −7,6% |
| Ridge | 53 995,1 | 57 536,7 | −6,2% |
| LightGBM | 56 472,0 | 57 536,7 | −1,9% |
| **Ensemble (mô hình cuối)** | **55 233,5** | 57 536,7 | **−4,0%** |

**Nhận xét:** mô hình nhận ra ngày mai nóng và nâng dự báo lên gần 2 100 MW so với baseline, giảm sai số từ −7,6% xuống −4,0%. Ngày kỷ lục vẫn cao hơn dự báo: đây là đợt nắng nóng cực đoan, thuộc nhóm ngày khó nhất. Khoảng P10–P90 của ngày này là 54 235 – 57 049 MW, và giá trị thực tế **nằm trên P90**, minh họa cho việc khoảng dự báo đang quá hẹp (`Model.md` mục 8).

---

## 9. Ví dụ 2: Ngày lễ Quốc khánh 02/09/2026

**Thứ Tư, ngày thứ 5 của kỳ nghỉ 5 ngày (29/08 → 02/09).** Pmax thực tế 37 835,0 MW.

### Bước 1: Baseline sạch

| Ngày tham chiếu | Pmax (MW) | Dùng? |
|---|---|---|
| 26/08/2026 (t−7) | 50 601,1 | ✔ |
| 19/08/2026 (t−14) | 49 310,2 | ✔ |
| 12/08/2026 (t−21) | 56 134,0 | ✔ |
| 05/08/2026 (t−28) | 49 166,4 | ✔ |

```
base = (50 601,1 + 49 310,2 + 56 134,0 + 49 166,4) / 4 = 51 302,9 MW
```

Baseline là mức của một **thứ Tư đi làm bình thường**. Nếu dùng nguyên baseline để dự báo thì sẽ sai **+35,6%**.

### Bước 2: Đặc trưng chính

| Đặc trưng | Giá trị | Ý nghĩa |
|---|---|---|
| `is_holiday` | **1** | Ngày lễ |
| `off_block_len` | **5** | Thuộc kỳ nghỉ dài 5 ngày |
| `ratio_lag2` | **trống** | Ngày t−2 (31/08) cũng là ngày nghỉ, nên không dùng làm thông tin "độ lệch gần đây" |
| Nhiệt độ | 33,7°C (HN) | Nóng hơn ngày tham chiếu khoảng 1,5°C ở HN, mát hơn 0,7°C ở ĐN |

### Bước 3: Hai mô hình

Huấn luyện trên 1 138 ngày (04/07/2023 → 30/08/2026).

| Nhóm đặc trưng | Ridge: đóng góp | LightGBM: SHAP |
|---|---|---|
| **Lịch** | **−0,2135** | **−0,1943** |
| Nhiệt độ | +0,0139 | +0,0007 |
| Độ lệch gần đây | −0,0033 | −0,0286 |
| Mùa trong năm | −0,0096 | −0,0072 |
| Giá trị gốc | 0,9908 | 0,9913 |
| **Tỉ lệ dự báo** | **0,7782** | **0,7619** |

Chi tiết nhóm lịch:
- **Ridge:** `is_holiday` −0,162 (z = 5,31 vì ngày lễ rất hiếm, × hệ số −0,0305); `off_block_len` −0,051; `dow_2` −0,020.
- **LightGBM:** `is_holiday` −0,154; `off_block_len` −0,044.

Cả hai mô hình **cùng kết luận**: ngày lễ trong kỳ nghỉ dài làm phụ tải giảm khoảng 22–24%. Ở ngày lễ, nhiệt độ gần như không ảnh hưởng.

**Quá trình cộng dồn của LightGBM:**

| Sau số cây | 1 | 10 | 50 | 100 | 300 | 600 |
|---|---|---|---|---|---|---|
| Tỉ lệ dự báo | 1,0027 | 0,9946 | 0,8749 | 0,7920 | 0,7681 | **0,7619** |

Các cây đầu chưa "nhận ra" ngày lễ (vẫn quanh 1,0). Phải sau khoảng 50–100 cây, khi các nhánh chia theo `is_holiday` được cộng dồn, dự báo mới giảm mạnh.

### Bước 4: Kết quả

```
r̂ = (0,7782 + 0,7619) / 2 = 0,7701
ŷ = 0,7701 × 51 302,9 = 39 506,7 MW
```

| Cách dự báo | Dự báo (MW) | Thực tế (MW) | Sai số |
|---|---|---|---|
| Baseline TB 4 tuần | 51 302,9 | 37 835,0 | **+35,6%** |
| Lấy số 2 ngày trước (31/08, cũng là ngày nghỉ) | 42 101,8 | 37 835,0 | +11,3% |
| Ridge | 39 926,2 | 37 835,0 | +5,5% |
| LightGBM | 39 087,2 | 37 835,0 | +3,3% |
| **Ensemble (mô hình cuối)** | **39 506,7** | 37 835,0 | **+4,4%** |

**Nhận xét:** đây là loại ngày baseline thất bại hoàn toàn. Nhờ các đặc trưng lịch, mô hình giảm sai số từ **35,6% xuống 4,4%**. Đó là lý do MAPE nhóm lễ/Tết giảm từ khoảng 24% xuống khoảng 5,7% (`Model.md` mục 7).

---

## 10. Huấn luyện: walk-forward

Mô hình **không được huấn luyện một lần rồi dùng mãi**. Để mô phỏng đúng thực tế, backtest **huấn luyện lại vào đầu mỗi tháng**, chỉ bằng dữ liệu đã có tại thời điểm đó:

```
Dự báo cho các ngày của tháng M:
    tập huấn luyện = mọi ngày từ 01/07/2023 đến (ngày đầu tháng M − 2 ngày)
    (cửa sổ mở rộng: mỗi tháng có thêm dữ liệu mới)
```

| Tháng được dự báo | Dữ liệu huấn luyện | Số ngày |
|---|---|---|
| 06/2026 | 04/07/2023 → 30/05/2026 | 1 046 |
| 09/2026 | 04/07/2023 → 30/08/2026 | 1 138 |

**Vì sao "− 2 ngày"?** Dự báo đầu tiên của tháng 6 (cho 01/06) được lập ngày 31/05, lúc đó EVN mới có số liệu đến 30/05. Nếu cho mô hình học cả ngày 31/05 là dùng thông tin **chưa tồn tại** lúc dự báo (rò rỉ thông tin).

Ngày bắt đầu thực tế là 04/07/2023 (không phải 01/07), vì những ngày đầu chưa có đủ dữ liệu quá khứ để tính baseline.

---

## 11. Chọn tham số và chọn mô hình

Dữ liệu được chia theo thời gian, **không xáo trộn**:

| Tập | Thời gian | Dùng để |
|---|---|---|
| Huấn luyện | 07/2023 → | Học hệ số / cây (walk-forward) |
| **Kiểm định** | 11/11/2024 → 10/11/2025 | **Chọn tham số và chọn mô hình cuối** |
| **Test** | 11/11/2025 → 10/11/2026 | **Chấm điểm một lần duy nhất** |

Quy trình:
1. Với mỗi bộ tham số (6 giá trị α của Ridge; 16 tổ hợp của LightGBM), chạy walk-forward trên **tập kiểm định**, tính MAPE.
2. Giữ bộ tham số có MAPE kiểm định nhỏ nhất.
3. So 3 ứng viên Ridge / LightGBM / Ensemble trên tập kiểm định, chọn mô hình cuối.
4. **Sau đó mới** chạy trên tập test, dùng đúng tham số và mô hình đã chọn.

Tập test không được dùng ở bất kỳ bước chọn lựa nào, nên kết quả test là ước lượng **trung thực** của độ chính xác khi dùng thật.

---

## 12. Cách đo sai số và kiểm định

### 12.1. Ba chỉ số sai số

Với n ngày, yᵢ là thực tế và ŷᵢ là dự báo:

```
MAPE = (100% / n) · Σ |ŷᵢ − yᵢ| / yᵢ          sai số phần trăm trung bình (chỉ số chính)
MAE  = (1 / n)    · Σ |ŷᵢ − yᵢ|               sai số trung bình, đơn vị MW
RMSE = √[(1 / n)  · Σ (ŷᵢ − yᵢ)²]             phạt nặng các ngày sai nhiều
```

**Ví dụ với hai ngày ở trên (mô hình Ensemble):**

| Ngày | y | ŷ | \|ŷ − y\| | \|ŷ − y\| / y |
|---|---|---|---|---|
| 24/06/2026 | 57 536,7 | 55 233,5 | 2 303,2 | 4,00% |
| 02/09/2026 | 37 835,0 | 39 506,7 | 1 671,7 | 4,42% |

```
MAPE = (4,00% + 4,42%) / 2 = 4,21%
MAE  = (2 303,2 + 1 671,7) / 2 = 1 987,5 MW
RMSE = √[(2 303,2² + 1 671,7²) / 2] = 2 012,4 MW
```

Hai ngày này đều khó (kỷ lục nắng nóng, ngày lễ). Trên toàn bộ 329 ngày test, MAPE là 2,12%.

### 12.2. Kiểm định Diebold–Mariano

Câu hỏi: mô hình tốt hơn baseline **thật sự**, hay chỉ do may mắn với năm test này?

```
dᵢ = |ŷᵢ(mô hình) − yᵢ| / yᵢ  −  |ŷᵢ(baseline) − yᵢ| / yᵢ      (chênh lệch sai số từng ngày)
DM = trung bình(d) / √(phương sai dài hạn của d / n)
```

- "Phương sai dài hạn" có tính đến việc sai số các ngày liền nhau tương quan với nhau (dự báo 2 bước, h = 2).
- Áp dụng hiệu chỉnh mẫu nhỏ của Harvey và cộng sự (1997), so với phân phối t với n − 1 bậc tự do.
- **DM < 0** và **p < 0,05**: mô hình chính xác hơn baseline một cách có ý nghĩa thống kê.

Kết quả: Pmax DM = −5,31; sản lượng DM = −5,69; cả hai p < 0,0001 (`Model.md` mục 7).

---

## 13. Khoảng dự báo (quantile)

Ngoài dự báo một con số, hai mô hình LightGBM phụ được huấn luyện để dự báo **phân vị 10%** và **phân vị 90%**, tạo thành khoảng P10–P90. Kỳ vọng: khoảng 80% số ngày, giá trị thực tế nằm trong khoảng này.

Mô hình phân vị dùng **hàm mất mát pinball** thay cho L1/L2:

```
L_τ(y, q) = τ · (y − q)        nếu y ≥ q
          = (1 − τ) · (q − y)  nếu y < q
```

Với τ = 0,9: dự báo thấp hơn thực tế bị phạt nặng gấp 9 lần dự báo cao hơn, nên mô hình đẩy q lên cao, sao cho chỉ khoảng 10% số ngày vượt q.

**Hạn chế đã biết:** trên tập test, khoảng P10–P90 chỉ chứa 64–66% số ngày, thay vì 80% (`Model.md` mục 8). Ví dụ 1 ở trên là một trường hợp thực tế nằm ngoài khoảng. Cần hiệu chỉnh (conformal prediction) trước khi sử dụng.
