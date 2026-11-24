"""Train YOLO11 on a Colab GPU and record held-out detection metrics."""
import argparse
import json
from pathlib import Path
import shutil


def write_json(path, content):
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(content, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    temporary.replace(path)


def train(dataset, output, epochs, imgsz, batch, seed):
    import torch
    import ultralytics
    from ultralytics import YOLO

    if not torch.cuda.is_available():
        raise RuntimeError("Chưa có GPU CUDA. Hãy chuyển Colab sang GPU rồi chạy lại.")
    report = json.loads((dataset / "dataset_check.json").read_text(encoding="utf-8"))
    if not report["ok"]:
        raise ValueError("Dataset chưa đạt kiểm tra cấu trúc")
    names = (dataset / "classes.txt").read_text(encoding="utf-8").splitlines()
    config = {
        "path": dataset.as_posix(),
        "train": "images/train",
        "val": "images/val",
        "test": "images/test",
        "names": dict(enumerate(names)),
    }
    # JSON is also valid YAML and preserves absolute paths on the remote runtime.
    config_path = dataset / "data.yaml"
    config_path.write_text(json.dumps(config, indent=2) + "\n", encoding="utf-8")
    output.mkdir(parents=True, exist_ok=False)
    settings = {
        "data": str(config_path), "epochs": epochs, "imgsz": imgsz,
        "batch": batch, "seed": seed, "device": 0, "workers": 2,
    }
    write_json(output / "run.json", {
        "model": "yolo11n.yaml",
        "pretrained": False,
        "settings": settings,
        "gpu": torch.cuda.get_device_name(0),
        "torch_version": torch.__version__,
        "ultralytics_version": ultralytics.__version__,
        "dataset": report,
    })

    model = YOLO("yolo11n.yaml")
    model.train(**settings, pretrained=False, project=str(output), name="train", plots=True)
    best = output / "train" / "weights" / "best.pt"
    if not best.is_file():
        raise RuntimeError(f"Không tìm thấy checkpoint: {best}")
    metrics = YOLO(str(best)).val(
        data=str(config_path), split="test", device=0, imgsz=imgsz, batch=batch,
        workers=2, project=str(output), name="test", plots=True,
    )
    boxes = metrics.box
    evaluated = {int(class_id): index for index, class_id in enumerate(boxes.ap_class_index)}
    support = report["counts"]["test"]["objects"]
    by_class = {}
    for class_id, name in enumerate(names):
        index = evaluated.get(class_id)
        count = support[name]
        by_class[name] = {
            "ground_truth_boxes": count,
            "map50": (float(boxes.ap50[index]) if index is not None else 0.0) if count else None,
            "map50_95": (float(boxes.ap[index]) if index is not None else 0.0) if count else None,
        }
    write_json(output / "test_metrics.json", {
        "test_images": report["counts"]["test"]["images"],
        "precision": float(boxes.mp),
        "recall": float(boxes.mr),
        "map50": float(boxes.map50),
        "map50_95": float(boxes.map),
        "classes": by_class,
    })
    shutil.copyfile(best, output / "best.pt")
    print(f"Checkpoint: {output / 'best.pt'}", flush=True)
    print(f"Test: {output / 'test_metrics.json'}", flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--epochs", type=int, default=80)
    parser.add_argument("--imgsz", type=int, default=640)
    parser.add_argument("--batch", type=int, default=8)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()
    if min(args.epochs, args.imgsz, args.batch) <= 0:
        parser.error("epochs, imgsz và batch phải lớn hơn 0")
    train(args.dataset.resolve(), args.output.resolve(), args.epochs, args.imgsz, args.batch, args.seed)


if __name__ == "__main__":
    main()
