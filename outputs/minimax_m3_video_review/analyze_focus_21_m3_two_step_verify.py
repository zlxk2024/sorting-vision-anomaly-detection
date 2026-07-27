import base64
import json
import os
import subprocess
import sys
from pathlib import Path

import requests


VIDEO = Path("/Users/lixing.guo/Desktop/异常检测视频/快递分类视频.mp4")
OUT_DIR = Path("/Users/lixing.guo/Documents/机械臂/outputs/minimax_m3_video_review/focus_21_two_step_verify")
FRAMES_DIR = OUT_DIR / "frames_fullpath_roi"
RESULT_JSON = OUT_DIR / "focus_21_two_step_verify_result.json"
RESULT_MD = OUT_DIR / "focus_21_two_step_verify_result.md"

API_BASE = os.environ.get("MINIMAX_API_BASE", "https://api.minimaxi.com/v1")
MODEL = os.environ.get("MINIMAX_MODEL", "MiniMax-M3")
API_KEY = os.environ.get("MINIMAX_API_KEY")

START = 20.6
END = 22.2
STEP = 0.2


SYSTEM_PROMPT = """你是快递分拣视频候选异常核验员。
你需要用“两步法”判断 20.6s-22.2s 这段是否存在开门未落。

两步法：
第一步：数包裹并分配临时ID。
- 逐帧统计可见包裹数量；
- 如果同一帧有两个包裹，分别命名为 parcel_A、parcel_B；
- 记录它们的大致位置：左/中/右，小车上/开口处/滑道上/袋口附近。

第二步：分别跟踪每个包裹。
- 看 parcel_A 是否进入滑道、是否下落、是否停留；
- 看 parcel_B 是否进入滑道、是否下落、是否停留；
- 不能因为其中一个包裹正常移动，就忽略另一个包裹。

开门未落判定：
- yes：至少一个包裹在小车/抽屉/格口开口附近连续多帧停留，没有进入滑道/没有下落；
- no：所有可见包裹都只是随小车正常移动，或正常进入滑道下落；
- uncertain：能看到两件或停留现象，但开门状态/释放关系看不清。

重要限制：
- 没有 PLC 信号，所以你只能根据画面判断；
- 不要把设备结构、挡板、灯光、背景当包裹；
- 如果判断 open_no_drop，需要指出是哪一个包裹没有下落；
- 如果只能确认两件同框，但不能确认开门未落，要输出 uncertain，而不是 no。

输出紧凑 JSON，不要 Markdown：
{
  "frame_counts": [
    {"time": "20.6s", "parcel_count": 1, "parcel_positions": "简短"}
  ],
  "parcel_tracks": [
    {
      "parcel_id": "parcel_A",
      "visible_times": ["21.0s", "21.2s"],
      "track_summary": "简短轨迹",
      "drop_status": "dropped | stayed | moved_with_cart | disappeared | uncertain"
    }
  ],
  "two_parcels_visible": true,
  "open_no_drop_verdict": "yes | no | uncertain",
  "confidence": 0.0,
  "key_frames": ["21.0s", "21.2s"],
  "evidence": "最多120字",
  "human_action": "accept | review | reject"
}
"""


def run(cmd):
    subprocess.run(cmd, check=True)


def extract_frame_roi(time_s: float, path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)
    # Full-path ROI keeps upper mechanism + chute + bag entrance.
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
            extract_frame_roi(t, frame_path)
        frames.append((t, frame_path))
    return frames


def call_minimax(frames):
    if not API_KEY:
        raise RuntimeError("MINIMAX_API_KEY is not set")
    content = [
        {
            "type": "text",
            "text": (
                f"请用两步法分析 {START:.1f}s-{END:.1f}s 全路径ROI连续帧。"
                "每张图间隔0.2秒。先数包裹，再分别跟踪每个包裹，最后判断是否开门未落。"
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
    print(f"Prepared {len(frames)} frames for two-step verify {START}-{END}", flush=True)
    resp = call_minimax(frames)
    content = resp.get("choices", [{}])[0].get("message", {}).get("content", "")
    RESULT_JSON.write_text(json.dumps({
        "start": START,
        "end": END,
        "step_seconds": STEP,
        "crop": "crop=720:880:0:120",
        "frames": [{"time": t, "path": str(p)} for t, p in frames],
        "content": content,
        "raw_response": resp,
    }, ensure_ascii=False, indent=2))
    RESULT_MD.write_text("# MiniMax-M3 21秒两步法核验\n\n```json\n" + content + "\n```\n")
    print(str(RESULT_JSON))
    print(str(RESULT_MD))


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(1)
