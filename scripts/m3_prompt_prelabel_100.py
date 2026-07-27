from __future__ import annotations

import base64
import concurrent.futures
import json
import os
import re
import shutil
import threading
import time
from pathlib import Path

import requests
from PIL import Image, ImageDraw, ImageFont


ROOT = Path("/Users/lixing.guo/Documents/机械臂")
SOURCE_DIR = ROOT / "datasets/sorting_yolo_stage1/images/to_label"
OUTPUT = (
    ROOT
    / "datasets/sorting_yolo_stage1/"
    "m3_prompt_prelabels_100_v1"
)
CONFIRMED_DIR = (
    ROOT
    / "datasets/sorting_yolo_stage1/m3_prelabels_10/"
    "five_class_all_10_v8_prompt_standard/images"
)

API_BASE = os.environ.get("MINIMAX_API_BASE", "https://api.minimaxi.com/v1")
API_KEY = os.environ.get("MINIMAX_API_KEY")
MODEL = os.environ.get("MINIMAX_MODEL", "MiniMax-M3")
MAX_WORKERS = int(os.environ.get("M3_PRELABEL_WORKERS", "4"))

CLASSES = ["parcel", "drawer_open", "drawer_closed", "chute", "bag"]
CLASS_ID = {name: index for index, name in enumerate(CLASSES)}
COLORS = {
    "parcel": (0, 160, 255),
    "drawer_open": (120, 210, 0),
    "drawer_closed": (255, 255, 255),
    "chute": (255, 70, 70),
    "bag": (255, 205, 0),
}

PROMPT = """你是一名工业视觉目标检测数据标注员。请对单张快递分拣现场图片做预标注。

只允许标注以下5类：
0 parcel
1 drawer_open
2 drawer_closed
3 chute
4 bag

统一标准：

parcel：
- 包括纸箱、黑色塑料袋、白色快递袋和软包。
- bbox必须完整包含包裹的全部可见实体，四周可以留2到5像素余量。
- 不得只框包裹中心，不得切掉包裹边缘。
- 图片边缘的包裹可以标注当前可见部分。

drawer_open：
- 只根据门板物理姿态判断。
- 门板已经翻下、平放或接近水平，才是drawer_open。
- 只框平放门板本体，不包含包裹、白色滑道、斜坡、导轨和机械结构。
- 门板必须完整可见；被图片左边或右边截断时不要标注。

drawer_closed：
- 只根据门板物理姿态判断。
- 门板立起、竖直或接近竖直，才是drawer_closed。
- 只框竖立门板本体。
- 不得把小车底部、棕色传动机构、电机、支架或轨道标为抽屉。
- 门板必须完整可见；被图片左边或右边截断时不要标注。

chute：
- 是抽屉下方完整的橙色落格通道/闸口面板。
- 以两侧结构边界或隔板为边界，一个完整闸口只标一个框。
- 不要把屏幕、立柱或局部橙色零件单独标为chute。

bag：
- 是闸口下方接收包裹的集包袋。
- 框住完整可见的袋口和袋身，不要只框袋口。
- 不包含输送带、支架或相邻袋子。

强制排除：
- 小车底盘、棕色传动机构、导轨、支架、电机不是抽屉。
- 无法确认门板实体或门板姿态时，不标抽屉。
- 不根据颜色直接判断抽屉状态。
- 不输出重复框。

坐标要求：
- 使用目标图片原始像素坐标xyxy：[x1,y1,x2,y2]。
- x1<x2，y1<y2，坐标不得超出图片。
- 输出前逐项检查包裹是否完整、抽屉是否完整可见。

只输出JSON，不要Markdown，不要解释：
{
  "image_width": 720,
  "image_height": 1280,
  "objects": [
    {
      "class": "parcel|drawer_open|drawer_closed|chute|bag",
      "bbox_xyxy": [x1,y1,x2,y2],
      "confidence": 0.0,
      "notes": "简短判断依据"
    }
  ]
}
"""

LOCK = threading.Lock()
PROGRESS = {"done": 0, "ok": 0, "failed": 0}


def get_font(size: int) -> ImageFont.ImageFont:
    for candidate in (
        "/System/Library/Fonts/PingFang.ttc",
        "/System/Library/Fonts/Supplemental/Arial.ttf",
    ):
        if Path(candidate).exists():
            return ImageFont.truetype(candidate, size)
    return ImageFont.load_default()


def data_url(path: Path) -> str:
    encoded = base64.b64encode(path.read_bytes()).decode("ascii")
    return "data:image/jpeg;base64," + encoded


def extract_json(text: str) -> dict:
    cleaned = text.strip()
    cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
    cleaned = re.sub(r"\s*```$", "", cleaned)
    start = cleaned.find("{")
    end = cleaned.rfind("}")
    if start < 0 or end < start:
        raise ValueError("response does not contain a JSON object")
    return json.loads(cleaned[start : end + 1])


def select_100() -> list[Path]:
    confirmed = {path.name for path in CONFIRMED_DIR.glob("*.jpg")}
    candidates = [
        path
        for path in sorted(SOURCE_DIR.glob("*.jpg"))
        if path.name not in confirmed
    ]
    if len(candidates) < 100:
        raise RuntimeError(f"only {len(candidates)} unconfirmed images are available")
    indices = [round(index * (len(candidates) - 1) / 99) for index in range(100)]
    selected = [candidates[index] for index in indices]
    if len({path.name for path in selected}) != 100:
        raise RuntimeError("selection produced duplicate images")
    return selected


def call_model(image_path: Path) -> tuple[dict, dict]:
    payload = {
        "model": MODEL,
        "messages": [
            {"role": "system", "name": "system", "content": PROMPT},
            {
                "role": "user",
                "name": "user",
                "content": [
                    {
                        "type": "text",
                        "text": (
                            f"标注目标图片：{image_path.name}。"
                            "先确认实体，再输出像素坐标。"
                        ),
                    },
                    {
                        "type": "image_url",
                        "image_url": {"url": data_url(image_path)},
                    },
                ],
            },
        ],
        "temperature": 0.0,
        "max_tokens": 2200,
    }
    response = requests.post(
        f"{API_BASE.rstrip('/')}/text/chatcompletion_v2",
        headers={
            "Authorization": f"Bearer {API_KEY}",
            "Content-Type": "application/json",
        },
        json=payload,
        timeout=180,
    )
    if response.status_code >= 400:
        raise RuntimeError(
            f"MiniMax HTTP {response.status_code}: {response.text[:500]}"
        )
    raw = response.json()
    content = raw.get("choices", [{}])[0].get("message", {}).get("content", "")
    return raw, extract_json(content)


def clamp_box(values: list, width: int, height: int) -> list[float] | None:
    if not isinstance(values, list) or len(values) != 4:
        return None
    try:
        x1, y1, x2, y2 = [float(value) for value in values]
    except (TypeError, ValueError):
        return None
    x1, x2 = sorted((max(0, min(width - 1, x1)), max(0, min(width - 1, x2))))
    y1, y2 = sorted((max(0, min(height - 1, y1)), max(0, min(height - 1, y2))))
    if x2 - x1 < 4 or y2 - y1 < 4:
        return None
    return [x1, y1, x2, y2]


def iou(box_a: list[float], box_b: list[float]) -> float:
    ax1, ay1, ax2, ay2 = box_a
    bx1, by1, bx2, by2 = box_b
    ix1, iy1 = max(ax1, bx1), max(ay1, by1)
    ix2, iy2 = min(ax2, bx2), min(ay2, by2)
    intersection = max(0, ix2 - ix1) * max(0, iy2 - iy1)
    union = (
        (ax2 - ax1) * (ay2 - ay1)
        + (bx2 - bx1) * (by2 - by1)
        - intersection
    )
    return intersection / union if union > 0 else 0


def clean_objects(parsed: dict, width: int, height: int) -> list[dict]:
    cleaned = []
    for candidate in parsed.get("objects", []):
        class_name = candidate.get("class")
        if class_name not in CLASS_ID:
            continue
        box = clamp_box(candidate.get("bbox_xyxy"), width, height)
        if box is None:
            continue

        # User-confirmed rule: incomplete drawer plates at image edges are ignored.
        if class_name in {"drawer_open", "drawer_closed"}:
            if box[0] <= 4 or box[2] >= width - 5:
                continue

        try:
            confidence = float(candidate.get("confidence", 0.5))
        except (TypeError, ValueError):
            confidence = 0.5
        confidence = max(0.0, min(1.0, confidence))

        item = {
            "class": class_name,
            "bbox_xyxy": box,
            "confidence": confidence,
            "notes": str(candidate.get("notes", "")),
        }
        duplicate = next(
            (
                existing
                for existing in cleaned
                if existing["class"] == class_name
                and iou(existing["bbox_xyxy"], box) >= 0.80
            ),
            None,
        )
        if duplicate is None:
            cleaned.append(item)
        elif confidence > duplicate["confidence"]:
            cleaned.remove(duplicate)
            cleaned.append(item)
    return cleaned


def save_outputs(
    image_path: Path,
    raw: dict,
    parsed: dict,
    objects: list[dict],
) -> None:
    image_dir = OUTPUT / "images"
    json_dir = OUTPUT / "raw_json"
    label_dir = OUTPUT / "labels_yolo"
    visual_dir = OUTPUT / "visualized"

    shutil.copy2(image_path, image_dir / image_path.name)
    (json_dir / f"{image_path.stem}.json").write_text(
        json.dumps(
            {"parsed": parsed, "cleaned_objects": objects, "raw_response": raw},
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    with Image.open(image_path) as source:
        width, height = source.size
        visual = source.convert("RGB")

    lines = []
    for obj in objects:
        x1, y1, x2, y2 = obj["bbox_xyxy"]
        class_id = CLASS_ID[obj["class"]]
        lines.append(
            f"{class_id} {((x1 + x2) / 2 / width):.6f} "
            f"{((y1 + y2) / 2 / height):.6f} "
            f"{((x2 - x1) / width):.6f} {((y2 - y1) / height):.6f}"
        )
    (label_dir / f"{image_path.stem}.txt").write_text(
        "\n".join(lines) + ("\n" if lines else ""),
        encoding="utf-8",
    )

    draw = ImageDraw.Draw(visual)
    font = get_font(17)
    for obj in objects:
        class_name = obj["class"]
        class_id = CLASS_ID[class_name]
        x1, y1, x2, y2 = obj["bbox_xyxy"]
        color = COLORS[class_name]
        label = f"{class_id}:{class_name} {obj['confidence']:.2f}"
        draw.rectangle((x1, y1, x2, y2), outline=color, width=5)
        text_box = draw.textbbox((x1, y1), label, font=font)
        label_y = max(0, y1 - (text_box[3] - text_box[1] + 6))
        draw.rectangle(
            (x1, label_y, x1 + text_box[2] - text_box[0] + 8, y1),
            fill=color,
        )
        text_color = (255, 255, 255) if class_name == "parcel" else (0, 0, 0)
        draw.text((x1 + 4, label_y + 2), label, fill=text_color, font=font)
    visual.save(visual_dir / image_path.name, quality=94)


def process_one(image_path: Path) -> dict:
    json_path = OUTPUT / "raw_json" / f"{image_path.stem}.json"
    label_path = OUTPUT / "labels_yolo" / f"{image_path.stem}.txt"
    visual_path = OUTPUT / "visualized" / image_path.name
    if json_path.exists() and label_path.exists() and visual_path.exists():
        try:
            saved = json.loads(json_path.read_text(encoding="utf-8"))
            object_count = len(saved.get("cleaned_objects", []))
        except Exception:
            object_count = 0
        with LOCK:
            PROGRESS["done"] += 1
            PROGRESS["ok"] += 1
            print(
                f"[{PROGRESS['done']:03d}/100] RESUME {image_path.name} "
                f"objects={object_count}",
                flush=True,
            )
        return {
            "image": image_path.name,
            "status": "ok",
            "objects": object_count,
            "resumed": True,
        }

    error = None
    for attempt in range(1, 4):
        try:
            raw, parsed = call_model(image_path)
            with Image.open(image_path) as image:
                width, height = image.size
            objects = clean_objects(parsed, width, height)
            save_outputs(image_path, raw, parsed, objects)
            with LOCK:
                PROGRESS["done"] += 1
                PROGRESS["ok"] += 1
                print(
                    f"[{PROGRESS['done']:03d}/100] OK {image_path.name} "
                    f"objects={len(objects)}",
                    flush=True,
                )
            return {
                "image": image_path.name,
                "status": "ok",
                "objects": len(objects),
            }
        except Exception as exc:
            error = str(exc)
            if attempt < 3:
                time.sleep(2**attempt)

    with LOCK:
        PROGRESS["done"] += 1
        PROGRESS["failed"] += 1
        print(
            f"[{PROGRESS['done']:03d}/100] FAILED {image_path.name}: {error}",
            flush=True,
        )
    return {"image": image_path.name, "status": "failed", "error": error}


def main() -> None:
    if not API_KEY:
        raise RuntimeError("MINIMAX_API_KEY is not set")
    for name in ("images", "raw_json", "labels_yolo", "visualized"):
        (OUTPUT / name).mkdir(parents=True, exist_ok=True)

    selected = select_100()
    (OUTPUT / "selected_images.txt").write_text(
        "\n".join(path.name for path in selected) + "\n",
        encoding="utf-8",
    )
    (OUTPUT / "classes.txt").write_text(
        "\n".join(CLASSES) + "\n", encoding="utf-8"
    )
    (OUTPUT / "prompt.txt").write_text(PROMPT, encoding="utf-8")

    with concurrent.futures.ThreadPoolExecutor(max_workers=MAX_WORKERS) as pool:
        results = list(pool.map(process_one, selected))

    (OUTPUT / "summary.json").write_text(
        json.dumps(
            {
                "model": MODEL,
                "selected": len(selected),
                "ok": sum(item["status"] == "ok" for item in results),
                "failed": sum(item["status"] == "failed" for item in results),
                "results": results,
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    print(json.dumps(PROGRESS, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
