from __future__ import annotations

import argparse
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.lines import Line2D

from .io import load_point_cloud
from .pipeline import ParcelDetection, ParcelVisionConfig, ParcelVisionPipeline, PlaneFrame


PALETTE = np.array(
    [
        [0, 158, 115],
        [0, 114, 178],
        [230, 159, 0],
        [204, 121, 167],
        [86, 180, 233],
        [213, 94, 0],
        [240, 228, 66],
        [148, 103, 189],
        [0, 170, 170],
        [187, 86, 149],
    ],
    dtype=np.uint8,
)


def create_visualizations(
    points: np.ndarray,
    detections: list[ParcelDetection],
    frame: PlaneFrame,
    config: ParcelVisionConfig,
    output_dir: Path,
) -> dict[str, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    local = frame.to_local(points)
    labels = assign_detection_labels(local, detections, frame, config)

    top_path = output_dir / "point_cloud_vs_prediction_top.png"
    view3d_path = output_dir / "point_cloud_vs_prediction_3d.png"
    ply_path = output_dir / "prediction_colored_cloudcompare.ply"
    save_top_comparison(top_path, local, labels, detections, frame, config)
    save_3d_comparison(view3d_path, local, labels, detections, frame, config)
    save_annotated_ply(ply_path, points, local, labels, detections, frame, config)
    return {"top_view": top_path, "view_3d": view3d_path, "cloudcompare": ply_path}


def assign_detection_labels(
    local: np.ndarray,
    detections: list[ParcelDetection],
    frame: PlaneFrame,
    config: ParcelVisionConfig,
) -> np.ndarray:
    labels = np.zeros(len(local), dtype=np.int32)
    heights = local[:, 2]
    for index, detection in enumerate(detections, start=1):
        center = frame.to_local(detection.center_camera[None, :])[0]
        yaw = local_yaw(detection, frame)
        c, s = np.cos(yaw), np.sin(yaw)
        relative = local[:, :2] - center[:2]
        along = relative[:, 0] * c + relative[:, 1] * s
        across = -relative[:, 0] * s + relative[:, 1] * c
        inside = (
            (np.abs(along) <= detection.length / 2.0 + config.grid_size)
            & (np.abs(across) <= detection.width / 2.0 + config.grid_size)
            & (heights >= config.min_height)
            & (heights <= detection.height + max(15.0, config.grid_size * 2))
        )
        labels[(labels == 0) & inside] = index
    return labels


def save_top_comparison(
    path: Path,
    local: np.ndarray,
    labels: np.ndarray,
    detections: list[ParcelDetection],
    frame: PlaneFrame,
    config: ParcelVisionConfig,
) -> None:
    sample = sampled_indices(len(local), 100_000)
    figure, axes = plt.subplots(1, 2, figsize=(16, 7), constrained_layout=True)
    height = np.clip(local[sample, 2], 0, config.max_height)
    raw = axes[0].scatter(
        local[sample, 0], local[sample, 1], c=height, cmap="turbo", s=1, linewidths=0
    )
    figure.colorbar(raw, ax=axes[0], label="Height above belt (mm)", shrink=0.8)
    axes[0].set_title("Raw point cloud")

    draw_labeled_points(axes[1], local[sample], labels[sample])
    draw_annotations_2d(axes[1], detections, frame)
    axes[1].legend(
        handles=[
            Line2D([0], [0], color="black", linewidth=1.5, label="Bounding box / direction"),
            Line2D([0], [0], marker="o", color="none", markerfacecolor="#ffd400", markeredgecolor="black", markersize=8, label="Geometric center"),
            Line2D([0], [0], marker="*", color="none", markerfacecolor="#e31a1c", markeredgecolor="white", markersize=12, label="Suction point"),
        ],
        loc="lower right",
        framealpha=0.9,
    )
    axes[1].set_title(f"Prediction: {len(detections)} parcels")
    for axis in axes:
        axis.set_aspect("equal", adjustable="box")
        axis.set_xlabel("Conveyor X (mm)")
        axis.set_ylabel("Conveyor Y (mm)")
        axis.grid(alpha=0.15)
    figure.savefig(path, dpi=180, facecolor="white")
    plt.close(figure)


def save_3d_comparison(
    path: Path,
    local: np.ndarray,
    labels: np.ndarray,
    detections: list[ParcelDetection],
    frame: PlaneFrame,
    config: ParcelVisionConfig,
) -> None:
    sample = sampled_indices(len(local), 45_000)
    figure = plt.figure(figsize=(16, 7), constrained_layout=True)
    raw_axis = figure.add_subplot(121, projection="3d")
    pred_axis = figure.add_subplot(122, projection="3d")
    height = np.clip(local[sample, 2], 0, config.max_height)
    raw_axis.scatter(
        local[sample, 0], local[sample, 1], local[sample, 2],
        c=height, cmap="turbo", s=0.5, linewidths=0,
    )
    raw_axis.set_title("Raw point cloud")
    draw_labeled_points_3d(pred_axis, local[sample], labels[sample])
    for detection in detections:
        corners = box_corners_local(detection, frame)
        for start, end in box_edges():
            pred_axis.plot(*corners[[start, end]].T, color="black", linewidth=1.2)
        center = frame.to_local(detection.center_camera[None, :])[0]
        grasp = frame.to_local(detection.grasp_camera[None, :])[0]
        pred_axis.scatter(*center, color="#ffd400", edgecolor="black", s=55, marker="o")
        pred_axis.scatter(*grasp, color="#e31a1c", edgecolor="white", s=80, marker="*")
    pred_axis.set_title(f"Prediction: {len(detections)} parcels")
    for axis in (raw_axis, pred_axis):
        axis.set_xlabel("X (mm)")
        axis.set_ylabel("Y (mm)")
        axis.set_zlabel("Height (mm)")
        axis.view_init(elev=38, azim=-58)
        axis.set_box_aspect((1.5, 1.0, 0.45))
    figure.savefig(path, dpi=180, facecolor="white")
    plt.close(figure)


def save_annotated_ply(
    path: Path,
    points: np.ndarray,
    local: np.ndarray,
    labels: np.ndarray,
    detections: list[ParcelDetection],
    frame: PlaneFrame,
    config: ParcelVisionConfig,
) -> None:
    colors = np.full((len(points), 3), [95, 105, 115], dtype=np.uint8)
    object_unassigned = (local[:, 2] >= config.min_height) & (labels == 0)
    colors[object_unassigned] = [175, 175, 175]
    for index in range(1, len(detections) + 1):
        colors[labels == index] = PALETTE[(index - 1) % len(PALETTE)]

    annotation_points: list[np.ndarray] = []
    annotation_colors: list[np.ndarray] = []
    for detection in detections:
        corners = box_corners_local(detection, frame)
        lines = np.vstack([sample_line(corners[a], corners[b], 5.0) for a, b in box_edges()])
        center = frame.to_local(detection.center_camera[None, :])[0]
        grasp = frame.to_local(detection.grasp_camera[None, :])[0]
        annotation_points.extend([lines, marker_cross(center, 22.0), marker_cross(grasp, 30.0)])
        annotation_colors.extend(
            [
                np.full((len(lines), 3), 255, dtype=np.uint8),
                np.tile([255, 212, 0], (6, 1)).astype(np.uint8),
                np.tile([227, 26, 28], (6, 1)).astype(np.uint8),
            ]
        )
    if annotation_points:
        annotated_local = np.vstack(annotation_points)
        points = np.vstack((points, frame.to_camera(annotated_local)))
        colors = np.vstack((colors, *annotation_colors))
    write_rgb_ply(path, points, colors)


def draw_labeled_points(axis, points: np.ndarray, labels: np.ndarray) -> None:
    axis.scatter(points[labels == 0, 0], points[labels == 0, 1], c="#aeb4bb", s=0.7, linewidths=0)
    for index in np.unique(labels[labels > 0]):
        selected = labels == index
        axis.scatter(
            points[selected, 0], points[selected, 1],
            c=[PALETTE[(index - 1) % len(PALETTE)] / 255.0], s=1.2, linewidths=0,
        )


def draw_labeled_points_3d(axis, points: np.ndarray, labels: np.ndarray) -> None:
    axis.scatter(*points[labels == 0].T, c="#aeb4bb", s=0.4, linewidths=0, alpha=0.35)
    for index in np.unique(labels[labels > 0]):
        selected = labels == index
        axis.scatter(
            *points[selected].T,
            c=[PALETTE[(index - 1) % len(PALETTE)] / 255.0], s=0.7, linewidths=0,
        )


def draw_annotations_2d(axis, detections: list[ParcelDetection], frame: PlaneFrame) -> None:
    for index, detection in enumerate(detections, start=1):
        corners = box_corners_local(detection, frame)[:4, :2]
        outline = corners[[0, 1, 2, 3, 0]]
        center = frame.to_local(detection.center_camera[None, :])[0]
        grasp = frame.to_local(detection.grasp_camera[None, :])[0]
        yaw = local_yaw(detection, frame)
        direction = np.array([np.cos(yaw), np.sin(yaw)]) * detection.length * 0.25
        axis.plot(outline[:, 0], outline[:, 1], color="black", linewidth=1.5)
        axis.scatter(*center[:2], color="#ffd400", edgecolor="black", s=55, zorder=5)
        axis.scatter(*grasp[:2], color="#e31a1c", edgecolor="white", s=100, marker="*", zorder=6)
        axis.arrow(
            center[0], center[1], direction[0], direction[1],
            width=2.0, head_width=18.0, color="black", length_includes_head=True,
        )
        axis.text(
            center[0], center[1] + detection.width * 0.15,
            f"#{index}\nscore={detection.score:.2f}",
            ha="center", va="center", fontsize=8, weight="bold",
            bbox={"facecolor": "white", "edgecolor": "none", "alpha": 0.72, "pad": 1.5},
        )


def box_corners_local(detection: ParcelDetection, frame: PlaneFrame) -> np.ndarray:
    center = frame.to_local(detection.center_camera[None, :])[0]
    yaw = local_yaw(detection, frame)
    c, s = np.cos(yaw), np.sin(yaw)
    rotation = np.array([[c, -s], [s, c]])
    half = np.array([detection.length, detection.width]) / 2.0
    footprint = np.array([[-1, -1], [1, -1], [1, 1], [-1, 1]]) * half
    footprint = footprint @ rotation.T + center[:2]
    bottom = np.column_stack((footprint, np.zeros(4)))
    top = np.column_stack((footprint, np.full(4, detection.height)))
    return np.vstack((bottom, top))


def local_yaw(detection: ParcelDetection, frame: PlaneFrame) -> float:
    local_rotation = frame.rotation.T @ detection.rotation_camera
    return float(np.arctan2(local_rotation[1, 0], local_rotation[0, 0]))


def box_edges() -> list[tuple[int, int]]:
    return [
        (0, 1), (1, 2), (2, 3), (3, 0),
        (4, 5), (5, 6), (6, 7), (7, 4),
        (0, 4), (1, 5), (2, 6), (3, 7),
    ]


def sample_line(start: np.ndarray, end: np.ndarray, spacing: float) -> np.ndarray:
    count = max(2, int(np.linalg.norm(end - start) / spacing) + 1)
    return np.linspace(start, end, count)


def marker_cross(center: np.ndarray, radius: float) -> np.ndarray:
    offsets = np.array(
        [[-radius, 0, 0], [radius, 0, 0], [0, -radius, 0], [0, radius, 0], [0, 0, -radius], [0, 0, radius]]
    )
    return center + offsets


def sampled_indices(size: int, limit: int) -> np.ndarray:
    if size <= limit:
        return np.arange(size)
    return np.random.default_rng(7).choice(size, limit, replace=False)


def write_rgb_ply(path: Path, points: np.ndarray, colors: np.ndarray) -> None:
    header = (
        "ply\nformat ascii 1.0\n"
        f"element vertex {len(points)}\n"
        "property float x\nproperty float y\nproperty float z\n"
        "property uchar red\nproperty uchar green\nproperty uchar blue\nend_header\n"
    )
    with path.open("w", encoding="ascii") as handle:
        handle.write(header)
        values = np.column_stack((points, colors))
        np.savetxt(handle, values, fmt="%.4f %.4f %.4f %d %d %d")


def main() -> None:
    parser = argparse.ArgumentParser(description="Visualize raw point cloud and parcel predictions")
    parser.add_argument("point_cloud", type=Path)
    parser.add_argument("--output", type=Path, default=Path("reports/visualization"))
    parser.add_argument("--grid-size", type=float, default=5.0)
    parser.add_argument("--min-height", type=float, default=10.0)
    parser.add_argument("--min-area", type=float, default=2500.0)
    parser.add_argument("--morphology-radius", type=int, default=1)
    args = parser.parse_args()

    points = load_point_cloud(args.point_cloud)
    config = ParcelVisionConfig(
        grid_size=args.grid_size,
        min_height=args.min_height,
        min_area=args.min_area,
        morphology_radius=args.morphology_radius,
    )
    pipeline = ParcelVisionPipeline(config)
    frame = pipeline.fit_conveyor_plane(points)
    detections = pipeline.process(points)
    outputs = create_visualizations(points, detections, frame, config, args.output)
    print(f"Detected {len(detections)} parcels")
    for name, output in outputs.items():
        print(f"{name}: {output}")


if __name__ == "__main__":
    main()
