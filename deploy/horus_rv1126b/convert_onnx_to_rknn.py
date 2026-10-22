#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Convert sorting YOLO ONNX to RKNN INT8 for Horus RV1126B."
    )
    parser.add_argument("--onnx", required=True, help="Input ONNX model path.")
    parser.add_argument("--output", required=True, help="Output RKNN model path.")
    parser.add_argument(
        "--dataset",
        required=True,
        help="RKNN quantization dataset text file, one image path per line.",
    )
    parser.add_argument("--target", default="rv1126b", help="RKNN target platform.")
    parser.add_argument(
        "--mean-values",
        default="0,0,0",
        help="Comma-separated mean values. Keep 0,0,0 for Ultralytics-style uint8 input.",
    )
    parser.add_argument(
        "--std-values",
        default="255,255,255",
        help="Comma-separated std values. Keep 255,255,255 for 0-1 normalization.",
    )
    return parser.parse_args()


def parse_triplet(value: str) -> list[list[float]]:
    parts = [float(x.strip()) for x in value.split(",")]
    if len(parts) != 3:
        raise ValueError(f"Expected three comma-separated values, got: {value}")
    return [parts]


def main() -> None:
    try:
        from rknn.api import RKNN
    except ImportError as exc:
        raise SystemExit(
            "rknn-toolkit2 is not installed. Run this script in the RKNN Toolkit2 "
            "Linux x86_64 environment."
        ) from exc

    args = parse_args()
    onnx = Path(args.onnx).expanduser().resolve()
    output = Path(args.output).expanduser().resolve()
    dataset = Path(args.dataset).expanduser().resolve()

    if not onnx.exists():
        raise FileNotFoundError(onnx)
    if not dataset.exists():
        raise FileNotFoundError(dataset)

    rknn = RKNN(verbose=True)
    print("--> Config")
    ret = rknn.config(
        target_platform=args.target,
        mean_values=parse_triplet(args.mean_values),
        std_values=parse_triplet(args.std_values),
        quant_img_RGB2BGR=False,
    )
    if ret != 0:
        raise RuntimeError(f"RKNN config failed: {ret}")

    print("--> Load ONNX")
    ret = rknn.load_onnx(model=str(onnx))
    if ret != 0:
        raise RuntimeError(f"RKNN load_onnx failed: {ret}")

    print("--> Build INT8 RKNN")
    ret = rknn.build(do_quantization=True, dataset=str(dataset))
    if ret != 0:
        raise RuntimeError(f"RKNN build failed: {ret}")

    print("--> Export RKNN")
    output.parent.mkdir(parents=True, exist_ok=True)
    ret = rknn.export_rknn(str(output))
    if ret != 0:
        raise RuntimeError(f"RKNN export failed: {ret}")

    rknn.release()
    print(f"RKNN exported: {output}")


if __name__ == "__main__":
    main()
