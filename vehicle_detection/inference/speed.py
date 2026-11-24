"""Estimate speed from ground-plane homography and track history."""
from collections import defaultdict, deque
import math
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
        if not math.isfinite(fps) or fps <= 0 or type(window_frames) is not int or window_frames < 2:
            raise ValueError("FPS phải dương và cửa sổ tốc độ cần ít nhất hai mẫu")
        self.fps = fps
        self.speed_limit_kmh = speed_limit_kmh
        self.ema_alpha = ema_alpha
        self.window_frames = window_frames

        # Tính ma trận Homography 3x3
        src = np.array(src_pts, dtype=np.float32)
        dst = np.array(dst_pts, dtype=np.float32)
        self.H, _ = cv2.findHomography(src, dst)

        if self.H is None or not np.isfinite(self.H).all():
            raise ValueError("Không tính được homography từ cấu hình camera")
        self.region = src

        # Lưu trữ lịch sử vị trí thực tế và vận tốc của từng xe: track_id -> deque
        self.track_history = defaultdict(lambda: deque(maxlen=max(30, window_frames)))
        self.smoothed_speeds = {}

    def pixel_to_world(self, px, py):
        """Chuyển đổi 1 điểm (px, py) trong ảnh sang tọa độ thế giới thực (X, Y) mét."""
        pt = np.array([[[px, py]]], dtype=np.float32)
        transformed = cv2.perspectiveTransform(pt, self.H)
        return float(transformed[0][0][0]), float(transformed[0][0][1])

    def forget(self, track_id):
        self.track_history.pop(track_id, None)
        self.smoothed_speeds.pop(track_id, None)

    def update(self, track_id, bottom_center_pt, frame_idx, *, timestamp_s=None):
        """
        Cập nhật vị trí và tính vận tốc của phương tiện track_id.
        :return: (speed_kmh, is_overspeed)
        """
        px, py = bottom_center_pt
        timestamp_s = frame_idx / self.fps if timestamp_s is None else timestamp_s
        history = self.track_history.get(track_id)
        if cv2.pointPolygonTest(self.region, (float(px), float(py)), False) < 0:
            self.forget(track_id)
            return 0.0, False
        if history and timestamp_s - history[-1][0] > 1.0:
            history.clear()
            self.smoothed_speeds.pop(track_id, None)
        if history and timestamp_s <= history[-1][0]:
            return 0.0, False
        world_x, world_y = self.pixel_to_world(px, py)

        self.track_history[track_id].append((timestamp_s, world_x, world_y))

        history = self.track_history[track_id]
        if len(history) < self.window_frames:
            # Chưa đủ số frame để tính vận tốc
            current_speed = self.smoothed_speeds.get(track_id, 0.0)
            return current_speed, current_speed > self.speed_limit_kmh

        # Lấy điểm trước đó k frames
        prev_time, prev_x, prev_y = history[-self.window_frames]
        distance_m = np.hypot(world_x - prev_x, world_y - prev_y)
        raw_speed_kmh = distance_m / (timestamp_s - prev_time) * 3.6

        # Lọc bỏ giá trị ngoại lai bất thường (outlier: v > 180 km/h do track giật)
        if raw_speed_kmh > 180.0:
            history.clear()
            self.smoothed_speeds.pop(track_id, None)
            return 0.0, False

        # Làm mượt bằng Exponential Moving Average (EMA)
        if track_id in self.smoothed_speeds:
            smoothed = self.ema_alpha * raw_speed_kmh + (1 - self.ema_alpha) * self.smoothed_speeds[track_id]
        else:
            smoothed = raw_speed_kmh

        self.smoothed_speeds[track_id] = smoothed
        is_overspeed = smoothed > self.speed_limit_kmh

        return smoothed, is_overspeed


