> Last updated: 2026-09-03 17:53 KST

# Warehouse NavMesh Automation Execution Plan

## Goal

현재 Warehouse 외부 바닥과 선반/장애물 표면까지 확장된 NavMesh를 안전한
Preview–Apply 자동화로 내부 통로 중심의 NavMesh로 교체한다.

## Baseline

- `/World/NavMeshVolume`은 공식 Warehouse transform을 사용한다.
- 기존 Bake 결과는 Worker 단독 왕복에 사용 가능하지만 cyan Surface가
  Warehouse 외부 바닥과 불필요한 구조물 표면에도 표시된다.
- 기본 Agent Radius는 20cm이며 Cart footprint는 반영하지 않는다.
- Worker–Cart kinematic pose sync는 live 검증을 통과했다.

## Candidate

- Preview가 composed Stage geometry, Cart bounds, exclusions와 interior floor
  후보를 read-only로 검사한다.
- Apply는 검증된 단일 후보 또는 명시적 bounds만 사용한다.
- 카트 폭의 절반에 10cm를 더한 Radius를 사용한다.
- Dynamic root만 제외하고 static Warehouse geometry는 유지한다.
- Apply 실패 시 memory snapshot으로 복구하고 Stage는 자동 저장하지 않는다.

## Fixed conditions

- Stage: `/home/cowltnr/LimoIsaacSIM/USD/cart_simulation_env/warehouse_cart_worker.usd`
- Warehouse: `/World/Environment/Warehouse`
- Volume: `/World/NavMeshVolume`
- Dynamic roots: `/World/Characters`, `/World/DynamicActors`
- Agent Height: 180cm
- Agent Max Step Height와 Max Floor Slope: 현재 값 유지
- Timeline: Stop
- 기존 Worker command, Animation Graph, Behavior Script와 Cart sync는 변경하지 않음

## Metrics and acceptance criteria

- Preview 실행이 USD와 settings를 변경하지 않음
- 모호한 floor 후보에서 Apply 차단
- Agent Radius 계산 및 20–80cm 안전 범위 검증
- Apply 후 외부 바닥 및 선반 상판 Surface 제거
- 벽, 선반, 정적 장애물 주변 clearance 생성
- Warehouse 주요 통로 연결 유지
- Worker 시작점의 closest point 거리 1m 이하
- 대표 Worker–Cart 경로에서 구조물 관통 없음
- Standard offline checks 통과

## Validation order

1. Pure calculation RED–GREEN
2. Preview report RED–GREEN
3. Transaction/restore RED–GREEN
4. Standard offline checks
5. 사용자 Script Editor Preview
6. Preview report 검토
7. 사용자 승인 후 Apply/Bake
8. Surface/Outline과 대표 경로 live 확인

## Status

- [x] 2단계 Preview–Apply 설계 승인
- [x] 설계 spec 작성 및 self-review
- [x] Pure calculation RED–GREEN (10개 계산·거부 조건 test)
- [x] Preview implementation RED–GREEN (총 14개 focused test)
- [x] Apply/restore implementation RED–GREEN (총 21개 focused test)
- [x] Standard offline checks (55개 test, 0 failures)
- [x] Preview live 결과 검토
- [ ] Apply/Bake live 결과 검토

## 구현 및 검증 기록

- `scripts/warehouse_navmesh_automation_config.py`에 bounds, floor 선택,
  Agent Radius, Z 보존 Volume 변환과 rollback controller를 구현했다.
- `scripts/configure_warehouse_navmesh.py`에 read-only live Preview reader와
  guarded Apply/Bake/restore adapter를 구현했다.
- Isaac Sim 4.5.0의 로컬 `omni.anim.navigation.core-106.4.0` source에서
  `NavMeshSettings`, `start_navmesh_baking()`, 완료 event,
  `get_draw_triangles()`와 `query_closest_point()` 계약을 확인했다.
- Focused test 21개와 두 script의 `py_compile`, scoped `git diff --check`가
  통과했다.
- 최종 `bash scripts/check.sh`, `bash scripts/test_offline.sh`, 전체
  `git diff --check`가 통과했다. 각 전체 test 실행 결과는 55개, 0 failures다.
- Live Isaac Sim 명령은 실행하지 않았다. 다음 checkpoint는 사용자 Script
  Editor의 Apply/Bake와 Surface 검토다.

## Live Preview 판정

- 사용자 Preview에서 Timeline `stopped`, `1m/unit`, Z-up을 확인했다.
- Cart 기반 Agent Radius는 `56.785cm`로 허용 범위 안이다.
- 동일 bounds를 가진 floor hierarchy 때문에 자동 선택은 차단됐지만, 중복 제거
  결과 실제 ground는 `6m × 6m` 타일 54개의 `6열 × 9행` 직사각형이다.
- 검토된 ground 합집합 `X=-28.0~8.0`, `Y=-23.4~30.6`을 명시적 bounds로
  사용하는 것이 현재 candidate다.
- Apply 후에는 외부 Surface 제거, 주요 통로 연결, static obstacle clearance,
  dynamic root exclusion의 descendant 적용 여부를 반드시 육안 검증한다.

## Live Apply/Bake 판정

- 사용자 실행 결과 `status=verified`, `triangle_count=241`을 확인했다.
- 적용된 Agent Height는 `180cm`, Agent Radius는 `56.785014cm`다.
- Worker closest point 거리는 `0.042701m`로 1m 기준을 통과했다.
- 사용자가 cyan Surface가 원하는 범위에 적용됐음을 확인했다.
- `saved=false`이므로 Stage는 아직 Script에 의해 자동 저장되지 않았다.
- 대표 Worker–Cart 왕복에서 통로 연결 및 구조물 비관통을 확인한 뒤
  Apply/Bake live 항목을 완료 처리한다.

## Safety

스크립트는 Timeline을 시작하거나 Stage를 저장하지 않는다. Preview는 read-only이며,
Apply는 유효한 내부 범위에서만 실행된다. ROS2 topic과 LIMO 제어에는 접근하지 않는다.
