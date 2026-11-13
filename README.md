# Detect Vehicle — đếm xe và ước lượng tốc độ

Dự án thu thập ảnh giao thông thực tế, gán nhãn 8 lớp phương tiện bằng Label
Studio, chuẩn bị dataset YOLO và chạy demo bám vết, đếm xe, ước lượng tốc độ.

Hiện có công cụ thu thập GUI/CLI, kiểm tra dataset, hiệu chuẩn camera qua JSON
và demo suy luận. Chưa có dataset, model 8 lớp đã huấn luyện hoặc kết quả đánh
 giá thực tế được cung cấp trong repository. Backend, dashboard, triển khai đa
camera và các chỉ tiêu trong tài liệu kiến trúc là mục tiêu thiết kế.

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
Trình kiểm tra không tự gộp, sửa nhãn hay chia tập.

## Chạy demo

Đặt model đã train vào `models/vehicle_detection/best.pt`, video kiểm thử vào
`data/evaluation/cam01/traffic.mp4`. Sao chép `configs/cameras/cam01.example.json`
thành `cam01.json` và thay bằng số đo thật của camera trước khi chạy:

```powershell
python -m vehicle_detection.inference.demo --video data/evaluation/cam01/traffic.mp4 --model models/vehicle_detection/best.pt --calibration configs/cameras/cam01.json --output outputs/inference/cam01.mp4
```

Không truyền `--calibration` thì demo dùng hình học minh họa và in cảnh báo;
kết quả tốc độ khi đó không dùng để đánh giá. Model mặc định `yolo11n.pt` là
model có sẵn, không đại diện cho bộ 8 lớp phương tiện của dự án.

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
