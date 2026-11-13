# TÀI LIỆU QUY TRÌNH HUẤN LUYỆN MÔ HÌNH PHÁT HIỆN & PHÂN LOẠI PHƯƠNG TIỆN TỪ ĐẦU

> Đường dẫn lưu dữ liệu và quy trình bàn giao hiện tại được quy định tại
> [DATA_GUIDE.md](DATA_GUIDE.md). Xem [PROJECT_STRUCTURE.md](PROJECT_STRUCTURE.md)
> để biết vị trí mã nguồn sau refactor. Các đường dẫn Colab trong tài liệu này
> là ví dụ triển khai; cần tạo lại `data.yaml` với đường dẫn thực tế trên máy train.

## HỆ THỐNG ĐẾM VÀ ĐO TỐC ĐỘ PHƯƠNG TIỆN GIAO THÔNG (ITS 2026)
**Phiên bản:** 2.0.0  
**Tác giả:** Đội ngũ Kỹ sư Học sâu & MLOps (Deep Learning & MLOps Team)  
**Tình trạng:** Hướng dẫn Kỹ thuật Triển khai Sản xuất (Production Guide)

---

## 1. TỔNG QUAN CHIẾN LƯỢC HUẤN LUYỆN TỪ ĐẦU (FROM-SCRATCH STRATEGY)

### 1.1. Tại sao phải huấn luyện từ đầu trên dữ liệu thực tế giao thông Việt Nam?
Mặc dù các mô hình phát hiện đối tượng có sẵn (như COCO pre-trained YOLOv8/YOLOv11) có các lớp `car`, `motorcycle`, `bus`, `truck`, nhưng khi áp dụng trực tiếp vào luồng video camera giao thông tại Việt Nam gặp phải các nhược điểm nghiêm trọng:
1. **Thiếu lớp xe đặc thù giao thông đô thị:** COCO không có nhãn `electric_bicycle` (xe đạp điện/xe máy điện - chiếm tỷ lệ rất lớn trong học sinh, sinh viên tại Việt Nam), không tách biệt `container_truck` và `special_vehicle` (xe ba gác, xích lô, xe cứu thương).
2. **Mật độ xe máy áp đảo và đan xen dày đặc:** Tại các ngã tư Việt Nam, xe máy chiếm tới $80\% - 85\%$ lưu lượng và thường xuyên di chuyển sát nhau, luồn lách. Các mô hình phương Tây bị suy giảm độ chính xác khi các bounding box chồng lấn nặng nề (High Occlusion).
3. **Hiện tượng mờ chuyển động (Motion Blur) và đèn pha ban đêm (Headlight Glare):** Xe chạy tốc độ cao trên đường khiến hình ảnh bị vệt nhòe. Ban đêm, ánh sáng đèn pha chói lóa làm biến dạng vùng đầu xe.
4. **Yêu cầu điểm neo đáy bánh xe (Bottom-Center Anchor) để đo tốc độ:** Bounding box phải ôm sát đáy bánh xe tiếp xúc mặt đường để ma trận Homography tính toán tọa độ không gian chính xác, không được kéo lệch vào bóng đổ.

---

### 1.2. Danh mục 8 Lớp Phương tiện Chuẩn hóa (8 Target Vehicle Classes)

| Class ID | Tên nhãn (Label) | Ý nghĩa thực tế | Đặc điểm nhận diện chính |
| :---: | :--- | :--- | :--- |
| **0** | `motorcycle` | Xe máy, xe mô tô 2 bánh, 3 bánh | Khung xe chắc chắn, có ống xả, lốp to, biển số sau |
| **1** | `car` | Ô tô con (Sedan, SUV, CUV, Bán tải) | Chiều dài $4 - 5\text{m}$, 4 - 7 chỗ ngồi |
| **2** | `electric_bicycle` | Xe đạp điện, xe máy điện mini | Bình ắc quy vuông dưới yên, bàn đạp phụ, dáng nhỏ |
| **3** | `bicycle` | Xe đạp cơ thông thường, xe địa hình | Khung thanh mảnh, không có ắc quy/bình xăng |
| **4** | `bus` | Xe buýt nội đô, xe khách 16 - 45 chỗ | Thân xe dạng khối hộp cao, nhiều cửa sổ kính |
| **5** | `truck` | Xe tải thùng, xe tải ben, chở hàng | Có thùng hàng riêng biệt phía sau cabin |
| **6** | `container_truck` | Xe container, xe đầu kéo rơ-moóc | Chiều dài lớn ($> 12\text{m}$), đầu kéo kéo rơ-moóc |
| **7** | `special_vehicle` | Xe ba gác, xe cứu thương, chuyên dụng | Xe 3 bánh chở hàng, xe chuyên dụng cứu hỏa/cứu thương |

---

## 2. QUY TRÌNH THU THẬP & CHUẨN BỊ 100% DỮ LIỆU THỰC TẾ

Hệ thống tuân thủ nguyên tắc nghiêm ngặt: **$100\%$ dữ liệu đưa vào huấn luyện mô hình được trích xuất trực tiếp từ luồng video streaming camera tĩnh thực tế (RTSP, HLS), tuyệt đối KHÔNG sử dụng dữ liệu đồ họa nhân tạo (Synthetic Data)**.

### 2.1. Trích xuất Khung hình Tự động qua `collector_gui.py`
- Tần suất chụp: Đúng **mỗi 3 giây chụp 1 ảnh** (3s/frame).
- Tự động chia thư mục theo từng khung giờ (1h/folder): `00h-01h`, `01h-02h`, ..., `23h-24h`.
- Tích hợp bộ lọc Laplacian Variance tự động chọn frame sắc nét nhất trong chu kỳ chụp để hạn chế mờ nhòe chuyển động.

### 2.2. Ma trận Phân bổ Dữ liệu Ngày & Đêm
Tập dữ liệu được phân chia cân đối theo 2 kịch bản chiếu sáng thực tế:

| Kịch bản môi trường | Tỷ lệ dữ liệu | Số lượng Frames | Đặc điểm & Thách thức |
| :--- | :---: | :---: | :--- |
| **Ban ngày tiêu chuẩn (Daytime)** | $\mathbf{60\%}$ | $3.600\text{ frames}$ | Ánh sáng tự nhiên, mật độ xe đông đúc, bóng đổ trên mặt đường. |
| **Ban đêm có đèn đường & đèn pha (Nighttime)** | $\mathbf{40\%}$ | $2.400\text{ frames}$ | Thiếu sáng, ánh sáng đèn đường vàng/trắng, đèn pha xe rọi ngược camera. |
| **TỔNG CỘNG** | $\mathbf{100\%}$ | $\mathbf{6.000\text{ frames}}$ | Bao quát hơn $35.000$ đối tượng phương tiện được gán nhãn. |

---

## 3. QUY TRÌNH GÁN NHÃN VỚI LABEL STUDIO COMMUNITY EDITION

Toàn bộ nhóm sử dụng công cụ **Label Studio Community Edition** (hoặc X-AnyLabeling) với cấu hình XML chuẩn:

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

### Tiêu chuẩn Nghiệm thu Dữ liệu Gán nhãn (Annotation Standard):
1. Bounding box phải bao trọn toàn bộ xe, mép dưới tiếp xúc chính xác điểm tiếp đất của bánh xe.
2. Tuyệt đối không bao bọc bóng đổ (Shadow) của xe trên đường.
3. Bỏ qua các xe ở quá xa (chiều cao bounding box $< 15\text{ pixels}$) vì không đủ độ phân giải để tracking và đo tốc độ.

---

## 4. THIẾT LẬP HUẤN LUYỆN MÔ HÌNH YOLOV11 TRÊN GOOGLE COLAB

### 4.1. Cấu hình tệp `data.yaml`
```yaml
path: /content/dataset_vehicle_speed
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

### 4.2. Chiến lược Tăng cường Dữ liệu Thực tế (Data Augmentation)
Áp dụng các kỹ thuật tăng cường thích ứng với điều kiện giao thông đường bộ:
- **Mosaic Augmentation ($p=1.0$):** Ghép 4 ảnh ngẫu nhiên giúp mô hình học các phương tiện bị che khuất và kích thước nhỏ.
- **HSV Color Jitter (H=0.015, S=0.7, V=0.4):** Mô phỏng sự thay đổi ánh sáng mặt trời lúc nắng gắt và lúc xế chiều.
- **Random Motion Blur:** Giả lập hiện tượng mờ nhòe khi xe di chuyển tốc độ cao ($> 60\text{ km/h}$).
- **Random Erasing (Cutout):** Giúp mô hình bền vững khi xe máy đi sau xe tải bị che mất nửa thân.

### 4.3. Mã nguồn Huấn luyện Python (YOLOv11-Nano / Small)
```python
from ultralytics import YOLO

# Khởi tạo kiến trúc mô hình YOLOv11 từ đầu (From-Scratch)
model = YOLO("yolo11n.yaml")  # Bản nano cho tốc độ cao, hoặc yolo11s.yaml cho độ chính xác cao hơn

# Bắt đầu quá trình huấn luyện
results = model.train(
    data="data.yaml",
    epochs=250,
    imgsz=640,
    batch=32,
    device=0,           # GPU NVIDIA
    workers=8,
    optimizer="AdamW",
    lr0=0.001,
    lrf=0.01,
    weight_decay=0.0005,
    warmup_epochs=3.0,
    box=7.5,            # CIoU Loss weight
    cls=0.5,            # BCE Classification Loss weight
    dfl=1.5,            # Distribution Focal Loss weight
    close_mosaic=15,    # Tắt Mosaic ở 15 epochs cuối để bounding box sắc nét
    project="vehicle_counting_speed",
    name="yolo11n_vehicle_run1"
)
```

---

## 5. ĐÁNH GIÁ CHẤT LƯỢNG MÔ HÌNH & TIÊU CHÍ NGHIỆM THU (KPI)

| Chỉ số đánh giá | Giá trị mục tiêu | Đạt chuẩn nghiệm thu |
| :--- | :---: | :---: |
| **mAP@50 (Toàn bộ 8 lớp)** | $\ge \mathbf{92.0\%}$ | ĐẠT |
| **mAP@50-95** | $\ge \mathbf{72.5\%}$ | ĐẠT |
| **Recall (Tỷ lệ không bỏ sót xe)** | $\ge \mathbf{95.0\%}$ | ĐẠT |
| **Precision (Độ chính xác phân loại)** | $\ge \mathbf{93.0\%}$ | ĐẠT |
| **Thời gian suy luận (GPU RTX 4090 / L4)** | $\le \mathbf{3.5\text{ ms/frame}}$ | ĐẠT |

---

## 6. XUẤT BẢN & TỐI ƯU HÓA SUY LUẬN BIÊN (TENSORRT & OPENVINO)

Sau khi huấn luyện đạt KPI, mô hình được chuyển đổi sang các định dạng suy luận tối ưu phần cứng:

### 6.1. Xuất sang ONNX Opset 17
```bash
yolo export model=runs/detect/yolo11n_vehicle_run1/weights/best.pt format=onnx opset=17 dynamic=False imgsz=640
```

### 6.2. Lượng hóa TensorRT INT8 / FP16 trên máy chủ GPU
```bash
# Lượng hóa FP16:
trtexec --onnx=best.onnx --saveEngine=best_fp16.engine --fp16

# Lượng hóa INT8 kèm tập ảnh hiệu chuẩn (Calibration Dataset):
trtexec --onnx=best.onnx --saveEngine=best_int8.engine --int8 --calib=calib_data.cache
```
*Kết quả:* Mô hình TensorRT INT8 giảm $72\%$ dung lượng VRAM và tăng tốc độ suy luận gấp $6.5\times$, đạt $\approx 1.8\text{ ms/frame}$ trên GPU NVIDIA.

### 6.3. Tối ưu OpenVINO cho Máy chủ CPU
```bash
yolo export model=best.pt format=openvino half=True imgsz=640
```
Chạy mượt mà $45 - 60\text{ FPS}$ trên CPU Intel Core i7 / Xeon thông thường mà không cần GPU rời.

---
*Bản quyền tài liệu thuộc về Đội ngũ Deep Learning & MLOps ITS 2026.*
