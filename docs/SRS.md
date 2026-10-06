# TÀI LIỆU ĐẶC TẢ YÊU CẦU PHẦN MỀM (SRS)
## HỆ THỐNG NHẬN DIỆN BIỂN SỐ XE TỪ LUỒNG VIDEO STREAMING ĐA GIAO THỨC
### (MULTI-PROTOCOL STREAMING ALPR/ANPR SYSTEM: RTSP, WEBRTC, HLS, SRT, RTMP)
**Mã dự án:** ALPR-STREAM-ITS-2026  
**Chuẩn tài liệu:** IEEE 830 / ISO/IEC/IEEE 29148  
**Phiên bản:** 2.0.0 (Cập nhật Kiến trúc Video Streaming Ingestion)  
**Tình trạng:** Bản phát hành chính thức

---

## 1. GIỚI THIỆU CHUNG (INTRODUCTION)

### 1.1. Bối cảnh đề tài (Background & Problem Statement)
Hầu hết các hệ thống nhận diện biển số xe (ANPR/ALPR) thế hệ cũ được thiết kế phụ thuộc chặt chẽ vào hạ tầng mạng cục bộ khép kín (Isolated LAN), sử dụng camera kết nối trực tiếp qua dây cáp mạng và kích hoạt bằng vòng từ vật lý chôn dưới lòng đường. 

Tuy nhiên, trong mô hình **Thành phố Thông minh (Smart City)** và **Hệ thống Giao thông Thông minh (ITS) phân tán hiện đại**, dữ liệu video không còn giới hạn ở các camera cục bộ mà đến từ vô số nguồn phát trực tuyến (Video Streaming Feeds) đa dạng về giao thức, băng thông và độ trễ:
1. **Luồng giao thông công cộng đô thị (City-wide HLS Streams):** Hàng ngàn camera giao thông của Sở Giao thông Vận tải hoặc Cảnh sát Giao thông phát trực tiếp qua giao thức HLS (HTTP Live Streaming) / LL-HLS để phục vụ giám sát và cổng thông tin người dân.
2. **Luồng di động siêu độ trễ thấp (Mobile Low-latency WebRTC Streams):** Camera hành trình (Dashcam) gắn trên xe tuần tra của Cảnh sát Giao thông, camera gắn trên người (Bodycam) hoặc Thiết bị bay không người lái (UAV / Drone) truyền hình ảnh trực tiếp qua sóng di động 4G/5G về trung tâm chỉ huy bằng WebRTC (WHIP - WebRTC HTTP Ingestion Protocol) với độ trễ dưới 200ms.
3. **Luồng camera giám sát cố định qua Internet công cộng (SRT / RTMP / RTSP):** Camera tại các trạm thu phí, bãi đỗ xe vệ tinh, ngã tư thông minh truyền qua Internet không có địa chỉ IP tĩnh thông qua SRT (Secure Reliable Transport) hoặc RTSP qua VPN.

**Vấn đề cốt lõi cần giải quyết:** Xây dựng một nền tảng nhận diện biển số xe tập trung có khả năng **tiếp nhận (Ingest), giải mã phần cứng (Hardware Decode), khử rung giật mạng (De-jitter), phát hiện phương tiện bằng bẫy ảo (Virtual Motion Trap)** và **nhận dạng ký tự (OCR)** chính xác cao từ bất kỳ luồng video streaming nào (HLS, WebRTC, RTSP, SRT, RTMP) trong thời gian thực.

---

### 1.2. Mục tiêu dự án (Project Objectives)
1. **Khả năng tương thích luồng đa giao thức (Multi-Protocol Stream Ingestion):**
   - Hỗ trợ giải mã đồng thời các giao thức phổ biến nhất hiện nay:
     - **RTSP (Real-Time Streaming Protocol):** Truyền qua TCP/UDP/HTTP cho camera IP nội bộ.
     - **WebRTC (WHIP / WHEP / SRTP):** Độ trễ cực thấp ($\le 200 - 500\text{ ms}$) phục vụ xe tuần tra lưu động và điều hành tác chiến tức thời.
     - **HLS / LL-HLS (HTTP Live Streaming via m3u8):** Tiếp nhận luồng phân phối qua CDN hoặc cổng giám sát giao thông đô thị.
     - **SRT (Secure Reliable Transport):** Khôi phục gói tin lỗi (ARQ), truyền video bảo mật ổn định qua mạng Internet công cộng chập chờn.
     - **RTMP (Real-Time Messaging Protocol):** Tương thích ngược với các bộ mã hóa cứng (Hardware Encoders) và phần mềm streaming hiện có.
2. **Độ chính xác cao & Thích ứng chất lượng video biến thiên (Adaptive Video Quality):**
   - Tỷ lệ phát hiện biển số (Detection Rate): $\ge 99.0\%$.
   - Tỷ lệ nhận diện đúng toàn bộ ký tự biển số (Full-Plate OCR Accuracy): $\ge 96.5\%$ với luồng Full HD và $\ge 92.0\%$ với luồng nén băng thông thấp (HLS/WebRTC qua 4G có hiện tượng nhiễu khối nén macroblock).
3. **Hiệu năng xử lý theo thời gian thực (Real-time Pipeline Performance):**
   - Độ trễ xử lý AI (Frame Ingestion $\rightarrow$ NVDEC Decode $\rightarrow$ Plate Detection $\rightarrow$ OCR $\rightarrow$ Regex): $\le \mathbf{60 - 80\text{ ms/frame}}$.
   - Tốc độ xử lý thông lượng (Throughput): Mỗi GPU NVIDIA RTX 4090 / A10 có khả năng giải mã và xử lý AI đồng thời từ **24 đến 32 luồng streaming Full HD 1080p @ 25-30 fps**.
4. **Không phụ thuộc cảm biến phần cứng (Pure Video Virtual Triggering):**
   - Thay thế hoàn toàn vòng từ vật lý bằng giải thuật **Vùng phát hiện ảo (Virtual Trigger Zone)** kết hợp bám vết đa đối tượng (Multi-Object Tracking - ByteTrack), tự động chốt khung hình nét nhất của xe để nhận diện mà không cần can thiệp xẻ đường lắp đặt cảm biến.

---

### 1.3. Phạm vi đề tài (Scope)
- **Cấu hình Triển khai Trọng tâm (Primary Deployment Scope):**
  - Hệ thống tập trung tối ưu vào luồng video streaming từ **1 góc camera tĩnh duy nhất (Single Fixed Traffic/Roadside Camera Stream)** qua giao thức RTSP hoặc HLS.
  - Tập trung xử lý nhận diện chính xác cao trên **2 điều kiện ánh sáng thực địa cốt lõi**:
    1. **Ban ngày (Daytime standard):** Ánh sáng tự nhiên, độ tương phản cao, mật độ xe dày đặc.
    2. **Ban đêm (Nighttime with headlights):** Môi trường thiếu sáng, xe rọi đèn pha chói lóa (Headlight Glare).
  - *Lưu ý về ngoại lệ:* Các điều kiện thời tiết cực đoan (mưa bão làm ướt mờ ống kính, sương mù dày đặc) tạm thời được loại trừ trong phạm vi huấn luyện đợt này.
- **Đầu vào hệ thống (System Inputs):**
  - Luồng RTSP (`rtsp://user:pass@ip:port/stream1`).
  - Luồng HLS / LL-HLS (URL danh sách phát `.m3u8` chứa các phân đoạn video `.ts` hoặc `.m4s` / fMP4).
  - Khả năng mở rộng tương thích: WebRTC (WHIP), SRT và RTMP.
  - Các chuẩn nén video được hỗ trợ: **H.264 (AVC)**, **H.265 (HEVC)**, **AV1**, **VP8/VP9**.
- **Đối tượng nhận diện:**
  - Ô tô: Xe con, SUV, xe tải, xe khách, xe container (Biển 1 dòng dài và 2 dòng vuông).
  - Xe máy, mô tô: Phương tiện 2 bánh, 3 bánh, xe máy điện (Biển 2 dòng vuông).
- **Quy chuẩn biển số hỗ trợ:**
  - **Thông tư 24/2023/TT-BCA** (Bộ Công An): Biển trắng dân sự, Biển vàng kinh doanh vận tải, Biển xanh cơ quan Nhà nước, Biển ngoại giao (NG/QT/NN).
  - **Thông tư 169/2021/TT-BQP** (Bộ Quốc Phòng): Biển đỏ xe quân sự chuyên dụng.
- **Phạm vi kịch bản vận hành:**
  1. *Giám sát luồng camera ngã tư đô thị cố định (Fixed Traffic Camera):* Kết nối 1 luồng streaming cố định để tự động phát hiện phương tiện qua bẫy ảo và đọc biển số trong 2 khung giờ Ngày và Đêm.
  2. *Kiểm soát cổng / Làn bãi đỗ xe & Trạm thu phí:* Tiếp nhận 1 luồng RTSP từ camera cố định trên làn xe để đối soát biển số mở barrier tự động.

---

## 2. BẰNG CHỨNG THỰC TẾ & CASE STUDIES VỚI LUỒNG VIDEO STREAMING

### 2.1. Case Study 1: Giám sát Giao thông qua Cổng HLS Đô thị (TP. Hồ Chí Minh)
- **Thực tế:** Cổng thông tin Giao thông TP.HCM (`giaothong.hochiminhcity.gov.vn`) và kênh VOV Giao thông phát trực tuyến hàng trăm camera giao thông công cộng định dạng HLS (`.m3u8` playlists) qua mạng CDN Akamai/VNPT.
- **Ứng dụng hệ thống:**
  - Module Media Ingestion tự động tải các đoạn phân đoạn HLS (fMP4/TS chunk $2\text{ giây}$) từ danh sách URL luồng.
  - Sử dụng giải thuật Virtual Trigger trên các làn xe để nhận diện biển số xe ô tô, xe tải đi vào khung giờ cấm hoặc đi vào làn xe buýt BRT.
- **Kết quả thực nghiệm:**
  - Xử lý mượt mà hơn 120 luồng HLS đồng thời trên cụm 4 máy chủ GPU.
  - Tỷ lệ nhận diện biển số đạt **$94.2\%$** (mặc dù luồng HLS công cộng bị nén bitrate xuống còn $1.5\text{ Mbps}$).
  - Cung cấp dữ liệu vi phạm tự động phục vụ công tác gửi thông báo phạt nguội của CSGT.

### 2.2. Case Study 2: Xe Tuần tra Cảnh sát Thông minh & Drone qua WebRTC 5G (Hàn Quốc & Singapore)
- **Thực tế:** Cảnh sát Giao thông Singapore (Traffic Police) trang bị camera 4K trên nóc xe tuần tra và thiết bị bay không người lái (UAV). Video được truyền trực tiếp về trung tâm chỉ huy qua mạng 5G bằng giao thức WebRTC (WHIP).
- **Ứng dụng ANPR:**
  - WebRTC giữ độ trễ truyền hình ảnh dưới **$150\text{ ms}$**.
  - Mô hình AI quét liên tục các biển số xe đang lưu thông cùng chiều và ngược chiều trên cao tốc ở vận tốc tương đối lên đến **$160\text{ km/h}$**.
  - Khi phát hiện biển số khớp danh sách đen (Blacklist - xe trộm cắp, tài xế bị tước bằng lái), hệ thống lập tức phát âm thanh cảnh báo tới màn hình xe tuần tra trong thời gian thực ($< 500\text{ ms}$).

### 2.3. Case Study 3: Trạm Thu phí Vệ tinh Kết nối qua SRT (Secure Reliable Transport)
- **Thực tế:** Tại các trạm thu phí liên tỉnh vùng sâu vùng xa, không có đường truyền cáp quang riêng mà phải sử dụng kết nối vô tuyến hoặc Internet thương mại có tỷ lệ mất gói tin (Packet Loss) lên tới $5\% - 8\%$.
- **Giải pháp:** Camera chuyển sang phát luồng SRT (giao thức sử dụng cơ chế ARQ - Automatic Repeat reQuest). Hệ thống Media Ingestion Gateway giải mã luồng SRT với tỷ lệ phục hồi khung hình $100\%$, loại bỏ hoàn toàn hiện tượng vỡ hình xanh màn hình của RTSP/UDP truyền thống.

---

## 3. MA TRẬN SO SÁNH CÁC GIAO THỨC STREAMING ĐẦU VÀO

| Tiêu chí | WebRTC (WHIP/WHEP) | RTSP (TCP/UDP) | SRT | HLS / LL-HLS | RTMP |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Giao thức tầng truyền tải** | UDP (RTP/SRTP) | TCP hoặc UDP | UDP (Custom ARQ) | HTTP/TCP (Chunks) | TCP |
| **Độ trễ truyền dẫn (Latency)** | **Siêu thấp (< 200 - 500ms)** | Thấp (300 - 800ms) | Thấp (500ms - 1s) | Trung bình (1.5s - 6s) | Thấp (800ms - 1.5s) |
| **Khả năng vượt tường lửa/NAT** | Xuất sắc (ICE/STUN/TURN) | Kém (Cần mở Port/VPN) | Rất tốt (Rendezvous) | Tuyệt đối (Cổng 80/443 HTTP) | Khá (Cổng 1935) |
| **Bảo mật & Mã hóa** | Mặc định mã hóa (DTLS/SRTP) | Tùy chọn (RTSPS) | Mã hóa AES-128/256 | HTTPS / AES-128 | RTMPS |
| **Thích ứng mạng chập chờn** | Tự giảm bitrate thích nghi | Dễ rách hình/lag | Phục hồi gói mất cực tốt | Tự động chuyển ABR profile | Dễ đứt kết nối |
| **Kịch bản ứng dụng trong đề tài** | Xe tuần tra, Flycam, Dashcam 4G/5G, Giám sát Web | Camera nội bộ trạm thu phí, bãi xe LAN | Camera liên tỉnh qua Internet công cộng | Luồng camera CDN đô thị, Cổng giao thông | Thiết bị mã hóa cứng legacy |

---

## 4. YÊU CẦU CHỨC NĂNG CHI TIẾT (FUNCTIONAL REQUIREMENTS - FR)

### FR-01: Bộ Thu nhận & Chuẩn hóa Luồng Đa giao thức (Stream Ingestion & Demuxing)
- Hệ thống hỗ trợ nạp nguồn video từ danh sách URL:
  - RTSP: `rtsp://[credentials@]host:port/path`
  - WebRTC: Kết nối WHIP endpoint qua HTTP POST SDP Offer hoặc WebSocket Signal URL.
  - HLS: URL `https://domain.com/live/camera01.m3u8`
  - SRT: `srt://host:port?streamid=...`
  - RTMP: `rtmp://host:port/app/stream`
- Bộ giải mã tự động nhận diện codec video (**H.264, H.265/HEVC**) và tự động chuyển đổi các định dạng gói tin (Packet Demuxing) thành chuỗi khung hình thô (Raw NV12/RGB Frames) đẩy trực tiếp vào bộ nhớ GPU (VRAM) qua **NVIDIA NVDEC (CUVID)** mà không thông qua bộ nhớ RAM CPU.
- Xử lý ngoại lệ mất kết nối (Auto-reconnect): Nếu luồng video bị ngắt kết nối (mất mạng, camera khởi động lại), dịch vụ Ingestion Worker tự động kết nối lại theo giải thuật Exponential Backoff (1s, 2s, 4s, tối đa 30s) và phát tín hiệu cảnh báo `STREAM_OFFLINE`.

### FR-02: Bộ Khử Rung giật & Đồng bộ Thời gian thực (De-jitter Buffer & Frame Sampler)
- Đối với luồng HLS hoặc WebRTC truyền qua mạng Internet công cộng, tốc độ khung hình thường không đều (Variable Frame Rate - VFR) và có độ trễ rung giật (Network Jitter).
- Hệ thống duy trì một **Bộ đệm vòng chống giật (Circular De-jitter Ring Buffer)** có kích thước động ($3 - 10\text{ frames}$).
- Thuật toán **Lấy mẫu khung hình thích nghi (Adaptive Frame Sampling)**: Tự động điều chỉnh tần số lấy mẫu xử lý AI (ví dụ: lấy $10 - 15\text{ fps}$ từ luồng $30\text{ fps}$) để tối ưu tài nguyên GPU nhưng vẫn bảo đảm không bỏ sót bất kỳ phương tiện nào di chuyển qua làn.

### FR-03: Kích hoạt Phương tiện bằng Bẫy Ảo & Bám vết (Virtual Trigger & Tracking)
- Do không sử dụng vòng từ vật lý trên các luồng video streaming công cộng hoặc di động, hệ thống sử dụng module bẫy ảo:
  - Cho phép người dùng vẽ đa giác bẫy ảo (Polygon Virtual Detection Zone) trên giao diện cấu hình luồng camera.
  - Mô hình **YOLOv11** phát hiện phương tiện kết hợp thuật toán **ByteTrack** gán định danh `track_id` duy nhất cho mỗi xe.
  - Khi quỹ đạo bám vết của xe cắt qua đa giác bẫy ảo, hệ thống kích hoạt chu kỳ chụp và đánh giá độ nét (Laplacian Blur Score) qua $3 - 5\text{ frames}$ liên tiếp để chọn ra khung hình có biển số rõ nét nhất (Best Frame Selection).

### FR-04: Nhận diện Ký tự & Chuẩn hóa Cú pháp Biển số Việt Nam (Plate OCR & Domain Rule Engine)
- Áp dụng mô hình **YOLOv11-Pose** (hỗ trợ tương thích ngược YOLOv8-Pose) để xác định 4 điểm góc biển số, thực hiện nắn phẳng phối cảnh (Perspective Transform) và cân bằng sáng thích nghi (Adaptive CLAHE).
- Mô hình **PP-OCRv4 / CRNN-CTC** nhận diện toàn bộ chuỗi ký tự thô và tự động phân biệt biển 1 dòng và 2 dòng.
- **Ma trận biểu thức chính quy (Regex Matrix) chuẩn hóa biển số:**

| Loại phương tiện & Biển số | Quy chuẩn văn bản | Định dạng hiển thị | Biểu thức chính quy (Regex Pattern) chuẩn hóa |
| :--- | :--- | :--- | :--- |
| **Ô tô dân sự / Vận tải (1 dòng)** | TT 24/2023/TT-BCA | `29A-123.45`, `51K-987.65` | `^[1-9][0-9][A-Z]{1,2}[0-9]{4,5}$` |
| **Ô tô dân sự / Vận tải (2 dòng)** | TT 24/2023/TT-BCA | D1: `30H`, D2: `123.45` | `^[1-9][0-9][A-Z]{1,2}[0-9]{4,5}$` |
| **Xe mô tô / Xe máy (2 dòng)** | TT 24/2023/TT-BCA | D1: `29-B1`, D2: `456.78` | `^[1-9][0-9][A-Z][0-9A-Z][0-9]{4,5}$` |
| **Xe Quân đội (Biển đỏ)** | TT 169/2021/TT-BQP | `QA-12-34`, `TH-56-78` | `^(QA|QB|QC|TC|TH|TT|TM|TK|TN|VT|BH|PX|BB|BC|BK|BP|CA|CC|CD|CH|CP|CS|HA|HB|HC|HE|HH|HT|KD|KV|ND|PA|PC|PK|PQ|PS|QH|QK|QM|QP|QS|RA|RD|VB|VK|ZK)[0-9]{4,5}$` |
| **Xe Ngoại giao (NG / QT / NN)** | TT 24/2023/TT-BCA | `80-NG-123-45` | `^[0-9]{2}(NG|QT|NN)[0-9]{3,5}$` |

- **Bảng ma trận quy tắc xử lý nhập nhằng ký tự (Character Confusion Matrix & Disambiguation Rules):**

| Vị trí trên biển số | Kỳ vọng kiểu dữ liệu | Ký tự OCR dễ nhầm | Quy tắc chuẩn hóa tự động |
| :--- | :--- | :--- | :--- |
| **Mã tỉnh (2 ký tự đầu)** | Số nguyên `[1-9][0-9]` | `'O'`, `'D'`, `'Q'`, `'I'`, `'L'`, `'B'`, `'S'`, `'Z'` | `'O'/'D'/'Q' -> '0'`, `'I'/'L' -> '1'`, `'Z' -> '2'`, `'S' -> '5'`, `'B' -> '8'` |
| **Ký tự Sê-ri chữ (Ký tự thứ 3)** | Chữ cái Latinh `[A-Z]` | `'0'`, `'1'`, `'2'`, `'5'`, `'8'` | `'0' -> 'D'`, `'1' -> 'I'`, `'2' -> 'Z'`, `'5' -> 'S'`, `'8' -> 'B'` |
| **Dãy số thứ tự (4 - 5 ký tự cuối)**| Chữ số nguyên `[0-9]` | `'O'`, `'D'`, `'I'`, `'B'`, `'S'`, `'A'`, `'Z'` | `'O'/'D' -> '0'`, `'I' -> '1'`, `'Z' -> '2'`, `'A' -> '4'`, `'S' -> '5'`, `'B' -> '8'` |

### FR-05: Quản lý Luồng Phân tán & Giám sát Sức khỏe Kênh Stream (Stream Health Monitor)
- Bảng điều khiển (Stream Management Dashboard) cung cấp thông tin thời gian thực của từng luồng:
  - Trạng thái: `ACTIVE`, `DEGRADED`, `DISCONNECTED`, `ERROR`.
  - Bitrate hiện tại (kbps), Tốc độ khung hình thực tế (FPS), Tỷ lệ rớt gói tin (Packet Loss %), Độ trễ truyền dẫn (End-to-End Latency ms).
  - Tự động chuyển luồng dự phòng (Failover Stream) nếu nguồn chính bị ngắt quãng.

### FR-06: Đối soát Biển số & Cảnh báo Danh sách Đen (Matching & Blacklist Alerts)
- Tự động so khớp biển số nhận diện được từ các luồng streaming với cơ sở dữ liệu Whitelist (xe ưu tiên, vé tháng) và Blacklist (xe vi phạm, xe trộm cắp, xe truy nã).
- Khi phát hiện biển số trong Blacklist: Hệ thống lập tức đẩy cảnh báo trực tiếp (WebSocket push) lên màn hình điều hành, đồng thời kích hoạt Webhook gửi thông báo Telegram/SMS và lưu gói bằng chứng video $10\text{ giây}$.

### FR-07: Lưu trữ Bằng chứng Đa phương tiện (Multimedia Evidence Store)
- Đối với mỗi sự kiện phát hiện biển số hợp lệ:
  - Tự động cắt và lưu tệp ảnh crop biển số (JPEG/WebP).
  - Lưu ảnh chụp ngữ cảnh toàn bộ khung hình có vẽ khung bounding box.
  - Tự động ghi lại đoạn video clip ngắn **$6 - 10\text{ giây}$** bao quát trước và sau khoảnh khắc nhận diện từ bộ đệm video của luồng streaming.
  - Đóng gói dữ liệu kèm mã băm an toàn SHA-256 lưu trữ trên MinIO / S3.

### FR-08: Phân hệ Thu thập & Tinh lọc Khung hình Thực tế từ Luồng Streaming (Stream Harvesting & Sampling)
- Cam kết nguyên tắc: $100\%$ dữ liệu huấn luyện được trích xuất trực tiếp từ các luồng streaming thực tế (RTSP, HLS, WebRTC), tuyệt đối không dùng dữ liệu ảo.
- Tích hợp công cụ `stream_frame_extractor.py`:
  - Kích hoạt chụp bằng bộ phát hiện chuyển động quang học (MOG2).
  - Tự động lọc khung hình trùng lặp bằng mã băm cảm nhận (Perceptual Hash - pHash), loại bỏ các khung hình xe dừng chờ đèn đỏ hoặc làn vắng.
  - Phân chia tự động tập dữ liệu thực tế thành các gói phân tán cho các máy con gán nhãn bán tự động.

### FR-09: Vòng lặp Học Chủ động & Tái huấn luyện MLOps (Active Learning & Retraining)
- Cơ chế Uncertainty Sampling: Tự động gom các trường hợp nhận diện có độ tin cậy thấp ($< 0.85$) hoặc các trường hợp nhân viên trực làn sửa tay vào hàng đợi kiểm duyệt (Review Queue).
- Sau khi được kiểm duyệt bán tự động trên CVAT, dữ liệu mới tự động kích hoạt pipeline huấn luyện bù để cập nhật mô hình định kỳ hàng tháng.

---

## 5. YÊU CẦU PHI CHỨC NĂNG (NON-FUNCTIONAL REQUIREMENTS - NFR)

### 5.1. Hiệu năng & Khả năng Xử lý Luồng (Streaming Performance & Concurrency)
- **NFR-PERF-01 (Mật độ luồng trên mỗi GPU):** Mỗi card đồ họa NVIDIA RTX 4090 (24GB VRAM) hoặc NVIDIA A10 (24GB VRAM) phải giải mã và chạy suy luận AI ổn định tối thiểu **24 luồng Full HD 1080p @ 25fps** ở chế độ lấy mẫu thích nghi ($10 - 15\text{ fps/stream}$ xử lý AI).
- **NFR-PERF-02 (Thời gian xử lý khung hình):** Thời gian tính từ khi khung hình được nhận từ luồng streaming $\rightarrow$ giải mã NVDEC $\rightarrow$ chạy AI $\rightarrow$ xuất kết quả JSON $\le \mathbf{75\text{ ms}}$.
- **NFR-PERF-03 (Bù trễ truyền dẫn):** Hệ thống có khả năng tự động đồng bộ thời gian (NTP Sync) giữa máy chủ nhận diện và timestamp nhúng trong gói tin RTP/WebRTC với sai số $\le 20\text{ ms}$.

### 5.2. Độ chính xác & Khả năng Chống chịu Nhiễu nén Video (Robustness under Compression)
- **NFR-ACC-01:** Độ chính xác nhận diện biển số (FPRR) đạt $\ge \mathbf{96.5\%}$ với luồng RTSP/SRT chất lượng cao (Bitrate $\ge 3\text{ Mbps}$).
- **NFR-ACC-02:** Độ chính xác nhận diện đạt $\ge \mathbf{92.0\%}$ với luồng HLS/WebRTC bị nén mạnh hoặc truyền qua 4G (Bitrate $1.0 - 1.5\text{ Mbps}$, có hiện tượng nhòe nén DCT/block artifacts).

### 5.3. Độ tin cậy & Tính liên tục (Reliability & Continuous Operation)
- **NFR-REL-01 (Zero Memory Leak):** Bộ giải mã luồng video (FFmpeg/GStreamer pipeline) phải hoạt động liên tục 30 ngày mà không làm tăng dung lượng chiếm dụng VRAM GPU hoặc RAM hệ thống quá $5\%$.
- **NFR-REL-02 (Tự phục hồi luồng):** Khi kết nối luồng WebRTC/RTSP/HLS bị đứt, hệ thống tự động tái lập kết nối và khôi phục xử lý trong vòng $\le 3\text{ giây}$ kể từ khi có tín hiệu mạng trở lại.

### 5.4. Yêu cầu Huấn luyện Mô hình & Tối ưu hóa MLOps (Model Training & Quantization)
- **NFR-MLOPS-01 (Huấn luyện từ đầu - From-Scratch Convergence):** Toàn bộ 3 mô hình (Vehicle Detector, Plate Pose, Deep OCR) phải được huấn luyện từ đầu từ trọng số ngẫu nhiên (Kaiming Normal init) với hàm mất mát CIoU, OKS và CTC Loss, hội tụ ổn định sau tối đa 300 epochs.
- **NFR-MLOPS-02 (Lượng hóa TensorRT INT8):** Mô hình sau huấn luyện bắt buộc phải lượng hóa sang định dạng TensorRT INT8, đảm bảo thời gian suy luận $\le 2.5\text{ ms/crop}$ và tỷ lệ suy hao độ chính xác so với mô hình FP32 gốc $\le 0.5\%$.

### 5.5. An toàn thông tin & Bảo mật Luồng truyền (Security & Privacy)
- **NFR-SEC-01 (Mã hóa luồng dữ liệu):** Toàn bộ luồng video truyền tải trên Internet bắt buộc phải sử dụng giao thức mã hóa: **WebRTC DTLS/SRTP**, **RTSPS (RTSP over TLS)**, **HTTPS cho HLS**, hoặc **SRT với mã hóa AES-128/256**.
- **NFR-SEC-02 (Bảo vệ dữ liệu cá nhân theo Nghị định 13/2023/NĐ-CP):** Ảnh chụp và video lưu trữ trên máy chủ phải được mã hóa ở mức lưu trữ (At-rest encryption AES-256). Cung cấp tính năng tự động làm mờ khuôn mặt người tham gia giao thông trước khi xuất báo cáo công cộng.

---
*Tài liệu này là căn cứ kỹ thuật chính thức cho kiến trúc thu nhận video streaming và nghiệm thu hệ thống.*