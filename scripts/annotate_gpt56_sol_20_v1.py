from pathlib import Path
import json
import math
import shutil

from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parents[1]
SOURCE_DIR = ROOT / "datasets/sorting_yolo_stage1/images/to_label"
OUTPUT = ROOT / "datasets/sorting_yolo_stage1/gpt56_sol_labels_20_v1"

CLASSES = ["parcel", "drawer_open", "drawer_closed", "chute", "bag"]
COLORS = {
    "parcel": (0, 160, 255),
    "drawer_open": (120, 210, 0),
    "drawer_closed": (255, 255, 255),
    "chute": (255, 70, 70),
    "bag": (255, 205, 0),
}

# GPT-reviewed labels using the latest user standard:
# - drawer_open: complete horizontal door plate only.
# - drawer_closed: complete vertical orange/brown door plate only.
# - do not label drawers cut by the image edge.
# - parcels must fully contain the visible parcel body.
# - chute is the complete orange destination chute/panel region.
# - bag is the whole visible receiving bag.
ANNOTATIONS = {
    "0037_event_18_open_no_drop_t17.60.jpg": [
        ("drawer_closed", 210, 372, 388, 429),
        ("drawer_closed", 422, 370, 606, 428),
        ("chute", 80, 488, 555, 752),
        ("bag", 117, 848, 638, 1279),
    ],
    "0038_event_18_open_no_drop_t17.70.jpg": [
        ("drawer_closed", 55, 374, 221, 430),
        ("drawer_closed", 270, 372, 432, 428),
        ("chute", 88, 488, 560, 752),
        ("bag", 118, 848, 638, 1279),
    ],
    "0039_event_18_open_no_drop_t17.80.jpg": [
        ("drawer_closed", 95, 375, 258, 431),
        ("drawer_closed", 304, 373, 468, 430),
        ("chute", 96, 488, 560, 752),
        ("bag", 119, 848, 638, 1279),
    ],
    "0040_event_18_open_no_drop_t17.90.jpg": [
        ("drawer_closed", 132, 376, 294, 432),
        ("drawer_closed", 338, 374, 502, 431),
        ("chute", 106, 488, 560, 752),
        ("bag", 120, 848, 638, 1279),
    ],
    "0041_event_18_open_no_drop_t18.00.jpg": [
        ("parcel", 55, 305, 155, 370),
        ("parcel", 407, 330, 485, 416),
        ("drawer_open", 388, 423, 560, 466),
        ("drawer_closed", 195, 382, 345, 428),
        ("chute", 136, 488, 545, 733),
        ("bag", 122, 850, 628, 1178),
    ],
    "0042_event_18_open_no_drop_t18.10.jpg": [
        ("parcel", 81, 306, 187, 380),
        ("parcel", 442, 332, 524, 417),
        ("drawer_closed", 18, 377, 183, 433),
        ("drawer_closed", 235, 377, 398, 432),
        ("drawer_open", 429, 423, 595, 468),
        ("chute", 118, 489, 554, 744),
        ("bag", 120, 855, 631, 1279),
    ],
    "0043_event_18_open_no_drop_t18.20.jpg": [
        ("parcel", 112, 320, 231, 393),
        ("parcel", 482, 340, 559, 420),
        ("drawer_open", 468, 422, 642, 467),
        ("drawer_closed", 52, 378, 229, 435),
        ("drawer_closed", 272, 376, 432, 432),
        ("chute", 87, 489, 560, 752),
        ("bag", 121, 886, 630, 1279),
    ],
    "0044_event_18_open_no_drop_t18.30.jpg": [
        ("parcel", 136, 321, 258, 394),
        ("parcel", 514, 339, 589, 420),
        ("drawer_open", 500, 421, 675, 467),
        ("drawer_closed", 89, 380, 265, 435),
        ("drawer_closed", 304, 377, 467, 433),
        ("chute", 95, 489, 559, 752),
        ("bag", 119, 887, 631, 1279),
    ],
    "0045_event_18_open_no_drop_t18.40.jpg": [
        ("parcel", 172, 320, 295, 396),
        ("parcel", 550, 337, 627, 420),
        ("drawer_closed", 127, 381, 302, 435),
        ("drawer_closed", 343, 379, 507, 434),
        ("chute", 104, 489, 559, 752),
        ("bag", 119, 887, 631, 1279),
    ],
    "0046_event_18_open_no_drop_t18.50.jpg": [
        ("parcel", 206, 319, 334, 398),
        ("drawer_closed", 165, 381, 338, 436),
        ("drawer_closed", 379, 379, 545, 434),
        ("chute", 115, 489, 557, 752),
        ("bag", 120, 887, 631, 1279),
    ],
    "0047_event_18_open_no_drop_t18.60.jpg": [
        ("parcel", 241, 315, 374, 393),
        ("drawer_open", 12, 423, 170, 470),
        ("drawer_open", 598, 423, 719, 468),
        ("drawer_closed", 213, 379, 375, 436),
        ("drawer_closed", 421, 375, 584, 434),
        ("chute", 75, 488, 549, 758),
        ("bag", 128, 888, 632, 1279),
    ],
    "0048_event_18_open_no_drop_t18.70.jpg": [
        ("parcel", 270, 318, 404, 398),
        ("drawer_open", 35, 422, 205, 470),
        ("drawer_closed", 250, 381, 412, 437),
        ("drawer_closed", 462, 376, 625, 434),
        ("chute", 81, 488, 550, 758),
        ("bag", 128, 888, 632, 1279),
    ],
    "0049_event_18_open_no_drop_t18.80.jpg": [
        ("parcel", 308, 318, 442, 399),
        ("drawer_open", 70, 422, 240, 470),
        ("drawer_closed", 289, 380, 450, 437),
        ("drawer_closed", 500, 376, 666, 434),
        ("chute", 88, 488, 550, 758),
        ("bag", 128, 888, 632, 1279),
    ],
    "0050_event_18_open_no_drop_t18.90.jpg": [
        ("parcel", 348, 317, 485, 401),
        ("drawer_open", 104, 423, 278, 471),
        ("drawer_closed", 328, 381, 491, 437),
        ("drawer_closed", 536, 376, 703, 434),
        ("chute", 96, 488, 550, 758),
        ("bag", 128, 888, 632, 1279),
    ],
    "0051_event_18_open_no_drop_t19.00.jpg": [
        ("parcel", 372, 318, 520, 417),
        ("drawer_open", 134, 423, 310, 471),
        ("drawer_closed", 366, 381, 530, 437),
        ("chute", 104, 488, 550, 758),
        ("bag", 128, 888, 632, 1279),
    ],
    "0052_event_19_slide_abnormal_t19.10.jpg": [
        ("parcel", 374, 324, 526, 452),
        ("drawer_open", 167, 423, 329, 471),
        ("chute", 19, 493, 500, 772),
        ("bag", 75, 898, 560, 1279),
    ],
    "0053_event_19_slide_abnormal_t19.20.jpg": [
        ("parcel", 408, 345, 586, 492),
        ("drawer_open", 198, 423, 360, 471),
        ("chute", 23, 493, 500, 772),
        ("bag", 75, 898, 560, 1279),
    ],
    "0054_event_19_slide_abnormal_t19.30.jpg": [
        ("parcel", 446, 374, 631, 522),
        ("drawer_open", 237, 423, 402, 471),
        ("chute", 19, 493, 500, 772),
        ("bag", 75, 898, 560, 1279),
    ],
    "0055_event_19_slide_abnormal_t19.40.jpg": [
        ("parcel", 0, 339, 34, 402),
        ("parcel", 490, 363, 669, 520),
        ("drawer_open", 279, 422, 442, 470),
        ("drawer_closed", 52, 388, 231, 446),
        ("chute", 0, 487, 489, 773),
        ("bag", 58, 897, 546, 1279),
    ],
    "0056_event_19_slide_abnormal_t19.50.jpg": [
        ("parcel", 540, 405, 719, 536),
        ("drawer_open", 320, 422, 485, 470),
        ("drawer_closed", 88, 388, 268, 446),
        ("chute", 0, 487, 489, 773),
        ("bag", 58, 897, 546, 1279),
    ],
}


def font(size: int) -> ImageFont.ImageFont:
    for candidate in (
        "/System/Library/Fonts/PingFang.ttc",
        "/System/Library/Fonts/Helvetica.ttc",
    ):
        if Path(candidate).exists():
            return ImageFont.truetype(candidate, size)
    return ImageFont.load_default()


def save_yolo(image_path: Path, boxes, label_path: Path) -> None:
    with Image.open(image_path) as image:
        width, height = image.size
    lines = []
    for class_name, x1, y1, x2, y2 in boxes:
        class_id = CLASSES.index(class_name)
        xc = ((x1 + x2) / 2) / width
        yc = ((y1 + y2) / 2) / height
        bw = (x2 - x1) / width
        bh = (y2 - y1) / height
        lines.append(f"{class_id} {xc:.6f} {yc:.6f} {bw:.6f} {bh:.6f}")
    label_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def render(image_path: Path, boxes, output_path: Path) -> None:
    image = Image.open(image_path).convert("RGB")
    draw = ImageDraw.Draw(image)
    label_font = font(17)
    for class_name, x1, y1, x2, y2 in boxes:
        color = COLORS[class_name]
        text = f"{CLASSES.index(class_name)}:{class_name}"
        draw.rectangle((x1, y1, x2, y2), outline=color, width=5)
        text_box = draw.textbbox((x1, y1), text, font=label_font)
        tw = text_box[2] - text_box[0] + 8
        th = text_box[3] - text_box[1] + 6
        label_y = max(0, y1 - th)
        draw.rectangle((x1, label_y, x1 + tw, y1), fill=color)
        text_color = (255, 255, 255) if class_name == "parcel" else (0, 0, 0)
        draw.text((x1 + 4, label_y + 2), text, fill=text_color, font=label_font)
    image.save(output_path, quality=95)


def make_contact_sheet(visual_dir: Path, output_path: Path) -> None:
    files = [visual_dir / name for name in ANNOTATIONS]
    thumb_w, thumb_h, cap_h, cols = 240, 427, 36, 5
    rows = math.ceil(len(files) / cols)
    sheet = Image.new("RGB", (thumb_w * cols, (thumb_h + cap_h) * rows), (32, 36, 44))
    draw = ImageDraw.Draw(sheet)
    caption_font = font(13)
    for index, path in enumerate(files):
        image = Image.open(path).convert("RGB")
        image.thumbnail((thumb_w, thumb_h))
        cell_x = index % cols * thumb_w
        cell_y = index // cols * (thumb_h + cap_h)
        x = cell_x + (thumb_w - image.width) // 2
        y = cell_y + cap_h + (thumb_h - image.height) // 2
        sheet.paste(image, (x, y))
        draw.text((cell_x + 4, cell_y + 6), path.name, fill="white", font=caption_font)
    sheet.save(output_path, quality=94)


def main() -> None:
    image_dir = OUTPUT / "images"
    label_dir = OUTPUT / "labels_yolo"
    visual_dir = OUTPUT / "visualized"
    for directory in (image_dir, label_dir, visual_dir):
        directory.mkdir(parents=True, exist_ok=True)

    summary = {}
    for filename, boxes in ANNOTATIONS.items():
        src = SOURCE_DIR / filename
        shutil.copy2(src, image_dir / filename)
        save_yolo(src, boxes, label_dir / f"{Path(filename).stem}.txt")
        render(src, boxes, visual_dir / filename)
        summary[filename] = {
            class_name: sum(1 for item in boxes if item[0] == class_name)
            for class_name in CLASSES
        }

    (OUTPUT / "classes.txt").write_text("\n".join(CLASSES) + "\n", encoding="utf-8")
    (OUTPUT / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    (OUTPUT / "README.md").write_text(
        "# Codex/GPT reviewed five-class labels, 20 images\n\n"
        "These labels follow the user-confirmed standard: horizontal door plate is "
        "`drawer_open`, vertical door plate is `drawer_closed`, clipped edge "
        "drawers are skipped, and parcel boxes contain the whole visible parcel.\n",
        encoding="utf-8",
    )
    make_contact_sheet(visual_dir, OUTPUT / "contact_sheet_20.jpg")
    print(json.dumps({"images": len(ANNOTATIONS), "output": str(OUTPUT)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
