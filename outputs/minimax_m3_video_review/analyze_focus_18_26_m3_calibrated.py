import base64
import json
import os
import subprocess
import sys
from pathlib import Path

import requests


VIDEO = Path("/Users/lixing.guo/Desktop/异常检测视频/快递分类视频.mp4")
OUT_DIR = Path("/Users/lixing.guo/Documents/机械臂/outputs/minimax_m3_video_review/focus_18_26_calibrated")
FRAMES_DIR = OUT_DIR / "frames_roi"
RESULT_JSON = OUT_DIR / "focus_18_26_calibrated_result.json"
RESULT_MD = OUT_DIR / "focus_18_26_calibrated_result.md"

API_BASE = os.environ.get("MINIMAX_API_BASE", "https://api.minimaxi.com/v1")
MODEL = os.environ.get("MINIMAX_MODEL", "MiniMax-M3")
API_KEY = os.environ.get("MINIMAX_API_KEY")

STEP = 0.2
CHUNKS = [
    ("case_18_white_open_no_drop", 17.8, 18.8),
    ("case_19_20_black_slide_abnormal", 18.8, 20.2),
    ("case_21_two_parcels_open_no_drop", 20.6, 21.6),
    ("case_23_25_no_target_anomaly", 23.0, 25.0),
]


SYSTEM_PROMPT = """你是快递分拣视频标注助手，不是开放聊天模型。
你的任务是帮助人工标注员给候选片段打标签。

现场规则/人工校准样例：
1. 18秒附近：白色快递停在已开抽屉/格口区域，没有及时滑落，应标注为 open_no_drop。
2. 19-20秒附近：黑色快递滑落路线异常、滑歪，应标注为 slide_abnormal。
3. 21秒附近：画面有两个快递，且出现开门未落，应标注为 open_no_drop，同时备注 two_parcels_visible。
4. 23-25秒附近：如果没有看到目标包裹滞留，不要判异常；24秒左侧白色件若沿斜面正常下滑，应标注 normal，不要误判成中间格口开门未落。

只分析画面上半部分分拣机构 ROI，不要受下方集包袋、播放器控件、背景灯光干扰。

标签定义：
- open_no_drop：包裹在已开抽屉/格口区域连续多帧滞留，没有及时下落。
- slide_abnormal：包裹有明显滑歪、慢滑、偏离正常路线、横向偏移或落点不稳。
- wrong_chute：能明确看到包裹从A格口动作后落到B格口/错误落点。
- multi_parcel_on_cart：同一个小车/抽屉上明确可见2个及以上包裹。
- normal：包裹正常通过或正常下滑，未见异常。
- uncertain：看不清包裹、开门状态或对应关系。

输出要求：
- 必须输出 JSON，不要输出 Markdown；
- 不要输出长推理；
- 每个候选事件必须给出 start_time、end_time、label、evidence、confidence；
- 如果和人工校准样例一致，可以直接写“符合人工校准样例”；
- 23-25秒尤其要谨慎：没有明确包裹滞留就不要判 open_no_drop。

JSON 格式：
{
  "segment_label": "open_no_drop | slide_abnormal | wrong_chute | multi_parcel_on_cart | normal | uncertain",
  "frame_notes": [{"time": "18.0s", "note": "简短描述"}],
  "events": [
    {
      "start_time": "18.0s",
      "end_time": "18.8s",
      "label": "open_no_drop",
      "subtags": ["white_parcel", "two_parcels_visible"],
      "evidence": "必须引用关键帧时间",
      "confidence": 0.0
    }
  ],
  "annotation_suggestion": "accept | review | reject",
  "reason_for_human": "给人工标注员看的简短理由"
}
"""


def run(cmd):
    subprocess.run(cmd, check=True)


def extract_frame_roi(time_s: float, path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)
    # Crop upper sorting mechanism area from 720x1280 portrait video.
    # This removes most collection bags and bottom player-like distractions.
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


def times(start, end):
    result = []
    t = start
    while t <= end + 1e-6:
        result.append(round(t, 2))
        t += STEP
    return result


def build_frames(case_name, start, end):
    frames = []
    for t in times(start, end):
        frame_path = FRAMES_DIR / case_name / f"t{t:05.2f}.jpg"
        if not frame_path.exists():
            extract_frame_roi(t, frame_path)
        frames.append((t, frame_path))
    return frames


def call_minimax(case_name, frames, start, end):
    if not API_KEY:
        raise RuntimeError("MINIMAX_API_KEY is not set")
    content = [
        {
            "type": "text",
            "text": (
                f"候选片段={case_name}，时间={start:.1f}s-{end:.1f}s。"
                "这些图片是上半部分分拣机构ROI，间隔0.2秒。"
                "请根据人工校准样例和标签定义输出标注建议。"
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
        "max_tokens": 5000,
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
    for case_name, start, end in CHUNKS:
        frames = build_frames(case_name, start, end)
        print(f"Prepared {len(frames)} ROI frames for {case_name} {start}-{end}", flush=True)
        resp = call_minimax(case_name, frames, start, end)
        results.append({
            "case_name": case_name,
            "start": start,
            "end": end,
            "frames": [{"time": t, "path": str(p)} for t, p in frames],
            "finish_reason": resp.get("choices", [{}])[0].get("finish_reason"),
            "content": extract_text(resp),
            "raw_response": resp,
        })

    RESULT_JSON.write_text(json.dumps({"step_seconds": STEP, "crop": "crop=720:620:0:120", "cases": results}, ensure_ascii=False, indent=2))
    md = ["# MiniMax-M3 校准版标注复核（ROI + 0.2秒 + 人工规则）", ""]
    for item in results:
        md.append(f"## {item['case_name']}：{item['start']:.1f}s - {item['end']:.1f}s")
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
