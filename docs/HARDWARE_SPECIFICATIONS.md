# ĐẶC TẢ HẠ TẦNG PHẦN CỨNG & MẠNG THU NHẬN STREAMING
## HỆ THỐNG NHẬN DIỆN BIỂN SỐ XE TỪ LUỒNG VIDEO STREAMING ĐA GIAO THỨC
### (HARDWARE, GPU TRANSCODING & STREAMING INFRASTRUCTURE SPECIFICATIONS)
**Phiên bản:** 2.0.0  
**Tác giả:** Đội ngũ Kỹ sư Hạ tầng Điện toán Đám mây & Streaming Media ITS

---

## 1. MÁY CHỦ THU NHẬN & XỬ LÝ AI TẬP TRUNG (STREAMING INGESTION & GPU SERVERS)

Khi đầu vào là các luồng video streaming (HLS, WebRTC, RTSP, SRT), trung tâm xử lý chuyển đổi từ các máy tính nhúng đơn lẻ tại cổng sang **Hạ tầng Cụm Máy chủ Đồ họa tập trung (Centralized GPU Server Cluster)** đặt tại Trung tâm Dữ liệu (Data Center) hoặc Phòng Điều hành Giao thông (Traffic Management Center - TMC).

### 1.1. Cấu hình Máy chủ Xử lý Chuẩn (2U Rackmount GPU Ingestion Server)
Mỗi máy chủ tiêu chuẩn được thiết kế để tiếp nhận và nhận diện biển số đồng thời cho **24 đến 32 luồng streaming Full HD 1080p @ 25-30 fps**:

| Thành phần phần cứng | Thông số kỹ thuật chi tiết | Vai trò & Mục đích sử dụng |
| :--- | :--- | :--- |
| **Bộ vi xử lý (CPU)** | 2x AMD EPYC 7763 (64 Cores, 128 Threads, 2.45GHz) hoặc 2x Intel Xeon Gold 6430 | Quản lý kết nối mạng đa luồng, xử lý giao thức WebRTC/HLS/SRT, chạy API Gateway. |
| **Bộ nhớ trong (RAM)** | 128GB DDR4-3200MHz ECC Registered (hoặc DDR5) | Bộ đệm RAM cho video stream de-jitter ring buffer và cơ sở dữ liệu in-memory Redis. |
| **Card đồ họa chuyên dụng (GPU)** | **1x hoặc 2x NVIDIA RTX 4090 24GB** (Dành cho On-premise tối ưu chi phí) hoặc **NVIDIA L4 / A10 24GB** (Dành cho Data Center chuẩn Enterprise) | Tận dụng bộ giải mã phần cứng kép **NVDEC** để decode 24-32 luồng H.264/H.265 cùng lúc và chạy mô hình TensorRT FP16/INT8. |
| **Giao diện mạng (NIC)** | 2x 10Gbps SFP+ Intel X520 / Mellanox ConnectX-5 (Hỗ trợ LACP Teaming) | Đảm bảo băng thông tiếp nhận hàng trăm luồng video cùng lúc không bị nghẽn mạng. |
| **Ổ cứng lưu trữ hệ thống** | 2x 960GB NVMe SSD (M.2 / U.2, PCIe 4.0, cấu hình RAID 1) | Chạy hệ điều hành Linux Ubuntu 22.04, Docker runtime và ghi log hệ thống tốc độ cao. |
| **Ổ cứng đệm video & bằng chứng** | 4x 3.84TB Enterprise NVMe SSD (U.2, PCIe 4.0, cấu hình RAID 10) | Ghi đệm vòng các đoạn video clip bằng chứng 6 giây (MP4) và ảnh crop độ nét cao trước khi đẩy lên MinIO S3. |
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
                     - YOLOv11 Vehicle Tracking
                     - YOLOv11-Pose Plate Localization
                     - PP-OCRv4 Character Recognition
```

#### Ma trận năng lực xử lý của các dòng GPU phổ biến:

| Model GPU | Dung lượng VRAM | Số bộ giải mã NVDEC | Khả năng Decode 1080p @ 30fps | Số luồng AI Streaming tối đa |
| :--- | :--- | :--- | :--- | :--- |
| **NVIDIA Jetson Orin NX (16GB)** | 16GB LPDDR5 (Chia sẻ) | 1x NVDEC (H.265/H.264) | 4 - 6 luồng 1080p | **4 luồng** (Triển khai biên) |
| **NVIDIA RTX 4060 Ti (16GB)** | 16GB GDDR6 | 1x NVDEC thế hệ 8 | 12 - 16 luồng 1080p | **8 - 12 luồng** (Trạm vệ tinh) |
| **NVIDIA RTX 4090 (24GB)** | 24GB GDDR6X | 2x NVDEC thế hệ 8 | 28 - 36 luồng 1080p | **24 - 30 luồng** (Tối ưu chi phí) |
| **NVIDIA L4 (24GB)** | 24GB GDDR6 | 4x NVDEC thế hệ 8 | 48 - 60 luồng 1080p | **32 - 40 luồng** (Khuyên dùng Data Center) |
| **NVIDIA A100 / H100 (80GB)** | 80GB HBM2e | 5x NVDEC | 80 - 100 luồng 1080p | **60 - 80 luồng** (Hệ thống cấp Quốc gia) |

*Nguyên tắc định kích cỡ an toàn:* Để hệ thống vận hành bền bỉ 24/7/365, luôn duy trì mức tải GPU và VRAM ở ngưỡng **$\le 75\%$**, dành $25\%$ dự phòng cho các khung giờ cao điểm khi mật độ xe dày đặc.

---

## 2. HẠ TẦNG NGUỒN PHÁT STREAMING (EDGE ENCODERS & CAMERAS)

Hệ thống tiếp nhận video từ 3 nhóm thiết bị phát luồng chính:

### 2.1. Nhóm 1: Camera Cố định qua RTSP & SRT (Fixed Roadside Cameras)
- **Thiết bị:** Camera IP chuyên dụng giao thông (Axis, Hanwha Vision, Hikvision, Dahua).
- **Chuẩn giao thức xuất:**
  - RTSP qua TCP port 554 (Mạng LAN nội bộ).
  - SRT Caller mode (qua mạng Internet công cộng đến máy chủ trung tâm với địa chỉ IP tĩnh/Domain).
- **Mã hóa:** H.264 Main Profile hoặc H.265 Main Profile; Bitrate khuyến nghị từ $2.5\text{ Mbps}$ đến $4.0\text{ Mbps}$ cho độ phân giải 1080p.
- **Tính năng bắt buộc:** Hỗ trợ đặt khóa khung hình (GOP - Group of Pictures) cố định, $\text{GOP} = 1\times$ hoặc $2\times \text{FPS}$ (khoảng cách giữa các I-frame là $1 - 2\text{ giây}$) giúp bộ giải mã khôi phục hình ảnh nhanh chóng nếu bị mất kết nối.

### 2.2. Nhóm 2: Thiết bị Di động Tuần tra qua WebRTC (Mobile Patrol & Drone Streams)
- **Thiết bị:** Camera hành trình 4G/5G chuyên dụng, Smartphone của CSGT, hoặc Bộ mã hóa ba-lô di động (LiveU / Kiloview P-Series) gắn SIM 5G đa nhà mạng (Bonding).
- **Giao thức truyền tải:** **WebRTC via WHIP (RFC draft-ietf-wish-whip)**.
- **Hạ tầng hỗ trợ NAT Traversal (Bắt buộc cho WebRTC di động):**
  - **Máy chủ STUN/TURN (Coturn):** Đặt tại Data Center có IP tĩnh công cộng, hỗ trợ giao thức TURN over TLS (TURNS port 443) để vượt qua tường lửa nghiêm ngặt của mạng di động Viettel, VinaPhone, MobiFone.
  - Bộ đệm tương thích thích nghi (Dynamic Bitrate Adaptation): Tự động giảm độ phân giải xuống 720p khi xe đi vào vùng sóng 4G yếu, tự động phục hồi 1080p khi vào vùng sóng 5G khỏe.

### 2.3. Nhóm 3: Luồng Phân phối Công cộng HLS / LL-HLS (City Traffic Portals)
- **Nguồn phát:** CDN Akamai, Cloudflare, hoặc VNPT CDN phân phối luồng camera ngã tư đô thị.
- **Định dạng luồng:**
  - File danh sách phát: `.m3u8` Playlist (HLS Version 3 hoặc HLS Version 7 hỗ trợ fMP4).
  - Thời lượng phân đoạn (Chunk Duration): $1.0\text{ giây} - 2.0\text{ giây}$ (Low-Latency HLS) hoặc $2.0 - 4.0\text{ giây}$ (Standard HLS).

---

## 3. TÍNH TOÁN BĂNG THÔNG MẠNG & THÔNG LƯỢNG TIẾP NHẬN (BANDWIDTH SIZING)

Hạ tầng mạng tại Trung tâm Dữ liệu phải được thiết kế đáp ứng đủ lưu lượng tải xuống (Ingress Traffic) liên tục cho các quy mô hệ thống:

### 3.1. Bảng Tính Băng thông Mạng Tiếp nhận (Ingress Network Bandwidth)
*Giả định: Mỗi luồng video 1080p nén chuẩn H.264/H.265 có bitrate trung bình là $3.0\text{ Mbps}$ ($375\text{ KB/s}$)*.

| Quy mô hệ thống | Số lượng luồng Stream đồng thời | Băng thông Ingress liên tục (Mbps) | Băng thông Ingress liên tục (MB/s) | Yêu cầu Card mạng (NIC) |
| :--- | :--- | :--- | :--- | :--- |
| **Quy mô Nhỏ** | 10 Luồng (1 bãi xe lớn / 5 xe tuần tra) | $30\text{ Mbps}$ | $3.75\text{ MB/s}$ | 1x 1Gbps Ethernet |
| **Quy mô Trung bình** | 50 Luồng (Khu đô thị thông minh) | $150\text{ Mbps}$ | $18.75\text{ MB/s}$ | 1x 1Gbps Ethernet chuyên dụng |
| **Quy mô Lớn** | 100 Luồng (Quận trung tâm thành phố) | $300\text{ Mbps}$ | $37.5\text{ MB/s}$ | 2x 1Gbps LACP Teaming |
| **Quy mô Đô thị (Metro)** | 250 Luồng (Giám sát toàn thành phố) | $750\text{ Mbps}$ | $93.75\text{ MB/s}$ | **1x 10Gbps SFP+** |
| **Quy mô Quốc gia** | 1.000 Luồng (Tuyến cao tốc liên tỉnh) | **$3.0\text{ Gbps}$** | $375.0\text{ MB/s}$ | **2x 10Gbps SFP+ (Bonding)** |

---

### 3.2. Bảng Tính Dung lượng Lưu trữ Video Bằng chứng & Ảnh Biển số (Storage Capacity)
*Giả định: Mỗi luồng stream ghi nhận trung bình $2.000\text{ lượt xe/ngày}$. Với mỗi xe, hệ thống lưu: Ảnh crop biển số ($20\text{ KB}$) + Ảnh ngữ cảnh ($80\text{ KB}$) + Đoạn video clip 6 giây MP4 ($2.5\text{ MB}$) $\approx \mathbf{2.6\text{ MB/sự kiện}}$.*

| Thời gian lưu trữ | 10 Luồng Stream (20.000 xe/ngày) | 50 Luồng Stream (100.000 xe/ngày) | 100 Luồng Stream (200.000 xe/ngày) |
| :--- | :--- | :--- | :--- |
| **1 Ngày** | $52\text{ GB}$ | $260\text{ GB}$ | $520\text{ GB}$ |
| **30 Ngày (1 Tháng)** | $1.56\text{ TB}$ | $7.8\text{ TB}$ | $15.6\text{ TB}$ |
| **90 Ngày (3 Tháng)** | $4.68\text{ TB}$ | $23.4\text{ TB}$ | $46.8\text{ TB}$ |
| **365 Ngày (1 Năm)** | **$18.98\text{ TB}$** | **$94.9\text{ TB}$** | **$189.8\text{ TB}$** |

#### Chiến lược tối ưu hóa chi phí lưu trữ (Storage Tiering Strategy):
1. **Lớp 0 - Ring Buffer trên RAM/NVMe:** Duy trì $6\text{ giây}$ video gần nhất của mọi luồng stream trong bộ nhớ đệm xoay vòng. Nếu không có phương tiện hoặc không có vi phạm, dữ liệu cũ bị ghi đè tự động mà không ghi xuống ổ cứng.
2. **Lớp 1 - Hot Storage (NVMe / SSD):** Chỉ khi xe kích hoạt bẫy ảo và nhận diện biển số, đoạn clip $6\text{ giây}$ cùng ảnh snapshot mới được ghi xuống ổ cứng NVMe để truy xuất trong vòng $15\text{ ngày}$.
3. **Lớp 2 - Warm/Cold Storage (Ceph / MinIO / AWS S3 Glacier):** Sau 30 ngày, hệ thống nén lại video clip với chuẩn H.265 CRF 28 (giảm 60% dung lượng) và chuyển sang kho lưu trữ đám mây chi phí thấp để phục vụ đối chiếu pháp lý khi cần.

---

## 4. SƠ ĐỒ ĐẤU NỐI HẠ TẦNG MẠNG & PHÂN LUỒNG TẬP TRUNG (NETWORK TOPOLOGY)

```
                            INTERNET & MẠNG DI ĐỘNG 4G/5G
                                          │
       ┌──────────────────────────────────┼──────────────────────────────────┐
       │ (WebRTC WHIP / SRTP)             │ (HLS HTTPS .m3u8)                │ (SRT / RTSPS)
       ▼                                  ▼                                  ▼
[Xe Tuần tra CSGT / Drone]     [Cổng GT Đô thị CDN]           [Camera Trạm Thu phí]
       │                                  │                                  │
       └──────────────────────────────────┼──────────────────────────────────┘
                                          │
                                          v
                   +-----------------------------------------------+
                   |     Tường lửa Bảo mật (Next-Gen Firewall)     |
                   |   (Cân bằng tải & Chống DDoS Cloudflare)      |
                   +----------------------+------------------------+
                                          │
               +--------------------------+--------------------------+
               │ 10Gbps SFP+                                         │ 10Gbps SFP+
               v                                                     v
   +-----------------------+                             +-----------------------+
   |  Coturn STUN/TURN Svc |                             | Reverse Proxy / NGINX |
   |  (NAT Traversal Hub)  |                             | (HLS / WHIP Endpoint) |
   +-----------+-----------+                             +-----------+-----------+
               │                                                     │
               └──────────────────────────┬──────────────────────────┘
                                          v
                      +---------------------------------------+
                      |   Cụm Máy chủ Ingestion & GPU AI      |
                      |   - Worker 1 (NVIDIA RTX 4090 / L4)   |
                      |   - Worker 2 (NVIDIA RTX 4090 / L4)   |
                      +-------------------+-------------------+
                                          │
                       ┌──────────────────┴──────────────────┐
                       v                                     v
         +---------------------------+         +---------------------------+
         | Cơ sở dữ liệu Chuỗi T/G   |         | Kho Lưu trữ Bằng chứng    |
         | (PostgreSQL 16 + Redis)   |         | (MinIO / S3 Object Store) |
         +---------------------------+         +---------------------------+
```

Kiến trúc hạ tầng mạng này đảm bảo tính co giãn linh hoạt (Elastic Scalability), cho phép bổ sung thêm card GPU hoặc máy chủ Worker mới trong vòng chưa đầy 10 phút mà không cần gián đoạn bất kỳ luồng streaming nào đang vận hành.

---

## 5. ĐẶC TẢ PHẦN CỨNG MÁY CLIENT & ĐÁNH GIÁ HIỆU NĂNG CHỐNG LAG (CLIENT EDGE HARDWARE & ANTI-LAG SPECS)

Khi mô hình được huấn luyện xong trên Google Colab và tải về chạy trực tiếp trên các máy client (máy trạm cabin kiểm soát bãi xe, cổng trạm thu phí hoặc laptop giám sát), hiệu năng và khả năng chống lag được phân định theo 3 profile phần cứng:

### 5.1. Bảng Phân Tích Cấu Hình Phần Cứng & Độ Trễ Máy Client

| Profile Máy Client | Cấu hình phần cứng tiêu biểu | Runtime & Bộ tăng tốc | Tốc độ xử lý (FPS) | Độ trễ suy luận AI | Đánh giá hiện tượng LAG |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Profile A (GPU Client):**<br>Máy trạm có GPU rời | CPU Intel i5/i7 + **NVIDIA RTX 3050 / 4060 / GTX 1660** (6GB - 8GB VRAM) | **NVIDIA TensorRT FP16** | **$60 - 120+\text{ FPS}$** | **$\mathbf{8 - 15\text{ ms}}$** | **KHÔNG LAG (0% Lag)**<br>Chạy mượt 4 - 8 camera đồng thời. |
| **Profile B (Edge AI Box):**<br>Máy tính nhúng công nghiệp | **NVIDIA Jetson Orin Nano (8GB) / Orin NX (16GB)** (Thiết kế Fanless $15\text{W}$) | **TensorRT FP16 / INT8** | **$35 - 55\text{ FPS}$** | **$\mathbf{20 - 32\text{ ms}}$** | **KHÔNG LAG (0% Lag)**<br>Chuyên dụng 24/7 ngoài trời. |
| **Profile C (Intel CPU Client):**<br>Mini-PC / Laptop văn phòng | **Intel Core i5 Gen 11/12/13** (Iris Xe Graphics / UHD 770, 16GB RAM) | **Intel OpenVINO INT8** | **$25 - 32\text{ FPS}$** | **$\mathbf{32 - 45\text{ ms}}$** | **KHÔNG LAG** nếu dùng Adaptive Sampler ($10\text{ fps}$). |
| **Profile D (Low-end CPU):**<br>Máy văn phòng cấu hình cũ | Intel Core i3 Gen 8/9 / Celeron N5095 / N100 (8GB RAM) | OpenVINO FP32 / CPU | $8 - 12\text{ FPS}$ | $85 - 120\text{ ms}$ | **CÓ NGUY CƠ LAG** nếu chạy 100% frame 30fps. Cần cấu hình hạ tốc độ lấy mẫu xuống 6-8 fps. |

### 5.2. Ba Nguyên Lý Triệt Tiêu Lag Khung Hình trên Máy Client:
1. **Tiến trình Đọc Luồng Bất Đồng Bộ (Decoupled Non-blocking Reader):** Tách luồng nhận video RTSP/WebRTC sang một Thread riêng biệt. Hàng đợi đệm chỉ có kích thước `maxsize=1`. Nếu AI đang bận xử lý, frame cũ bị tự động loại bỏ (Drop old frame), đảm bảo khung hình đưa vào AI luôn là khung hình mới nhất ở thời gian thực.
2. **Lấy Mẫu Thích Nghi (Adaptive Sampler - 10 FPS):** Mắt người và bám vết xe chỉ cần $10\text{ fps}$ để theo dõi quỹ đạo phương tiện. Giảm tần số suy luận từ $30\text{ fps} \rightarrow 10\text{ fps}$ giúp giảm tải $66\%$ CPU của máy client mà không làm giảm độ chính xác.
3. **Kích Hoạt OCR theo Bẫy Ảo (Trigger-based OCR):** Chỉ thực hiện OCR khi phương tiện cắt qua vạch bẫy ảo và đạt điểm độ nét cao nhất. Khối OCR không chạy liên tục trên mọi frame rác.