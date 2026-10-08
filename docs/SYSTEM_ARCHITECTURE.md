# TÀI LIỆU THIẾT KẾ KIẾN TRÚC HỆ THỐNG (SYSTEM ARCHITECTURE)
## HỆ THỐNG ĐẾM VÀ ĐO TỐC ĐỘ PHƯƠNG TIỆN GIAO THÔNG TỪ LUỒNG VIDEO STREAMING ĐA GIAO THỨC
### (MULTI-PROTOCOL STREAMING VEHICLE COUNTING & SPEED ESTIMATION: RTSP, WEBRTC, HLS, SRT, RTMP)
**Phiên bản:** 2.0.0  
**Tác giả:** Đội ngũ Kiến trúc sư Hệ thống ITS & Video Streaming Pipeline

---

## 1. TỔNG QUAN KIẾN TRÚC HỆ THỐNG (HIGH-LEVEL STREAMING ARCHITECTURE)

Hệ thống được thiết kế theo mô hình **Kiến trúc Thu nhận và Xử lý Luồng Đa tầng (Multi-tier Stream Ingestion & Processing Architecture)**. Hệ thống tách biệt hoàn toàn giữa tầng thu nhận video mạng (Network Streaming Gateway), tầng giải mã phần cứng không sao chép (Zero-copy Hardware Decoding), tầng suy luận AI & Đo tốc độ (AI Inference, Tracking & Speed Engine) và tầng dịch vụ nghiệp vụ & lưu trữ chuỗi thời gian (Time-series Core Services & Storage).

```
+-----------------------------------------------------------------------------------------------------------------------+
|                                        CÁC NGUỒN PHÁT VIDEO STREAMING ĐẦU VÀO                                         |
|                                                                                                                       |
|   +-----------------------+     +-----------------------+     +-----------------------+     +----------------------+  |
|   |  Camera IP Cố định    |     |  Flycam / Di động     |     |  Cổng GT Đô thị (CDN) |     |  Trạm xa lộ / Cao tốc|  |
|   |  RTSP (H.264 / H.265) |     |  WebRTC (WHIP / SRTP) |     |  HLS / LL-HLS (.m3u8) |     |  SRT / RTMP Stream   |  |
|   +-----------+-----------+     +-----------+-----------+     +-----------+-----------+     +----------+-----------+  |
+---------------|-----------------------------|-----------------------------|----------------------------|--------------+
                |                             |                             |                            |
                v                             v                             v                            v
+-----------------------------------------------------------------------------------------------------------------------+
|                         TẦNG CỔNG THU NHẬN LUỒNG PHÂN TÁN (STREAM INGESTION GATEWAY LAYER)                            |
|                                                                                                                       |
|   +---------------------------------------------------------------------------------------------------------------+   |
|   | MediaMTX / GStreamer 1.24 Ingestion Workers / LiveKit WebRTC SFU Server                                       |   |
|   | - Session Manager: Quản lý vòng đời kết nối từng luồng, cơ chế Auto-Reconnect (Exponential Backoff)           |   |
|   | - Demuxer Engine: Bóc tách gói tin RTP, MPEG-TS, fMP4 Chunks, SRT Packets                                     |   |
|   | - De-jitter Ring Buffer: Triệt tiêu trễ mạng thất thường, ổn định Presentation Timestamp (PTS) cho đo tốc độ  |   |
|   +-------------------------------------------------------+-------------------------------------------------------+   |
+-----------------------------------------------------------|-----------------------------------------------------------+
                                                            | Raw Bitstream Packets (H.264 / H.265 / AV1)
                                                            v
+-----------------------------------------------------------------------------------------------------------------------+
|                       TẦNG GIẢI MÃ PHẦN CỨNG & XỬ LÝ KHUNG HÌNH (HARDWARE ACCELERATED PIPELINE)                       |
|                                                                                                                       |
|   +---------------------------------------------------------------------------------------------------------------+   |
|   | NVIDIA DeepStream SDK / NVDEC (Hardware Video Decoder - CUVID)                                                |   |
|   | - Giải mã phần cứng trực tiếp vào bộ nhớ GPU VRAM (Zero-Copy Host RAM to Device VRAM)                         |   |
|   | - Adaptive Frame Sampler: Lấy mẫu FPS ổn định phục vụ tính thời gian di chuyển delta-t                            |   |
|   | - Pre/Post-event Ring Buffer: Đệm sẵn 6 giây video (30fps) để tự động xuất clip bằng chứng khi xe chạy quá tốc độ|   |
|   +-------------------------------------------------------+-------------------------------------------------------+   |
+-----------------------------------------------------------|-----------------------------------------------------------+
                                                            | Tensors trong GPU VRAM (NV12 / FP32 RGB Tensors)
                                                            v
+-----------------------------------------------------------------------------------------------------------------------+
|                     TẦNG SUY LUẬN AI, BÁM VẾT & ĐO TỐC ĐỘ (AI INFERENCE, TRACKING & SPEED ENGINE)                     |
|                                                                                                                       |
|   +---------------------+   +---------------------+   +---------------------+   +---------------------+               |
|   | 1. Phát hiện xe     |   | 2. Bám vết đa đối   |   | 3. Điểm tiếp xúc    |   | 4. Vạch đếm ảo &    |               |
|   | YOLOv11 Detector    |-->| tượng (ByteTrack)   |-->| đáy bánh xe         |-->| Phân loại xe        |               |
|   | (8 nhóm xe VN)      |   | Gán duy nhất TrackID|   | (Bottom-Center pt)  |   | (Line-Crossing Count|               |
|   +---------------------+   +---------------------+   +----------+----------+   +---------------------+               |
|                                                                  |                                                    |
|                                                                  v                                                    |
|                                 +-----------------------------------------------------------------+                   |
|                                 | 5. Ma trận Biến đổi Phối cảnh & Đo Tốc độ (Homography Engine)   |                   |
|                                 | - Ánh xạ Pixel -> Tọa độ thực địa Mét: [X, Y, 1]^T = H * [x, y, 1]^T              |
|                                 | - Tính quãng đường d = sqrt(dX^2 + dY^2) / dt -> v (km/h)      |                   |
|                                 | - Bộ lọc Kalman Filter / EMA khử nhiễu rung lắc bounding box    |                   |
|                                 +--------------------------------+--------------------------------+                   |
|                                                                  |                                                    |
|                                                                  v                                                    |
|                                 +-----------------------------------------------------------------+                   |
|                                 | 6. Phát hiện Vi phạm Quá tốc độ & Cắt Clip Bằng chứng 6s        |                   |
|                                 | (Overspeed Trigger: v > Speed_Limit -> Lưu Snapshot & Video)    |                   |
|                                 +--------------------------------+--------------------------------+                   |
+------------------------------------------------------------------|----------------------------------------------------+
                                                                   | Metadata JSON + Violation Snapshot + 6s Clip MP4
                                                                   v
+-----------------------------------------------------------------------------------------------------------------------+
|                         TẦNG DỊCH VỤ NGHIỆP VỤ & LƯU TRỮ (TIME-SERIES SERVICES & STORAGE)                             |
|                                                                                                                       |
|   +--------------------+      +--------------------+      +--------------------+      +--------------------+          |
|   | Core Traffic Svc   |      | Speed Violation Svc|      | Traffic Analytics  |      | Live ITS Dashboard |          |
|   | (FastAPI / Golang) |      | (Telegram/Webhook) |      | (Lưu lượng & Heat) |      | (WebSockets / WSS) |          |
|   +---------+----------+      +---------+----------+      +---------+----------+      +---------+----------+          |
|             |                           |                           |                           |                     |
|             +---------------------------+-------------+-------------+---------------------------+                     |
|                                                       v                                                               |
|   +---------------------------------------------------------------------------------------------------------------+   |
|   | PostgreSQL 16 + TimescaleDB (Lưu chuỗi thời gian: Lưu lượng xe theo phút/giờ/làn, Vận tốc trung bình)          |   |
|   | Redis 7 (Bộ nhớ đệm Track ID đang hoạt động & Vận tốc tức thời thời gian thực < 1ms)                          |   |
|   | MinIO / AWS S3 (Lưu trữ ảnh snapshot vi phạm + video clip bằng chứng 6s MP4 có mã băm SHA-256)               |   |
|   +---------------------------------------------------------------------------------------------------------------+   |
+-----------------------------------------------------------------------------------------------------------------------+
```

---

## 2. CHI TIẾT CÁC PHÂN HỆ XỬ LÝ (CORE PIPELINE SUBSYSTEMS)

### 2.1. Phân hệ Tiếp nhận & Phân kênh Đa Giao thức (Multi-Protocol Ingestion Subsystem)
Hệ thống sử dụng lớp trừu tượng hóa thống nhất (Unified Stream Ingestor) xây dựng trên nền tảng **GStreamer 1.24** kết hợp với **NVIDIA DeepStream SDK**:
1. **RTSP (Real-Time Streaming Protocol):** Nhận luồng trực tiếp từ Camera IP giao thông, xử lý kết nối lại tự động qua `rtspsrc`.
2. **WebRTC (WHIP / SRTP):** Nhận luồng siêu độ trễ thấp ($< 300\text{ ms}$) từ Flycam hoặc thiết bị di động kiểm tra tốc độ lưu động.
3. **HLS / LL-HLS:** Tiếp nhận luồng công cộng từ các cổng giao thông đô thị, tự động bóc tách danh sách phát `.m3u8` và giải mã chuỗi phân đoạn `.ts` / `.m4s`.
4. **SRT (Secure Reliable Transport):** Đảm bảo truyền nhận video đường dài chất lượng cao qua Internet công cộng có tỷ lệ mất gói tin lên tới $10\%$.

---

### 2.2. Phân hệ Phát hiện & Bám vết Phương tiện (Detection & Tracking Subsystem)

#### 1. Mô hình YOLOv11 Vehicle Detector
- Phát hiện vị trí (Bounding Box) và phân loại 8 nhóm phương tiện phổ biến tại Việt Nam:
  `motorcycle`, `car`, `electric_bicycle`, `bicycle`, `bus`, `truck`, `container_truck`, `special_vehicle`.
- Được lượng hóa sang **TensorRT FP16 / INT8** để đạt tốc độ suy luận $\le 3.5\text{ ms}$ trên GPU NVIDIA.

#### 2. Thuật toán Bám vết Đa đối tượng ByteTrack
- Sử dụng thuật toán **ByteTrack** dựa trên Kalman Filter 8 chiều trạng thái:
  $$x = [u, v, s, r, \dot{u}, \dot{v}, \dot{s}, \dot{r}]^T$$
  trong đó $(u, v)$ là tọa độ tâm bbox, $s$ là diện tích, $r$ là tỷ lệ khung hình.
- Phối hợp liên kết detection cả mức tin cậy cao ($\text{score} \ge 0.5$) và mức tin cậy thấp ($0.1 \le \text{score} < 0.5$) để tránh mất dấu phương tiện khi bị che khuất một phần (Occlusion).
- Mỗi phương tiện được gán một `track_id` duy nhất trong suốt hành trình qua khung hình.

---

### 2.3. Giải thuật Đếm Lưu lượng theo Làn & Hướng (Line-Crossing Counting Engine)

```
             Hướng di chuyển (Vector V)
                     │
                     ▼
  [Frame t-1: P_pre] ───┐
                        │   (Vệt di chuyển cắt qua vạch ảo)
  ══════════════════════╪══════════════════════  [Vạch đếm ảo: AB]
                        │
   [Frame t: P_curr]  ──┘
```

1. **Điểm neo tọa độ xe (Anchor Point):**
   - Không sử dụng tâm hình học của bounding box vì chiều cao của xe tải/xe buýt rất lớn gây sai lệch vị trí tiếp đất do góc phối cảnh.
   - Sử dụng **Điểm chính giữa đáy bounding box (Bottom-Center)**:
     $$P(t) = \left( x_{\text{center}}, y_{\text{bottom}} \right) = \left( \frac{x_1 + x_2}{2}, y_2 \right)$$
     Điểm này đại diện chính xác cho vị trí bánh xe tiếp xúc với mặt đường.

2. **Thuật toán giao cắt đoạn thẳng (Line Intersection Test):**
   - Vạch ảo xác định bởi đoạn thẳng nối 2 điểm $A(x_A, y_A)$ và $B(x_B, y_B)$.
   - Vệt di chuyển của phương tiện xác định bởi đoạn thẳng nối vị trí trước đó $P(t-1)$ và vị trí hiện tại $P(t)$.
   - Sử dụng tích có hướng (Cross Product Orientation Test) để xác định điểm giao nhau và hướng di chuyển:
     $$\text{Side}(P, A, B) = (x_B - x_A)(y_P - y_A) - (y_B - y_A)(x_P - x_A)$$
   - Nếu $\text{Side}(P(t-1), A, B) \times \text{Side}(P(t), A, B) < 0$ và đoạn thẳng $P(t-1)P(t)$ cắt $AB$: Phương tiện đã vượt qua vạch đếm.
   - Căn cứ vào dấu của tích có hướng, hệ thống xác định hướng: **Hướng In (Đi tới)** hoặc **Hướng Out (Đi lùi)**.
   - Ghi nhận đếm và gán nhãn `counted = True` cho `track_id` để loại bỏ 100% hiện tượng đếm trùng.

---

### 2.4. Giải thuật Đo Tốc độ qua Ma trận Phối cảnh (Homography Speed Estimation Engine)

```
        MẶT PHẲNG ẢNH (CAMERA PIXELS)                 MẶT PHẲNG MẶT ĐƯỜNG THỰC ĐẾ (MÉT)
           (Phối cảnh biến dạng)                           (Góc nhìn chim bay - Bird's Eye View)
                   y
                   │                                               Y (mét)
              p1 ┌───┐ p2                                            │
                /     \                                     P1 ┌───────────┐ P2
               /       \         Ma trận Homography (H)        │           │
              /         \      ─────────────────────────►      │  d (mét)  │
             /           \                                     │           │
         p4 └─────────────┘ p3                              P4 └───────────┘ P3
          ────────────────► x                                 ────────────────► X (mét)
```

#### 1. Hiệu chuẩn Camera & Tính Ma trận Homography ($H$):
- Người dùng chọn 4 điểm mốc trên mặt đường trong ảnh camera: $p_1(x_1, y_1), p_2(x_2, y_2), p_3(x_3, y_3), p_4(x_4, y_4)$ (ví dụ: 4 góc của vạch kẻ đường hoặc 4 cọc tiêu chuẩn).
- Đo khoảng cách thực địa giữa 4 điểm này ngoài đời thực: $P_1(0, 0), P_2(W, 0), P_3(W, L), P_4(0, L)$ (đơn vị: mét).
- OpenCV tính ma trận $3 \times 3$ **Homography ($H$)**:
  $$H = \text{cv2.findHomography}(\text{pts\_src}, \text{pts\_dst})$$
  $$\begin{bmatrix} X' \\ Y' \\ Z' \end{bmatrix} = H \begin{bmatrix} x \\ y \\ 1 \end{bmatrix}, \quad X_{\text{world}} = \frac{X'}{Z'}, \quad Y_{\text{world}} = \frac{Y'}{Z'}$$

#### 2. Tính Quãng đường & Vận tốc tức thời:
- Với mỗi frame $t$, điểm tiếp xúc bánh xe $p_t(x, y)$ được chuyển thành tọa độ mét $P_t(X_t, Y_t)$.
- Để loại bỏ nhiễu rung lắc nhỏ giữa các frame sát nhau, hệ thống tính quãng đường qua khoảng cửa sổ thời gian $k$ frames ($k \approx 5 - 10$ frames, tương ứng $0.2 - 0.4\text{ giây}$):
  $$d = \sqrt{(X_t - X_{t-k})^2 + (Y_t - Y_{t-k})^2} \quad (\text{mét})$$
- Thời gian dịch chuyển $\Delta t$:
  $$\Delta t = \frac{k}{\text{FPS}} \quad (\text{giây})$$
- Vận tốc thô (Raw Velocity):
  $$v_{\text{raw}} = \frac{d}{\Delta t} \times 3.6 \quad (\text{km/h})$$

#### 3. Bộ lọc Khử nhiễu Vận tốc (Velocity Smoothing Filter):
- Để triệt tiêu dao động bất thường khi bounding box co giãn nhẹ, vận tốc ước tính được làm mượt bằng **Exponential Moving Average (EMA)**:
  $$v_{\text{smooth}}(t) = \alpha \cdot v_{\text{raw}}(t) + (1 - \alpha) \cdot v_{\text{smooth}}(t-1) \quad (\alpha = 0.35)$$
- Hoặc kết hợp bộ lọc **1D Kalman Filter** cập nhật trạng thái vận tốc của từng xe.

---

### 2.5. Cơ chế Phát hiện Vi phạm Quá tốc độ (Overspeed Capture & Evidence Pipeline)
1. Mỗi làn đường được gán một cấu hình `speed_limit` (ví dụ: $60\text{ km/h}$).
2. Khi $v_{\text{smooth}} > \text{speed\_limit}$:
   - Đánh dấu trạng thái xe là `VIOLATION_OVERSPEED`.
   - Chụp ảnh snapshot độ phân giải gốc 1080p, vẽ bounding box màu đỏ rực, đóng dấu watermark thời gian, tọa độ camera, mã Track ID và tốc độ vi phạm.
   - Kích hoạt Worker cắt video: Trích xuất chính xác 6 giây video MP4 (từ buffer video trước 3s và sau 3s) bằng NVDEC + NVENC phần cứng.
   - Đẩy metadata vi phạm vào CSDL và gửi tin nhắn cảnh báo tức thời qua Webhook / Telegram Bot.

---

## 3. THIẾT KẾ CƠ SỞ DỮ LIỆU CHUỖI THỜI GIAN (DATABASE SCHEMA)

Sử dụng **PostgreSQL 16** tích hợp extension **TimescaleDB** để quản lý hàng triệu bản ghi giao thông theo chuỗi thời gian siêu nhanh:

### Bảng 1: `video_streams` (Quản lý các luồng camera)
```sql
CREATE TABLE video_streams (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    stream_code VARCHAR(50) NOT NULL UNIQUE,       -- 'CAM_LANE_01_RTSP'
    stream_name VARCHAR(120) NOT NULL,             -- 'Camera Ngã Tư Hàng Xanh Làn 1'
    protocol VARCHAR(20) NOT NULL,                 -- 'RTSP', 'WEBRTC', 'HLS', 'SRT', 'RTMP'
    source_url TEXT NOT NULL,                      -- 'rtsp://192.168.1.100:554/stream1'
    fps NUMERIC(5, 2) DEFAULT 30.0,
    speed_limit NUMERIC(5, 1) DEFAULT 60.0,        -- Giới hạn tốc độ cho phép (km/h)
    homography_matrix JSONB NOT NULL,              -- Mảng 9 phần tử ma trận 3x3 H
    counting_lines JSONB NOT NULL,                 -- Danh sách vạch đếm [{"id": "line_1", "p1": [x,y], "p2": [x,y]}]
    status VARCHAR(20) DEFAULT 'ACTIVE',
    created_at TIMESTAMPTZ DEFAULT NOW()
);
```

### Bảng 2: `vehicle_detections` (Lưu thông tin phương tiện & đo tốc độ - TimescaleDB Hypertable)
```sql
CREATE TABLE vehicle_detections (
    time TIMESTAMPTZ NOT NULL,
    stream_id UUID REFERENCES video_streams(id),
    track_id INTEGER NOT NULL,
    vehicle_type VARCHAR(30) NOT NULL,             -- 'motorcycle', 'car', 'bus', 'truck'...
    confidence NUMERIC(4, 3) NOT NULL,
    speed_kmh NUMERIC(5, 1) NOT NULL,              -- Vận tốc đo được (km/h)
    direction VARCHAR(20) NOT NULL,                -- 'IN', 'OUT'
    lane_id INTEGER DEFAULT 1,
    is_overspeed BOOLEAN DEFAULT FALSE,
    snapshot_url TEXT,                             -- Link ảnh MinIO
    video_clip_url TEXT                            -- Link video 6s MinIO nếu vi phạm
);
-- Chuyển đổi thành bảng chuỗi thời gian tối ưu partition theo ngày
SELECT create_hypertable('vehicle_detections', 'time');
CREATE INDEX idx_vehicle_stream_time ON vehicle_detections (stream_id, time DESC);
CREATE INDEX idx_vehicle_type ON vehicle_detections (vehicle_type);
CREATE INDEX idx_vehicle_overspeed ON vehicle_detections (is_overspeed, time DESC);
```

### Bảng 3: `traffic_hourly_stats` (Bảng tổng hợp lưu lượng theo từng giờ)
```sql
CREATE TABLE traffic_hourly_stats (
    hour_bucket TIMESTAMPTZ NOT NULL,
    stream_id UUID REFERENCES video_streams(id),
    total_vehicles INTEGER NOT NULL DEFAULT 0,
    motorcycle_count INTEGER NOT NULL DEFAULT 0,
    car_count INTEGER NOT NULL DEFAULT 0,
    truck_count INTEGER NOT NULL DEFAULT 0,
    bus_count INTEGER NOT NULL DEFAULT 0,
    other_count INTEGER NOT NULL DEFAULT 0,
    avg_speed_kmh NUMERIC(5, 1) NOT NULL,
    overspeed_violations INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (hour_bucket, stream_id)
);
```

---

## 4. BỘ CÔNG CỤ GÁN NHÃN & MLOPS PIPELINE

1. **Gán nhãn với Label Studio Community Edition:**
   - Sử dụng template XML cấu hình sẵn tại `annotation/label_studio_template.xml`.
   - 8 lớp phương tiện chuẩn xác: `motorcycle`, `car`, `electric_bicycle`, `bicycle`, `bus`, `truck`, `container_truck`, `special_vehicle`.
   - Xuất dữ liệu trực tiếp sang định dạng YOLO TXT format kèm `data.yaml`.
2. **Huấn luyện Mô hình YOLOv11:**
   - Huấn luyện trên Google Colab / GPU Workstation với PyTorch 2.x.
   - Lượng hóa sang ONNX và TensorRT INT8 / FP16 để tích hợp vào engine suy luận thời gian thực.

---
*Tài liệu kiến trúc hệ thống đếm và đo tốc độ phương tiện ITS 2026.*
