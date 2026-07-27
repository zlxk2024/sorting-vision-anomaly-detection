from __future__ import annotations

import numpy as np

from .pipeline import ParcelDetection, PlaneFrame
from .visualize import box_corners_local


def build_grasp_plan(
    detections: list[ParcelDetection],
    frame: PlaneFrame,
    vertical_clearance_mm: float = 20.0,
) -> dict:
    if not detections:
        return {"recommended_object_id": None, "eligible_count": 0, "candidates": []}

    local_grasps = {
        detection.object_id: frame.to_local(detection.grasp_camera[None, :])[0]
        for detection in detections
    }
    footprints = {
        detection.object_id: box_corners_local(detection, frame)[:4, :2]
        for detection in detections
    }
    blockers: dict[str, list[str]] = {detection.object_id: [] for detection in detections}
    for lower in detections:
        lower_height = local_grasps[lower.object_id][2]
        for upper in detections:
            if upper is lower:
                continue
            upper_height = local_grasps[upper.object_id][2]
            if upper_height <= lower_height + vertical_clearance_mm:
                continue
            if convex_polygons_overlap(footprints[lower.object_id], footprints[upper.object_id]):
                blockers[lower.object_id].append(upper.object_id)

    ordered = sorted(
        detections,
        key=lambda item: (
            bool(blockers[item.object_id]),
            -local_grasps[item.object_id][2],
            -item.score,
        ),
    )
    candidates = []
    for rank, detection in enumerate(ordered, start=1):
        grasp = detection.grasp_camera
        blocked_by = sorted(
            blockers[detection.object_id],
            key=lambda object_id: -local_grasps[object_id][2],
        )
        candidates.append(
            {
                "rank": rank,
                "object_id": detection.object_id,
                "eligible_now": not blocked_by,
                "blocked_by": blocked_by,
                "surface_height_mm": float(local_grasps[detection.object_id][2]),
                "suction_score": detection.score,
                "grasp_camera_mm": [float(value) for value in grasp],
                "action": "pick_then_rescan" if not blocked_by else "wait_for_rescan",
            }
        )
    eligible = [item for item in candidates if item["eligible_now"]]
    return {
        "recommended_object_id": eligible[0]["object_id"] if eligible else None,
        "eligible_count": len(eligible),
        "vertical_clearance_mm": vertical_clearance_mm,
        "candidates": candidates,
    }


def convex_polygons_overlap(first: np.ndarray, second: np.ndarray) -> bool:
    for polygon in (first, second):
        edges = np.roll(polygon, -1, axis=0) - polygon
        axes = np.column_stack((-edges[:, 1], edges[:, 0]))
        for axis in axes:
            norm = np.linalg.norm(axis)
            if norm < 1e-9:
                continue
            axis = axis / norm
            first_projection = first @ axis
            second_projection = second @ axis
            if first_projection.max() < second_projection.min() or second_projection.max() < first_projection.min():
                return False
    return True
