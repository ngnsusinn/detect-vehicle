# HƯỚNG DẪN QUY TRÌNH GÁN NHÃN MÁY CON, HUẤN LUYỆN GOOGLE COLAB & TRIỂN KHAI MÁY CLIENT
## HỆ THỐNG ĐẾM VÀ ĐO TỐC ĐỘ PHƯƠNG TIỆN GIAO THÔNG TỪ LUỒNG VIDEO STREAMING
**Mã tài liệu:** GUIDE-SPEED-COUNT-COLAB-CLIENT-2026  
**Phiên bản:** 2.0.0 (Cập nhật Toàn diện Bài toán Đếm Xe & Đo Tốc độ)  
**Đối tượng áp dụng:** Kỹ sư Triển khai, Kỹ sư AI & Vận hành Hệ thống ITS

---

## 1. TỔNG QUAN QUY TRÌNH VẬN HÀNH KHÉP KÍN (END-TO-END WORKFLOW)

Quy trình phối hợp giữa các máy con gán nhãn (Annotation Stations), môi trường đám mây Google Colab (GPU Cloud Training) và máy trạm thực địa (Client Inference Nodes) được thiết kế tinh gọn:

```
[MÁY CON (ANNOTATION PCS)]              [GOOGLE COLAB (GPU CLOUD)]             [MÁY CLIENT (EDGE / RUNTIME)]
                                                                               
  +---------------------+                                                        +----------------------+
  | Cắt frame từ stream |                                                        | Camera Streaming     |
  | collector_gui.py /  |                                                        | (RTSP/WebRTC/HLS/MP4)|
  | frame_extractor.py  |                                                        +----------+-----------+
  +----------+----------+                                                                   |
             |                                                                              v
             v                                                                   +----------------------+
  +---------------------+                                                        | Video Stream Ingest  |
  | Gán nhãn 8 lớp xe   |                                                        | (Async Decoupled Q)  |
  | (Label Studio /     |                                                        +----------+-----------+
  |  X-AnyLabeling)     |                                                                   |
  +----------+----------+                                                                   v
             |                                                                   +----------------------+
             v                                  +-----------------------+        | AI Pipeline:         |
  +---------------------+                       | Google Colab GPU      |        | - YOLOv11 Detector   |
  | Đóng gói 100% Real  |                       | (T4 Free / A100 Pro)  |        |   (TensorRT/OpenVINO)|
  | Dataset (Images +   |──────────────────────►| - Train YOLOv11       |───────►| - ByteTrack Multi-Obj|
  | YOLO format txt)    |                       |   Vehicle Detector    |        | - Line-Crossing Count|
  +---------------------+                       | - Xuất ONNX / TRT     |        | - Homography Speed   |
                                                +-----------------------+        +----------+-----------+
                                                                                            |
                                                                                            v
                                                                                 [Kết quả: Lưu lượng xe /
                                                                                 [Cảnh báo Quá tốc độ & Clip]
```

---

## 2. HƯỚNG DẪN CÀI ĐẶT & GÁN NHÃN TẠI MÁY CON (STEP-BY-STEP ANNOTATION GUIDE)

### 2.1. Lựa chọn Công cụ Gán nhãn: **Label Studio Community Edition** hoặc **X-AnyLabeling**
Thành viên có thể sử dụng một trong 2 công cụ chính thức của dự án:
- **Công cụ chính (Web-based): Label Studio Community Edition**
  - Giao diện trực quan trên trình duyệt web, hỗ trợ gán nhãn theo nhóm qua mạng LAN.
  - Sử dụng tệp cấu hình XML có sẵn: `annotation/label_studio_template.xml`.
- **Công cụ Portable chạy độc lập: X-AnyLabeling**
  - Chạy file `.exe` offline không cần cài đặt Python.

---

### 2.2. Danh mục 8 Lớp Phương tiện Chuẩn hóa (8 Target Vehicle Classes)

Mỗi thành viên khi gán nhãn phải tuân thủ đúng danh mục 8 nhãn và phím tắt (Hotkeys):

| Class ID | Label (Tên lớp) | Ý nghĩa thực tế | Phím tắt | Lưu ý khi gán |
| :---: | :--- | :--- | :---: | :--- |
| **0** | `motorcycle` | Xe máy, xe mô tô 2 bánh, 3 bánh | `1` | Ôm sát từ đỉnh đầu xe/nón bảo hiểm xuống đáy lốp |
| **1** | `car` | Ô tô con (Sedan, SUV, CUV, Bán tải) | `2` | Ôm trọn thân xe và bánh xe chạm đất, bỏ qua bóng đổ |
| **2** | `electric_bicycle`| Xe đạp điện, xe máy điện mini | `3` | Nhận biết qua bình ắc quy vuông dưới yên, bàn đạp phụ |
| **3** | `bicycle` | Xe đạp cơ thông thường | `4` | Khung xe thanh mảnh |
| **4** | `bus` | Xe buýt nội đô, xe khách 16 - 45 chỗ | `5` | Khối xe vuông cao |
| **5** | `truck` | Xe tải chở hàng, xe tải ben | `6` | Có thùng hàng phía sau |
| **6** | `container_truck` | Xe container, xe đầu kéo rơ-moóc | `7` | Thân xe rất dài |
| **7** | `special_vehicle` | Xe ba gác, xe cứu thương, xe chuyên dụng| `8` | Xe 3 bánh, xe chuyên dụng cứu hộ |

---

### 2.3. Quy tắc Vàng khi Gán nhãn Bounding Box phục vụ Đo Tốc độ
1. **Điểm neo tiếp đất của bánh xe:** Do hệ thống dùng điểm Bottom-Center làm tọa độ không gian để ánh xạ qua ma trận Homography, đáy của bounding box phải nằm chính xác tại điểm tiếp xúc giữa lốp xe và mặt đường.
2. **Tuyệt đối KHÔNG gán bóng đổ (Shadow):** Không được kéo bounding box bao trùm vệt bóng đen của xe trên đường vì sẽ làm sai lệch tọa độ tiếp đất thực tế.
3. **Xe bị che khuất (Occlusion):** Nếu xe bị che khuất một phần bởi xe khác nhưng vẫn nhìn thấy $\ge 30\%$ thân xe, vẫn vẽ bounding box bao quát toàn bộ diện tích xe nhìn thấy được.

---

### 2.4. Phân chia 4 Gói Dữ liệu cho các Thành viên
- **Gói 1 (Day-1 - TV 2):** Ban ngày sáng ($07\text{h}00 - 12\text{h}00$) $\approx 1.500$ frames; $\sim 9.000$ bboxes.
- **Gói 2 (Day-2 - TV 3):** Ban ngày chiều ($12\text{h}00 - 17\text{h}30$) $\approx 1.500$ frames; $\sim 9.000$ bboxes.
- **Gói 3 (Night-1 - TV 4):** Ban đêm chập tối ($18\text{h}30 - 21\text{h}00$) $\approx 1.200$ frames; $\sim 7.000$ bboxes.
- **Gói 4 (Night-2 - TV 5):** Ban đêm muộn & đèn pha ($21\text{h}00 - 23\text{h}30$) $\approx 1.200$ frames; $\sim 7.000$ bboxes.

---

## 3. QUY TRÌNH HUẤN LUYỆN TRÊN GOOGLE COLAB (100% REAL DATASET)

### 3.1. Các bước thực hiện trên Google Colab GPU (NVIDIA T4 / A100)
1. **Kết nối Google Drive & Chuẩn bị môi trường:**
```python
from google.colab import drive
drive.mount('/content/drive')

!pip install ultralytics
```

2. **Giải nén tập dữ liệu nén:**
```python
!unzip -q /content/drive/MyDrive/dataset_speed_count/master_dataset_yolo.zip -d /content/dataset/
```

3. **Chạy script huấn luyện YOLOv11 Vehicle Detector:**
```python
from ultralytics import YOLO

model = YOLO("yolo11n.pt")  # Sử dụng kiến trúc yolo11n tối ưu tốc độ cao

model.train(
    data="/content/dataset/data.yaml",
    epochs=200,
    imgsz=640,
    batch=32,
    device=0,
    project="/content/drive/MyDrive/checkpoints",
    name="yolo11n_vehicle_speed"
)
```

4. **Thời gian huấn luyện trên Colab:**
   - **Colab Miễn phí (GPU NVIDIA T4 16GB):** Chỉ mất khoảng **$1.8 - 2.5\text{ giờ}$** cho $6.000$ khung hình ảnh thực tế ($200\text{ epochs}$).
   - **Colab Pro (GPU NVIDIA A100):** Chỉ mất khoảng **$25 - 35\text{ phút}$**.
   - Trọng số tốt nhất tự động lưu tại `/content/drive/MyDrive/checkpoints/yolo11n_vehicle_speed/weights/best.pt`.

5. **Xuất mô hình sang ONNX Opset 17:**
```python
model = YOLO("/content/drive/MyDrive/checkpoints/yolo11n_vehicle_speed/weights/best.pt")
model.export(format="onnx", opset=17, dynamic=False, imgsz=640)
```

---

## 4. ĐÁNH GIÁ HIỆU SUẤT MÁY CLIENT: CHẠY HỆ THỐNG LIỆU CÓ BỊ LAG KHÔNG?

### 4.1. Bảng Đánh giá Hiệu năng Chi tiết theo từng Cấu hình Máy Client

| Cấu hình Phần cứng Máy Client | Công nghệ Tối ưu | Độ trễ suy luận AI (Latency/frame) | Tốc độ xử lý (FPS) | Đánh giá hiện tượng LAG | Khả năng đáp ứng thực tế |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **PC có GPU rời:**<br>Intel Core i5 + NVIDIA RTX 3050 / RTX 4060 | **NVIDIA TensorRT FP16 / INT8** | **$\mathbf{3 - 8\text{ ms}}$** | **$120 - 200+\text{ FPS}$** | **HOÀN TOÀN KHÔNG LAG**<br>(Mượt mà $100\%$, đáp ứng 4 - 8 luồng stream) | Đo tốc độ và đếm xe tức thời, chính xác từng frame. |
| **Thiết bị nhúng AI biên:**<br>NVIDIA Jetson Orin Nano (8GB) / Orin NX | **NVIDIA TensorRT FP16** | **$\mathbf{12 - 20\text{ ms}}$** | **$45 - 60\text{ FPS}$** | **HOÀN TOÀN KHÔNG LAG**<br>(Đáp ứng tốt 2 - 4 luồng stream) | Chuẩn công nghiệp lắp trực tiếp tại cột camera ngoài trời. |
| **Laptop / PC văn phòng không GPU:**<br>Intel Core i5 / i7 Gen 11 - 13 (Iris Xe) | **Intel OpenVINO FP16 / INT8** | **$\mathbf{18 - 30\text{ ms}}$** | **$30 - 45\text{ FPS}$** | **HOÀN TOÀN KHÔNG LAG**<br>(Đáp ứng mượt 1 - 2 luồng 1080p @ 30fps) | Chạy thời gian thực mượt mà không cần GPU rời. |

---

### 4.2. Bốn Nguyên Tắc Kỹ Thuật Triệt Tiêu Hoàn Toàn Lag trên Máy Client
1. **Luồng đọc Stream bất đồng bộ (Decoupled Async Frame Reader):** Đọc video ở một thread độc lập, liên tục giải phóng buffer FFmpeg để không bao giờ bị nghẽn hàng đợi khung hình.
2. **Lượng hóa phần cứng (Hardware Quantization):** Luôn chuyển đổi model `.pt` sang OpenVINO (cho CPU) hoặc TensorRT (cho GPU NVIDIA).
3. **Tính toán hình học siêu nhẹ (Vectorized Homography):** Sử dụng phép nhân ma trận mảng NumPy thay vì lặp từng đối tượng, thời gian tính toán Homography và Line-Crossing chỉ mất $< 0.5\text{ ms/frame}$.
4. **Ghi đĩa và cắt clip bất đồng bộ (Async Queue Writer):** Lưu ảnh snapshot và cắt clip video vi phạm quá tốc độ ở thread phụ (Worker Thread) để không ảnh hưởng đến vòng lặp chính của luồng AI.

---
*Bản quyền tài liệu kỹ thuật thuộc về Nhóm Kỹ sư Triển khai ITS 2026.*
