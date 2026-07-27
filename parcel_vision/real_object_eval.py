from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

import numpy as np
from scipy.optimize import linear_sum_assignment

from .io import load_point_cloud
from .pipeline import ParcelVisionConfig, ParcelVisionPipeline


def build_real_object_composite(files: list[Path]) -> tuple[np.ndarray, list[dict]]:
    placements = [(-330.0, -180.0, 0.0), (260.0, -130.0, 27.0), (20.0, 240.0, -22.0)]
    belt_x, belt_y = np.meshgrid(
        np.arange(-700.0, 701.0, 15.0), np.arange(-470.0, 471.0, 15.0)
    )
    clouds = [np.column_stack((belt_x.ravel(), belt_y.ravel(), np.full(belt_x.size, 1000.0)))]
    expected: list[dict] = []

    for file, (center_x, center_y, yaw) in zip(files, placements):
        raw = load_point_cloud(file) * 1000.0
        raw = raw[np.isfinite(raw).all(axis=1)]
        center = np.median(raw, axis=0)
        _, _, vh = np.linalg.svd(raw - center, full_matrices=False)
        principal = (raw - center) @ vh.T
        low, high = np.percentile(principal, [1.0, 99.0], axis=0)
        keep = ((principal >= low) & (principal <= high)).all(axis=1)
        principal = principal[keep]
        extents = np.percentile(principal, 99, axis=0) - np.percentile(principal, 1, axis=0)
        order = np.argsort(extents)[::-1]
        local = principal[:, order]
        local -= np.median(local, axis=0)
        # Lay the package on its largest face: two largest dimensions form the
        # footprint and the smallest dimension is the height.
        local[:, 2] -= np.percentile(local[:, 2], 1)
        dimensions = np.percentile(local, 99, axis=0) - np.percentile(local, 1, axis=0)
        angle = np.radians(yaw)
        planar_rotation = np.array([[np.cos(angle), -np.sin(angle)], [np.sin(angle), np.cos(angle)]])
        local[:, :2] = local[:, :2] @ planar_rotation.T + [center_x, center_y]
        local[:, 2] = np.clip(local[:, 2], 0.0, dimensions[2])
        camera_points = np.column_stack((local[:, 0], local[:, 1], 1000.0 - local[:, 2]))
        clouds.append(camera_points)
        expected.append(
            {
                "source": file.name,
                "center_xy": [center_x, center_y],
                "length": float(max(dimensions[0], dimensions[1])),
                "width": float(min(dimensions[0], dimensions[1])),
                "height": float(dimensions[2]),
                "yaw": yaw,
            }
        )
    return np.vstack(clouds), expected


def evaluate(files: list[Path], output_dir: Path) -> dict:
    points, expected = build_real_object_composite(files)
    output_dir.mkdir(parents=True, exist_ok=True)
    np.save(output_dir / "real_cereal_box_composite.npy", points)
    _write_ascii_ply(output_dir / "real_cereal_box_composite.ply", points)

    pipeline = ParcelVisionPipeline(
        ParcelVisionConfig(
            grid_size=5.0,
            min_height=8.0,
            max_height=500.0,
            min_area=2_000.0,
            plane_distance_threshold=3.0,
            plane_ransac_iterations=180,
            # Real single-view RGB-D surfaces have broad self-occlusion gaps.
            # At a 5 mm grid, radius 8 uses an 85 mm-wide closing structure.
            morphology_radius=8,
        )
    )
    started = time.perf_counter()
    detections = pipeline.process(points)
    runtime_ms = (time.perf_counter() - started) * 1000.0

    center_errors: list[float] = []
    grasp_errors: list[float] = []
    length_errors: list[float] = []
    width_errors: list[float] = []
    height_errors: list[float] = []
    matches: list[dict] = []
    if detections:
        distances = np.array(
            [
                [np.linalg.norm(det.center_camera[:2] - exp["center_xy"]) for exp in expected]
                for det in detections
            ]
        )
        rows, cols = linear_sum_assignment(distances)
        for row, col in zip(rows, cols):
            det, exp = detections[row], expected[col]
            center_error = float(distances[row, col])
            grasp_error = float(np.linalg.norm(det.grasp_camera[:2] - exp["center_xy"]))
            center_errors.append(center_error)
            grasp_errors.append(grasp_error)
            length_errors.append(abs(det.length - exp["length"]))
            width_errors.append(abs(det.width - exp["width"]))
            height_errors.append(abs(det.height - exp["height"]))
            matches.append(
                {
                    "source": exp["source"],
                    "expected": exp,
                    "detected": det.protocol_item("offline_eval")["location"],
                    "center_xy_error_mm": center_error,
                    "grasp_xy_error_mm": grasp_error,
                }
            )

    report = {
        "suite": "real_rgbd_object_cloud_synthetic_conveyor_layout",
        "source_dataset": "UW RGB-D Object Dataset cereal_box_1",
        "source_frames": [file.name for file in files],
        "input_points": len(points),
        "expected_parcels": len(expected),
        "detected_parcels": len(detections),
        "runtime_ms": runtime_ms,
        "center_xy_error_mm": _stats(center_errors),
        "grasp_xy_error_mm": _stats(grasp_errors),
        "length_error_mm": _stats(length_errors),
        "width_error_mm": _stats(width_errors),
        "height_error_mm": _stats(height_errors),
        "matches": matches,
        "limitations": [
            "Object surfaces are real RGB-D captures, but the conveyor plane and object placement are synthetic.",
            "The source files contain pre-segmented single objects, not a complete cluttered conveyor frame.",
        ],
    }
    (output_dir / "real_object_composite_report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return report


def _stats(values: list[float]) -> dict:
    if not values:
        return {"count": 0, "mean": 0.0, "max": 0.0}
    array = np.asarray(values)
    return {"count": len(values), "mean": float(array.mean()), "max": float(array.max())}


def _write_ascii_ply(path: Path, points: np.ndarray) -> None:
    header = (
        "ply\nformat ascii 1.0\n"
        f"element vertex {len(points)}\n"
        "property float x\nproperty float y\nproperty float z\nend_header\n"
    )
    with path.open("w", encoding="ascii") as handle:
        handle.write(header)
        np.savetxt(handle, points, fmt="%.4f %.4f %.4f")


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate real RGB-D cereal-box clouds on a synthetic conveyor")
    parser.add_argument("files", nargs="+", type=Path)
    parser.add_argument("--output", type=Path, default=Path("reports/real_object_composite"))
    args = parser.parse_args()
    print(json.dumps(evaluate(args.files, args.output), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
