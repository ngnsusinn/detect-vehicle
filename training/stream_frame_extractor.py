#!/usr/bin/env python3
"""
CÔNG CỤ THU THẬP & TRÍCH XUẤT KHUNG HÌNH THỰC TẾ TỪ LUỒNG VIDEO STREAMING
(REAL-WORLD STREAMING FRAME EXTRACTOR & DIVERSITY SAMPLER)
Cam kết: 100% dữ liệu huấn luyện được trích xuất trực tiếp từ camera thực tế (RTSP, HLS, WebRTC),
hoàn toàn KHÔNG sử dụng bất kỳ dữ liệu ảo hay dữ liệu sinh nhân tạo nào.
"""

import os
import sys
import time
import argparse
import json
import math
import shutil
from datetime import datetime

# Đảm bảo xuất Unicode an toàn trên mọi terminal
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')


class StreamFrameExtractor:
    """
    Trích xuất tự động các khung hình có chuyển động phương tiện từ luồng streaming thực tế,
    lọc trùng lặp bằng pHash để đảm bảo độ đa dạng cao nhất cho dữ liệu gán nhãn.
    """
    def __init__(self, stream_url, output_dir, session_tag="traffic", min_motion_area=1500, phash_diff_threshold=6):
        try:
            import cv2
            import numpy as np
        except ImportError:
            print("❌ LỖI: Vui lòng cài đặt opencv-python và numpy để thu thập luồng streaming:")
            print("👉 Chạy lệnh: pip install opencv-python numpy")
            sys.exit(1)

        self.cv2 = cv2
        self.np = np
        self.stream_url = stream_url
        self.output_dir = output_dir
        self.session_tag = session_tag
        self.min_motion_area = min_motion_area
        self.phash_diff_threshold = phash_diff_threshold
        
        self.images_dir = os.path.join(output_dir, "raw_frames", session_tag)
        os.makedirs(self.images_dir, exist_ok=True)
        
        self.log_file = os.path.join(output_dir, f"capture_manifest_{session_tag}.jsonl")
        self.fgbg = cv2.createBackgroundSubtractorMOG2(history=300, varThreshold=32, detectShadows=False)
        self.last_saved_hash = None
        self.saved_count = 0
        self.total_frames_processed = 0

    def calculate_phash(self, image):
        """Tính mã băm cảm nhận (Perceptual Hash) 64-bit đơn giản bằng DCT"""
        resized = self.cv2.resize(image, (32, 32), interpolation=self.cv2.INTER_AREA)
        gray = self.cv2.cvtColor(resized, self.cv2.COLOR_BGR2GRAY)
        dct = self.cv2.dct(self.np.float32(gray))
        dct_low = dct[:8, :8]
        avg = (self.np.sum(dct_low) - dct_low[0, 0]) / 63.0
        phash_bits = (dct_low > avg).flatten()
        return phash_bits

    def hamming_distance(self, hash1, hash2):
        """Tính khoảng cách Hamming giữa 2 mã băm pHash"""
        if hash1 is None or hash2 is None:
            return 999
        return int(self.np.count_nonzero(hash1 != hash2))

    def run(self, max_frames=2000, max_duration_sec=3600):
        print(f"\n🚀 Bắt đầu kết nối tới luồng camera thực tế: {self.stream_url}")
        print(f"📁 Thư mục lưu khung hình: {self.images_dir}")
        print(f"🎯 Chỉ tiêu trích xuất: Tối đa {max_frames} khung hình thực tế...")

        cap = self.cv2.VideoCapture(self.stream_url)
        if not cap.isOpened():
            print(f"❌ LỖI: Không thể mở luồng video tại địa chỉ: {self.stream_url}")
            return

        start_time = time.time()
        last_save_time = 0

        with open(self.log_file, "a", encoding="utf-8") as f_log:
            while True:
                ret, frame = cap.read()
                if not ret:
                    print("⚠️ Mất tín hiệu luồng stream. Đang thử kết nối lại sau 2 giây...")
                    time.sleep(2)
                    cap.release()
                    cap = self.cv2.VideoCapture(self.stream_url)
                    continue

                self.total_frames_processed += 1
                curr_time = time.time()

                # Kiểm tra giới hạn thời gian chạy
                if (curr_time - start_time) > max_duration_sec or self.saved_count >= max_frames:
                    print(f"\n✅ Hoàn thành phiên trích xuất: Đã thu thập {self.saved_count} khung hình thực tế.")
                    break

                # 1. Phát hiện chuyển động (Motion Detection)
                # Thu nhỏ ảnh tạm để tăng tốc độ phân tích chuyển động
                h, w = frame.shape[:2]
                small_frame = self.cv2.resize(frame, (640, int(640 * h / w)))
                fgmask = self.fgbg.apply(small_frame)
                
                # Khử nhiễu mask chuyển động
                kernel = self.cv2.getStructuringElement(self.cv2.MORPH_RECT, (5, 5))
                fgmask = self.cv2.morphologyEx(fgmask, self.cv2.MORPH_OPEN, kernel)
                
                motion_pixels = self.cv2.countNonZero(fgmask)

                # Chỉ xem xét lưu nếu có diện tích chuyển động đáng kể (xe đang di chuyển vào làn)
                if motion_pixels > self.min_motion_area:
                    # Giới hạn tốc độ chụp: tối đa 3 ảnh/giây để tránh chụp liên tiếp cùng 1 góc xe
                    if (curr_time - last_save_time) >= 0.35:
                        curr_phash = self.calculate_phash(small_frame)
                        h_dist = self.hamming_distance(curr_phash, self.last_saved_hash)

                        # 2. Bộ lọc độ đa dạng (Diversity Filter)
                        # Chỉ lưu nếu khung hình khác biệt so với khung hình vừa lưu trước đó
                        if h_dist >= self.phash_diff_threshold:
                            self.saved_count += 1
                            timestamp_str = datetime.now().strftime("%Y%m%d_%H%M%S_%f")[:19]
                            file_name = f"real_{self.session_tag}_{self.saved_count:06d}_{timestamp_str}.jpg"
                            save_path = os.path.join(self.images_dir, file_name)

                            # Lưu khung hình thực tế ở độ phân giải gốc chất lượng cao
                            self.cv2.imwrite(save_path, frame, [int(self.cv2.IMWRITE_JPEG_QUALITY), 95])
                            self.last_saved_hash = curr_phash
                            last_save_time = curr_time

                            # Ghi nhật ký nguồn gốc khung hình
                            manifest_record = {
                                "file_name": file_name,
                                "source_stream": self.stream_url,
                                "timestamp": datetime.now().isoformat(),
                                "resolution": f"{w}x{h}",
                                "motion_score": int(motion_pixels),
                                "phash_distance": int(h_dist)
                            }
                            f_log.write(json.dumps(manifest_record, ensure_ascii=False) + "\n")
                            f_log.flush()

                            if self.saved_count % 50 == 0 or self.saved_count == max_frames:
                                print(f"  -> Đã thu thập {self.saved_count}/{max_frames} ảnh thực tế hợp lệ (Đã xử lý {self.total_frames_processed} frames)...")

        cap.release()
        print(f"\n📄 Tệp nhật ký thu thập: {self.log_file}")


def split_for_workstations(raw_dir, output_batches_dir, num_machines=4):
    """
    Chia đều dữ liệu ảnh thực tế đã thu thập thành các gói cho các máy con gán nhãn
    """
    os.makedirs(output_batches_dir, exist_ok=True)
    all_files = [f for f in os.listdir(raw_dir) if f.lower().endswith(('.jpg', '.jpeg', '.png'))]
    all_files.sort()
    
    total = len(all_files)
    if total == 0:
        print(f"Không tìm thấy ảnh nào trong thư mục {raw_dir}")
        return

    print(f"\n📦 Bắt đầu phân chia {total} ảnh thực tế cho {num_machines} máy con gán nhãn...")
    batch_size = math.ceil(total / num_machines)

    for m in range(num_machines):
        start_idx = m * batch_size
        end_idx = min(start_idx + batch_size, total)
        machine_files = all_files[start_idx:end_idx]

        machine_dir = os.path.join(output_batches_dir, f"may_con_{m+1:02d}")
        os.makedirs(machine_dir, exist_ok=True)

        for fn in machine_files:
            shutil.copy(os.path.join(raw_dir, fn), os.path.join(machine_dir, fn))
            
        print(f"  -> Máy con {m+1}: Nhận {len(machine_files)} ảnh tại thư mục: {machine_dir}")

    print("✅ Đã chia gói hoàn tất! Bạn có thể chép các thư mục máy con sang các trạm làm việc.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Thu thập khung hình thực tế từ luồng video streaming camera")
    parser.add_argument("--stream", type=str, required=True, help="URL luồng streaming camera (RTSP, HLS .m3u8, WebRTC, hoặc tệp MP4 camera ghi lại)")
    parser.add_argument("--output", type=str, default="./real_stream_dataset", help="Thư mục lưu trữ ảnh thực tế")
    parser.add_argument("--tag", type=str, default="lane_01", help="Thẻ phân biệt làn xe/camera (ví dụ: lane_day, lane_night, cam_toll_01)")
    parser.add_argument("--max-frames", type=int, default=1000, help="Số khung hình thực tế tối đa cần thu thập trong phiên")
    parser.add_argument("--split-machines", type=int, default=0, help="Số lượng máy con muốn chia nhỏ dữ liệu sau khi thu thập (nếu > 0)")
    args = parser.parse_args()

    extractor = StreamFrameExtractor(
        stream_url=args.stream,
        output_dir=args.output,
        session_tag=args.tag
    )
    extractor.run(max_frames=args.max_frames)

    if args.split_machines > 0:
        split_for_workstations(
            raw_dir=extractor.images_dir,
            output_batches_dir=os.path.join(args.output, "workstation_batches"),
            num_machines=args.split_machines
        )
