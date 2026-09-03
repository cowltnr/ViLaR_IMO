> Last updated: 2026-09-03 15:52 KST

# Warehouse Worker–Cart Pose Sync Execution Plan

## Goal

Worker의 검증된 왕복 이동을 유지하면서 `CartAssembly`와 하위 두 Pallet을
현재 상대 배치 그대로 동기화한다.

## Baseline

- `Worker_01`은 People `GoTo` command로 약 6 m 구간을 정상 왕복한다.
- `CartAssembly`와 Pallet은 baseline에서 정지한다.
- Worker의 runtime 이동은 `/World/Characters/Worker_01/DHGen/SkelRoot`에
  연결된 Animation Graph character가 수행한다.

## Candidate

Animation Graph character pose 기반의 per-frame kinematic pose sync를 별도
Script Editor 도구로 추가했다. Play 후 첫 유효 frame에서 현재 Worker–Cart
상대 transform을 자동 보정하고 Cart transform은 Session Layer에만 기록한다.

## Fixed conditions

- USD: `/home/cowltnr/LimoIsaacSIM/USD/cart_simulation_env/warehouse_cart_worker.usd`
- Worker command file과 NavMesh는 변경하지 않았다.
- Worker, Cart, Pushcart, Pallet 초기 배치는 변경하지 않았다.
- 기존 왕복 경로와 People animation을 그대로 사용했다.
- Physics contact와 push animation은 추가하지 않았다.

## Acceptance result

- [x] Offline pose composition/relative-transform test 통과
- [x] 잘못된 pose/quaternion 입력 거부
- [x] Play 중 Worker–Cart 상대 위치 유지 확인
- [x] 두 Pallet의 CartAssembly 동반 이동 확인
- [x] 방향 전환 후 Worker 앞 초기 상대 배치 유지 확인
- [x] Stop 시 Cart 초기 위치 복원 확인
- [x] `bash scripts/check.sh`: 34개 test 통과
- [x] `bash scripts/test_offline.sh`: 34개 test 통과
- [x] `git diff --check`와 새 파일 `py_compile` 통과

## Validation evidence

- 두 번의 의도된 RED를 확인했다: 새 pose math 모듈 부재, 이후
  `PoseSyncController` 부재.
- Focused suite `tests.unit.test_warehouse_worker_cart_pose_sync`의 9개 test가
  통과했다.
- Sandbox 내부 LibreOffice test는 dconf 쓰기 제한으로 실패했으며, 동일 standard
  checks를 정상 권한 환경에서 재실행하여 전체 통과를 확인했다.
- 사용자가 Isaac Sim Script Editor에서 sync script를 실행하고 live acceptance
  항목 확인 완료를 보고했다.

## Safety and limitations

- 스크립트는 ROS2 topic을 publish하거나 USD를 자동 저장하지 않는다.
- Cart transform은 Session Layer에만 기록하고 Stop에서 제거한다.
- 이 결과는 visual/kinematic sync 검증이며 실제 손–손잡이 contact force나
  전용 push animation을 검증하지 않는다.

## Status

완료. 다음 연구 단계는 Worker–Cart 운반을 LIMO/VLM 관측 시나리오의 동적
warehouse event로 연결하는 것이다.
