from __future__ import annotations

from pathlib import Path

from ultralytics import YOLO


ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "datasets/sorting_yolo_v2_mixed/data.yaml"
INITIAL_WEIGHTS = (
    ROOT / "runs/sorting_yolo/sorting_yolo11n_v1/weights/best.pt"
)
PROJECT = ROOT / "runs/sorting_yolo"
RUN_NAME = "sorting_yolo11n_v2_mixed"


def main() -> None:
    if not DATA.is_file():
        raise FileNotFoundError("Training dataset is not included; provide datasets/sorting_yolo_v2_mixed/data.yaml")
    if not INITIAL_WEIGHTS.exists():
        raise FileNotFoundError(INITIAL_WEIGHTS)
    model = YOLO(str(INITIAL_WEIGHTS))
    model.train(
        data=str(DATA),
        epochs=15,
        imgsz=320,
        batch=16,
        device="cpu",
        workers=0,
        patience=5,
        cache=False,
        pretrained=True,
        optimizer="AdamW",
        lr0=0.001,
        lrf=0.05,
        weight_decay=0.0005,
        close_mosaic=5,
        project=str(PROJECT),
        name=RUN_NAME,
        exist_ok=True,
        seed=42,
        deterministic=True,
        plots=True,
        save=True,
        val=True,
        verbose=True,
    )


if __name__ == "__main__":
    main()
