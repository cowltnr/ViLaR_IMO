> Last updated: 2026-09-03 15:17 KST

# Warehouse Worker Navigation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 현재 Warehouse Stage의 Viewport Camera를 복구하고, 실제 Warehouse Bounds에 맞는 NavMesh를 Bake한 뒤 Worker 단독 이동 준비 상태를 검증한다.

**Architecture:** Stage에 저장된 Camera와 NavMesh 설정은 오프라인 검사 가능한 순수 Python 설정 계산과 Isaac Sim Runtime 작업으로 분리한다. 원본은 Timestamp Backup으로 보존하고, Headless Isaac Sim에서 Remote Asset을 완전히 로드한 후 Bounds 측정, Volume 수정, Bake 및 경로 Query를 수행한다.

**Tech Stack:** Python 3, OpenUSD, Isaac Sim 4.5.0, `omni.anim.navigation.core`, `Isaacsim.Replicator.Agent`

**Spec:** 승인된 2026-09-02 대화 설계와 `docs/experiments/warehouse-cart-worker-context.md`

## Global Constraints

- ROS2, LIMO, VLM Server와 `/sim/cmd_vel` Publisher를 실행하지 않는다.
- Warehouse와 Cart/Pallet의 기존 구성은 보존한다.
- Worker 단독 이동만 다루며 Cart 동기화는 다음 작업으로 남긴다.
- Live Stage를 수정하기 전 같은 디렉터리에 Backup을 만든다.
- 실패한 Bake와 Path Query 결과도 Context 문서에 기록한다.

---

### Task 1: Camera 및 NavMesh 설정 계산

**Files:**
- Create: `scripts/warehouse_worker_navigation_config.py`
- Test: `tests/unit/test_warehouse_worker_navigation_config.py`

**Interfaces:**
- Produces: `camera_target_distance(position, target) -> float`
- Produces: `compute_navmesh_transform(minimum, maximum, floor_z, margin_xy, below_floor, height) -> tuple`

- [x] 실패 테스트를 작성하고 현재 미구현 상태에서 실패를 확인한다.
- [x] Camera 거리와 축 정렬 NavMesh Volume Transform 계산을 구현한다.
- [x] 단위 테스트 통과를 확인한다.

### Task 2: 현재 Stage Runtime 진단

**Files:**
- Create: `scripts/setup_warehouse_worker_navigation.py`

**Interfaces:**
- Consumes: 작업 USD 경로와 Task 1 설정 계산 함수
- Produces: Warehouse/바닥 Bounds, Worker 시작점, NavMesh 후보 범위가 포함된 진단 출력

- [x] 현재 USD를 Backup하고 SHA-256을 기록한다.
- [x] Isaac Sim Headless에서 Stage와 Remote Asset을 완전히 로드한다.
- [x] Warehouse Bounds와 이름에 `floor`가 포함된 Prim Bounds를 출력한다. 전체
      Warehouse BBox 계산이 장시간 정지하여 중단했으며, 같은 방법은 재시도하지 않는다.
      대신 공식 Warehouse의 Floor 배치와 NavMeshVolume을 정적으로 검사해 범위를 확정했다.
- [x] 공식 `full_warehouse.usd`의 제작자 NavMeshVolume 값을 정적 검사하여
      Volume 범위를 결정한다.

### Task 3: Camera 복구 및 NavMesh Bake

**Files:**
- Modify: `/home/cowltnr/LimoIsaacSIM/USD/cart_simulation_env/warehouse_cart_worker.usd`
- Modify: `scripts/setup_warehouse_worker_navigation.py`

**Interfaces:**
- Produces: 복구된 Perspective Camera, 축소된 `/World/NavMeshVolume`, Bake된 NavMesh Cache 및 Query 결과

- [x] Live Viewport에서 `DynamicActors`를 선택하고 `F`를 눌러 Camera Focus를
      복구한다. USD 저장 여부는 NavMesh 검증 후 확인한다.
- [x] 공식 Warehouse NavMeshVolume Transform으로 수정한다.
- [x] NavMesh Surface 표시와 Live Query 성공으로 Bake 완료를 확인한다.
- [x] Triangle Vertex가 0보다 큼을 확인하고, Worker 최근접점에서 목적지까지
      60개 Point의 테스트 Path가 존재함을 검증한다.
- [x] NavMesh Surface를 화면에서 확인하고 Stage를 저장한다.

### Task 4: Worker 단독 이동 준비

**Files:**
- Create: `/home/cowltnr/LimoIsaacSIM/USD/cart_simulation_env/worker_commands.txt`
- Modify: `scripts/setup_warehouse_worker_navigation.py`

**Interfaces:**
- Produces: `Worker_01`의 `Idle → GoTo → Idle → 복귀` 명령과 IRA Character 설정 상태

- [x] NavMesh Query에서 검증된 점을 목적지로 선택한다.
- [x] 반복 가능한 Worker Command File을 작성한다.
- [x] `/World/Characters/Worker_01`에 Character Animation/Behavior 설정을 적용한다.
- [x] Timeline에서 Worker만 왕복하고 Cart가 정지하는지 확인한다.

현재 상태: Animation Graph, Behavior Script, NavMesh 왕복 명령을 적용하고
저장했다. Worker 단독 왕복과 Cart 정지를 Live Isaac Sim에서 확인했으며,
Cart Pose 동기화는 별도 후속 작업으로 남긴다.

### Task 5: 문서와 최종 검증

**Files:**
- Modify: `docs/experiments/warehouse-cart-worker-context.md`
- Modify: `docs/index.md` only if a new maintained document is introduced
- Move: this plan to `docs/exec-plans/completed/`

- [x] 측정값, Backup, 명령 파일, 성공·실패 결과와 남은 한계를 기록한다.
- [x] `bash scripts/check.sh`와 `bash scripts/test_offline.sh`를 실행한다.
- [x] USD의 Animation Graph 및 Behavior Script 관계와 Command File을 정적으로 검증한다.
- [x] 모든 기준 충족 후 계획을 `completed/`로 이동한다.
