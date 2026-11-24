# Model

- `pretrained/`: weights khởi tạo có sẵn, nếu dùng transfer learning.
- `vehicle_detection/`: model 8 lớp đã huấn luyện, ví dụ `best.pt`, `best.onnx`.

Kèm mỗi bản model bằng `release.json` ghi phiên bản dataset, thứ tự lớp,
kiến trúc, tham số/lệnh train, metric trên test, phiên bản thư viện và SHA-256
của weights. Đây là hồ sơ bàn giao thủ công, không được demo tự tạo/đọc.

Model COCO có sẵn không có cùng mapping 8 lớp với dataset của dự án.
Truyền đường dẫn weights rõ ràng bằng `--model` khi chạy demo.

Bản triển khai `vehicle_detection/colab-retrain-20261124/` có sẵn trong Git.
Thư mục gồm checkpoint PyTorch mặc định, bản ONNX, bộ OpenVINO INT8 và
`backend-validation.json` chứa kết quả kiểm thử cùng SHA-256 của các tệp mô hình.
Lưu các checkpoint khác và kết quả thí nghiệm tại kho chung.
