> Last updated: 2026-09-03 19:48 KST

# ViLaR IMO

LIMO, ROS2 Humble, NVIDIA Isaac Sim을 기반으로 Camera–2D LiDAR perception과 VLM-assisted Route 선택을 연구하는 실내 이동체 프로젝트다.

## 연구 목표

ViLaR IMO는 실내 이동체가 Camera, 2D LiDAR, Odometry로 주변을 인식하고 안전하게 정지·주행하는 현재 Baseline 위에서, 의미 기반 VLM 판단과 SLAM 기반 Path Planning, 이종 이동체 환경정보 공유를 단계적으로 비교하는 연구 저장소다.

- **현재 Baseline:** 미리 정의된 `wp1`–`wp5` Waypoint Route 중 Intent 또는 VLM이 Route를 선택하고 Point Follower 또는 Pure Pursuit가 추종한다.
- **연구 방향:** SLAM Map/Pose에서 Planner Candidate를 생성하는 기능과 여러 차량·로봇 사이의 양방향 환경정보 공유는 아직 production pipeline이 아닌 검증 예정 Candidate다.
- **원칙:** 기존 Baseline을 보존하고 동일 조건·지표로 Candidate를 비교하며, `offline -> replay -> Isaac Sim -> real LIMO` 순서로 검증한다.

세부 연구 질문과 단계는 [연구 방향](docs/research-direction.md), 평가 조건은 [실험 Protocol](docs/experiments/protocol.md)을 따른다.

## 현재 구현 범위

| 상태 | 구현 |
|---|---|
| 정적 소스 확인 | [`imo_server_lidar.py`](imo_server_lidar.py)가 `/sim/camera/color/image_raw`, `/sim/scan`, `/sim/odom`을 구독하고 `GET /video`, `/lidar`, `/odometry`로 제공한다. |
| 정적 소스 확인 | [`edge_control.py`](edge_control.py)가 YOLOv8s, Camera–2D LiDAR 거리 추정, 정지/VLM 판단, JSON·이미지 전송 worker를 시작한다. |
| 정적 소스 확인 | [`waypoint_tools/intent_decision.py`](waypoint_tools/intent_decision.py)와 [`vlm_server.py`](vlm_server.py)가 새 Path를 생성하지 않고 `wp1`–`wp5` 후보를 선택한다. |
| 정적 소스 확인 | [`waypoint_tools/point_follower.py`](waypoint_tools/point_follower.py)와 [`waypoint_tools/pure_pursuit_follower.py`](waypoint_tools/pure_pursuit_follower.py)가 `/selected_route` 또는 `/selected_route_goal`을 받아 `/sim/cmd_vel`을 발행한다. |
| 정적 소스 확인 | [`k8s_server.py`](k8s_server.py)가 `POST /inference`를 받아 `logs/json/`과 `logs/images/`에 로컬 저장한다. 다른 이동체로 재배포하는 인터페이스는 없다. |
| Live 검증 | Warehouse Worker–Cart의 고정 왕복, Cart/Pallet Pose 동기화, NavMesh 범위 유지, Stop 시 runtime override 해제를 Isaac Sim 4.5.0에서 사용자가 확인했다. |

전체 인터페이스와 소스 근거는 [ARCHITECTURE.md](ARCHITECTURE.md)에 정리되어 있다. 이 표의 정적 소스 확인은 통합 시스템의 Live 동작을 의미하지 않는다.

## 실행 환경

| 구성 | 기준 | 근거와 검증 범위 |
|---|---|---|
| OS | Ubuntu 22.04 | 프로젝트의 목표 실행 환경이다. 저장소 정적 검사만으로 설치 상태나 배포 Host의 실제 OS를 확인할 수 없다. |
| Python | Python 3.10 | 프로젝트의 목표 Interpreter다. Offline 검사는 `python3`를 사용하지만 실제 실행 전 `python3 --version`을 별도로 확인해야 한다. |
| Middleware | ROS2 Humble | 프로젝트의 목표 ROS2 배포판이다. 이번 저장소 검사는 ROS graph나 설치 상태를 Live 확인하지 않았다. |
| Simulator | NVIDIA Isaac Sim 4.5.0 | Warehouse 고정 왕복 범위는 사용자가 이 버전에서 Live 확인했다. 현재 설치본이나 전체 ViLaR IMO pipeline은 자동 검증하지 않았다. |
| Detection | Ultralytics YOLOv8s (`detector/yolov8s.pt`) | `edge_control.py`의 model 경로를 정적 소스로 확인했다. Model inference의 현재 장치·성능은 Live 검증하지 않았다. |
| VLM | Ollama `qwen2.5vl:3b` | `vlm_server.py`의 model 설정을 정적 소스로 확인했다. Ollama service와 model 설치·응답은 Live 검증하지 않았다. |

앞의 버전은 호환 대상으로 문서화한 기준이며, 정적 source/config 근거와 사용자
Live 확인은 같은 의미가 아니다. 실제 실행 환경은 승인된 검증 단계에서 별도로
확인한다.

## 전체 구조

```text
현재 Baseline
Camera / 2D LiDAR / Odometry
  -> imo_server_lidar.py (ROS2 -> HTTP)
  -> edge_control.py (YOLO + Camera–LiDAR fusion + stop/VLM decision)
       -> vlm_server.py (허용된 wp1–wp5 중 Route 선택)
       -> Point Follower 또는 Pure Pursuit -> /sim/cmd_vel
       -> k8s_server.py -> 로컬 JSON / image log

연구 방향
SLAM Map/Pose -> 안전한 Planner Candidate 생성 -> 제한된 VLM 선택
Dynamic Event -> 검증·통합 Server -> 다중 차량·로봇 Local Planning
```

VLM 선택은 현재 고정 Route Baseline의 일부지만, SLAM Candidate 생성과 multi-vehicle sharing은 연구 방향이다.

## Repository 구조

`git ls-tree -d --name-only HEAD` 기준 tracked 최상위 디렉터리와 주요 root 파일이다.

| 경로 | 역할 | 일반 사용 |
|---|---|---|
| [`.codex/`](.codex/) | 저장소용 Codex 설정과 명령 규칙 | 저장소 작업 도구의 안전·허용 명령 설정을 확인한다. |
| [`.vscode/`](.vscode/) | VS Code workspace 설정 | 편집기에서 저장소 공통 설정을 적용한다. |
| [`LIMO/`](LIMO/) | LIMO 제품·ROS2 참고 문서 | 하드웨어와 기존 자료를 참고하며 production code로 실행하지 않는다. |
| [`Robot Motion Control Meeting/`](<Robot Motion Control Meeting/>) | 과거 Robot Motion Control 회의 PDF | 원문 회의 기록을 조회한다. |
| [`artifacts/`](artifacts/) | 재현 가능한 실험 Run 보관 위치 | 새 결과를 `artifacts/runs/<run-id>/`에 보존한다. |
| [`assets/`](assets/) | 저장소에 포함된 Isaac Sim Warehouse USD, Backup, Worker command | Warehouse Stage를 열고 과거 USD 상태를 비교한다. |
| [`detector/`](detector/) | YOLO model weight | Edge detection model을 선택할 때 사용한다. 현재 launcher는 `yolov8s.pt`를 읽는다. |
| [`docs/`](docs/) | Architecture, Safety, Experiment, 연구·운영 문서 | [문서 Index](docs/index.md)에서 목적별 문서를 찾는다. |
| [`edge_modules/`](edge_modules/) | Edge 설정, HTTP helper, 공유 상태 | Edge worker가 공통 URL·threshold·상태를 사용할 때 import한다. |
| [`edge_threads/`](edge_threads/) | Sensor polling, inference, decision, log transmission worker | `edge_control.py`가 thread 단위로 시작한다. |
| [`ictc_test/`](ictc_test/) | 기록 rosbag, 평가 script, 표·plot | 기존 Controller·VLM 실험을 offline 분석할 때 사용한다. |
| [`logs/`](logs/) | 확인용 JSON·image sample log | Log schema와 이전 출력 예시를 검토한다. 새 실험 결과는 `artifacts/runs/`에 둔다. |
| [`ref_img/`](ref_img/) | 문서·검증 참고 이미지 | NavMesh 등 과거 시각 증거를 확인한다. |
| [`scripts/`](scripts/) | Offline 검사와 Warehouse Isaac Sim 자동화 | `check.sh`, `test_offline.sh` 또는 승인된 Script Editor 작업에 사용한다. |
| [`sensor/`](sensor/) | Camera FOV와 LiDAR 길이 조회 helper | `edge_control.py` 초기화에서 Sensor metadata를 조회한다. |
| [`tests/`](tests/) | Offline unit test | Live 시스템 없이 계산·자동화 계약을 검증한다. |
| [`waypoint_tools/`](waypoint_tools/) | 고정 Route, Intent 결정, Marker, 두 Route follower | 현재 Waypoint Baseline을 선택·시각화·추종한다. |
| [`README.md`](README.md) | 공개 프로젝트 시작점 | 목표, 현재 범위, 실행 경계와 문서 링크를 먼저 확인한다. |
| [`ARCHITECTURE.md`](ARCHITECTURE.md) | 정적 소스 기반 Architecture·Interface 감사 | 구현 주장과 Topic/HTTP 계약의 근거·한계를 확인한다. |
| [`AGENTS.md`](AGENTS.md) | 저장소 기여·안전 지침 | 변경이나 검증 전에 적용 범위의 규칙을 읽는다. |
| [`World.usd`](World.usd) | Root에 보존된 기존 Isaac Sim USD Stage | 해당 Stage의 Asset dependency와 목적을 확인한 뒤 별도 시나리오에서 사용한다. Warehouse 기본 Stage는 아니다. |
| [`edge_control.py`](edge_control.py) | Edge perception/decision pipeline launcher | Sensor server와 ROS2/VLM/logging 의존성을 확인하고 승인 후 실행한다. Import 시 Sensor 조회가 발생한다. |
| [`imo_server_lidar.py`](imo_server_lidar.py) | ROS2 Camera·LiDAR·Odometry를 HTTP로 노출하는 gateway | Robot/Simulator Sensor stream server가 필요할 때 승인 후 실행한다. |
| [`vlm_server.py`](vlm_server.py) | Ollama 기반 `POST /select_wp` server | 허용된 Waypoint 후보 중 VLM Route를 고르는 실험에 사용한다. |
| [`k8s_server.py`](k8s_server.py) | `POST /inference` JSON·image 로컬 저장 server | Edge payload를 `logs/`에 기록할 때 사용한다. |
| [`intent_server.py`](intent_server.py) | I2NSF YAML 수신용 legacy Flask server | 격리된 policy 실험에서만 사용한다. Import만 해도 server가 시작되고 `/received_policy.yaml`에 기록한다. |
| [`imo_control.py`](imo_control.py) | 거리 정지와 속도 명령용 Flask/ROS2 controller | 실제 `/cmd_vel` 제어가 필요한 승인된 실험에서 사용한다. `/sim/cmd_vel` publisher가 아니다. |
| [`received_policy.yaml`](received_policy.yaml) | 수신 I2NSF policy 예시 | Legacy policy 형식과 마지막 저장 예시를 확인한다. |

## Warehouse Worker–Cart 시나리오

현재 공개 Stage는 [`assets/isaac_sim/cart_simulation_env/warehouse_cart_worker.usd`](assets/isaac_sim/cart_simulation_env/warehouse_cart_worker.usd)이며, 통합 Bootstrap은 [`scripts/setup_warehouse_runtime.py`](scripts/setup_warehouse_runtime.py)다. Bootstrap은 Timeline이 멈춘 정확한 Stage와 필수 Prim을 확인한 뒤 `PRECHECK -> NAVMESH -> WORKER_BEHAVIOR -> CART_SYNC -> READY` 순서로 구성한다. 성공해도 Timeline을 Play하거나 Stage를 저장하지 않는다.

이 시나리오의 **약 6 m 이동·대기·출발점 복귀 Worker–Cart Baseline은 Live 검증됨**이다. 이는 ViLaR IMO 전체 perception/VLM/control pipeline의 통합 Live 검증이나 자유 순찰·SLAM 경로 생성 검증을 뜻하지 않는다. 세부 결과와 재개 절차는 [Warehouse Worker–Cart Context](docs/experiments/warehouse-cart-worker-context.md)를 참고한다.

USD 파일은 저장소 안에 있어도 NVIDIA 원격 Asset, 로컬 Isaac Sim Asset Pack, MDL/Texture 또는 `omni.anim.people` Behavior Script dependency를 유지할 수 있다. 다른 환경에서 열 때 누락된 Reference와 extension을 먼저 확인한다. 과거 Stage는 [`backups/`](assets/isaac_sim/cart_simulation_env/backups/)에 보존되어 있으며 기본 실행 대상으로 사용하지 않는다.

## 빠른 시작

먼저 저장소만 사용하는 offline 검사를 실행한다.

```bash
bash scripts/check.sh
bash scripts/test_offline.sh
```

Warehouse Live 절차는 Isaac Sim을 자동으로 시작하지 않는다. 사람의 검토와 승인을 받은 뒤 다음 순서를 사용한다.

1. Isaac Sim 4.5.0에서 `assets/isaac_sim/cart_simulation_env/warehouse_cart_worker.usd`를 열고 Asset loading을 기다린다.
2. Timeline을 `Stop` 상태로 유지한다.
3. Script Editor에서 아래의 `/absolute/path/to/ViLaR_IMO`를 실제 clone 절대 경로로 바꿔 실행한다.

   ```python
   import sys
   from pathlib import Path

   repo = Path("/absolute/path/to/ViLaR_IMO").resolve()
   if str(repo) not in sys.path:
       sys.path.insert(0, str(repo))
   exec((repo / "scripts/setup_warehouse_runtime.py").read_text(encoding="utf-8"))
   ```

4. Console의 단계별 `OK`와 `WAREHOUSE_RUNTIME_READY=...`를 검토한다.
5. `READY`가 확인된 뒤에만 사용자가 직접 Play한다. 오류가 나면 Play하지 않는다.

ROS2 node, Flask server, Ollama, Isaac Sim 또는 실제 LIMO를 시작하는 명령은 자동 검증에 포함되지 않는다. 각 entry point의 목적·의존성·motion 영향을 확인하고 명시적 승인을 받은 뒤 실행한다.

## 환경변수

환경변수는 선택 사항이다. 지정하지 않으면 clone 내부의 portable 기본 경로를 사용한다.

| 변수 | 기본값 | 용도 |
|---|---|---|
| `VILAR_WAREHOUSE_STAGE` | `assets/isaac_sim/cart_simulation_env/warehouse_cart_worker.usd` | Bootstrap이 허용할 작업 Stage를 override한다. 지정값은 절대 경로여야 한다. |
| `VILAR_WORKER_COMMAND_FILE` | `assets/isaac_sim/cart_simulation_env/worker_commands.txt` | People Simulation command file을 override한다. 지정값은 절대 경로여야 한다. |

Override가 필요하면 Isaac Sim을 시작하는 같은 환경에서 설정한다.

```bash
export VILAR_WAREHOUSE_STAGE="$PWD/assets/isaac_sim/cart_simulation_env/warehouse_cart_worker.usd"
export VILAR_WORKER_COMMAND_FILE="$PWD/assets/isaac_sim/cart_simulation_env/worker_commands.txt"
```

## 안전 원칙

- `/sim/cmd_vel` publisher는 한 번에 하나만 실행한다. 코드가 이를 자동 중재하지 않는다.
- VLM output이 invalid, unavailable 또는 timeout이면 정지를 유지하고 새 Route를 발행하지 않는 것이 요구 안전 동작이다.
- `/sim/cmd_vel`, `/selected_route`, `/selected_route_goal`, `/user_intent_goal`, `/navigation_stop`은 명시적 승인 없이 publish하지 않는다.
- 속도 제한과 정지 threshold를 승인 없이 높이거나 약화하지 않는다.
- Live 검증은 `offline -> replay -> Isaac Sim stopped-state -> low-speed single route -> full scenario -> real LIMO` 순서를 지킨다.
- Rosbag, log, model, dataset, USD Backup과 experiment artifact를 삭제하거나 덮어쓰지 않는다.

전체 규칙은 [Robot and Simulator Safety](docs/safety/robot-safety.md)를 따른다.

## 검증된 상태

- Camera/LiDAR/Odometry gateway, Edge worker 구성, 고정 Route/VLM 선택, 두 Controller, logging endpoint는 production code 정적 검사로 확인됐다.
- Warehouse Worker–Cart 통합 Bootstrap은 offline unit test와 사용자의 Isaac Sim 4.5.0 Live 검증 기록이 있다.
- Live 확인 범위는 고정 왕복 시나리오다. SLAM Planner Candidate, VLM Warehouse event 판단, 다중 이동체 정보 공유, 전체 LIMO pipeline의 end-to-end Live 검증은 완료되지 않았다.
- 저장소 검증 진입점은 `bash scripts/check.sh`와 `bash scripts/test_offline.sh`다. Live process는 두 command가 시작하지 않는다.

## 알려진 제한

- `edge_threads/infer_thread.py`에는 VLM 실패 후에도 중복 코드가 `wp_mode`를 켜고 `/selected_route`를 발행할 수 있는 경로가 있다. 요구 안전 동작과 불일치하므로 VLM/주행 실험 전에 수정·검증해야 한다.
- `k8s_server.py`는 JSON·image를 로컬 저장할 뿐, 다른 이동체가 조회하거나 Event를 수신하는 공유 interface를 제공하지 않는다. Multi-vehicle sharing은 연구 방향이다.
- `waypoint_tools/intent_decision.py`는 valid Intent의 상태 파일을 기록하지 않고 invalid Intent 경로에서 정의되지 않은 `self.current_intent_state_file`을 사용한다.
- Point Follower와 Pure Pursuit가 모두 `/sim/cmd_vel` publisher를 만들 수 있지만 단일 publisher를 강제하는 lock이나 launch arbitration은 없다.
- `edge_modules/config.py`의 Robot address와 여러 threshold는 source에 고정되어 있으며 실제 배포 환경을 자동 검증하지 않는다.
- USD는 외부 Isaac Sim Asset/Behavior dependency를 포함할 수 있고, NavMesh runtime setting과 Bake cache는 USD 저장만으로 재시작 후 동일 상태가 보장되지 않는다.

## 문서 안내

- [Documentation Index](docs/index.md): 전체 문서 지도
- [Architecture and Static Source Audit](ARCHITECTURE.md): 구현·Topic·HTTP·Schema 근거와 불일치
- [Robot and Simulator Safety](docs/safety/robot-safety.md): Live 실행 및 motion 승인 기준
- [Experiment Protocol](docs/experiments/protocol.md): Baseline/Candidate 비교와 결과 보존 규칙
- [Warehouse Worker–Cart Context](docs/experiments/warehouse-cart-worker-context.md): Live 검증 기록, Bootstrap과 제약
- [Research Direction](docs/research-direction.md): SLAM, VLM, I2ICF와 Agent Architecture 연구 범위
- [GitHub Publishing and Maintenance](docs/automation/github-publishing.md): `/tmp` clone, secret/size 검사, 별도 push 승인 절차
