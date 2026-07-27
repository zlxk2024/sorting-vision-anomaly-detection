from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Optional, Sequence

import numpy as np
from scipy import ndimage
from scipy.sparse import coo_matrix
from scipy.sparse.csgraph import connected_components
from scipy.spatial import ConvexHull


@dataclass
class ParcelVisionConfig:
    """All distances use millimetres and angles use degrees."""

    grid_size: float = 5.0
    min_height: float = 10.0
    max_height: float = 800.0
    min_area: float = 2_500.0
    max_area: float = 1_500_000.0
    plane_distance_threshold: float = 3.0
    plane_ransac_iterations: int = 250
    morphology_radius: int = 1
    segmentation_method: str = "connected"
    height_edge_threshold: float = 12.0
    suction_radius: float = 25.0
    local_flatness_radius: float = 35.0
    max_local_roughness: float = 8.0
    min_detection_score: float = 0.0
    roi_xy: Optional[tuple[float, float, float, float]] = None
    random_seed: int = 7


@dataclass
class ParcelDetection:
    object_id: str
    center_camera: np.ndarray
    grasp_camera: np.ndarray
    rotation_camera: np.ndarray
    length: float
    width: float
    height: float
    angle_z: float
    score: float
    point_count: int
    object_type: int = 2

    def transformed(self, camera_to_robot: np.ndarray) -> "ParcelDetection":
        matrix = np.asarray(camera_to_robot, dtype=float)
        if matrix.shape != (4, 4):
            raise ValueError("camera_to_robot must be a 4x4 homogeneous matrix")

        def transform_point(point: np.ndarray) -> np.ndarray:
            return (matrix @ np.append(point, 1.0))[:3]

        rotation = matrix[:3, :3] @ self.rotation_camera
        return ParcelDetection(
            object_id=self.object_id,
            center_camera=transform_point(self.center_camera),
            grasp_camera=transform_point(self.grasp_camera),
            rotation_camera=rotation,
            length=self.length,
            width=self.width,
            height=self.height,
            angle_z=float(np.degrees(np.arctan2(rotation[1, 0], rotation[0, 0]))),
            score=self.score,
            point_count=self.point_count,
            object_type=self.object_type,
        )

    def protocol_item(self, device: str = "arm1", include_extensions: bool = True) -> dict:
        x, y, z = self.grasp_camera
        roll, pitch, yaw = rotation_matrix_to_euler_xyz(self.rotation_camera)
        location = {
            "x": f"{x:.2f}",
            "y": f"{y:.2f}",
            "z": f"{z:.2f}",
            "angle_z": f"{yaw:.2f}",
            "angle_y": f"{pitch:.2f}",
            "angle_x": f"{roll:.2f}",
            "object_length": f"{self.length:.2f}",
            "object_width": f"{self.width:.2f}",
            "object_height": f"{self.height:.2f}",
            "object_type": str(self.object_type),
        }
        if include_extensions:
            location["object_id"] = self.object_id
            location["score"] = f"{self.score:.3f}"
        return {
            "device": device,
            "location": location,
        }


@dataclass
class PlaneFrame:
    origin: np.ndarray
    x_axis: np.ndarray
    y_axis: np.ndarray
    normal: np.ndarray
    inlier_mask: np.ndarray

    @property
    def rotation(self) -> np.ndarray:
        return np.column_stack((self.x_axis, self.y_axis, self.normal))

    def to_local(self, points: np.ndarray) -> np.ndarray:
        return (points - self.origin) @ self.rotation

    def to_camera(self, local_points: np.ndarray) -> np.ndarray:
        return self.origin + local_points @ self.rotation.T


class ParcelVisionPipeline:
    def __init__(self, config: Optional[ParcelVisionConfig] = None):
        self.config = config or ParcelVisionConfig()

    def process(
        self,
        points_xyz: np.ndarray,
        camera_to_robot: Optional[np.ndarray] = None,
    ) -> list[ParcelDetection]:
        points = _validate_points(points_xyz)
        frame = self.fit_conveyor_plane(points)
        local = frame.to_local(points)
        object_mask = (
            (local[:, 2] >= self.config.min_height)
            & (local[:, 2] <= self.config.max_height)
        )
        if self.config.roi_xy is not None:
            xmin, xmax, ymin, ymax = self.config.roi_xy
            object_mask &= (
                (local[:, 0] >= xmin)
                & (local[:, 0] <= xmax)
                & (local[:, 1] >= ymin)
                & (local[:, 1] <= ymax)
            )

        object_indices = np.flatnonzero(object_mask)
        if object_indices.size == 0:
            return []

        labels, grid_origin, point_cells = self._segment_height_map(local[object_mask])
        point_labels = labels[point_cells[:, 1], point_cells[:, 0]]
        detections: list[ParcelDetection] = []
        for label_id in range(1, int(labels.max()) + 1):
            selected = object_indices[point_labels == label_id]
            if selected.size < 4:
                continue
            parcel_local = local[selected]
            detection = self._measure_parcel(
                parcel_local, frame, labels == label_id, grid_origin, label_id
            )
            if detection is not None and detection.score >= self.config.min_detection_score:
                detections.append(detection)

        detections.sort(key=lambda item: (-item.score, -item.height, item.object_id))
        for index, detection in enumerate(detections, start=1):
            detection.object_id = f"pkg_{index:04d}"
        if camera_to_robot is not None:
            detections = [item.transformed(camera_to_robot) for item in detections]
        return detections

    def process_labeled_instances(
        self,
        points_xyz: np.ndarray,
        instance_labels: np.ndarray,
        camera_to_robot: Optional[np.ndarray] = None,
    ) -> list[ParcelDetection]:
        raw_points = np.asarray(points_xyz, dtype=float)
        labels = np.asarray(instance_labels)
        if raw_points.ndim != 2 or raw_points.shape[1] < 3:
            raise ValueError("points_xyz must have shape (N, 3) or (N, >=3)")
        if labels.ndim != 1 or len(labels) != len(raw_points):
            raise ValueError("instance_labels must have shape (N,)")
        finite = np.isfinite(raw_points[:, :3]).all(axis=1)
        points = raw_points[finite, :3]
        labels = labels[finite]
        if len(points) < 100:
            raise ValueError("Point cloud needs at least 100 finite XYZ points")

        frame = self.fit_conveyor_plane(points)
        local = frame.to_local(points)
        detections: list[ParcelDetection] = []
        for instance_id in np.unique(labels[labels > 0]):
            selected = labels == instance_id
            selected &= (
                (local[:, 2] >= self.config.min_height)
                & (local[:, 2] <= self.config.max_height)
            )
            parcel_local = local[selected]
            if len(parcel_local) < 4:
                continue
            component_mask, grid_origin = self._instance_component_mask(parcel_local)
            detection = self._measure_parcel(
                parcel_local, frame, component_mask, grid_origin, int(instance_id)
            )
            if detection is None or detection.score < self.config.min_detection_score:
                continue
            detection.object_id = f"instance_{int(instance_id):04d}"
            detections.append(detection)

        detections.sort(key=lambda item: (-item.score, -item.height, item.object_id))
        if camera_to_robot is not None:
            detections = [item.transformed(camera_to_robot) for item in detections]
        return detections

    def _instance_component_mask(
        self, parcel_local: np.ndarray
    ) -> tuple[np.ndarray, np.ndarray]:
        grid = self.config.grid_size
        grid_origin = parcel_local[:, :2].min(axis=0) - grid * 2
        cells = np.floor((parcel_local[:, :2] - grid_origin) / grid).astype(int)
        width, height = cells.max(axis=0) + 3
        component = np.zeros((height, width), dtype=bool)
        component[cells[:, 1], cells[:, 0]] = True
        radius = self.config.morphology_radius
        if radius > 0:
            structure = np.ones((2 * radius + 1, 2 * radius + 1), dtype=bool)
            component = ndimage.binary_closing(component, structure=structure)
            # An instance-mask hole may be an occluding parcel, not missing
            # depth. Keep large holes excluded from suction-point selection.
        return component, grid_origin

    def fit_conveyor_plane(self, points: np.ndarray) -> PlaneFrame:
        cfg = self.config
        rng = np.random.default_rng(cfg.random_seed)
        sample_points = points
        if len(points) > 30_000:
            sample_points = points[rng.choice(len(points), 30_000, replace=False)]

        best_mask: Optional[np.ndarray] = None
        best_count = 0
        for _ in range(cfg.plane_ransac_iterations):
            triple = sample_points[rng.choice(len(sample_points), 3, replace=False)]
            normal = np.cross(triple[1] - triple[0], triple[2] - triple[0])
            norm = np.linalg.norm(normal)
            if norm < 1e-8:
                continue
            normal /= norm
            distance = np.abs((sample_points - triple[0]) @ normal)
            mask = distance <= cfg.plane_distance_threshold
            count = int(mask.sum())
            if count > best_count:
                best_count = count
                best_mask = mask

        if best_mask is None or best_count < max(50, len(sample_points) * 0.05):
            raise ValueError("Could not find a dominant conveyor plane")

        plane_points = sample_points[best_mask]
        origin = plane_points.mean(axis=0)
        _, _, vh = np.linalg.svd(plane_points - origin, full_matrices=False)
        normal = vh[-1]
        # For an overhead camera at the origin, positive height points towards it.
        if np.dot(normal, -origin) < 0:
            normal = -normal

        full_distance = np.abs((points - origin) @ normal)
        inlier_mask = full_distance <= cfg.plane_distance_threshold
        x_reference = np.array([1.0, 0.0, 0.0])
        x_axis = x_reference - np.dot(x_reference, normal) * normal
        if np.linalg.norm(x_axis) < 0.2:
            x_reference = np.array([0.0, 1.0, 0.0])
            x_axis = x_reference - np.dot(x_reference, normal) * normal
        x_axis /= np.linalg.norm(x_axis)
        y_axis = np.cross(normal, x_axis)
        y_axis /= np.linalg.norm(y_axis)
        return PlaneFrame(origin, x_axis, y_axis, normal, inlier_mask)

    def _segment_height_map(
        self, object_points: np.ndarray
    ) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        grid = self.config.grid_size
        xy_min = object_points[:, :2].min(axis=0) - grid * 2
        cells = np.floor((object_points[:, :2] - xy_min) / grid).astype(int)
        width, height = cells.max(axis=0) + 3
        occupancy = np.zeros((height, width), dtype=bool)
        occupancy[cells[:, 1], cells[:, 0]] = True
        height_map = np.full((height, width), -np.inf)
        np.maximum.at(height_map, (cells[:, 1], cells[:, 0]), object_points[:, 2])
        raw_occupancy = occupancy.copy()

        radius = self.config.morphology_radius
        if radius > 0:
            structure = np.ones((2 * radius + 1, 2 * radius + 1), dtype=bool)
            occupancy = ndimage.binary_closing(occupancy, structure=structure)
            occupancy = ndimage.binary_fill_holes(occupancy)
        if self.config.segmentation_method == "connected":
            labels, _ = ndimage.label(occupancy, structure=np.ones((3, 3), dtype=int))
        elif self.config.segmentation_method == "height_edges":
            labels = self._label_height_surfaces(occupancy, raw_occupancy, height_map)
        else:
            raise ValueError(
                f"Unknown segmentation_method: {self.config.segmentation_method}"
            )

        cell_area = grid * grid
        counts = np.bincount(labels.ravel())
        valid = np.flatnonzero(
            (counts * cell_area >= self.config.min_area)
            & (counts * cell_area <= self.config.max_area)
        )
        valid = valid[valid != 0]
        remap = np.zeros(len(counts), dtype=np.int32)
        remap[valid] = np.arange(1, len(valid) + 1)
        return remap[labels], xy_min, cells

    def _label_height_surfaces(
        self,
        occupancy: np.ndarray,
        raw_occupancy: np.ndarray,
        height_map: np.ndarray,
    ) -> np.ndarray:
        # Closing creates cells without measured depth. Give them the height of
        # the nearest observed cell before comparing neighboring surfaces.
        _, nearest = ndimage.distance_transform_edt(
            ~raw_occupancy, return_indices=True
        )
        filled_height = height_map.copy()
        missing = ~raw_occupancy
        filled_height[missing] = height_map[tuple(nearest[:, missing])]

        cell_ids = np.full(occupancy.shape, -1, dtype=np.int32)
        cell_ids[occupancy] = np.arange(int(occupancy.sum()), dtype=np.int32)
        graph_rows: list[np.ndarray] = []
        graph_cols: list[np.ndarray] = []
        height_limit = self.config.height_edge_threshold
        height, width = occupancy.shape
        for dy, dx in ((0, 1), (1, 0), (1, 1), (1, -1)):
            first = (
                slice(0, height - dy),
                slice(max(0, -dx), width - max(0, dx)),
            )
            second = (
                slice(dy, height),
                slice(max(0, dx), width - max(0, -dx)),
            )
            neighbors = (
                occupancy[first]
                & occupancy[second]
                & (np.abs(filled_height[first] - filled_height[second]) <= height_limit)
            )
            source = cell_ids[first][neighbors]
            target = cell_ids[second][neighbors]
            graph_rows.extend((source, target))
            graph_cols.extend((target, source))

        labels = np.zeros(occupancy.shape, dtype=np.int32)
        occupied_count = int(occupancy.sum())
        if occupied_count == 0:
            return labels
        if graph_rows:
            rows = np.concatenate(graph_rows)
            cols = np.concatenate(graph_cols)
            graph = coo_matrix(
                (np.ones(len(rows), dtype=np.uint8), (rows, cols)),
                shape=(occupied_count, occupied_count),
            )
            _, components = connected_components(graph, directed=False)
        else:
            components = np.arange(occupied_count, dtype=np.int32)
        labels[occupancy] = components + 1
        return labels

    def _measure_parcel(
        self,
        parcel_local: np.ndarray,
        frame: PlaneFrame,
        component_mask: np.ndarray,
        grid_origin: np.ndarray,
        label_id: int,
    ) -> Optional[ParcelDetection]:
        xy = parcel_local[:, :2]
        center_xy, length, width, yaw = minimum_area_rectangle(xy)
        height = float(np.percentile(parcel_local[:, 2], 90))
        if not (self.config.min_height <= height <= self.config.max_height):
            return None

        grasp_xy, edge_distance = self._choose_grasp_xy(
            parcel_local, component_mask, grid_origin, center_xy
        )
        distances = np.linalg.norm(xy - grasp_xy, axis=1)
        local_top = parcel_local[distances <= self.config.local_flatness_radius, 2]
        if local_top.size < 4:
            local_top = parcel_local[:, 2]
        grasp_height = float(np.median(local_top))
        roughness = float(np.std(local_top))

        center_camera = frame.to_camera(np.array([*center_xy, height / 2.0]))
        grasp_camera = frame.to_camera(np.array([*grasp_xy, grasp_height]))
        yaw_radians = np.radians(yaw)
        local_rotation = np.array(
            [
                [np.cos(yaw_radians), -np.sin(yaw_radians), 0.0],
                [np.sin(yaw_radians), np.cos(yaw_radians), 0.0],
                [0.0, 0.0, 1.0],
            ]
        )
        rotation_camera = frame.rotation @ local_rotation
        edge_score = np.clip(edge_distance / max(self.config.suction_radius, 1.0), 0, 1)
        flat_score = np.clip(1.0 - roughness / max(self.config.max_local_roughness, 1.0), 0, 1)
        density_score = np.clip(len(parcel_local) / 100.0, 0, 1)
        score = float(0.45 * edge_score + 0.4 * flat_score + 0.15 * density_score)
        return ParcelDetection(
            object_id=f"component_{label_id}",
            center_camera=center_camera,
            grasp_camera=grasp_camera,
            rotation_camera=rotation_camera,
            length=length,
            width=width,
            height=height,
            angle_z=yaw,
            score=score,
            point_count=len(parcel_local),
        )

    def _choose_grasp_xy(
        self,
        parcel_local: np.ndarray,
        component_mask: np.ndarray,
        grid_origin: np.ndarray,
        center_xy: np.ndarray,
    ) -> tuple[np.ndarray, float]:
        distance = ndimage.distance_transform_edt(component_mask) * self.config.grid_size
        maximum = float(distance.max())
        # Rectangles often have a line of equally safe points. Pick the candidate
        # nearest the parcel centre so small point-cloud holes do not move the grip.
        candidates = np.argwhere(distance >= maximum - self.config.grid_size)
        candidate_xy = grid_origin + (candidates[:, ::-1] + 0.5) * self.config.grid_size
        selected = int(np.argmin(np.linalg.norm(candidate_xy - center_xy, axis=1)))
        row, col = candidates[selected]
        xy = grid_origin + (np.array([col, row]) + 0.5) * self.config.grid_size
        return xy, float(distance[row, col])


def minimum_area_rectangle(points_xy: np.ndarray) -> tuple[np.ndarray, float, float, float]:
    points = np.asarray(points_xy, dtype=float)
    if len(points) < 3:
        raise ValueError("At least three points are required")
    try:
        hull = points[ConvexHull(points).vertices]
    except Exception:
        center = points.mean(axis=0)
        return center, 0.0, 0.0, 0.0

    edges = np.diff(np.vstack((hull, hull[0])), axis=0)
    angles = np.unique(np.mod(np.arctan2(edges[:, 1], edges[:, 0]), np.pi / 2.0))
    best = None
    for angle in angles:
        c, s = np.cos(angle), np.sin(angle)
        rotation = np.array([[c, s], [-s, c]])
        rotated = points @ rotation.T
        minimum = rotated.min(axis=0)
        maximum = rotated.max(axis=0)
        dimensions = maximum - minimum
        area = dimensions[0] * dimensions[1]
        if best is None or area < best[0]:
            center_rotated = (minimum + maximum) / 2.0
            center = center_rotated @ rotation
            best = (area, center, dimensions, angle)

    assert best is not None
    _, center, dimensions, angle = best
    if dimensions[1] > dimensions[0]:
        dimensions = dimensions[::-1]
        angle += np.pi / 2.0
    yaw = ((np.degrees(angle) + 90.0) % 180.0) - 90.0
    return center, float(dimensions[0]), float(dimensions[1]), float(yaw)


def rotation_matrix_to_euler_xyz(rotation: np.ndarray) -> tuple[float, float, float]:
    r = np.asarray(rotation, dtype=float)
    pitch = np.arcsin(np.clip(-r[2, 0], -1.0, 1.0))
    if abs(np.cos(pitch)) > 1e-7:
        roll = np.arctan2(r[2, 1], r[2, 2])
        yaw = np.arctan2(r[1, 0], r[0, 0])
    else:
        roll = np.arctan2(-r[1, 2], r[1, 1])
        yaw = 0.0
    return tuple(float(value) for value in np.degrees([roll, pitch, yaw]))


def _validate_points(points_xyz: np.ndarray) -> np.ndarray:
    points = np.asarray(points_xyz, dtype=float)
    if points.ndim != 2 or points.shape[1] < 3:
        raise ValueError("points_xyz must have shape (N, 3) or (N, >=3)")
    points = points[:, :3]
    points = points[np.isfinite(points).all(axis=1)]
    if len(points) < 100:
        raise ValueError("Point cloud needs at least 100 finite XYZ points")
    return points
