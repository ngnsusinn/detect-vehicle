"""Load camera geometry. Coordinates must match the original video resolution."""
import json
import math
from pathlib import Path


def _points(value, count, key):
    if not isinstance(value, list) or len(value) != count:
        raise ValueError(f"{key}: cần {count} điểm [x, y]")
    for point in value:
        if not isinstance(point, list) or len(point) != 2:
            raise ValueError(f"{key}: mỗi điểm phải là [x, y]")
        if any(isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v) for v in point):
            raise ValueError(f"{key}: tọa độ phải là số hữu hạn")
    if len({tuple(p) for p in value}) != count:
        raise ValueError(f"{key}: các điểm phải khác nhau")


def _convex_quad(points, key):
    crosses = []
    for index in range(4):
        a, b, c = (points[(index + offset) % 4] for offset in range(3))
        crosses.append((b[0] - a[0]) * (c[1] - b[1]) - (b[1] - a[1]) * (c[0] - b[0]))
    if not (all(v > 0 for v in crosses) or all(v < 0 for v in crosses)):
        raise ValueError(f"{key}: cần tứ giác lồi, các điểm theo thứ tự quanh chu vi")


def load_calibration(path):
    config = json.loads(Path(path).read_text(encoding="utf-8-sig"))
    if not isinstance(config, dict):
        raise ValueError("Cấu hình hiệu chuẩn phải là JSON object")
    size = config.get("image_size")
    if not isinstance(size, list) or len(size) != 2 or any(type(v) is not int or v <= 0 for v in size):
        raise ValueError("image_size: cần [width, height] nguyên dương")
    for key, count in (("source_points_px", 4), ("target_points_m", 4), ("count_line_px", 2)):
        _points(config.get(key), count, key)
    for key in ("source_points_px", "count_line_px"):
        for x, y in config[key]:
            if not (0 <= x < size[0] and 0 <= y < size[1]):
                raise ValueError(f"{key}: điểm nằm ngoài image_size")
    if any(type(v) is not int for point in config["count_line_px"] for v in point):
        raise ValueError("count_line_px: cần tọa độ pixel nguyên")
    _convex_quad(config["source_points_px"], "source_points_px")
    _convex_quad(config["target_points_m"], "target_points_m")
    return config
