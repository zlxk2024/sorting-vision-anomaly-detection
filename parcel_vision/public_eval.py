from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

import numpy as np

from .io import load_point_cloud
from .pipeline import ParcelVisionConfig, ParcelVisionPipeline


def evaluate_public_cloud(path: str | Path, unit_scale: float = 0.0) -> dict:
    source = Path(path)
    points = load_point_cloud(source)
    raw_count = len(points)
    finite_mask = np.isfinite(points).all(axis=1)
    points = points[finite_mask]
    if unit_scale <= 0:
        typical_range = float(np.median(np.linalg.norm(points, axis=1)))
        unit_scale = 1000.0 if typical_range < 50.0 else 1.0
    points = points * unit_scale

    # Bound extreme scanner outliers before rasterisation. The percentiles retain
    # the scene while preventing a single corrupt coordinate from making a huge grid.
    lower = np.percentile(points, 0.1, axis=0)
    upper = np.percentile(points, 99.9, axis=0)
    bounded = points[((points >= lower) & (points <= upper)).all(axis=1)]
    pipeline = ParcelVisionPipeline(
        ParcelVisionConfig(
            grid_size=8.0,
            min_height=12.0,
            max_height=600.0,
            min_area=1_000.0,
            plane_distance_threshold=6.0,
            plane_ransac_iterations=180,
            morphology_radius=1,
        )
    )
    started = time.perf_counter()
    frame = pipeline.fit_conveyor_plane(bounded)
    detections = pipeline.process(bounded)
    runtime_ms = (time.perf_counter() - started) * 1000.0
    signed_distance = (bounded - frame.origin) @ frame.normal
    inlier_distance = np.abs(signed_distance[frame.inlier_mask])
    return {
        "suite": "public_real_point_cloud_smoke_test",
        "source": str(source),
        "raw_points": raw_count,
        "finite_points": int(finite_mask.sum()),
        "bounded_points": len(bounded),
        "unit_scale_to_mm": unit_scale,
        "axis_bounds_mm": {"min": bounded.min(axis=0).tolist(), "max": bounded.max(axis=0).tolist()},
        "plane_inlier_ratio": float(frame.inlier_mask.mean()),
        "plane_residual_mm": {
            "median": float(np.median(inlier_distance)),
            "p95": float(np.percentile(inlier_distance, 95)),
        },
        "detected_clusters": len(detections),
        "runtime_ms": runtime_ms,
        "detections": [item.protocol_item("offline_eval")["location"] for item in detections],
        "accuracy_available": False,
        "accuracy_note": "This public scene has no parcel instance ground truth; cluster output is a robustness smoke test, not parcel accuracy.",
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate a public real point cloud")
    parser.add_argument("point_cloud")
    parser.add_argument("--unit-scale", type=float, default=0.0, help="multiply input coordinates by this value; 0 auto-detects")
    parser.add_argument("--output", default="reports/public_real_report.json")
    args = parser.parse_args()
    report = evaluate_public_cloud(args.point_cloud, args.unit_scale)
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
