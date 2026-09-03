#!/usr/bin/env python3
"""Apply the default Isaac Sim Animation Graph to one warehouse worker."""

from __future__ import annotations

import asyncio
import traceback


DEFAULT_WORKER_PATH = "/World/Characters/Worker_01"


def select_worker_skelroot_paths(skelroot_paths: list[str], worker_path: str) -> list[str]:
    normalized_worker_path = worker_path.rstrip("/")
    worker_child_prefix = normalized_worker_path + "/"
    selected = [path for path in skelroot_paths if path.startswith(worker_child_prefix)]
    if not selected:
        worker_name = normalized_worker_path.rsplit("/", 1)[-1]
        raise RuntimeError(f"{worker_name} 아래에서 SkelRoot를 찾을 수 없습니다: {normalized_worker_path}")
    return selected


async def apply_animation_graph_to_worker(worker_path: str = DEFAULT_WORKER_PATH) -> dict[str, object]:
    """Apply and verify Isaac Sim's default biped Animation Graph in the live stage."""
    import AnimGraphSchema
    import omni.kit.app
    import omni.usd
    from isaacsim.core.utils.extensions import enable_extension
    from isaacsim.core.utils.stage import is_stage_loading

    enable_extension("omni.anim.people")
    enable_extension("isaacsim.replicator.agent.core")
    for _ in range(3):
        await omni.kit.app.get_app().next_update_async()

    from isaacsim.replicator.agent.core.simulation import SimulationManager
    from isaacsim.replicator.agent.core.stage_util import CharacterUtil

    stage = omni.usd.get_context().get_stage()
    worker = stage.GetPrimAtPath(worker_path) if stage else None
    if not worker or not worker.IsValid():
        raise RuntimeError(f"Worker Prim을 찾을 수 없습니다: {worker_path}")

    manager = SimulationManager()
    manager.load_default_skeleton_and_animations()

    for _ in range(600):
        if not is_stage_loading():
            break
        await omni.kit.app.get_app().next_update_async()
    else:
        raise TimeoutError("기본 Biped Animation Asset 로딩이 600 frame 안에 완료되지 않았습니다.")

    for _ in range(3):
        await omni.kit.app.get_app().next_update_async()

    all_skelroots = CharacterUtil.get_characters_in_stage(count_invisible=True)
    selected_paths = select_worker_skelroot_paths(
        [str(prim.GetPath()) for prim in all_skelroots],
        worker_path,
    )
    selected_prims = [stage.GetPrimAtPath(path) for path in selected_paths]
    manager.setup_animation_graph_to_character(selected_prims)

    default_biped = CharacterUtil.get_default_biped_character()
    animation_graph = CharacterUtil.get_anim_graph_from_character(default_biped)
    if not animation_graph or not animation_graph.IsValid():
        raise RuntimeError("기본 Biped Animation Graph를 찾을 수 없습니다.")

    expected_target = animation_graph.GetPath()
    for skelroot in selected_prims:
        api = AnimGraphSchema.AnimationGraphAPI(skelroot)
        targets = api.GetAnimationGraphRel().GetTargets()
        if targets != [expected_target]:
            raise RuntimeError(
                f"Animation Graph 검증 실패: {skelroot.GetPath()} targets={list(targets)}"
            )

    result = {
        "worker": worker_path,
        "skelroots": selected_paths,
        "animation_graph": str(expected_target),
        "saved": False,
    }
    print(f"[Worker Animation] 적용 및 검증 완료: {result}")
    print("[Worker Animation] 아직 저장하지 않았습니다. Stage에서 Ctrl+S를 눌러 저장하세요.")
    return result


def _report_task_result(task: asyncio.Task) -> None:
    try:
        task.result()
    except Exception:
        print("[Worker Animation] 적용 실패")
        traceback.print_exc()


def run(worker_path: str = DEFAULT_WORKER_PATH) -> asyncio.Task:
    """Schedule the live-stage operation from Isaac Sim's Script Editor."""
    task = asyncio.ensure_future(apply_animation_graph_to_worker(worker_path))
    task.add_done_callback(_report_task_result)
    print(f"[Worker Animation] 적용 시작: {worker_path}")
    return task


if __name__ == "__main__":
    _TASK = run()
