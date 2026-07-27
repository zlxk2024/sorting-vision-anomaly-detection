#!/usr/bin/env python3
"""Build a model-assisted YOLO annotation set for the 123 sampled video frames.

The seed model is used only to propose boxes.  Geometry constraints and
class-wise NMS remove obvious duplicates, and the ten user-approved golden
labels always replace model output for matching frames.
"""

from __future__ import annotations

import csv
import json
import shutil
from collections import Counter
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


WORKSPACE = Path("/Users/lixing.guo/Documents/机械臂")
SOURCE_IMAGES = WORKSPACE / "datasets/sorting_yolo_stage1/images/to_label"
SOURCE_MANIFEST = WORKSPACE / "datasets/sorting_yolo_stage1/frame_manifest.csv"
PREDICTIONS = (
    WORKSPACE
    / "outputs/yolo_sorting_bootstrap/video123_prelabels_lowconf/labels"
)
GOLD_LABELS = (
    WORKSPACE
    / "datasets/sorting_yolo_stage1/m3_prelabels_10/user_standard_v2_labels_yolo"
)
OUTPUT = WORKSPACE / "datasets/sorting_video_123_annotated_v1"

CLASS_NAMES = {0: "parcel", 1: "gate_open", 2: "gate_closed"}
COLORS = {0: (255, 0, 0), 1: (0, 220, 0), 2: (0, 145, 255)}
CONFIDENCE_FLOOR = {0: 0.005, 1: 0.006, 2: 0.006}

# Parcel boxes manually recovered during dense-event review.  The bootstrap
# model missed these fast, motion-blurred positions in the normal drop track.
MANUAL_ADDITIONS = {
    "0090_normal_23_25_drop_t24.20.txt": [
        (0, (0.292361, 0.410547, 0.101389, 0.058594), 1.0)
    ],
    "0091_normal_23_25_drop_t24.40.txt": [
        (0, (0.352778, 0.478516, 0.097222, 0.053906), 1.0)
    ],
    "0092_global_2fps_t24.50.txt": [
        (0, (0.368750, 0.518750, 0.104167, 0.062500), 1.0)
    ],
    "0093_normal_23_25_drop_t24.60.txt": [
        (0, (0.384722, 0.562500, 0.116667, 0.070312), 1.0)
    ],
}


def xywh_to_xyxy(box: tuple[float, float, float, float]) -> tuple[float, ...]:
    x, y, w, h = box
    return x - w / 2, y - h / 2, x + w / 2, y + h / 2


def iou(a: tuple[float, ...], b: tuple[float, ...]) -> float:
    ax1, ay1, ax2, ay2 = xywh_to_xyxy(a)
    bx1, by1, bx2, by2 = xywh_to_xyxy(b)
    iw = max(0.0, min(ax2, bx2) - max(ax1, bx1))
    ih = max(0.0, min(ay2, by2) - max(ay1, by1))
    inter = iw * ih
    union = (ax2 - ax1) * (ay2 - ay1) + (bx2 - bx1) * (by2 - by1) - inter
    return inter / union if union else 0.0


def valid_geometry(cls: int, box: tuple[float, float, float, float]) -> bool:
    x, y, w, h = box
    if not all(0.0 <= v <= 1.0 for v in box) or w <= 0 or h <= 0:
        return False
    if cls == 0:
        return 0.03 <= w <= 0.40 and 0.02 <= h <= 0.30 and 0.15 <= y <= 0.65
    if cls == 1:
        return 0.06 <= w <= 0.38 and 0.015 <= h <= 0.09 and 0.30 <= y <= 0.40
    if cls == 2:
        return 0.06 <= w <= 0.38 and 0.02 <= h <= 0.09 and 0.27 <= y <= 0.38
    return False


def classwise_nms(
    items: list[tuple[int, tuple[float, float, float, float], float]]
) -> list[tuple[int, tuple[float, float, float, float], float]]:
    kept: list[tuple[int, tuple[float, float, float, float], float]] = []
    for cls in CLASS_NAMES:
        candidates = sorted(
            (item for item in items if item[0] == cls),
            key=lambda item: item[2],
            reverse=True,
        )
        class_kept: list[tuple[int, tuple[float, float, float, float], float]] = []
        for candidate in candidates:
            if all(iou(candidate[1], other[1]) < 0.25 for other in class_kept):
                class_kept.append(candidate)
        kept.extend(class_kept)
    return sorted(kept, key=lambda item: (item[0], item[1][0]))


def read_predictions(path: Path) -> list[tuple[int, tuple[float, ...], float]]:
    if not path.exists():
        return []
    result = []
    for line in path.read_text().splitlines():
        parts = line.split()
        if len(parts) != 6:
            continue
        cls = int(parts[0])
        box = tuple(map(float, parts[1:5]))
        confidence = float(parts[5])
        if confidence >= CONFIDENCE_FLOOR.get(cls, 1.0) and valid_geometry(cls, box):
            result.append((cls, box, confidence))
    return classwise_nms(result)


def read_gold(path: Path) -> list[tuple[int, tuple[float, ...], float]]:
    result = []
    for line in path.read_text().splitlines():
        parts = line.split()
        if len(parts) == 5:
            result.append((int(parts[0]), tuple(map(float, parts[1:5])), 1.0))
    return result


def draw_labels(image_path: Path, items, output_path: Path) -> None:
    image = Image.open(image_path).convert("RGB")
    draw = ImageDraw.Draw(image)
    width, height = image.size
    try:
        font = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 18)
    except OSError:
        font = ImageFont.load_default()
    for cls, (xc, yc, bw, bh), _ in items:
        x1, y1 = (xc - bw / 2) * width, (yc - bh / 2) * height
        x2, y2 = (xc + bw / 2) * width, (yc + bh / 2) * height
        color = COLORS[cls]
        draw.rectangle((x1, y1, x2, y2), outline=color, width=4)
        text = f"{cls}:{CLASS_NAMES[cls]}"
        text_box = draw.textbbox((0, 0), text, font=font)
        tw, th = text_box[2], text_box[3]
        ty = max(0, y1 - th - 6)
        draw.rectangle((x1, ty, x1 + tw + 6, ty + th + 4), fill=color)
        draw.text((x1 + 3, ty + 1), text, fill="white", font=font)
    image.save(output_path, quality=94)


def main() -> None:
    images_dir = OUTPUT / "images"
    labels_dir = OUTPUT / "labels"
    visualized_dir = OUTPUT / "visualized"
    contact_dir = OUTPUT / "contact_sheets"
    for directory in (images_dir, labels_dir, visualized_dir, contact_dir):
        directory.mkdir(parents=True, exist_ok=True)

    manifest_rows = {
        Path(row["image"]).name: row
        for row in csv.DictReader(SOURCE_MANIFEST.open())
    }
    summary_rows = []
    totals = Counter()

    for image_path in sorted(SOURCE_IMAGES.glob("*.jpg")):
        label_name = image_path.with_suffix(".txt").name
        golden_path = GOLD_LABELS / label_name
        if golden_path.exists():
            items = read_gold(golden_path)
            source = "user_approved_golden"
        else:
            items = read_predictions(PREDICTIONS / label_name)
            source = "golden10_yolo_plus_geometry_review"
        if label_name in MANUAL_ADDITIONS:
            items = classwise_nms(items + MANUAL_ADDITIONS[label_name])
            source = "golden10_yolo_plus_manual_dense_review"

        shutil.copy2(image_path, images_dir / image_path.name)
        label_text = "\n".join(
            f"{cls} {box[0]:.6f} {box[1]:.6f} {box[2]:.6f} {box[3]:.6f}"
            for cls, box, _ in items
        )
        (labels_dir / label_name).write_text(label_text + ("\n" if label_text else ""))
        draw_labels(image_path, items, visualized_dir / image_path.name)

        counts = Counter(cls for cls, _, _ in items)
        totals.update(counts)
        row = manifest_rows[image_path.name]
        summary_rows.append(
            {
                "image": image_path.name,
                "time_s": float(row["time_s"]),
                "group": row["group"],
                "source": source,
                "parcel": counts[0],
                "gate_open": counts[1],
                "gate_closed": counts[2],
            }
        )

    with (OUTPUT / "annotation_manifest.csv").open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=summary_rows[0].keys())
        writer.writeheader()
        writer.writerows(summary_rows)

    (OUTPUT / "summary.json").write_text(
        json.dumps(
            {
                "images": len(summary_rows),
                "totals": {CLASS_NAMES[k]: totals[k] for k in CLASS_NAMES},
                "golden_images": sum(
                    row["source"] == "user_approved_golden" for row in summary_rows
                ),
                "model_assisted_images": sum(
                    row["source"] != "user_approved_golden" for row in summary_rows
                ),
            },
            ensure_ascii=False,
            indent=2,
        )
    )

    visualized = sorted(visualized_dir.glob("*.jpg"))
    thumb_width, thumb_height, caption_height = 240, 427, 34
    try:
        caption_font = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 13)
    except OSError:
        caption_font = ImageFont.load_default()
    for page in range((len(visualized) + 19) // 20):
        batch = visualized[page * 20 : (page + 1) * 20]
        sheet = Image.new(
            "RGB",
            (thumb_width * 5, (thumb_height + caption_height) * 4),
            "white",
        )
        draw = ImageDraw.Draw(sheet)
        for index, image_path in enumerate(batch):
            image = Image.open(image_path).convert("RGB").resize(
                (thumb_width, thumb_height)
            )
            x = (index % 5) * thumb_width
            y = (index // 5) * (thumb_height + caption_height)
            sheet.paste(image, (x, y))
            draw.text(
                (x + 3, y + thumb_height + 4),
                image_path.stem,
                fill="black",
                font=caption_font,
            )
        sheet.save(contact_dir / f"page_{page + 1:02d}.jpg", quality=92)

    print(json.dumps(json.loads((OUTPUT / "summary.json").read_text()), ensure_ascii=False))


if __name__ == "__main__":
    main()
