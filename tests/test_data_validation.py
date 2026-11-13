import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
import xml.etree.ElementTree as ET

import yaml

from vehicle_detection.classes import CLASS_NAMES
from vehicle_detection.data.validate import validate_dataset, write_training_config
from vehicle_detection.paths import PROJECT_ROOT


class DatasetValidationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / "dataset"
        self.root.mkdir()
        (self.root / "classes.txt").write_text("\n".join(CLASS_NAMES) + "\n", encoding="utf-8")
        for split in ("train", "val", "test"):
            for kind in ("images", "labels"):
                (self.root / kind / split).mkdir(parents=True)
            # The validator intentionally checks bytes and labels, not image decoding.
            (self.root / "images" / split / "frame.jpg").write_bytes(f"image-fixture-{split}".encode())
            (self.root / "labels" / split / "frame.txt").write_text("1 0.5 0.5 0.2 0.4\n", encoding="utf-8")

    def test_valid_dataset_and_reviewed_negative(self):
        (self.root / "labels/val/frame.txt").write_text("", encoding="utf-8")
        result = validate_dataset(self.root)
        self.assertTrue(result.ok, result.errors)
        self.assertEqual(result.counts["train"]["objects"]["car"], 1)
        self.assertEqual(result.counts["val"]["empty_labels"], 1)

    def test_missing_label_is_not_a_negative_image(self):
        (self.root / "labels/train/frame.txt").unlink()
        result = validate_dataset(self.root)
        self.assertFalse(result.ok)
        self.assertTrue(any("thiếu nhãn" in error for error in result.errors))

    def test_invalid_labels(self):
        for row in ("8 0.5 0.5 0.2 0.2", "1 nan 0.5 0.2 0.2", "1 0.1 0.5 0.8 0.2", "1 0.5 0.5 0 0.2", "1 0.5 0.5 0.2"):
            with self.subTest(row=row):
                (self.root / "labels/train/frame.txt").write_text(row, encoding="utf-8")
                self.assertFalse(validate_dataset(self.root).ok)

    def test_duplicate_content_across_splits_even_with_different_names(self):
        content = (self.root / "images/train/frame.jpg").read_bytes()
        (self.root / "images/test/renamed.png").write_bytes(content)
        (self.root / "labels/test/renamed.txt").write_text("", encoding="utf-8")
        result = validate_dataset(self.root)
        self.assertTrue(any("trùng nội dung giữa" in error for error in result.errors))

    def test_wrong_class_order_and_orphan_label(self):
        (self.root / "classes.txt").write_text("\n".join(reversed(CLASS_NAMES)), encoding="utf-8")
        (self.root / "labels/test/orphan.txt").write_text("", encoding="utf-8")
        result = validate_dataset(self.root)
        self.assertTrue(any("thứ tự lớp" in error for error in result.errors))
        self.assertTrue(any("không có ảnh" in error for error in result.errors))

    def test_generated_config_is_absolute_and_does_not_change_template(self):
        output = Path(self.temp.name) / "output/data.local.yaml"
        write_training_config(self.root, output)
        config = yaml.safe_load(output.read_text(encoding="utf-8"))
        self.assertEqual(Path(config["path"]), self.root.resolve())
        self.assertEqual(list(config["names"].values()), list(CLASS_NAMES))
        self.assertEqual(config["test"], "images/test")

    def test_cli_failure_writes_report_but_not_training_config(self):
        (self.root / "labels/train/frame.txt").unlink()
        report = Path(self.temp.name) / "report.json"
        config = Path(self.temp.name) / "data.local.yaml"
        process = subprocess.run(
            [sys.executable, "-m", "vehicle_detection.data.validate", "--dataset", str(self.root),
             "--report", str(report), "--config-output", str(config)],
            cwd=PROJECT_ROOT, capture_output=True,
        )
        self.assertEqual(process.returncode, 1, process.stderr)
        self.assertTrue(report.exists(), process.stderr.decode("utf-8", errors="replace"))
        self.assertFalse(json.loads(report.read_text(encoding="utf-8"))["ok"])
        self.assertFalse(config.exists())

    def test_class_schema_agrees_across_annotation_and_training(self):
        root = PROJECT_ROOT / "data/vehicle_detection"
        self.assertEqual((root / "classes.txt").read_text(encoding="utf-8").splitlines(), list(CLASS_NAMES))
        config = yaml.safe_load((root / "data.yaml").read_text(encoding="utf-8"))
        self.assertEqual(config["names"], dict(enumerate(CLASS_NAMES)))
        template = ET.parse(PROJECT_ROOT / "annotation/label_studio_template.xml")
        self.assertEqual([label.attrib["value"] for label in template.findall(".//Label")], list(CLASS_NAMES))


if __name__ == "__main__":
    unittest.main()
