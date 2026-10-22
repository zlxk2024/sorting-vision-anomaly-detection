from __future__ import annotations

from pathlib import Path
import csv
import shutil


ROOT = Path(__file__).resolve().parents[1]
DATASET = ROOT / "datasets/sorting_yolo_stage1"
SOURCE = DATASET / "all_video_frames"
BATCHES = DATASET / "batches"
FPS = 30
FRAME_COUNT = 1184
CLASSES = ["parcel", "drawer_open", "drawer_closed", "chute", "bag"]


def second_for_frame(frame_no: int) -> int:
    return (frame_no - 1) // FPS


def main() -> None:
    progress_rows = []

    for second in range(second_for_frame(FRAME_COUNT) + 1):
        batch = BATCHES / f"second_{second:03d}"
        image_dir = batch / "images"
        label_dir = batch / "labels_yolo"
        visual_dir = batch / "visualized"
        review_dir = batch / "needs_review"
        for directory in (image_dir, label_dir, visual_dir, review_dir):
            directory.mkdir(parents=True, exist_ok=True)

        start_frame = second * FPS + 1
        end_frame = min((second + 1) * FPS, FRAME_COUNT)
        frame_rows = []
        for frame_no in range(start_frame, end_frame + 1):
            filename = f"frame_{frame_no:06d}.jpg"
            source = SOURCE / filename
            target = image_dir / filename
            if not target.exists():
                shutil.copy2(source, target)

            reviewed = second in {19, 20}
            frame_rows.append(
                {
                    "image": filename,
                    "frame_no": frame_no,
                    "time_seconds": f"{(frame_no - 1) / FPS:.3f}",
                    "annotation_standard": "v1.2",
                    "parcel": "",
                    "drawer_open": "",
                    "drawer_closed": "",
                    "chute": "",
                    "bag": "",
                    "review_status": (
                        "visual_reviewed" if reviewed else "in_progress"
                    ),
                }
            )

        # Do not overwrite the richer reviewed manifests for seconds 19 and 20.
        manifest = batch / "manifest.csv"
        if second not in {19, 20} or not manifest.exists():
            with manifest.open("w", newline="", encoding="utf-8") as stream:
                writer = csv.DictWriter(stream, fieldnames=frame_rows[0].keys())
                writer.writeheader()
                writer.writerows(frame_rows)

        classes_path = batch / "classes.txt"
        if not classes_path.exists():
            classes_path.write_text("\n".join(CLASSES) + "\n", encoding="utf-8")

        readme = batch / "README.md"
        if second not in {19, 20} or not readme.exists():
            readme.write_text(
                f"# 第 {second} 秒五类标注批次\n\n"
                f"- 时间范围：{second:.3f}–{(end_frame - 1) / FPS:.3f} 秒\n"
                f"- 图片：{end_frame - start_frame + 1} 张，"
                f"frame_{start_frame:06d}.jpg 至 frame_{end_frame:06d}.jpg\n"
                "- 标准：ANNOTATION_STANDARD_v1.md（v1.2）\n"
                "- 类别：parcel、drawer_open、drawer_closed、chute、bag\n"
                "- 不使用 MiniMax-M3；不生成拼图\n"
                "- 状态：in_progress（逐帧视觉复核完成后才改为 visual_reviewed）\n",
                encoding="utf-8",
            )

        progress_rows.append(
            {
                "second": second,
                "batch": str(batch),
                "start_frame": start_frame,
                "end_frame": end_frame,
                "frame_count": end_frame - start_frame + 1,
                "status": (
                    "visual_reviewed" if second in {19, 20} else "in_progress"
                ),
            }
        )

    progress_path = BATCHES / "annotation_progress.csv"
    with progress_path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=progress_rows[0].keys())
        writer.writeheader()
        writer.writerows(progress_rows)

    print(f"Prepared {len(progress_rows)} second batches at {BATCHES}")


if __name__ == "__main__":
    main()
