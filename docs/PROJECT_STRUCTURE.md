# Cấu trúc dự án và hướng dẫn phát triển

## Phân chia trách nhiệm

```text
detect-vehicle/
├── vehicle_detection/
│   ├── paths.py                 # Đường dẫn mặc định tính từ vị trí checkout
│   ├── classes.py               # Mapping 8 lớp dùng chung trong mã nguồn
│   ├── collection/
│   │   ├── gui.py               # Thu thập GUI và CLI OpenCV
│   │   ├── ffmpeg.py            # Thu thập bằng FFmpeg
│   │   ├── extractor.py         # Lọc chuyển động/pHash, chia gói gán nhãn
│   │   └── storage.py           # Quy tắc thư mục camera/ngày/khung giờ
│   ├── data/
│   │   └── validate.py          # Kiểm tra dataset và tạo cấu hình train cục bộ
│   └── inference/
│       ├── demo.py              # Đọc video, YOLO/ByteTrack, hiển thị kết quả
│       ├── calibration.py       # Đọc và kiểm tra hình học camera từ JSON
│       ├── speed.py             # Homography và ước lượng tốc độ theo track
│       └── counting.py          # Đếm track cắt vạch
├── annotation/                  # Cấu hình và hướng dẫn Label Studio
├── configs/cameras/             # JSON hiệu chuẩn dùng lúc suy luận
├── data/                        # Đầu vào và dữ liệu trung gian
├── models/                      # Weights đầu vào/đã huấn luyện
├── outputs/                     # Kết quả, báo cáo và cấu hình riêng cho máy
├── tests/                       # Kiểm thử tự động
├── docs/                        # Tài liệu vận hành và thiết kế
├── collector_gui.py             # Entry point tương thích
├── stream_capture_ffmpeg.py     # Entry point tương thích
├── speed_estimation_demo.py     # Entry point tương thích
└── training/                    # Entry point tương thích
```

Chạy `python -m vehicle_detection.<module>` tại gốc dự án, không chạy trực tiếp
file nằm bên trong package. Package này chưa được đóng gói để cài bằng pip.
Các wrapper cũ giữ lệnh chạy; mã nguồn chính được sửa trong package.

## Lệnh chạy

| Công việc | Lệnh từ gốc dự án |
| --- | --- |
| GUI thu thập | `python -m vehicle_detection.collection.gui` |
| CLI thu thập | `python -m vehicle_detection.collection.gui --stream "video.mp4" --tag cam01` |
| FFmpeg | `python -m vehicle_detection.collection.ffmpeg --stream "video.mp4" --tag cam01` |
| Lọc chuyển động/pHash | `python -m vehicle_detection.collection.extractor --stream "video.mp4" --tag cam01 --max-frames 1000` |
| Chia gói từ ảnh có sẵn | `python -m vehicle_detection.collection.extractor --split-from "data/raw/frames/cam01/2026-11-13_08h-09h" --split-machines 4` |
| Kiểm tra dataset | `python -m vehicle_detection.data.validate` |
| Xem tham số demo | `python -m vehicle_detection.inference.demo --help` |

GUI và CLI OpenCV/FFmpeg mặc định lưu ảnh vào `data/raw/frames/`. Tham số
`--output` hoặc nút chọn thư mục GUI vẫn cho phép lưu nơi khác. Với `--output`
do người dùng nhập, đường dẫn tương đối được tính theo thư mục chạy lệnh.

Extractor lưu ảnh và manifest vào khung giờ bắt đầu phiên; GUI/FFmpeg chuyển
thư mục khi sang giờ mới. Gói giao gán nhãn mặc định nằm ở
`data/annotation_batches/may_con_01/` ...; dùng `--batches-output` để đặt thư mục
đợt riêng, tránh ghi đè khi chia lại. Chức năng chia gói chỉ đọc ảnh ngay trong
`--split-from`, không duyệt các thư mục con và không chia train/val/test.

## Chuyển từ cấu trúc cũ

Refactor không tự di chuyển dữ liệu cá nhân. Nếu có dữ liệu ở đường dẫn cũ:

| Vị trí trước đây | Vị trí mới |
| --- | --- |
| `dataset_collected/<camera>/<ngày>_<giờ>/` | `data/raw/frames/<camera>/<ngày>_<giờ>/` |
| `real_stream_dataset/raw_frames/<tag>/` | `data/raw/frames/<camera>/<session_id>/` |
| `real_stream_dataset/capture_manifest_<tag>.jsonl` | Đặt cạnh ảnh trong phiên tương ứng |
| `real_stream_dataset/workstation_batches/` | `data/annotation_batches/<batch_id>/` |
| Dataset YOLO đã chia tập ở nơi khác | `data/vehicle_detection/`, sau khi kiểm tra class ID |

Sao chép trước, kiểm tra số file và ghép cặp ảnh/nhãn rồi mới xử lý bản cũ theo
chính sách sao lưu của nhóm. Không đè các đợt có cùng tên. Ghi lại đường dẫn
gốc trong metadata để giữ khả năng truy vết. Các thư mục cũ vẫn nằm trong
`.gitignore` để tránh vô tình đưa dữ liệu lên Git.

## Quy tắc thay đổi mã nguồn

- Thêm đường dẫn mặc định vào `paths.py`; tránh gắn đường dẫn vào vị trí file GUI.
- Sửa logic chia khung giờ tại `collection/storage.py` để các công cụ dùng chung.
- Mapping lớp chuẩn nằm trong `classes.py`. Nếu thay đổi schema lớp, cập nhật
  `data/vehicle_detection/classes.txt`, `data.yaml`, XML Label Studio và tài liệu;
  cần chuyển ID của nhãn cũ trước khi dùng với schema mới.
- Cấu hình camera thật đặt ở `configs/cameras/<camera_id>.json`; file `.example.json`
  chỉ minh họa. Backup cấu hình thật ở kho dữ liệu của nhóm vì Git bỏ qua file này.
- Kết quả và log để trong `outputs/`; không đặt weights trong mã nguồn.

## Kiểm tra sau thay đổi

```powershell
python -m unittest discover -s tests -v
python -m compileall -q vehicle_detection collector_gui.py stream_capture_ffmpeg.py speed_estimation_demo.py training
python -m vehicle_detection.collection.ffmpeg --help
python -m vehicle_detection.collection.extractor --help
python -m vehicle_detection.data.validate --help
python -m vehicle_detection.inference.demo --help
```

Kiểm thử tự động dùng dữ liệu tạm và không cần camera/GPU. Kiểm thử thuật toán
đếm/tốc độ cần NumPy/OpenCV. Việc kiểm tra cú pháp/CLI không chứng minh chất
lượng model hoặc độ chính xác đo tốc độ ngoài thực địa.

## Giới hạn hiện tại

Demo có một vạch đếm, mỗi track được tính một lần; chưa quản lý nhiều làn hoặc
xuất bảng đếm theo thời gian. Tốc độ tính theo chỉ số frame/FPS, chưa dùng timestamp
thực của từng frame. Chưa có pipeline tự động chuyển JSON Label Studio, remap lớp,
gộp/chia dataset hoặc đánh giá ground truth. Các bước này được ghi rõ trong
[DATA_GUIDE.md](DATA_GUIDE.md) để thực hiện và kiểm duyệt trước khi huấn luyện.
