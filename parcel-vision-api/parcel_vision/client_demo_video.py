from __future__ import annotations

import argparse
import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.animation as animation
import matplotlib.font_manager as font_manager
import matplotlib.pyplot as plt
import numpy as np

from .pipeline import ParcelVisionConfig, ParcelVisionPipeline
from .visualize import (
    PALETTE,
    assign_detection_labels,
    box_corners_local,
    box_edges,
)


def create_client_demo_video(
    point_cloud: Path,
    evaluation: Path,
    output: Path,
    fps: int = 12,
    duration_seconds: int = 12,
) -> Path:
    configure_chinese_font()
    points = np.load(point_cloud)
    metrics = json.loads(evaluation.read_text(encoding="utf-8"))
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
    frame = pipeline.fit_conveyor_plane(points)
    detections = pipeline.process(points)
    local = frame.to_local(points)
    labels = assign_detection_labels(local, detections, frame, config)
    sample = sample_indices(len(points), 24_000)

    figure = plt.figure(figsize=(16, 8), facecolor="#080b10")
    figure.subplots_adjust(left=0.015, right=0.985, top=0.86, bottom=0.13, wspace=0.02)
    raw_axis = figure.add_subplot(121, projection="3d")
    prediction_axis = figure.add_subplot(122, projection="3d")
    style_axis(raw_axis, "原始3D点云")
    style_axis(prediction_axis, "算法识别结果")

    sampled_local = local[sample]
    sampled_labels = labels[sample]
    raw_axis.scatter(
        sampled_local[:, 0],
        sampled_local[:, 1],
        sampled_local[:, 2],
        c=np.clip(sampled_local[:, 2], 0, 220),
        cmap="turbo",
        s=0.65,
        linewidths=0,
        alpha=0.9,
        depthshade=False,
    )
    background = sampled_labels == 0
    prediction_axis.scatter(
        *sampled_local[background].T,
        c="#6d7785",
        s=0.35,
        linewidths=0,
        alpha=0.16,
        depthshade=False,
    )
    for instance_id in np.unique(sampled_labels[sampled_labels > 0]):
        selected = sampled_labels == instance_id
        prediction_axis.scatter(
            *sampled_local[selected].T,
            c=[PALETTE[(instance_id - 1) % len(PALETTE)] / 255.0],
            s=0.9,
            linewidths=0,
            alpha=0.95,
            depthshade=False,
        )

    for detection in detections:
        corners = box_corners_local(detection, frame)
        for start, end in box_edges():
            prediction_axis.plot(
                *corners[[start, end]].T,
                color="#eef3f8",
                linewidth=1.0,
                alpha=0.88,
            )
        center = frame.to_local(detection.center_camera[None, :])[0]
        grasp = frame.to_local(detection.grasp_camera[None, :])[0]
        prediction_axis.scatter(
            *center,
            color="#ffd400",
            edgecolor="#171717",
            linewidth=0.7,
            s=42,
            marker="o",
            depthshade=False,
        )
        prediction_axis.scatter(
            *grasp,
            color="#ff3b30",
            edgecolor="white",
            linewidth=0.55,
            s=62,
            marker="*",
            depthshade=False,
        )
        prediction_axis.text(
            center[0],
            center[1],
            detection.height + 16,
            detection.object_id.replace("pkg_", "#"),
            color="white",
            fontsize=7,
            ha="center",
            va="bottom",
        )

    figure.text(
        0.5,
        0.945,
        "快递3D点云识别与机械臂抓取定位",
        color="white",
        fontsize=24,
        weight="bold",
        ha="center",
        va="center",
    )
    visible_metrics = metrics["matched_visible_surface_error_mm"]
    figure.text(
        0.5,
        0.075,
        (
            f"识别 {metrics['detected_parcels']}/{metrics['expected_parcels']} 件"
            f"    |    点云 {metrics['input_points']:,} 点"
            f"    |    吸取点可见表面误差 P95 {visible_metrics['p95']:.2f} mm"
            f"    |    当前推荐 {metrics['recommended_object_id']}"
        ),
        color="#dce6ef",
        fontsize=13,
        ha="center",
        va="center",
    )
    figure.text(
        0.985,
        0.018,
        "高拟真仿真演示 | 现场精度以真实相机验收为准",
        color="#8492a3",
        fontsize=9,
        ha="right",
        va="bottom",
    )
    figure.text(
        0.025,
        0.018,
        "黄色：几何中心    红色：吸取点    白色：预测包围框",
        color="#8492a3",
        fontsize=9,
        ha="left",
        va="bottom",
    )

    frame_count = fps * duration_seconds
    moving_frames = max(1, frame_count - fps * 2)

    def update(frame_index: int):
        progress = min(frame_index, moving_frames - 1) / max(1, moving_frames - 1)
        azimuth = -65 + 115 * smoothstep(progress)
        elevation = 42 + 7 * np.sin(progress * np.pi)
        for axis in (raw_axis, prediction_axis):
            axis.view_init(elev=elevation, azim=azimuth)
        return ()

    output.parent.mkdir(parents=True, exist_ok=True)
    writer = animation.FFMpegWriter(
        fps=fps,
        codec="libx264",
        bitrate=5200,
        extra_args=["-pix_fmt", "yuv420p", "-movflags", "+faststart"],
    )
    movie = animation.FuncAnimation(
        figure,
        update,
        frames=frame_count,
        interval=1000 / fps,
        blit=False,
    )
    movie.save(output, writer=writer, dpi=100)
    plt.close(figure)
    return output


def style_axis(axis, title: str) -> None:
    axis.set_facecolor("#080b10")
    axis.set_title(title, color="white", fontsize=16, weight="bold", pad=10)
    axis.set_xlim(-1000, 1000)
    axis.set_ylim(-650, 650)
    axis.set_zlim(-25, 260)
    axis.set_box_aspect((1.55, 1.0, 0.42))
    axis.set_xlabel("X / mm", color="#9aa7b5", labelpad=8)
    axis.set_ylabel("Y / mm", color="#9aa7b5", labelpad=8)
    axis.set_zlabel("高度 / mm", color="#9aa7b5", labelpad=5)
    axis.tick_params(colors="#708090", labelsize=7)
    axis.grid(True, alpha=0.12)
    for pane in (axis.xaxis.pane, axis.yaxis.pane, axis.zaxis.pane):
        pane.set_facecolor((0.04, 0.055, 0.075, 1.0))
        pane.set_edgecolor((0.25, 0.3, 0.36, 0.35))


def configure_chinese_font() -> None:
    font_path = Path("/System/Library/Fonts/PingFang.ttc")
    if font_path.exists():
        font_manager.fontManager.addfont(str(font_path))
        plt.rcParams["font.family"] = font_manager.FontProperties(fname=font_path).get_name()
    plt.rcParams["axes.unicode_minus"] = False


def sample_indices(size: int, limit: int) -> np.ndarray:
    if size <= limit:
        return np.arange(size)
    return np.random.default_rng(20260720).choice(size, limit, replace=False)


def smoothstep(value: float) -> float:
    return value * value * (3 - 2 * value)


def main() -> None:
    parser = argparse.ArgumentParser(description="Create a side-by-side client demo video")
    parser.add_argument(
        "--point-cloud",
        type=Path,
        default=Path("reports/generated_irregular_parcels/irregular_parcels.npy"),
    )
    parser.add_argument(
        "--evaluation",
        type=Path,
        default=Path("reports/generated_irregular_parcels/evaluation.json"),
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("reports/client_demo/parcel_vision_demo.mp4"),
    )
    parser.add_argument("--fps", type=int, default=12)
    parser.add_argument("--duration", type=int, default=12)
    args = parser.parse_args()
    print(
        create_client_demo_video(
            args.point_cloud,
            args.evaluation,
            args.output,
            args.fps,
            args.duration,
        )
    )


if __name__ == "__main__":
    main()
