> Last updated: 2026-09-03 17:08 KST

# Warehouse NavMesh Preview–Apply Automation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Isaac Sim 4.5.0의 열린 Warehouse Stage를 read-only Preview한 뒤 검증된 내부 범위에만 NavMesh 설정을 적용하고 Bake할 수 있는 Script Editor 도구를 만든다.

**Architecture:** Isaac Sim과 무관한 bounds·floor 선택·단위 변환·Agent Radius 계산은 순수 Python 모듈로 분리한다. Live adapter는 Preview report를 생성하고, Apply 시 snapshot을 만든 후 Dynamic Actor 제외와 Volume/settings 변경을 수행하며 오류 시 restore한다.

**Tech Stack:** Python 3.10, `unittest`, Isaac Sim 4.5.0, USD `Usd`/`UsdGeom`/`NavSchema`, `omni.anim.navigation.core`, `omni.timeline`, `carb.settings`

**Spec:** `docs/superpowers/specs/2026-09-03-warehouse-navmesh-automation-design.md`

## Global Constraints

- Preview는 USD attribute, API schema, NavMesh setting, Bake cache를 변경하지 않는다.
- Timeline을 자동 시작하지 않고 `Stop` 상태만 허용한다.
- Apply는 유일한 내부 floor 후보 또는 명시적 `interior_bounds`가 있을 때만 허용한다.
- `/World/Characters`와 `/World/DynamicActors`만 자동 제외한다.
- Warehouse subtree의 기존 `NavMeshExcludeAPI`는 자동 제거하지 않는다.
- Stage와 외부 USD를 자동 저장하거나 덮어쓰지 않는다.
- ROS2 topic, Flask server, Ollama, LIMO 제어에는 접근하지 않는다.

---

### Task 1: Pure geometry and selection contract

**Files:**
- Create: `scripts/warehouse_navmesh_automation_config.py`
- Create: `tests/unit/test_warehouse_navmesh_automation_config.py`

**Interfaces:**
- Produces: `Bounds3D(minimum: Vector3, maximum: Vector3)`
- Produces: `FloorCandidate(path: str, bounds: Bounds3D)`
- Produces: `InteriorSelection(status: str, candidate: FloorCandidate | None, reasons: tuple[str, ...])`
- Produces: `calculate_agent_radius_cm(cart_bounds, meters_per_unit, margin_cm=10.0, minimum_cm=20.0, maximum_cm=80.0) -> float`
- Produces: `select_interior_floor(candidates, worker_position, volume_bounds, meters_per_unit, max_floor_delta_m=0.5) -> InteriorSelection`
- Produces: `replace_volume_xy(interior_bounds, current_center, current_scale, inset=0.0) -> tuple[Vector3, Vector3]`

- [x] **Step 1: Write failing calculation tests**

```python
def test_agent_radius_uses_cart_width_and_stage_units(self):
    bounds = Bounds3D((-0.4, -0.9, 0.0), (0.4, 0.9, 1.2))
    self.assertEqual(calculate_agent_radius_cm(bounds, 1.0), 50.0)

def test_selects_only_floor_containing_worker_near_feet(self):
    result = select_interior_floor(
        [FloorCandidate("/World/Floor", Bounds3D((-10, -8, -0.1), (10, 8, 0.05)))],
        worker_position=(0, 0, 0.04),
        volume_bounds=Bounds3D((-20, -20, -0.2), (20, 20, 0.5)),
        meters_per_unit=1.0,
    )
    self.assertEqual(result.status, "selected")
    self.assertEqual(result.candidate.path, "/World/Floor")
```

Add separate literal-fixture tests for ambiguous candidates, no candidate, radius below/above 20–80cm, inverted bounds, and Z-preserving XY replacement.

- [x] **Step 2: Run RED**

Run: `python3 -m unittest tests.unit.test_warehouse_navmesh_automation_config -v`

Expected: import failure because `scripts.warehouse_navmesh_automation_config` does not exist.

- [x] **Step 3: Implement minimal pure module**

Implement frozen dataclasses with finite/increasing bounds validation. Define cart width as `min(size_x, size_y)` and convert stage units through `meters_per_unit * 100`. Return `ambiguous` instead of guessing unless exactly one floor passes every filter.

- [x] **Step 4: Run GREEN**

Run: `python3 -m unittest tests.unit.test_warehouse_navmesh_automation_config -v`

Expected: all calculation and refusal-path tests pass.

### Task 2: Read-only Isaac Sim Preview

**Files:**
- Create: `scripts/configure_warehouse_navmesh.py`
- Modify: `tests/unit/test_warehouse_navmesh_automation_config.py`

**Interfaces:**
- Consumes: Task 1 dataclasses and functions
- Produces: `build_preview_report(scene: SceneSnapshot) -> dict[str, object]`
- Produces: `preview() -> dict[str, object]` for Script Editor
- Produces: `run(mode="preview", interior_bounds=None)` entry point

- [x] **Step 1: Write failing report tests**

```python
def test_preview_report_blocks_apply_when_floor_is_ambiguous(self):
    report = build_preview_report(ambiguous_scene_snapshot())
    self.assertFalse(report["apply_allowed"])
    self.assertEqual(report["interior_selection"]["status"], "ambiguous")

def test_preview_report_lists_dynamic_exclusions_without_applying_them(self):
    report = build_preview_report(valid_scene_snapshot())
    self.assertEqual(
        report["dynamic_exclusion_paths"],
        ["/World/Characters", "/World/DynamicActors"],
    )
```

The snapshots are complete real dataclass values; no Isaac Sim framework mock is used.

- [x] **Step 2: Run RED**

Run: `python3 -m unittest tests.unit.test_warehouse_navmesh_automation_config -v`

Expected: failure because `SceneSnapshot` and `build_preview_report` are absent.

- [x] **Step 3: Implement report builder and live reader**

Add `SceneSnapshot` to the pure module. In the live script, import Isaac Sim modules only inside live functions, require `timeline.is_stopped()`, traverse the composed Warehouse with `UsdGeom.BBoxCache`, collect named geometry, inspect `NavMeshExcludeAPI`, compute the Cart local-aligned bounds, and print one `WAREHOUSE_NAVMESH_PREVIEW=<json>` line. Do not call any USD setter, settings setter, command execution, or Bake API in `preview()`.

- [x] **Step 4: Run GREEN and syntax check**

Run: `python3 -m unittest tests.unit.test_warehouse_navmesh_automation_config -v`

Run: `python3 -m py_compile scripts/warehouse_navmesh_automation_config.py scripts/configure_warehouse_navmesh.py`

Expected: tests and compilation pass outside Isaac Sim.

### Task 3: Transactional Apply, restore, and Bake lifecycle

**Files:**
- Modify: `scripts/configure_warehouse_navmesh.py`
- Modify: `scripts/warehouse_navmesh_automation_config.py`
- Modify: `tests/unit/test_warehouse_navmesh_automation_config.py`

**Interfaces:**
- Consumes: valid Preview report or explicit `Bounds3D`
- Produces: `NavMeshApplyController(snapshot, apply_changes, start_bake, restore_changes)`
- Produces: `apply_and_bake(interior_bounds=None) -> asyncio.Task`
- Produces: global `restore()` handle retained in `builtins._warehouse_navmesh_automation_handle`

- [x] **Step 1: Write failing transaction tests**

```python
def test_apply_failure_restores_snapshot(self):
    events = []
    controller = NavMeshApplyController(
        capture_snapshot=lambda: "before",
        apply_changes=lambda _snapshot: (_ for _ in ()).throw(RuntimeError("apply failed")),
        start_bake=lambda: events.append("bake"),
        restore_changes=lambda snapshot: events.append(("restore", snapshot)),
    )
    with self.assertRaisesRegex(RuntimeError, "apply failed"):
        controller.run()
    self.assertEqual(events, [("restore", "before")])
```

Add tests proving invalid Preview never calls Apply/Bake and successful Apply calls capture → apply → bake exactly once.

- [x] **Step 2: Run RED**

Run: `python3 -m unittest tests.unit.test_warehouse_navmesh_automation_config -v`

Expected: failure because `NavMeshApplyController` is absent.

- [x] **Step 3: Implement transaction and live mutation adapter**

Capture exact Volume translate/scale, relevant settings, and whether the two dynamic roots already have `NavMeshExcludeAPI`. Apply only X/Y Volume changes while preserving Z, set Agent Height/Radius and Auto-Bake false, apply exclusion to the two dynamic roots, then call `start_navmesh_baking()`. Subscribe to navigation events until progress reaches completion; verify nonzero triangles and a closest point within 1m of Worker. On any exception restore the captured USD values/settings/API states and print whether a rebake is required.

- [x] **Step 4: Run GREEN**

Run: `python3 -m unittest tests.unit.test_warehouse_navmesh_automation_config -v`

Expected: calculation, Preview, and transaction tests all pass.

### Task 4: Documentation and repository verification

**Files:**
- Create: `docs/exec-plans/active/2026-09-03-warehouse-navmesh-automation.md`
- Modify: `docs/experiments/warehouse-cart-worker-context.md`

**Interfaces:**
- Consumes: final Preview/Apply API and verification output
- Produces: exact Script Editor commands, rollback procedure, measured Preview output, and live acceptance status

- [x] **Step 1: Record baseline and execution procedure**

Document current over-broad cyan Surface, fixed settings, exact paths, Preview command, Apply command, expected JSON fields, `restore()` command, and the rule not to save before visual approval.

- [x] **Step 2: Run standard checks**

Run: `bash scripts/check.sh`

Run: `bash scripts/test_offline.sh`

Run: `git diff --check`

Expected: all exit 0. Record exact dependency failures rather than reporting them as passes.

- [x] **Step 3: Review intended diff**

Verify that changes are limited to the two new scripts, their unit test, approved design/plan, active execution plan, and existing Warehouse context document.

- [x] **Step 4: Handoff Preview before Apply**

Ask the user to execute only `run(mode="preview")` first and return the single JSON output. Do not authorize Apply until `apply_allowed`, floor path, bounds, radius, static exclusions, and dynamic exclusions have been reviewed.
