from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from .pipeline import ParcelDetection, ParcelVisionPipeline


@dataclass(frozen=True)
class CameraIntrinsics:
    fx: float
    fy: float
    cx: float
    cy: float


def rgbd_instance_masks_to_detections(
    depth: np.ndarray,
    instance_masks: np.ndarray,
    intrinsics: CameraIntrinsics,
    pipeline: ParcelVisionPipeline,
    depth_scale_to_mm: float = 1.0,
    camera_to_robot: np.ndarray | None = None,
) -> list[ParcelDetection]:
    points, labels = depth_and_masks_to_labeled_cloud(
        depth, instance_masks, intrinsics, depth_scale_to_mm
    )
    return pipeline.process_labeled_instances(points, labels, camera_to_robot)


def depth_and_masks_to_labeled_cloud(
    depth: np.ndarray,
    instance_masks: np.ndarray,
    intrinsics: CameraIntrinsics,
    depth_scale_to_mm: float = 1.0,
) -> tuple[np.ndarray, np.ndarray]:
    depth_array = np.asarray(depth, dtype=float)
    masks = np.asarray(instance_masks, dtype=bool)
    if depth_array.ndim != 2:
        raise ValueError("depth must have shape (H, W)")
    if masks.ndim != 3 or masks.shape[1:] != depth_array.shape:
        raise ValueError("instance_masks must have shape (K, H, W)")
    if depth_scale_to_mm <= 0:
        raise ValueError("depth_scale_to_mm must be positive")

    valid = np.isfinite(depth_array) & (depth_array > 0)
    rows, cols = np.indices(depth_array.shape)
    z = depth_array * depth_scale_to_mm
    x = (cols - intrinsics.cx) * z / intrinsics.fx
    y = (rows - intrinsics.cy) * z / intrinsics.fy
    points = np.column_stack((x[valid], y[valid], z[valid]))

    pixel_labels = np.zeros(depth_array.shape, dtype=np.int32)
    for instance_id, mask in enumerate(masks, start=1):
        available = mask & (pixel_labels == 0)
        pixel_labels[available] = instance_id
    return points, pixel_labels[valid]
