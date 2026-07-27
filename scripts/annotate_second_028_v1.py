from __future__ import annotations

from pathlib import Path
import csv

from PIL import Image, ImageDraw, ImageFont


ROOT = Path("/Users/lixing.guo/Documents/机械臂")
SOURCE = ROOT / "datasets/sorting_yolo_stage1/all_video_frames"
OUTPUT = ROOT / "datasets/sorting_yolo_stage1/batches/second_028"
CLASSES = ["parcel", "drawer_open", "drawer_closed", "chute", "bag"]
COLORS = {0: (0, 153, 255), 1: (40, 200, 40), 2: (255, 255, 255),
          3: (255, 70, 70), 4: (255, 200, 0)}


def add_complete(items, class_id, x1, y1, x2, y2):
    if x1 >= 2 and x2 <= 718 and x2 > x1 and y2 > y1:
        items.append((class_id, round(x1), round(y1), round(x2), round(y2)))


PARCEL_ANCHORS = {
    853: (78, 425, 171, 471),
    856: (111, 439, 226, 493),
    861: (158, 493, 232, 540),
    866: (190, 547, 265, 601),
    870: (201, 602, 284, 654),
}

OPEN_A = {841: (463, 418, 622, 458), 846: (540, 418, 718, 458)}
OPEN_B = {
    849: (20, 420, 196, 458),
    851: (51, 420, 232, 458),
    856: (61, 420, 218, 458),
    861: (136, 420, 294, 458),
    866: (211, 420, 369, 458),
    870: (272, 420, 429, 458),
}
CLOSED_A = {
    841: (20, 375, 206, 426), 846: (129, 375, 284, 426),
    851: (205, 375, 355, 426), 856: (280, 375, 432, 426),
    861: (350, 375, 506, 426), 866: (433, 375, 585, 426),
    870: (489, 375, 646, 426),
}
CLOSED_B = {
    841: (265, 375, 443, 426), 846: (340, 375, 489, 426),
    851: (410, 375, 565, 426), 856: (475, 375, 638, 426),
    861: (562, 375, 718, 426),
}
CLOSED_C = {
    861: (2, 375, 96, 426), 866: (26, 375, 172, 426),
    870: (55, 375, 229, 426),
}


def interpolate(frame_no, anchors):
    keys = sorted(anchors)
    if frame_no <= keys[0]:
        return anchors[keys[0]]
    for left, right in zip(keys, keys[1:]):
        if left <= frame_no <= right:
            t = (frame_no - left) / (right - left)
            return tuple(anchors[left][i] + t * (anchors[right][i] - anchors[left][i])
                         for i in range(4))
    return anchors[keys[-1]]


def boxes_for_frame(frame_no):
    k = frame_no - 841
    boxes = []

    if frame_no >= 853:
        add_complete(boxes, 0, *interpolate(frame_no, PARCEL_ANCHORS))

    # Flat silver door plates repeat with the moving sorter.
    if frame_no <= 846:
        add_complete(boxes, 1, *interpolate(frame_no, OPEN_A))
    if frame_no >= 849:
        add_complete(boxes, 1, *interpolate(frame_no, OPEN_B))

    # Only the complete orange upright door plates are drawer_closed.
    add_complete(boxes, 2, *interpolate(frame_no, CLOSED_A))
    if frame_no <= 861:
        add_complete(boxes, 2, *interpolate(frame_no, CLOSED_B))
    if frame_no >= 861:
        add_complete(boxes, 2, *interpolate(frame_no, CLOSED_C))

    boxes.append((3, 0, 480, 420, 786))
    boxes.append((3, 423, 480, 719, 777))
    boxes.append((4, 0, 866, 500, 1279))
    return boxes


def to_yolo(width, height, item):
    c, x1, y1, x2, y2 = item
    return (f"{c} {((x1+x2)/2)/width:.6f} {((y1+y2)/2)/height:.6f} "
            f"{(x2-x1)/width:.6f} {(y2-y1)/height:.6f}")


def render(image_path, annotations, destination):
    im = Image.open(image_path).convert("RGB")
    draw = ImageDraw.Draw(im)
    font = ImageFont.load_default()
    for c, x1, y1, x2, y2 in annotations:
        color = COLORS[c]
        label = f"{c}:{CLASSES[c]}"
        draw.rectangle((x1, y1, x2, y2), outline=color, width=4)
        tw = len(label) * 6 + 8
        ty = max(0, y1 - 17)
        draw.rectangle((x1, ty, x1 + tw, ty + 17), fill=color)
        draw.text((x1 + 4, ty + 3), label,
                  fill=(0, 0, 0) if c in {1, 2, 4} else (255, 255, 255), font=font)
    im.save(destination, quality=94)


def main():
    label_dir = OUTPUT / "labels_yolo"
    visual_dir = OUTPUT / "visualized"
    label_dir.mkdir(parents=True, exist_ok=True)
    visual_dir.mkdir(parents=True, exist_ok=True)
    rows = []
    for frame_no in range(841, 871):
        filename = f"frame_{frame_no:06d}.jpg"
        image_path = SOURCE / filename
        annotations = boxes_for_frame(frame_no)
        with Image.open(image_path) as im:
            width, height = im.size
        (label_dir / f"frame_{frame_no:06d}.txt").write_text(
            "\n".join(to_yolo(width, height, a) for a in annotations) + "\n",
            encoding="utf-8")
        render(image_path, annotations, visual_dir / filename)
        counts = {name: sum(a[0] == c for a in annotations)
                  for c, name in enumerate(CLASSES)}
        rows.append({"image": filename, "frame_no": frame_no,
                     "time_seconds": f"{(frame_no-1)/30:.3f}",
                     "annotation_standard": "v1.2", **counts,
                     "review_status": "visual_reviewed_first_pass"})
    with (OUTPUT / "manifest.csv").open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)
    (OUTPUT / "README.md").write_text(
        "# 第 28 秒五类标注批次\n\n"
        "- 时间范围：28.000–28.967 秒\n"
        "- 图片：30 张，未生成拼图\n"
        "- 标准：ANNOTATION_STANDARD_v1.md（v1.2）\n"
        "- 黑色包裹从水平打开门板离开并进入左侧闸口\n"
        "- 状态：visual_reviewed_first_pass，等待用户抽查\n",
        encoding="utf-8")


if __name__ == "__main__":
    main()
