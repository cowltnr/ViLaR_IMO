import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from scripts.setup_warehouse_runtime import (
    RuntimeBootstrap,
    RuntimeSession,
    WorkerRuntimeSnapshot,
    normalize_stage_identifier,
)


class _Restorable:
    def __init__(self, events, name):
        self._events = events
        self._name = name

    def restore(self):
        self._events.append(f"restore:{self._name}")


class _CartHandle:
    def __init__(self, events):
        self._events = events

    def shutdown(self):
        self._events.append("shutdown:cart")


class _FailingCartHandle:
    def __init__(self, events):
        self._events = events

    def shutdown(self):
        self._events.append("shutdown:cart")
        raise RuntimeError("cart cleanup failed")


class _Settings:
    def __init__(self, values):
        self.values = dict(values)

    def get(self, path):
        return self.values.get(path)

    def set(self, path, value):
        self.values[path] = value

    def destroy_item(self, path):
        self.values.pop(path, None)


class WorkerRuntimeSnapshotTest(unittest.TestCase):
    def test_restore_recovers_settings_and_existing_command_file(self):
        settings = _Settings({"/command": "old.txt", "/loops": 2})
        with TemporaryDirectory() as directory:
            command_file = Path(directory) / "worker_commands.txt"
            command_file.write_bytes(b"old commands\n")
            snapshot = WorkerRuntimeSnapshot.capture(
                settings=settings,
                setting_paths=("/command", "/loops", "/navmesh"),
                command_file=command_file,
            )
            settings.set("/command", "new.txt")
            settings.set("/loops", 0)
            settings.set("/navmesh", True)
            command_file.write_bytes(b"new commands\n")

            snapshot.restore()

            self.assertEqual(
                settings.values,
                {"/command": "old.txt", "/loops": 2},
            )
            self.assertEqual(command_file.read_bytes(), b"old commands\n")


class StageIdentifierTest(unittest.TestCase):
    def test_file_identifier_and_plain_path_normalize_to_same_absolute_path(self):
        plain = "/home/cowltnr/LimoIsaacSIM/USD/cart_simulation_env/warehouse_cart_worker.usd"

        self.assertEqual(normalize_stage_identifier("file:" + plain), plain)
        self.assertEqual(normalize_stage_identifier(plain), plain)

    def test_rejects_non_file_stage_identifier(self):
        with self.assertRaisesRegex(ValueError, "file-backed"):
            normalize_stage_identifier("anon:0x123:stage")


class RuntimeBootstrapTest(unittest.IsolatedAsyncioTestCase):
    def build_bootstrap(self, *, fail_at=None):
        events = []

        def precheck():
            events.append("precheck")
            if fail_at == "precheck":
                raise RuntimeError("bad stage")
            return {"stage": "warehouse_cart_worker.usd"}

        async def setup_navmesh():
            events.append("setup:navmesh")
            if fail_at == "navmesh":
                raise RuntimeError("bake failed")
            return {"triangles": 241}, _Restorable(events, "navmesh")

        def capture_worker_state():
            events.append("capture:worker")
            return _Restorable(events, "worker")

        async def setup_worker():
            events.append("setup:worker")
            if fail_at == "worker":
                raise RuntimeError("worker failed")
            return {"goal": [0.0, 4.78, 0.04]}

        def setup_cart():
            events.append("setup:cart")
            if fail_at == "cart":
                raise RuntimeError("cart failed")
            return _CartHandle(events)

        bootstrap = RuntimeBootstrap(
            precheck=precheck,
            setup_navmesh=setup_navmesh,
            capture_worker_state=capture_worker_state,
            setup_worker=setup_worker,
            setup_cart=setup_cart,
            log=lambda message: events.append(f"log:{message}"),
        )
        return bootstrap, events

    async def test_success_configures_components_in_safe_order(self):
        bootstrap, events = self.build_bootstrap()

        session = await bootstrap.start()

        self.assertIsNotNone(session)
        self.assertTrue(session.active)
        self.assertEqual(session.status, "ready")
        self.assertEqual(
            [event for event in events if not event.startswith("log:")],
            [
                "precheck",
                "setup:navmesh",
                "capture:worker",
                "setup:worker",
                "setup:cart",
            ],
        )
        self.assertEqual(session.result["navmesh"], {"triangles": 241})
        self.assertEqual(session.result["worker"]["goal"], [0.0, 4.78, 0.04])

    async def test_precheck_failure_does_not_start_any_component(self):
        bootstrap, events = self.build_bootstrap(fail_at="precheck")

        with self.assertRaisesRegex(RuntimeError, "bad stage"):
            await bootstrap.start()

        self.assertEqual(
            [event for event in events if not event.startswith("log:")],
            ["precheck"],
        )

    async def test_worker_failure_restores_worker_then_navmesh(self):
        bootstrap, events = self.build_bootstrap(fail_at="worker")

        with self.assertRaisesRegex(RuntimeError, "worker failed"):
            await bootstrap.start()

        self.assertEqual(
            [event for event in events if event.startswith("restore:")],
            ["restore:worker", "restore:navmesh"],
        )

    async def test_cart_failure_restores_worker_then_navmesh(self):
        bootstrap, events = self.build_bootstrap(fail_at="cart")

        with self.assertRaisesRegex(RuntimeError, "cart failed"):
            await bootstrap.start()

        self.assertEqual(
            [event for event in events if event.startswith("restore:")],
            ["restore:worker", "restore:navmesh"],
        )

    async def test_ready_session_is_reused_without_duplicate_setup(self):
        bootstrap, events = self.build_bootstrap()
        first = await bootstrap.start()

        second = await bootstrap.start()

        self.assertIs(second, first)
        self.assertEqual(events.count("setup:navmesh"), 1)
        self.assertEqual(events.count("setup:cart"), 1)

    async def test_shutdown_removes_cart_and_worker_runtime_but_keeps_navmesh(self):
        bootstrap, events = self.build_bootstrap()
        session = await bootstrap.start()

        session.shutdown()

        self.assertFalse(session.active)
        self.assertEqual(
            [event for event in events if event.startswith(("shutdown:", "restore:"))],
            ["shutdown:cart", "restore:worker"],
        )

    async def test_shutdown_can_explicitly_restore_navmesh(self):
        bootstrap, events = self.build_bootstrap()
        session = await bootstrap.start()

        session.shutdown(restore_navmesh=True)

        self.assertEqual(
            [event for event in events if event.startswith(("shutdown:", "restore:"))],
            ["shutdown:cart", "restore:worker", "restore:navmesh"],
        )

    async def test_setup_error_stays_primary_and_later_cleanup_still_runs(self):
        events = []

        class FailingWorkerRestore:
            def restore(self):
                events.append("restore:worker")
                raise RuntimeError("worker cleanup failed")

        bootstrap = RuntimeBootstrap(
            precheck=lambda: {},
            setup_navmesh=lambda: _async_value(({}, _Restorable(events, "navmesh"))),
            capture_worker_state=FailingWorkerRestore,
            setup_worker=lambda: _async_error(RuntimeError("worker setup failed")),
            setup_cart=lambda: _CartHandle(events),
            log=lambda _message: None,
        )

        with self.assertRaisesRegex(RuntimeError, "worker setup failed"):
            await bootstrap.start()

        self.assertEqual(events, ["restore:worker", "restore:navmesh"])


class RuntimeSessionTest(unittest.TestCase):
    def test_shutdown_attempts_all_cleanup_when_cart_cleanup_fails(self):
        events = []
        session = RuntimeSession(
            result={"status": "ready"},
            navmesh_handle=_Restorable(events, "navmesh"),
            worker_snapshot=_Restorable(events, "worker"),
            cart_handle=_FailingCartHandle(events),
        )

        with self.assertRaisesRegex(RuntimeError, "cart cleanup failed"):
            session.shutdown(restore_navmesh=True)

        self.assertEqual(
            events,
            ["shutdown:cart", "restore:worker", "restore:navmesh"],
        )
        self.assertFalse(session.active)


async def _async_value(value):
    return value


async def _async_error(error):
    raise error


if __name__ == "__main__":
    unittest.main()
