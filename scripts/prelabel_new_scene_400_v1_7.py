from __future__ import annotations

from pathlib import Path
import json

from ultralytics import YOLO


ROOT = Path(__file__).resolve().parents[1]
BATCH = (
    ROOT
    / "datasets/sorting_two_chutes_supplement/review_expansion_400_v1_7"
)
MODEL = (
    ROOT
    / "runs/detect/runs/sorting_yolo/"
    "two_chutes_prelabel_calibration_v1/weights/best.pt"
)


def main() -> None:
    images = sorted((BATCH / "images").glob("*.jpg"))
    if len(images) != 400:
        raise RuntimeError(f"Expected 400 images, found {len(images)}")
    model = YOLO(str(MODEL))
    predictions = {}
    batch_size = 25
    for start in range(0, len(images), batch_size):
        batch = images[start : start + batch_size]
        results = model.predict(
            [str(path) for path in batch],
            imgsz=640,
            conf=0.03,
            device="mps",
            verbose=False,
        )
        for image_path, result in zip(batch, results):
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
        print(f"predicted {min(start + batch_size, len(images))}/{len(images)}")
    output = BATCH / "candidate_predictions_calibrated.json"
    output.write_text(
        json.dumps(predictions, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps({"images": len(images), "output": str(output)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
