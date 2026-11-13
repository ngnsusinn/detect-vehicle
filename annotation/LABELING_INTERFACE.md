# Labeling Interface cho Label Studio

File sử dụng: [label_studio_template.xml](label_studio_template.xml).
Trong Label Studio, mở **Settings → Labeling Interface → Code**, dán toàn bộ
nội dung file XML rồi Save. Khi tạo project, mục này có thể mang tên Labeling Setup.
Đầu vào duy nhất bắt buộc là `data.image`; có thể import ảnh trực tiếp hoặc task JSON:

```json
[
  {
    "data": {
      "image": "/data/local-files/?d=raw/frames/cam01_20261113_081530_125_000142.jpg"
    }
  }
]
```

Ví dụ URL trên giả định Local File Serving đã bật và document root là thư mục
`data` của dự án. Thay bằng đường dẫn ảnh thực tế hoặc URL ảnh có thể truy cập.
Không cần thêm các trường metadata để giao diện hoạt động.

## Đối chiếu yêu cầu với source

| Yêu cầu / nguồn | Giao diện đáp ứng |
| --- | --- |
| `vehicle_detection/classes.py`, `data/vehicle_detection/data.yaml` | Giữ đúng 8 tên lớp; `category` 0–7 và hotkey 1–8; không thêm lớp chạy/dừng vào detector |
| `vehicle_detection/inference/demo.py`, SRS FR-03 | Box chữ nhật không xoay, hướng dẫn căn đáy tiếp đất để lấy bottom-center |
| `docs/DATA_ANNOTATION_SPECIFICATION.md`, mục 2.5 | Không bao bóng; xe hai bánh gồm cả người; bỏ qua xe che hơn 70% hoặc box cao dưới 20 px ảnh gốc |
| `docs/LABELING_GUIDELINE_DETAIL.md`, mục 4–5 | Bao cả hàng gắn liền; box phần nhìn thấy, không suy đoán phần bị che; phân biệt các lớp dễ nhầm |
| Đặc tả dữ liệu, mục 1.2 | `motion_state` cho từng xe: `moving`, `stopped`, `unknown` |
| Yêu cầu thu thập ngày/đêm | `lighting`: day/night/twilight để thống kê và chọn dữ liệu |
| Kiểm duyệt QA/QC | Chất lượng ảnh, trạng thái toàn ảnh, ghi chú, xác nhận rà soát; thuộc tính che khuất, cắt biên, tiếp đất và độ chắc chắn từng box |
| Kiểm tra ảnh âm trong `vehicle_detection/data/validate.py` | Có trạng thái `negative`; không bắt buộc vẽ box cho mọi ảnh |
| Xử lý ảnh ban đêm | Có zoom, thanh độ sáng, tương phản và tâm ngắm |

Tên `image`, `label` và các giá trị lớp được giữ nguyên để tương thích với
annotation/prediction cũ. Annotation cũ cần được bổ sung các thuộc tính bắt buộc
trước khi nộp lại. Không dùng alias cho nhãn để tránh thay đổi giá trị xuất.

## Thao tác

1. Xem ảnh, chọn ánh sáng và chất lượng. Gán cả xe dừng lẫn xe đang chạy.
2. Bấm 1–8 chọn lớp, kéo box ôm sát. Bán tải là `car`, khách 16 chỗ là `bus`.
   Xe máy điện cỡ lớn là `motorcycle`; xe đạp điện/xe điện mini là `electric_bicycle`.
   Ba gác chở hàng, xích lô và xe chuyên dụng thuộc `special_vehicle`.
3. Chọn từng box và điền các thuộc tính bắt buộc. Nếu thiếu video/chuỗi ảnh đối
   chiếu, chọn `motion_state=unknown`; một ảnh tĩnh không chứng minh xe chạy/dừng.
4. Nếu bánh bị che hoặc bị cắt, vẽ phần xe nhìn thấy và đánh dấu
   `ground_contact=not_visible`; không kéo đáy xuống vị trí bánh giả định.
   Những box này có thể dùng cho detector sau kiểm duyệt nhưng không làm mẫu
   chuẩn điểm tiếp đất để đánh giá tốc độ.
5. Chọn trạng thái toàn ảnh, ghi chú trường hợp khó, xác nhận rà soát và Submit.
   `labeled` phải có box; `negative` chỉ dùng khi ảnh thật sự không có xe thuộc
   8 lớp. Nếu có xe nhưng tất cả bị bỏ qua vì ngưỡng kích thước/che khuất, dùng
   `needs_review` để người kiểm duyệt quyết định cách xử lý, tránh tạo ảnh âm sai.
6. Ảnh không sử dụng được chọn `unusable` và `reject`. Xe/lớp chưa chắc chắn
   hoặc `ground_contact=uncertain` cần chọn `needs_review` ở cấp ảnh.

Quy ước biên: che khuất đúng 70% vẫn có thể gán nếu nhận diện được; box cao
đúng 20 px vẫn được gán. Chiều cao tính trên ảnh gốc, không theo độ phóng to:
`height_px = result.value.height / 100 * result.original_height` trong JSON.

Tài liệu chi tiết có ví dụ tên mẫu xe điện chưa thống nhất giữa bảng và phần
khử nhầm lẫn. Interface dùng quy ước phân biệt theo kích thước/kiểu xe ở phần
khử nhầm lẫn; trường hợp thiếu căn cứ phải chuyển kiểm duyệt, không đoán theo hãng.

## Xuất dữ liệu và giới hạn

- Luôn lưu cả **JSON gốc của Label Studio** vào `data/label_studio/exports/`
  để giữ trạng thái chuyển động, thuộc tính từng box, ghi chú và thông tin QA.
- Trước khi xuất YOLO, lọc task đã kiểm duyệt: chỉ nhận `labeled` và ảnh âm
  `negative` hợp lệ. Không gộp task `needs_review`, `reject` hoặc ảnh `unusable`
  vào dataset. Chọn JSON/YOLO theo cùng tập task đã duyệt.
- YOLO detection TXT chỉ có `class_id x_center y_center width height`.
  Thuộc tính chạy/dừng, che khuất và các trường QA không được dùng làm đầu ra
  huấn luyện bởi pipeline detector hiện tại; JSON giữ chúng cho bước mở rộng sau.
- Đối chiếu `classes.txt` bản xuất với `data/vehicle_detection/classes.txt`.
  XML khai báo `category` để cố định ID theo tài liệu Label Studio; vẫn phải
  kiểm tra mapping ở bản xuất thực tế và remap nếu exporter có thứ tự khác.
- Với ảnh âm đã duyệt, bảo đảm có file `.txt` rỗng cùng tên ảnh, kể cả khi
  exporter không tạo file nhãn rỗng. Thiếu file không được coi là ảnh âm.
- Giao diện bắt buộc nhập các trường đánh dấu `required`; XML không tự kiểm tra
  số box so với trạng thái ảnh, kích thước 20 px, tỷ lệ che khuất, vị trí bánh xe
  hay tính đúng của lớp. Xác nhận rà soát là kiểm tra của người gán nhãn;
  cần kiểm duyệt chéo tối thiểu 10% theo guideline và kiểm tra dữ liệu sau xuất.
- Tỷ lệ 60% ngày / 40% đêm, cân bằng lớp, độ nét, độ phân giải và chia tập theo
  camera/thời gian là yêu cầu ở cấp dataset. Các trường trên hỗ trợ thống kê,
  không tự bảo đảm các tỷ lệ hoặc KPI độ chính xác của mô hình.
- ByteTrack, track ID, vạch đếm/làn, ROI và Homography được xử lý trong pipeline
  video và cấu hình camera (`configs/cameras/`); không gán tốc độ, hướng hay
  track ID từ các ảnh độc lập. Đánh giá đếm/tốc độ cần video có thời gian và
  dữ liệu chuẩn thực địa riêng, xem `docs/DATA_GUIDE.md`.

Sau khi đưa ảnh/nhãn đã duyệt vào dataset, chạy:

```powershell
python -m vehicle_detection.data.validate
```

## Tham chiếu cú pháp Label Studio

- [Image: zoom, brightness, contrast](https://labelstud.io/tags/image)
- [Label: category, hotkey, hint](https://labelstud.io/tags/label)
- [Choices: required, perRegion](https://labelstud.io/tags/choices.html)
- [Xuất annotation](https://labelstud.io/guide/export)
