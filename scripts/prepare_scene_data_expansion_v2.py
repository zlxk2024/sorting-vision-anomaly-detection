from __future__ import annotations

from collections import Counter
from pathlib import Path
import csv
import json

import cv2


ROOT = Path(__file__).resolve().parents[1]
OLD_DATASET = ROOT / "datasets/sorting_yolo_stage1/yolo_dataset_v1"
OLD_OUTPUT = ROOT / "datasets/sorting_yolo_stage1/compact_v2_selection"
NEW_VIDEO = (Path(__file__).resolve().parents[1] / "data/videos/两个口的视频.mp4")
NEW_OUTPUT = (
    ROOT / "datasets/sorting_two_chutes_supplement/review_additional_10_v2"
)

CLASSES = ["parcel", "drawer_open", "drawer_closed", "chute", "bag"]

# These timestamps are outside the previously reviewed 0–45 s event windows.
# They cover different parcel appearances and later portions of the new scene.
REVIEW_TIMESTAMPS = [
    61.8,
    88.3,
    96.8,
    104.0,
    117.5,
    124.0,
    128.6,
    145.0,
    156.0,
    171.5,
]


def read_class_counts(label_path: Path) -> tuple[int, ...]:
    counts = Counter()
    for line in label_path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            counts[int(line.split()[0])] += 1
    return tuple(counts[index] for index in range(len(CLASSES)))


def build_old_compact_manifest() -> dict:
    rows = list(
        csv.DictReader(
            (OLD_DATASET / "split_manifest.csv").open(encoding="utf-8")
        )
    )
    rows.sort(key=lambda row: int(Path(row["frame"]).stem.split("_")[1]))
    class_counts = [
        read_class_counts((ROOT / row["label_source"])) for row in rows
    ]

    # 1. Regular coverage at about 5 fps (one frame every 0.2 s).
    selected = {index for index in range(len(rows)) if index % 6 == 0}

    # 2. Denser parcel coverage: retain roughly one of every three
    # parcel-positive frames.
    parcel_indices = [
        index for index, counts in enumerate(class_counts) if counts[0] > 0
    ]
    selected.update(parcel_indices[::3])

    # 3. Always retain both sides of a visible entity/state-count transition.
    for index in range(1, len(rows)):
        if class_counts[index][:3] != class_counts[index - 1][:3]:
            selected.add(index - 1)
            selected.add(index)

    OLD_OUTPUT.mkdir(parents=True, exist_ok=True)
    output_rows = []
    totals = Counter()
    split_counts = Counter()
    for index in sorted(selected):
        row = dict(rows[index])
        counts = class_counts[index]
        split_counts[row["split"]] += 1
        for class_index, count in enumerate(counts):
            totals[CLASSES[class_index]] += count
            row[CLASSES[class_index]] = count
        row["selection_reason"] = ",".join(
            reason
            for reason, condition in (
                ("regular_5fps", index % 6 == 0),
                ("parcel_dense", index in set(parcel_indices[::3])),
                (
                    "state_transition",
                    (
                        index > 0
                        and class_counts[index][:3]
                        != class_counts[index - 1][:3]
                    )
                    or (
                        index + 1 < len(rows)
                        and class_counts[index][:3]
                        != class_counts[index + 1][:3]
                    ),
                ),
            )
            if condition
        )
        output_rows.append(row)

    manifest_path = OLD_OUTPUT / "manifest.csv"
    with manifest_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=output_rows[0].keys())
        writer.writeheader()
        writer.writerows(output_rows)

    summary = {
        "source_images": len(rows),
        "selected_images": len(output_rows),
        "retained_ratio": round(len(output_rows) / len(rows), 4),
        "split_images": dict(split_counts),
        "instances": dict(totals),
        "selection_policy": {
            "regular_sampling": "every 6 frames (about 5 fps)",
            "parcel_sampling": "every third parcel-positive frame",
            "state_transition": "both adjacent frames retained",
        },
    }
    (OLD_OUTPUT / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    (OLD_OUTPUT / "README.md").write_text(
        "# 旧场景精简候选集\n\n"
        "该目录只保存筛选清单，不复制或删除原始图片。筛选目标是减少"
        "30 FPS连续帧冗余，同时保留包裹运动和抽屉状态切换。\n\n"
        "- 常规画面：约5 FPS抽样；\n"
        "- 包裹画面：更密集保留；\n"
        "- parcel/drawer状态数量变化：保留切换前后帧；\n"
        "- 原始1,184帧仍完整保留，可用于对照实验。\n",
        encoding="utf-8",
    )
    return summary


def extract_review_frames() -> dict:
    if not NEW_VIDEO.exists():
        raise FileNotFoundError(NEW_VIDEO)

    image_dir = NEW_OUTPUT / "images"
    image_dir.mkdir(parents=True, exist_ok=True)
    capture = cv2.VideoCapture(str(NEW_VIDEO))
    if not capture.isOpened():
        raise RuntimeError(f"Cannot open video: {NEW_VIDEO}")

    rows = []
    for index, timestamp in enumerate(REVIEW_TIMESTAMPS, start=1):
        capture.set(cv2.CAP_PROP_POS_MSEC, timestamp * 1000)
        ok, frame = capture.read()
        if not ok:
            raise RuntimeError(f"Cannot read frame at {timestamp:.2f}s")
        filename = f"additional_{index:02d}_t{timestamp:06.2f}s.jpg"
        output_path = image_dir / filename
        if not cv2.imwrite(str(output_path), frame):
            raise RuntimeError(f"Cannot write: {output_path}")
        rows.append(
            {
                "image": filename,
                "time_seconds": f"{timestamp:.2f}",
                "source_video": str(NEW_VIDEO),
                "annotation_status": "pending_visual_review",
            }
        )
    capture.release()

    with (NEW_OUTPUT / "manifest.csv").open(
        "w", newline="", encoding="utf-8"
    ) as handle:
        writer = csv.DictWriter(handle, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)
    (NEW_OUTPUT / "README.md").write_text(
        "# 新场景追加复核：首批10张\n\n"
        "- 来源：`两个口的视频.mp4`；\n"
        "- 时间范围：61.8–171.5秒，避开此前重点标注的0–45秒；\n"
        "- 当前仅完成差异化抽帧，状态为 `pending_visual_review`；\n"
        "- 下一步按照统一v1.5标准逐张标注五类实体。\n",
        encoding="utf-8",
    )
    return {"images": len(rows), "output": str(NEW_OUTPUT)}


def main() -> None:
    result = {
        "old_compact": build_old_compact_manifest(),
        "new_review_batch": extract_review_frames(),
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
