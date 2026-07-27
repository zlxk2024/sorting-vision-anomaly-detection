from __future__ import annotations

import argparse
import csv
import json
import math
from collections import defaultdict
from pathlib import Path

import cv2
from ultralytics import YOLO


ROOT = Path("/Users/lixing.guo/Documents/机械臂")
VIDEO = Path("/Users/lixing.guo/Desktop/异常检测视频/快递分类视频.mp4")
WEIGHTS = ROOT / "runs/sorting_yolo/sorting_yolo11n_v1/weights/best.pt"
OUTPUT = ROOT / "runs/sorting_events_v1"
FPS = 30.0

CLASS_NAMES = {
    0: "parcel",
    1: "drawer_open",
    2: "drawer_closed",
    3: "chute",
    4: "bag",
}
COLORS = {
    0: (255, 120, 0),
    1: (40, 200, 40),
    2: (255, 255, 255),
    3: (40, 80, 255),
    4: (0, 200, 255),
}
EVENT_NAMES = {
    "open_no_drop": "不掉件",
    "wrong_chute": "飘格",
    "multi_parcel_drawer": "一车两件",
    "chute_stall": "失速/滞留",
}


def center(box):
    return ((box[0] + box[2]) / 2, (box[1] + box[3]) / 2)


def point_in(box, point):
    return box[0] <= point[0] <= box[2] and box[1] <= point[1] <= box[3]


def iou(a, b):
    x1, y1 = max(a[0], b[0]), max(a[1], b[1])
    x2, y2 = min(a[2], b[2]), min(a[3], b[3])
    inter = max(0, x2 - x1) * max(0, y2 - y1)
    aa = max(0, a[2] - a[0]) * max(0, a[3] - a[1])
    bb = max(0, b[2] - b[0]) * max(0, b[3] - b[1])
    return inter / max(aa + bb - inter, 1)


def deduplicate_parcels(items):
    kept = []
    for item in sorted(items, key=lambda x: x["confidence"], reverse=True):
        cx, cy = center(item["box"])
        duplicate = False
        for other in kept:
            ox, oy = center(other["box"])
            if iou(item["box"], other["box"]) > 0.25 or math.hypot(cx - ox, cy - oy) < 32:
                duplicate = True
                break
        if not duplicate:
            kept.append(item)
    return kept


def nearest_drawer(parcel, drawers, open_only=False):
    px, py = center(parcel["box"])
    candidates = []
    for drawer in drawers:
        if open_only and drawer["class_id"] != 1:
            continue
        x1, y1, x2, y2 = drawer["box"]
        w = x2 - x1
        # 抽屉包裹区：门板上方约 220 px，水平方向略放宽。
        zone = (x1 - 0.35 * w, y1 - 220, x2 + 0.35 * w, y2 + 35)
        if point_in(zone, (px, py)):
            dx, dy = center(drawer["box"])
            candidates.append((abs(px - dx) + 0.25 * abs(py - dy), drawer))
    return min(candidates, default=(None, None), key=lambda x: x[0])[1]


def merge_frame_events(frame_events, min_frames, event_type):
    grouped = defaultdict(list)
    for item in frame_events:
        grouped[item["key"]].append(item)
    merged = []
    for key, items in grouped.items():
        items.sort(key=lambda x: x["frame"])
        run = [items[0]]
        runs = []
        for item in items[1:]:
            if item["frame"] <= run[-1]["frame"] + 2:
                run.append(item)
            else:
                runs.append(run)
                run = [item]
        runs.append(run)
        for run in runs:
            duration = run[-1]["frame"] - run[0]["frame"] + 1
            if duration >= min_frames:
                merged.append(
                    {
                        "type": event_type,
                        "name": EVENT_NAMES[event_type],
                        "start_frame": run[0]["frame"],
                        "end_frame": run[-1]["frame"],
                        "start_seconds": round((run[0]["frame"] - 1) / FPS, 3),
                        "end_seconds": round((run[-1]["frame"] - 1) / FPS, 3),
                        "confidence": round(
                            sum(x["confidence"] for x in run) / len(run), 3
                        ),
                        "track_ids": run[0].get("track_ids", [key]),
                        "evidence": run[0]["evidence"],
                    }
                )
    return merged


def consecutive_runs(history, max_gap=2):
    if not history:
        return []
    history = sorted(history, key=lambda x: x["frame"])
    runs = [[history[0]]]
    for item in history[1:]:
        if item["frame"] <= runs[-1][-1]["frame"] + max_gap:
            runs[-1].append(item)
        else:
            runs.append([item])
    return runs


def coalesce_events(events):
    merged = []
    for event in sorted(events, key=lambda x: (x["type"], x["start_frame"])):
        same = next(
            (
                existing
                for existing in reversed(merged)
                if existing["type"] == event["type"]
                and set(existing["track_ids"]) == set(event["track_ids"])
                and event["start_frame"] <= existing["end_frame"] + 3
            ),
            None,
        )
        if same:
            same["end_frame"] = max(same["end_frame"], event["end_frame"])
            same["end_seconds"] = round((same["end_frame"] - 1) / FPS, 3)
            same["confidence"] = round(max(same["confidence"], event["confidence"]), 3)
        else:
            merged.append(event)
    return sorted(merged, key=lambda x: (x["start_frame"], x["type"]))


def analyze(frames):
    tracks = defaultdict(list)
    expected_chute = {}
    no_drop_candidates = []
    multi_candidates = []
    wrong_candidates = []

    for frame_data in frames:
        frame_no = frame_data["frame"]
        dets = frame_data["detections"]
        parcels = deduplicate_parcels([d for d in dets if d["class_id"] == 0])
        drawers = [d for d in dets if d["class_id"] in {1, 2}]
        opens = [d for d in drawers if d["class_id"] == 1]
        chutes = sorted(
            [d for d in dets if d["class_id"] == 3],
            key=lambda d: center(d["box"])[0],
        )

        for parcel in parcels:
            tid = parcel["track_id"]
            if tid is not None:
                chute_boundary = None
                if len(chutes) >= 2:
                    chute_boundary = (
                        chutes[0]["box"][2] + chutes[1]["box"][0]
                    ) / 2
                chute_index = next(
                    (
                        idx
                        for idx, chute in enumerate(chutes)
                        if point_in(chute["box"], center(parcel["box"]))
                    ),
                    None,
                )
                tracks[tid].append(
                    {
                        "frame": frame_no,
                        "point": center(parcel["box"]),
                        "confidence": parcel["confidence"],
                        "in_chute": any(
                            point_in(chute["box"], center(parcel["box"]))
                            for chute in chutes
                        ),
                        "chute_index": chute_index,
                        "chute_boundary": chute_boundary,
                    }
                )
            drawer = nearest_drawer(parcel, drawers)
            if drawer and tid is not None and len(chutes) >= 2:
                drawer_x = center(drawer["box"])[0]
                expected = min(
                    range(len(chutes)),
                    key=lambda idx: abs(center(chutes[idx]["box"])[0] - drawer_x),
                )
                expected_chute.setdefault(tid, expected)

            open_drawer = nearest_drawer(parcel, opens, open_only=True)
            if open_drawer and tid is not None:
                px, py = center(parcel["box"])
                dx, dy = center(open_drawer["box"])
                no_drop_candidates.append(
                    {
                        "key": tid,
                        "frame": frame_no,
                        "confidence": min(parcel["confidence"], open_drawer["confidence"]),
                        "relative_y": py - dy,
                        "track_ids": [tid],
                        "evidence": "drawer_open 持续存在，包裹相对门板未产生正常向下位移",
                    }
                )

            if tid is not None and tid in expected_chute and len(chutes) >= 2:
                actual = next(
                    (
                        idx
                        for idx, chute in enumerate(chutes)
                        if point_in(chute["box"], center(parcel["box"]))
                    ),
                    None,
                )
                if actual is not None and actual != expected_chute[tid]:
                    wrong_candidates.append(
                        {
                            "key": tid,
                            "frame": frame_no,
                            "confidence": parcel["confidence"],
                            "track_ids": [tid],
                            "evidence": (
                                f"包裹来源关联闸口 {expected_chute[tid] + 1}，"
                                f"实际进入闸口 {actual + 1}"
                            ),
                        }
                    )

        # 同一抽屉内必须存在两个空间上可分离的包裹，连续出现才成立。
        for drawer in drawers:
            assigned = [p for p in parcels if nearest_drawer(p, [drawer]) is not None]
            if len(assigned) >= 2:
                ids = sorted({p["track_id"] for p in assigned if p["track_id"] is not None})
                if len(ids) >= 2:
                    pair = tuple(ids[:2])
                    multi_candidates.append(
                        {
                            "key": pair,
                            "frame": frame_no,
                            "confidence": min(
                                drawer["confidence"],
                                *(p["confidence"] for p in assigned[:2]),
                            ),
                            "track_ids": list(pair),
                            "evidence": "同一抽屉包裹区内持续检测到两个独立包裹轨迹",
                        }
                    )

    # 不掉件路径一：门状态明确时，检查包裹相对门板的纵向变化。
    stable_no_drop = []
    by_track = defaultdict(list)
    for item in no_drop_candidates:
        by_track[item["key"]].append(item)
    for tid, items in by_track.items():
        items.sort(key=lambda x: x["frame"])
        for item in items:
            nearby = [x for x in items if item["frame"] <= x["frame"] <= item["frame"] + 24]
            if len(nearby) >= 20:
                values = [x["relative_y"] for x in nearby]
                if max(values) - min(values) <= 38:
                    stable_no_drop.extend(nearby)

    events = []
    events += merge_frame_events(stable_no_drop, 20, "open_no_drop")
    events += merge_frame_events(multi_candidates, 4, "multi_parcel_drawer")

    # 不掉件路径二：门状态偶发错分时，用“随小车横移、纵向不落”的相对运动补偿。
    # 至少连续约 0.57 秒，水平移动明显，纵向范围很小，并且位于上层分拣机构。
    for tid, history in tracks.items():
        for run in consecutive_runs(history):
            if len(run) < 18 or run[-1]["frame"] - run[0]["frame"] < 17:
                continue
            ys = [item["point"][1] for item in run]
            dx = run[-1]["point"][0] - run[0]["point"][0]
            dy = run[-1]["point"][1] - run[0]["point"][1]
            if (
                max(ys) < 520
                and max(ys) - min(ys) <= 45
                and abs(dy) <= 32
                and abs(dx) >= 100
            ):
                events.append(
                    {
                        "type": "open_no_drop",
                        "name": EVENT_NAMES["open_no_drop"],
                        "start_frame": run[0]["frame"],
                        "end_frame": run[-1]["frame"],
                        "start_seconds": round((run[0]["frame"] - 1) / FPS, 3),
                        "end_seconds": round((run[-1]["frame"] - 1) / FPS, 3),
                        "confidence": round(
                            0.85 * sum(x["confidence"] for x in run) / len(run), 3
                        ),
                        "track_ids": [tid],
                        "evidence": "包裹随小车水平移动，但连续多帧没有正常向下位移",
                    }
                )

    # 飘格路径：优先使用来源/目标闸口映射；检测断续时用轨迹跨越闸口边界补偿。
    events += merge_frame_events(wrong_candidates, 3, "wrong_chute")
    for tid, history in tracks.items():
        for run in consecutive_runs(history):
            if len(run) < 8:
                continue
            occupied = [x["chute_index"] for x in run if x["chute_index"] is not None]
            dx = run[-1]["point"][0] - run[0]["point"][0]
            dy = run[-1]["point"][1] - run[0]["point"][1]
            boundaries = [x["chute_boundary"] for x in run if x["chute_boundary"] is not None]
            boundary_crossed = False
            source_index = target_index = None
            if boundaries:
                boundary = sorted(boundaries)[len(boundaries) // 2]
                source_index = 0 if run[0]["point"][0] < boundary else 1
                target_index = 0 if run[-1]["point"][0] < boundary else 1
                boundary_crossed = source_index != target_index
            if len(occupied) >= 5 and occupied[0] != occupied[-1]:
                source_index, target_index = occupied[0], occupied[-1]
                boundary_crossed = True
            if boundary_crossed and abs(dx) >= 150 and dy >= 60:
                events.append(
                    {
                        "type": "wrong_chute",
                        "name": EVENT_NAMES["wrong_chute"],
                        "start_frame": run[0]["frame"],
                        "end_frame": run[-1]["frame"],
                        "start_seconds": round((run[0]["frame"] - 1) / FPS, 3),
                        "end_seconds": round((run[-1]["frame"] - 1) / FPS, 3),
                        "confidence": round(
                            0.9 * sum(x["confidence"] for x in run) / len(run), 3
                        ),
                        "track_ids": [tid],
                        "evidence": (
                            f"包裹轨迹从闸口 {source_index + 1} "
                            f"跨越边界进入闸口 {target_index + 1}"
                        ),
                    }
                )

    # 失速/滞留：轨迹在闸口范围内持续至少 0.65 秒且净位移很小。
    stall_events = []
    for tid, history in tracks.items():
        if len(history) < 20:
            continue
        for start in range(0, len(history) - 19):
            window = history[start : start + 20]
            if window[-1]["frame"] - window[0]["frame"] > 24:
                continue
            if sum(item["in_chute"] for item in window) < 15:
                continue
            x1, y1 = window[0]["point"]
            x2, y2 = window[-1]["point"]
            if math.hypot(x2 - x1, y2 - y1) <= 35:
                stall_events.append(
                    {
                        "type": "chute_stall",
                        "name": EVENT_NAMES["chute_stall"],
                        "start_frame": window[0]["frame"],
                        "end_frame": window[-1]["frame"],
                        "start_seconds": round((window[0]["frame"] - 1) / FPS, 3),
                        "end_seconds": round((window[-1]["frame"] - 1) / FPS, 3),
                        "confidence": round(
                            sum(x["confidence"] for x in window) / len(window), 3
                        ),
                        "track_ids": [tid],
                        "evidence": "包裹轨迹连续约 0.65 秒净位移不超过 35 px",
                    }
                )
                break
    events += stall_events
    return coalesce_events(events)


def save_outputs(frames, events):
    OUTPUT.mkdir(parents=True, exist_ok=True)
    (OUTPUT / "events_v1.json").write_text(
        json.dumps(events, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    with (OUTPUT / "events_v1.csv").open("w", newline="", encoding="utf-8") as f:
        fieldnames = [
            "type",
            "name",
            "start_frame",
            "end_frame",
            "start_seconds",
            "end_seconds",
            "confidence",
            "track_ids",
            "evidence",
        ]
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for event in events:
            writer.writerow({**event, "track_ids": "|".join(map(str, event["track_ids"]))})
    (OUTPUT / "detections_v1.json").write_text(
        json.dumps(frames, ensure_ascii=False), encoding="utf-8"
    )

    cap = cv2.VideoCapture(str(VIDEO))
    fps = cap.get(cv2.CAP_PROP_FPS) or FPS
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    writer = cv2.VideoWriter(
        str(OUTPUT / "sorting_events_v1.mp4"),
        cv2.VideoWriter_fourcc(*"mp4v"),
        fps,
        (width, height),
    )
    active_by_frame = defaultdict(list)
    for event in events:
        for frame_no in range(event["start_frame"], event["end_frame"] + 1):
            active_by_frame[frame_no].append(event)

    frame_no = 1
    while True:
        ok, image = cap.read()
        if not ok:
            break
        if frame_no <= len(frames):
            for det in frames[frame_no - 1]["detections"]:
                x1, y1, x2, y2 = map(int, det["box"])
                color = COLORS[det["class_id"]]
                cv2.rectangle(image, (x1, y1), (x2, y2), color, 2)
                text = f'{CLASS_NAMES[det["class_id"]]} {det["confidence"]:.2f}'
                cv2.putText(
                    image, text, (x1, max(20, y1 - 6)),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 1, cv2.LINE_AA
                )
        y = 45
        for event in active_by_frame.get(frame_no, []):
            text = (
                f'ALARM {event["name"]} '
                f'{event["start_seconds"]:.1f}-{event["end_seconds"]:.1f}s'
            )
            cv2.rectangle(image, (15, y - 28), (min(width - 10, 600), y + 8), (0, 0, 220), -1)
            cv2.putText(
                image, text, (25, y),
                cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 255), 2, cv2.LINE_AA
            )
            y += 45
        writer.write(image)
        frame_no += 1
    cap.release()
    writer.release()


def main():
    global VIDEO, WEIGHTS, OUTPUT, FPS
    parser = argparse.ArgumentParser(description="YOLO + tracking sorting anomaly detector")
    parser.add_argument("--video", type=Path, default=VIDEO)
    parser.add_argument("--weights", type=Path, default=WEIGHTS)
    parser.add_argument("--output", type=Path, default=OUTPUT)
    parser.add_argument("--device", default="cpu")
    parser.add_argument("--imgsz", type=int, default=320)
    parser.add_argument("--conf", type=float, default=0.15)
    args = parser.parse_args()
    VIDEO = args.video.expanduser().resolve()
    WEIGHTS = args.weights.expanduser().resolve()
    OUTPUT = args.output.expanduser().resolve()
    if not VIDEO.is_file():
        parser.error(f"video not found: {VIDEO}")
    if not WEIGHTS.is_file():
        parser.error(f"weights not found: {WEIGHTS}")

    probe = cv2.VideoCapture(str(VIDEO))
    detected_fps = probe.get(cv2.CAP_PROP_FPS)
    probe.release()
    if detected_fps and detected_fps > 0:
        FPS = float(detected_fps)

    OUTPUT.mkdir(parents=True, exist_ok=True)
    model = YOLO(str(WEIGHTS))
    frames = []
    results = model.track(
        source=str(VIDEO),
        stream=True,
        persist=True,
        tracker="bytetrack.yaml",
        imgsz=args.imgsz,
        conf=args.conf,
        iou=0.5,
        device=args.device,
        verbose=False,
    )
    for frame_no, result in enumerate(results, start=1):
        detections = []
        ids = result.boxes.id
        ids = ids.int().cpu().tolist() if ids is not None else [None] * len(result.boxes)
        for box, class_id, confidence, track_id in zip(
            result.boxes.xyxy.cpu().tolist(),
            result.boxes.cls.int().cpu().tolist(),
            result.boxes.conf.cpu().tolist(),
            ids,
        ):
            detections.append(
                {
                    "class_id": class_id,
                    "class_name": CLASS_NAMES[class_id],
                    "confidence": round(confidence, 4),
                    "track_id": track_id,
                    "box": [round(value, 2) for value in box],
                }
            )
        frames.append({"frame": frame_no, "detections": detections})
        if frame_no % 150 == 0:
            print(f"processed {frame_no} frames")
    events = analyze(frames)
    save_outputs(frames, events)
    print(json.dumps(events, ensure_ascii=False, indent=2))
    print(OUTPUT)


if __name__ == "__main__":
    main()
