from pathlib import Path
import json
import shutil

from PIL import Image, ImageDraw, ImageFont


ROOT = Path("/Users/lixing.guo/Documents/机械臂")
SOURCE = (
    ROOT
    / "datasets/sorting_yolo_stage1/m3_prelabels_10/"
    "user_standard_v2_original_images_10/0041_event_18_open_no_drop_t18.00.jpg"
)
OUTPUT = (
    ROOT
    / "datasets/sorting_yolo_stage1/m3_prelabels_10/"
    "five_class_user_standard_5_v6_drawer_open_corrected"
)

CLASSES = ["parcel", "drawer_open", "drawer_closed", "chute", "bag"]
COLORS = {
    "parcel": (0, 160, 255),
    "drawer_open": (120, 210, 0),
    "drawer_closed": (255, 255, 255),
    "chute": (255, 70, 70),
    "bag": (255, 205, 0),
}

# drawer_open is the complete horizontal white plate protruding toward the camera.
# It is below the parcel and must not include the parcel or the sloped/vertical board.
BOXES = [
    ("parcel", 55, 305, 155, 370),
    ("parcel", 407, 330, 485, 416),
    ("drawer_closed", 5, 380, 150, 430),
    ("drawer_closed", 195, 382, 345, 428),
    ("drawer_closed", 612, 348, 719, 398),
    ("drawer_open", 388, 423, 560, 466),
    ("chute", 136, 488, 545, 733),
    ("bag", 122, 850, 628, 1178),
]


def get_font(size: int) -> ImageFont.ImageFont:
    candidates = [
        "/System/Library/Fonts/PingFang.ttc",
        "/System/Library/Fonts/Supplemental/Arial.ttf",
    ]
    for candidate in candidates:
        if Path(candidate).exists():
            return ImageFont.truetype(candidate, size)
    return ImageFont.load_default()


def main() -> None:
    image_dir = OUTPUT / "images"
    label_dir = OUTPUT / "labels_yolo"
    visual_dir = OUTPUT / "visualized"
    for directory in (image_dir, label_dir, visual_dir):
        directory.mkdir(parents=True, exist_ok=True)

    shutil.copy2(SOURCE, image_dir / SOURCE.name)
    image = Image.open(SOURCE).convert("RGB")
    width, height = image.size

    label_lines = []
    for class_name, x1, y1, x2, y2 in BOXES:
        class_id = CLASSES.index(class_name)
        cx = (x1 + x2) / 2 / width
        cy = (y1 + y2) / 2 / height
        bw = (x2 - x1) / width
        bh = (y2 - y1) / height
        label_lines.append(
            f"{class_id} {cx:.6f} {cy:.6f} {bw:.6f} {bh:.6f}"
        )

    (label_dir / f"{SOURCE.stem}.txt").write_text(
        "\n".join(label_lines) + "\n", encoding="utf-8"
    )
    (OUTPUT / "classes.txt").write_text(
        "\n".join(CLASSES) + "\n", encoding="utf-8"
    )

    draw = ImageDraw.Draw(image)
    font = get_font(19)
    line_width = 5
    for class_name, x1, y1, x2, y2 in BOXES:
        color = COLORS[class_name]
        label = f"{CLASSES.index(class_name)}:{class_name}"
        draw.rectangle((x1, y1, x2, y2), outline=color, width=line_width)
        text_box = draw.textbbox((x1, y1), label, font=font)
        text_height = text_box[3] - text_box[1] + 6
        label_y = max(0, y1 - text_height)
        draw.rectangle(
            (x1, label_y, x1 + text_box[2] - text_box[0] + 8, y1),
            fill=color,
        )
        text_color = (0, 0, 0) if class_name != "parcel" else (255, 255, 255)
        draw.text((x1 + 4, label_y + 2), label, fill=text_color, font=font)

    image.save(visual_dir / SOURCE.name, quality=95)

    summary = {
        SOURCE.name: {
            class_name: sum(1 for box in BOXES if box[0] == class_name)
            for class_name in CLASSES
        },
        "drawer_open_box_xyxy": [388, 423, 560, 466],
    }
    (OUTPUT / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    (OUTPUT / "README.md").write_text(
        "# Five-class annotation — drawer_open corrected\n\n"
        "The `drawer_open` box marks only the complete horizontal white plate "
        "that protrudes toward the camera. It excludes the parcel above, the "
        "sloped/vertical board, rail, and surrounding mechanism.\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
