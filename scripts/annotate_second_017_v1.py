from __future__ import annotations

from pathlib import Path
import csv

from PIL import Image, ImageDraw, ImageFont
from scipy.optimize import linear_sum_assignment
import numpy as np


ROOT = Path("/Users/lixing.guo/Documents/机械臂")
SOURCE = ROOT / "datasets/sorting_yolo_stage1/all_video_frames"
OUTPUT = ROOT / "datasets/sorting_yolo_stage1/batches/second_017"
CLASSES = ["parcel", "drawer_open", "drawer_closed", "chute", "bag"]
COLORS = {
    0: (0, 153, 255),
    1: (40, 200, 40),
    2: (255, 255, 255),
    3: (255, 70, 70),
    4: (255, 200, 0),
}


# Frames at 0.1-second intervals were checked separately.  Boxes use
# (class_id, x1, y1, x2, y2).
ANCHORS = {
    511: [
        (1, 378, 386, 553, 422),
        (2, 153, 348, 335, 406),
        (3, 88, 448, 558, 744),
        (3, 566, 448, 719, 744),
        (4, 111, 829, 607, 1279),
    ],
    514: [
        (1, 432, 386, 592, 423),
        (2, 27, 344, 177, 400),
        (2, 226, 347, 382, 404),
        (3, 90, 448, 559, 746),
        (3, 567, 448, 719, 746),
        (4, 113, 832, 610, 1279),
    ],
    517: [
        (1, 477, 387, 643, 424),
        (2, 87, 345, 240, 402),
        (2, 282, 346, 436, 404),
        (3, 92, 449, 560, 748),
        (3, 568, 449, 719, 748),
        (4, 114, 835, 613, 1279),
    ],
    520: [
        (1, 523, 391, 697, 430),
        (2, 119, 349, 271, 405),
        (2, 318, 350, 469, 406),
        (3, 94, 452, 560, 750),
        (3, 568, 452, 719, 750),
        (4, 115, 839, 616, 1279),
    ],
    523: [
        (2, 154, 351, 307, 407),
        (2, 357, 351, 510, 408),
        (3, 96, 455, 560, 752),
        (3, 568, 455, 719, 752),
        (4, 116, 843, 620, 1279),
    ],
    526: [
        (2, 188, 354, 344, 410),
        (2, 393, 354, 553, 411),
        (3, 98, 459, 558, 754),
        (3, 566, 459, 719, 754),
        (4, 117, 846, 624, 1279),
    ],
    529: [
        (2, 210, 372, 388, 429),
        (2, 422, 370, 606, 428),
        (3, 80, 488, 555, 752),
        (3, 563, 488, 719, 752),
        (4, 117, 848, 638, 1279),
    ],
    532: [
        (2, 55, 374, 221, 430),
        (2, 270, 372, 432, 428),
        (3, 88, 488, 560, 752),
        (3, 568, 488, 719, 752),
        (4, 118, 848, 638, 1279),
    ],
    535: [
        (2, 95, 375, 258, 431),
        (2, 304, 373, 468, 430),
        (3, 96, 488, 560, 752),
        (3, 568, 488, 719, 752),
        (4, 119, 848, 638, 1279),
    ],
    538: [
        (0, 389, 342, 456, 411),
        (2, 132, 376, 294, 432),
        (2, 338, 374, 502, 431),
        (3, 106, 488, 560, 752),
        (3, 568, 488, 719, 752),
        (4, 120, 848, 638, 1279),
    ],
    539: [
        (0, 400, 343, 469, 413),
        (2, 145, 378, 307, 433),
        (2, 351, 376, 515, 432),
        (3, 112, 488, 557, 748),
        (3, 565, 488, 719, 748),
        (4, 121, 849, 635, 1279),
    ],
    540: [
        (0, 411, 344, 480, 414),
        (1, 390, 421, 553, 462),
        (2, 175, 380, 328, 434),
        (3, 124, 488, 551, 741),
        (3, 559, 488, 719, 741),
        (4, 121, 849, 632, 1279),
    ],
    541: [
        (0, 55, 305, 155, 370),
        (0, 407, 330, 485, 416),
        (1, 388, 423, 560, 466),
        (2, 195, 382, 345, 428),
        (3, 136, 488, 545, 733),
        (3, 553, 488, 719, 733),
        (4, 122, 850, 628, 1279),
    ],
}


def center(box):
    return np.array(((box[1] + box[3]) / 2, (box[2] + box[4]) / 2))


def interpolate(left, right, ratio):
    result = []
    for class_id in range(5):
        a = [box for box in left if box[0] == class_id]
        b = [box for box in right if box[0] == class_id]
        if not a or not b:
            continue
        costs = np.array(
            [[np.linalg.norm(center(x) - center(y)) for y in b] for x in a]
        )
        rows, cols = linear_sum_assignment(costs)
        for i, j in zip(rows, cols):
            if costs[i, j] > (180 if class_id == 0 else 135):
                continue
            coords = tuple(
                round(a[i][k] + (b[j][k] - a[i][k]) * ratio)
                for k in range(1, 5)
            )
            result.append((class_id, *coords))
    return result


def boxes_for_frame(frame_no):
    if frame_no in ANCHORS:
        return ANCHORS[frame_no], "reviewed_anchor"
    lower = max(key for key in ANCHORS if key < frame_no)
    upper = min(key for key in ANCHORS if key > frame_no)
    ratio = (frame_no - lower) / (upper - lower)
    return interpolate(ANCHORS[lower], ANCHORS[upper], ratio), "anchor_propagated_needs_review"


def to_yolo(width, height, item):
    class_id, x1, y1, x2, y2 = item
    return (
        f"{class_id} {((x1 + x2) / 2) / width:.6f} "
        f"{((y1 + y2) / 2) / height:.6f} "
        f"{(x2 - x1) / width:.6f} {(y2 - y1) / height:.6f}"
    )


def render(image_path, annotations, destination):
    image = Image.open(image_path).convert("RGB")
    draw = ImageDraw.Draw(image)
    font = ImageFont.load_default()
    for class_id, x1, y1, x2, y2 in annotations:
        color = COLORS[class_id]
        label = f"{class_id}:{CLASSES[class_id]}"
        draw.rectangle((x1, y1, x2, y2), outline=color, width=4)
        text_width = len(label) * 6 + 8
        text_y = max(0, y1 - 17)
        draw.rectangle((x1, text_y, x1 + text_width, text_y + 17), fill=color)
        text_color = (0, 0, 0) if class_id in {1, 2, 4} else (255, 255, 255)
        draw.text((x1 + 4, text_y + 3), label, fill=text_color, font=font)
    image.save(destination, quality=94)


def main():
    label_dir = OUTPUT / "labels_yolo"
    visual_dir = OUTPUT / "visualized"
    label_dir.mkdir(parents=True, exist_ok=True)
    visual_dir.mkdir(parents=True, exist_ok=True)
    rows = []
    for frame_no in range(511, 541):
        filename = f"frame_{frame_no:06d}.jpg"
        source = SOURCE / filename
        annotations, status = boxes_for_frame(frame_no)
        with Image.open(source) as image:
            width, height = image.size
        (label_dir / f"frame_{frame_no:06d}.txt").write_text(
            "\n".join(to_yolo(width, height, item) for item in annotations) + "\n",
            encoding="utf-8",
        )
        render(source, annotations, visual_dir / filename)
        counts = {
            name: sum(item[0] == class_id for item in annotations)
            for class_id, name in enumerate(CLASSES)
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
        "# 第 17 秒五类标注批次\n\n"
        "- 时间范围：17.000–17.967 秒\n"
        "- 图片：30 张，frame_000511.jpg 至 frame_000540.jpg\n"
        "- 标准：ANNOTATION_STANDARD_v1.md（v1.2）\n"
        "- 每 0.1 秒逐图检查一个锚点；中间帧为传播候选，仍需最终逐帧复核\n"
        "- 两个可辨认闸口均已保留；未使用 MiniMax-M3；未生成拼图\n",
        encoding="utf-8",
    )
    print(f"Wrote 30 frames to {OUTPUT}")


if __name__ == "__main__":
    main()
