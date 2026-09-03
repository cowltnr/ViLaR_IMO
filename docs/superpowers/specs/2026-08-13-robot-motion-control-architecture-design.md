> Last updated: 2026-08-15 21:16 KST

# Robot Motion Control Architecture Image Design

## Goal

Create two project-local PNG architecture diagrams under `ictc_test/` using
`ictc_test/overview.png` as the visual and compositional reference and
`ictc_test/IETF125.png` as the control-command flow reference:

1. A current-state diagram grounded in the executable repository code.
2. A target-state conceptual diagram that adds future control capabilities and
   clearly distinguishes them from current behavior.

The diagrams explain the system from the robot motion-control perspective. They
do not claim that the simulator, ROS2 graph, servers, or robot were run.

## Deliverables

- `ictc_test/robot_motion_control_current.png`
- `ictc_test/robot_motion_control_future.png`

Both images use the reference canvas aspect ratio of approximately 1843:926 and
English labels to match `overview.png`.

## Shared visual language

- White background and a wide landscape canvas.
- Large rounded containers with medium-gray outlines and soft shadows.
- Light blue for sensing and state feedback.
- Light yellow for decisions, safety, and command arbitration.
- Light green for route planning and VLM assistance.
- Light purple for motion controllers and actuation.
- Thick solid gray arrows for active command/data flow.
- Colored dotted arrows for advisory, logging, or shared-environment flow.
- Match `overview.png` before introducing any new color. When an additional
  semantic color is necessary, use a low-saturation pastel tint: muted salmon
  for faults, soft sky blue for feedback, sage green for advisory/target, and
  subdued lavender for interface badges. Avoid saturated primary colors.
- A black dotted rounded boundary for the ego-vehicle system.
- Compact, readable typography with short labels; no paragraphs inside boxes.
- Similar spatial structure in both images so they can be compared directly.

## Current-state diagram

### Layout

- Top: `Cloud / Edge Services`, containing `User Intent`, `VLM Route Selection`,
  and `JSON + Image Logs`.
- Left: `1. Sensing & Perception`, containing Camera, 2D LiDAR, Odometry, YOLO
  Detection, Camera–LiDAR Fusion, and the resulting perception/ego state.
- Center: `2. Route & Safety Decision`, containing intent parsing, candidate
  route matching, obstacle thresholds, emergency stop, and alternative-route
  selection.
- Lower center: `3. Motion Controller`, showing `Point Follower` and
  `Pure Pursuit` as alternative selectable controllers, not simultaneous
  publishers.
- Right: `4. Robot Actuation`, containing `/sim/cmd_vel`, Speed / Steering, and
  the Ego Vehicle.
- Bottom feedback path: robot pose and TF feedback (`odom → base_link`) returns
  to the controller and perception/state area.

### Exact interfaces to show

- `/user_intent_goal`
- `/selected_route`
- `/selected_route_goal`
- `/navigation_stop`
- `/sim/cmd_vel`

### ROS2 subscription view

- `RobotStreamer` subscribes to `/sim/camera/color/image_raw`, `/sim/scan`, and
  `/sim/odom`.
- `IntentDecisionNode` subscribes to `/user_intent_goal` and publishes
  `/selected_route` plus `/intent_feedback`.
- The selected `Point Follower` or `Pure Pursuit` controller subscribes to
  `/selected_route`, `/selected_route_goal`, and `/navigation_stop`.
- Each follower obtains pose through TF lookup `odom → base_link` rather than a
  direct odometry-topic subscription.
- The selected follower publishes `/sim/cmd_vel` as `geometry_msgs/Twist`.

### Control-command view

Adapt the command concept shown in `IETF125.png` to the executable code's
current interfaces, while keeping the inactive YAML path separate:
`/user_intent_goal → IntentDecisionNode → Selected Route / Goal → Selected
Follower → Twist /sim/cmd_vel`. Edge safety adds `Safety Stop` and
`Emergency Stop` through `/navigation_stop`. Do not show `Continue` as an edge
publication and do not reproduce obsolete endpoint names as current ROS2
topics.

### Safety semantics

- Emergency-stop input has visual priority over route-following commands.
- Invalid route input causes the follower to stop.
- A prominent note states: `Only one controller may publish /sim/cmd_vel`.
- A small `Implementation Caveat` callout records that current
  `edge_threads/infer_thread.py` can duplicate `/selected_route` publication
  after VLM handling. The caveat is separated from the intended normal flow.

## Target-state conceptual diagram

### Layout

Use the same major left/center/right placement as the current-state diagram,
but title the center stack `Hierarchical Motion Control` and include:

- `Mission & Intent Manager`
- `Deterministic Safety Supervisor`
- `Global Route Planner`
- `VLM Route Advisor`
- `Local Trajectory Planner & Obstacle Avoidance`
- `Controller Manager`
- `Point Follower`, `Pure Pursuit`, and `MPC (Target)` controller choices
- `Command Arbitration — Single /sim/cmd_vel Publisher`
- `State Estimation & Health Monitor`
- `Fallback Controller / Safe Stop`
- `Shared Environment & Multi-Robot Coordination`

The target-state image keeps the same `SUB`, `PUB`, and `TF` badges for current
interfaces. `Command Arbitration` is the only future `PUB /sim/cmd_vel` point;
no unimplemented ROS2 topic name is invented for proposed components.

### Current-versus-target distinction

- Existing repository capabilities use solid borders.
- Proposed capabilities use dotted borders and a visible `Target` tag.
- The VLM remains an advisor; deterministic validation and the Safety
  Supervisor gate all motion resumption.
- Command Arbitration is the sole motion-command output path.
- Missing sensors, invalid VLM output, controller faults, or stale state lead to
  `Safe Stop`, never an unvalidated motion command.

## Content accuracy boundaries

- The current-state image follows production source rather than README claims
  where they disagree.
- `/sim/cmd_vel` is used for the documented simulator followers; the image does
  not imply that `imo_control.py` publishes that topic.
- Cloud log sharing to other robots is not shown as implemented behavior because
  the repository currently provides local writes but no verified retrieval or
  distribution endpoint.
- Live availability and runtime QoS/TF connectivity are not claimed.

## Acceptance criteria

- Both PNG files exist under `ictc_test/` and open successfully.
- Their aspect ratio and visual style are recognizably aligned with
  `overview.png`.
- Major boxes and arrows remain legible at full resolution.
- All required current ROS2 topic labels are spelled exactly.
- Subscriber, publisher, and TF relationships are visually distinguishable.
- Current and target capabilities cannot be mistaken for each other.
- Both selectable followers are visible, with single-publisher safety called
  out.
- No live ROS2, Isaac Sim, Flask, Ollama, or robot process is started.

## Validation

Inspect the generated images at original resolution for composition, text
accuracy, clipped content, unreadable labels, and confusing arrow direction.
Use file metadata to confirm PNG format and dimensions. If generation distorts
critical interface text, regenerate with a targeted correction rather than
accepting ambiguous labels.

## 2026-08-15 code-accuracy correction

The two existing PNGs require a targeted correction pass. Preserve their
layout, palette, curvature, typography, ROS2 badge system, and file names while
changing the following content.

### Robot-side process boundary

Show a compact implementation boundary in the current-state image because it
explains how ROS2 sensor topics become the HTTP inputs used by the edge
pipeline:

- `ROS2 Sensor Process` subscribes to `/sim/odom`,
  `/sim/camera/color/image_raw`, and `/sim/scan`.
- `Flask HTTP Sensor Gateway` exposes `/video`, `/odometry`,
  and `/lidar`.
- The boundary between them is labeled `Queue / Shared State`.
- Do not place `multiprocessing.Process`, `Manager dict`, or edge-thread details
  in the main diagram. They are implementation details rather than motion
  control concepts.
- In the target-state image, collapse the same current capability into one
  solid `ROS2-to-HTTP Sensor Gateway` box.

This process detail remains compact and subordinate to the motion-control flow.

### Corrected current-state content

- Separate `Intent YAML Server` from the active ROS2 control path and mark it
  `Separate / not connected to active control path`.
- Show the active intent path as `/user_intent_goal → IntentDecisionNode →
  /selected_route → selected follower`.
- Show `/tmp/current_intent_state.json` as `Partially Implemented`; do not draw
  a verified normal-flow arrow from `IntentDecisionNode` to the edge decision.
- Remove the normal `Continue` command arrow. The edge code publishes
  `/navigation_stop` with `stop`; it does not publish `resume` or `Continue`.
- Separate `VLM Route Selection` from edge-owned stop/detour activation.
- Replace the absolute claim that one controller is active with
  `Operational Constraint: run only one controller` and
  `No code-level command arbitration`.
- Keep both implementation caveats visible: duplicate `/selected_route`
  publication after VLM handling, and incomplete current-intent-state writing.

### Corrected target-state content

Use the legend literally:

- Solid current capabilities: robot-side ROS2/Flask sensor gateway, YOLO and
  Camera–LiDAR fusion, `IntentDecisionNode`, predefined route matching, current
  VLM route selection, threshold stop checks, Point Follower, Pure Pursuit, and
  direct follower `/sim/cmd_vel` publication.
- Dotted `Target` capabilities: Mission & Intent Manager, true Global Route
  Planner, Local Trajectory Planner & Obstacle Avoidance, Deterministic Safety
  Supervisor, State Estimation & Health Monitor, Controller Manager, MPC,
  Fallback Controller / Safe Stop, Command Arbitration, and Shared Environment
  & Multi-Robot Coordination.
- Current `VLM Route Selection` feeds a proposed deterministic validator. It is
  not labeled as a target-only capability and never connects directly to robot
  actuation.
- Clearly distinguish the current direct follower publisher behavior from the
  target single-publisher arbitration behavior.

### Correction acceptance criteria

- Every solid/dotted classification agrees with executable source or is
  explicitly qualified as an abstraction.
- No arrow claims that the edge publishes `Continue` or `resume`.
- The current sensor ROS2-to-HTTP process boundary is accurate and compact,
  while the target image uses the approved gateway abstraction.
- The diagrams do not imply code-level controller exclusion or command
  arbitration in the current implementation.
- Both corrected images remain readable at 1672×941 or an equivalent landscape
  resolution and retain the `overview.png` pastel visual language.
