from pathlib import Path
import csv
import shutil

from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "datasets/sorting_yolo_stage1/all_video_frames"
OUTPUT = ROOT / "datasets/sorting_yolo_stage1/batches/second_019"

CLASSES = ["parcel", "drawer_open", "drawer_closed", "chute", "bag"]
COLORS = {
    0: (0, 153, 255),       # parcel: blue
    1: (40, 200, 40),       # drawer_open: green
    2: (255, 255, 255),     # drawer_closed: white
    3: (255, 70, 70),       # chute: red
    4: (255, 200, 0),       # bag: yellow
}


def box(class_id, x1, y1, x2, y2):
    return (class_id, int(x1), int(y1), int(x2), int(y2))


def reviewed_boxes(frame_no):
    """Frame-specific boxes after visual review of frames 571-601."""
    k = frame_no - 571
    boxes = []

    # Large black parcel sliding abnormally toward the right edge.
    large_parcel = {
        571: (349, 316, 507, 454),
        572: (361, 317, 516, 450),
        573: (373, 319, 522, 451),
        574: (384, 322, 529, 453),
        575: (396, 325, 538, 458),
        576: (405, 329, 549, 467),
        577: (417, 334, 562, 484),
        578: (429, 339, 576, 489),
        579: (440, 345, 590, 493),
        580: (454, 352, 604, 500),
        581: (465, 360, 617, 505),
        582: (480, 370, 634, 516),
        583: (492, 381, 650, 523),
        584: (504, 391, 665, 533),
        585: (516, 402, 679, 542),
        586: (527, 414, 695, 554),
        587: (538, 425, 714, 565),
        588: (548, 438, 719, 578),
        589: (560, 451, 719, 590),
        590: (570, 466, 719, 610),
        591: (580, 480, 719, 628),
        592: (590, 497, 719, 645),
    }
    if frame_no in large_parcel:
        boxes.append(box(0, *large_parcel[frame_no]))

    # Second black parcel entering from the left. Frames before 585 are too
    # severely clipped by the image edge to satisfy the standard.
    small_parcel = {
        585: (22, 348, 82, 402),
        586: (29, 347, 89, 400),
        587: (38, 347, 99, 399),
        588: (48, 346, 110, 398),
        589: (57, 346, 119, 398),
        590: (68, 345, 129, 397),
        591: (78, 345, 140, 396),
        592: (88, 344, 150, 396),
        593: (99, 344, 161, 395),
        594: (109, 344, 172, 395),
        595: (119, 343, 183, 394),
        596: (130, 342, 194, 394),
        597: (141, 341, 206, 393),
        598: (151, 340, 217, 392),
        599: (164, 339, 229, 392),
        600: (174, 339, 241, 391),
        601: (185, 338, 252, 390),
    }
    if frame_no in small_parcel:
        boxes.append(box(0, *small_parcel[frame_no]))

    # Complete horizontal drawer plate in the center.
    open_a_x1 = round(141 + 12.1 * k)
    open_a_x2 = round(295 + 13.1 * k)
    open_y1 = round(434 - 0.4 * k)
    open_y2 = round(475 - 0.6 * k)
    boxes.append(box(1, open_a_x1, open_y1, open_a_x2, open_y2))

    # A second horizontal drawer plate remains identifiable until frame 586.
    if frame_no <= 586:
        open_b_x1 = round(350 + 12.1 * k)
        open_b_x2 = round(510 + 13.0 * k)
        boxes.append(box(1, open_b_x1, open_y1, open_b_x2, open_y2))

    # Complete vertical orange closed plate. Other plates touching the left or
    # right image edge are deliberately omitted.
    if frame_no >= 581:
        j = frame_no - 581
        closed_x1 = round(47 + 11.35 * j)
        closed_x2 = round(208 + 12.5 * j)
        closed_y1 = round(395 - 0.6 * j)
        boxes.append(box(2, closed_x1, closed_y1, closed_x2, 445))

    # A second closed plate becomes fully visible at the left side near the
    # end of the interval. Earlier appearances are clipped by the image edge.
    closed_left = {
        596: (15, 386, 196, 446),
        597: (28, 385, 209, 446),
        598: (40, 385, 222, 446),
        599: (53, 384, 235, 446),
        600: (65, 383, 248, 446),
        601: (77, 383, 260, 445),
    }
    if frame_no in closed_left:
        boxes.append(box(2, *closed_left[frame_no]))

    # One chute remains identifiable throughout the interval. Its left side
    # reaches the image edge later in the sequence, but the channel body and
    # chute ownership remain clear, so v1.1 requires it to stay labeled.
    chute_x1 = max(0, round(31 - 3.0 * k))
    chute_x2 = round(515 - 1.83 * k)
    boxes.append(box(3, chute_x1, 481, chute_x2, 807))
    # Adjacent right-hand chute remains attributable up to the image edge.
    boxes.append(box(3, chute_x2 + 8, 481, 719, 807))

    # Main receiving bag: all visible bag body is included; the bottom is
    # naturally truncated by the image edge.
    bag_x1 = round(68 - 0.6 * k)
    bag_x2 = round(594 - 1.1 * k)
    bag_y1 = round(892 + 0.15 * k)
    boxes.append(box(4, bag_x1, bag_y1, bag_x2, 1279))

    return boxes


def to_yolo(width, height, item):
    class_id, x1, y1, x2, y2 = item
    x_center = ((x1 + x2) / 2) / width
    y_center = ((y1 + y2) / 2) / height
    box_width = (x2 - x1) / width
    box_height = (y2 - y1) / height
    return (
        f"{class_id} {x_center:.6f} {y_center:.6f} "
        f"{box_width:.6f} {box_height:.6f}"
    )


def main():
    image_dir = OUTPUT / "images"
    label_dir = OUTPUT / "labels_yolo"
    visual_dir = OUTPUT / "visualized"
    for directory in (image_dir, label_dir, visual_dir):
        directory.mkdir(parents=True, exist_ok=True)

    manifest_rows = []
    for frame_no in range(571, 601):
        filename = f"frame_{frame_no:06d}.jpg"
        source_path = SOURCE / filename
        target_path = image_dir / filename
        shutil.copy2(source_path, target_path)

        with Image.open(source_path) as source_image:
            width, height = source_image.size
            annotations = reviewed_boxes(frame_no)

            label_path = label_dir / f"frame_{frame_no:06d}.txt"
            label_path.write_text(
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
                draw.text(
                    (x1 + 4, text_y + 3),
                    label,
                    fill=text_color,
                    font=font,
                )
            visual.save(visual_dir / filename, quality=94)

        class_counts = {name: 0 for name in CLASSES}
        for class_id, *_ in annotations:
            class_counts[CLASSES[class_id]] += 1
        manifest_rows.append(
            {
                "image": filename,
                "frame_no": frame_no,
                "time_seconds": f"{(frame_no - 1) / 30:.3f}",
                "annotation_standard": "v1.2",
                **class_counts,
                "review_status": "visual_reviewed",
            }
        )

    with (OUTPUT / "manifest.csv").open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=manifest_rows[0].keys())
        writer.writeheader()
        writer.writerows(manifest_rows)

    (OUTPUT / "classes.txt").write_text("\n".join(CLASSES) + "\n", encoding="utf-8")
    (OUTPUT / "README.md").write_text(
        "# 第 19 秒五类标注批次\n\n"
        "- 时间范围：19.000–19.967 秒\n"
        "- 图片：30 张，frame_000571.jpg 至 frame_000600.jpg\n"
        "- 标准：ANNOTATION_STANDARD_v1.md（v1.2）\n"
        "- 方法：逐张视觉检查；未调用 MiniMax-M3；未生成拼图\n"
        "- 状态：第一轮标注，等待用户逐图复核\n"
        "- 类别：parcel、drawer_open、drawer_closed、chute、bag\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
