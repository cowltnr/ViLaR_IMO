"""Safety preflight between inspection JSON and the future Isaac runtime.

This module validates recorded source approaches only. It never queries or
mutates Isaac Sim, USD, People, NavMesh, ROS2, or timeline state.
"""

from dataclasses import dataclass
import math


@dataclass(frozen=True)
class SourceApproach:
    box_id: str
    navmesh_point: tuple
    path_points: tuple
    snap_distance_m: float
    box_horizontal_distance_m: float


def _point(value):
    if value is None or len(value) != 3:
        return None
    value = tuple(float(x) for x in value)
    return value if all(math.isfinite(x) for x in value) else None


def collect_source_approaches(report, box_ids, *, max_snap_distance_m=.15):
    """Return deterministic source candidates or a blocking reason.

    A connected NavMesh probe is necessary but not sufficient for extraction;
    callers must still run clearance and arm-reach checks before movement.
    """
    if report.get('stage_modified'):
        return (), 'stage_modified_during_inspection'
    if report.get('navmesh', {}).get('status') != 'queried_not_motion_validated':
        return (), 'navmesh_not_available_for_preflight'
    entries = {entry.get('path'): entry for entry in report.get('source_approaches', [])}
    result = []
    for box_id in tuple(box_ids):
        entry = entries.get(box_id)
        if not entry or entry.get('status') != 'connected_probe_selected':
            return (), f'no_connected_source_approach:{box_id}'
        point = _point(entry.get('navmesh_point'))
        path = tuple(_point(p) for p in entry.get('path_points', ()))
        if point is None or not path or any(p is None for p in path):
            return (), f'invalid_source_path:{box_id}'
        snap = float(entry.get('snap_distance_m', math.inf))
        distance = float(entry.get('box_horizontal_distance_m', math.inf))
        if not all(math.isfinite(x) and x >= 0 for x in (snap, distance)):
            return (), f'invalid_source_distance:{box_id}'
        if snap > max_snap_distance_m:
            return (), f'source_snap_too_far:{box_id}'
        result.append(SourceApproach(box_id, point, path, snap, distance))
    return tuple(result), None
