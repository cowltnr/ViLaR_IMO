> Last updated: 2026-09-02 17:15 KST

# Warehouse Cart Worker USD 수정 실행 계획

## 목표

`warehouse_cart_worker.usd`의 누적 Reference와 저장된 Physics 상태를 정리하고,
Worker Pose에 `CartAssembly`를 동기화하기 쉬운 Local Transform 구조로
정규화한다. Isaac Sim이나 ROS2는 실행하지 않고 bundled OpenUSD를 사용한
정적 검사만 수행한다.

## 기준 상태와 고정 조건

- 수정 대상: `/home/cowltnr/LimoIsaacSIM/USD/cart_simulation_env/warehouse_cart_worker.usd`
- 수정 전 SHA-256: `2a4d8ea3c50686c5ea933b3dd189ef542a8ae4779edb423787abc24b3c324ec7`
- Warehouse와 Worker의 Reference 및 기존 World Transform은 변경하지 않는다.
- Pushcart는 로컬 `SM_PushcartA_02.usd` 하나만 참조한다.
- Pallet 두 개의 기존 World 위치와 Orientation을 유지한다.
- Pallet은 시각적 운반용 Kinematic Body로 고정한다.

## 검증 기준

- [x] 목표 Stage 계층이 모두 존재한다.
- [x] Pushcart Reference가 A02 하나뿐이다.
- [x] `CartAssembly` 원점과 Pushcart Local 원점이 정규화되어 있다.
- [x] Pallet 두 개의 Local 위치가 정규화 후 예상값과 일치한다.
- [x] Pallet 두 개의 `physics:kinematicEnabled`가 `true`이다.
- [x] Pallet 두 개의 선속도와 각속도가 모두 0이다.
- [x] 수정 전 Backup이 대상 USD와 같은 디렉터리에 존재한다.
- [x] `bash scripts/check.sh`와 관련 오프라인 검사가 통과한다.

## 작업 순서

1. 수정 전 검증 실패를 재현한다.
2. 원본 USD를 Timestamp가 포함된 이름으로 Backup한다.
3. `/tmp` 복사본에서 Reference, Transform, Physics 속성을 수정한다.
4. 복사본이 검증을 통과한 뒤 대상 파일을 교체한다.
5. 대상 파일을 새로 열어 동일 검증을 반복한다.
6. Context 문서에 결과, Backup 위치, 새 SHA-256과 한계를 기록한다.
7. 저장소 검사 후 이 계획을 `completed/`로 이동한다.
