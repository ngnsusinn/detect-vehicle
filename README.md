# HỆ THỐNG ĐẾM VÀ ĐO TỐC ĐỘ PHƯƠNG TIỆN GIAO THÔNG TỪ LUỒNG VIDEO STREAMING ĐA GIAO THỨC
### (AI-POWERED MULTI-PROTOCOL VIDEO STREAMING VEHICLE COUNTING & SPEED ESTIMATION SYSTEM - ITS 2026)

> Giải pháp giám sát giao thông thông minh ứng dụng Thị giác máy tính (Computer Vision), Học sâu (Deep Learning) và Tăng tốc phần cứng GPU, hỗ trợ tiếp nhận trực tiếp từ các luồng video streaming đa dạng (**RTSP, WebRTC, HLS, SRT, RTMP, File MP4**) để thực hiện **Phát hiện & Phân loại phương tiện** (xe máy, ô tô, xe đạp điện, xe đạp, xe khách, xe tải, container), **Bám vết đa đối tượng (ByteTrack)**, **Đếm lưu lượng theo làn/hướng** và **Đo tốc độ phương tiện thời gian thực qua ma trận biến đổi phối cảnh (Homography Transform)** với sai số cực thấp ($\le \pm 3 - 5\text{ km/h}$).

---

## 🚀 TÍNH NĂNG CỐT LÕI (CORE FEATURES)

1. **Thu nhận & Giải mã Luồng Đa Giao thức (Multi-Protocol Streaming Ingestion):**
   - Hỗ trợ kết nối trực tiếp các luồng camera giao thông qua: **RTSP**, **HLS / LL-HLS (.m3u8)**, **WebRTC (WHIP)**, **SRT**, **RTMP** và video tệp (`.mp4`, `.avi`).
   - Tối ưu hóa giải mã phần cứng không sao chép (Zero-copy GPU Decoding) qua NVIDIA NVDEC / DeepStream SDK.

2. **Phát hiện & Phân loại Phương tiện Chuyên sâu (Vehicle Detection & Classification):**
   - Ứng dụng mô hình **YOLOv11 / YOLOv8** tối ưu riêng cho đặc thù giao thông Việt Nam.
   - Phân loại chi tiết 8 nhóm phương tiện:
     - `motorcycle` (Xe máy, mô tô 2 bánh, 3 bánh)
     - `car` (Ô tô con, Sedan, SUV, CUV, bán tải)
     - `electric_bicycle` (Xe đạp điện, xe máy điện)
     - `bicycle` (Xe đạp cơ thông thường)
     - `bus` (Xe buýt, xe khách 16 - 45 chỗ)
     - `truck` (Xe tải thùng, xe ben)
     - `container_truck` (Xe đầu kéo, container)
     - `special_vehicle` (Xe ba gác, xe cứu thương, xe chuyên dụng)

3. **Bám vết Đa đối tượng Bền vững (Multi-Object Tracking - ByteTrack):**
   - Gán `Track ID` duy nhất cho từng phương tiện.
   - Bám vết liên tục qua các khung hình ngay cả khi mật độ phương tiện đông đúc hoặc bị che khuất tạm thời (Occlusion Robustness).

4. **Đếm Lưu lượng Thông minh theo Làn & Hướng (Directional Line-Crossing Counting):**
   - Thiết lập vạch ảo (Virtual Tripwire) hoặc vùng ảo (ROI Counting Zone).
   - Tự động đếm và cộng dồn lưu lượng theo từng loại xe, từng chiều di chuyển (hướng đi / hướng về) và từng làn đường.

5. **Đo Tốc độ Phương tiện bằng Ma trận Phối cảnh (Homography Speed Estimation):**
   - Ánh xạ tọa độ từ mặt phẳng ảnh pixel sang mặt phẳng mặt đường thực địa mét ($X, Y$) thông qua ma trận **Homography ($H$)**:
     $$v = \frac{d}{\Delta t} \times 3.6 \quad (\text{km/h}), \quad d = \sqrt{(X_2 - X_1)^2 + (Y_2 - Y_1)^2}$$
   - Lọc nhiễu vận tốc bằng bộ lọc Kalman Filter / Exponential Moving Average (EMA) để triệt tiêu hiện tượng nhảy vận tốc cục bộ do rung camera hoặc sai lệch bounding box.
   - Sai số đo kiểm thực tế $\le \pm 3 - 5\text{ km/h}$.

6. **Phát hiện & Cắt Clip Bằng chứng Vi phạm Quá tốc độ (Overspeed Capture & Alert):**
   - Tự động phát hiện phương tiện vượt ngưỡng tốc độ quy định trên làn đường (ví dụ: $> 50\text{ km/h}$ trong đô thị hoặc $> 80\text{ km/h}$ trên quốc lộ).
   - Tự động chụp ảnh snapshot phương tiện vi phạm kèm thông tin: Track ID, loại xe, vận tốc tức thời, thời điểm vi phạm.
   - Cắt tự động video clip bằng chứng 6 giây (3 giây trước và 3 giây sau khi chạm vạch tốc độ) lưu vào MinIO/S3.

7. **Bộ công cụ Gán nhãn Label Studio Community Tích hợp:**
   - Cung cấp sẵn tệp cấu hình XML `annotation/label_studio_template.xml` và `annotation/label_studio_yolo_simple.xml` chuẩn xuất định dạng YOLO TXT.
   - Hướng dẫn chi tiết quy trình gán nhãn tại: [annotation/README_LABEL_STUDIO.md](annotation/README_LABEL_STUDIO.md).

---

## 📚 CẤU TRÚC BỘ TÀI LIỆU KỸ THUẬT (DOCUMENTATION INDEX)

Toàn bộ tài liệu kỹ thuật chuyên sâu của dự án được lưu trữ trong thư mục `docs/`:

1. [Tài liệu Đặc tả Yêu cầu Phần mềm (docs/SRS.md)](docs/SRS.md):
   - Chuẩn IEEE 830 / ISO/IEC/IEEE 29148 cho bài toán Đếm và Đo tốc độ phương tiện.
   - Đặc tả 9 nhóm yêu cầu chức năng (FR-01 đến FR-09) và 5 nhóm yêu cầu phi chức năng (NFR 5.1 đến 5.5).
   - Tiêu chuẩn dung sai đo tốc độ theo quy chuẩn đo lường và giao thông thông minh.

2. [Tài liệu Thiết kế Kiến trúc Hệ thống (docs/SYSTEM_ARCHITECTURE.md)](docs/SYSTEM_ARCHITECTURE.md):
   - Kiến trúc tổng thể 4 tầng: Ingestion Gateway $\rightarrow$ Hardware Accelerated NVDEC Pipeline $\rightarrow$ AI Inference, ByteTrack & Homography Speed Engine $\rightarrow$ Core Services, TimescaleDB & Dashboard.
   - Chi tiết giải thuật ánh xạ Homography, đường cơ sở đo vận tốc và bộ lọc Kalman Filter.
   - Thiết kế CSDL TimescaleDB lưu trữ chuỗi thời gian lưu lượng và vận tốc xe.

3. [Tài liệu Hạ tầng Phần cứng & Mạng Streaming (docs/HARDWARE_SPECIFICATIONS.md)](docs/HARDWARE_SPECIFICATIONS.md):
   - Cấu hình máy chủ GPU tập trung (NVIDIA RTX 4090 / NVIDIA L4 / Jetson Orin).
   - Định cỡ GPU (GPU Sizing) xử lý đồng thời 20 - 32 luồng streaming đo tốc độ và đếm xe.
   - Bảng tính dung lượng lưu trữ clip bằng chứng vi phạm quá tốc độ và ảnh snapshot phương tiện.

4. [Tài liệu Quy trình Huấn luyện Mô hình Từ đầu (docs/MODEL_TRAINING_PIPELINE.md)](docs/MODEL_TRAINING_PIPELINE.md):
   - Chiến lược huấn luyện mô hình YOLOv11 Vehicle Detector từ đầu với **100% dữ liệu ảnh thực tế** từ camera streaming ngày & đêm.
   - Chuẩn hóa 8 lớp phương tiện giao thông Việt Nam.
   - Tối ưu hóa suy luận biên TensorRT INT8 / FP16 và OpenVINO CPU.

5. [Hướng dẫn Gán nhãn Phân tán & Huấn luyện Colab (docs/DISTRIBUTED_ANNOTATION_COLAB_GUIDE.md)](docs/DISTRIBUTED_ANNOTATION_COLAB_GUIDE.md):
   - Hướng dẫn phân chia dữ liệu gán nhãn cho nhóm nhiều thành viên với **Label Studio Community** và **X-AnyLabeling**.
   - Sổ tay huấn luyện Google Colab GPU (T4 / A100) và xuất weights model ONNX/TensorRT.

6. [Hướng dẫn Thu thập Dữ liệu Video Streaming (docs/DATA_COLLECTION_GUIDE.md)](docs/DATA_COLLECTION_GUIDE.md):
   - Hướng dẫn sử dụng công cụ GUI (`collector_gui.py` / `run_collector.bat`) tự động cắt frame chu kỳ 3 giây theo từng khung giờ (1h/folder).
   - Hỗ trợ nguồn RTSP, HLS, WebRTC, YouTube Livestream, Webcam, MP4.

7. [Kế hoạch Phân công Công việc Nhóm 5 Thành viên (docs/PROJECT_WORK_PLAN.md)](docs/PROJECT_WORK_PLAN.md):
   - Phân chia công việc chi tiết cho nhóm 5 thành viên xoay quanh bài toán Đếm xe & Đo tốc độ trên 1 góc camera tĩnh (tập trung 60% Ban ngày, 40% Ban đêm).
   - Phân bổ 4 gói dán nhãn dữ liệu và đề cương 5 chương báo cáo tiểu luận.

8. [Đặc tả Tiêu chuẩn Dữ liệu Gán nhãn (docs/DATA_ANNOTATION_SPECIFICATION.md)](docs/DATA_ANNOTATION_SPECIFICATION.md):
   - 5 đặc điểm kỹ thuật bắt buộc của dữ liệu ảnh (góc nghiêng $30^\circ - 50^\circ$, điểm đáy bánh xe, chống nhòe motion blur, cân bằng lớp xe Việt Nam, ngày/đêm).
   - Quy tắc kỹ thuật vẽ Bounding Box trên Label Studio Community (bỏ qua bóng đổ, xe 2 bánh ôm cả người lái, xử lý che khuất).
   - Bảng Checklist kiểm duyệt chất lượng (QA/QC Checklist) nghiệm thu từng gói dữ liệu.

9. [Cẩm nang Hướng dẫn Gán nhãn Chi tiết (docs/LABELING_GUIDELINE_DETAIL.md)](docs/LABELING_GUIDELINE_DETAIL.md):
   - Hướng dẫn thực hành từng bước từ import ảnh, phím tắt 1-8 tăng tốc gấp 3 lần đến xuất file nén YOLO format.
   - Bảng phân biệt các cặp xe dễ nhầm lẫn (bán tải vs xe tải nhỏ, xe 16 chỗ vs bus, xe đạp điện vs xe máy).
   - Quy tắc vẽ Bounding Box chuẩn xác đáy bánh xe chạm đất phục vụ đo tốc độ Homography.

---

## 🎯 CÁC CHỈ SỐ KỸ THUẬT CỐT LÕI (KEY SYSTEM PERFORMANCE INDICATORS)

| Chỉ số kỹ thuật | Giá trị cam kết | Ghi chú vận hành |
| :--- | :--- | :--- |
| **Giao thức Streaming hỗ trợ** | **RTSP, HLS, WebRTC, SRT, RTMP, MP4** | Giải mã tự động chuẩn nén H.264, H.265/HEVC, AV1 |
| **Độ chính xác đếm xe (Counting Accuracy)** | $\ge \mathbf{97.5\%}$ | Đã kiểm thử trên luồng giao thông thực tế mật độ cao |
| **Sai số đo tốc độ (Speed Error)** | $\le \mathbf{\pm 3 - 5\text{ km/h}}$ | So sánh với súng bắn tốc độ chuẩn và GPS phương tiện |
| **Độ trễ suy luận AI (Latency)** | $\le \mathbf{60 - 75\text{ ms/frame}}$ | Tính từ lúc nhận frame $\rightarrow$ NVDEC decode $\rightarrow$ YOLO $\rightarrow$ ByteTrack $\rightarrow$ Speed |
| **Mật độ luồng trên mỗi GPU** | **20 – 32 luồng 1080p @ 25-30fps** | Vận hành trên NVIDIA RTX 4090 / NVIDIA L4 (24GB VRAM) |
| **Phân loại phương tiện (Classification mAP50)** | $\ge \mathbf{92.0\%}$ | Nhận diện chính xác 8 loại phương tiện giao thông phổ biến |
| **Thời gian lưu clip bằng chứng vi phạm** | $\le \mathbf{1.5\text{ giây}}$ | Tự động xuất clip MP4 6 giây đưa vào MinIO S3 |

---

## 🛠️ NGĂN XẾP CÔNG NGHỆ CHỦ CHỐT (CORE TECH STACK)

- **Streaming Ingestion & Video Decoding:** GStreamer 1.24, FFmpeg, MediaMTX, OpenCV, NVIDIA NVDEC / DeepStream SDK.
- **AI & Deep Learning:** PyTorch, Ultralytics YOLOv11 / YOLOv8, TensorRT 10.x, OpenVINO 2024.
- **Multi-Object Tracking & Geometry:** ByteTrack, OpenCV Perspective Transform (Homography Matrix $H$), Kalman Filter, Shapely.
- **Data Annotation:** Label Studio Community Edition, X-AnyLabeling.
- **Backend & Core Services:** Python 3.11 (FastAPI), Golang, Docker, Kubernetes.
- **Time-series Database & Storage:** PostgreSQL 16 + TimescaleDB, Redis 7, MinIO / S3.
- **Dashboard & Visualization:** React.js / Vue 3, Tailwind CSS, Chart.js / Recharts.

---

## 🏁 BẮT ĐẦU NHANH (QUICK START)

### 1. Cài đặt thư viện
```bash
pip install -r requirements.txt
```

### 2. Thu thập dữ liệu video streaming
```bash
# Khởi chạy giao diện đồ họa thu thập ảnh:
python collector_gui.py
# Hoặc nhấp đúp vào run_collector.bat trên Windows
```

### 3. Gán nhãn dữ liệu bằng Label Studio Community
Xem hướng dẫn chi tiết tại [annotation/README_LABEL_STUDIO.md](annotation/README_LABEL_STUDIO.md) và sử dụng file cấu hình [annotation/label_studio_template.xml](annotation/label_studio_template.xml).

### 4. Chạy thử nghiệm thuật toán Bám vết, Đếm xe & Đo tốc độ
```bash
python speed_estimation_demo.py --video sample_traffic.mp4
```

---
*Bản quyền tài liệu kỹ thuật thuộc về Nhóm Kiến trúc Hệ thống ITS & Video Streaming Pipeline 2026.*
