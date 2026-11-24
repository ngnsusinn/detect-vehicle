"""Package a validated YOLO dataset and its Colab training entry point."""
import argparse
import json
from pathlib import Path
import tempfile
from zipfile import ZIP_DEFLATED, ZIP_STORED, ZipFile

from vehicle_detection.data.validate import IMAGE_SUFFIXES, SPLITS, validate_dataset
from vehicle_detection.paths import PROJECT_ROOT


def package_dataset(dataset, output):
    result = validate_dataset(dataset)
    if not result.ok:
        raise ValueError("\n".join(result.errors))
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=output.parent) as temp:
        archive = Path(temp) / "dataset.zip"
        with ZipFile(archive, "w", ZIP_DEFLATED) as bundle:
            bundle.write(PROJECT_ROOT / "training/train_colab.py", "train_colab.py")
            bundle.write(dataset / "classes.txt", "dataset/classes.txt")
            bundle.writestr("dataset/dataset_check.json", json.dumps(result.as_dict(), ensure_ascii=False, indent=2))
            for split in SPLITS:
                for image in sorted((dataset / "images" / split).iterdir()):
                    if image.is_file() and image.suffix.lower() in IMAGE_SUFFIXES:
                        bundle.write(image, f"dataset/images/{split}/{image.name}", ZIP_STORED)
                for label in sorted((dataset / "labels" / split).glob("*.txt")):
                    if label.is_file():
                        bundle.write(label, f"dataset/labels/{split}/{label.name}")
        archive.replace(output)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        package_dataset(args.dataset, args.output)
    except (OSError, ValueError) as exc:
        parser.error(str(exc))
    print(f"Colab ZIP: {args.output.resolve()}")


if __name__ == "__main__":
    main()
