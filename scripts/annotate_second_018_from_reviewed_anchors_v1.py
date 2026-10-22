from __future__ import annotations

from pathlib import Path
import csv
import importlib.util

from PIL import Image, ImageDraw, ImageFont
from scipy.optimize import linear_sum_assignment
import numpy as np


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "datasets/sorting_yolo_stage1/all_video_frames"
OUTPUT = ROOT / "datasets/sorting_yolo_stage1/batches/second_018"
ANCHOR_SCRIPT = ROOT / "scripts/annotate_gpt56_sol_20_v1.py"

CLASSES = ["parcel", "drawer_open", "drawer_closed", "chute", "bag"]
COLORS = {
    "parcel": (0, 153, 255),
    "drawer_open": (40, 200, 40),
    "drawer_closed": (255, 255, 255),
    "chute": (255, 70, 70),
    "bag": (255, 200, 0),
}


def load_anchor_annotations():
    spec = importlib.util.spec_from_file_location("reviewed_anchor_module", ANCHOR_SCRIPT)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    anchors = {}
    for filename, boxes in module.ANNOTATIONS.items():
        marker = "_t"
        if marker not in filename:
            continue
        time_text = filename.rsplit(marker, 1)[1].rsplit(".jpg", 1)[0]
        time_seconds = float(time_text)
        if 18.0 <= time_seconds <= 19.0:
            frame_no = round(time_seconds * 30) + 1
            anchors[frame_no] = boxes
    return anchors


def center(box):
    _, x1, y1, x2, y2 = box
    return np.array(((x1 + x2) / 2, (y1 + y2) / 2), dtype=float)


def interpolate_pair(left_boxes, right_boxes, ratio):
    """Propagate reviewed 0.1 s anchors to the two in-between source frames.

    This is an explicit pre-annotation propagation step.  The generated frame
    remains marked `anchor_propagated_needs_review` until individually checked.
    """
    result = []
    for class_name in CLASSES:
        left = [box for box in left_boxes if box[0] == class_name]
        right = [box for box in right_boxes if box[0] == class_name]
        if not left or not right:
            # Do not invent a newly appearing/disappearing target between anchors.
            continue

        costs = np.zeros((len(left), len(right)), dtype=float)
        for i, a in enumerate(left):
            for j, b in enumerate(right):
                costs[i, j] = np.linalg.norm(center(a) - center(b))
        rows, cols = linear_sum_assignment(costs)
        max_distance = 180 if class_name == "parcel" else 130
        for i, j in zip(rows, cols):
            if costs[i, j] > max_distance:
                continue
            a = left[i]
            b = right[j]
            coords = tuple(
                round(a[k] + (b[k] - a[k]) * ratio) for k in range(1, 5)
            )
            result.append((class_name, *coords))
    return result


def boxes_for_frame(frame_no, anchors):
    if frame_no in anchors:
        boxes = list(anchors[frame_no])
        status = "reviewed_anchor_corrected_v1.2"
    else:
        lower = max(key for key in anchors if key < frame_no)
        upper = min(key for key in anchors if key > frame_no)
        ratio = (frame_no - lower) / (upper - lower)
        boxes = interpolate_pair(anchors[lower], anchors[upper], ratio)
        status = "anchor_propagated_needs_review"

    # The older anchor set contained only the main chute.  Under v1.2 the
    # adjacent right-hand channel must also be labeled because its channel body,
    # central divider and ownership are all identifiable even though its outer
    # side reaches the image edge.
    chutes = [item for item in boxes if item[0] == "chute"]
    if len(chutes) == 1:
        _, _, y1, main_x2, y2 = chutes[0]
        right_x1 = min(718, main_x2 + 8)
        if right_x1 < 718:
            boxes.append(("chute", right_x1, y1, 719, y2))
    return boxes, status


def to_yolo(width, height, item):
    class_name, x1, y1, x2, y2 = item
    return (
        f"{CLASSES.index(class_name)} {((x1 + x2) / 2) / width:.6f} "
        f"{((y1 + y2) / 2) / height:.6f} "
        f"{(x2 - x1) / width:.6f} {(y2 - y1) / height:.6f}"
    )


def render(image_path, boxes, output_path):
    image = Image.open(image_path).convert("RGB")
    draw = ImageDraw.Draw(image)
    font = ImageFont.load_default()
    for class_name, x1, y1, x2, y2 in boxes:
        color = COLORS[class_name]
        label = f"{CLASSES.index(class_name)}:{class_name}"
        draw.rectangle((x1, y1, x2, y2), outline=color, width=4)
        text_width = len(label) * 6 + 8
        text_y = max(0, y1 - 17)
        draw.rectangle((x1, text_y, x1 + text_width, text_y + 17), fill=color)
        text_color = (255, 255, 255) if class_name in {"parcel", "chute"} else (0, 0, 0)
        draw.text((x1 + 4, text_y + 3), label, fill=text_color, font=font)
    image.save(output_path, quality=94)


def main():
    anchors = load_anchor_annotations()
    expected = set(range(541, 572, 3))
    if set(anchors) != expected:
        raise RuntimeError(f"Unexpected reviewed anchors: {sorted(anchors)}")

    label_dir = OUTPUT / "labels_yolo"
    visual_dir = OUTPUT / "visualized"
    label_dir.mkdir(parents=True, exist_ok=True)
    visual_dir.mkdir(parents=True, exist_ok=True)

    rows = []
    for frame_no in range(541, 571):
        filename = f"frame_{frame_no:06d}.jpg"
        image_path = SOURCE / filename
        boxes, status = boxes_for_frame(frame_no, anchors)
        with Image.open(image_path) as image:
            width, height = image.size
        (label_dir / f"frame_{frame_no:06d}.txt").write_text(
            "\n".join(to_yolo(width, height, box) for box in boxes) + "\n",
            encoding="utf-8",
        )
        render(image_path, boxes, visual_dir / filename)
        counts = {
            class_name: sum(box[0] == class_name for box in boxes)
            for class_name in CLASSES
        }
        rows.append(
            {
                "image": filename,
                "frame_no": frame_no,
                "time_seconds": f"{(frame_no - 1) / 30:.3f}",
                "annotation_standard": "v1.2",
                **counts,
                "review_status": status,
            }
        )

    with (OUTPUT / "manifest.csv").open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)

    (OUTPUT / "README.md").write_text(
        "# 第 18 秒五类标注批次\n\n"
        "- 时间范围：18.000–18.967 秒\n"
        "- 图片：30 张，frame_000541.jpg 至 frame_000570.jpg\n"
        "- 标准：ANNOTATION_STANDARD_v1.md（v1.2）\n"
        "- 18.0、18.1……18.9 秒为既有 GPT 逐图复核锚点\n"
        "- 锚点之间两帧为时序传播候选，状态为 anchor_propagated_needs_review\n"
        "- 未使用 MiniMax-M3；未生成拼图\n",
        encoding="utf-8",
    )
    print(f"Wrote {len(rows)} frames to {OUTPUT}")


if __name__ == "__main__":
    main()
