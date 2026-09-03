> Last updated: 2026-08-15 21:16 KST

# Architecture Arrow Clarity Design

## Goal

Make every arrow in `robot_motion_control_current.png` and `robot_motion_control_future.png` terminate at an identifiable producer or consumer, point in the implemented data-flow direction, and distinguish current code from proposed target behavior.

## Current diagram connection rules

- `Flask HTTP Gateway — Main Process` connects directly to `YOLO + Camera–LiDAR Fusion` through the three shown HTTP GET inputs.
- `YOLO + Camera–LiDAR Fusion` connects to `Edge Safety Decision`; it does not connect to `IntentDecisionNode`.
- `ROS2 User Goal` connects to `IntentDecisionNode` through `/user_intent_goal`.
- `IntentDecisionNode` publishes `/selected_route` to the selected motion controller and has a partially implemented state-file path to `Edge Safety Decision` through `/tmp/current_intent_state.json`.
- `Edge Safety Decision` connects bidirectionally to `VLM Route Selection`: request `POST /select_wp`, response `selected_wp + reason`.
- `Edge Safety Decision` connects directly to `JSON + Image Logs` with `POST /inference`.
- Route output `/selected_route` or `/selected_route_goal` reaches the selected controller.
- Both stop conditions converge on `/navigation_stop = "stop"`, consumed by either controller:
  - route-select stop: person distance `≤ 6.0 m`, stop before requesting VLM;
  - emergency stop: person distance `≤ 1.2 m`, always active including waypoint mode.
- The selected controller publishes `/sim/cmd_vel` to robot actuation; TF feedback `odom → base_link` points back from robot/simulator state to the controller.

## Target diagram connection rules

- Solid arrows show current code; dotted green arrows show proposed behavior; blue dashed arrows show state/TF feedback.
- The current sensor, inference, VLM, log, route-topic, stop-topic, controller, `/sim/cmd_vel`, and TF paths follow the same direction as the current diagram.
- Current ROS2 control inputs point into Point Follower and Pure Pursuit, not away from them.
- Target planning is a continuous path: Shared Environment / Mission Manager → Global Route Planner → Local Trajectory Planner → Deterministic Safety Supervisor → Controller Manager → internal velocity proposal → Command Arbitration → Robot Actuation.
- State Estimation receives robot/simulator feedback and feeds the local planner and deterministic safety supervisor.
- VLM current request/result connects to threshold/edge inference; VLM advisory also connects to the proposed deterministic safety supervisor.
- Fault inputs connect to `Fallback Controller / Safe Stop`, which connects to the deterministic safety supervisor and arbitration path.
- Current `POST /inference` must end at `JSON + Image Logs (Current)`.

## Visual constraints

- Preserve 1672×941 dimensions, all existing box content, RobotLAB LIMO image, rounded geometry, pastel palette, and legend semantics.
- Remove orphan line segments and crossing paths whose endpoints cannot be identified.
- Keep labels adjacent to their own arrows and use junction nodes or buses only when all branches are labeled.

## Verification

- Inspect both PNGs at original resolution.
- Trace every line from start to arrowhead and check it against this specification.
- Update `robot_motion_control_architecture_explanation.txt` for the clarified stop and VLM paths.
- Run `bash scripts/check.sh` and `bash scripts/test_offline.sh` without starting live robot services.
