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


from vehicle_detection.classes import VEHICLE_CLASSES, CLASS_NAMES_VI


from vehicle_detection.inference.speed import HomographySpeedEstimator
from vehicle_detection.inference.counting import LineCrossingCounter
from vehicle_detection.inference.calibration import load_calibration


def run_pipeline(video_source, model_path="yolo11n.pt", speed_limit=60.0, output_path=None, calibration_path=None):
    """Vòng lặp chính xử lý video streaming / video file."""
    calibration = load_calibration(calibration_path) if calibration_path else None
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

    if calibration:
        if calibration["image_size"] != [width, height]:
            cap.release()
            raise ValueError("Độ phân giải video khác image_size trong cấu hình hiệu chuẩn")
        src_polygon = calibration["source_points_px"]
        dst_rect = calibration["target_points_m"]
    else:
        print("WARNING: Chưa nạp hiệu chuẩn camera; tốc độ chỉ mang tính minh họa.")
        src_polygon = [
            (int(width * 0.35), int(height * 0.45)),
            (int(width * 0.65), int(height * 0.45)),
            (int(width * 0.90), int(height * 0.90)),
            (int(width * 0.10), int(height * 0.90)),
        ]
        dst_rect = [(0.0, 0.0), (8.0, 0.0), (8.0, 25.0), (0.0, 25.0)]

    speed_estimator = HomographySpeedEstimator(
        src_pts=src_polygon,
        dst_pts=dst_rect,
        fps=fps,
        speed_limit_kmh=speed_limit
    )

    # 2. Cấu hình vạch đếm ảo (Virtual Line) ngang qua làn đường
    if calibration:
        line_p1, line_p2 = (tuple(point) for point in calibration["count_line_px"])
    else:
        line_p1 = (int(width * 0.15), int(height * 0.70))
        line_p2 = (int(width * 0.85), int(height * 0.70))
    counter = LineCrossingCounter(line_p1, line_p2)

    writer = None
    if output_path:
        from pathlib import Path
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
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


def main():
    parser = argparse.ArgumentParser(description="Demo Đếm xe và Đo tốc độ phương tiện giao thông.")
    parser.add_argument("--video", type=str, default="0", help="Đường dẫn file video hoặc link RTSP (hoặc '0' cho webcam)")
    parser.add_argument("--model", type=str, default="yolo11n.pt", help="Đường dẫn weights model YOLOv11")
    parser.add_argument("--limit", type=float, default=60.0, help="Giới hạn tốc độ cảnh báo quá tốc độ (km/h)")
    parser.add_argument("--output", type=str, default=None, help="Đường dẫn lưu video kết quả (.mp4)")
    parser.add_argument("--calibration", type=str, help="JSON hiệu chuẩn camera (điểm ảnh, tọa độ mét và vạch đếm)")
    args = parser.parse_args()

    video_input = int(args.video) if args.video.isdigit() else args.video
    try:
        run_pipeline(video_input, model_path=args.model, speed_limit=args.limit,
                     output_path=args.output, calibration_path=args.calibration)
    except (ValueError, OSError) as exc:
        parser.error(str(exc))


if __name__ == "__main__":
    main()
