from pathlib import Path
import csv
import json
import shutil

from PIL import Image, ImageDraw, ImageFont


ROOT = Path("/Users/lixing.guo/Documents/机械臂")
SOURCE = ROOT / "datasets/sorting_yolo_stage1/all_video_frames"
OUTPUT = ROOT / "datasets/sorting_yolo_stage1/gpt_labels_first100_v1"

CLASSES = ["parcel", "drawer_open", "drawer_closed", "chute", "bag"]
COLORS = {
    "parcel": (0, 160, 255),
    "drawer_open": (120, 210, 0),
    "drawer_closed": (255, 255, 255),
    "chute": (255, 70, 70),
    "bag": (255, 205, 0),
}


def interp_box(keys: list[tuple[int, tuple[int, int, int, int]]], n: int):
    for key, box in keys:
        if n == key:
            return box
    for (a, box_a), (b, box_b) in zip(keys, keys[1:]):
        if a < n < b:
            ratio = (n - a) / (b - a)
            return tuple(
                round(box_a[i] + (box_b[i] - box_a[i]) * ratio) for i in range(4)
            )
    return None


WHITE_PARCEL = [
    (46, (214, 356, 280, 415)),
    (50, (260, 382, 334, 444)),
    (55, (318, 424, 403, 500)),
    (60, (335, 476, 425, 558)),
    (66, (345, 560, 450, 656)),
    (70, (355, 620, 470, 730)),
]

YELLOW_PARCEL = [
    (78, (24, 290, 105, 370)),
    (82, (54, 260, 145, 365)),
    (86, (86, 280, 185, 395)),
    (90, (132, 255, 250, 390)),
    (95, (210, 340, 365, 470)),
    (100, (285, 385, 450, 505)),
]


def base_boxes(n: int):
    boxes = [
        ("chute", 70, 390, 565, 770),
        ("bag", 112, 820, 640, 1279),
    ]
    return boxes


def parcel_boxes(n: int):
    boxes = []
    if 46 <= n <= 70:
        box = interp_box(WHITE_PARCEL, n)
        if box:
            boxes.append(("parcel", *box))
    if 78 <= n <= 100:
        box = interp_box(YELLOW_PARCEL, n)
        if box:
            boxes.append(("parcel", *box))
    return boxes


def boxes_for_frame(n: int):
    return parcel_boxes(n) + base_boxes(n)


def get_font(size: int) -> ImageFont.ImageFont:
    for candidate in (
        "/System/Library/Fonts/PingFang.ttc",
        "/System/Library/Fonts/Helvetica.ttc",
    ):
        if Path(candidate).exists():
            return ImageFont.truetype(candidate, size)
    return ImageFont.load_default()


def save_yolo(image_path: Path, boxes, destination: Path) -> None:
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
    destination.write_text("\n".join(lines) + "\n", encoding="utf-8")


def render(image_path: Path, boxes, destination: Path) -> None:
    image = Image.open(image_path).convert("RGB")
    draw = ImageDraw.Draw(image)
    font = get_font(17)
    for class_name, x1, y1, x2, y2 in boxes:
        color = COLORS[class_name]
        label = f"{CLASSES.index(class_name)}:{class_name}"
        draw.rectangle((x1, y1, x2, y2), outline=color, width=5)
        tb = draw.textbbox((x1, y1), label, font=font)
        tw = tb[2] - tb[0] + 8
        th = tb[3] - tb[1] + 6
        y_text = max(0, y1 - th)
        draw.rectangle((x1, y_text, x1 + tw, y1), fill=color)
        text_color = (255, 255, 255) if class_name == "parcel" else (0, 0, 0)
        draw.text((x1 + 4, y_text + 2), label, fill=text_color, font=font)
    image.save(destination, quality=95)


def main() -> None:
    image_dir = OUTPUT / "images"
    label_dir = OUTPUT / "labels_yolo"
    visual_dir = OUTPUT / "visualized"
    for directory in (image_dir, label_dir, visual_dir):
        directory.mkdir(parents=True, exist_ok=True)

    summary_rows = []
    totals = {name: 0 for name in CLASSES}
    frames = sorted(SOURCE.glob("frame_*.jpg"))[:100]
    for frame_index, source_path in enumerate(frames, start=1):
        boxes = boxes_for_frame(frame_index)
        target_image = image_dir / source_path.name
        shutil.copy2(source_path, target_image)
        save_yolo(source_path, boxes, label_dir / f"{source_path.stem}.txt")
        render(source_path, boxes, visual_dir / source_path.name)
        counts = {name: sum(1 for box in boxes if box[0] == name) for name in CLASSES}
        for name, count in counts.items():
            totals[name] += count
        summary_rows.append(
            {
                "frame": source_path.name,
                "time_seconds": f"{(frame_index - 1) / 30:.3f}",
                **counts,
            }
        )

    with (OUTPUT / "annotation_manifest.csv").open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=summary_rows[0].keys())
        writer.writeheader()
        writer.writerows(summary_rows)
    (OUTPUT / "classes.txt").write_text("\n".join(CLASSES) + "\n", encoding="utf-8")
    (OUTPUT / "summary.json").write_text(
        json.dumps({"images": len(frames), "totals": totals}, ensure_ascii=False, indent=2)
        + "\n",
        encoding="utf-8",
    )
    (OUTPUT / "README.md").write_text(
        "# First 100 video frames, five-class GPT-reviewed labels\n\n"
        "No contact sheet is generated. Outputs are per-image YOLO labels and per-image visualizations.\n"
        "Parcel boxes are only used for clear moving parcels on the chute; parcels already inside the bag are not labelled as parcel.\n",
        encoding="utf-8",
    )
    print(json.dumps({"images": len(frames), "output": str(OUTPUT), "totals": totals}, ensure_ascii=False))


if __name__ == "__main__":
    main()
