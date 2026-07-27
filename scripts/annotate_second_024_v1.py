from __future__ import annotations

from pathlib import Path
import csv

from PIL import Image, ImageDraw, ImageFont


ROOT = Path("/Users/lixing.guo/Documents/机械臂")
SOURCE = ROOT / "datasets/sorting_yolo_stage1/all_video_frames"
OUTPUT = ROOT / "datasets/sorting_yolo_stage1/batches/second_024"
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
    721: (101, 442, 181, 505),
    726: (158, 486, 228, 553),
    731: (210, 558, 281, 631),
    736: (228, 623, 306, 709),
    741: (264, 727, 326, 833),
    744: (273, 815, 337, 914),
}


def interpolate_anchors(frame_no, anchors):
    keys = sorted(anchors)
    if frame_no <= keys[0]:
        return anchors[keys[0]]
    if frame_no >= keys[-1]:
        return anchors[keys[-1]]
    for left, right in zip(keys, keys[1:]):
        if left <= frame_no <= right:
            ratio = (frame_no - left) / (right - left)
            return tuple(
                anchors[left][i] + ratio * (anchors[right][i] - anchors[left][i])
                for i in range(4)
            )
    raise RuntimeError(frame_no)


def boxes_for_frame(frame_no):
    k = frame_no - 721
    boxes = []

    # The white parcel leaves the horizontal drawer and falls through the chute.
    # It remains annotated while visually identifiable, including motion blur.
    if frame_no <= 744:
        add_complete(boxes, 0, *interpolate_anchors(frame_no, PARCEL_ANCHORS))

    # Open flat silver plate that released the parcel.
    add_complete(
        boxes,
        1,
        57 + 13.15 * k,
        447,
        214 + 13.15 * k,
        480,
    )

    # Two successive orange upright closed plates enter from the left.
    x_primary = 82 + 13.0 * (frame_no - 736)
    add_complete(boxes, 2, x_primary, 409, x_primary + 156, 457)
    x_next = x_primary - 220
    add_complete(boxes, 2, x_next, 409, x_next + 162, 457)

    boxes.append((3, 0, 493, 411, 785))
    boxes.append((3, 414, 493, 719, 777))
    boxes.append((4, 0, 873, 495, 1279))
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
    for frame_no in range(721, 751):
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
        "# 第 24 秒五类标注批次\n\n"
        "- 时间范围：24.000–24.967 秒\n"
        "- 图片：30 张，frame_000721.jpg 至 frame_000750.jpg\n"
        "- 标准：ANNOTATION_STANDARD_v1.md（v1.2）\n"
        "- 逐帧跟踪白色包裹从开门板离开、穿过闸口并进入落袋的过程\n"
        "- 水平银色板标 drawer_open；完整橙色竖板标 drawer_closed\n"
        "- 两个闸口和主落袋均已标注；未生成拼图\n"
        "- 状态：visual_reviewed_first_pass，等待用户抽查\n",
        encoding="utf-8",
    )
    print(f"Wrote 30 frames to {OUTPUT}")


if __name__ == "__main__":
    main()
