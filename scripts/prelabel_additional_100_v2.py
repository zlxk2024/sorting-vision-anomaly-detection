from __future__ import annotations

from pathlib import Path
import json

from ultralytics import YOLO


ROOT = Path(__file__).resolve().parents[1]
BATCH = (
    ROOT / "datasets/sorting_two_chutes_supplement/review_additional_100_v2"
)
MODELS = {
    "v1": ROOT / "runs/sorting_yolo/sorting_yolo11n_v1/weights/best.pt",
    "calibrated": (
        ROOT
        / "runs/detect/runs/sorting_yolo/"
        "two_chutes_prelabel_calibration_v1/weights/best.pt"
    ),
}


def main() -> None:
    images = sorted((BATCH / "images").glob("*.jpg"))
    if len(images) != 200:
        raise RuntimeError(f"Expected 200 images, found {len(images)}")

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
        predictions = {}
        for image_path, result in zip(images, results):
            detections = []
            if result.boxes is not None:
                for cls, confidence, box in zip(
                    result.boxes.cls.tolist(),
                    result.boxes.conf.tolist(),
                    result.boxes.xyxy.tolist(),
                ):
                    detections.append(
                        {
                            "class_id": int(cls),
                            "class_name": result.names[int(cls)],
                            "confidence": round(float(confidence), 4),
                            "box": [
                                round(float(value), 2) for value in box
                            ],
                        }
                    )
            predictions[image_path.name] = detections
        output_path = BATCH / f"candidate_predictions_{model_name}.json"
        output_path.write_text(
            json.dumps(predictions, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        outputs[model_name] = str(output_path)
    print(json.dumps(outputs, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
