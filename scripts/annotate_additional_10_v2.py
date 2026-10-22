from __future__ import annotations

from collections import Counter
from pathlib import Path
import csv
import json

from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = (
    ROOT / "datasets/sorting_two_chutes_supplement/review_additional_10_v2"
)
IMAGE_DIR = OUTPUT / "images"
LABEL_DIR = OUTPUT / "labels_yolo"
VISUAL_DIR = OUTPUT / "visualized"

CLASSES = ["parcel", "drawer_open", "drawer_closed", "chute", "bag"]
COLORS = {
    "parcel": (0, 153, 255),
    "drawer_open": (40, 200, 40),
    "drawer_closed": (255, 255, 255),
    "chute": (255, 70, 70),
    "bag": (255, 200, 0),
}

# Manually reviewed on each original frame.  The new camera slowly shifts
# during the video, so chute and bag coordinates are intentionally adjusted
# per frame rather than copied from a static template.
#
# New-angle drawer rule, calibrated by the user:
# - drawer_closed: a narrow/thin lower lip that stays flush with the carrier;
# - drawer_open: a broad silver plate visibly flipped out below the ribbed
#   carrier, exposing a large front surface;
# - judge by exposed plate area, thickness and mechanical position, not color
#   alone or the bounding-box aspect ratio;
# - exposed black mechanisms are not drawers;
# - a plate cut by the left/right image boundary is not labelled.
ANNOTATIONS = {
    "additional_01_t061.80s.jpg": [
        ("parcel", 342, 474, 390, 520),
        ("drawer_open", 405, 287, 527, 334),
        ("chute", 0, 329, 278, 656),
        ("chute", 282, 327, 543, 652),
        ("bag", 84, 687, 307, 959),
        ("bag", 341, 683, 543, 959),
    ],
    "additional_02_t088.30s.jpg": [
        ("drawer_open", 98, 269, 222, 316),
        ("chute", 0, 315, 274, 634),
        ("chute", 278, 315, 543, 632),
        ("bag", 67, 676, 296, 959),
        ("bag", 338, 675, 543, 959),
    ],
    "additional_03_t096.80s.jpg": [
        ("chute", 0, 314, 274, 634),
        ("chute", 278, 315, 543, 632),
        ("bag", 67, 676, 296, 959),
        ("bag", 338, 676, 543, 959),
    ],
    "additional_04_t104.00s.jpg": [
        ("chute", 0, 306, 275, 630),
        ("chute", 279, 308, 543, 628),
        ("bag", 69, 673, 297, 959),
        ("bag", 340, 672, 543, 959),
    ],
    "additional_05_t117.50s.jpg": [
        ("chute", 0, 307, 275, 629),
        ("chute", 279, 308, 543, 628),
        ("bag", 69, 673, 297, 959),
        ("bag", 340, 672, 543, 959),
    ],
    "additional_06_t124.00s.jpg": [
        ("parcel", 42, 174, 102, 228),
        ("chute", 0, 302, 275, 626),
        ("chute", 279, 303, 543, 625),
        ("bag", 67, 668, 296, 959),
        ("bag", 338, 666, 543, 959),
    ],
    "additional_07_t128.60s.jpg": [
        ("parcel", 62, 99, 128, 172),
        ("drawer_closed", 45, 242, 174, 278),
        ("drawer_open", 209, 263, 339, 315),
        ("drawer_open", 362, 269, 475, 317),
        ("chute", 0, 303, 275, 624),
        ("chute", 279, 304, 543, 622),
        ("bag", 68, 668, 297, 959),
        ("bag", 339, 666, 543, 959),
    ],
    "additional_08_t145.00s.jpg": [
        ("chute", 0, 293, 267, 614),
        ("chute", 272, 294, 543, 611),
        ("bag", 58, 656, 287, 959),
        ("bag", 326, 653, 527, 959),
    ],
    "additional_09_t156.00s.jpg": [
        ("drawer_open", 14, 231, 145, 284),
        ("chute", 0, 289, 257, 614),
        ("chute", 261, 291, 533, 610),
        ("bag", 46, 650, 277, 959),
        ("bag", 318, 646, 520, 959),
    ],
    "additional_10_t171.50s.jpg": [
        ("parcel", 383, 105, 424, 162),
        ("drawer_open", 17, 215, 146, 269),
        ("drawer_open", 334, 236, 449, 292),
        ("chute", 0, 282, 251, 602),
        ("chute", 255, 284, 520, 599),
        ("bag", 38, 638, 265, 959),
        ("bag", 306, 636, 508, 959),
    ],
}


def get_font(size: int) -> ImageFont.ImageFont:
    for candidate in (
        "/System/Library/Fonts/PingFang.ttc",
        "/System/Library/Fonts/Helvetica.ttc",
    ):
        if Path(candidate).exists():
            return ImageFont.truetype(candidate, size)
    return ImageFont.load_default()


def write_yolo_label(
    image_path: Path, boxes: list[tuple], output_path: Path
) -> None:
    with Image.open(image_path) as image:
        width, height = image.size
    lines = []
    for class_name, x1, y1, x2, y2 in boxes:
        class_id = CLASSES.index(class_name)
        lines.append(
            f"{class_id} {((x1 + x2) / 2) / width:.6f} "
            f"{((y1 + y2) / 2) / height:.6f} "
            f"{(x2 - x1) / width:.6f} {(y2 - y1) / height:.6f}"
        )
    output_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def render(
    image_path: Path, boxes: list[tuple], output_path: Path
) -> None:
    image = Image.open(image_path).convert("RGB")
    draw = ImageDraw.Draw(image)
    font = get_font(14)
    for class_name, x1, y1, x2, y2 in boxes:
        color = COLORS[class_name]
        label = f"{CLASSES.index(class_name)}:{class_name}"
        draw.rectangle((x1, y1, x2, y2), outline=color, width=4)
        text_box = draw.textbbox((x1, y1), label, font=font)
        label_width = text_box[2] - text_box[0] + 8
        label_height = text_box[3] - text_box[1] + 6
        label_y = max(0, y1 - label_height)
        draw.rectangle(
            (x1, label_y, x1 + label_width, y1), fill=color
        )
        text_color = (
            (255, 255, 255)
            if class_name in {"parcel", "chute"}
            else (0, 0, 0)
        )
        draw.text(
            (x1 + 4, label_y + 2),
            label,
            fill=text_color,
            font=font,
        )
    image.save(output_path, quality=95)


def main() -> None:
    LABEL_DIR.mkdir(parents=True, exist_ok=True)
    VISUAL_DIR.mkdir(parents=True, exist_ok=True)

    original_manifest = {
        row["image"]: row
        for row in csv.DictReader(
            (OUTPUT / "manifest.csv").open(encoding="utf-8")
        )
    }
    totals = Counter()
    manifest_rows = []
    annotations_json = {}

    for filename, boxes in ANNOTATIONS.items():
        image_path = IMAGE_DIR / filename
        if not image_path.exists():
            raise FileNotFoundError(image_path)
        with Image.open(image_path) as image:
            width, height = image.size
        for box in boxes:
            _, x1, y1, x2, y2 = box
            if not (0 <= x1 < x2 <= width and 0 <= y1 < y2 <= height):
                raise ValueError(f"Invalid box in {filename}: {box}")

        write_yolo_label(
            image_path, boxes, LABEL_DIR / f"{image_path.stem}.txt"
        )
        render(image_path, boxes, VISUAL_DIR / filename)
        counts = Counter(box[0] for box in boxes)
        totals.update(counts)
        source_row = original_manifest[filename]
        manifest_rows.append(
            {
                "image": filename,
                "time_seconds": source_row["time_seconds"],
                "annotation_standard": "v1.7",
                "review_status": "visual_reviewed_first_pass",
                **{name: counts[name] for name in CLASSES},
            }
        )
        annotations_json[filename] = boxes

    with (OUTPUT / "manifest.csv").open(
        "w", newline="", encoding="utf-8"
    ) as handle:
        writer = csv.DictWriter(
            handle, fieldnames=manifest_rows[0].keys()
        )
        writer.writeheader()
        writer.writerows(manifest_rows)
    (OUTPUT / "classes.txt").write_text(
        "\n".join(CLASSES) + "\n", encoding="utf-8"
    )
    (OUTPUT / "annotations.json").write_text(
        json.dumps(annotations_json, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    summary = {
        "images": len(manifest_rows),
        "totals": {name: totals[name] for name in CLASSES},
        "review_status": "visual_reviewed_first_pass",
    }
    (OUTPUT / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
