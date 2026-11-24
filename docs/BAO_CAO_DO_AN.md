# Hệ thống đếm và đo tốc độ phương tiện từ video giao thông

Bản thực nghiệm ngày 23/11/2026 triển khai luồng xử lý cho một camera tĩnh, từ
ghi hình và hiệu chuẩn đến xuất số liệu đếm và tốc độ. YOLO11n đã được huấn luyện
trên Google Colab. Bộ kiểm thử giả lập xác nhận thuật toán hình học và đầu ra
nghiệm thu. Độ chính xác của mô hình hiện tại và dữ liệu thực địa giới hạn mức
nghiệm thu của đồ án.

## Chương 1. Bài toán và phạm vi

Đầu vào là video liên tục từ camera cố định. Hệ thống phát hiện phương tiện,
theo dõi từng phương tiện qua các frame, đếm lượt cắt vạch theo hai hướng và
ước lượng tốc độ trong vùng mặt đường đã hiệu chuẩn. Tám lớp được quy định
trong [bảng lớp và quy trình dữ liệu](DATA_GUIDE.md). Đơn vị đếm là một lượt
cắt trên mỗi vạch theo ID bám vết. Tổng liên làn là tổng lượt cắt, nên một xe
đi qua nhiều vạch có thể xuất hiện trong nhiều thống kê.

Phạm vi thực nghiệm tập trung vào một camera. Các mục tiêu nhiều camera,
đa giao thức, độ chính xác và vận hành liên tục được quy định trong [SRS](SRS.md).

## Chương 2. Kiến trúc và cách vận hành

FFmpeg ghi video liên tục vào MKV, giữ luồng video nguồn bằng stream copy.
Ứng dụng đọc video, dùng YOLO11n phát hiện xe và ByteTrack cập nhật ID. Điểm
neo là trung điểm cạnh dưới của bounding box. Vạch đếm có hướng và giới hạn
tốc độ riêng. Khi kết thúc phiên, hệ thống ghi video chú thích, các sự kiện
cắt vạch, các mẫu tốc độ, lưu lượng theo giờ của video và thống kê theo làn.

Thư mục bằng chứng cục bộ chứa ảnh, clip khoảng ba giây mỗi phía của sự kiện
và SHA-256 để kiểm tra toàn vẹn. Chỉ phát sinh bằng chứng khi có mẫu tốc độ
tại vạch vượt ngưỡng cấu hình. Chạy demo và công cụ nghiệm thu theo [README](../README.md).

## Chương 3. Hiệu chuẩn và đo lường

Bốn điểm ảnh trên cùng mặt phẳng đường ứng với bốn điểm tính bằng mét. Ma
trận homography chuyển điểm neo sang hệ tọa độ mặt đường. Tốc độ bằng độ dài
dịch chuyển giữa hai mẫu chia cho khoảng thời gian rồi nhân 3,6. Hệ thống dùng
EMA để làm mượt, bỏ mẫu ngoài vùng đo và cập nhật lại lịch sử sau khoảng gián
đoạn dài. Tùy nguồn, thời gian lấy từ PTS hoặc chỉ số frame chia FPS.

Công cụ nghiệm thu ghép sự kiện một-một theo video, vạch, hướng, lớp và dung
sai thời gian. Tốc độ được so với số đo độc lập bằng trung vị của các mẫu
trong cửa sổ tham chiếu sau khi ghép ID xe thủ công với ID ByteTrack. Báo cáo
gồm TP, FP, FN, F1, sai lệch số lượt, MAE, RMSE và tỷ lệ phép đo có mẫu.
Quy tắc nhập số đo và mẫu CSV được mô tả trong [hướng dẫn nghiệm thu](DATA_GUIDE.md#8-dữ-liệu-đánh-giá-đếm-xe-và-tốc-độ).

## Chương 4. Thực nghiệm

### Phát hiện phương tiện

Pilot Colab gồm 296 ảnh và 5.681 hộp nhãn, chia 154 train, 41 validation và
101 test theo các đoạn quay. Tất cả lấy từ cùng một camera vào buổi sáng.
Tập train thiếu xe container. Tập test có 1.406 hộp xe máy, 681 hộp ô tô con,
82 hộp xe tải và một hộp xe đạp. Thứ tự lớp của gói 0300–0400 dùng mapping
template dự án vì ZIP chỉ chứa nhãn văn bản.

YOLO11n được khởi tạo từ YAML và huấn luyện 80 epoch trên Tesla T4. Trên 101
ảnh test, precision đạt 72,4%, recall 39,4%, mAP50 41,1% và mAP50–95 23,4%.
AP50 theo lớp là 87,0% cho ô tô con, 55,0% cho xe máy, 22,3% cho xe tải và
0% cho xe đạp trên một hộp tham chiếu. Kết quả gốc nằm ở
`outputs/training/vehicle_colab_t4_pilot_v1/test_metrics.json`.

### Bản xuất CPU

Đo riêng trên Ryzen 5 PRO 4650U với cùng 101 ảnh, ảnh đầu vào 640 px, batch 1
và preprocessing vuông. Điều kiện này khác lượt đánh giá Colab. Thời gian
trong bảng là thời gian suy luận của detector trên mỗi ảnh.

| Dạng mô hình | mAP50 | mAP50–95 | Suy luận |
| --- | ---: | ---: | ---: |
| PyTorch | 42,05% | 24,14% | 76,4 ms/ảnh |
| ONNX FP32 | 42,05% | 24,14% | 55,4 ms/ảnh |
| OpenVINO INT8 | 42,08% | 23,94% | 34,0 ms/ảnh |

OpenVINO INT8 được hiệu chuẩn trên 154 ảnh train. Lượt chạy OpenVINO đọc đủ
120 frame từ bản phát lại HLS qua HTTP cục bộ. Chi tiết so sánh và SHA-256
nằm trong `outputs/reports/backend-validation.json`.

### Đếm xe và tốc độ

Ca kiểm thử giả lập chạy 80 frame, hai vạch và hai quỹ đạo biết trước với vận
tốc 28,8 km/h. Hai lượt được ghép với đối chứng, MAE bằng 0 trong ca giả lập.
Chỉ làn đặt ngưỡng 20 km/h phát sinh bằng chứng. Clip có 61 frame, bao gồm
frame sự kiện và đủ khung trước/sau theo thời gian danh định.

Trong một ca riêng, ảnh một ô tô từ tập test được ghép vào clip chuyển động
giả lập 90 frame. Mô hình OpenVINO INT8 và ByteTrack đếm đúng một lượt. Tốc
độ tham chiếu là 25,92 km/h, trung vị 11 mẫu đo là 26,27 km/h và sai số tuyệt
đối là 0,35 km/h. Bằng chứng gồm một clip 61 frame. Video và báo cáo nằm tại
`outputs/inference/synthetic-demo/annotated.mp4` và
`outputs/reports/synthetic-motion-evaluation.json`. Ca này kiểm tra hệ thống
với detector thật trên chuyển động có kiểm soát.

Ca thử video ngoài dùng đoạn giây 32–40 của `T1P1-Eufy` từ ForeSpeed. Video
được đổi kích thước về 1152×648. Duyệt frame xác nhận một xe bán tải đi từ
trái sang phải qua vạch tại khoảng 3,8 giây. YOLO11n pilot chạy trên ONNX
bỏ sót lượt này, nên kết quả là 0 TP và 1 FN. Ca thử có một lượt đối chứng
và hình học minh họa, dùng để kiểm tra khả năng chuyển sang góc camera khác.
Báo cáo nằm ở `outputs/reports/forespeed-count.json`. Nguồn video của Iuliani
và cộng sự được dùng theo giấy phép CC BY-NC 4.0. [ForeSpeed](https://github.com/ampedsoftware/forespeed) · [Giấy phép](https://github.com/ampedsoftware/forespeed/blob/main/LICENSE.txt)

## Chương 5. Kết luận nghiệm thu

| Yêu cầu | Tình trạng |
| --- | --- |
| FR-01, FR-02. Video và thời gian | Đã thử với MP4, MKV và HLS phát lại. Đã hỗ trợ PTS và FPS danh định. RTSP thực địa, tự kết nối lại, WebRTC, SRT, RTMP và giải mã NVDEC chưa được kiểm chứng hoặc triển khai đầy đủ. |
| FR-03, FR-04. Phát hiện và bám vết | Đã train pilot 8 đầu ra, chạy ByteTrack và kiểm tra ba định dạng. Thiếu ảnh đêm và lớp hiếm. Mục tiêu mAP50 ≥ 92% chưa đạt. |
| FR-05, FR-06. Đếm và đo tốc độ | Có vạch theo làn, hiệu chuẩn và công cụ đối sánh. Ca giả lập đạt. Ca ngoài bỏ sót một lượt. Chưa có kết quả sai số đếm/tốc độ trên camera đồ án. |
| FR-07. Cảnh báo và bằng chứng | Có ảnh, clip và SHA-256 cục bộ. Lưu trữ MinIO/S3, mã hóa, làm mờ khuôn mặt và nghiệm thu bảo mật vẫn thuộc triển khai thực tế. |
| FR-08. Thống kê | Có báo cáo phiên theo vạch và giờ video, cơ cấu, trung bình và P85. Còn thiếu TimescaleDB, dashboard trực tuyến, tổng hợp nhiều phiên và cảnh báo ùn tắc. |
| FR-09. Dữ liệu | Có công cụ thu thập, mẫu Label Studio và kiểm tra dataset. Chưa có tập ngày/đêm đủ tám lớp hoặc vòng gán nhãn chủ động hoàn chỉnh. |
| NFR. Hiệu năng và vận hành | Có phép đo CPU cho detector. Chưa đạt mục tiêu 5 ms/ảnh trên CPU thử nghiệm. Các phép thử nhiều luồng, tự phục hồi và chạy liên tục 30 ngày còn thiếu môi trường đo. |

Nghiệm thu thực địa cần video ngày và đêm từ camera mục tiêu, kích thước
mặt đường đo tại bốn điểm ảnh đã chọn, sự kiện đối chứng và tốc độ tham chiếu
đồng bộ của từng xe. Các chỉ tiêu về độ chính xác được chốt sau khi chạy công
cụ nghiệm thu trên dữ liệu đó.
