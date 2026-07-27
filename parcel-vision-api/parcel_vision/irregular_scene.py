from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from scipy.optimize import linear_sum_assignment

from .generate_scene import evaluate_scene, scene_ground_truth, write_xyz_ply
from .grasp_plan import build_grasp_plan
from .io import build_protocol_response
from .pipeline import ParcelVisionConfig, ParcelVisionPipeline
from .stacked_scene import metric_summary, rotation_x, rotation_y, save_three_way_comparison, save_truth_cloud
from .stress import ExpectedParcel, StressScene
from .visualize import assign_detection_labels, create_visualizations


@dataclass
class IrregularParcel:
    kind: str
    center: tuple[float, float]
    length: float
    width: float
    height: float
    yaw: float
    base_height: float = 0.0


def generate_irregular_scene(seed: int, output_dir: Path) -> dict:
    output_dir.mkdir(parents=True, exist_ok=True)
    scene, truth_labels = make_irregular_scene(np.random.default_rng(seed))
    np.save(output_dir / "irregular_parcels.npy", scene.points)
    write_xyz_ply(output_dir / "irregular_parcels.ply", scene.points)
    save_truth_cloud(output_dir / "ground_truth_colored_cloudcompare.ply", scene.points, truth_labels)

    config = ParcelVisionConfig(
        grid_size=5.0,
        min_height=10.0,
        min_area=1_800.0,
        plane_distance_threshold=5.0,
        plane_ransac_iterations=180,
        morphology_radius=1,
        max_local_roughness=16.0,
        segmentation_method="height_edges",
        height_edge_threshold=12.0,
        min_detection_score=0.68,
    )
    pipeline = ParcelVisionPipeline(config)
    frame = pipeline.fit_conveyor_plane(scene.points)
    detections = pipeline.process(scene.points)
    prediction_labels = assign_detection_labels(
        frame.to_local(scene.points), detections, frame, config
    )
    create_visualizations(scene.points, detections, frame, config, output_dir)
    save_three_way_comparison(
        output_dir / "raw_truth_prediction_comparison.png",
        scene.points,
        truth_labels,
        prediction_labels,
        scene.expected,
        detections,
        frame,
        "Irregular parcel prediction",
        "Ground truth: 12 irregular parcels",
    )
    save_depth_style_view(
        output_dir / "overhead_depth_style.png", scene.points, frame
    )

    truth = scene_ground_truth(scene, seed)
    (output_dir / "ground_truth.json").write_text(
        json.dumps(truth, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    prediction = build_protocol_response(detections, f"irregular-{seed}", 0, "arm1")
    (output_dir / "prediction.json").write_text(
        json.dumps(prediction, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    grasp_plan = build_grasp_plan(detections, frame)
    (output_dir / "grasp_plan.json").write_text(
        json.dumps(grasp_plan, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    report = evaluate_scene(scene, detections)
    report.update(
        {
            "seed": seed,
            "input_points": len(scene.points),
            "expected_types": [parcel.kind for parcel in scene.expected],
            "eligible_grasp_candidates": grasp_plan["eligible_count"],
            "recommended_object_id": grasp_plan["recommended_object_id"],
            "matched_visible_surface_error_mm": matched_visible_surface_error(
                scene, truth_labels, detections
            ),
            "files": {
                "raw_ply": "irregular_parcels.ply",
                "raw_npy": "irregular_parcels.npy",
                "depth_style": "overhead_depth_style.png",
                "comparison": "raw_truth_prediction_comparison.png",
                "prediction_colored_ply": "prediction_colored_cloudcompare.ply",
                "truth_colored_ply": "ground_truth_colored_cloudcompare.ply",
                "prediction": "prediction.json",
                "grasp_plan": "grasp_plan.json",
            },
            "notice": "Synthetic irregular RGB-D geometry, not an on-site camera capture.",
        }
    )
    (output_dir / "evaluation.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return report


def make_irregular_scene(
    rng: np.random.Generator,
) -> tuple[StressScene, np.ndarray]:
    specs = irregular_layout()
    belt_length, belt_width, spacing = 1900.0, 1250.0, 6.0
    x, y = np.meshgrid(
        np.arange(-belt_length / 2, belt_length / 2 + 1, spacing),
        np.arange(-belt_width / 2, belt_width / 2 + 1, spacing),
    )
    xy = np.column_stack((x.ravel(), y.ravel()))
    heights = np.zeros(len(xy))
    labels = np.zeros(len(xy), dtype=np.int32)
    for instance_id, spec in enumerate(specs, start=1):
        u, v = local_coordinates(xy, spec)
        top, inside = irregular_height(u, v, spec)
        candidate = spec.base_height + top
        visible = inside & (candidate > heights)
        heights[visible] = candidate[visible]
        labels[visible] = instance_id

    dropout = np.full(len(xy), 0.02)
    for instance_id, spec in enumerate(specs, start=1):
        dropout[labels == instance_id] = 0.12 if "bag" in spec.kind else 0.055
    keep = rng.random(len(xy)) > dropout
    # Reflective labels and dark plastic create contiguous missing-depth patches.
    holes = (
        (((xy[:, 0] + 235) / 48) ** 2 + ((xy[:, 1] - 315) / 38) ** 2 < 1)
        | (((xy[:, 0] - 610) / 52) ** 2 + ((xy[:, 1] + 125) / 44) ** 2 < 1)
    )
    keep &= ~holes
    xy, heights, labels = xy[keep], heights[keep], labels[keep]

    roll, pitch, noise_sigma = 0.8, -2.1, 1.4
    local_to_camera = rotation_y(np.radians(pitch)) @ rotation_x(np.radians(roll)) @ np.diag([1, 1, -1])
    translation = np.array([12.0, -8.0, 1120.0])
    local_points = np.column_stack((xy, heights))
    points = translation + local_points @ local_to_camera.T
    points += rng.normal(0.0, noise_sigma, points.shape)
    points = np.round(points * 2.0) / 2.0
    outlier_count = 110
    outliers_local = np.column_stack(
        (
            rng.uniform(-belt_length / 2, belt_length / 2, outlier_count),
            rng.uniform(-belt_width / 2, belt_width / 2, outlier_count),
            rng.uniform(-30, 260, outlier_count),
        )
    )
    points = np.vstack((points, translation + outliers_local @ local_to_camera.T))
    labels = np.append(labels, np.zeros(outlier_count, dtype=np.int32))

    expected = []
    for spec in specs:
        angle = np.radians(spec.yaw)
        expected.append(
            ExpectedParcel(
                center_camera=translation + local_to_camera @ np.array([*spec.center, spec.base_height + spec.height / 2]),
                top_camera=translation + local_to_camera @ np.array([*spec.center, spec.base_height + spec.height]),
                major_axis_camera=local_to_camera @ np.array([np.cos(angle), np.sin(angle), 0]),
                length=spec.length,
                width=spec.width,
                height=spec.height,
                kind=spec.kind,
            )
        )
    return StressScene(points, expected, noise_sigma, float(dropout.mean()), (roll, pitch), outlier_count), labels


def irregular_layout() -> list[IrregularParcel]:
    return [
        IrregularParcel("large_crumpled_bag", (-680, 340), 300, 245, 78, -9),
        IrregularParcel("trapezoid_box", (-265, 340), 390, 260, 145, 13),
        IrregularParcel("long_narrow_parcel", (260, 355), 430, 130, 62, -6),
        IrregularParcel("rounded_soft_bag", (690, 315), 265, 225, 95, 17),
        IrregularParcel("damaged_corner_box", (-650, -80), 315, 215, 112, -12),
        IrregularParcel("padded_mailer", (-205, -70), 350, 220, 48, 15),
        IrregularParcel("tube", (260, -80), 345, 125, 108, -21),
        IrregularParcel("l_shape_package", (675, -105), 330, 245, 82, 7),
        IrregularParcel("large_poly_bag", (-300, -405), 410, 255, 72, -7),
        IrregularParcel("small_box", (75, -380), 185, 145, 125, 24, 72),
        IrregularParcel("tiny_flat_packet", (70, 165), 88, 58, 26, 19),
        IrregularParcel("tiny_soft_piece", (455, -335), 76, 52, 34, -28),
    ]


def local_coordinates(xy: np.ndarray, spec: IrregularParcel) -> tuple[np.ndarray, np.ndarray]:
    angle = np.radians(spec.yaw)
    c, s = np.cos(angle), np.sin(angle)
    relative = xy - np.asarray(spec.center)
    return relative[:, 0] * c + relative[:, 1] * s, -relative[:, 0] * s + relative[:, 1] * c


def irregular_height(u: np.ndarray, v: np.ndarray, spec: IrregularParcel) -> tuple[np.ndarray, np.ndarray]:
    length, width, height = spec.length, spec.width, spec.height
    ellipse = (u / (length / 2)) ** 2 + (v / (width / 2)) ** 2
    rectangle = (np.abs(u) <= length / 2) & (np.abs(v) <= width / 2)
    if spec.kind == "large_crumpled_bag":
        inside = ellipse <= 1 + 0.1 * np.sin(u / 18) + 0.06 * np.sin(v / 13)
        top = height * (0.55 + 0.43 * np.clip(1 - ellipse, 0, 1))
        top += 5 * np.sin(u / 16) * np.cos(v / 12)
    elif spec.kind == "trapezoid_box":
        half_width = width * (0.36 + 0.14 * (u / length + 0.5))
        inside = (np.abs(u) <= length / 2) & (np.abs(v) <= half_width)
        top = np.full(len(u), height)
    elif spec.kind == "long_narrow_parcel":
        inside = rectangle & ~((u < -length * 0.38) & (v > width * 0.25))
        top = height * (0.92 + 0.06 * np.cos(u / 35))
    elif spec.kind == "rounded_soft_bag":
        inside = ellipse <= 1 + 0.08 * np.cos(u / 15)
        top = height * (0.52 + 0.46 * np.clip(1 - ellipse, 0, 1))
        top += 3 * np.sin(v / 11)
    elif spec.kind == "damaged_corner_box":
        damaged_corner = (u > length * 0.22) & (v > width * 0.12) & (u + v > (length + width) * 0.28)
        inside = rectangle & ~damaged_corner
        top = np.full(len(u), height)
    elif spec.kind == "padded_mailer":
        inside = rectangle & (ellipse <= 1.42)
        top = height * (0.8 + 0.18 * np.clip(1 - ellipse, 0, 1)) + 2 * np.sin(u / 14)
    elif spec.kind == "tube":
        inside = rectangle
        top = np.maximum(8, height * np.sqrt(np.clip(1 - (v / (width / 2)) ** 2, 0, 1)))
    elif spec.kind == "l_shape_package":
        inside = rectangle & ~((u > -length * 0.05) & (v > -width * 0.05))
        top = np.full(len(u), height)
    elif spec.kind == "large_poly_bag":
        inside = ellipse <= 1 + 0.09 * np.sin(u / 20) * np.cos(v / 14)
        top = height * (0.58 + 0.38 * np.clip(1 - ellipse, 0, 1)) + 3 * np.sin(u / 17)
    elif spec.kind == "small_box":
        inside = rectangle
        top = np.full(len(u), height)
    elif spec.kind == "tiny_flat_packet":
        inside = rectangle & ~((u > length * 0.28) & (v > width * 0.18))
        top = np.full(len(u), height) + 1.2 * np.sin(u / 8)
    elif spec.kind == "tiny_soft_piece":
        inside = ellipse <= 1 + 0.08 * np.sin(u / 6)
        top = height * (0.62 + 0.35 * np.clip(1 - ellipse, 0, 1))
    else:
        raise ValueError(spec.kind)
    return top, inside


def save_depth_style_view(path: Path, points: np.ndarray, frame) -> None:
    local = frame.to_local(points)
    objects = local[:, 2] >= 10
    figure, axis = plt.subplots(figsize=(7, 10), facecolor="#05080d")
    axis.set_facecolor("#05080d")
    axis.scatter(
        local[objects, 0], local[objects, 1], c=local[objects, 2],
        cmap="turbo", s=2.2, linewidths=0,
    )
    axis.set_aspect("equal", adjustable="box")
    axis.set_xlim(-950, 950)
    axis.set_ylim(-625, 625)
    axis.axis("off")
    figure.savefig(path, dpi=200, bbox_inches="tight", pad_inches=0, facecolor=figure.get_facecolor())
    plt.close(figure)


def matched_visible_surface_error(
    scene: StressScene, truth_labels: np.ndarray, detections: list
) -> dict:
    errors = []
    if detections and scene.expected:
        distances = np.array(
            [
                [np.linalg.norm(detection.grasp_camera - truth.top_camera) for truth in scene.expected]
                for detection in detections
            ]
        )
        rows, columns = linear_sum_assignment(distances)
        for row, column in zip(rows, columns):
            visible_points = scene.points[truth_labels == column + 1]
            if len(visible_points):
                errors.append(
                    float(
                        np.min(
                            np.linalg.norm(
                                visible_points - detections[row].grasp_camera, axis=1
                            )
                        )
                    )
                )
    return metric_summary(errors)


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate irregular parcel depth point clouds")
    parser.add_argument("--seed", type=int, default=20260719)
    parser.add_argument("--output", type=Path, default=Path("reports/generated_irregular_parcels"))
    args = parser.parse_args()
    print(json.dumps(generate_irregular_scene(args.seed, args.output), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
