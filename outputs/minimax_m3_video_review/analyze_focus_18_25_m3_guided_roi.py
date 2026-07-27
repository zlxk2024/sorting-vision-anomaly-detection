import base64
import json
import os
import subprocess
import sys
from pathlib import Path

import requests


VIDEO = Path("/Users/lixing.guo/Desktop/异常检测视频/快递分类视频.mp4")
OUT_DIR = Path("/Users/lixing.guo/Documents/机械臂/outputs/minimax_m3_video_review/focus_18_25_guided_roi")
FRAMES_DIR = OUT_DIR / "frames_guided_roi"
RESULT_JSON = OUT_DIR / "focus_18_25_guided_roi_result.json"
RESULT_MD = OUT_DIR / "focus_18_25_guided_roi_result.md"

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
你看到的是带颜色参考框的连续帧，颜色框只是观察区域，不代表答案。

颜色区域含义：
- 红框：释放/开门/滞留观察区。重点看包裹是否停在小车、抽屉、格口开口附近。
- 蓝框：滑道轨迹区。重点看包裹是否沿本格口滑道居中、连续下滑，是否贴边、横向偏移、滑歪。
- 绿框：袋口落点区。重点看包裹是否进入对应袋口，是否偏到相邻袋口或袋外。

判定规则：
- open_no_drop：包裹在红框或红蓝交界处连续多帧滞留，且未进入蓝框正常滑道。
- slide_abnormal：包裹进入蓝框后轨迹明显贴边、横向偏移、跨格口边界、慢滑或从边缘异常滑出。
- wrong_chute：包裹从一个格口释放，但最终进入相邻/错误绿框袋口。
- multi_parcel_on_cart：同一承载小车/抽屉上同时看见2个及以上包裹。
- normal：包裹从红框释放后，沿蓝框正常下滑并进入对应绿框袋口。
- uncertain：看不清包裹、开门状态或轨迹对应关系。

严格限制：
- 不能把颜色框当作物体；
- 不能只因为机构开合就判异常，必须看到包裹；
- 每个异常必须引用连续关键帧时间；
- 置信度要保守，明显才高于0.85。

输出 JSON：
{
  "segment_summary": "normal | has_candidate_anomaly | uncertain",
  "frame_notes": [{"time": "18.0s", "note": "简短描述"}],
  "events": [
    {
      "start_time": "18.0s",
      "end_time": "19.0s",
      "label": "open_no_drop | slide_abnormal | wrong_chute | multi_parcel_on_cart | normal | uncertain",
      "subtags": ["white_parcel", "black_parcel", "two_parcels_visible", "red_zone_stay", "blue_zone_drift", "green_zone_entry"],
      "evidence": "必须包含关键帧时间和红/蓝/绿区域证据",
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


def extract_guided_frame(time_s: float, path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)
    # Crop full-path ROI, then overlay observation zones:
    # red: release/stay region, blue: chute path, green: bag-entry region.
    vf = ",".join([
        "crop=720:880:0:120",
        "drawbox=x=0:y=65:w=720:h=215:color=red@0.45:t=5",
        "drawbox=x=0:y=230:w=720:h=305:color=blue@0.35:t=5",
        "drawbox=x=0:y=520:w=720:h=260:color=green@0.35:t=5",
    ])
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
        vf,
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
            extract_guided_frame(t, frame_path)
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
                "图片间隔0.2秒，并带有红/蓝/绿观察区域框。"
                "请根据颜色区域定义和画面证据输出预标注。"
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
        print(f"Prepared {len(frames)} guided ROI frames for {segment_name} {start}-{end}", flush=True)
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
        "overlay": {
            "red": "release/stay region: y=65..280",
            "blue": "chute path: y=230..535",
            "green": "bag entry: y=520..780",
        },
        "segments": results,
    }, ensure_ascii=False, indent=2))

    md = ["# MiniMax-M3 区域参考线版预标注（红/蓝/绿ROI + 0.2秒）", ""]
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
