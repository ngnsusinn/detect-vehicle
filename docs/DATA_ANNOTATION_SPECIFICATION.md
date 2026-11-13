# ĐẶC TẢ YÊU CẦU & TIÊU CHUẨN DỮ LIỆU GÁN NHÃN (DATA ANNOTATION SPECIFICATION)

> Đường dẫn lưu dữ liệu và quy trình bàn giao hiện tại được quy định tại
> [DATA_GUIDE.md](DATA_GUIDE.md). Xem [PROJECT_STRUCTURE.md](PROJECT_STRUCTURE.md)
> để biết vị trí mã nguồn sau refactor. Các đường dẫn Colab trong tài liệu này
> là ví dụ triển khai; cần tạo lại `data.yaml` với đường dẫn thực tế trên máy train.

## HỆ THỐNG ĐẾM VÀ ĐO TỐC ĐỘ PHƯƠNG TIỆN GIAO THÔNG TỪ LUỒNG VIDEO STREAMING
**Mã tài liệu:** SPEC-DATA-ANNOTATION-ITS-2026  
**Phiên bản:** 2.0.0  
**Tác giả:** Đội ngũ AI & Data Quality Assurance (Data QA/QC Team)  
**Mục đích:** Quy chuẩn hóa toàn bộ tiêu chuẩn dữ liệu ảnh và quy tắc dán nhãn phục vụ huấn luyện mô hình YOLOv11, ByteTrack và Đo tốc độ Homography.

---

## 1. TỔNG QUAN YÊU CẦU DỮ LIỆU ĐẦU VÀO

Để hệ thống đo tốc độ và đếm xe đạt được các chỉ số KPI cam kết (sai số đo tốc độ $\le \pm 3 - 5\text{ km/h}$, tỷ lệ đếm đúng $\ge 97.5\%$), dữ liệu ảnh đưa vào gán nhãn phải thỏa mãn các tiêu chuẩn khắt khe về **hình học không gian**, **quang học** và **tính đại diện thực tế**.

```
[Camera Stream Góc Xiên 30°-50°] ──► [Chụp mỗi 3.0s + Lọc Nét Laplacian] ──► [Lưu 100% Ảnh Chung Thư Mục]
                                                                                            │
                                     ┌──────────────────────────────────────────────────────┘
                                     ▼
                   [TIÊU CHUẨN BOUNDING BOX CHUẨN XÁC KHI DÁN NHÃN]
                   - Điểm đáy chạm chính xác mép tiếp đất của lốp xe
                   - Tuyệt đối tách rời bóng đổ (Shadow Independence)
                   - Bao trọn người lái đối với phương tiện 2 bánh
                   - Phân loại 8 nhóm phương tiện & trạng thái xe do người dán nhãn thực hiện
```

### 1.1. Chu kỳ Chụp & Tần suất Lấy mẫu Ảnh Đầu vào
- **Tần suất chuẩn hóa: Đúng mỗi $3.0\text{ giây}$ chụp $1\text{ ảnh}$ ($0.33\text{ fps}$).**
- **Cơ sở khoa học:**
  - Vận tốc lưu thông trung bình trong đô thị: $30 - 50\text{ km/h}$ ($\approx 8 - 14\text{ m/s}$).
  - Tầm quan sát của camera tĩnh: khoảng $25 - 40\text{m}$.
  - Thời gian một phương tiện đi qua khung hình: $2.5 - 4.0\text{ giây}$.
  - Do đó, chu kỳ **3.0s** đảm bảo mỗi phương tiện chỉ xuất hiện $1 - 2$ lần ở các cự ly khác nhau (xa và gần), dòng xe được đổi mới liên tục, tránh hiện tượng mô hình học vẹt (overfitting).

### 1.2. Nguyên tắc Lưu trữ Toàn bộ Ảnh chung 1 Thư mục
- **Lưu toàn bộ $100\%$ ảnh vào chung 1 thư mục theo khung giờ:** Không lọc bỏ và không chia tách thư mục riêng cho xe dừng hay xe chạy.
- **Không phân loại trạng thái ở bước chụp ảnh:** Công cụ chụp ảnh tập trung tối đa vào việc lấy khung hình sắc nét nhất (chống nhòe motion blur bằng Laplacian Variance) và ghi đĩa tốc độ cao.
- **Phân loại do khâu Dán nhãn & Huấn luyện đảm nhiệm:** Mọi công tác phân loại (nhận diện 8 loại phương tiện, xác định trạng thái xe đang chạy hay đang dừng chờ đèn đỏ/ùn tắc) sẽ do thành viên dán nhãn trực tiếp trên **Label Studio Community** và mô hình học sâu đảm nhiệm.

### 1.3. Quy ước Đặt tên Tệp Ảnh Đầu vào Đồng nhất
```text
<Tên_Camera>_<YYYYMMDD>_<HHMMSS>_<MiliGiay>_<SốThứTự>.jpg

Ví dụ:
cam_lane01_20261008_081530_125_000142.jpg
cam_lane01_20261008_081533_130_000143.jpg  <-- Cách nhau 3.0s, lưu tuần tự chung 1 folder
```

---

## 2. NĂM ĐẶC ĐIỂM KỸ THUẬT CỐT LÕI CỦA DỮ LIỆU GÁN NHÃN

### 2.1. Đặc điểm về Điểm Tiếp xúc Bánh xe & Góc nhìn Camera (Tối quan trọng cho Đo tốc độ)
Trong bài toán đo tốc độ bằng thị giác máy tính, vận tốc được tính bằng cách ánh xạ tọa độ điểm tiếp đất của bánh xe qua ma trận phối cảnh **Homography ($H$)**:
- **Góc nhìn Camera (Perspective View):**
  - Camera phải đặt ở góc nhìn xiên từ trên cao xuống mặt đường với góc nghiêng khuyến nghị từ **$30^\circ$ đến $50^\circ$** (thường lắp trên cột đèn giao thông cao $5 - 8\text{m}$ hoặc giá long môn).
  - Góc nhìn này vừa bảo đảm quan sát rõ thân xe để phân loại, vừa nhìn thấy rõ mặt đường và điểm tiếp xúc giữa bánh xe với mặt đất.
- **Rõ mép đáy bánh xe tiếp đất:**
  - Ảnh phải nhìn rõ được vị trí lốp xe chạm mặt đường. Tránh các góc quay quá thấp ngang tầm mắt (eye-level) vì xe phía trước sẽ che khuất toàn bộ bánh xe của phương tiện phía sau.
- **Tách bạch hoàn toàn với bóng đổ (Shadow Independence):**
  - Ảnh chụp ban ngày cần có độ tương phản đủ để phân biệt rõ đâu là **lốp cao su thực tế** và đâu là **vệt bóng đen đổ dài trên mặt đường**.
  - *Cảnh báo kỹ thuật:* Nếu gán nhãn bao trùm cả bóng xe, điểm neo tọa độ sẽ bị dịch lệch từ $1 - 2\text{m}$, dẫn đến sai số tính toán vận tốc lên tới $30\% - 50\%$.

---

### 2.2. Đặc điểm về Độ Sắc nét & Chống Nhòe Chuyển động (Motion Blur)
Phương tiện tham gia giao thông thường di chuyển với vận tốc từ $30 - 80\text{ km/h}$:
- **Không bị vỡ hạt nén (No Macroblock Compression Artifacts):**
  - Khung hình trích xuất từ stream phải là I-Frame (Keyframe) hoặc khung hình có bitrate đủ cao, không bị nén vỡ khối vuông do suy giảm băng thông mạng.
- **Được tinh lọc qua bộ chấm điểm sắc nét (Laplacian Variance):**
  - Khung hình chọn gán nhãn phải đạt điểm sắc nét cao:
    $$\text{Score}_{\text{sharpness}} = \text{Var}(\nabla^2 I) > 300$$
  - Hạn chế tối đa hiện tượng vệt mờ kéo dài (motion blur streak) khi phương tiện chạy nhanh.
- **Độ phân giải tiêu chuẩn:**
  - Bắt buộc đạt độ phân giải **Full HD ($1920 \times 1080$)** hoặc tối thiểu **HD ($1280 \times 720$)**.
  - Đảm bảo khi phương tiện ở cự ly $25 - 35\text{m}$, các chi tiết phân loại (bình ắc quy xe điện, ống xả xe máy, biển số) vẫn hiển thị sắc nét.

---

### 2.3. Cân bằng Cơ cấu Phương tiện Giao thông Việt Nam (Class Distribution)
Giao thông tại Việt Nam có mật độ xe máy áp đảo, nếu lấy mẫu ngẫu nhiên sẽ dẫn đến hiện tượng mất cân bằng dữ liệu nghiêm trọng:
- **Chủ động cân bằng mẫu:**
  - Xe máy (`motorcycle`) chiếm $> 80\%$ thực tế ngoài đường. Trong tập dữ liệu gán nhãn, cần chủ động chọn lọc thêm các khung hình có sự xuất hiện của các lớp ít gặp: `truck` (xe tải), `bus` (xe khách/buýt), `container_truck` (xe container), `special_vehicle` (xe ba gác, cứu thương).
- **Đủ chi tiết để phân biệt các cặp phương tiện dễ nhầm lẫn:**
  - **Xe máy (`motorcycle`) vs. Xe đạp điện (`electric_bicycle`):**
    - *Xe máy:* Có ống pô xả, lốp dày, phuộc nhún lớn, bình xăng/cốp lớn.
    - *Xe đạp điện:* Có khối bình ắc quy vuông dưới yên xe, có bàn đạp phụ, khung sườn thanh mảnh.
  - **Ô tô con (`car`) vs. Xe tải nhỏ (`truck`):**
    - Xe bán tải (Pickup / Ranger / Hilux) hoặc SUV 7 chỗ: Xếp vào nhóm `car`.
    - Xe có thùng chở hàng riêng biệt phía sau cabin: Xếp vào nhóm `truck`.

---

### 2.4. Đa dạng Điều kiện Chiếu sáng & Môi trường (60% Ngày - 40% Đêm)
Mô hình vận hành liên tục 24/7, do đó tập dữ liệu phải phản ánh đúng các biến đổi quang học trong ngày:

| Điều kiện môi trường | Tỷ lệ dữ liệu | Số lượng Frames | Đặc điểm nhận dạng & Lưu ý khi gán |
| :--- | :---: | :---: | :--- |
| **Ban ngày tiêu chuẩn (Daytime)** | $\mathbf{60\%}$ | **3.600 frames** | Ánh sáng tự nhiên, mật độ xe đông đúc, nắng gắt tạo bóng đen đậm dưới gầm xe. |
| **Ban đêm có đèn đường & đèn pha (Nighttime)** | $\mathbf{40\%}$ | **2.400 frames** | Thiếu sáng; xe rọi đèn pha chói (Headlight Glare) xóa mờ vùng đầu xe; ánh sáng đèn cao áp vàng/LED trắng hỗn hợp. |

---

### 2.5. Tiêu chuẩn Kỹ thuật Vẽ Bounding Box trên Label Studio

Khi gán nhãn trên giao diện **Label Studio Community**, người thực hiện bắt buộc phải tuân theo 4 quy tắc hình học:

```
        [QUY TẮC 1: BỎ QUA BÓNG ĐỔ]                    [QUY TẮC 2: XE 2 BÁNH ÔM CẢ NGƯỜI]
    
        [SAI: Kéo trùm bóng]   [ĐÚNG: Ôm sát bánh]             [SAI: Bỏ người]     [ĐÚNG: Ôm cả người+xe]
             ┌────────────┐        ┌────────────┐                                     ┌──────────┐ ◄── Đầu người
             │   Ô TÔ     │        │   Ô TÔ     │                                     │  (Người) │
             │  O      O  │        │  O      O  │                  ┌──────────┐       │ ┌──────┐ │
             │░░░░░░░░░░░░│        └────────────┘ ◄── Mép bánh     │  (Xe)    │       │ │(Xe)  │ │
             └────────────┘         ░░░░░░░░░░░░ (Bóng đổ)         └──────────┘       └─┴──────┴─┘ ◄── Mép bánh
```

1. **Quy tắc 1 - Ôm trọn phương tiện từ điểm cao nhất đến mép đáy bánh xe:**
   - Cạnh dưới cùng của Bounding Box phải tiếp xúc chính xác tại điểm lốp xe chạm mặt đường.
   - Tuyệt đối không kéo Bounding Box trùm ra vệt bóng đổ của xe.
2. **Quy tắc 2 - Phương tiện 2 bánh bắt buộc bao trùm cả người điều khiển:**
   - Đối với `motorcycle`, `electric_bicycle`, `bicycle`: Khung Bounding Box phải bao trùm từ **mũ bảo hiểm / đỉnh đầu người lái** xuống đến **mép đáy lốp xe**.
   - Không gán riêng rẽ người và xe thành 2 box khác nhau.
3. **Quy tắc 3 - Xử lý che khuất (Occlusion Handling):**
   - Xe bị che khuất dưới $70\%$ (vẫn nhìn thấy $\ge 30\%$ thân xe): **Vẫn gán nhãn**, bao trùm toàn bộ diện tích xe nhìn thấy được.
   - Xe bị che khuất quá nặng ($> 70\%$, chỉ thấy một phần gương chiếu hậu hoặc góc đuôi xe): **Bỏ qua không gán**.
4. **Quy tắc 4 - Ngưỡng kích thước tối thiểu (Min Object Size):**
   - Các xe ở quá xa cuối chân trời có chiều cao $< 20\text{ pixels}$: **Bỏ qua không gán** vì không đủ độ phân giải cho bài toán bám vết và đo tốc độ.

---

## 3. BẢNG CHECKLIST KIỂM DUYỆT CHẤT LƯỢNG (QA/QC CHECKLIST)

Mỗi gói dữ liệu trước khi nghiệm thu phải được kiểm tra chéo theo bảng đối soát sau:

| Hạng mục kiểm tra | Tiêu chuẩn ĐẠT (PASS) | Lỗi vi phạm PHẢI SỬA (FAIL) |
| :--- | :--- | :--- |
| **Vị trí đáy box** | Cạnh đáy nằm sát mép tiếp đất của lốp xe | Cạnh đáy bị hụt lơ lửng trên thân xe hoặc kéo xuống lòng đường |
| **Bóng đổ (Shadow)** | Toàn bộ bóng đen nằm ngoài Bounding Box | Kéo Bounding Box bao trùm cả bóng xe |
| **Phương tiện 2 bánh** | Bao trọn cả người ngồi trên xe và thân xe | Chỉ vẽ khung bao thân xe, bỏ quên đầu/thân người lái |
| **Phân biệt lớp** | Phân loại chính xác 8 nhóm phương tiện | Nhầm lẫn xe đạp điện thành xe máy, xe tải nhỏ thành ô tô con |
| **Độ nhòe (Blur)** | Xe có đường viền rõ nét, nhận dạng được loại | Ảnh xe bị vệt nhòe kéo dài do chuyển động quá nhanh |
| **Xe che khuất** | Bỏ qua các xe bị che khuất $> 70\%$ | Gán nhãn các mảnh xe quá nhỏ gây nhiễu cho mô hình |

---

## 4. HƯỚNG DẪN ĐÓNG GÓI & CẤU TRÚC TẬP DỮ LIỆU ĐẦU RA

Sau khi xuất dữ liệu từ Label Studio theo định dạng **YOLO**:

```text
dataset_speed_counting_master/
├── data.yaml                     # File cấu hình đường dẫn và 8 lớp
├── classes.txt                   # Danh sách tên 8 lớp theo đúng thứ tự 0 - 7
├── train/
│   ├── images/                   # 70% dữ liệu huấn luyện
│   └── labels/                   # Tệp nhãn .txt tương ứng (class_id x y w h)
├── val/
│   ├── images/                   # 20% dữ liệu đánh giá
│   └── labels/
└── test/
    ├── images/                   # 10% dữ liệu kiểm thử độc lập
    └── labels/
```

### Nội dung chuẩn tệp `classes.txt`:
```text
motorcycle
car
electric_bicycle
bicycle
bus
truck
container_truck
special_vehicle
```

---
*Tài liệu đặc tả chất lượng dữ liệu gán nhãn thuộc Bộ hồ sơ kỹ thuật Dự án ITS 2026.*
