# HƯỚNG DẪN THU THẬP DỮ LIỆU ẢNH THỰC TẾ TỪ LUỒNG STREAMING

> Đường dẫn lưu dữ liệu và quy trình bàn giao hiện tại được quy định tại
> [DATA_GUIDE.md](DATA_GUIDE.md). Xem [PROJECT_STRUCTURE.md](PROJECT_STRUCTURE.md)
> để biết vị trí mã nguồn sau refactor. Các đường dẫn Colab trong tài liệu này
> là ví dụ triển khai; cần tạo lại `data.yaml` với đường dẫn thực tế trên máy train.

## BỘ CÔNG CỤ THU THẬP TỰ ĐỘNG THEO CHU KỲ & KHUNG GIỜ (STREAM DATA COLLECTOR)
**Phiên bản:** 1.0.0  
**Tác giả:** Đội ngũ Kỹ thuật & MLOps Dự án Đếm & Đo Tốc Độ Phương Tiện ITS 2026  

---

## 1. TỔNG QUAN & CAM KẾT CHẤT LƯỢNG DỮ LIỆU

Nhằm đáp ứng yêu cầu kỹ thuật nghiêm ngặt: **$100\%$ dữ liệu huấn luyện phải được trích xuất trực tiếp từ các luồng streaming thực tế** (camera giao thông RTSP, HLS, WebRTC, video camera thực địa hoặc webcam), hệ thống cung cấp công cụ thu thập tự động chuyên dụng tích hợp giao diện đồ họa trực quan (GUI):

- **Tần suất chụp ảnh cố định:** Đúng **mỗi 3 giây chụp 1 ảnh** ($3.0\text{s/frame}$), đảm bảo ghi nhận các phương tiện mới lưu thông qua góc máy mà không bị quá tải lưu trữ.
- **Phân bổ thư mục tự động theo từng khung giờ (1h / folder):** Toàn bộ $24\text{ giờ}$ trong ngày được chia thành 24 khung giờ cố định (`00h-01h`, `01h-02h`, ..., `23h-24h`). Mỗi khi đồng hồ bước qua khung giờ mới, hệ thống tự động tạo thư mục tương ứng và lưu ảnh vào đó mà không cần dừng luồng:
  - Ví dụ: `2026-10-06_09h-10h`, `2026-10-06_10h-11h`, `2026-10-06_11h-12h`...
- **Đa dạng nguồn tiếp nhận:** Hỗ trợ URL RTSP (`rtsp://...`), HLS HTTP (`http://.../playlist.m3u8`), **YouTube Livestream** (`https://www.youtube.com/watch?v=...` hoặc `https://www.youtube.com/live/...`), WebRTC/HTTP stream, file video ghi sẵn (`.mp4`, `.avi`, `.mkv`), hoặc Webcam cắm trực tiếp qua cổng USB (`0`, `1`). Tự động bóc tách luồng HLS trực tiếp từ YouTube thông qua `yt-dlp`.

---

## 2. CẤU TRÚC THƯ MỤC LƯU TRỮ ĐẦU RA

Dữ liệu được tổ chức theo cấu trúc phân cấp khoa học, trực quan, hỗ trợ theo dõi theo ngày, theo camera và theo khung thời gian chiếu sáng trong ngày:

```text
data/raw/frames/
├── cam_lane01/
│   ├── 2026-10-05_08h-09h/
│   │   ├── cam_lane01_20261005_080003_120_000001.jpg
│   │   ├── cam_lane01_20261005_080006_145_000002.jpg
│   │   └── ...
│   ├── 2026-10-05_09h-10h/
│   │   ├── cam_lane01_20261005_090003_050_001201.jpg
│   │   └── ...
│   └── 2026-10-05_10h-11h/
│       └── ...
└── cam_lane02/
    └── 2026-10-05_09h-10h/
        └── ...
```

### Quy ước đặt tên tệp ảnh:
`<Tên_Camera>_<NămThángNgày>_<GiờPhútGiây>_<MiliGiây>_<SốThứTựẢnh>.jpg` (hoặc `.png`)
- **Ví dụ:** `cam_lane01_20261005_091530_125_000142.jpg`
- **Định dạng & Chất lượng:** Định dạng JPEG chất lượng tối đa ($100\%$) hoặc PNG Lossless, giữ nguyên độ phân giải gốc của camera (1080p hoặc 2K) phục vụ gán nhãn phát hiện phương tiện và đo tốc độ chính xác nhất.

---

## 3. HƯỚNG DẪN KHỞI CHẠY GIAO DIỆN ĐỒ HỌA (GUI)

### Cách 1: Khởi động nhanh bằng 1 click chuột (Khuyên dùng trên Windows)
Nhấp đúp chuột trực tiếp vào tệp:
```text
run_collector.bat
```
*(File batch sẽ tự động kiểm tra thư viện Python, cài đặt bổ sung `opencv-python` và `Pillow` nếu thiếu, sau đó mở giao diện đồ họa ngay lập tức).*

### Cách 2: Khởi động bằng dòng lệnh Terminal / PowerShell
Mở terminal trong thư mục dự án và chạy:
```bash
python collector_gui.py
```

---

## 4. CÁC TÍNH NĂNG CHÍNH TRÊN GIAO DIỆN NGƯỜI DÙNG

```
+-----------------------------------------------------------------------------------------+
| 📹 BỘ THU THẬP DỮ LIỆU ẢNH STREAMING ĐA GIAO THỨC          ● ĐANG CHỤP  10:15:30 [09h-12h]|
+------------------------------------+----------------------------------------------------+
| ⚙️ CẤU HÌNH THU THẬP               | 📺 XEM TRỰC TIẾP LUỒNG STREAM (LIVE PREVIEW)       |
|                                    |                                                    |
| Nguồn Stream:                      |       +------------------------------------+       |
| [rtsp://admin:pass@192.168.1.100 ] |       |                                    |       |
| [Webcam 0] [HLS Mẫu] [Chọn MP4...] |       |          (Hình ảnh Camera          |       |
|                                    |       |             thời gian thực)        |       |
| Tên Camera (Tag):                  |       |                                    |       |
| [cam_lane01                      ] |       +------------------------------------+       |
|                                    |                                                    |
| Thư mục lưu Dataset:               |                                                    |
| [C:\...\data\raw\frames  ][Duyệt]|                                                    |
|                                    +----------------------------------------------------+
| Chu kỳ: [ 3.0 ] s/ảnh (3h/1 folder)| 📝 NHẬT KÝ THU THẬP DỮ LIỆU                        |
|                                    | [10:15:27] 📸 [#000140] Đã lưu cam_lane01_...     |
| 📊 THỐNG KÊ                        | [10:15:30] 📸 [#000141] Đã lưu cam_lane01_...     |
| 📸 Đã chụp: 141 ảnh                | [10:15:33] 📸 [#000142] Đã lưu cam_lane01_...     |
| 📁 Khung: 2026-10-05_09h-12h       +----------------------------------------------------+
| ⏳ Chụp tiếp sau: 2.1 s            |
| ⚡ FPS: 29.8 | 1920x1080           |
|                                    |
| [ ▶ BẮT ĐẦU CHỤP ]                 |
| [ ⏸ TẠM DỪNG ] [ ⏹ DỪNG LẠI ]    |
| [ 📂 Mở Thư Mục Ảnh Hiện Tại ]    |
+------------------------------------+
```

1. **Khung Cấu hình Nguồn phát:**
   - **Nguồn Stream:** Nhập link RTSP, link HLS `.m3u8`, hoặc bấm nút **"Chọn Tệp MP4..."** để trích xuất ảnh từ video quay thực tế bằng điện thoại/camera hành trình. Bấm **"Webcam 0"** để test trực tiếp bằng webcam máy tính.
   - **Tên Camera / Làn xe:** Đặt tên để hệ thống tự động tạo thư mục con (ví dụ: `lan_o_to_01`, `lan_xe_may_02`, `cong_so_1`).
   - **Thư mục lưu trữ:** Cho phép chọn bất kỳ ổ đĩa nào còn nhiều dung lượng.
   - **Chu kỳ chụp:** Mặc định `3.0` giây / 1 ảnh.
2. **Khung Xem Trực tiếp (Live Preview):**
   - Hiển thị trực tiếp hình ảnh camera đang phát với tỷ lệ co giãn thông minh, mượt mà không bị giật khung hình nhờ công nghệ đa luồng độc lập (Background Worker Thread).
3. **Bảng Thống kê & Giám sát:**
   - Đếm số lượng ảnh đã lưu trong phiên làm việc.
   - Hiển thị tên thư mục khung giờ 3h đang kích hoạt.
   - Bộ đếm ngược thời gian thực ($3.0\text{s} \rightarrow 2.0\text{s} \rightarrow 1.0\text{s} \rightarrow \text{Chụp}$).
   - Đo tốc độ FPS và độ phân giải thực tế của camera.
4. **Bảng Điều khiển:**
   - **Bắt đầu chụp:** Kích hoạt kết nối và bắt đầu chu kỳ lưu ảnh.
   - **Tạm dừng / Tiếp tục:** Dừng lưu ảnh tạm thời (ví dụ khi đoạn đường đang trống xe) mà không ngắt kết nối stream.
   - **Dừng lại:** Đóng luồng an toàn.
   - **Mở Thư Mục Ảnh Hiện Tại:** Mở trực tiếp thư mục khung giờ 3h trên Windows Explorer để người dùng kiểm tra ảnh vừa chụp.

---

---

## 5. CHẾ ĐỘ CHẠY DÒNG LỆNH CHẤT LƯỢNG CAO BẰNG FFMPEG (KHUYÊN DÙNG ĐỂ CHỐNG MỜ NHÒE)

Để đạt chất lượng ảnh chụp cao nhất, loại bỏ hoàn toàn hiện tượng mờ nhòe (motion blur) và các khối nén macroblock của video stream, hệ thống cung cấp công cụ chuyên dụng chạy bằng FFmpeg engine: `stream_capture_ffmpeg.py`.

### Khởi động nhanh bằng file batch:
```text
capture_ffmpeg.bat
```
*(File batch sẽ yêu cầu nhập link stream/YouTube và tự động chạy chế độ lọc ảnh nét nhất).*

### Chạy trực tiếp bằng dòng lệnh:
```bash
# 1. Chế độ 'sharpest' (Khuyên dùng): Tự động tìm khung hình sắc nét nhất quanh mỗi chu kỳ 3s
python stream_capture_ffmpeg.py --stream "rtsp://admin:pass@192.168.1.100:554/stream1" --tag "cam_lane01" --interval 3.0 --mode sharpest --format jpg --quality 100

# 2. Chế độ chỉ chụp I-Frame (Keyframe gốc, không dính P/B frame vỡ nét):
python stream_capture_ffmpeg.py --stream "https://www.youtube.com/watch?v=..." --tag "cam_yt_live" --interval 3.0 --mode keyframe

# 3. Xuất định dạng PNG không nén (Lossless 100%):
python stream_capture_ffmpeg.py --stream "http://example.com/live.m3u8" --tag "cam_hls" --interval 3.0 --mode sharpest --format png
```

### Chạy chế độ Headless CLI cơ bản qua collector_gui:
```bash
python collector_gui.py --stream "https://www.youtube.com/watch?v=..." --tag "cam_youtube_live" --interval 3.0
```

---

## 6. PHÂN CHIA DỮ LIỆU ĐỂ BẮT ĐẦU GÁN NHÃN

Sau khi thu thập được khối lượng ảnh lớn từ các khung giờ khác nhau, bạn có thể sử dụng công cụ có sẵn `training/stream_frame_extractor.py` để chia đều gói ảnh cho các máy con tiến hành gán nhãn:

```bash
# Chia dữ liệu trong khung giờ 09h-12h cho 4 máy con gán nhãn
python training/stream_frame_extractor.py --split-from "data/raw/frames/cam01/2026-11-13_08h-09h" --split-machines 4
```

Các thư mục máy con (`may_con_01`, `may_con_02`, `may_con_03`, `may_con_04`) sẽ được tạo tự động để chuyển sang các trạm làm việc theo tài liệu [docs/DISTRIBUTED_ANNOTATION_COLAB_GUIDE.md](DISTRIBUTED_ANNOTATION_COLAB_GUIDE.md).
