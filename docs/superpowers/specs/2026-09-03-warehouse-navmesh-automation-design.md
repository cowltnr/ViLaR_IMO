> Last updated: 2026-09-03 16:49 KST

# Warehouse NavMesh Preview–Apply Automation Design

## 목적

Isaac Sim 4.5.0에서 열린 `warehouse_cart_worker.usd` Stage를 대상으로 다음
작업을 자동화한다.

- Warehouse 외부 바닥과 선반 상판에 생성된 불필요한 NavMesh를 줄인다.
- 벽, 선반, 기둥과 정적 장애물 주변에 통행 여백을 만든다.
- Worker–Cart의 실제 크기를 반영한 `Agent Radius`를 제안한다.
- Worker, Cart, Pallet 등 Dynamic Actor는 Bake 입력에서 제외한다.
- 잘못된 범위를 바로 적용하지 않도록 Preview와 Apply를 분리한다.

## 범위와 전제

- 대상 Stage는 이미 Isaac Sim GUI에 로드되어 있고 Remote Warehouse Asset의
  composition이 완료된 상태다.
- 기본 경로는 `/World/Environment/Warehouse`, `/World/NavMeshVolume`,
  `/World/Characters`, `/World/DynamicActors`다.
- 기존 NavMeshVolume과 Worker–Cart 동기화 구조를 보존한다.
- 외부 USD 파일을 새로 만들거나 작업 Stage를 자동 저장하지 않는다.
- Timeline을 자동 시작하지 않으며 실행 전 `Stop` 상태를 요구한다.
- 이 도구는 NavMesh 생성만 담당한다. NPC command와 LIMO 경로 계획은 바꾸지 않는다.

## 선택한 방식

한 번에 추정하고 Bake하지 않고 다음 두 단계로 실행한다.

### 1단계: Preview

Preview는 read-only로 동작한다.

1. 필요한 Prim과 현재 Stage 단위, up axis, Timeline 상태를 검증한다.
2. Warehouse를 순회하며 이름에 `floor` 또는 `ground`가 포함된 floor 후보와
   `wall`, `rack`, `shelf`, `obstacle`, `barrier`가 포함된 정적 구조 후보의
   world-aligned bounding box를 수집한다.
3. 현재 NavMeshVolume transform과 Warehouse/후보 geometry 범위를 출력한다.
4. `CartAssembly`의 local-aligned horizontal bounds를 계산한다.
5. 두 수평 길이 중 작은 값을 카트 폭으로 정의하고 다음 식으로 Agent Radius를
   제안한다.

   ```text
   proposed_radius_cm = cart_width × meters_per_unit × 100 ÷ 2 + 10
   ```

6. 제안 Radius가 20–80cm 범위를 벗어나거나 Cart bounds가 비어 있으면 자동
   제안을 거부한다.
7. Characters와 DynamicActors 아래의 NavMesh 제외 대상과, 실수로 제외된
   Warehouse 정적 geometry를 보고한다.
8. interior bounds를 한 가지로 확정할 수 있을 때만 Apply용 후보를 출력한다.

Preview는 USD attribute, API schema, NavMesh setting 또는 Bake cache를 변경하지
않는다.

### 내부 범위 판정

이름이 일치하는 floor 후보 중 다음 조건을 모두 만족하는 단일 후보만 자동
선택한다.

- 유효하고 비어 있지 않은 bounds를 가짐
- Worker 시작점 XY를 포함함
- floor top Z가 Worker 발 위치와 0.5m 이내임
- 후보 XY bounds가 현재 NavMeshVolume XY bounds보다 작음

0개 또는 2개 이상이면 결과를 `ambiguous`로 표시하고 Apply를 금지한다. 이 경우
Preview JSON과 Top View를 바탕으로 확정한 `interior_bounds`를 설정에 기록한 뒤
다시 실행한다. 이름 추정만으로 필요한 통로를 제거하지 않는 것이 우선이다.

NavMeshVolume은 floor bounds보다 XY 방향으로 커지지 않으며, floor 가장자리에서
안쪽으로 작은 inset을 적용할 수 있다. Z 범위는 현재 검증된 Warehouse 공식
NavMeshVolume 값을 기본으로 유지하여 선반 상판을 포함하지 않도록 한다.

## Apply 단계

Apply는 Preview 결과가 유효하거나 명시적인 `interior_bounds`가 제공된 경우에만
동작한다.

1. 현재 NavMeshVolume transform, NavMesh settings, 대상 Prim의
   `NavMeshExcludeAPI` 상태를 memory snapshot으로 보관한다.
2. NavMeshVolume X/Y를 확정된 Warehouse 내부 범위로 설정하고 기존 Z 범위는
   유지한다.
3. `/World/Characters`와 `/World/DynamicActors`에 `NavMeshExcludeAPI`를 적용한다.
4. Warehouse subtree에 잘못 적용된 `NavMeshExcludeAPI`는 자동 제거하지 않는다.
   해당 경로를 오류로 보고하고 Apply를 중단한다. Reference 내부의 의도된
   authoring을 임의로 바꾸지 않기 위해서다.
5. `Agent Height = 180cm`, 계산된 `Agent Radius`, 기존 Step Height와 Floor
   Slope를 사용한다.
6. `Auto-Bake`는 끄고 수동 Bake task를 한 번 시작한다.
7. 완료 event를 기다린 뒤 baked triangle 수와 Worker 시작점의
   `query_closest_point()` 결과를 검증한다.
8. 성공 결과와 원래 설정을 JSON 형태로 출력한다.

Apply는 Stage를 저장하거나 Timeline을 재생하지 않는다. 사용자는 결과를 확인한
뒤에만 저장 여부를 결정한다.

## 복구 방식

Apply 중 오류가 발생하면 memory snapshot의 NavMeshVolume transform, settings,
API 적용 상태로 복구를 시도한다. Bake 이전 상태를 완전히 재현할 수 없는 runtime
cache 문제를 고려하여 오류를 숨기지 않고 재Bake 필요 여부를 출력한다.

정상 Apply 후에도 Script Editor에서 호출할 `restore()` handle을 유지한다.
사용자가 결과를 승인하기 전에는 `Ctrl+S`를 누르지 않는다. 기존 USD 파일을
자동으로 덮어쓰거나 backup 파일을 삭제하지 않는다.

## 파일 구조

- `scripts/warehouse_navmesh_automation_config.py`: 순수 bounds, 단위 변환,
  candidate selection, radius 계산
- `scripts/configure_warehouse_navmesh.py`: Isaac Sim Preview/Apply adapter와 Bake
  lifecycle
- `tests/unit/test_warehouse_navmesh_automation_config.py`: Isaac Sim 없이 계산 및
  안전 거부 조건 검증
- `docs/exec-plans/active/2026-09-03-warehouse-navmesh-automation.md`: 진행 상태와
  live 검증 기록
- `docs/experiments/warehouse-cart-worker-context.md`: 실행 방법과 최종 결과

## 오류 처리

다음 조건에서는 Apply나 Bake를 시작하지 않는다.

- Timeline이 Play 또는 Pause 상태
- 필수 Prim이 없음
- Stage 단위 또는 up axis가 예상과 다름
- Warehouse bounds 또는 Cart bounds가 비어 있음
- interior bounds가 ambiguous함
- 제안 Agent Radius가 허용 범위를 벗어남
- Warehouse 정적 geometry에 `NavMeshExcludeAPI`가 존재함
- 이미 다른 NavMesh Bake가 진행 중임

오류 메시지에는 실패 조건, 관련 Prim path, 사용자가 확인할 항목을 포함한다.

## 검증 계획

### Offline

- 카트 bounds에서 폭과 Radius를 정확히 계산한다.
- Stage 단위를 cm로 올바르게 변환한다.
- Radius 20–80cm 경계를 검증한다.
- Worker를 포함하는 단일 floor 후보만 선택한다.
- floor 후보가 없거나 여러 개면 ambiguous 결과를 반환한다.
- NavMeshVolume Z 범위를 보존하면서 X/Y bounds만 교체한다.
- invalid/empty/inverted bounds를 거부한다.
- `bash scripts/check.sh`, `bash scripts/test_offline.sh`, `git diff --check`를 통과한다.

### Isaac Sim live

- Preview 실행 전후 USD dirty state와 NavMesh settings가 변하지 않는다.
- Apply 후 Warehouse 벽 바깥 Surface가 제거된다.
- 선반 상판에 Walkable Surface가 생성되지 않는다.
- 벽, 선반과 정적 장애물 주변에 계산된 Radius만큼 여백이 생긴다.
- Warehouse 주요 통로가 연결되어 있다.
- Worker 시작점과 선택한 목적지 사이 shortest path가 존재한다.
- Worker–Cart가 대표 경로에서 구조물을 관통하지 않는다.

## 알려진 한계

- Asset의 floor Prim 이름과 hierarchy가 의미를 드러내지 않으면 자동 내부 경계
  추정은 중단되며 Preview 결과를 이용한 한 번의 설정 보정이 필요하다.
- Axis-aligned bounds는 비정형 Warehouse 경계를 정확하게 표현하지 못한다. 이
  경우 여러 NavMeshVolume으로 나누는 후속 확장이 필요하다.
- Worker 중심의 원형 Agent Radius는 앞쪽으로 치우친 Cart footprint를 완전히
  모델링하지 않는다. 대표 경로의 육안 collision 확인이 필요하다.
- NavMesh Bake 결과의 최종 적절성은 사용자가 Surface/Outline을 보고 확인해야 한다.
