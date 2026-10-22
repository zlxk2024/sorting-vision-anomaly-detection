#!/usr/bin/env python3
from __future__ import annotations

import argparse
import random
from pathlib import Path


IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".bmp"}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Create an RKNN quantization dataset list from representative images."
    )
    parser.add_argument(
        "--image-dir",
        default="datasets/sorting_yolo_v2_mixed/images/train",
        help="Directory containing training images.",
    )
    parser.add_argument(
        "--output",
        default="deploy/horus_rv1126b/quant_images.txt",
        help="Output text file for RKNN quantization image paths.",
    )
    parser.add_argument("--limit", type=int, default=300, help="Max image count.")
    parser.add_argument("--seed", type=int, default=42, help="Sampling seed.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    image_dir = Path(args.image_dir).expanduser().resolve()
    output = Path(args.output).expanduser().resolve()
    if not image_dir.exists():
        raise FileNotFoundError(image_dir)

    images = sorted(
        p for p in image_dir.rglob("*") if p.is_file() and p.suffix.lower() in IMAGE_EXTS
    )
    if not images:
        raise RuntimeError(f"No images found under {image_dir}")

    random.Random(args.seed).shuffle(images)
    selected = sorted(images[: args.limit])
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text("\n".join(str(p) for p in selected) + "\n", encoding="utf-8")
    print(f"Quantization image list: {output}")
    print(f"Images selected: {len(selected)} / {len(images)}")


if __name__ == "__main__":
    main()
