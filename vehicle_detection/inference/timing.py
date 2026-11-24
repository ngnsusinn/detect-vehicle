"""Select one monotonic time base for an entire video run."""
import math


class FrameClock:
    def __init__(self, fps, mode):
        self.fps = fps
        self.mode = mode
        self.origin_ms = None
        self.last_time = 0.0

    def timestamp(self, frame_index, position_ms):
        valid_position = math.isfinite(position_ms) and position_ms >= 0
        if self.mode != "fps" and frame_index == 1 and valid_position:
            self.origin_ms = position_ms
            return 0.0
        if self.mode == "auto":
            if valid_position and self.origin_ms is not None and position_ms > self.origin_ms:
                self.mode = "pts"
            elif frame_index <= 2:
                self.mode = "fps"
        if self.mode == "fps":
            return (frame_index - 1) / self.fps
        if not valid_position or self.origin_ms is None:
            raise ValueError(f"Frame {frame_index}: không đọc được PTS")
        timestamp = (position_ms - self.origin_ms) / 1000
        if timestamp <= self.last_time:
            raise ValueError(f"Frame {frame_index}: PTS không tăng. Kiểm tra timestamp nguồn video.")
        self.last_time = timestamp
        return timestamp
