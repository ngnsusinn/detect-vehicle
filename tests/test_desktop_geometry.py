import unittest

from vehicle_detection.inference.desktop_geometry import ImageViewport, make_config, positive_number


class DesktopGeometryTests(unittest.TestCase):
    def test_letterbox_preserves_original_pixel_coordinates(self):
        view = ImageViewport.fit(1920, 1080, 1000, 700)
        self.assertEqual((view.width, view.height, view.top), (1000, 562, 69))
        self.assertIsNone(view.source_point(420, 35))
        self.assertEqual(view.source_point(500, 350), [960, 540])
        self.assertEqual(view.canvas_point([960, 540]), (500, 350))

    def test_count_only_config_preserves_line_without_dummy_speed_geometry(self):
        lines = {"a": {"line_id": "a", "points_px": [[20, 80], [140, 80]], "speed_limit_kmh": 40}}
        count_only = make_config("camera-36", [160, 160], [], lines)
        self.assertFalse(count_only["speed_enabled"])
        self.assertNotIn("target_points_m", count_only)
        calibrated = make_config("camera-36", [160, 160], [[10, 10], [150, 10], [150, 150], [10, 150]],
                                 lines, dimensions=(positive_number("7,5", "Rộng"), 20))
        self.assertTrue(calibrated["speed_enabled"])
        self.assertEqual(calibrated["target_points_m"][2], [7.5, 20])

    def test_map_profile_preserves_calibration_when_replacing_count_line(self):
        profile = {
            "camera_id": "camera-36",
            "image_size": [160, 160],
            "speed_source": "map_estimate",
            "source_points_px": [[40, 45], [115, 45], [150, 130], [10, 130]],
            "target_points_m": [[0, 0], [8, 0.2], [9, 14], [-0.5, 13]],
        }
        line = {"line_id": "main", "points_px": [[20, 80], [140, 80]]}
        config = make_config("camera-36", (160, 160), [], {"main": line}, speed_profile=profile)
        self.assertEqual(config["target_points_m"], profile["target_points_m"])
        self.assertEqual(config["count_lines"], [line])
        self.assertNotIn("count_lines", profile)
        for camera, size in (("camera-35", (160, 160)), ("camera-36", (320, 160))):
            with self.subTest(camera=camera, size=size), self.assertRaises(ValueError):
                make_config(camera, size, [], {"main": line}, speed_profile=profile)

    def test_rejects_nonfinite_or_zero_dimensions(self):
        for value in ("NaN", "inf", "0", "-1"):
            with self.subTest(value=value), self.assertRaises(ValueError):
                positive_number(value, "Rộng")
