"""Preview and configure Warehouse NavMesh from Isaac Sim's Script Editor.

Importing this module outside Isaac Sim is safe. Isaac-specific modules are
loaded only by the live-stage entry points.
"""

from __future__ import annotations

import asyncio
import builtins
import json
import math
import traceback
from dataclasses import dataclass
from typing import Any

from scripts.warehouse_navmesh_automation_config import (
    Bounds3D,
    FloorCandidate,
    NavMeshApplyController,
    SceneSnapshot,
    calculate_agent_radius_cm,
    replace_volume_xy,
    select_interior_floor,
    validate_explicit_interior_bounds,
)


WAREHOUSE_PATH = "/World/Environment/Warehouse"
VOLUME_PATH = "/World/NavMeshVolume"
WORKER_PATH = "/World/Characters/Worker_01"
CART_PATH = "/World/DynamicActors/CartAssembly"
DYNAMIC_ROOT_PATHS = ("/World/Characters", "/World/DynamicActors")
_HANDLE_NAME = "_warehouse_navmesh_automation_handle"


def _bounds_dict(bounds: Bounds3D) -> dict[str, list[float]]:
    return {
        "minimum": list(bounds.minimum),
        "maximum": list(bounds.maximum),
    }


def _candidate_dict(candidate: FloorCandidate | None) -> dict[str, Any] | None:
    if candidate is None:
        return None
    return {"path": candidate.path, "bounds": _bounds_dict(candidate.bounds)}


def build_preview_report(scene: SceneSnapshot) -> dict[str, Any]:
    """Build a JSON-compatible report without changing stage or settings."""

    selection = select_interior_floor(
        scene.floor_candidates,
        scene.worker_position,
        scene.volume_bounds,
        scene.meters_per_unit,
    )
    blocking_reasons: list[str] = []
    if scene.timeline_state != "stopped":
        blocking_reasons.append("timeline must be stopped")
    if scene.up_axis.upper() != "Z":
        blocking_reasons.append("stage up axis must be Z")
    blocking_reasons.extend(selection.reasons)
    if scene.warehouse_excluded_paths:
        blocking_reasons.append("Warehouse contains NavMeshExcludeAPI")

    proposed_radius_cm: float | None
    try:
        proposed_radius_cm = calculate_agent_radius_cm(
            scene.cart_bounds, scene.meters_per_unit
        )
    except ValueError as error:
        proposed_radius_cm = None
        blocking_reasons.append(str(error))

    proposed_volume = None
    if selection.candidate is not None:
        center, scale = replace_volume_xy(
            selection.candidate.bounds,
            scene.volume_center,
            scene.volume_scale,
        )
        proposed_volume = {"translate": list(center), "scale": list(scale)}

    return {
        "stage_identifier": scene.stage_identifier,
        "meters_per_unit": scene.meters_per_unit,
        "up_axis": scene.up_axis,
        "timeline_state": scene.timeline_state,
        "warehouse_bounds": _bounds_dict(scene.warehouse_bounds),
        "current_volume": {
            "bounds": _bounds_dict(scene.volume_bounds),
            "translate": list(scene.volume_center),
            "scale": list(scene.volume_scale),
        },
        "worker_position": list(scene.worker_position),
        "cart_local_bounds": _bounds_dict(scene.cart_bounds),
        "floor_candidates": [
            _candidate_dict(candidate) for candidate in scene.floor_candidates
        ],
        "static_structure_paths": list(scene.static_structure_paths),
        "dynamic_exclusion_paths": list(scene.dynamic_root_paths),
        "warehouse_excluded_paths": list(scene.warehouse_excluded_paths),
        "current_settings": dict(scene.current_settings),
        "proposed_agent_radius_cm": proposed_radius_cm,
        "proposed_volume": proposed_volume,
        "interior_selection": {
            "status": selection.status,
            "candidate": _candidate_dict(selection.candidate),
            "reasons": list(selection.reasons),
        },
        "blocking_reasons": blocking_reasons,
        "apply_allowed": not blocking_reasons,
    }


def preview() -> dict[str, Any]:
    """Read the open stage and print one machine-readable Preview line."""

    scene = _read_live_scene()
    report = build_preview_report(scene)
    print("WAREHOUSE_NAVMESH_PREVIEW=" + json.dumps(report, sort_keys=True))
    return report


def run(mode: str = "preview", interior_bounds=None):
    """Script Editor entry point. Preview is synchronous; Apply returns a task."""

    if mode == "preview":
        if interior_bounds is not None:
            raise ValueError("interior_bounds is only valid in Apply mode")
        return preview()
    if mode == "apply":
        return apply_and_bake(interior_bounds)
    raise ValueError("mode must be 'preview' or 'apply'")


def _read_live_scene() -> SceneSnapshot:
    import carb.settings
    import NavSchema
    import omni.timeline
    import omni.usd
    from omni.anim.navigation.core import NavMeshSettings
    from pxr import Usd, UsdGeom

    context = omni.usd.get_context()
    stage = context.get_stage()
    if stage is None:
        raise RuntimeError("no stage is open")

    timeline = omni.timeline.get_timeline_interface()
    if timeline.is_stopped():
        timeline_state = "stopped"
    elif timeline.is_playing():
        timeline_state = "playing"
    else:
        timeline_state = "paused"

    def require_prim(path: str):
        prim = stage.GetPrimAtPath(path)
        if not prim or not prim.IsValid():
            raise RuntimeError(f"required prim not found: {path}")
        return prim

    warehouse = require_prim(WAREHOUSE_PATH)
    volume = require_prim(VOLUME_PATH)
    worker = require_prim(WORKER_PATH)
    cart = require_prim(CART_PATH)
    dynamic_roots = tuple(
        path
        for path in DYNAMIC_ROOT_PATHS
        if stage.GetPrimAtPath(path) and stage.GetPrimAtPath(path).IsValid()
    )
    if dynamic_roots != DYNAMIC_ROOT_PATHS:
        missing = sorted(set(DYNAMIC_ROOT_PATHS) - set(dynamic_roots))
        raise RuntimeError(f"required dynamic roots not found: {missing}")

    purposes = [UsdGeom.Tokens.default_, UsdGeom.Tokens.render, UsdGeom.Tokens.proxy]
    bbox_cache = UsdGeom.BBoxCache(
        Usd.TimeCode.Default(), purposes, useExtentsHint=True
    )

    def bounds_from_range(value, path: str) -> Bounds3D:
        if value.IsEmpty():
            raise RuntimeError(f"empty bounds: {path}")
        try:
            return Bounds3D(tuple(value.GetMin()), tuple(value.GetMax()))
        except ValueError as error:
            raise RuntimeError(f"invalid bounds for {path}: {error}") from error

    def world_bounds(prim) -> Bounds3D:
        value = bbox_cache.ComputeWorldBound(prim).ComputeAlignedRange()
        return bounds_from_range(value, str(prim.GetPath()))

    def local_bounds(prim) -> Bounds3D:
        value = bbox_cache.ComputeLocalBound(prim).ComputeAlignedRange()
        return bounds_from_range(value, str(prim.GetPath()))

    floor_candidates: list[FloorCandidate] = []
    static_structure_paths: list[str] = []
    warehouse_excluded_paths: list[str] = []
    floor_words = ("floor", "ground")
    structure_words = ("wall", "rack", "shelf", "obstacle", "barrier")
    for prim in Usd.PrimRange(warehouse):
        lower_name = prim.GetName().lower()
        if prim.HasAPI(NavSchema.NavMeshExcludeAPI):
            warehouse_excluded_paths.append(str(prim.GetPath()))
        if any(word in lower_name for word in structure_words):
            static_structure_paths.append(str(prim.GetPath()))
        if not any(word in lower_name for word in floor_words):
            continue
        try:
            floor_candidates.append(
                FloorCandidate(str(prim.GetPath()), world_bounds(prim))
            )
        except RuntimeError:
            # Empty or planar candidates are reported indirectly by an ambiguous
            # selection instead of making Preview mutate or guess at geometry.
            continue

    volume_translate = volume.GetAttribute("xformOp:translate").Get()
    volume_scale = volume.GetAttribute("xformOp:scale").Get()
    if volume_translate is None or volume_scale is None:
        raise RuntimeError(
            f"{VOLUME_PATH} must have xformOp:translate and xformOp:scale"
        )
    worker_matrix = UsdGeom.Xformable(worker).ComputeLocalToWorldTransform(
        Usd.TimeCode.Default()
    )

    settings = carb.settings.get_settings()

    def read_setting(primary_path: str, default_path: str):
        value = settings.get(primary_path)
        if value is None:
            value = settings.get(default_path)
        if value is None:
            raise RuntimeError(f"NavMesh setting is unavailable: {primary_path}")
        return value

    current_settings = (
        (
            "agent_height_cm",
            float(
                read_setting(
                    NavMeshSettings.AGENT_HEIGHT_SETTING_PATH,
                    NavMeshSettings.DEFAULT_AGENT_HEIGHT_SETTING_PATH,
                )
            ),
        ),
        (
            "agent_radius_cm",
            float(
                read_setting(
                    NavMeshSettings.AGENT_RADIUS_SETTING_PATH,
                    NavMeshSettings.DEFAULT_AGENT_RADIUS_SETTING_PATH,
                )
            ),
        ),
        (
            "agent_max_step_height_cm",
            float(
                read_setting(
                    NavMeshSettings.AGENT_MAX_STEP_HEIGHT_SETTING_PATH,
                    NavMeshSettings.DEFAULT_AGENT_MAX_STEP_HEIGHT_SETTING_PATH,
                )
            ),
        ),
        (
            "agent_max_floor_slope_degrees",
            float(
                read_setting(
                    NavMeshSettings.AGENT_MAX_FLOOR_SLOPE_SETTING_PATH,
                    NavMeshSettings.DEFAULT_AGENT_MAX_FLOOR_SLOPE_SETTING_PATH,
                )
            ),
        ),
        (
            "auto_rebake",
            bool(
                read_setting(
                    NavMeshSettings.AUTO_REBAKE_SETTING_PATH,
                    NavMeshSettings.DEFAULT_AUTO_REBAKE_SETTING_PATH,
                )
            ),
        ),
    )

    return SceneSnapshot(
        stage_identifier=stage.GetRootLayer().identifier,
        meters_per_unit=float(UsdGeom.GetStageMetersPerUnit(stage)),
        up_axis=str(UsdGeom.GetStageUpAxis(stage)),
        timeline_state=timeline_state,
        warehouse_bounds=world_bounds(warehouse),
        volume_bounds=world_bounds(volume),
        volume_center=tuple(volume_translate),
        volume_scale=tuple(volume_scale),
        worker_position=tuple(worker_matrix.ExtractTranslation()),
        cart_bounds=local_bounds(cart),
        floor_candidates=tuple(floor_candidates),
        static_structure_paths=tuple(sorted(set(static_structure_paths))),
        dynamic_root_paths=dynamic_roots,
        warehouse_excluded_paths=tuple(sorted(warehouse_excluded_paths)),
        current_settings=current_settings,
    )


@dataclass
class _LiveMutationSnapshot:
    volume_translate: tuple[float, float, float]
    volume_scale: tuple[float, float, float]
    setting_values: dict[str, Any]
    dynamic_exclusion_states: dict[str, bool]


class _LiveRestoreHandle:
    def __init__(self, snapshot: _LiveMutationSnapshot):
        self.snapshot = snapshot
        self.restored = False

    def restore(self) -> dict[str, Any]:
        if self.restored:
            return {"restored": True, "already_restored": True, "rebake_required": True}
        _restore_live_changes(self.snapshot)
        self.restored = True
        result = {"restored": True, "already_restored": False, "rebake_required": True}
        print("WAREHOUSE_NAVMESH_RESTORE=" + json.dumps(result, sort_keys=True))
        return result


def _coerce_interior_bounds(value) -> Bounds3D:
    if isinstance(value, Bounds3D):
        return value
    if not isinstance(value, (tuple, list)) or len(value) != 2:
        raise ValueError("interior_bounds must be Bounds3D or (minimum, maximum)")
    return Bounds3D(value[0], value[1])


def _settings_paths():
    from omni.anim.navigation.core import NavMeshSettings

    return (
        NavMeshSettings.AGENT_HEIGHT_SETTING_PATH,
        NavMeshSettings.AGENT_RADIUS_SETTING_PATH,
        NavMeshSettings.AGENT_MAX_STEP_HEIGHT_SETTING_PATH,
        NavMeshSettings.AGENT_MAX_FLOOR_SLOPE_SETTING_PATH,
        NavMeshSettings.AUTO_REBAKE_SETTING_PATH,
    )


def _capture_live_snapshot() -> _LiveMutationSnapshot:
    import carb.settings
    import NavSchema
    import omni.usd

    stage = omni.usd.get_context().get_stage()
    if stage is None:
        raise RuntimeError("no stage is open")
    volume = stage.GetPrimAtPath(VOLUME_PATH)
    if not volume or not volume.IsValid():
        raise RuntimeError(f"required prim not found: {VOLUME_PATH}")

    translate = volume.GetAttribute("xformOp:translate").Get()
    scale = volume.GetAttribute("xformOp:scale").Get()
    if translate is None or scale is None:
        raise RuntimeError(f"{VOLUME_PATH} transform is unavailable")

    settings = carb.settings.get_settings()
    setting_values = {path: settings.get(path) for path in _settings_paths()}
    exclusion_states = {}
    for path in DYNAMIC_ROOT_PATHS:
        prim = stage.GetPrimAtPath(path)
        if not prim or not prim.IsValid():
            raise RuntimeError(f"required prim not found: {path}")
        exclusion_states[path] = bool(prim.HasAPI(NavSchema.NavMeshExcludeAPI))

    return _LiveMutationSnapshot(
        volume_translate=tuple(float(value) for value in translate),
        volume_scale=tuple(float(value) for value in scale),
        setting_values=setting_values,
        dynamic_exclusion_states=exclusion_states,
    )


def _set_vec3_attribute(attribute, values) -> None:
    current_value = attribute.Get()
    if current_value is None:
        raise RuntimeError(f"attribute has no current value: {attribute.GetPath()}")
    typed_value = type(current_value)(*values)
    if not attribute.Set(typed_value):
        raise RuntimeError(f"failed to set attribute: {attribute.GetPath()}")


def _restore_live_changes(snapshot: _LiveMutationSnapshot) -> None:
    import carb.settings
    import NavSchema
    import omni.usd

    stage = omni.usd.get_context().get_stage()
    if stage is None:
        raise RuntimeError("cannot restore because no stage is open")
    volume = stage.GetPrimAtPath(VOLUME_PATH)
    if not volume or not volume.IsValid():
        raise RuntimeError(f"cannot restore missing prim: {VOLUME_PATH}")

    _set_vec3_attribute(
        volume.GetAttribute("xformOp:translate"), snapshot.volume_translate
    )
    _set_vec3_attribute(volume.GetAttribute("xformOp:scale"), snapshot.volume_scale)

    settings = carb.settings.get_settings()
    for path, value in snapshot.setting_values.items():
        if value is None:
            settings.destroy_item(path)
        else:
            settings.set(path, value)

    for path, was_excluded in snapshot.dynamic_exclusion_states.items():
        prim = stage.GetPrimAtPath(path)
        if not prim or not prim.IsValid():
            raise RuntimeError(f"cannot restore missing prim: {path}")
        is_excluded = bool(prim.HasAPI(NavSchema.NavMeshExcludeAPI))
        if was_excluded and not is_excluded:
            prim.ApplyAPI(NavSchema.NavMeshExcludeAPI)
        elif not was_excluded and is_excluded:
            prim.RemoveAPI(NavSchema.NavMeshExcludeAPI)


def _apply_live_changes(
    snapshot: _LiveMutationSnapshot,
    *,
    interior_bounds: Bounds3D,
    proposed_radius_cm: float,
) -> None:
    import carb.settings
    import NavSchema
    import omni.usd
    from omni.anim.navigation.core import NavMeshSettings

    stage = omni.usd.get_context().get_stage()
    if stage is None:
        raise RuntimeError("no stage is open")
    volume = stage.GetPrimAtPath(VOLUME_PATH)
    center, scale = replace_volume_xy(
        interior_bounds,
        snapshot.volume_translate,
        snapshot.volume_scale,
    )
    _set_vec3_attribute(volume.GetAttribute("xformOp:translate"), center)
    _set_vec3_attribute(volume.GetAttribute("xformOp:scale"), scale)

    for path in DYNAMIC_ROOT_PATHS:
        prim = stage.GetPrimAtPath(path)
        if not prim.HasAPI(NavSchema.NavMeshExcludeAPI):
            prim.ApplyAPI(NavSchema.NavMeshExcludeAPI)

    settings = carb.settings.get_settings()
    settings.set(NavMeshSettings.AGENT_HEIGHT_SETTING_PATH, 180.0)
    settings.set(NavMeshSettings.AGENT_RADIUS_SETTING_PATH, proposed_radius_cm)
    settings.set(NavMeshSettings.AUTO_REBAKE_SETTING_PATH, False)


def _allowed_with_explicit_bounds(report: dict[str, Any]) -> tuple[bool, list[str]]:
    selection_reasons = set(report["interior_selection"]["reasons"])
    remaining = [
        reason for reason in report["blocking_reasons"] if reason not in selection_reasons
    ]
    return not remaining, remaining


async def _bake_and_verify_async(
    worker_position,
    meters_per_unit: float,
    begin_transaction,
) -> dict[str, Any]:
    import omni.anim.navigation.core as nav

    interface = nav.acquire_interface()
    event_stream = interface.get_navmesh_event_stream()
    event_future = asyncio.get_running_loop().create_future()

    def on_navmesh_event(event):
        if event.type != nav.EVENT_TYPE_NAVMESH_UPDATED or event_future.done():
            return
        event_future.set_result(event.payload.get_dict())

    subscription = event_stream.create_subscription_to_pop(
        on_navmesh_event,
        name="warehouse navmesh automation",
    )
    try:
        if not begin_transaction(interface.start_navmesh_baking):
            raise RuntimeError("NavMesh bake did not start; another bake may be running")
        payload = await asyncio.wait_for(event_future, timeout=300.0)
    finally:
        subscription = None

    if not bool(payload.get("status", False)):
        raise RuntimeError(f"NavMesh bake failed or was cancelled: {payload}")
    navmesh = interface.get_navmesh()
    if navmesh is None:
        raise RuntimeError("NavMesh bake reported success but returned no NavMesh")

    triangle_count = 0
    for area_index in range(interface.get_area_count()):
        triangle_count += len(navmesh.get_draw_triangles(area_index)) // 3
    if triangle_count <= 0:
        raise RuntimeError("baked NavMesh contains no triangles")

    closest = navmesh.query_closest_point(worker_position, 0)
    if closest is None:
        raise RuntimeError("no NavMesh point exists near the Worker start")
    distance_m = math.dist(tuple(worker_position), tuple(closest)) * meters_per_unit
    if distance_m > 1.0:
        raise RuntimeError(
            f"closest NavMesh point is {distance_m:.3f}m from Worker, exceeding 1m"
        )
    return {
        "status": "verified",
        "triangle_count": triangle_count,
        "worker_closest_point": [float(value) for value in closest],
        "worker_closest_distance_m": distance_m,
        "saved": False,
    }


async def _apply_and_bake_async(interior_bounds=None) -> dict[str, Any]:
    previous = getattr(builtins, _HANDLE_NAME, None)
    if previous is not None and not previous.restored:
        raise RuntimeError("an unrestored Warehouse NavMesh Apply handle already exists")

    scene = _read_live_scene()
    report = build_preview_report(scene)
    if interior_bounds is None:
        if not report["apply_allowed"]:
            raise ValueError(
                "Preview blocks Apply: " + "; ".join(report["blocking_reasons"])
            )
        selected = report["interior_selection"]["candidate"]
        selected_bounds = Bounds3D(
            selected["bounds"]["minimum"], selected["bounds"]["maximum"]
        )
    else:
        selected_bounds = validate_explicit_interior_bounds(
            _coerce_interior_bounds(interior_bounds),
            scene.warehouse_bounds,
            scene.volume_bounds,
            scene.worker_position,
        )
        allowed, remaining = _allowed_with_explicit_bounds(report)
        if not allowed:
            raise ValueError("Preview blocks Apply: " + "; ".join(remaining))

    radius_cm = report["proposed_agent_radius_cm"]
    if radius_cm is None:
        raise ValueError("Preview did not produce a valid Agent Radius")

    snapshot = _capture_live_snapshot()
    handle = _LiveRestoreHandle(snapshot)
    setattr(builtins, _HANDLE_NAME, handle)
    try:
        def begin_transaction(start_bake):
            controller = NavMeshApplyController(
                apply_allowed=True,
                capture_snapshot=lambda: snapshot,
                apply_changes=lambda captured: _apply_live_changes(
                    captured,
                    interior_bounds=selected_bounds,
                    proposed_radius_cm=float(radius_cm),
                ),
                start_bake=start_bake,
                restore_changes=lambda _captured: handle.restore(),
            )
            return controller.run()

        result = await _bake_and_verify_async(
            scene.worker_position,
            scene.meters_per_unit,
            begin_transaction,
        )
    except BaseException:
        if not handle.restored:
            handle.restore()
        print(
            "[Warehouse NavMesh] Apply/Bake failed; settings and USD edits were "
            "restored. Re-bake the prior configuration if needed."
        )
        raise

    result.update(
        {
            "agent_height_cm": 180.0,
            "agent_radius_cm": float(radius_cm),
            "volume_bounds": _bounds_dict(selected_bounds),
            "restore_available": True,
        }
    )
    print("WAREHOUSE_NAVMESH_APPLY=" + json.dumps(result, sort_keys=True))
    print("[Warehouse NavMesh] Inspect Surface/Outline before Ctrl+S.")
    return result


def _report_task_result(task: asyncio.Task) -> None:
    try:
        task.result()
    except Exception:
        print("[Warehouse NavMesh] task failed")
        traceback.print_exc()


def apply_and_bake(interior_bounds=None) -> asyncio.Task:
    """Schedule guarded Apply/Bake from Script Editor without starting Timeline."""

    task = asyncio.ensure_future(_apply_and_bake_async(interior_bounds))
    task.add_done_callback(_report_task_result)
    print("[Warehouse NavMesh] Apply/Bake task scheduled; Stage will not be saved.")
    return task


def restore() -> dict[str, Any]:
    """Restore the most recent Apply snapshot; a manual re-bake is then required."""

    handle = getattr(builtins, _HANDLE_NAME, None)
    if handle is None:
        raise RuntimeError("no Warehouse NavMesh Apply snapshot is available")
    return handle.restore()


if __name__ == "__main__":
    _PREVIEW_REPORT = run(mode="preview")
