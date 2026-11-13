"""Estimate speed from ground-plane homography and track history."""
from collections import defaultdict, deque
import cv2
import numpy as np


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


