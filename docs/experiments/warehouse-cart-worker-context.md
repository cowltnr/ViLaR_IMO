> Last updated: 2026-09-03 19:48 KST

# Warehouse Cart Worker 작업 Context

## 목적

Isaac Sim 4.5.0 Warehouse에서 작업자가 Pallet 두 개를 적재한 Pushcart를
미는 장면을 구성한다. 물리적으로 화물을 운반하는 방식이 아니라, 작업자
Pose에 `CartAssembly`를 동기화하는 시각적·Kinematic 방식을 사용한다.

Context 복구 시 이 문서와 다음 파일을 먼저 확인한다.

- `assets/isaac_sim/cart_simulation_env/warehouse_cart_worker.usd`
- `assets/isaac_sim/cart_simulation_env/warehouse_cart.usd`
- `docs/safety/robot-safety.md`

## 현재 파일과 Asset

| 항목 | 위치 또는 상태 |
|---|---|
| 작업 Stage | `assets/isaac_sim/cart_simulation_env/warehouse_cart_worker.usd` |
| 원본 Stage | `assets/isaac_sim/cart_simulation_env/warehouse_cart.usd` |
| Pushcart | 2026-09-02 authoring 당시 외부 로컬 Asset의 historical absolute path: `/home/cowltnr/isaacsim_assets/Assets/Isaac/4.5/Isaac/Environments/Simple_Warehouse/Props/SM_PushcartA_02.usd`. 다른 환경에서는 해당 Reference를 해석할 Asset이 필요하다. |
| Pallet | NVIDIA 원격 `Isaac/Props/Pallet/o3dyn_pallet.usd` Payload |
| Warehouse | NVIDIA 원격 `Isaac/Environments/Simple_Warehouse/full_warehouse.usd` Reference |
| Worker | NVIDIA 원격 `People/DH_Characters_Extended/3ca0be41-0420-11ef-933e-b40ede968205/plain.usd` Reference |

Pushcart와 필요한 MDL/Texture 약 26MB는 로컬 Asset Root에 선별 설치했다.
Isaac Sim Asset Pack 1 전체는 설치하지 않았다.

## 목표 Stage 구조

```text
/World
├── Environment
│   └── Warehouse
└── DynamicActors
    ├── CartAssembly
    │   ├── Pushcart
    │   ├── o3dyn_pallet_lower
    │   └── o3dyn_pallet_upper
    └── Characters
        └── Worker_01
```

Warehouse는 정적 환경으로 유지한다. Cart와 Pallet은 `CartAssembly`의
자식으로 묶고, Worker는 별도 Actor로 둔다. People Simulation이 Worker를
이동시키면 Python Callback이 Worker Pose와 방향을 읽어 CartAssembly를
손잡이 앞쪽 Offset에 배치한다.

## 2026-09-02 정적 검사 결과

검사는 Isaac Sim, Timeline, ROS2를 시작하지 않고 bundled OpenUSD
라이브러리로 수행했다.

- `warehouse_cart_worker.usd`는 정상적으로 열리는 USDC 0.8.0 파일이다.
- Stage는 `Z-up`, `metersPerUnit = 1.0`, Default Prim은 `/World`이다.
- Warehouse, CartAssembly, Pallet 두 개, Worker의 상위 계층은 목표 구조와
  일치한다.
- 검사 당시 파일 SHA-256은
  `2a4d8ea3c50686c5ea933b3dd189ef542a8ae4779edb423787abc24b3c324ec7`이다.
- 일반 OpenUSD 검사기의 원격 HTTP Reference 경고는 Isaac Sim HTTP
  Resolver를 사용하지 않은 정적 검사의 한계다. 원격 Worker URL은 HTTP
  200으로 존재를 확인했다.

## 확인된 문제

1. `/World/DynamicActors/CartAssembly/Pushcart`에 다음 Reference 네 개가
   누적되어 있다.

   ```text
   SM_PushcartA_01.usd
   SM_PushcartA_03.usd
   SM_PushcartB.usd
   SM_PushcartA_02.usd
   ```

   로컬에는 A02만 있으므로 A01, A03, B Reference를 제거하고 A02 하나만
   남겨야 한다. 원인은 같은 Prim에 `add_reference_to_stage()`를 반복 실행한
   것이다.

2. 두 Pallet에 이전 Simulation의 `physics:velocity`와
   `physics:angularVelocity`가 저장되어 있다. Timeline 재생 시 Pallet이
   움직이거나 회전할 수 있다.

3. 원본 `o3dyn_pallet.usd`의 Root Prim에는 `PhysicsRigidBodyAPI`가 적용되어
   있고 `physics:rigidBodyEnabled = true`, `physics:kinematicEnabled = false`,
   `physics:mass = 60.0`이다. 시각적 고정 방식에서는 각 Pallet Root에
   Kinematic Override를 적용하고 저장된 속도를 0으로 초기화해야 한다.

4. `CartAssembly` 원점은 `(0, 0, 0)`인데 Pushcart Local 위치는
   `(0.05092745, -0.03272356, 0)`이다. Worker 동기화 Offset을 명확하게 하기
   위해 CartAssembly 원점을 현재 Cart 위치로 옮기고 Pushcart를 Local 원점에
   두는 정규화가 필요하다.

## 2026-09-02 수정 결과

`warehouse_cart_worker.usd`의 정적 구조 수정과 오프라인 검증을 완료했다.

- 수정 전 Backup:
  `assets/isaac_sim/cart_simulation_env/backups/warehouse_cart_worker.pre_fix_20260902_1708.usd`
- Backup SHA-256:
  `2a4d8ea3c50686c5ea933b3dd189ef542a8ae4779edb423787abc24b3c324ec7`
- 수정 파일 SHA-256:
  `202cdfc121303d319637c26be83e1953e21a21ea6b6035e56bbc2510da0c3285`
- Pushcart Reference는 로컬 `SM_PushcartA_02.usd` 하나만 남겼다.
- `CartAssembly`를 기존 Pushcart 위치로 옮기고 Pushcart Local 위치를
  `(0, 0, 0)`으로 정규화했다.
- Pallet 두 개는 기존 World 위치가 유지되도록 Local 위치를 보정했다.
- Pallet 두 개에 `physics:kinematicEnabled = true`를 적용하고 저장된 선속도와
  각속도를 0으로 초기화했다.
- 수정 후 파일을 새로 열어 계층, Reference, Transform, Kinematic 상태와
  속도 값을 재검증했다.
- `bash scripts/check.sh`와 `bash scripts/test_offline.sh`가 최종 단독 실행에서
  통과했다.

Isaac Sim Timeline을 이용한 외형, Remote Asset 해석, People Simulation 동작은
아직 검증하지 않았다. Live 검증은 사용자 승인 후 수행해야 한다.

## Worker 동작 제약

- 기본 People Simulation은 `GoTo`, `Idle` 등의 보행 동작을 제공한다.
- 기본 Asset에는 자연스러운 Pushcart 전용 손·팔 Animation이 없다.
- Worker는 걷고 CartAssembly가 앞에서 동기화되는 방식으로 연출한다.
- Cart가 Worker의 NavMesh 반경에 포함되지 않으므로 넓은 직선 통로에서
  먼저 검증한다.
- Worker–Cart 동기화 Python Callback과 People Simulation Command File은
  USD에 자동 저장되지 않으며 별도 파일로 관리해야 한다.

## 2026-09-03 Worker Navigation 진행 상태

### Viewport 조작 불능 원인과 복구

- 작업 Stage에 저장된 Perspective Camera의 `position`과 `target` 간 거리가
  약 `0.007 m`로 줄어 있었다. Viewport의 Zoom/Pan 이동량이 Focus 거리의
  영향을 받아 Mouse Wheel이 동작하지 않는 것처럼 보인 상태였다.
- 사용자가 Stage의 `DynamicActors`를 선택하고 `F`를 눌러 Framing하자
  Zoom과 이동이 정상화되었다. Stage 전체가 아니라 해당 Prim을 대상으로
  Camera Focus를 다시 잡은 것이 복구에 효과가 있었다.
- 이 결과로 GPU, Mouse Hardware, Isaac Sim 전역 설정 문제가 아니라 현재
  Stage에 한정된 Camera Focus 문제였음이 확인되었다.

### NavMeshVolume 진단

- NavMesh 수정 전 Backup은
  `assets/isaac_sim/cart_simulation_env/backups/warehouse_cart_worker.pre_navigation_20260903_1317.usd`로 이동·보존돼 있다.
  작업 파일과 Backup의 SHA-256은 모두
  `a850a09c37297e93adb30e8dd270ca7bd5beb6cdb545a817810fe1466d4de00c`이다.
- 현재 `/World/NavMeshVolume`의 `scale = (450, 450, 450)`은 Isaac Sim의
  `CreateNavMeshVolumeCommand`가 첫 Volume을 만들 때 전체 Stage Bounding Box와
  최소 크기 `400`, Padding `50`을 사용하면서 자동 생성된 값이다.
- Headless Isaac Sim에서 Remote Asset 로딩은 완료되었지만, 합성된 Warehouse
  전체 BBox 계산이 장시간 완료되지 않아 해당 진단 방식은 중단했다. 이 실행은
  진단 전용이었으며 USD를 수정하지 않았다.
- 대신 공식 `full_warehouse.usd`를 OpenUSD로 정적 검사했다. 제작자가 포함한
  `/Navmesh/NavMeshVolume`의 값은 다음과 같다.

  ```text
  Translate = (-10.0, 3.593179408, 0.152315379)
  Rotate    = (0.0, 0.0, 0.0)
  Scale     = (36.114853, 60.0, 0.58926105)
  ```

- 작업 Stage는 Warehouse의 `/Root`만 `/World/Environment/Warehouse`에
  Reference하므로, 공식 USD의 형제 Prim인 `/Navmesh`는 함께 합성되지 않는다.
  따라서 작업 Stage의 `/World/NavMeshVolume`은 유지하되 위 Transform으로
  교체한 뒤 다시 Bake해야 한다.

### 다음 검증 순서

1. 열린 Isaac Sim에서 `/World/NavMeshVolume`에 공식 Transform을 적용한다.
2. `Window > Navigation > NavMesh`에서 `Bake`를 실행한다.
3. Viewport의 Eye 메뉴에서 `Navigation > NavMesh`를 켜고 Warehouse 통로에
   NavMesh 표면이 생성되었는지 확인한다.
4. Bake 성공 후에만 Worker 시작점과 목적지 사이의 `query_shortest_path()`를
   검증하고 `worker_commands.txt`를 작성한다.
5. `Worker_01`에 Animation Graph와 Behavior Script를 설정하여 단독 이동을
   검증한다. Cart 동기화는 이 단계 이후 별도 작업으로 진행한다.

### Animation Graph 적용 준비

- [`ref_img/navmesh.png`](../../ref_img/navmesh.png)에서
  청록색 NavMesh Surface가 Warehouse 바닥 통로에 생성된 것을 확인했다.
- 현재 저장된 작업 USD는 Camera Focus와 공식 Warehouse NavMeshVolume
  Transform을 포함한다. SHA-256은
  `e28d82a9e1fa6d79ee34298a802d022cc06783370d048531cad2be3da04e10d8`이다.
- `scripts/configure_warehouse_worker_animation.py`는 실행 중인 Isaac Sim의
  Script Editor에서 사용할 Live Stage 설정 스크립트다. 기본 Biped Animation
  Asset을 로드하고 `Worker_01` 아래의 SkelRoot에만 Animation Graph를 적용한 뒤
  관계 Target을 검증한다. Stage는 자동 저장하지 않는다.
- `tests/unit/test_configure_warehouse_worker_animation.py`는 다른 Character와
  `Biped_Setup`의 SkelRoot가 선택되지 않는지, 대상 SkelRoot가 없을 때 명시적으로
  실패하는지 검증하며 두 테스트가 통과했다.
- Animation Graph만으로 Worker 위치는 바뀌지 않는다. 방향 지정 이동에는
  Behavior Script와 `GoTo` 명령이 필요하고, Cart 동반 이동에는 별도의
  Worker–`CartAssembly` Pose 동기화 Callback이 필요하다.

### Animation Graph 적용 결과와 Worker 단독 이동 준비

- 저장된 `/World/Characters/Worker_01/DHGen/SkelRoot`에
  `AnimationGraphAPI`와 `/World/Characters/Biped_Setup/CharacterAnimation/AnimationGraph`
  Target이 기록된 것을 정적으로 확인했다.
- 공식 `Biped_Setup.usd` Reference가 `/World/Characters/Biped_Setup`에 저장됐다.
- Animation Graph 저장 후 USD SHA-256은
  `0c70b3d2b3f5ea3efb3c155d85ad1274b1e1d37e07bac67f22416d0253cfdd3d`이다.
- Behavior 적용 전 Backup은
  `assets/isaac_sim/cart_simulation_env/backups/warehouse_cart_worker.pre_behavior_20260903_1441.usd`이며
  같은 SHA-256을 확인했다.
- `scripts/configure_warehouse_worker_behavior.py`는 Live NavMesh에서 Worker
  시작점에 가까운 점과 4–6 m 거리의 연결 가능한 목적지를 Query한다. 성공 시
  기본값인 `assets/isaac_sim/cart_simulation_env/worker_commands.txt`에
  `Idle → GoTo → Idle → 출발점 복귀 → Idle` 명령을 기록하고, 공식
  People Behavior Script를 Worker SkelRoot에 연결한다. 통합 Bootstrap에서는
  `VILAR_WORKER_COMMAND_FILE`로 절대 경로 Override를 지정할 수 있다.
- 이 스크립트는 Stage를 저장하거나 Timeline을 시작하지 않으며, Cart에는
  어떠한 이동 설정도 적용하지 않는다.

### Worker 단독 왕복 Live 검증 결과

- `Worker_01`의 NavMesh 최근접 시작점은
  `(-0.000, -1.217722, 0.042701)`, 선택된 목적지는
  `(0.000, 4.782278, 0.042701)`이다.
- 시작점과 목적지 사이 `query_shortest_path()`는 60개 Path Point를 반환했다.
- 생성된 `worker_commands.txt`는 2초 대기, 약 6 m 전진, 3초 대기,
  출발점 복귀, 3초 대기의 5개 명령으로 구성된다.
- 사용자가 Isaac Sim Timeline에서 Worker의 정상 왕복과 Cart/Pallet의 정지를
  확인했다. 따라서 Worker 단독 이동 Baseline은 Live 검증을 통과했다.
- 저장된 `/World/Characters/Worker_01/DHGen/SkelRoot`에는
  `AnimationGraphAPI`, `OmniScriptingAPI`, 공식
  `omni.anim.people/scripts/character_behavior.py`가 기록돼 있다.
- 검증 후 작업 USD SHA-256은
  `f98cb28fcbd07e8d0c26e54382ed111bee1ab45fe466afdbb2ccbecbe191e65b`,
  Command File SHA-256은
  `c30fbef63f1cf9b777f4d5fcb4080a94fe7fb71b48c811a531bfe447a1c17dbc`이다.
- `command_file_path`는 Isaac Sim Runtime Setting이므로 재시작 후에는
  `configure_warehouse_worker_behavior.py`를 다시 실행해야 한다. USD에 저장된
  Animation Graph 및 Behavior Script 관계는 유지된다.
- 다음 연구 구현은 Worker World Pose와 Heading을 읽어 `CartAssembly`를
  손잡이 Offset에 배치하는 Kinematic Pose 동기화다.
- 최종 검증에서 `bash scripts/check.sh`와 `bash scripts/test_offline.sh`가
  각각 25개 테스트, 0개 실패로 통과했다. Worker 단독 Navigation 실행 계획은
  `docs/exec-plans/completed/2026-09-02-warehouse-worker-navigation.md`로 이동했다.

## 2026-09-03 Worker–Cart Pose Sync 완료 상태

### 구현 방식

- `scripts/warehouse_worker_cart_pose_sync.py`는 Animation Graph가 실제로
  이동시키는 `/World/Characters/Worker_01/DHGen/SkelRoot`의 runtime world pose를
  매 update frame마다 읽는다.
- Play 후 첫 유효 runtime frame에서 Worker와 Cart의 현재 pose를 이용해
  상대 transform을 한 번 자동 보정한다. `ag.get_character()`는 runtime에서만
  유효하므로 Timeline이 정지된 설정 시점에는 보정하지 않는다.
- 이후 `T_cart = T_worker × T_relative` 관계로
  `/World/DynamicActors/CartAssembly`를 갱신한다. Pushcart와 두 Pallet은
  CartAssembly의 자식이므로 함께 이동한다.
- Cart translate/orient는 Session Layer에만 기록된다. 원본 USD를 자동 저장하지
  않으며 Timeline Stop 시 해당 두 property override만 제거한다.
- 같은 Script를 다시 실행하면 이전 update/timeline subscription을 먼저 해제하여
  중복 callback을 방지한다.

### Offline 검증

- identity pose의 상대 위치 보존, 90도 회전 시 offset 회전, 회전된 초기 pose의
  상대 transform 복원, zero-length quaternion 및 잘못된 position 길이 거부를
  검증한다.
- Play/Pause/Stop 상태 제어기 test는 정지 상태 무기록, 첫 Play 보정, 후속 pose
  갱신, Stop 시 override 제거와 재보정을 검증한다.
- Focused test `tests.unit.test_warehouse_worker_cart_pose_sync`의 9개 test가
  통과했다. `bash scripts/check.sh`와 `bash scripts/test_offline.sh`도 각각
  34개 test로 통과했고 `git diff --check`와 새 파일 `py_compile`이 통과했다.
  Sandbox 내부 실행에서는 unrelated LibreOffice test가 dconf 쓰기 제한으로
  실패했지만, 동일 명령을 정상 권한 환경에서 재실행하여 통과를 확인했다.
- 사용자가 Isaac Sim live 검증을 완료했다. Worker와 CartAssembly 및 두 Pallet의
  동반 왕복, 방향 전환 시 초기 상대 배치 유지, Stop 시 Cart 초기 위치 복원을
  확인한 것으로 기록한다.
- Worker–Cart Pose Sync 실행 계획은
  `docs/exec-plans/completed/2026-09-03-warehouse-worker-cart-pose-sync.md`로
  완료 처리했다.

### 과거 단독 Isaac Sim Script Editor 실행 절차 (historical snapshot)

아래 절차는 통합 Bootstrap 이전의 단독 Pose sync 검증 기록이다. 현재 재개에는
뒤의 `통합 Runtime Bootstrap` 절차를 사용한다. 과거 절차를 진단 목적으로 다시
사용해야 한다면 machine-specific 경로 대신 현재 clone root와 repository-relative
script 경로를 조합한다.

1. `warehouse_cart_worker.usd`를 열고 Timeline을 `Stop` 상태로 둔다.
2. 기존 Worker Behavior와 `worker_commands.txt` 설정이 현재 runtime에 적용되어
   있는지 확인한다. Isaac Sim 재시작 후라면 먼저
   `scripts/configure_warehouse_worker_behavior.py`를 실행한다.
3. Script Editor에서 다음 코드를 실행한다.

   ```python
   from pathlib import Path

   repo = Path("/absolute/path/to/ViLaR_IMO").resolve()
   exec((repo / "scripts/warehouse_worker_cart_pose_sync.py").read_text(
       encoding="utf-8"
   ))
   ```

4. `[Worker-Cart Sync] READY`가 출력되면 Play를 누른다.
5. `[Worker-Cart Sync] CALIBRATED` 출력 후 Worker, Cart, 두 Pallet이 왕복하고
   방향 전환 시 초기 상대 배치를 유지하는지 확인한다.
6. Stop을 누르고 `[Worker-Cart Sync] STOPPED` 출력과 Cart 초기 위치 복원을
   확인한다.

Pose sync는 runtime 전용이므로 이 단계에서는 `Ctrl+S`가 필요하지 않다.
Worker Behavior와 command setting이 재시작으로 사라진 경우에만 Behavior 설정
스크립트를 다시 실행한다.

## 2026-09-03 Warehouse NavMesh 자동화 진행 상태

### 해결하려는 문제와 방식

- 현재 cyan NavMesh Surface가 Warehouse 벽 밖 바닥과 선반·장애물 상판까지
  넓게 생성된 상태를 Baseline으로 둔다.
- `scripts/configure_warehouse_navmesh.py`는 열린 composed Stage를 읽는
  `Preview`와 검증 후 USD/settings를 바꾸는 `Apply`를 분리한다.
- `Preview`는 Warehouse floor 후보, 현재 Volume, Worker 시작점, Cart local
  bounds, static structure, 기존 `NavMeshExcludeAPI`를 읽기만 한다.
- Cart의 두 수평 길이 중 작은 값을 폭으로 보고
  `폭 / 2 + 10cm`를 Agent Radius로 제안한다. 20–80cm를 벗어나면 Apply를
  차단한다.
- 단일 내부 floor 후보가 없거나 둘 이상이면 임의로 고르지 않고
  `apply_allowed=false`를 출력한다. 이 경우 Preview 결과를 보고 명시적
  `interior_bounds`를 결정한다.
- Apply는 `/World/Characters`와 `/World/DynamicActors`에만
  `NavMeshExcludeAPI`를 추가한다. Warehouse의 벽·선반·정적 장애물은 제외하지
  않아 Bake 시 obstacle로 사용한다.
- Apply/Bake 실패 시 Volume transform, NavMesh settings, dynamic exclusion
  상태를 memory snapshot으로 복구한다. Stage와 runtime NavMesh cache는 자동
  저장하지 않는다.

### 과거 단독 Preview 실행 절차 (historical snapshot)

이 블록은 통합 Bootstrap 이전의 NavMesh Preview 절차다. 현재 재개에는 통합
Bootstrap을 사용하고, NavMesh만 진단할 때 아래 repository-relative script를
사용한다.

1. `warehouse_cart_worker.usd`를 열고 asset 로딩이 끝난 뒤 Timeline을 반드시
   `Stop` 상태로 둔다.
2. Script Editor에서 다음 코드만 실행한다.

   ```python
   import sys
   from pathlib import Path

   repo = Path("/absolute/path/to/ViLaR_IMO").resolve()
   if str(repo) not in sys.path:
       sys.path.insert(0, str(repo))

   exec((repo / "scripts/configure_warehouse_navmesh.py").read_text(
       encoding="utf-8"
   ))
   ```

3. Console의 `WAREHOUSE_NAVMESH_PREVIEW={...}` 한 줄을 복사한다.
4. 이 단계에서는 `Ctrl+S`, Play, Bake를 실행하지 않는다. Preview는 USD,
   settings, Bake cache를 변경하지 않는다.

확인할 핵심 필드는 `apply_allowed`, `blocking_reasons`,
`interior_selection`, `floor_candidates`, `proposed_volume`,
`proposed_agent_radius_cm`, `warehouse_excluded_paths`,
`dynamic_exclusion_paths`다.

### 검토 후 사용할 Apply와 복구 API

Preview 결과가 검토되기 전에는 다음 API를 실행하지 않는다. 단일 floor가 자동
선택된 경우 `run(mode="apply")`를 사용하고, floor가 모호하여 검토한 bounds를
직접 지정할 때만 아래처럼 최소·최대 좌표를 제공한다.

```python
run(mode="apply", interior_bounds=((min_x, min_y, min_z), (max_x, max_y, max_z)))
```

Apply 성공 후 cyan Surface/Outline을 육안 검증하기 전에는 `Ctrl+S`를 누르지
않는다. 결과가 잘못되면 다음을 실행하고 기존 설정으로 다시 Bake해야 한다.

```python
restore()
```

현재까지 순수 계산, Preview report, transaction/rollback의 21개 focused test와
두 script의 `py_compile`이 통과했다. Live Preview 및 Apply/Bake도 실행됐으며,
대표 Worker–Cart 왕복 경로 검증과 저장 여부 확인이 남아 있다.

### Live Preview 결과

- 2026-09-03 사용자가 Isaac Sim 4.5.0 Script Editor에서 Preview를 실행했다.
- Stage 단위는 `1m/unit`, up axis는 `Z`, Timeline은 `stopped`로 확인됐다.
- Cart local horizontal size의 작은 값은 약 `0.9357m`이며 제안 Agent Radius는
  `56.785cm`다.
- 원본 floor 후보 168개는 parent/child hierarchy의 동일 bounds를 포함한다.
  bounds 중복 제거 후 57개이며 Worker 높이와 같은 ground 후보는 55개다.
- 이 중 54개는 `6m × 6m` 정규 floor tile의 `6열 × 9행` 배치다. 나머지 1개는
  약 `1.077m × 2.154m` 크기의 이름에 `floor`가 포함된 구조물로 구분된다.
- 정규 ground tile 합집합은 `X=-28.0~8.0`, `Y=-23.4~30.6`이다.
- 현재 Volume은 `X=-28.0574~8.0574`, `Y=-26.4068~33.5932`이므로 바닥보다
  X 양끝 약 `0.057m`, Y 양끝 약 `3m` 넓다.
- 자동 단일 후보 선택은 동일 타일의 hierarchy 3개가 Worker를 포함하여
  `3 floor candidates matched`로 안전하게 차단됐다. 한 타일만 선택하면
  Warehouse 전체 통로가 사라지므로 이 후보는 Apply에 사용하지 않는다.
- `warehouse_excluded_paths=[]`로 정적 Warehouse에 잘못 적용된 exclusion은 없다.
  예정 dynamic exclusion은 `/World/Characters`, `/World/DynamicActors`다.
- 검토된 명시적 Apply 후보는 `((-28.0, -23.4, -0.001),
  (8.0, 30.6, 0.001))`이다. Apply adapter는 이 값의 X/Y만 사용하고 현재 Volume
  Z center/scale을 보존한다.

### Live Apply/Bake 결과

- 사용자가 검토된 명시적 bounds로 Apply/Bake를 실행하고 cyan Surface가 원하는
  범위에 적용됐음을 육안 확인했다.
- 적용값은 Agent Height `180cm`, Agent Radius `56.785014cm`, Volume
  `X=-28.0~8.0`, `Y=-23.4~30.6`이다.
- Bake 결과는 `status=verified`, `triangle_count=241`이다.
- Worker closest point는
  `(-0.006862, -1.382673, 0.042701)`이고 Worker와의 거리는
  `0.042701m`로 1m 허용 기준을 만족한다.
- 출력의 `saved=false`는 Script가 Stage를 자동 저장하지 않았다는 뜻이다.
  Volume과 `NavMeshExcludeAPI` authoring은 사용자가 시각·왕복 검증 후
  `Ctrl+S`로 저장해야 한다.
- Agent Radius/Height와 Bake 결과는 runtime navigation settings/cache이므로 USD
  저장만으로 재시작 후 동일 상태가 보장되지 않는다. 재시작 후에는 설정 재적용과
  Bake 상태 확인이 필요하다.

## 2026-09-03 통합 Runtime Bootstrap

### 목적과 동작

- `scripts/setup_warehouse_runtime.py`는 Isaac Sim 재시작 후 필요한 작업을
  `PRECHECK → NAVMESH → WORKER_BEHAVIOR → CART_SYNC → READY` 순서로 실행한다.
- Precheck는 정확한 `warehouse_cart_worker.usd`, Timeline Stop, Warehouse,
  NavMeshVolume, Worker/SkelRoot, DynamicActors/CartAssembly prim을 확인한다.
- 새 NavMesh가 필요하면 검증된 내부 bounds
  `((-28.0, -23.4, -0.001), (8.0, 30.6, 0.001))`로 Apply/Bake한다. 현재
  Isaac Sim session에 앞서 검증된 NavMesh handle과 유효한 triangle이 있으면
  이를 재사용하며 임의로 되돌리지 않는다.
- Worker 설정 전에 People runtime setting과 기존 `worker_commands.txt`를
  snapshot한다. 이후 단계가 실패하면 Cart callback, Worker snapshot, 이번
  실행에서 새로 적용한 NavMesh를 역순으로 복구한다.
- 성공해도 Play와 Stage 저장은 수행하지 않는다. READY 확인 후 사용자가 직접
  Play를 누른다.

### Script Editor 실행

기본 Stage와 command file은 각각
`assets/isaac_sim/cart_simulation_env/warehouse_cart_worker.usd`와
`assets/isaac_sim/cart_simulation_env/worker_commands.txt`다. 다른 절대 경로를
사용할 때만 Isaac Sim을 시작한 같은 환경에서 `VILAR_WAREHOUSE_STAGE`와
`VILAR_WORKER_COMMAND_FILE`을 설정한다. Stage 로딩 완료 및 Timeline Stop
상태에서 현재 clone root를 지정하고 다음 코드만 실행한다.

```python
import sys
from pathlib import Path

repo = Path("/absolute/path/to/ViLaR_IMO").resolve()
if str(repo) not in sys.path:
    sys.path.insert(0, str(repo))

exec((repo / "scripts/setup_warehouse_runtime.py").read_text(encoding="utf-8"))
```

Console에 아래 순서가 표시되고 마지막 `WAREHOUSE_RUNTIME_READY={...}`가 나오면
구성이 완료된 것이다.

```text
[Warehouse Runtime] PRECHECK OK
[Warehouse Runtime] NAVMESH OK
[Warehouse Runtime] WORKER_BEHAVIOR OK
[Warehouse Runtime] CART_SYNC OK
[Warehouse Runtime] READY
```

같은 Isaac Sim session에서 READY 상태로 다시 실행하면 기존 session을 반환하여
중복 Bake와 callback 설치를 막는다. callback과 Worker runtime setting만 정리할
때는 Script가 실행된 namespace에서 다음을 호출한다.

```python
shutdown_warehouse_runtime()
```

Isaac Sim 재시작 후에는 repository-relative 작업 Stage를 다시 열고 필요하면 두
환경변수 Override를 같은 값으로 복원한 뒤 통합 Bootstrap을 다시 실행한다.
앞의 historical standalone 절차들을 순서대로 반복할 필요는 없다.

현재 통합 스크립트도 기존 baseline인 `약 6m 이동 → 대기 → 출발점 복귀`만
구성한다. NavMesh 전체를 사용할 수 있지만 자유 순찰은 목적지 생성기가 별도로
필요하므로 이번 변경 범위에는 포함하지 않았다.

### 첫 Live Bootstrap 결과

- 사용자가 통합 스크립트를 실행하여 `WAREHOUSE_RUNTIME_READY` 출력을 확인했다.
- Precheck는 대상 Stage, Timeline Stop, 필수 prim 7개를 모두 통과했다.
- NavMesh는 새로 Bake하지 않고 기존 handle을 재사용했으며
  `status=verified_existing`, `triangle_count=151`이다.
- Worker 시작점은 `(-0.006862, -1.382673, 0.042701)`, 목적지는
  `(-0.006862, 4.617327, 0.042701)`이고 shortest path point는 21개다.
- Worker Behavior와 Cart Sync 구성까지 READY에 도달했으며, 자동 Play 및 Stage
  저장은 수행되지 않았다.
- 이전 직접 Apply/Bake 결과의 triangle 수는 241개였으므로 이번 151개 결과를
  동일한 Bake 결과라고 단정하지 않는다. 다만 사용자가 Play 후 아래 동작 기준을
  모두 확인했으므로 현재 고정 왕복 baseline에 대한 Live 검증은 통과했다.
  - Worker가 목적지에 도착한 후 출발점으로 복귀함
  - Cart와 두 Pallet이 Worker와 동시에 이동함
  - Cart가 선반이나 장애물을 관통하지 않음
  - Worker와 Cart가 NavMesh 영역을 벗어나지 않음
  - Stop 시 Cart runtime transform override가 정상적으로 해제됨

## 다음 권장 단계

연구 목적상 다음 단계는 단순 운반 장면에 VLM 판단이 필요한 warehouse event를
추가하는 것이다. 우선 하나의 직선 통로에 다음 세 상태를 재현한다.

1. `통과 가능`: Worker와 Cart가 통로를 지나가지만 LIMO의 예상 도착 전에 빠져나감
2. `일시 차단`: Worker가 하역 위치에서 일정 시간 정지하여 LIMO가 기다려야 함
3. `지속 차단`: Cart/Pallet이 통로를 계속 막아 LIMO가 우회해야 함

첫 구현은 2번 `일시 차단` 상태를 권장한다. 동일한 사람·카트 검출 결과라도
Worker의 이동 상태와 작업 맥락에 따라 `기다림`과 `우회`가 달라져야 하므로,
단순 object detection보다 VLM의 scene understanding 필요성을 설명하기 쉽다.
구현 시에는 People command에 `GoTo → Idle(하역 대기) → GoTo`를 추가하고,
카메라 관측 구간과 LIMO 정지 위치를 먼저 고정한다. 실제 손동작이나 새 USD는
첫 실험 범위에서 제외한다.
