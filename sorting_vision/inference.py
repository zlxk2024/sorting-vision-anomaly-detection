from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_WEIGHTS = PROJECT_ROOT / "models/sorting_yolo11n_v2_mixed_best.pt"
ARTIFACTS = {
    "events": "events_v1.json",
    "events_csv": "events_v1.csv",
    "detections": "detections_v1.json",
    "video": "sorting_events_v1.mp4",
}


def verify_models(root: Path = PROJECT_ROOT) -> list[dict]:
    manifest = json.loads((root / "models/manifest.json").read_text(encoding="utf-8"))
    for item in manifest["artifacts"]:
        path = root / "models" / item["filename"]
        if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != item["sha256"]:
            raise ValueError(f"Invalid or missing model: {item['filename']}. Run git lfs pull.")
    return manifest["artifacts"]


def run_video(
    video: Path,
    output: Path,
    weights: Path = DEFAULT_WEIGHTS,
    device: str = "cpu",
    image_size: int = 320,
    confidence: float = 0.15,
    timeout: float = 1800,
) -> dict:
    """Run the existing detection/tracking/rules pipeline in an isolated process.

    Each call has its own process and output directory, so the legacy script's
    module-level FPS and paths cannot leak across requests.
    """
    video, output, weights = video.resolve(), output.resolve(), weights.resolve()
    if not video.is_file() or not weights.is_file():
        raise ValueError("Video or model file does not exist")
    output.mkdir(parents=True, exist_ok=True)
    command = [
        sys.executable, str(PROJECT_ROOT / "scripts/detect_sorting_events_v1.py"),
        "--video", str(video), "--output", str(output), "--weights", str(weights),
        "--device", device, "--imgsz", str(image_size), "--conf", str(confidence),
    ]
    with (output / "inference.log").open("w", encoding="utf-8") as log:
        result = subprocess.run(command, stdout=log, stderr=subprocess.STDOUT, timeout=timeout, check=False)
    if result.returncode:
        raise RuntimeError("Video inference failed; inspect the server-side inference.log")
    if any(not (output / name).is_file() for name in ARTIFACTS.values()):
        raise RuntimeError("Inference did not produce all required artifacts")
    events = json.loads((output / ARTIFACTS["events"]).read_text(encoding="utf-8"))
    detections = json.loads((output / ARTIFACTS["detections"]).read_text(encoding="utf-8"))
    return {
        "status": "completed", "model_version": "YOLO11n-V2", "rule_version": "v1",
        "frame_count": len(detections), "event_count": len(events), "events": events,
    }
