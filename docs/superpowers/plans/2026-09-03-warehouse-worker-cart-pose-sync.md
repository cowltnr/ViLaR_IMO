> Last updated: 2026-09-03 15:30 KST

# Warehouse Worker–Cart Pose Sync Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Worker Animation Graph runtime pose를 따라 CartAssembly 전체가 현재 상대 배치를 유지하며 이동하는 Script Editor 도구를 제공한다.

**Architecture:** Isaac Sim에 의존하지 않는 pose math를 분리하여 offline unit test로 검증한다. Live adapter는 Animation Graph character pose를 읽고 Session Layer에 CartAssembly transform override를 기록하며, Stop 또는 재설정 시 해당 override만 제거한다.

**Tech Stack:** Python 3.10, `unittest`, Isaac Sim 4.5.0, USD `Gf`/`Sdf`/`UsdGeom`, `omni.anim.graph.core`, `omni.kit.app`, `omni.timeline`

**Spec:** `docs/superpowers/specs/2026-09-03-warehouse-worker-cart-pose-sync-design.md`

## Global Constraints

- 원본 `warehouse_cart_worker.usd`를 스크립트가 자동 저장하거나 덮어쓰지 않는다.
- Runtime transform은 Session Layer에만 기록하고 `STOP`에서 제거한다.
- ROS2 topic, Flask server, LIMO 제어에는 접근하지 않는다.
- 기존 Worker command, NavMesh, Animation Graph와 pallet 계층은 변경하지 않는다.
- Live Isaac Sim 검증은 사용자가 직접 Play/Stop하며 수행한다.

---

### Task 1: Offline pose math contract

**Files:**
- Create: `tests/unit/test_warehouse_worker_cart_pose_sync.py`
- Create: `scripts/warehouse_worker_cart_pose_sync.py`

**Interfaces:**
- Produces: `normalize_quaternion_xyzw(quaternion)`, `compose_pose(parent_pose, child_pose)`, `relative_pose(parent_pose, child_pose)`
- Pose type: `(position_xyz, quaternion_xyzw)` where both members are numeric tuples

- [x] **Step 1: Write the failing tests**

```python
def test_relative_pose_round_trip_preserves_cart_pose(self):
    worker = ((1.0, 2.0, 0.0), (0.0, 0.0, 0.0, 1.0))
    cart = ((1.05, 3.185, 0.0), (0.0, 0.0, 0.0, 1.0))
    self.assertPoseAlmostEqual(compose_pose(worker, relative_pose(worker, cart)), cart)

def test_compose_rotates_offset_with_worker(self):
    worker = ((2.0, 3.0, 0.0), (0.0, 0.0, 2 ** -0.5, 2 ** -0.5))
    relative = ((0.0, 1.0, 0.0), (0.0, 0.0, 0.0, 1.0))
    self.assertPoseAlmostEqual(compose_pose(worker, relative), ((1.0, 3.0, 0.0), worker[1]))
```

- [x] **Step 2: Run the test to verify RED**

Run: `python3 -m unittest tests.unit.test_warehouse_worker_cart_pose_sync -v`

Expected: import failure because `scripts.warehouse_worker_cart_pose_sync` does not exist.

- [x] **Step 3: Implement minimal pose math**

Implement tuple validation, quaternion normalization, multiplication, conjugation,
vector rotation, pose composition, and relative-pose calculation without importing
Isaac Sim modules at module import time.

- [x] **Step 4: Run the focused test to verify GREEN**

Run: `python3 -m unittest tests.unit.test_warehouse_worker_cart_pose_sync -v`

Expected: all pose math and validation tests pass.

### Task 2: Isaac Sim runtime synchronizer

**Files:**
- Modify: `scripts/warehouse_worker_cart_pose_sync.py`
- Modify: `tests/unit/test_warehouse_worker_cart_pose_sync.py`

**Interfaces:**
- Consumes: Task 1 pose functions
- Produces: `run(worker_skelroot_path, cart_path)` returning a live synchronizer; `stop()` for safe callback cleanup

- [x] **Step 1: Add failing state-machine tests**

Use small real fake objects implementing the synchronizer's injected callbacks and
assert these observable outcomes: calibration occurs once, paused updates do not
write poses, playing updates do, and stop clears the Cart session override.

- [x] **Step 2: Run the focused test to verify RED**

Run: `python3 -m unittest tests.unit.test_warehouse_worker_cart_pose_sync -v`

Expected: failures for the missing `PoseSyncController` behavior.

- [x] **Step 3: Implement the runtime adapter and controller**

Implement `PoseSyncController` with injected `read_worker_pose`, `read_cart_pose`,
`write_cart_pose`, `clear_cart_override`, and `is_playing` callables. Add an Isaac Sim
adapter that validates the prims and character, subscribes to app/timeline events,
authors only `xformOp:translate` and `xformOp:orient` in the Session Layer, and removes
only those session-layer property specs on Stop.

- [x] **Step 4: Run the focused test to verify GREEN**

Run: `python3 -m unittest tests.unit.test_warehouse_worker_cart_pose_sync -v`

Expected: all controller and pose tests pass.

### Task 3: Documentation and standard verification

**Files:**
- Modify: `docs/experiments/warehouse-cart-worker-context.md`
- Modify: `docs/exec-plans/active/2026-09-03-warehouse-worker-cart-pose-sync.md`

**Interfaces:**
- Consumes: final script behavior and verification output
- Produces: exact Script Editor procedure, validation state, and remaining limitations

- [x] **Step 1: Document the operator procedure**

Record that the operator keeps Timeline stopped, runs
`scripts/warehouse_worker_cart_pose_sync.py` in Script Editor, presses Play, checks
Worker/Cart/Pallet round trip, and presses Stop. Explicitly state that no Ctrl+S is
required for the runtime sync.

- [x] **Step 2: Run standard checks**

Run: `bash scripts/check.sh`

Run: `bash scripts/test_offline.sh`

Run: `git diff --check`

Expected: all commands exit 0. If an environment dependency fails, record the exact
error rather than claiming success.

- [x] **Step 3: Review the final diff**

Verify that only the new sync script, its test, the approved design/plan, active
execution plan, context documentation, and required index/timestamp updates changed.

- [x] **Step 4: Prepare live handoff**

Provide the exact Script Editor execution steps. Keep the execution plan active until
the user reports the Isaac Sim acceptance criteria; then record the result and move it
to `docs/exec-plans/completed/`.
