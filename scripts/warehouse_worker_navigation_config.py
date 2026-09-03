"""Pure calculations shared by the Isaac Sim worker-navigation setup."""

from __future__ import annotations

import math
from collections.abc import Sequence


Vector3 = tuple[float, float, float]


def _vector3(value: Sequence[float], name: str) -> Vector3:
    if len(value) != 3:
        raise ValueError(f"{name} must contain exactly three values")
    return float(value[0]), float(value[1]), float(value[2])


def camera_target_distance(position: Sequence[float], target: Sequence[float]) -> float:
    """Return Euclidean distance between a viewport camera and its target."""

    camera_position = _vector3(position, "position")
    camera_target = _vector3(target, "target")
    return math.dist(camera_position, camera_target)


def compute_navmesh_transform(
    minimum: Sequence[float],
    maximum: Sequence[float],
    floor_z: float,
    margin_xy: float,
    below_floor: float,
    height: float,
) -> tuple[Vector3, Vector3]:
    """Compute center and scale for an axis-aligned, one-meter NavMeshVolume."""

    lower = _vector3(minimum, "minimum")
    upper = _vector3(maximum, "maximum")
    if any(high <= low for low, high in zip(lower, upper)):
        raise ValueError("maximum values must be greater than minimum values")
    if margin_xy < 0 or below_floor < 0 or height <= 0:
        raise ValueError("margins must be non-negative and height must be positive")

    min_x = lower[0] - margin_xy
    max_x = upper[0] + margin_xy
    min_y = lower[1] - margin_xy
    max_y = upper[1] + margin_xy
    min_z = float(floor_z) - below_floor
    max_z = float(floor_z) + height

    center = (
        (min_x + max_x) / 2.0,
        (min_y + max_y) / 2.0,
        (min_z + max_z) / 2.0,
    )
    scale = (max_x - min_x, max_y - min_y, max_z - min_z)
    return center, scale
