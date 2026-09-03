#!/usr/bin/env python3
"""Safely bootstrap the Warehouse Worker–Cart runtime in Isaac Sim."""

from __future__ import annotations

import asyncio
import builtins
import json
import traceback
from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import Any
from urllib.parse import unquote, urlparse


EXPECTED_STAGE_PATH = Path(
    "/home/cowltnr/LimoIsaacSIM/USD/cart_simulation_env/warehouse_cart_worker.usd"
)
INTERIOR_BOUNDS = ((-28.0, -23.4, -0.001), (8.0, 30.6, 0.001))
WORKER_PATH = "/World/Characters/Worker_01"
WORKER_SKELROOT_PATH = "/World/Characters/Worker_01/DHGen/SkelRoot"
CART_PATH = "/World/DynamicActors/CartAssembly"
COMMAND_FILE = Path(
    "/home/cowltnr/LimoIsaacSIM/USD/cart_simulation_env/worker_commands.txt"
)
REQUIRED_PRIM_PATHS = (
    "/World/Environment/Warehouse",
    "/World/NavMeshVolume",
    "/World/Characters",
    WORKER_PATH,
    WORKER_SKELROOT_PATH,
    "/World/DynamicActors",
    CART_PATH,
)
PEOPLE_SETTING_PATHS = (
    "/exts/omni.anim.people/command_settings/command_file_path",
    "/exts/omni.anim.people/command_settings/number_of_loop",
    "/exts/omni.anim.people/navigation_settings/navmesh_enabled",
    "/exts/omni.anim.people/navigation_settings/dynamic_avoidance_enabled",
    "/persistent/exts/omni.anim.people/character_prim_path",
)
_RUNTIME_SESSION_NAME = "_warehouse_runtime_bootstrap_session"
_RUNTIME_TASK_NAME = "_warehouse_runtime_bootstrap_task"


def normalize_stage_identifier(identifier: str) -> str:
    """Return an absolute path for a plain path or local file URI."""
    parsed = urlparse(str(identifier))
    if parsed.scheme and parsed.scheme != "file":
        raise ValueError(f"Stage must be file-backed, got: {identifier}")
    if parsed.scheme == "file" and parsed.netloc not in ("", "localhost"):
        raise ValueError(f"Stage must be a local file-backed stage, got: {identifier}")
    raw_path = unquote(parsed.path) if parsed.scheme == "file" else str(identifier)
    return str(Path(raw_path).expanduser().resolve())


class WorkerRuntimeSnapshot:
    """Restore People settings and the Worker command file after a failed setup."""

    def __init__(
        self,
        *,
        settings: Any,
        setting_values: dict[str, Any],
        command_file: Path,
        command_file_bytes: bytes | None,
    ) -> None:
        self._settings = settings
        self._setting_values = setting_values
        self._command_file = command_file
        self._command_file_bytes = command_file_bytes
        self.restored = False

    @classmethod
    def capture(
        cls,
        *,
        settings: Any,
        setting_paths: tuple[str, ...],
        command_file: Path,
    ) -> "WorkerRuntimeSnapshot":
        path = Path(command_file)
        return cls(
            settings=settings,
            setting_values={name: settings.get(name) for name in setting_paths},
            command_file=path,
            command_file_bytes=path.read_bytes() if path.exists() else None,
        )

    def restore(self) -> None:
        if self.restored:
            return
        for path, value in self._setting_values.items():
            if value is None:
                self._settings.destroy_item(path)
            else:
                self._settings.set(path, value)
        if self._command_file_bytes is None:
            self._command_file.unlink(missing_ok=True)
        else:
            self._command_file.write_bytes(self._command_file_bytes)
        self.restored = True


class BorrowedNavMeshHandle:
    """Do not roll back a verified NavMesh that predates this bootstrap."""

    restored = False

    def restore(self) -> dict[str, Any]:
        return {"restored": False, "borrowed": True}


class RuntimeSession:
    """Own callbacks and rollback handles created by one successful bootstrap."""

    def __init__(
        self,
        *,
        result: dict[str, Any],
        navmesh_handle: Any,
        worker_snapshot: Any,
        cart_handle: Any,
    ) -> None:
        self.result = result
        self._navmesh_handle = navmesh_handle
        self._worker_snapshot = worker_snapshot
        self._cart_handle = cart_handle
        self.status = "ready"
        self.active = True

    def shutdown(self, *, restore_navmesh: bool = False) -> None:
        """Remove runtime state; restore NavMesh edits only when requested."""
        if not self.active:
            return
        cleanup_errors = []
        actions = [self._cart_handle.shutdown, self._worker_snapshot.restore]
        if restore_navmesh:
            actions.append(self._navmesh_handle.restore)
        for action in actions:
            try:
                action()
            except Exception as error:
                cleanup_errors.append(error)
        self.active = False
        self.status = "stopped"
        if cleanup_errors:
            raise RuntimeError(
                "; ".join(str(error) for error in cleanup_errors)
            ) from cleanup_errors[0]


class RuntimeBootstrap:
    """Sequence independently testable Warehouse runtime setup operations."""

    def __init__(
        self,
        *,
        precheck: Callable[[], dict[str, Any]],
        setup_navmesh: Callable[[], Awaitable[tuple[dict[str, Any], Any]]],
        capture_worker_state: Callable[[], Any],
        setup_worker: Callable[[], Awaitable[dict[str, Any]]],
        setup_cart: Callable[[], Any],
        log: Callable[[str], None] = print,
    ) -> None:
        self._precheck = precheck
        self._setup_navmesh = setup_navmesh
        self._capture_worker_state = capture_worker_state
        self._setup_worker = setup_worker
        self._setup_cart = setup_cart
        self._log = log
        self._session: RuntimeSession | None = None

    async def start(self):
        if self._session is not None and self._session.active:
            self._log("[Warehouse Runtime] ALREADY READY")
            return self._session

        navmesh_handle = None
        worker_snapshot = None
        cart_handle = None
        try:
            precheck_result = self._precheck()
            self._log("[Warehouse Runtime] PRECHECK OK")

            navmesh_result, navmesh_handle = await self._setup_navmesh()
            self._log("[Warehouse Runtime] NAVMESH OK")

            worker_snapshot = self._capture_worker_state()
            worker_result = await self._setup_worker()
            self._log("[Warehouse Runtime] WORKER_BEHAVIOR OK")

            cart_handle = self._setup_cart()
            self._log("[Warehouse Runtime] CART_SYNC OK")

            result = {
                "status": "ready",
                "precheck": precheck_result,
                "navmesh": navmesh_result,
                "worker": worker_result,
                "timeline_started": False,
                "stage_saved": False,
            }
            self._session = RuntimeSession(
                result=result,
                navmesh_handle=navmesh_handle,
                worker_snapshot=worker_snapshot,
                cart_handle=cart_handle,
            )
            self._log("[Warehouse Runtime] READY")
            return self._session
        except BaseException:
            cleanup_actions = []
            if cart_handle is not None:
                cleanup_actions.append(cart_handle.shutdown)
            if worker_snapshot is not None:
                cleanup_actions.append(worker_snapshot.restore)
            if navmesh_handle is not None:
                cleanup_actions.append(navmesh_handle.restore)
            for action in cleanup_actions:
                try:
                    action()
                except Exception as cleanup_error:
                    self._log(
                        "[Warehouse Runtime] ROLLBACK WARNING: "
                        f"{type(cleanup_error).__name__}: {cleanup_error}"
                    )
            self._log("[Warehouse Runtime] FAILED; applied state was rolled back")
            raise


def _precheck_live() -> dict[str, Any]:
    import omni.timeline
    import omni.usd

    timeline = omni.timeline.get_timeline_interface()
    if not timeline.is_stopped():
        raise RuntimeError("Stop the Timeline before configuring Warehouse runtime.")

    stage = omni.usd.get_context().get_stage()
    if stage is None:
        raise RuntimeError("No USD stage is open.")
    actual_stage_path = normalize_stage_identifier(stage.GetRootLayer().identifier)
    expected_stage_path = str(EXPECTED_STAGE_PATH.resolve())
    if actual_stage_path != expected_stage_path:
        raise RuntimeError(
            "Unexpected Stage: "
            f"expected={expected_stage_path}, actual={actual_stage_path}"
        )

    missing_paths = []
    for path in REQUIRED_PRIM_PATHS:
        prim = stage.GetPrimAtPath(path)
        if not prim or not prim.IsValid():
            missing_paths.append(path)
    if missing_paths:
        raise RuntimeError(f"Required prims are missing: {missing_paths}")

    return {
        "stage": actual_stage_path,
        "timeline": "stopped",
        "required_prim_count": len(REQUIRED_PRIM_PATHS),
    }


def _capture_worker_state_live() -> WorkerRuntimeSnapshot:
    import carb.settings

    return WorkerRuntimeSnapshot.capture(
        settings=carb.settings.get_settings(),
        setting_paths=PEOPLE_SETTING_PATHS,
        command_file=COMMAND_FILE,
    )


async def _setup_navmesh_live():
    from scripts import configure_warehouse_navmesh as navmesh_setup

    existing = getattr(builtins, navmesh_setup._HANDLE_NAME, None)
    if existing is not None and not existing.restored:
        import omni.anim.navigation.core as nav

        interface = nav.acquire_interface()
        navmesh = interface.get_navmesh()
        if navmesh is None:
            raise RuntimeError(
                "An active NavMesh handle exists, but no baked NavMesh is available. "
                "Run configure_warehouse_navmesh.restore() before retrying."
            )
        triangle_count = sum(
            len(navmesh.get_draw_triangles(area_index)) // 3
            for area_index in range(interface.get_area_count())
        )
        if triangle_count <= 0:
            raise RuntimeError(
                "An active NavMesh handle exists, but its baked NavMesh is empty. "
                "Run configure_warehouse_navmesh.restore() before retrying."
            )
        return (
            {
                "status": "verified_existing",
                "triangle_count": triangle_count,
                "reused": True,
                "saved": False,
            },
            BorrowedNavMeshHandle(),
        )

    result = await navmesh_setup._apply_and_bake_async(INTERIOR_BOUNDS)
    handle = getattr(builtins, navmesh_setup._HANDLE_NAME, None)
    if handle is None or handle.restored:
        raise RuntimeError("NavMesh completed without an active restore handle.")
    return result, handle


async def _setup_worker_live() -> dict[str, Any]:
    from scripts.configure_warehouse_worker_behavior import configure_worker_behavior

    return await configure_worker_behavior(WORKER_PATH, COMMAND_FILE)


def _setup_cart_live():
    from scripts.warehouse_worker_cart_pose_sync import run as setup_cart_sync

    return setup_cart_sync(WORKER_SKELROOT_PATH, CART_PATH)


def _build_live_bootstrap() -> RuntimeBootstrap:
    return RuntimeBootstrap(
        precheck=_precheck_live,
        setup_navmesh=_setup_navmesh_live,
        capture_worker_state=_capture_worker_state_live,
        setup_worker=_setup_worker_live,
        setup_cart=_setup_cart_live,
    )


async def start_warehouse_runtime() -> RuntimeSession:
    """Configure the stopped live Stage without starting Play or saving USD."""
    previous = getattr(builtins, _RUNTIME_SESSION_NAME, None)
    if previous is not None and previous.active:
        print("[Warehouse Runtime] ALREADY READY")
        return previous

    bootstrap = _build_live_bootstrap()
    session = await bootstrap.start()
    setattr(builtins, _RUNTIME_SESSION_NAME, session)
    print("WAREHOUSE_RUNTIME_READY=" + json.dumps(session.result, sort_keys=True))
    print("[Warehouse Runtime] Press Play manually after reviewing READY output.")
    return session


def shutdown_warehouse_runtime(*, restore_navmesh: bool = False) -> None:
    """Stop callbacks/runtime settings; optionally restore pre-bootstrap NavMesh edits."""
    session = getattr(builtins, _RUNTIME_SESSION_NAME, None)
    if session is None:
        raise RuntimeError("No Warehouse runtime session is available.")
    session.shutdown(restore_navmesh=restore_navmesh)
    print(
        "[Warehouse Runtime] SHUTDOWN"
        + ("; prior NavMesh edits restored, re-bake required." if restore_navmesh else "")
    )


def _report_task_result(task: asyncio.Task) -> None:
    try:
        task.result()
    except Exception:
        print("[Warehouse Runtime] TASK FAILED")
        traceback.print_exc()


def run() -> asyncio.Task:
    """Schedule one bootstrap task from Isaac Sim's Script Editor."""
    previous_task = getattr(builtins, _RUNTIME_TASK_NAME, None)
    if previous_task is not None and not previous_task.done():
        print("[Warehouse Runtime] START ALREADY IN PROGRESS")
        return previous_task

    task = asyncio.ensure_future(start_warehouse_runtime())
    task.add_done_callback(_report_task_result)
    setattr(builtins, _RUNTIME_TASK_NAME, task)
    print("[Warehouse Runtime] STARTED; Timeline and Stage save remain manual.")
    return task


if __name__ == "__main__":
    _WAREHOUSE_RUNTIME_TASK = run()
