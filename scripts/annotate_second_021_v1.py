from __future__ import annotations

from pathlib import Path
import csv

from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "datasets/sorting_yolo_stage1/all_video_frames"
OUTPUT = ROOT / "datasets/sorting_yolo_stage1/batches/second_021"

CLASSES = ["parcel", "drawer_open", "drawer_closed", "chute", "bag"]
COLORS = {
    0: (0, 153, 255),
    1: (40, 200, 40),
    2: (255, 255, 255),
    3: (255, 70, 70),
    4: (255, 200, 0),
}


def add_if_complete(items, class_id, x1, y1, x2, y2):
    # Drawer/parcel entities cut by the frame edge are not retained.
    if x1 >= 2 and x2 <= 718 and x2 > x1 and y2 > y1:
        items.append((class_id, round(x1), round(y1), round(x2), round(y2)))


def boxes_for_frame(frame_no):
    k = frame_no - 631
    boxes = []

    # Two independent parcels are present at the start.  The right-hand parcel
    # leaves the image during this second; the left-hand one stays visible.
    add_if_complete(
        boxes,
        0,
        281 + 13.1 * k,
        350 - 0.25 * k,
        349 + 13.1 * k,
        415 - 0.15 * k,
    )
    if frame_no <= 641:
        add_if_complete(
            boxes,
            0,
            512 + 13.0 * k,
            308 - 0.15 * k,
            570 + 13.1 * k,
            380 - 0.10 * k,
        )

    # Actual opened door plates: the flat horizontal silver plates at the
    # lower end of each moving drawer.  The large white slopes are excluded.
    opens = (
        (36 + 13.15 * k, 417 - 0.12 * k, 198 + 13.15 * k, 457 - 0.10 * k),
        (250 + 13.05 * k, 416 - 0.12 * k, 412 + 13.05 * k, 456 - 0.10 * k),
        (461 + 13.00 * k, 415 - 0.12 * k, 620 + 13.00 * k, 455 - 0.10 * k),
    )
    for coords in opens:
        add_if_complete(boxes, 1, *coords)

    # Two visible chute channels are separated by the central brown divider.
    # Channel ownership remains clear although the outer sides meet the image
    # boundary, so v1.2 keeps both visible channel bodies.
    boxes.append((3, 0, 479, 409, 784))
    boxes.append((3, 412, 479, 719, 777))

    # Main receiving bag.  Side green bags are clipped and therefore omitted.
    boxes.append((4, 0, 878, 489, 1279))
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
    for frame_no in range(631, 661):
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
        "# 第 21 秒五类标注批次\n\n"
        "- 时间范围：21.000–21.967 秒\n"
        "- 图片：30 张，frame_000631.jpg 至 frame_000660.jpg\n"
        "- 标准：ANNOTATION_STANDARD_v1.md（v1.2）\n"
        "- 已检查双包裹、水平开门板、两个可辨认闸口和主落袋\n"
        "- 未使用 MiniMax-M3；未生成拼图\n"
        "- 状态：visual_reviewed_first_pass，等待用户抽查\n",
        encoding="utf-8",
    )
    print(f"Wrote 30 frames to {OUTPUT}")


if __name__ == "__main__":
    main()
