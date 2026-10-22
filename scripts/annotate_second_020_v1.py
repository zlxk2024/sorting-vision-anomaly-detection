from pathlib import Path
import csv
import shutil

from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "datasets/sorting_yolo_stage1/all_video_frames"
OUTPUT = ROOT / "datasets/sorting_yolo_stage1/batches/second_020"

CLASSES = ["parcel", "drawer_open", "drawer_closed", "chute", "bag"]
COLORS = {
    0: (0, 153, 255),
    1: (40, 200, 40),
    2: (255, 255, 255),
    3: (255, 70, 70),
    4: (255, 200, 0),
}


def box(class_id, x1, y1, x2, y2):
    return (class_id, int(x1), int(y1), int(x2), int(y2))


def reviewed_boxes(frame_no):
    """Boxes for natural second 20 after frame-by-frame visual review."""
    k = frame_no - 601
    boxes = []

    # Parcel 1: black soft parcel moving continuously across the upper carrier.
    black_x1 = round(185 + 10.9 * k)
    black_x2 = round(252 + 10.55 * k)
    black_y1 = round(338 - 0.62 * k)
    black_y2 = round(390 - 0.59 * k)
    boxes.append(box(0, black_x1, black_y1, black_x2, black_y2))

    # Parcel 2: white/black soft parcel is fully visible from frame 604.
    if frame_no >= 604:
        white_x1 = round(-12 + 9.75 * k)
        white_x2 = round(46 + 9.90 * k)
        white_y1 = round(374 - 0.79 * k)
        white_y2 = round(397 - 0.59 * k)
        boxes.append(box(0, white_x1, white_y1, white_x2, white_y2))

    # Open plate already present at the beginning; it remains complete through
    # frame 603 and is clipped by the right image edge afterwards.
    if frame_no <= 603:
        boxes.append(
            box(
                1,
                round(504 + 13.0 * k),
                round(421 - 0.3 * k),
                round(688 + 13.0 * k),
                round(457 - 0.3 * k),
            )
        )

    # The center closed plate flips during frames 613-614. Mark open only once
    # the horizontal plate is clear.
    if frame_no >= 614:
        j = frame_no - 614
        boxes.append(
            box(
                1,
                round(258 + 11.9 * j),
                round(420 - 0.55 * j),
                round(414 + 12.0 * j),
                round(461 - 0.65 * j),
            )
        )

    # A second plate becomes clearly horizontal at the end of the second.
    late_open = {
        629: (247, 414, 408, 453),
        630: (260, 413, 421, 452),
    }
    if frame_no in late_open:
        boxes.append(box(1, *late_open[frame_no]))

    # Another complete horizontal plate enters from the left at frames 629-630.
    left_open = {
        629: (10, 415, 172, 457),
        630: (22, 414, 185, 456),
    }
    if frame_no in left_open:
        boxes.append(box(1, *left_open[frame_no]))

    # Closed plate A: complete until it begins to flip at frame 613.
    if frame_no <= 612:
        boxes.append(
            box(
                2,
                round(77 + 12.8 * k),
                round(383 - 0.45 * k),
                round(260 + 12.5 * k),
                round(445 - 0.20 * k),
            )
        )

    # Closed plate B: moves toward the right image edge and remains complete
    # through frame 620.
    if frame_no <= 620:
        boxes.append(
            box(
                2,
                round(274 + 13.4 * k),
                round(383 - 0.45 * k),
                round(458 + 13.2 * k),
                round(445 - 0.20 * k),
            )
        )

    # Closed plate C becomes fully visible from the left at frame 611 and stays
    # vertical through frame 627. Frames 628-629 are its flip transition.
    if 611 <= frame_no <= 627:
        j = frame_no - 611
        boxes.append(
            box(
                2,
                round(8 + 12.55 * j),
                round(388 - 0.55 * j),
                round(175 + 12.95 * j),
                round(445 - 0.25 * j),
            )
        )

    # The identifiable chute remains visible with its left side at the image
    # edge; v1.2 requires labeling the complete visible channel body.
    chute_x2 = round(460 - 1.83 * k)
    boxes.append(box(3, 0, 480, chute_x2, 807))
    # Adjacent right-hand chute remains attributable up to the image edge.
    boxes.append(box(3, chute_x2 + 8, 480, 719, 807))

    # Main yellow/white receiving bag. Include all visible body and right tie.
    bag_x1 = max(0, round(50 - 1.72 * k))
    bag_x2 = round(560 - 2.9 * k)
    bag_y1 = round(895 - 0.38 * k)
    boxes.append(box(4, bag_x1, bag_y1, bag_x2, 1279))

    return boxes


def to_yolo(width, height, item):
    class_id, x1, y1, x2, y2 = item
    return (
        f"{class_id} {((x1 + x2) / 2) / width:.6f} "
        f"{((y1 + y2) / 2) / height:.6f} "
        f"{(x2 - x1) / width:.6f} {(y2 - y1) / height:.6f}"
    )


def main():
    image_dir = OUTPUT / "images"
    label_dir = OUTPUT / "labels_yolo"
    visual_dir = OUTPUT / "visualized"
    for directory in (image_dir, label_dir, visual_dir):
        directory.mkdir(parents=True, exist_ok=True)

    rows = []
    for frame_no in range(601, 631):
        filename = f"frame_{frame_no:06d}.jpg"
        source_path = SOURCE / filename
        shutil.copy2(source_path, image_dir / filename)

        with Image.open(source_path) as source_image:
            width, height = source_image.size
            annotations = reviewed_boxes(frame_no)
            (label_dir / f"frame_{frame_no:06d}.txt").write_text(
                "\n".join(to_yolo(width, height, item) for item in annotations)
                + "\n",
                encoding="utf-8",
            )

            visual = source_image.convert("RGB")
            draw = ImageDraw.Draw(visual)
            font = ImageFont.load_default()
            for class_id, x1, y1, x2, y2 in annotations:
                color = COLORS[class_id]
                label = f"{class_id}:{CLASSES[class_id]}"
                draw.rectangle((x1, y1, x2, y2), outline=color, width=4)
                text_height = 17
                text_width = len(label) * 6 + 8
                text_y = max(0, y1 - text_height)
                draw.rectangle(
                    (x1, text_y, x1 + text_width, text_y + text_height),
                    fill=color,
                )
                text_color = (0, 0, 0) if class_id in (1, 2, 4) else (255, 255, 255)
                draw.text((x1 + 4, text_y + 3), label, fill=text_color, font=font)
            visual.save(visual_dir / filename, quality=94)

        counts = {name: 0 for name in CLASSES}
        for class_id, *_ in annotations:
            counts[CLASSES[class_id]] += 1
        rows.append(
            {
                "image": filename,
                "frame_no": frame_no,
                "time_seconds": f"{(frame_no - 1) / 30:.3f}",
                "annotation_standard": "v1.2",
                **counts,
                "review_status": "visual_reviewed",
            }
        )

    with (OUTPUT / "manifest.csv").open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)

    (OUTPUT / "classes.txt").write_text("\n".join(CLASSES) + "\n", encoding="utf-8")
    (OUTPUT / "README.md").write_text(
        "# 第 20 秒五类标注批次\n\n"
        "- 时间范围：20.000–20.967 秒\n"
        "- 图片：30 张，frame_000601.jpg 至 frame_000630.jpg\n"
        "- 标准：ANNOTATION_STANDARD_v1.md（v1.2）\n"
        "- 方法：逐张视觉检查；未调用 MiniMax-M3；未生成拼图\n"
        "- 状态：第一轮标注，等待用户逐图复核\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
