import base64
import json
import os
import subprocess
import sys
from pathlib import Path

import requests


VIDEO = Path("/Users/lixing.guo/Desktop/异常检测视频/快递分类视频.mp4")
OUT_DIR = Path("/Users/lixing.guo/Documents/机械臂/outputs/minimax_m3_video_review")
FRAMES_DIR = OUT_DIR / "frames"
RESULT_JSON = OUT_DIR / "m3_candidate_events.json"
RESULT_MD = OUT_DIR / "m3_candidate_events.md"

API_BASE = os.environ.get("MINIMAX_API_BASE", "https://api.minimaxi.com/v1")
MODEL = os.environ.get("MINIMAX_MODEL", "MiniMax-M3")
API_KEY = os.environ.get("MINIMAX_API_KEY")

WINDOW_SECONDS = 8
STRIDE_SECONDS = 6
FRAME_OFFSETS = [0.5, 2.5, 4.5, 6.5]
VIDEO_DURATION = 39.466667


SYSTEM_PROMPT = """你是快递分拣异常识别助手。
你需要根据连续关键帧判断候选异常片段。只根据画面能看到的内容判断，不要编造。

重点寻找三类异常：
1. open_no_drop：抽屉/闸门开门后，包裹没有掉落或明显滞留。
2. wrong_chute：A格口/抽屉开门，但包裹滑到旁边B格口或错误落点。
3. multi_parcel_on_cart：一个小车/抽屉上同时有2个及以上包裹。

输出必须是 JSON 数组。每个元素字段：
start_time, end_time, type, open_chute, actual_chute, evidence, confidence。
type 只能取：open_no_drop、wrong_chute、multi_parcel_on_cart、normal、uncertain。
confidence 取 0 到 1。
如果看不清，type 用 uncertain，confidence 不要超过 0.5。
"""


def run(cmd):
    subprocess.run(cmd, check=True)


def extract_frame(time_s: float, path: Path):
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
        "-q:v",
        "4",
        str(path),
    ])


def data_url(path: Path) -> str:
    raw = path.read_bytes()
    encoded = base64.b64encode(raw).decode("ascii")
    return f"data:image/jpeg;base64,{encoded}"


def build_windows():
    windows = []
    start = 0
    while start < VIDEO_DURATION:
        end = min(start + WINDOW_SECONDS, VIDEO_DURATION)
        frames = []
        for offset in FRAME_OFFSETS:
            t = min(start + offset, max(VIDEO_DURATION - 0.2, 0))
            if t < end + 0.05:
                frame_path = FRAMES_DIR / f"window_{start:02d}_{end:05.2f}_t{t:05.2f}.jpg"
                if not frame_path.exists():
                    extract_frame(t, frame_path)
                frames.append((t, frame_path))
        windows.append({"start": start, "end": end, "frames": frames})
        start += STRIDE_SECONDS
    return windows


def make_user_content(window):
    content = [
        {
            "type": "text",
            "text": (
                f"请分析这个快递分拣视频片段。片段时间范围："
                f"{window['start']:.1f}s 到 {window['end']:.1f}s。"
                "下面图片按时间顺序排列，每张图片文件名中包含原视频时间点。"
                "请判断是否存在 open_no_drop、wrong_chute、multi_parcel_on_cart。"
            ),
        }
    ]
    for t, path in window["frames"]:
        content.append({"type": "text", "text": f"frame_time={t:.2f}s"})
        content.append({"type": "image_url", "image_url": {"url": data_url(path)}})
    return content


def call_minimax(window):
    if not API_KEY:
        raise RuntimeError("MINIMAX_API_KEY is not set")

    url = f"{API_BASE.rstrip('/')}/text/chatcompletion_v2"
    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": MODEL,
        "messages": [
            {"role": "system", "name": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "name": "user", "content": make_user_content(window)},
        ],
        "temperature": 0.1,
        "max_tokens": 1200,
    }
    response = requests.post(url, headers=headers, json=payload, timeout=120)
    if response.status_code >= 400:
        raise RuntimeError(f"MiniMax HTTP {response.status_code}: {response.text[:1000]}")
    return response.json()


def extract_text(resp):
    try:
        return resp["choices"][0]["message"]["content"]
    except Exception:
        return json.dumps(resp, ensure_ascii=False)


def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    windows = build_windows()
    all_results = []
    for idx, window in enumerate(windows, start=1):
        print(f"Analyzing window {idx}/{len(windows)}: {window['start']:.1f}-{window['end']:.1f}s", flush=True)
        resp = call_minimax(window)
        text = extract_text(resp)
        all_results.append({
            "window_start": window["start"],
            "window_end": window["end"],
            "frames": [{"time": t, "path": str(p)} for t, p in window["frames"]],
            "raw_response": resp,
            "content": text,
        })

    RESULT_JSON.write_text(json.dumps(all_results, ensure_ascii=False, indent=2))
    lines = ["# MiniMax-M3 候选异常片段", ""]
    for item in all_results:
        lines.append(f"## {item['window_start']:.1f}s - {item['window_end']:.1f}s")
        lines.append("")
        lines.append("```json")
        lines.append(item["content"])
        lines.append("```")
        lines.append("")
    RESULT_MD.write_text("\n".join(lines))
    print(str(RESULT_JSON))
    print(str(RESULT_MD))


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(1)
