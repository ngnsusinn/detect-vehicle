"""Assemble an explicitly split YOLO dataset from Label Studio archives."""
import argparse
import csv
import re
import shutil
import sys
import tempfile
from pathlib import Path, PurePosixPath
from zipfile import BadZipFile, ZipFile

from PIL import Image

from vehicle_detection.classes import CLASS_NAMES
from vehicle_detection.data.validate import IMAGE_SUFFIXES, SPLITS, validate_dataset

FRAME_NUMBER = re.compile(r"_(\d+)$")
UPLOAD_PREFIX = re.compile(r"^[0-9a-f]{8}-", re.IGNORECASE)


def index_files(paths, suffixes):
    files = {}
    for path in paths:
        if path.suffix.lower() in suffixes:
            if path.stem in files:
                raise ValueError(f"Nhiều tệp cùng tên gốc: {path.stem}")
            files[path.stem] = path
    return files


def convert_label(text, class_names):
    lines = []
    for line in text.splitlines():
        if not line.strip():
            continue
        fields = line.split()
        if len(fields) != 5:
            raise ValueError("Nhãn YOLO detection cần đúng 5 cột")
        source_id = int(fields[0])
        if not 0 <= source_id < len(class_names):
            raise ValueError(f"ID lớp {source_id} nằm ngoài bảng lớp của gói xuất")
        name = class_names[source_id]
        if name not in CLASS_NAMES:
            raise ValueError(f"BOX dùng lớp ngoài danh mục phương tiện: {name}")
        lines.append(" ".join([str(CLASS_NAMES.index(name)), *fields[1:]]))
    return "".join(f"{line}\n" for line in lines)


def prepare_dataset(batches, dataset_dir, images_dir=None, fallback_classes=None):
    """Publish a validated dataset and manifest together into a new directory."""
    destination = Path(dataset_dir).resolve()
    if destination.exists():
        raise ValueError(f"Thư mục đích đã tồn tại: {destination}")
    originals = index_files(Path(images_dir).iterdir(), IMAGE_SUFFIXES) if images_dir else {}
    destination.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=destination.parent) as temp:
        stage = Path(temp) / "dataset"
        for split in SPLITS:
            (stage / "images" / split).mkdir(parents=True)
            (stage / "labels" / split).mkdir(parents=True)
        (stage / "classes.txt").write_text("\n".join(CLASS_NAMES) + "\n", encoding="utf-8")
        seen = set()
        with (stage / "splits.csv").open("w", encoding="utf-8", newline="") as stream:
            manifest = csv.writer(stream)
            manifest.writerow(["image_name", "split", "archive", "frame_range", "source_image", "source_label"])
            for split, archive, frame_range in batches:
                if split not in SPLITS:
                    raise ValueError(f"Tập dữ liệu không hợp lệ: {split}")
                written = 0
                with ZipFile(archive) as bundle:
                    entries = [PurePosixPath(entry.filename) for entry in bundle.infolist() if not entry.is_dir()]
                    if any("\\" in str(entry) or ":" in entry.name for entry in entries):
                        raise ValueError(f"{archive}: tên tệp không tương thích giữa Windows và Colab")
                    images = index_files(entries, IMAGE_SUFFIXES)
                    labels = index_files((p for p in entries if p.name != "classes.txt"), {".txt"})
                    class_file = next((p for p in entries if p.name == "classes.txt"), None)
                    if class_file:
                        class_text = bundle.read(str(class_file)).decode("utf-8-sig")
                    elif fallback_classes:
                        class_text = Path(fallback_classes).read_text(encoding="utf-8-sig")
                    else:
                        raise ValueError(f"{archive}: thiếu classes.txt, cần --fallback-classes")
                    class_names = [line.strip() for line in class_text.splitlines()]
                    if not class_names or "" in class_names or len(set(class_names)) != len(class_names):
                        raise ValueError(f"{archive}: bảng lớp rỗng hoặc có tên lớp lặp")
                    for stem, label in sorted(labels.items()):
                        canonical = UPLOAD_PREFIX.sub("", stem)
                        number = FRAME_NUMBER.search(canonical)
                        if frame_range and (number is None or not frame_range[0] <= int(number[1]) <= frame_range[1]):
                            continue
                        if canonical.casefold() in seen:
                            raise ValueError(f"Ảnh xuất hiện nhiều lần trong dataset: {canonical}")
                        image = images.get(stem) or images.get(canonical)
                        original = originals.get(canonical) or originals.get(stem)
                        if image:
                            source = bundle.open(str(image))
                            source_ref = f"{archive}!{image}"
                        elif original:
                            source = original.open("rb")
                            source_ref = str(original)
                            image = original
                        else:
                            raise ValueError(f"{archive}!{label}: không tìm thấy ảnh tương ứng")
                        image_path = stage / "images" / split / f"{canonical}{image.suffix.lower()}"
                        with source, image_path.open("wb") as target:
                            shutil.copyfileobj(source, target)
                        with Image.open(image_path) as decoded:
                            decoded.load()
                        try:
                            content = convert_label(bundle.read(str(label)).decode("utf-8-sig"), class_names)
                        except ValueError as exc:
                            raise ValueError(f"{archive}!{label}: {exc}") from exc
                        (stage / "labels" / split / f"{canonical}.txt").write_text(content, encoding="utf-8")
                        interval = "-".join(map(str, frame_range)) if frame_range else "all"
                        manifest.writerow([image_path.name, split, archive, interval, source_ref, label])
                        seen.add(canonical.casefold())
                        written += 1
                if not written:
                    raise ValueError(f"{archive}: không có nhãn được chọn cho {split}")
        result = validate_dataset(stage)
        if not result.ok:
            raise ValueError("\n".join(result.errors))
        if destination.exists():
            raise ValueError(f"Thư mục đích đã tồn tại: {destination}")
        stage.rename(destination)
    return result


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--batch", action="append", nargs=3, required=True, metavar=("SPLIT", "ZIP", "RANGE"),
                        help="Lặp lại cho từng đoạn, RANGE là all hoặc FIRST-LAST theo số cuối tên ảnh")
    parser.add_argument("--images", type=Path, help="Thư mục ảnh gốc cho gói chỉ có nhãn")
    parser.add_argument("--fallback-classes", type=Path, help="Bảng ID lớp đã xác nhận cho gói thiếu classes.txt")
    parser.add_argument("--output", type=Path, required=True, help="Thư mục dataset mới")
    args = parser.parse_args()
    batches = []
    for split, archive, interval in args.batch:
        if split not in SPLITS:
            parser.error(f"Tập dữ liệu không hợp lệ: {split}")
        match = re.fullmatch(r"(\d+)-(\d+)", interval)
        if interval != "all" and (not match or int(match[1]) > int(match[2])):
            parser.error(f"Khoảng frame không hợp lệ: {interval}")
        batches.append((split, Path(archive).resolve(), tuple(map(int, match.groups())) if match else None))
    try:
        result = prepare_dataset(batches, args.output, args.images, args.fallback_classes)
    except (BadZipFile, OSError, ValueError) as exc:
        parser.error(str(exc))
    for split, counts in result.counts.items():
        print(f"{split}: {counts['images']} ảnh, {sum(counts['objects'].values())} bbox")
    print(f"Dataset: {args.output.resolve()}")


if __name__ == "__main__":
    main()
