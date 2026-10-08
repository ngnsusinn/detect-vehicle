# TÀI LIỆU ĐẶC TẢ YÊU CẦU PHẦN MỀM (SRS)
## HỆ THỐNG ĐẾM VÀ ĐO TỐC ĐỘ PHƯƠNG TIỆN GIAO THÔNG TỪ LUỒNG VIDEO STREAMING ĐA GIAO THỨC
### (MULTI-PROTOCOL STREAMING VEHICLE COUNTING & SPEED ESTIMATION SYSTEM: RTSP, WEBRTC, HLS, SRT, RTMP)
**Mã dự án:** SPEED-COUNT-ITS-2026  
**Chuẩn tài liệu:** IEEE 830 / ISO/IEC/IEEE 29148  
**Phiên bản:** 2.0.0 (Cập nhật Toàn diện Bài toán Đếm Xe & Đo Tốc độ)  
**Tình trạng:** Bản phát hành chính thức

---

## 1. GIỚI THIỆU CHUNG (INTRODUCTION)

### 1.1. Bối cảnh đề tài (Background & Problem Statement)
Trong các đô thị hiện đại và hệ thống **Giao thông Thông minh (ITS - Intelligent Transportation Systems)**, việc thu thập số liệu lưu lượng phương tiện và giám sát tốc độ di chuyển là nền tảng để điều phối tín hiệu đèn giao thông, quy hoạch hạ tầng đường bộ và phát hiện các hành vi vi phạm an toàn giao thông.

Các phương pháp đo đếm truyền thống tồn tại nhiều nhược điểm nghiêm trọng:
1. **Vòng từ cảm ứng vật lý chôn dưới mặt đường:** Chi phí thi công cao, phải xẻ đường gây hư hại hạ tầng, dễ đứt cáp và không thể phân loại chi tiết các loại phương tiện (chỉ nhận biết có vật kim loại đi qua).
2. **Súng bắn tốc độ cầm tay / Radar chuyên dụng:** Chi phí thiết bị vô cùng đắt đỏ ($15.000 - $30.000 USD/điểm), phạm vi quét hẹp, dễ bị che khuất và khó triển khai diện rộng trên hàng ngàn camera giao thông hiện có.
3. **Phân phối luồng video phân tán qua Internet:** Các camera giao thông hiện nay truyền phát trực tiếp qua vô số giao thức mạng khác nhau (**HLS** từ cổng thông tin đô thị, **WebRTC** từ camera hành trình di động, **RTSP** nội bộ, **SRT** từ các trạm xa xôi) với băng thông và độ trễ biến thiên liên tục.

**Vấn đề cốt lõi cần giải quyết:** Xây dựng một nền tảng phần mềm thuần Thị giác máy tính (Pure Computer Vision & AI) có khả năng **tiếp nhận trực tiếp mọi luồng video streaming (RTSP, HLS, WebRTC, SRT, RTMP)**, tự động **phát hiện và phân loại chính xác 8 nhóm phương tiện**, **bám vết đa đối tượng (ByteTrack)**, **đếm lưu lượng theo làn/hướng** và **đo tốc độ phương tiện qua ma trận biến đổi phối cảnh (Homography Transform)** theo thời gian thực mà không cần lắp đặt thêm cảm biến phần cứng trên mặt đường.

---

### 1.2. Mục tiêu dự án (Project Objectives)
1. **Thu nhận & Giải mã luồng đa giao thức (Multi-Protocol Streaming Ingestion):**
   - Hỗ trợ giải mã đồng thời: RTSP, HLS/LL-HLS, WebRTC (WHIP), SRT, RTMP và tệp video MP4.
   - Giải mã phần cứng không sao chép (Zero-copy GPU decoding) trên NVIDIA NVDEC.
2. **Độ chính xác cao trong phân loại & đếm xe:**
   - Tỷ lệ đếm đúng phương tiện (Counting Accuracy): $\ge \mathbf{97.5\%}$.
   - Tỷ lệ phân loại đúng 8 nhóm phương tiện (xe máy, ô tô, xe đạp điện, xe đạp, xe khách, xe tải, container, xe chuyên dụng): $\text{mAP50} \ge \mathbf{92.0\%}$.
3. **Đo tốc độ phương tiện chuẩn xác:**
   - Sai số đo tốc độ (Speed Estimation Error): $\le \mathbf{\pm 3 - 5\text{ km/h}}$ so với tốc độ thực tế của phương tiện khi xe di chuyển trong dải tốc độ $10 - 120\text{ km/h}$.
4. **Hiệu năng thời gian thực trên GPU (Real-time Latency & Throughput):**
   - Độ trễ xử lý toàn chu trình (Pipeline Latency): $\le \mathbf{60 - 75\text{ ms/frame}}$.
   - Thông lượng: Xử lý đồng thời từ **20 đến 32 luồng streaming Full HD 1080p** trên mỗi GPU NVIDIA RTX 4090 / NVIDIA L4.
5. **Tự động bắt lỗi vi phạm tốc độ & xuất bằng chứng:**
   - Tự động phát hiện phương tiện vượt tốc độ cho phép trên làn, chụp ảnh snapshot kèm bounding box, thông tin vận tốc, và tự động trích xuất clip video bằng chứng 6 giây (3s trước và 3s sau khi vi phạm).

---

### 1.3. Phạm vi đề tài (Scope)
- **Cấu hình Triển khai Trọng tâm (Primary Deployment Scope):**
  - Hệ thống tập trung tối ưu vào luồng video streaming từ **1 góc camera tĩnh (Single Fixed Roadside Traffic Camera)** qua RTSP hoặc HLS.
  - Xử lý ổn định trên **2 điều kiện ánh sáng thực địa cốt lõi**:
    1. **Ban ngày (Daytime standard):** Ánh sáng tự nhiên, lưu lượng xe đông đúc, bóng đổ phương tiện.
    2. **Ban đêm có đèn đường & đèn pha xe (Nighttime with headlights):** Môi trường thiếu sáng, xe bật đèn pha chói lóa.
- **Đối tượng phân loại phương tiện (8 nhóm lớp chuẩn):**
  1. `motorcycle`: Xe máy, xe mô tô 2 bánh, 3 bánh.
  2. `car`: Ô tô con (Sedan, SUV, CUV, Hatchback, xe bán tải pickup).
  3. `electric_bicycle`: Xe đạp điện, xe máy điện mini.
  4. `bicycle`: Xe đạp cơ thể thao, xe đạp thông thường.
  5. `bus`: Xe buýt nội đô, xe khách 16 - 45 chỗ, xe giường nằm.
  6. `truck`: Xe tải thùng, xe tải ben chuyên chở hàng hóa.
  7. `container_truck`: Xe container, xe đầu kéo rơ-moóc hạng nặng.
  8. `special_vehicle`: Xe ba gác, xe xích lô, xe cứu thương, xe chuyên dụng.

---

## 2. BẰNG CHỨNG THỰC TẾ & CASE STUDIES

### 2.1. Case Study 1: Đếm & Đo Tốc Độ từ Cổng Giao thông HLS Đô thị
- **Thực tế:** Cổng thông tin Giao thông TP.HCM (`giaothong.hochiminhcity.gov.vn`) phát trực tuyến hàng trăm camera giao thông công cộng qua định dạng HLS (`.m3u8`).
- **Ứng dụng:**
  - Ingestion Gateway kết nối tự động tới các luồng HLS, thiết lập vạch đếm ảo và ma trận Homography dựa trên khoảng cách giữa các vạch sơn kẻ đường tiêu chuẩn (vạch đứt quãng dài 3m, khoảng cách giữa 2 vạch 6m).
  - Tự động thống kê lưu lượng xe máy và ô tô theo từng khung giờ trong ngày, phát hiện tình trạng ùn tắc giao thông khi vận tốc dòng xe trung bình giảm xuống dưới $15\text{ km/h}$.

### 2.2. Case Study 2: Giám sát Tốc độ & Lưu lượng trên Quốc lộ / Cao tốc qua RTSP/SRT
- **Thực tế:** Các camera giao thông lắp đặt trên giá long môn (gantry) truyền luồng RTSP qua mạng VPN quang học hoặc SRT qua Internet công cộng.
- **Ứng dụng:**
  - Thiết lập vùng bẫy tốc độ ảo có chiều dài 20m trên mặt đường.
  - Khi xe vượt quá tốc độ tối đa cho phép của đoạn đường ($> 80\text{ km/h}$ hoặc $> 100\text{ km/h}$), hệ thống tự động ghi nhận mã Track ID, trích xuất hình ảnh phương tiện và video bằng chứng, kích hoạt cảnh báo tới trung tâm giám sát.

---

## 3. MA TRẬN SO SÁNH CÁC GIAO THỨC STREAMING ĐẦU VÀO

| Tiêu chí | WebRTC (WHIP) | RTSP (TCP/UDP) | SRT | HLS / LL-HLS | RTMP |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Giao thức truyền tải** | UDP (SRTP/DTLS) | TCP hoặc UDP | UDP (Custom ARQ) | HTTP/TCP | TCP |
| **Độ trễ truyền dẫn** | **Siêu thấp (< 300ms)** | Thấp (300 - 800ms) | Thấp (500ms - 1s) | Trung bình (2 - 6s) | Thấp (1 - 2s) |
| **Vượt NAT/Firewall** | Xuất sắc (ICE/TURN) | Yêu cầu mở Port/VPN| Rất tốt (Rendezvous)| Tuyệt đối (Port 80/443)| Khá (Port 1935) |
| **Bảo mật** | Bắt buộc DTLS/SRTP | Tùy chọn RTSPS | Mã hóa AES-128/256 | HTTPS | RTMPS |
| **Ứng dụng trong đề tài** | Camera di động, Dashcam | Camera IP cố định bãi xe/làn| Đường truyền xa, Internet| Luồng giao thông đô thị| Bộ mã hóa cứng legacy|

---

## 4. YÊU CẦU CHỨC NĂNG CHI TIẾT (FUNCTIONAL REQUIREMENTS - FR)

### FR-01: Thu nhận & Chuẩn hóa Luồng Đa Giao thức (Multi-Protocol Stream Ingestion)
- Hệ thống hỗ trợ tiếp nhận đồng thời các nguồn video: RTSP, WebRTC (WHIP), HLS (`.m3u8`), SRT, RTMP, Tệp video MP4 và Webcam USB.
- Tự động giải mã phần cứng chuẩn nén H.264, H.265 (HEVC) trực tiếp vào bộ nhớ GPU VRAM qua **NVIDIA NVDEC (CUVID)** không sao chép qua RAM CPU.
- Hỗ trợ cơ chế tự động kết nối lại (Auto-reconnect Exponential Backoff) khi camera mất mạng hoặc khởi động lại.

### FR-02: Bộ Khử Rung giật & Ổn định Nhịp Khung hình (De-jitter & FPS Normalizer)
- Duy trì bộ đệm khử rung giật mạng (De-jitter Ring Buffer) để ổn định tốc độ khung hình (Frame Interval $\Delta t$).
- Cố định chu kỳ tính toán thời gian giữa 2 khung hình liên tiếp ($\Delta t = \frac{1}{\text{FPS}}$) hoặc đọc trực tiếp Presentation Timestamp (PTS) nhúng trong gói tin để phục vụ tính toán vận tốc tuyệt đối chính xác.

### FR-03: Phát hiện & Phân loại Phương tiện Chuyên sâu (AI Vehicle Detection & Classification)
- Mô hình **YOLOv11** phát hiện đồng thời vị trí bounding box và phân loại chính xác 8 nhóm phương tiện:
  `motorcycle`, `car`, `electric_bicycle`, `bicycle`, `bus`, `truck`, `container_truck`, `special_vehicle`.
- Ngưỡng độ tin cậy phát hiện (Confidence Threshold) có thể cấu hình linh hoạt (mặc định $\ge 0.40$).
- Sử dụng điểm tiếp xúc giữa bánh xe và mặt đường (Bottom-Center của Bounding Box: $x_c = \frac{x_1 + x_2}{2}, y_b = y_2$) làm điểm mốc tọa độ không gian đại diện cho xe.

### FR-04: Bám vết Đa Đối tượng Bền vững (Multi-Object Tracking - ByteTrack)
- Tích hợp thuật toán **ByteTrack** để gán và duy trì định danh `track_id` duy nhất cho từng phương tiện di chuyển trong khung hình.
- Khả năng duy trì bám vết kể cả khi phương tiện bị che khuất tạm thời (Lost Track Buffer duy trì $30\text{ frames}$).
- Lưu lại chuỗi vết lịch sử tọa độ tâm đáy (Trajectory History) của từng xe qua thời gian: $T_{id} = \{(x_t, y_t, t)\}_{t=1}^N$.

### FR-05: Đếm Lưu lượng theo Làn & Hướng Di chuyển (Line-Crossing & ROI Counting)
- Cho phép người quản trị thiết lập vạch đếm ảo (Virtual Counting Line) hoặc đa giác vùng (Polygon ROI) trên giao diện cấu hình.
- Giải thuật giao cắt hình học (Line-Crossing Detection): Xác định chính xác thời điểm vệt di chuyển của phương tiện cắt qua vạch ảo theo vector hướng:
  - Hướng thuận (In / Upward): Xe đi về phía trước / lại gần.
  - Hướng nghịch (Out / Downward): Xe đi lùi / ra xa.
- Tự động cộng dồn số lượng phương tiện theo từng loại xe (Class Counters) và theo từng làn đường riêng biệt. Chống đếm trùng 100% nhờ gắn cờ `counted = True` theo `track_id`.

### FR-06: Đo Tốc độ qua Ma trận Biến đổi Phối cảnh (Homography Speed Estimation)
- Giao diện cho phép người dùng hiệu chuẩn 4 điểm chuẩn thực địa trên mặt đường (Camera Calibration Points) tương ứng với một hình chữ nhật thực địa đã biết kích thước (chiều dài $L\text{ mét}$, chiều rộng $W\text{ mét}$).
- Hệ thống tính toán ma trận phối cảnh $3 \times 3$ **Homography ($H$)**:
  $$\begin{bmatrix} X_{world} \\ Y_{world} \\ 1 \end{bmatrix} \sim H \begin{bmatrix} x_{pixel} \\ y_{pixel} \\ 1 \end{bmatrix}$$
- Với mỗi phương tiện có `track_id`, hệ thống chuyển đổi tọa độ điểm đáy bánh xe từ $(x_t, y_t)$ sang $(X_t, Y_t)$ trên mặt đất thực tế.
- Tính quãng đường di chuyển thực tế $d = \sqrt{(X_t - X_{t-k})^2 + (Y_t - Y_{t-k})^2}\text{ (mét)}$.
- Vận tốc tức thời được tính theo công thức:
  $$v = \frac{d}{\Delta t} \times 3.6 \quad (\text{km/h}), \quad \text{với } \Delta t = \frac{k}{\text{FPS}}$$
- Lọc nhiễu dao động vận tốc bằng bộ lọc Kalman Filter hoặc Exponential Moving Average (EMA, $\alpha = 0.3$) để loại bỏ sai số rung lắc bounding box.

### FR-07: Bắt Lỗi & Cắt Clip Bằng chứng Vi phạm Quá tốc độ (Overspeed Capture & Alert)
- Cấu hình ngưỡng tốc độ giới hạn trên từng làn (Speed Limit, ví dụ $50\text{ km/h}$ hoặc $80\text{ km/h}$).
- Khi phương tiện vượt quá ngưỡng quy định:
  - Tự động chụp ảnh snapshot độ phân giải cao có khoanh viền đỏ quanh phương tiện, hiển thị nhãn: `ID`, `Loại xe`, `Tốc độ: XX km/h`.
  - Tự động trích xuất đoạn video clip bằng chứng ngắn $6\text{ giây}$ (3 giây trước và 3 giây sau khi chạm vạch đo) từ Ring Buffer của luồng streaming.
  - Lưu trữ tệp bằng chứng an toàn vào MinIO / S3 với chữ ký số băm SHA-256.

### FR-08: Thống kê Lưu lượng & Phân tích Giao thông Thông minh (Traffic Analytics)
- Tự động tổng hợp và ghi nhận vào CSDL TimescaleDB:
  - Lưu lượng xe theo từng khung giờ (Xe/giờ), theo ngày, theo tuần.
  - Tỷ lệ cơ cấu các loại phương tiện (Modal Split: % xe máy, % ô tô con, % xe tải...).
  - Vận tốc trung bình (Average Speed) và vận tốc phân vị 85 (85th Percentile Speed) trên từng làn đường.
  - Tự động cảnh báo ùn tắc giao thông (Traffic Congestion Alert) khi vận tốc trung bình giảm dưới ngưỡng cấu hình trong $> 5\text{ phút}$.

### FR-09: Bộ Công cụ Gán nhãn Label Studio Community & Thu thập Dữ liệu Thực tế
- Sử dụng $100\%$ dữ liệu ảnh thực tế trích xuất từ các luồng streaming qua `collector_gui.py`.
- Tích hợp tệp cấu hình mẫu Label Studio Community (`annotation/label_studio_template.xml`) chuẩn xuất định dạng YOLO TXT với đầy đủ phím tắt và màu sắc trực quan.
- Quy trình kiểm thử chất lượng dữ liệu (QA/QC) và huấn luyện chủ động (Active Learning).

---

## 5. YÊU CẦU PHI CHỨC NĂNG (NON-FUNCTIONAL REQUIREMENTS - NFR)

### 5.1. Hiệu năng & Khả năng Xử lý Luồng (Streaming Performance & Concurrency)
- **NFR-PERF-01 (Mật độ luồng trên mỗi GPU):** Mỗi GPU NVIDIA RTX 4090 hoặc NVIDIA L4 (24GB VRAM) phải xử lý đồng thời tối thiểu **20 - 32 luồng streaming Full HD 1080p @ 25-30fps** cho toàn bộ pipeline (Decode $\rightarrow$ YOLO $\rightarrow$ ByteTrack $\rightarrow$ Speed $\rightarrow$ Counting).
- **NFR-PERF-02 (Thời gian xử lý khung hình):** Tổng thời gian xử lý toàn bộ các công đoạn trên mỗi frame $\le \mathbf{60 - 75\text{ ms}}$.
- **NFR-PERF-03 (Bù trễ truyền dẫn):** Sai số đồng bộ thời gian đo tốc độ giữa timestamp video và đồng hồ hệ thống $\le 20\text{ ms}$.

### 5.2. Độ chính xác & Khả năng Đo lường (Accuracy & Measurement Tolerances)
- **NFR-ACC-01 (Độ chính xác đếm xe):** Tỷ lệ đếm đúng phương tiện đạt $\ge \mathbf{97.5\%}$ trên luồng giao thông thực tế.
- **NFR-ACC-02 (Sai số đo tốc độ):** Sai số đo tốc độ tuyệt đối $\le \mathbf{\pm 3 - 5\text{ km/h}}$ trong dải vận tốc $10 - 120\text{ km/h}$.
- **NFR-ACC-03 (Độ chính xác phân loại loại xe):** Chỉ số $\text{mAP50}$ của mô hình phát hiện & phân loại phương tiện đạt $\ge \mathbf{92.0\%}$.

### 5.3. Độ tin cậy & Tính liên tục (Reliability & Continuous Operation)
- **NFR-REL-01 (Zero Memory Leak):** Pipeline hoạt động liên tục 30 ngày đêm không bị rò rỉ bộ nhớ VRAM và RAM ($< 5\%$ tăng trưởng).
- **NFR-REL-02 (Tự động phục hồi luồng):** Khi kết nối luồng camera bị gián đoạn, hệ thống tự động tái kết nối trong vòng $\le 3\text{ giây}$.

### 5.4. Yêu cầu Huấn luyện Mô hình & Lượng hóa (Model Training & Quantization)
- **NFR-MLOPS-01 (Huấn luyện từ đầu):** Mô hình YOLOv11 Vehicle Detector được huấn luyện từ đầu trên tập dữ liệu thực tế ngày & đêm, hội tụ ổn định sau 200 - 300 epochs.
- **NFR-MLOPS-02 (Lượng hóa TensorRT / OpenVINO):** Mô hình phải được tối ưu sang TensorRT FP16/INT8 (GPU) hoặc OpenVINO INT8 (CPU), đảm bảo thời gian suy luận $\le 5\text{ ms/frame}$.

### 5.5. An toàn thông tin & Bảo mật Dữ liệu (Security & Privacy)
- **NFR-SEC-01 (Mã hóa luồng truyền):** Sử dụng các giao thức mã hóa chuẩn HTTPS, RTSPS, WebRTC SRTP/DTLS hoặc SRT AES-256.
- **NFR-SEC-02 (Tuân thủ quyền riêng tư):** Hình ảnh và video lưu trữ bằng chứng được bảo mật lưu trữ mã hóa At-Rest AES-256. Có tùy chọn làm mờ khuôn mặt người tham gia giao thông theo Nghị định 13/2023/NĐ-CP.

---
*Tài liệu này là căn cứ kỹ thuật chính thức cho kiến trúc hệ thống đếm và đo tốc độ phương tiện giao thông thông minh.*
