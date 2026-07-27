import base64
import json
import os
import subprocess
import sys
from pathlib import Path

import requests


VIDEO = Path("/Users/lixing.guo/Desktop/异常检测视频/快递分类视频.mp4")
OUT_DIR = Path("/Users/lixing.guo/Documents/机械臂/outputs/minimax_m3_video_review/focus_18_26")
FRAMES_DIR = OUT_DIR / "frames"
RESULT_JSON = OUT_DIR / "focus_18_26_result.json"
RESULT_MD = OUT_DIR / "focus_18_26_result.md"

API_BASE = os.environ.get("MINIMAX_API_BASE", "https://api.minimaxi.com/v1")
MODEL = os.environ.get("MINIMAX_MODEL", "MiniMax-M3")
API_KEY = os.environ.get("MINIMAX_API_KEY")

START = 18.0
END = 26.0
STEP = 0.5
CHUNKS = [(18.0, 22.0), (22.0, 26.0)]


SYSTEM_PROMPT = """你是快递分拣异常识别质检员。
你将看到同一段快递分拣视频的连续关键帧，间隔约0.5秒。

请特别关注：
1. 抽屉/闸门是否打开；
2. 打开后包裹是否立即掉落，还是滞留/不掉；
3. 包裹是否从目标格口滑落到旁边格口或错误落点；
4. 小车/抽屉上是否有2个及以上包裹；
5. 是否存在“滑歪”“慢滑”“开门未落”“掉错格口”。

要求：
- 不要输出推理过程；
- 每帧 observation 最多 25 个汉字；
- evidence 最多 50 个汉字；
- 必须输出 JSON，不要输出 Markdown；
- 只根据画面判断，看不清就写 uncertain，不要编造格口编号；

JSON 格式：
{
  "frame_observations": [
    {
      "time": "18.0s",
      "observation": "这一帧看到的现象"
    }
  ],
  "events": [
    {
      "start_time": "18.0s",
      "end_time": "26.0s",
      "type": "open_no_drop | wrong_chute | slide_abnormal | multi_parcel_on_cart | normal | uncertain",
      "open_chute": "未知/左/中/右/A/B/C/编号",
      "actual_chute": "未知/左/中/右/A/B/C/无",
      "evidence": "关键依据",
      "confidence": 0.0
    }
  ],
  "need_human_review": true
}
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
    return "data:image/jpeg;base64," + base64.b64encode(path.read_bytes()).decode("ascii")


def times(start=START, end=END):
    result = []
    t = start
    while t <= end + 1e-6:
        result.append(round(t, 2))
        t += STEP
    return result


def build_frames(start=START, end=END):
    frames = []
    for t in times(start, end):
        frame_path = FRAMES_DIR / f"t{t:05.2f}.jpg"
        if not frame_path.exists():
            extract_frame(t, frame_path)
        frames.append((t, frame_path))
    return frames


def call_minimax(frames, start, end):
    if not API_KEY:
        raise RuntimeError("MINIMAX_API_KEY is not set")
    content = [
        {
            "type": "text",
            "text": (
                f"请分析原视频 {start:.1f}s 到 {end:.1f}s 的连续关键帧。"
                "每张图间隔约0.5秒。只输出紧凑 JSON。"
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
        "max_tokens": 6000,
    }
    url = f"{API_BASE.rstrip('/')}/text/chatcompletion_v2"
    headers = {"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"}
    resp = requests.post(url, headers=headers, json=payload, timeout=180)
    if resp.status_code >= 400:
        raise RuntimeError(f"MiniMax HTTP {resp.status_code}: {resp.text[:1200]}")
    return resp.json()


def extract_text(resp):
    try:
        return resp["choices"][0]["message"]["content"]
    except Exception:
        return json.dumps(resp, ensure_ascii=False)


def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    chunk_results = []
    all_frames = []
    for start, end in CHUNKS:
        frames = build_frames(start, end)
        all_frames.extend(frames)
        print(f"Prepared {len(frames)} frames from {start}s to {end}s", flush=True)
        resp = call_minimax(frames, start, end)
        text = extract_text(resp)
        chunk_results.append({
            "start": start,
            "end": end,
            "frames": [{"time": t, "path": str(p)} for t, p in frames],
            "finish_reason": resp.get("choices", [{}])[0].get("finish_reason"),
            "content": text,
            "raw_response": resp,
        })
    RESULT_JSON.write_text(json.dumps({"frames": [{"time": t, "path": str(p)} for t, p in all_frames], "chunks": chunk_results}, ensure_ascii=False, indent=2))
    md = ["# MiniMax-M3 18-26秒重点复核", ""]
    for item in chunk_results:
        md.append(f"## {item['start']:.1f}s - {item['end']:.1f}s")
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
