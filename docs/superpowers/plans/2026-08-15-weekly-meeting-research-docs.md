> Last updated: 2026-08-15 21:16 KST

# Weekly Meeting Research Docs Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 2026-08-12 회의 내용을 출처별로 기록하고 현재 연구 방향 문서를 갱신한다.

**Architecture:** 날짜별 회의 문서는 원본 회의록과 대화 내용을 분리해 보존한다. 누적 연구 방향 문서는 검증된 코드 Baseline과 제안된 연구 항목을 구분하며, 회의 목록과 문서 색인에서 각 문서로 연결한다.

**Tech Stack:** Markdown, repository production-source inspection, `scripts/check.sh`

## Global Constraints

- 2026-08-12 원본 회의록 파일이 없으므로 사용자 입력을 `대화 기반`으로만 기록한다.
- 현재 코드는 동작의 기준으로 사용하고, 미구현 기능은 `제안` 또는 `보류`로 표시한다.
- I2ICF의 범위는 다중 이동체 환경정보 공유이며, Intent와 Manager Agent 구조는 별도 연구 축으로 구분한다.
- Live ROS2, Isaac Sim, Ollama, Flask, 실제 LIMO를 실행하지 않는다.
- 기존 회의 자료와 실험 산출물을 삭제하거나 덮어쓰지 않는다.

---

### Task 1: 2026-08-12 회의 기록 작성

**Files:**
- Create: `docs/meetings/2026-08-12.md`

**Interfaces:**
- Consumes: 사용자가 전달한 2026-08-12 회의 내용과 production code 정적 점검 결과
- Produces: 출처가 구분된 회의 기록 및 다음 회의 전 실행 항목

- [x] **Step 1: 입력 출처와 상태를 기록한다**

  저장소에서 2026-08-12 원본 회의록을 찾지 못했음을 명시하고, 사용자 입력을 대화 기반 자료로 연결한다.

- [x] **Step 2: 논의와 Action Items를 상태별로 정리한다**

  다중 이동체 양방향 공유는 연구 방향, 정적/동적 Layer 분리는 구조 제안, Agent/MCP/A2A는 검토 제안으로 구분한다.

- [x] **Step 3: 기존 대화와의 범위 차이를 기록한다**

  I2ICF 자체는 Intent를 다루지 않고, Manager Agent의 Intent 처리는 별도 Agent Architecture 후보로 둔다.

- [x] **Step 4: 다음 회의 전 산출물과 위험을 기록한다**

  VLM 시나리오, Isaac Sim 반영안, 전체 Architecture 초안, 해외 연구 비교표를 2026-08-19 전 산출물로 정의한다.

### Task 2: 누적 연구 방향 갱신

**Files:**
- Create: `docs/research-direction.md`

**Interfaces:**
- Consumes: `docs/meetings/2026-08-12.md`, `ARCHITECTURE.md`, 관련 production code
- Produces: Now/Next/Later 순서와 결정 이력을 포함한 연구 방향 문서

- [x] **Step 1: 검증된 Baseline을 기록한다**

  `wp1`~`wp5` 사전 Route 선택, Point Follower/Pure Pursuit, 단방향 로그 전송 및 로컬 저장을 현재 동작으로 기록한다.

- [x] **Step 2: 연구 축을 분리한다**

  SLAM·Path Planning, VLM 시나리오, 다중 이동체 환경정보 공유, Agent Architecture, 해외 연구 및 차별화로 구분한다.

- [x] **Step 3: 실행 순서와 평가 기준을 기록한다**

  1주 내 문서·시나리오 산출물을 Now로, Isaac Sim/SLAM 및 공유 프로토콜 실험을 Next로, 다중 이동체 통합을 Later로 둔다.

### Task 3: 목록과 문서 색인 연결

**Files:**
- Create: `docs/meetings/index.md`
- Modify: `docs/index.md`

**Interfaces:**
- Consumes: Task 1과 Task 2의 문서 경로
- Produces: 저장소 문서 색인에서 회의 기록과 연구 방향으로 이동 가능한 링크

- [x] **Step 1: 회의 목록을 만든다**

  2026-08-12 회의를 `확인 필요` 상태로 등록하고 원본 파일 부재를 표시한다.

- [x] **Step 2: 최상위 문서 색인에 링크를 추가한다**

  `docs/index.md`에 Research tracking 절을 추가한다.

### Task 4: 문서 검증

**Files:**
- Verify: `docs/meetings/2026-08-12.md`
- Verify: `docs/meetings/index.md`
- Verify: `docs/research-direction.md`
- Verify: `docs/index.md`

**Interfaces:**
- Consumes: 생성·수정된 Markdown 문서
- Produces: 링크, 출처 구분, 금지된 미검증 주장에 대한 검증 결과

- [x] **Step 1: 필수 절과 링크를 정적으로 확인한다**

  `rg`로 회의록 기반, 대화 기반, 종합 정리, Now/Next/Later 및 상대 링크를 확인한다.

- [x] **Step 2: 일반 검사를 실행한다**

  Run: `bash scripts/check.sh`

  Expected: 종료 코드 0. 문서 변경과 무관한 실패가 발생하면 정확한 오류와 미검증 범위를 기록한다.

- [x] **Step 3: 변경 범위를 검토한다**

  `git diff -- docs`와 `git status --short`로 의도한 문서만 변경되었는지 확인한다.
