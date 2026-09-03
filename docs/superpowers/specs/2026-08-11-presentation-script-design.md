> Last updated: 2026-09-03 18:26 KST

# SLAM·I2ICF 발표 대본 설계

## 목적

`SDV_Robocar_SLAM_I2ICF_연구방향_8장_최종.pptx`의 8개 슬라이드를 10분 안에 설명할 수 있는 한국어 실전 발표 대본을 작성한다.

## 구성

- 슬라이드별 구간 시간과 누적 시간을 표시한다.
- 각 장에는 실제로 읽을 수 있는 발표 문장과 다음 장으로 이어지는 전환 문장을 넣는다.
- SLAM 부분은 약 5분, I2ICF 부분은 약 5분으로 배분한다.
- Route, Path, Planner, Costmap, Candidate, Baseline, Schema, Metrics 등 슬라이드에서 사용하는 기술 용어는 영어 표기를 유지한다.
- 현재 구현, 확인된 한계, 제안 구조를 분명히 구분한다.
- SLAM이 Path를 직접 생성하는 것으로 설명하지 않는다. SLAM은 Map과 Pose를 제공하고 Planner가 Path를 생성한다고 설명한다.
- I2ICF는 다중·이기종 이동체의 환경정보 공유만 다루며 intent 해석과 policy control은 범위에서 제외한다.
- VLM 실패나 timeout 상황에서는 정지를 유지한다는 안전 원칙을 포함한다.

## 산출물

- 저장 위치: 저장소 현재 위치
- 파일명: `SDV_Robocar_SLAM_I2ICF_발표대본.txt`
- 인코딩: UTF-8
- 총 발표 시간: 약 10분
