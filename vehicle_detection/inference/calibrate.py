"""Build camera geometry from a reference image and field measurements."""
import argparse
import json
import math
from pathlib import Path
import sys

import cv2
import numpy as np

from vehicle_detection.inference.calibration import validate_calibration


def _pixel(text):
    parts = text.split(",")
    if len(parts) != 2:
        raise ValueError(f"Tọa độ {text!r} cần theo dạng X,Y")
    return [int(part) for part in parts]


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reference", type=Path, required=True)
    parser.add_argument("--camera", required=True)
    parser.add_argument("--road", nargs=4, required=True, metavar="X,Y",
                        help="Trái xa, phải xa, phải gần, trái gần")
    parser.add_argument("--meters", nargs=2, type=float, required=True, metavar=("WIDTH", "LENGTH"))
    parser.add_argument("--lane", action="append", nargs=4, required=True, metavar=("ID", "P1", "P2", "KM/H"),
                        help="Lặp lại cho mỗi vạch. P1, P2 có dạng X,Y. Dùng default cho ngưỡng mặc định.")
    parser.add_argument("--measurement-note", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--preview", type=Path)
    args = parser.parse_args()
    try:
        if args.output.exists() or (args.preview and args.preview.exists()):
            raise FileExistsError("Cấu hình hoặc ảnh kiểm tra đã tồn tại. Hãy chọn tên mới.")
        if args.preview and args.preview.resolve() == args.output.resolve():
            raise ValueError("Cấu hình và ảnh kiểm tra phải là hai tệp khác nhau")
        if not args.measurement_note.strip():
            raise ValueError("Cần ghi nguồn số đo thực địa")
        frame = cv2.imdecode(np.frombuffer(args.reference.read_bytes(), np.uint8), cv2.IMREAD_COLOR)
        if frame is None:
            raise ValueError(f"Không đọc được ảnh tham chiếu {args.reference}")
        meters_w, meters_l = args.meters
        if not all(math.isfinite(value) and value > 0 for value in args.meters):
            raise ValueError("Kích thước thực địa phải là số hữu hạn lớn hơn 0")
        height, width = frame.shape[:2]
        config = validate_calibration({
            "camera_id": args.camera, "image_size": [width, height],
            "source_points_px": [_pixel(point) for point in args.road],
            "target_points_m": [[0, 0], [meters_w, 0], [meters_w, meters_l], [0, meters_l]],
            "count_lines": [{"line_id": name, "points_px": [_pixel(start), _pixel(end)],
                             "speed_limit_kmh": None if limit == "default" else float(limit)}
                            for name, start, end, limit in args.lane],
            "measurement_note": args.measurement_note,
        })
        if args.preview:
            road = np.asarray(config["source_points_px"], np.int32)
            cv2.polylines(frame, [road], True, (255, 200, 0), 3)
            for index, point in enumerate(road, start=1):
                cv2.circle(frame, tuple(point), 6, (0, 255, 255), -1)
                cv2.putText(frame, f"P{index}", tuple(point + (7, -7)), cv2.FONT_HERSHEY_SIMPLEX,
                            0.7, (0, 255, 255), 2)
            for lane in config["count_lines"]:
                start, end = map(tuple, lane["points_px"])
                cv2.arrowedLine(frame, start, end, (0, 165, 255), 3)
                cv2.putText(frame, lane["line_id"], (start[0], max(15, start[1] - 8)),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 165, 255), 2)
            ok, encoded = cv2.imencode(args.preview.suffix, frame)
            if not ok:
                raise OSError(f"Không thể tạo ảnh {args.preview}")
            args.preview.parent.mkdir(parents=True, exist_ok=True)
            with args.preview.open("xb") as stream:
                stream.write(encoded.tobytes())
        args.output.parent.mkdir(parents=True, exist_ok=True)
        with args.output.open("x", encoding="utf-8") as stream:
            json.dump(config, stream, ensure_ascii=False, indent=2)
            stream.write("\n")
    except (OSError, ValueError, cv2.error) as exc:
        parser.error(str(exc))
    print(f"Đã tạo cấu hình {args.output}")


if __name__ == "__main__":
    main()
