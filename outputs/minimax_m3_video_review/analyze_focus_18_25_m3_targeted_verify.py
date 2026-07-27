import base64
import json
import os
import subprocess
import sys
from pathlib import Path

import requests


VIDEO = Path("/Users/lixing.guo/Desktop/异常检测视频/快递分类视频.mp4")
OUT_DIR = Path("/Users/lixing.guo/Documents/机械臂/outputs/minimax_m3_video_review/focus_18_25_targeted_verify")
FRAMES_DIR = OUT_DIR / "frames_fullpath_roi"
RESULT_JSON = OUT_DIR / "focus_18_25_targeted_verify_result.json"
RESULT_MD = OUT_DIR / "focus_18_25_targeted_verify_result.md"

API_BASE = os.environ.get("MINIMAX_API_BASE", "https://api.minimaxi.com/v1")
MODEL = os.environ.get("MINIMAX_MODEL", "MiniMax-M3")
API_KEY = os.environ.get("MINIMAX_API_KEY")

STEP = 0.2
TASKS = [
    ("verify_18_open_no_drop", 17.8, 18.8, "open_no_drop"),
    ("verify_19_20_slide_abnormal", 18.8, 20.2, "slide_abnormal"),
    ("verify_21_open_no_drop_multi_visible", 20.6, 21.8, "open_no_drop"),
    ("verify_23_25_normal_guard", 23.0, 25.0, "open_no_drop_or_slide_abnormal"),
]


SYSTEM_PROMPT = """你是快递分拣视频“候选异常核验员”。
注意：你不是自由分类器。每次只核验用户给定的 target_label 是否成立。

画面结构：
- 上方：小车/抽屉/格口机构；
- 中部：白色滑道/格口斜面；
- 下方：橙色导流板、格口边界、集包袋入口。

核验标准：
1. open_no_drop 成立条件：
   - 明确看到包裹在小车/抽屉/格口开口附近；
   - 机构处于打开/释放/可下落状态，或包裹已经到达开口区域；
   - 包裹连续多帧没有进入滑道或没有及时下落。
2. slide_abnormal 成立条件：
   - 明确看到包裹已经开始滑落；
   - 轨迹明显横向偏移、贴边、跨格口边界、滑歪、慢滑、撞边或从边缘异常滑出。
3. 如果 target_label 不成立，但存在其他明显异常，可以在 other_possible_label 写出来。
4. 如果看不清或对应关系不确定，verdict 必须是 uncertain。
5. 不要把设备白色挡板、灯光、背景牌、颜色框/界面元素当包裹。

输出必须是紧凑 JSON，不要 Markdown，不要长推理：
{
  "target_label": "open_no_drop",
  "verdict": "yes | no | uncertain",
  "confidence": 0.0,
  "key_frames": ["18.0s", "18.2s"],
  "evidence": "一句话证据，最多80字",
  "other_possible_label": "none | slide_abnormal | wrong_chute | multi_parcel_on_cart | normal | uncertain",
  "human_action": "accept | review | reject"
}
"""


def run(cmd):
    subprocess.run(cmd, check=True)


def extract_frame_roi(time_s: float, path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)
    run([
        "ffmpeg",
        "-y",
        "-v",
        "error",
        "-ss",
        f"{time_s:.2f}",
        "-i",
        str(VIDEO),
        "-frames:v",
        "1",
        "-vf",
        "crop=720:880:0:120",
        "-q:v",
        "3",
        str(path),
    ])


def data_url(path: Path) -> str:
    return "data:image/jpeg;base64," + base64.b64encode(path.read_bytes()).decode("ascii")


def times(start, end):
    values = []
    t = start
    while t <= end + 1e-6:
        values.append(round(t, 2))
        t += STEP
    return values


def build_frames(task_name, start, end):
    frames = []
    for t in times(start, end):
        frame_path = FRAMES_DIR / task_name / f"t{t:05.2f}.jpg"
        if not frame_path.exists():
            extract_frame_roi(t, frame_path)
        frames.append((t, frame_path))
    return frames


def call_minimax(task_name, frames, start, end, target_label):
    if not API_KEY:
        raise RuntimeError("MINIMAX_API_KEY is not set")
    content = [
        {
            "type": "text",
            "text": (
                f"任务={task_name}。时间={start:.1f}s-{end:.1f}s。"
                f"请只核验 target_label={target_label} 是否成立。"
                "图片为全路径ROI，间隔0.2秒。"
            ),
        }
    ]
    for t, path in frames:
        content.append({"type": "text", "text": f"frame_time={t:.2f}s"})
        content.append({"type": "image_url", "image_url": {"url": data_url(path)}})

    payload = {
        "model": MODEL,
        "messages": [
            {"role": "system", "name": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "name": "user", "content": content},
        ],
        "temperature": 0.0,
        "max_tokens": 2000,
    }
    url = f"{API_BASE.rstrip('/')}/text/chatcompletion_v2"
    headers = {"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"}
    resp = requests.post(url, headers=headers, json=payload, timeout=180)
    if resp.status_code >= 400:
        raise RuntimeError(f"MiniMax HTTP {resp.status_code}: {resp.text[:1200]}")
    return resp.json()


def extract_text(resp):
    return resp.get("choices", [{}])[0].get("message", {}).get("content", "")


def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    results = []
    for task_name, start, end, target_label in TASKS:
        frames = build_frames(task_name, start, end)
        print(f"Prepared {len(frames)} targeted frames for {task_name} {start}-{end}", flush=True)
        resp = call_minimax(task_name, frames, start, end, target_label)
        results.append({
            "task_name": task_name,
            "start": start,
            "end": end,
            "target_label": target_label,
            "frames": [{"time": t, "path": str(p)} for t, p in frames],
            "finish_reason": resp.get("choices", [{}])[0].get("finish_reason"),
            "content": extract_text(resp),
            "raw_response": resp,
        })

    RESULT_JSON.write_text(json.dumps({
        "step_seconds": STEP,
        "crop": "crop=720:880:0:120",
        "tasks": results,
    }, ensure_ascii=False, indent=2))

    md = ["# MiniMax-M3 目标异常核验版（不自由分类 + 全路径ROI + 0.2秒）", ""]
    for item in results:
        md.append(f"## {item['task_name']}：{item['start']:.1f}s - {item['end']:.1f}s，target={item['target_label']}")
        md.append("")
        md.append("```json")
        md.append(item["content"])
        md.append("```")
        md.append("")
    RESULT_MD.write_text("\n".join(md))
    print(str(RESULT_JSON))
    print(str(RESULT_MD))


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(1)
