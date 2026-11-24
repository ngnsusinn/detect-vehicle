"""Track traffic, count line crossings and estimate ground-plane speed."""
import argparse
import csv
from contextlib import ExitStack
import json
import math
from pathlib import Path
import sys
from time import perf_counter

import cv2
import numpy as np

from vehicle_detection.classes import CLASS_NAMES
from vehicle_detection.inference.analytics import TrafficStats
from vehicle_detection.inference.calibration import MAP_SPEED_SOURCE, load_calibration, validate_calibration
from vehicle_detection.inference.camera_view import CameraView
from vehicle_detection.inference.counting import LineCrossingCounter
from vehicle_detection.inference.evidence import EvidenceRecorder
from vehicle_detection.inference.speed import HomographySpeedEstimator
from vehicle_detection.inference.stream_catalog import load_stream
from vehicle_detection.inference.timing import FrameClock
from vehicle_detection.paths import DEFAULT_WEIGHTS

WINDOW_NAME = "Detect Vehicle - Dem xe va do toc do"
COUNT_COLUMNS = ("video_file", "frame_index", "timestamp_s", "track_id", "class_name", "direction",
                 "line_id", "speed_kmh", "speed_limit_kmh", "is_overspeed")
SPEED_COLUMNS = ("video_file", "frame_index", "timestamp_s", "track_id", "class_name",
                 "speed_kmh", "is_overspeed", "geometry")


def open_video_source(source):
    if isinstance(source, str) and source.lower().startswith(("rtsp://", "rtsps://", "http://", "https://")):
        return cv2.VideoCapture(source, cv2.CAP_FFMPEG, [
            cv2.CAP_PROP_OPEN_TIMEOUT_MSEC, 8000, cv2.CAP_PROP_READ_TIMEOUT_MSEC, 5000,
        ])
    return cv2.VideoCapture(source)


def _geometry(calibration, width, height, limit):
    if calibration:
        if calibration["image_size"] != [width, height]:
            raise ValueError("Độ phân giải video khác image_size trong cấu hình hiệu chuẩn")
        specs = calibration.get("count_lines")
        if specs is None:
            specs = [{"line_id": "main", "points_px": calibration["count_line_px"]}]
        lines = {spec["line_id"]: (tuple(map(tuple, spec["points_px"])), spec.get("speed_limit_kmh") or limit)
                 for spec in specs}
        return calibration.get("source_points_px"), calibration.get("target_points_m"), lines
    polygon = [(int(width * x), int(height * y)) for x, y in
               ((0.35, 0.45), (0.65, 0.45), (0.90, 0.90), (0.10, 0.90))]
    ground = [(0, 0), (8, 0), (8, 25), (0, 25)]
    line = ((int(width * 0.15), int(height * 0.70)), (int(width * 0.85), int(height * 0.70)))
    return polygon, ground, {"main": (line, limit)}


def _csv_writer(stack, path, columns):
    stream = stack.enter_context(path.open("w", encoding="utf-8", newline=""))
    writer = csv.writer(stream)
    writer.writerow(columns)
    return writer


def _tracking_rows(result, names):
    boxes = result.boxes
    if boxes is None or boxes.id is None:
        return
    for box, track_id, class_id in zip(boxes.xyxy.cpu().numpy(), boxes.id.int().cpu().tolist(),
                                      boxes.cls.int().cpu().tolist()):
        name = names[class_id]
        if name in CLASS_NAMES:
            yield box, track_id, name


def _draw_track(frame, box, anchor, track_id, name, speed, overspeed, *, approximate=False):
    x1, y1, x2, y2 = map(int, box)
    color = (0, 0, 255) if overspeed else (0, 255, 0)
    cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)
    cv2.circle(frame, tuple(map(int, anchor)), 4, (0, 255, 255), -1)
    label = f"ID {track_id} | {name}"
    if speed is not None:
        label += f" | {'~' if approximate else ''}{speed:.1f} km/h"
    cv2.putText(frame, label, (x1, max(16, y1 - 5)), cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 2)


def run_pipeline(video_source, model_path="yolo11n.pt", speed_limit=60.0, output_path=None,
                 calibration_path=None, *, show=True, events_dir=None, evidence_dir=None,
                 timing="auto", confidence=None, stream_id=None, calibration_config=None,
                 measure_speed=True, on_frame=None, stop_event=None):
    """Process a video or stream and optionally save its overlay, CSV and evidence."""
    if not math.isfinite(speed_limit) or speed_limit <= 0:
        raise ValueError("Giới hạn tốc độ phải là số hữu hạn lớn hơn 0")
    if confidence is not None and not 0 < confidence <= 1:
        raise ValueError("Ngưỡng confidence phải thuộc (0, 1]")
    if timing not in {"auto", "pts", "fps"}:
        raise ValueError("Timing phải là auto, pts hoặc fps")
    is_file = isinstance(video_source, str) and Path(video_source).is_file()
    source_name = stream_id or video_source
    if not stream_id and isinstance(video_source, str) and "://" in video_source:
        source_name = "luồng video"
    if output_path and is_file:
        if Path(output_path).resolve() == Path(video_source).resolve():
            raise ValueError("Video đầu vào và đầu ra phải là hai tệp khác nhau")
    if calibration_path and calibration_config is not None:
        raise ValueError("Chỉ dùng một nguồn cấu hình hiệu chuẩn")
    calibration = load_calibration(calibration_path) if calibration_path else calibration_config
    if calibration_config is not None:
        validate_calibration(calibration_config)
    measure_speed = measure_speed and (calibration or {}).get("speed_enabled", True)
    approximate = measure_speed and (calibration or {}).get("speed_source") == MAP_SPEED_SOURCE
    illustrative = (not calibration or (calibration_path and Path(calibration_path).stem.casefold().endswith(".example"))
                    or str(calibration.get("measurement_note", "")).strip().casefold().startswith("example only:"))
    if evidence_dir and (illustrative or approximate or not measure_speed):
        raise ValueError("--evidence-dir yêu cầu hiệu chuẩn camera bằng số đo thực địa")
    if measure_speed and illustrative:
        print("WARNING: Tốc độ chỉ mang tính minh họa.")
    with ExitStack() as stack:
        cap = open_video_source(video_source)
        stack.callback(cap.release)
        if not cap.isOpened():
            raise OSError(f"Không thể mở nguồn video: {source_name}")
        ok, frame = cap.read()
        if not ok:
            raise OSError(f"Nguồn video không có khung hình đọc được: {source_name}")
        height, width = frame.shape[:2]
        fps = cap.get(cv2.CAP_PROP_FPS)
        if not math.isfinite(fps) or fps <= 0:
            if calibration and measure_speed:
                raise ValueError("Nguồn video thiếu FPS để ước lượng tốc độ theo hiệu chuẩn")
            print("WARNING: Không đọc được FPS. Demo sử dụng 30 FPS.")
            fps = 30.0

        from ultralytics import YOLO

        polygon, ground, lines = _geometry(calibration, width, height, speed_limit)
        view = CameraView(calibration) if approximate else None
        if view is not None and not view.matches(frame):
            raise ValueError("Góc quay không khớp hồ sơ bản đồ. Mở khung hình để đặt lại vạch.")
        window = max(6, round(0.35 * fps) + 1) if approximate else 6
        estimator = (HomographySpeedEstimator(polygon, ground, fps, speed_limit, window_frames=window)
                     if measure_speed else None)
        counters = {name: LineCrossingCounter(*line) for name, (line, _) in lines.items()}
        stats = TrafficStats({name: limit for name, (_, limit) in lines.items()}, report_overspeed=not approximate)
        outline = np.asarray(polygon, dtype=np.int32) if measure_speed else None
        geometry = (MAP_SPEED_SOURCE if approximate else "illustrative" if illustrative else "configured"
                    ) if measure_speed else "disabled"
        clock_mode = timing
        if timing == "auto" and approximate:
            clock_mode = "pts"
        elif timing == "auto" and not is_file:
            clock_mode = "fps"
        clock = FrameClock(fps, clock_mode)
        model = YOLO(model_path)
        track_args = {"persist": True, "tracker": "bytetrack.yaml", "verbose": False}
        if confidence is not None:
            track_args["conf"] = confidence
        video_file = Path(video_source).name if is_file else stream_id or "stream"
        counts_csv = speeds_csv = writer = None
        if events_dir:
            events = Path(events_dir)
            events.mkdir(parents=True, exist_ok=True)
            counts_csv = _csv_writer(stack, events / "counts.csv", COUNT_COLUMNS)
            speeds_csv = _csv_writer(stack, events / "speeds.csv", SPEED_COLUMNS)
        if output_path:
            Path(output_path).parent.mkdir(parents=True, exist_ok=True)
            writer = cv2.VideoWriter(str(output_path), cv2.VideoWriter_fourcc(*"mp4v"), fps, (width, height))
            stack.callback(writer.release)
            if not writer.isOpened():
                raise OSError(f"Không thể ghi video: {output_path}")
        if show:
            stack.callback(cv2.destroyAllWindows)
        evidence = EvidenceRecorder(evidence_dir, fps, (width, height)) if evidence_dir else None

        frame_idx = 0
        timestamp = 0.0
        total_in = total_out = 0
        last_seen = {}
        previous_pts = None
        repeated_pts = 0
        stale_frames = max(60, math.ceil(2 * fps))
        started = perf_counter()
        presentation_fps = f"{width}x{height} @ {fps:.2f} FPS"
        print(f"Bắt đầu xử lý {presentation_fps}")
        while ok and not (stop_event and stop_event.is_set()):
            position_ms = cap.get(cv2.CAP_PROP_POS_MSEC)
            if approximate and clock.mode == "pts" and position_ms == previous_pts:
                repeated_pts += 1
                if repeated_pts > 4:
                    raise ValueError("PTS của camera không tăng qua nhiều khung hình")
                ok, frame = cap.read()
                continue
            previous_pts = position_ms
            repeated_pts = 0
            if view is not None and frame_idx and not view.matches(frame):
                raise ValueError("Góc quay đã thay đổi. Mở khung hình để đặt lại vạch.")
            frame_idx += 1
            if frame_idx % stale_frames == 0:
                expired = [track_id for track_id, previous in last_seen.items() if frame_idx - previous >= stale_frames]
                for track_id in expired:
                    del last_seen[track_id]
                    if estimator:
                        estimator.forget(track_id)
                    for counter in counters.values():
                        counter.forget(track_id)
            timestamp = clock.timestamp(frame_idx, position_ms)
            results = model.track(frame, **track_args)
            if outline is not None:
                cv2.polylines(frame, [outline], True, (255, 200, 0), 2)
            for line_id, (line, _) in lines.items():
                cv2.line(frame, *line, (0, 165, 255), 3)
                cv2.putText(frame, line_id, (line[0][0], max(14, line[0][1] - 5)),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 165, 255), 1)
            evidence_events = []
            active_tracks = 0
            if results:
                for box, track_id, name in _tracking_rows(results[0], model.names):
                    active_tracks += 1
                    last_seen[track_id] = frame_idx
                    anchor = (float((box[0] + box[2]) / 2), float(box[3]))
                    speed, overspeed = (estimator.update(track_id, anchor, frame_idx, timestamp_s=timestamp)
                                        if estimator else (0.0, False))
                    context = (video_file, frame_idx, round(timestamp, 6), track_id, name)
                    measured = estimator is not None and track_id in estimator.smoothed_speeds
                    logged_speed = round(float(speed), 3) if measured else None
                    if speeds_csv and measured:
                        speeds_csv.writerow((*context, logged_speed, None if approximate else int(overspeed), geometry))
                    crossing_flags = []
                    for line_id, counter in counters.items():
                        direction = counter.update(track_id, anchor, name)
                        if not direction:
                            continue
                        limit = lines[line_id][1]
                        is_over = speed > limit if measured and not approximate else None
                        crossing_flags.append(bool(is_over))
                        stats.record(line_id, direction, name, timestamp, speed if measured else None)
                        if counts_csv:
                            counts_csv.writerow((*context, direction, line_id, logged_speed, limit,
                                                 int(is_over) if is_over is not None else None))
                        if evidence and is_over:
                            evidence_events.append({**dict(zip(COUNT_COLUMNS[:5], context)), "line_id": line_id,
                                                    "direction": direction, "speed_kmh": logged_speed,
                                                    "speed_limit_kmh": limit, "timestamp_s": timestamp})
                    alert = not approximate and (any(crossing_flags) if crossing_flags else overspeed)
                    _draw_track(frame, box, anchor, track_id, name, speed if measured else None,
                                alert, approximate=approximate)

            total_in = sum(counter.total_in for counter in counters.values())
            total_out = sum(counter.total_out for counter in counters.values())
            summary = f"IN: {total_in} | OUT: {total_out}"
            if approximate:
                summary += " | MAP ESTIMATE"
            elif geometry == "illustrative":
                summary += " | DEMO"
            cv2.putText(frame, summary, (12, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.65, (0, 255, 255), 2)
            for row, (line_id, counter) in enumerate(counters.items(), start=2):
                cv2.putText(frame, f"{line_id}: {counter.total_in} IN / {counter.total_out} OUT",
                            (12, row * 20), cv2.FONT_HERSHEY_SIMPLEX,
                            0.5, (0, 255, 255), 1)
            if len(counters) == 1:
                for row, (name, count) in enumerate(sorted(counter.class_counts.items()), start=3):
                    cv2.putText(frame, f"{name}: {count}", (12, row * 20), cv2.FONT_HERSHEY_SIMPLEX,
                                0.5, (0, 255, 255), 1)
            if evidence:
                evidence.observe(timestamp, frame, evidence_events)
            if writer is not None:
                writer.write(frame)
            if on_frame:
                on_frame(frame, {"frame": frame_idx, "total_in": total_in, "total_out": total_out,
                                 "active_tracks": active_tracks, "source_fps": fps, "geometry": geometry})
            if show:
                cv2.imshow(WINDOW_NAME, frame)
                if cv2.waitKey(1) & 0xFF == ord("q"):
                    break
            if stop_event and stop_event.is_set():
                break
            ok, frame = cap.read()
        elapsed = perf_counter() - started
        if evidence:
            evidence.close()
        report = {
            "video_file": video_file, "camera_id": (calibration or {}).get("camera_id"),
            "geometry": geometry, "time_base": "fps" if clock.mode == "auto" else clock.mode,
            "frames": frame_idx, "source_fps": fps, "last_timestamp_s": timestamp,
            "processing_seconds": elapsed, "processing_fps": frame_idx / elapsed,
            "total_in": total_in, "total_out": total_out, **stats.report(),
        }
        if events_dir:
            (events / "session_summary.json").write_text(
                json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8",
            )
    print(f"Hoàn tất {frame_idx} frame, IN {total_in}, OUT {total_out}")
    return report


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description="Đếm xe và ước lượng tốc độ phương tiện")
    sources = parser.add_mutually_exclusive_group()
    sources.add_argument("--video", help="Tệp video, URL luồng hoặc chỉ số camera")
    sources.add_argument("--camera-list", type=Path, help="Tệp JSON có ID, TEN và STSPLINK")
    parser.add_argument("--camera-id", type=int, help="ID camera trong --camera-list")
    parser.add_argument("--model", help="Trọng số detector YOLO. Danh sách camera mặc định dùng model dự án.")
    parser.add_argument("--limit", type=float, default=60.0, help="Ngưỡng cảnh báo km/h")
    parser.add_argument("--output", help="Video MP4 có overlay")
    parser.add_argument("--calibration", help="JSON hiệu chuẩn camera")
    parser.add_argument("--headless", action="store_true", help="Chạy không mở cửa sổ video")
    parser.add_argument("--events-dir", type=Path, help="Thư mục lưu counts.csv và speeds.csv")
    parser.add_argument("--evidence-dir", type=Path, help="Thư mục mới lưu ảnh và clip vượt ngưỡng tại vạch")
    parser.add_argument("--timing", choices=("auto", "pts", "fps"), default="auto",
                        help="Nguồn thời gian. Auto ưu tiên PTS trên video lưu cục bộ.")
    parser.add_argument("--confidence", type=float, help="Ngưỡng phát hiện, giữ mặc định ByteTrack khi bỏ qua")
    parser.add_argument("--count-only", action="store_true", help="Chỉ đếm lượt qua vạch")
    args = parser.parse_args()
    if bool(args.camera_list) != (args.camera_id is not None):
        parser.error("--camera-list và --camera-id phải dùng cùng nhau")
    try:
        stream_id = None
        model = args.model or "yolo11n.pt"
        if args.camera_list:
            video_input, name = load_stream(args.camera_list, args.camera_id)
            stream_id = f"camera-{args.camera_id}"
            if args.model is None:
                if not DEFAULT_WEIGHTS.is_file():
                    raise ValueError(f"Thiếu trọng số {DEFAULT_WEIGHTS}. Chỉ định model bằng --model.")
                model = str(DEFAULT_WEIGHTS)
            print(f"Camera {args.camera_id} {name}".rstrip())
        else:
            source = args.video or "0"
            video_input = int(source) if source.isdigit() else source
        run_pipeline(video_input, model, args.limit, args.output, args.calibration,
                     show=not args.headless, events_dir=args.events_dir, evidence_dir=args.evidence_dir,
                     timing=args.timing, confidence=args.confidence, stream_id=stream_id,
                     measure_speed=not args.count_only)
    except (ImportError, OSError, ValueError) as exc:
        parser.error(str(exc))


if __name__ == "__main__":
    main()
