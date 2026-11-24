import csv
import io
from pathlib import Path
import tempfile
import unittest
from zipfile import ZipFile

from PIL import Image

from vehicle_detection.classes import CLASS_NAMES
from vehicle_detection.data.prepare import prepare_dataset


def image_bytes(color):
    stream = io.BytesIO()
    Image.new("RGB", (16, 16), color).save(stream, "JPEG")
    return stream.getvalue()


class PrepareDatasetTests(unittest.TestCase):
    def test_mixed_exports_remap_ids_and_pair_upload_names(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            originals = root / "originals"
            originals.mkdir()
            (originals / "cam_01.jpg").write_bytes(image_bytes("red"))
            classes = root / "classes.txt"
            classes.write_text("\n".join(CLASS_NAMES), encoding="utf-8")
            labels_only = root / "labels.zip"
            box = "0 0.5 0.5 0.25 0.25\n"
            with ZipFile(labels_only, "w") as archive:
                archive.writestr("cam_01.txt", box)
            with_images = root / "with_images.zip"
            with ZipFile(with_images, "w") as archive:
                archive.writestr("classes.txt", "car\nmotorcycle\ncertain\n")
                for number, color in ((2, "green"), (3, "blue")):
                    name = f"abcdef12-cam_{number:02}"
                    archive.writestr(f"images/{name}.jpg", image_bytes(color))
                    archive.writestr(f"labels/{name}.txt", box)
            batches = [("train", labels_only, None), ("val", with_images, (2, 2)), ("test", with_images, (3, 3))]
            output = root / "dataset"
            report = prepare_dataset(batches, output, originals, classes)
            self.assertTrue(report.ok)
            self.assertEqual((output / "labels/val/cam_02.txt").read_text(encoding="utf-8"), "1" + box[1:])
            self.assertTrue((output / "images/test/cam_03.jpg").is_file())
            with (output / "splits.csv").open(encoding="utf-8") as stream:
                self.assertEqual([row["split"] for row in csv.DictReader(stream)], ["train", "val", "test"])

    def test_missing_mapping_does_not_publish_partial_dataset(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            archive = root / "labels.zip"
            with ZipFile(archive, "w") as bundle:
                bundle.writestr("cam_01.txt", "0 0.5 0.5 0.25 0.25\n")
            output = root / "dataset"
            with self.assertRaisesRegex(ValueError, "classes.txt"):
                prepare_dataset([("train", archive, None)], output)
            self.assertFalse(output.exists())
