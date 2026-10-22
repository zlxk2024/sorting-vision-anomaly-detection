from __future__ import annotations

from pathlib import Path
import csv
import json

from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "datasets/sorting_two_chutes_supplement/review_10_v1"
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


# Every box below was checked on its individual source frame under
# ANNOTATION_STANDARD_v1.md v1.2.  No interpolation or model prelabel is used.
ANNOTATIONS = {
    "sample_01_t5.40s.jpg": [
        ("parcel", 144, 220, 224, 294),
        ("drawer_closed", 107, 266, 228, 302),
        ("drawer_closed", 268, 260, 381, 306),
        ("drawer_closed", 403, 261, 531, 303),
        ("chute", 0, 352, 287, 670),
        ("chute", 291, 350, 543, 665),
        ("bag", 120, 710, 345, 959),
        ("bag", 353, 701, 543, 959),
    ],
    "sample_02_t6.20s.jpg": [
        ("parcel", 416, 228, 488, 317),
        ("drawer_open", 62, 304, 215, 350),
        ("drawer_open", 217, 303, 361, 350),
        ("drawer_open", 366, 303, 511, 350),
        ("chute", 0, 361, 291, 671),
        ("chute", 295, 359, 543, 666),
        ("bag", 125, 716, 349, 959),
        ("bag", 356, 705, 543, 959),
    ],
    "sample_03_t21.40s.jpg": [
        ("parcel", 253, 194, 312, 273),
        ("drawer_open", 83, 289, 204, 335),
        ("drawer_open", 235, 289, 350, 335),
        ("chute", 0, 336, 250, 647),
        ("chute", 254, 336, 530, 643),
        ("bag", 83, 695, 276, 959),
        ("bag", 329, 687, 530, 959),
    ],
    "sample_04_t22.20s.jpg": [
        ("parcel", 480, 201, 543, 298),
        ("drawer_open", 332, 290, 449, 340),
        ("chute", 0, 344, 250, 647),
        ("chute", 254, 343, 530, 642),
        ("bag", 85, 697, 276, 959),
        ("bag", 330, 690, 531, 959),
    ],
    "sample_05_t36.40s.jpg": [
        ("parcel", 143, 219, 204, 278),
        ("chute", 0, 343, 276, 647),
        ("chute", 280, 342, 530, 642),
        ("bag", 105, 695, 297, 959),
        ("bag", 354, 690, 530, 959),
    ],
    "sample_06_t37.20s.jpg": [
        ("parcel", 387, 228, 465, 291),
        ("drawer_open", 219, 291, 336, 338),
        ("drawer_open", 367, 291, 483, 338),
        ("chute", 0, 340, 276, 647),
        ("chute", 280, 340, 530, 642),
        ("bag", 105, 695, 298, 959),
        ("bag", 354, 690, 530, 959),
    ],
    "sample_07_t42.40s.jpg": [
        ("parcel", 299, 201, 375, 295),
        ("drawer_open", 272, 290, 384, 338),
        ("chute", 0, 340, 276, 647),
        ("chute", 280, 339, 530, 642),
        ("bag", 105, 695, 298, 959),
        ("bag", 354, 690, 530, 959),
    ],
    "sample_08_t43.20s.jpg": [
        ("parcel", 111, 191, 157, 241),
        ("chute", 0, 340, 276, 647),
        ("chute", 280, 339, 530, 642),
        ("bag", 105, 695, 298, 959),
        ("bag", 354, 690, 530, 959),
    ],
    "sample_09_t43.80s.jpg": [
        ("parcel", 296, 182, 340, 249),
        ("drawer_open", 253, 291, 368, 338),
        ("chute", 0, 340, 276, 647),
        ("chute", 280, 339, 530, 642),
        ("bag", 105, 695, 298, 959),
        ("bag", 354, 690, 530, 959),
    ],
    "sample_10_t44.60s.jpg": [
        ("chute", 0, 340, 276, 647),
        ("chute", 280, 339, 530, 642),
        ("bag", 105, 695, 298, 959),
        ("bag", 354, 690, 530, 959),
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


def write_label(image_path: Path, boxes: list[tuple], label_path: Path) -> None:
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
    label_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def render(image_path: Path, boxes: list[tuple], output_path: Path) -> None:
    image = Image.open(image_path).convert("RGB")
    draw = ImageDraw.Draw(image)
    font = get_font(16)
    for class_name, x1, y1, x2, y2 in boxes:
        color = COLORS[class_name]
        label = f"{CLASSES.index(class_name)}:{class_name}"
        draw.rectangle((x1, y1, x2, y2), outline=color, width=4)
        text_box = draw.textbbox((x1, y1), label, font=font)
        text_width = text_box[2] - text_box[0] + 8
        text_height = text_box[3] - text_box[1] + 6
        label_y = max(0, y1 - text_height)
        draw.rectangle((x1, label_y, x1 + text_width, y1), fill=color)
        text_color = (255, 255, 255) if class_name in {"parcel", "chute"} else (0, 0, 0)
        draw.text((x1 + 4, label_y + 2), label, fill=text_color, font=font)
    image.save(output_path, quality=95)


def main() -> None:
    LABEL_DIR.mkdir(parents=True, exist_ok=True)
    VISUAL_DIR.mkdir(parents=True, exist_ok=True)
    rows = []
    totals = {name: 0 for name in CLASSES}

    for filename, boxes in ANNOTATIONS.items():
        image_path = IMAGE_DIR / filename
        if not image_path.exists():
            raise FileNotFoundError(image_path)
        with Image.open(image_path) as image:
            width, height = image.size
        for class_name, x1, y1, x2, y2 in boxes:
            if not (0 <= x1 < x2 < width and 0 <= y1 < y2 < height):
                raise ValueError(f"Invalid box in {filename}: {(class_name, x1, y1, x2, y2)}")

        stem = Path(filename).stem
        write_label(image_path, boxes, LABEL_DIR / f"{stem}.txt")
        render(image_path, boxes, VISUAL_DIR / filename)

        counts = {name: sum(item[0] == name for item in boxes) for name in CLASSES}
        for name, count in counts.items():
            totals[name] += count
        time_seconds = stem.split("_t", 1)[1].removesuffix("s")
        rows.append(
            {
                "image": filename,
                "time_seconds": time_seconds,
                "annotation_standard": "v1.5",
                "review_status": "visual_reviewed_first_pass",
                **counts,
            }
        )

    with (OUTPUT / "manifest.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)

    (OUTPUT / "classes.txt").write_text("\n".join(CLASSES) + "\n", encoding="utf-8")
    (OUTPUT / "summary.json").write_text(
        json.dumps({"images": len(rows), "totals": totals}, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    (OUTPUT / "README.md").write_text(
        "# 两个口视频补充标注：首批10张\n\n"
        "- 视频：`两个口的视频.mp4`\n"
        "- 标准：`ANNOTATION_STANDARD_v1.md` v1.5\n"
        "- 类别：parcel、drawer_open、drawer_closed、chute、bag\n"
        "- 方法：逐张查看原图并确认边界；未使用模型预标、固定框或插值。\n"
        "- 关闭门板按实体姿态和安装位置判断；俯拍下呈横向扁框仍标 drawer_closed。\n"
        "- 暴露的驱动机构和翻转机构背面不标为 drawer_closed。\n"
        "- 画面左侧仅局部出现的集包袋不标；中间和右侧可确认的袋子分别标注。\n"
        "- 当前状态：visual_reviewed_first_pass，等待用户逐张验收。\n",
        encoding="utf-8",
    )
    print(json.dumps({"output": str(OUTPUT), "images": len(rows), "totals": totals}, ensure_ascii=False))


if __name__ == "__main__":
    main()
