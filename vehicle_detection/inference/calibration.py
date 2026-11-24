"""Load camera geometry. Coordinates must match the original video resolution."""
import json
import math
from pathlib import Path
import re

from vehicle_detection.paths import PROJECT_ROOT

MAP_SPEED_SOURCE = "map_estimate"


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


def _line_points(points, size, key):
    _points(points, 2, key)
    for x, y in points:
        if type(x) is not int or type(y) is not int or not (0 <= x < size[0] and 0 <= y < size[1]):
            raise ValueError(f"{key}: cần tọa độ pixel nguyên trong image_size")


def validate_calibration(config, *, require_lines=True):
    if not isinstance(config, dict):
        raise ValueError("Cấu hình hiệu chuẩn phải là JSON object")
    size = config.get("image_size")
    if not isinstance(size, list) or len(size) != 2 or any(type(v) is not int or v <= 0 for v in size):
        raise ValueError("image_size: cần [width, height] nguyên dương")
    speed_enabled = config.get("speed_enabled", True)
    if type(speed_enabled) is not bool:
        raise ValueError("speed_enabled: cần true hoặc false")
    if config.get("speed_source") == MAP_SPEED_SOURCE and (
        not speed_enabled or not re.fullmatch(r"camera-\d+", str(config.get("camera_id", "")))
    ):
        raise ValueError("Hiệu chuẩn từ bản đồ cần mã camera và bật đo tốc độ")
    if speed_enabled or "source_points_px" in config or "target_points_m" in config:
        for key in ("source_points_px", "target_points_m"):
            _points(config.get(key), 4, key)
        if any(not (0 <= x < size[0] and 0 <= y < size[1]) for x, y in config["source_points_px"]):
            raise ValueError("source_points_px: điểm nằm ngoài image_size")
        _convex_quad(config["source_points_px"], "source_points_px")
        _convex_quad(config["target_points_m"], "target_points_m")
    if (require_lines and "count_lines" not in config) or "count_line_px" in config:
        _line_points(config.get("count_line_px"), size, "count_line_px")
    if "count_lines" in config:
        entries = config["count_lines"]
        if not isinstance(entries, list) or not entries:
            raise ValueError("count_lines: cần ít nhất một vạch")
        ids = set()
        for entry in entries:
            line_id = entry.get("line_id") if isinstance(entry, dict) else None
            if (not isinstance(line_id, str) or not re.fullmatch(r"[a-zA-Z0-9_-]{1,40}", line_id)
                    or line_id.casefold() in ids):
                raise ValueError("count_lines: line_id phải khác nhau và chỉ dùng chữ ASCII, số, - hoặc _")
            _line_points(entry.get("points_px"), size, line_id)
            limit = entry.get("speed_limit_kmh")
            if limit is not None and (type(limit) not in (int, float) or not math.isfinite(limit) or limit <= 0):
                raise ValueError(f"{line_id}: speed_limit_kmh phải là số dương hữu hạn")
            ids.add(line_id.casefold())
    return config


def load_calibration(path):
    return validate_calibration(json.loads(Path(path).read_text(encoding="utf-8-sig")))


def load_camera_speed_profile(camera_id):
    if not re.fullmatch(r"camera-\d+", camera_id):
        return None
    path = PROJECT_ROOT / "configs" / "cameras" / f"{camera_id}.speed.json"
    if not path.is_file():
        return None
    profile = validate_calibration(json.loads(path.read_text(encoding="utf-8-sig")), require_lines=False)
    if profile.get("camera_id") != camera_id or profile.get("speed_source") != MAP_SPEED_SOURCE:
        raise ValueError(f"Hồ sơ tốc độ không khớp với {camera_id}")
    return profile
