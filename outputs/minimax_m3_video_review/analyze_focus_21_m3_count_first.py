import base64
import json
import os
import subprocess
import sys
from pathlib import Path

import requests


VIDEO = Path("/Users/lixing.guo/Desktop/异常检测视频/快递分类视频.mp4")
OUT_DIR = Path("/Users/lixing.guo/Documents/机械臂/outputs/minimax_m3_video_review/focus_21_count_first")
FRAMES_DIR = OUT_DIR / "frames_upper_roi"
RESULT_JSON = OUT_DIR / "focus_21_count_first_result.json"
RESULT_MD = OUT_DIR / "focus_21_count_first_result.md"

API_BASE = os.environ.get("MINIMAX_API_BASE", "https://api.minimaxi.com/v1")
MODEL = os.environ.get("MINIMAX_MODEL", "MiniMax-M3")
API_KEY = os.environ.get("MINIMAX_API_KEY")

START = 20.6
END = 22.2
STEP = 0.2


SYSTEM_PROMPT = """你是快递分拣视频候选异常核验员。
本任务只看上部机构ROI，重点核验两个问题：

观察顺序必须固定：
1. parcel_count：逐帧数上方小车/抽屉/格口区域里可见包裹数量；
2. multi_parcel_visible：判断是否有任一时刻同时可见2个及以上包裹；
3. open_no_drop：判断是否有包裹停在已打开/释放状态的抽屉或格口区域，连续多帧没有进入滑道/没有下落。

判定注意：
- 不要把设备挡板、背景、灯光当包裹；
- 如果有两个包裹分别在相邻小车/格口上，也要标记 two_parcels_visible，但不等于 multi_parcel_on_same_cart；
- 如果只能确认“两件同框”，但不能确认在同一个小车上，写 two_parcels_visible=true、multi_parcel_on_same_cart=false；
- 如果开门状态看不清，但包裹持续停在开口附近，open_no_drop_verdict 可为 uncertain 或 yes，置信度保守。

输出紧凑 JSON：
{
  "frame_counts": [{"time": "20.6s", "parcel_count": 1, "notes": "简短"}],
  "two_parcels_visible": true,
  "multi_parcel_on_same_cart": "yes | no | uncertain",
  "open_no_drop_verdict": "yes | no | uncertain",
  "confidence": 0.0,
  "key_frames": ["21.0s", "21.2s"],
  "evidence": "一句话证据，最多100字",
  "human_action": "accept | review | reject"
}
"""


def run(cmd):
    subprocess.run(cmd, check=True)


def extract_frame_upper_roi(time_s: float, path: Path):
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
        "crop=720:620:0:120",
        "-q:v",
        "3",
        str(path),
    ])


def data_url(path: Path) -> str:
    return "data:image/jpeg;base64," + base64.b64encode(path.read_bytes()).decode("ascii")


def times():
    values = []
    t = START
    while t <= END + 1e-6:
        values.append(round(t, 2))
        t += STEP
    return values


def build_frames():
    frames = []
    for t in times():
        frame_path = FRAMES_DIR / f"t{t:05.2f}.jpg"
        if not frame_path.exists():
            extract_frame_upper_roi(t, frame_path)
        frames.append((t, frame_path))
    return frames


def call_minimax(frames):
    if not API_KEY:
        raise RuntimeError("MINIMAX_API_KEY is not set")
    content = [
        {
            "type": "text",
            "text": (
                f"请分析 {START:.1f}s-{END:.1f}s 上部机构ROI连续帧。"
                "先逐帧数包裹，再判断是否两件同框、是否开门未落。"
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
        "max_tokens": 3000,
    }
    url = f"{API_BASE.rstrip('/')}/text/chatcompletion_v2"
    headers = {"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"}
    resp = requests.post(url, headers=headers, json=payload, timeout=180)
    if resp.status_code >= 400:
        raise RuntimeError(f"MiniMax HTTP {resp.status_code}: {resp.text[:1200]}")
    return resp.json()


def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    frames = build_frames()
    print(f"Prepared {len(frames)} upper ROI frames for {START}-{END}", flush=True)
    resp = call_minimax(frames)
    content = resp.get("choices", [{}])[0].get("message", {}).get("content", "")
    RESULT_JSON.write_text(json.dumps({
        "start": START,
        "end": END,
        "step_seconds": STEP,
        "crop": "crop=720:620:0:120",
        "frames": [{"time": t, "path": str(p)} for t, p in frames],
        "content": content,
        "raw_response": resp,
    }, ensure_ascii=False, indent=2))
    RESULT_MD.write_text("# MiniMax-M3 21秒先数包裹核验\n\n```json\n" + content + "\n```\n")
    print(str(RESULT_JSON))
    print(str(RESULT_MD))


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(1)
