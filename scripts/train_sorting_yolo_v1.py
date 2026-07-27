from __future__ import annotations

from pathlib import Path

import torch
from ultralytics import YOLO


ROOT = Path("/Users/lixing.guo/Documents/机械臂")
DATA = ROOT / "datasets/sorting_yolo_stage1/yolo_dataset_v1/data.yaml"
PROJECT = ROOT / "runs/sorting_yolo"


def main() -> None:
    device = "mps" if torch.backends.mps.is_available() else "cpu"
    print(f"training device: {device}")
    model = YOLO("yolo11n.pt")
    model.train(
        data=str(DATA),
        # 8 GB M1 的第一版可行性配置；后续可在云端 GPU 用 640/100 轮精训。
        epochs=10,
        imgsz=320,
        batch=16,
        device=device,
        workers=0,
        patience=10,
        cache=False,
        pretrained=True,
        project=str(PROJECT),
        name="sorting_yolo11n_v1",
        exist_ok=True,
        seed=42,
        deterministic=True,
        plots=True,
        save=True,
        val=False,
        verbose=True,
    )
    weights = PROJECT / "sorting_yolo11n_v1/weights/best.pt"
    if not weights.exists():
        weights = PROJECT / "sorting_yolo11n_v1/weights/last.pt"
    if weights.exists():
        YOLO(str(weights)).val(
            data=str(DATA),
            split="test",
            imgsz=320,
            batch=16,
            # MPS 的 NMS 在当前环境较慢；最终测试改用 CPU，只执行一次。
            device="cpu",
            workers=0,
            project=str(PROJECT),
            name="sorting_yolo11n_v1_test",
            plots=True,
        )


if __name__ == "__main__":
    main()
