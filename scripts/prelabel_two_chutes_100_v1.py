from __future__ import annotations

from pathlib import Path
import json

from ultralytics import YOLO


ROOT = Path("/Users/lixing.guo/Documents/机械臂")
BATCH = ROOT / "datasets/sorting_two_chutes_supplement/review_100_v1"
MODELS = {
    "original": ROOT / "runs/sorting_yolo/sorting_yolo11n_v1/weights/best.pt",
    "calibrated": (
        ROOT
        / "runs/detect/runs/sorting_yolo/two_chutes_prelabel_calibration_v1/weights/best.pt"
    ),
}


def main() -> None:
    images = sorted((BATCH / "images").glob("*.jpg"))
    outputs = {}
    for model_name, model_path in MODELS.items():
        model = YOLO(str(model_path))
        results = model.predict(
            [str(path) for path in images],
            imgsz=640,
            conf=0.03,
            device="mps",
            verbose=False,
        )
        rows = {}
        for image_path, result in zip(images, results):
            detections = []
            if result.boxes is not None:
                for cls, conf, box in zip(
                    result.boxes.cls.tolist(),
                    result.boxes.conf.tolist(),
                    result.boxes.xyxy.tolist(),
                ):
                    detections.append(
                        {
                            "class_id": int(cls),
                            "class_name": result.names[int(cls)],
                            "confidence": round(float(conf), 4),
                            "box": [round(float(value), 2) for value in box],
                        }
                    )
            rows[image_path.name] = detections
        output = BATCH / f"candidate_predictions_{model_name}.json"
        output.write_text(
            json.dumps(rows, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        outputs[model_name] = str(output)
    print(json.dumps({"images": len(images), "outputs": outputs}))


if __name__ == "__main__":
    main()
