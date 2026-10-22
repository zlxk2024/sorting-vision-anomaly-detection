"""Measure synchronous API latency and throughput using caller-owned videos."""
from __future__ import annotations

import argparse
import json
import os
import statistics
import subprocess
import threading
import time
import urllib.request
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", default="http://127.0.0.1:8080")
    parser.add_argument("--video", type=Path, nargs="+", required=True)
    parser.add_argument("--repeats", type=int, default=3)
    parser.add_argument("--timeout", type=int, default=1900)
    parser.add_argument("--container", help="Optional Docker container name for resource sampling")
    parser.add_argument("--output", type=Path, default=Path("runs/benchmark.json"))
    args = parser.parse_args()
    if args.repeats < 1:
        parser.error("repeats must be positive")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    headers = {}
    if os.environ.get("SORTING_API_KEY"):
        headers["Authorization"] = "Bearer " + os.environ["SORTING_API_KEY"]
    samples, results = [], []
    sampler = None
    if args.container:
        sampler = subprocess.Popen(
            ["docker", "stats", "--format", "{{json .}}", args.container],
            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True,
        )
        def collect():
            for line in sampler.stdout:
                start = line.find("{")
                if start < 0:
                    continue
                try:
                    item = json.loads(line[start:])
                    samples.append({"monotonic": time.monotonic(), "cpu_percent": float(item["CPUPerc"].rstrip("%")),
                                    "memory_usage": item["MemUsage"], "memory_percent": float(item["MemPerc"].rstrip("%"))})
                except (ValueError, KeyError):
                    continue
        thread = threading.Thread(target=collect, daemon=True)
        thread.start()
    try:
        for video in args.video:
            for repeat in range(1, args.repeats + 1):
                started = time.monotonic()
                with video.open("rb") as stream:
                    request = urllib.request.Request(
                        args.url.rstrip("/") + "/v1/analyze-video", data=stream,
                        headers={**headers, "Content-Type": "application/octet-stream",
                                 "Content-Length": str(video.stat().st_size), "X-Filename": video.name},
                    )
                    with urllib.request.urlopen(request, timeout=args.timeout) as response:
                        result = json.load(response)
                completed = time.monotonic()
                record = {"video": video.name, "repeat": repeat, "frames": result["frame_count"],
                          "request_seconds": round(completed - started, 4),
                          "effective_fps": round(result["frame_count"] / (completed - started), 3),
                          "event_count": result["event_count"], "job_id": result["job_id"]}
                # Download is measured separately from the upload-to-result request.
                artifact_url = args.url.rstrip("/") + result["artifacts"]["video"]
                download_started = time.monotonic()
                size = 0
                with urllib.request.urlopen(urllib.request.Request(artifact_url, headers=headers), timeout=args.timeout) as response:
                    while chunk := response.read(1024 * 1024):
                        size += len(chunk)
                record["download_seconds"] = round(time.monotonic() - download_started, 4)
                record["annotated_video_bytes"] = size
                active = [s for s in samples if started <= s["monotonic"] <= completed]
                if active:
                    record["cpu_percent_mean"] = round(statistics.mean(s["cpu_percent"] for s in active), 2)
                    record["cpu_percent_peak"] = max(s["cpu_percent"] for s in active)
                    peak = max(active, key=lambda s: s["memory_percent"])
                    record["memory_usage_at_peak"] = peak["memory_usage"]
                results.append(record)
                print(json.dumps(record, ensure_ascii=False), flush=True)
                write_report(args.output, results, samples)
    finally:
        if sampler:
            sampler.terminate()
            try:
                sampler.wait(timeout=5)
            except subprocess.TimeoutExpired:
                sampler.kill()
                sampler.wait()
            thread.join(timeout=5)
        write_report(args.output, results, samples)


def write_report(path, results, samples):
    summary = []
    for name in dict.fromkeys(r["video"] for r in results):
        group = [r for r in results if r["video"] == name]
        summary.append({"video": name, "requests": len(group),
                        "request_seconds_median": statistics.median(r["request_seconds"] for r in group),
                        "request_seconds_max": max(r["request_seconds"] for r in group),
                        "effective_fps_median": statistics.median(r["effective_fps"] for r in group)})
    path.write_text(json.dumps({
        "metric_definition": "Request time includes upload, process/model startup, decoding, detection/tracking, rules, video rendering, and JSON response. Video download is separate. Docker CPU 100% equals one logical CPU. Small-sample summaries are medians/maxima, not tail-latency estimates.",
        "results": results, "summary": summary, "resource_samples": samples,
    }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
