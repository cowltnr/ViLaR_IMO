> Last updated: 2026-09-03 18:26 KST

# 직관적인 SLAM·I2ICF 발표자료 재구성 설계

## 목표

기존 발표자료를 총 7장으로 재구성한다. SLAM 설명은 기존의 세 장을 유지하고, I2ICF는 구체적인 이동체 간 정보 공유 사례 한 장으로 축소하며, 마지막에 일주일 안에 수행 가능한 Next Step을 추가한다.

## 슬라이드 구성

1. 연구 고도화 방향
2. 오늘 회의에서 확인할 내용
3. Predefined Route 방식의 한계
4. SLAM Map에서 Path가 생성되는 구조
5. 장애물 발견 시 정지와 Replanning
6. LIMO A의 관측을 Robot B가 활용하는 I2ICF 사례
7. 다음 주 Isaac Sim 기반 구현 계획

## 표현 원칙

- 한 슬라이드에는 하나의 질문 또는 핵심 메시지만 둔다.
- I2ICF의 추상적인 구성요소 이름보다 `발견 → 공유 → 각자 판단` 흐름을 우선한다.
- I2ICF 범위는 환경정보 공유이며 intent 해석과 policy control은 제외한다.
- SLAM은 Map과 Pose, Planner는 Path, Controller는 Path 추종을 담당한다고 구분한다.
- 다음 주 계획은 Isaac Sim에서 SLAM Occupancy Map 저장, Localization 확인, 단일 Path 생성, 장애물 하나를 이용한 Replanning 확인으로 제한한다.
- 복수 Candidate, VLM Selection, I2ICF 통신 구현은 다음 주 범위에서 제외한다.
- 실제 ROS2, Isaac Sim, Flask, Ollama 또는 실제 LIMO를 자동 실행하지 않는다.

## 산출물

- `SDV_Robocar_SLAM_I2ICF_직관적_7장.pptx`
- 편집 가능한 16:9 PowerPoint 형식
