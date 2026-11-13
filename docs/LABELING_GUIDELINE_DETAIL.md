# CẨM NANG HƯỚNG DẪN GÁN NHÃN DỮ LIỆU CHI TIẾT (STEP-BY-STEP ANNOTATION GUIDELINE)

> Đường dẫn lưu dữ liệu và quy trình bàn giao hiện tại được quy định tại
> [DATA_GUIDE.md](DATA_GUIDE.md). Xem [PROJECT_STRUCTURE.md](PROJECT_STRUCTURE.md)
> để biết vị trí mã nguồn sau refactor. Các đường dẫn Colab trong tài liệu này
> là ví dụ triển khai; cần tạo lại `data.yaml` với đường dẫn thực tế trên máy train.

## DỰ ÁN: HỆ THỐNG ĐẾM VÀ ĐO TỐC ĐỘ PHƯƠNG TIỆN GIAO THÔNG (ITS 2026)
**Mã tài liệu:** GUIDE-LABELING-ITS-2026  
**Phiên bản:** 2.1.0  
**Đối tượng áp dụng:** Toàn bộ thành viên nhóm gán nhãn dữ liệu, Kỹ sư AI & Trưởng nhóm QA/QC  
**Mục tiêu:** Chuẩn hóa 100% thao tác dán nhãn Bounding Box nhằm phục vụ huấn luyện mô hình YOLOv11, bám vết ByteTrack và thuật toán tính vận tốc qua ma trận biến đổi phối cảnh Homography.

---

## 📑 MỤC LỤC
1. [Tổng quan Quy trình Gán nhãn](#1-tổng-quan-quy-trình-gán-nhãn)
2. [Cài đặt & Thiết lập Dự án Label Studio Community](#2-cài-đặt--thiết-lập-dự-án-label-studio-community)
3. [Quy chuẩn 8 Nhóm Phương tiện Giao thông & Bảng Khử Nhầm lẫn](#3-quy-chuẩn-8-nhóm-phương-tiện-giao-thông--bảng-khử-nhầm-lẫn)
4. [Nguyên tắc Vàng khi Vẽ Bounding Box phục vụ Đo Tốc độ & Đếm xe](#4-nguyên-tắc-vàng-khi-vẽ-bounding-box-phục-vụ-đo-tốc-độ--đếm-xe)
5. [Hướng dẫn Xử lý các Kịch bản Khó (Che khuất, Đèn pha, Bóng xe)](#5-hướng-dẫn-xử-lý-các-kịch-bản-khó)
6. [Hệ thống Phím tắt & Kỹ thuật Tăng tốc độ Gán nhãn](#6-hệ-thống-phím-tắt--kỹ-thuật-tăng-tốc-độ-gán-nhãn)
7. [Quy trình Xuất dữ liệu Chuẩn YOLO & Kiểm duyệt Nghiệm thu (QA/QC)](#7-quy-trình-xuất-dữ-liệu-chuẩn-yolo--kiểm-duyệt-nghiệm-thu-qaqc)

---

## 1. TỔNG QUAN QUY TRÌNH GÁN NHÃN

Dữ liệu hình ảnh được thu thập tự động từ công cụ `collector_gui.py` hoặc `stream_capture_ffmpeg.py` (cứ mỗi 3 giây chụp 1 ảnh chất lượng cao vào các thư mục khung giờ `08h-09h`, `09h-10h`...).

```
[Ảnh từ collector_gui.py] ──► [Nạp vào Label Studio] ──► [Dán nhãn Bbox 8 lớp xe]
                                                                  │
                                      ┌───────────────────────────┘
                                      ▼
                      [Kiểm duyệt chéo QA/QC 10%]
                                      │
                                      ▼
                     [Export định dạng YOLO Format]
                     (images/ + labels/*.txt + data.yaml)
                                      │
                                      ▼
                      [Nạp lên Colab train YOLOv11]
```

---

## 2. CÀI ĐẶT & THIẾT LẬP DỰ ÁN LABEL STUDIO COMMUNITY

### Bước 2.1: Khởi động Label Studio trên máy tính
Mở Command Prompt hoặc PowerShell và chạy:
```bash
# 1. Kích hoạt môi trường (nếu có venv)
# 2. Cấu hình cho phép load ảnh trực tiếp từ ổ cứng nội bộ:
set LABEL_STUDIO_LOCAL_FILES_SERVING_ENABLED=true
set LABEL_STUDIO_LOCAL_FILES_DOCUMENT_ROOT=C:\Users\ngnsusinn\Documents\detect-plate-vehicle

# 3. Khởi chạy ứng dụng:
label-studio start
```
Trình duyệt sẽ tự động mở tại địa chỉ: `http://localhost:8080`.

---

### Bước 2.2: Tạo Dự án mới & Cấu hình Template
1. Nhấp **Create Project** $\rightarrow$ Đặt tên dự án (Ví dụ: `Vehicle_Dataset_Day_01_TV2`).
2. Chuyển sang tab **Labeling Setup** $\rightarrow$ Chọn **Custom template** (hoặc nút **Code**).
3. Xóa toàn bộ nội dung mẫu và dán đoạn XML chuẩn sau:

```xml
<View>
  <Image name="image" value="$image" zoom="true" zoomBy="1.5" rotateControl="true"/>
  <RectangleLabels name="label" toName="image" canRotate="false">
    <Label value="motorcycle" background="#FFA39E" hotkey="1"/>
    <Label value="car" background="#91CAFF" hotkey="2"/>
    <Label value="electric_bicycle" background="#FFD591" hotkey="3"/>
    <Label value="bicycle" background="#ADC6FF" hotkey="4"/>
    <Label value="bus" background="#D3ADF7" hotkey="5"/>
    <Label value="truck" background="#87E8DE" hotkey="6"/>
    <Label value="container_truck" background="#FFADD2" hotkey="7"/>
    <Label value="special_vehicle" background="#D9D9D9" hotkey="8"/>
  </RectangleLabels>
</View>
```
4. Bấm **Save** để lưu lại.

---

### Bước 2.3: Nạp ảnh vào Dự án (Import Data)
Có 2 cách nạp ảnh:
* **Cách 1 (Kéo thả trực tiếp):** Vào tab **Data Manager** $\rightarrow$ Bấm **Import** $\rightarrow$ Kéo toàn bộ ảnh trong thư mục khung giờ (ví dụ `2026-10-08_08h-09h`) thả vào giao diện.
* **Cách 2 (Local Storage - Khuyên dùng khi tập ảnh lớn):**
  * Vào **Settings** $\rightarrow$ **Cloud Storage** $\rightarrow$ **Add Source Storage**.
  * Chọn Storage Type: **Local Files**.
  * Nhập Absolute Local Path tới thư mục ảnh.
  * Tích chọn **Treat every bucket object as a source file** $\rightarrow$ Bấm **Sync Storage**.

---

## 3. QUY CHUẨN 8 NHÓM PHƯƠNG TIỆN GIAO THÔNG & BẢNG KHỬ NHẦM LẪN

Mỗi đối tượng phải được gán chính xác vào **1 trong 8 lớp** sau:

| Class ID | Label (Tên lớp) | Phím tắt | Phạm vi phương tiện thực tế | Dấu hiệu đặc trưng & Lưu ý |
| :---: | :--- | :---: | :--- | :--- |
| **0** | `motorcycle` | **`1`** | Xe máy, xe mô tô 2 bánh, 3 bánh, xe tay ga, xe số, phân khối lớn. | Có ống xả (pô), lốp dày, phuộc nhún lớn, có biển số sau. |
| **1** | `car` | **`2`** | Ô tô con (Sedan, Hatchback, SUV, CUV, MPV 7 chỗ, xe bán tải Pickup). | Thân xe du lịch, cabin liền mạch, chiều dài khoảng $4 - 5\text{m}$. |
| **2** | `electric_bicycle` | **`3`** | Xe đạp điện, xe máy điện mini (VinFast Feliz/Klara, Pega, xe điện học sinh). | Có bình ắc quy vuông dưới yên, bàn đạp phụ (nếu có), không có pô xả, khung sườn nhỏ. |
| **3** | `bicycle` | **`4`** | Xe đạp cơ thông thường, xe đạp địa hình, xe đạp mini, xe cào cào. | Khung kim loại thanh mảnh, dùng bàn đạp chân, không có bình điện/động cơ. |
| **4** | `bus` | **`5`** | Xe buýt nội đô, xe khách 16 chỗ (Ford Transit/Solati), xe 29-45 chỗ, xe giường nằm. | Thân xe dạng khối hộp cao, nhiều hàng ghế và cửa kính hai bên. |
| **5** | `truck` | **`6`** | Xe tải nhẹ, xe tải ben, xe tải thùng kín, xe bồn, xe chở hàng. | Có cabin riêng phía trước và khoang chở hàng riêng biệt phía sau. |
| **6** | `container_truck`| **`7`** | Xe đầu kéo kéo rơ-moóc, xe container 20ft/40ft. | Chiều dài rất lớn ($> 12\text{m}$), đầu kéo tách rời sơ-mi rơ-moóc. |
| **7** | `special_vehicle`| **`8`** | Xe ba gác máy, xe xích lô, xe thương binh, xe cứu thương, xe cứu hỏa, xe cẩu. | Phương tiện chuyên dụng hoặc xe tự chế 3 bánh chở hàng cồng kềnh. |

---

### Bảng Phân biệt các cặp phương tiện DỄ NHẦM LẪN NHẤT:

```
[XE BÁN TẢI (PICKUP: Ranger/Hilux)] ──► Gán nhãn: "car"  (KHÔNG gán là truck)
[XE VAN 16 CHỖ (Transit/Solati)]    ──► Gán nhãn: "bus"  (KHÔNG gán là car)
[XE MÁY ĐIỆN VINFAST TO (Theon/Evo)]──► Gán nhãn: "motorcycle" (Kích thước tương đương xe máy)
[XE ĐẠP ĐIỆN HỌC SINH (Ắc quy nhỏ)] ──► Gán nhãn: "electric_bicycle"
```

1. **Xe bán tải (Ford Ranger, Toyota Hilux, Mitsubishi Triton):**
   * *Quy ước:* Luôn gán là **`car`** (vì kích thước và vận tốc lưu thông tương tự ô tô con).
2. **Xe khách 16 chỗ (Ford Transit, Hyundai Solati):**
   * *Quy ước:* Luôn gán là **`bus`** (thuộc nhóm phương tiện vận tải hành khách).
3. **Xe máy điện to vs. Xe đạp điện nhỏ:**
   * Các dòng xe máy điện kích thước lớn như VinFast Theon, Feliz, Klara: gán là **`motorcycle`**.
   * Các dòng xe đạp điện nhỏ có bàn đạp phụ của học sinh (Pega, Cap A, Nijia): gán là **`electric_bicycle`**.
4. **Xe tải nhỏ chở hàng (Suzuki 500kg, Kia K200):**
   * Có thùng hàng riêng phía sau $\rightarrow$ Luôn gán là **`truck`**.

---

## 4. NGUYÊN TẮC VÀNG KHI VẼ BOUNDING BOX PHỤC VỤ ĐO TỐC ĐỘ & ĐẾM XE

Thuật toán đo tốc độ hoạt động bằng cách lấy điểm chính giữa mép đáy của Bounding Box:
$$P_{\text{anchor}} = \left( \frac{x_1 + x_2}{2}, y_2 \right)$$
để ánh xạ xuống mặt đất qua ma trận Homography. Do đó, độ chính xác của mép đáy box quyết định trực tiếp tới sai số đo tốc độ!

---

### Quy tắc 1: Cạnh đáy Bounding Box PHẢI CHẠM ĐÚNG VỊ TRÍ BÁNH XE TIẾP ĐẤT
* Bounding Box phải bao trọn từ điểm cao nhất của thân xe xuống đến **mép dưới cùng của lốp xe chạm mặt đường**.
* Không được để đáy box bị lơ lửng lưng chừng thân xe (sẽ làm hệ thống tưởng xe đang ở vị trí xa hơn thực tế).

---

### Quy tắc 2: TUYỆT ĐỐI KHÔNG KÉO TRÙM BÓNG ĐỔ (SHADOW INDEPENDENCE)
* Vào ban ngày trời nắng, phương tiện sẽ tạo ra vệt bóng đổ đen dài trên mặt đường.
* **Hành vi sai:** Kéo đáy box trùm ra hết bóng đen $\rightarrow$ Sai lệch vị trí thực tế tới $1.5 - 3\text{ mét}$, làm sai số đo vận tốc lên tới $40\%$.
* **Hành vi đúng:** Dừng cạnh đáy Bounding Box chính xác tại mép tiếp xúc của lốp xe cao su với mặt đường, **bỏ qua hoàn toàn bóng đổ**.

```
    [SAI - Kéo bao trùm bóng đổ]                    [ĐÚNG - Ôm sát lốp xe tiếp đất]
    
         ┌────────────┐                                  ┌────────────┐
         │   Ô TÔ     │                                  │   Ô TÔ     │
         │  O      O  │                                  │  O      O  │
         │░░░░░░░░░░░░│ ◄── BÓNG ĐỔ                      └────────────┘ ◄── Mép bánh chạm đất
         └────────────┘                                   ░░░░░░░░░░░░  (Bỏ qua bóng đổ)
```

---

### Quy tắc 3: Phương tiện 2 bánh PHẢI BAO TRÙM CẢ NGƯỜI ĐIỀU KHIỂN
* Đối với `motorcycle`, `electric_bicycle`, `bicycle`:
* Khung chữ nhật phải vẽ từ **đỉnh mũ bảo hiểm / đầu người ngồi trên xe** kéo xuống tận **mép đáy lốp xe chạm đất**.
* Bao trùm cả người lái, người ngồi sau và toàn bộ thân xe thành **một khối Bounding Box duy nhất**. Không tách riêng người và xe.

```
    [SAI - Chỉ vẽ thân xe, bỏ người]                 [ĐÚNG - Bao trọn cả người + xe]
    
             (Đầu người)                                      ┌──────────┐ ◄── Mũ bảo hiểm
           ┌──────────────┐                                   │ (Người)  │
           │   (Xe máy)   │                                   │ ┌──────┐ │
           └──────────────┘ ◄── Mép bánh                      │ │ (Xe) │ │
                                                              └─┴──────┴─┘ ◄── Mép bánh
```

---

### Quy tắc 4: Xe chở hàng cồng kềnh (Hàng hóa gắn liền với xe)
* Nếu xe máy, xe ba gác, xe tải chở hàng hóa cồng kềnh phía sau (sọt hàng, bao tải, thùng xốp):
* **Vẽ Bounding Box bao trùm cả khối hàng hóa đó** nếu hàng hóa gắn liền và di chuyển cùng phương tiện.

---

## 5. HƯỚNG DẪN XỬ LÝ CÁC KỊCH BẢN KHÓ

### 5.1. Xe bị che khuất (Occlusion Handling)
* **Quy tắc 30% - 70%:**
  * Nếu xe bị xe khác che khuất dưới $70\%$ (tức là **vẫn nhìn thấy được $\ge 30\%$ thân xe**): **VẪN GÁN NHÃN**. Vẽ box ôm trọn phần thân xe còn nhìn thấy được.
  * Nếu xe bị che khuất quá nặng ($> 70\%$, chỉ thò ra một góc gương hoặc chóp đuôi xe): **BỎ QUA KHÔNG GÁN** để tránh làm mô hình học nhiễu.

---

### 5.2. Xe ở quá xa chân trời (Small Objects / Truncation)
* Các phương tiện ở xa tít chân trời có kích thước quá bé (chiều cao bounding box $< 20\text{ pixels}$):
* **BỎ QUA KHÔNG GÁN**, vì ở khoảng cách đó camera không đủ độ phân giải để đo tốc độ hoặc đếm vạch.

---

### 5.3. Ban đêm có đèn pha xe rọi ngược (Headlight Glare)
* Ban đêm, đèn pha ô tô/xe máy rọi thẳng vào camera tạo ra vệt sáng chói lóa (Glare), làm mờ phần mặt ca-lăng và đầu xe.
* **Cách xử lý:** 
  1. Dùng thanh công cụ **Brightness / Contrast** trên Label Studio để hạ độ sáng ảnh xuống.
  2. Căn cứ vào đường viền kính lái, nóc xe và vệt sáng phản chiếu bánh xe trên mặt đường để xác định đúng khung xe và mép đáy tiếp đất.

---

## 6. HỆ THỐNG PHÍM TẮT & KỸ THUẬT TĂNG TỐC ĐỘ GÁN NHÃN

Sử dụng phím tắt thành thạo sẽ giúp tăng tốc độ gán nhãn lên **gấp 3 đến 5 lần**:

| Phím tắt | Thao tác | Mô tả chi tiết |
| :---: | :--- | :--- |
| **`1`** | Chọn nhãn `motorcycle` | Kích hoạt vẽ khung xe máy |
| **`2`** | Chọn nhãn `car` | Kích hoạt vẽ khung ô tô con |
| **`3`** | Chọn nhãn `electric_bicycle` | Kích hoạt vẽ xe đạp điện |
| **`4`** | Chọn nhãn `bicycle` | Kích hoạt vẽ xe đạp |
| **`5`** | Chọn nhãn `bus` | Kích hoạt vẽ xe khách/xe buýt |
| **`6`** | Chọn nhãn `truck` | Kích hoạt vẽ xe tải |
| **`7`** | Chọn nhãn `container_truck`| Kích hoạt vẽ xe container |
| **`8`** | Chọn nhãn `special_vehicle`| Kích hoạt vẽ xe chuyên dụng |
| **`Ctrl + Enter`** | **Submit / Update** | Lưu nhãn của ảnh hiện tại và chuyển sang ảnh kế tiếp |
| **`U`** | Unselect | Hủy chọn box đang chỉnh sửa |
| **`Del` / `Backspace`** | Xóa Box | Xóa bounding box bị vẽ lỗi |
| **`Cuộn chuột`** | Zoom In / Out | Phóng to vùng xe ở xa để vẽ chuẩn xác |
| **`Giữ Chuột phải`** | Pan Image | Kéo di chuyển vùng quan sát trên ảnh |

---

### 💡 Mẹo tăng tốc độ gán nhãn (Pro-Tips):
1. **Gán theo từng loại xe (Batch by Class):** Thay vì chuyển đổi liên tục giữa các phím số, bạn bấm phím `1` (xe máy) và kéo toàn bộ xe máy trong ảnh trước, sau đó bấm phím `2` (ô tô) kéo hết ô tô. Cách này giúp mắt và tay phản xạ nhanh hơn rất nhiều.
2. **Kéo từ góc trên-trái xuống góc dưới-phải:** Luôn kéo chuột kết thúc ở mép dưới bánh xe để căn chỉnh đáy box chuẩn xác nhất.
3. **Bật chế độ Auto-Save:** Trong Settings của Label Studio, bật tự động lưu khi bấm submit.

---

## 7. QUY TRÌNH XUẤT DỮ LIỆU CHUẨN YOLO & KIỂM DUYỆT NGHIỆM THU (QA/QC)

### 7.1. Bảng Checklist Tự Kiểm tra Trước khi Nộp Gói Dữ liệu
Trước khi đóng gói nộp cho Trưởng nhóm QA/QC, mỗi thành viên phải kiểm tra 5 tiêu chí sau:

- [ ] **1. Đáy box:** Đáy Bounding Box có chạm mép tiếp xúc lốp xe và mặt đường không? Có bị hụt lơ lửng không?
- [ ] **2. Bóng xe:** Có box nào bị kéo trùm vệt bóng đen dưới lòng đường không?
- [ ] **3. Xe 2 bánh:** Có bao trọn cả đầu người lái và mũ bảo hiểm không?
- [ ] **4. Lớp nhãn:** Xe bán tải đã gán là `car` chưa? Xe 16 chỗ đã gán là `bus` chưa?
- [ ] **5. Số lượng:** Đã dán đủ số lượng khung hình được giao trong gói chưa?

---

### 7.2. Các bước Xuất dữ liệu Định dạng YOLO từ Label Studio
1. Tại màn hình dự án Label Studio, bấm nút **Export** ở góc trên bên phải.
2. Chọn định dạng: **YOLO** (Label Studio sẽ tự động tạo tệp nén `.zip`).
3. Giải nén tệp `.zip`, bạn sẽ thấy cấu trúc:
   ```text
   project_export/
   ├── images/       # Chứa các tệp ảnh .jpg
   ├── labels/       # Chứa các tệp nhãn .txt tương ứng (class_id x y w h)
   ├── classes.txt   # Danh sách tên 8 lớp (từ 0 đến 7)
   └── notes.json
   ```

### 7.3. Cấu hình tệp `data.yaml` chuẩn bị huấn luyện YOLOv11
Tạo tệp `data.yaml` đặt trong thư mục gốc dataset:
```yaml
path: /path/to/dataset
train: images/train
val: images/val
test: images/test

names:
  0: motorcycle
  1: car
  2: electric_bicycle
  3: bicycle
  4: bus
  5: truck
  6: container_truck
  7: special_vehicle
```

---
*Tài liệu hướng dẫn kỹ thuật này là quy chuẩn nghiệm thu chính thức của Nhóm Dự án ITS 2026.*
