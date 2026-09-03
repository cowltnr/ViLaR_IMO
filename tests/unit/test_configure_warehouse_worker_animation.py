import unittest

from scripts.configure_warehouse_worker_animation import select_worker_skelroot_paths


class ConfigureWarehouseWorkerAnimationTest(unittest.TestCase):
    def test_selects_only_skelroots_below_requested_worker(self):
        paths = [
            "/World/Characters/Worker_01/Body/SkelRoot",
            "/World/Characters/Worker_02/Body/SkelRoot",
            "/World/Characters/Biped_Setup/biped_demo_meters",
        ]

        selected = select_worker_skelroot_paths(paths, "/World/Characters/Worker_01")

        self.assertEqual(selected, ["/World/Characters/Worker_01/Body/SkelRoot"])

    def test_rejects_stage_without_requested_worker_skelroot(self):
        with self.assertRaisesRegex(RuntimeError, "Worker_01.*SkelRoot"):
            select_worker_skelroot_paths(
                ["/World/Characters/Worker_02/Body/SkelRoot"],
                "/World/Characters/Worker_01",
            )


if __name__ == "__main__":
    unittest.main()
