from __future__ import annotations

from pathlib import Path
import argparse
import json

from ultralytics import YOLO


ROOT = Path(__file__).resolve().parents[1]
DATA_ROOT = ROOT / "datasets/sorting_yolo_v2_mixed"
CLASSES = ["parcel", "drawer_open", "drawer_closed", "chute", "bag"]


def metric_payload(metrics) -> dict:
    box = metrics.box
    class_rows = {}
    for index, class_name in enumerate(CLASSES):
        precision, recall, ap50, ap = box.class_result(index)
        class_rows[class_name] = {
            "precision": round(float(precision), 6),
            "recall": round(float(recall), 6),
            "map50": round(float(ap50), 6),
            "map50_95": round(float(ap), 6),
        }
    return {
        "overall": {
            "precision": round(float(box.mp), 6),
            "recall": round(float(box.mr), 6),
            "map50": round(float(box.map50), 6),
            "map50_95": round(float(box.map), 6),
        },
        "per_class": class_rows,
        "speed_ms_per_image": {
            key: round(float(value), 4)
            for key, value in metrics.speed.items()
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--weights", required=True)
    parser.add_argument("--tag", required=True)
    parser.add_argument("--imgsz", type=int, default=320)
    parser.add_argument("--batch", type=int, default=16)
    args = parser.parse_args()

    output_root = ROOT / "runs/sorting_yolo/evaluations" / args.tag
    output_root.mkdir(parents=True, exist_ok=True)
    model = YOLO(args.weights)
    results = {}
    datasets = {
        "all_test": DATA_ROOT / "data.yaml",
        "old_scene_test": DATA_ROOT / "data_old_test.yaml",
        "new_scene_test": DATA_ROOT / "data_new_test.yaml",
    }
    for name, data in datasets.items():
        metrics = model.val(
            data=str(data),
            split="test",
            imgsz=args.imgsz,
            batch=args.batch,
            device="cpu",
            workers=0,
            plots=name == "all_test",
            project=str(output_root),
            name=name,
            exist_ok=True,
            verbose=False,
        )
        results[name] = metric_payload(metrics)
        print(name, json.dumps(results[name]["overall"], ensure_ascii=False))

    payload = {
        "tag": args.tag,
        "weights": str(Path(args.weights).resolve()),
        "imgsz": args.imgsz,
        "batch": args.batch,
        "datasets": results,
    }
    (output_root / "metrics.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(output_root / "metrics.json")


if __name__ == "__main__":
    main()
