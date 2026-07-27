from __future__ import annotations

from pathlib import Path
import csv
from PIL import Image, ImageDraw, ImageFont

ROOT = Path("/Users/lixing.guo/Documents/机械臂")
SOURCE = ROOT / "datasets/sorting_yolo_stage1/all_video_frames"
BATCH_ROOT = ROOT / "datasets/sorting_yolo_stage1/batches"
CLASSES = ["parcel", "drawer_open", "drawer_closed", "chute", "bag"]
COLORS = {0: (0, 153, 255), 1: (40, 200, 40), 2: (255, 255, 255),
          3: (255, 70, 70), 4: (255, 200, 0)}


def add_complete(items, class_id, box):
    x1, y1, x2, y2 = box
    if x1 >= 2 and x2 <= 718 and x2 > x1 and y2 > y1:
        items.append((class_id, round(x1), round(y1), round(x2), round(y2)))


def interpolate(frame_no, anchors):
    keys = sorted(anchors)
    if frame_no <= keys[0]:
        return anchors[keys[0]]
    for left, right in zip(keys, keys[1:]):
        if left <= frame_no <= right:
            t = (frame_no-left)/(right-left)
            return tuple(anchors[left][i] + t*(anchors[right][i]-anchors[left][i])
                         for i in range(4))
    return anchors[keys[-1]]


def common_scene(boxes, chute_y=480, bag=(0, 866, 500, 1279)):
    boxes.extend([(3, 0, chute_y, 420, 786),
                  (3, 423, chute_y, 719, 777),
                  (4, *bag)])


def write_batch(second, frame_start, frame_end, boxes_for_frame, notes):
    output = BATCH_ROOT / f"second_{second:03d}"
    label_dir = output / "labels_yolo"
    visual_dir = output / "visualized"
    label_dir.mkdir(parents=True, exist_ok=True)
    visual_dir.mkdir(parents=True, exist_ok=True)
    rows = []
    font = ImageFont.load_default()
    for frame_no in range(frame_start, frame_end + 1):
        name = f"frame_{frame_no:06d}.jpg"
        src = SOURCE / name
        annotations = boxes_for_frame(frame_no)
        im = Image.open(src).convert("RGB")
        w, h = im.size
        lines = []
        for c, x1, y1, x2, y2 in annotations:
            lines.append(
                f"{c} {((x1+x2)/2)/w:.6f} {((y1+y2)/2)/h:.6f} "
                f"{(x2-x1)/w:.6f} {(y2-y1)/h:.6f}"
            )
        (label_dir / f"frame_{frame_no:06d}.txt").write_text(
            "\n".join(lines) + "\n", encoding="utf-8")
        draw = ImageDraw.Draw(im)
        for c, x1, y1, x2, y2 in annotations:
            color = COLORS[c]
            label_text = f"{c}:{CLASSES[c]}"
            draw.rectangle((x1, y1, x2, y2), outline=color, width=4)
            tw = len(label_text)*6 + 8
            ty = max(0, y1-17)
            draw.rectangle((x1, ty, x1+tw, ty+17), fill=color)
            draw.text((x1+4, ty+3), label_text,
                      fill=(0,0,0) if c in {1,2,4} else (255,255,255), font=font)
        im.save(visual_dir / name, quality=94)
        counts = {n: sum(a[0] == c for a in annotations)
                  for c, n in enumerate(CLASSES)}
        rows.append({"image": name, "frame_no": frame_no,
                     "time_seconds": f"{(frame_no-1)/30:.3f}",
                     "annotation_standard": "v1.2", **counts,
                     "review_status": "visual_reviewed_first_pass"})
    with (output / "manifest.csv").open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=rows[0].keys())
        writer.writeheader(); writer.writerows(rows)
    (output / "README.md").write_text(
        f"# 第 {second} 秒五类标注批次\n\n"
        f"- 图片：{frame_end-frame_start+1} 张，未生成拼图\n"
        "- 标准：ANNOTATION_STANDARD_v1.md（v1.2）\n"
        f"- {notes}\n"
        "- 状态：visual_reviewed_first_pass，等待用户抽查\n",
        encoding="utf-8")
