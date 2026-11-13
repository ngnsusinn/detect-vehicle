# Kho dữ liệu của dự án

Hướng dẫn đầy đủ: **[docs/DATA_GUIDE.md](../docs/DATA_GUIDE.md)**.

| Thư mục | Lưu gì |
| --- | --- |
| `raw/videos/` | Video gốc nếu có, chia theo camera/phiên quay |
| `raw/frames/` | Ảnh chưa gán nhãn, đầu ra mặc định của công cụ thu thập |
| `annotation_batches/` | Bản sao ảnh giao cho các thành viên gán nhãn |
| `label_studio/exports/` | Bản xuất ZIP YOLO, JSON nguyên bản |
| `label_studio/extracted/` | Bản giải nén riêng của từng đợt |
| `label_studio/backups/` | Bản sao lưu dự án Label Studio |
| `vehicle_detection/` | Dataset đã duyệt: `images/` và `labels/`, mỗi bên có `train/val/test` |
| `metadata/` | Nguồn ảnh, tiến độ gán nhãn, danh sách chia tập và phiên bản dataset |
| `calibration/` | Ảnh tham chiếu camera, bản đo khoảng cách thực địa |
| `evaluation/` | Video độc lập và ground truth đếm xe/tốc độ |

Bắt đầu bằng cách sao chép `metadata/*.example.csv` thành các file `.csv` tương
ứng rồi điền dữ liệu thực tế. File mẫu chỉ có tiêu đề, không phải dữ liệu thật.

`vehicle_detection/classes.txt` quy định 8 class ID chuẩn; phải kiểm tra mapping
của mỗi bản xuất trước khi gộp. Không chỉ sửa tên lớp nếu ID bị lệch.
`vehicle_detection/data.yaml` là bản mẫu; dùng lệnh kiểm tra dưới đây để tạo cấu
hình có đường dẫn tuyệt đối trên máy đang huấn luyện:

```powershell
python -m vehicle_detection.data.validate --report outputs/reports/dataset_check.json --config-output outputs/training/data.local.yaml
```

Chạy từ thư mục gốc dự án. Lệnh không sửa dữ liệu; chỉ tạo báo cáo nếu yêu cầu,
và chỉ tạo YAML khi tất cả kiểm tra bắt buộc đạt. Dataset hiện chỉ là bộ khung.

Ảnh/nhãn, metadata thật và backup được bỏ qua bởi Git. Git chỉ giữ README,
cấu hình dataset, các CSV mẫu và `.gitkeep`. Cần sao lưu dữ liệu ở kho dùng
chung riêng; Git không lưu giúp dữ liệu này.
