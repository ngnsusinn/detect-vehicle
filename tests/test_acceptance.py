import csv
import hashlib
import json
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import cv2
import numpy as np

from vehicle_detection.inference.demo import run_pipeline
from vehicle_detection.inference.evaluate import evaluate_counts, evaluate_speeds


class Tensor:
    def __init__(self, values):
        self.values = np.asarray(values)

    def cpu(self):
        return self

    def int(self):
        return self

    def numpy(self):
        return self.values

    def tolist(self):
        return self.values.tolist()


class FixedTrajectories:
    names = {0: "car", 1: "truck"}

    def __init__(self, _):
        self.index = 0

    def track(self, frame, **options):
        inbound = 10 + 2 * self.index
        outbound = 150 - 2 * self.index
        self.index += 1
        xyxy = Tensor([[35, inbound - 20, 55, inbound], [105, outbound - 20, 125, outbound]])
        return [SimpleNamespace(boxes=SimpleNamespace(xyxy=xyxy, id=Tensor([1, 2]), cls=Tensor([0, 1])))]


class AcceptanceTests(unittest.TestCase):
    def test_video_to_lane_report_evidence_and_reference_metrics(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            video, events, evidence = root / "test.mp4", root / "events", root / "evidence"
            writer = cv2.VideoWriter(str(video), cv2.VideoWriter_fourcc(*"mp4v"), 10, (160, 160))
            self.assertTrue(writer.isOpened())
            for _ in range(80):
                writer.write(np.zeros((160, 160, 3), dtype=np.uint8))
            writer.release()
            calibration = root / "camera.json"
            calibration.write_text(json.dumps({
                "camera_id": "synthetic",
                "image_size": [160, 160],
                "source_points_px": [[10, 10], [150, 10], [150, 150], [10, 150]],
                "target_points_m": [[0, 0], [56, 0], [56, 56], [0, 56]],
                "count_lines": [
                    {"line_id": "a", "points_px": [[12, 80], [78, 80]], "speed_limit_kmh": 20},
                    {"line_id": "b", "points_px": [[82, 80], [148, 80]], "speed_limit_kmh": 30},
                ],
            }), encoding="utf-8")
            with patch.dict(sys.modules, {"ultralytics": SimpleNamespace(YOLO=FixedTrajectories)}):
                run_pipeline(str(video), calibration_path=calibration, show=False, events_dir=events,
                             evidence_dir=evidence, timing="fps")

            with (events / "counts.csv").open(encoding="utf-8", newline="") as stream:
                crossings = [(row["line_id"], row["direction"], row["is_overspeed"]) for row in csv.DictReader(stream)]
            self.assertEqual(crossings, [("a", "IN", "1"), ("b", "OUT", "0")])
            stats = json.loads((events / "session_summary.json").read_text(encoding="utf-8"))
            self.assertAlmostEqual(stats["lines"]["a"]["p85_speed_kmh"], 28.8, places=4)
            self.assertEqual(stats["lines"]["a"]["modal_share"], {"car": 1.0})
            records = json.loads((evidence / "evidence.json").read_text(encoding="utf-8"))
            self.assertEqual(len(records), 1)
            self.assertTrue(records[0]["complete_pre"] and records[0]["complete_post"])
            for name, checksum in records[0]["sha256"].items():
                self.assertEqual(hashlib.sha256((evidence / name).read_bytes()).hexdigest(), checksum)
            clip = cv2.VideoCapture(str(evidence / records[0]["clip"]))
            self.assertEqual(int(clip.get(cv2.CAP_PROP_FRAME_COUNT)), 61)
            clip.release()

            count_truth = root / "count_truth.csv"
            count_truth.write_text("video_file,line_id,timestamp_s,class_name,direction\n"
                                   "test.mp4,a,3.5,car,IN\ntest.mp4,b,3.5,truck,OUT\n", encoding="utf-8")
            speed_truth = root / "speed_truth.csv"
            speed_truth.write_text("measurement_id,video_file,vehicle_id,start_time_s,end_time_s,"
                                   "reference_speed_kmh,reference_method\n"
                                   "1,test.mp4,manual-a,3,4,28.8,synthetic\n"
                                   "2,test.mp4,manual-b,3,4,28.8,synthetic\n", encoding="utf-8")
            links = root / "links.csv"
            links.write_text("video_file,vehicle_id,track_id\ntest.mp4,manual-a,1\ntest.mp4,manual-b,2\n", encoding="utf-8")
            self.assertEqual(evaluate_counts(count_truth, events / "counts.csv", 0.15)["f1"], 1)
            speed_report = evaluate_speeds(speed_truth, events / "speeds.csv", links)
            self.assertEqual(speed_report["coverage"], 1)
            self.assertAlmostEqual(speed_report["mae_kmh"], 0)
