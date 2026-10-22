from pathlib import Path
import csv
import json
import shutil

from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "datasets/sorting_yolo_stage1/all_video_frames"
OUTPUT = ROOT / "datasets/sorting_yolo_stage1/gpt_visual_confirmed_10_v1"

CLASSES = ["parcel", "drawer_open", "drawer_closed", "chute", "bag"]
COLORS = {
    "parcel": (0, 160, 255),
    "drawer_open": (120, 210, 0),
    "drawer_closed": (255, 255, 255),
    "chute": (255, 70, 70),
    "bag": (255, 205, 0),
}


# These ten frames were visually checked one by one.  Only targets that are
# clear under the latest user standard are labelled.
ANNOTATIONS = {
    "frame_000001.jpg": [
        ("drawer_closed", 48, 260, 250, 326),
        ("drawer_closed", 300, 262, 505, 329),
        ("bag", 105, 820, 650, 1279),
    ],
    "frame_000002.jpg": [
        ("drawer_closed", 48, 260, 250, 326),
        ("drawer_closed", 300, 262, 505, 329),
        ("bag", 105, 820, 650, 1279),
    ],
    "frame_000003.jpg": [
        ("drawer_closed", 46, 260, 248, 326),
        ("drawer_closed", 300, 262, 505, 329),
        ("bag", 105, 820, 650, 1279),
    ],
    "frame_000004.jpg": [
        ("drawer_closed", 45, 260, 248, 326),
        ("drawer_closed", 300, 262, 506, 329),
        ("bag", 105, 820, 650, 1279),
    ],
    "frame_000005.jpg": [
        ("drawer_closed", 44, 260, 247, 326),
        ("drawer_closed", 300, 262, 506, 329),
        ("bag", 105, 820, 650, 1279),
    ],
    "frame_000006.jpg": [
        ("drawer_closed", 44, 260, 247, 326),
        ("drawer_closed", 300, 262, 506, 329),
        ("bag", 105, 820, 650, 1279),
    ],
    "frame_000007.jpg": [
        ("drawer_closed", 44, 260, 247, 326),
        ("drawer_closed", 300, 262, 506, 329),
        ("bag", 105, 820, 650, 1279),
    ],
    "frame_000008.jpg": [
        ("drawer_closed", 44, 260, 247, 326),
        ("drawer_closed", 300, 262, 506, 329),
        ("bag", 105, 820, 650, 1279),
    ],
    "frame_000009.jpg": [
        ("drawer_closed", 44, 260, 247, 326),
        ("drawer_closed", 300, 262, 506, 329),
        ("bag", 105, 820, 650, 1279),
    ],
    "frame_000010.jpg": [
        ("drawer_closed", 44, 260, 247, 326),
        ("drawer_closed", 300, 262, 506, 329),
        ("bag", 105, 820, 650, 1279),
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
    font = get_font(17)
    for class_name, x1, y1, x2, y2 in boxes:
        color = COLORS[class_name]
        label = f"{CLASSES.index(class_name)}:{class_name}"
        draw.rectangle((x1, y1, x2, y2), outline=color, width=5)
        text_box = draw.textbbox((x1, y1), label, font=font)
        text_width = text_box[2] - text_box[0] + 8
        text_height = text_box[3] - text_box[1] + 6
        label_y = max(0, y1 - text_height)
        draw.rectangle((x1, label_y, x1 + text_width, y1), fill=color)
        text_color = (255, 255, 255) if class_name == "parcel" else (0, 0, 0)
        draw.text((x1 + 4, label_y + 2), label, fill=text_color, font=font)
    image.save(output_path, quality=95)


def main() -> None:
    image_dir = OUTPUT / "images"
    label_dir = OUTPUT / "labels_yolo"
    visual_dir = OUTPUT / "visualized"
    for directory in (image_dir, label_dir, visual_dir):
        directory.mkdir(parents=True, exist_ok=True)

    rows = []
    totals = {name: 0 for name in CLASSES}
    for filename, boxes in ANNOTATIONS.items():
        source = SOURCE / filename
        shutil.copy2(source, image_dir / filename)
        save_yolo(source, boxes, label_dir / f"{Path(filename).stem}.txt")
        render(source, boxes, visual_dir / filename)
        counts = {name: sum(1 for box in boxes if box[0] == name) for name in CLASSES}
        for name, count in counts.items():
            totals[name] += count
        frame_no = int(Path(filename).stem.split("_")[-1])
        rows.append({"frame": filename, "time_seconds": f"{(frame_no - 1) / 30:.3f}", **counts})

    with (OUTPUT / "annotation_manifest.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)
    (OUTPUT / "classes.txt").write_text("\n".join(CLASSES) + "\n", encoding="utf-8")
    (OUTPUT / "summary.json").write_text(
        json.dumps({"images": len(ANNOTATIONS), "totals": totals}, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    (OUTPUT / "README.md").write_text(
        "# GPT visual confirmed 10 frames\n\n"
        "These labels were created by visual inspection only.  No batch coordinate "
        "template, interpolation, or M3 API was used.  Chute and drawer_open are "
        "left empty in this batch because they are not clearly confirmed under "
        "the current user standard.\n",
        encoding="utf-8",
    )
    print(json.dumps({"output": str(OUTPUT), "images": len(ANNOTATIONS), "totals": totals}, ensure_ascii=False))


if __name__ == "__main__":
    main()
