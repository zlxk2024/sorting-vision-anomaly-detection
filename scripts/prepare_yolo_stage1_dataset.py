import csv
import json
import subprocess
from pathlib import Path


VIDEO = (Path(__file__).resolve().parents[1] / "data/videos/快递分类视频.mp4")
OUT_ROOT = (Path(__file__).resolve().parents[1] / "datasets/sorting_yolo_stage1")
IMAGES_DIR = OUT_ROOT / "images" / "to_label"
LABELS_DIR = OUT_ROOT / "labels" / "to_label"
META_CSV = OUT_ROOT / "frame_manifest.csv"
DATA_YAML = OUT_ROOT / "data.yaml"
GUIDE_MD = OUT_ROOT / "标注说明.md"


CLASSES = ["parcel", "gate_open", "gate_closed"]


def run(cmd):
    subprocess.run(cmd, check=True)


def extract_frame(time_s: float, out_path: Path):
    out_path.parent.mkdir(parents=True, exist_ok=True)
    if out_path.exists():
        return
    run([
        "ffmpeg",
        "-y",
        "-v",
        "error",
        "-ss",
        f"{time_s:.3f}",
        "-i",
        str(VIDEO),
        "-frames:v",
        "1",
        "-q:v",
        "3",
        str(out_path),
    ])


def build_plan():
    plan = []

    # Full video coarse sampling: useful for normal/background diversity.
    t = 0.0
    while t <= 39.4:
        plan.append((round(t, 2), "global_2fps", "mixed_background_or_normal"))
        t += 0.5

    # High-density key event windows.
    event_windows = [
        (17.6, 19.0, 0.1, "event_18_open_no_drop", "open_no_drop_white_parcel"),
        (18.8, 20.2, 0.1, "event_19_slide_abnormal", "slide_abnormal_black_parcel"),
        (20.6, 22.2, 0.1, "event_21_two_parcels_open_no_drop", "two_parcels_visible_open_no_drop"),
        (23.0, 25.0, 0.2, "normal_23_25_drop", "normal_drop_negative_sample"),
    ]
    for start, end, step, group, event_label in event_windows:
        t = start
        while t <= end + 1e-9:
            plan.append((round(t, 2), group, event_label))
            t += step

    # De-duplicate by exact time while preserving richer event group over global.
    priority = {
        "global_2fps": 0,
        "normal_23_25_drop": 1,
        "event_18_open_no_drop": 2,
        "event_19_slide_abnormal": 2,
        "event_21_two_parcels_open_no_drop": 2,
    }
    by_time = {}
    for item in plan:
        time_s, group, event_label = item
        if time_s not in by_time or priority[group] > priority[by_time[time_s][1]]:
            by_time[time_s] = item
    return [by_time[t] for t in sorted(by_time)]


def write_dataset_files(rows):
    OUT_ROOT.mkdir(parents=True, exist_ok=True)
    LABELS_DIR.mkdir(parents=True, exist_ok=True)

    with META_CSV.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=[
            "image",
            "time_s",
            "group",
            "event_label_for_reference_only",
            "annotation_status",
            "notes",
        ])
        writer.writeheader()
        writer.writerows(rows)

    DATA_YAML.write_text(
        "\n".join([
            "train: images/train",
            "val: images/val",
            "test: images/test",
            "",
            "names:",
            "  0: parcel",
            "  1: gate_open",
            "  2: gate_closed",
            "",
        ]),
        encoding="utf-8",
    )

    GUIDE_MD.write_text(
        """# YOLO 第一阶段标注说明

## 目标

第一阶段只验证 YOLO 能不能稳定识别基础视觉对象：

- `parcel`
- `gate_open`
- `gate_closed`

不要直接用 YOLO 框标 `open_no_drop`、`slide_abnormal`、`wrong_chute`。这些异常是事件级标签，后续用规则/状态机判断。

## 类别定义

| ID | 类别 | 怎么标 |
|---:|---|---|
| 0 | parcel | 所有可见包裹都标，包括纸箱、黑袋、白袋、小件 |
| 1 | gate_open | 已打开/正在打开、允许包裹释放的抽屉/闸门/翻板 |
| 2 | gate_closed | 关闭状态的抽屉/闸门/翻板 |

## 标注原则

1. 看到几个包裹，就标几个 `parcel`。
2. 包裹被遮挡时，只框可见部分。
3. 打开的门/抽屉/翻板标 `gate_open`。
4. 明确关闭的门/抽屉/翻板标 `gate_closed`。
5. 看不清的门状态可以不标，避免脏数据。
6. 事件标签只参考 `frame_manifest.csv`，不要作为 YOLO 类别。

## 当前抽帧分组

- `event_18_open_no_drop`：18 秒附近，白色件开门未落。
- `event_19_slide_abnormal`：19-20 秒附近，黑色件滑落异常。
- `event_21_two_parcels_open_no_drop`：21 秒附近，两件同框/开门未落候选。
- `normal_23_25_drop`：23-25 秒正常下滑负样本。
- `global_2fps`：全视频 0.5 秒间隔抽帧，用于补充正常和背景变化。

## 标完之后

把已标注图片放入：

```text
images/train
images/val
images/test
```

对应 YOLO txt 标签放入：

```text
labels/train
labels/val
labels/test
```

建议比例：

```text
train 80%
val   15%
test   5%
```
""",
        encoding="utf-8",
    )


def main():
    if not VIDEO.exists():
        raise FileNotFoundError(VIDEO)

    rows = []
    plan = build_plan()
    for idx, (time_s, group, event_label) in enumerate(plan, start=1):
        image_name = f"{idx:04d}_{group}_t{time_s:05.2f}.jpg"
        image_path = IMAGES_DIR / image_name
        extract_frame(time_s, image_path)

        # Create empty label placeholders so labeling tools/users see expected paths.
        label_path = LABELS_DIR / image_name.replace(".jpg", ".txt")
        label_path.parent.mkdir(parents=True, exist_ok=True)
        if not label_path.exists():
            label_path.write_text("", encoding="utf-8")

        rows.append({
            "image": str(image_path),
            "time_s": f"{time_s:.2f}",
            "group": group,
            "event_label_for_reference_only": event_label,
            "annotation_status": "to_label",
            "notes": "",
        })

    write_dataset_files(rows)

    summary = {
        "video": str(VIDEO),
        "dataset_root": str(OUT_ROOT),
        "image_count": len(rows),
        "classes": CLASSES,
        "manifest": str(META_CSV),
        "data_yaml": str(DATA_YAML),
        "guide": str(GUIDE_MD),
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
