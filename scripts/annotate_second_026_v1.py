from __future__ import annotations

from pathlib import Path
import csv

from PIL import Image, ImageDraw, ImageFont


ROOT = Path("/Users/lixing.guo/Documents/机械臂")
SOURCE = ROOT / "datasets/sorting_yolo_stage1/all_video_frames"
OUTPUT = ROOT / "datasets/sorting_yolo_stage1/batches/second_026"
CLASSES = ["parcel", "drawer_open", "drawer_closed", "chute", "bag"]
COLORS = {
    0: (0, 153, 255),
    1: (40, 200, 40),
    2: (255, 255, 255),
    3: (255, 70, 70),
    4: (255, 200, 0),
}


def add_complete(items, class_id, x1, y1, x2, y2):
    if x1 >= 2 and x2 <= 718 and x2 > x1 and y2 > y1:
        items.append((class_id, round(x1), round(y1), round(x2), round(y2)))


def boxes_for_frame(frame_no):
    k = frame_no - 781
    boxes = []

    # Last orange upright closed door from the previous group.
    add_complete(boxes, 2, 423 + 13.0 * k, 398, 589 + 13.0 * k, 448)

    # New black parcel becomes complete after entering from the left.
    if frame_no >= 805:
        p = frame_no - 805
        add_complete(
            boxes,
            0,
            7 + 13.0 * p,
            349 + 4.8 * p,
            121 + 13.0 * p,
            434 + 4.4 * p,
        )

    # Its horizontal opened plate is not retained until fully inside the frame.
    if frame_no >= 808:
        p = frame_no - 808
        add_complete(boxes, 1, 5 + 13.0 * p, 433, 161 + 13.0 * p, 465)

    boxes.append((3, 0, 486, 408, 783))
    boxes.append((3, 411, 486, 719, 775))
    boxes.append((4, 0, 868, 492, 1279))
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
    for frame_no in range(781, 811):
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
        "# 第 26 秒五类标注批次\n\n"
        "- 时间范围：26.000–26.967 秒\n"
        "- 图片：30 张，frame_000781.jpg 至 frame_000810.jpg\n"
        "- 标准：ANNOTATION_STANDARD_v1.md（v1.2）\n"
        "- 标注离场的橙色关闭门板，以及末端完整进入的黑色包裹和开门板\n"
        "- 机构翻转背面不作为 drawer；画面边缘截断实体不标\n"
        "- 两个闸口和主落袋均已标注；未生成拼图\n"
        "- 状态：visual_reviewed_first_pass，等待用户抽查\n",
        encoding="utf-8",
    )
    print(f"Wrote 30 frames to {OUTPUT}")


if __name__ == "__main__":
    main()
