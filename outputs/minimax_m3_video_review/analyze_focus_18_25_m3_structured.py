import base64
import json
import os
import subprocess
import sys
from pathlib import Path

import requests


VIDEO = Path("/Users/lixing.guo/Desktop/异常检测视频/快递分类视频.mp4")
OUT_DIR = Path("/Users/lixing.guo/Documents/机械臂/outputs/minimax_m3_video_review/focus_18_25_structured")
FRAMES_DIR = OUT_DIR / "frames_fullpath_roi"
RESULT_JSON = OUT_DIR / "focus_18_25_structured_result.json"
RESULT_MD = OUT_DIR / "focus_18_25_structured_result.md"

API_BASE = os.environ.get("MINIMAX_API_BASE", "https://api.minimaxi.com/v1")
MODEL = os.environ.get("MINIMAX_MODEL", "MiniMax-M3")
API_KEY = os.environ.get("MINIMAX_API_KEY")

STEP = 0.2
CHUNKS = [
    ("segment_a", 17.8, 20.2),
    ("segment_b", 20.4, 22.2),
    ("segment_c", 23.0, 25.0),
]


SYSTEM_PROMPT = """你是快递分拣视频预标注助手。
目标：从连续帧中找出疑似异常时间段，给人工标注员复核。

重要：你不能因为看到设备运动就判异常。必须同时看到“包裹 + 机构动作/滑落轨迹 + 异常现象”。

现场结构说明：
- 画面上方是分拣小车/抽屉/格口开合机构；
- 画面中部是白色滑道/格口斜面；
- 画面下方是橙色导流板、格口边界和集包袋入口；
- 包裹正常情况：从对应小车/抽屉出来后，沿本格口滑道相对居中、连续、顺畅地下滑，最后进入对应袋口；
- 开门未落：抽屉/格口处于打开或放行状态，包裹却连续多帧停留在上部/格口区域，没有及时进入滑道；
- 滑落异常：包裹已经开始下滑，但轨迹明显横向偏移、贴边、跨边界、撞边、慢滑、偏离本格口中心线；
- 一车多件：同一小车/抽屉/承载区域同时可见2个及以上包裹。

负样例规则：
- 如果只看到空抽屉/空格口开合，不算异常；
- 如果包裹沿左/中/右某个滑道连续下滑并进入对应袋口，标 normal；
- 如果看不清包裹和打开机构的对应关系，标 uncertain，不要强判；
- 不要把设备白色挡板、灯光反射、背景牌子当包裹；
- 不要输出已知答案式结论，必须引用画面证据。

输出要求：
- 必须输出 JSON，不要输出 Markdown；
- frame_notes 每帧最多 20 个汉字；
- events 可以为空数组；
- 每个 event 必须包含关键帧时间和异常依据；
- confidence 保守给分：看得很清楚才 >0.85，不确定则 <=0.6。

JSON 格式：
{
  "segment_summary": "normal | has_candidate_anomaly | uncertain",
  "frame_notes": [{"time": "18.0s", "note": "简短描述"}],
  "events": [
    {
      "start_time": "18.0s",
      "end_time": "19.0s",
      "label": "open_no_drop | slide_abnormal | wrong_chute | multi_parcel_on_cart | normal | uncertain",
      "subtags": ["white_parcel", "black_parcel", "two_parcels_visible", "lateral_drift", "edge_stuck"],
      "evidence": "必须包含关键帧时间",
      "confidence": 0.0,
      "suggestion_for_human": "accept | review | reject"
    }
  ],
  "miss_risk": "low | medium | high",
  "false_positive_risk": "low | medium | high"
}
"""


def run(cmd):
    subprocess.run(cmd, check=True)


def extract_frame_roi(time_s: float, path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)
    # Full-path ROI: keep sorter mechanism + chute + bag entrance, remove most ceiling/bottom noise.
    # Input is 720x1280. Crop y=120..1000.
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


def build_frames(segment_name, start, end):
    frames = []
    for t in times(start, end):
        frame_path = FRAMES_DIR / segment_name / f"t{t:05.2f}.jpg"
        if not frame_path.exists():
            extract_frame_roi(t, frame_path)
        frames.append((t, frame_path))
    return frames


def call_minimax(segment_name, frames, start, end):
    if not API_KEY:
        raise RuntimeError("MINIMAX_API_KEY is not set")

    content = [
        {
            "type": "text",
            "text": (
                f"请分析候选片段 {segment_name}，时间 {start:.1f}s-{end:.1f}s。"
                "这些图片是分拣机构+滑道+袋口的全路径ROI，间隔0.2秒。"
                "请只根据画面证据给出预标注建议。"
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
    return resp.get("choices", [{}])[0].get("message", {}).get("content", "")


def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    results = []
    for segment_name, start, end in CHUNKS:
        frames = build_frames(segment_name, start, end)
        print(f"Prepared {len(frames)} full-path ROI frames for {segment_name} {start}-{end}", flush=True)
        resp = call_minimax(segment_name, frames, start, end)
        results.append({
            "segment_name": segment_name,
            "start": start,
            "end": end,
            "frames": [{"time": t, "path": str(p)} for t, p in frames],
            "finish_reason": resp.get("choices", [{}])[0].get("finish_reason"),
            "content": extract_text(resp),
            "raw_response": resp,
        })

    RESULT_JSON.write_text(json.dumps({
        "step_seconds": STEP,
        "crop": "crop=720:880:0:120",
        "segments": results,
    }, ensure_ascii=False, indent=2))

    md = ["# MiniMax-M3 结构规则版预标注（无答案提示 + 全路径ROI + 0.2秒）", ""]
    for item in results:
        md.append(f"## {item['segment_name']}：{item['start']:.1f}s - {item['end']:.1f}s")
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
