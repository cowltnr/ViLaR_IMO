#!/usr/bin/env python3
"""Configure one warehouse worker for a validated NavMesh round trip."""

from __future__ import annotations

import asyncio
import math
import traceback
from pathlib import Path
from scripts.warehouse_runtime_paths import resolve_warehouse_runtime_paths


DEFAULT_WORKER_PATH = "/World/Characters/Worker_01"
DEFAULT_COMMAND_FILE = resolve_warehouse_runtime_paths().command_file


def build_goal_candidates(start: tuple[float, float, float]) -> list[tuple[float, float, float]]:
    x, y, z = (float(value) for value in start)
    return [
        (x, y + 6.0, z),
        (x + 6.0, y, z),
        (x - 6.0, y, z),
        (x, y - 6.0, z),
        (x + 4.0, y + 4.0, z),
        (x - 4.0, y + 4.0, z),
        (x + 4.0, y - 4.0, z),
        (x - 4.0, y - 4.0, z),
    ]


def build_worker_command_lines(
    worker_name: str,
    start: tuple[float, float, float],
    goal: tuple[float, float, float],
) -> list[str]:
    if math.dist(start, goal) < 1e-6:
        raise ValueError("start and goal must be different")

    def goto_line(point: tuple[float, float, float]) -> str:
        return (
            f"{worker_name} GoTo "
            f"{point[0]:.3f} {point[1]:.3f} {point[2]:.3f} _"
        )

    return [
        f"{worker_name} Idle 2",
        goto_line(goal),
        f"{worker_name} Idle 3",
        goto_line(start),
        f"{worker_name} Idle 3",
    ]


async def configure_worker_behavior(
    worker_path: str = DEFAULT_WORKER_PATH,
    command_file: Path = DEFAULT_COMMAND_FILE,
) -> dict[str, object]:
    """Validate a live NavMesh, attach People behavior, and prepare a round trip."""
    import AnimGraphSchema
    import carb
    import omni.anim.navigation.core as nav
    import omni.kit.app
    import omni.timeline
    import omni.usd
    from isaacsim.core.utils.extensions import enable_extension

    timeline = omni.timeline.get_timeline_interface()
    if timeline.is_playing():
        raise RuntimeError("Stop the Timeline before configuring Worker behavior.")

    enable_extension("omni.anim.people")
    enable_extension("isaacsim.replicator.agent.core")
    for _ in range(3):
        await omni.kit.app.get_app().next_update_async()

    from isaacsim.replicator.agent.core.simulation import SimulationManager
    from isaacsim.replicator.agent.core.settings import BehaviorScriptPaths
    from isaacsim.replicator.agent.core.stage_util import CharacterUtil
    from omni.anim.people.settings import PeopleSettings

    stage = omni.usd.get_context().get_stage()
    worker = stage.GetPrimAtPath(worker_path) if stage else None
    if not worker or not worker.IsValid():
        raise RuntimeError(f"Worker prim not found: {worker_path}")

    skelroot = CharacterUtil.get_character_skelroot_by_root(worker)
    if not skelroot or not skelroot.IsValid():
        raise RuntimeError(f"SkelRoot not found below: {worker_path}")

    graph_targets = (
        AnimGraphSchema.AnimationGraphAPI(skelroot)
        .GetAnimationGraphRel()
        .GetTargets()
    )
    if not graph_targets:
        raise RuntimeError("Animation Graph is not attached to Worker_01.")

    navmesh = nav.acquire_interface().get_navmesh()
    if navmesh is None or len(navmesh.get_draw_triangles(0)) == 0:
        raise RuntimeError("Baked NavMesh is unavailable. Bake NavMesh before running this script.")

    worker_matrix = omni.usd.get_world_transform_matrix(worker)
    worker_position = worker_matrix.ExtractTranslation()
    raw_start = tuple(float(worker_position[index]) for index in range(3))
    start_point = navmesh.query_closest_point(carb.Float3(*raw_start))
    if start_point is None:
        raise RuntimeError("No NavMesh point was found near Worker_01.")
    start = tuple(float(start_point[index]) for index in range(3))
    if math.dist(raw_start, start) > 1.0:
        raise RuntimeError(
            f"Worker_01 is too far from NavMesh: worker={raw_start}, closest={start}"
        )

    goal = None
    path_point_count = 0
    for candidate in build_goal_candidates(start):
        closest = navmesh.query_closest_point(carb.Float3(*candidate))
        if closest is None:
            continue
        snapped = tuple(float(closest[index]) for index in range(3))
        if math.dist(candidate, snapped) > 1.5 or math.dist(start, snapped) < 4.0:
            continue
        path = navmesh.query_shortest_path(
            start_pos=carb.Float3(*start),
            end_pos=carb.Float3(*snapped),
        )
        points = list(path.get_points()) if path is not None else []
        if len(points) >= 2:
            goal = snapped
            path_point_count = len(points)
            break

    if goal is None:
        raise RuntimeError("No reachable 4-6 m test goal was found around Worker_01.")

    worker_name = worker_path.rstrip("/").rsplit("/", 1)[-1]
    command_lines = build_worker_command_lines(worker_name, start, goal)
    command_file.parent.mkdir(parents=True, exist_ok=True)
    command_file.write_text("\n".join(command_lines) + "\n", encoding="utf-8")

    settings = carb.settings.get_settings()
    settings.set(PeopleSettings.COMMAND_FILE_PATH, str(command_file))
    settings.set(PeopleSettings.NUMBER_OF_LOOP, 0)
    settings.set(PeopleSettings.NAVMESH_ENABLED, True)
    settings.set(PeopleSettings.DYNAMIC_AVOIDANCE_ENABLED, True)
    settings.set(PeopleSettings.CHARACTER_PRIM_PATH, "/World/Characters")

    manager = SimulationManager()
    manager.setup_python_scripts_to_character([skelroot])

    expected_script = BehaviorScriptPaths.behavior_script_path()
    authored_scripts = skelroot.GetAttribute("omni:scripting:scripts").Get() or []
    authored_paths = [
        item.path if hasattr(item, "path") else str(item)
        for item in authored_scripts
    ]
    if expected_script not in authored_paths:
        raise RuntimeError(
            f"Behavior Script verification failed: expected={expected_script}, actual={authored_paths}"
        )

    result = {
        "worker": worker_path,
        "skelroot": str(skelroot.GetPath()),
        "start": start,
        "goal": goal,
        "path_points": path_point_count,
        "command_file": str(command_file),
        "behavior_script": expected_script,
        "stage_saved": False,
        "timeline_started": False,
    }
    print(f"[Worker Behavior] CONFIGURED: {result}")
    print("[Worker Behavior] Save the stage, then press Play to test Worker-only motion.")
    return result


def _report_task_result(task: asyncio.Task) -> None:
    try:
        task.result()
    except Exception:
        print("[Worker Behavior] FAILED")
        traceback.print_exc()


def run(
    worker_path: str = DEFAULT_WORKER_PATH,
    command_file: Path = DEFAULT_COMMAND_FILE,
) -> asyncio.Task:
    """Schedule configuration from Isaac Sim's Script Editor."""
    task = asyncio.ensure_future(configure_worker_behavior(worker_path, command_file))
    task.add_done_callback(_report_task_result)
    print(f"[Worker Behavior] STARTED: {worker_path}")
    return task


if __name__ == "__main__":
    _TASK = run()
