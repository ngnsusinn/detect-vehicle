"""Evaluate line crossings and speed estimates against independent reference CSVs."""
import argparse
from collections import Counter, defaultdict
import csv
import json
import math
from pathlib import Path
from statistics import mean, median
import sys

from vehicle_detection.classes import CLASS_NAMES


def _rows(path, required):
    with Path(path).open(encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        missing = set(required) - set(reader.fieldnames or ())
        if missing:
            raise ValueError(f"{path}: thiếu cột {', '.join(sorted(missing))}")
        for row in reader:
            if any(not row[field] or not row[field].strip() for field in required):
                raise ValueError(f"{path}, dòng {reader.line_num}: dữ liệu bắt buộc bị trống")
            yield {key: value.strip() if value else "" for key, value in row.items() if key is not None}


def _number(value, field):
    try:
        number = float(value)
    except ValueError as exc:
        raise ValueError(f"{field}: cần số hữu hạn, không âm") from exc
    if not math.isfinite(number) or number < 0:
        raise ValueError(f"{field}: cần số hữu hạn, không âm")
    return number


def _crossing_times(path):
    result = defaultdict(list)
    for row in _rows(path, ("video_file", "class_name", "direction", "timestamp_s")):
        if row["direction"] not in {"IN", "OUT"} or row["class_name"] not in CLASS_NAMES:
            raise ValueError(f"{path}: lớp hoặc hướng cắt vạch không hợp lệ")
        key = (row["video_file"], row.get("line_id") or "main", row["direction"], row["class_name"])
        result[key].append(_number(row["timestamp_s"], "timestamp_s"))
    return result


def _matched_count(reference, predicted, tolerance):
    left, right = sorted(reference), sorted(predicted)
    i = j = matched = 0
    while i < len(left) and j < len(right):
        diff = right[j] - left[i]
        if diff < -tolerance:
            j += 1
        elif diff > tolerance:
            i += 1
        else:
            matched += 1
            i += 1
            j += 1
    return matched


def _count_metrics(tp, fp, fn):
    reference = tp + fn
    predicted = tp + fp
    total = 2 * tp + fp + fn
    return {"reference_count": reference, "predicted_count": predicted,
            "true_positive": tp, "false_positive": fp, "false_negative": fn,
            "count_error": predicted - reference,
            "precision": tp / predicted if predicted else None,
            "recall": tp / reference if reference else None,
            "f1": 2 * tp / total if total else None}


def evaluate_counts(truth, predictions, tolerance=0.5):
    if not math.isfinite(tolerance) or tolerance < 0:
        raise ValueError("Dung sai ghép sự kiện phải là số hữu hạn, không âm")
    reference = _crossing_times(truth)
    predicted = _crossing_times(predictions)
    groups = []
    total = Counter()
    for key in sorted(reference.keys() | predicted.keys()):
        expected = reference.get(key, [])
        observed = predicted.get(key, [])
        tp = _matched_count(expected, observed, tolerance)
        fp, fn = len(observed) - tp, len(expected) - tp
        total.update({"tp": tp, "fp": fp, "fn": fn})
        labels = dict(zip(("video_file", "line_id", "direction", "class_name"), key))
        groups.append({**labels, **_count_metrics(tp, fp, fn)})
    return {"tolerance_s": tolerance, **_count_metrics(total["tp"], total["fp"], total["fn"]), "groups": groups}


def _track_links(path):
    links = {}
    assigned = set()
    for row in _rows(path, ("video_file", "vehicle_id", "track_id")):
        key = (row["video_file"], row["vehicle_id"])
        target = (row["video_file"], row["track_id"])
        if key in links or target in assigned:
            raise ValueError(f"{path}: liên kết vehicle_id và track_id phải là một-một trong mỗi video")
        links[key] = target
        assigned.add(target)
    return links


def evaluate_speeds(truth, predictions, track_links):
    links = _track_links(track_links)
    samples = defaultdict(list)
    for row in _rows(predictions, ("video_file", "track_id", "timestamp_s", "speed_kmh", "geometry")):
        if row["geometry"] != "configured":
            raise ValueError(f"{predictions}: chỉ chấp nhận tốc độ từ cấu hình camera đã đo")
        timestamp = _number(row["timestamp_s"], "timestamp_s")
        speed = _number(row["speed_kmh"], "speed_kmh")
        samples[(row["video_file"], row["track_id"])].append((timestamp, speed))

    measurements = []
    seen_ids = set()
    errors = []
    required = ("measurement_id", "video_file", "vehicle_id", "start_time_s", "end_time_s",
                "reference_speed_kmh", "reference_method")
    for row in _rows(truth, required):
        start = _number(row["start_time_s"], "start_time_s")
        end = _number(row["end_time_s"], "end_time_s")
        reference = _number(row["reference_speed_kmh"], "reference_speed_kmh")
        measurement = (row["video_file"], row["measurement_id"])
        if measurement in seen_ids or start >= end:
            raise ValueError(f"{truth}: mã phép đo bị lặp hoặc khoảng thời gian không hợp lệ")
        seen_ids.add(measurement)
        key = (row["video_file"], row["vehicle_id"])
        link = links.get(key)
        values = [speed for timestamp, speed in samples.get(link, ()) if start <= timestamp <= end]
        estimated = median(values) if values else None
        error = estimated - reference if estimated is not None else None
        if error is not None:
            errors.append(error)
        status = "matched" if values else ("no_samples" if link else "unmapped_vehicle")
        measurements.append({**{field: row[field] for field in ("measurement_id", "video_file", "vehicle_id", "reference_method")},
                             "track_id": link[1] if link else None, "status": status, "samples": len(values),
                             "start_time_s": start, "end_time_s": end, "reference_speed_kmh": reference,
                             "estimated_speed_kmh": estimated, "error_kmh": error})

    count = len(measurements)
    return {"reference_measurements": count, "matched_measurements": len(errors),
            "coverage": len(errors) / count if count else None,
            "mae_kmh": mean(map(abs, errors)) if errors else None,
            "rmse_kmh": math.sqrt(mean(error ** 2 for error in errors)) if errors else None,
            "bias_kmh": mean(errors) if errors else None,
            "within_5_kmh": sum(abs(error) <= 5 for error in errors) / len(errors) if errors else None,
            "measurements": measurements}


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--events", type=Path, required=True, help="Thư mục CSV do demo xuất")
    parser.add_argument("--count-truth", type=Path, required=True)
    parser.add_argument("--speed-truth", type=Path)
    parser.add_argument("--track-links", type=Path)
    parser.add_argument("--tolerance", type=float, default=0.5)
    parser.add_argument("--dataset-kind", choices=("field", "external", "synthetic"), required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if bool(args.speed_truth) != bool(args.track_links):
        parser.error("--speed-truth và --track-links phải được cung cấp cùng nhau")
    try:
        report = {"dataset_kind": args.dataset_kind,
                  "counts": evaluate_counts(args.count_truth, args.events / "counts.csv", args.tolerance)}
        if args.speed_truth:
            report["speeds"] = evaluate_speeds(args.speed_truth, args.events / "speeds.csv", args.track_links)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    except (OSError, ValueError) as exc:
        parser.error(str(exc))
    print(f"Đã tạo báo cáo {args.output}")


if __name__ == "__main__":
    main()
