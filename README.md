# HỆ THỐNG NHẬN DIỆN BIỂN SỐ XE TỪ LUỒNG VIDEO STREAMING ĐA GIAO THỨC
### (MULTI-PROTOCOL VIDEO STREAMING ANPR/ALPR SYSTEM)

> Giải pháp nhận diện biển số xe ứng dụng Deep Learning và Tăng tốc phần cứng GPU chuyên dụng, hỗ trợ tiếp nhận trực tiếp từ các luồng video streaming đa dạng (**HLS, WebRTC, RTSP, SRT, RTMP**) với độ trễ siêu thấp ($\le 80\text{ ms}$), hỗ trợ đầy đủ quy chuẩn biển số Việt Nam (Thông tư 24/2023/TT-BCA) cho hệ thống Giám sát Đô thị Thông minh (Smart City), Xe tuần tra di động (Mobile Police ANPR) và Trạm thu phí/bãi xe hiện đại.

---

## 📚 CẤU TRÚC BỘ TÀI LIỆU KỸ THUẬT (DOCUMENTATION INDEX)

Toàn bộ tài liệu kỹ thuật chuyên sâu của dự án được lưu trữ trong thư mục `docs/`:

1. [Tài liệu Đặc tả Yêu cầu Phần mềm (docs/SRS.md)](docs/SRS.md):
   - Chuẩn IEEE 830 / ISO/IEC/IEEE 29148.
   - Bối cảnh đề tài, mục tiêu và phạm vi ứng dụng đa giao thức streaming.
   - Bằng chứng thực nghiệm & Case studies: Cổng giao thông HLS TP.HCM, Xe tuần tra WebRTC 5G, Trạm thu phí liên tỉnh qua SRT.
   - Ma trận so sánh 5 giao thức streaming: WebRTC, RTSP, SRT, HLS/LL-HLS, RTMP.
   - Đặc tả 9 nhóm yêu cầu chức năng (FR-01 đến FR-09) và 5 nhóm yêu cầu phi chức năng (NFR 5.1 đến 5.5).
   - Ràng buộc cú pháp biển số Việt Nam theo Thông tư 24/2023/TT-BCA, quy chuẩn quân sự Thông tư 169/2021/TT-BQP, ma trận Regex và bảng khử nhập nhằng ký tự.
2. [Tài liệu Thiết kế Kiến trúc Hệ thống (docs/SYSTEM_ARCHITECTURE.md)](docs/SYSTEM_ARCHITECTURE.md):
   - Kiến trúc tổng thể 4 tầng: Ingestion Gateway $\rightarrow$ Hardware Accelerated NVDEC Pipeline $\rightarrow$ AI Inference & Virtual Triggering $\rightarrow$ Core Services & Storage.
   - Pipeline GStreamer và NVIDIA DeepStream giải mã phần cứng không sao chép (Zero-copy GPU VRAM).
   - Kỹ thuật bẫy ảo (Virtual Trigger Zone), lấy mẫu thích nghi (Adaptive Sampler) và giải thuật chọn khung hình nét nhất (Laplacian Variance).
   - Thiết kế cơ sở dữ liệu PostgreSQL 16 (TimescaleDB Hypertable), Redis Cache, MinIO S3.
   - Đặc tả RESTful API, giao thức Ingestion di động WebRTC WHIP và WebSocket phát sự kiện thời gian thực.
3. [Tài liệu Hạ tầng Phần cứng & Mạng Streaming (docs/HARDWARE_SPECIFICATIONS.md)](docs/HARDWARE_SPECIFICATIONS.md):
   - Cấu hình máy chủ GPU tập trung (2U Rackmount với NVIDIA RTX 4090 / NVIDIA L4 / A10).
   - Ma trận phân tích năng lực giải mã phần cứng NVDEC và định kích cỡ GPU (GPU Sizing).
   - Bảng tính toán băng thông mạng Ingress cho 10, 50, 100, 250, 1.000 luồng stream đồng thời.
   - Bảng tính toán dung lượng lưu trữ clip bằng chứng 6 giây (MP4) và ảnh snapshot trong 1 năm.
   - Sơ đồ đấu nối mạng tích hợp STUN/TURN (Coturn) vượt tường lửa 4G/5G.
4. [Tài liệu Quy trình Huấn luyện Mô hình Từ đầu (docs/MODEL_TRAINING_PIPELINE.md)](docs/MODEL_TRAINING_PIPELINE.md):
   - Chiến lược huấn luyện từ đầu với **100% dữ liệu thực tế** trích xuất từ camera streaming (RTSP, HLS, WebRTC), cam kết không dùng dữ liệu ảo.
   - Chuỗi 3 mô hình học sâu: YOLOv11 Vehicle Detection, YOLOv11-Pose 4-Corner Plate, Deep OCR PP-OCRv4 / CRNN-CTC.
   - Chuẩn gán nhãn dữ liệu CVAT / Label Studio và hàm mất mát CIoU, OKS, CTC Loss.
   - Tối ưu hóa suy luận và lượng hóa phần cứng TensorRT INT8 (giảm $74\%$ VRAM, tăng tốc gấp $7.9\times$).
   - Vòng lặp học chủ động (Active Learning MLOps Loop) tự động gom dữ liệu khó và tái huấn luyện không downtime.
5. [Hướng dẫn Gán nhãn Máy con, Huấn luyện Colab & Deploy Client (docs/DISTRIBUTED_ANNOTATION_COLAB_GUIDE.md)](docs/DISTRIBUTED_ANNOTATION_COLAB_GUIDE.md):
   - Quy trình gán nhãn phân tán tại các máy con với X-AnyLabeling / Label Studio trên $100\%$ dữ liệu ảnh thực tế.
   - Sổ tay huấn luyện Google Colab (Free T4 / Pro A100), đánh giá chi tiết thời gian train ($6 - 8.5\text{h}$) và số lượng mẫu thực tế cần thiết.
   - Đánh giá hiệu năng máy client: Khẳng định máy client **100% không bị lag** khi áp dụng 4 nguyên tắc kỹ thuật (Async Reader, Adaptive Sampler 10fps, Virtual Trigger, OpenVINO/TensorRT).
6. [Công cụ Thu thập Khung hình Thực tế từ Stream (training/stream_frame_extractor.py)](training/stream_frame_extractor.py):
   - Mã nguồn Python kết nối trực tiếp vào luồng video RTSP/HLS/WebRTC, tự động phát hiện chuyển động (MOG2), lọc trùng bằng pHash và tự chia gói dữ liệu cho các máy con gán nhãn.
7. [Ứng dụng Giao diện Đồ họa Thu thập Ảnh Streaming (collector_gui.py / run_collector.bat)](docs/DATA_COLLECTION_GUIDE.md):
   - Ứng dụng GUI Tkinter đa luồng chuyên dụng thu thập dữ liệu ảnh từ RTSP, HLS, WebRTC, Webcam và video MP4.
   - Cơ chế tự động: Đúng **mỗi 3 giây chụp 1 ảnh** (3s/frame).
   - Tự động phân chia thư mục theo **từng khung giờ (1h / folder)** (`00h-01h`, `01h-02h`, ..., `23h-24h`).
   - Tích hợp công cụ dòng lệnh FFmpeg chuyên dụng (`stream_capture_ffmpeg.py` / `capture_ffmpeg.bat`) và bộ lọc chọn frame sắc nét nhất (Laplacian Variance) chống mờ nhòe chuyển động.
   - Tích hợp khung xem trực tiếp (Live Stream Preview), đếm ngược thời gian chụp kế tiếp, bảng thống kê và nhật ký hoạt động thời gian thực.
   - Hỗ trợ cả chế độ đồ họa và chế độ dòng lệnh ngầm (Headless CLI) cho máy chủ.
   - Xem hướng dẫn chi tiết tại: [Tài liệu Hướng dẫn Thu thập Dữ liệu (docs/DATA_COLLECTION_GUIDE.md)](docs/DATA_COLLECTION_GUIDE.md).
8. [Kế hoạch Phân công Công việc Nhóm 5 Thành viên (docs/PROJECT_WORK_PLAN.md)](docs/PROJECT_WORK_PLAN.md):
   - Phân chia công việc chi tiết cho nhóm 5 thành viên theo phạm vi tinh gọn: **1 góc camera tĩnh duy nhất**, tập trung dữ liệu **Ban ngày (60%)** và **Ban đêm (40%)**.
   - Phân bổ 4 gói dán nhãn X-AnyLabeling máy con và đề cương chi tiết 5 chương tiểu luận học thuật.
   - Lộ trình thực hiện 4 tuần và tiêu chuẩn nghiệm thu chất lượng (KPI).

---

## 🎯 CÁC CHỈ SỐ KỸ THUẬT CỐT LÕI (KEY SYSTEM PERFORMANCE INDICATORS)

| Chỉ số kỹ thuật | Giá trị cam kết | Ghi chú vận hành |
| :--- | :--- | :--- |
| **Giao thức Streaming hỗ trợ** | **WebRTC, RTSP, HLS, SRT, RTMP** | Giải mã tự động chuẩn nén H.264, H.265/HEVC, AV1 |
| **Mật độ luồng trên mỗi GPU** | **24 – 32 luồng 1080p @ 25-30fps** | Vận hành an toàn trên NVIDIA RTX 4090 hoặc NVIDIA L4 (24GB VRAM) |
| **Thời gian xử lý khung hình (Latency)** | $\le \mathbf{75\text{ ms/frame}}$ | Tính từ lúc nhận frame $\rightarrow$ NVDEC decode $\rightarrow$ AI $\rightarrow$ JSON kết quả |
| **Độ chính xác nhận diện 100% biển số** | $\ge \mathbf{96.5\%}$ (RTSP/SRT), $\ge \mathbf{92.0\%}$ (HLS/WebRTC 4G) | Đã kiểm thử trên tập dữ liệu phương tiện thực tế tại Việt Nam |
| **Thời gian bù trễ & Phục hồi kết nối** | $\le \mathbf{3\text{ giây}}$ | Tự động chuyển luồng dự phòng và tự động khôi phục luồng bị đứt |
| **Khả năng bám vết & Chống đọc trùng** | ByteTrack $100\%$ không bỏ sót xe | Mỗi xe qua vùng bẫy ảo chỉ kích hoạt đọc biển 1 lần duy nhất |

---

## 🛠️ NGĂN XẾP CÔNG NGHỆ CHỦ CHỐT (CORE TECH STACK)

- **Streaming Ingestion & Transcoding:** GStreamer 1.24, MediaMTX, LiveKit WebRTC SFU, Coturn (STUN/TURN), NVIDIA NVDEC / DeepStream SDK.
- **AI & Deep Learning:** PyTorch, TensorRT 10.x, YOLOv11 (Vehicle Tracking), YOLOv11-Pose (4-Corner Plate Keypoint), PP-OCRv4 / CRNN-CTC.
- **Backend & Microservices:** Golang, Python 3.11 (FastAPI), NGINX Reverse Proxy, Docker, Kubernetes.
- **Data & Storage:** PostgreSQL 16 + TimescaleDB (Timeseries Hypertable), Redis 7 (In-Memory Whitelist/Blacklist), MinIO / S3.
- **Frontend Dashboard:** React.js / Vue 3, Tailwind CSS, WebRTC Player / HLS.js.

---
*Bản quyền tài liệu kỹ thuật thuộc về Nhóm Kiến trúc Hệ thống ITS & Video Streaming Pipeline.*