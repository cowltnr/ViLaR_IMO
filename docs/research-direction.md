> Last updated: 2026-08-15 21:16 KST

# SDV Robocar 연구 방향

## 문서 상태

- 최종 갱신일: 2026-08-15
- 최신 근거: [`meetings/2026-08-12.md`](meetings/2026-08-12.md)
- 다음 검토 예정: 2026-08-19
- 원칙: 현재 코드의 동작과 제안 연구를 분리하고, Baseline을 보존한 상태에서 Candidate를 비교한다.

## 현재 연구 목표

1. VLM 사용이 실제로 필요한 주행 시나리오를 선정한다.
2. 우선 시나리오를 Isaac Sim에 구축하고 SLAM 기반 2D Occupancy Grid Map을 생성한다.
3. 사전 정의된 Route 선택을 Baseline으로 유지하면서, SLAM Map에서 실시간 Path Candidate를 생성·평가하는 Candidate 방식을 설계한다.
4. 여러 차량·로봇이 동적 장애물과 주행 환경 정보를 양방향으로 공유하고 각 이동체가 Local Planning에 반영하는 구조를 연구한다.
5. 해외 유사 연구와 비교해 VLM 판단, 실시간 경로 생성, 이종 이동체 정보 공유의 결합에서 차별화 가능성을 검증한다.

## 확인된 시스템 Baseline

다음은 production code 정적 점검으로 확인한 현재 동작이다. Live 실행 결과를 의미하지 않는다.

- `waypoint_tools/waypoint_routes/routes.py`에 `wp1`~`wp5` Route가 고정 좌표로 정의되어 있다.
- `vlm_server.py`는 전달받은 후보 중 하나의 Route ID를 선택하며 새 경로를 생성하지 않는다.
- `waypoint_tools/point_follower.py`와 `waypoint_tools/pure_pursuit_follower.py`가 선택된 Route를 추종한다.
- Edge는 `k8s_server.py`의 `POST /inference`로 JSON과 이미지를 전송하고 Server는 이를 로컬 파일로 저장한다.
- 다른 이동체가 저장 정보를 조회하거나 Server가 Dynamic Event를 재배포하는 Interface는 구현되어 있지 않다.
- VLA, Diffusion Model, Worker/Manager Agent, MCP, A2A는 현재 production pipeline의 구현 요소가 아니다.
- `edge_threads/infer_thread.py`에는 VLM 실패 이후에도 `/selected_route`를 중복 발행하는 경로가 있어, VLM 기반 실험 전 안전 동작을 별도 수정·검증해야 한다.

## 연구 축

### SLAM·Path Planning

- **Baseline:** `wp1`~`wp5` 중 Route를 선택하고 Point Follower 또는 Pure Pursuit로 추종한다.
- **Candidate 목표:** SLAM이 제공하는 Map과 Pose, 정적·동적 Cost를 이용해 현재 위치에서 Goal까지 주행 가능한 Path를 실시간으로 생성한다.
- **단계적 접근:** 먼저 단일 Planner가 생성한 안전 Path를 재현하고, 이후 서로 다른 통로를 사용하는 복수 Candidate 생성과 VLM 선택을 추가한다.
- **안전 경계:** Planner가 충돌 검사와 운동학 제약을 통과한 후보만 VLM에 제공한다. VLM은 Path를 직접 생성하지 않고 안전 후보 중 선택한다.
- **Controller 관계:** Path Planner는 경로를 만들고 Point Follower/Pure Pursuit는 경로를 따라간다. Candidate 검증 단계에서는 기존 Controller를 유지한다.

### VLM 활용 시나리오

- VLM은 단순 최단거리 계산이 아니라 표지, 작업 상황, 사람 행동, 통로의 의미처럼 Costmap만으로 표현하기 어려운 맥락 판단에 사용한다.
- 우선 후보는 스마트 팩토리에서 작업 중인 통로, 일시 폐쇄 표지, 사람 밀집 구역 등 의미 기반 우회가 필요한 상황이다.
- 각 시나리오는 VLM 입력, 허용 출력, 결정 시점, 안전 후보 집합, Timeout/Invalid Output 시 정지를 명시한다.
- VLM 없이 해결 가능한 장애물 회피는 전통 Planner의 Baseline으로 처리해 VLM 사용의 필요성을 비교한다.

### 다중 이동체 환경정보 공유

- I2ICF는 Intent가 아니라 여러 차량·로봇의 환경정보 공유 관점으로 한정한다.
- 각 이동체는 Static Layer를 로컬에 유지하고, 새로 관측한 Dynamic Obstacle/Object Event를 Edge Server로 전송하는 구조를 우선 검토한다.
- Server는 수신 Event를 검증·통합하고 관련 이동체에 Pub/Sub 또는 Push로 배포한다.
- 수신한 이동체는 자신의 크기, 회전반경, 센서 상태와 Local Costmap을 기준으로 정보를 적용하고 Path를 다시 생성한다.
- 공유 후보 필드는 `robot_id`, `event_id`, `frame_id`, 위치/영역, 객체 종류, Timestamp, TTL, Confidence, Source다. 이는 제안 Schema이며 아직 확정되지 않았다.

### Agent Architecture

- Manager Agent가 Task 또는 Intent를 분해·할당하고, 로봇별 Worker Agent가 로컬 상황과 Capability에 따라 수행하는 구조를 별도 후보로 검토한다.
- MCP는 Tool/Context 연결 후보, A2A는 Agent 간 Task·상태 교환 후보로 조사한다.
- 이 연구 축을 I2ICF 정보 공유와 혼합하지 않는다. I2ICF는 환경정보의 정확성·지연·통신량을, Agent Architecture는 Task 조정 성공률·복구·안전성을 평가한다.
- Manager 장애나 통신 단절 시 각 로봇의 Local Safety와 정지 우선 원칙을 유지해야 한다.

### 해외 연구 및 차별화

- 미국·유럽을 포함해 Multi-Robot SLAM, Collaborative Perception, Fleet Management, Semantic/VLM Navigation, Agentic Robotics 연구를 조사한다.
- 공통 비교 항목은 연구 문제, 이동체 수와 종류, 공유 데이터, 통신 방식, Planning 연계, AI Model 역할, 실험 환경, 안전 처리, 지표와 한계다.
- 차별점은 Survey 이전에 확정하지 않는다. 현재 검증할 가설은 `이종 이동체의 동적 환경정보 공유`와 `안전 후보에 한정된 VLM 선택`을 결합하면 사전 Route만 사용하는 구조보다 상황 대응 범위를 넓힐 수 있다는 것이다.

## 실행 순서

### Now: 2026-08-12 ~ 2026-08-19

1. **VLM 시나리오 후보표 작성**
   - 스마트 팩토리 중심 후보를 나열하고 VLM이 필요한 이유를 적는다.
   - 1주 내 Isaac Sim에 구성 가능한 시나리오 1개를 선정한다.
2. **Isaac Sim 반영 명세 작성**
   - Map, Robot, Camera, 2D LiDAR, Odometry, Dynamic Object, 시작·Goal 조건을 정의한다.
   - 이번 주에는 자동 실행하지 않고 구축에 필요한 Asset과 Topic을 확인한다.
3. **Robot Control Architecture 초안 작성**
   - 현재 구현과 제안 기능을 다른 색 또는 선으로 구분한다.
   - Sequential/Parallel 흐름, ROS2/HTTP/MCP/A2A 경계, 안전 정지 경로를 표시한다.
4. **해외 연구 비교표 초안 작성**
   - 공통 비교 항목을 먼저 고정하고 각 항목에 원문 출처를 연결한다.
5. **2026-08-19 결정 질문 준비**
   - 우선 시나리오, 공유 Message Schema, Pub/Sub 대 Push, Agent Architecture 범위, 첫 Planner Candidate를 결정할 수 있게 정리한다.

### Next

1. 승인된 시나리오를 Isaac Sim에 구축한다.
2. Offline 확인 후 Isaac Sim에서 SLAM 2D Occupancy Grid Map을 생성·저장한다.
3. 고정 Route Baseline을 재현하고 단일 SLAM Planner Candidate를 별도 구현한다.
4. Dynamic Event Schema와 Static/Dynamic Layer 갱신 규칙을 정의한다.
5. 기록 데이터 또는 Offline Harness로 Event 지연, 중복, 만료, 좌표 변환을 검증한다.
6. Pub/Sub와 Push 중 최소 구현 후보를 동일 조건에서 비교한다.

### Later

1. 두 대 이상의 동종 이동체에서 양방향 Dynamic Event 공유를 검증한다.
2. 이종 차량·로봇으로 확장하고 Capability별 적용 규칙을 검증한다.
3. 복수 Path Candidate 생성과 VLM 선택을 통합한다.
4. Agent Architecture를 별도 Candidate로 구현해 중앙 조정과 Local Autonomy의 역할을 비교한다.
5. 반복 실험 후 Baseline 대비 효과가 확인된 요소만 통합 Architecture에 반영한다.

## 평가 기준

### 다음 회의 전 문서 산출물

- VLM 시나리오 후보가 환경, 사건, VLM 필요성, 입력, 출력, 실패 처리를 포함한다.
- 우선 시나리오 1개가 Isaac Sim 구성 요소와 시작·Goal 조건을 포함한다.
- Architecture가 현재 구현과 제안 기능, Sequential/Parallel 흐름, 통신 경계, 안전 정지를 구분한다.
- 해외 연구 비교표의 각 항목에 확인 가능한 출처가 연결된다.

### 이후 비교 실험

- 기존 Route 선택 Baseline과 Candidate는 동일 Map, 시작·Goal, 장애물, 속도 제한, 허용 오차, Sampling Rate를 사용한다.
- Path Planning은 성공률, 경로 길이, Planning Time, Collision/Stop, 최소 장애물 거리, Tracking Error, Travel Time을 기록한다.
- 정보 공유는 End-to-End Latency, 전송량, Event 누락·중복, 오래된 Event 적용률, Replanning 성공률을 기록한다.
- VLM은 Candidate 선택 정확도, Invalid Output, Timeout, 판단 지연, 안전 규칙 위반을 기록한다.
- 실험은 `offline test -> recorded-data replay -> Isaac Sim -> real LIMO` 순서로 진행하고 결과를 `artifacts/runs/`에 새 Run ID로 보존한다.

## 미해결 질문과 위험

- 어떤 스마트 팩토리 사건이 VLM 사용 필요성을 가장 명확히 보여주는가?
- 첫 Planner Candidate는 무엇이며, 서로 다른 경로군을 어떤 기준으로 생성할 것인가?
- Static Layer의 동일성을 어떻게 보장하고 Map Version을 어떻게 관리할 것인가?
- 서로 다른 이동체의 좌표 Frame과 Sensor Confidence를 어떻게 통합할 것인가?
- Pub/Sub와 Push 중 지연, 대역폭, 장애 복구 조건에 맞는 방식은 무엇인가?
- Dynamic Event의 TTL, 삭제, 갱신, 충돌 해결 규칙은 무엇인가?
- Manager Agent, MCP, A2A는 이번 연구의 필수 구현인가, 장기 비교 후보인가?
- VLA와 Diffusion Model을 Pipeline에 포함할 명확한 연구 질문과 Baseline이 있는가?
- 현재 VLM 실패 처리 결함과 `/sim/cmd_vel` 단일 Publisher 운영 규칙을 어떻게 검증할 것인가?

## 결정 이력

| 날짜 | 출처 | 상태 | 결정 또는 변경 |
|---|---|---|---|
| 2026-08-12 | [`meetings/2026-08-12.md`](meetings/2026-08-12.md) 대화 기반 | 확정 | 단일 LIMO의 정보 전송에서 다중 차량·로봇 양방향 환경정보 공유로 연구 범위를 확장한다. |
| 2026-08-12 | 같은 문서 | 제안 | Static Layer를 유지하고 Dynamic Obstacle/Object Event만 선택적으로 갱신한다. |
| 2026-08-12 | 같은 문서 | 확정 | 전체 Robot Motion Control Pipeline과 Architecture 초안을 작성한다. |
| 2026-08-12 | 같은 문서 | 제안 | Worker/Manager Agent와 MCP/A2A를 I2ICF와 분리된 Agent Architecture 후보로 검토한다. |
| 2026-08-12 | 같은 문서 | 확정 | 해외 유사 연구 Survey와 차별점 검토를 진행한다. |
