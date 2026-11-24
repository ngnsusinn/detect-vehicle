import csv
import tempfile
import unittest
from pathlib import Path

from vehicle_detection.inference.evaluate import evaluate_counts, evaluate_speeds


def write_csv(path, headers, rows):
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.writer(stream)
        writer.writerow(headers)
        writer.writerows(rows)


class EvaluationTests(unittest.TestCase):
    def test_matches_once_and_keeps_lane_class_and_direction_separate(self):
        headers = ("video_file", "line_id", "direction", "class_name", "timestamp_s")
        with tempfile.TemporaryDirectory() as folder:
            truth, predicted = (Path(folder) / f"{name}.csv" for name in ("truth", "predictions"))
            write_csv(truth, headers, [("video.mp4", "lane-a", "IN", "car", 1),
                                       ("video.mp4", "lane-a", "IN", "car", 2),
                                       ("video.mp4", "lane-b", "OUT", "truck", 8)])
            write_csv(predicted, headers, [("video.mp4", "lane-a", "IN", "car", 0.8),
                                           ("video.mp4", "lane-a", "IN", "car", 1.05),
                                           ("video.mp4", "lane-a", "IN", "car", 2.15),
                                           ("video.mp4", "lane-a", "OUT", "truck", 8)])
            report = evaluate_counts(truth, predicted, tolerance=0.3)
            self.assertEqual((report["true_positive"], report["false_positive"], report["false_negative"]), (2, 2, 1))
            self.assertAlmostEqual(report["f1"], 4 / 7)

    def test_speed_median_window_and_unmapped_coverage(self):
        with tempfile.TemporaryDirectory() as folder:
            truth, predicted, links = (Path(folder) / f"{name}.csv" for name in ("truth", "predictions", "links"))
            write_csv(truth, ("measurement_id", "video_file", "vehicle_id", "start_time_s", "end_time_s",
                              "reference_speed_kmh", "reference_method"), [
                ("1", "video.mp4", "vehicle-1", 1, 2, 20, "radar"), ("2", "video.mp4", "vehicle-2", 1, 2, 50, "radar"),
            ])
            write_csv(links, ("video_file", "vehicle_id", "track_id"), [("video.mp4", "vehicle-1", 10)])
            speed_headers = ("video_file", "track_id", "timestamp_s", "speed_kmh", "geometry")
            write_csv(predicted, speed_headers, [("video.mp4", 10, 0.9, 100, "configured"),
                                                 ("video.mp4", 10, 1.1, 20, "configured"),
                                                 ("video.mp4", 10, 1.9, 24, "configured")])
            report = evaluate_speeds(truth, predicted, links)
            self.assertEqual(report["coverage"], 0.5)
            self.assertEqual(report["mae_kmh"], 2)
            self.assertEqual(report["measurements"][1]["status"], "unmapped_vehicle")
            write_csv(predicted, speed_headers, [("video.mp4", 10, 1.5, 20, "illustrative")])
            with self.assertRaisesRegex(ValueError, "camera"):
                evaluate_speeds(truth, predicted, links)
