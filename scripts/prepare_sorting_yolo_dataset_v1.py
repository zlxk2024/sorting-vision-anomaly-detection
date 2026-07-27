from __future__ import annotations

import csv
import shutil
from pathlib import Path


ROOT = Path("/Users/lixing.guo/Documents/机械臂")
SOURCE = ROOT / "datasets/sorting_yolo_stage1/batches"
OUTPUT = ROOT / "datasets/sorting_yolo_stage1/yolo_dataset_v1"

# 按完整秒划分，防止高度相似的相邻帧同时进入训练集和验证集。
VAL_SECONDS = {2, 10, 18, 28}
TEST_SECONDS = {5, 13, 19, 27}
CLASS_NAMES = ["parcel", "drawer_open", "drawer_closed", "chute", "bag"]


def split_for(second: int) -> str:
    if second in VAL_SECONDS:
        return "val"
    if second in TEST_SECONDS:
        return "test"
    return "train"


def main() -> None:
    if OUTPUT.exists():
        shutil.rmtree(OUTPUT)
    for split in ("train", "val", "test"):
        (OUTPUT / "images" / split).mkdir(parents=True)
        (OUTPUT / "labels" / split).mkdir(parents=True)

    rows = []
    for second in range(40):
        batch = SOURCE / f"second_{second:03d}"
        split = split_for(second)
        images = sorted((batch / "images").glob("*.jpg"))
        for image in images:
            label = batch / "labels_yolo" / f"{image.stem}.txt"
            if not label.exists():
                raise FileNotFoundError(label)
            out_image = OUTPUT / "images" / split / image.name
            out_label = OUTPUT / "labels" / split / label.name
            out_image.symlink_to(image.resolve())
            out_label.symlink_to(label.resolve())
            rows.append(
                {
                    "frame": image.name,
                    "second": second,
                    "split": split,
                    "image_source": str(image.resolve()),
                    "label_source": str(label.resolve()),
                }
            )

    yaml_lines = [
        f"path: {OUTPUT}",
        "train: images/train",
        "val: images/val",
        "test: images/test",
        "names:",
    ]
    yaml_lines.extend(f"  {idx}: {name}" for idx, name in enumerate(CLASS_NAMES))
    (OUTPUT / "data.yaml").write_text("\n".join(yaml_lines) + "\n", encoding="utf-8")

    with (OUTPUT / "split_manifest.csv").open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)

    counts = {split: sum(row["split"] == split for row in rows)
              for split in ("train", "val", "test")}
    (OUTPUT / "README.md").write_text(
        "# Sorting YOLO Dataset v1\n\n"
        f"- train: {counts['train']} frames\n"
        f"- val: {counts['val']} frames\n"
        f"- test: {counts['test']} frames\n"
        "- split unit: whole second (30 consecutive frames)\n"
        f"- validation seconds: {sorted(VAL_SECONDS)}\n"
        f"- test seconds: {sorted(TEST_SECONDS)}\n"
        "- labels: parcel, drawer_open, drawer_closed, chute, bag\n",
        encoding="utf-8",
    )
    print(counts)
    print(OUTPUT / "data.yaml")


if __name__ == "__main__":
    main()
