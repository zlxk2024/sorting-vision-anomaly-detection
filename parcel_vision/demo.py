from __future__ import annotations

import numpy as np


def make_synthetic_scene(seed: int = 11) -> tuple[np.ndarray, list[dict]]:
    """Create an overhead-camera scene in millimetres for tests and demos."""
    rng = np.random.default_rng(seed)
    belt_x, belt_y = np.meshgrid(
        np.arange(-600.0, 601.0, 20.0), np.arange(-400.0, 401.0, 20.0)
    )
    belt = np.column_stack((belt_x.ravel(), belt_y.ravel(), np.full(belt_x.size, 1000.0)))
    expected = [
        {"center": (-310.0, -170.0), "length": 300.0, "width": 180.0, "height": 120.0, "yaw": 0.0},
        {"center": (230.0, -120.0), "length": 280.0, "width": 150.0, "height": 80.0, "yaw": 28.0},
        {"center": (20.0, 230.0), "length": 220.0, "width": 120.0, "height": 45.0, "yaw": -18.0},
    ]
    clouds = [belt]
    for parcel in expected:
        clouds.append(_box_top(rng=rng, **parcel))
    points = np.vstack(clouds)
    points += rng.normal(0.0, 0.7, points.shape)
    return points, expected


def _box_top(
    center: tuple[float, float],
    length: float,
    width: float,
    height: float,
    yaw: float,
    rng: np.random.Generator,
) -> np.ndarray:
    xs, ys = np.meshgrid(
        np.arange(-length / 2.0, length / 2.0 + 1.0, 8.0),
        np.arange(-width / 2.0, width / 2.0 + 1.0, 8.0),
    )
    local = np.column_stack((xs.ravel(), ys.ravel()))
    angle = np.radians(yaw)
    rotation = np.array([[np.cos(angle), -np.sin(angle)], [np.sin(angle), np.cos(angle)]])
    xy = local @ rotation.T + np.asarray(center)
    z = np.full((len(xy), 1), 1000.0 - height)
    keep = rng.random(len(xy)) > 0.03
    return np.column_stack((xy, z))[keep]
