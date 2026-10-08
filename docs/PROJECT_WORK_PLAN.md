# KẾ HOẠCH PHÂN CHIA CÔNG VIỆC NHÓM 5 THÀNH VIÊN
## ĐỀ TÀI: HỆ THỐNG ĐẾM VÀ ĐO TỐC ĐỘ PHƯƠNG TIỆN GIAO THÔNG TỪ LUỒNG VIDEO STREAMING
### (PHẠM VI TINH GỌN: 1 GÓC CAMERA TĨNH - TẬP TRUNG BAN NGÀY & BAN ĐÊM)

**Mã tài liệu:** PLAN-SPEED-COUNT-TEAM5-2026  
**Phiên bản:** 2.0.0 (Cập nhật Toàn diện Bài toán Đếm Xe & Đo Tốc độ)  
**Tình trạng:** Kế hoạch thực thi chính thức của nhóm

---

## 1. BỐI CẢNH & NGUYÊN TẮC PHÂN CÔNG CÔNG VIỆC

### 1.1. Phạm vi kỹ thuật điều chỉnh tinh gọn
Để đảm bảo đề tài đạt độ chính xác tối đa (sai số đo tốc độ $\le \pm 3 - 5\text{ km/h}$, tỷ lệ đếm đúng $\ge 97.5\%$), loại bỏ các yếu tố nhiễu không kiểm soát và hoàn thành đúng tiến độ học thuật:
1. **Nguồn dữ liệu đầu vào:** Sử dụng **1 góc camera tĩnh duy nhất (Single Fixed Traffic Camera Stream)** làm luồng tiếp nhận chính (RTSP / HLS / Video ghi thực địa).
2. **Kịch bản ánh sáng tập trung:** Tập trung dữ liệu vào **2 điều kiện cốt lõi**:
   - **Ban ngày (Daytime standard):** Khung giờ $07\text{h}00 - 17\text{h}30$ (ánh sáng tự nhiên, mật độ phương tiện dày đặc). Chiếm $\mathbf{60\%}$ tập dữ liệu.
   - **Ban đêm (Nighttime with headlights):** Khung giờ $18\text{h}30 - 23\text{h}30$ (môi trường thiếu sáng, đèn đường và đèn pha xe). Chiếm $\mathbf{40\%}$ tập dữ liệu.
3. **8 nhóm phương tiện trọng tâm:** `motorcycle`, `car`, `electric_bicycle`, `bicycle`, `bus`, `truck`, `container_truck`, `special_vehicle`.

### 1.2. Phân định trách nhiệm cốt lõi
- **Thành viên 1 (Bạn / Trưởng nhóm):**
  - *Đã hoàn thành:* Xây dựng bộ công cụ thu thập tự động ([collector_gui.py](../collector_gui.py)), thu thập dữ liệu ảnh thực tế từ luồng stream tĩnh, phân bổ thư mục theo khung giờ 1h kèm bộ lọc pHash và Laplacian Variance.
  - *Đảm nhận kỹ thuật chính:* Thực hiện huấn luyện mô hình **YOLOv11 Vehicle Detector** từ đầu trên Google Colab; xây dựng module tích hợp **ByteTrack**, **Line-Crossing Counter** và **Homography Speed Estimator**; tối ưu hóa xuất mô hình sang ONNX, TensorRT INT8 và Intel OpenVINO.
- **Khối lượng phân chia cho các thành viên (TV 2, 3, 4, 5):**
  - **Dán nhãn dữ liệu (Data Annotation):** Sử dụng **Label Studio Community Edition** hoặc **X-AnyLabeling**, chia đều 2 tập Ban ngày và Ban đêm cho 4 thành viên.
  - **Soạn thảo Báo cáo Tiểu luận (Report/Thesis):** Chia đều 5 chương học thuật chặt chẽ cho 5 thành viên.

---

## 2. MA TRẬN PHÂN CÔNG TRÁCH NHIỆM (RACI MATRIX)

| Thành viên | Vai trò dự án | Phần việc Dán nhãn phụ trách | Phần việc Báo cáo phụ trách | Trách nhiệm |
| :--- | :--- | :--- | :--- | :---: |
| **TV 1 (Bạn)** | **Trưởng nhóm & Kỹ sư AI / MLOps Lead** | **Data QA/QC Lead:** Kiểm duyệt chéo 10% dữ liệu mỗi gói; tạo tập Test độc lập (~800 frame); gộp Master Dataset; viết code tích hợp AI + Speed Engine. | **Chương 4:** Thực nghiệm Huấn luyện YOLOv11 & Đánh giá Sai số Đo tốc độ / Đếm xe; MLOps. | **Chủ trì** |
| **TV 2** | **Kỹ sư Tiền xử lý & Ingestion** | **Gói Day-1 (Ban ngày sáng):** Khung giờ $07\text{h}00 - 12\text{h}00$ (~1.500 frame; ~9.000 bounding boxes). | **Chương 1:** Tổng quan đề tài, Smart City & ITS, bài toán đếm xe & đo tốc độ từ video streaming. | **Thực hiện** |
| **TV 3** | **Kỹ sư Kiến trúc & Bám vết** | **Gói Day-2 (Ban ngày chiều):** Khung giờ $12\text{h}00 - 17\text{h}30$ (~1.500 frame; ~9.000 bounding boxes). | **Chương 2:** Thiết kế Kiến trúc Hệ thống, Video Streaming Pipeline & Giải thuật Bám vết ByteTrack. | **Thực hiện** |
| **TV 4** | **Kỹ sư Thị giác máy tính & Hình học** | **Gói Night-1 (Ban đêm chập tối):** Khung giờ $18\text{h}30 - 21\text{h}00$ (~1.200 frame; ~7.000 bounding boxes). | **Chương 3:** Cơ sở Lý thuyết Biến đổi Phối cảnh (Homography), Hiệu chuẩn Camera & Lọc nhiễu Kalman Filter. | **Thực hiện** |
| **TV 5** | **Kỹ sư Triển khai & Kiểm thử** | **Gói Night-2 (Ban đêm muộn & Đèn pha):** Khung giờ $21\text{h}00 - 23\text{h}30$ (~1.200 frame; ~7.000 bounding boxes). | **Chương 5:** Triển khai Thực tế, Đánh giá Hiệu năng Real-time và Cảnh báo Quá tốc độ, Kết luận. | **Thực hiện** |

---

## 3. KẾ HOẠCH DÁN NHÃN DỮ LIỆU BAN NGÀY & BAN ĐÊM (DATA ANNOTATION)

### 3.1. Chỉ tiêu định lượng tập dữ liệu
- **Tổng số khung hình toàn cảnh (Frames):** $\mathbf{6.000\text{ khung hình}}$ (Ban ngày: $3.600$ frames; Ban đêm: $2.400$ frames).
- **Tổng số phương tiện được gán nhãn (Vehicle Bboxes):** $\mathbf{\ge 35.000\text{ đối tượng}}$.

### 3.2. Bảng phân bổ chi tiết cho 4 thành viên

| Phân công | Kịch bản dữ liệu thực tế | Số lượng Frame | Số Bboxes dự kiến | Tiêu chuẩn kỹ thuật nghiệm thu |
| :--- | :--- | :---: | :---: | :--- |
| **Thành viên 2** | **Gói Day-1: Ban ngày sáng**<br>*(Khung giờ 07h-12h)* | **1.500 frame** | **~9.000 bboxes** | - Mật độ xe máy và ô tô cao giờ cao điểm.<br>- Khung chữ nhật ôm sát đáy bánh xe.<br>- Phân loại đúng xe máy vs xe đạp điện. |
| **Thành viên 3** | **Gói Day-2: Ban ngày chiều**<br>*(Khung giờ 12h-17h30)* | **1.500 frame** | **~9.000 bboxes** | - Nắng gắt buổi trưa và bóng đổ.<br>- Không kéo khung bao trùm bóng xe.<br>- Phân loại đúng xe tải, xe buýt, xe container. |
| **Thành viên 4** | **Gói Night-1: Ban đêm chập tối**<br>*(Khung giờ 18h30-21h)* | **1.200 frame** | **~7.000 bboxes** | - Đèn đường bật, phương tiện bật đèn demi.<br>- Tăng độ sáng (Brightness) trên Label Studio để nhìn rõ thân xe tối màu. |
| **Thành viên 5** | **Gói Night-2: Ban đêm muộn**<br>*(Khung giờ 21h-23h30)* | **1.200 frame** | **~7.000 bboxes** | - Đèn pha xe rọi ngược vào camera.<br>- Xác định đúng mép tiếp đất của lốp xe dù có vệt sáng đèn pha phản chiếu. |
| **TV 1 (Bạn)** | **QA/QC Lead & Testset độc lập** | **Kiểm tra chéo 10%** | **~3.500 bboxes** | - Kiểm tra ngẫu nhiên độ chính xác của 4 gói.<br>- Tạo tập Testset độc lập gồm 500 mẫu ngày + 300 mẫu đêm.<br>- Đóng gói `master_dataset_yolo.zip`. |

---

## 4. ĐỀ CƯƠNG CHI TIẾT 5 CHƯƠNG TIỂU LUẬN / BÁO CÁO

Tiểu luận được cấu trúc thành 5 chương chuẩn mực học thuật, tập trung xoay quanh luồng video streaming từ 1 camera tĩnh và so sánh thực nghiệm 2 điều kiện Ngày / Đêm:

```
[Chương 1: TV 2] Tổng quan & Bài toán đếm xe, đo tốc độ từ video streaming
       │
[Chương 2: TV 3] Kiến trúc hệ thống, Giải mã phần cứng & Tracking ByteTrack
       │
[Chương 3: TV 4] Cơ sở Lý thuyết Homography, Hiệu chuẩn Camera & Lọc Kalman
       │
[Chương 4: TV 1] Thực nghiệm Huấn luyện YOLOv11 & Đánh giá Sai số Đo tốc độ / Đếm xe
       │
[Chương 5: TV 5] Triển khai Client Real-time, Bắt lỗi Quá tốc độ & Kết luận
```

---
*Kế hoạch thực hiện dự án Đếm và Đo tốc độ phương tiện ITS 2026.*
