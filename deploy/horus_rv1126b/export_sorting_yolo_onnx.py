#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Export the trained sorting YOLO model to static ONNX."
    )
    parser.add_argument(
        "--weights",
        default="models/sorting_yolo11n_v2_mixed_best.pt",
        help="Path to trained YOLO .pt weights.",
    )
    parser.add_argument("--imgsz", type=int, default=320, help="Export input size.")
    parser.add_argument("--opset", type=int, default=12, help="ONNX opset.")
    parser.add_argument(
        "--no-simplify",
        action="store_true",
        help="Disable ONNX simplification.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    weights = Path(args.weights).expanduser().resolve()
    if not weights.exists():
        raise FileNotFoundError(weights)

    repo_root = Path(__file__).resolve().parents[2]
    os.environ.setdefault("MPLCONFIGDIR", str(repo_root / "outputs/mpl_config"))
    os.environ.setdefault("YOLO_CONFIG_DIR", str(repo_root / "outputs/ultralytics_config"))
    Path(os.environ["MPLCONFIGDIR"]).mkdir(parents=True, exist_ok=True)
    Path(os.environ["YOLO_CONFIG_DIR"]).mkdir(parents=True, exist_ok=True)

    from ultralytics import YOLO

    model = YOLO(str(weights))
    output = model.export(
        format="onnx",
        imgsz=args.imgsz,
        opset=args.opset,
        simplify=not args.no_simplify,
        dynamic=False,
    )
    print(f"ONNX exported: {output}")


if __name__ == "__main__":
    main()
