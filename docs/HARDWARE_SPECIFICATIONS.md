# ĐẶC TẢ HẠ TẦNG PHẦN CỨNG & MẠNG THU NHẬN STREAMING
## HỆ THỐNG ĐẾM VÀ ĐO TỐC ĐỘ PHƯƠNG TIỆN GIAO THÔNG TỪ LUỒNG VIDEO STREAMING
### (HARDWARE, GPU TRANSCODING & STREAMING INFRASTRUCTURE SPECIFICATIONS)
**Phiên bản:** 2.0.0 (Cập nhật Toàn diện Bài toán Đếm Xe & Đo Tốc độ)  
**Tác giả:** Đội ngũ Kỹ sư Hạ tầng Điện toán Đám mây & Streaming Media ITS

---

## 1. MÁY CHỦ THU NHẬN & XỬ LÝ AI TẬP TRUNG (STREAMING INGESTION & GPU SERVERS)

Khi đầu vào là các luồng video streaming (RTSP, WebRTC, HLS, SRT), trung tâm xử lý được thiết kế theo mô hình **Hạ tầng Cụm Máy chủ Đồ họa Tập trung (Centralized GPU Server Cluster)** đặt tại Trung tâm Điều hành Giao thông (TMC) hoặc Data Center.

### 1.1. Cấu hình Máy chủ Xử lý Chuẩn (2U Rackmount GPU Ingestion Server)
Mỗi máy chủ tiêu chuẩn được thiết kế để tiếp nhận, phân loại xe, đếm lưu lượng và đo tốc độ đồng thời cho **20 đến 32 luồng streaming Full HD 1080p @ 25-30 fps**:

| Thành phần phần cứng | Thông số kỹ thuật chi tiết | Vai trò & Mục đích sử dụng |
| :--- | :--- | :--- |
| **Bộ vi xử lý (CPU)** | 2x AMD EPYC 7763 (64 Cores, 128 Threads) hoặc 2x Intel Xeon Gold 6430 | Quản lý kết nối mạng đa luồng, xử lý giao thức WebRTC/HLS/SRT, chạy API Gateway. |
| **Bộ nhớ trong (RAM)** | 128GB DDR4-3200MHz ECC Registered (hoặc DDR5) | Bộ đệm RAM cho video stream de-jitter ring buffer và cơ sở dữ liệu in-memory Redis. |
| **Card đồ họa chuyên dụng (GPU)** | **1x hoặc 2x NVIDIA RTX 4090 24GB** (On-premise tối ưu chi phí) hoặc **NVIDIA L4 / A10 24GB** (Data Center chuẩn Enterprise) | Tận dụng bộ giải mã phần cứng kép **NVDEC** để decode 20-32 luồng H.264/H.265 cùng lúc và chạy mô hình YOLOv11 TensorRT FP16/INT8. |
| **Giao diện mạng (NIC)** | 2x 10Gbps SFP+ Intel X520 / Mellanox ConnectX-5 (Hỗ trợ LACP Teaming) | Đảm bảo băng thông tiếp nhận hàng trăm luồng video cùng lúc không bị nghẽn mạng. |
| **Ổ cứng lưu trữ hệ thống** | 2x 960GB NVMe SSD (M.2 / U.2, PCIe 4.0, cấu hình RAID 1) | Chạy hệ điều hành Linux Ubuntu 22.04, Docker runtime và ghi log hệ thống tốc độ cao. |
| **Ổ cứng đệm video & bằng chứng** | 4x 3.84TB Enterprise NVMe SSD (U.2, PCIe 4.0, cấu hình RAID 10) | Ghi đệm vòng các đoạn video clip bằng chứng 6 giây (MP4) phương tiện chạy quá tốc độ trước khi đẩy lên MinIO S3. |
| **Bộ nguồn dự phòng (PSU)** | Bộ nguồn kép dự phòng Redundant 2x 1600W (80 Plus Platinum) | Đảm bảo máy chủ hoạt động liên tục khi 1 nhánh điện nguồn gặp sự cố. |

---

### 1.2. Năng lực Giải mã Phần cứng & Tính toán AI của GPU (GPU Dimensioning)

NVIDIA cung cấp bộ xử lý giải mã chuyên dụng độc lập mang tên **NVDEC** (NVIDIA Video Decoder) nằm riêng biệt trên đế silicon, hoàn toàn không chiếm dụng nhân CUDA xử lý đồ họa:

```
[Băng thông mạng 10Gbps] ──► [NVDEC Hardware Decoder] ──► [VRAM (Zero-Copy Frame)]
                                                                  │
                                 ┌────────────────────────────────┘
                                 ▼
                     [Tensor Cores (FP16 / INT8)]
                     - YOLOv11 Vehicle Detection (8 Classes)
                     - ByteTrack Multi-Object Tracking
                     - Vectorized Homography Matrix & Line-Crossing
```

#### Ma trận năng lực xử lý của các dòng GPU phổ biến:

| Model GPU | Dung lượng VRAM | Số bộ giải mã NVDEC | Khả năng Decode 1080p @ 30fps | Số luồng AI Streaming tối đa |
| :--- | :--- | :--- | :--- | :--- |
| **NVIDIA Jetson Orin NX (16GB)** | 16GB LPDDR5 (Chia sẻ) | 1x NVDEC (H.265/H.264) | 4 - 6 luồng 1080p | **4 luồng** (Triển khai biên tại ngã tư) |
| **NVIDIA RTX 4060 Ti (16GB)** | 16GB GDDR6 | 1x NVDEC thế hệ 8 | 12 - 16 luồng 1080p | **8 - 12 luồng** (Trạm vệ tinh) |
| **NVIDIA RTX 4090 (24GB)** | 24GB GDDR6X | 2x NVDEC thế hệ 8 | 28 - 36 luồng 1080p | **20 - 32 luồng** (Tối ưu hiệu năng/chi phí) |
| **NVIDIA L4 (24GB)** | 24GB GDDR6 | 4x NVDEC thế hệ 8 | 48 - 60 luồng 1080p | **30 - 40 luồng** (Khuyên dùng Data Center) |
| **NVIDIA A100 / H100 (80GB)** | 80GB HBM2e | 5x NVDEC | 80 - 100 luồng 1080p | **60 - 80 luồng** (Hệ thống cấp Quốc gia) |

---

## 2. HẠ TẦNG NGUỒN PHÁT STREAMING (EDGE ENCODERS & CAMERAS)

Hệ thống tiếp nhận video từ 3 nhóm thiết bị phát luồng chính:
1. **Camera IP Cố định qua RTSP & SRT:** Lắp đặt trên giá long môn (gantry) hoặc cột camera giao thông nhìn xiên góc đường. Chuẩn nén H.264/H.265, Bitrate $2.5 - 4.0\text{ Mbps}$, GOP cố định $1 - 2\text{ giây}$.
2. **Thiết bị Di động & Flycam qua WebRTC (WHIP):** Tiếp nhận luồng video siêu độ trễ thấp ($< 300\text{ ms}$) hỗ trợ đo kiểm tốc độ lưu động.
3. **Cổng Thông tin Giao thông HLS:** Kết nối luồng công cộng `.m3u8` phục vụ đếm lưu lượng và giám sát mật độ giao thông đô thị.

---

## 3. TÍNH TOÁN BĂNG THÔNG MẠNG & DUNG LƯỢNG LƯU TRỮ (STORAGE SIZING)

Khác với hệ thống nhận diện biển số phải lưu ảnh chụp mọi xe, hệ thống Đếm và Đo tốc độ chỉ lưu trữ ảnh snapshot và clip 6s cho các phương tiện **VI PHẠM QUÁ TỐC ĐỘ** (thường chiếm khoảng $3\% - 5\%$ tổng lưu lượng xe). Đối với các xe bình thường, hệ thống chỉ lưu chuỗi metadata số liệu (lưu lượng, loại xe, vận tốc) vào TimescaleDB, giúp tiết kiệm tới **$95\%$ dung lượng lưu trữ**.

### Bảng Tính Dung lượng Lưu trữ Video Bằng chứng Vi phạm Quá tốc độ:
*Giả định: Mỗi luồng stream có $10.000\text{ lượt xe/ngày}$, tỷ lệ chạy quá tốc độ là $3\%$ ($300\text{ xe vi phạm/ngày}$). Mỗi vi phạm lưu: Ảnh snapshot ($150\text{ KB}$) + Đoạn clip 6s MP4 ($2.5\text{ MB}$) $\approx \mathbf{2.65\text{ MB/vi phạm}}$.*

| Thời gian lưu trữ | 10 Luồng Stream (3.000 vi phạm/ngày) | 50 Luồng Stream (15.000 vi phạm/ngày) | 100 Luồng Stream (30.000 vi phạm/ngày) |
| :--- | :--- | :--- | :--- |
| **1 Ngày** | $7.95\text{ GB}$ | $39.75\text{ GB}$ | $79.5\text{ GB}$ |
| **30 Ngày (1 Tháng)** | $238.5\text{ GB}$ | $1.19\text{ TB}$ | $2.38\text{ TB}$ |
| **90 Ngày (3 Tháng)** | $715.5\text{ GB}$ | $3.57\text{ TB}$ | $7.14\text{ TB}$ |
| **365 Ngày (1 Năm)** | **$2.90\text{ TB}$** | **$14.5\text{ TB}$** | **$29.0\text{ TB}$** |

---
*Bản quyền tài liệu kỹ thuật thuộc về Nhóm Kỹ sư Hạ tầng ITS 2026.*
