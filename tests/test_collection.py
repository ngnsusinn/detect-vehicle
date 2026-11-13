from datetime import datetime
from pathlib import Path
import tempfile
import unittest

from vehicle_detection.collection.storage import get_slot_info, get_current_storage_directory
from vehicle_detection.collection.extractor import split_for_workstations
from vehicle_detection.paths import RAW_FRAMES_DIR, PROJECT_ROOT


class CollectionTests(unittest.TestCase):
    def test_hour_boundaries_and_directory_creation(self):
        self.assertEqual(get_slot_info(datetime(2026, 11, 13, 0)), (0, 1, "00h-01h"))
        now = datetime(2026, 11, 13, 23, 59)
        self.assertEqual(get_slot_info(now), (23, 24, "23h-24h"))
        with tempfile.TemporaryDirectory() as temp:
            folder, slot = get_current_storage_directory(temp, "cam01", now)
            self.assertEqual(slot, "2026-11-13_23h-24h")
            self.assertEqual(Path(folder), Path(temp) / "cam01" / slot)
            self.assertTrue(Path(folder).is_dir())

    def test_default_frames_are_under_project_data(self):
        self.assertEqual(RAW_FRAMES_DIR, PROJECT_ROOT / "data/raw/frames")

    def test_split_preserves_sources_and_assigns_each_image_once(self):
        with tempfile.TemporaryDirectory() as temp:
            raw, batches = Path(temp) / "raw", Path(temp) / "batches"
            raw.mkdir()
            for index in range(5):
                (raw / f"{index}.jpg").write_bytes(str(index).encode())
            (raw / "manifest.jsonl").write_text("{}", encoding="utf-8")
            split_for_workstations(raw, batches, num_machines=3)
            copies = sorted(batches.glob("*/*.jpg"))
            self.assertEqual(len(copies), 5)
            self.assertEqual(len(list(raw.glob("*.jpg"))), 5)
            self.assertEqual({p.name for p in copies}, {p.name for p in raw.glob("*.jpg")})
            self.assertFalse(list(batches.glob("*/*.jsonl")))


if __name__ == "__main__":
    unittest.main()
