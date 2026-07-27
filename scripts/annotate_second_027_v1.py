from __future__ import annotations

from pathlib import Path
import csv

from PIL import Image, ImageDraw, ImageFont


ROOT = Path("/Users/lixing.guo/Documents/机械臂")
SOURCE = ROOT / "datasets/sorting_yolo_stage1/all_video_frames"
OUTPUT = ROOT / "datasets/sorting_yolo_stage1/batches/second_027"
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


PARCEL_ANCHORS = {
    811: (52, 374, 198, 466),
    816: (91, 420, 255, 533),
    821: (116, 480, 310, 586),
    826: (142, 548, 353, 670),
    831: (157, 653, 401, 802),
    836: (174, 797, 413, 1000),
}


def interpolate_anchors(frame_no):
    keys = sorted(PARCEL_ANCHORS)
    for left, right in zip(keys, keys[1:]):
        if left <= frame_no <= right:
            ratio = (frame_no - left) / (right - left)
            return tuple(
                PARCEL_ANCHORS[left][i]
                + ratio * (PARCEL_ANCHORS[right][i] - PARCEL_ANCHORS[left][i])
                for i in range(4)
            )
    return PARCEL_ANCHORS[keys[-1]]


def boxes_for_frame(frame_no):
    k = frame_no - 811
    boxes = []

    # Black parcel leaves its open drawer, crosses the chute and enters the bag.
    if frame_no <= 836:
        add_complete(boxes, 0, *interpolate_anchors(frame_no))

    # The horizontal silver release plate remains visible throughout this second.
    add_complete(boxes, 1, 44 + 13.2 * k, 431, 201 + 13.2 * k, 464)

    # Two successive orange upright closed plates enter from the left.
    x_primary = 2 + 13.0 * (frame_no - 821)
    add_complete(boxes, 2, x_primary, 378, x_primary + 160, 427)
    add_complete(boxes, 2, x_primary - 219, 378, x_primary - 59, 427)

    boxes.append((3, 0, 480, 407, 783))
    boxes.append((3, 410, 480, 719, 775))
    boxes.append((4, 0, 865, 490, 1279))
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
    for frame_no in range(811, 841):
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
        "# 第 27 秒五类标注批次\n\n"
        "- 时间范围：27.000–27.967 秒\n"
        "- 图片：30 张，frame_000811.jpg 至 frame_000840.jpg\n"
        "- 标准：ANNOTATION_STANDARD_v1.md（v1.2）\n"
        "- 逐帧跟踪黑色包裹从开门板滑出、穿过闸口并进入主落袋\n"
        "- 仅标完整水平开门板和完整橙色关闭门板\n"
        "- 两个闸口和主落袋均已标注；未生成拼图\n"
        "- 状态：visual_reviewed_first_pass，等待用户抽查\n",
        encoding="utf-8",
    )
    print(f"Wrote 30 frames to {OUTPUT}")


if __name__ == "__main__":
    main()
