# Dữ liệu cần chuẩn bị và nơi lưu

Tài liệu này quy định đường dẫn dữ liệu hiện tại của dự án. Mọi đường dẫn tương
đối bên dưới tính từ thư mục gốc `detect-vehicle/`. Repository chỉ cung cấp bộ
khung; ảnh, nhãn, video, model và số đo thực địa phải được nhóm bổ sung.

## 1. Cần dữ liệu gì để làm từng công việc?

| Mục đích | Bắt buộc có | Nơi đặt |
| --- | --- | --- |
| Bắt đầu gán nhãn | Ảnh giao thông thực tế, schema 8 lớp | `data/raw/frames/`, `annotation/label_studio_template.xml` |
| Huấn luyện detector | Ảnh/nhãn YOLO đã duyệt, train/val/test riêng, mapping lớp | `data/vehicle_detection/` |
| Truy vết và tái tạo dataset | Nguồn ảnh, bản xuất gốc, danh sách chia tập, phiên bản dữ liệu | `data/metadata/`, `data/label_studio/exports/` |
| Chạy nhận diện/đếm trên video | Video hoặc luồng camera, weights, vạch đếm | `data/evaluation/`, `models/vehicle_detection/`, `configs/cameras/` |
| Ước lượng tốc độ theo mét | Ảnh camera tham chiếu, tọa độ pixel, khoảng cách đo thực địa, FPS đáng tin cậy | `data/calibration/`, `configs/cameras/` |
| Đánh giá đếm xe | Video độc lập và bảng đếm thủ công theo lớp/hướng/thời gian | `data/evaluation/` |
| Đánh giá sai số tốc độ | Video đồng bộ với phép đo tốc độ tham chiếu và ID phương tiện | `data/evaluation/` |
| Tiếp tục sửa nhãn sau này | JSON export và bản sao lưu Label Studio cùng ảnh gốc | `data/label_studio/exports/`, `data/label_studio/backups/`, `data/raw/` |

Nhãn bounding box đủ để train detector. Nhãn này **không chứa** khoảng cách mặt
đường, ID bám vết, kết quả đếm chuẩn hoặc tốc độ chuẩn; cần thu thập các dữ liệu
đó riêng nếu muốn đánh giá toàn bộ hệ thống.

## 2. Cây thư mục dữ liệu

```text
data/
├── raw/
│   ├── videos/<camera_id>/<session_id>/original.mp4
│   └── frames/<camera_id>/<YYYY-MM-DD>_<HHh-HHh>/*.jpg
├── annotation_batches/<batch_id>/<member_id>/*.jpg
├── label_studio/
│   ├── exports/<batch_id>.zip
│   ├── exports/<batch_id>.json
│   ├── extracted/<batch_id>/images/, labels/, classes.txt
│   └── backups/<backup_id>/
├── vehicle_detection/
│   ├── classes.txt
│   ├── data.yaml
│   ├── images/train/, val/, test/
│   └── labels/train/, val/, test/
├── metadata/
│   ├── sources.csv
│   ├── annotation_batches.csv
│   ├── splits.csv
│   └── releases.csv
├── calibration/<camera_id>/reference.jpg, survey.json
└── evaluation/<camera_id>/<session_id>/
    ├── traffic.mp4
    ├── counts_ground_truth.csv
    └── speeds_ground_truth.csv

configs/cameras/<camera_id>.json
models/vehicle_detection/best.pt, release.json
outputs/training/, inference/, reports/
```

Chỉ các thư mục nền được tạo sẵn. Các thư mục camera/phiên/đợt và file thật
được tạo khi có dữ liệu. Tên video/ảnh gốc được giữ nguyên để truy vết; cây trên
chỉ minh họa tên `original.mp4`, không yêu cầu đổi tên video hiện có.

## 3. Ảnh và video gốc

### 3.1. Nội dung và chất lượng cần thu thập

- Có cả ban ngày và ban đêm, ít xe và đông xe, các hướng di chuyển của camera.
  Mục tiêu phân bổ ban đầu của nhóm là khoảng 60% ngày / 40% đêm; đây là kế
  hoạch lấy mẫu, không phải điều kiện đủ để đảm bảo chất lượng model.
- Có ví dụ thật của cả 8 lớp, ưu tiên bổ sung các lớp hiếm thay vì lấy thêm
  hàng loạt frame gần như giống nhau của xe máy. Theo dõi số bounding box mỗi
  lớp, không chỉ tổng số ảnh.
- Có xe nhỏ/xa, xe bị che khuất, ánh sáng yếu, chói đèn và điều kiện thời tiết
  thực tế dự kiến vận hành. Loại ảnh hỏng; ảnh quá mờ không thể gán nhãn cần
  được tách để rà soát thay vì đoán nhãn.
- Giữ độ phân giải gốc; không resize ảnh sau khi đã gán nhãn nếu chưa cập nhật
  quy trình chuyển đổi. Với YOLO chuẩn hóa, vẫn phải giữ ảnh/nhãn đúng cặp.
- Lưu một số ảnh không có phương tiện làm ảnh âm tính sau khi đã kiểm duyệt.

Không có số lượng ảnh cố định đảm bảo đạt mAP hoặc sai số tốc độ cụ thể.
Chốt mục tiêu số ảnh/bbox từng lớp theo đợt; đánh giá trên tập độc lập rồi quyết
định cần thu thêm tình huống nào. Bộ kiểm tra chỉ xác nhận cấu trúc và định
dạng; không chứng nhận nhãn đúng về mặt thị giác.

### 3.2. Nơi lưu và công cụ tạo

GUI và FFmpeg mặc định ghi vào:

```text
data/raw/frames/cam01/2026-11-13_08h-09h/
```

```powershell
python -m vehicle_detection.collection.gui
python -m vehicle_detection.collection.ffmpeg --stream "data/raw/videos/cam01/session01/original.mp4" --tag cam01 --interval 3
```

Chọn một công cụ phù hợp cho mỗi phiên, không cần chạy đồng thời hai công cụ.
Khung giờ trong tên thư mục phản ánh đồng hồ máy thu thập, **không nhất thiết là
thời gian sự kiện của video ghi sẵn**. Ghi thời gian ghi hình gốc và timezone vào
metadata; không suy ra thời gian thực địa từ tên thư mục khi cắt video cũ.

Video gốc hữu ích để cắt lại ảnh, kiểm tra bám vết và đếm xe. Nếu thu trực tiếp
stream mà không ghi video thì vẫn có thể train từ ảnh đã chụp, nhưng không thể
khôi phục chuỗi chuyển động chỉ bằng các ảnh cách nhau 3 giây. Công cụ chụp ảnh
hiện tại không đồng thời lưu toàn bộ stream thành video.

## 4. Metadata để biết mỗi ảnh đến từ đâu

Sao chép các file `data/metadata/*.example.csv` thành tên tương ứng không có
`.example`, ví dụ `sources.example.csv` → `sources.csv`. Ghi CSV UTF-8, dùng
đường dẫn tương đối với gốc dự án và dấu `/`. Các file này được nhóm điền thủ
công; công cụ chưa tự tạo hoặc đọc chúng.

| File | Mỗi dòng đại diện | Các trường cần chú ý |
| --- | --- | --- |
| `sources.csv` | Một phiên quay/thu thập | `session_id`, `camera_id`, `recorded_at` có múi giờ, `timezone`, `period` là day/night, thời tiết, width/height, FPS, đường dẫn ảnh/video |
| `annotation_batches.csv` | Một đợt giao/nhận nhãn | ID đợt, phiên nguồn, người gán/reviewer, trạng thái, bản xuất và thư mục giải nén, xác nhận mapping lớp |
| `splits.csv` | Một ảnh được đưa vào dataset | Tên ảnh cuối, phiên nguồn, `group_id`, split, batch, đường dẫn ảnh/nhãn nguồn, trạng thái QA |
| `releases.csv` | Một phiên bản dataset đã chốt | Phiên bản/ngày tạo, số ảnh từng split, classes, manifest chia tập, SHA-256 của gói nén |

Quy ước trạng thái đợt: `assigned`, `labeling`, `review`, `approved`, `rejected`.
Chỉ dữ liệu `approved` được đưa vào dataset huấn luyện. Nếu một batch có nhiều
phiên nguồn, ghi nhiều dòng liên kết batch/phiên thay vì bỏ thông tin nguồn.
`group_id` gom các frame gần nhau hoặc cùng đoạn quay để chia tập nhất quán.
Không đưa tài khoản/mật khẩu camera vào CSV hoặc cấu hình Git.

Ví dụ một bản ghi nguồn (giá trị minh họa):

```csv
session_id,camera_id,recorded_at,timezone,period,weather,width,height,fps,video_path,frames_path,notes
cam01_20261113_am,cam01,2026-11-13T08:00:00+07:00,Asia/Bangkok,day,dry,1920,1080,25,data/raw/videos/cam01/cam01_20261113_am/original.mp4,data/raw/frames/cam01/2026-11-13_08h-09h,example only
```

## 5. Giao ảnh và nhận dữ liệu Label Studio

### 5.1. Giao ảnh

Giữ ảnh gốc trong `raw/`. Bản sao giao cho người gán nhãn đặt ở
`data/annotation_batches/<batch_id>/<member_id>/`. Một ảnh chỉ có một người
chịu trách nhiệm trong một vòng gán nhãn; reviewer kiểm tra trên bản nhận về.

Để chia một thư mục ảnh có sẵn cho 4 thành viên:

```powershell
python -m vehicle_detection.collection.extractor --split-from "data/raw/frames/cam01/2026-11-13_08h-09h" --split-machines 4 --batches-output "data/annotation_batches/cam01_20261113_am"
```

Công cụ tạo `may_con_01` ... `may_con_04`, sao chép ảnh và không gọi camera.
Không dùng chức năng này để chia train/val/test. Chọn thư mục đợt mới cho mỗi
lần bàn giao; tránh sao chép chồng lên một đợt đã được sửa nhãn.

### 5.2. Schema lớp bắt buộc

| ID chuẩn | Tên nhãn | Phương tiện |
| --- | --- | --- |
| 0 | `motorcycle` | Xe máy/mô tô |
| 1 | `car` | Ô tô con, SUV, bán tải |
| 2 | `electric_bicycle` | Xe đạp điện/xe máy điện mini theo quy ước nhóm |
| 3 | `bicycle` | Xe đạp cơ |
| 4 | `bus` | Xe buýt, xe khách |
| 5 | `truck` | Xe tải |
| 6 | `container_truck` | Xe đầu kéo/container |
| 7 | `special_vehicle` | Xe chuyên dụng |

Mã nguồn dùng `vehicle_detection/classes.py`; dataset có `classes.txt` và
`data.yaml`; giao diện Label Studio dùng `annotation/label_studio_template.xml`.
Các thành viên phải dùng cùng quy ước. Với trường hợp khó phân biệt, xem
[cẩm nang gán nhãn](LABELING_GUIDELINE_DETAIL.md) và chốt với reviewer.

**Không giả định ID xuất từ Label Studio trùng thứ tự XML.** Mỗi đợt phải đối
chiếu `classes.txt` hoặc thông tin lớp trong export. Nếu ID khác, lập bảng
`ID xuất → tên lớp → ID chuẩn`, chuyển ID trong từng dòng nhãn trên bản sao,
rồi kiểm tra trực quan. Không đổi mỗi tên trong `classes.txt`; cách đó làm
nhãn mang sai ý nghĩa. Dự án chưa có công cụ remap tự động.

### 5.3. Bàn giao bản xuất

1. Xuất YOLO cho huấn luyện và JSON để lưu nội dung nhãn gốc/phục vụ sửa sau này.
2. Lưu nguyên bản tại `data/label_studio/exports/`, ví dụ
   `2026-11-13_cam01_member01_batch01.zip` và file JSON cùng tên đợt.
3. Giải nén mỗi đợt vào `data/label_studio/extracted/<batch_id>/`; không giải nén
   nhiều bản xuất chung một thư mục. Kiểm tra cấu trúc thực tế của bản xuất.
4. Cần có ảnh, nhãn TXT và mapping lớp. Nếu bản xuất chỉ có nhãn, lấy ảnh đúng
   cặp từ kho gốc; không lấy ảnh khác chỉ vì tên gần giống.
5. Reviewer kiểm tra mapping, bbox, ảnh thiếu nhãn, ảnh âm tính, lớp dễ nhầm và
   dữ liệu trùng trước khi đánh dấu approved.

JSON nguyên bản là bản lưu nhãn, không phải nhãn YOLO để đưa thẳng vào train.
Lưu thêm snapshot Label Studio ở `data/label_studio/backups/<backup_id>/` nếu
cần khôi phục đầy đủ dự án, cấu hình và dữ liệu nội bộ. Việc tạo thư mục này
không tự thay đổi nơi Label Studio lưu database. Bản sao lưu phải nhất quán
với cơ sở dữ liệu và ảnh mà dự án đang dùng; kiểm tra phục hồi trên bản thử.

## 6. Dataset YOLO sau kiểm duyệt

### 6.1. Ghép cặp ảnh và nhãn

```text
data/vehicle_detection/images/train/cam01_session01_000001.jpg
data/vehicle_detection/labels/train/cam01_session01_000001.txt
```

Giữ thư mục split phẳng. Ảnh JPG/JPEG/PNG và nhãn TXT cùng tên gốc; mỗi ảnh
chỉ có một nhãn TXT. Không để cả `abc.jpg` và `abc.png` cùng một split.
Nếu trùng tên giữa các batch, thêm tiền tố camera/phiên cho cả ảnh và nhãn,
đồng thời ghi tên cũ/mới trong `splits.csv`.

Một dòng bbox:

```text
1 0.500000 0.600000 0.200000 0.300000
```

Nghĩa là class `car`, tâm ở (0.5, 0.6), rộng 0.2, cao 0.3 lần kích thước ảnh.
Mỗi dòng có đúng 5 cột, class ID nguyên 0–7; tọa độ hữu hạn, chuẩn hóa [0, 1],
chiều rộng/cao lớn hơn 0 và box nằm trong ảnh. Không dùng nhãn segmentation,
polygon hoặc tọa độ pixel cho bộ dữ liệu detection này.

Ảnh âm tính đã kiểm duyệt dùng file TXT rỗng. **Thiếu TXT không được xem là
ảnh âm tính** vì có thể là lỗi xuất hoặc ảnh chưa được gán nhãn.

### 6.2. Chia train/val/test

Gợi ý ban đầu 80% train / 10% val / 10% test, tính gần đúng theo ảnh nhưng
quyết định theo nhóm phiên/đoạn video. Không random từng frame của cùng đoạn
stream vào cả ba tập. Các frame gần nhau có thể làm kết quả đánh giá cao giả.

- `train`: học trọng số; có bbox hợp lệ, đủ đa dạng các lớp/điều kiện.
- `val`: chọn model và điều chỉnh tham số; giữ độc lập với train.
- `test`: đánh giá lần cuối; không dùng để chọn epoch hoặc tinh chỉnh ngưỡng.

Lưu quyết định vào `splits.csv` rồi mới sao chép. Kiểm tra ngày/đêm, lớp hiếm,
các hướng và điều kiện ánh sáng ở từng tập. Nếu lớp nào không có trong test,
ghi rõ chưa đủ dữ liệu để đánh giá lớp đó. Để đánh giá khả năng tổng quát hóa
sang camera mới, giữ camera đó hoàn toàn ngoài train/val.

### 6.3. Kiểm tra và tạo cấu hình trên máy huấn luyện

```powershell
python -m vehicle_detection.data.validate --report outputs/reports/dataset_check.json --config-output outputs/training/data.local.yaml
```

Lệnh kiểm tra đủ ba split, mapping `classes.txt`, ảnh/nhãn đi cặp, tên ảnh
trùng, nhãn mồ côi, số cột, ID, tọa độ, box vượt biên, ảnh rỗng và nội dung ảnh
trùng giữa các split bằng SHA-256. Nhãn rỗng hợp lệ được thống kê riêng.
Thiếu lớp ở từng tập và ảnh trùng nội bộ cùng split được báo cảnh báo để nhóm
xem xét. Train không có bbox hợp lệ sẽ báo lỗi.

Lệnh chỉ dùng thư viện chuẩn, không giải mã ảnh hoặc nhận biết nhãn vẽ sai.
Ảnh hỏng nhưng có dữ liệu vẫn cần kiểm tra mở ảnh trực quan; SHA-256 chỉ phát
hiện bản sao byte giống hệt, không phát hiện frame gần nhau hay ảnh đã nén lại.
Việc kiểm tra không đọc metadata hoặc xác nhận phiên quay độc lập.

Mã thoát 0 = đạt kiểm tra bắt buộc, 1 = có lỗi. Báo cáo JSON được ghi nếu yêu
cầu, kể cả khi FAIL. YAML chỉ được tạo khi PASS, không sửa bản mẫu
`data/vehicle_detection/data.yaml`. Bộ khung mới tạo sẽ FAIL do chưa có dữ liệu.

`outputs/training/data.local.yaml` có `path` tuyệt đối theo máy hiện tại.
Khi chuyển sang Colab hoặc máy khác, chạy lại lệnh với `--dataset` trỏ vào
dataset trên máy đó; không dùng lại đường dẫn Windows trong Colab.

Ví dụ cấu hình đầu vào train trong Python sau khi đã PASS:

```python
from ultralytics import YOLO

model = YOLO("yolo11n.yaml")  # Khởi tạo từ đầu; .pt nếu chọn transfer learning
model.train(
    data="outputs/training/data.local.yaml",
    project="outputs/training",
    name="vehicle_detection_v001",
    epochs=200,
    imgsz=640,
)
```

Số epoch/kích thước ở đây là ví dụ thử nghiệm, cần chọn theo phần cứng và
kết quả validation. Sao chép model tốt nhất sau train vào
`models/vehicle_detection/best.pt`, kèm `release.json` mô tả dataset/model.

## 7. Dữ liệu hiệu chuẩn camera để ước lượng tốc độ

### 7.1. Cần đo và lưu những gì?

1. Chụp một frame gốc ở đúng camera, vị trí, zoom và độ phân giải sẽ suy luận;
   lưu `data/calibration/<camera_id>/reference.jpg`.
2. Chọn bốn điểm trên cùng mặt phẳng đường, tạo tứ giác lồi, theo thứ tự quanh
   chu vi (ví dụ trái xa → phải xa → phải gần → trái gần). Lưu tọa độ pixel.
3. Đo vị trí/khoảng cách thực địa tương ứng bằng mét. Ghi ngày đo, người đo,
   phương pháp, đơn vị và các điểm mốc vào `survey.json` cạnh ảnh tham chiếu.
   Không lấy kích thước đường minh họa 8 × 25 m làm số đo thật.
4. Chọn hai đầu vạch đếm nằm trong khung hình, ghi quy ước IN/OUT trong hồ sơ
   camera và kiểm tra lại bằng video mẫu.
5. Xác nhận FPS/thời gian video; nếu camera di chuyển/đổi zoom/độ phân giải,
   tạo lại hiệu chuẩn và lưu phiên bản cũ để truy vết.

`survey.json` là hồ sơ đo do nhóm lưu, không có schema bắt buộc trong mã nguồn.
File được demo đọc là `configs/cameras/<camera_id>.json` theo schema dưới đây.

### 7.2. Cấu hình được demo hỗ trợ

Sao chép `configs/cameras/cam01.example.json` thành `cam01.json`, thay toàn bộ
tọa độ bằng số đo thật. Không coi file example là camera đã hiệu chuẩn.

| Trường | Nội dung |
| --- | --- |
| `camera_id` | ID camera để quản lý hồ sơ |
| `image_size` | `[width, height]` nguyên dương, đúng độ phân giải video đầu vào |
| `source_points_px` | 4 điểm `[x, y]` pixel theo thứ tự quanh tứ giác mặt đường |
| `target_points_m` | 4 điểm `[X, Y]` mét tương ứng từng điểm nguồn, cùng thứ tự |
| `count_line_px` | 2 điểm pixel nguyên, khác nhau, tạo vạch đếm |
| `measurement_note` | Ghi chú nguồn số đo, phiên bản hiệu chuẩn |

Các điểm nguồn/vạch đếm phải nằm trong ảnh. Bốn điểm nguồn và bốn điểm đích
phải tạo tứ giác lồi không suy biến. Demo kiểm tra các điều kiện này và từ chối
video có độ phân giải khác `image_size`; không tự scale hiệu chuẩn.

```powershell
python -m vehicle_detection.inference.demo --video data/evaluation/cam01/session01/traffic.mp4 --model models/vehicle_detection/best.pt --calibration configs/cameras/cam01.json --output outputs/inference/cam01_session01.mp4
```

Homography giả định đường gần phẳng trong vùng đo. Demo hiện tính thời gian
bằng chỉ số frame/FPS; stream rớt frame, video FPS biến thiên hoặc timestamp
không ổn định có thể làm sai tốc độ dù tọa độ hiệu chuẩn đúng. Chưa có cơ chế
đọc timestamp từng frame hoặc loại bỏ track ngoài vùng hiệu chuẩn, nên cần
kiểm tra vùng đánh giá và thời gian nguồn riêng trước khi báo sai số.

## 8. Dữ liệu đánh giá đếm xe và tốc độ

Dùng video liên tục chưa dùng trong train/val. Ảnh trích mỗi 3 giây không đủ
để kiểm tra toàn bộ hành trình track và việc cắt vạch. Đặt video và ground
truth chung trong `data/evaluation/<camera_id>/<session_id>/`.

### 8.1. Ground truth đếm xe

File `counts_ground_truth.csv` đề xuất một dòng cho mỗi phương tiện cắt vạch:

```csv
event_id,video_file,timestamp_s,frame_index,vehicle_id,class_name,direction,line_id,reviewer
```

`timestamp_s` là số giây từ đầu video, `frame_index` dùng quy ước bắt đầu từ 1
để khớp vòng lặp demo, `direction` là IN/OUT đã thống nhất với hướng vạch.
`vehicle_id` là ID thủ công trong video, không phải ID ngẫu nhiên do ByteTrack
cấp. Sau đó tổng hợp theo khoảng thời gian, lớp và hướng để so với kết quả
thuật toán. Nên có người thứ hai kiểm tra các tình huống đông xe/che khuất.

### 8.2. Ground truth tốc độ

File `speeds_ground_truth.csv` đề xuất:

```csv
measurement_id,video_file,vehicle_id,start_time_s,end_time_s,reference_speed_kmh,reference_method,sync_note,reviewer
```

Tốc độ tham chiếu cần đến từ thiết bị đo độc lập hoặc phép đo quãng đường/thời
gian có cơ sở, cùng phương tiện và đoạn thời gian của video. Ghi rõ phương
pháp, sai số tham chiếu và cách đồng bộ. Không dùng chính kết quả Homography
làm ground truth để đánh giá Homography.

Demo hiện xuất video có overlay, chưa xuất tự động hai bảng CSV hoặc tự tính
metric so với ground truth. Đây là dữ liệu cần chuẩn bị cho bước đánh giá tiếp
theo. Báo cáo và bảng so sánh thủ công/công cụ bổ sung đặt ở `outputs/reports/`.
Không khẳng định sai số ±3–5 km/h hoặc độ chính xác đếm cụ thể khi chưa đo trên
dữ liệu đánh giá này.

## 9. Chốt phiên bản và sao lưu

Trước khi bàn giao một dataset:

- Đủ ảnh/nhãn cho ba split, đúng 8 lớp; các cảnh báo lớp hiếm đã được xem xét.
- Đã kiểm tra trực quan nhãn và mở được ảnh; ảnh âm tính được xác nhận.
- Có nguồn ảnh, bản xuất gốc, quyết định mapping lớp và manifest chia tập.
- Kiểm tra tự động PASS; không có bản sao ảnh lọt giữa train/val/test.
- Có phiên bản dataset, thống kê ảnh/bbox theo lớp/ngày đêm và báo cáo kiểm tra.
- Có gói sao lưu trên kho dùng chung, SHA-256 và người chịu trách nhiệm.

Đóng gói `data/vehicle_detection/` với cấu trúc tương đối cùng metadata cần
thiết; giữ bản export/raw ở kho riêng để không phải sao chép mọi video trong
mỗi lần phát hành. Mỗi phiên bản đã dùng để train nên được giữ nguyên; sửa nhãn
thì tạo phiên bản tiếp theo và ghi thay đổi.

`.gitignore` bỏ qua dữ liệu thực trong `data/`, model, outputs và cấu hình
camera thật. Chỉ README, cấu hình mẫu, CSV mẫu, class list và bộ khung được
theo dõi bằng Git. **Commit mã nguồn không sao lưu dữ liệu dự án.** Sao lưu
riêng cả camera JSON, hồ sơ đo và model release cùng với dữ liệu.
