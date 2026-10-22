from __future__ import annotations

from pathlib import Path
import csv
import json

import cv2


ROOT = Path(__file__).resolve().parents[1]
VIDEO = (Path(__file__).resolve().parents[1] / "data/videos/两个口的视频.mp4")
OUTPUT = (
    ROOT / "datasets/sorting_two_chutes_supplement/review_additional_100_v2"
)

# Ten independent windows outside the original 0–45 s review range.
# Each window contains ten frames at 0.2 s spacing.
WINDOW_STARTS = [
    48.4,
    61.0,
    77.8,
    87.6,
    96.0,
    116.8,
    123.4,
    127.8,
    143.8,
    154.8,
    50.4,
    54.4,
    56.8,
    64.0,
    70.8,
    90.6,
    100.6,
    104.6,
    134.8,
    163.8,
]
FRAMES_PER_WINDOW = 10
STEP_SECONDS = 0.2


def main() -> None:
    if not VIDEO.exists():
        raise FileNotFoundError(VIDEO)
    image_dir = OUTPUT / "images"
    image_dir.mkdir(parents=True, exist_ok=True)

    capture = cv2.VideoCapture(str(VIDEO))
    if not capture.isOpened():
        raise RuntimeError(f"Cannot open {VIDEO}")
    rows = []
    for window_index, start in enumerate(WINDOW_STARTS, start=1):
        for frame_index in range(FRAMES_PER_WINDOW):
            timestamp = start + frame_index * STEP_SECONDS
            capture.set(cv2.CAP_PROP_POS_MSEC, timestamp * 1000)
            ok, frame = capture.read()
            if not ok:
                raise RuntimeError(f"Cannot read frame at {timestamp:.2f}s")
            filename = (
                f"w{window_index:02d}_{frame_index + 1:02d}"
                f"_t{timestamp:06.2f}s.jpg"
            )
            output_path = image_dir / filename
            if not cv2.imwrite(str(output_path), frame):
                raise RuntimeError(f"Cannot write {output_path}")
            rows.append(
                {
                    "image": filename,
                    "window": window_index,
                    "time_seconds": f"{timestamp:.2f}",
                    "source_video": str(VIDEO),
                    "annotation_standard": "v1.7",
                    "review_status": "pending_prelabel",
                }
            )
    capture.release()

    OUTPUT.mkdir(parents=True, exist_ok=True)
    with (OUTPUT / "manifest.csv").open(
        "w", newline="", encoding="utf-8"
    ) as handle:
        writer = csv.DictWriter(handle, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)
    (OUTPUT / "README.md").write_text(
        "# 新场景追加200张（v1.7）\n\n"
        "- 20个独立时间窗口，每个窗口10张；\n"
        "- 帧间隔0.2秒；\n"
        "- 不使用拼图作为交付；\n"
        "- 当前状态：pending_prelabel。\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "images": len(rows),
                "windows": len(WINDOW_STARTS),
                "output": str(OUTPUT),
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
