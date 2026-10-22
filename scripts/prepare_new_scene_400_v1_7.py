from __future__ import annotations

from pathlib import Path
import csv
import json

import cv2


ROOT = Path(__file__).resolve().parents[1]
VIDEO = (Path(__file__).resolve().parents[1] / "data/videos/两个口的视频.mp4")
OUTPUT = (
    ROOT
    / "datasets/sorting_two_chutes_supplement/review_expansion_400_v1_7"
)
IMAGE_DIR = OUTPUT / "images"

SAMPLE_COUNT = 400
START_SECONDS = 0.10
END_SECONDS = 176.40


def main() -> None:
    if not VIDEO.exists():
        raise FileNotFoundError(VIDEO)
    IMAGE_DIR.mkdir(parents=True, exist_ok=True)
    capture = cv2.VideoCapture(str(VIDEO))
    if not capture.isOpened():
        raise RuntimeError(f"Cannot open {VIDEO}")

    step = (END_SECONDS - START_SECONDS) / SAMPLE_COUNT
    rows = []
    for index in range(SAMPLE_COUNT):
        timestamp = START_SECONDS + index * step
        capture.set(cv2.CAP_PROP_POS_MSEC, timestamp * 1000)
        ok, frame = capture.read()
        if not ok:
            raise RuntimeError(f"Cannot read frame at {timestamp:.3f}s")
        filename = f"n{index + 1:04d}_t{timestamp:07.3f}s.jpg"
        if not cv2.imwrite(str(IMAGE_DIR / filename), frame):
            raise RuntimeError(filename)
        rows.append(
            {
                "image": filename,
                "index": index + 1,
                "time_seconds": f"{timestamp:.3f}",
                "source_video": str(VIDEO),
                "annotation_standard": "v1.7",
                "review_status": "pending_prelabel",
            }
        )
    capture.release()

    with (OUTPUT / "manifest_source.csv").open(
        "w", newline="", encoding="utf-8"
    ) as handle:
        writer = csv.DictWriter(handle, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)
    (OUTPUT / "README.md").write_text(
        "# 新机位扩充 400 张（v1.7）\n\n"
        "- 来源：`两个口的视频.mp4`；\n"
        "- 全视频均匀采样 400 张，避免只集中在少数异常窗口；\n"
        "- 重点补充 drawer_closed、包裹运动、状态切换和负样本；\n"
        "- 当前状态：pending_prelabel。\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "images": len(rows),
                "step_seconds": round(step, 4),
                "output": str(OUTPUT),
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
