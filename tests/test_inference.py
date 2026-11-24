import json
from pathlib import Path
import tempfile
import unittest

from vehicle_detection.inference.calibration import load_calibration
from vehicle_detection.inference.counting import LineCrossingCounter
from vehicle_detection.inference.speed import HomographySpeedEstimator
from vehicle_detection.inference.timing import FrameClock
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
            {"count_lines": [{"line_id": "../lane", "points_px": [[10, 10], [50, 10]]}]},
            {"count_lines": [{"line_id": "a", "points_px": [[10, 10], [50, 10]], "speed_limit_kmh": 0}]},
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

    def test_touching_line_requires_transition_between_sides(self):
        counter = LineCrossingCounter((0, 5), (10, 5))
        for point in ((5, 4), (5, 5), (5, 4), (5, 5)):
            self.assertIsNone(counter.update(1, point, "car"))
        self.assertEqual(counter.update(1, (5, 6), "car"), "IN")
        self.assertIsNone(counter.update(2, (11, 4), "car"))
        self.assertIsNone(counter.update(2, (11, 6), "car"))

    def test_speed_starts_fresh_after_leaving_calibrated_region(self):
        points = [(0, 0), (10, 0), (10, 10), (0, 10)]
        estimator = HomographySpeedEstimator(points, points, fps=10, window_frames=2)
        estimator.update(1, (1, 1), 1)
        self.assertAlmostEqual(estimator.update(1, (2, 1), 2)[0], 36)
        self.assertEqual(estimator.update(1, (11, 1), 3), (0, False))
        self.assertNotIn(1, estimator.smoothed_speeds)
        self.assertEqual(estimator.update(1, (4, 1), 4), (0, False))
        self.assertAlmostEqual(estimator.update(1, (5, 1), 5)[0], 36)

    def test_speed_uses_pts_for_variable_frame_intervals(self):
        points = [(0, 0), (10, 0), (10, 10), (0, 10)]
        estimator = HomographySpeedEstimator(points, points, fps=10, window_frames=2)
        estimator.update(1, (1, 1), 1, timestamp_s=0.0)
        self.assertAlmostEqual(estimator.update(1, (2, 1), 2, timestamp_s=0.2)[0], 18)

    def test_clock_selects_once_and_rejects_a_pts_regression(self):
        clock = FrameClock(10, "auto")
        self.assertEqual(clock.timestamp(1, 50), 0)
        self.assertEqual(clock.timestamp(2, 250), 0.2)
        self.assertEqual(clock.mode, "pts")
        with self.assertRaisesRegex(ValueError, "PTS"):
            clock.timestamp(3, 200)
        fallback = FrameClock(10, "auto")
        self.assertEqual(fallback.timestamp(1, 0), 0)
        self.assertEqual(fallback.timestamp(2, 0), 0.1)
        self.assertEqual(fallback.timestamp(3, 350), 0.2)


if __name__ == "__main__":
    unittest.main()
