"""Geometry shared by the desktop editor and the inference pipeline."""
from dataclasses import dataclass
import math

from vehicle_detection.inference.calibration import validate_calibration


def positive_number(text, label):
    try:
        value = float(text.strip().replace(",", "."))
    except ValueError:
        raise ValueError(f"{label}: nhập số dương") from None
    if not math.isfinite(value) or value <= 0:
        raise ValueError(f"{label}: nhập số dương hữu hạn")
    return value


def make_config(camera_id, image_size, road, lines, *, dimensions=None, note="", speed_profile=None):
    if speed_profile is not None:
        if speed_profile["camera_id"] != camera_id or speed_profile["image_size"] != list(image_size):
            raise ValueError("Hiệu chuẩn mặc định khác camera hoặc độ phân giải")
        return validate_calibration({**speed_profile, "count_lines": list(lines.values())})
    config = {
        "camera_id": camera_id,
        "image_size": list(image_size),
        "count_lines": list(lines.values()),
        "speed_enabled": dimensions is not None,
    }
    if dimensions is not None:
        width, length = dimensions
        config.update(source_points_px=road,
                      target_points_m=[[0, 0], [width, 0], [width, length], [0, length]],
                      measurement_note=note.strip() or "Kích thước nhập từ phép đo thực địa.")
    return validate_calibration(config)


@dataclass(frozen=True)
class ImageViewport:
    source_width: int
    source_height: int
    width: int
    height: int
    left: int
    top: int

    @classmethod
    def fit(cls, source_width, source_height, canvas_width, canvas_height):
        ratio = min(canvas_width / source_width, canvas_height / source_height)
        width = max(1, round(source_width * ratio))
        height = max(1, round(source_height * ratio))
        return cls(source_width, source_height, width, height,
                   (canvas_width - width) // 2, (canvas_height - height) // 2)

    def source_point(self, x, y):
        if not (self.left <= x < self.left + self.width and self.top <= y < self.top + self.height):
            return None
        src_x = min(self.source_width - 1, round((x - self.left) * self.source_width / self.width))
        src_y = min(self.source_height - 1, round((y - self.top) * self.source_height / self.height))
        return [src_x, src_y]

    def canvas_point(self, point):
        x, y = point
        return self.left + x * self.width / self.source_width, self.top + y * self.height / self.source_height
