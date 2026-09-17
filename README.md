> Last updated: 2026-09-17 20:12 KST

# SDV Robocar Framework — Semantic-Dynamic Map Branch

Camera–2D LiDAR fusion, obstacle-aware stopping, VLM-based route selection, waypoint following 구조를 유지하면서, Static Map과 Semantic-Dynamic Map 기능을 추가한 LIMO Robot용 Isaac Sim / ROS2 Framework입니다.

이 브랜치는 기존 Main Branch의 SDV Robocar Framework를 기반으로 다음 기능을 확장합니다.

- Shared Static Occupancy Map
- Dynamic Object의 Global Map Localization
- Semantic Object 표현
- Object Table 기반 상태 관리
- Object-level Delta Update
- Semantic-Dynamic Grid
- RViz 기반 Semantic Map Visualization
- ROS2 Workspace 기반 Repository 구조 정리

---

## Environment

```text
Ubuntu 22.04
ROS2 Humble
NVIDIA Isaac Sim 4.5.0
Python 3.10
Ultralytics YOLOv8s
Ollama-based VLM server (qwen2.5vl:3b)
```

---

## 1. Framework Overview

이 브랜치에서는 기존 Framework의 Perception–Decision–VLM–Control 구조를 유지하면서, 검출된 Dynamic Object를 Global Map에 반영하기 위한 Mapping Layer를 추가했습니다.

1. **Perception**
   - Camera, 2D LiDAR, Odometry 정보를 수신합니다.
   - YOLO 기반 Object Detection을 수행합니다.
   - Camera Bounding Box와 2D LiDAR를 이용해 Person Distance를 추정합니다.
   - Detection Timestamp와 Robot Pose 정보를 함께 유지하여 Global Localization에 사용합니다.

2. **Decision**
   - User Intent를 수신하고 Waypoint Route 가능 여부를 확인합니다.
   - 장애물 검출 시 Robot을 정지시키고 필요할 경우 VLM 기반 대체 경로를 선택합니다.
   - 선택된 Route와 Goal을 Waypoint Follower에 전달합니다.

3. **Semantic Mapping**
   - `/dynamic_object_detection`의 객체 정보를 Global `map` Frame으로 변환합니다.
   - Semantic Object를 Object Table에 등록합니다.
   - Object 상태를 `CREATE`, `UPDATE`, `DELETE`로 관리합니다.
   - 변경된 Object 정보만 Semantic-Dynamic Grid에 반영합니다.

4. **VLM / Shared Environment Update**
   - VLM 기반 Alternative Route Selection 기능을 유지합니다.
   - 기존 JSON / Image Log 저장 구조를 유지합니다.
   - Semantic Mapping Layer는 기존 Framework와 독립적으로 추가되어 함께 실행됩니다.

---

## 2. Framework Flow

```text
Sensor Input
  └── Camera / 2D LiDAR / Odometry
        ↓
Perception Processing
  └── YOLO Detection + Camera–LiDAR Distance Estimation
        ↓
/dynamic_object_detection
        ↓
Semantic Localization
  └── Object position in global map frame
        ↓
/semantic_object
        ↓
Object Table
  └── CREATE / UPDATE / DELETE
        ↓
/object_delta
        ↓
Semantic-Dynamic Grid
  ├── /semantic_dynamic_grid
  └── /semantic_dynamic_grid_viz
        ↓
RViz

Decision / Navigation
  └── User Intent → Route Selection → Pure Pursuit → /sim/cmd_vel
```

Static Map은 별도로 관리합니다.

```text
mapping/maps/static/static_map.yaml
        ↓
nav2_map_server
        ↓
/map
```

---

## 3. Perception Layer

기존 Main Branch의 Camera–2D LiDAR Fusion 구조를 유지합니다.

### Sensor Inputs

| Sensor | Role |
|---|---|
| Camera | YOLO Object Detection 및 VLM Context Input |
| 2D LiDAR | Object Distance Estimation |
| Odometry | Robot Pose / Speed 확인 및 Global Localization 검증 |

### Detection Output 확장

기존 Detection 정보:

```text
class
confidence
bbox
distance
angle
```

Semantic-Dynamic Map을 위해 다음 정보를 추가로 사용합니다.

```text
LiDAR ROS Timestamp
Odometry ROS Timestamp
Robot Pose
```

Detection 결과는 다음 Topic으로 전달합니다.

```text
/dynamic_object_detection
```

---

## 4. Decision Layer

기존 Main Branch의 Intent Decision 및 VLM 기반 Alternative Route Selection 구조를 유지합니다.

### 주요 Decision Topic

| Topic | Role |
|---|---|
| `/user_intent_goal` | User Goal 입력 |
| `/intent_feedback` | Goal 가능 여부 Feedback |
| `/navigation_stop` | 장애물 발생 시 Stop / Resume |
| `/selected_route` | 선택된 Waypoint Route |
| `/selected_route_goal` | 선택된 Route + Final Goal |
| `/sim/cmd_vel` | Robot Velocity Command |

Goal-aware Navigation에서는 다음 형식으로 Route와 Goal을 전달합니다.

```text
/selected_route_goal <- wp_name;x,y
```

---

## 5. Semantic Mapping Layer

### Semantic Localization

`semantic_localization_node.py`는 검출 객체의 거리와 방향을 이용해 `laser_link` 기준 위치를 계산하고, Detection 시점의 TF를 이용해 Global `map` Frame으로 변환합니다.

입력:

```text
/dynamic_object_detection
```

출력:

```text
/dynamic_object
/dynamic_object_marker
/semantic_object
```

### Object Table

`object_table_node.py`는 `/semantic_object`를 입력으로 받아 객체 상태를 관리합니다.

```text
CREATE = 0
UPDATE = 1
DELETE = 2
```

현재 V1에서는 upstream에서 `closest_person` 하나만 전달하므로 임시 Object ID를 사용합니다.

```text
person_0
```

TTL 동안 객체가 다시 검출되지 않으면 `DELETE`를 발행합니다.

```text
/object_delta
```

### Semantic-Dynamic Grid

`semantic_dynamic_grid_node.py`는 `/object_delta`를 입력으로 받아 현재 Object 상태를 Grid에 반영합니다.

현재 Encoding:

```text
-1 = Unknown / Unobserved
 0 = Observed Free
 1 = Person
 2+ = Additional Semantic Class
```

Semantic Object는 다음 방식으로 Encoding합니다.

```text
grid_value = class_id + 1
```

현재 `person`은:

```text
class_id = 0
grid_value = 1
```

로 표현됩니다.

RViz에서는 Custom Message를 직접 표시하지 않고, 별도 OccupancyGrid Topic을 사용합니다.

```text
/semantic_dynamic_grid_viz
```

---

## 6. Control Layer

기존 Main Branch의 Waypoint Following 구조를 유지합니다.

이 브랜치에서는 `waypoint_tools`를 정식 ROS2 Package 구조로 이동했습니다.

```text
nav2_ws/src/waypoint_tools/
```

주요 파일:

| File | Role |
|---|---|
| `intent_decision.py` | User Goal과 Route 가능 여부 확인 |
| `pure_pursuit_follower.py` | 선택된 Route를 따라 Goal까지 주행 |
| `point_follower.py` | Point 기반 주행 |
| `marker.py` | Waypoint / Route RViz Visualization |
| `waypoint_routes/routes.py` | `wp1`–`wp5` Route 좌표 정의 |

---

## 7. Static Map and Shared Map

이 브랜치에서는 여러 Robot이 동일한 기준 Map을 사용할 수 있도록 Static Occupancy Map을 별도로 관리합니다.

```text
mapping/maps/static/
├── static_map.png
└── static_map.yaml
```

Static Map은 `nav2_map_server`를 통해 `/map`으로 Publish합니다.

```text
/map
```

현재 Semantic-Dynamic Grid는 Static Map의:

```text
origin
resolution
width
height
```

정보를 그대로 사용합니다.

Global Map Position을 Grid Cell로 변환하는 기본식:

```text
grid_x = floor((map_x - origin_x) / resolution)
grid_y = floor((map_y - origin_y) / resolution)
```

---

## 8. Information Shared with Other Modules

Semantic Mapping Layer에서 공유하는 핵심 정보는 다음과 같습니다.

- Dynamic Object의 Global Position
- Semantic Class
- Confidence
- Object ID
- Last Seen Timestamp
- Source Robot
- Object State Change
- Semantic Grid Position

Object 단위 변경 정보는 다음 Topic을 통해 전달합니다.

```text
/object_delta
```

현재 상태 변화:

```text
CREATE
UPDATE
DELETE
```

전체 Map을 매번 갱신하는 대신 변경된 Object 상태를 기준으로 Semantic-Dynamic Grid를 갱신합니다.

---

## 9. Framework Modules

| Framework block | Main file | Role |
|---|---|---|
| Sensor streaming | `imo_server_lidar.py` | Camera, Odometry, LiDAR Data 제공 |
| Perception processing | `edge_threads/infer_thread.py` | YOLO Detection 및 Camera–LiDAR Fusion |
| Edge launcher | `edge_control.py` | Edge Thread 실행 및 종료 관리 |
| VLM reasoning | `vlm_server.py` | Alternative Route Selection |
| Cloud logging | `k8s_server.py` | JSON / Image Log 저장 |
| Intent feasibility | `nav2_ws/src/waypoint_tools/waypoint_tools/intent_decision.py` | Goal / Route 가능 여부 판단 |
| Route following | `nav2_ws/src/waypoint_tools/waypoint_tools/pure_pursuit_follower.py` | Pure Pursuit 기반 Route 주행 |
| Route definition | `nav2_ws/src/waypoint_tools/waypoint_tools/waypoint_routes/routes.py` | Route 좌표 정의 |
| Semantic localization | `mapping/ros2_ws/src/robot_motion_map/robot_motion_map/semantic_localization_node.py` | Dynamic Object Global Localization |
| Object state management | `mapping/ros2_ws/src/robot_motion_map/robot_motion_map/object_table_node.py` | Object CREATE / UPDATE / DELETE 관리 |
| Semantic grid | `mapping/ros2_ws/src/robot_motion_map/robot_motion_map/semantic_dynamic_grid_node.py` | Semantic-Dynamic Grid 생성 |
| Legacy dynamic grid | `mapping/ros2_ws/src/robot_motion_map/robot_motion_map/dynamic_grid_node.py` | 기존 Dynamic Grid 비교용 유지 |

---

## 10. Main Topics and Interfaces

### ROS2 Topics

| Topic | Purpose |
|---|---|
| `/map` | Static Occupancy Map |
| `/dynamic_object_detection` | Detection + LiDAR Fusion Result |
| `/dynamic_object` | Legacy Global Object Position |
| `/dynamic_object_marker` | RViz Marker |
| `/semantic_object` | Global Semantic Object |
| `/object_delta` | CREATE / UPDATE / DELETE |
| `/semantic_dynamic_grid` | Custom Semantic-Dynamic Grid |
| `/semantic_dynamic_grid_viz` | RViz용 Semantic Grid |
| `/dynamic_grid` | 기존 Dynamic Grid |
| `/user_intent_goal` | User Navigation Goal |
| `/selected_route` | Selected Waypoint Route |
| `/selected_route_goal` | Selected Route + Final Goal |
| `/navigation_stop` | Stop / Resume |
| `/sim/cmd_vel` | Robot Velocity Command |

### Custom ROS2 Messages

추가된 Message Package:

```text
mapping/ros2_ws/src/robot_motion_interfaces/
```

Message:

```text
SemanticObject.msg
ObjectState.msg
ObjectDelta.msg
SemanticDynamicGrid.msg
```

---

## 11. ROS2 Package Build

이 브랜치에서는 ROS2 Package를 두 Workspace로 관리합니다.

### Waypoint Workspace

Repository Root 기준:

```bash
cd nav2_ws
source /opt/ros/humble/setup.bash

colcon build --symlink-install

cd ..
```

### Mapping Workspace

```bash
cd mapping/ros2_ws
source /opt/ros/humble/setup.bash
source ../../../nav2_ws/install/setup.bash

colcon build --symlink-install

cd ../../..
```

주요 Package:

```text
nav2_ws/src/waypoint_tools
mapping/ros2_ws/src/robot_motion_interfaces
mapping/ros2_ws/src/robot_motion_map
```

---

## 12. Execution Order

전체 시스템은 `all_system.launch.py`를 통해 한 번에 실행할 수 있습니다.

### [Step 1.] Isaac Sim 실행

Isaac Sim에서 LIMO Robot Scene을 Load하고 ROS2 Bridge를 활성화한 뒤 Simulation을 시작합니다.

주요 Topic이 정상적으로 Publish되는지 확인합니다.

```text
/sim/scan
/sim/odom
/tf
/sim/cmd_vel
```

### [Step 2.] Workspace Source

Repository Root에서 실행합니다.

```bash
source /opt/ros/humble/setup.bash
source ./nav2_ws/install/setup.bash
source ./mapping/ros2_ws/install/setup.bash
```

### [Step 3.] 전체 시스템 실행

```bash
ros2 launch robot_motion_map all_system.launch.py
```

자동 실행되는 주요 구성:

```text
Timestamp Sync
map → odom TF
Static Map Server
Lifecycle Manager
Semantic Localization
Object Table
Semantic-Dynamic Grid
Dynamic Grid
Intent Decision
Pure Pursuit
RViz

LiDAR / Odometry Server
K8s Server
Ollama
VLM Server
Edge Control
```

Ollama를 제외하려면:

```bash
ros2 launch robot_motion_map all_system.launch.py \
  launch_ollama:=false
```

RViz도 제외하려면:

```bash
ros2 launch robot_motion_map all_system.launch.py \
  launch_ollama:=false \
  launch_rviz:=false
```

### [Step 4.] User Goal 발행

새 Terminal에서 Repository Root 기준으로 Workspace를 Source합니다.

```bash
source /opt/ros/humble/setup.bash
source ./nav2_ws/install/setup.bash
source ./mapping/ros2_ws/install/setup.bash
```

Goal 발행:

```bash
ros2 topic pub --once \
  /user_intent_goal \
  std_msgs/msg/String \
  "{data: '11.0,0.0'}"
```

### [Step 5.] Semantic-Dynamic Map 확인

Semantic Object:

```bash
ros2 topic echo /semantic_object
```

Object Delta:

```bash
ros2 topic echo /object_delta
```

Semantic-Dynamic Grid:

```bash
ros2 topic echo /semantic_dynamic_grid --once
```

RViz용 Semantic Grid:

```bash
ros2 topic echo /semantic_dynamic_grid_viz --once
```

기존 Dynamic Grid:

```bash
ros2 topic echo /dynamic_grid --once
```

Node 확인:

```bash
ros2 node list
```

### [Step 6.] RViz 확인

`all_system.launch.py` 사용 시 RViz는 자동 실행됩니다.

권장 설정:

```text
Fixed Frame
  map

Static Map
  Topic: /map
  Durability: Transient Local

Semantic Dynamic Grid
  Topic: /semantic_dynamic_grid_viz
  Durability: Transient Local

Person Marker
  Topic: /dynamic_object_marker

Dynamic Grid
  Topic: /dynamic_grid
  Optional
```

---

## Summary

이 브랜치는 기존 SDV Robocar Framework의 Camera–2D LiDAR Fusion, VLM 기반 Route Selection, Waypoint Following 구조를 유지하면서 Semantic-Dynamic Map 기능을 추가합니다.

현재 전체 흐름:

```text
Dynamic Object Detection
        ↓
Global Semantic Localization
        ↓
Object Table
        ↓
CREATE / UPDATE / DELETE
        ↓
Semantic-Dynamic Grid
        ↓
RViz Visualization
```

또한 실제 Build 및 실행 방식에 맞춰:

```text
nav2_ws/src/waypoint_tools
mapping/ros2_ws/src/robot_motion_interfaces
mapping/ros2_ws/src/robot_motion_map
```

형태로 Repository 구조를 재정리했습니다.

현재 Branch에서는 다음 항목까지 검증되었습니다.

```text
nav2_ws Build                     OK
mapping/ros2_ws Build             OK
all_system.launch.py              OK
Semantic Object                   OK
Object CREATE / UPDATE / DELETE   OK
Semantic-Dynamic Grid             OK
RViz Visualization               OK
```

현재 제한 사항:

- Perception Pipeline은 아직 `closest_person` 하나만 ROS2로 전달
- `person_0`은 임시 Object ID
- Multi-Object Detection / Tracking은 후속 연구
- Sensor LOS/FOV 기반 Observed Free 영역 계산은 후속 연구
