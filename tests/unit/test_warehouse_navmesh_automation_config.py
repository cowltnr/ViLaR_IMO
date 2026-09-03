"""Offline contracts for Warehouse NavMesh Preview–Apply automation."""

from __future__ import annotations

import unittest

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
from scripts.configure_warehouse_navmesh import build_preview_report


class WarehouseNavMeshGeometryTest(unittest.TestCase):
    def test_agent_radius_uses_cart_width_and_stage_units(self):
        cart_bounds = Bounds3D((-0.4, -0.9, 0.0), (0.4, 0.9, 1.2))

        radius_cm = calculate_agent_radius_cm(cart_bounds, meters_per_unit=1.0)

        self.assertEqual(radius_cm, 50.0)

    def test_agent_radius_converts_centimeter_stage_units(self):
        cart_bounds = Bounds3D((-40.0, -90.0, 0.0), (40.0, 90.0, 120.0))

        radius_cm = calculate_agent_radius_cm(cart_bounds, meters_per_unit=0.01)

        self.assertEqual(radius_cm, 50.0)

    def test_agent_radius_rejects_value_below_supported_minimum(self):
        cart_bounds = Bounds3D((-0.05, -0.1, 0.0), (0.05, 0.1, 0.2))

        with self.assertRaisesRegex(ValueError, "20.0.*80.0"):
            calculate_agent_radius_cm(cart_bounds, meters_per_unit=1.0)

    def test_agent_radius_rejects_value_above_supported_maximum(self):
        cart_bounds = Bounds3D((-0.8, -1.0, 0.0), (0.8, 1.0, 1.2))

        with self.assertRaisesRegex(ValueError, "20.0.*80.0"):
            calculate_agent_radius_cm(cart_bounds, meters_per_unit=1.0)

    def test_bounds_reject_inverted_axis(self):
        with self.assertRaisesRegex(ValueError, "maximum"):
            Bounds3D((1.0, 0.0, 0.0), (0.0, 1.0, 1.0))

    def test_selects_only_floor_containing_worker_near_feet(self):
        result = select_interior_floor(
            [
                FloorCandidate(
                    "/World/Environment/Warehouse/Floor",
                    Bounds3D((-10.0, -8.0, -0.1), (10.0, 8.0, 0.05)),
                ),
                FloorCandidate(
                    "/World/Environment/Warehouse/UpperFloor",
                    Bounds3D((-10.0, -8.0, 2.9), (10.0, 8.0, 3.1)),
                ),
            ],
            worker_position=(0.0, 0.0, 0.04),
            volume_bounds=Bounds3D((-20.0, -20.0, -0.2), (20.0, 20.0, 0.5)),
            meters_per_unit=1.0,
        )

        self.assertEqual(result.status, "selected")
        self.assertEqual(result.candidate.path, "/World/Environment/Warehouse/Floor")

    def test_multiple_matching_floors_are_ambiguous(self):
        floors = [
            FloorCandidate("/World/FloorA", Bounds3D((-5.0, -5.0, 0.0), (5.0, 5.0, 0.05))),
            FloorCandidate("/World/FloorB", Bounds3D((-4.0, -4.0, -0.02), (4.0, 4.0, 0.04))),
        ]

        result = select_interior_floor(
            floors,
            worker_position=(0.0, 0.0, 0.04),
            volume_bounds=Bounds3D((-10.0, -10.0, -0.5), (10.0, 10.0, 0.5)),
            meters_per_unit=1.0,
        )

        self.assertEqual(result.status, "ambiguous")
        self.assertIsNone(result.candidate)
        self.assertEqual(result.reasons, ("2 floor candidates matched",))

    def test_no_matching_floor_is_ambiguous(self):
        floor = FloorCandidate(
            "/World/Floor",
            Bounds3D((20.0, 20.0, 0.0), (30.0, 30.0, 0.05)),
        )

        result = select_interior_floor(
            [floor],
            worker_position=(0.0, 0.0, 0.04),
            volume_bounds=Bounds3D((-10.0, -10.0, -0.5), (10.0, 10.0, 0.5)),
            meters_per_unit=1.0,
        )

        self.assertEqual(result.status, "ambiguous")
        self.assertIsNone(result.candidate)
        self.assertEqual(result.reasons, ("no floor candidate matched",))

    def test_replace_volume_xy_preserves_current_z(self):
        center, scale = replace_volume_xy(
            interior_bounds=Bounds3D((-8.0, -6.0, -0.1), (12.0, 10.0, 0.1)),
            current_center=(-10.0, 3.5, 0.15),
            current_scale=(36.0, 60.0, 0.59),
            inset=0.5,
        )

        self.assertEqual(center, (2.0, 2.0, 0.15))
        self.assertEqual(scale, (19.0, 15.0, 0.59))

    def test_replace_volume_xy_rejects_inset_that_removes_floor(self):
        with self.assertRaisesRegex(ValueError, "inset"):
            replace_volume_xy(
                interior_bounds=Bounds3D((0.0, 0.0, 0.0), (1.0, 1.0, 0.1)),
                current_center=(0.0, 0.0, 0.0),
                current_scale=(1.0, 1.0, 1.0),
                inset=0.5,
            )

    def test_explicit_interior_bounds_must_stay_inside_warehouse_xy(self):
        with self.assertRaisesRegex(ValueError, "Warehouse XY"):
            validate_explicit_interior_bounds(
                interior_bounds=Bounds3D((-11.0, -6.0, -0.1), (8.0, 6.0, 0.1)),
                warehouse_bounds=Bounds3D((-10.0, -8.0, -0.2), (10.0, 8.0, 4.0)),
                volume_bounds=Bounds3D((-20.0, -20.0, -0.5), (20.0, 20.0, 0.5)),
                worker_position=(0.0, 0.0, 0.04),
            )

    def test_explicit_interior_bounds_must_contain_worker_xy(self):
        with self.assertRaisesRegex(ValueError, "Worker XY"):
            validate_explicit_interior_bounds(
                interior_bounds=Bounds3D((1.0, 1.0, -0.1), (8.0, 6.0, 0.1)),
                warehouse_bounds=Bounds3D((-10.0, -8.0, -0.2), (10.0, 8.0, 4.0)),
                volume_bounds=Bounds3D((-20.0, -20.0, -0.5), (20.0, 20.0, 0.5)),
                worker_position=(0.0, 0.0, 0.04),
            )

    def test_explicit_interior_bounds_must_not_expand_current_volume_xy(self):
        with self.assertRaisesRegex(ValueError, "current Volume XY"):
            validate_explicit_interior_bounds(
                interior_bounds=Bounds3D((-9.0, -7.0, -0.1), (9.0, 7.0, 0.1)),
                warehouse_bounds=Bounds3D((-10.0, -8.0, -0.2), (10.0, 8.0, 4.0)),
                volume_bounds=Bounds3D((-8.0, -6.0, -0.5), (8.0, 6.0, 0.5)),
                worker_position=(0.0, 0.0, 0.04),
            )

    def test_explicit_interior_bounds_accept_safe_xy_region(self):
        bounds = Bounds3D((-8.0, -6.0, -0.1), (8.0, 6.0, 0.1))

        result = validate_explicit_interior_bounds(
            interior_bounds=bounds,
            warehouse_bounds=Bounds3D((-10.0, -8.0, -0.2), (10.0, 8.0, 4.0)),
            volume_bounds=Bounds3D((-20.0, -20.0, -0.5), (20.0, 20.0, 0.5)),
            worker_position=(0.0, 0.0, 0.04),
        )

        self.assertIs(result, bounds)


def _scene_snapshot(*, floors: tuple[FloorCandidate, ...]) -> SceneSnapshot:
    return SceneSnapshot(
        stage_identifier="/tmp/warehouse_cart_worker.usd",
        meters_per_unit=1.0,
        up_axis="Z",
        timeline_state="stopped",
        warehouse_bounds=Bounds3D((-10.0, -8.0, -0.2), (10.0, 8.0, 4.0)),
        volume_bounds=Bounds3D((-20.0, -20.0, -0.5), (20.0, 20.0, 0.5)),
        volume_center=(-0.0, 0.0, 0.0),
        volume_scale=(40.0, 40.0, 1.0),
        worker_position=(0.0, 0.0, 0.04),
        cart_bounds=Bounds3D((-0.4, -0.9, 0.0), (0.4, 0.9, 1.2)),
        floor_candidates=floors,
        static_structure_paths=("/World/Environment/Warehouse/Rack",),
        dynamic_root_paths=("/World/Characters", "/World/DynamicActors"),
        warehouse_excluded_paths=(),
        current_settings=(("agent_height_cm", 180.0), ("agent_radius_cm", 20.0)),
    )


class WarehouseNavMeshPreviewReportTest(unittest.TestCase):
    def test_preview_report_blocks_apply_when_floor_is_ambiguous(self):
        snapshot = _scene_snapshot(
            floors=(
                FloorCandidate(
                    "/World/Environment/Warehouse/FloorA",
                    Bounds3D((-5.0, -5.0, 0.0), (5.0, 5.0, 0.05)),
                ),
                FloorCandidate(
                    "/World/Environment/Warehouse/FloorB",
                    Bounds3D((-4.0, -4.0, -0.02), (4.0, 4.0, 0.04)),
                ),
            )
        )

        report = build_preview_report(snapshot)

        self.assertFalse(report["apply_allowed"])
        self.assertEqual(report["interior_selection"]["status"], "ambiguous")
        self.assertEqual(
            report["blocking_reasons"], ["2 floor candidates matched"]
        )

    def test_preview_report_lists_dynamic_exclusions_without_applying_them(self):
        snapshot = _scene_snapshot(
            floors=(
                FloorCandidate(
                    "/World/Environment/Warehouse/Floor",
                    Bounds3D((-10.0, -8.0, -0.1), (10.0, 8.0, 0.05)),
                ),
            )
        )

        report = build_preview_report(snapshot)

        self.assertTrue(report["apply_allowed"])
        self.assertEqual(
            report["dynamic_exclusion_paths"],
            ["/World/Characters", "/World/DynamicActors"],
        )
        self.assertEqual(report["proposed_agent_radius_cm"], 50.0)

    def test_preview_report_blocks_apply_when_timeline_is_not_stopped(self):
        snapshot = _scene_snapshot(
            floors=(
                FloorCandidate(
                    "/World/Environment/Warehouse/Floor",
                    Bounds3D((-10.0, -8.0, -0.1), (10.0, 8.0, 0.05)),
                ),
            )
        )
        snapshot = SceneSnapshot(
            **{
                **snapshot.__dict__,
                "timeline_state": "playing",
            }
        )

        report = build_preview_report(snapshot)

        self.assertFalse(report["apply_allowed"])
        self.assertIn("timeline must be stopped", report["blocking_reasons"])

    def test_preview_report_blocks_apply_for_warehouse_exclusion(self):
        snapshot = _scene_snapshot(
            floors=(
                FloorCandidate(
                    "/World/Environment/Warehouse/Floor",
                    Bounds3D((-10.0, -8.0, -0.1), (10.0, 8.0, 0.05)),
                ),
            )
        )
        snapshot = SceneSnapshot(
            **{
                **snapshot.__dict__,
                "warehouse_excluded_paths": (
                    "/World/Environment/Warehouse/Rack",
                ),
            }
        )

        report = build_preview_report(snapshot)

        self.assertFalse(report["apply_allowed"])
        self.assertEqual(
            report["blocking_reasons"],
            ["Warehouse contains NavMeshExcludeAPI"],
        )


class WarehouseNavMeshApplyTransactionTest(unittest.TestCase):
    def test_apply_failure_restores_snapshot(self):
        events = []

        def fail_apply(_snapshot):
            raise RuntimeError("apply failed")

        controller = NavMeshApplyController(
            apply_allowed=True,
            capture_snapshot=lambda: "before",
            apply_changes=fail_apply,
            start_bake=lambda: events.append("bake"),
            restore_changes=lambda snapshot: events.append(("restore", snapshot)),
        )

        with self.assertRaisesRegex(RuntimeError, "apply failed"):
            controller.run()

        self.assertEqual(events, [("restore", "before")])

    def test_invalid_preview_never_captures_applies_or_bakes(self):
        events = []
        controller = NavMeshApplyController(
            apply_allowed=False,
            capture_snapshot=lambda: events.append("capture"),
            apply_changes=lambda _snapshot: events.append("apply"),
            start_bake=lambda: events.append("bake"),
            restore_changes=lambda _snapshot: events.append("restore"),
        )

        with self.assertRaisesRegex(ValueError, "Preview"):
            controller.run()

        self.assertEqual(events, [])

    def test_successful_apply_captures_applies_and_bakes_once_in_order(self):
        events = []

        def capture():
            events.append("capture")
            return "before"

        controller = NavMeshApplyController(
            apply_allowed=True,
            capture_snapshot=capture,
            apply_changes=lambda snapshot: events.append(("apply", snapshot)),
            start_bake=lambda: events.append("bake") or "bake-started",
            restore_changes=lambda _snapshot: events.append("restore"),
        )

        result = controller.run()

        self.assertEqual(result, "bake-started")
        self.assertEqual(events, ["capture", ("apply", "before"), "bake"])


if __name__ == "__main__":
    unittest.main()
