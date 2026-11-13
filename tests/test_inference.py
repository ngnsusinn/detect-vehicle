import json
from pathlib import Path
import tempfile
import unittest

from vehicle_detection.inference.calibration import load_calibration
from vehicle_detection.inference.counting import LineCrossingCounter
from vehicle_detection.inference.speed import HomographySpeedEstimator
from vehicle_detection.paths import PROJECT_ROOT


class CalibrationTests(unittest.TestCase):
    def test_example_and_invalid_geometry(self):
        example = PROJECT_ROOT / "configs/cameras/cam01.example.json"
        config = load_calibration(example)
        self.assertEqual(config["image_size"], [1920, 1080])
        changes = [
            {"image_size": [0, 1080]},
            {"source_points_px": [[0, 0], [1, 1], [2, 2], [3, 3]]},
            {"target_points_m": [[0, 0], [8, 25], [8, 0], [0, 25]]},
            {"count_line_px": [[10, 10], [10, 10]]},
            {"count_line_px": [[-1, 10], [50, 10]]},
        ]
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "camera.json"
            for change in changes:
                with self.subTest(change=change):
                    path.write_text(json.dumps(config | change), encoding="utf-8")
                    with self.assertRaises(ValueError):
                        load_calibration(path)


class InferenceRegressionTests(unittest.TestCase):
    def test_count_both_directions_and_only_once_per_track(self):
        counter = LineCrossingCounter((0, 5), (10, 5))
        self.assertIsNone(counter.update(1, (5, 4), "car"))
        self.assertEqual(counter.update(1, (5, 6), "car"), "IN")
        self.assertIsNone(counter.update(1, (5, 4), "car"))
        counter.update(2, (5, 6), "truck")
        self.assertEqual(counter.update(2, (5, 4), "truck"), "OUT")
        self.assertEqual((counter.total_in, counter.total_out), (1, 1))
        self.assertEqual(dict(counter.class_counts), {"car": 1, "truck": 1})

    def test_identity_geometry_one_meter_per_frame_at_ten_fps(self):
        points = [(0, 0), (10, 0), (10, 10), (0, 10)]
        estimator = HomographySpeedEstimator(points, points, fps=10, speed_limit_kmh=30, ema_alpha=1, window_frames=2)
        self.assertEqual(estimator.update(1, (1, 1), 1), (0, False))
        speed, overspeed = estimator.update(1, (2, 1), 2)
        self.assertAlmostEqual(speed, 36, places=4)
        self.assertTrue(overspeed)


if __name__ == "__main__":
    unittest.main()
