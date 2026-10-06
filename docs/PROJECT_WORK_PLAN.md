# KẾ HOẠCH PHÂN CHIA CÔNG VIỆC NHÓM 5 THÀNH VIÊN
## ĐỀ TÀI: HỆ THỐNG NHẬN DIỆN BIỂN SỐ XE TỪ LUỒNG VIDEO STREAMING (ALPR ITS)
### (PHẠM VI TINH GỌN: 1 GÓC CAMERA TĨNH - TẬP TRUNG BAN NGÀY & BAN ĐÊM)

**Mã tài liệu:** PLAN-ALPR-TEAM5-2026  
**Phiên bản:** 2.0.0 (Cập nhật phạm vi 1 Camera Tĩnh & 2 Kịch bản Ngày/Đêm)  
**Tình trạng:** Kế hoạch thực thi chính thức của nhóm

---

## 1. BỐI CẢNH & NGUYÊN TẮC PHÂN CÔNG CÔNG VIỆC

### 1.1. Phạm vi kỹ thuật điều chỉnh tinh gọn
Để đảm bảo đề tài đạt độ chính xác tối đa ($\ge 96.5\%$), loại bỏ các yếu tố nhiễu không kiểm soát và hoàn thành đúng tiến độ học thuật:
1. **Nguồn dữ liệu đầu vào:** Sử dụng **1 góc camera tĩnh duy nhất (Single Fixed Roadside/Traffic Camera Stream)** làm luồng tiếp nhận chính (RTSP / HLS / Video camera cố định). Loại bỏ việc xử lý đa camera phân tán phức tạp ở giai đoạn này.
2. **Kịch bản ánh sáng tập trung:** Tập trung toàn bộ dữ liệu vào **2 điều kiện cốt lõi**:
   - **Ban ngày (Daytime standard):** Khung giờ $07\text{h}00 - 17\text{h}30$ (ánh sáng tự nhiên, độ tương phản cao, mật độ phương tiện dày đặc). Chiếm $\mathbf{60\%}$ tập dữ liệu.
   - **Ban đêm (Nighttime with headlights):** Khung giờ $18\text{h}30 - 23\text{h}30$ (môi trường thiếu sáng, biển số bị rọi đèn pha chói lóa - Headlight Glare). Chiếm $\mathbf{40\%}$ tập dữ liệu.
   - **Loại trừ tạm thời:** Các trường hợp thời tiết cực đoan như mưa bão, mặt đường đọng vũng nước phản chiếu, sương mù dày đặc... tạm thời được loại bỏ để tối ưu hóa độ hội tụ của mô hình nhận diện.

### 1.2. Phân định trách nhiệm cốt lõi
- **Thành viên 1 (Bạn / Trưởng nhóm):**
  - *Đã hoàn thành:* Xây dựng bộ công cụ thu thập tự động ([collector_gui.py](../collector_gui.py), [training/stream_frame_extractor.py](../training/stream_frame_extractor.py)), thu thập và trích xuất dữ liệu ảnh thực tế từ luồng stream tĩnh, phân bổ thư mục theo khung giờ 1h kèm bộ lọc pHash chống trùng lặp.
  - *Đảm nhận kỹ thuật chính:* Thực hiện toàn bộ công tác **Huấn luyện mô hình Deep Learning từ đầu (From-Scratch)** trên Google Colab (YOLOv11 phát hiện xe, YOLOv11-Pose 4 góc biển số, Deep OCR PP-OCRv4/CRNN-CTC); tối ưu hóa và xuất mô hình sang ONNX, TensorRT INT8 và Intel OpenVINO.
- **Khối lượng phân chia cho cả nhóm (Tập trung TV 2, 3, 4, 5):**
  - **Dán nhãn dữ liệu (Data Annotation):** Chia đều 2 tập Ban ngày và Ban đêm cho 4 thành viên.
  - **Soạn thảo Báo cáo Tiểu luận (Report/Thesis):** Chia đều 5 chương học thuật chặt chẽ cho 5 thành viên (mỗi bạn phụ trách 1 chương bám sát tài liệu kỹ thuật có sẵn).

---

## 2. MA TRẬN PHÂN CÔNG TRÁCH NHIỆM (RACI MATRIX)

| Thành viên | Vai trò dự án | Phần việc Dán nhãn phụ trách | Phần việc Tiểu luận phụ trách | Trách nhiệm |
| :--- | :--- | :--- | :--- | :---: |
| **TV 1 (Bạn)** | **Trưởng nhóm & Kỹ sư AI / MLOps** | **Data QA/QC Lead:** Kiểm duyệt chéo 10% dữ liệu mỗi gói; chuẩn bị tập Test độc lập (~800 frame, 2.000 biển); gộp Master Dataset. | **Chương 4:** Thực nghiệm Huấn luyện & MLOps + Tổng hợp toàn bài, Abstract, chuẩn hóa định dạng. | **Chủ trì** |
| **TV 2** | **Kỹ sư Tiền xử lý & Ingestion** | **Gói Day-1 (Ban ngày sáng):** Xe máy & Ô tô khung giờ $07\text{h}00 - 12\text{h}00$ (~1.800 frame; ~6.000 biển OCR). | **Chương 1:** Tổng quan đề tài, Smart City, bài toán nhận diện biển số từ 1 luồng camera tĩnh. | **Thực hiện** |
| **TV 3** | **Kỹ sư Kiến trúc & Hạ tầng** | **Gói Day-2 (Ban ngày chiều):** Xe máy & Ô tô khung giờ $12\text{h}00 - 17\text{h}30$ (~1.800 frame; ~6.000 biển OCR). | **Chương 2:** Thiết kế Kiến trúc Hệ thống, NVDEC Zero-copy, Virtual Trigger & CSDL. | **Thực hiện** |
| **TV 4** | **Kỹ sư Thị giác máy tính** | **Gói Night-1 (Ban đêm chập tối):** Xe máy & Ô tô khung giờ $18\text{h}30 - 21\text{h}00$ (~1.500 frame; ~5.000 biển OCR). | **Chương 3:** Cơ sở Lý thuyết Deep Learning, YOLOv11, Pose 4 góc, Deep OCR & Regex. | **Thực hiện** |
| **TV 5** | **Kỹ sư Triển khai & Tối ưu** | **Gói Night-2 (Ban đêm muộn & Đèn pha):** Xe máy & Ô tô khung giờ $21\text{h}00 - 23\text{h}30$ (~1.500 frame; ~5.000 biển OCR). | **Chương 5:** Triển khai Client chống lag, Thực nghiệm kiểm thử Ngày/Đêm, Kết luận. | **Thực hiện** |

---

## 3. KẾ HOẠCH DÁN NHÃN DỮ LIỆU BAN NGÀY & BAN ĐÊM (DATA ANNOTATION)

### 3.1. Chỉ tiêu định lượng tập dữ liệu
Từ 1 góc camera tĩnh duy nhất, tập dữ liệu được gom lại tối ưu:
- **Tổng số khung hình toàn cảnh (Frames):** $\mathbf{6.600\text{ khung hình}}$ (Ban ngày: $3.600$ frames; Ban đêm: $3.000$ frames).
- **Tổng số ảnh cắt biển số OCR (Plate Crops):** $\mathbf{22.000\text{ biển số}}$ (Ban ngày: $12.000$ biển; Ban đêm: $10.000$ biển).

### 3.2. Bảng phân bổ chi tiết cho 4 thành viên

| Phân công | Kịch bản dữ liệu thực tế | Số lượng Frame (Bbox + Pose) | Số lượng Biển số (Text OCR) | Thách thức kỹ thuật & Tiêu chuẩn nghiệm thu |
| :--- | :--- | :---: | :---: | :--- |
| **Thành viên 2** | **Gói Day-1: Ban ngày sáng**<br>*(Khung giờ 07h-12h)* | **1.800 frame** | **~6.000 biển** | - Mật độ xe lưu thông cao giờ cao điểm sáng.<br>- Chấm 4 góc theo đúng thứ tự: TL $\rightarrow$ TR $\rightarrow$ BR $\rightarrow$ BL.<br>- Biển xe máy 2 dòng phân cách bằng dấu `-` (Ví dụ: `29B1-12345`). |
| **Thành viên 3** | **Gói Day-2: Ban ngày chiều**<br>*(Khung giờ 12h-17h30)* | **1.800 frame** | **~6.000 biển** | - Nắng gắt buổi trưa và chuyển biến ánh sáng chiều.<br>- Chú ý không nhầm bóng xe đổ với thân xe.<br>- Gán đúng phân loại xe: `car`, `motorcycle`, `truck`, `bus`. |
| **Thành viên 4** | **Gói Night-1: Ban đêm chập tối**<br>*(Khung giờ 18h30-21h)* | **1.500 frame** | **~5.000 biển** | - Đèn đường bật, phương tiện bật đèn demi/cos.<br>- Phóng to ảnh để nhận diện rõ 4 góc biển số.<br>- Cẩn thận phân biệt chữ cái `'B'` và số `'8'`, chữ `'D'` và số `'0'`. |
| **Thành viên 5** | **Gói Night-2: Ban đêm muộn**<br>*(Khung giờ 21h-23h30)* | **1.500 frame** | **~5.000 biển** | - Đèn pha chiếu thẳng vào camera (Headlight Glare mạnh).<br>- Căn chỉnh 4 điểm góc chính xác vào mép phôi biển dập nổi.<br>- Gán nhãn cẩn thận các biển xe tải/xe khách chạy đêm. |
| **TV 1 (Bạn)** | **QA/QC Lead & Testset độc lập** | **Kiểm tra chéo 10%** | **2.000 biển (Test)** | - Kiểm tra ngẫu nhiên độ chính xác của 4 gói.<br>- Tạo tập Test độc lập (không trùng train/val) gồm 1.000 mẫu ngày + 1.000 mẫu đêm.<br>- Ghép và nén tệp `master_dataset.zip`. |

---

## 4. ĐỀ CƯƠNG CHI TIẾT & PHÂN CÔNG SOẠN THẢO TIỂU LUẬN

Tiểu luận được cấu trúc thành 5 chương chuẩn mực học thuật, tập trung xoay quanh luồng video streaming từ 1 camera tĩnh và so sánh thực nghiệm 2 điều kiện Ngày / Đêm:

```
[Chương 1: TV 2] Tổng quan & Bài toán nhận diện camera tĩnh
       │
[Chương 2: TV 3] Kiến trúc hệ thống & Xử lý luồng thời gian thực
       │
[Chương 3: TV 4] Cơ sở lý thuyết Deep Learning & Quy chuẩn biển số
       │
[Chương 4: TV 1] Quy trình huấn luyện mô hình từ đầu & MLOps (Bạn)
       │
[Chương 5: TV 5] Triển khai Client chống lag, Đánh giá Ngày/Đêm & Kết luận
```

### Chương 1: Tổng quan Đề tài & Bài toán Nhận diện Luồng Video Streaming
- **Người viết:** **Thành viên 2** *(10 - 12 trang)*
- **Căn cứ tài liệu:** [docs/SRS.md](SRS.md) (Mục 1, 2, 3).
- **Nội dung chi tiết:**
  - `1.1.` Bối cảnh Đô thị thông minh (Smart City) và nhu cầu số hóa giám sát phương tiện giao thông.
  - `1.2.` Những hạn chế cốt tử của hệ thống ANPR truyền thống (phụ thuộc vòng từ vật lý, camera cục bộ).
  - `1.3.` Bài toán tiếp nhận luồng video streaming từ 1 góc camera giao thông cố định (Fixed Camera Ingestion).
  - `1.4.` So sánh các giao thức truyền tải video (RTSP nội bộ, HLS cổng thông tin, WebRTC độ trễ thấp).
  - `1.5.` Mục tiêu đề tài, giới hạn phạm vi nghiên cứu (Tập trung điều kiện Ngày & Đêm trên 1 góc camera).

### Chương 2: Thiết kế Kiến trúc Hệ thống & Xử lý Luồng Thời gian thực
- **Người viết:** **Thành viên 3** *(12 - 14 trang)*
- **Căn cứ tài liệu:** [docs/SYSTEM_ARCHITECTURE.md](SYSTEM_ARCHITECTURE.md) & [docs/HARDWARE_SPECIFICATIONS.md](HARDWARE_SPECIFICATIONS.md).
- **Nội dung chi tiết:**
  - `2.1.` Kiến trúc tổng thể hệ thống ALPR Streaming (Từ Ingestion $\rightarrow$ NVDEC $\rightarrow$ AI $\rightarrow$ Lưu trữ).
  - `2.2.` Cơ chế giải mã phần cứng GPU Zero-copy NVDEC (Triệt tiêu độ trễ sao chép bộ nhớ).
  - `2.3.` Kỹ thuật Bẫy ảo (Virtual Trigger Zone) và Lấy mẫu thích nghi (Adaptive Sampler 10fps).
  - `2.4.` Thuật toán chọn khung hình sắc nét nhất (Laplacian Variance Sharpness Selector) khắc phục nhòe chuyển động.
  - `2.5.` Thiết kế Cơ sở dữ liệu giao dịch (PostgreSQL 16 + TimescaleDB) và đệm cache (Redis).

### Chương 3: Cơ sở Lý thuyết & Các Mô hình Học sâu
- **Người viết:** **Thành viên 4** *(12 - 14 trang)*
- **Căn cứ tài liệu:** [docs/MODEL_TRAINING_PIPELINE.md](MODEL_TRAINING_PIPELINE.md) & [docs/SRS.md](SRS.md) (Mục FR-04).
- **Nội dung chi tiết:**
  - `3.1.` Tổng quan về mạng Nơ-ron tích chập (CNN) trong nhận diện đối tượng.
  - `3.2.` Mô hình Phát hiện Phương tiện YOLOv11 (Kiến trúc C3k2, SPPF, hàm mất mát CIoU Loss).
  - `3.3.` Mô hình Định vị Biển số YOLOv11-Pose (Hồi quy 4 điểm góc, hàm mất mát OKS Loss).
  - `3.4.` Giải thuật Nắn phẳng phối cảnh tự động (Perspective Homography Warping) đưa biển số về dạng trực diện.
  - `3.5.` Mô hình Nhận dạng Ký tự Deep OCR (PP-OCRv4 / SVTR + BiLSTM + CTC Loss).
  - `3.6.` Quy chuẩn biển số Việt Nam (Thông tư 24/2023/TT-BCA) và ma trận Regex xử lý khử nhầm lẫn ký tự.

### Chương 4: Quy trình Huấn luyện Mô hình từ đầu & MLOps Pipeline
- **Người viết:** **Thành viên 1 (Bạn)** *(14 - 16 trang)*
- **Căn cứ tài liệu:** [docs/MODEL_TRAINING_PIPELINE.md](MODEL_TRAINING_PIPELINE.md) & [docs/DISTRIBUTED_ANNOTATION_COLAB_GUIDE.md](DISTRIBUTED_ANNOTATION_COLAB_GUIDE.md).
- **Nội dung chi tiết:**
  - `4.1.` Chiến lược huấn luyện từ đầu (From-Scratch) với 100% dữ liệu streaming thực tế từ 1 camera tĩnh.
  - `4.2.` Quy trình thu thập và tinh lọc dữ liệu theo khung giờ ([collector_gui.py](../collector_gui.py), bộ lọc pHash).
  - `4.3.` Kỹ thuật tăng cường dữ liệu thực tế (Albumentations mô phỏng ánh sáng ngày, chói đèn đêm).
  - `4.4.` Quá trình thực nghiệm huấn luyện trên Google Colab (đồ thị hàm mất mát, phân tích hội tụ).
  - `4.5.` Tối ưu hóa suy luận và Lượng hóa phần cứng TensorRT INT8 / Intel OpenVINO.
  - `4.6.` Vòng lặp học chủ động (Active Learning MLOps Loop).

### Chương 5: Triển khai Ứng dụng Thực tế, Đánh giá Hiệu năng & Kết luận
- **Người viết:** **Thành viên 5** *(10 - 12 trang)*
- **Căn cứ tài liệu:** [docs/HARDWARE_SPECIFICATIONS.md](HARDWARE_SPECIFICATIONS.md) (Mục 5) & [docs/DISTRIBUTED_ANNOTATION_COLAB_GUIDE.md](DISTRIBUTED_ANNOTATION_COLAB_GUIDE.md) (Mục 4).
- **Nội dung chi tiết:**
  - `5.1.` Đánh giá hiệu năng hệ thống trên các máy Client thực tế (PC có GPU rời, Laptop Intel Core i5).
  - `5.2.` Phân tích 4 nguyên lý kỹ thuật đảm bảo 100% không lag (Async Reader, Adaptive 10fps, Virtual Trigger, OpenVINO).
  - `5.3.` Bảng so sánh thực nghiệm độ chính xác và độ trễ giữa Ban ngày và Ban đêm:
    - *Ban ngày:* Accuracy $\ge 96.8\%$, Latency $\le 65\text{ ms}$.
    - *Ban đêm (Lóa đèn):* Accuracy $\ge 93.5\%$, Latency $\le 72\text{ ms}$.
  - `5.4.` Đánh giá bảo mật và quyền riêng tư dữ liệu cá nhân theo Nghị định 13/2023/NĐ-CP.
  - `5.5.` Kết luận đề tài, đánh giá ưu nhược điểm và đề xuất hướng mở rộng trong tương lai.

---

## 5. LỘ TRÌNH THỰC HIỆN 4 TUẦN (TIMELINE GANTT)

| Mốc thời gian | Nhiệm vụ Thành viên 1 (Bạn) | Nhiệm vụ TV 2, 3, 4, 5 | Sản phẩm bàn giao tuần |
| :--- | :--- | :--- | :--- |
| **Tuần 1** | - Bàn giao 4 gói ảnh (Day-1, Day-2, Night-1, Night-2) từ thư mục camera tĩnh.<br>- Hướng dẫn các bạn cài đặt X-AnyLabeling. | - Cài đặt phần mềm X-AnyLabeling.<br>- Dán nhãn thử 200 ảnh đầu tiên để TV 1 nghiệm thu quy chuẩn.<br>- Thống nhất đề cương chi tiết tiểu luận. | 4 gói nhãn thử 200 ảnh đạt chuẩn quy tắc TL-TR-BR-BL. |
| **Tuần 2** | - Theo dõi tiến độ gán nhãn.<br>- Kiểm tra chéo (QA/QC) ngẫu nhiên 10% dữ liệu.<br>- Chuẩn bị tập Testset độc lập. | - Hoàn thành 100% dán nhãn gói được giao (1.500 - 1.800 frame + text OCR).<br>- Nộp gói `dataset_partX.zip` lên Google Drive.<br>- Bắt đầu viết 50% nội dung chương tiểu luận. | 100% dữ liệu gán nhãn hoàn tất + Bản phác thảo 50% tiểu luận. |
| **Tuần 3** | - Huấn luyện cả 3 mô hình trên Google Colab GPU.<br>- Xuất weights ONNX, lượng hóa TensorRT INT8 / OpenVINO.<br>- Cung cấp metrics (Loss curve, mAP, FPS, latency) cho TV 4 & TV 5. | - Hoàn thành 100% bản nháp chương tiểu luận của mình.<br>- Chèn các hình ảnh sơ đồ, biểu đồ và công thức toán học từ `docs/`. | 3 Model weights (.onnx / .engine) + 100% bản nháp 5 chương. |
| **Tuần 4** | - Chủ trì ghép 5 chương thành 1 file báo cáo duy nhất.<br>- Chuẩn hóa format (Times New Roman 13, giãn dòng 1.3, mục lục tự động). | - Đọc chéo soát lỗi chính tả, câu từ học thuật.<br>- Chuẩn bị Slide thuyết trình bảo vệ đề tài. | File báo cáo hoàn chỉnh (DOCX/PDF) + Slide trình chiếu. |

---

## 6. QUY CHẾ ĐÁNH GIÁ THÀNH VIÊN & TIÊU CHUẨN NGHIỆM THU

Nhóm áp dụng thang điểm đánh giá định lượng 100 điểm cho mỗi thành viên:
1. **Tiến độ hoàn thành (Trọng số 25 điểm):** Nộp đúng hạn theo từng mốc tuần. Chậm mỗi 24h trừ 5 điểm.
2. **Chất lượng gán nhãn dữ liệu (Trọng số 35 điểm):**
   - Tỷ lệ sai sót qua khâu kiểm tra ngẫu nhiên QA/QC (sai thứ tự 4 góc, vẽ lệch bounding box quá 15%, gõ nhầm text OCR) phải **$< 2.0\%$**.
   - Nếu tỷ lệ sai $> 5.0\%$, thành viên phải nhận lại gói dữ liệu và tự rà soát sửa lại trong 24 giờ.
3. **Chất lượng bài viết tiểu luận (Trọng số 40 điểm):**
   - Viết đúng trọng tâm kỹ thuật, diễn đạt lưu loát chuẩn phong cách học thuật.
   - Trình bày công thức toán, hình vẽ minh họa kiến trúc rõ ràng, không sao chép nguyên văn thô thiển từ Internet.
