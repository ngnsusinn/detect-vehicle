# Detect Vehicle — đếm xe và ước lượng tốc độ

Dự án thu thập ảnh giao thông thực tế, gán nhãn 8 lớp phương tiện bằng Label
Studio, chuẩn bị dataset YOLO và chạy demo bám vết, đếm xe, ước lượng tốc độ.

Hiện có công cụ thu thập GUI/CLI, ghép và kiểm tra dataset, notebook huấn luyện
trên Google Colab, hiệu chuẩn camera, demo suy luận và công cụ đối sánh với
dữ liệu nghiệm thu. Xem [báo cáo đồ án](docs/BAO_CAO_DO_AN.md) để biết kết quả
đã đo và tình trạng từng yêu cầu.

## Bắt đầu

Chạy các lệnh dưới đây tại thư mục gốc dự án. Dùng Python 3.11 trở lên;
FFmpeg cần có trong PATH khi dùng công cụ FFmpeg. GUI cần Tkinter và màn hình.

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python -m vehicle_detection.collection.gui
```

Hoặc nhấp đúp `run_collector.bat`. Ảnh mới mặc định được lưu tại
`data/raw/frames/<camera>/<ngày>_<khung-giờ>/`, độc lập với thư mục chạy lệnh.
Nếu đã có dữ liệu trong `dataset_collected/` hoặc `real_stream_dataset/`, xem
[quy trình chuyển dữ liệu cũ](docs/PROJECT_STRUCTURE.md#chuyển-từ-cấu-trúc-cũ).

Thu thập bằng FFmpeg:

```powershell
python -m vehicle_detection.collection.ffmpeg --stream "video.mp4" --tag cam01
```

## Dữ liệu cần chuẩn bị

Đọc **[hướng dẫn dữ liệu chi tiết](docs/DATA_GUIDE.md)** trước khi gộp dữ liệu:
file cần có, thư mục đích, 8 class ID, metadata, QA, chia train/val/test,
hiệu chuẩn camera, dữ liệu đánh giá và sao lưu.

1. Thu thập ảnh vào `data/raw/frames/`, video gốc nếu có vào `data/raw/videos/`.
2. Gán nhãn theo [template Label Studio](annotation/label_studio_template.xml).
3. Lưu bản xuất gốc ở `data/label_studio/exports/`, giải nén từng đợt vào
   `data/label_studio/extracted/`.
4. Kiểm duyệt và sao chép cặp ảnh/nhãn vào `data/vehicle_detection/`.
5. Kiểm tra và tạo cấu hình train có đường dẫn tuyệt đối:

```powershell
python -m vehicle_detection.data.validate --report outputs/reports/dataset_check.json --config-output outputs/training/data.local.yaml
```

Bộ khung rỗng sẽ báo FAIL cho đến khi có đủ ảnh/nhãn train, val, test.

## Huấn luyện trên Google Colab

Dùng [notebook Colab](training/vehicle_detection_colab.ipynb) với gói
`outputs/training/vehicle-colab-pilot-v1.zip`. Quy trình chuẩn bị gói, thiết lập
GPU và vị trí kết quả được mô tả trong [hướng dẫn huấn luyện](docs/MODEL_TRAINING_PIPELINE.md#chạy-thử-trên-google-colab).

## Ứng dụng Windows

Nhấp đúp `run_traffic_monitor.bat`, hoặc chạy `python traffic_monitor.py` trong
môi trường dự án. Ứng dụng mặc định dùng `models/vehicle_detection/colab-retrain-20261124/best.pt`.
Lấy trọng số từ kho chung hoặc truyền `--model` với đường dẫn đến trọng số đã tải.

Với camera 36, ứng dụng tự nạp hồ sơ tốc độ từ bản đồ khi khung hình khớp với
các mốc cố định. Sau khi mở khung hình, bấm hai đầu vạch rồi chọn **Bắt đầu**.
Đặt vạch trong vùng màu xanh nếu cần tốc độ tại thời điểm qua vạch. Kết quả có
dấu `~` vì khoảng cách lấy từ ảnh vệ tinh và chưa được kiểm chứng thực địa.

1. Dán URL RTSP/HLS hoặc chọn video. Với danh sách JSON có `STSPLINK`, chọn
   **Chọn danh sách camera…** và nhập ID. Nếu muốn đặt nguồn khi khởi động,
   chạy `python traffic_monitor.py --camera-list "C:\du-lieu\cameras.json" --camera-id 36`.
2. Chọn **Mở khung hình**. Đặt tên và ngưỡng cho vạch, bấm **Chọn 2 đầu vạch**
   rồi bấm hai đầu trên ảnh. Nhập tên khác để thêm vạch. Nút **Đảo chiều**
   đổi quy ước IN/OUT của vạch đang chọn.
3. Khi có số đo thực địa, chọn **Chọn 4 điểm vùng đo** rồi bấm lần lượt trái
   xa, phải xa, phải gần, trái gần. Nhập rộng và dài theo mét rồi bật **Đo tốc
   độ bằng kích thước đã đo**. Khi chưa hiệu chuẩn, có thể chạy chế độ chỉ đếm.
4. Lưu cấu hình để dùng lại. Chọn **Bắt đầu** để xem video đã bám vết. **Dừng**
   hoàn tất tệp đầu ra trong `outputs/inference/desktop/`. Vùng và kích thước
   được chỉnh giữa các phiên. URL nhập vào không được ghi trong cấu hình.

## Chạy demo

Đặt model đã train vào `models/vehicle_detection/best.pt`, video kiểm thử vào
`data/evaluation/cam01/traffic.mp4`. Sao chép `configs/cameras/cam01.example.json`
thành `cam01.json` và thay bằng số đo thật của camera trước khi chạy:

```powershell
python -m vehicle_detection.inference.demo --video data/evaluation/cam01/traffic.mp4 --model models/vehicle_detection/best.pt --calibration configs/cameras/cam01.json --output outputs/inference/cam01.mp4 --events-dir outputs/inference/cam01 --headless
```

`--events-dir` ghi `counts.csv` khi xe cắt vạch và `speeds.csv` cho từng mẫu
tốc độ trong vùng hiệu chuẩn, cùng `session_summary.json` tổng hợp lượt đếm,
cơ cấu xe, tốc độ trung bình và P85 theo vạch. Bỏ `--headless` để mở video
khi chạy. Dùng `--timing pts` nếu cần bắt buộc dùng timestamp từ video và
`--evidence-dir` nếu cần lưu ảnh và clip vượt ngưỡng trong vùng đã hiệu chuẩn.

`--model` nhận đường dẫn trọng số `.pt`, `.onnx` hoặc thư mục mô hình OpenVINO.
Xem [lệnh xuất và kiểm tra model](docs/MODEL_TRAINING_PIPELINE.md#xuất-bản-onnx-và-openvino-int8).

Để xử lý camera trực tiếp, truyền `--video "<URL RTSP hoặc HLS>"` cùng
`--model models/vehicle_detection/best.pt`. Nếu đã có danh sách JSON với các
trường `ID`, `TEN` và `STSPLINK` trong `data`, chọn một camera bằng ID:

```powershell
python -m vehicle_detection.inference.demo --camera-list "C:\du-lieu\cameras.json" --camera-id 40
```

Lệnh trên tự chọn `models/vehicle_detection/best.pt` nếu bỏ `--model`. Đổi
`40` thành ID của nguồn cần chạy. Khi đo tốc độ, truyền `--calibration` với
cấu hình đã đo đúng camera và đúng độ phân giải của luồng.

Không truyền `--calibration` thì demo dùng hình học minh họa và in cảnh báo;
kết quả tốc độ khi đó không dùng để đánh giá. Với `--video` và không truyền
`--model`, demo dùng model dựng sẵn `yolo11n.pt`.

## Nghiệm thu

Dùng [quy trình ghi video, hiệu chuẩn và đối sánh](docs/DATA_GUIDE.md#7-dữ-liệu-hiệu-chuẩn-camera-để-ước-lượng-tốc-độ)
để tạo báo cáo với dữ liệu thực địa. Ba mẫu CSV nằm trong `data/metadata/`.

```powershell
python -m vehicle_detection.inference.evaluate --events outputs/inference/cam01 --count-truth data/evaluation/cam01/counts_ground_truth.csv --speed-truth data/evaluation/cam01/speeds_ground_truth.csv --track-links data/evaluation/cam01/track_links.csv --dataset-kind field --output outputs/reports/cam01-evaluation.json
```

## Cấu trúc chính

```text
vehicle_detection/   Mã nguồn: collection/, data/, inference/, paths.py, classes.py
annotation/          Template XML và hướng dẫn Label Studio
configs/cameras/     Cấu hình hình học của từng camera
data/               Dữ liệu gốc, gán nhãn, dataset, metadata, hiệu chuẩn, đánh giá
models/              Weights đầu vào và model đã huấn luyện
outputs/             Báo cáo, cấu hình máy train, kết quả huấn luyện và suy luận
training/            Điểm chạy tương thích với đường dẫn cũ
tests/               Kiểm thử quy tắc dữ liệu, hiệu chuẩn và thuật toán
docs/               Hướng dẫn vận hành và tài liệu thiết kế
```

Xem [cấu trúc mã nguồn và cách chuyển dữ liệu cũ](docs/PROJECT_STRUCTURE.md).
Các lệnh `python collector_gui.py`, `python stream_capture_ffmpeg.py`,
`python speed_estimation_demo.py` và các lệnh trong `training/` vẫn được hỗ trợ.

## Tài liệu

- [Dữ liệu cần có và nơi lưu](docs/DATA_GUIDE.md)
- [Cấu trúc dự án và phát triển](docs/PROJECT_STRUCTURE.md)
- [Thiết lập Label Studio](annotation/README_LABEL_STUDIO.md)
- [Thu thập dữ liệu](docs/DATA_COLLECTION_GUIDE.md)
- [Quy tắc gán nhãn chi tiết](docs/LABELING_GUIDELINE_DETAIL.md)
- [Tiêu chuẩn kiểm duyệt nhãn](docs/DATA_ANNOTATION_SPECIFICATION.md)
- [Huấn luyện mô hình](docs/MODEL_TRAINING_PIPELINE.md)
- [Gán nhãn nhóm và Colab](docs/DISTRIBUTED_ANNOTATION_COLAB_GUIDE.md)
- [Phân công nhóm](docs/PROJECT_WORK_PLAN.md)
- [Yêu cầu hệ thống](docs/SRS.md), [kiến trúc](docs/SYSTEM_ARCHITECTURE.md),
  [phần cứng](docs/HARDWARE_SPECIFICATIONS.md)

## Kiểm tra mã nguồn

```powershell
python -m unittest discover -s tests -v
python -m compileall -q vehicle_detection collector_gui.py stream_capture_ffmpeg.py speed_estimation_demo.py training
```
