from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from .generate_scene import evaluate_scene, scene_ground_truth, write_xyz_ply
from .grasp_plan import build_grasp_plan
from .io import build_protocol_response
from .pipeline import ParcelVisionConfig, ParcelVisionPipeline
from .stress import ExpectedParcel, StressScene
from .visualize import (
    PALETTE,
    assign_detection_labels,
    create_visualizations,
    draw_annotations_2d,
    draw_labeled_points,
    write_rgb_ply,
)


@dataclass
class StackedParcel:
    truth_id: int
    kind: str
    center: tuple[float, float]
    length: float
    width: float
    height: float
    yaw: float
    base_height: float


def generate_stacked_scene(seed: int, output_dir: Path) -> dict:
    output_dir.mkdir(parents=True, exist_ok=True)
    scene, truth_labels, visible_counts = make_stacked_scene(np.random.default_rng(seed))
    np.save(output_dir / "stacked_10_parcels.npy", scene.points)
    write_xyz_ply(output_dir / "stacked_10_parcels.ply", scene.points)

    baseline_config = ParcelVisionConfig(
        grid_size=5.0,
        min_height=10.0,
        min_area=2_500.0,
        plane_distance_threshold=5.0,
        plane_ransac_iterations=180,
        morphology_radius=1,
        max_local_roughness=15.0,
    )
    baseline_pipeline = ParcelVisionPipeline(baseline_config)
    baseline_detections = baseline_pipeline.process(scene.points)
    config = ParcelVisionConfig(
        grid_size=5.0,
        min_height=10.0,
        min_area=2_500.0,
        plane_distance_threshold=5.0,
        plane_ransac_iterations=180,
        morphology_radius=1,
        max_local_roughness=15.0,
        segmentation_method="height_edges",
        height_edge_threshold=12.0,
        min_detection_score=0.75,
    )
    pipeline = ParcelVisionPipeline(config)
    frame = pipeline.fit_conveyor_plane(scene.points)
    detections = pipeline.process(scene.points)
    prediction_labels = assign_detection_labels(frame.to_local(scene.points), detections, frame, config)

    create_visualizations(scene.points, detections, frame, config, output_dir)
    save_truth_cloud(output_dir / "ground_truth_colored_cloudcompare.ply", scene.points, truth_labels)
    save_three_way_comparison(
        output_dir / "raw_truth_prediction_comparison.png",
        scene.points,
        truth_labels,
        prediction_labels,
        scene.expected,
        detections,
        frame,
        "Height-edge prediction",
    )

    truth = scene_ground_truth(scene, seed)
    for index, parcel in enumerate(truth["parcels"], start=1):
        parcel["visible_point_count"] = visible_counts.get(index, 0)
    truth["layout"] = "ten parcels in three mutually occluding layers"
    (output_dir / "ground_truth.json").write_text(
        json.dumps(truth, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    prediction = build_protocol_response(detections, f"stacked-simulation-{seed}", 0, "arm1")
    (output_dir / "prediction.json").write_text(
        json.dumps(prediction, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    grasp_plan = build_grasp_plan(detections, frame)
    (output_dir / "grasp_plan.json").write_text(
        json.dumps(grasp_plan, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    ideal_mask_detections = pipeline.process_labeled_instances(scene.points, truth_labels)
    ideal_mask_prediction = build_protocol_response(
        ideal_mask_detections, f"ideal-rgbd-masks-{seed}", 0, "arm1"
    )
    (output_dir / "ideal_rgbd_mask_prediction.json").write_text(
        json.dumps(ideal_mask_prediction, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    ideal_mask_metrics = evaluate_visible_mask_grasps(
        scene, truth_labels, ideal_mask_detections
    )
    closed_loop = simulate_closed_loop(seed)
    (output_dir / "closed_loop_pick_report.json").write_text(
        json.dumps(closed_loop, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    baseline_prediction = build_protocol_response(
        baseline_detections, f"stacked-baseline-{seed}", 0, "arm1"
    )
    (output_dir / "baseline_prediction.json").write_text(
        json.dumps(baseline_prediction, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    report = evaluate_scene(scene, detections)
    report.update(
        {
            "seed": seed,
            "input_points": len(scene.points),
            "parcel_types": count_types(scene.expected),
            "visible_points_per_truth": visible_counts,
            "segmentation_count_error": len(detections) - len(scene.expected),
            "baseline_detected_parcels": len(baseline_detections),
            "optimized_detected_surfaces": len(detections),
            "recommended_object_id": grasp_plan["recommended_object_id"],
            "eligible_grasp_candidates": grasp_plan["eligible_count"],
            "ideal_rgbd_mask_evaluation": ideal_mask_metrics,
            "closed_loop_pick_evaluation": {
                "cleared_parcels": closed_loop["cleared_parcels"],
                "total_parcels": closed_loop["total_parcels"],
                "completed": closed_loop["completed"],
            },
            "files": {
                "raw_ply": "stacked_10_parcels.ply",
                "raw_npy": "stacked_10_parcels.npy",
                "truth_colored_ply": "ground_truth_colored_cloudcompare.ply",
                "prediction_colored_ply": "prediction_colored_cloudcompare.ply",
                "comparison": "raw_truth_prediction_comparison.png",
                "ground_truth": "ground_truth.json",
                "prediction": "prediction.json",
                "baseline_prediction": "baseline_prediction.json",
                "grasp_plan": "grasp_plan.json",
                "ideal_rgbd_mask_prediction": "ideal_rgbd_mask_prediction.json",
                "closed_loop_pick_report": "closed_loop_pick_report.json",
            },
            "notice": "High-fidelity stacked-scene simulation, not an on-site camera capture.",
        }
    )
    (output_dir / "evaluation.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return report


def make_stacked_scene(
    rng: np.random.Generator,
    specs: list[StackedParcel] | None = None,
) -> tuple[StressScene, np.ndarray, dict[int, int]]:
    specs = list(specs) if specs is not None else stacked_layout()
    belt_length, belt_width, spacing = 1900.0, 1250.0, 7.0
    x, y = np.meshgrid(
        np.arange(-belt_length / 2, belt_length / 2 + 1, spacing),
        np.arange(-belt_width / 2, belt_width / 2 + 1, spacing),
    )
    xy = np.column_stack((x.ravel(), y.ravel()))
    heights = np.zeros(len(xy))
    labels = np.zeros(len(xy), dtype=np.int32)
    for index, spec in enumerate(specs, start=1):
        u, v = parcel_coordinates(xy, spec)
        top, inside = parcel_height(u, v, spec)
        candidate = spec.base_height + top
        visible = inside & (candidate > heights)
        heights[visible] = candidate[visible]
        labels[visible] = index

    noise_sigma = 1.6
    material_dropout = np.full(len(xy), 0.025)
    for index, spec in enumerate(specs, start=1):
        if spec.kind == "soft_bag":
            material_dropout[labels == index] = 0.11
        elif spec.kind == "tube":
            material_dropout[labels == index] = 0.07
        else:
            material_dropout[labels == index] = 0.055
    keep = rng.random(len(xy)) > material_dropout
    # Simulate one reflective-label hole and one dark-bag depth hole.
    hole1 = ((xy[:, 0] + 50) / 55) ** 2 + ((xy[:, 1] + 15) / 38) ** 2 < 1
    hole2 = ((xy[:, 0] - 245) / 70) ** 2 + ((xy[:, 1] - 35) / 48) ** 2 < 1
    keep &= ~(hole1 | hole2)
    xy, heights, labels = xy[keep], heights[keep], labels[keep]

    roll, pitch = 1.4, -2.8
    local_to_camera = rotation_y(np.radians(pitch)) @ rotation_x(np.radians(roll)) @ np.diag([1, 1, -1])
    translation = np.array([18.0, -12.0, 1180.0])
    local_points = np.column_stack((xy, heights))
    points = translation + local_points @ local_to_camera.T
    points += rng.normal(0.0, noise_sigma, points.shape)
    points = np.round(points * 2.0) / 2.0

    outlier_count = 160
    outliers_local = np.column_stack(
        (
            rng.uniform(-belt_length / 2, belt_length / 2, outlier_count),
            rng.uniform(-belt_width / 2, belt_width / 2, outlier_count),
            rng.uniform(-40, 380, outlier_count),
        )
    )
    points = np.vstack((points, translation + outliers_local @ local_to_camera.T))
    labels = np.append(labels, np.zeros(outlier_count, dtype=np.int32))

    expected = []
    for spec in specs:
        angle = np.radians(spec.yaw)
        major_axis = local_to_camera @ np.array([np.cos(angle), np.sin(angle), 0.0])
        center_height = spec.base_height + spec.height / 2
        top_height = spec.base_height + spec.height
        expected.append(
            ExpectedParcel(
                center_camera=translation + local_to_camera @ np.array([*spec.center, center_height]),
                top_camera=translation + local_to_camera @ np.array([*spec.center, top_height]),
                major_axis_camera=major_axis,
                length=spec.length,
                width=spec.width,
                height=spec.height,
                kind=spec.kind,
            )
        )
    visible_counts = {index: int(np.sum(labels == index)) for index in range(1, len(specs) + 1)}
    scene = StressScene(points, expected, noise_sigma, 0.0, (roll, pitch), outlier_count)
    return scene, labels, visible_counts


def stacked_layout() -> list[StackedParcel]:
    return [
        StackedParcel(1, "cardboard_box", (-430, -100), 520, 330, 105, 8, 0),
        StackedParcel(2, "soft_bag", (-40, -70), 470, 310, 105, -10, 0),
        StackedParcel(3, "cardboard_box", (390, -90), 520, 325, 125, 7, 0),
        StackedParcel(4, "padded_mailer", (90, 285), 470, 275, 48, 14, 0),
        StackedParcel(5, "cardboard_box", (-330, -70), 340, 225, 105, -8, 105),
        StackedParcel(6, "soft_bag", (-20, -25), 340, 235, 92, 16, 105),
        StackedParcel(7, "cardboard_box", (300, -45), 350, 230, 100, -12, 125),
        StackedParcel(8, "padded_mailer", (120, 270), 310, 190, 42, -8, 105),
        StackedParcel(9, "tube", (-125, -10), 310, 125, 110, 5, 205),
        StackedParcel(10, "soft_bag", (225, 35), 285, 195, 88, -18, 225),
    ]


def parcel_coordinates(xy: np.ndarray, spec: StackedParcel) -> tuple[np.ndarray, np.ndarray]:
    angle = np.radians(spec.yaw)
    c, s = np.cos(angle), np.sin(angle)
    relative = xy - np.asarray(spec.center)
    return relative[:, 0] * c + relative[:, 1] * s, -relative[:, 0] * s + relative[:, 1] * c


def parcel_height(u: np.ndarray, v: np.ndarray, spec: StackedParcel) -> tuple[np.ndarray, np.ndarray]:
    normalized = (u / (spec.length / 2)) ** 2 + (v / (spec.width / 2)) ** 2
    if spec.kind == "cardboard_box":
        inside = (np.abs(u) <= spec.length / 2) & (np.abs(v) <= spec.width / 2)
        top = np.full(len(u), spec.height)
    elif spec.kind == "soft_bag":
        inside = normalized <= 1.0 + 0.05 * np.sin(u / 19.0)
        top = spec.height * (0.58 + 0.42 * np.clip(1 - normalized, 0, 1))
        top += 3.5 * np.sin(u / 17.0) * np.cos(v / 14.0)
    elif spec.kind == "padded_mailer":
        inside = (np.abs(u) <= spec.length / 2) & (np.abs(v) <= spec.width / 2)
        top = spec.height * (0.8 + 0.2 * np.clip(1 - normalized, 0, 1))
    elif spec.kind == "tube":
        inside = (np.abs(u) <= spec.length / 2) & (np.abs(v) <= spec.width / 2)
        top = np.maximum(8.0, spec.height * np.sqrt(np.clip(1 - (v / (spec.width / 2)) ** 2, 0, 1)))
    else:
        raise ValueError(spec.kind)
    return top, inside


def save_truth_cloud(path: Path, points: np.ndarray, labels: np.ndarray) -> None:
    colors = np.full((len(points), 3), [105, 112, 120], dtype=np.uint8)
    for index in np.unique(labels[labels > 0]):
        colors[labels == index] = PALETTE[(index - 1) % len(PALETTE)]
    write_rgb_ply(path, points, colors)


def save_three_way_comparison(
    path: Path,
    points: np.ndarray,
    truth_labels: np.ndarray,
    prediction_labels: np.ndarray,
    expected: list[ExpectedParcel],
    detections: list,
    frame,
    prediction_name: str,
    truth_name: str = "Ground truth: 10 stacked parcels",
) -> None:
    local = frame.to_local(points)
    figure, axes = plt.subplots(1, 3, figsize=(21, 7), constrained_layout=True)
    height = np.clip(local[:, 2], 0, 400)
    axes[0].scatter(local[:, 0], local[:, 1], c=height, cmap="turbo", s=0.7, linewidths=0)
    axes[0].set_title("Raw overhead point cloud")
    draw_labeled_points(axes[1], local, truth_labels)
    for index, parcel in enumerate(expected, start=1):
        center = frame.to_local(parcel.center_camera[None, :])[0]
        axes[1].text(center[0], center[1], f"T{index}", weight="bold", ha="center")
    axes[1].set_title(truth_name)
    draw_labeled_points(axes[2], local, prediction_labels)
    draw_annotations_2d(axes[2], detections, frame)
    axes[2].set_title(f"{prediction_name}: {len(detections)} candidates")
    for axis in axes:
        axis.set_aspect("equal", adjustable="box")
        axis.set_xlabel("Conveyor X (mm)")
        axis.set_ylabel("Conveyor Y (mm)")
        axis.grid(alpha=0.15)
    figure.savefig(path, dpi=180, facecolor="white")
    plt.close(figure)


def count_types(expected: list[ExpectedParcel]) -> dict[str, int]:
    result: dict[str, int] = {}
    for parcel in expected:
        result[parcel.kind] = result.get(parcel.kind, 0) + 1
    return result


def evaluate_visible_mask_grasps(
    scene: StressScene,
    truth_labels: np.ndarray,
    detections: list,
) -> dict:
    visible_surface_errors = []
    full_center_errors = []
    for detection in detections:
        instance_id = int(detection.object_id.rsplit("_", 1)[-1])
        visible_points = scene.points[truth_labels == instance_id]
        if len(visible_points) == 0:
            continue
        visible_surface_errors.append(
            float(np.min(np.linalg.norm(visible_points - detection.grasp_camera, axis=1)))
        )
        full_center_errors.append(
            float(
                np.linalg.norm(
                    detection.grasp_camera - scene.expected[instance_id - 1].top_camera
                )
            )
        )
    return {
        "detected_instances": len(detections),
        "visible_surface_error_mm": metric_summary(visible_surface_errors),
        "full_object_top_center_error_mm": metric_summary(full_center_errors),
        "interpretation": (
            "Visible-surface error measures suction safety; full-center error remains large "
            "for partially occluded lower parcels."
        ),
    }


def metric_summary(values: list[float]) -> dict:
    if not values:
        return {"count": 0, "mean": 0.0, "p95": 0.0, "max": 0.0}
    array = np.asarray(values)
    return {
        "count": len(values),
        "mean": float(array.mean()),
        "p95": float(np.percentile(array, 95)),
        "max": float(array.max()),
    }


def simulate_closed_loop(seed: int) -> dict:
    active = stacked_layout()
    steps = []
    for step_index in range(1, 16):
        if not active:
            break
        scene, truth_labels, _ = make_stacked_scene(
            np.random.default_rng(seed + step_index * 101), active
        )
        pipeline = ParcelVisionPipeline(
            ParcelVisionConfig(
                grid_size=5.0,
                min_height=10.0,
                min_area=2_500.0,
                plane_distance_threshold=5.0,
                plane_ransac_iterations=180,
                morphology_radius=1,
                max_local_roughness=15.0,
                segmentation_method="height_edges",
                height_edge_threshold=12.0,
                min_detection_score=0.75,
            )
        )
        frame = pipeline.fit_conveyor_plane(scene.points)
        detections = pipeline.process(scene.points)
        plan = build_grasp_plan(detections, frame)
        recommended = plan["recommended_object_id"]
        if recommended is None:
            steps.append(
                {
                    "step": step_index,
                    "remaining_before_pick": len(active),
                    "status": "blocked_no_grasp_candidate",
                }
            )
            break
        selected = next(item for item in detections if item.object_id == recommended)
        object_points = truth_labels > 0
        distances = np.linalg.norm(
            scene.points[object_points] - selected.grasp_camera, axis=1
        )
        nearest_index = int(np.argmin(distances))
        selected_label = int(truth_labels[object_points][nearest_index])
        selected_spec = active[selected_label - 1]
        visible_error = float(distances[nearest_index])
        steps.append(
            {
                "step": step_index,
                "remaining_before_pick": len(active),
                "detected_surface_candidates": len(detections),
                "eligible_candidates": plan["eligible_count"],
                "selected_candidate": recommended,
                "selected_truth_id": f"truth_{selected_spec.truth_id:04d}",
                "selected_kind": selected_spec.kind,
                "visible_surface_error_mm": visible_error,
                "status": "picked_and_rescanned",
            }
        )
        active.pop(selected_label - 1)

    cleared = 10 - len(active)
    return {
        "total_parcels": 10,
        "cleared_parcels": cleared,
        "remaining_parcels": len(active),
        "completed": not active,
        "pick_count": len([step for step in steps if step["status"] == "picked_and_rescanned"]),
        "visible_surface_error_mm": metric_summary(
            [step["visible_surface_error_mm"] for step in steps if "visible_surface_error_mm" in step]
        ),
        "steps": steps,
    }


def rotation_x(angle: float) -> np.ndarray:
    c, s = np.cos(angle), np.sin(angle)
    return np.array([[1, 0, 0], [0, c, -s], [0, s, c]])


def rotation_y(angle: float) -> np.ndarray:
    c, s = np.cos(angle), np.sin(angle)
    return np.array([[c, 0, s], [0, 1, 0], [-s, 0, c]])


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate ten mutually stacked parcel point clouds")
    parser.add_argument("--seed", type=int, default=20260718)
    parser.add_argument("--output", type=Path, default=Path("reports/generated_stacked_10_parcels"))
    args = parser.parse_args()
    print(json.dumps(generate_stacked_scene(args.seed, args.output), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
