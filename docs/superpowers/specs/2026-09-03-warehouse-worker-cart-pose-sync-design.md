> Last updated: 2026-09-03 15:28 KST

# Warehouse Worker–Cart Pose Sync Design

## 목적

Isaac Sim 4.5.0의 People `GoTo` 명령으로 이동하는
`/World/Characters/Worker_01/DHGen/SkelRoot`의 runtime pose를 추적하여,
`/World/DynamicActors/CartAssembly`가 현재 상대 배치를 유지한 채 함께
이동하도록 한다. `CartAssembly` 아래의 Pushcart와 두 Pallet은 기존 계층을
그대로 사용한다.

## 승인된 방식

Play 후 첫 유효 runtime frame에서 Worker와 CartAssembly의 world transform으로
상대 transform을 자동 보정한다. `ag.get_character()`는 runtime에서만 유효하기
때문이다. 이후 Timeline이 재생되는 동안 Animation Graph character의 pose를 매
update frame마다 읽고 아래 관계를 유지한다.

```text
T_worker_initial^-1 × T_cart_initial = T_relative
T_cart_runtime = T_worker_runtime × T_relative
```

이 방식은 좌표를 하드코딩하지 않으므로 Worker 또는 Cart의 초기 배치를
바꾸더라도 다시 실행하면 새 배치를 기준으로 동기화한다.

## 구성 요소

- 순수 Python transform 함수: quaternion 정규화·회전·합성과 상대 pose 계산
- Isaac Sim adapter: stage prim과 Animation Graph character를 검증하고 pose를 읽음
- update subscription: Timeline이 재생 중일 때 CartAssembly의 pose를 갱신
- timeline subscription: `STOP`에서 임시 pose override를 제거하고 초기 위치 복원
- 전역 handle: Script Editor에서 스크립트를 다시 실행할 때 기존 subscription을
  해제하여 중복 callback을 방지

## USD 기록 정책

동기화 transform은 root layer가 아니라 Session Layer에만 기록한다. 따라서
실행 중 Cart 위치를 원본 `warehouse_cart_worker.usd`에 저장하지 않는다.
Timeline `STOP` 시 CartAssembly prim의 session-layer transform property override만
제거한다. 다른 session-layer spec은 변경하지 않는다.

## 안전 및 범위

- 이 단계는 visual/kinematic sync이며 실제 손–손잡이 contact force를 계산하지 않는다.
- ROS2 topic을 publish하거나 LIMO를 제어하지 않는다.
- 기존 Worker command, NavMesh, Animation Graph, pallet relative transform을 변경하지 않는다.
- Timeline이 재생 중일 때 설정을 시작하지 않고 명확한 오류를 낸다.
- Worker, SkelRoot, CartAssembly 또는 character interface를 찾지 못하면 동기화를 시작하지 않는다.

## 검증

### Offline acceptance criteria

- identity 회전에서 상대 offset이 보존된다.
- Worker가 90도 회전하면 Cart offset도 같은 방향으로 회전한다.
- 초기 Worker/Cart pose에서 계산한 상대 transform을 새 Worker pose에 적용하면
  기대한 Cart pose가 산출된다.
- zero-length quaternion 및 잘못된 tuple 크기는 거부된다.
- 표준 offline checks가 통과한다.

### Isaac Sim acceptance criteria

- Script Editor 실행 시 prim 검증과 초기 보정 결과가 출력된다.
- Play 중 Worker와 CartAssembly 및 두 Pallet이 왕복 경로를 함께 이동한다.
- 방향 전환 시 카트가 Worker 기준 초기 상대 위치를 유지한다.
- Stop 후 CartAssembly가 저장된 초기 위치로 돌아온다.
- 이 live 검증은 사용자가 직접 Play/Stop하고 육안으로 확인한다.

## 알려진 한계

- Worker 팔 자세는 별도 push animation이 아니므로 손잡이를 실제로 잡지 않는다.
- Collision/contact에 의해 Cart가 밀리는 물리 실험을 대신하지 않는다.
- Session Layer 동작과 Animation Graph runtime API는 Isaac Sim 4.5.0에서 최종 확인해야 한다.
