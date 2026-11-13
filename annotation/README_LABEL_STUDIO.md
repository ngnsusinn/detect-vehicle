# HƯỚNG DẪN GÁN NHÃN BẰNG LABEL STUDIO COMMUNITY CHO BÀI TOÁN PHÂN LOẠI & ĐẾM XE

Tài liệu này hướng dẫn chi tiết cách thiết lập và sử dụng **Label Studio Community Edition** để gán nhãn dữ liệu phương tiện giao thông (Bounding Box Object Detection) phục vụ huấn luyện mô hình **YOLOv8 / YOLOv11** trong hệ thống **Đếm và Đo tốc độ phương tiện giao thông**.

---

## 1. CÀI ĐẶT & KHỞI CHẠY LABEL STUDIO COMMUNITY

### Cách 1: Cài đặt qua môi trường Python (Khuyến nghị)
```bash
# 1. Kích hoạt môi trường ảo Python 3.10 hoặc 3.11
python -m venv ls_env

# Trên Windows:
ls_env\Scripts\activate
# Trên Linux/macOS:
source ls_env/bin/activate

# 2. Cài đặt Label Studio phiên bản mới nhất
pip install label-studio

# 3. Cho phép truy cập tệp cục bộ (Local File Serving) nếu nạp ảnh từ ổ cứng
# Trên Windows CMD:
set LABEL_STUDIO_LOCAL_FILES_SERVING_ENABLED=true
set LABEL_STUDIO_LOCAL_FILES_DOCUMENT_ROOT=C:\Users\ngnsusinn\Documents\detect-vehicle

# Trên Windows PowerShell:
$env:LABEL_STUDIO_LOCAL_FILES_SERVING_ENABLED="true"
$env:LABEL_STUDIO_LOCAL_FILES_DOCUMENT_ROOT="C:\Users\ngnsusinn\Documents\detect-vehicle"

# 4. Khởi chạy Label Studio (Mặc định chạy tại http://localhost:8080)
label-studio start
```

### Cách 2: Khởi chạy bằng Docker
```bash
docker run -it -p 8080:8080 \
  -v $(pwd)/mydata:/label-studio/data \
  -e LABEL_STUDIO_LOCAL_FILES_SERVING_ENABLED=true \
  heartexlabs/label-studio:latest
```

---

## 2. THIẾT LẬP TEMPLATE GÁN NHÃN TRÊN LABEL STUDIO

1. Đăng nhập vào giao diện Label Studio (`http://localhost:8080`).
2. Bấm **Create Project**, đặt tên dự án (ví dụ: `Vehicle_Detection_Speed_Counting`).
3. Chuyển sang thẻ **Labeling Setup** $\rightarrow$ Chọn **Custom template** (hoặc bấm vào nút **Code** ở góc trên bên phải khung thiết lập).
4. Xóa toàn bộ nội dung mặc định và dán nội dung từ tệp `annotation/label_studio_template.xml`:

Dùng toàn bộ file XML hiện hành: [label_studio_template.xml](label_studio_template.xml).
Xem [hướng dẫn interface và đối chiếu yêu cầu](LABELING_INTERFACE.md) để nhập thuộc tính từng xe,
xử lý ảnh âm, kiểm duyệt và xuất cả JSON + YOLO. File XML là cấu hình chuẩn duy nhất;
không dùng lại đoạn template 8 nhãn cũ vì thiếu trạng thái xe và các trường QA.
5. Bấm **Save** để hoàn tất cấu hình giao diện.

---

## 3. DANH MỤC LỚP PHƯƠNG TIỆN & PHÍM TẮT (HOTKEYS)

| Index | Label (Tên lớp) | Ý nghĩa thực tế | Phím tắt | Màu sắc gợi ý |
| :---: | :--- | :--- | :---: | :---: |
| **0** | `motorcycle` | Xe máy, xe mô tô 2 bánh, 3 bánh | `1` | Hồng nhạt (`#FFA39E`) |
| **1** | `car` | Ô tô con (Sedan, SUV, CUV, Hatchback, bán tải) | `2` | Xanh dương (`#91CAFF`) |
| **2** | `electric_bicycle` | Xe đạp điện, xe máy điện mini | `3` | Vàng cam (`#FFD591`) |
| **3** | `bicycle` | Xe đạp cơ thông thường, xe địa hình | `4` | Xanh lam (`#ADC6FF`) |
| **4** | `bus` | Xe buýt nội đô, xe khách 16 - 45 chỗ, xe giường nằm | `5` | Tím nhạt (`#D3ADF7`) |
| **5** | `truck` | Xe tải nhẹ, xe tải ben, xe tải thùng | `6` | Xanh ngọc (`#87E8DE`) |
| **6** | `container_truck` | Xe container, xe đầu kéo rơ-moóc | `7` | Hồng cánh sen (`#FFADD2`) |
| **7** | `special_vehicle` | Xe ba gác, xe cứu thương, xe chuyên dụng | `8` | Xám (`#D9D9D9`) |

---

## 4. QUY TẮC GÁN NHÃN ĐẠT CHUẨN ĐẾM & ĐO TỐC ĐỘ

> 📘 **CẨM NANG HƯỚNG DẪN CHI TIẾT DÀNH CHO THÀNH VIÊN NHÓM:**  
> Đọc tài liệu hướng dẫn đầy đủ từng bước tại: [Tài liệu Hướng dẫn Gán nhãn Chi tiết (docs/LABELING_GUIDELINE_DETAIL.md)](../docs/LABELING_GUIDELINE_DETAIL.md).  
> Tài liệu trên hướng dẫn chi tiết cách zoom, pan, phím tắt nhanh, bảng phân biệt các cặp xe dễ nhầm (bán tải vs tải, xe 16 chỗ vs bus, xe đạp điện vs xe máy), xử lý đèn pha ban đêm và bảng checklist tự kiểm tra.

Để mô hình YOLOv11 phát hiện chính xác điểm tiếp xúc bánh xe với mặt đường (vị trí tính tọa độ đo vận tốc):
1. **Bao trọn toàn bộ xe:** Khung hình chữ nhật phải ôm sát từ mép trên nóc xe (hoặc đầu người lái xe 2 bánh) xuống đến mép đáy của bánh xe tiếp xúc mặt đất.
2. **Không gán bóng đổ (Shadow):** Tuyệt đối không kéo khung chữ nhật bao trùm bóng đổ của phương tiện trên mặt đường.
3. **Xe bị che khuất (Occlusion):** Nếu xe bị che khuất dưới $70\%$, vẫn gán nhãn bao trùm phần thân xe nhìn thấy được. Nếu bị che khuất quá $70\%$, bỏ qua không gán.
4. **Phân biệt xe máy và xe đạp điện:** 
   - Xe máy: Có bô xả, phuộc nhún lớn, kích thước lốp dày, thường có biển số sau.
   - Xe đạp điện: Có hộp ắc quy vuông dưới yên, bàn đạp phụ hoặc khung xe thanh mảnh.

---

## 5. XUẤT DỮ LIỆU ĐỂ HUẤN LUYỆN YOLOV11 (EXPORT DATASET)

Dự án đã có cấu trúc lưu dữ liệu tại [`data/`](../data/README.md): lưu bản xuất
gốc vào `data/label_studio/exports/`, giải nén theo từng đợt vào
`data/label_studio/extracted/`, sau đó đưa các cặp ảnh/nhãn đã kiểm duyệt vào
`data/vehicle_detection/`. Xem hướng dẫn tại liên kết trên trước khi gộp các
đợt dữ liệu, đặc biệt là thứ tự class ID và cách chia train/val/test.

1. Trong dự án Label Studio, bấm nút **Export** ở góc trên bên phải.
2. Chọn định dạng **YOLO** và lấy kèm ảnh nếu tùy chọn xuất hỗ trợ. Kiểm tra file nén `.zip` sau khi xuất:
   - Thư mục `images/`: Chứa các ảnh gốc nếu bản xuất có kèm ảnh; nếu không, bổ sung ảnh đúng cặp từ kho ảnh nguồn.
   - Thư mục `labels/`: Chứa các tệp nhãn `.txt` tương ứng với mỗi ảnh theo chuẩn YOLO:
     ```text
     <class_id> <x_center> <y_center> <width> <height>
     ```
     (Mọi tọa độ đều được chuẩn hóa trong khoảng $[0.0, 1.0]$).
   - Tệp `classes.txt`: Mapping class ID của bản xuất. Đối chiếu với `data/vehicle_detection/classes.txt`; nếu thứ tự khác phải chuyển ID trong nhãn trước khi gộp.

### File cấu hình `data.yaml` chuẩn cho YOLOv11:
```yaml
path: /path/to/dataset
train: images/train
val: images/val
test: images/test

names:
  0: motorcycle
  1: car
  2: electric_bicycle
  3: bicycle
  4: bus
  5: truck
  6: container_truck
  7: special_vehicle
```
