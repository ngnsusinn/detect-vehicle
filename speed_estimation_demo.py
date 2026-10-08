#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
HỆ THỐNG DEMO ĐẾM VÀ ĐO TỐC ĐỘ PHƯƠNG TIỆN GIAO THÔNG (ITS 2026)
------------------------------------------------------------------
Thuật toán cốt lõi:
1. Phát hiện & Phân loại phương tiện: YOLOv11 / YOLOv8 (8 lớp giao thông VN)
2. Bám vết đa đối tượng: ByteTrack (persist=True)
3. Điểm neo tọa độ: Điểm giữa đáy bounding box (Bottom-Center: tiếp xúc mặt đường)
4. Đo tốc độ: Ma trận biến đổi phối cảnh Homography Matrix (H)
   v = (d / dt) * 3.6 (km/h) với bộ lọc EMA làm mượt vận tốc
5. Đếm xe: Line-Crossing qua vạch ảo theo từng chiều (IN / OUT) và theo loại xe
6. Bắt lỗi quá tốc độ: Cảnh báo xe vượt ngưỡng quy định
"""

import sys
import argparse
from collections import defaultdict, deque
import numpy as np
import cv2

# Đảm bảo in tiếng Việt UTF-8
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

try:
    from ultralytics import YOLO
except ImportError:
    print("❌ LỖI: Thư viện ultralytics chưa được cài đặt.")
    print("👉 Hãy chạy: pip install ultralytics")
    sys.exit(1)


# Danh mục 8 lớp phương tiện giao thông Việt Nam
VEHICLE_CLASSES = {
    0: "motorcycle",
    1: "car",
    2: "electric_bicycle",
    3: "bicycle",
    4: "bus",
    5: "truck",
    6: "container_truck",
    7: "special_vehicle"
}

# Tên hiển thị tiếng Việt
CLASS_NAMES_VI = {
    "motorcycle": "Xe máy",
    "car": "Ô tô con",
    "electric_bicycle": "Xe đạp điện",
    "bicycle": "Xe đạp",
    "bus": "Xe khách/buýt",
    "truck": "Xe tải",
    "container_truck": "Xe container",
    "special_vehicle": "Xe chuyên dụng"
}


class HomographySpeedEstimator:
    """
    Module tính toán tốc độ phương tiện bằng ma trận phối cảnh Homography (H).
    Chuyển đổi từ tọa độ ảnh (Pixel) sang tọa độ mặt đường thực địa (Mét).
    """
    def __init__(self, src_pts, dst_pts, fps=30.0, speed_limit_kmh=60.0, ema_alpha=0.35, window_frames=6):
        """
        :param src_pts: 4 điểm trên mặt đường trong ảnh camera [(x1,y1), (x2,y2), (x3,y3), (x4,y4)]
        :param dst_pts: 4 điểm tọa độ thực tế tương ứng (Mét) [(0,0), (W,0), (W,L), (0,L)]
        :param fps: Tốc độ khung hình của video stream
        :param speed_limit_kmh: Giới hạn tốc độ cảnh báo (km/h)
        :param ema_alpha: Hệ số làm mượt vận tốc EMA (0 < alpha <= 1)
        :param window_frames: Khoảng cách frame để tính vận tốc tức thời (giảm sai số vi phân)
        """
        self.fps = fps
        self.speed_limit_kmh = speed_limit_kmh
        self.ema_alpha = ema_alpha
        self.window_frames = window_frames

        # Tính ma trận Homography 3x3
        src = np.array(src_pts, dtype=np.float32)
        dst = np.array(dst_pts, dtype=np.float32)
        self.H, _ = cv2.findHomography(src, dst)

        # Lưu trữ lịch sử vị trí thực tế và vận tốc của từng xe: track_id -> deque
        self.track_history = defaultdict(lambda: deque(maxlen=30))
        self.smoothed_speeds = {}

    def pixel_to_world(self, px, py):
        """Chuyển đổi 1 điểm (px, py) trong ảnh sang tọa độ thế giới thực (X, Y) mét."""
        if self.H is None:
            return 0.0, 0.0
        pt = np.array([[[px, py]]], dtype=np.float32)
        transformed = cv2.perspectiveTransform(pt, self.H)
        return float(transformed[0][0][0]), float(transformed[0][0][1])

    def update(self, track_id, bottom_center_pt, frame_idx):
        """
        Cập nhật vị trí và tính vận tốc của phương tiện track_id.
        :return: (speed_kmh, is_overspeed)
        """
        px, py = bottom_center_pt
        world_x, world_y = self.pixel_to_world(px, py)

        # Lưu vào lịch sử: (frame_idx, world_x, world_y, px, py)
        self.track_history[track_id].append((frame_idx, world_x, world_y, px, py))

        history = self.track_history[track_id]
        if len(history) < self.window_frames:
            # Chưa đủ số frame để tính vận tốc
            current_speed = self.smoothed_speeds.get(track_id, 0.0)
            return current_speed, current_speed > self.speed_limit_kmh

        # Lấy điểm trước đó k frames
        prev_idx, prev_x, prev_y, _, _ = history[-self.window_frames]
        delta_f = frame_idx - prev_idx
        if delta_f <= 0:
            current_speed = self.smoothed_speeds.get(track_id, 0.0)
            return current_speed, current_speed > self.speed_limit_kmh

        # Tính khoảng cách thực tế di chuyển (mét)
        distance_m = np.sqrt((world_x - prev_x)**2 + (world_y - prev_y)**2)
        delta_t = delta_f / self.fps  # giây

        if delta_t > 0:
            raw_speed_kmh = (distance_m / delta_t) * 3.6  # km/h
        else:
            raw_speed_kmh = 0.0

        # Lọc bỏ giá trị ngoại lai bất thường (outlier: v > 180 km/h do track giật)
        if raw_speed_kmh > 180.0:
            raw_speed_kmh = self.smoothed_speeds.get(track_id, 0.0)

        # Làm mượt bằng Exponential Moving Average (EMA)
        if track_id in self.smoothed_speeds:
            smoothed = self.ema_alpha * raw_speed_kmh + (1 - self.ema_alpha) * self.smoothed_speeds[track_id]
        else:
            smoothed = raw_speed_kmh

        self.smoothed_speeds[track_id] = smoothed
        is_overspeed = smoothed > self.speed_limit_kmh

        return smoothed, is_overspeed


class LineCrossingCounter:
    """
    Module đếm xe qua vạch ảo (Virtual Tripwire Line).
    Hỗ trợ đếm theo hướng (IN / OUT) và theo từng chủng loại phương tiện.
    """
    def __init__(self, line_pt1, line_pt2):
        self.p1 = np.array(line_pt1, dtype=np.float32)
        self.p2 = np.array(line_pt2, dtype=np.float32)
        self.counted_ids = set()
        self.prev_positions = {}

        # Thống kê số lượng
        self.total_in = 0
        self.total_out = 0
        self.class_counts = defaultdict(int)

    def _side(self, pt):
        """Tính hướng của điểm pt so với đường thẳng p1-p2 bằng tích có hướng."""
        return (self.p2[0] - self.p1[0]) * (pt[1] - self.p1[1]) - (self.p2[1] - self.p1[1]) * (pt[0] - self.p1[0])

    def _intersect(self, a, b, c, d):
        """Kiểm tra 2 đoạn thẳng ab và cd có cắt nhau không."""
        def ccw(p, q, r):
            return (r[1] - p[1]) * (q[0] - p[0]) > (q[1] - p[1]) * (r[0] - p[0])
        return (ccw(a, c, d) != ccw(b, c, d)) and (ccw(a, b, c) != ccw(a, b, d))

    def update(self, track_id, current_pt, cls_name):
        """
        Cập nhật vị trí và phát hiện cắt vạch.
        :return: 'IN', 'OUT' hoặc None
        """
        if track_id in self.counted_ids:
            return None

        prev_pt = self.prev_positions.get(track_id)
        self.prev_positions[track_id] = current_pt

        if prev_pt is None:
            return None

        # Kiểm tra cắt vạch
        if self._intersect(prev_pt, current_pt, self.p1, self.p2):
            side_prev = self._side(prev_pt)
            side_curr = self._side(current_pt)

            if side_prev < 0 and side_curr >= 0:
                direction = "IN"
                self.total_in += 1
            else:
                direction = "OUT"
                self.total_out += 1

            self.counted_ids.add(track_id)
            self.class_counts[cls_name] += 1
            return direction

        return None


def run_pipeline(video_source, model_path="yolo11n.pt", speed_limit=60.0, output_path=None):
    """Vòng lặp chính xử lý video streaming / video file."""
    print(f"🚀 Đang khởi tạo mô hình AI: {model_path}...")
    model = YOLO(model_path)

    cap = cv2.VideoCapture(video_source)
    if not cap.isOpened():
        print(f"❌ Không thể mở nguồn video: {video_source}")
        return

    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    print(f"📹 Video: {width}x{height} @ {fps:.1f} FPS")

    # 1. Cấu hình 4 điểm mặt đường (Pixels) cho góc camera mẫu
    # Người dùng có thể điều chỉnh 4 tọa độ này tương ứng với mặt đường thực tế
    src_polygon = [
        (int(width * 0.35), int(height * 0.45)),  # Top-Left (Xa)
        (int(width * 0.65), int(height * 0.45)),  # Top-Right (Xa)
        (int(width * 0.90), int(height * 0.90)),  # Bottom-Right (Gần)
        (int(width * 0.10), int(height * 0.90))   # Bottom-Left (Gần)
    ]
    # Kích thước thực tế: Đoạn đường rộng 8m, dài 25m
    dst_rect = [
        (0.0, 0.0),
        (8.0, 0.0),
        (8.0, 25.0),
        (0.0, 25.0)
    ]

    speed_estimator = HomographySpeedEstimator(
        src_pts=src_polygon,
        dst_pts=dst_rect,
        fps=fps,
        speed_limit_kmh=speed_limit
    )

    # 2. Cấu hình vạch đếm ảo (Virtual Line) ngang qua làn đường
    line_p1 = (int(width * 0.15), int(height * 0.70))
    line_p2 = (int(width * 0.85), int(height * 0.70))
    counter = LineCrossingCounter(line_p1, line_p2)

    writer = None
    if output_path:
        fourcc = cv2.VideoWriter_fourcc(*'mp4v')
        writer = cv2.VideoWriter(output_path, fourcc, fps, (width, height))

    frame_idx = 0
    print("▶ Bắt đầu xử lý luồng bám vết, đếm xe và đo tốc độ... (Bấm 'Q' để thoát)")

    while cap.isOpened():
        ret, frame = cap.read()
        if not ret:
            break
        frame_idx += 1

        # 1. Bám vết đa đối tượng bằng YOLOv11 + ByteTrack
        results = model.track(frame, persist=True, tracker="bytetrack.yaml", verbose=False)

        # 2. Vẽ vùng hiệu chuẩn đo tốc độ (ROI Polygon)
        pts_poly = np.array(src_polygon, np.int32).reshape((-1, 1, 2))
        cv2.polylines(frame, [pts_poly], isClosed=True, color=(255, 200, 0), thickness=2)

        # 3. Vẽ vạch đếm xe
        cv2.line(frame, line_p1, line_p2, (0, 165, 255), 3)
        cv2.putText(frame, "VACH DEM XE (COUNT LINE)", (line_p1[0], line_p1[1] - 8),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 165, 255), 2)

        if results and results[0].boxes and results[0].boxes.id is not None:
            boxes = results[0].boxes.xyxy.cpu().numpy()
            track_ids = results[0].boxes.id.int().cpu().numpy()
            clss = results[0].boxes.cls.int().cpu().numpy()
            confs = results[0].boxes.conf.cpu().numpy()

            for box, track_id, cls_id, conf in zip(boxes, track_ids, clss, confs):
                x1, y1, x2, y2 = box.astype(int)
                # Tọa độ đáy bánh xe tiếp xúc mặt đường (Bottom-Center)
                bx = int((x1 + x2) / 2)
                by = int(y2)

                cls_name = model.names.get(cls_id, f"class_{cls_id}")
                vi_name = CLASS_NAMES_VI.get(cls_name, cls_name)

                # Cập nhật đo tốc độ
                speed, is_overspeed = speed_estimator.update(track_id, (bx, by), frame_idx)

                # Cập nhật đếm xe qua vạch
                counter.update(track_id, (bx, by), cls_name)

                # Màu sắc: Đỏ rực nếu chạy quá tốc độ, Xanh lá nếu tốc độ an toàn
                color = (0, 0, 255) if is_overspeed else (0, 255, 0)

                # Vẽ bounding box và điểm đáy bánh xe
                cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)
                cv2.circle(frame, (bx, by), 5, (0, 255, 255), -1)

                # Nhãn hiển thị: ID | Loại xe | Tốc độ
                speed_str = f"{speed:.1f} km/h" if speed > 3.0 else "Calculating..."
                label = f"ID:{track_id} {vi_name} | {speed_str}"
                if is_overspeed:
                    label += " [QUA TOC DO!]"

                (w_label, h_label), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 2)
                cv2.rectangle(frame, (x1, y1 - 22), (x1 + w_label, y1), color, -1)
                cv2.putText(frame, label, (x1, y1 - 5), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 0), 2)

        # 4. Vẽ bảng thống kê lưu lượng (Dashboard Overlay)
        overlay = frame.copy()
        cv2.rectangle(overlay, (20, 20), (380, 220), (20, 20, 30), -1)
        cv2.addWeighted(overlay, 0.75, frame, 0.25, 0, frame)

        cv2.putText(frame, "HE THONG DEM & DO TOC DO XE ITS", (35, 45),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 255), 2)
        cv2.putText(frame, f"Tong xe IN  (Vao): {counter.total_in}", (35, 80),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.55, (255, 255, 255), 1)
        cv2.putText(frame, f"Tong xe OUT (Ra) : {counter.total_out}", (35, 105),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.55, (255, 255, 255), 1)
        cv2.putText(frame, f"Gioi han toc do  : {speed_limit} km/h", (35, 130),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0, 200, 255), 1)

        # Thống kê chi tiết loại xe
        y_offset = 160
        for cname, cnt in list(counter.class_counts.items())[:3]:
            vn = CLASS_NAMES_VI.get(cname, cname)
            cv2.putText(frame, f"+ {vn}: {cnt} xe", (35, y_offset),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, (200, 200, 200), 1)
            y_offset += 22

        if writer:
            writer.write(frame)

        cv2.imshow("He Thong Dem & Do Toc Do Phuong Tien (ITS 2026)", frame)
        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

    cap.release()
    if writer:
        writer.release()
    cv2.destroyAllWindows()
    print("✅ Hoàn tất xử lý.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Demo Đếm xe và Đo tốc độ phương tiện giao thông.")
    parser.add_argument("--video", type=str, default="0", help="Đường dẫn file video hoặc link RTSP (hoặc '0' cho webcam)")
    parser.add_argument("--model", type=str, default="yolo11n.pt", help="Đường dẫn weights model YOLOv11")
    parser.add_argument("--limit", type=float, default=60.0, help="Giới hạn tốc độ cảnh báo quá tốc độ (km/h)")
    parser.add_argument("--output", type=str, default=None, help="Đường dẫn lưu video kết quả (.mp4)")
    args = parser.parse_args()

    video_input = int(args.video) if args.video.isdigit() else args.video
    run_pipeline(video_input, model_path=args.model, speed_limit=args.limit, output_path=args.output)
