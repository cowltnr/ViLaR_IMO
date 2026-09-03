import unittest
from pathlib import Path

from scripts.warehouse_runtime_paths import resolve_warehouse_runtime_paths


class WarehouseRuntimePathsTest(unittest.TestCase):
    def test_repository_assets_are_the_defaults(self):
        root = Path("/tmp/vilar-clone")
        paths = resolve_warehouse_runtime_paths({}, root)
        self.assertEqual(
            paths.stage,
            root / "assets/isaac_sim/cart_simulation_env/warehouse_cart_worker.usd",
        )
        self.assertEqual(
            paths.command_file,
            root / "assets/isaac_sim/cart_simulation_env/worker_commands.txt",
        )

    def test_environment_overrides_both_paths(self):
        paths = resolve_warehouse_runtime_paths(
            {
                "VILAR_WAREHOUSE_STAGE": "/opt/scenes/warehouse.usd",
                "VILAR_WORKER_COMMAND_FILE": "/opt/scenes/commands.txt",
            },
            Path("/tmp/vilar-clone"),
        )
        self.assertEqual(paths.stage, Path("/opt/scenes/warehouse.usd"))
        self.assertEqual(paths.command_file, Path("/opt/scenes/commands.txt"))

    def test_relative_environment_path_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "absolute"):
            resolve_warehouse_runtime_paths(
                {"VILAR_WAREHOUSE_STAGE": "relative/warehouse.usd"},
                Path("/tmp/vilar-clone"),
            )


if __name__ == "__main__":
    unittest.main()
