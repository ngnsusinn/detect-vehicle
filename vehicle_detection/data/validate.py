"""Read-only checks for the project's flat YOLO dataset layout (standard library only)."""
import argparse
from collections import Counter
from dataclasses import dataclass, field
import hashlib
import json
import math
from pathlib import Path
import sys

from vehicle_detection.classes import CLASS_NAMES
from vehicle_detection.paths import DATASET_DIR

SPLITS = ("train", "val", "test")
IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png"}


@dataclass
class ValidationResult:
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    counts: dict = field(default_factory=dict)

    @property
    def ok(self):
        return not self.errors

    def as_dict(self):
        return {"ok": self.ok, "errors": self.errors,
                "warnings": self.warnings, "counts": self.counts}


def validate_dataset(dataset_dir):
    root = Path(dataset_dir).resolve()
    result = ValidationResult()
    try:
        actual_classes = (root / "classes.txt").read_text(encoding="utf-8-sig").splitlines()
        if actual_classes != list(CLASS_NAMES):
            result.errors.append("classes.txt: thứ tự lớp không khớp 8 lớp chuẩn của dự án")
    except (OSError, UnicodeError) as exc:
        result.errors.append(f"classes.txt: không đọc được ({exc})")

    seen_hashes = {}
    for split in SPLITS:
        image_dir, label_dir = root / "images" / split, root / "labels" / split
        objects = Counter()
        stats = {"images": 0, "labels": 0, "empty_labels": 0, "objects": {}}
        result.counts[split] = stats
        if not image_dir.is_dir() or not label_dir.is_dir():
            result.errors.append(f"{split}: thiếu images/{split} hoặc labels/{split}")
            continue
        for folder in (image_dir, label_dir):
            if any(item.is_dir() for item in folder.iterdir()):
                result.errors.append(f"{folder.relative_to(root)}: cần thư mục phẳng, không có thư mục con")
        images = sorted(p for p in image_dir.iterdir() if p.is_file() and p.suffix.lower() in IMAGE_SUFFIXES)
        labels = {p.stem: p for p in label_dir.iterdir() if p.is_file() and p.suffix == ".txt"}
        stats["images"], stats["labels"] = len(images), len(labels)
        if not images:
            result.errors.append(f"{split}: chưa có ảnh JPG/JPEG/PNG")
        image_stems = set()
        for image in images:
            if image.stem in image_stems:
                result.errors.append(f"{split}/{image.stem}: nhiều ảnh dùng chung tên gốc")
            image_stems.add(image.stem)
            if image.stem not in labels:
                result.errors.append(f"images/{split}/{image.name}: thiếu nhãn .txt tương ứng")
            try:
                with image.open("rb") as stream:
                    digest = hashlib.file_digest(stream, "sha256").hexdigest()
                previous = seen_hashes.get(digest)
                if previous is not None and previous[0] != split:
                    result.errors.append(f"Ảnh trùng nội dung giữa {previous[1]} và {image.relative_to(root)}")
                elif previous is not None:
                    result.warnings.append(f"Ảnh trùng nội dung trong {split}: {image.name}")
                else:
                    seen_hashes[digest] = (split, str(image.relative_to(root)))
                if image.stat().st_size == 0:
                    result.errors.append(f"{image.relative_to(root)}: ảnh rỗng")
            except OSError as exc:
                result.errors.append(f"{image.relative_to(root)}: không đọc được ({exc})")

        for stem, label in sorted(labels.items()):
            relative = label.relative_to(root)
            if stem not in image_stems:
                result.errors.append(f"{relative}: không có ảnh tương ứng")
            try:
                lines = label.read_text(encoding="utf-8-sig").splitlines()
            except (OSError, UnicodeError) as exc:
                result.errors.append(f"{relative}: không đọc được ({exc})")
                continue
            if not any(line.strip() for line in lines):
                stats["empty_labels"] += 1
            for line_no, line in enumerate(lines, 1):
                if not line.strip():
                    continue
                where = f"{relative}:{line_no}"
                parts = line.split()
                try:
                    if len(parts) != 5:
                        raise ValueError("cần đúng 5 cột: class_id x_center y_center width height")
                    class_id = int(parts[0])
                    if not 0 <= class_id < len(CLASS_NAMES):
                        raise ValueError("class_id phải từ 0 đến 7")
                    x, y, width, height = map(float, parts[1:])
                    if not all(math.isfinite(value) for value in (x, y, width, height)):
                        raise ValueError("tọa độ phải là số hữu hạn")
                    if not (0 <= x <= 1 and 0 <= y <= 1 and 0 < width <= 1 and 0 < height <= 1):
                        raise ValueError("tọa độ phải chuẩn hóa [0, 1], kích thước phải lớn hơn 0")
                    if min(x - width / 2, y - height / 2) < -1e-6 or max(x + width / 2, y + height / 2) > 1 + 1e-6:
                        raise ValueError("bounding box vượt biên ảnh")
                    objects[CLASS_NAMES[class_id]] += 1
                except ValueError as exc:
                    result.errors.append(f"{where}: {exc}")
        stats["objects"] = {name: objects[name] for name in CLASS_NAMES}
        missing = [name for name in CLASS_NAMES if not objects[name]]
        if missing:
            result.warnings.append(f"{split}: chưa có đối tượng của lớp {', '.join(missing)}")
        if split == "train" and not objects:
            result.errors.append("train: cần ít nhất một bounding box hợp lệ để huấn luyện detector")
    return result


def write_training_config(dataset_dir, output_path):
    """Write an absolute dataset path without changing the portable template."""
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    lines = [f"path: {json.dumps(Path(dataset_dir).resolve().as_posix(), ensure_ascii=False)}"]
    lines.extend(f"{split}: images/{split}" for split in SPLITS)
    lines.append("names:")
    lines.extend(f"  {index}: {name}" for index, name in enumerate(CLASS_NAMES))
    output.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description="Kiểm tra dataset YOLO 8 lớp phương tiện")
    parser.add_argument("--dataset", type=Path, default=DATASET_DIR)
    parser.add_argument("--report", type=Path, help="Lưu báo cáo kiểm tra JSON")
    parser.add_argument("--config-output", type=Path, help="Tạo YAML có path tuyệt đối khi kiểm tra thành công")
    args = parser.parse_args()
    result = validate_dataset(args.dataset)
    for split, stats in result.counts.items():
        print(f"{split}: {stats['images']} ảnh, {stats['labels']} nhãn, {stats['empty_labels']} nhãn rỗng")
    for warning in result.warnings:
        print(f"WARNING: {warning}")
    for error in result.errors:
        print(f"ERROR: {error}")
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(result.as_dict(), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if result.ok and args.config_output:
        write_training_config(args.dataset, args.config_output)
        print(f"Đã tạo cấu hình: {args.config_output.resolve()}")
    print("PASS" if result.ok else "FAIL")
    return 0 if result.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
