# TÀI LIỆU THIẾT KẾ KIẾN TRÚC HỆ THỐNG (SYSTEM ARCHITECTURE)
## HỆ THỐNG NHẬN DIỆN BIỂN SỐ XE TỪ LUỒNG VIDEO STREAMING ĐA GIAO THỨC
### (MULTI-PROTOCOL STREAMING ALPR/ANPR: RTSP, WEBRTC, HLS, SRT, RTMP)
**Phiên bản:** 2.0.0  
**Tác giả:** Đội ngũ Kiến trúc sư Hệ thống ITS & Video Streaming Pipeline

---

## 1. TỔNG QUAN KIẾN TRÚC HỆ THỐNG (HIGH-LEVEL STREAMING ARCHITECTURE)

Hệ thống được thiết kế theo mô hình **Kiến trúc Thu nhận và Xử lý Luồng Đa tầng (Multi-tier Stream Ingestion & Processing Architecture)**. Hệ thống tách biệt hoàn toàn giữa tầng thu nhận video mạng (Network Streaming Gateway), tầng giải mã phần cứng không sao chép (Zero-copy Hardware Decoding), tầng suy luận AI (Inference Pipeline) và tầng dịch vụ nghiệp vụ (Business & Storage Services).

```
+-----------------------------------------------------------------------------------------------------------------------+
|                                        CÁC NGUỒN PHÁT VIDEO STREAMING ĐẦU VÀO                                         |
|                                                                                                                       |
|   +-----------------------+     +-----------------------+     +-----------------------+     +----------------------+  |
|   |  Camera IP Cố định    |     |  Xe tuần tra / Drone  |     |  Cổng GT Đô thị (CDN) |     |  Trạm thu phí từ xa  |  |
|   |  RTSP (H.264 / H.265) |     |  WebRTC (WHIP / SRTP) |     |  HLS / LL-HLS (.m3u8) |     |  SRT / RTMP Stream   |  |
|   +-----------+-----------+     +-----------+-----------+     +-----------+-----------+     +----------+-----------+  |
+---------------|-----------------------------|-----------------------------|----------------------------|--------------+
                |                             |                             |                            |
                v                             v                             v                            v
+-----------------------------------------------------------------------------------------------------------------------+
|                         TẦNG CỔNG THU NHẬN LUỒNG PHÂN TÁN (STREAM INGESTION GATEWAY LAYER)                            |
|                                                                                                                       |
|   +---------------------------------------------------------------------------------------------------------------+   |
|   | MediaMTX / GStreamer Ingestion Workers / LiveKit WebRTC SFU Server                                            |   |
|   | - Session Manager: Quản lý vòng đời kết nối từng luồng, cơ chế Auto-Reconnect & Failover                      |   |
|   | - Demuxer Engine: Bóc tách gói tin RTP, MPEG-TS, fMP4 Chunks, SRT Packets                                     |   |
|   | - De-jitter Ring Buffer: Triệt tiêu hiện tượng trễ mạng thất thường, sắp xếp lại khung hình đúng thứ tự       |   |
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
|   | - Adaptive Frame Sampler: Lấy mẫu khung hình thích nghi (tách $12\text{ fps}$ cho AI; giữ $30\text{ fps}$ ghi clip)|   |
|   | - Pre-event & Post-event Ring Buffer: Đệm sẵn $6\text{ giây}$ video để cắt clip bằng chứng khi phát hiện xe vi phạm|   |
|   +-------------------------------------------------------+-------------------------------------------------------+   |
+-----------------------------------------------------------|-----------------------------------------------------------+
                                                            | Tensors trong GPU VRAM (NV12 / FP32 RGB Tensors)
                                                            v
+-----------------------------------------------------------------------------------------------------------------------+
|                       TẦNG SUY LUẬN AI & BẪY ẢO PHƯƠNG TIỆN (AI INFERENCE & VIRTUAL TRIGGER)                         |
|                                                                                                                       |
|   +---------------------+   +---------------------+   +---------------------+   +---------------------+               |
|   | 1. Bẫy ảo & Bám vết |   | 2. Định vị biển số  |   | 3. Nắn thẳng góc    |   | 4. Nhận dạng ký tự  |               |
|   | Virtual Loop Trap + |-->| YOLOv11-Pose        |-->| Warp Perspective    |-->| PP-OCRv4 / CRNN-CTC |               |
|   | ByteTrack (YOLOv11) |   | (4 đỉnh biển số)    |   | + Adaptive CLAHE    |   | TensorRT FP16/INT8  |               |
|   +---------------------+   +---------------------+   +---------------------+   +----------+----------+               |
|                                                                                            |                          |
|                                     +------------------------------------------------------+                          |
|                                     v                                                                                 |
|                             +-----------------------------------------------+                                         |
|                             | 5. Bộ lọc Cú pháp & Quy tắc Biển số Việt Nam  |                                         |
|                             | (Regex Thông tư 24/2023/TT-BCA + Confusion Fix|                                         |
|                             +-----------------------+-----------------------+                                         |
+-----------------------------------------------------|-----------------------------------------------------------------+
                                                      | Metadata JSON + Cropped Image + 6s Video Clip
                                                      v
+-----------------------------------------------------------------------------------------------------------------------+
|                            TẦNG DỊCH VỤ NGHIỆP VỤ & LƯU TRỮ (CORE SERVICES & STORAGE)                                 |
|                                                                                                                       |
|   +--------------------+      +--------------------+      +--------------------+      +--------------------+          |
|   | Core ANPR Service  |      | Alert & Blacklist  |      | Stream Health Svc  |      | Live Dashboard     |          |
|   | (Golang / FastAPI) |      | (Telegram/Webhook) |      | (Prometheus/Grafana|      | (WebRTC / WSS Push)|          |
|   +---------+----------+      +---------+----------+      +---------+----------+      +---------+----------+          |
|             |                           |                           |                           |                     |
|             +---------------------------+-------------+-------------+---------------------------+                     |
|                                                       v                                                               |
|   +---------------------------------------------------------------------------------------------------------------+   |
|   | PostgreSQL 16 + TimescaleDB (Lưu trữ Metadata giao dịch) | Redis 7 (Cache Whitelist/Blacklist tra cứu < 1ms)  |   |
|   | MinIO / AWS S3 (Lưu trữ ảnh cận cảnh biển số + ảnh ngữ cảnh + đoạn video bằng chứng 6s MP4)                   |   |
|   +---------------------------------------------------------------------------------------------------------------+   |
+-----------------------------------------------------------------------------------------------------------------------+
```

---

## 2. CHI TIẾT CÁC PHÂN HỆ XỬ LÝ VIDEO STREAMING (STREAMING PIPELINE DETAILS)

### 2.1. Phân hệ Tiếp nhận & Phân kênh Đa Giao thức (Multi-Protocol Ingestion Subsystem)

Mỗi giao thức video streaming có cơ chế truyền tải và đặc tính kỹ thuật riêng biệt. Hệ thống sử dụng một lớp trừu tượng hóa thống nhất (Unified Stream Ingestor) xây dựng trên nền tảng **GStreamer 1.24** kết hợp với **NVIDIA DeepStream SDK**:

#### 1. Xử lý luồng RTSP (Real-Time Streaming Protocol)
- Sử dụng phần tử `rtspsrc` với cơ chế đệm jitter thích nghi.
- Hỗ trợ cả truyền qua UDP (ưu tiên độ trễ) và TCP (ưu tiên chống mất gói tin).
- Hỗ trợ RTSPS (mã hóa qua TLS) và chứng thực cơ bản (Digest / Basic Authentication).

#### 2. Xử lý luồng WebRTC (WHIP / SRTP)
- Nhận luồng video truyền trực tiếp từ các thiết bị di động (xe tuần tra, drone, smartphone của lực lượng chức năng) thông qua giao thức chuẩn **WHIP (WebRTC HTTP Ingestion Protocol)**.
- Thiết bị phát chỉ cần gửi một yêu cầu `HTTP POST` chứa SDP Offer tới Endpoint của hệ thống. Máy chủ phản hồi SDP Answer và thiết lập kênh truyền SRTP bảo mật độ trễ $< 200\text{ ms}$.
- Xử lý mượt mà việc thay đổi địa chỉ IP máy phát (hỗ trợ chuyển trạm BTS khi xe tuần tra di chuyển tốc độ cao nhờ ICE Restart).

#### 3. Xử lý luồng HLS / LL-HLS (HTTP Live Streaming)
- Tương thích với các cổng thông tin giám sát giao thông đô thị phân phối qua danh sách phát `.m3u8`.
- Module HLS Ingestion Worker duy trì một tiến trình nền liên tục thăm dò (poll) file manifest `.m3u8` để tải các phân đoạn mới nhất (`.ts` hoặc `.m4s`).
- Giải nén (demux) các khối dữ liệu HTTP tải về và ghép nối liên tục thành một luồng video tuần tự (Continuous Stream Pipeline) trước khi đưa vào bộ giải mã phần cứng.

#### 4. Xử lý luồng SRT (Secure Reliable Transport)
- Sử dụng phần tử `srtsrc` ở chế độ Caller, Listener hoặc Rendezvous.
- Cấu hình độ trễ đệm thích nghi (Latency Buffer: $120 - 500\text{ ms}$) và cơ chế tự động gửi lại gói lỗi (ARQ), đảm bảo video không bị vỡ hạt (artifact free) ngay cả khi truyền qua sóng 4G/Internet công cộng có tỷ lệ mất gói lên đến $10\%$.

---

### 2.2. Pipeline Giải mã Phần cứng Không Sao chép (Zero-Copy Hardware Accelerated Decoding)

Để xử lý đồng thời từ 24 đến 32 luồng video Full HD 1080p trên một GPU duy nhất, hệ thống tuyệt đối **không giải mã trên CPU** và **không truyền dữ liệu khung hình qua lại giữa RAM hệ thống và VRAM GPU**.

```
[Mạng Internet/LAN: Gói tin nén H.264/H.265]
                    │
                    ▼
[Phần tử mạng: rtspsrc / whipsink / srtsrc / souphttpsrc]
                    │
                    ▼
[Bộ phân kênh: h264parse / h265parse]
                    │
                    ▼
[NVIDIA Hardware Decoder: nvv4l2decoder (NVDEC Engine)]
                    │
                    ├─────────────────────────────────────────────────┐
                    │ (Khung hình NV12 trong GPU VRAM)                 │
                    ▼                                                 ▼
[nvvideoconvert: Chuyển màu sang RGBA/FP32]           [Bộ đệm vòng Circular Buffer]
                    │                                  (Lưu sẵn 6 giây video @ 30fps)
                    ▼                                                 │
[NVIDIA TensorRT nvstreammux: Batching 24 luồng]                     │ (Khi có xe vi phạm)
                    │                                                 ▼
                    ▼                                       [nvv4l2h264enc + mp4mux]
[NVIDIA Triton Inference Server / DeepStream GIE]                     │
(YOLOv11 Detection + ByteTrack + OCR)                                 ▼
                                                       [Xuất đoạn clip 6s bằng chứng MP4]
```

#### GStreamer Pipeline String mẫu cho luồng RTSP tăng tốc phần cứng:
```bash
gst-launch-1.0 rtspsrc location=rtsp://cam-ip:554/live latency=100 drop-on-latency=true ! \
    rtph264depay ! h264parse ! \
    nvv4l2decoder enable-max-performance=1 drop-frame-interval=0 ! \
    nvvideoconvert ! \
    video/x-raw(memory:NVMM), format=RGBA ! \
    appsink name=ai_sink emit-signals=true max-buffers=2 drop=true
```

---

### 2.3. Bẫy ảo & Kỹ thuật Lấy mẫu Khung hình Thích nghi (Virtual Trigger & Adaptive Sampler)

Khác với hệ thống bãi đỗ xe truyền thống có cảm biến vòng từ vật lý báo hiệu thời điểm xe dừng lại, luồng video streaming là một dòng dữ liệu chuyển động liên tục không ngừng nghỉ.

#### 1. Kỹ thuật Lấy mẫu Khung hình Thích nghi (Adaptive Frame Sampling):
- Luồng video gốc được giải mã ở tốc độ thực tế ($25 - 30\text{ fps}$).
- Tuy nhiên, việc chạy Deep Learning OCR trên toàn bộ 30 khung hình/giây của 32 luồng ($32 \times 30 = 960\text{ FPS}$) sẽ làm quá tải năng lực tính toán của GPU.
- Hệ thống áp dụng **Cơ chế 2 mức tốc độ (Two-tier Rate Processing)**:
  - *Mức 1 (Phát hiện & Bám vết):* Chạy mô hình phát hiện xe nhẹ (YOLOv11-Nano) ở tần suất **$10\text{ fps}$** (bỏ qua 2 khung hình, xử lý 1 khung hình). Thuật toán ByteTrack duy trì quỹ đạo xe một cách mượt mà.
  - *Mức 2 (Nhận diện Biển số & OCR):* Chỉ khi một phương tiện được bám vết tiến vào **Vùng bẫy ảo (Virtual Detection Zone)**, hệ thống mới kích hoạt module đọc biển số.

#### 2. Giải thuật Chọn Khung hình Nét nhất (Best Frame Selection):
Khi phương tiện đi qua vùng bẫy ảo, hệ thống thu thập một chuỗi từ 3 đến 5 khung hình liên tiếp chứa biển số và chấm điểm chất lượng ảnh bằng **Toán tử Laplacian Variance**:
$$\text{Score}_{\text{sharpness}} = \text{Var}(\nabla^2 I)$$
- Khung hình có $\text{Score}_{\text{sharpness}}$ cao nhất (ít bị nhòe chuyển động nhất, kích thước diện tích biển số lớn nhất) được chọn để đưa vào mạng **YOLOv11-Pose** (hoặc YOLOv8-Pose) nắn phẳng và **PP-OCRv4** đọc chữ.
- Nhờ giải thuật này, độ chính xác nhận diện tăng thêm **$8.5\%$** so với việc chỉ đọc ngẫu nhiên một khung hình khi xe vừa chạm bẫy ảo.

---

## 3. THIẾT KẾ CƠ SỞ DỮ LIỆU & QUẢN LÝ LUỒNG STREAM (DATABASE SCHEMA)

Hệ thống bổ sung bảng quản lý danh mục luồng streaming `video_streams` bên cạnh các bảng lịch sử giao dịch và bằng chứng:

### Bảng 1: `video_streams` (Quản lý các luồng video streaming đầu vào)
```sql
CREATE TABLE video_streams (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    stream_code VARCHAR(50) NOT NULL UNIQUE,       -- Ví dụ: 'STREAM_HLS_Q1_01', 'STREAM_WEBRTC_PATROL_05'
    stream_name VARCHAR(120) NOT NULL,             -- Tên hiển thị: 'Camera Ngã tư Hàng Xanh'
    protocol VARCHAR(20) NOT NULL,                 -- 'RTSP', 'WEBRTC', 'HLS', 'SRT', 'RTMP'
    source_url TEXT NOT NULL,                      -- URL kết nối luồng
    backup_url TEXT,                               -- URL dự phòng khi luồng chính lỗi
    resolution VARCHAR(20) DEFAULT '1920x1080',    -- Độ phân giải luồng
    expected_fps INTEGER DEFAULT 25,               -- FPS dự kiến
    status VARCHAR(20) DEFAULT 'INITIALIZING',     -- 'ACTIVE', 'DEGRADED', 'OFFLINE', 'ERROR'
    virtual_zone_polygon JSONB NOT NULL,           -- Tọa độ đa giác bẫy ảo: [{"x":0.15,"y":0.55}, {"x":0.85,"y":0.55}, ...]
    assigned_gpu_id INTEGER DEFAULT 0,             -- ID GPU xử lý (0, 1, 2, 3...)
    current_bitrate_kbps INTEGER DEFAULT 0,
    packet_loss_rate NUMERIC(5, 2) DEFAULT 0.0,
    last_ping_at TIMESTAMPTZ DEFAULT NOW(),
    created_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX idx_streams_status ON video_streams (status);
CREATE INDEX idx_streams_protocol ON video_streams (protocol);
```

### Bảng 2: `stream_detections` (Bản ghi nhận diện biển số từ luồng video)
```sql
CREATE TABLE stream_detections (
    id UUID DEFAULT gen_random_uuid(),
    stream_id UUID REFERENCES video_streams(id),
    track_id INTEGER NOT NULL,                     -- ID bám vết của xe trong luồng
    plate_number VARCHAR(16) NOT NULL,             -- Chuỗi biển số chuẩn hóa: '29A12345'
    formatted_plate VARCHAR(20) NOT NULL,          -- Chuỗi hiển thị: '29A-123.45'
    plate_type VARCHAR(20) NOT NULL,               -- 'CIVILIAN_WHITE', 'COMMERCIAL_YELLOW', 'GOV_BLUE', 'MILITARY_RED'
    vehicle_type VARCHAR(20) NOT NULL,             -- 'CAR', 'MOTORCYCLE', 'TRUCK', 'BUS'
    confidence NUMERIC(5, 4) NOT NULL,             -- Độ tin cậy OCR (0.0000 - 1.0000)
    is_blacklist_match BOOLEAN DEFAULT FALSE,      -- Trùng danh sách đen
    plate_crop_url VARCHAR(255) NOT NULL,          -- URL ảnh crop biển số trên S3
    overview_frame_url VARCHAR(255) NOT NULL,      -- URL ảnh chụp toàn cảnh
    evidence_video_url VARCHAR(255),               -- URL đoạn video clip 6 giây bằng chứng vi phạm
    pts_timestamp BIGINT NOT NULL,                 -- Presentation Timestamp trong luồng video
    captured_at TIMESTAMPTZ NOT NULL,              -- Thời gian thực (Wall clock time)
    processing_time_ms INTEGER NOT NULL,           -- Thời gian xử lý từ lúc trúng bẫy đến khi có kết quả
    PRIMARY KEY (id, captured_at)
);
SELECT create_hypertable('stream_detections', 'captured_at', chunk_time_interval => INTERVAL '1 day');
CREATE INDEX idx_stream_det_plate ON stream_detections (plate_number, captured_at DESC);
CREATE INDEX idx_stream_det_blacklist ON stream_detections (is_blacklist_match) WHERE is_blacklist_match = TRUE;
```

---

## 4. ĐẶC TẢ GIAO DIỆN LẬP TRÌNH ỨNG DỤNG (API SPECIFICATIONS)

### 4.1. Đăng ký Luồng Video Streaming Mới (REST API)
- **Endpoint:** `POST /api/v1/streams`
- **Headers:** `Content-Type: application/json`, `Authorization: Bearer <ADMIN_TOKEN>`
- **Request Body:**
```json
{
  "stream_code": "STREAM_HLS_DIST1_LELOI",
  "stream_name": "Camera Lê Lợi - Nguyễn Huệ (HLS)",
  "protocol": "HLS",
  "source_url": "https://cdn-traffic.hcmc.gov.vn/live/cam_leloi/index.m3u8",
  "backup_url": "https://backup-cdn.hcmc.gov.vn/live/cam_leloi/index.m3u8",
  "virtual_zone_polygon": [
    {"x": 0.15, "y": 0.55},
    {"x": 0.85, "y": 0.55},
    {"x": 0.95, "y": 0.85},
    {"x": 0.05, "y": 0.85}
  ],
  "expected_fps": 30,
  "assigned_gpu_id": 0
}
```
- **Response Body (201 Created):**
```json
{
  "status": "SUCCESS",
  "stream_id": "c7a8b912-3456-789a-bcde-0123456789ab",
  "message": "Stream pipeline spawned successfully on GPU 0.",
  "state": "ACTIVE"
}
```

### 4.2. Ingestion Luồng Di động qua WebRTC (Chuẩn IETF WHIP)
- **Endpoint:** `POST /api/v1/whip/endpoint/{stream_code}`
- **Headers:** `Content-Type: application/sdp`, `Authorization: Bearer <DEVICE_TOKEN>`
- **Request Body:** Gửi nguyên văn chuỗi `SDP Offer` từ thiết bị xe tuần tra hoặc flycam.
- **Response (201 Created):** Trả về chuỗi `SDP Answer` của máy chủ nhận luồng; thiết lập kết nối SRTP trực tiếp với độ trễ $< 200\text{ ms}$.

### 4.3. WebSocket Live Alert & Detection Stream
- **Endpoint:** `wss://its-streaming.internal/ws/detections`
- **Sự kiện phát đi khi phát hiện biển số (Broadcast Payload):**
```json
{
  "event": "PLATE_DETECTED",
  "stream_code": "STREAM_WEBRTC_PATROL_02",
  "timestamp": "2026-10-05T14:45:10.512Z",
  "plate_number": "51K-987.65",
  "confidence": 0.982,
  "vehicle_type": "CAR",
  "plate_type": "COMMERCIAL_YELLOW",
  "is_blacklist_match": true,
  "blacklist_info": {
    "reason": "Xe hết hạn đăng kiểm & có lệnh truy nã tài xế",
    "alert_level": "CRITICAL"
  },
  "media": {
    "plate_crop_url": "https://storage.its.vn/crops/20261005/51K98765_crop.jpg",
    "overview_frame_url": "https://storage.its.vn/frames/20261005/51K98765_full.jpg",
    "video_clip_url": "https://storage.its.vn/clips/20261005/51K98765_evidence.mp4"
  },
  "latency_ms": 68
}
```

---

## 5. CƠ CHẾ BÙ TRỄ, TỰ PHỤC HỒI & TẢI TRỌNG (FAILOVER & SCALABILITY)

1. **Khử hiện tượng rớt luồng (Stream Watchdog & Circuit Breaker):**
   - Một tiến trình giám sát độc lập (Stream Health Watchdog) liên tục kiểm tra thông số `pts` (Presentation Time Stamp) của từng luồng.
   - Nếu trong vòng $3\text{ giây}$ liên tiếp không có khung hình mới được giải mã, Watchdog tự động kích hoạt ngắt kết nối cũ, giải phóng bộ nhớ decode phần cứng và chuyển sang kết nối URL dự phòng (`backup_url`).
2. **Khả năng mở rộng theo chiều ngang (Horizontal Auto-scaling với Kubernetes):**
   - Các Ingestion Node được đóng gói thành các Docker Container có GPU Passthrough (`nvidia-container-toolkit`).
   - Cụm điều phối Kubernetes tự động phân bổ tải các luồng video mới tới các Worker Pod còn dư tài nguyên VRAM và GPU compute capacity.
3. **Quản lý VRAM GPU:**
   - Mỗi luồng 1080p chiếm khoảng $120\text{ MB}$ bộ nhớ VRAM cho decode buffer và pipeline.
   - Một GPU 24GB VRAM an toàn vận hành ở mức $70\%$ tải ($16.8\text{ GB}$), tiếp nhận ổn định **24 luồng Full HD 1080p** liên tục 24/7/365.

---

## 6. KIẾN TRÚC MLOPS & HUẤN LUYỆN MÔ HÌNH TỪ ĐẦU (MLOPS TRAINING ARCHITECTURE)

Hệ thống tích hợp một phân hệ MLOps khép kín phụ trách việc thu thập từ camera streaming, gán nhãn phân tán và huấn luyện từ đầu 100% dữ liệu thật:

```
[Các luồng Video Camera Thực tế] ──► [stream_frame_extractor.py (pHash Filter)]
                                                        │
                                                        ▼
[Gán nhãn Phân tán tại Máy con]  ──► [10.000 Khung hình & 30.000 Biển số Thực tế]
                                                        │
                                                        ▼
                        +-----------------------------------------------+
                        | CỤM MÁY CHỦ HUẤN LUYỆN GPU (TRAINING CLUSTER) |
                        | - Giai đoạn 1: YOLOv11 Vehicle Detector       |
                        | - Giai đoạn 2: YOLOv11-Pose 4-Corner Plate    |
                        | - Giai đoạn 3: PP-OCRv4 / CRNN CTC Recog      |
                        +-----------------------+-----------------------+
                                                │ PyTorch Weights (.pt)
                                                ▼
                        +-----------------------------------------------+
                        | TỐI ƯU HÓA & LƯỢNG HÓA TENSORRT (OPTIMIZATION)|
                        | - ONNX Export (Opset 17)                      |
                        | - IInt8EntropyCalibrator2 (1.000 ảnh chuẩn)   |
                        | - TensorRT FP16 / INT8 Engine (.engine)       |
                        +-----------------------+-----------------------+
                                                │
                                                ▼
                        +-----------------------------------------------+
                        | KHO QUẢN LÝ MÔ HÌNH (MLFLOW MODEL REGISTRY)   |
                        | - Kiểm thử tự động trên Testset 10.000 mẫu    |
                        | - Shadow Deployment (Chạy ngầm 7 ngày)        |
                        | - Canary / Blue-Green OTA Hot Swap            |
                        +-----------------------------------------------+
```

Chi tiết quy trình thuật toán và công thức huấn luyện được quy định tại [docs/MODEL_TRAINING_PIPELINE.md](docs/MODEL_TRAINING_PIPELINE.md).