#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
HỆ THỐNG THU THẬP DỮ LIỆU ẢNH TỪ LUỒNG STREAMING (STREAM DATA COLLECTOR GUI)
-----------------------------------------------------------------------------
- Chu kỳ chụp: Mỗi 3 giây chụp 1 ảnh (có thể tùy chỉnh).
- Phân chia thư mục tự động theo từng khung giờ (1h / folder):
    00h-01h | 01h-02h | ... | 22h-23h | 23h-24h
- Hỗ trợ đa nguồn: RTSP, HLS (.m3u8), HTTP, MP4/AVI, Webcam (0, 1...)
- KIẾN TRÚC TRIỆT TIÊU 100% HIỆN TƯỢNG KHỰNG / GIẬT HÌNH:
    1. FreshFrameReader (Thread 1): Đọc stream liên tục, giải phóng toàn bộ buffer FFMPEG;
       hỗ trợ CAP_DSHOW cho Webcam trên Windows và Pacing chuẩn nhịp FPS cho tệp MP4.
    2. VideoCaptureWorker (Thread 2): Tự động Resize & Convert RGB ở C++ (giải phóng GIL),
       bơm thumbnail vào preview_queue và kích hoạt snapshot mỗi 3 giây.
    3. AsyncDiskWriter (Thread 3): Nén & ghi ảnh JPEG 95% xuống ổ cứng hoàn toàn ngầm.
    4. Tkinter UI (Main Thread): Hiển thị trực tiếp qua tk.Label BitBlt siêu nhẹ (< 1ms),
       quét hàng đợi mỗi 10ms và chỉ cập nhật text label mỗi 250ms (chống layout thrashing).
"""

import os
import sys
import time
import math
import json
import queue
import threading
import subprocess
from datetime import datetime

from vehicle_detection.paths import RAW_FRAMES_DIR
from vehicle_detection.collection.storage import get_slot_info, get_current_storage_directory

# Đảm bảo terminal và print hỗ trợ UTF-8
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

# Cấu hình tối ưu độ trễ cho FFMPEG / OpenCV (Bỏ flags;low_delay để giữ nguyên bộ lọc deblocking khử vỡ hạt)
os.environ["OPENCV_FFMPEG_CAPTURE_OPTIONS"] = "rtsp_transport;tcp|fflags;nobuffer|max_delay;500000"

# Kiểm tra các thư viện bắt buộc
try:
    import cv2
    import numpy as np
except ImportError:
    print("❌ LỖI THIẾU THƯ VIỆN: opencv-python hoặc numpy chưa được cài đặt.")
    print("👉 Hãy chạy lệnh: pip install opencv-python Pillow numpy")
    sys.exit(1)

try:
    from PIL import Image, ImageTk
    HAS_PIL = True
except ImportError:
    HAS_PIL = False

try:
    import tkinter as tk
    from tkinter import ttk, messagebox, filedialog
except ImportError:
    print("❌ LỖI: Tkinter không khả dụng trong môi trường Python hiện tại.")
    sys.exit(1)


# ==============================================================================
# HÀM ĐIỀU TIẾT HỆ THỐNG & ĐỘ ƯU TIÊN LUỒNG TRÊN WINDOWS
# ==============================================================================

def set_thread_priority(priority_level=0):
    """
    Điều chỉnh độ ưu tiên luồng (Thread Priority) trên Windows để đảm bảo:
    - Luồng đọc stream (FreshFrameReader) và luồng render preview (VideoCaptureWorker)
      luôn được ưu tiên CPU cao nhất, không bị nghẽn giật.
    - Luồng ghi đĩa (AsyncDiskWriter) chạy ở mức ưu tiên thấp (-1), chỉ tận dụng CPU nhàn rỗi.
    """
    if sys.platform == "win32":
        try:
            import ctypes
            handle = ctypes.windll.kernel32.GetCurrentThread()
            ctypes.windll.kernel32.SetThreadPriority(handle, int(priority_level))
        except Exception:
            pass


def enable_high_precision_timer():
    """Kích hoạt bộ hẹn giờ độ chính xác cao 1ms (timeBeginPeriod) trên Windows"""
    if sys.platform == "win32":
        try:
            import ctypes
            ctypes.windll.winmm.timeBeginPeriod(1)
        except Exception:
            pass


def disable_high_precision_timer():
    """Hủy kích hoạt bộ hẹn giờ độ chính xác cao trên Windows"""
    if sys.platform == "win32":
        try:
            import ctypes
            ctypes.windll.winmm.timeEndPeriod(1)
        except Exception:
            pass


# ==============================================================================
# HÀM BĂM CẢM NHẬN (PERCEPTUAL HASH) - LỌC TRÙNG LẶP KHI XE DỪNG ĐÈN ĐỎ
# ==============================================================================

def calculate_phash(image_bgr):
    """
    Tính mã băm cảm nhận (Perceptual Hash) 64-bit bằng DCT qua OpenCV.
    Kháng nhiễu hạt nhẹ, nén video và thay đổi ánh sáng nhỏ.
    """
    if image_bgr is None:
        return None
    try:
        resized = cv2.resize(image_bgr, (32, 32), interpolation=cv2.INTER_AREA)
        gray = cv2.cvtColor(resized, cv2.COLOR_BGR2GRAY)
        dct = cv2.dct(np.float32(gray))
        dct_low = dct[:8, :8]
        avg = (np.sum(dct_low) - dct_low[0, 0]) / 63.0
        return (dct_low > avg).flatten()
    except Exception:
        return None


def hamming_distance(hash1, hash2):
    """
    Tính khoảng cách Hamming (0 - 64) giữa 2 mã băm pHash.
    - dist <= 6: Hai ảnh giống nhau > 90-95% (xe dừng đèn đỏ / cảnh tĩnh không đổi).
    - dist > 6: Có phương tiện mới di chuyển vào khung hình.
    """
    if hash1 is None or hash2 is None:
        return 999
    return int(np.count_nonzero(hash1 != hash2))


# ==============================================================================
# HÀM HỖ TRỢ XỬ LÝ KHUNG GIỜ 1H & ĐƯỜNG DẪN LƯU TRỮ
# ==============================================================================

# ==============================================================================
# HÀM BÓC TÁCH LUỒNG VIDEO YOUTUBE (YOUTUBE LIVESTREAM RESOLVER)
# ==============================================================================

def is_youtube_url(url):
    """Kiểm tra xem URL có phải là liên kết YouTube hay không"""
    if not isinstance(url, str):
        return False
    u = url.lower().strip()
    return "youtube.com/" in u or "youtu.be/" in u


def resolve_youtube_stream(url, log_func=None):
    """
    Trích xuất luồng phát video trực tiếp (HLS .m3u8 hoặc stream URL) từ link YouTube thông qua yt-dlp.
    Hỗ trợ cả Livestream trực tiếp và Video thông thường trên YouTube.
    """
    try:
        import yt_dlp
    except ImportError:
        err = "Chưa cài đặt thư viện 'yt-dlp'. Vui lòng chạy lệnh: pip install yt-dlp"
        if log_func:
            log_func(f"⚠️ {err}")
        return None, 0.0, err

    try:
        if log_func:
            log_func("🔍 Đang giải mã luồng video YouTube qua yt-dlp (vui lòng đợi vài giây)...")

        # Cực kỳ quan trọng: KHÔNG truyền tham số 'format' cố định vào ydl_opts
        # để tránh lỗi 'Requested format is not available' trên các luồng Livestream YouTube.
        ydl_opts = {
            'quiet': True,
            'no_warnings': True,
            'noplaylist': True,
            'skip_download': True,
        }
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url.strip(), download=False)
            if not info:
                return None, "Không trích xuất được thông tin từ liên kết YouTube này."

            title = info.get('title', 'YouTube Stream')
            is_live = info.get('is_live', False)
            live_tag = " [LIVESTREAM TRỰC TIẾP]" if is_live else ""

            formats = info.get('formats', [])
            stream_url = None
            selected_res = "N/A"

            # 1. Lọc tất cả các định dạng CÓ VIDEO (bỏ qua các luồng audio only như fmt 233, 234)
            video_formats = [
                f for f in formats
                if f.get('url') and f.get('vcodec') and f.get('vcodec') != 'none'
            ]

            if video_formats:
                # Sắp xếp ưu tiên độ phân giải cao nhất (1080p -> 720p -> 480p...)
                # và ưu tiên chuẩn nén H.264/AVC (avc1) để OpenCV / FFMPEG giải mã phần cứng mượt mà nhất
                def sort_key(f):
                    h = f.get('height') or 0
                    fps = f.get('fps') or 0
                    tbr = f.get('tbr') or 0
                    vcodec = str(f.get('vcodec', '')).lower()
                    codec_score = 10 if ('avc' in vcodec or 'h264' in vcodec) else 0
                    return (h, codec_score, tbr, fps)

                video_formats.sort(key=sort_key, reverse=True)
                best_fmt = video_formats[0]
                stream_url = best_fmt.get('url')
                w = best_fmt.get('width', '?')
                h = best_fmt.get('height', '?')
                selected_res = f"{w}x{h}"

            # 2. Nếu không tìm thấy trong formats, thử info.get('url')
            if not stream_url:
                stream_url = info.get('url')

            # 3. Thử requested_formats nếu yt-dlp đã tự chọn định dạng ghép
            if not stream_url and 'requested_formats' in info:
                for rf in info['requested_formats']:
                    if rf.get('vcodec') != 'none' and rf.get('url'):
                        stream_url = rf.get('url')
                        break

            if not stream_url:
                return None, 0.0, "Không tìm thấy định dạng luồng video phù hợp."

            detected_fps = 30.0
            if video_formats:
                raw_fps = best_fmt.get('fps')
                if raw_fps and raw_fps > 0:
                    detected_fps = float(raw_fps)

            if log_func:
                log_func(f"✅ Đã kết nối thành công: {title}{live_tag} ({selected_res} @ {detected_fps:.0f} FPS)")

            return stream_url, detected_fps, None

    except Exception as e:
        err_msg = f"Lỗi bóc tách luồng YouTube: {str(e)}"
        if log_func:
            log_func(f"❌ {err_msg}")
        return None, 0.0, err_msg


# ==============================================================================
# THREAD 1: ĐỌC FRAME TƯƠI MỚI LIÊN TỤC (FRESH FRAME READER)
# Loại bỏ 100% hiện tượng tích tụ buffer, hỗ trợ webcam DSHOW & pacing video file
# ==============================================================================

class FreshFrameReader(threading.Thread):
    def __init__(self, source, source_fps=None):
        super().__init__(daemon=True)
        self.source = source
        self.source_fps = source_fps
        self.cap = None
        self.is_running = True
        self.latest_frame = None
        self.frame_count = 0
        self.lock = threading.Lock()

        self.width = 0
        self.height = 0
        self.fps = 30.0
        self.is_file = False
        self.frame_interval = 0.0333
        self.is_connected = False
        self.error_msg = ""

    def connect(self):
        source = self.source
        is_webcam = False
        if isinstance(source, str) and source.isdigit():
            source = int(source)
            is_webcam = True
        elif isinstance(source, int):
            is_webcam = True

        if is_webcam:
            # Trên Windows: Bắt buộc dùng DirectShow (CAP_DSHOW) để đạt 30 FPS mượt mà
            if sys.platform == "win32":
                self.cap = cv2.VideoCapture(source, cv2.CAP_DSHOW)
            else:
                self.cap = cv2.VideoCapture(source)
        else:
            self.is_file = os.path.isfile(str(source))
            if not self.is_file and str(source).startswith(("rtsp://", "rtsps://", "http://", "https://")):
                self.cap = cv2.VideoCapture(source, cv2.CAP_FFMPEG)
                self.cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
            else:
                self.cap = cv2.VideoCapture(source)

        if not self.cap or not self.cap.isOpened():
            self.is_connected = False
            self.error_msg = "Không thể mở nguồn phát video."
            return False

        self.width = int(self.cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        self.height = int(self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        stream_fps = self.cap.get(cv2.CAP_PROP_FPS)

        if stream_fps and 10.0 <= stream_fps <= 120.0 and not math.isnan(stream_fps):
            self.fps = float(stream_fps)
        elif self.source_fps and 10.0 <= self.source_fps <= 120.0:
            self.fps = float(self.source_fps)
        else:
            self.fps = 30.0

        self.frame_interval = 1.0 / self.fps
        self.is_connected = True
        return True

    def run(self):
        set_thread_priority(1)  # Ưu tiên cao nhất cho luồng đọc stream (Thread 1)

        if not self.connect():
            return

        is_http_hls = str(self.source).startswith(("http://", "https://"))
        needs_pacing = self.is_file or is_http_hls

        target_interval = self.frame_interval
        next_frame_time = time.time()
        consecutive_failures = 0

        while self.is_running:
            ret, frame = self.cap.read()

            if not ret or frame is None:
                if self.is_file:
                    # Video file phát hết: tua lại từ đầu để lặp liên tục
                    self.cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                    time.sleep(0.02)
                    next_frame_time = time.time()
                    continue
                else:
                    consecutive_failures += 1
                    # Với luồng HLS / Livestream: cho phép chờ tối đa 20 chu kỳ (~1s) trước khi ngắt kết nối
                    if consecutive_failures < 20:
                        time.sleep(0.05)
                        continue

                    # Mất tín hiệu mạng thực sự: thử kết nối lại
                    consecutive_failures = 0
                    self.is_connected = False
                    time.sleep(1.5)
                    if self.cap:
                        self.cap.release()
                    self.connect()
                    next_frame_time = time.time()
                    continue

            consecutive_failures = 0
            with self.lock:
                self.latest_frame = frame
                self.frame_count += 1
                self.is_connected = True

            # PACING CHUẨN THỜI GIAN THỰC CHO TỆP VIDEO VÀ LUỒNG HLS YOUTUBE
            # Triệt tiêu hoàn toàn hiện tượng xả 60 frames trong 0.05s rồi đứng hình 2s
            if needs_pacing:
                now = time.time()
                next_frame_time += target_interval
                wait_time = next_frame_time - now
                if wait_time > 0:
                    time.sleep(wait_time)
                elif wait_time < -0.2:
                    next_frame_time = now
            else:
                time.sleep(0.001)

        if self.cap:
            self.cap.release()

    def get_latest_frame(self):
        with self.lock:
            if self.latest_frame is not None:
                return True, self.latest_frame, self.frame_count
            return False, None, 0

    def stop(self):
        self.is_running = False


# ==============================================================================
# THREAD 3: GHI ĐĨA BẤT ĐỒNG BỘ (ASYNC DISK WRITER)
# Ghi ảnh 1080p JPEG 95% ở background, giải phóng 100% luồng đọc và giao diện
# ==============================================================================

class AsyncDiskWriter(threading.Thread):
    def __init__(self, save_queue, base_dir, camera_tag, jpeg_quality=100, log_callback=None):
        super().__init__(daemon=True)
        self.save_queue = save_queue
        self.base_dir = base_dir
        self.camera_tag = camera_tag
        self.jpeg_quality = int(jpeg_quality)
        self.log_callback = log_callback
        self.is_running = True
        self.current_slot_name = ""
        self.current_save_dir = ""

    def log(self, msg):
        if self.log_callback:
            self.log_callback(msg)

    def stop(self):
        self.is_running = False

    def run(self):
        # Hạ độ ưu tiên luồng ghi đĩa trên Windows xuống mức thấp (-1)
        # Đảm bảo CPU luôn ưu tiên 100% cho luồng hiển thị video 30 FPS không bao giờ khựng giật
        set_thread_priority(-1)

        while self.is_running or not self.save_queue.empty():
            try:
                item = self.save_queue.get(timeout=0.1)
            except queue.Empty:
                continue

            if item is None:
                break

            sharpness_score = 0.0
            motion_state = "moving"
            if len(item) == 5:
                frame, timestamp_epoch, seq, sharpness_score, motion_state = item
            elif len(item) == 4:
                frame, timestamp_epoch, seq, sharpness_score = item
            else:
                frame, timestamp_epoch, seq = item
            try:
                now = datetime.fromtimestamp(timestamp_epoch)

                # TỐI ƯU HÓA CAO ĐỘ: Chỉ kiểm tra và tạo thư mục khi chuyển khung giờ 1h
                # Triệt tiêu hoàn toàn hàng nghìn lệnh os.makedirs() gây nghẽn I/O ổ đĩa
                _, _, slot_str = get_slot_info(now)
                date_str = now.strftime("%Y-%m-%d")
                slot_name = f"{date_str}_{slot_str}"

                if slot_name != self.current_slot_name or not self.current_save_dir:
                    self.current_slot_name = slot_name
                    self.current_save_dir = os.path.join(self.base_dir, self.camera_tag, slot_name)
                    os.makedirs(self.current_save_dir, exist_ok=True)
                    if self.current_slot_name != "":
                        self.log(f"⏰ [CHUYỂN KHUNG GIỜ] Bắt đầu lưu vào khung: {slot_name}")

                timestamp_str = now.strftime("%Y%m%d_%H%M%S")
                millis = int(now.microsecond / 1000)
                # TÊN TỆP CHUẨN ĐỒNG NHẤT: Lưu 100% ảnh vào chung 1 thư mục
                file_name = f"{self.camera_tag}_{timestamp_str}_{millis:03d}_{seq:06d}.jpg"
                file_path = os.path.join(self.current_save_dir, file_name)

                # Nén JPEG trực tiếp trong RAM bằng imencode (Chất lượng 100% giữ nguyên chi tiết)
                encode_params = [int(cv2.IMWRITE_JPEG_QUALITY), self.jpeg_quality]
                success, enc_buf = cv2.imencode('.jpg', frame, encode_params)

                if success:
                    # Ghi buffer nhị phân trực tiếp xuống đĩa bằng tofile (cực nhanh, không lock NTFS lâu)
                    enc_buf.tofile(file_path)
                    file_size_kb = len(enc_buf) / 1024.0
                    sharp_tag = f" | Độ nét: {sharpness_score:.0f}" if sharpness_score > 0 else ""
                    self.log(f"📸 [#{seq:05d}] Đã lưu {file_name} ({file_size_kb:.1f} KB{sharp_tag}) -> [{slot_name}]")
                else:
                    self.log(f"❌ Lỗi nén ảnh JPEG: {file_name}")
            except Exception as e:
                self.log(f"❌ Lỗi khi ghi đĩa: {e}")
            finally:
                self.save_queue.task_done()


# ==============================================================================
# THREAD 2: WORKER ĐIỀU PHỐI PREVIEW & CHỤP ĐỊNH KỲ
# Chuẩn bị thumbnail trên CPU background, đẩy vào UI không tốn tài nguyên
# ==============================================================================

class VideoCaptureWorker(threading.Thread):
    def __init__(self, stream_url, base_dir, camera_tag, interval_sec=3.0, jpeg_quality=100,
                 preview_queue=None, get_preview_size=None, log_callback=None, status_callback=None):
        super().__init__(daemon=True)
        self.stream_url = stream_url
        self.base_dir = base_dir
        self.camera_tag = camera_tag
        self.interval_sec = max(0.5, float(interval_sec))
        self.jpeg_quality = int(jpeg_quality)

        self.preview_queue = preview_queue
        self.get_preview_size = get_preview_size
        self.log_callback = log_callback
        self.status_callback = status_callback

        self.is_running = False
        self.is_paused = False

        self.total_captured = 0
        self.current_fps = 0.0
        self.resolution_str = "N/A"
        self.last_capture_time = 0.0
        self.next_capture_in = self.interval_sec

        self.reader = None
        self.save_queue = queue.Queue(maxsize=50)
        self.disk_writer = AsyncDiskWriter(
            save_queue=self.save_queue,
            base_dir=self.base_dir,
            camera_tag=self.camera_tag,
            jpeg_quality=self.jpeg_quality,
            log_callback=self.log_callback
        )

    def log(self, message):
        if self.log_callback:
            self.log_callback(message)

    def update_status(self, state, text):
        if self.status_callback:
            self.status_callback(state, text)

    def stop(self):
        self.is_running = False
        if self.reader:
            self.reader.stop()
        if self.disk_writer:
            self.disk_writer.stop()
            try:
                self.save_queue.put_nowait(None)
            except Exception:
                pass

    def pause(self):
        self.is_paused = True
        self.update_status("PAUSED", "Đang tạm dừng thu thập")

    def resume(self):
        self.is_paused = False
        self.update_status("CAPTURING", "Đang thu thập dữ liệu")

    def run(self):
        set_thread_priority(0)  # Ưu tiên chuẩn cho luồng xử lý preview (Thread 2)
        self.is_running = True
        self.disk_writer.start()

        target_source = self.stream_url
        source_fps = None

        # Tự động nhận diện và bóc tách luồng phát trực tiếp YouTube
        if is_youtube_url(target_source):
            self.update_status("CONNECTING", "Đang giải mã link YouTube...")
            direct_url, yt_fps, err = resolve_youtube_stream(target_source, self.log)
            if direct_url:
                target_source = direct_url
                source_fps = yt_fps
            else:
                self.update_status("ERROR", "Lỗi link YouTube")
                self.log(f"❌ {err}")
                self.stop()
                return

        self.update_status("CONNECTING", f"Đang kết nối: {self.stream_url}")
        self.log(f"🚀 Khởi động kết nối: {self.stream_url}")
        self.log(f"⏱️ Tần suất chụp: {self.interval_sec:.1f}s / ảnh | Tự động chia 1h/folder")

        # Khởi chạy FreshFrameReader độc lập với bộ điều tiết nhịp FPS
        self.reader = FreshFrameReader(target_source, source_fps=source_fps)
        self.reader.start()

        # Chờ luồng kết nối trong tối đa 15 giây (cho luồng mạng / YouTube HLS)
        wait_start = time.time()
        while not self.reader.is_connected and self.is_running:
            if time.time() - wait_start > 15.0:
                err_msg = self.reader.error_msg or "Hết thời gian chờ kết nối (Timeout > 15s)"
                self.update_status("ERROR", err_msg)
                self.log(f"❌ LỖI: {err_msg} tại: {self.stream_url}")
                self.stop()
                return
            time.sleep(0.05)

        if not self.is_running:
            return

        self.resolution_str = f"{self.reader.width}x{self.reader.height}"
        self.log(f"✅ Kết nối thành công! Độ phân giải: {self.resolution_str} | FPS: {self.reader.fps:.1f}")
        self.update_status("CAPTURING", "Đang thu thập dữ liệu...")

        last_frame_id = -1
        fps_counter = 0
        fps_timer = time.time()
        self.last_capture_time = time.time()

        # Bộ đệm chọn khung hình sắc nét nhất (Anti-Motion Blur Burst Buffer)
        sharp_candidates = []
        is_sampling_sharp = False
        sample_start_time = 0.0

        # Tần suất render preview: 30 FPS (~33ms)
        target_preview_interval = 1.0 / min(30.0, max(15.0, self.reader.fps))
        last_preview_time = 0.0

        while self.is_running:
            loop_start = time.time()

            ret, frame, frame_id = self.reader.get_latest_frame()
            if not ret or frame is None:
                time.sleep(0.005)
                continue

            current_time = time.time()

            # Đếm thời gian tới lần chụp tiếp theo
            time_since_last = current_time - self.last_capture_time
            self.next_capture_in = max(0.0, self.interval_sec - time_since_last)

            # 1. TẠO THUMBNAIL PREVIEW ĐÚNG TỶ LỆ CHUẨN (LETTERBOXING) & CHỐNG LẶP FRAME
            if self.preview_queue and (frame_id != last_frame_id) and (current_time - last_preview_time >= target_preview_interval):
                last_frame_id = frame_id
                last_preview_time = current_time

                fps_counter += 1
                if current_time - fps_timer >= 1.0:
                    self.current_fps = fps_counter / (current_time - fps_timer)
                    fps_counter = 0
                    fps_timer = current_time

                # Lấy kích thước container của video_box
                target_w, target_h = (640, 360)
                if self.get_preview_size:
                    tw, th = self.get_preview_size()
                    if tw > 50 and th > 50:
                        target_w, target_h = tw, th

                # Giữ nguyên tỷ lệ chuẩn (Aspect Ratio) của camera gốc (16:9, 4:3...)
                h, w = frame.shape[:2]
                scale = min(target_w / w, target_h / h)
                new_w = max(1, int(w * scale))
                new_h = max(1, int(h * scale))

                # Resize mượt mà với INTER_LINEAR chống răng cưa và đổi màu sang RGB
                thumb_bgr = cv2.resize(frame, (new_w, new_h), interpolation=cv2.INTER_LINEAR)
                thumb_rgb = cv2.cvtColor(thumb_bgr, cv2.COLOR_BGR2RGB)

                # Letterboxing: Đặt video vào chính giữa canvas đen đúng kích thước container
                # Triệt tiêu 100% hiện tượng méo tỷ lệ và co giật kích thước widget
                canvas_frame = np.zeros((target_h, target_w, 3), dtype=np.uint8)
                y_off = (target_h - new_h) // 2
                x_off = (target_w - new_w) // 2
                canvas_frame[y_off:y_off + new_h, x_off:x_off + new_w] = thumb_rgb

                # Đưa thumbnail nhỏ vào preview_queue (Drop-old nếu queue đầy)
                try:
                    if self.preview_queue.full():
                        try:
                            self.preview_queue.get_nowait()
                        except queue.Empty:
                            pass
                    self.preview_queue.put_nowait((
                        canvas_frame,
                        self.next_capture_in,
                        self.current_fps,
                        self.total_captured,
                        self.resolution_str
                    ))
                except Exception:
                    pass

            # 2. KIỂM TRA ĐIỀU KIỆN CHỤP ẢNH ĐỊNH KỲ VỚI BỘ LỌC CHỐNG NHÒE CHUYỂN ĐỘNG
            # Quét tìm khung hình có độ nét cao nhất (Laplacian Variance) trong cửa sổ 0.25s
            if not self.is_paused:
                # Kích hoạt cửa sổ tìm frame nét nhất trước mốc chụp 0.25 giây
                if not is_sampling_sharp and (current_time - self.last_capture_time >= max(0.1, self.interval_sec - 0.25)):
                    is_sampling_sharp = True
                    sharp_candidates = []
                    sample_start_time = current_time

                if is_sampling_sharp:
                    try:
                        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
                        score = float(cv2.Laplacian(gray, cv2.CV_64F).var())
                    except Exception:
                        score = 0.0
                    sharp_candidates.append((frame.copy(), current_time, score))

                    # Khi đã quét đủ 0.25s hoặc có ít nhất 6 frames
                    if (current_time - sample_start_time >= 0.25) or len(sharp_candidates) >= 8:
                        is_sampling_sharp = False
                        self.last_capture_time = current_time
                        if sharp_candidates:
                            # Chọn frame có độ nét cao nhất (loại bỏ hoàn toàn motion blur)
                            sharp_candidates.sort(key=lambda x: x[2], reverse=True)
                            best_frame, best_time, best_score = sharp_candidates[0]

                            # LƯU 100% ẢNH VÀO CHUNG 1 THƯ MỤC - KHÔNG BỎ ẢNH NÀO
                            # Việc phân loại phương tiện và trạng thái do dán nhãn & mô hình đảm nhiệm
                            self.total_captured += 1
                            try:
                                self.save_queue.put_nowait((best_frame, best_time, self.total_captured, best_score))
                            except queue.Full:
                                self.log("⚠️ Hàng đợi ghi đĩa bận. Đã bỏ qua 1 frame snapshot.")
                        sharp_candidates = []

            # Nhường CPU nhẹ nhàng giữ nhịp vòng lặp
            elapsed = time.time() - loop_start
            sleep_wait = 0.003 - elapsed
            if sleep_wait > 0:
                time.sleep(sleep_wait)

        if self.reader:
            self.reader.stop()
        self.update_status("STOPPED", "Đã dừng tiến trình thu thập")
        self.log("🛑 Tiến trình thu thập đã kết thúc an toàn.")


# ==============================================================================
# GIAO DIỆN NGƯỜI DÙNG TKINTER HIỆN ĐẠI (STREAM DATA COLLECTOR GUI)
# ==============================================================================

class StreamCollectorApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Hệ Thống Thu Thập Dữ Liệu Video Streaming (Đếm & Đo Tốc Độ Xe ITS 2026)")
        self.root.geometry("1280x820")
        self.root.minsize(1050, 680)

        self.bg_color = "#1e1e2e"
        self.panel_bg = "#252538"
        self.accent_color = "#3b82f6"
        self.text_color = "#cdd6f4"
        self.success_color = "#10b981"
        self.warning_color = "#f59e0b"
        self.danger_color = "#ef4444"

        self.root.configure(bg=self.bg_color)

        self.worker = None
        self.photo_image = None
        self.preview_w = 640
        self.preview_h = 360
        self.last_stat_update = 0.0

        # Hàng đợi trung chuyển Preview tối đa 1 frame
        self.preview_queue = queue.Queue(maxsize=1)

        # Hàng đợi nhật ký (Log Queue) độc lập cho background thread
        # Giải phóng hoàn toàn UI thread khỏi các lệnh in log đồng bộ gây khựng giật khi chụp
        self.log_queue = queue.Queue(maxsize=500)

        self.setup_styles()
        self.create_widgets()

        # Đăng ký đóng ứng dụng an toàn
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)

        # Vòng lặp cập nhật đồng hồ (1 giây/lần)
        self.update_clock()

        # Vòng lặp render video độc lập siêu mượt (10ms poll)
        self.update_preview_loop()

    def setup_styles(self):
        style = ttk.Style()
        style.theme_use('clam')

        style.configure("Dark.TLabelframe", background=self.panel_bg, foreground="#89b4fa",
                        relief="ridge", borderwidth=1)
        style.configure("Dark.TLabelframe.Label", background=self.panel_bg, foreground="#89b4fa",
                        font=("Segoe UI", 10, "bold"))

        style.configure("TEntry", fieldbackground="#313244", foreground="#ffffff", insertcolor="#ffffff")
        style.configure("TCombobox", fieldbackground="#313244", foreground="#ffffff")

    def create_widgets(self):
        # -------------------------------------------------------------
        # 1. HEADER BANNER
        # -------------------------------------------------------------
        header_frame = tk.Frame(self.root, bg="#11111b", height=65)
        header_frame.pack(fill="x", side="top")

        title_lbl = tk.Label(
            header_frame,
            text="📹 BỘ THU THẬP DỮ LIỆU ẢNH STREAMING ĐA GIAO THỨC",
            font=("Segoe UI", 15, "bold"),
            bg="#11111b",
            fg="#89b4fa"
        )
        title_lbl.pack(side="left", padx=20, pady=12)

        self.status_badge = tk.Label(
            header_frame,
            text="● SẴN SÀNG",
            font=("Segoe UI", 10, "bold"),
            bg="#313244",
            fg="#a6adc8",
            padx=12,
            pady=4
        )
        self.status_badge.pack(side="right", padx=20, pady=15)

        self.clock_lbl = tk.Label(
            header_frame,
            text="00:00:00 | Khung giờ: 00h-01h",
            font=("Consolas", 10),
            bg="#11111b",
            fg="#bac2de"
        )
        self.clock_lbl.pack(side="right", padx=15, pady=15)

        # -------------------------------------------------------------
        # 2. KHU VỰC THÂN CHÍNH (CHIA 2 CỘT TRÁI - PHẢI)
        # -------------------------------------------------------------
        main_body = tk.Frame(self.root, bg=self.bg_color)
        main_body.pack(fill="both", expand=True, padx=15, pady=12)

        left_col = tk.Frame(main_body, bg=self.bg_color, width=380)
        left_col.pack(side="left", fill="y", padx=(0, 10))

        right_col = tk.Frame(main_body, bg=self.bg_color)
        right_col.pack(side="right", fill="both", expand=True)

        # -------------------------------------------------------------
        # 2.1 CỘT TRÁI: CẤU HÌNH & BẢNG ĐIỀU KHIỂN
        # -------------------------------------------------------------
        config_box = ttk.LabelFrame(left_col, text="⚙️ CẤU HÌNH THU THẬP", style="Dark.TLabelframe", padding=12)
        config_box.pack(fill="x", pady=(0, 10))

        # URL Stream
        tk.Label(config_box, text="Nguồn Stream (RTSP / HLS / YouTube / Webcam / File):", bg=self.panel_bg, fg=self.text_color, font=("Segoe UI", 9, "bold")).pack(anchor="w")

        self.stream_url_var = tk.StringVar(value="rtsp://")
        self.stream_entry = tk.Entry(config_box, textvariable=self.stream_url_var, bg="#313244", fg="#ffffff", insertbackground="#ffffff", relief="flat", font=("Segoe UI", 9))
        self.stream_entry.pack(fill="x", pady=(2, 6), ipady=4)

        # Nút chọn file video hoặc webcam mẫu
        btn_preset_frame = tk.Frame(config_box, bg=self.panel_bg)
        btn_preset_frame.pack(fill="x", pady=(0, 10))

        tk.Button(btn_preset_frame, text="Webcam 0", bg="#45475a", fg="#ffffff", relief="flat", padx=5, command=lambda: self.stream_url_var.set("0")).pack(side="left", padx=2)
        tk.Button(btn_preset_frame, text="HLS Mẫu", bg="#45475a", fg="#ffffff", relief="flat", padx=5, command=lambda: self.stream_url_var.set("https://test-streams.mux.dev/x36xhzz/x36xhzz.m3u8")).pack(side="left", padx=2)
        tk.Button(btn_preset_frame, text="Dán Link", bg="#b91c1c", fg="#ffffff", relief="flat", padx=6, command=self.paste_from_clipboard).pack(side="left", padx=2)
        tk.Button(btn_preset_frame, text="Chọn MP4...", bg="#45475a", fg="#ffffff", relief="flat", padx=5, command=self.browse_video_file).pack(side="right", padx=2)

        # Tên Camera / Thẻ phân loại
        tk.Label(config_box, text="Tên Camera / Làn xe (Tag):", bg=self.panel_bg, fg=self.text_color, font=("Segoe UI", 9, "bold")).pack(anchor="w")
        self.camera_tag_var = tk.StringVar(value="cam_lane01")
        tk.Entry(config_box, textvariable=self.camera_tag_var, bg="#313244", fg="#ffffff", insertbackground="#ffffff", relief="flat", font=("Segoe UI", 9)).pack(fill="x", pady=(2, 10), ipady=4)

        # Thư mục lưu trữ gốc
        tk.Label(config_box, text="Thư mục lưu trữ Dataset:", bg=self.panel_bg, fg=self.text_color, font=("Segoe UI", 9, "bold")).pack(anchor="w")
        dir_frame = tk.Frame(config_box, bg=self.panel_bg)
        dir_frame.pack(fill="x", pady=(2, 10))

        default_dataset_dir = str(RAW_FRAMES_DIR)
        self.base_dir_var = tk.StringVar(value=default_dataset_dir)
        tk.Entry(dir_frame, textvariable=self.base_dir_var, bg="#313244", fg="#ffffff", insertbackground="#ffffff", relief="flat", font=("Segoe UI", 9)).pack(side="left", fill="x", expand=True, ipady=4)
        tk.Button(dir_frame, text="Duyệt...", bg="#45475a", fg="#ffffff", relief="flat", padx=8, command=self.browse_output_dir).pack(side="right", padx=(5, 0))

        # Tần suất chụp & Quy tắc lưu trữ
        param_grid = tk.Frame(config_box, bg=self.panel_bg)
        param_grid.pack(fill="x", pady=(0, 5))

        tk.Label(param_grid, text="Chu kỳ chụp:", bg=self.panel_bg, fg=self.text_color).grid(row=0, column=0, sticky="w")
        self.interval_var = tk.StringVar(value="3.0")
        tk.Spinbox(param_grid, from_=0.5, to=60.0, increment=0.5, textvariable=self.interval_var, width=6, bg="#313244", fg="#ffffff", buttonbackground="#45475a").grid(row=0, column=1, padx=5, pady=3, sticky="w")
        tk.Label(param_grid, text="giây / ảnh", bg=self.panel_bg, fg="#a6adc8").grid(row=0, column=2, sticky="w")

        tk.Label(param_grid, text="Chia folder:", bg=self.panel_bg, fg=self.text_color).grid(row=1, column=0, sticky="w", pady=4)
        tk.Label(param_grid, text="Mỗi 1 giờ / 1 folder", font=("Segoe UI", 9, "bold"), fg="#89b4fa", bg=self.panel_bg).grid(row=1, column=1, columnspan=2, sticky="w", pady=4)

        tk.Label(config_box, text="💡 Cứ mỗi 3s chụp 1 ảnh nét nhất. Lưu 100% ảnh chung thư mục để sẵn sàng dán nhãn.",
                 font=("Segoe UI", 8, "italic"), fg="#a6adc8", bg=self.panel_bg, wraplength=340, justify="left").pack(anchor="w", pady=(2, 6))

        # -------------------------------------------------------------
        # KHU VỰC THỐNG KÊ (DASHBOARD STATS)
        # -------------------------------------------------------------
        stats_box = ttk.LabelFrame(left_col, text="📊 THỐNG KÊ THU THẬP", style="Dark.TLabelframe", padding=12)
        stats_box.pack(fill="x", pady=(0, 10))

        self.stat_captured_lbl = tk.Label(stats_box, text="📸 Đã chụp & lưu: 0 ảnh", font=("Segoe UI", 11, "bold"), fg=self.success_color, bg=self.panel_bg)
        self.stat_captured_lbl.pack(anchor="w", pady=2)

        self.stat_slot_lbl = tk.Label(stats_box, text="📁 Khung giờ lưu: Đang chờ...", font=("Segoe UI", 9), fg="#bac2de", bg=self.panel_bg)
        self.stat_slot_lbl.pack(anchor="w", pady=2)

        self.stat_countdown_lbl = tk.Label(stats_box, text="⏳ Chụp ảnh tiếp theo sau: -- s", font=("Segoe UI", 9), fg="#f9e2af", bg=self.panel_bg)
        self.stat_countdown_lbl.pack(anchor="w", pady=2)

        self.stat_fps_lbl = tk.Label(stats_box, text="⚡ FPS luồng: -- | Độ phân giải: --", font=("Segoe UI", 9), fg="#a6adc8", bg=self.panel_bg)
        self.stat_fps_lbl.pack(anchor="w", pady=2)

        # -------------------------------------------------------------
        # NÚT ĐIỀU KHIỂN (ACTION BUTTONS)
        # -------------------------------------------------------------
        btn_frame = tk.Frame(left_col, bg=self.bg_color)
        btn_frame.pack(fill="x", pady=5)

        self.btn_start = tk.Button(
            btn_frame,
            text="▶ BẮT ĐẦU CHỤP",
            font=("Segoe UI", 10, "bold"),
            bg="#22c55e",
            fg="#ffffff",
            activebackground="#16a34a",
            relief="flat",
            height=2,
            command=self.start_capture
        )
        self.btn_start.pack(fill="x", pady=(0, 6))

        action_row = tk.Frame(btn_frame, bg=self.bg_color)
        action_row.pack(fill="x")

        self.btn_pause = tk.Button(
            action_row,
            text="⏸ TẠM DỪNG",
            font=("Segoe UI", 9, "bold"),
            bg="#f59e0b",
            fg="#ffffff",
            relief="flat",
            state="disabled",
            command=self.toggle_pause
        )
        self.btn_pause.pack(side="left", fill="x", expand=True, padx=(0, 4))

        self.btn_stop = tk.Button(
            action_row,
            text="⏹ DỪNG LẠI",
            font=("Segoe UI", 9, "bold"),
            bg="#ef4444",
            fg="#ffffff",
            relief="flat",
            state="disabled",
            command=self.stop_capture
        )
        self.btn_stop.pack(side="right", fill="x", expand=True, padx=(4, 0))

        tk.Button(
            btn_frame,
            text="📂 Mở Thư Mục Ảnh Hiện Tại",
            font=("Segoe UI", 9),
            bg="#3b82f6",
            fg="#ffffff",
            relief="flat",
            command=self.open_current_folder
        ).pack(fill="x", pady=(6, 0))

        # -------------------------------------------------------------
        # 2.2 CỘT PHẢI: LIVE VIDEO PREVIEW & TERMINAL LOGS
        # -------------------------------------------------------------
        video_box = ttk.LabelFrame(right_col, text="📺 XEM TRỰC TIẾP LUỒNG STREAM (LIVE PREVIEW)", style="Dark.TLabelframe", padding=6)
        video_box.pack(fill="both", expand=True, pady=(0, 10))

        # Sử dụng tk.Label thay vì Canvas để BitBlt trực tiếp lên cửa sổ, loại bỏ 100% giật khựng
        self.video_label = tk.Label(
            video_box,
            bg="#11111b",
            fg="#6c7086",
            font=("Segoe UI", 12),
            text="Chưa có luồng phát.\nVui lòng nhập URL và bấm 'BẮT ĐẦU CHỤP' để kích hoạt xem trực tiếp."
        )
        self.video_label.pack(fill="both", expand=True)
        self.video_label.bind("<Configure>", self.on_video_resize)

        log_box = ttk.LabelFrame(right_col, text="📝 NHẬT KÝ THU THẬP DỮ LIỆU", style="Dark.TLabelframe", padding=6)
        log_box.pack(fill="x")

        self.log_text = tk.Text(log_box, bg="#181825", fg="#cdd6f4", font=("Consolas", 9), height=7, relief="flat", wrap="word")
        self.log_text.pack(side="left", fill="both", expand=True)

        scroll = tk.Scrollbar(log_box, command=self.log_text.yview)
        scroll.pack(side="right", fill="y")
        self.log_text.config(yscrollcommand=scroll.set)

        self.add_log("👋 Chào mừng bạn đến với ứng dụng Thu thập Ảnh Video Streaming!")
        self.add_log(f"📁 Thư mục lưu trữ mặc định: {default_dataset_dir}")
        self.add_log("💡 Kiến trúc tối ưu: 3 Thread chuyên biệt triệt tiêu 100% hiện tượng khựng giật hình ảnh.")

    def on_video_resize(self, event):
        """Cập nhật kích thước vùng hiển thị khi người dùng thay đổi kích cỡ cửa sổ"""
        # Ngưỡng sai số 4px để chống hiện tượng dao động micro-jitter của layout
        if abs(event.width - self.preview_w) > 4 or abs(event.height - self.preview_h) > 4:
            if event.width > 50 and event.height > 50:
                self.preview_w = event.width
                self.preview_h = event.height

    def get_preview_size(self):
        return self.preview_w, self.preview_h

    # --------------------------------------------------------------------------
    # VÒNG LẶP RENDER PREVIEW SIÊU NHẸ (< 1MS TRÊN UI THREAD)
    # --------------------------------------------------------------------------

    def enqueue_log(self, msg):
        """Hàng đợi ghi log bất đồng bộ từ background thread (an toàn 100% không làm nghẽn UI)"""
        try:
            self.log_queue.put_nowait(msg)
        except queue.Full:
            try:
                self.log_queue.get_nowait()
                self.log_queue.put_nowait(msg)
            except Exception:
                pass

    def update_preview_loop(self):
        """
        Vòng lặp Tkinter 10ms: Chỉ chuyển đổi mảng RGB nhỏ sang PhotoImage và BitBlt.
        Không tính toán resize, không đổi màu hệ hình trên UI thread.
        Đồng thời tiêu thụ nhật ký từ hàng đợi nền bất đồng bộ với yview_moveto (nhẹ hơn see("end") 100 lần).
        """
        try:
            # 1. Hiển thị hình ảnh video tức thì (< 1ms)
            if not self.preview_queue.empty():
                item = self.preview_queue.get_nowait()
                thumb_rgb, next_in, fps, count, res = item

                if HAS_PIL and thumb_rgb is not None:
                    img = Image.fromarray(thumb_rgb)
                    self.photo_image = ImageTk.PhotoImage(image=img)
                    self.video_label.configure(image=self.photo_image, text="")

                # 2. Cập nhật số liệu chữ cách quãng 250ms (chống layout thrashing)
                now = time.time()
                if now - self.last_stat_update >= 0.25:
                    self.stat_captured_lbl.config(text=f"📸 Đã chụp & lưu: {count} ảnh")
                    self.stat_countdown_lbl.config(text=f"⏳ Chụp ảnh tiếp theo sau: {next_in:.1f} s")
                    self.stat_fps_lbl.config(text=f"⚡ FPS: {fps:.1f} | Độ phân giải: {res}")
                    self.last_stat_update = now

            # 3. Tiêu thụ hàng đợi nhật ký (Log Queue) bất đồng bộ
            # Rút tối đa 2 tin log mỗi chu kỳ 10ms để hoàn toàn không gây trễ nhịp hiển thị frame
            logs_added = 0
            while not self.log_queue.empty() and logs_added < 2:
                try:
                    msg = self.log_queue.get_nowait()
                    now_str = datetime.now().strftime("%H:%M:%S")
                    self.log_text.insert("end", f"[{now_str}] {msg}\n")
                    logs_added += 1
                except queue.Empty:
                    break

            if logs_added > 0:
                line_count = int(float(self.log_text.index("end-1c")))
                if line_count > 120:
                    self.log_text.delete("1.0", "30.0")
                self.log_text.yview_moveto(1.0)

        except Exception:
            pass

        # Quét hàng đợi mỗi 10 mili-giây: bám sát tốc độ phát của camera
        self.root.after(10, self.update_preview_loop)

    # --------------------------------------------------------------------------
    # CÁC HÀM XỬ LÝ SỰ KIỆN GIAO DIỆN
    # --------------------------------------------------------------------------

    def paste_from_clipboard(self):
        """Dán nhanh link từ Clipboard (hỗ trợ link YouTube, RTSP, HLS)"""
        try:
            clipboard_text = self.root.clipboard_get().strip()
            if clipboard_text:
                self.stream_url_var.set(clipboard_text)
                self.add_log(f"📋 Đã dán liên kết: {clipboard_text}")
        except Exception:
            pass

    def browse_video_file(self):
        f = filedialog.askopenfilename(
            title="Chọn tệp video camera ghi lại",
            filetypes=[("Video files", "*.mp4 *.avi *.mkv *.mov *.ts"), ("All files", "*.*")]
        )
        if f:
            self.stream_url_var.set(f)

    def browse_output_dir(self):
        d = filedialog.askdirectory(title="Chọn thư mục lưu trữ Dataset")
        if d:
            self.base_dir_var.set(d)

    def add_log(self, text):
        now_str = datetime.now().strftime("%H:%M:%S")
        self.log_text.insert("end", f"[{now_str}] {text}\n")
        line_count = int(float(self.log_text.index("end-1c")))
        if line_count > 120:
            self.log_text.delete("1.0", "30.0")
        self.log_text.yview_moveto(1.0)

    def update_status_badge(self, state, text):
        if state == "CAPTURING":
            self.status_badge.config(text=f"● {text}", bg="#065f46", fg="#34d399")
        elif state == "PAUSED":
            self.status_badge.config(text=f"❚❚ {text}", bg="#78350f", fg="#fde68a")
        elif state == "CONNECTING" or state == "RECONNECTING":
            self.status_badge.config(text=f"◌ {text}", bg="#1e3a8a", fg="#93c5fd")
        elif state == "ERROR":
            self.status_badge.config(text=f"✖ {text}", bg="#7f1d1d", fg="#fca5a5")
        else:
            self.status_badge.config(text="● SẴN SÀNG", bg="#313244", fg="#a6adc8")

    def update_clock(self):
        now = datetime.now()
        _, _, slot_str = get_slot_info(now)
        clock_text = f"{now.strftime('%d/%m/%Y %H:%M:%S')} | Khung: {slot_str}"
        self.clock_lbl.config(text=clock_text)

        if self.worker and self.worker.is_running:
            self.stat_slot_lbl.config(text=f"📁 Thư mục khung giờ: {now.strftime('%Y-%m-%d')}_{slot_str}")

        self.root.after(1000, self.update_clock)

    def start_capture(self):
        stream_url = self.stream_url_var.get().strip()
        if not stream_url or stream_url == "rtsp://":
            messagebox.showwarning("Cảnh báo", "Vui lòng nhập đường dẫn URL Stream, tệp MP4 hoặc chọn Webcam!")
            return

        base_dir = self.base_dir_var.get().strip()
        camera_tag = self.camera_tag_var.get().strip() or "stream"

        try:
            interval = float(self.interval_var.get().strip())
        except ValueError:
            interval = 3.0

        self.btn_start.config(state="disabled")
        self.btn_pause.config(state="normal", text="⏸ TẠM DỪNG", bg="#f59e0b")
        self.btn_stop.config(state="normal")
        self.stream_entry.config(state="disabled")

        self.worker = VideoCaptureWorker(
            stream_url=stream_url,
            base_dir=base_dir,
            camera_tag=camera_tag,
            interval_sec=interval,
            preview_queue=self.preview_queue,
            get_preview_size=self.get_preview_size,
            log_callback=self.enqueue_log,
            status_callback=lambda state, txt: self.root.after(0, self.update_status_badge, state, txt)
        )
        self.worker.start()

    def toggle_pause(self):
        if not self.worker:
            return
        if self.worker.is_paused:
            self.worker.resume()
            self.btn_pause.config(text="⏸ TẠM DỪNG", bg="#f59e0b")
        else:
            self.worker.pause()
            self.btn_pause.config(text="▶ TIẾP TỤC", bg="#22c55e")

    def stop_capture(self):
        if self.worker:
            self.worker.stop()
            self.worker = None

        self.btn_start.config(state="normal")
        self.btn_pause.config(state="disabled", text="⏸ TẠM DỪNG")
        self.btn_stop.config(state="disabled")
        self.stream_entry.config(state="normal")
        self.update_status_badge("STOPPED", "SẴN SÀNG")

        self.photo_image = None
        self.video_label.configure(
            image="",
            text="Đã dừng luồng thu thập.\nBấm 'BẮT ĐẦU CHỤP' để tiếp tục phiên mới."
        )

    def open_current_folder(self):
        base_dir = self.base_dir_var.get().strip()
        camera_tag = self.camera_tag_var.get().strip() or "stream"
        target_dir, slot_name = get_current_storage_directory(base_dir, camera_tag)

        if not os.path.exists(target_dir):
            os.makedirs(target_dir, exist_ok=True)

        if sys.platform == "win32":
            os.startfile(target_dir)
        elif sys.platform == "darwin":
            subprocess.Popen(["open", target_dir])
        else:
            subprocess.Popen(["xdg-open", target_dir])

        self.add_log(f"📂 Đã mở thư mục: {target_dir}")

    def on_closing(self):
        """Dọn dẹp tài nguyên và tắt ứng dụng an toàn"""
        self.stop_capture()
        disable_high_precision_timer()
        self.root.destroy()


# ==============================================================================
# HỖ TRỢ CHẠY CHẾ ĐỘ DÒNG LỆNH (HEADLESS CLI MODE)
# ==============================================================================

def run_cli_mode(args):
    import argparse
    parser = argparse.ArgumentParser(description="Thu thập ảnh từ luồng video streaming (CLI)")
    parser.add_argument("--stream", type=str, required=True, help="URL stream (RTSP, HLS, mp4...)")
    parser.add_argument("--output", type=str, default=str(RAW_FRAMES_DIR), help="Thư mục gốc")
    parser.add_argument("--tag", type=str, default="cam_lane01", help="Tên camera / làn xe")
    parser.add_argument("--interval", type=float, default=3.0, help="Chu kỳ chụp (giây, mặc định 3.0)")
    parser.add_argument("--quality", type=int, default=100, help="Chất lượng JPEG (1-100, mặc định 100)")
    cli_args = parser.parse_args(args)

    print("=" * 70)
    print("🚀 BẮT ĐẦU CHẠY THU THẬP Ở CHẾ ĐỘ DÒNG LỆNH (HEADLESS CLI)")
    print(f"📡 Nguồn Stream: {cli_args.stream}")
    print(f"⏱️ Chu kỳ: {cli_args.interval} giây / 1 ảnh")
    print("📁 Chia folder tự động: Mỗi 1 giờ 1 folder (00h-01h, 01h-02h, ...)")
    print("=" * 70)

    worker = VideoCaptureWorker(
        stream_url=cli_args.stream,
        base_dir=cli_args.output,
        camera_tag=cli_args.tag,
        interval_sec=cli_args.interval,
        jpeg_quality=cli_args.quality,
        log_callback=print,
        status_callback=lambda st, txt: print(f"[{st}] {txt}")
    )
    worker.start()

    try:
        while True:
            time.sleep(1.0)
    except KeyboardInterrupt:
        print("\n🛑 Nhận tín hiệu dừng từ người dùng...")
        worker.stop()
        worker.join()
        print("✅ Đã kết thúc phiên thu thập.")


# ==============================================================================
# ĐIỂM VÀO CHÍNH (MAIN ENTRY POINT)
# ==============================================================================

def main():
    enable_high_precision_timer()
    try:
        if "--cli" in sys.argv or "--stream" in sys.argv:
            cli_args = [arg for arg in sys.argv[1:] if arg != "--cli"]
            run_cli_mode(cli_args)
        else:
            root = tk.Tk()
            app = StreamCollectorApp(root)
            root.mainloop()
    finally:
        disable_high_precision_timer()


if __name__ == "__main__":
    main()
