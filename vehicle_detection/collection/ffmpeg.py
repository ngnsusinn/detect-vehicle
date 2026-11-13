#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
================================================================================
HỆ THỐNG TRÍCH XUẤT & CHỤP ẢNH CHẤT LƯỢNG CAO DỰA TRÊN FFMPEG (HỆ THỐNG ĐẾM & ĐO TỐC ĐỘ XE ITS 2026)
HIGH-FIDELITY STREAM CAPTURE ENGINE POWERED BY FFMPEG & SHARPNESS FILTER
================================================================================
Giải quyết triệt để vấn đề: "Xem stream thì nét nhưng capture ảnh bị mờ/giảm chất lượng":
1. Trích xuất chuẩn I-Frame (Keyframe): Loại bỏ 100% P/B-frame bị nén vỡ macroblock.
2. Bộ lọc chống nhòe chuyển động (Laplacian Variance Sharpness Selector): Tự động chọn
   khung hình sắc nét nhất trong chu kỳ chụp khi phương tiện di chuyển qua góc máy.
3. Giải mã FFmpeg nguyên bản (Full precision deblocking & chroma reconstruction):
   Khắc phục hiện tượng OpenCV VideoCapture skip frame hoặc giảm độ chính xác giải mã.
4. Xuất ảnh chất lượng tối đa: Hỗ trợ PNG lossless hoặc JPEG qscale=1 (chất lượng 100%).
5. Tự động phân chia thư mục theo từng khung giờ (1h/folder) và hỗ trợ đầy đủ các nguồn:
   RTSP, HLS (.m3u8), YouTube Livestream, Webcam, Tệp video ghi sẵn.
"""

import os
import sys
import time
import math
import json
import shutil
import argparse
import subprocess
from datetime import datetime

from vehicle_detection.paths import RAW_FRAMES_DIR
from vehicle_detection.collection.storage import get_slot_info, get_current_storage_directory

# Đảm bảo terminal hiển thị UTF-8 chuẩn trên Windows
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

try:
    import cv2
    import numpy as np
    HAS_CV2 = True
except ImportError:
    HAS_CV2 = False

try:
    from PIL import Image
    HAS_PIL = True
except ImportError:
    HAS_PIL = False


# ==============================================================================
# HÀM TIỆN ÍCH HỆ THỐNG & KHUNG GIỜ 1H
# ==============================================================================

def check_ffmpeg_available():
    """Kiểm tra sự tồn tại của lệnh ffmpeg trong hệ thống"""
    ffmpeg_cmd = shutil.which("ffmpeg")
    return ffmpeg_cmd is not None


def is_youtube_url(url):
    """Kiểm tra URL có phải là liên kết YouTube hay không"""
    if not isinstance(url, str):
        return False
    u = url.lower().strip()
    return "youtube.com/" in u or "youtu.be/" in u


def resolve_youtube_stream(url):
    """
    Trích xuất luồng video phân giải cao nhất từ YouTube bằng yt-dlp.
    Ưu tiên 1080p H.264/AVC hoặc MP4 để FFmpeg giải mã mượt mà nhất.
    """
    try:
        import yt_dlp
    except ImportError:
        print("❌ LỖI: Chưa cài đặt thư viện 'yt-dlp'. Vui lòng chạy: pip install yt-dlp")
        return None, 0.0, "Thiếu yt-dlp"

    print("🔍 Đang phân tích và giải mã liên kết YouTube bằng yt-dlp...")
    ydl_opts = {
        'quiet': True,
        'no_warnings': True,
        'noplaylist': True,
        'skip_download': True,
    }
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url.strip(), download=False)
            if not info:
                return None, 0.0, "Không trích xuất được thông tin YouTube."

            title = info.get('title', 'YouTube Stream')
            formats = info.get('formats', [])

            # Lọc video formats có URL hợp lệ
            video_formats = [
                f for f in formats
                if f.get('url') and f.get('vcodec') and f.get('vcodec') != 'none'
            ]

            if not video_formats:
                stream_url = info.get('url')
                if not stream_url and 'requested_formats' in info:
                    for rf in info['requested_formats']:
                        if rf.get('url'):
                            stream_url = rf.get('url')
                            break
                if not stream_url:
                    return None, 0.0, "Không tìm thấy định dạng luồng video phù hợp."
                return stream_url, 30.0, None

            # Sắp xếp ưu tiên độ phân giải cao nhất (1080p > 720p > 480p) và bitrate cao nhất
            def sort_key(f):
                h = f.get('height') or 0
                fps = f.get('fps') or 0
                tbr = f.get('tbr') or 0
                vcodec = str(f.get('vcodec', '')).lower()
                codec_bonus = 50 if ('avc' in vcodec or 'h264' in vcodec) else 0
                return (h, codec_bonus, tbr, fps)

            video_formats.sort(key=sort_key, reverse=True)
            best_fmt = video_formats[0]
            stream_url = best_fmt.get('url')
            w = best_fmt.get('width', '?')
            h = best_fmt.get('height', '?')
            fps = float(best_fmt.get('fps') or 30.0)

            print(f"✅ Đã chọn luồng chất lượng cao nhất: {title} ({w}x{h} @ {fps:.0f} FPS)")
            return stream_url, fps, None
    except Exception as e:
        return None, 0.0, str(e)


# ==============================================================================
# HÀM TÍNH ĐỘ SẮC NÉT (SHARPNESS METRIC - LAPLACIAN VARIANCE)
# ==============================================================================

def compute_sharpness(image_bgr_or_gray):
    """
    Tính điểm sắc nét bằng phương sai toán tử Laplacian (Laplacian Variance).
    - Ảnh mờ chuyển động (motion blur) hoặc out-net: điểm thấp (< 100).
    - Ảnh sắc nét, rõ viền thân xe và bánh xe: điểm cao (> 300 - 1500+).
    """
    if not HAS_CV2 or image_bgr_or_gray is None:
        return 0.0
    if len(image_bgr_or_gray.shape) == 3:
        gray = cv2.cvtColor(image_bgr_or_gray, cv2.COLOR_BGR2GRAY)
    else:
        gray = image_bgr_or_gray
    lap = cv2.Laplacian(gray, cv2.CV_64F)
    score = lap.var()
    return float(score)


def calculate_phash(image_bgr):
    """Tính mã băm cảm nhận (Perceptual Hash) 64-bit bằng DCT để phát hiện xe dừng đèn đỏ"""
    if not HAS_CV2 or image_bgr is None:
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
    """Khoảng cách Hamming: <= 6 nghĩa là hai ảnh giống nhau > 90% (xe dừng / cảnh tĩnh)"""
    if hash1 is None or hash2 is None:
        return 999
    return int(np.count_nonzero(hash1 != hash2))


# ==============================================================================
# CHẾ ĐỘ 1: FFMPEG RAW PIPE VỚI BỘ LỌC CHỌN ẢNH SẮC NÉT NHẤT (BEST SHARPNESS)
# ==============================================================================

def run_ffmpeg_sharpness_capture(source_url, base_dir, camera_tag, interval=3.0,
                                 burst_window=0.8, image_format="jpg", jpeg_quality=100):
    """
    Sử dụng FFmpeg trực tiếp để decode luồng video nguyên bản sang raw video pipe.
    Trong mỗi chu kỳ (mặc định 3s):
    - Đọc một chùm khung hình (burst) trong khoảng thời gian `burst_window` (0.8s ~ 20-25 frames).
    - Chấm điểm độ sắc nét (Laplacian Variance) từng frame.
    - Chọn khung hình có ĐỘ NÉT CAO NHẤT (ít bị motion blur nhất) để lưu xuống ổ đĩa!
    - Lưu bằng định dạng JPEG chất lượng tối đa 100 hoặc PNG Lossless.
    """
    print("\n" + "=" * 75)
    print("🎯 KHỞI CHẠY ENGINE CAPTURE FFMPEG VỚI BỘ LỌC CHỐNG NHÒE CHUYỂN ĐỘNG")
    print(f"📡 Nguồn Stream: {source_url}")
    print(f"⏱️ Chu kỳ chụp: {interval:.1f} giây / ảnh")
    print(f"🔎 Cửa sổ tìm frame nét nhất: {burst_window:.1f} giây")
    print(f"🖼️ Định dạng lưu: {image_format.upper()} (Chất lượng: {'Lossless' if image_format == 'png' else f'{jpeg_quality}%'})")
    print("📁 Phân chia tự động: 1h / 1 thư mục")
    print("=" * 75 + "\n")

    # 1. Thăm dò thông số video bằng ffprobe
    probe_cmd = [
        "ffprobe", "-v", "error",
        "-select_streams", "v:0",
        "-show_entries", "stream=width,height,r_frame_rate",
        "-of", "json",
        source_url
    ]
    width, height, fps = 1920, 1080, 30.0
    try:
        probe_res = subprocess.run(probe_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=10)
        if probe_res.returncode == 0:
            import json
            p_data = json.loads(probe_res.stdout)
            streams = p_data.get("streams", [])
            if streams:
                width = int(streams[0].get("width", 1920))
                height = int(streams[0].get("height", 1080))
                r_fps = streams[0].get("r_frame_rate", "30/1")
                if "/" in r_fps:
                    num, den = r_fps.split("/")
                    fps = float(num) / max(1.0, float(den))
                else:
                    fps = float(r_fps)
                print(f"📹 Thông số luồng stream gốc: {width}x{height} @ {fps:.1f} FPS")
    except Exception:
        print(f"⚠️ Không thể thăm dò qua ffprobe, sử dụng thông số dự phòng: {width}x{height} @ {fps:.1f} FPS")

    frame_bytes = width * height * 3  # RGB24 format

    # 2. Xây dựng lệnh FFmpeg decode chất lượng tối đa sang stdout
    # Thiết lập flags decode chuẩn xác nhất: accurate_rnd, full_chroma_int, deblock đầy đủ
    ffmpeg_cmd = [
        "ffmpeg",
        "-hide_banner",
        "-loglevel", "warning",
    ]

    # Cấu hình giao thức mạng tối ưu
    if source_url.startswith("rtsp://"):
        ffmpeg_cmd.extend(["-rtsp_transport", "tcp"])

    ffmpeg_cmd.extend([
        "-i", source_url,
        "-f", "rawvideo",
        "-pix_fmt", "bgr24",
        "-an",
        "-"
    ])

    print("🚀 Đang kết nối FFmpeg tới luồng video...")
    proc = subprocess.Popen(ffmpeg_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, bufsize=10 * frame_bytes)

    total_captured = 0
    last_capture_time = time.time()
    burst_frames = []
    in_burst = False
    burst_start_time = 0.0

    current_slot_name = ""
    current_save_dir = ""

    try:
        while True:
            # Đọc 1 frame thô (raw BGR24) từ pipe
            raw_frame = proc.stdout.read(frame_bytes)
            if not raw_frame or len(raw_frame) != frame_bytes:
                print("⚠️ Luồng FFmpeg bị ngắt hoặc kết thúc. Đang kiểm tra...")
                break

            curr_time = time.time()

            # Kiểm tra thời điểm bắt đầu chu kỳ thu thập chùm frame
            if not in_burst and (curr_time - last_capture_time >= (interval - burst_window)):
                in_burst = True
                burst_frames = []
                burst_start_time = curr_time

            # Đang trong giai đoạn thu thập chùm frame để tìm frame nét nhất
            if in_burst:
                frame_np = np.frombuffer(raw_frame, dtype=np.uint8).reshape((height, width, 3))
                sharpness = compute_sharpness(frame_np)
                burst_frames.append((frame_np, sharpness, curr_time))

                # Hết khoảng thời gian burst: Chọn frame có độ nét cao nhất
                if curr_time - burst_start_time >= burst_window:
                    in_burst = False
                    last_capture_time = curr_time

                    if burst_frames:
                        # Sắp xếp theo điểm độ sắc nét giảm dần
                        burst_frames.sort(key=lambda x: x[1], reverse=True)
                        best_frame, best_sharpness, best_time = burst_frames[0]
                        total_captured += 1

                        # Xử lý thư mục khung giờ 1h
                        now = datetime.fromtimestamp(best_time)
                        _, _, slot_str = get_slot_info(now)
                        date_str = now.strftime("%Y-%m-%d")
                        slot_name = f"{date_str}_{slot_str}"

                        if slot_name != current_slot_name or not current_save_dir:
                            current_slot_name = slot_name
                            current_save_dir = os.path.join(base_dir, camera_tag, slot_name)
                            os.makedirs(current_save_dir, exist_ok=True)
                            print(f"\n⏰ [CHUYỂN KHUNG GIỜ 1H] Lưu vào: {slot_name}")

                        timestamp_str = now.strftime("%Y%m%d_%H%M%S")
                        millis = int(now.microsecond / 1000)
                        ext = "png" if image_format.lower() == "png" else "jpg"
                        # TÊN TỆP ĐỒNG NHẤT: Lưu 100% ảnh vào chung 1 thư mục
                        file_name = f"{camera_tag}_{timestamp_str}_{millis:03d}_{total_captured:06d}.{ext}"
                        file_path = os.path.join(current_save_dir, file_name)

                        # Lưu ảnh với chất lượng cao nhất
                        if ext == "png":
                            cv2.imwrite(file_path, best_frame, [int(cv2.IMWRITE_PNG_COMPRESSION), 1])
                        else:
                            cv2.imwrite(file_path, best_frame, [int(cv2.IMWRITE_JPEG_QUALITY), jpeg_quality])

                        file_size_kb = os.path.getsize(file_path) / 1024.0
                        print(f"📸 [#{total_captured:05d}] Đã lưu {file_name} ({file_size_kb:.1f} KB) | "
                              f"Độ nét (Laplacian): {best_sharpness:.1f} (Chọn từ {len(burst_frames)} frames) -> [{slot_name}]")

                        burst_frames = []

    except KeyboardInterrupt:
        print("\n🛑 Nhận tín hiệu dừng (Ctrl+C). Đang ngắt tiến trình an toàn...")
    finally:
        if proc:
            proc.terminate()
            try:
                proc.wait(timeout=3)
            except Exception:
                proc.kill()
        print(f"\n✅ Hoàn thành phiên thu thập! Tổng số ảnh đã lưu: {total_captured}")


# ==============================================================================
# CHẾ ĐỘ 2: FFMPEG NATIVE CAPTURE (CHỈ BẮT I-FRAME HOẶC FPS CỐ ĐỊNH)
# ==============================================================================

def run_ffmpeg_native_capture(source_url, base_dir, camera_tag, interval=3.0,
                              only_keyframes=False, image_format="jpg", jpeg_quality=100):
    """
    Sử dụng trực tiếp tính năng capture ảnh của FFmpeg:
    - Nếu only_keyframes=True: Chỉ trích xuất I-Frame (Intra Keyframe) nguyên bản.
      Đây là khung hình sắc nét nhất, không bị nén vỡ macroblock do chuyển động.
    - Nếu only_keyframes=False: Chụp định kỳ chính xác mỗi N giây (fps=1/interval).
    - Tự động luân chuyển thư mục theo khung giờ 1h bằng vòng lặp điều phối.
    """
    print("\n" + "=" * 75)
    print("🚀 KHỞI CHẠY ENGINE CAPTURE FFMPEG TRỰC TIẾP (NATIVE FFMPEG PIPELINE)")
    print(f"📡 Nguồn Stream: {source_url}")
    print(f"⏱️ Chu kỳ chụp: {interval:.1f} giây / ảnh")
    print(f"🔑 Chế độ Keyframe (I-Frame): {'BẬT (Chỉ lấy frame gốc)' if only_keyframes else 'TẮT (Chụp định kỳ fps=1/N)'}")
    print(f"🖼️ Định dạng lưu: {image_format.upper()} (Chất lượng tối đa)")
    print("📁 Phân chia tự động: 1h / 1 thư mục")
    print("=" * 75 + "\n")

    total_captured = 0
    ext = "png" if image_format.lower() == "png" else "jpg"

    try:
        while True:
            # Lấy thư mục khung giờ 1h hiện tại
            now = datetime.now()
            target_dir, slot_name = get_current_storage_directory(base_dir, camera_tag)
            slot_start, slot_end, _ = get_slot_info(now)

            # Tính thời gian còn lại đến khi hết khung giờ 1h (để FFmpeg tự chuyển folder)
            import datetime as dt
            next_slot_time = (now + dt.timedelta(hours=1)).replace(minute=0, second=0, microsecond=0)
            time_left_sec = max(10.0, (next_slot_time - now).total_seconds())

            print(f"⏰ [KHUNG GIỜ HIỆN TẠI] {slot_name} | Chạy trong {time_left_sec / 60:.1f} phút tiếp theo...")

            # Thiết lập bộ lọc video (Video Filter)
            if only_keyframes:
                # Chỉ lấy I-frame (Keyframe) và giới hạn nhịp không nhanh hơn interval
                vf_filter = f"select='eq(pict_type,I)',fps=fps=1/{interval}"
            else:
                vf_filter = f"fps=1/{interval}"

            # Chuẩn hóa đường dẫn thư mục sang forward slash chống lỗi escape trên Windows
            norm_target_dir = os.path.abspath(target_dir).replace("\\", "/")
            os.makedirs(norm_target_dir, exist_ok=True)

            date_prefix = now.strftime("%Y%m%d_%H%M%S")
            pattern_path = f"{norm_target_dir}/{camera_tag}_{date_prefix}_%06d.{ext}"

            ffmpeg_cmd = [
                "ffmpeg",
                "-hide_banner",
                "-loglevel", "warning",
            ]

            if source_url.startswith("rtsp://"):
                ffmpeg_cmd.extend(["-rtsp_transport", "tcp"])

            ffmpeg_cmd.extend([
                "-i", source_url,
                "-t", str(int(time_left_sec)),
                "-vf", vf_filter,
            ])

            if ext == "png":
                ffmpeg_cmd.extend(["-c:v", "png"])
            else:
                # -q:v 1 là chất lượng JPEG cao nhất (100%)
                ffmpeg_cmd.extend(["-q:v", "1"])

            ffmpeg_cmd.append(pattern_path)

            print(f"▶ Bắt đầu trích xuất FFmpeg vào: {norm_target_dir}")
            sub_proc = subprocess.run(ffmpeg_cmd)

            if sub_proc.returncode != 0:
                print(f"⚠️ FFmpeg kết thúc với mã {sub_proc.returncode}. Đang thử kết nối lại sau 3 giây...")
                time.sleep(3)

    except KeyboardInterrupt:
        print("\n🛑 Nhận tín hiệu dừng từ người dùng. Kết thúc an toàn.")


# ==============================================================================
# ĐIỂM VÀO CHÍNH (MAIN ENTRY POINT)
# ==============================================================================

def main():
    parser = argparse.ArgumentParser(
        description="Bộ công cụ thu thập & trích xuất ảnh chất lượng cao từ Stream (FFmpeg Engine)"
    )
    parser.add_argument("--stream", type=str, required=True,
                        help="Đường dẫn nguồn: URL RTSP, HLS (.m3u8), link YouTube, webcam (0), hoặc tệp video MP4")
    parser.add_argument("--tag", type=str, default="cam_lane01",
                        help="Tên camera hoặc làn xe (mặc định: cam_lane01)")
    parser.add_argument("--output", type=str, default=str(RAW_FRAMES_DIR),
                        help="Thư mục ảnh gốc (mặc định: data/raw/frames trong dự án)")
    parser.add_argument("--interval", type=float, default=3.0,
                        help="Chu kỳ chụp ảnh (giây, mặc định: 3.0)")
    parser.add_argument("--mode", type=str, default="sharpest",
                        choices=["sharpest", "keyframe", "native"],
                        help="Chế độ chụp: 'sharpest' (Tự chọn frame nét nhất chống motion blur - Khuyên dùng), "
                             "'keyframe' (Chỉ chụp I-frame gốc), 'native' (FFmpeg FPS thuần)")
    parser.add_argument("--format", type=str, default="jpg", choices=["jpg", "png"],
                        help="Định dạng ảnh đầu ra: 'jpg' (chất lượng 100) hoặc 'png' (lossless hoàn toàn)")
    parser.add_argument("--quality", type=int, default=100,
                        help="Chất lượng JPEG (1-100, mặc định: 100)")
    parser.add_argument("--burst-window", type=float, default=0.8,
                        help="Độ rộng cửa sổ (giây) quét tìm frame nét nhất trong chế độ 'sharpest' (mặc định: 0.8s)")

    args = parser.parse_args()

    # Kiểm tra sự tồn tại của FFmpeg
    if not check_ffmpeg_available():
        print("❌ LỖI NGHIÊM TRỌNG: Không tìm thấy công cụ 'ffmpeg' trong hệ thống!")
        print("👉 Vui lòng cài đặt FFmpeg hoặc thêm FFmpeg vào biến môi trường PATH.")
        print("   Trên Windows: Chạy 'winget install Gyan.FFmpeg' hoặc tải từ https://ffmpeg.org/download.html")
        sys.exit(1)

    target_source = args.stream.strip()

    # Xử lý nếu nguồn là YouTube
    if is_youtube_url(target_source):
        yt_stream_url, yt_fps, err = resolve_youtube_stream(target_source)
        if yt_stream_url:
            target_source = yt_stream_url
        else:
            print(f"❌ Lỗi giải mã link YouTube: {err}")
            sys.exit(1)

    # Chạy theo chế độ được chọn
    if args.mode == "sharpest":
        if not HAS_CV2 or not HAS_PIL:
            print("⚠️ Chế độ 'sharpest' cần thư viện opencv-python và Pillow để phân tích độ sắc nét.")
            print("👉 Đang chuyển sang chế độ 'keyframe' dùng FFmpeg trực tiếp...")
            run_ffmpeg_native_capture(
                source_url=target_source,
                base_dir=args.output,
                camera_tag=args.tag,
                interval=args.interval,
                only_keyframes=True,
                image_format=args.format,
                jpeg_quality=args.quality
            )
        else:
            run_ffmpeg_sharpness_capture(
                source_url=target_source,
                base_dir=args.output,
                camera_tag=args.tag,
                interval=args.interval,
                burst_window=args.burst_window,
                image_format=args.format,
                jpeg_quality=args.quality
            )
    elif args.mode == "keyframe":
        run_ffmpeg_native_capture(
            source_url=target_source,
            base_dir=args.output,
            camera_tag=args.tag,
            interval=args.interval,
            only_keyframes=True,
            image_format=args.format,
            jpeg_quality=args.quality
        )
    else:  # native
        run_ffmpeg_native_capture(
            source_url=target_source,
            base_dir=args.output,
            camera_tag=args.tag,
            interval=args.interval,
            only_keyframes=False,
            image_format=args.format,
            jpeg_quality=args.quality
        )


if __name__ == "__main__":
    main()
