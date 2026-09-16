"""Warehouse roaming parameters. Importing this file does not start motion."""

# 재현 가능한 무작위 목적지 선택.
# 같은 seed여도 장면이나 후보 거절 결과가 바뀌면 경로는 달라질 수 있습니다.
RANDOM_SEED = 42
ENABLED = True  # False preserves stack-then-wait behavior.

# 현재 위치에서 다음 목적지까지의 수평 거리 범위.
MIN_GOAL_DISTANCE_M = 3.0
MAX_GOAL_DISTANCE_M = 10.0

# 한 번에 검사할 목적지 후보 수.
# 한 프레임에 전부 처리하지 않고 하나씩 처리하도록 사용합니다.
MAX_GOAL_ATTEMPTS = 30

# 후보 좌표를 NavMesh에 투영했을 때 허용할 오차.
MAX_NAVMESH_SNAP_M = 0.15

# 기존 분석으로 확인했던 바닥 외곽 범위.
# 이 사각형 내부라고 모두 통행 가능한 것은 아닙니다.
WAREHOUSE_X_RANGE = (-28.0, 8.0)
WAREHOUSE_Y_RANGE = (-23.4, 30.6)

# 목적지를 찾지 못했을 때 재탐색 전 대기.
RETRY_SECONDS = 2.0

# 이동 완료 판정과 이동 시간 상한.
ARRIVAL_TOLERANCE_M = 0.20
MOVE_TIMEOUT_SECONDS = 90.0

# Footprint queries use the existing inflated NavMesh, not a replacement Bake.
FOOTPRINT_GRID_M = 0.30
PATH_SAMPLE_M = 0.20
TURN_SAMPLE_DEG = 5.0
FOOTPRINT_SNAP_M = 0.10
GUARD_STEPS_PER_FRAME = 4
GUARD_FRAME_BUDGET_SECONDS = .006
MAX_GUARD_POSES = 3000
DOCK_POSITION_TOLERANCE_M = .10
DOCK_ANGLE_TOLERANCE_DEG = 5.0
ALIGN_RATE_DEG_S = 45.0
MAX_RUNTIME_STEP_M = .50
MAX_RUNTIME_TURN_DEG = 30.0
