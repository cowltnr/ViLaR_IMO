> Last updated: 2026-09-03 18:37 KST

# ViLaR IMO GitHub Repository Maintenance Design

## 목적

공개 GitHub 저장소 `cowltnr/ViLaR_IMO`를 정리하고 이후 README 및 파일 구조를
지속적으로 갱신할 수 있는 절차를 정의한다. 모든 GitHub 작업은 임시 clone에서만
수행하며 원본 로컬 프로젝트와 Isaac Sim USD는 수정하지 않는다.

## 절대 조건

- 원본 프로젝트 `/home/cowltnr/PycharmProjects/SDV_Robocar`는 read-only로
  취급한다.
- 원본 USD `/home/cowltnr/LimoIsaacSIM/USD/cart_simulation_env`는 read-only로
  취급한다.
- 원본 프로젝트에서 `git add`, `git commit`, `git remote set-url`, `git push`,
  파일 이동·삭제·수정을 수행하지 않는다.
- GitHub 변경은 매 작업마다 `/tmp`에 새로 만든 `ViLaR_IMO` clone에서만
  수행한다. 기존 임시 clone을 최신 상태라고 가정하지 않는다.
- weekly-report 문서, 출력, 자동화 코드, test 및 log는 업로드하지 않는다.
- 제3자 Isaac Sim 설치본, cache, `__pycache__`, 개인 IDE 상태는 업로드하지
  않는다.
- force push, history rewrite, Git LFS migration, 라이선스 선택, 원격 파일 대량
  삭제는 별도 사용자 승인이 있어야 한다.

## 이번 정리 범위

### 포함

1. README를 `ViLaR_IMO` 연구 목적과 Warehouse 실험 중심으로 개편한다.
2. 실행 환경, 주요 구성 요소, 폴더 구조, Isaac Sim 실행 순서와 현재 제한을
   README에 정확히 기술한다.
3. `.idea/`와 USD `.thumbs/`를 GitHub에서 제거한다.
4. 세 개의 `warehouse_cart_worker.pre_*.usd`를
   `assets/isaac_sim/cart_simulation_env/backups/`로 이동한다.
5. Live 검증이 끝난 Warehouse NavMesh execution plan을 `completed/`로 이동한다.
6. 삭제된 발표 대본을 현재 산출물처럼 가리키는 presentation plan/spec 문구를
   과거 기록 또는 제거 상태로 수정한다.
7. Warehouse runtime script의 로컬 절대경로를 환경변수와 repository-relative
   기본값으로 교체한다.
8. GitHub 유지관리 지침을 `docs/automation/github-publishing.md`에 작성하고
   `docs/index.md`에서 연결한다.

### 제외

- ROS2 topic, HTTP endpoint, JSON schema, controller 동작 변경
- `ictc_test/`, `logs/`, `World.usd`, LIMO 참고자료의 대규모 이동
- 모델과 rosbag의 Git LFS 전환 또는 Git 이력 재작성
- 라이선스 자동 선택
- 원본 로컬 파일 변경

## 경로 이식성 설계

Warehouse runtime은 다음 우선순위로 경로를 결정한다.

1. 환경변수 `VILAR_WAREHOUSE_STAGE`와 `VILAR_WORKER_COMMAND_FILE`
2. clone 내부 `assets/isaac_sim/cart_simulation_env/warehouse_cart_worker.usd`와
   `worker_commands.txt`

환경변수가 없으면 repository clone의 asset을 사용한다. Stage precheck는 실제로
열린 Stage와 결정된 Stage 경로가 같은지 계속 검증한다. 자동 Play, 자동 Stage
저장, ROS2 publish 금지는 유지한다.

## README 자동 갱신 원칙

- README는 작업 시점의 production code, `ARCHITECTURE.md`, `docs/index.md`,
  experiment context를 읽은 뒤 임시 clone에서만 갱신한다.
- 구현되지 않은 future architecture를 현재 기능으로 표현하지 않는다.
- 실행 명령과 파일 경로는 clone에서 존재하는지 검증한다.
- 알려진 코드·문서 불일치는 제한 사항으로 표시한다.
- README를 변경하면 첫 줄의 KST `Last updated` 시간을 실제 수정 시각으로
  갱신한다.

## 향후 GitHub 작업 절차

1. 원본 프로젝트와 USD 상태를 read-only로 확인한다.
2. `/tmp`에 새 디렉터리를 만들고 `ViLaR_IMO`를 clone한다.
3. 원본에서 가져올 파일 목록과 제외 목록을 Preview한다.
4. 사용자가 승인한 파일만 임시 clone에 복사하거나 수정한다.
5. secret, 100MB 초과 파일, weekly-report 파일, cache와 절대경로를 검사한다.
6. `bash scripts/check.sh`와 `bash scripts/test_offline.sh`를 실행한다.
7. staged file 목록과 diff를 검토한다.
8. 임시 clone에서 commit하고 `ViLaR_IMO/main`에 push한다.
9. 원격 commit SHA와 로컬 임시 commit SHA가 같은지 확인한다.
10. 원본 프로젝트의 status와 remote가 작업 전 상태에서 변하지 않았는지
    read-only로 확인한다.

## 검증 기준

- 원본 프로젝트 및 원본 USD의 파일 내용과 Git 설정이 변경되지 않는다.
- README가 새 repository 이름, 현재 구조와 실행 절차를 설명한다.
- runtime path test가 환경변수 우선순위와 repository 기본 경로를 검증한다.
- 기존 Worker 왕복, NavMesh, Cart sync offline test가 유지된다.
- weekly-report 및 generated/cache 파일이 commit tree에 없다.
- 100MB 초과 파일과 secret pattern이 없다.
- 표준 offline 검사와 staged diff 검사가 통과한다.

## 위험과 제한

- USD 안에 authoring 당시 Isaac Sim asset 또는 behavior script 경로가 남아 있을
  수 있다. Python path 설정화만으로 모든 USD dependency의 이식성이 보장되지는
  않으므로 별도 inspection 결과를 README에 명시한다.
- 공개 저장소의 LIMO 문서, 모델 weight, rosbag 재배포 권한은 이번 작업에서
  확정하지 않는다. 라이선스 결정 전까지 이를 해결된 문제로 표현하지 않는다.
- 디렉터리 대규모 이동은 기존 연구 script를 깨뜨릴 수 있으므로 이번에는
  실행에 영향이 없는 정리만 수행한다.
