> Last updated: 2026-09-03 18:18 KST

# Warehouse Runtime Bootstrap Execution Plan

## Goal

Isaac Sim 재시작 후 각각 실행해야 하는 Warehouse NavMesh, Worker Behavior,
Worker–Cart Pose Sync 설정을 하나의 안전한 Script Editor 진입점으로 통합한다.

## Baseline

- NavMesh Apply/Bake, Worker Behavior, Cart Pose Sync는 각각 독립 스크립트로
  실행할 수 있다.
- Worker는 고정된 약 6m 왕복 명령을 사용하며, Cart와 두 Pallet은 runtime pose
  sync로 Worker를 따라간다.
- Isaac Sim 재시작 시 People runtime setting과 Cart callback을 다시 구성해야 한다.
- 기존 개별 스크립트는 보존하며 계속 독립 실행할 수 있어야 한다.

## Candidate

- `PRECHECK -> NAVMESH -> WORKER_BEHAVIOR -> CART_SYNC -> READY` 순서로 실행한다.
- 정확한 Stage, 필수 prim, Timeline Stop 상태를 변경 전에 검증한다.
- 단계 실패 시 이번 실행에서 생성한 callback, Worker runtime setting/command
  file, NavMesh Apply를 역순으로 복구한다.
- 성공 후에도 Timeline을 시작하거나 Stage를 저장하지 않는다.
- 같은 runtime에서 READY 상태로 다시 실행하면 중복 callback이나 재Bake 없이
  기존 handle을 반환한다.

## Fixed conditions

- Stage: `/home/cowltnr/LimoIsaacSIM/USD/cart_simulation_env/warehouse_cart_worker.usd`
- Interior bounds: `X=-28.0~8.0`, `Y=-23.4~30.6`, `Z=-0.001~0.001`
- Worker: `/World/Characters/Worker_01`
- Worker SkelRoot: `/World/Characters/Worker_01/DHGen/SkelRoot`
- Cart: `/World/DynamicActors/CartAssembly`
- Worker 이동 방식: 현재 고정 왕복 baseline 유지
- 자동 Play, 자동 Stage 저장, ROS2 publish 없음

## Metrics and acceptance criteria

- 성공 단계 순서가 고정되고 READY 결과가 구성 요소 결과를 포함한다.
- Precheck 실패 시 어떤 구성 요소도 변경하지 않는다.
- NavMesh/Worker/Cart 단계 실패 시 이미 적용된 상태가 역순으로 복구된다.
- 동일 READY handle 재실행 시 NavMesh 재Bake 및 callback 중복 설치가 없다.
- 명시적 shutdown이 Cart callback과 Worker runtime 상태를 정리한다.
- 기존 개별 스크립트와 고정 왕복 baseline을 변경하지 않는다.
- `bash scripts/check.sh`와 `bash scripts/test_offline.sh`가 통과한다.

## Validation order

1. Orchestration offline test RED
2. 최소 구현 후 focused test GREEN
3. 오류 복구 및 중복 실행 test RED–GREEN
4. `bash scripts/check.sh`
5. `bash scripts/test_offline.sh`
6. 사용자 승인에 의한 Isaac Sim Script Editor live 실행

## Status

- [x] 안전 구조 승인
- [x] Orchestration test RED–GREEN (12개 focused test)
- [x] Live adapter 구현
- [x] Standard offline checks (67개 test, 0 failures)
- [x] 사용자 live 검증

## 구현 및 검증 기록

- `scripts/setup_warehouse_runtime.py`에 pure orchestration과 Isaac Sim live
  adapter를 분리했다. Isaac 전용 모듈은 live 함수 내부에서만 import한다.
- Worker 설정 전 People runtime setting과 command file을 snapshot하고, 실패 시
  구성 요소를 역순으로 정리한다. cleanup 하나가 실패해도 나머지 cleanup을 계속
  시도하며 최초 setup 오류를 유지한다.
- 기존 수동 Apply에서 생성된 유효한 NavMesh handle과 triangle이 있으면 이를
  재사용한다. 이번 실행이 소유하지 않은 NavMesh는 실패 rollback에서 변경하지
  않는다.
- Focused test 12개가 성공 순서, 실패 전 무변경, Worker/Cart 실패 rollback,
  중복 실행, shutdown, cleanup 오류 격리, setting/file 복원을 검증한다.
- `bash scripts/check.sh`와 별도 `bash scripts/test_offline.sh`가 각각 67개 test,
  0 failures로 통과했다.
- Live Isaac Sim 실행은 Codex가 자동으로 수행하지 않았으며, 사용자가 Script
  Editor에서 통합 스크립트를 실행하고 READY 출력을 확인했다.
- 사용자 첫 Live 실행에서 PRECHECK부터 READY까지 완료됐다. 기존 NavMesh를
  재사용한 결과는 `triangle_count=151`, Worker path는 21 points였다. 이전 직접
  Bake의 241 triangles와 차이는 있었지만 아래 동작 기준을 모두 통과했다.
- 사용자가 Worker의 목적지 도착 및 출발점 복귀, Cart와 두 Pallet의 동반 이동,
  선반·장애물 비관통, NavMesh 영역 비이탈, Stop 후 Cart runtime transform 해제를
  직접 확인했다.

## 완료 판정

Offline test와 사용자 Live 검증에서 정의된 acceptance criteria를 모두
충족했다. 통합 Runtime Bootstrap은 기존 고정 왕복 baseline을 유지한 상태로
완료하며, 자유 순찰 목적지 생성은 별도 candidate 연구로 남긴다.

## Safety

통합 스크립트는 Timeline을 시작하거나 Stage를 저장하지 않는다. 실패 시 이번
실행의 변경만 복구하며, 기존 미복구 NavMesh handle은 자동으로 덮어쓰거나
복구하지 않는다. ROS2 topic과 실제 LIMO에는 접근하지 않는다.
