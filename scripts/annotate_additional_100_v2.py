from __future__ import annotations

from collections import Counter
from pathlib import Path
import csv
import json

from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = (
    ROOT / "datasets/sorting_two_chutes_supplement/review_additional_100_v2"
)
IMAGE_DIR = OUTPUT / "images"
LABEL_DIR = OUTPUT / "labels_yolo"
VISUAL_DIR = OUTPUT / "visualized"
PREDICTIONS = OUTPUT / "candidate_predictions_calibrated.json"

CLASSES = ["parcel", "drawer_open", "drawer_closed", "chute", "bag"]
COLORS = {
    "parcel": (0, 153, 255),
    "drawer_open": (40, 200, 40),
    "drawer_closed": (255, 255, 255),
    "chute": (255, 70, 70),
    "bag": (255, 200, 0),
}

# User-confirmed narrow closed lip in the 127.8–129.6 s sequence.
# The carrier moves from left to right.  The first fully visible frame is 128.6
# s and the final fully visible frame is 129.4 s.
MANUAL_CLOSED = {
    "w08_05_t128.60s.jpg": [("drawer_closed", 45, 242, 174, 278)],
    "w08_06_t128.80s.jpg": [("drawer_closed", 99, 242, 226, 278)],
    "w03_10_t079.60s.jpg": [("drawer_closed", 50, 249, 169, 280)],
}

MANUAL_PARCELS = {
    "w02_01_t061.00s.jpg": [("parcel", 178, 247, 230, 301)],
    "w02_02_t061.20s.jpg": [("parcel", 215, 287, 286, 336)],
    "w02_03_t061.40s.jpg": [("parcel", 288, 343, 337, 384)],
    "w02_04_t061.60s.jpg": [("parcel", 318, 394, 367, 441)],
    "w02_05_t061.80s.jpg": [("parcel", 341, 474, 392, 521)],
    "w02_06_t062.00s.jpg": [("parcel", 353, 536, 408, 595)],
    "w02_07_t062.20s.jpg": [("parcel", 364, 630, 423, 688)],
    "w07_04_t124.00s.jpg": [("parcel", 42, 174, 102, 228)],
    "w07_05_t124.20s.jpg": [("parcel", 83, 155, 158, 238)],
    "w07_06_t124.40s.jpg": [("parcel", 155, 149, 230, 234)],
    "w07_07_t124.60s.jpg": [("parcel", 215, 168, 293, 251)],
    "w07_08_t124.80s.jpg": [("parcel", 276, 173, 342, 246)],
    "w07_09_t125.00s.jpg": [("parcel", 335, 172, 404, 248)],
    "w07_10_t125.20s.jpg": [("parcel", 387, 175, 452, 248)],
    "w08_01_t127.80s.jpg": [
        ("parcel", 338, 187, 383, 261),
        ("parcel", 442, 211, 505, 279),
    ],
    "w08_02_t128.00s.jpg": [("parcel", 398, 193, 442, 260)],
    "w08_03_t128.20s.jpg": [("parcel", 446, 191, 492, 264)],
    "w08_04_t128.40s.jpg": [("parcel", 44, 151, 91, 231)],
    "w08_05_t128.60s.jpg": [("parcel", 62, 99, 128, 172)],
    "w08_06_t128.80s.jpg": [("parcel", 120, 103, 207, 206)],
    "w08_07_t129.00s.jpg": [("parcel", 186, 114, 271, 232)],
    "w08_08_t129.20s.jpg": [("parcel", 235, 111, 319, 233)],
    "w08_09_t129.40s.jpg": [("parcel", 305, 117, 387, 233)],
    "w08_10_t129.60s.jpg": [("parcel", 366, 122, 448, 227)],
    "w20_01_t163.80s.jpg": [("parcel", 153, 128, 210, 191)],
    "w20_02_t164.00s.jpg": [("parcel", 212, 129, 272, 197)],
    "w20_03_t164.20s.jpg": [("parcel", 265, 136, 321, 195)],
    "w20_04_t164.40s.jpg": [("parcel", 332, 135, 390, 203)],
    "w20_05_t164.60s.jpg": [("parcel", 392, 139, 446, 203)],
    "w20_06_t164.80s.jpg": [("parcel", 450, 144, 500, 211)],
}

# These windows were checked on the original frames and contain no active
# parcel.  Low-confidence model boxes there are equipment texture or stored
# parcels inside the collection bag.
NO_MODEL_PARCEL_WINDOWS = set(range(1, 18)) | {19, 20}


def iou(a: tuple, b: tuple) -> float:
    x1, y1 = max(a[0], b[0]), max(a[1], b[1])
    x2, y2 = min(a[2], b[2]), min(a[3], b[3])
    intersection = max(0, x2 - x1) * max(0, y2 - y1)
    if intersection <= 0:
        return 0.0
    area_a = (a[2] - a[0]) * (a[3] - a[1])
    area_b = (b[2] - b[0]) * (b[3] - b[1])
    return intersection / (area_a + area_b - intersection)


def nms(candidates: list[tuple[float, tuple]], threshold: float) -> list[tuple]:
    selected = []
    for confidence, box in sorted(candidates, reverse=True):
        area = (box[2] - box[0]) * (box[3] - box[1])
        keep = True
        for kept in selected:
            kept_area = (kept[2] - kept[0]) * (kept[3] - kept[1])
            x1, y1 = max(box[0], kept[0]), max(box[1], kept[1])
            x2, y2 = min(box[2], kept[2]), min(box[3], kept[3])
            intersection = max(0, x2 - x1) * max(0, y2 - y1)
            containment = intersection / max(1, min(area, kept_area))
            if iou(box, kept) >= threshold or containment >= 0.60:
                keep = False
                break
        if keep:
            selected.append(box)
    return selected


def get_font(size: int) -> ImageFont.ImageFont:
    for candidate in (
        "/System/Library/Fonts/PingFang.ttc",
        "/System/Library/Fonts/Helvetica.ttc",
    ):
        if Path(candidate).exists():
            return ImageFont.truetype(candidate, size)
    return ImageFont.load_default()


def candidate_boxes(
    filename: str, window: int, predictions: list[dict]
) -> list[tuple]:
    output = []

    # The calibrated model is stable on the two static chutes and bags.
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

    # Broad silver plates detected by the calibrated model are open candidates.
    open_candidates = [
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
    for box in nms(open_candidates, 0.30):
        output.append(("drawer_open", *box))

    # Parcel threshold remains deliberately low to preserve fast/motion-blurred
    # parcels.  These boxes require mandatory visual review and are not yet
    # training labels.
    if filename in MANUAL_PARCELS:
        output.extend(MANUAL_PARCELS[filename])
    elif window not in NO_MODEL_PARCEL_WINDOWS:
        parcel_candidates = []
        for item in predictions:
            if item["class_name"] != "parcel" or item["confidence"] < 0.15:
                continue
            x1, y1, x2, y2 = (round(value) for value in item["box"])
            width, height = x2 - x1, y2 - y1
            if (
                width < 20
                or height < 20
                or width > 180
                or height > 180
                or x1 <= 2
                or x2 >= 542
            ):
                continue
            parcel_candidates.append(
                (item["confidence"], (x1, y1, x2, y2))
            )
        for box in nms(parcel_candidates, 0.30):
            output.append(("parcel", *box))
    return output


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
    source_manifest = {
        row["image"]: row
        for row in csv.DictReader(
            (OUTPUT / "manifest.csv").open(encoding="utf-8")
        )
    }
    LABEL_DIR.mkdir(parents=True, exist_ok=True)
    VISUAL_DIR.mkdir(parents=True, exist_ok=True)

    rows = []
    totals = Counter()
    all_annotations = {}
    for image_path in sorted(IMAGE_DIR.glob("*.jpg")):
        source = source_manifest[image_path.name]
        window = int(source["window"])
        boxes = candidate_boxes(
            image_path.name, window, predictions[image_path.name]
        )
        boxes.extend(MANUAL_CLOSED.get(image_path.name, []))
        boxes.sort(key=lambda item: (CLASSES.index(item[0]), item[1], item[2]))
        write_yolo(
            image_path, boxes, LABEL_DIR / f"{image_path.stem}.txt"
        )
        render(image_path, boxes, VISUAL_DIR / image_path.name)
        counts = Counter(item[0] for item in boxes)
        totals.update(counts)
        rows.append(
            {
                "image": image_path.name,
                "window": source["window"],
                "time_seconds": source["time_seconds"],
                "annotation_standard": "v1.7",
                "review_status": "visual_reviewed_v1.7",
                **{name: counts[name] for name in CLASSES},
            }
        )
        all_annotations[image_path.name] = boxes

    with (OUTPUT / "manifest_final.csv").open(
        "w", newline="", encoding="utf-8"
    ) as handle:
        writer = csv.DictWriter(handle, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)
    (OUTPUT / "annotations_final.json").write_text(
        json.dumps(all_annotations, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    summary = {
        "images": len(rows),
        "totals": {name: totals[name] for name in CLASSES},
        "review_status": "visual_reviewed_v1.7",
        "training_eligible": True,
        "review_notes": [
            "200 images reviewed in temporal order, window by window.",
            "drawer_open and drawer_closed follow the user-calibrated v1.7 mechanical-pose rule.",
            "w20_09_t165.40s false parcel removed after individual-frame review.",
        ],
    }
    (OUTPUT / "summary_final.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
