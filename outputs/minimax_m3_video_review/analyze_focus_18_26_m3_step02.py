import base64
import json
import os
import subprocess
import sys
from pathlib import Path

import requests


VIDEO = Path("/Users/lixing.guo/Desktop/异常检测视频/快递分类视频.mp4")
OUT_DIR = Path("/Users/lixing.guo/Documents/机械臂/outputs/minimax_m3_video_review/focus_18_26_step02")
FRAMES_DIR = OUT_DIR / "frames"
RESULT_JSON = OUT_DIR / "focus_18_26_step02_result.json"
RESULT_MD = OUT_DIR / "focus_18_26_step02_result.md"

API_BASE = os.environ.get("MINIMAX_API_BASE", "https://api.minimaxi.com/v1")
MODEL = os.environ.get("MINIMAX_MODEL", "MiniMax-M3")
API_KEY = os.environ.get("MINIMAX_API_KEY")

STEP = 0.2
CHUNKS = [(18.0, 20.2), (20.4, 22.2), (22.4, 26.0)]


SYSTEM_PROMPT = """你是快递分拣异常识别质检员。
你将看到同一段快递分拣视频的连续关键帧，间隔约0.2秒。

核心任务：
识别以下异常：
1. open_no_drop：明确看到包裹在已打开抽屉/格口上连续多帧滞留，没有按预期下落；
2. slide_abnormal：明确看到包裹滑歪、慢滑、偏离正常下落路线；
3. wrong_chute：明确看到包裹从A格口/抽屉动作后落到相邻B格口/错误落点；
4. multi_parcel_on_cart：同一个小车/抽屉上明确看到2个及以上包裹。

严格判定规则：
- 如果没有明确看到包裹，不允许判定 open_no_drop、slide_abnormal 或 wrong_chute；
- 如果只看到盖板/抽屉运动，但没有看到包裹，必须判 normal 或 uncertain；
- 如果不能确认“包裹”和“打开格口/抽屉”的对应关系，必须判 uncertain；
- 只有同时满足“看到包裹在抽屉/格口上”+“看到闸门/盖板打开或处于打开状态”+“连续多帧未正常下落”，才允许判 open_no_drop；
- 不要根据想象补全格口编号，不要把远处模糊白色结构误认为包裹；
- 对每个异常必须引用关键帧时间作为证据；
- 如果是误报风险较高，请降低 confidence 并写 uncertain。

输出要求：
- 不要输出推理过程；
- 必须输出 JSON，不要输出 Markdown；
- 每帧 observation 最多 20 个汉字；
- evidence 最多 60 个汉字；

JSON 格式：
{
  "frame_observations": [
    {"time": "18.0s", "observation": "简短现象"}
  ],
  "events": [
    {
      "start_time": "18.0s",
      "end_time": "20.2s",
      "type": "open_no_drop | wrong_chute | slide_abnormal | multi_parcel_on_cart | normal | uncertain",
      "open_chute": "未知/左/中/右/A/B/C/编号",
      "actual_chute": "未知/左/中/右/A/B/C/无",
      "evidence": "关键依据，必须包含帧时间",
      "confidence": 0.0
    }
  ],
  "false_positive_risk": "low | medium | high",
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


def times(start, end):
    result = []
    t = start
    while t <= end + 1e-6:
        result.append(round(t, 2))
        t += STEP
    return result


def build_frames(start, end):
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
                "每张图间隔约0.2秒。请严格按规则：看不到包裹就不准判异常。"
                "只输出紧凑 JSON。"
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
        "max_tokens": 7000,
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

    RESULT_JSON.write_text(json.dumps({
        "step_seconds": STEP,
        "frames": [{"time": t, "path": str(p)} for t, p in all_frames],
        "chunks": chunk_results,
    }, ensure_ascii=False, indent=2))

    md = ["# MiniMax-M3 18-26秒重点复核（0.2秒抽帧 + 严格提示词）", ""]
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
