from pathlib import Path
import json
import math
import shutil

from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parents[1]
SOURCE_DIR = (
    ROOT
    / "datasets/sorting_yolo_stage1/m3_prelabels_10/"
    "user_standard_v2_original_images_10"
)
OUTPUT = (
    ROOT
    / "datasets/sorting_yolo_stage1/m3_prelabels_10/"
    "five_class_other_5_v7_pose_standard"
)

CLASSES = ["parcel", "drawer_open", "drawer_closed", "chute", "bag"]
COLORS = {
    "parcel": (0, 160, 255),
    "drawer_open": (120, 210, 0),
    "drawer_closed": (255, 255, 255),
    "chute": (255, 70, 70),
    "bag": (255, 205, 0),
}

# Annotation rule:
# - drawer_open: the door plate is laid flat / horizontal.
# - drawer_closed: the door plate is standing / vertical.
# - Boxes cover the physical door plate only, not the parcel, chute surface,
#   guide rail, or surrounding mechanism.
ANNOTATIONS = {
    "0057_event_19_slide_abnormal_t19.60.jpg": [
        ("parcel", 58, 331, 107, 392),
        ("parcel", 556, 450, 719, 590),
        ("drawer_open", 359, 425, 526, 470),
        ("drawer_closed", 132, 384, 305, 431),
        ("chute", 0, 478, 480, 770),
        ("bag", 51, 891, 535, 1279),
    ],
    "0070_event_21_two_parcels_open_no_drop_t21.10.jpg": [
        ("parcel", 313, 334, 405, 416),
        ("parcel", 539, 296, 620, 376),
        ("drawer_open", 84, 412, 241, 459),
        ("drawer_open", 289, 411, 455, 455),
        ("drawer_open", 501, 406, 676, 451),
        ("chute", 0, 470, 410, 751),
        ("bag", 0, 850, 482, 1279),
    ],
    "0071_event_21_two_parcels_open_no_drop_t21.20.jpg": [
        ("parcel", 342, 333, 421, 413),
        ("parcel", 553, 295, 628, 375),
        ("drawer_open", 89, 414, 250, 461),
        ("drawer_open", 330, 411, 494, 461),
        ("drawer_open", 542, 405, 719, 451),
        ("chute", 0, 476, 411, 751),
        ("bag", 0, 850, 482, 1279),
    ],
    "0089_normal_23_25_drop_t24.00.jpg": [
        ("parcel", 88, 442, 174, 510),
        ("drawer_open", 80, 445, 218, 493),
        ("chute", 10, 497, 436, 750),
        ("bag", 66, 861, 519, 1279),
    ],
    "0094_normal_23_25_drop_t24.80.jpg": [
        ("drawer_open", 386, 445, 539, 491),
        ("drawer_closed", 190, 399, 337, 454),
        ("chute", 16, 500, 451, 750),
        ("bag", 66, 860, 522, 1279),
    ],
}


def get_font(size: int) -> ImageFont.ImageFont:
    candidates = [
        "/System/Library/Fonts/PingFang.ttc",
        "/System/Library/Fonts/Supplemental/Arial.ttf",
    ]
    for candidate in candidates:
        if Path(candidate).exists():
            return ImageFont.truetype(candidate, size)
    return ImageFont.load_default()


def render_visual(
    source: Path,
    boxes: list[tuple[str, int, int, int, int]],
    destination: Path,
) -> None:
    image = Image.open(source).convert("RGB")
    draw = ImageDraw.Draw(image)
    font = get_font(17)
    line_width = 5

    for class_name, x1, y1, x2, y2 in boxes:
        color = COLORS[class_name]
        label = f"{CLASSES.index(class_name)}:{class_name}"
        draw.rectangle((x1, y1, x2, y2), outline=color, width=line_width)
        text_box = draw.textbbox((x1, y1), label, font=font)
        text_width = text_box[2] - text_box[0] + 8
        text_height = text_box[3] - text_box[1] + 6
        label_y = max(0, y1 - text_height)
        draw.rectangle((x1, label_y, x1 + text_width, y1), fill=color)
        text_color = (255, 255, 255) if class_name == "parcel" else (0, 0, 0)
        draw.text((x1 + 4, label_y + 2), label, fill=text_color, font=font)

    image.save(destination, quality=95)


def save_yolo(
    source: Path,
    boxes: list[tuple[str, int, int, int, int]],
    destination: Path,
) -> None:
    with Image.open(source) as image:
        width, height = image.size

    lines = []
    for class_name, x1, y1, x2, y2 in boxes:
        class_id = CLASSES.index(class_name)
        cx = (x1 + x2) / 2 / width
        cy = (y1 + y2) / 2 / height
        bw = (x2 - x1) / width
        bh = (y2 - y1) / height
        lines.append(f"{class_id} {cx:.6f} {cy:.6f} {bw:.6f} {bh:.6f}")
    destination.write_text("\n".join(lines) + "\n", encoding="utf-8")


def make_contact_sheet(visual_dir: Path, destination: Path) -> None:
    font = get_font(18)
    thumb_width = 360
    thumb_height = 640
    header_height = 34
    columns = min(5, len(ANNOTATIONS))
    rows = math.ceil(len(ANNOTATIONS) / columns)
    sheet = Image.new(
        "RGB",
        (thumb_width * columns, (thumb_height + header_height) * rows),
        (32, 36, 44),
    )
    draw = ImageDraw.Draw(sheet)
    for index, filename in enumerate(ANNOTATIONS):
        image = Image.open(visual_dir / filename).convert("RGB")
        image.thumbnail((thumb_width, thumb_height))
        column = index % columns
        row = index // columns
        cell_x = column * thumb_width
        cell_y = row * (thumb_height + header_height)
        x = cell_x + (thumb_width - image.width) // 2
        y = cell_y + header_height + (thumb_height - image.height) // 2
        sheet.paste(image, (x, y))
        draw.text(
            (cell_x + 6, cell_y + 6),
            filename.split("_t")[0],
            fill=(255, 255, 255),
            font=font,
        )
    sheet.save(destination, quality=95)


def main() -> None:
    image_dir = OUTPUT / "images"
    label_dir = OUTPUT / "labels_yolo"
    visual_dir = OUTPUT / "visualized"
    for directory in (image_dir, label_dir, visual_dir):
        directory.mkdir(parents=True, exist_ok=True)

    summary = {}
    for filename, boxes in ANNOTATIONS.items():
        source = SOURCE_DIR / filename
        shutil.copy2(source, image_dir / filename)
        save_yolo(source, boxes, label_dir / f"{Path(filename).stem}.txt")
        render_visual(source, boxes, visual_dir / filename)
        summary[filename] = {
            class_name: sum(1 for box in boxes if box[0] == class_name)
            for class_name in CLASSES
        }

    (OUTPUT / "classes.txt").write_text(
        "\n".join(CLASSES) + "\n", encoding="utf-8"
    )
    (OUTPUT / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    (OUTPUT / "README.md").write_text(
        "# Five-class annotations — pose-based door standard\n\n"
        "Classes: parcel, drawer_open, drawer_closed, chute, bag.\n\n"
        "- drawer_open: the physical door plate is laid flat/horizontal.\n"
        "- drawer_closed: the physical door plate is standing/vertical.\n"
        "- A door box contains only the door plate itself.\n"
        "- Door plates cut off by the left or right image edge are not labelled.\n"
        "- Ambiguous or heavily occluded door plates are not force-labelled.\n",
        encoding="utf-8",
    )
    make_contact_sheet(
        visual_dir,
        OUTPUT / f"contact_sheet_{len(ANNOTATIONS)}.jpg",
    )


if __name__ == "__main__":
    main()
