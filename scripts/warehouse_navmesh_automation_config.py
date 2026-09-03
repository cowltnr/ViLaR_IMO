"""Pure geometry and safety rules for Warehouse NavMesh automation."""

from __future__ import annotations

import math
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from typing import Any, Callable


Vector3 = tuple[float, float, float]


def _vector3(value: Sequence[float], name: str) -> Vector3:
    if len(value) != 3:
        raise ValueError(f"{name} must contain exactly three values")
    result = (float(value[0]), float(value[1]), float(value[2]))
    if not all(math.isfinite(component) for component in result):
        raise ValueError(f"{name} values must be finite")
    return result


@dataclass(frozen=True)
class Bounds3D:
    minimum: Vector3
    maximum: Vector3

    def __post_init__(self) -> None:
        minimum = _vector3(self.minimum, "minimum")
        maximum = _vector3(self.maximum, "maximum")
        if any(high <= low for low, high in zip(minimum, maximum)):
            raise ValueError("maximum values must be greater than minimum values")
        object.__setattr__(self, "minimum", minimum)
        object.__setattr__(self, "maximum", maximum)

    @property
    def size(self) -> Vector3:
        return tuple(
            high - low for low, high in zip(self.minimum, self.maximum)
        )  # type: ignore[return-value]


@dataclass(frozen=True)
class FloorCandidate:
    path: str
    bounds: Bounds3D

    def __post_init__(self) -> None:
        if not self.path:
            raise ValueError("floor candidate path must not be empty")


@dataclass(frozen=True)
class InteriorSelection:
    status: str
    candidate: FloorCandidate | None
    reasons: tuple[str, ...]


@dataclass(frozen=True)
class SceneSnapshot:
    """Read-only values collected from an open Isaac Sim stage."""

    stage_identifier: str
    meters_per_unit: float
    up_axis: str
    timeline_state: str
    warehouse_bounds: Bounds3D
    volume_bounds: Bounds3D
    volume_center: Vector3
    volume_scale: Vector3
    worker_position: Vector3
    cart_bounds: Bounds3D
    floor_candidates: tuple[FloorCandidate, ...]
    static_structure_paths: tuple[str, ...]
    dynamic_root_paths: tuple[str, ...]
    warehouse_excluded_paths: tuple[str, ...]
    current_settings: tuple[tuple[str, float | bool], ...]

    def __post_init__(self) -> None:
        if not self.stage_identifier:
            raise ValueError("stage_identifier must not be empty")
        meters_per_unit = float(self.meters_per_unit)
        if not math.isfinite(meters_per_unit) or meters_per_unit <= 0:
            raise ValueError("meters_per_unit must be positive and finite")
        object.__setattr__(self, "meters_per_unit", meters_per_unit)
        object.__setattr__(self, "volume_center", _vector3(self.volume_center, "volume_center"))
        object.__setattr__(self, "volume_scale", _vector3(self.volume_scale, "volume_scale"))
        object.__setattr__(
            self, "worker_position", _vector3(self.worker_position, "worker_position")
        )


@dataclass
class NavMeshApplyController:
    """Run the synchronous part of Apply as a rollback-capable transaction."""

    apply_allowed: bool
    capture_snapshot: Callable[[], Any]
    apply_changes: Callable[[Any], None]
    start_bake: Callable[[], Any]
    restore_changes: Callable[[Any], None]

    def run(self) -> Any:
        if not self.apply_allowed:
            raise ValueError("Preview does not allow Apply")

        snapshot = self.capture_snapshot()
        try:
            self.apply_changes(snapshot)
            return self.start_bake()
        except Exception as apply_error:
            try:
                self.restore_changes(snapshot)
            except Exception as restore_error:
                raise RuntimeError(
                    f"Apply failed and restore also failed: {restore_error}"
                ) from apply_error
            raise


def calculate_agent_radius_cm(
    cart_bounds: Bounds3D,
    meters_per_unit: float,
    margin_cm: float = 10.0,
    minimum_cm: float = 20.0,
    maximum_cm: float = 80.0,
) -> float:
    """Return half the cart width plus a clearance margin, in centimeters."""

    meters_per_unit = float(meters_per_unit)
    margin_cm = float(margin_cm)
    if not math.isfinite(meters_per_unit) or meters_per_unit <= 0:
        raise ValueError("meters_per_unit must be positive and finite")
    if not math.isfinite(margin_cm) or margin_cm < 0:
        raise ValueError("margin_cm must be non-negative and finite")
    if minimum_cm > maximum_cm:
        raise ValueError("minimum_cm must not exceed maximum_cm")

    width_stage_units = min(cart_bounds.size[0], cart_bounds.size[1])
    radius_cm = width_stage_units * meters_per_unit * 100.0 / 2.0 + margin_cm
    if not minimum_cm <= radius_cm <= maximum_cm:
        raise ValueError(
            f"calculated radius {radius_cm:.3f}cm is outside "
            f"the supported {minimum_cm:.1f}–{maximum_cm:.1f}cm range"
        )
    return radius_cm


def select_interior_floor(
    candidates: Iterable[FloorCandidate],
    worker_position: Sequence[float],
    volume_bounds: Bounds3D,
    meters_per_unit: float,
    max_floor_delta_m: float = 0.5,
) -> InteriorSelection:
    """Select a unique floor containing the worker and smaller than the volume."""

    worker = _vector3(worker_position, "worker_position")
    meters_per_unit = float(meters_per_unit)
    max_floor_delta_m = float(max_floor_delta_m)
    if not math.isfinite(meters_per_unit) or meters_per_unit <= 0:
        raise ValueError("meters_per_unit must be positive and finite")
    if not math.isfinite(max_floor_delta_m) or max_floor_delta_m < 0:
        raise ValueError("max_floor_delta_m must be non-negative and finite")

    matches: list[FloorCandidate] = []
    volume_size = volume_bounds.size
    for candidate in candidates:
        bounds = candidate.bounds
        contains_worker_xy = all(
            low <= position <= high
            for low, position, high in zip(
                bounds.minimum[:2], worker[:2], bounds.maximum[:2]
            )
        )
        floor_near_feet = (
            abs(bounds.maximum[2] - worker[2]) * meters_per_unit
            <= max_floor_delta_m
        )
        candidate_size = bounds.size
        smaller_than_volume = (
            candidate_size[0] < volume_size[0]
            and candidate_size[1] < volume_size[1]
        )
        if contains_worker_xy and floor_near_feet and smaller_than_volume:
            matches.append(candidate)

    if len(matches) == 1:
        return InteriorSelection("selected", matches[0], ())
    if not matches:
        return InteriorSelection("ambiguous", None, ("no floor candidate matched",))
    return InteriorSelection(
        "ambiguous", None, (f"{len(matches)} floor candidates matched",)
    )


def replace_volume_xy(
    interior_bounds: Bounds3D,
    current_center: Sequence[float],
    current_scale: Sequence[float],
    inset: float = 0.0,
) -> tuple[Vector3, Vector3]:
    """Replace a volume's XY extent while preserving its current Z transform."""

    center = _vector3(current_center, "current_center")
    scale = _vector3(current_scale, "current_scale")
    inset = float(inset)
    if any(component <= 0 for component in scale):
        raise ValueError("current_scale values must be positive")
    if not math.isfinite(inset) or inset < 0:
        raise ValueError("inset must be non-negative and finite")

    size = interior_bounds.size
    next_size_x = size[0] - 2.0 * inset
    next_size_y = size[1] - 2.0 * inset
    if next_size_x <= 0 or next_size_y <= 0:
        raise ValueError("inset must leave a positive XY floor area")

    next_center = (
        (interior_bounds.minimum[0] + interior_bounds.maximum[0]) / 2.0,
        (interior_bounds.minimum[1] + interior_bounds.maximum[1]) / 2.0,
        center[2],
    )
    next_scale = (next_size_x, next_size_y, scale[2])
    return next_center, next_scale


def validate_explicit_interior_bounds(
    interior_bounds: Bounds3D,
    warehouse_bounds: Bounds3D,
    volume_bounds: Bounds3D,
    worker_position: Sequence[float],
) -> Bounds3D:
    """Reject manually supplied XY bounds that can expand beyond safe scope."""

    worker = _vector3(worker_position, "worker_position")
    inside_warehouse = all(
        outer_low <= inner_low and inner_high <= outer_high
        for outer_low, inner_low, inner_high, outer_high in zip(
            warehouse_bounds.minimum[:2],
            interior_bounds.minimum[:2],
            interior_bounds.maximum[:2],
            warehouse_bounds.maximum[:2],
        )
    )
    if not inside_warehouse:
        raise ValueError("interior_bounds must stay inside Warehouse XY")

    contains_worker = all(
        low <= position <= high
        for low, position, high in zip(
            interior_bounds.minimum[:2], worker[:2], interior_bounds.maximum[:2]
        )
    )
    if not contains_worker:
        raise ValueError("interior_bounds must contain Worker XY")

    interior_size = interior_bounds.size
    volume_size = volume_bounds.size
    if interior_size[0] > volume_size[0] or interior_size[1] > volume_size[1]:
        raise ValueError("interior_bounds must not expand current Volume XY")
    return interior_bounds
