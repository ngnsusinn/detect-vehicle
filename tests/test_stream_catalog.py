import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

from vehicle_detection.inference.demo import main
from vehicle_detection.inference.stream_catalog import load_stream


class StreamCatalogTests(unittest.TestCase):
    def test_select_camera_by_id_and_use_trained_model(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            path = root / "cameras.json"
            source = "rtsp://example:placeholder@localhost:554/camera"
            path.write_text(json.dumps({"success": True, "data": [
                {"ID": 39, "STSPLINK": "rtsp://localhost/other"},
                {"ID": 40, "TEN": "Camera 40\nGiao thông", "STSPLINK": source},
            ]}), encoding="utf-8")
            weights = root / "models/vehicle_detection/best.pt"
            weights.parent.mkdir(parents=True)
            weights.touch()
            args = ["demo", "--camera-list", str(path), "--camera-id", "40", "--headless"]
            with patch.object(sys, "argv", args), patch.object(sys, "stdout", io.TextIOWrapper(io.BytesIO())) as output, \
                 patch("vehicle_detection.inference.demo.PROJECT_ROOT", root), \
                 patch("vehicle_detection.inference.demo.run_pipeline") as pipeline:
                main()
                output.flush()
                printed = output.buffer.getvalue().decode()
            self.assertIn("Camera 40 Giao thông", printed)
            self.assertNotIn(source, printed)
            self.assertEqual(pipeline.call_args.args[:2], (source, str(weights)))
            self.assertEqual(pipeline.call_args.kwargs["stream_id"], "camera-40")

    def test_rejects_unknown_duplicate_inactive_and_invalid_sources(self):
        for entries, message in (
            ([], "Tìm thấy 0"),
            ([{"ID": 40}, {"ID": 40}], "Tìm thấy 2"),
            ([{"ID": 40, "DELETED": 1}], "ngưng hoạt động"),
            ([{"ID": 40, "STSPLINK": "file:///some/path"}], "RTSP"),
        ):
            with self.subTest(message=message), tempfile.TemporaryDirectory() as folder:
                path = Path(folder) / "source.txt"
                path.write_text(json.dumps({"data": entries}), encoding="utf-8")
                with self.assertRaisesRegex(ValueError, message):
                    load_stream(path, 40)
