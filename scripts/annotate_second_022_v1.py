from __future__ import annotations

from pathlib import Path
import csv

from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "datasets/sorting_yolo_stage1/all_video_frames"
OUTPUT = ROOT / "datasets/sorting_yolo_stage1/batches/second_022"

CLASSES = ["parcel", "drawer_open", "drawer_closed", "chute", "bag"]
COLORS = {
    0: (0, 153, 255),
    1: (40, 200, 40),
    2: (255, 255, 255),
    3: (255, 70, 70),
    4: (255, 200, 0),
}


def add_complete(items, class_id, x1, y1, x2, y2):
    # A moving entity touching either image edge is omitted.
    if x1 >= 2 and x2 <= 718 and x2 > x1 and y2 > y1:
        items.append((class_id, round(x1), round(y1), round(x2), round(y2)))


def boxes_for_frame(frame_no):
    k = frame_no - 661
    boxes = []

    # The black parcel on the far-right drawer remains fully identifiable only
    # in the first few frames; once clipped by the image edge it is omitted.
    if frame_no <= 663:
        add_complete(
            boxes,
            0,
            655 + 7.5 * k,
            352,
            713 + 2.0 * k,
            415,
        )

    # One horizontal silver door plate moves out on the right.
    if frame_no <= 670:
        add_complete(
            boxes,
            1,
            444 + 13.3 * k,
            429,
            596 + 13.3 * k,
            458,
        )

    # The next horizontal silver door plate enters from the left.  It is not
    # retained until its whole plate is visible.
    if frame_no >= 674:
        k2 = frame_no - 674
        add_complete(
            boxes,
            1,
            14 + 13.7 * k2,
            431,
            169 + 13.7 * k2,
            464,
        )

    # The two large brown/silver flipped mechanisms are machine backsides, not
    # drawer_closed instances.
    boxes.append((3, 0, 480, 408, 782))
    boxes.append((3, 411, 480, 719, 776))
    boxes.append((4, 0, 875, 490, 1279))
    return boxes


def to_yolo(width, height, item):
    class_id, x1, y1, x2, y2 = item
    return (
        f"{class_id} {((x1 + x2) / 2) / width:.6f} "
        f"{((y1 + y2) / 2) / height:.6f} "
        f"{(x2 - x1) / width:.6f} {(y2 - y1) / height:.6f}"
    )


def render(image_path, annotations, destination):
    image = Image.open(image_path).convert("RGB")
    draw = ImageDraw.Draw(image)
    font = ImageFont.load_default()
    for class_id, x1, y1, x2, y2 in annotations:
        color = COLORS[class_id]
        label = f"{class_id}:{CLASSES[class_id]}"
        draw.rectangle((x1, y1, x2, y2), outline=color, width=4)
        text_width = len(label) * 6 + 8
        text_y = max(0, y1 - 17)
        draw.rectangle((x1, text_y, x1 + text_width, text_y + 17), fill=color)
        text_color = (0, 0, 0) if class_id in {1, 2, 4} else (255, 255, 255)
        draw.text((x1 + 4, text_y + 3), label, fill=text_color, font=font)
    image.save(destination, quality=94)


def main():
    label_dir = OUTPUT / "labels_yolo"
    visual_dir = OUTPUT / "visualized"
    label_dir.mkdir(parents=True, exist_ok=True)
    visual_dir.mkdir(parents=True, exist_ok=True)

    rows = []
    for frame_no in range(661, 691):
        filename = f"frame_{frame_no:06d}.jpg"
        image_path = SOURCE / filename
        annotations = boxes_for_frame(frame_no)
        with Image.open(image_path) as image:
            width, height = image.size
        (label_dir / f"frame_{frame_no:06d}.txt").write_text(
            "\n".join(to_yolo(width, height, item) for item in annotations) + "\n",
            encoding="utf-8",
        )
        render(image_path, annotations, visual_dir / filename)
        counts = {
            name: sum(item[0] == class_id for item in annotations)
            for class_id, name in enumerate(CLASSES)
        }
        rows.append(
            {
                "image": filename,
                "frame_no": frame_no,
                "time_seconds": f"{(frame_no - 1) / 30:.3f}",
                "annotation_standard": "v1.2",
                **counts,
                "review_status": "visual_reviewed_first_pass",
            }
        )

    with (OUTPUT / "manifest.csv").open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)
    (OUTPUT / "README.md").write_text(
        "# 第 22 秒五类标注批次\n\n"
        "- 时间范围：22.000–22.967 秒\n"
        "- 图片：30 张，frame_000661.jpg 至 frame_000690.jpg\n"
        "- 标准：ANNOTATION_STANDARD_v1.md（v1.2）\n"
        "- 机构翻转背面不作为 drawer 标注；保留完整水平开门板\n"
        "- 两个可辨认闸口和主落袋均已标注\n"
        "- 未使用 MiniMax-M3；未生成拼图\n"
        "- 状态：visual_reviewed_first_pass，等待用户抽查\n",
        encoding="utf-8",
    )
    print(f"Wrote 30 frames to {OUTPUT}")


if __name__ == "__main__":
    main()
