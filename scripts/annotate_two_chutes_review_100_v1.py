from __future__ import annotations

from collections import Counter
from pathlib import Path
import csv
import json

import cv2
from PIL import Image, ImageDraw, ImageFont


ROOT = Path("/Users/lixing.guo/Documents/机械臂")
OUTPUT = ROOT / "datasets/sorting_two_chutes_supplement/review_100_v1"
IMAGE_DIR = OUTPUT / "images"
LABEL_DIR = OUTPUT / "labels_yolo"
VISUAL_DIR = OUTPUT / "visualized"
CALIBRATED_JSON = OUTPUT / "candidate_predictions_calibrated.json"
ANCHOR_IMAGE = (
    ROOT
    / "datasets/sorting_two_chutes_supplement/review_10_v1/images/sample_01_t5.40s.jpg"
)

CLASSES = ["parcel", "drawer_open", "drawer_closed", "chute", "bag"]
COLORS = {
    "parcel": (0, 153, 255),
    "drawer_open": (40, 200, 40),
    "drawer_closed": (255, 255, 255),
    "chute": (255, 70, 70),
    "bag": (255, 200, 0),
}

# Confirmed scene regions.  These are static scene entities, but each frame is
# still checked for visibility before final delivery.
SCENE_BOXES = {
    1: [
        ("chute", 0, 352, 287, 670),
        ("chute", 291, 350, 543, 665),
        ("bag", 120, 710, 345, 959),
        ("bag", 353, 701, 543, 959),
    ],
    2: [
        ("chute", 0, 340, 250, 647),
        ("chute", 254, 339, 530, 643),
        ("bag", 84, 695, 276, 959),
        ("bag", 329, 688, 530, 959),
    ],
    3: [
        ("chute", 0, 341, 276, 647),
        ("chute", 280, 340, 530, 642),
        ("bag", 105, 695, 298, 959),
        ("bag", 354, 690, 530, 959),
    ],
    4: [
        ("chute", 0, 340, 276, 647),
        ("chute", 280, 339, 530, 642),
        ("bag", 105, 695, 298, 959),
        ("bag", 354, 690, 530, 959),
    ],
    5: [
        ("chute", 0, 340, 276, 647),
        ("chute", 280, 339, 530, 642),
        ("bag", 105, 695, 298, 959),
        ("bag", 354, 690, 530, 959),
    ],
}


def parcel_box(cx: float, cy: float, w: float, h: float) -> tuple | None:
    x1, y1, x2, y2 = cx - w / 2, cy - h / 2, cx + w / 2, cy + h / 2
    # An entity cut by the frame boundary is not labelled under v1.5.
    if x1 < 0 or y1 < 0 or x2 > 544 or y2 > 960:
        return None
    return (
        "parcel",
        round(x1),
        round(y1),
        round(x2),
        round(y2),
    )


# Parcel paths were read frame by frame.  Interpolated centres are only used
# within a visually confirmed continuous trajectory; boundary boxes are padded
# so the full soft parcel, including motion blur, stays inside the box.
PARCELS: dict[str, list[tuple]] = {}


def add_path(window: int, frames: range, x0: float, dx: float, y: float, w: float, h: float):
    for offset, frame_no in enumerate(frames):
        box = parcel_box(x0 + dx * offset, y, w, h)
        if box is not None:
            PARCELS.setdefault(f"w{window}_{frame_no:02d}.jpg", []).append(box)


# w1: black parcel, two visible passes.
add_path(1, range(1, 4), 386, 55, 263, 68, 70)
add_path(1, range(6, 14), 82, 56, 262, 70, 82)
add_path(1, range(18, 21), 121, 57, 220, 64, 72)
# w2: white mailer, two passes.
add_path(2, range(4, 13), 36, 55.5, 235, 66, 82)
add_path(2, range(15, 21), 52, 57, 231, 72, 72)
# w3: one continuous grey-mailer pass.
add_path(3, range(6, 15), 24, 60.7, 248, 72, 72)
# w4: first pass plus the beginning of a second pass.  Both are visible in
# frames 17–18, so those frames legitimately contain two parcel boxes.
add_path(4, range(9, 18), 19, 56, 248, 76, 94)
add_path(4, range(17, 21), 55, 56, 216, 60, 62)
# w5: continuation seen at 43.8 s; it exits on the right by frame 5.
add_path(5, range(1, 6), 318, 56, 216, 52, 70)


def iou(a: tuple[float, float, float, float], b: tuple[float, float, float, float]) -> float:
    x1, y1 = max(a[0], b[0]), max(a[1], b[1])
    x2, y2 = min(a[2], b[2]), min(a[3], b[3])
    inter = max(0, x2 - x1) * max(0, y2 - y1)
    if inter == 0:
        return 0.0
    aa = (a[2] - a[0]) * (a[3] - a[1])
    bb = (b[2] - b[0]) * (b[3] - b[1])
    return inter / (aa + bb - inter)


def nms(candidates: list[tuple[float, tuple]], threshold: float = 0.25) -> list[tuple]:
    selected: list[tuple] = []
    for score, box in sorted(candidates, reverse=True):
        if all(iou(box, kept) < threshold for kept in selected):
            selected.append(box)
    return selected


def load_open_candidates() -> dict[str, list[tuple]]:
    raw = json.loads(CALIBRATED_JSON.read_text(encoding="utf-8"))
    output: dict[str, list[tuple]] = {}
    for filename, predictions in raw.items():
        candidates = []
        for pred in predictions:
            if pred["class_name"] != "drawer_open" or pred["confidence"] < 0.50:
                continue
            x1, y1, x2, y2 = pred["box"]
            w, h = x2 - x1, y2 - y1
            if not (55 <= w <= 165 and 25 <= h <= 65 and 275 <= y1 <= 315 and y2 <= 360):
                continue
            if x1 < 4 or x2 > 540:
                continue
            # Small padding keeps the entire light horizontal plate inside.
            box = (
                max(0, round(x1 - 3)),
                max(0, round(y1 - 3)),
                min(543, round(x2 + 3)),
                min(959, round(y2 + 3)),
            )
            candidates.append((float(pred["confidence"]), box))
        output[filename] = [("drawer_open", *box) for box in nms(candidates, 0.30)]
    return output


def closed_candidates(image_path: Path, open_boxes: list[tuple]) -> list[tuple]:
    """Match only the confirmed blue/grey front closed lips.

    The three templates are from the user-confirmed 5.40 s frame.  Matching is
    restricted to the physical lip band and deduplicated.  It does not label
    the orange rail, white chute surface, or exposed black mechanism.
    """
    anchor = cv2.imread(str(ANCHOR_IMAGE), cv2.IMREAD_GRAYSCALE)
    image = cv2.imread(str(image_path), cv2.IMREAD_GRAYSCALE)
    templates = [
        anchor[266:302, 107:228],
        anchor[260:306, 268:381],
        anchor[261:303, 403:531],
    ]
    candidates: list[tuple[float, tuple]] = []
    strip = image[242:322]
    for template in templates:
        result = cv2.matchTemplate(strip, template, cv2.TM_CCOEFF_NORMED)
        while True:
            _, score, _, location = cv2.minMaxLoc(result)
            if score < 0.60:
                break
            x, local_y = location
            y = local_y + 242
            h, w = template.shape
            box = (x, y, x + w, y + h)
            candidates.append((float(score), box))
            cv2.rectangle(
                result,
                (max(0, x - w // 2), max(0, local_y - 8)),
                (min(result.shape[1] - 1, x + w // 2), min(result.shape[0] - 1, local_y + 8)),
                -1,
                -1,
            )
    kept = nms(candidates, 0.22)
    result = []
    for box in kept:
        if box[0] <= 2 or box[2] >= 542:
            continue
        if any(iou(box, item[1:]) > 0.12 for item in open_boxes):
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
    font = get_font(14)
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
    open_candidates = load_open_candidates()
    totals = Counter()
    rows = []
    all_annotations = {}

    for image_path in sorted(IMAGE_DIR.glob("w*.jpg")):
        window = int(image_path.stem[1])
        opens = open_candidates.get(image_path.name, [])
        closed = closed_candidates(image_path, opens)
        boxes = PARCELS.get(image_path.name, []) + opens + closed + SCENE_BOXES[window]
        boxes.sort(key=lambda item: (CLASSES.index(item[0]), item[1], item[2]))

        with Image.open(image_path) as image:
            width, height = image.size
        for box in boxes:
            _, x1, y1, x2, y2 = box
            if not (0 <= x1 < x2 < width and 0 <= y1 < y2 < height):
                raise ValueError(f"Invalid box {image_path.name}: {box}")

        write_label(image_path, boxes, LABEL_DIR / f"{image_path.stem}.txt")
        render(image_path, boxes, VISUAL_DIR / image_path.name)
        counts = Counter(item[0] for item in boxes)
        totals.update(counts)
        rows.append(
            {
                "image": image_path.name,
                "annotation_standard": "v1.5",
                "review_status": "visual_reviewed_first_pass",
                **{name: counts[name] for name in CLASSES},
            }
        )
        all_annotations[image_path.name] = boxes

    with (OUTPUT / "manifest.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)
    (OUTPUT / "classes.txt").write_text("\n".join(CLASSES) + "\n", encoding="utf-8")
    (OUTPUT / "annotations.json").write_text(
        json.dumps(all_annotations, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    (OUTPUT / "summary.json").write_text(
        json.dumps({"images": len(rows), "totals": totals}, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    (OUTPUT / "README.md").write_text(
        "# 两个口视频：100张补充标注\n\n"
        "- 标准：`ANNOTATION_STANDARD_v1.md` v1.5\n"
        "- 类别：parcel、drawer_open、drawer_closed、chute、bag\n"
        "- 每张图独立输出可视化和 YOLO 标签，不使用交付拼图。\n"
        "- 新机位 drawer_closed 只框抽屉前端关闭下沿，不框整车或橙色导轨。\n"
        "- 状态：visual_reviewed_first_pass，供用户抽检后再并入训练集。\n",
        encoding="utf-8",
    )
    print(json.dumps({"images": len(rows), "totals": dict(totals)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
