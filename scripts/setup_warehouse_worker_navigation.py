#!/usr/bin/env python3
"""Diagnose and configure NavMesh for the warehouse worker stage in Isaac Sim."""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
import time
from pathlib import Path

from isaacsim import SimulationApp


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--stage", required=True, type=Path)
    parser.add_argument("--mode", choices=("diagnose",), default="diagnose")
    return parser.parse_args()


ARGS = parse_args()
APP = SimulationApp(
    launch_config={
        "headless": True,
        "renderer": "RaytracedLighting",
        "sync_loads": False,
    }
)


def vec3(value) -> list[float]:
    return [float(value[0]), float(value[1]), float(value[2])]


def aligned_world_range(bbox_cache, prim):
    value = bbox_cache.ComputeWorldBound(prim).ComputeAlignedRange()
    if value.IsEmpty():
        return None
    return {"min": vec3(value.GetMin()), "max": vec3(value.GetMax())}


def main() -> int:
    import omni.usd
    from isaacsim.core.utils.extensions import enable_extension
    from isaacsim.core.utils.stage import is_stage_loading
    from pxr import Usd, UsdGeom

    print("PROGRESS: enabling omni.anim.navigation.core", flush=True)
    enable_extension("omni.anim.navigation.core")
    for _ in range(10):
        APP.update()
    print("PROGRESS: navigation extension enabled", flush=True)

    stage_path = ARGS.stage.expanduser().resolve()
    if not stage_path.is_file():
        raise FileNotFoundError(stage_path)

    context = omni.usd.get_context()
    print(f"PROGRESS: opening stage {stage_path}", flush=True)
    open_task = asyncio.ensure_future(
        context.open_stage_async(str(stage_path), omni.usd.UsdContextInitialLoadSet.LOAD_ALL)
    )
    open_deadline = time.monotonic() + 180.0
    while not open_task.done():
        APP.update()
        if time.monotonic() > open_deadline:
            open_task.cancel()
            raise TimeoutError("Stage open exceeded 180 seconds")
    open_result = open_task.result()
    if isinstance(open_result, tuple):
        opened, error = open_result
    else:
        opened, error = bool(open_result), ""
    if not opened:
        raise RuntimeError(f"Stage open failed: {stage_path}: {error}")
    print("PROGRESS: stage opened; waiting for referenced assets", flush=True)

    update_count = 0
    load_deadline = time.monotonic() + 180.0
    while is_stage_loading():
        APP.update()
        update_count += 1
        if update_count % 300 == 0:
            print(f"PROGRESS: asset loading update {update_count}", flush=True)
        if time.monotonic() > load_deadline:
            raise TimeoutError("Referenced asset loading exceeded 180 seconds")
    for _ in range(30):
        APP.update()
    print("PROGRESS: referenced assets loaded", flush=True)

    stage = context.get_stage()
    purposes = [UsdGeom.Tokens.default_, UsdGeom.Tokens.render, UsdGeom.Tokens.proxy]
    bbox_cache = UsdGeom.BBoxCache(Usd.TimeCode.Default(), purposes, useExtentsHint=True)

    warehouse = stage.GetPrimAtPath("/World/Environment/Warehouse")
    worker = stage.GetPrimAtPath("/World/Characters/Worker_01")
    volume = stage.GetPrimAtPath("/World/NavMeshVolume")
    if not warehouse:
        raise RuntimeError("Warehouse prim not found")
    if not worker:
        raise RuntimeError("Worker prim not found at /World/Characters/Worker_01")
    if not volume:
        raise RuntimeError("NavMeshVolume prim not found")

    worker_matrix = UsdGeom.Xformable(worker).ComputeLocalToWorldTransform(Usd.TimeCode.Default())
    floor_candidates = []
    for prim in Usd.PrimRange(warehouse):
        if "floor" not in prim.GetName().lower():
            continue
        world_range = aligned_world_range(bbox_cache, prim)
        if world_range:
            floor_candidates.append({"path": str(prim.GetPath()), **world_range})

    camera_settings = stage.GetRootLayer().customLayerData.get("cameraSettings", {})
    perspective = camera_settings.get("Perspective", {})
    output = {
        "stage": str(stage_path),
        "meters_per_unit": float(UsdGeom.GetStageMetersPerUnit(stage)),
        "up_axis": str(UsdGeom.GetStageUpAxis(stage)),
        "loading_updates": update_count,
        "warehouse_bounds": aligned_world_range(bbox_cache, warehouse),
        "worker_world_position": vec3(worker_matrix.ExtractTranslation()),
        "navmesh_volume": {
            "translate": vec3(volume.GetAttribute("xformOp:translate").Get()),
            "scale": vec3(volume.GetAttribute("xformOp:scale").Get()),
        },
        "perspective_camera": perspective,
        "floor_candidates": floor_candidates,
    }
    print("WAREHOUSE_NAV_DIAGNOSTIC=" + json.dumps(output, sort_keys=True))
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    finally:
        APP.close()
