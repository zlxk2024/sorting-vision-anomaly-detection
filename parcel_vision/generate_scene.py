from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

import numpy as np
from scipy.optimize import linear_sum_assignment

from .io import build_protocol_response
from .pipeline import ParcelVisionConfig, ParcelVisionPipeline
from .stress import ExpectedParcel, StressScene
from .visualize import create_visualizations


def generate_scene(seed: int, output_dir: Path, count: int = 10) -> dict:
    output_dir.mkdir(parents=True, exist_ok=True)
    scene = make_mixed_scene(np.random.default_rng(seed), count)
    np.save(output_dir / "realistic_parcel_scene.npy", scene.points)
    write_xyz_ply(output_dir / "realistic_parcel_scene.ply", scene.points)

    config = ParcelVisionConfig(
        grid_size=5.0,
        plane_distance_threshold=5.0,
        plane_ransac_iterations=140,
        morphology_radius=1,
        max_local_roughness=12.0,
    )
    pipeline = ParcelVisionPipeline(config)
    frame = pipeline.fit_conveyor_plane(scene.points)
    started = time.perf_counter()
    detections = pipeline.process(scene.points)
    runtime_ms = (time.perf_counter() - started) * 1000.0
    visuals = create_visualizations(scene.points, detections, frame, config, output_dir)

    truth = scene_ground_truth(scene, seed)
    (output_dir / "ground_truth.json").write_text(
        json.dumps(truth, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    prediction = build_protocol_response(detections, f"simulation-{seed}", 0, "arm1")
    (output_dir / "prediction.json").write_text(
        json.dumps(prediction, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    report = evaluate_scene(scene, detections)
    report.update(
        {
            "seed": seed,
            "input_points": len(scene.points),
            "runtime_ms": runtime_ms,
            "files": {
                "raw_ply": "realistic_parcel_scene.ply",
                "raw_npy": "realistic_parcel_scene.npy",
                "ground_truth": "ground_truth.json",
                "prediction": "prediction.json",
                **{key: path.name for key, path in visuals.items()},
            },
            "notice": "High-fidelity synthetic sensor data, not an on-site camera capture.",
        }
    )
    (output_dir / "evaluation.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return report


def make_mixed_scene(rng: np.random.Generator, count: int) -> StressScene:
    if not 1 <= count <= 12:
        raise ValueError("count must be between 1 and 12")

    belt_length, belt_width = 1900.0, 1250.0
    roll, pitch = float(rng.uniform(-2.5, 2.5)), float(rng.uniform(-3.5, 3.5))
    rotation = rotation_y(np.radians(pitch)) @ rotation_x(np.radians(roll))
    local_to_camera = rotation @ np.diag([1.0, 1.0, -1.0])
    translation = np.array([rng.uniform(-25, 25), rng.uniform(-25, 25), rng.uniform(1050, 1200)])
    noise_sigma = float(rng.uniform(0.8, 2.0))
    dropout = float(rng.uniform(0.04, 0.14))

    bx, by = np.meshgrid(
        np.arange(-belt_length / 2, belt_length / 2 + 1, 18.0),
        np.arange(-belt_width / 2, belt_width / 2 + 1, 18.0),
    )
    belt = np.column_stack((bx.ravel(), by.ravel(), np.zeros(bx.size)))
    belt = belt[rng.random(len(belt)) > dropout * 0.3]

    kinds = ["cardboard_box", "soft_bag", "padded_mailer", "tube"]
    cells = [
        (x, y)
        for y in (-420.0, 0.0, 420.0)
        for x in (-720.0, -240.0, 240.0, 720.0)
    ]
    rng.shuffle(cells)
    local_clouds = [belt]
    expected: list[ExpectedParcel] = []
    for index, (base_x, base_y) in enumerate(cells[:count]):
        kind = kinds[index % len(kinds)]
        length = float(rng.uniform(210, 330))
        width = float(rng.uniform(115, 210))
        if kind == "soft_bag":
            width = float(rng.uniform(150, 225))
            height = float(rng.uniform(55, 115))
        elif kind == "padded_mailer":
            height = float(rng.uniform(25, 55))
        elif kind == "tube":
            width = float(rng.uniform(95, 145))
            height = width * float(rng.uniform(0.72, 0.95))
        else:
            height = float(rng.uniform(70, 190))
        center = np.array([base_x + rng.uniform(-35, 35), base_y + rng.uniform(-30, 30)])
        yaw = float(rng.uniform(-28, 28))
        surface = mixed_parcel_surface(rng, center, length, width, height, yaw, kind, dropout)
        local_clouds.append(surface)

        angle = np.radians(yaw)
        major_local = np.array([np.cos(angle), np.sin(angle), 0.0])
        top_height = height if kind == "cardboard_box" else float(surface[:, 2].max())
        expected.append(
            ExpectedParcel(
                center_camera=translation + local_to_camera @ np.array([*center, height / 2]),
                top_camera=translation + local_to_camera @ np.array([*center, top_height]),
                major_axis_camera=local_to_camera @ major_local,
                length=length,
                width=width,
                height=height,
                kind=kind,
            )
        )

    local_points = np.vstack(local_clouds)
    points = translation + local_points @ local_to_camera.T
    points += rng.normal(0.0, noise_sigma, points.shape)
    points = np.round(points * 2.0) / 2.0
    outlier_count = int(rng.integers(80, 220))
    outliers_local = np.column_stack(
        (
            rng.uniform(-belt_length / 2, belt_length / 2, outlier_count),
            rng.uniform(-belt_width / 2, belt_width / 2, outlier_count),
            rng.uniform(-50, 360, outlier_count),
        )
    )
    points = np.vstack((points, translation + outliers_local @ local_to_camera.T))
    return StressScene(points, expected, noise_sigma, dropout, (roll, pitch), outlier_count)


def mixed_parcel_surface(
    rng: np.random.Generator,
    center: np.ndarray,
    length: float,
    width: float,
    height: float,
    yaw: float,
    kind: str,
    dropout: float,
) -> np.ndarray:
    xs, ys = np.meshgrid(
        np.arange(-length / 2, length / 2 + 1, 7.0),
        np.arange(-width / 2, width / 2 + 1, 7.0),
    )
    u, v = xs.ravel(), ys.ravel()
    normalized = (u / (length / 2)) ** 2 + (v / (width / 2)) ** 2
    if kind == "cardboard_box":
        z = np.full_like(u, height)
        shape = np.ones(len(u), dtype=bool)
    elif kind == "soft_bag":
        shape = normalized <= 1.0 + 0.05 * np.sin(u / 17.0)
        z = height * (0.55 + 0.43 * np.clip(1.0 - normalized, 0, 1))
        z += 4.0 * np.sin(u / 18.0) * np.cos(v / 15.0)
    elif kind == "padded_mailer":
        corner = 24.0
        shape = (np.abs(u) <= length / 2 - corner) | (np.abs(v) <= width / 2 - corner)
        shape |= ((np.abs(u) - (length / 2 - corner)) ** 2 + (np.abs(v) - (width / 2 - corner)) ** 2) <= corner**2
        z = height * (0.78 + 0.2 * np.clip(1.0 - normalized, 0, 1))
        z += 1.8 * np.sin(u / 14.0)
    elif kind == "tube":
        shape = np.abs(v) <= width / 2
        z = height * np.sqrt(np.clip(1.0 - (v / (width / 2)) ** 2, 0, 1))
        z = np.maximum(z, 8.0)
    else:
        raise ValueError(f"Unknown parcel kind: {kind}")

    keep = shape & (rng.random(len(u)) > dropout)
    hole_u, hole_v = rng.uniform(-length * 0.2, length * 0.2), rng.uniform(-width * 0.2, width * 0.2)
    hole = ((u - hole_u) / (length * 0.09)) ** 2 + ((v - hole_v) / (width * 0.11)) ** 2 < 1
    keep &= ~hole
    angle = np.radians(yaw)
    planar_rotation = np.array([[np.cos(angle), -np.sin(angle)], [np.sin(angle), np.cos(angle)]])
    xy = np.column_stack((u, v)) @ planar_rotation.T + center
    return np.column_stack((xy, z))[keep]


def rotation_x(angle: float) -> np.ndarray:
    c, s = np.cos(angle), np.sin(angle)
    return np.array([[1, 0, 0], [0, c, -s], [0, s, c]])


def rotation_y(angle: float) -> np.ndarray:
    c, s = np.cos(angle), np.sin(angle)
    return np.array([[c, 0, s], [0, 1, 0], [-s, 0, c]])


def scene_ground_truth(scene: StressScene, seed: int) -> dict:
    parcels = []
    for index, parcel in enumerate(scene.expected, start=1):
        parcels.append(
            {
                "id": f"truth_{index:04d}",
                "kind": parcel.kind,
                "center_camera_mm": parcel.center_camera.tolist(),
                "top_camera_mm": parcel.top_camera.tolist(),
                "major_axis_camera": parcel.major_axis_camera.tolist(),
                "length_mm": parcel.length,
                "width_mm": parcel.width,
                "height_mm": parcel.height,
            }
        )
    return {
        "seed": seed,
        "sensor_effects": {
            "noise_sigma_mm": scene.noise_sigma,
            "dropout_ratio": scene.dropout,
            "belt_tilt_degrees": list(scene.tilt_degrees),
            "outlier_count": scene.outlier_count,
        },
        "parcels": parcels,
    }


def evaluate_scene(scene: StressScene, detections: list) -> dict:
    matches = []
    if detections and scene.expected:
        distances = np.array(
            [
                [np.linalg.norm(det.grasp_camera - expected.top_camera) for expected in scene.expected]
                for det in detections
            ]
        )
        rows, cols = linear_sum_assignment(distances)
        for row, col in zip(rows, cols):
            detection = detections[row]
            expected = scene.expected[col]
            detected_axis = detection.rotation_camera[:, 0]
            detected_axis /= np.linalg.norm(detected_axis)
            expected_axis = expected.major_axis_camera / np.linalg.norm(expected.major_axis_camera)
            angle = np.degrees(np.arccos(np.clip(abs(np.dot(detected_axis, expected_axis)), 0, 1)))
            matches.append(
                {
                    "prediction_id": detection.object_id,
                    "truth_id": f"truth_{col + 1:04d}",
                    "kind": expected.kind,
                    "grasp_error_mm": float(distances[row, col]),
                    "length_error_mm": abs(detection.length - expected.length),
                    "width_error_mm": abs(detection.width - expected.width),
                    "height_error_mm": abs(detection.height - expected.height),
                    "orientation_error_degrees": float(angle),
                }
            )
    return {
        "expected_parcels": len(scene.expected),
        "detected_parcels": len(detections),
        "matched_parcels": len(matches),
        "mean_grasp_error_mm": mean_metric(matches, "grasp_error_mm"),
        "mean_orientation_error_degrees": mean_metric(matches, "orientation_error_degrees"),
        "matches": matches,
    }


def mean_metric(rows: list[dict], key: str) -> float:
    return float(np.mean([row[key] for row in rows])) if rows else 0.0


def write_xyz_ply(path: Path, points: np.ndarray) -> None:
    header = (
        "ply\nformat ascii 1.0\n"
        f"element vertex {len(points)}\n"
        "property float x\nproperty float y\nproperty float z\nend_header\n"
    )
    with path.open("w", encoding="ascii") as handle:
        handle.write(header)
        np.savetxt(handle, points, fmt="%.4f %.4f %.4f")


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate a realistic synthetic parcel point-cloud scene")
    parser.add_argument("--seed", type=int, default=20260717)
    parser.add_argument("--count", type=int, default=10)
    parser.add_argument("--output", type=Path, default=Path("reports/generated_realistic_scene"))
    args = parser.parse_args()
    report = generate_scene(args.seed, args.output, args.count)
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
