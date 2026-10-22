from __future__ import annotations

from collections import Counter
from pathlib import Path
import csv
import json

import cv2
from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = (
    ROOT
    / "datasets/sorting_two_chutes_supplement/review_expansion_400_v1_7"
)
IMAGE_DIR = OUTPUT / "images"
LABEL_DIR = OUTPUT / "labels_yolo"
VISUAL_DIR = OUTPUT / "visualized"
PREDICTIONS = OUTPUT / "candidate_predictions_calibrated.json"
ANCHOR_IMAGE = (
    ROOT
    / "datasets/sorting_two_chutes_supplement/review_10_v1/images/"
    "sample_01_t5.40s.jpg"
)

CLASSES = ["parcel", "drawer_open", "drawer_closed", "chute", "bag"]
COLORS = {
    "parcel": (0, 153, 255),
    "drawer_open": (40, 200, 40),
    "drawer_closed": (255, 255, 255),
    "chute": (255, 70, 70),
    "bag": (255, 200, 0),
}

# Visual review corrections for the new camera angle.  These indices contained
# high-confidence parcel predictions on fixed metal ribs/rails rather than on
# physical parcels.
FALSE_PARCEL_INDICES = {
    17, 19, 21, 34, 42, 43, 44, 48, 77, 87, 101, 118, 119, 121,
    133, 138, 139, 153, 163, 167, 169, 170, 171, 172, 189, 190,
}

# Parcels recovered during frame-by-frame review.  Most are deliberately taken
# from lower-confidence model proposals so that the boxes stay reproducible.
# They cover thin white parcels, bright green parcels, large white/blue bags,
# and parcels already descending toward a chute.
MANUAL_PARCELS = {
    11: [(21, 164, 70, 240)],
    12: [(25, 211, 87, 289)],
    13: [(162, 219, 228, 294)],
    173: [(470, 188, 534, 279)],
    211: [(84, 284, 134, 333)],
    212: [(227, 186, 259, 245), (224, 291, 267, 339)],
    213: [(365, 297, 407, 346)],
    214: [(451, 283, 496, 332)],
    241: [(289, 152, 380, 265)],
    242: [(419, 162, 504, 272)],
    252: [(108, 124, 178, 237)],
    253: [(239, 167, 304, 249)],
    254: [(373, 176, 433, 260)],
    292: [(0, 93, 79, 206)],
    293: [(120, 103, 206, 205)],
    294: [(265, 128, 339, 240)],
    295: [(383, 123, 469, 232)],
    296: [(509, 134, 543, 200)],
    320: [(270, 153, 306, 210)],
    321: [(77, 119, 188, 244)],
    322: [(215, 136, 329, 260)],
    323: [(357, 172, 463, 265)],
    324: [(470, 156, 543, 273)],
    325: [(10, 107, 82, 221)],
    326: [(161, 138, 214, 207)],
    367: [(0, 126, 110, 224)],
    368: [(24, 86, 82, 208), (128, 140, 245, 243)],
    369: [(153, 156, 221, 240), (274, 154, 389, 256)],
    370: [(396, 148, 521, 267)],
    371: [(420, 174, 485, 260)],
    388: [(122, 68, 178, 177)],
    389: [(267, 81, 311, 182)],
}


def image_index(image_name: str) -> int:
    return int(image_name[1:5])


def iou(a: tuple, b: tuple) -> float:
    x1, y1 = max(a[0], b[0]), max(a[1], b[1])
    x2, y2 = min(a[2], b[2]), min(a[3], b[3])
    intersection = max(0, x2 - x1) * max(0, y2 - y1)
    if intersection <= 0:
        return 0.0
    aa = (a[2] - a[0]) * (a[3] - a[1])
    bb = (b[2] - b[0]) * (b[3] - b[1])
    return intersection / (aa + bb - intersection)


def nms(candidates: list[tuple[float, tuple]], threshold: float) -> list[tuple]:
    selected = []
    for confidence, box in sorted(candidates, reverse=True):
        if all(iou(box, kept) < threshold for kept in selected):
            selected.append(box)
    return selected


def predicted_boxes(predictions: list[dict], index: int) -> list[tuple]:
    output = []
    for class_name in ("chute", "bag"):
        candidates = [
            (
                item["confidence"],
                tuple(round(value) for value in item["box"]),
            )
            for item in predictions
            if item["class_name"] == class_name
            and item["confidence"] >= 0.50
        ]
        for box in nms(candidates, 0.35)[:2]:
            output.append((class_name, *box))

    opens = [
        (
            item["confidence"],
            tuple(round(value) for value in item["box"]),
        )
        for item in predictions
        if item["class_name"] == "drawer_open"
        and item["confidence"] >= 0.50
        and item["box"][0] > 2
        and item["box"][2] < 542
    ]
    for box in nms(opens, 0.30):
        output.append(("drawer_open", *box))

    parcels = []
    if index not in FALSE_PARCEL_INDICES:
        for item in predictions:
            if item["class_name"] != "parcel" or item["confidence"] < 0.40:
                continue
            x1, y1, x2, y2 = (round(value) for value in item["box"])
            width, height = x2 - x1, y2 - y1
            if (
                width < 35
                or height < 20
                or width > 180
                or height > 180
                or height / max(1, width) > 2.10
                or x1 <= 2
                or x2 >= 542
            ):
                continue
            parcels.append((item["confidence"], (x1, y1, x2, y2)))
    for box in MANUAL_PARCELS.get(index, []):
        parcels.append((1.0, box))
    for box in nms(parcels, 0.30):
        output.append(("parcel", *box))
    return output


def closed_candidates(image_path: Path, open_boxes: list[tuple]) -> list[tuple]:
    """Generate candidates for the narrow, flush closed lip only."""
    anchor = cv2.imread(str(ANCHOR_IMAGE), cv2.IMREAD_GRAYSCALE)
    image = cv2.imread(str(image_path), cv2.IMREAD_GRAYSCALE)
    templates = [
        anchor[266:302, 107:228],
        anchor[260:306, 268:381],
        anchor[261:303, 403:531],
    ]
    candidates: list[tuple[float, tuple]] = []
    strip = image[235:325]
    for template in templates:
        match = cv2.matchTemplate(strip, template, cv2.TM_CCOEFF_NORMED)
        while True:
            _, score, _, location = cv2.minMaxLoc(match)
            if score < 0.62:
                break
            x, local_y = location
            y = local_y + 235
            height, width = template.shape
            candidates.append(
                (float(score), (x, y, x + width, y + height))
            )
            cv2.rectangle(
                match,
                (max(0, x - width // 2), max(0, local_y - 8)),
                (
                    min(match.shape[1] - 1, x + width // 2),
                    min(match.shape[0] - 1, local_y + 8),
                ),
                -1,
                -1,
            )
    result = []
    for box in nms(candidates, 0.22):
        if box[0] <= 2 or box[2] >= 542:
            continue
        overlaps_open = False
        for item in open_boxes:
            open_box = item[1:]
            horizontal_overlap = max(
                0, min(box[2], open_box[2]) - max(box[0], open_box[0])
            )
            horizontal_containment = horizontal_overlap / max(
                1, min(box[2] - box[0], open_box[2] - open_box[0])
            )
            vertical_gap = max(
                0, open_box[1] - box[3], box[1] - open_box[3]
            )
            if (
                iou(box, open_box) > 0.10
                or (
                    horizontal_containment > 0.50
                    and vertical_gap < 60
                )
            ):
                overlaps_open = True
                break
        if overlaps_open:
            continue
        # A valid closed lip must belong to a bright silver carrier directly
        # above it.  This rejects dark drive mechanisms and orange rail
        # textures that resemble the lip template.
        region_above = image[max(0, box[1] - 100) : box[1], box[0] : box[2]]
        if (
            region_above.size == 0
            or float(region_above.mean()) < 120
            or float((region_above > 150).mean()) < 0.30
        ):
            continue
        result.append(("drawer_closed", *box))
    return result


def get_font(size: int) -> ImageFont.ImageFont:
    for candidate in (
        "/System/Library/Fonts/PingFang.ttc",
        "/System/Library/Fonts/Helvetica.ttc",
    ):
        if Path(candidate).exists():
            return ImageFont.truetype(candidate, size)
    return ImageFont.load_default()


def write_yolo(image_path: Path, boxes: list[tuple], output_path: Path) -> None:
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


def render(image_path: Path, boxes: list[tuple], output_path: Path) -> None:
    image = Image.open(image_path).convert("RGB")
    draw = ImageDraw.Draw(image)
    font = get_font(13)
    for class_name, x1, y1, x2, y2 in boxes:
        color = COLORS[class_name]
        label = f"{CLASSES.index(class_name)}:{class_name}"
        draw.rectangle((x1, y1, x2, y2), outline=color, width=4)
        text_box = draw.textbbox((x1, y1), label, font=font)
        label_width = text_box[2] - text_box[0] + 8
        label_height = text_box[3] - text_box[1] + 6
        label_y = max(0, y1 - label_height)
        draw.rectangle((x1, label_y, x1 + label_width, y1), fill=color)
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
    predictions = json.loads(PREDICTIONS.read_text(encoding="utf-8"))
    source_rows = {
        row["image"]: row
        for row in csv.DictReader(
            (OUTPUT / "manifest_source.csv").open(encoding="utf-8")
        )
    }
    LABEL_DIR.mkdir(parents=True, exist_ok=True)
    VISUAL_DIR.mkdir(parents=True, exist_ok=True)

    rows = []
    totals = Counter()
    annotations = {}
    for image_path in sorted(IMAGE_DIR.glob("*.jpg")):
        boxes = predicted_boxes(
            predictions[image_path.name],
            image_index(image_path.name),
        )
        opens = [item for item in boxes if item[0] == "drawer_open"]
        boxes.extend(closed_candidates(image_path, opens))
        boxes.sort(key=lambda item: (CLASSES.index(item[0]), item[1], item[2]))
        write_yolo(image_path, boxes, LABEL_DIR / f"{image_path.stem}.txt")
        render(image_path, boxes, VISUAL_DIR / image_path.name)
        counts = Counter(item[0] for item in boxes)
        totals.update(counts)
        source = source_rows[image_path.name]
        rows.append(
            {
                "image": image_path.name,
                "time_seconds": source["time_seconds"],
                "annotation_standard": "v1.7",
                "review_status": "visual_reviewed_v1.7",
                **{name: counts[name] for name in CLASSES},
            }
        )
        annotations[image_path.name] = boxes

    with (OUTPUT / "manifest.csv").open(
        "w", newline="", encoding="utf-8"
    ) as handle:
        writer = csv.DictWriter(handle, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)
    (OUTPUT / "annotations.json").write_text(
        json.dumps(annotations, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    summary = {
        "images": len(rows),
        "totals": {name: totals[name] for name in CLASSES},
        "review_status": "visual_reviewed_v1.7",
        "training_eligible": True,
    }
    (OUTPUT / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
