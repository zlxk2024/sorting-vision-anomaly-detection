import base64
import json
import os
import re
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont
import requests


DATASET_ROOT = Path("/Users/lixing.guo/Documents/机械臂/datasets/sorting_yolo_stage1")
IMAGE_DIR = DATASET_ROOT / "images" / "to_label"
OUT_DIR = DATASET_ROOT / "m3_prelabels_10"
VIS_DIR = OUT_DIR / "visualized"
YOLO_DIR = OUT_DIR / "labels_yolo"
JSON_DIR = OUT_DIR / "raw_json"
SUMMARY_JSON = OUT_DIR / "summary.json"
SUMMARY_MD = OUT_DIR / "summary.md"

API_BASE = os.environ.get("MINIMAX_API_BASE", "https://api.minimaxi.com/v1")
MODEL = os.environ.get("MINIMAX_MODEL", "MiniMax-M3")
API_KEY = os.environ.get("MINIMAX_API_KEY")

CLASS_NAMES = ["parcel", "gate_open", "gate_closed"]
CLASS_ID = {name: i for i, name in enumerate(CLASS_NAMES)}

SELECTED_IMAGES = [
    "0041_event_18_open_no_drop_t18.00.jpg",
    "0043_event_18_open_no_drop_t18.20.jpg",
    "0047_event_18_open_no_drop_t18.60.jpg",
    "0052_event_19_slide_abnormal_t19.10.jpg",
    "0055_event_19_slide_abnormal_t19.40.jpg",
    "0057_event_19_slide_abnormal_t19.60.jpg",
    "0070_event_21_two_parcels_open_no_drop_t21.10.jpg",
    "0071_event_21_two_parcels_open_no_drop_t21.20.jpg",
    "0082_normal_23_25_drop_t24.00.jpg",
    "0086_normal_23_25_drop_t24.80.jpg",
]


PROMPT = """你是 YOLO 数据集预标注助手。
请只做静态目标框预标注，不要判断异常事件。

需要标注的类别只有三类：
1. parcel：所有可见包裹，包括纸箱、黑袋、白袋、软包、小件。
2. gate_open：已打开或正在打开、允许包裹释放的抽屉/闸门/翻板/格口门。
3. gate_closed：明确关闭状态的抽屉/闸门/翻板/格口门。

标注要求：
- 框用像素坐标 xyxy，基于原图尺寸 width=720, height=1280；
- 只框可见部分；
- 看不清门状态时不要标 gate_open/gate_closed；
- 不要把袋子、背景灯、屏幕、支架、颜色反光当包裹；
- 如果不确定类别，降低 confidence；
- 输出 JSON，不要 Markdown，不要解释。

JSON 格式：
{
  "image_width": 720,
  "image_height": 1280,
  "objects": [
    {
      "class": "parcel | gate_open | gate_closed",
      "bbox_xyxy": [x1, y1, x2, y2],
      "confidence": 0.0,
      "notes": "可选简短说明"
    }
  ]
}
"""


def data_url(path: Path) -> str:
    return "data:image/jpeg;base64," + base64.b64encode(path.read_bytes()).decode("ascii")


def extract_json(text: str):
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    start = text.find("{")
    end = text.rfind("}")
    if start >= 0 and end >= start:
        text = text[start : end + 1]
    return json.loads(text)


def call_m3(image_path: Path):
    if not API_KEY:
        raise RuntimeError("MINIMAX_API_KEY is not set")
    payload = {
        "model": MODEL,
        "messages": [
            {"role": "system", "name": "system", "content": PROMPT},
            {
                "role": "user",
                "name": "user",
                "content": [
                    {"type": "text", "text": f"请预标注这张图片：{image_path.name}"},
                    {"type": "image_url", "image_url": {"url": data_url(image_path)}},
                ],
            },
        ],
        "temperature": 0.0,
        "max_tokens": 2500,
    }
    url = f"{API_BASE.rstrip('/')}/text/chatcompletion_v2"
    headers = {"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"}
    resp = requests.post(url, headers=headers, json=payload, timeout=180)
    if resp.status_code >= 400:
        raise RuntimeError(f"MiniMax HTTP {resp.status_code}: {resp.text[:1000]}")
    raw = resp.json()
    content = raw.get("choices", [{}])[0].get("message", {}).get("content", "")
    return raw, extract_json(content)


def clamp_box(box, width, height):
    x1, y1, x2, y2 = [float(v) for v in box]
    x1 = max(0, min(width - 1, x1))
    y1 = max(0, min(height - 1, y1))
    x2 = max(0, min(width - 1, x2))
    y2 = max(0, min(height - 1, y2))
    if x2 < x1:
        x1, x2 = x2, x1
    if y2 < y1:
        y1, y2 = y2, y1
    return x1, y1, x2, y2


def to_yolo_line(obj, width, height):
    cls = obj.get("class")
    if cls not in CLASS_ID:
        return None
    x1, y1, x2, y2 = clamp_box(obj.get("bbox_xyxy", [0, 0, 0, 0]), width, height)
    if (x2 - x1) < 3 or (y2 - y1) < 3:
        return None
    xc = ((x1 + x2) / 2) / width
    yc = ((y1 + y2) / 2) / height
    bw = (x2 - x1) / width
    bh = (y2 - y1) / height
    return f"{CLASS_ID[cls]} {xc:.6f} {yc:.6f} {bw:.6f} {bh:.6f}"


def draw_visualization(image_path: Path, objects, out_path: Path):
    img = Image.open(image_path).convert("RGB")
    width, height = img.size
    d = ImageDraw.Draw(img)
    colors = {"parcel": "lime", "gate_open": "red", "gate_closed": "dodgerblue"}
    try:
        font = ImageFont.truetype("/System/Library/Fonts/PingFang.ttc", 20)
    except Exception:
        font = None
    for obj in objects:
        cls = obj.get("class")
        if cls not in CLASS_ID:
            continue
        x1, y1, x2, y2 = clamp_box(obj.get("bbox_xyxy", [0, 0, 0, 0]), width, height)
        color = colors.get(cls, "yellow")
        d.rectangle([x1, y1, x2, y2], outline=color, width=4)
        label = f"{CLASS_ID[cls]}:{cls} {obj.get('confidence', 0):.2f}"
        text_w = min(width - x1, len(label) * 11 + 8)
        d.rectangle([x1, max(0, y1 - 26), x1 + text_w, y1], fill=color)
        d.text((x1 + 3, max(0, y1 - 24)), label, fill="black", font=font)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    img.save(out_path, quality=95)


def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    VIS_DIR.mkdir(parents=True, exist_ok=True)
    YOLO_DIR.mkdir(parents=True, exist_ok=True)
    JSON_DIR.mkdir(parents=True, exist_ok=True)

    summaries = []
    for name in SELECTED_IMAGES:
        image_path = IMAGE_DIR / name
        if not image_path.exists():
            print(f"SKIP missing {image_path}", file=sys.stderr)
            continue
        print(f"Prelabeling {name}", flush=True)
        raw, parsed = call_m3(image_path)
        width, height = Image.open(image_path).size
        objects = parsed.get("objects", [])

        raw_out = JSON_DIR / name.replace(".jpg", ".json")
        raw_out.write_text(json.dumps({"parsed": parsed, "raw_response": raw}, ensure_ascii=False, indent=2), encoding="utf-8")

        lines = []
        for obj in objects:
            line = to_yolo_line(obj, width, height)
            if line:
                lines.append(line)
        yolo_out = YOLO_DIR / name.replace(".jpg", ".txt")
        yolo_out.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")

        vis_out = VIS_DIR / name
        draw_visualization(image_path, objects, vis_out)

        counts = {cls: 0 for cls in CLASS_NAMES}
        for obj in objects:
            if obj.get("class") in counts:
                counts[obj["class"]] += 1
        summaries.append({
            "image": str(image_path),
            "visualized": str(vis_out),
            "yolo_label": str(yolo_out),
            "raw_json": str(raw_out),
            "object_count": len(objects),
            "counts": counts,
        })

    SUMMARY_JSON.write_text(json.dumps(summaries, ensure_ascii=False, indent=2), encoding="utf-8")
    md = ["# M3 预标注 10 张关键帧结果", ""]
    md.append("| 图片 | parcel | gate_open | gate_closed | 可视化 | 标签 |")
    md.append("|---|---:|---:|---:|---|---|")
    for s in summaries:
        c = s["counts"]
        md.append(
            f"| {Path(s['image']).name} | {c['parcel']} | {c['gate_open']} | {c['gate_closed']} | "
            f"[jpg]({s['visualized']}) | [txt]({s['yolo_label']}) |"
        )
    md.append("")
    md.append("说明：这是 M3 自动预标注结果，需要人工复核后才能作为训练真值。")
    SUMMARY_MD.write_text("\n".join(md), encoding="utf-8")

    print(json.dumps({
        "out_dir": str(OUT_DIR),
        "summary_json": str(SUMMARY_JSON),
        "summary_md": str(SUMMARY_MD),
        "count": len(summaries),
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
