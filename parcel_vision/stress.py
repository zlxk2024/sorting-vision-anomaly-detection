from __future__ import annotations

import argparse
import json
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Optional

import numpy as np
from scipy.optimize import linear_sum_assignment

from .pipeline import ParcelVisionConfig, ParcelVisionPipeline


@dataclass
class ExpectedParcel:
    center_camera: np.ndarray
    top_camera: np.ndarray
    major_axis_camera: np.ndarray
    length: float
    width: float
    height: float
    kind: str


@dataclass
class StressScene:
    points: np.ndarray
    expected: list[ExpectedParcel]
    noise_sigma: float
    dropout: float
    tilt_degrees: tuple[float, float]
    outlier_count: int


def make_stress_scene(rng: np.random.Generator) -> StressScene:
    belt_width, belt_length = 900.0, 1400.0
    roll = float(rng.uniform(-5.0, 5.0))
    pitch = float(rng.uniform(-5.0, 5.0))
    rotation = _rotation_y(np.radians(pitch)) @ _rotation_x(np.radians(roll))
    # Local +Z points from the belt towards the overhead camera.
    local_to_camera = rotation @ np.diag([1.0, 1.0, -1.0])
    translation = np.array([rng.uniform(-40, 40), rng.uniform(-40, 40), rng.uniform(850, 1250)])
    noise_sigma = float(rng.uniform(0.4, 2.5))
    dropout = float(rng.uniform(0.0, 0.18))

    bx, by = np.meshgrid(
        np.arange(-belt_length / 2, belt_length / 2 + 1, 18.0),
        np.arange(-belt_width / 2, belt_width / 2 + 1, 18.0),
    )
    belt_local = np.column_stack((bx.ravel(), by.ravel(), np.zeros(bx.size)))
    belt_local = belt_local[rng.random(len(belt_local)) > dropout * 0.35]

    expected: list[ExpectedParcel] = []
    local_clouds = [belt_local]
    occupied: list[tuple[np.ndarray, float]] = []
    target_count = int(rng.integers(2, 7))
    attempts = 0
    while len(expected) < target_count and attempts < 200:
        attempts += 1
        length = float(rng.uniform(150, 360))
        width = float(rng.uniform(90, min(230, length - 20)))
        height = float(rng.uniform(25, 180))
        yaw = float(rng.uniform(-85, 85))
        center = np.array(
            [
                rng.uniform(-belt_length / 2 + length / 2 + 25, belt_length / 2 - length / 2 - 25),
                rng.uniform(-belt_width / 2 + width / 2 + 25, belt_width / 2 - width / 2 - 25),
            ]
        )
        radius = np.hypot(length, width) / 2.0
        if any(np.linalg.norm(center - other) < radius + other_radius + 18.0 for other, other_radius in occupied):
            continue
        occupied.append((center, radius))
        kind = "soft" if rng.random() < 0.4 else "box"
        top = _parcel_surface(rng, center, length, width, height, yaw, kind, dropout)
        local_clouds.append(top)
        angle = np.radians(yaw)
        major_local = np.array([np.cos(angle), np.sin(angle), 0.0])
        center_local = np.array([center[0], center[1], height / 2.0])
        top_local = np.array([center[0], center[1], height if kind == "box" else height * 0.96])
        expected.append(
            ExpectedParcel(
                center_camera=translation + local_to_camera @ center_local,
                top_camera=translation + local_to_camera @ top_local,
                major_axis_camera=local_to_camera @ major_local,
                length=length,
                width=width,
                height=height,
                kind=kind,
            )
        )

    points_local = np.vstack(local_clouds)
    points = translation + points_local @ local_to_camera.T
    points += rng.normal(0.0, noise_sigma, points.shape)
    points = np.round(points * 2.0) / 2.0

    outlier_count = int(rng.integers(0, 180))
    if outlier_count:
        outliers_local = np.column_stack(
            (
                rng.uniform(-belt_length / 2, belt_length / 2, outlier_count),
                rng.uniform(-belt_width / 2, belt_width / 2, outlier_count),
                rng.uniform(-80, 350, outlier_count),
            )
        )
        outliers = translation + outliers_local @ local_to_camera.T
        points = np.vstack((points, outliers))
    return StressScene(points, expected, noise_sigma, dropout, (roll, pitch), outlier_count)


def _parcel_surface(
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
    if kind == "soft":
        radial = np.clip(1.0 - (u / (length / 2)) ** 2 - (v / (width / 2)) ** 2, 0.0, 1.0)
        z = height * (0.72 + 0.25 * radial)
        z += 2.0 * np.sin(u / 19.0) + 1.5 * np.sin(v / 13.0)
    else:
        z = np.full_like(u, height)

    angle = np.radians(yaw)
    planar_rotation = np.array([[np.cos(angle), -np.sin(angle)], [np.sin(angle), np.cos(angle)]])
    xy = np.column_stack((u, v)) @ planar_rotation.T + center
    keep = rng.random(len(xy)) > dropout
    # Add one contiguous depth hole, similar to a dark or reflective label patch.
    if rng.random() < 0.7:
        hole_center = rng.normal(0.0, [length * 0.18, width * 0.18])
        hole = ((u - hole_center[0]) / (length * 0.12)) ** 2 + ((v - hole_center[1]) / (width * 0.12)) ** 2 < 1
        keep &= ~hole
    return np.column_stack((xy, z))[keep]


def run_stress_suite(scene_count: int = 100, seed: int = 20260715) -> dict:
    rng = np.random.default_rng(seed)
    pipeline = ParcelVisionPipeline(
        ParcelVisionConfig(
            grid_size=5.0,
            plane_distance_threshold=5.0,
            plane_ransac_iterations=140,
            morphology_radius=1,
            max_local_roughness=12.0,
        )
    )
    position_errors: list[float] = []
    height_errors: list[float] = []
    length_errors: list[float] = []
    width_errors: list[float] = []
    orientation_errors: list[float] = []
    runtimes: list[float] = []
    expected_total = detected_total = matched_total = exact_count_scenes = 0
    failures: list[dict] = []

    for scene_index in range(scene_count):
        scene = make_stress_scene(rng)
        started = time.perf_counter()
        try:
            detections = pipeline.process(scene.points)
            error = None
        except Exception as exc:
            detections = []
            error = str(exc)
        runtimes.append((time.perf_counter() - started) * 1000.0)
        expected_total += len(scene.expected)
        detected_total += len(detections)
        if len(detections) == len(scene.expected):
            exact_count_scenes += 1

        if detections and scene.expected:
            distances = np.array(
                [
                    [np.linalg.norm(det.grasp_camera - exp.top_camera) for exp in scene.expected]
                    for det in detections
                ]
            )
            rows, cols = linear_sum_assignment(distances)
            for row, col in zip(rows, cols):
                if distances[row, col] > 80.0:
                    continue
                det, exp = detections[row], scene.expected[col]
                matched_total += 1
                position_errors.append(float(distances[row, col]))
                height_errors.append(abs(det.height - exp.height))
                length_errors.append(abs(det.length - exp.length))
                width_errors.append(abs(det.width - exp.width))
                detected_axis = det.rotation_camera[:, 0] / np.linalg.norm(det.rotation_camera[:, 0])
                expected_axis = exp.major_axis_camera / np.linalg.norm(exp.major_axis_camera)
                orientation_errors.append(float(np.degrees(np.arccos(np.clip(abs(np.dot(detected_axis, expected_axis)), 0, 1)))))

        if error or len(detections) != len(scene.expected):
            failures.append(
                {
                    "scene": scene_index,
                    "expected": len(scene.expected),
                    "detected": len(detections),
                    "noise_sigma_mm": round(scene.noise_sigma, 3),
                    "dropout": round(scene.dropout, 3),
                    "tilt_degrees": [round(value, 3) for value in scene.tilt_degrees],
                    "outliers": scene.outlier_count,
                    "error": error,
                }
            )

    return {
        "suite": "high_fidelity_synthetic_point_cloud",
        "seed": seed,
        "scene_count": scene_count,
        "expected_parcels": expected_total,
        "detected_parcels": detected_total,
        "matched_parcels": matched_total,
        "precision": _ratio(matched_total, detected_total),
        "recall": _ratio(matched_total, expected_total),
        "exact_count_scene_rate": _ratio(exact_count_scenes, scene_count),
        "position_error_mm": _stats(position_errors),
        "height_error_mm": _stats(height_errors),
        "length_error_mm": _stats(length_errors),
        "width_error_mm": _stats(width_errors),
        "orientation_error_degrees": _stats(orientation_errors),
        "runtime_ms": _stats(runtimes),
        "failure_count": len(failures),
        "failures": failures[:30],
        "limits": [
            "Synthetic sensor model; results are not a replacement for on-site camera validation.",
            "Parcels are single-layer and spatially separated; fully touching parcels are outside this baseline.",
        ],
    }


def write_report(report: dict, output_dir: str | Path = "reports") -> tuple[Path, Path]:
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    json_path = output / "stress_report.json"
    markdown_path = output / "stress_report.md"
    json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    markdown_path.write_text(_markdown(report), encoding="utf-8")
    return json_path, markdown_path


def _markdown(report: dict) -> str:
    def metric(name: str) -> str:
        values = report[name]
        return f"平均 {values['mean']:.2f}，P95 {values['p95']:.2f}，最大 {values['max']:.2f}"

    return f"""# 快递点云定位高拟真压力测试报告

## 测试范围

- 随机场景：{report['scene_count']} 帧
- 真实快递数：{report['expected_parcels']}
- 输出目标数：{report['detected_parcels']}
- 成功匹配数：{report['matched_parcels']}
- 固定随机种子：{report['seed']}

每帧随机加入 0.4-2.5 mm 深度噪声、0-18% 随机缺点、连续深度空洞、0-180 个离群点、传送带 ±5° 倾斜，并混合纸箱和平滑鼓包软包。

## 结果

| 指标 | 结果 |
|---|---:|
| 检测精确率 | {report['precision'] * 100:.2f}% |
| 检测召回率 | {report['recall'] * 100:.2f}% |
| 整帧数量完全正确率 | {report['exact_count_scene_rate'] * 100:.2f}% |
| 三维抓取点误差/mm | {metric('position_error_mm')} |
| 高度误差/mm | {metric('height_error_mm')} |
| 长度误差/mm | {metric('length_error_mm')} |
| 宽度误差/mm | {metric('width_error_mm')} |
| 主方向误差/° | {metric('orientation_error_degrees')} |
| 单帧时间/ms | {metric('runtime_ms')} |

## 结论边界

该结果用于算法回归和压力测试，不代表现场3D相机最终精度。当前基线针对单层、已摊开且存在可见间隙的快递；完全贴合、上下叠放以及透明包装需要RGB实例分割或额外深度策略。
"""


def _stats(values: list[float]) -> dict:
    if not values:
        return {"count": 0, "mean": 0.0, "median": 0.0, "p95": 0.0, "max": 0.0}
    array = np.asarray(values)
    return {
        "count": len(values),
        "mean": float(array.mean()),
        "median": float(np.median(array)),
        "p95": float(np.percentile(array, 95)),
        "max": float(array.max()),
    }


def _ratio(numerator: int, denominator: int) -> float:
    return float(numerator / denominator) if denominator else 0.0


def _rotation_x(angle: float) -> np.ndarray:
    c, s = np.cos(angle), np.sin(angle)
    return np.array([[1, 0, 0], [0, c, -s], [0, s, c]])


def _rotation_y(angle: float) -> np.ndarray:
    c, s = np.cos(angle), np.sin(angle)
    return np.array([[c, 0, s], [0, 1, 0], [-s, 0, c]])


def main() -> None:
    parser = argparse.ArgumentParser(description="Run randomized parcel point-cloud stress tests")
    parser.add_argument("--scenes", type=int, default=100)
    parser.add_argument("--seed", type=int, default=20260715)
    parser.add_argument("--output", default="reports")
    args = parser.parse_args()
    report = run_stress_suite(args.scenes, args.seed)
    json_path, markdown_path = write_report(report, args.output)
    print(json.dumps({"json": str(json_path), "markdown": str(markdown_path), **report}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
